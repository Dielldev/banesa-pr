"""Pipeline: crawl MerrJep list pages -> pick in-scope candidates -> fetch details -> data/raw_merrjep.json"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
import hoods
import merrjep

DATA = merrjep.DATA
PAGES = int(os.environ.get("PAGES", "150"))


def main():
    os.makedirs(DATA, exist_ok=True)
    print(f"[1/3] Crawling {PAGES} list pages...", flush=True)
    stubs = merrjep.crawl(PAGES)
    print(f"      {len(stubs)} unique listings", flush=True)
    json.dump(stubs, open(os.path.join(DATA, "merrjep_stubs.json"), "w"), ensure_ascii=False)

    # Fetch details for in-scope hoods plus unknown-hood ads (their lagje hides in the body).
    cands = []
    for s in stubs:
        if common.looks_like_rental(s["title"]):
            continue
        hood, tier = hoods.detect(s["title"])
        if tier in ("core", "nearby") or hood is None:
            cands.append(s)
    print(f"[2/3] Fetching {len(cands)} detail pages...", flush=True)
    full = merrjep.details(cands)

    keep = [d for d in full if not d.get("is_rental") and d.get("tier") in ("core", "nearby")]
    print(f"[3/3] {len(keep)} in-scope sale listings (core+nearby)", flush=True)
    json.dump(full, open(os.path.join(DATA, "raw_merrjep.json"), "w"), ensure_ascii=False)
    print("done", flush=True)


if __name__ == "__main__":
    main()
