"""Persistent state for the incremental updater: data/store.json.

The store is what makes "fetch new listings" possible. It remembers every listing
the scrapers have accepted (raw, un-scored rows plus bookkeeping) and every ad that
was looked at and rejected, so a run only has to touch what it has not seen.

    listings  id -> raw row + first_seen / last_seen / date (+ price_prev / price_changed)
    skipped   id -> last-seen date, for ads that are rentals / other lagje / not apartments

It is written one record per line so git diffs (and the Actions bot's commits) stay small.
"""
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
import hoods
import merrjep

DATA = merrjep.DATA
PATH = os.path.join(DATA, "store.json")
VERSION = 1

# An ad that is out of scope is remembered this long after it was last seen.
SKIP_TTL_DAYS = 150


def today_iso():
    return datetime.date.today().isoformat()


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def empty():
    return {"version": VERSION, "updated": None, "last_full": None, "last_run": None,
            "skipped": {}, "listings": {}}


def load(path=PATH):
    if not os.path.exists(path):
        return empty()
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    store = empty()
    store.update({k: raw.get(k) for k in ("version", "updated", "last_full", "last_run")})
    store["skipped"] = {i: d for i, d in raw.get("skipped", [])}
    store["listings"] = {r["id"]: r for r in raw.get("listings", [])}
    return store


def _line(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def save(store, path=PATH):
    """Atomic write, one record per line, stable ordering (so unchanged rows never diff)."""
    head = [f'"{k}":{_line(store.get(k))}' for k in ("version", "updated", "last_full", "last_run")]
    skipped = [_line([i, d]) for i, d in sorted(store["skipped"].items())]
    rows = [_line(r) for _, r in sorted(store["listings"].items())]
    body = ",\n".join(head) + ',\n"skipped":[\n' + ",\n".join(skipped) + '\n],\n"listings":[\n' + ",\n".join(rows) + "\n]\n"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("{\n" + body + "}\n")
    os.replace(tmp, path)


def known_ids(store):
    return set(store["listings"]) | set(store["skipped"])


def prune_skipped(store, today=None):
    cutoff = ((today or datetime.date.today()) - datetime.timedelta(days=SKIP_TTL_DAYS)).isoformat()
    stale = [i for i, d in store["skipped"].items() if d < cutoff]
    for i in stale:
        del store["skipped"][i]
    return len(stale)


# fields rank.py computes; never persisted, always recomputed from the raw row
DERIVED = {"eur_m2", "per_m2_stated", "area_uncertain", "suspect_price", "hood_median_eur_m2", "benchmark",
           "discount_pct", "score", "score_reason", "score_parts", "days_old", "price_derived", "agency",
           "is_priority", "priority_agency", "price_was"}


# --- seeding from the legacy raw_*.json files ---------------------------------

def _load_json(name):
    p = os.path.join(DATA, name)
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else []


def seed_from_raw():
    """Build a store from the pre-existing scrape (raw_*.json + the ranked listings.json,
    which remembers each ad's publication date as of the day it was crawled)."""
    from merge import fill_gaps          # local import: merge pulls in hoods/merrjep only

    store = empty()
    ranked = {}
    ranked_path = os.path.join(DATA, "listings.json")
    seed_day = today_iso()
    if os.path.exists(ranked_path):
        old = json.load(open(ranked_path, encoding="utf-8"))
        ranked = {r["id"]: r for r in old.get("listings", [])}
        seed_day = (old.get("generated") or seed_day)[:10]

    by_id = {}
    # raw_all.json (the merged union) last: it still holds rows a later partial re-crawl replaced
    for name in ("raw_agencies.json", "raw_merrjep.json", "raw_sites.json", "raw_prishtina_io.json", "raw_all.json"):
        for r in _load_json(name):
            rid = r.get("id")
            if not rid:
                continue
            if rid in by_id:
                fill_gaps(by_id[rid], r)
            else:
                by_id[rid] = r

    # ads that only survive in the ranked file (a later partial re-crawl replaced their raw row)
    for rid, l in ranked.items():
        if rid not in by_id:
            by_id[rid] = {k: v for k, v in l.items() if k not in DERIVED}
            if l.get("price_derived"):
                by_id[rid]["price"] = None      # that total was computed from a per-m² figure, not scraped

    today = today_iso()
    for rid, r in by_id.items():
        if not r.get("hood"):
            r["hood"], r["tier"] = hoods.detect(r.get("title"), r.get("description"))
        if r.get("is_rental") or r.get("tier") not in ("core", "nearby"):
            store["skipped"][rid] = today
            continue
        r["date"] = (ranked.get(rid) or {}).get("date") or common.parse_posted(r.get("posted", ""), datetime.date.fromisoformat(seed_day))
        r["first_seen"] = seed_day + "T00:00:00+00:00"
        # dated to the old crawl, so the first complete sweep can tell which ads have since vanished
        r["last_seen"] = seed_day
        store["listings"][rid] = r
    return store
