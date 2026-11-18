"""Fetch new listings — incremental update of the Pristina apartment board.

    python3 update.py              quick: only what is new (a handful of requests)
    python3 update.py --full       deep sweep: every source end to end, then prune dead ads
    python3 update.py --rebuild    re-score from the store, no network

How it stays cheap
------------------
data/store.json remembers every ad it has accepted *and* every ad it looked at and
rejected, so a run fetches detail pages only for ads it has never seen. MerrJep's
category is newest-first, so a quick run walks pages until two batches in a row
contain nothing unknown. prishtina.io is a one-request sitemap diff. Anem / IN are
a few index pages. A quiet run with nothing new touches no files at all, so the
scheduled job produces no commit (and no redeploy) unless something changed.

How it stays safe
-----------------
* A source that fails is reported and skipped; its existing rows are kept.
* Listings are only removed after a *complete, error-free* sweep of their source
  has not seen them for GRACE_DAYS, and never more than MAX_PRUNE_FRACTION of a
  source at once (override with --force-prune after checking).
* Work is checkpointed after every source, and --budget stops fetching cleanly, so
  an interrupted catch-up simply resumes on the next run.
"""
import argparse
import datetime
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_site
import common
import hoods
import merge
import merrjep
import prishtina_io
import rank
import sites
import store as storemod
import storefront

SOURCES = ("merrjep", "storefronts", "prishtina_io", "anem", "inrealestate")
QUICK_SOURCES = ("merrjep", "prishtina_io", "anem", "inrealestate")   # storefronts are not date-ordered

# Relative share of the time budget. Cheap, independent sites go first with a small slice each;
# MerrJep (hundreds of ad pages, throttled) runs last and takes whatever is left over.
WEIGHT = {"prishtina_io": 2, "anem": 1, "inrealestate": 1, "storefronts": 2, "merrjep": 4}
RUN_ORDER = ("anem", "inrealestate", "prishtina_io", "storefronts", "merrjep")

MJ_DEPTH = 150           # list pages ≈ two months of ads
MJ_BATCH = 3              # pages fetched together; two quiet batches in a row ends a quick crawl
SITE_QUIET_PAGES = 2
GRACE_DAYS = {"mj": 21, "pio": 10, "ane": 10, "inr": 10}
MAX_PRUNE_FRACTION = 0.40
AGENCY_SITE_KEYS = {"anem": "Anem Real Estate", "inrealestate": "IN Real Estate"}


class Ctx:
    def __init__(self, store, full, only, budget_min, force_prune):
        self.store = store
        self.full = full
        self.only = only
        self.force_prune = force_prune
        self.today = storemod.today_iso()
        self.now = storemod.now_iso()
        self.known = storemod.known_ids(store)
        self.new = set()           # ids accepted this run
        self.updated = set()       # known ids whose price changed
        self.renewed = set()       # known ids re-dated by the seller
        self.removed = []          # ids pruned
        self.swept = set()         # id-prefix groups that had a complete sweep this run
        self.report = {}
        self.deferred = 0          # fetches skipped because the --budget ran out
        self.budget_end = time.time() + budget_min * 60 if budget_min else None
        self.deadline = self.budget_end      # the running source's own cut-off (see allot())

    def expired(self):
        return self.deadline is not None and time.time() > self.deadline

    def allot(self, left):
        """Give the next source a slice of what remains of --budget, in proportion to its weight
        (`left` = the sources still to run, itself included). Time a quick source doesn't use
        rolls over to the later ones, so MerrJep — slow and throttled — can never use up the
        minutes the other sites need, and a stalled site can't eat MerrJep's."""
        if self.budget_end is None:
            return
        now = time.time()
        total = sum(WEIGHT.get(s, 1) for s in left)
        share = max(0.0, self.budget_end - now) * WEIGHT.get(left[0], 1) / total
        self.deadline = now + share


def log(msg):
    print(msg, flush=True)


# --- storing results --------------------------------------------------------

def skip(ctx, rid):
    ctx.store["skipped"][rid] = ctx.today
    ctx.known.add(rid)


def accept(ctx, row):
    """Keep a freshly fetched row, or park it in `skipped` if it's out of scope."""
    rid = row["id"]
    if row.get("skip") or row.get("is_rental") or row.get("tier") not in ("core", "nearby"):
        skip(ctx, rid)
        return False
    row = {k: v for k, v in row.items() if k != "skip"}
    row["first_seen"] = ctx.now
    row["last_seen"] = ctx.today
    row["date"] = row.get("date") or common.parse_posted(row.get("posted", ""))
    ctx.store["listings"][rid] = row
    ctx.known.add(rid)
    ctx.new.add(rid)
    return True


def refresh_known(ctx, stub):
    """An ad we already hold showed up again: note it, and pick up price drops / re-posts."""
    rid = stub["id"]
    row = ctx.store["listings"].get(rid)
    if row is None:
        if rid in ctx.store["skipped"]:
            ctx.store["skipped"][rid] = ctx.today
        return
    row["last_seen"] = ctx.today
    price = stub.get("price")
    if price and price != row.get("price"):
        if row.get("price"):
            row["price_prev"], row["price_changed"] = row["price"], ctx.today
        row["price"] = price
        ctx.updated.add(rid)
    posted = common.parse_posted(stub.get("posted", ""))
    if posted and posted > (row.get("date") or ""):
        row["date"], row["posted"] = posted, stub["posted"]
        ctx.renewed.add(rid)


def fetch_many(ctx, items, fn, workers, label):
    """Map fn over items on a small pool. None = failed or not attempted (budget spent)."""
    def one(it):
        if ctx.expired():
            ctx.deferred += 1
            return None
        return fn(it)

    out = []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for i, r in enumerate(ex.map(one, items), 1):
            out.append(r)
            if i % 100 == 0:
                log(f"    {label}: {i}/{len(items)}")
    return out


def classify_stub(stub):
    """Title-only triage, as run.py does: True = worth fetching the ad page."""
    if common.looks_like_rental(stub.get("title")):
        return False
    hood, tier = hoods.detect(stub.get("title"))
    return tier in ("core", "nearby") or hood is None


def ingest_stubs(ctx, stubs, rep):
    """Shared by the MerrJep crawls: refresh known ads, triage + fetch the unknown ones."""
    unknown = []
    for s in stubs:
        if s["id"] in ctx.known:
            refresh_known(ctx, s)
        else:
            unknown.append(s)
    cands = []
    for s in unknown:
        if classify_stub(s):
            cands.append(s)
        else:
            skip(ctx, s["id"])
    rep["candidates"] = rep.get("candidates", 0) + len(cands)
    if not cands:
        return
    log(f"    fetching {len(cands)} new ad pages")

    def detail(stub):
        h = common.fetch(stub["url"])
        return merrjep.parse_detail(h, stub) if h else None

    for stub, row in zip(cands, fetch_many(ctx, cands, detail, 6, "details")):
        if row is None:
            rep["failed"] = rep.get("failed", 0) + 1
        elif accept(ctx, row):
            rep["new"] = rep.get("new", 0) + 1


# --- MerrJep category -------------------------------------------------------

def list_page(p):
    h = common.fetch(merrjep.LIST if p == 1 else f"{merrjep.LIST}?Page={p}")
    return None if h is None else merrjep.parse_list_page(h)


def crawl_category(ctx, max_pages, rep):
    """Newest-first walk. Quick mode stops after two batches with nothing unknown."""
    stubs, seen = [], set()
    failed, end, quiet, dead_batches, page = [], None, 0, 0, 1
    with ThreadPoolExecutor(max_workers=MJ_BATCH) as ex:
        while page <= max_pages and end is None and not ctx.expired():
            batch = list(range(page, min(page + MJ_BATCH, max_pages + 1)))
            any_new, bad = False, 0
            for p, res in zip(batch, ex.map(list_page, batch)):
                if res is None:
                    failed.append(p)
                    bad += 1
                elif not res:
                    end = end or p
                else:
                    for s in res:
                        if s["id"] not in seen:
                            seen.add(s["id"])
                            stubs.append(s)
                            any_new |= s["id"] not in ctx.known
            page += MJ_BATCH
            if (page - 1) % 15 == 0 or bad:
                unknown = sum(1 for s in stubs if s["id"] not in ctx.known)
                log(f"    list page {page - 1}/{max_pages}: {len(stubs)} ads, {unknown} unknown"
                    + (f", {bad} page(s) failed" if bad else ""))
            dead_batches = dead_batches + 1 if bad == len(batch) else 0
            if dead_batches >= 3:
                raise RuntimeError("MerrJep is not answering (3 batches of list pages failed)")
            quiet = quiet + 1 if (not any_new and not bad) else 0
            if not ctx.full and quiet >= 2:
                rep["stopped_early"] = True
                break
    rep["pages"] = min(page - 1, max_pages)
    reached_depth = page > max_pages
    rep["complete"] = bool(ctx.full and not failed and (reached_depth or (end and end > 20)))
    if failed:
        rep["failed_pages"] = failed
    return stubs


def run_merrjep(ctx, rep, pages):
    stubs = crawl_category(ctx, pages, rep)
    rep["seen"] = len(stubs)
    ingest_stubs(ctx, stubs, rep)
    return rep.get("complete", False)


# --- MerrJep agency storefronts (full only) ----------------------------------

def crawl_store(slug, max_pages):
    """-> (stubs, complete). A failed page or an empty first page is not a 'complete' sweep."""
    stubs, seen = [], set()
    for p in range(1, max_pages + 1):
        h = common.fetch(f"{storefront.BASE}/{slug}" + ("" if p == 1 else f"?Page={p}"))
        if h is None:
            return stubs, False
        page = storefront.parse_store_page(h, slug)
        if not page and p == 1:
            return stubs, False
        fresh = [s for s in page if s["id"] not in seen]
        if not fresh or len(page) < 40:
            seen.update(s["id"] for s in fresh)
            stubs.extend(fresh)
            return stubs, True
        seen.update(s["id"] for s in fresh)
        stubs.extend(fresh)
    return stubs, False          # ran out of page budget before the end


def run_storefronts(ctx, rep):
    complete = True
    apts = []
    for slug, name in storefront.AGENCIES.items():
        if ctx.expired():
            complete = False
            break
        stubs, ok = crawl_store(slug, storefront.DEPTH.get(slug, 60))
        complete &= ok
        mine = [s for s in stubs if storefront.is_apartment(s)]
        log(f"    {name:32} {len(stubs):5} ads -> {len(mine):4} Pristina apartments{'' if ok else '  (INCOMPLETE)'}")
        apts.extend(mine)
    rep["seen"] = len(apts)
    before = set(ctx.new)
    ingest_stubs(ctx, apts, rep)
    for rid in ctx.new - before:
        row = ctx.store["listings"][rid]
        row["priority_agency"] = storefront.AGENCIES.get(row.get("agency_slug"))
    rep["complete"] = complete
    return complete


# --- prishtina.io -----------------------------------------------------------

def run_prishtina_io(ctx, rep):
    sm = common.fetch(prishtina_io.SITEMAP)
    if not sm:
        raise RuntimeError("sitemap unreachable")
    urls = {}
    for u in re.findall(r"<loc>([^<]+)</loc>", sm):
        m = re.search(r"/en/properties/(\d+)$", u)
        if m:
            urls["pio-" + m.group(1)] = u
    rep["seen"] = len(urls)
    had = sum(1 for i in ctx.known if i.startswith("pio-"))
    for rid in urls:
        if rid in ctx.known:
            row = ctx.store["listings"].get(rid)
            if row:
                row["last_seen"] = ctx.today
            else:
                ctx.store["skipped"][rid] = ctx.today
    todo = [(rid, u) for rid, u in sorted(urls.items(), reverse=True) if rid not in ctx.known]
    if todo:
        log(f"    {len(todo)} new property pages")
        rows = fetch_many(ctx, todo, lambda t: prishtina_io.parse(t[1]), prishtina_io.WORKERS, "prishtina.io")
        for (rid, _), row in zip(todo, rows):
            if row is None:
                rep["failed"] = rep.get("failed", 0) + 1
            elif accept(ctx, row):
                rep["new"] = rep.get("new", 0) + 1
    # one request sees the whole site, so any run is a complete sweep — unless the sitemap looks truncated
    complete = had == 0 or len(urls) >= 0.5 * had
    rep["complete"] = complete
    return complete


# --- Anem / IN Real Estate -----------------------------------------------------

def site_page_ids(h, cfg, agency):
    prefix = re.sub(r"[^a-z]", "", agency.lower())[:3]
    out = {}
    for m in cfg["prop"].finditer(h or ""):
        out[f"{prefix}-{m.group(1)}"] = m.group(0).rstrip("\"'")
    return out


def run_site(ctx, agency, rep):
    cfg = sites.SITES[agency]
    first = common.fetch(cfg["index"].format(p=1), tries=2, timeout=20)
    if not first:
        raise RuntimeError("unreachable")
    found, order, quiet, failed, natural_end = {}, [], 0, False, False
    for p in range(1, cfg["pages"] + 1):
        if p > 1:
            time.sleep(cfg.get("delay", 0))
        h = first if p == 1 else common.fetch(cfg["index"].format(p=p))
        if h is None:
            failed = True
            break
        ids = site_page_ids(h, cfg, agency)
        fresh = {i: u for i, u in ids.items() if i not in found}
        if not fresh:
            natural_end = True
            break
        unknown = [i for i in fresh if i not in ctx.known]
        found.update(fresh)
        order.extend(fresh)
        quiet = quiet + 1 if not unknown else 0
        if not ctx.full and quiet >= SITE_QUIET_PAGES:
            rep["stopped_early"] = True
            break
    rep["seen"] = len(found)
    for rid in found:
        if rid in ctx.known:
            row = ctx.store["listings"].get(rid)
            if row:
                row["last_seen"] = ctx.today
            else:
                ctx.store["skipped"][rid] = ctx.today
    todo = [(rid, found[rid]) for rid in order if rid not in ctx.known]
    if todo:
        log(f"    {len(todo)} new property pages")
        rows = fetch_many(ctx, todo,
                          lambda t: sites.parse_property(t[1], agency, cfg["prop"], cfg.get("delay", 0)),
                          cfg.get("workers", 4), agency)
        for (rid, _), row in zip(todo, rows):
            if row is None:
                rep["failed"] = rep.get("failed", 0) + 1
            elif accept(ctx, row):
                rep["new"] = rep.get("new", 0) + 1
    complete = bool(ctx.full and natural_end and not failed)
    rep["complete"] = complete
    return complete


# --- pruning ------------------------------------------------------------------

def prune(ctx):
    """Drop listings a complete sweep has stopped seeing. Returns ids removed."""
    today = datetime.date.fromisoformat(ctx.today)
    for group in sorted(ctx.swept):
        cutoff = (today - datetime.timedelta(days=GRACE_DAYS[group])).isoformat()
        mine = [r for r in ctx.store["listings"].values() if r["id"].startswith(group + "-")]
        stale = [r["id"] for r in mine if (r.get("last_seen") or "") < cutoff]
        if not stale:
            continue
        if len(stale) > MAX_PRUNE_FRACTION * len(mine) and not ctx.force_prune:
            log(f"  ! not pruning {group}: {len(stale)} of {len(mine)} look gone — more than "
                f"{MAX_PRUNE_FRACTION:.0%}. If that's expected, re-run with --force-prune")
            continue
        for rid in stale:
            del ctx.store["listings"][rid]
        ctx.removed.extend(stale)
        log(f"  pruned {len(stale)} {group} listings not seen since {cutoff}")


# --- output -------------------------------------------------------------------

def rebuild(store):
    """store -> ranked data/listings.json -> trimmed public/data/listings.json (+ meta.json)."""
    today = datetime.date.today()
    rows = []
    for r in store["listings"].values():
        c = dict(r)
        prev, changed = c.get("price_prev"), c.get("price_changed")
        if prev and c.get("price") and c["price"] < prev and changed and \
                (today - datetime.date.fromisoformat(changed)).days <= 60:
            c["price_was"] = prev
        rows.append(c)
    merge.apply_priority(rows)
    # richer rows win a tie when the same flat is listed twice: priority agencies, then oldest
    rows.sort(key=lambda r: (not r.get("is_priority"), r.get("first_seen") or "", r["id"]))
    rows = merge.dedupe_cross_listed(rows)
    out = rank.build(rows)
    out["updated"] = store.get("updated") or out["generated"]
    with open(os.path.join(storemod.DATA, "listings.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False)
    build_site.main()
    return out


# --- driver -------------------------------------------------------------------

def summarize(ctx, out):
    lines = ["| source | state | seen | new | failed | deferred | note |", "|---|---|---:|---:|---:|---:|---|"]
    for name, r in ctx.report.items():
        note = r.get("error") or ("stopped early" if r.get("stopped_early") else
                                  "complete sweep" if r.get("complete") else "")
        lines.append(f"| {name} | {r['state']} | {r.get('seen', '')} | {r.get('new', 0)} | {r.get('failed', 0)} | {r.get('deferred', 0)} | {note} |")
    lines.append("")
    lines.append(f"**{len(ctx.new)} new**, {len(ctx.updated)} price changes, {len(ctx.renewed)} re-posted, "
                 f"{len(ctx.removed)} removed" + (f" — {out['stats']['total']} listings on the board" if out else ""))
    return "\n".join(lines)


def run(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--full", action="store_true", help="deep sweep of every source, then prune dead ads")
    ap.add_argument("--only", help="comma list of: " + ", ".join(SOURCES))
    ap.add_argument("--pages", type=int, default=MJ_DEPTH, help="MerrJep category depth (default %(default)s)")
    ap.add_argument("--budget", type=float, default=0, help="stop fetching after this many minutes (0 = no limit)")
    ap.add_argument("--force-prune", action="store_true", help="allow removing a large share of a source in one go")
    ap.add_argument("--forget-skipped", action="store_true", help="re-evaluate ads previously rejected as out of scope")
    ap.add_argument("--rebuild", action="store_true", help="only re-score from the store; no network")
    args = ap.parse_args(argv)

    only = [s.strip() for s in args.only.split(",")] if args.only else list(SOURCES if args.full else QUICK_SOURCES)
    bad = [s for s in only if s not in SOURCES]
    if bad:
        ap.error(f"unknown source(s): {', '.join(bad)}")

    store = storemod.load()
    if not store["listings"] and not store["skipped"]:
        log("No store yet — seeding from the existing raw_*.json scrape…")
        store = storemod.seed_from_raw()
        log(f"  seeded {len(store['listings'])} listings, {len(store['skipped'])} rejected ads")
    if args.forget_skipped:
        store["skipped"].clear()

    if args.rebuild:
        out = rebuild(store)
        storemod.save(store)
        log(f"rebuilt: {out['stats']['total']} listings")
        return 0

    ctx = Ctx(store, args.full, only, args.budget, args.force_prune)
    log(f"{'FULL' if args.full else 'quick'} update — {', '.join(only)} "
        f"(store: {len(store['listings'])} listings, {len(store['skipped'])} rejected)")

    runners = {
        "merrjep": lambda rep: run_merrjep(ctx, rep, args.pages),
        "storefronts": lambda rep: run_storefronts(ctx, rep),
        "prishtina_io": lambda rep: run_prishtina_io(ctx, rep),
        "anem": lambda rep: run_site(ctx, AGENCY_SITE_KEYS["anem"], rep),
        "inrealestate": lambda rep: run_site(ctx, AGENCY_SITE_KEYS["inrealestate"], rep),
    }
    group_of = {"merrjep": "mj", "storefronts": "mj", "prishtina_io": "pio", "anem": "ane", "inrealestate": "inr"}
    group_ok = {}
    only.sort(key=RUN_ORDER.index)               # cheap sites first, MerrJep last (see WEIGHT)
    for n, name in enumerate(only):
        ctx.allot(only[n:])
        rep = ctx.report[name] = {"state": "running"}
        t0, deferred0 = time.time(), ctx.deferred
        log(f"▶ {name}")
        try:
            complete = runners[name](rep)
            rep["state"] = "ok" if not rep.get("failed") and not rep.get("failed_pages") else "partial"
            group_ok.setdefault(group_of[name], []).append(bool(complete))
        except Exception as e:                      # one broken source must not sink the run
            rep["state"], rep["error"] = "error", str(e)
            group_ok.setdefault(group_of[name], []).append(False)
            log(f"  ✗ {name}: {e}")
        rep["seconds"] = round(time.time() - t0)
        rep["deferred"] = ctx.deferred - deferred0
        rep["failed"] = max(0, rep.get("failed", 0) - rep["deferred"])      # out-of-budget is not a failure
        if rep["deferred"] and rep["state"] == "ok":
            rep["state"] = "partial"
        log(f"  {rep['state']}: {rep.get('seen', 0)} seen, {rep.get('new', 0)} new, {rep.get('failed', 0)} failed"
            + (f", {rep['deferred']} deferred to the next run (budget)" if rep["deferred"] else "") + f" ({rep['seconds']}s)")
        if ctx.full or ctx.new:
            storemod.save(store)                      # checkpoint: a long catch-up survives interruption

    # a group counts as swept only if every source feeding it completed
    needs = {"mj": {"merrjep", "storefronts"}, "pio": {"prishtina_io"}, "ane": {"anem"}, "inr": {"inrealestate"}}
    for g, srcs in needs.items():
        if srcs <= set(only) and all(group_ok.get(g, [False])):
            ctx.swept.add(g)
    if ctx.swept:
        prune(ctx)

    errors = [n for n, r in ctx.report.items() if r["state"] == "error"]
    meaningful = bool(ctx.new or ctx.updated or ctx.removed)
    first_build = not os.path.exists(build_site.OUT)
    out = None
    if meaningful or args.full or first_build:
        storemod.prune_skipped(store)
        store["updated"] = ctx.now if meaningful or first_build else store.get("updated")
        if args.full and len(errors) < len(only):
            store["last_full"] = ctx.now
        store["last_run"] = {"at": ctx.now, "mode": "full" if args.full else "quick",
                             "new": len(ctx.new), "price_changes": len(ctx.updated),
                             "removed": len(ctx.removed),
                             "sources": {n: {k: v for k, v in r.items() if k in ("state", "seen", "new", "failed", "deferred", "error")}
                                         for n, r in ctx.report.items()}}
        storemod.save(store)
        out = rebuild(store)
    else:
        log("\nNothing new — no files written.")

    summary = summarize(ctx, out)
    log("\n" + summary)
    if ctx.new:
        log("\nNew listings:")
        for rid in sorted(ctx.new)[:15]:
            r = store["listings"][rid]
            price = f"€{int(r['price']):,}" if r.get("price") else "ask"
            log(f"  {r.get('hood') or '?':16} {price:>9} {str(r.get('area') or '—') + ' m²':>9}  {r['title'][:70]}")
    gh = os.environ.get("GITHUB_STEP_SUMMARY")
    if gh:
        with open(gh, "a", encoding="utf-8") as f:
            f.write("## Listings update\n\n" + summary + "\n")
    return 1 if errors and len(errors) == len(only) else 0


if __name__ == "__main__":
    sys.exit(run())
