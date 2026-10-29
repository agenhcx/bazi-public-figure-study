"""Focused offline patch validation; no network or collected-date fixtures."""
import copy
import importlib.util
from pathlib import Path
import unittest


BUILD_PATH = Path(__file__).resolve().parents[1] / "scripts" / "build.py"
SPEC = importlib.util.spec_from_file_location("fields_followup_build", BUILD_PATH)
BUILD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILD)


class PatchTests(unittest.TestCase):
    def setUp(self):
        self.roster = {"rows": [{
            "fields_id": "fields-fixture-1", "name": "Alessio Figalli",
            "award_year": 2018, "original_through_2025": True,
            "award_declined": False,
        }]}
        self.inputs = [{"schema_version": 1, "records": [{
            "fields_id": "fields-fixture-1", "name": "Alessio Figalli",
            "award_year": 2018, "status": "month_only",
            "claims": [{
                "date_raw": "April 1984", "year": 1984, "month": 4,
                "day": None, "precision": "month", "calendar": "not_stated",
                "source_url": "https://example.edu/figalli/cv",
                "source_type": "first_person_cv", "source_status": "body_observed",
                "excerpt": "Born: April 1984", "identity_note": "Named fixture CV.",
            }],
            "sources": [{
                "url": "https://example.edu/figalli/cv", "status": "body_observed",
                "access_method": "previous_pass", "note": "Fixture source.",
            }],
            "search_queries_used": 2, "body_candidates_opened": 0,
            "direct_cv_attempts": 1, "checked_at_utc": None,
            "review_note": "Original month precision is preserved as a claim.",
        }]}]
        self.patch = {
            "name": "Alessio Figalli", "date": "1984-04-02",
            "source_url": "https://www.heidelberg-laureate-forum.org/laureate/alessio-figalli/",
            "excerpt": "April 2, 1984, Rome, Italy",
            "source_status": "body_observed", "calendar": "not_stated",
            "source_type": "institutional_biography",
        }

    def test_identity_mismatch_or_unknown_name_rejected(self):
        for change in ({"fields_id": "fields-wrong-id"}, {"name": "Unknown Person"}):
            with self.subTest(change=change):
                patch = dict(self.patch, **change)
                with self.assertRaises(ValueError):
                    BUILD.apply_patches(self.roster, self.inputs, {"records": [patch]})

    def test_duplicate_patch_rejected(self):
        for with_id in (False, True):
            with self.subTest(with_id=with_id):
                patch = copy.deepcopy(self.patch)
                if with_id:
                    patch["fields_id"] = "fields-fixture-1"
                with self.assertRaises(ValueError):
                    BUILD.apply_patches(self.roster, self.inputs,
                                        {"records": [patch, copy.deepcopy(patch)]})

    def test_patch_preserves_v1_inputs_budgets_and_records_separate_round(self):
        original = copy.deepcopy(self.inputs)
        patched, audit = BUILD.apply_patches(self.roster, self.inputs,
                                             {"records": [self.patch]})
        self.assertEqual(self.inputs, original)
        row = patched[0]["records"][0]
        old = original[0]["records"][0]
        for budget in ("search_queries_used", "body_candidates_opened", "direct_cv_attempts"):
            self.assertEqual(row[budget], old[budget])
        self.assertEqual(row["claims"][0], old["claims"][0])
        self.assertEqual(len(row["claims"]), 2)
        self.assertEqual(row["status"], "day_source_verified")
        new_claim = row["claims"][1]
        self.assertEqual((new_claim["year"], new_claim["month"], new_claim["day"]),
                         (1984, 4, 2))
        self.assertEqual(new_claim["calendar"], "not_stated")
        self.assertTrue(any(source["url"] == self.patch["source_url"]
                            and source["status"] == "body_observed"
                            for source in row["sources"]))
        self.assertEqual(len(audit["patches"]), 1)
        event = audit["patches"][0]
        self.assertEqual(event["fields_id"], "fields-fixture-1")
        self.assertEqual(event["name"], "Alessio Figalli")
        self.assertEqual(event["search_queries_used"], 1)
        self.assertEqual(event["body_candidates_opened"], 1)
        self.assertEqual(event["direct_cv_attempts"], 0)
        self.assertIsNone(event["at_utc"])


if __name__ == "__main__":
    unittest.main()
