"""Scrape agency websites that don't have (usable) MerrJep storefronts.

Both supported sites expose the full ad text in their og:/meta description, so
one detail parser covers them; only the index crawl differs per site.
"""
import html as _html
import json
import os
import time
import re
import sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
import hoods
import merrjep

SITES = {
    "Anem Real Estate": {
        "index": "https://anem-ks.com/en/properties?page={p}",
        "prop": re.compile(r'https://anem-ks\.com/en/property/(\d+)/[^"\']+'),
        "pages": 75,
        "workers": 4, "delay": 0.35,
    },
    "IN Real Estate": {
        "index": "https://inrealestate-ks.com/en/properties?page={p}",
        "prop": re.compile(r'https://inrealestate-ks\.com/en/property/(\d+)/[^"\']+'),
        "pages": 56,
        "workers": 2, "delay": 0.8,   # their WAF bans bursts; crawl this one slowly
    },
}

META = {
    "title": re.compile(r'<meta property="og:title" content="([^"]*)"'),
    "desc": re.compile(r'<meta (?:property="og:description"|name="description") content="([^"]*)"'),
    "image": re.compile(r'<meta property="og:image" content="([^"]*)"'),
}
PRICE_RX = re.compile(r'([\d][\d.,]{2,12})\s*€')
RENT_RX = re.compile(r'/month|/muaj|for rent|me qera|me qira|qera|qira', re.I)


def collect_urls(cfg):
    urls, seen = [], set()
    for p in range(1, cfg["pages"] + 1):
        if cfg.get("delay"):
            time.sleep(cfg["delay"])
        h = common.fetch(cfg["index"].format(p=p))
        if not h:
            break
        found = set(m.group(0).rstrip('"\'') for m in cfg["prop"].finditer(h))
        fresh = [u for u in found if u not in seen]
        if not fresh:
            break
        seen.update(fresh)
        urls.extend(fresh)
    return urls


def parse_property(url, agency, prop_rx, delay=0.0):
    if delay:
        time.sleep(delay)
    h = common.fetch(url)
    if not h:
        return None
    g = {k: (rx.search(h).group(1) if rx.search(h) else "") for k, rx in META.items()}
    title = common.text(_html.unescape(g["title"])).split(" - ")[0]
    desc = common.text(_html.unescape(g["desc"]))
    blob = f"{title} {desc}"

    if RENT_RX.search(blob):
        return None

    prices = [common.parse_price(x) for x in PRICE_RX.findall(h)]
    prices = [p for p in prices if p]
    price = max(prices) if prices else None

    hood, tier = hoods.detect(title, desc)
    mid = prop_rx.search(url)
    low = blob.lower()
    return {
        "id": f"{re.sub(r'[^a-z]', '', agency.lower())[:3]}-{mid.group(1) if mid else abs(hash(url))}",
        "source": agency,
        "url": url,
        "title": title,
        "description": desc[:1500],
        "price": price,
        "area": common.parse_area(title) or common.parse_area(desc),
        "area_mentions": common.all_areas(desc),
        "rooms": common.parse_rooms(title) or common.parse_rooms(desc),
        "floor": common.parse_floor(desc),
        "image": g["image"] or None,
        "agency_slug": None,
        "agency_name": agency,
        "priority_agency": agency,
        "hood": hood,
        "tier": tier,
        "is_rental": False,
        "seller_type": "Kompani",
        "posted": "",
        "features": sorted({n for n, pat in merrjep.FEATURES.items() if re.search(pat, low)}),
    }


OUT = os.path.join(merrjep.DATA, "raw_sites.json")


def load_existing():
    return json.load(open(OUT)) if os.path.exists(OUT) else []


def main():
    only = sys.argv[1:] or None
    out = [r for r in load_existing() if not only or r.get("source") not in only]

    for agency, cfg in SITES.items():
        if only and agency not in only:
            continue
        probe = common.fetch(cfg["index"].format(p=1), tries=1, timeout=20)
        if not probe:
            print(f"  {agency:22} unreachable right now — skipped", flush=True)
            continue

        urls = collect_urls(cfg)
        print(f"  {agency:22} {len(urls)} property pages", flush=True)
        with ThreadPoolExecutor(max_workers=cfg.get("workers", 6)) as ex:
            rows = [r for r in ex.map(
                lambda u: parse_property(u, agency, cfg["prop"], cfg.get("delay", 0)), urls) if r]
        inscope = [r for r in rows if r["tier"] in ("core", "nearby")]
        print(f"  {'':22} {len(rows)} for sale -> {len(inscope)} in scope", flush=True)

        out.extend(rows)
        json.dump(out, open(OUT, "w"), ensure_ascii=False)   # save after each site
        print(f"  {'':22} saved ({len(out)} total)", flush=True)

    print(f"done: {len(out)} listings", flush=True)


if __name__ == "__main__":
    main()
