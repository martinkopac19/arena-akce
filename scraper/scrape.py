#!/usr/bin/env python3
"""Stiahne program akcií O2 arena, O2 universum a UNYP Arena do events.json.

Zdroje:
  * O2 arena      – https://www.o2arena.cz/events/      (HTML zoznam)
  * O2 universum  – https://www.o2universum.cz/events/  (HTML zoznam)
  * UNYP Arena    – GoOut API (oficiálny web nemá kalendár akcií)
                    + domáce zápasy florbalovej Sparty (muži A, ženy A)
                    + domáce zápasy VK Lvi Praha (volejbal, muži aj ženy)

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


SPARTA_FLORBAL = "https://www.sparta-florbal.cz"
SPARTA_TEAMS = ("/tym/436-muzi-a", "/tym/439-zeny-a")
FLORBAL_DATE_RE = re.compile(r"(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{4})(?:\s+(\d{1,2}):(\d{2}))?")


def scrape_sparta_florbal():
    """Domáce zápasy ACEMA Sparta Praha v UNYP Arene (zo zoznamu zápasov tímu)."""
    out = []
    for team in SPARTA_TEAMS:
        page = fetch(f"{SPARTA_FLORBAL}{team}/zapasy")
        for item in page.split('<a href="')[1:]:
            if 'team-game-item' not in item[:300]:
                continue
            href = item[:item.index('"')]
            date = re.search(r'<span class="date-small[^"]*">([^<]+)</span>', item)
            place = re.search(r'<span class="place-divider[^"]*">[^<]*</span><span>([^<]*)</span>', item)
            comp = re.search(r'<span class="competition-divider[^"]*">[^<]*</span><span[^>]*>([^<]*)</span>', item)
            teams = [clean(t) for t in re.findall(r'<strong class="[^"]*">(.*?)</strong>', item, re.S)][:2]
            if not (date and place and len(teams) == 2) or "UNYP" not in place.group(1).upper():
                continue
            m = FLORBAL_DATE_RE.search(date.group(1))
            if not m:
                continue
            d, mo, y, hh, mm = m.groups()
            dt = datetime(int(y), int(mo), int(d), int(hh or 0), int(mm or 0), tzinfo=PRAGUE)
            competition = clean(comp.group(1)) if comp else ""
            if "zeny" in team:
                competition = ("Ženy – " + competition) if competition else "Ženy"
            out.append({
                "venue": "unyp",
                "tag": "Florbal",
                "title": f"{teams[0]} – {teams[1]}",
                "start": dt.isoformat(),
                "date": dt.date().isoformat(),
                "hasTime": bool(hh),
                "url": SPARTA_FLORBAL + href if href.startswith("/") else href,
                "image": None,
                "description": competition,
            })
    return out


LVI_URL = "https://www.vklvipraha.cz/"
CZ_MONTHS = {"leden": 1, "unor": 2, "brezen": 3, "duben": 4, "kveten": 5, "cerven": 6,
             "cervenec": 7, "srpen": 8, "zari": 9, "rijen": 10, "listopad": 11, "prosinec": 12}
_ASCII = str.maketrans("áčďéěíňóřšťúůýžÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ", "acdeeinorstuuyzACDEEINORSTUUYZ")
MATCH_RE = re.compile(r"(\d{1,2})[.:](\d{2})\s+([^,()]+?)\s*(?:,|$)")


def _pretty(name):
    name = re.sub(r"\s+-\s+", " – ", name.strip())
    if not name.isupper():
        return name
    # "LVICE – KP BRNO" -> "Lvice – KP Brno" (krátke skratky ponecháme veľkými)
    return " ".join(w if len(w) <= 2 else w.capitalize() for w in name.split(" "))


def scrape_lvi_volejbal():
    """Domáce zápasy VK Lvi Praha v UNYP Arene z 'Kalendáře akcí' na webe klubu.

    Formáty riadkov:
      "extraliga mužů: Lvi - Karlovarsko (18.30 Unyp arena)"
      "DVOJUTKÁNÍ V UNYP ARENĚ: 17.00 LVICE - KP BRNO, 19.30 LVI - AERO"
    Rok v kalendári nie je – dopočítame ho (mesiac v minulosti => budúci rok).
    """
    page = fetch(LVI_URL)
    now = datetime.now(PRAGUE)
    out = []
    rows = re.findall(r'<p class="day">\s*(\d{1,2})\s*</p>\s*<p class="month">\s*([^<]+?)\s*</p>\s*</td>\s*'
                      r'<td class="text">(.*?)</td>', page, re.S)
    for day, month_name, text in rows:
        text = clean(text)
        month = CZ_MONTHS.get(month_name.lower().translate(_ASCII))
        if not month or "unyp" not in text.lower():
            continue
        year = now.year + (1 if month < now.month - 2 else 0)
        label, _, rest = text.partition(":")
        if "dvojutk" in label.lower().translate(_ASCII):
            matches = MATCH_RE.findall(rest)
            competition = "Dvojzápas"
        else:
            m = re.search(r"\((\d{1,2})[.:](\d{2})", rest)
            matches = [(m.group(1), m.group(2), rest[:m.start()])] if m else []
            competition = label.strip()
            competition = competition[:1].upper() + competition[1:]
        for hh, mm, name in matches:
            dt = datetime(year, month, int(day), int(hh), int(mm), tzinfo=PRAGUE)
            out.append({
                "venue": "unyp",
                "tag": "Volejbal",
                "title": _pretty(name),
                "start": dt.isoformat(),
                "date": dt.date().isoformat(),
                "hasTime": True,
                "url": LVI_URL,
                "image": None,
                "description": competition,
            })
    return out


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else "events.json"
    all_events, errors = [], {}
    for key, fn in (("o2arena", lambda: scrape_o2("o2arena")),
                    ("o2universum", lambda: scrape_o2("o2universum")),
                    ("unyp", scrape_unyp),
                    ("unyp-florbal", scrape_sparta_florbal),
                    ("unyp-volejbal", scrape_lvi_volejbal)):
        try:
            evs = fn()
            print(f"{key}: {len(evs)} termínov zo zdroja", file=sys.stderr)
            all_events.extend(evs)
        except Exception as exc:  # jeden zlyhaný zdroj nemá zhodiť ostatné
            errors[key] = str(exc)
            print(f"{key}: CHYBA {exc}", file=sys.stderr)

    # necháme len termíny od včera ďalej (kvôli časovým pásmam), deduplikácia.
    # V UNYP Arene nemôžu byť dve akcie v rovnakom čase – ak GoOut uvádza aj
    # zápas z klubového webu, ponecháme klubový záznam (má súpera a súťaž).
    cutoff = (datetime.now(PRAGUE) - timedelta(days=1)).date().isoformat()
    seen, events = set(), []
    for e in sorted(all_events, key=lambda e: (e["start"], e["venue"], "tag" not in e)):
        k = (e["venue"], e["start"]) if e["venue"] == "unyp" and e["hasTime"] else (e["venue"], e["start"], e["title"])
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
    if len(errors) == 5:
        sys.exit(1)


if __name__ == "__main__":
    main()
