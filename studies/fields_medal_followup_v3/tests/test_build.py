"""Synthetic offline checks for follow-up v3 patch integration."""
import copy
import importlib.util
from pathlib import Path
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "build.py"
SPEC = importlib.util.spec_from_file_location("fields_followup_v3_build", SCRIPT)
build = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(build)


class PatchTests(unittest.TestCase):
    def setUp(self):
        self.url = "https://www.heidelberg-laureate-forum.org/laureate/caucher-birkar/"
        self.roster = {"rows": [{"fields_id": "fields-one", "name": "Caucher Birkar", "award_year": 2018,
                                  "original_through_2025": True, "award_declined": False}]}
        snippet = {"date_raw": "July 1978", "year": 1978, "month": 7, "day": None,
                   "precision": "month", "calendar": "not_stated", "source_url": self.url,
                   "source_type": "institutional_biography", "source_status": "search_snippet_only",
                   "excerpt": "Born in July 1978", "identity_note": "Named laureate snippet."}
        self.inputs = [{"schema_version": 1, "records": [{"fields_id": "fields-one", "name": "Caucher Birkar",
                       "award_year": 2018, "status": "blocked", "claims": [snippet],
                       "sources": [{"url": self.url, "status": "search_snippet_only", "access_method": "search", "note": "lead only"}],
                       "search_queries_used": 2, "body_candidates_opened": 2, "direct_cv_attempts": 1,
                       "checked_at_utc": None, "review_note": "Original bounded pass."}]}]
        self.patch = {"name": "Caucher Birkar", "date_raw": "July, 1978", "year": 1978,
                      "month": 7, "day": None, "precision": "month", "source_url": self.url,
                      "excerpt": "July, 1978, Marivan, Iran", "source_status": "body_observed",
                      "calendar": "not_stated", "source_type": "institutional_biography"}
        self.log = {"body_requests": [{"name": "Caucher Birkar", "url": self.url, "status": "body_observed",
                      "current_round_search_queries_used": 1, "current_round_body_opens": 1,
                      "timestamp_utc": None, "award_identity": "Named 2018 Fields laureate."}]}

    def test_month_kept_partial_and_old_snippet_and_budgets_preserved(self):
        original = copy.deepcopy(self.inputs)
        patched, audit = build.apply_patches(self.roster, self.inputs, [self.patch], self.log)
        self.assertEqual(self.inputs, original)
        record = patched[0]["records"][0]
        self.assertEqual(record["status"], "month_only")
        self.assertEqual(record["claims"][0], original[0]["records"][0]["claims"][0])
        self.assertEqual(record["claims"][-1]["precision"], "month")
        self.assertIsNone(record["claims"][-1]["day"])
        self.assertEqual(record["claims"][-1]["source_status"], "body_observed")
        for key in ("search_queries_used", "body_candidates_opened", "direct_cv_attempts"):
            self.assertEqual(record[key], original[0]["records"][0][key])
        self.assertEqual(audit["actor"], "worker")
        self.assertEqual(audit["patches"][0]["search_queries_used"], 1)
        self.assertIsNone(audit["patches"][0]["at_utc"])

    def test_duplicate_and_identity_mismatches_rejected(self):
        bad_id = dict(self.patch, fields_id="fields-wrong")
        unknown = dict(self.patch, name="Unknown Person")
        for patches in ([self.patch, self.patch], [bad_id], [unknown]):
            with self.subTest(patches=patches), self.assertRaises(ValueError):
                build.apply_patches(self.roster, self.inputs, {"records": patches}, self.log)

    def test_day_requires_matching_body_url_and_preserves_zero_new_searches(self):
        day = {key: value for key, value in self.patch.items() if key not in {"year", "month", "day", "precision", "date_raw"}}
        day.update(date="1978-07-02", excerpt="July 2, 1978, Marivan, Iran")
        log = copy.deepcopy(self.log)
        log["body_requests"][0]["current_round_search_queries_used"] = 0
        patched, audit = build.apply_patches(self.roster, self.inputs, [day], log)
        self.assertEqual(patched[0]["records"][0]["claims"][-1]["day"], 2)
        self.assertEqual(audit["patches"][0]["search_queries_used"], 0)
        wrong_url = copy.deepcopy(log)
        wrong_url["body_requests"][0]["url"] = "https://www.heidelberg-laureate-forum.org/laureate/other/"
        with self.assertRaises(ValueError):
            build.apply_patches(self.roster, self.inputs, [day], wrong_url)
        missing = dict(self.patch)
        del missing["month"]
        with self.assertRaises(ValueError):
            build.apply_patches(self.roster, self.inputs, [missing], self.log)


if __name__ == "__main__":
    unittest.main()
