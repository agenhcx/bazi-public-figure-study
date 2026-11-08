import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("build_japan", ROOT / "scripts" / "build_japan.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def person(key="a"):
    return dict(member_key=key, name_jp="Example " + key, broad_section_supported="2",
                section_evidence_status="test", restored_layers=["restored435"])


def claim(key="a", **overrides):
    c = dict(member_key=key, name_jp="Example " + key, body_verified=True,
             identity_body_supported=True, source_url="https://example.org/" + key,
             raw_birth_statement="Born 1900-02-03", identity_support="named scientist and matching institution",
             year=1900, month=2, day=3, precision="day", calendar="not_stated", calendar_comparable=True)
    c.update(overrides)
    return c


class JapanEvidenceTests(unittest.TestCase):
    def test_name_only_authority_never_fills_birthdate(self):
        master, _, _, summary = m.assemble([person()], [], {}, set(), {"a": {"match_status": "unique_name_match", "birth_year": "1900"}})
        self.assertEqual(master[0]["dob_status"], "not_institutionally_processed")
        self.assertEqual(master[0]["source_date_components_iso"], "")
        self.assertEqual(summary["body_day_no_known_conflict"], 0)
        with self.assertRaises(ValueError):
            m.assemble([person()], [claim(identity_body_supported=False)], {}, set(), {})

    def test_precision_calendar_and_same_person_guards(self):
        for bad in [claim(precision="year"), claim(name_jp="Another person"), claim(day=30), claim(body_verified=False)]:
            with self.assertRaises(ValueError):
                m.assemble([person()], [bad], {}, set(), {})
        result = m.assemble([person()], [claim(precision="month", day=None)], {}, set(), {})[0][0]
        self.assertEqual(result["source_date_components_iso"], "1900-02")
        self.assertEqual(result["dob_status"], "body_month_only")

    def test_source_dual_calendar_is_not_conflict(self):
        old = claim(year=1899, month=12, day=10, calendar="lunar_explicit", calendar_comparable=False,
                    raw_birth_statement="old calendar expression supplied by source")
        master = m.assemble([person()], [claim(), old], {}, set(), {})[0]
        self.assertEqual(master[0]["dob_status"], "body_day_no_known_conflict")
        self.assertEqual(master[0]["birth_claim_count"], 2)
        lone = m.assemble([person()], [old], {}, set(), {})[0]
        self.assertEqual(lone[0]["dob_status"], "source_calendar_hold")
        self.assertEqual(lone[0]["source_date_components_iso"], "")

    def test_year_disagreement_and_explicit_caveat_block_selection(self):
        master = m.assemble([person()], [claim(), claim(year=1901, month=None, day=None, precision="year")], {}, set(), {})[0]
        self.assertEqual(master[0]["dob_status"], "source_date_conflict_hold")
        self.assertEqual(master[0]["source_date_components_iso"], "")
        hold = {"a": {"status": "source_caveat_hold", "reason": "Source explicitly reports multiple dates"}}
        master = m.assemble([person()], [claim()], hold, set(), {})[0]
        self.assertEqual(master[0]["dob_status"], "source_caveat_hold")
        self.assertFalse(master[0]["final_cohort_accepted"])

    def test_restored_scope_union_and_historical_conflict_survive(self):
        rows = m.roster(ROOT / "inputs")
        self.assertEqual(len(rows), 482)
        counts = m.collections.Counter(r["broad_section_supported"] for r in rows)
        self.assertEqual(counts, {"2": 428, "1": 7, "": 47})
        historical = [r for r in rows if r.get("historical_section_conflict") == "1"]
        self.assertEqual(len(historical), 1)
        self.assertIn("historical_conflict_retained", historical[0]["section_evidence_status"])
        self.assertTrue(all(not r["final_cohort_accepted"] for r in rows))
        self.assertTrue(all(not r["exact_subsection_supported"] for r in rows if "degree_rule" in r["section_evidence_status"]))
        hiratsuka = next(r for r in rows if r["name_jp"] == "平塚 直秀")
        self.assertEqual(hiratsuka["exact_subsection_supported"], "6")

    def test_normalization_corrects_false_body_hash_and_keeps_calendar_conflicts(self):
        spec = importlib.util.spec_from_file_location("normalize_japan", ROOT / "scripts" / "normalize_japan.py")
        n = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(n)
        claims, _, holds = n.normalize(ROOT)
        bad = "5b131ca14aa96311d3432b0062c7443d3b0e6346ec279bd376a75f0a76bcd5d7"
        self.assertTrue(all(c.get("source_sha256") != bad for c in claims))
        self.assertTrue(any(c.get("source_hash_correction") for c in claims))
        fujisawa = next(c for c in claims if c["name_jp"] == "藤沢 利喜太郎")
        self.assertTrue(fujisawa["calendar_comparable"])
        self.assertEqual(fujisawa["calendar"], "not_stated")
        key = next(c["member_key"] for c in claims if c["name_jp"] == "山極 勝三郎")
        self.assertEqual(holds[key]["status"], "source_date_conflict_hold")
        self.assertEqual({c["day"] for c in claims if c["member_key"] == key and not c["calendar_comparable"]}, {22, 23})


if __name__ == "__main__":
    unittest.main()
