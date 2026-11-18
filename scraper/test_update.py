"""Offline tests for the incremental updater. Run:  python3 -m unittest test_update -v"""
import datetime
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import store as storemod
import update


def stub(n, posted="Sot 10:00", price=None, title=None):
    return {"id": f"mj-{n}", "source": "MerrJep", "url": f"https://x/shpallja/a/{n}",
            "title": title or f"Banesë në Prishtina e Re {n}", "price": price,
            "agency_slug": None, "posted": posted, "image": None}


def make_ctx(rows=(), skipped=(), full=False, **kw):
    st = storemod.empty()
    for r in rows:
        st["listings"][r["id"]] = r
    for i in skipped:
        st["skipped"][i] = "2026-01-01"
    return update.Ctx(st, full, [], 0, kw.get("force_prune", False))


def row(n, **kw):
    r = {"id": f"mj-{n}", "title": "Banesë", "price": 100000, "area": 60, "hood": "Prishtina e Re",
         "tier": "core", "date": "2026-11-01", "first_seen": "2026-11-01T00:00:00+00:00",
         "last_seen": "2026-11-01"}
    r.update(kw)
    return r


class CrawlCategory(unittest.TestCase):
    def pages(self, n_new_pages, total=60):
        """Pages 1..n_new_pages hold unknown ads; later pages only ads we already know."""
        calls = []

        def fake(p):
            calls.append(p)
            if p > total:
                return []
            base = p * 100
            return [stub(base + i) for i in range(5)]
        return fake, calls

    def test_quick_stops_after_two_quiet_batches(self):
        fake, calls = self.pages(0)
        known_rows = [row(p * 100 + i) for p in range(1, 61) for i in range(5)]
        # pages 1-2 contain something unknown, the rest are fully known
        ctx = make_ctx(rows=[r for r in known_rows if not r["id"].startswith(("mj-1", "mj-2"))
                             or int(r["id"][3:]) >= 300])
        with mock.patch.object(update, "list_page", fake):
            rep = {}
            stubs = update.crawl_category(ctx, 150, rep)
        # batch 1 (pages 1-3) has unknowns, batches 2 and 3 are quiet -> stop after page 9
        self.assertEqual(max(calls), 9)
        self.assertTrue(rep["stopped_early"])
        self.assertFalse(rep["complete"])
        self.assertTrue(any(s["id"] == "mj-100" for s in stubs))

    def test_full_goes_to_the_end_and_is_complete(self):
        fake, calls = self.pages(0, total=12)
        ctx = make_ctx(rows=[row(p * 100 + i) for p in range(1, 13) for i in range(5)], full=True)
        with mock.patch.object(update, "list_page", fake):
            rep = {}
            update.crawl_category(ctx, 12, rep)
        self.assertEqual(sorted(set(calls)), list(range(1, 13)))
        self.assertTrue(rep["complete"])

    def test_failed_page_makes_sweep_incomplete(self):
        def fake(p):
            return None if p == 4 else [stub(p * 100 + i) for i in range(3)]
        ctx = make_ctx(full=True)
        with mock.patch.object(update, "list_page", fake):
            rep = {}
            update.crawl_category(ctx, 9, rep)
        self.assertFalse(rep["complete"])
        self.assertEqual(rep["failed_pages"], [4])

    def test_dead_site_aborts_instead_of_hammering(self):
        calls = []
        ctx = make_ctx()
        with mock.patch.object(update, "list_page", lambda p: calls.append(p)):
            with self.assertRaises(RuntimeError):
                update.crawl_category(ctx, 150, {})
        self.assertLessEqual(len(calls), 9)

    def test_promoted_ads_repeating_on_every_page_do_not_block_early_stop(self):
        promoted = [stub(9000 + i) for i in range(5)]
        ctx = make_ctx(rows=[row(9000 + i) for i in range(5)] + [row(p * 100 + i) for p in range(1, 40) for i in range(5)])
        with mock.patch.object(update, "list_page", lambda p: promoted + [stub(p * 100 + i) for i in range(5)]):
            rep = {}
            update.crawl_category(ctx, 150, rep)
        self.assertTrue(rep["stopped_early"])


class KnownAds(unittest.TestCase):
    def test_price_drop_is_recorded(self):
        ctx = make_ctx(rows=[row(1)])
        update.refresh_known(ctx, stub(1, price=90000))
        r = ctx.store["listings"]["mj-1"]
        self.assertEqual((r["price"], r["price_prev"]), (90000, 100000))
        self.assertIn("mj-1", ctx.updated)

    def test_missing_stub_price_never_erases_a_price(self):
        ctx = make_ctx(rows=[row(1)])
        update.refresh_known(ctx, stub(1, price=None))
        self.assertEqual(ctx.store["listings"]["mj-1"]["price"], 100000)
        self.assertFalse(ctx.updated)

    def test_repost_moves_date_forward_only(self):
        ctx = make_ctx(rows=[row(1, date="2026-11-01")])
        update.refresh_known(ctx, stub(1, posted="Sot 09:00"))
        self.assertEqual(ctx.store["listings"]["mj-1"]["date"], datetime.date.today().isoformat())
        ctx2 = make_ctx(rows=[row(1, date="2999-01-01")])
        update.refresh_known(ctx2, stub(1, posted="Sot 09:00"))
        self.assertEqual(ctx2.store["listings"]["mj-1"]["date"], "2999-01-01")

    def test_seeing_a_skipped_ad_keeps_it_skipped(self):
        ctx = make_ctx(skipped=["mj-5"])
        update.refresh_known(ctx, stub(5))
        self.assertEqual(ctx.store["skipped"]["mj-5"], ctx.today)
        self.assertNotIn("mj-5", ctx.store["listings"])


class Ingest(unittest.TestCase):
    def test_only_unknown_in_scope_ads_are_fetched(self):
        fetched = []
        ctx = make_ctx(rows=[row(1)], skipped=["mj-2"])
        stubs = [stub(1), stub(2),                                              # known / rejected before
                 stub(3), stub(4, title="Banesë me qera në Dardani"),           # new / rental by title
                 stub(5, title="Banesë në Kalabri"),        # new / other lagje by title
                 stub(6, title="Banesë 70m2 në Qendër")]                        # new, nearby

        def fake_detail(h, s):
            return {**s, "area": 60, "hood": "Prishtina e Re" if s["id"] == "mj-3" else "Qendër",
                    "tier": "core" if s["id"] == "mj-3" else "nearby", "is_rental": False}

        def fake_fetch(url, **kw):
            fetched.append(url)
            return "<html>"

        with mock.patch.object(update.common, "fetch", fake_fetch), \
             mock.patch.object(update.merrjep, "parse_detail", fake_detail):
            rep = {}
            update.ingest_stubs(ctx, stubs, rep)
        self.assertEqual(sorted(u.rsplit("/", 1)[1] for u in fetched), ["3", "6"])
        self.assertEqual(ctx.new, {"mj-3", "mj-6"})
        self.assertTrue({"mj-4", "mj-5"} <= set(ctx.store["skipped"]))
        self.assertEqual(rep["new"], 2)
        self.assertEqual(ctx.store["listings"]["mj-3"]["first_seen"], ctx.now)

    def test_failed_detail_fetch_stays_unknown_so_it_is_retried(self):
        ctx = make_ctx()
        with mock.patch.object(update.common, "fetch", lambda *a, **k: None):
            rep = {}
            update.ingest_stubs(ctx, [stub(7)], rep)
        self.assertNotIn("mj-7", ctx.known)
        self.assertEqual(rep["failed"], 1)

    def test_out_of_scope_after_reading_the_page_is_remembered(self):
        ctx = make_ctx()
        with mock.patch.object(update.common, "fetch", lambda *a, **k: "<html>"), \
             mock.patch.object(update.merrjep, "parse_detail",
                               lambda h, s: {**s, "tier": "other", "hood": "Kalabria", "is_rental": False}):
            update.ingest_stubs(ctx, [stub(8, title="Banesë në shitje")], {})
        self.assertIn("mj-8", ctx.store["skipped"])
        self.assertFalse(ctx.new)

    def test_budget_stops_fetching_without_losing_state(self):
        ctx = make_ctx()
        ctx.deadline = 1                       # long past
        with mock.patch.object(update.common, "fetch", lambda *a, **k: "<html>") as f:
            rep = {}
            update.ingest_stubs(ctx, [stub(9)], rep)
        self.assertNotIn("mj-9", ctx.known)
        self.assertEqual(rep["failed"], 1)


class Scope(unittest.TestCase):
    def test_rejects_rentals_offices_houses_and_other_cities(self):
        for title in ("70m² rental apartment in Qafa", "ZYRE ME QERA LAKRISHTE", "Lokal në shitje 152m² në Qendër",
                      "Premises for sale 181m² in Bregu i Diellit", "Shtëpi 400m² në SHITJE te 4 Llullat",
                      "Shitet banesa në lagjën Qender – Shkup", "Banesë – Zyre 140m² me QIRA në Pejton"):
            self.assertTrue(update.out_of_scope({"title": title}), title)

    def test_keeps_real_apartments(self):
        for title in ("Apartment for sale 83m² in Mati 1 neighborhood", "Shitet banesa 84m2 ne qender te qafa",
                      "Penthouse 217m2 ne shitje ne Lagjen Arberia", "PENT HOUSE 96+40m2 kati 7 te VERA HILL",
                      "Banesa 60-110m2 te URTINA ne DRAGODAN RRUGE MITROVICES", "Banesë për shitje dhe qira në Dardani"):
            self.assertFalse(update.out_of_scope({"title": title}), title)

    def test_sweep_moves_existing_offenders_to_skipped(self):
        ctx = make_ctx(rows=[row(1, title="Zyre në shitje"), row(2, title="Banesë 60m² në shitje")])
        self.assertEqual(update.sweep_scope(ctx), 1)
        self.assertIn("mj-1", ctx.store["skipped"])
        self.assertIn("mj-2", ctx.store["listings"])


class Budget(unittest.TestCase):
    def ctx(self, minutes):
        return update.Ctx(storemod.empty(), False, [], minutes, False)

    def test_no_budget_means_no_deadline(self):
        c = self.ctx(0)
        c.allot(["anem", "merrjep"])
        self.assertFalse(c.expired())

    def test_merrjep_cannot_take_the_whole_budget(self):
        import time
        c = self.ctx(45)
        order = sorted(update.QUICK_SOURCES, key=update.RUN_ORDER.index)
        self.assertEqual(order[-1], "merrjep")
        c.allot(order)
        first = c.deadline - time.time()
        self.assertLess(first, 45 * 60 * 0.25)         # a small site gets a small slice
        c.allot(["merrjep"])                            # last one inherits everything left
        self.assertGreater(c.deadline - time.time(), 40 * 60)

    def test_slice_of_a_stalled_source_does_not_leak_into_the_next(self):
        import time
        c = self.ctx(10)
        c.allot(["anem", "inrealestate", "merrjep"])
        c.budget_end = time.time() - 1                  # budget gone entirely
        c.allot(["inrealestate", "merrjep"])
        self.assertTrue(c.expired())


class Prune(unittest.TestCase):
    def days_ago(self, n):
        return (datetime.date.today() - datetime.timedelta(days=n)).isoformat()

    def test_removes_only_past_grace_and_only_in_swept_groups(self):
        ctx = make_ctx(rows=[row(1, last_seen=self.days_ago(1)), row(2, last_seen=self.days_ago(30)),
                             row(3, last_seen=self.days_ago(30)), row(4, last_seen=self.days_ago(2)),
                             row(5, last_seen=self.days_ago(1)), row(6, last_seen=self.days_ago(1)),
                             {**row(7), "id": "pio-7", "last_seen": self.days_ago(60)}])
        ctx.swept = {"mj"}
        update.prune(ctx)
        self.assertEqual(sorted(ctx.removed), ["mj-2", "mj-3"])
        self.assertIn("pio-7", ctx.store["listings"])           # pio wasn't swept

    def test_refuses_mass_removal_without_force(self):
        ctx = make_ctx(rows=[row(i, last_seen=self.days_ago(40)) for i in range(1, 5)] + [row(9)])
        ctx.swept = {"mj"}
        update.prune(ctx)
        self.assertEqual(ctx.removed, [])
        ctx.force_prune = True
        update.prune(ctx)
        self.assertEqual(len(ctx.removed), 4)


class StoreFile(unittest.TestCase):
    def test_roundtrip_and_stable_one_record_per_line(self):
        st = storemod.empty()
        st["listings"] = {"mj-2": row(2), "mj-1": row(1, title="Ç ë 𝕌")}
        st["skipped"] = {"mj-9": "2026-11-01", "mj-3": "2026-11-02"}
        st["updated"] = "2026-11-18T10:00:00+00:00"
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "store.json")
            storemod.save(st, p)
            with open(p, encoding="utf-8") as fh:
                first = fh.read()
            back = storemod.load(p)
            self.assertEqual(back["listings"], st["listings"])
            self.assertEqual(back["skipped"], st["skipped"])
            self.assertEqual(back["updated"], st["updated"])
            storemod.save(back, p)
            with open(p, encoding="utf-8") as fh:
                self.assertEqual(first, fh.read())                           # byte-stable
            self.assertTrue(first.index('"mj-1"') < first.index('"mj-2"'))  # sorted
            self.assertEqual(sum(1 for ln in first.splitlines() if ln.startswith('{"')), 2)


if __name__ == "__main__":
    unittest.main()
