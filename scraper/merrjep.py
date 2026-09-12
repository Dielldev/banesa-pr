"""MerrJep.com scraper: apartments for sale in Pristina.

Stage 1 (crawl)  list pages  -> listing stubs
Stage 2 (detail) listing page -> area / rooms / floor / description / agency
"""
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
import hoods

BASE = "https://www.merrjep.com"
LIST = BASE + "/shpallje/patundshmeri/banesa/ne-shitje/prishtine"
DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

CARD_SPLIT = re.compile(r'(?=<div class="new row row-listing)')


def parse_list_page(html):
    out = []
    for card in CARD_SPLIT.split(html)[1:]:
        pid = re.search(r'data-product-id="(\d+)"', card)
        if not pid:
            continue
        link = re.search(r'href="(/shpallja/[^"]+)"', card)
        if not link:
            continue
        title_m = re.search(r'<h2>.*?<a[^>]*>(.*?)</a>', card, re.S)
        title = common.text(title_m.group(1)) if title_m else ""
        price_m = re.search(r'<p class="list-price">(.*?)</p>', card, re.S)
        price = common.parse_price(common.text(price_m.group(1))) if price_m else None
        store = re.search(r'href="//www\.merrjep\.com/([a-z0-9\-]+)"[^>]*>\s*<span class="label[^"]*isstore', card)
        agency_slug = store.group(1) if store else None
        if not agency_slug:
            logo = re.search(r'href="//www\.merrjep\.com/([a-z0-9\-]+)"\s*>\s*<img[^>]*big-logo', card)
            agency_slug = logo.group(1) if logo else None
        date_m = re.search(r'<span class="pull-right ci-text-right">\s*(.*?)\s*</span>', card, re.S)
        img = re.search(r'(?:data-)?src="(https://media\.merrjep\.com/[^"]+)"', card)
        out.append({
            "id": "mj-" + pid.group(1),
            "source": "MerrJep",
            "url": BASE + link.group(1),
            "title": title,
            "price": price,
            "agency_slug": agency_slug,
            "posted": common.text(date_m.group(1)) if date_m else "",
            "image": img.group(1) if img else None,
        })
    return out


def crawl(pages):
    seen, stubs = set(), []

    def one(p):
        url = LIST if p == 1 else f"{LIST}?Page={p}"
        h = common.fetch(url)
        return parse_list_page(h) if h else []

    with ThreadPoolExecutor(max_workers=6) as ex:
        for i, res in enumerate(ex.map(one, range(1, pages + 1)), 1):
            for s in res:
                if s["id"] not in seen:
                    seen.add(s["id"])
                    stubs.append(s)
            if i % 10 == 0:
                print(f"  list page {i}/{pages} -> {len(stubs)} unique", flush=True)
    return stubs


LD_RX = re.compile(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', re.S)
TAG_RX = re.compile(r'<[^>]*class="tag-item"[^>]*>(.*?)</[a-z]+>\s*<[^>]*>(.*?)</', re.S)

FEATURES = {
    "parking": r"parking|garazh|garaz",
    "elevator": r"ashensor|\blift\b",
    "new_build": r"nd[eë]rtim i ri|nd[eë]rtes[eë] e re|banes[eë] e re|new build|i\/e re\b",
    "balcony": r"ballkon|terras|terrac|verand",
    "furnished": r"mobilu|furnish",
    "renovated": r"rinovu|renovat",
    "basement": r"bodrum|depo\b",
    "duplex": r"dupleks|duplex",
    "heating": r"ngrohje qendrore|ngrohje\b",
}


def parse_detail(html_text, stub):
    d = dict(stub)
    desc, ld_price = "", None

    for block in LD_RX.findall(html_text):
        try:
            obj = json.loads(block.strip())
        except (ValueError, TypeError):
            continue
        if isinstance(obj, dict) and obj.get("@type") == "Product":
            desc = (obj.get("description") or "").strip()
            offers = obj.get("offers") or {}
            if isinstance(offers, dict):
                try:
                    ld_price = float(offers.get("price"))
                except (TypeError, ValueError):
                    ld_price = None
            img = obj.get("image")
            if isinstance(img, list) and img and isinstance(img[0], dict):
                d["image"] = img[0].get("contentUrl") or d.get("image")
            break

    tags = {}
    for k, v in TAG_RX.findall(html_text):
        k, v = common.text(k).rstrip(":"), common.text(v)
        if k and v:
            tags[k] = v

    title = stub.get("title") or ""
    blob = " ".join([title, desc, " ".join(f"{k} {v}" for k, v in tags.items())])

    d["description"] = desc[:1500]
    d["area"] = common.parse_area(title) or common.parse_area(desc)
    d["area_mentions"] = common.all_areas(desc)
    d["rooms"] = common.parse_rooms(title) or common.parse_rooms(desc)
    d["floor"] = common.parse_floor(desc) if common.parse_floor(desc) is not None else common.parse_floor(title)
    d["ld_price_raw"] = ld_price
    if ld_price and not d.get("price") and 5_000 <= ld_price <= 5_000_000:
        d["price"] = ld_price
    d["seller_type"] = tags.get("Publikuar nga") or ""
    d["municipality"] = tags.get("Komuna") or ""

    listing_type = (tags.get("Lloji i shpalljes") or "").lower()
    d["is_rental"] = ("qera" in listing_type or "qira" in listing_type
                      or (not listing_type and common.looks_like_rental(title, desc)))

    hood, tier = hoods.detect(title, desc)
    d["hood"], d["tier"] = hood, tier
    d["features"] = sorted({n for n, pat in FEATURES.items() if re.search(pat, blob, re.I)})
    return d


def details(stubs, workers=6):
    def one(s):
        h = common.fetch(s["url"])
        if not h:
            return {**s, "area": None, "rooms": None, "floor": None,
                    "hood": hoods.detect(s.get("title"))[0], "tier": hoods.detect(s.get("title"))[1],
                    "description": "", "features": [], "is_rental": False}
        return parse_detail(h, s)

    out = []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for i, r in enumerate(ex.map(one, stubs), 1):
            out.append(r)
            if i % 100 == 0:
                print(f"  detail {i}/{len(stubs)}", flush=True)
    return out


if __name__ == "__main__":
    pages = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    os.makedirs(DATA, exist_ok=True)
    print(f"Crawling {pages} MerrJep list pages...")
    stubs = crawl(pages)
    print(f"-> {len(stubs)} unique listings")
    with open(os.path.join(DATA, "merrjep_stubs.json"), "w") as f:
        json.dump(stubs, f, ensure_ascii=False)
