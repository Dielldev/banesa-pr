# Banesa — Prishtina e Re

Ranked board of apartments for sale in **Prishtina e Re** and the adjacent lagje.

Sources, in priority order:

| Source | What it covers |
|---|---|
| MerrJep category crawl | all Pristina apartment ads, 150 pages deep |
| MerrJep agency storefronts | Pro Real Estate (213 pages), Domino (77), ASR, THE BEST, EA |
| prishtina.io | Prishtina Real Estate — structured records, exact m²/price/floor |
| anem-ks.com | Anem Real Estate |
| inrealestate-ks.com | IN Real Estate |

Photos are downloaded and packed into sprite sheets under `sprites/`, because a
published artifact cannot hotlink `media.merrjep.com` (blocked by the page CSP)
and can only publish 255 files per version.

Open `index.html` in a browser — it is self-contained, no server needed.

## Refresh the data

```bash
cd scraper
PAGES=150 python3 run.py        # MerrJep category crawl (~20 min)
python3 patch_prices.py         # backfill per-m² prices the card omits
python3 storefront.py           # the priority agencies' MerrJep storefronts
python3 prishtina_io.py         # Prishtina Real Estate
python3 sites.py                # Anem + IN Real Estate (slow on purpose: their WAFs ban bursts)
python3 merge.py                # combine + de-duplicate -> data/raw_all.json
python3 rank.py                 # score and rank -> data/listings.json
python3 images.py               # download photos -> sprites/ (cached in /tmp)
python3 build_site.py           # -> index.html and artifact.html
```

`PAGES` controls crawl depth; 150 pages reaches roughly two months back.

## How the ranking works

Every listing is scored 0–100:

| Component | Max | Basis |
|---|---|---|
| Value | 70 | €/m² against the **median for that lagje** — a 40% discount maxes it |
| Quality | 16 | new build, parking, elevator, renovated, balcony, heating, basement |
| Freshness | 6 | listed within 7 / 30 / 90 days |
| Seller | 3 | verified company storefront rather than a private post |
| Priority agency | 5 | the agencies picked for this search |

Comparing against the lagje median rather than a city-wide one stops cheap
outskirts stock from crowding out genuine bargains in expensive streets.

## Data caveats

These are **asking prices**, not valuations.

- About a third of ads quote **no total price**; many state a €/m² figure instead,
  which the scraper uses (shown with `~` when the total is derived from it).
- Sizes come from the ad text. Where an ad quotes several conflicting m² figures
  (duplex splits, gross vs. net), the listing is tagged **size unclear**, kept out
  of the median, and its value bonus is halved.
- Ads whose body names another municipality (Podujevë, Fushë Kosovë, Ferizaj…)
  are dropped, since agencies reuse Pristina lagje names in unrelated posts.
- Neighbourhood is inferred from the ad text; the title wins over the body.

Always verify the *fletë poseduese* and view the property before committing.

## Layout

```
scraper/
  common.py         HTTP, text, price/area/room/date parsers, scope guards
  hoods.py          lagje detection and core/nearby tiers
  merrjep.py        list-page and detail-page (JSON-LD) parsing
  run.py            crawl -> detail pipeline
  patch_prices.py   per-m² price backfill
  rank.py           scoring -> data/listings.json
  build_site.py     inlines data into the page template
  site_template.html
data/               scraped + ranked JSON
index.html          the site (standalone)
artifact.html       body-only form for publishing
```
