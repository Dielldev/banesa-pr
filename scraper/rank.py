"""Turn raw scraped listings into the ranked dataset the site consumes.

Value score (0-100) = price-per-m2 discount vs the listing's own neighbourhood
median (the dominant term), plus modest bonuses for quality signals, freshness
and a verified company seller.
"""
import datetime
import json
import os
import re
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
import hoods

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

SANE_EUR_M2 = (700, 7000)
PER_M2_RANGE = (300, 7000)   # a "price" in this band is a per-m2 figure, not a total
FEATURE_POINTS = {"new_build": 6, "parking": 5, "elevator": 4, "renovated": 3,
                  "balcony": 2, "heating": 1, "basement": 1, "duplex": 1, "furnished": 1}
FEATURE_CAP = 16
PRIORITY_BONUS = 5   # agencies the user asked to prioritise
VALUE_SPAN = 0.40      # a 40% discount to the local median maxes the value term
VALUE_MAX = 70


def agency_name(slug):
    """merrjep storefront slug -> display name. Only the legal-form prefixes
    (n.sh. = ndërmarrje shoqërore) are abbreviations; everything else is a word."""
    if not slug:
        return None
    parts, out = slug.split("-"), []
    for i, w in enumerate(parts):
        if w in ("n", "sh") and i < 2:
            out.append(w.upper() + ".")
        else:
            out.append(w.capitalize())
    return " ".join(out).replace("N. SH.", "N.SH.")


def median_map(rows, key, min_n=8):
    buckets = {}
    for r in rows:
        k = r.get(key)
        if k and r.get("eur_m2"):
            buckets.setdefault(k, []).append(r["eur_m2"])
    return {k: statistics.median(v) for k, v in buckets.items() if len(v) >= min_n}, \
           {k: len(v) for k, v in buckets.items()}


def score_all(rows, today=None):
    today = today or datetime.date.today()

    for r in rows:
        title = r.get("title") or ""
        a, p = r.get("area"), r.get("price")
        stated = common.parse_per_m2(r.get("description"))
        raw = stated or r.get("ld_price_raw")

        # An area quoted only in the body, with other conflicting figures next to
        # it (duplex floor splits, gross-vs-net), is not safe to value on.
        mentions = r.get("area_mentions") or []
        from_title = common.parse_area(title) is not None
        r["area_uncertain"] = bool(
            not from_title and len(mentions) > 1 and max(mentions) / min(mentions) > 1.5)

        r["price_derived"] = False
        if p and a and a > 0:
            r["eur_m2"] = round(p / a)
        elif not p and raw and PER_M2_RANGE[0] <= raw <= PER_M2_RANGE[1]:
            # agencies routinely put the per-m2 asking figure in the price field
            r["eur_m2"] = round(raw)
            r["per_m2_stated"] = stated is not None
            if a and a > 0:
                r["price"] = p = round(raw * a)
                r["price_derived"] = True
        else:
            r["eur_m2"] = None

        if r["eur_m2"] and not (SANE_EUR_M2[0] <= r["eur_m2"] <= SANE_EUR_M2[1]):
            r["eur_m2"] = None
            r["suspect_price"] = True
        r["date"] = common.parse_posted(r.get("posted", ""), today)
        r["agency"] = (r.get("priority_agency") or r.get("agency_name")
                       or agency_name(r.get("agency_slug")))

    priced = [r for r in rows if r["eur_m2"] and not r.get("area_uncertain")]
    hood_med, hood_n = median_map(priced, "hood")
    tier_med, _ = median_map(priced, "tier", min_n=5)
    overall = statistics.median([r["eur_m2"] for r in priced]) if priced else None

    for r in rows:
        r["hood_median_eur_m2"] = None
        r["benchmark"] = None
        if not r["eur_m2"]:
            r["score"] = None
            r["score_reason"] = "Missing price or size — can't be valued"
            continue

        if r.get("hood") in hood_med:
            med, bench = hood_med[r["hood"]], r["hood"]
        elif r.get("tier") in tier_med:
            med, bench = tier_med[r["tier"]], f"{r['tier']} average"
        else:
            med, bench = overall, "Pristina overall"
        r["hood_median_eur_m2"] = round(med)
        r["benchmark"] = bench

        discount = (med - r["eur_m2"]) / med
        if r.get("area_uncertain") and discount > 0:
            discount *= 0.5
        r["discount_pct"] = round(discount * 100, 1)
        value = VALUE_MAX / 2 + (max(-VALUE_SPAN, min(VALUE_SPAN, discount)) / VALUE_SPAN) * (VALUE_MAX / 2)

        feats = min(FEATURE_CAP, sum(FEATURE_POINTS.get(f, 0) for f in r.get("features", [])))
        prio = PRIORITY_BONUS if r.get("is_priority") else 0

        fresh = 0
        if r.get("date"):
            age = (today - datetime.date.fromisoformat(r["date"])).days
            r["days_old"] = age
            fresh = 6 if age <= 7 else 4 if age <= 30 else 2 if age <= 90 else 0

        trust = 2 if (r.get("seller_type") or "").lower().startswith("kompani") else 0
        trust += 1 if (r.get("agency_slug") or r.get("agency_name")) else 0

        r["score"] = round(value + feats + fresh + min(3, trust) + prio, 1)
        r["score_parts"] = {"value": round(value, 1), "features": feats,
                            "freshness": fresh, "seller": min(3, trust), "priority": prio}
        sign = "below" if discount > 0 else "above"
        note = ""
        if r.get("price_derived"):
            note = " · total estimated from the agency's per-m² asking price"
        elif not r.get("price"):
            note = " · agency quotes per m² only"
        if r.get("area_uncertain"):
            note += " · size ambiguous in the ad, verify before trusting"
        r["score_reason"] = (f"€{r['eur_m2']:,}/m² — {abs(r['discount_pct']):.0f}% {sign} "
                             f"the {bench} median of €{round(med):,}/m²{note}")

    rows.sort(key=lambda r: (r["score"] is None, -(r["score"] or 0)))
    return rows, {"hood_median": hood_med, "hood_count": hood_n, "overall_median": overall}


def main():
    raw = json.load(open(os.path.join(DATA, "raw_all.json")))
    rows = []
    for r in raw:
        if r.get("is_rental") or r.get("tier") not in ("core", "nearby"):
            continue
        # a lagje matched only in the body, next to another municipality's name,
        # is almost always an ad for a flat somewhere else entirely
        if hoods.detect(r.get("title"))[1] not in ("core", "nearby") and \
           common.mentions_other_municipality(r.get("description")):
            continue
        rows.append(r)
    # de-dupe identical re-posts: same agency, price and area
    seen, uniq = set(), []
    for r in rows:
        k = (r.get("agency_slug"), r.get("price"), r.get("area"), (r.get("title") or "")[:40].lower())
        if k in seen:
            continue
        seen.add(k)
        uniq.append(r)

    ranked, stats = score_all(uniq)
    out = {
        "generated": datetime.datetime.now().isoformat(timespec="seconds"),
        "source": "MerrJep + agency sites",
        "stats": {
            "total": len(ranked),
            "priced": sum(1 for r in ranked if r["eur_m2"]),
            "core": sum(1 for r in ranked if r["tier"] == "core"),
            "overall_median_eur_m2": round(stats["overall_median"]) if stats["overall_median"] else None,
            "hood_median": {k: round(v) for k, v in stats["hood_median"].items()},
            "hood_count": stats["hood_count"],
            "priority": sum(1 for r in ranked if r.get("is_priority")),
            "priority_agencies": sorted({r["agency"] for r in ranked if r.get("is_priority") and r.get("agency")}),
            "sources": sorted({r.get("source") or "MerrJep" for r in ranked}),
        },
        "listings": ranked,
    }
    json.dump(out, open(os.path.join(DATA, "listings.json"), "w"), ensure_ascii=False)
    print(f"ranked {len(ranked)} listings -> data/listings.json")
    print("medians:", out["stats"]["hood_median"])


if __name__ == "__main__":
    main()
