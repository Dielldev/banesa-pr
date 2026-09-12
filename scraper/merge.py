"""Combine the three scrape outputs into one de-duplicated pool.

Sources overlap: an agency's stock shows up both in the Pristina category crawl
and on its own MerrJep storefront (same ad id), and sometimes again on the
agency's own website (different id, same flat).
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hoods
import merrjep

DATA = merrjep.DATA

# the agencies the user asked to prioritise -> canonical display name
PRIORITY = {
    "the-best-real-estate":       "THE BEST REAL ESTATE L.L.C",
    "prishtina-real-estate-llc":  "Prishtina Real Estate L.L.C",
    "agjensioni-pro-real-estate": "Pro Real Estate",
    "ea-real-estate-l-l-c":       "EA Real Estate L.L.C",
    "domino":                     "Real Estate Domino",
    "asr-real-estate":            "ASR Real Estate",
}
PRIORITY_SITES = {"Anem Real Estate", "IN Real Estate", "Prishtina Real Estate L.L.C"}


def load(name):
    p = os.path.join(DATA, name)
    return json.load(open(p)) if os.path.exists(p) else []


def main():
    pool, by_id = [], {}

    # storefront rows are richer (they carry priority_agency), so they win ties
    for rows in (load("raw_agencies.json"), load("raw_merrjep.json"),
                 load("raw_sites.json"), load("raw_prishtina_io.json")):
        for r in rows:
            rid = r.get("id")
            if not rid:
                continue
            if rid in by_id:
                cur = by_id[rid]
                for k, v in r.items():          # fill gaps without overwriting
                    if cur.get(k) in (None, "", []) and v not in (None, "", []):
                        cur[k] = v
                continue
            by_id[rid] = r
            pool.append(r)

    for r in pool:
        slug = r.get("agency_slug")
        name = PRIORITY.get(slug) or (r.get("agency_name") if r.get("agency_name") in PRIORITY_SITES else None)
        r["priority_agency"] = name
        r["is_priority"] = bool(name)
        if not r.get("hood"):
            r["hood"], r["tier"] = hoods.detect(r.get("title"), r.get("description"))

    # a flat listed on both MerrJep and the agency's own site: same money, same size
    seen, uniq = set(), []
    for r in pool:
        p, a = r.get("price"), r.get("area")
        key = (round(p), round(a), r.get("hood")) if (p and a) else None
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        uniq.append(r)

    json.dump(uniq, open(os.path.join(DATA, "raw_all.json"), "w"), ensure_ascii=False)
    prio = sum(1 for r in uniq if r["is_priority"])
    print(f"merged {len(pool)} -> {len(uniq)} unique ({prio} from priority agencies)")


if __name__ == "__main__":
    main()
