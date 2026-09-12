"""Backfill: recompute hood/area mentions from stored text, and re-fetch the
JSON-LD price for listings whose price came back empty (agencies often put the
per-m2 figure there instead of a total)."""
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
import hoods
import merrjep

DATA = merrjep.DATA
LD_RX = re.compile(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', re.S)


def ld_price(url):
    h = common.fetch(url)
    if not h:
        return None
    for b in LD_RX.findall(h):
        try:
            o = json.loads(b.strip())
        except (ValueError, TypeError):
            continue
        if isinstance(o, dict) and o.get("@type") == "Product":
            try:
                return float((o.get("offers") or {}).get("price"))
            except (TypeError, ValueError):
                return None
    return None


def main():
    rows = json.load(open(os.path.join(DATA, "raw_merrjep.json")))
    for r in rows:
        desc = r.get("description") or ""
        r["area_mentions"] = common.all_areas(desc)
        r["hood"], r["tier"] = hoods.detect(r.get("title"), desc)

    todo = [r for r in rows
            if not r.get("price") and not r.get("is_rental") and r.get("tier") in ("core", "nearby")]
    print(f"re-fetching LD price for {len(todo)} listings...", flush=True)

    with ThreadPoolExecutor(max_workers=8) as ex:
        for i, (r, p) in enumerate(zip(todo, ex.map(lambda x: ld_price(x["url"]), todo)), 1):
            r["ld_price_raw"] = p
            if i % 200 == 0:
                print(f"  {i}/{len(todo)}", flush=True)

    got = sum(1 for r in todo if r.get("ld_price_raw"))
    print(f"recovered a price figure for {got}/{len(todo)}")
    json.dump(rows, open(os.path.join(DATA, "raw_merrjep.json"), "w"), ensure_ascii=False)
    print("done")


if __name__ == "__main__":
    main()
