"""Prishtina Real Estate (prishtina.io).

Their pages embed the whole property record as escaped JSON, which gives exact
surface, price, floor and bedroom counts rather than numbers parsed out of prose.
Property ids come from their sitemap.
"""
import html as _html
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
import hoods
import merrjep

AGENCY = "Prishtina Real Estate L.L.C"
SITEMAP = "https://www.prishtina.io/sitemap.xml"
WORKERS, DELAY = 4, 0.25


def num(seg, key):
    m = re.search(r'\\"%s\\":\s*([\d.]+)' % key, seg)
    return float(m.group(1)) if m else None


def txt(seg, key):
    m = re.search(r'\\"%s\\":\s*\\"((?:[^"\\]|\\.){0,120}?)\\"' % key, seg)
    if not m:
        return ""
    return _html.unescape(m.group(1).replace('\\/', '/').replace('\\u0026', '&')).strip()


def meta(h, prop):
    m = re.search(r'<meta property="%s" content="([^"]*)"' % prop, h)
    return _html.unescape(m.group(1)) if m else ""


def parse(url):
    time.sleep(DELAY)
    h = common.fetch(url)
    if not h:
        return None
    i = h.find("surface_m2")
    if i < 0:
        return None
    seg = h[max(0, i - 3000):i + 3000]

    cat = re.search(r'\\"category\\":\s*\[\\"([a-z_]+)\\"', seg)
    if not cat or cat.group(1) not in ("apartment", "penthouse"):
        return None

    price = num(seg, "sell_price")
    if not price:                      # rent-only record
        return None
    area = num(seg, "surface_m2")

    title = meta(h, "og:title") or txt(seg, "search_title_en") or txt(seg, "search_title")
    desc = common.text(meta(h, "og:description"))
    city, street, addr = txt(seg, "city"), txt(seg, "street"), txt(seg, "address_description")
    if city and "prishtin" not in city.lower():
        return None

    hood, tier = hoods.detect(title, street, addr, desc)
    low = f"{title} {desc} {addr}".lower()
    feats = {n for n, pat in merrjep.FEATURES.items() if re.search(pat, low)}
    if num(seg, "garage"):
        feats.add("parking")
    if num(seg, "number_of_terraces"):
        feats.add("balcony")
    year = num(seg, "building_year")
    if year and year >= 2018:
        feats.add("new_build")

    pid = re.search(r'/properties/(\d+)', url)
    return {
        "id": "pio-" + (pid.group(1) if pid else str(abs(hash(url)))),
        "source": AGENCY,
        "url": url,
        "title": title,
        "description": desc[:1500],
        "price": price,
        "area": area,
        "area_mentions": [area] if area else [],
        "rooms": int(num(seg, "number_of_bed_rooms") or 0) or None,
        "floor": int(num(seg, "floor")) if num(seg, "floor") is not None else None,
        "image": meta(h, "og:image") or None,
        "agency_slug": None,
        "agency_name": AGENCY,
        "priority_agency": AGENCY,
        "hood": hood,
        "tier": tier,
        "is_rental": False,
        "seller_type": "Kompani",
        "posted": "",
        "features": sorted(feats),
    }


def main():
    sm = common.fetch(SITEMAP)
    urls = sorted({u for u in re.findall(r'<loc>([^<]+)</loc>', sm or "")
                   if re.search(r'/en/properties/\d+$', u)})
    print(f"  {AGENCY}: {len(urls)} property pages", flush=True)

    rows = []
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        for i, r in enumerate(ex.map(parse, urls), 1):
            if r:
                rows.append(r)
            if i % 500 == 0:
                print(f"    {i}/{len(urls)} -> {len(rows)} apartments for sale", flush=True)

    inscope = [r for r in rows if r["tier"] in ("core", "nearby")]
    print(f"  {len(rows)} apartments for sale -> {len(inscope)} in scope", flush=True)

    out = os.path.join(merrjep.DATA, "raw_prishtina_io.json")
    json.dump(rows, open(out, "w"), ensure_ascii=False)
    print("done", flush=True)


if __name__ == "__main__":
    main()
