"""Scrape a MerrJep agency storefront end to end.

Storefront pages use different markup from the category listing, but the ad
pages behind them are identical, so detail parsing is shared with merrjep.py.
"""
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
import merrjep

BASE = "https://www.merrjep.com"
CARD = re.compile(r'(?=<div class="bootstrap4 row border m-0 search-result)')

# merrjep slug -> the name the user asked for
AGENCIES = {
    "the-best-real-estate":       "THE BEST REAL ESTATE L.L.C",
    "prishtina-real-estate-llc":  "Prishtina Real Estate L.L.C",
    "agjensioni-pro-real-estate": "Pro Real Estate",
    "ea-real-estate-l-l-c":       "EA Real Estate L.L.C",
    "domino":                     "Real Estate Domino",
    "asr-real-estate":            "ASR Real Estate",
}

# storefronts are not date-ordered, so a page cap drops listings arbitrarily:
# crawl each one to its real end
DEPTH = {"agjensioni-pro-real-estate": 220, "domino": 85, "asr-real-estate": 60}


def parse_store_page(html_text, slug):
    out = []
    for card in CARD.split(html_text)[1:]:
        link = re.search(r'href="(/shpallja/([^"/]+)/(\d+))"', card)
        if not link:
            continue
        cats = re.findall(r'<a class="nobold"[^>]*>(.*?)</a>', card, re.S)
        cats = [common.text(c) for c in cats]
        title_m = re.search(r'<a[^>]*class="[^"]*Link_vis[^"]*"[^>]*title="([^"]*)"', card)
        if not title_m:
            title_m = re.search(r'title="([^"]{4,160})"', card)
        price_m = re.search(r'([\d\s.,]{3,12})\s*EUR', card)
        date_m = re.search(r'>\s*((?:Sot|Dje|\d{1,2}\s+[a-zë]{3,5})\s+\d{1,2}:\d{2})\s*<', card)
        img = re.search(r'data-src="(https://media\.merrjep\.com/[^"]+)"', card)
        out.append({
            "id": "mj-" + link.group(3),
            "source": "MerrJep",
            "url": BASE + link.group(1),
            "title": common.text(title_m.group(1)) if title_m else "",
            "price": common.parse_price(price_m.group(1)) if price_m else None,
            "agency_slug": slug,
            "posted": date_m.group(1) if date_m else "",
            "image": img.group(1) if img else None,
            "store_category": cats[0] if cats else "",
            "store_location": cats[1] if len(cats) > 1 else "",
        })
    return out


def crawl_store(slug, max_pages=60):
    stubs, seen = [], set()
    for p in range(1, max_pages + 1):
        url = f"{BASE}/{slug}" + ("" if p == 1 else f"?Page={p}")
        h = common.fetch(url)
        if not h:
            break
        page = parse_store_page(h, slug)
        fresh = [s for s in page if s["id"] not in seen]
        if not fresh:
            break
        for s in fresh:
            seen.add(s["id"])
        stubs.extend(fresh)
        if len(page) < 40:      # short page = last page
            break
    return stubs


def is_apartment(stub):
    cat = (stub.get("store_category") or "").lower()
    loc = (stub.get("store_location") or "").lower()
    if "prishtin" not in loc:
        return False
    if cat and not re.search(r"banes|apartament", cat):
        return False
    return True


def main():
    all_stubs = []
    for slug, name in AGENCIES.items():
        s = crawl_store(slug, max_pages=DEPTH.get(slug, 60))
        apts = [x for x in s if is_apartment(x)]
        print(f"  {name:32} {len(s):5} ads -> {len(apts):4} Pristina apartments", flush=True)
        all_stubs.extend(apts)

    seen, uniq = set(), []
    for s in all_stubs:
        if s["id"] not in seen:
            seen.add(s["id"])
            uniq.append(s)
    # the Pristina category crawl already fetched many of these ads; reuse them
    cache = {}
    for fn in ("raw_merrjep.json", "raw_agencies.json"):
        prev = os.path.join(merrjep.DATA, fn)
        if os.path.exists(prev):
            for r in json.load(open(prev)):
                if r.get("area") is not None or r.get("description"):
                    cache[r["id"]] = r
    todo = [s for s in uniq if s["id"] not in cache]
    reused = [{**cache[s["id"]], **{k: v for k, v in s.items() if v not in (None, "", [])}}
              for s in uniq if s["id"] in cache]
    print(f"[detail] {len(reused)} reused from earlier crawl, fetching {len(todo)}...", flush=True)
    full = reused + merrjep.details(todo, workers=8)
    for r in full:
        r["priority_agency"] = AGENCIES.get(r.get("agency_slug"))
    json.dump(full, open(os.path.join(merrjep.DATA, "raw_agencies.json"), "w"), ensure_ascii=False)
    kept = [r for r in full if not r.get("is_rental")]
    print(f"done: {len(full)} fetched, {len(kept)} for sale", flush=True)


if __name__ == "__main__":
    main()
