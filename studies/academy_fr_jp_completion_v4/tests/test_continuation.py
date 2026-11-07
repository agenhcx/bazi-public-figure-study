import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("v4_continue", ROOT / "scripts/continue.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def claim(key, name, **kwargs):
    c = dict(member_key=key, name_jp=name, year=1900, month=2, day=3, precision="day",
             calendar="not_stated", calendar_comparable=True, body_verified=True, identity_body_supported=True,
             source_url="https://example.org/fixture", source_tier="commercial_edited_biographical_reference_secondary",
             raw_birth_statement="Fixture born1900-02-03", identity_support="Named fixture with matching career.")
    c.update(kwargs)
    return c


class ContinuationTests(unittest.TestCase):
    def test_no_delta_preserves_baseline_counts_and_sections(self):
        m.check_baseline()
        rows, _, _, s = m.japan([], {}, [])
        self.assertEqual(s["body_day_no_known_conflict"], 213)
        self.assertEqual(s["day_status_net_change"], 0)
        self.assertEqual((s["broad_section_ii_supported"], s["section_i_excluded"], s["section_unresolved"]), (428, 7, 47))
        self.assertEqual(sum(bool(r["v3_identity_hold_released"]) for r in rows), 7)
        self.assertTrue(all(not r["final_cohort_accepted"] for r in rows))

    def test_unconverted_alternate_preserves_source_supplied_modern_date(self):
        old = next(r for r in m.previous_japan()[0] if r["name_jp"] == "志賀 潔")
        c = claim(old["member_key"], old["name_jp"], year=1870, month=12, day=18,
                  calendar="lunar_explicit", calendar_comparable=False, raw_birth_statement="旧暦明治3年12月18日")
        rows, _, _, _ = m.japan([c], {}, [])
        r = next(r for r in rows if r["member_key"] == c["member_key"])
        self.assertEqual(r["source_date_components_iso"], "1871-02-07")
        self.assertEqual(r["dob_status"], "body_day_no_known_conflict")
        with self.assertRaises(ValueError):
            m.japan([c], {c["member_key"]: {"status": "source_calendar_hold", "reason": "unconverted alternate"}}, [])

    def test_reference_only_day_does_not_become_institution_supported(self):
        person = next(r for r in m.previous_japan()[0] if r["dob_status"] == "not_body_source_processed" and r["broad_section_supported"] == "2")
        c = claim(person["member_key"], person["name_jp"])
        rows, _, _, s = m.japan([c], {}, [])
        r = next(r for r in rows if r["member_key"] == c["member_key"])
        self.assertEqual(r["day_evidence_tier"], "edited_reference_only")
        self.assertEqual(s["institutional_or_university_supported_day_no_known_conflict"], 169)
        self.assertEqual(s["edited_reference_only_day_no_known_conflict"], 45)
        other = dict(c, source_tier="commercial_financial_filing_reproduction_secondary")
        rows, _, _, s = m.japan([other], {}, [])
        self.assertEqual(s["edited_reference_only_day_no_known_conflict"], 44)
        self.assertEqual(s["other_attributed_secondary_only_day_no_known_conflict"], 1)

    def test_missing_day_unknown_identity_and_snippets_are_rejected(self):
        person = next(r for r in m.previous_japan()[0] if r["dob_status"] == "not_body_source_processed")
        for c in [claim(person["member_key"], person["name_jp"], precision="year"),
                  claim("unknown", person["name_jp"]), claim(person["member_key"], person["name_jp"], body_verified=False)]:
            with self.assertRaises(ValueError):
                m.japan([c], {}, [])

    def test_france_empty_delta_preserves_prior_review_provenance_and_dates(self):
        base = m.readcsv(m.BASE / "outputs/france_master877.csv")
        rows, _, _, _, s = m.france([])
        self.assertEqual(s["current"], {"identity_accepted": 755, "membership_accepted": 267, "dob_accepted": 744})
        self.assertEqual(s["all_three_accepted"], 265)
        for before, after in zip(base, rows):
            for k in ["accepted_dob_iso", "membership_as_of_year", "v3_membership_decision_status", "v3_evidence_urls"]:
                self.assertEqual(before[k], after[k])

    def test_prepared_inputs_match_pinned_transcriptions(self):
        for name, data in m.prepare().items():
            self.assertEqual(data, m.js(ROOT / "inputs" / name))


if __name__ == "__main__":
    unittest.main()
