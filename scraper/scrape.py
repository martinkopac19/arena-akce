#!/usr/bin/env python3
"""Stiahne program akcií O2 arena, O2 universum a UNYP Arena do events.json.

Zdroje:
  * O2 arena      – https://www.o2arena.cz/events/      (HTML zoznam)
  * O2 universum  – https://www.o2universum.cz/events/  (HTML zoznam)
  * UNYP Arena    – GoOut API (oficiálny web nemá kalendár akcií)

Iba štandardná knižnica Pythonu. Použitie:
  python3 scrape.py [výstupný_súbor]
"""
import html
import json
import re
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

PRAGUE = ZoneInfo("Europe/Prague")
UA = "Mozilla/5.0 (compatible; arena-akce/1.0)"
GOOUT_UNYP_VENUE_ID = 73058

VENUES = {
    "o2arena": {"name": "O2 arena", "url": "https://www.o2arena.cz/events/"},
    "o2universum": {"name": "O2 universum", "url": "https://www.o2universum.cz/events/"},
    "unyp": {"name": "UNYP Arena", "url": "https://goout.net/cs/unyp-arena/vziwqe/"},
}


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "cs"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")


def clean(text):
    text = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


DATE_RE = re.compile(r"(\d{1,2})\.(\d{1,2})\.(\d{4})(?:\s+(\d{1,2}):(\d{2}))?")


def scrape_o2(venue_key):
    """O2 arena a O2 universum bežia na rovnakom WordPress šablóne.

    Oba weby zobrazujú spoločný program oboch hál – miesto konania sa
    preto určuje podľa domény odkazu na akciu (o2arena.cz / o2universum.cz).
    """
    page = fetch(VENUES[venue_key]["url"])
    events = []
    for block in page.split('<div class="event_preview')[1:]:
        link = re.search(r'<h3>\s*<a href="([^"]+)"[^>]*>(.*?)</a>', block, re.S)
        time_p = re.search(r'<p class="time">(.*?)</p>', block, re.S)
        if not link or not time_p:
            continue
        img = re.search(r"url\((https?://[^)]+)\)", block)
        perex = re.search(r'<p class="perex">(.*?)</p>', block, re.S)
        title = clean(link.group(2))
        href = link.group(1)
        venue = "o2universum" if "o2universum.cz" in href else "o2arena" if "o2arena.cz" in href else venue_key
        for d, m, y, hh, mm in DATE_RE.findall(time_p.group(1)):
            has_time = bool(hh)
            dt = datetime(int(y), int(m), int(d), int(hh or 0), int(mm or 0), tzinfo=PRAGUE)
            events.append({
                "venue": venue,
                "title": title,
                "start": dt.isoformat(),
                "date": dt.date().isoformat(),
                "hasTime": has_time,
                "url": href,
                "image": img.group(1) if img else None,
                "description": clean(perex.group(1)) if perex else "",
            })
    return events


def scrape_unyp():
    url = (
        "https://goout.net/services/entities/v1/schedules"
        f"?languages[]=cs&venueIds[]={GOOUT_UNYP_VENUE_ID}&include=events,images"
    )
    data = json.loads(fetch(url))
    inc = data.get("included", {})
    events_by_id = {e["id"]: e for e in inc.get("events", [])}
    images_by_id = {i["id"]: i for i in inc.get("images", [])}
    out = []
    for s in data.get("schedules", []):
        attrs = s.get("attributes", {})
        if attrs.get("state") not in (None, "approved"):
            continue
        rel = s.get("relationships", {})
        ev = events_by_id.get((rel.get("event") or {}).get("id"), {})
        loc = (ev.get("locales") or {}).get("cs") or next(iter((ev.get("locales") or {}).values()), {})
        img = None
        for ref in (ev.get("relationships") or {}).get("images", []):
            if ref["id"] in images_by_id:
                img = images_by_id[ref["id"]]["attributes"].get("url")
                break
        start = datetime.fromisoformat(attrs["startAt"]).astimezone(PRAGUE)
        s_loc = (s.get("locales") or {}).get("cs") or {}
        out.append({
            "venue": "unyp",
            "title": loc.get("name") or "Akce",
            "start": start.isoformat(),
            "date": start.date().isoformat(),
            "hasTime": bool(attrs.get("hasTime", True)),
            "url": s_loc.get("siteUrl") or s.get("url"),
            "image": img,
            "description": clean(loc.get("description", ""))[:220],
            "pricing": attrs.get("pricing"),
        })
    return out


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else "events.json"
    all_events, errors = [], {}
    for key, fn in (("o2arena", lambda: scrape_o2("o2arena")),
                    ("o2universum", lambda: scrape_o2("o2universum")),
                    ("unyp", scrape_unyp)):
        try:
            evs = fn()
            print(f"{key}: {len(evs)} termínov zo zdroja", file=sys.stderr)
            all_events.extend(evs)
        except Exception as exc:  # jeden zlyhaný zdroj nemá zhodiť ostatné
            errors[key] = str(exc)
            print(f"{key}: CHYBA {exc}", file=sys.stderr)

    # necháme len termíny od včera ďalej (kvôli časovým pásmam), deduplikácia
    cutoff = (datetime.now(PRAGUE) - timedelta(days=1)).date().isoformat()
    seen, events = set(), []
    for e in sorted(all_events, key=lambda e: (e["start"], e["venue"])):
        k = (e["venue"], e["start"], e["title"])
        if e["date"] >= cutoff and k not in seen:
            seen.add(k)
            events.append(e)

    result = {
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "venues": {k: v for k, v in VENUES.items()},
        "errors": errors,
        "events": events,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    print(f"Zapísaných {len(events)} termínov do {out_path}", file=sys.stderr)
    if len(errors) == 3:
        sys.exit(1)


if __name__ == "__main__":
    main()
