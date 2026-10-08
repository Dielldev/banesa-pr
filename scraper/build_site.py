"""Trim the ranked dataset into public/data/listings.json — the file the React app fetches."""
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
OUT = os.path.join(ROOT, "public", "data", "listings.json")

KEEP = ("id source url title price area rooms floor hood tier agency date days_old "
        "eur_m2 hood_median_eur_m2 discount_pct score score_reason features "
        "price_derived area_uncertain score_parts image seller_type").split()

SURROGATE = re.compile("[\ud800-\udfff]")
# 044 123 456 / 049-123-456 / +383 44 123 456
PHONE = re.compile(r"(?<!\d)(?:\+383[ -]?|0)(4[3-9])[ /.-]?(\d{3})[ /.-]?(\d{3})(?!\d)")


def mend(s):
    """MerrJep writes emoji as surrogate-pair entities; rejoin them and drop
    anything that survived as a lone surrogate or replacement character."""
    try:
        s = s.encode("utf-16", "surrogatepass").decode("utf-16")
    except UnicodeError:
        s = SURROGATE.sub("", s)
    return SURROGATE.sub("", s).replace("�", "").strip()


def clean(s, limit=None):
    if not s:
        return s
    s = mend(str(s))
    return s[:limit].rstrip() + "…" if limit and len(s) > limit else s


def phone_of(text):
    m = PHONE.search(text or "")
    return f"0{m.group(1)} {m.group(2)} {m.group(3)}" if m else None


def main():
    src = json.load(open(os.path.join(DATA, "listings.json")))
    sprite_path = os.path.join(DATA, "sprites.json")
    sprites = json.load(open(sprite_path)) if os.path.exists(sprite_path) else {}
    out = []
    for l in src["listings"]:
        r = {k: l.get(k) for k in KEEP if l.get(k) not in (None, "")}
        r["title"] = clean(l.get("title")) or "Banesë në shitje"
        for k in ("agency", "score_reason"):
            if l.get(k):
                r[k] = clean(l[k])
        if l.get("description"):
            r["description"] = clean(l["description"], 420)
            phone = phone_of(l["description"])
            if phone:
                r["phone"] = phone
        if l.get("is_priority"):
            r["prio"] = 1
        if r.get("seller_type"):
            r["seller_type"] = "company" if r["seller_type"] == "Kompani" else "private"
        cell = sprites.get(l["id"])
        if cell:
            r["sp"] = cell
        out.append(r)

    payload = {"generated": src["generated"], "source": src["source"],
               "stats": src["stats"], "listings": out}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
    withimg = sum(1 for r in out if r.get("sp"))
    withphone = sum(1 for r in out if r.get("phone"))
    print(f"{OUT} -> {os.path.getsize(OUT):,} bytes | {len(out)} listings | "
          f"{withimg} with photos | {withphone} with phone")


if __name__ == "__main__":
    main()
