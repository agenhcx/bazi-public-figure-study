import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

import pandas as pd

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("collect_cohorts", HERE / "collect_cohorts.py")
c = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(c)


def row(fid, rating=2500, dob="1990-01-02", hemisphere="north", eligible=True):
    return {"fide_id": str(fid), "identity_bridge_modern_fide_id": str(fid), "name": f"P{fid}",
            "rating": rating, "exact_dob_frozen": dob, "birthplace_hemisphere": hemisphere,
            "eligible": eligible, "birth_year": "1990", "evidence_eligible": eligible}


def record(**changes):
    r = {"fide": "1", "person": "http://www.wikidata.org/entity/Q1", "dob": "+1990-01-02T00:00:00Z",
         "precision": "11", "calendar": "http://www.wikidata.org/entity/Q1985727",
         "birthplace": "http://www.wikidata.org/entity/Q2", "lat": "45", "lon": "5"}
    r.update(changes)
    return r


class CollectionTests(unittest.TestCase):
    def test_complete_ties_and_excluded_ids(self):
        rows = [row(1, 2700), row(2, 2600), row(3, 2600), row(4, 2500)]
        selected, cutoff = c.top_with_ties(rows, 2)
        self.assertEqual([r["fide_id"] for r in selected], ["1", "2", "3"])
        self.assertEqual(cutoff, 2600)
        selected, cutoff = c.top_with_ties(rows, 2, {"1", "2"})
        self.assertEqual([r["fide_id"] for r in selected], ["3", "4"])
        self.assertEqual(cutoff, 2500)

    def test_insufficient_eligible_does_not_silently_shrink(self):
        self.assertEqual(c.top_with_ties([row(1, eligible=False)], 1), (None, None))

    def test_id_and_date_validation(self):
        self.assertEqual(c.canonical_id({"fide_id": "00012"}), "12")
        self.assertEqual(c.canonical_id({"fide_id": "12", "identity_bridge_modern_fide_id": "20"}), "20")
        for bad in ("12.5", "-3", "0", "nan"):
            with self.assertRaises(ValueError):
                c.canonical_id({"fide_id": bad})
        self.assertEqual(c.valid_dob("2000-02-29", "2013", "2000")[0], "2000-02-29")
        for dob in ("1900-02-29", "2013-01-02", "1990-2-01", "0000-01-01"):
            self.assertIsNone(c.valid_dob(dob, "2013")[0])
        self.assertEqual(c.valid_dob("1990-01-01", "2013", "1991")[1], "birth_year_mismatch")

    def test_gregorian_exact_best_rank_records(self):
        good = c.metadata_from_records("1", {"records": [record()], "retrieved_utc": "now"})
        self.assertTrue(good["evidence_eligible"])
        self.assertEqual(good["exact_dob_frozen"], "1990-01-02")
        for changes in ({"calendar": "http://www.wikidata.org/entity/Q1985786"},
                        {"precision": "9"}, {"before": "1"}, {"lat": "-45"}):
            result = c.metadata_from_records("1", {"records": [record(**changes)], "retrieved_utc": "now"})
            self.assertFalse(result["evidence_eligible"])

    def test_wikidata_person_dob_and_hemisphere_ambiguity(self):
        for extra in (record(person="http://www.wikidata.org/entity/Q3"),
                      record(dob="+1990-01-03T00:00:00Z"), record(lat="-5")):
            result = c.metadata_from_records("1", {"records": [record(), extra], "retrieved_utc": "now"})
            self.assertFalse(result["evidence_eligible"])
        empty = c.metadata_from_records("1", {"records": [], "retrieved_utc": "now"})
        self.assertFalse(empty["evidence_eligible"])

    def test_current_query_includes_calendar_and_best_rank(self):
        query = c.query_text(["1", "2"])
        self.assertIn("wikibase:BestRank", query)
        self.assertIn("wikibase:timeCalendarModel", query)
        self.assertIn("wikibase:timeBefore", query)
        self.assertIn('VALUES ?fide { "1" "2" }', query)

    def test_failed_request_never_becomes_negative_cache(self):
        class FailedSession:
            def get(self, *args, **kwargs):
                raise OSError("network unavailable")
        with tempfile.TemporaryDirectory() as tmp:
            path, cache = Path(tmp) / "cache.json", {}
            with self.assertRaises(RuntimeError):
                c.fetch_records(["1"], FailedSession(), cache, path, retries=1, delay=0)
            self.assertEqual(cache, {})
            self.assertFalse(path.exists())

    def test_genuine_empty_response_is_cached_and_resume_skips_it(self):
        class Response:
            def raise_for_status(self):
                pass
            def json(self):
                return {"results": {"bindings": []}}
        class Session:
            calls = 0
            def get(self, *args, **kwargs):
                self.calls += 1
                return Response()
        with tempfile.TemporaryDirectory() as tmp:
            path, cache, session = Path(tmp) / "cache.json", {}, Session()
            c.fetch_records(["1", "2"], session, cache, path, delay=0)
            c.fetch_records(["1"], session, cache, path, delay=0)
            self.assertEqual(session.calls, 1)
            self.assertEqual(json.loads(path.read_text())["1"]["records"], [])

    def test_frozen_snapshot_evidence_wins_and_is_never_fetched(self):
        a, b = row(1), row(1, dob="1990-01-03")
        seeds = {"2013": {"1": a}, "2023": {"1": b, "2": row(2)}}
        resolver = c.Resolver(seeds, None, {}, Path("unused"), 1, 1, 0)
        with patch.object(c, "fetch_records") as fetch:
            resolver.prefetch(["1", "2", "3"])
            self.assertEqual(fetch.call_args.args[0], ["3"])
        self.assertEqual(resolver.evidence("1", "2013")["exact_dob_frozen"], "1990-01-02")
        self.assertEqual(resolver.evidence("1", "2023")["exact_dob_frozen"], "1990-01-03")

    def test_cross_snapshot_conflicts_are_detected(self):
        self.assertEqual(c.find_conflicts({"a": [row(1)], "b": [row(1)]}), [])
        conflicts = c.find_conflicts({"a": [row(1)], "b": [row(1, dob="1990-01-03")]})
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]["canonical_id"], "1")

    def test_cross_snapshot_reuse_rechecks_current_year(self):
        old = row(1, eligible=False)
        old["wikidata_person_qids"] = "Q1"
        seeds = {"2013": {"1": old}, "2023": {}}
        resolver = c.Resolver(seeds, None, {}, Path("unused"), 1, 1, 0)
        self.assertFalse(resolver.evidence("1", "2013")["evidence_eligible"])
        reused = resolver.evidence("1", "2023")
        self.assertTrue(c.adjudicate({"fide_id": "1", "birth_year": "1990"}, reused, "2023")["eligible"])
        self.assertFalse(c.adjudicate({"fide_id": "1", "birth_year": "1991"}, reused, "2023")["eligible"])
        self.assertEqual(reused["evidence_reused_from_snapshot"], "2013-01")

    def test_scan_completes_elo_group_and_refills_only_new(self):
        population = pd.DataFrame([{"fide_id": str(i), "name": f"P{i}", "rating": r,
                                     "birth_year": "1990"} for i, r in [(1, 2700), (2, 2600), (3, 2600), (4, 2500)]])
        class Resolver:
            def prefetch(self, ids):
                pass
            def evidence(self, fid, year):
                return row(fid)
        with tempfile.TemporaryDirectory() as tmp:
            full, new, audit, fcut, ncut = c.scan(population, "2013", Resolver(), 2,
                                                {"1", "2"}, Path(tmp) / "audit.csv", batch_size=2)
        self.assertEqual(len(full), 3)
        self.assertEqual([r["fide_id"] for r in new], ["3", "4"])
        self.assertEqual((fcut, ncut), (2600, 2500))
        self.assertEqual(len(audit), 4)

    def test_frozen_2013_anchor_checks_all_ratings(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "old.csv"
            path.write_text("fide_id,rating\n1,2500\n")
            c.check_snapshot_anchors(pd.DataFrame([{"fide_id": "1", "rating": 2500}]), path, "2013")
            with self.assertRaises(ValueError):
                c.check_snapshot_anchors(pd.DataFrame([{"fide_id": "1", "rating": 2501}]), path, "2013")


class PopulationParserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # The legacy parser module imports requests at module scope, but these
        # tests exercise only its pure fixed-width functions without HTTP.
        with patch.dict(sys.modules, {"requests": types.ModuleType("requests")}):
            cls.parser = c.import_module(HERE.parents[1] / "chess_2023_cohorts_v1/build_chess_2023_cohorts_v2.py", "legacy_test_parser")

    def parse(self, header_year="13", request_year="2013", mutation=None, without_foa=False):
        header = ("ID Number      Name                                                         "
                  f"Fed Sex Tit  WTit OTit           FOA JAN{header_year} Gms K  B-day Flag")
        lines = [
            "25121731       A C J John                                                   IND M                                1063  0   40 1987  i",
            "5045886        A K, Kalshyan                                                IND M                                1671  0   20 1964",
            "4804929        A-ALI, Sali Abbas Abdulzahra                                 IRQ F   WFM  WFM                     1876  13  20 2001  w",
        ]
        if without_foa:
            start = header.index("FOA")
            header = header[:start] + header[start + 4:]
            header = header.replace("JAN13", "jan13")
            lines = [line[:start] + line[start + 4:] for line in lines]
        if mutation:
            lines = mutation(lines)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "population.txt"
            path.write_text(header + "\n" + "\n".join(lines) + "\n")
            return c.parse_population(path, request_year, self.parser, minimum_rows=3)

    def test_january2013_layout_and_active_filter(self):
        table = self.parse(without_foa=True)
        self.assertEqual(len(table), 1)
        self.assertEqual(table.iloc[0]["fide_id"], "5045886")
        self.assertEqual(table.iloc[0]["rating"], 1671)
        self.assertEqual(table.iloc[0]["birth_year"], "1964")
        self.assertEqual(table.iloc[0]["snapshot"], "2013-01")

    def test_january2023_layout(self):
        self.assertEqual(self.parse("23", "2023").iloc[0]["snapshot"], "2023-01")

    def test_wrong_snapshot_header_rejected(self):
        with self.assertRaises(ValueError):
            self.parse("23", "2013")

    def test_noninteger_rating_rejected_without_truncation(self):
        with self.assertRaises(ValueError):
            self.parse(mutation=lambda lines: [line.replace("1671", "16.1") for line in lines])


if __name__ == "__main__":
    unittest.main()
