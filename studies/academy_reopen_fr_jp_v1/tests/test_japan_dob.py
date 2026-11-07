"""Synthetic offline checks; no assumption that the national cohort is known."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest


def roster():
    return [
        {"member_key": "jpa:one", "name_jp": "人物 一", "name_en": "PERSON One"},
        {"member_key": "jpa:two", "name_jp": "人物 二", "name_en": "PERSON Two"},
        {"member_key": "jpa:three", "name_jp": "人物 三", "name_en": "PERSON Three"},
    ]


def seed(index=0):
    person = roster()[index]
    return dict(person, status="day_source_verified", date="1990-02-03", claims=[{
        "date_raw": "1990年2月3日", "year": 1990, "month": 2, "day": 3,
        "precision": "day", "calendar": "not_stated",
        "source_url": "https://museum.example.jp/biography",
        "source_type": "institutional_biography", "source_status": "body_observed",
        "excerpt": "人物 一 1990年2月3日生", "identity_note": "Named institutional biography.",
    }])


class JapanDOBTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(__file__).resolve().parents[1] / "scripts" / "assemble_japan_dob.py"
        spec = importlib.util.spec_from_file_location("japan_dob_assembly_under_test", path)
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)

    def run_assembly(self, rows, records):
        return self.module.assemble(rows, {"schema_version": 1, "records": records})

    def test_duplicate_ids_and_wrong_identity_are_rejected(self):
        with self.assertRaises(ValueError):
            self.run_assembly(roster() + [copy.deepcopy(roster()[0])], [seed()])
        wrong = seed()
        wrong["name_jp"] = "別人"
        with self.assertRaises(ValueError):
            self.run_assembly(roster(), [wrong])
        with self.assertRaises(ValueError):
            self.run_assembly(roster(), [seed(), seed()])
        wrong_id = seed()
        wrong_id["member_key"] = "jpa:absent"
        with self.assertRaises(ValueError):
            self.run_assembly(roster(), [wrong_id])

    def test_unknown_status_and_snippet_verified_day_are_rejected(self):
        unknown = seed()
        unknown["status"] = "unchecked_but_verified"
        with self.assertRaises(ValueError):
            self.run_assembly(roster(), [unknown])
        snippet = seed()
        snippet["claims"][0]["source_status"] = "search_snippet_only"
        with self.assertRaises(ValueError):
            self.run_assembly(roster(), [snippet])

    def test_month_is_not_padded_and_unprocessed_is_not_not_found(self):
        month = seed()
        month.update(status="month_only", date="1990-02")
        month["claims"][0].update(date_raw="1990年2月", day=None, precision="month")
        absent = seed(1)
        absent.update(status="not_found", date=None, claims=[])
        master, ledger, missing, summary = self.run_assembly(roster(), [month, absent])
        by_id = {r["member_key"]: r for r in master}
        self.assertEqual(by_id["jpa:one"]["source_date_components_iso"], "1990-02")
        self.assertIsNone(ledger[0]["day"])
        self.assertEqual(by_id["jpa:two"]["dob_status"], "not_found")
        self.assertEqual(by_id["jpa:three"]["dob_status"], "not_processed")
        self.assertEqual(summary["processed_count"], 2)
        self.assertEqual(summary["not_processed_count"], 1)
        self.assertIsNone(summary["full_japan_missing_count"])
        self.assertEqual(len(missing), 3)
        self.assertTrue(all(r["final_cohort_accepted"] is False for r in master))
        self.assertTrue(all(r["bazi_variables_computed"] == 0 for r in master))

    def test_source_supplied_solar_and_old_calendar_are_preserved_together(self):
        solar = seed()
        solar["date"] = "1871-02-07"
        solar["claims"][0].update(date_raw="1871年2月7日", year=1871, month=2, day=7,
                                  source_supplied_conversion=True,
                                  collector_calendar_conversion_performed=False,
                                  normalization_note="Era-year transcription only.")
        old = {"date_raw": "旧暦明治3年12月18日", "calendar": "lunar_explicit",
               "source_url": solar["claims"][0]["source_url"], "source_status": "body_observed",
               "note": "Source itself supplies the equivalent modern solar date."}
        solar["source_original_calendar_birth"] = old
        master, ledger, missing, summary = self.run_assembly(roster(), [solar])
        self.assertEqual(master[0]["dob_status"], "day_source_verified")
        self.assertEqual(ledger[0]["calendar"], "not_stated")
        self.assertEqual(json.loads(ledger[0]["source_original_calendar_birth_json"]), old)
        self.assertEqual(ledger[0]["normalization_note"], "Era-year transcription only.")
        self.assertEqual(summary["day_body_verified_count"], 1)

    def test_invalid_dates_and_precision_filling_are_rejected(self):
        invalid = seed()
        invalid["date"] = "1990-02-30"
        invalid["claims"][0]["day"] = 30
        with self.assertRaises(ValueError):
            self.run_assembly(roster(), [invalid])
        filled = seed()
        filled["status"] = "month_only"
        filled["claims"][0]["precision"] = "month"
        with self.assertRaises(ValueError):
            self.run_assembly(roster(), [filled])


if __name__ == "__main__":
    unittest.main()
