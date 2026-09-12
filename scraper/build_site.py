"""Inline the ranked dataset into the page template -> index.html (self-contained)."""
import html
import json
import re
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")

KEEP = ("id url title price area rooms floor hood tier agency date days_old "
        "eur_m2 hood_median_eur_m2 discount_pct score score_reason features "
        "price_derived area_uncertain score_parts").split()


SURROGATE = re.compile("[\ud800-\udfff]")


def mend(s):
    """MerrJep writes emoji as surrogate-pair entities; rejoin them and drop
    anything that survived as a lone surrogate or replacement character."""
    try:
        s = s.encode("utf-16", "surrogatepass").decode("utf-16")
    except UnicodeError:
        s = SURROGATE.sub("", s)
    return SURROGATE.sub("", s).replace("\ufffd", "").strip()


def clean(s, limit=None):
    if not s:
        return s
    s = mend(str(s))
    s = html.escape(s, quote=False).replace("</", "<\\/")
    return s[:limit].rstrip() + "…" if limit and len(s) > limit else s


def main():
    src = json.load(open(os.path.join(DATA, "listings.json")))
    sprite_path = os.path.join(DATA, "sprites.json")
    sprites = json.load(open(sprite_path)) if os.path.exists(sprite_path) else {}
    out = []
    for l in src["listings"]:
        r = {k: l.get(k) for k in KEEP if l.get(k) is not None}
        r["title"] = clean(l.get("title"))
        if l.get("agency"):
            r["agency"] = clean(l["agency"])
        if l.get("description"):
            r["description"] = clean(l["description"], 420)
        if l.get("score_reason"):
            r["score_reason"] = clean(l["score_reason"])
        if l.get("is_priority"):
            r["prio"] = 1
        cell = sprites.get(l["id"])
        if cell:
            r["sp"] = cell
        out.append(r)

    payload = {"generated": src["generated"], "source": src["source"],
               "stats": src["stats"], "listings": out}
    blob = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("</script", "<\\/script")

    tpl = open(os.path.join(HERE, "site_template.html"), encoding="utf-8").read()
    page = tpl.replace("/*__DATA__*/", blob)

    # artifact.html is the body-only form the Artifact host wraps itself
    open(os.path.join(ROOT, "artifact.html"), "w", encoding="utf-8").write(page)

    # index.html is a complete document, for opening straight off disk
    doc = ('<!doctype html>\n<html lang="sq">\n<head>\n<meta charset="utf-8">\n'
           '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
           + page + "\n</html>\n")
    open(os.path.join(ROOT, "index.html"), "w", encoding="utf-8").write(doc)
    withimg = sum(1 for r in out if r.get("sp"))
    print(f"index.html -> {len(doc):,} bytes | artifact.html -> {len(page):,} bytes | "
          f"{len(out)} listings | {withimg} with photos")


if __name__ == "__main__":
    main()
