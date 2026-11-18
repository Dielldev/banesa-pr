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

## The app

React 19 + TypeScript (strict) + Vite, with Leaflet for the map. The UI follows the
"Housi" listing layout: card list on the left, price-pin map on the right, a Map/Grid
toggle, and a filter sheet. On a phone it collapses to a single column with a floating
Map/List switch.

```bash
npm install
npm run dev        # http://localhost:5173
npm run build      # typecheck + production build -> dist/
npm run data       # rebuild public/data/listings.json from data/listings.json
npm run fetch      # fetch new listings (see below)
```

Photos load as sharp 480px images straight from the source host, painted over a
low-res placeholder cut from the sprite sheets in `public/sprites/` (so cards are never
blank, and still show a photo if the source host is down).

**Map pins are per-lagje, not per-address** — the ads carry no coordinates. Each listing
is placed at a stable spot inside its lagje, so a pin tells you the neighbourhood only.

## Fetching new listings

Works like jobscrape's "Fetch new jobs": one command that only does the work that's new.

```bash
npm run fetch          # quick: new ads only — seconds, a handful of requests
npm run fetch:full     # deep sweep of every source, then removes ads that vanished
npm run test:scraper   # offline tests for the updater
```

`scraper/update.py` keeps `data/store.json`: every ad it has accepted (raw, un-scored) **and** every ad it
looked at and rejected (rentals, other lagje), so it only fetches pages it has never seen.

| Source | Quick run | Full run |
|---|---|---|
| MerrJep category (newest first) | walks pages until two batches in a row hold nothing unknown | all 150 pages |
| MerrJep agency storefronts | – (not date-ordered) | every page of the 6 priority agencies |
| prishtina.io | diffs the sitemap, fetches only new property pages | same |
| Anem / IN Real Estate | first pages until nothing is new | every page |

Beyond finding new ads, it also picks up **price drops** (shown as a ↓ chip on the card and `price_was`) and
re-posts (new date). A **"New"** badge marks ads first seen in the last two days.

Safety: a source that fails is reported and skipped (its rows are kept); ads are removed only after a *complete,
error-free* full sweep hasn't seen them for 21 days (10 for the agency sites), and never more than 40% of a
source at once (`--force-prune` overrides after you've checked). `--budget MIN` stops cleanly so an interrupted
catch-up resumes next time. A run that finds nothing writes no files.

Other flags: `--only merrjep,prishtina_io`, `--pages N`, `--rebuild` (re-score from the store, offline),
`--forget-skipped` (re-judge rejected ads after you change `hoods.py`).

### Hosting it for free

1. Deploy to Vercel as before (it already redeploys from every push to `main`).
2. `.github/workflows/update-listings.yml` does the rest, on GitHub's free runners: a **quick** update every
   hour and a **full** sweep on Sundays. It commits `data/store.json` and `public/data/*.json` only when
   something changed, and that push is what redeploys the site. Nothing to configure or pay for (the repo is
   public, so Actions minutes are unlimited).
3. Run it on demand: GitHub → Actions → **Update listings** → *Run workflow* (pick `quick` or `full`). The
   run's summary page shows per-source results.

Open tabs notice new data on their own (they poll a 100-byte `meta.json`) and show a "N new listings added" toast.

If a source blocks GitHub's IP range, its row in the run summary shows `error` and the old data stays live;
run `npm run fetch` from your own machine, commit, and push instead. GitHub pauses scheduled workflows after
60 days without repository activity, so an abandoned repo would stop updating.

### The Update button

The **Update** button (top right, a blue pill) opens a sheet with one big *Check for new listings* button.

- **Without setup** it fetches the newest published data right now. Open tabs also do this by themselves every
  10 minutes and whenever you come back to the tab, and a toast says how many listings were added.
- **With one setup step** it also starts a scrape on demand: it triggers the GitHub workflow, shows progress
  ("Searching the listing sites…", about 1–3 minutes), then swaps the new listings in without a reload, or says
  *you're up to date*. Starting a scrape is limited to one every 5 minutes, no matter how many people tap it.

To switch on the on-demand part (once):

1. GitHub → Settings → Developer settings → Personal access tokens → **Fine-grained tokens** → Generate.
   Repository access: **Only select repositories → banesa-pr**. Permissions → Repository → **Actions: Read and write**.
2. Vercel → the `banesa-pr` project → Settings → Environment Variables → add `GH_DISPATCH_TOKEN` with that token
   (Production). Then redeploy (Deployments → ⋯ → Redeploy).

The token can only start and read workflow runs on this one repository. The function is `api/refresh.js`.

### On a phone

It's built for phones first: one column of cards, a Map / Grid switch, bottom-sheet filters, and a big **Call**
button on every listing. To put it on the home screen: iPhone → Safari → Share → *Add to Home Screen*; Android →
Chrome menu → *Install app*. It then opens full screen like an app.

### Rebuilding from scratch

The old step-by-step pipeline still works and is useful for a clean re-crawl (the store seeds itself from
`data/raw_*.json` when `data/store.json` doesn't exist):

```bash
cd scraper
PAGES=150 python3 run.py && python3 patch_prices.py && python3 storefront.py
python3 prishtina_io.py && python3 sites.py && python3 merge.py
rm ../data/store.json && python3 update.py --rebuild     # seed the store from those files
python3 images.py                                        # optional: low-res photo placeholders
```

New ads found by the updater have no sprite placeholder (the real photo still loads from the source host);
`images.py` can be re-run to add them.

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
src/
  main.tsx, App.tsx      app shell, state, URL sync
  types.ts               Listing / Filters types
  data.ts                fetches /data/listings.json
  lib/
    filters.ts           filtering, sorting, URL <-> filter state
    geo.ts               lagje centres and per-listing pin placement
    dates.ts, format.ts, photo.ts, hooks.ts
  components/            Header, Toolbar, ListingCard, MapView, MapPopup,
                         FilterSheet, UpdateSheet, DetailDrawer, SortMenu, ...
  styles/app.css         design tokens + all styles
public/
  data/listings.json     generated by scraper/build_site.py
  sprites/               placeholder photo sheets
api/refresh.js           Vercel function behind the Update button
scraper/                 update.py (incremental), plus crawl/merge/rank/build (Python)
data/                    store.json (committed state) + scrape intermediates (not deployed)
.github/workflows/       scheduled free refresh
```
