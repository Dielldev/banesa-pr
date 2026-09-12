"""Download every listing photo and pack them into sprite sheets.

Artifacts can't hotlink media.merrjep.com (blocked by the page CSP) and can only
publish 255 files at a time, so ~3k individual thumbnails are not an option.
Packing them into a few dozen sheets ships every photo in one publish and costs
the page one HTTP request per sheet.
"""
import concurrent.futures as cf
import io
import json
import os
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
SPRITES = os.path.join(ROOT, "sprites")
CACHE = os.environ.get("IMG_CACHE", "/tmp/banesa-img-cache")

CELL_W, CELL_H = 198, 150          # 1.5x the 132x100 card slot
COLS, ROWS = 10, 8                 # 80 cells per sheet -> 1980x1200
PER_SHEET = COLS * ROWS
QUALITY = 72


def cache_path(lid):
    return os.path.join(CACHE, lid + ".bin")


def download(item):
    lid, url = item
    p = cache_path(lid)
    if os.path.exists(p) and os.path.getsize(p) > 500:
        return lid, True
    raw = common.fetch_bytes(url)
    if not raw or len(raw) < 500:
        return lid, False
    with open(p, "wb") as f:
        f.write(raw)
    return lid, True


def load_cell(lid):
    """Open a cached image and cover-crop it to the cell size."""
    try:
        im = Image.open(cache_path(lid))
        im = im.convert("RGB")
    except Exception:
        return None
    sw, sh = im.size
    if sw < 40 or sh < 40:
        return None
    scale = max(CELL_W / sw, CELL_H / sh)
    im = im.resize((max(1, round(sw * scale)), max(1, round(sh * scale))), Image.LANCZOS)
    left = (im.width - CELL_W) // 2
    top = (im.height - CELL_H) // 2
    return im.crop((left, top, left + CELL_W, top + CELL_H))


def build(listings):
    os.makedirs(CACHE, exist_ok=True)
    os.makedirs(SPRITES, exist_ok=True)
    for f in os.listdir(SPRITES):
        os.remove(os.path.join(SPRITES, f))

    jobs = [(l["id"], l["image"]) for l in listings if l.get("image")]
    print(f"[img] {len(jobs)} photos to fetch", flush=True)
    ok = set()
    with cf.ThreadPoolExecutor(max_workers=16) as ex:
        for i, (lid, good) in enumerate(ex.map(download, jobs), 1):
            if good:
                ok.add(lid)
            if i % 500 == 0:
                print(f"  fetched {i}/{len(jobs)} ({len(ok)} ok)", flush=True)
    print(f"[img] {len(ok)} downloaded", flush=True)

    placed, sheet_no, cell_no = {}, 0, 0
    sheet = Image.new("RGB", (COLS * CELL_W, ROWS * CELL_H), (222, 228, 233))

    def flush(n):
        sheet.save(os.path.join(SPRITES, f"s{n}.jpg"), "JPEG",
                   quality=QUALITY, optimize=True, progressive=True)

    for l in listings:
        if l["id"] not in ok:
            continue
        cell = load_cell(l["id"])
        if cell is None:
            continue
        c, r = cell_no % COLS, cell_no // COLS
        sheet.paste(cell, (c * CELL_W, r * CELL_H))
        placed[l["id"]] = [sheet_no, c, r]
        cell_no += 1
        if cell_no == PER_SHEET:
            flush(sheet_no)
            sheet_no += 1
            cell_no = 0
            sheet = Image.new("RGB", (COLS * CELL_W, ROWS * CELL_H), (222, 228, 233))
    if cell_no:
        flush(sheet_no)

    total = sum(os.path.getsize(os.path.join(SPRITES, f)) for f in os.listdir(SPRITES))
    print(f"[img] {len(placed)} images in {sheet_no + 1} sheets, {total/1e6:.1f} MB", flush=True)
    json.dump(placed, open(os.path.join(DATA, "sprites.json"), "w"))
    return placed


if __name__ == "__main__":
    src = json.load(open(os.path.join(DATA, "listings.json")))
    build(src["listings"])
