import copy
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("continuation", ROOT / "scripts/assemble.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def french_person():
    return dict(candidate_group_id="f", display_name="Example Scientist", accepted_canonical_person_name="Example Scientist",
                identity_accepted="1", membership_accepted="0", dob_accepted="1", accepted_dob_iso="1900-01-02",
                accepted_full_member_election_date="", accepted_full_member_election_year="", bazi_computed="0",
                membership_role_supported="0", election_cutoff_stable="0", election_date_conflict="0")


def french_decision(**override):
    d = dict(candidate_group_id="f", name="Example Scientist", reviewed=True,
             membership_accepted=1, membership_role_supported=1, election_cutoff_stable=1,
             election_date_conflict=0, accepted_full_member_election_date=None,
             accepted_full_member_election_year=1920, accepted_full_member_election_precision="year",
             decision_status="approved", reason="Named full-member election in the original source.",
             evidence=[dict(body_verified=True, source_url="https://example.org/archive", quote="elected full member1920", identity_note="matching named scientist and career")])
    d.update(override)
    return d


class ContinuationTests(unittest.TestCase):
    def test_year_only_membership_does_not_fill_day_or_change_dob(self):
        original = french_person()
        rows, _, _, _, summary = m.france([original], [french_decision()])
        self.assertEqual(rows[0]["accepted_full_member_election_year"], "1920")
        self.assertEqual(rows[0]["accepted_full_member_election_date"], "")
        self.assertEqual(rows[0]["accepted_dob_iso"], original["accepted_dob_iso"])
        self.assertEqual(summary["new_strict_memberships"], 1)
        self.assertEqual(original["membership_accepted"], "0")

    def test_role_asof_bound_is_not_election_and_does_not_relax_strict_gate(self):
        d = french_decision(membership_accepted=0, membership_as_of_year=1934,
                            accepted_full_member_election_year=None, accepted_full_member_election_precision=None)
        rows, accepted, _, _, summary = m.france([french_person()], [d])
        self.assertEqual(rows[0]["membership_as_of_year"], 1934)
        self.assertEqual(rows[0]["accepted_full_member_election_year"], "")
        self.assertFalse(accepted)
        self.assertEqual(summary["role_cutoff_and_dob_supported"], 1)
        self.assertEqual(summary["new_strict_memberships"], 0)

    def test_competing_election_and_cutoff_cannot_be_bypassed(self):
        for d in [french_decision(election_date_conflict=1), french_decision(election_cutoff_stable=0),
                  french_decision(accepted_full_member_election_year=2026), french_decision(accepted_full_member_election_year=1890),
                  french_decision(evidence=[]), french_decision(name="Different Person")]:
            with self.assertRaises(ValueError):
                m.france([french_person()], [d])
        row = french_person()
        row["election_date_conflict"] = "1"
        with self.assertRaises(ValueError):
            m.france([row], [french_decision()])

    def test_nonordinary_event_does_not_erase_earlier_supported_role(self):
        row = french_person()
        row["membership_role_supported"] = "1"
        row["election_cutoff_stable"] = "1"
        d = french_decision(membership_accepted=0, membership_role_supported=0, election_cutoff_stable=0,
                            accepted_full_member_election_year=None, accepted_full_member_election_precision=None,
                            observed_role="correspondent")
        actual = m.france([row], [d])[0][0]
        self.assertEqual(actual["membership_role_supported"], "1")
        self.assertEqual(actual["membership_accepted"], "0")

    def test_duplicate_and_unapproved_france_decisions_are_rejected(self):
        d = french_decision()
        for decisions in [[d, copy.deepcopy(d)], [french_decision(reviewed=False)]]:
            with self.assertRaises(ValueError):
                m.france([french_person()], decisions)

    def test_identity_release_cannot_lift_birth_or_calendar_conflict(self):
        old = m.js(m.BASE / "inputs/japan_dob_holds.json")
        key = next(k for k, v in old.items() if v["status"] == "source_date_conflict_hold")
        person = next(r for r in m.J.roster(m.BASE / "inputs") if r["member_key"] == key)
        d = dict(member_key=key, name_jp=person["name_jp"], decision_type="release_identity_assignment_hold",
                 identity_body_supported=True, body_verified=True, source_url="https://example.org/subject",
                 evidence_quote="named subject career", identity_bridge="Matching scientist and institution")
        with self.assertRaises(ValueError):
            m.japan([d], [], [])

    def test_edited_reference_day_is_separate_from_institution_day(self):
        base = m.csv_rows(m.BASE / "japan_outputs/japan_master.csv")
        p = next(r for r in base if r["dob_status"] == "not_institutionally_processed" and r["broad_section_supported"] == "2")
        c = dict(member_key=p["member_key"], name_jp=p["name_jp"], year=1900, month=2, day=3,
                 precision="day", calendar="not_stated", calendar_comparable=True, body_verified=True,
                 identity_body_supported=True, source_url="https://example.org/edited-dictionary",
                 source_tier="commercial_edited_biographical_reference_secondary", raw_birth_statement="Born1900-02-03",
                 identity_support="Fixture represents a named edited-reference subject and matching career.")
        rows, _, _, _, summary = m.japan([], [c], [])
        row = next(r for r in rows if r["member_key"] == c["member_key"])
        self.assertEqual(row["day_evidence_tier"], "edited_reference_only")
        self.assertFalse(row["has_institution_or_university_day_claim"])
        self.assertEqual(summary["edited_reference_only_day_no_known_conflict"], 1)
        self.assertEqual(summary["institutional_or_university_supported_day_no_known_conflict"], 120)
        self.assertFalse(row["final_cohort_accepted"])

    def test_preparation_and_baseline_are_pinned(self):
        m.check_baseline()
        spec = importlib.util.spec_from_file_location("prepare", ROOT / "scripts/prepare_inputs.py")
        p = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(p)
        for name, value in p.prepare(ROOT).items():
            self.assertEqual(value, m.js(ROOT / "inputs" / name))


if __name__ == "__main__":
    unittest.main()
