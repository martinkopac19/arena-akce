# Akcie v halách – PWA

Jednoduchá PWA appka, ktorá ukazuje **dnešné a zajtrajšie** akcie v:

- **O2 arena** – zdroj: <https://www.o2arena.cz/events/>
- **O2 universum** – zdroj: <https://www.o2universum.cz/events/>
- **UNYP Arena** – zdroj: [GoOut](https://goout.net/cs/unyp-arena/vziwqe/) (oficiálny web haly kalendár akcií nemá)

## Ako to funguje

Prehliadač nemôže kvôli CORS sťahovať cudzie weby priamo, preto:

1. GitHub Action `.github/workflows/deploy.yml` každé 3 hodiny spustí
   `scraper/scrape.py` (čistý Python, bez závislostí), ktorý vytvorí `app/events.json`.
2. Obsah `app/` sa nasadí na GitHub Pages.
3. Appka si načíta `events.json` a vyfiltruje akcie na dnes / zajtra (pražský čas).
   Service worker drží appku aj posledné dáta offline.

## Spustenie

1. Kód je na vetve `main` (naplánované spúšťanie funguje len na predvolenej vetve).
2. V repozitári: **Settings → Pages → Build and deployment → Source: GitHub Actions**.
3. **Actions → „Akcie v halách (PWA)“ → Run workflow** (prvé nasadenie).
4. Otvor `https://martinkopac19.github.io/arena-akce/` na mobile a daj **Pridať na plochu**.

## Lokálne

```sh
python3 scraper/scrape.py app/events.json
cd app && python3 -m http.server 8000   # http://localhost:8000
```
