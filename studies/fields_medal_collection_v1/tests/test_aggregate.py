"""Offline validation tests with synthetic facts, independent of collected birthdays."""
import copy
import importlib.util
import pathlib
import sys
import unittest


SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "aggregate.py"
spec = importlib.util.spec_from_file_location("fields_aggregate", SCRIPT)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
aggregate = module.aggregate


def fixture():
    rows, records = [], []
    for i in range(68):
        main = i < 64
        name = "Grigori Perelman" if i == 13 else "Person " + str(i)
        row = {"fields_id": "fields-" + str(i), "name": name,
               "award_year": 2022 if main else 2026,
               "original_through_2025": main,
               "award_declined": i == 13,
               "roster_source_url": "https://example.edu/roster"}
        url = "https://example.edu/person/" + str(i)
        claim = {"date_raw": "1 January 1987", "year": 1987, "month": 1,
                 "day": 1, "precision": "day", "calendar": "not_stated",
                 "source_url": url, "source_type": "institutional_biography",
                 "source_status": "body_observed", "excerpt": "Born 1 January 1987",
                 "identity_note": "Page identifies " + name}
        record = {"fields_id": row["fields_id"], "name": name,
                  "award_year": row["award_year"], "status": "day_source_verified",
                  "claims": [claim], "sources": [{"url": url,
                    "status": "body_observed", "access_method": "offline_fixture",
                    "note": "Synthetic body source"}],
                  "search_queries_used": 1, "body_candidates_opened": 1,
                  "direct_cv_attempts": 0, "checked_at_utc": "2026-10-29T00:00:00Z",
                  "review_note": "Synthetic validation fixture"}
        rows.append(row)
        records.append(record)
    roster = {"rows": rows, "main_roster_count": 64, "extension2026_count": 4}
    inputs = [{"schema_version": 1, "shard_id": "synthetic", "records": records}]
    return roster, inputs


class AggregateTests(unittest.TestCase):
    def setUp(self):
        self.roster, self.inputs = fixture()

    def run_aggregate(self):
        return aggregate(self.roster, self.inputs)

    def test_exact_roster_and_extension_split(self):
        records, summary = self.run_aggregate()
        self.assertEqual(len(records), 68)
        self.assertEqual(sum(r["cohort"] == "main" for r in records), 64)
        self.assertEqual(sum(r["cohort"] == "extension2026" for r in records), 4)
        self.assertEqual(summary["main"]["status_counts"]["day_source_verified"], 64)
        self.assertEqual(summary["extension2026"]["status_counts"]["day_source_verified"], 4)
        self.assertEqual(summary["analysis_record_count"], 0)
        self.assertEqual(summary["bazi_record_count"], 0)
        self.assertFalse(summary["final_analysis_cohort_freeze"])

    def test_duplicate_record_id_rejected(self):
        self.inputs[0]["records"].append(copy.deepcopy(self.inputs[0]["records"][0]))
        with self.assertRaises(ValueError):
            self.run_aggregate()

    def test_missing_record_rejected(self):
        self.inputs[0]["records"].pop()
        with self.assertRaises(ValueError):
            self.run_aggregate()

    def test_roster_identity_and_award_year_must_match(self):
        for field, value in [("name", "Wrong person"), ("award_year", 2018)]:
            with self.subTest(field=field):
                roster, inputs = fixture()
                inputs[0]["records"][0][field] = value
                with self.assertRaises(ValueError):
                    aggregate(roster, inputs)

    def test_body_claim_cannot_use_blocked_source_ledger(self):
        self.inputs[0]["records"][0]["sources"][0]["status"] = "blocked"
        with self.assertRaises(ValueError):
            self.run_aggregate()

    def test_each_collection_budget_is_enforced(self):
        for field, value in [("search_queries_used", 3),
                             ("body_candidates_opened", 3), ("direct_cv_attempts", 2)]:
            with self.subTest(field=field):
                roster, inputs = fixture()
                inputs[0]["records"][0][field] = value
                with self.assertRaises(ValueError):
                    aggregate(roster, inputs)

    def test_month_precision_cannot_have_day_component(self):
        self.inputs[0]["records"][0]["claims"][0]["precision"] = "month"
        with self.assertRaises(ValueError):
            self.run_aggregate()

    def test_partial_dates_are_preserved_without_day_padding(self):
        rec = self.inputs[0]["records"][0]
        rec["claims"][0].update(precision="month", day=None, date_raw="January 1987")
        rec["status"] = "month_only"
        records, _ = self.run_aggregate()
        self.assertEqual(next(r for r in records if r["fields_id"] == "fields-0")["source_date_components_iso"], "1987-01")
        self.assertEqual(next(r for r in records if r["fields_id"] == "fields-0")["derived_status"], "month_only")
        rec["claims"][0].update(precision="year", month=None, date_raw="1987")
        rec["status"] = "year_only"
        records, _ = self.run_aggregate()
        self.assertEqual(next(r for r in records if r["fields_id"] == "fields-0")["source_date_components_iso"], "1987")
        self.assertEqual(next(r for r in records if r["fields_id"] == "fields-0")["derived_status"], "year_only")

    def test_conflicting_days_kept_without_selected_winner(self):
        rec = self.inputs[0]["records"][0]
        other = copy.deepcopy(rec["claims"][0])
        other.update(day=2, date_raw="2 January 1987",
                     source_url="https://other.edu/person/0", excerpt="Born 2 January 1987")
        rec["claims"].append(other)
        rec["sources"].append({"url": other["source_url"], "status": "body_observed",
                               "access_method": "offline_fixture", "note": "Second source"})
        rec["body_candidates_opened"] = 2
        records, _ = self.run_aggregate()
        self.assertEqual(next(r for r in records if r["fields_id"] == "fields-0")["derived_status"], "conflicting_sources")
        self.assertEqual(next(r for r in records if r["fields_id"] == "fields-0")["source_date_components_iso"], "")
        self.assertEqual(len(next(r for r in records if r["fields_id"] == "fields-0")["claims"]), 2)

    def test_birth_after_1985_and_declined_award_are_retained(self):
        records, _ = self.run_aggregate()
        self.assertEqual(next(r for r in records if r["fields_id"] == "fields-0")["source_date_components_iso"], "1987-01-01")
        perelman = next(r for r in records if r["name"] == "Grigori Perelman")
        self.assertTrue(perelman["award_declined"])

    def test_snippet_is_retained_but_never_counts_as_body_coverage(self):
        rec = self.inputs[0]["records"][0]
        rec["claims"][0]["source_status"] = "search_snippet_only"
        rec["sources"][0]["status"] = "search_snippet_only"
        records, summary = self.run_aggregate()
        self.assertEqual(next(r for r in records if r["fields_id"] == "fields-0")["derived_status"], "not_found")
        self.assertEqual(next(r for r in records if r["fields_id"] == "fields-0")["source_date_components_iso"], "")
        self.assertEqual(len(next(r for r in records if r["fields_id"] == "fields-0")["claims"]), 1)
        self.assertEqual(summary["main"]["status_counts"]["day_source_verified"], 63)

    def test_credential_urls_and_non_http_urls_rejected(self):
        for url in ["https://user:secret@example.edu/bio", "file:///tmp/bio"]:
            with self.subTest(url=url):
                roster, inputs = fixture()
                rec = inputs[0]["records"][0]
                rec["claims"][0]["source_url"] = url
                rec["sources"][0]["url"] = url
                with self.assertRaises(ValueError):
                    aggregate(roster, inputs)


if __name__ == "__main__":
    unittest.main()
