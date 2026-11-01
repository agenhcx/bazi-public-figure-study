import sys
sys.dont_write_bytecode = True
import copy
import importlib.util
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("v14_continue", ROOT / "scripts/continue.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class ContinuationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.jp, cls.claims, cls.queue, cls.jp_summary = m.previous_japan()
        cls.fr = m.readcsv(m.BASE / "outputs/france_master877.csv")

    def test_complete_final_japan_state_and_claim_fields_are_the_baseline(self):
        rows, claims, queue, summary = m.japan([], {}, [])
        self.assertEqual((rows, claims, queue), (self.jp, self.claims, self.queue))
        self.assertEqual(claims, m.js(m.BASE / "inputs/japan_claims.json"))
        self.assertEqual(len(claims), self.jp_summary["body_claim_rows"])
        self.assertEqual(summary["inherited_v13_raw_source_claim_rows"], len(self.claims))
        self.assertEqual(m.final_japan(), (rows, claims, queue, summary))

    def test_every_france_field_and_both_complete_histories_survive(self):
        rows, accepted, gaps, history, summary = m.france([])
        self.assertEqual(rows, self.fr)
        self.assertEqual(history, m.readcsv(m.BASE / "outputs/france_membership_decisions.csv"))
        self.assertEqual(m.france_case_adjudications(), m.readcsv(m.BASE / "outputs/france_case_adjudications.csv"))
        self.assertEqual(len(accepted) + len(gaps), len(rows))
        self.assertEqual(summary["current"], m.baseline_summary()["france"]["current"])
        self.assertEqual(summary["new_individual_case_adjudications"], 0)
        self.assertEqual(summary["inherited_v13_case_adjudication_rows"], len(m.france_case_adjudications()))
        self.assertEqual(summary["inherited_v13_membership_decision_rows"], len(history))

    def test_inherited_holds_and_all_four_calendar_outcomes_survive(self):
        rows, _, _, _ = m.japan([], {}, [])
        by = {r["member_key"]: r for r in rows}
        holds = m.inherited_holds()
        for old in self.jp:
            if old["dob_status"].endswith("_hold"):
                self.assertEqual((holds[old["member_key"]]["status"], holds[old["member_key"]]["reason"]),
                                 (old["dob_status"], old["dob_hold_note"]))
                self.assertEqual(by[old["member_key"]], old)
        releases = m.js(m.V13.V12.ROOT / "source_audits/v12_final_read_only_audit.json")["four_prior_calendar_releases_preserved"]
        self.assertEqual(len(releases), 4)
        for key, date in releases.items():
            self.assertEqual((by[key]["dob_status"], by[key]["source_date_components_iso"]),
                             ("body_day_no_known_conflict", date))

    def test_father_machine_hold_and_son_are_immutable(self):
        by = {r["candidate_group_id"]: r for r in m.france([])[0]}
        father = by["CTHS_102829"]
        self.assertEqual(father["exact_dob_claims"], "1862-11-23")
        self.assertEqual(father["exact_dob_conflict"], "0")
        self.assertEqual(father["v12_dob_review_status"], m.UNRESOLVED_BIRTHYEAR_STATUS)
        self.assertEqual(father["v12_dob_review_observed_birthyears"], "[1862, 1867]")
        self.assertTrue(father["v12_dob_review_control_sha256"])
        for key in ("CTHS_102829", "CTHS_112057"):
            self.assertEqual(by[key], next(r for r in self.fr if r["candidate_group_id"] == key))
        for kwargs in (dict(decisions=[dict(candidate_group_id="CTHS_102829")]),
                       dict(decisions=[], individual_cases=[dict(candidate_group_id="CTHS_102829")])):
            with self.assertRaisesRegex(ValueError, "Unresolved actual-source birthyear conflict"):
                m.france(**kwargs)

    def test_inherited_machine_status_blocks_promotion_without_an_exact_control_map(self):
        father = next(r for r in self.fr if r["candidate_group_id"] == "CTHS_102829")
        with patch.object(m, "birthyear_control", return_value=None):
            with self.assertRaisesRegex(ValueError, "Unresolved actual-source birthyear conflict"):
                m.block_unresolved_birthyear(father)

    def test_father_cannot_self_approve_with_root_and_qa_flags(self):
        with tempfile.TemporaryDirectory(prefix="academy-v14-father-") as folder:
            root = Path(folder); (root / "inputs").mkdir()
            approvals = [dict(candidate_group_id="CTHS_102829", root_approved=True, independent_qa_passed=True,
                              new_values=dict(identity_accepted="1", dob_accepted="1", accepted_dob_iso="1862-11-23"))]
            m.dump(root / "inputs/france_individual_case_approvals.json", approvals)
            with self.assertRaisesRegex(ValueError, "Unresolved actual-source birthyear conflict"):
                m.reviewed_individual_case_decisions(root)

    def test_no_new_raw_dob_claim_japan_hold_or_hard_route_is_authorized(self):
        for delta, holds, processed, section, message in (
            ([self.claims[0]], {}, [], [], "New raw DOB claims"),
            ([], {self.jp[0]["member_key"]: dict(status="source_calendar_hold")}, [], [], "New Japan holds"),
            ([], {}, [self.jp[0]["member_key"]], [], "hard routes remain parked"),
            ([], {}, [], [dict(member_key=self.jp[0]["member_key"])], "No new v14"),
        ):
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message): m.japan(delta, holds, processed, section)

    def test_unapproved_france_acceptance_or_quarantine_cannot_bypass_scope(self):
        gap = next(r for r in self.fr if r["membership_accepted"] == "0" and r["candidate_group_id"] != "CTHS_102829")
        with self.assertRaisesRegex(ValueError, "exact reviewed source approvals"):
            m.france([dict(candidate_group_id=gap["candidate_group_id"], root_approved=True, independent_qa_passed=True)])
        with self.assertRaisesRegex(ValueError, "exact reviewed source approvals"):
            m.france_case_adjudications([dict(candidate_group_id=gap["candidate_group_id"])])
        with self.assertRaisesRegex(ValueError, "No new v14"):
            m.france([], dob_quarantines=[dict(candidate_group_id=gap["candidate_group_id"])])

    def test_predecessor_acceptances_do_not_authorize_new_v14_changes(self):
        self.assertEqual(set(m.EXACT_MEMBERSHIP_ACCEPTANCES), {"PROFILE2_738d6d5c74a7a874"})
        self.assertEqual(set(m.EXACT_INDIVIDUAL_CASE_ACCEPTANCES), {"CTHS_128379", "PROFILE2_08407b6d0479b1d0"})
        with self.assertRaisesRegex(ValueError, "exact reviewed source approvals"):
            m.france(m.V13.reviewed_membership_decisions(), individual_cases=m.V13.reviewed_individual_case_decisions())
        self.assertEqual(len(m.reviewed_individual_case_decisions()), 2)
        self.assertEqual(len(m.reviewed_membership_decisions()), 2)

    def test_selection_can_remain_empty_unfrozen_without_guessed_queues(self):
        with tempfile.TemporaryDirectory(prefix="academy-v14-unfrozen-") as folder:
            root = Path(folder); (root / "inputs").mkdir()
            config = dict(selection_frozen=False, japan=[], france=[], expected_totals=dict(japan=0, france=0))
            m.dump(root / "inputs/selection_config.json", config)
            self.assertEqual(m.selections(root, allow_unfrozen_empty=True), {"japan": set(), "france": set()})
            with self.assertRaisesRegex(ValueError, "awaiting the root-reviewed queue freeze"): m.selections(root)
            config["france"] = [dict(path="selection_queues/guessed.csv", count=1)]
            m.dump(root / "inputs/selection_config.json", config)
            with self.assertRaisesRegex(ValueError, "awaiting the root-reviewed queue freeze"): m.selections(root, allow_unfrozen_empty=True)

    def test_fixed_queue_identity_cardinality_disjointness_and_path_guards(self):
        with tempfile.TemporaryDirectory(prefix="academy-v14-selection-") as folder:
            root = Path(folder); (root / "inputs").mkdir(); (root / "selection_queues").mkdir()
            key = self.fr[0]["candidate_group_id"]
            (root / "selection_queues/fr.csv").write_text("candidate_group_id\n" + key + "\n")
            config = dict(selection_frozen=True, japan=[], france=[dict(path="selection_queues/fr.csv", count=1)], expected_totals=dict(japan=0, france=1))
            def write(): m.dump(root / "inputs/selection_config.json", config)
            write(); self.assertEqual(m.selections(root), {"japan": set(), "france": {key}})
            config["france"].append(copy.deepcopy(config["france"][0])); write()
            with self.assertRaisesRegex(ValueError, "Overlapping fixed queues"): m.selections(root)
            config["france"] = [dict(path="selection_queues/../fr.csv", count=1)]; write()
            with self.assertRaisesRegex(ValueError, "must stay in selection_queues"): m.selections(root)
            config["france"] = [dict(path="selection_queues/fr.csv", count=2)]; write()
            with self.assertRaisesRegex(ValueError, "cardinality mismatch"): m.selections(root)
            config["france"][0]["count"] = 1
            (root / "selection_queues/fr.csv").write_text("candidate_group_id\nUNKNOWN\n"); write()
            with self.assertRaisesRegex(ValueError, "Unknown fixed selection identity"): m.selections(root)

    def test_prepare_preserves_complete_claims_and_both_history_inputs(self):
        prepared = m.prepare()
        self.assertEqual(len(prepared), 13)
        self.assertEqual(prepared["japan_claims.json"], self.claims)
        self.assertEqual(prepared["inherited_france_case_adjudications.json"], m.france_case_adjudications())
        self.assertEqual(prepared["inherited_france_decisions.json"], m.readcsv(m.BASE / "outputs/france_membership_decisions.csv"))
        self.assertEqual(set(prepared["france_processed_ids.json"]), m.selections()["france"])
        self.assertEqual(prepared["japan_delta_processed_ids.json"], [])

    def test_processing_dispositions_keep_unsearched_and_review_status_boundaries(self):
        with tempfile.TemporaryDirectory(prefix="academy-v14-status-") as folder:
            path = Path(folder) / "processed.csv"
            path.write_text("candidate_group_id,status\nx,not_searched\ny,pending\nz,body_reviewed_held\n")
            self.assertEqual(m.reviewed_ids(path, "candidate_group_id"), {"z"})
            path.write_text("candidate_group_id,review_status\nx,target_name_not_found_in_document\n")
            self.assertEqual(m.reviewed_ids(path, "candidate_group_id"), {"x"})
            path.write_text("candidate_group_id,status\nx,not_searched\nx,body_reviewed\n")
            with self.assertRaisesRegex(ValueError, "Duplicate processing disposition"): m.reviewed_ids(path, "candidate_group_id")

    def test_pinned_baseline_rejects_a_changed_predecessor_history_hash(self):
        with tempfile.TemporaryDirectory(prefix="academy-v14-pin-") as folder:
            root = Path(folder); (root / "inputs").mkdir()
            provenance = m.js(ROOT / "inputs/baseline_provenance.json")
            provenance["baseline_sha256"]["outputs/france_case_adjudications.csv"] = "0" * 64
            m.dump(root / "inputs/baseline_provenance.json", provenance)
            with self.assertRaisesRegex(ValueError, "Changed v13 baseline inventory or bytes"): m.check_baseline(root)

    def test_inherited_component_guards_keep_two_responses_literal_credit_and_nulls(self):
        d = next(d for d in m.js(m.BASE / "source_batches/france_b/decisions.json") if d["candidate_group_id"] == "CTHS_102838")
        e = d["evidence"][0]
        self.assertTrue(m.academy_original(e))
        for changes in (dict(cths_same_body_authorship_role_start_verified=True), dict(cths_evidence_spans_multiple_http_responses=False),
                        dict(cths_parent_notice_http_status=200), dict(cths_parent_notice_retrieved_utc="2026-11-01T00:00:00Z"),
                        dict(credited_authors=["Personal writer (Institut de France)"]), dict(cths_expanded_biography_http_status=404),
                        dict(returned_close_handler_person_id="102823")):
            attack = copy.deepcopy(e); attack.update(changes)
            with self.subTest(changes=changes): self.assertFalse(m.academy_original(attack))

    def test_production_replay_preserves_japan_and_truthful_source_processing(self):
        with tempfile.TemporaryDirectory(prefix="academy-v14-outputs-") as folder:
            output = Path(folder) / "outputs"; summary = m.assemble(output)
            for name in m.INHERITED_CSV_FILES[:3]: self.assertEqual((output / name).read_bytes(), (m.BASE / "outputs" / name).read_bytes())
            self.assertEqual(summary["actual_processed_counts"], dict(japan=0, france=4))
            self.assertEqual(summary["france"]["current"], dict(identity_accepted=787, dob_accepted=775, membership_accepted=642))
            self.assertEqual((summary["france"]["all_three_accepted"], summary["france"]["all_three_remaining_gaps"]), (639, 238))
            self.assertEqual(summary["existing_singleton_DOB_cases_approved"], 2)
            self.assertFalse(summary["analysis_cohort_frozen"])
            self.assertEqual(summary["bazi_variables_computed"], 0)
            self.assertEqual(summary["outreach_count"], 0)
            self.assertEqual(summary["new_raw_DOB_claims"], 0)
            with self.assertRaisesRegex(ValueError, "Fresh output directory required"): m.assemble(output)


    def test_exact_case_and_membership_approval_sets_cannot_self_expand(self):
        self.assertEqual(len(m.reviewed_individual_case_decisions()), 2)
        self.assertEqual(sum(str(d["membership_accepted"]) == "1" for d in m.reviewed_membership_decisions()), 1)
        original = m.js
        for field in ("root_approved", "independent_qa_passed", "independent_qa_sha256", "decisions_sha256", "worker_manifest_sha256"):
            approvals = m.js(ROOT / "inputs/france_membership_approvals.json")
            approvals[0][field] = False if field.endswith("approved") or field.endswith("passed") else "0" * 64
            with self.subTest(field=field), patch.object(m, "js", side_effect=lambda p: approvals if p == ROOT / "inputs/france_membership_approvals.json" else original(p)):
                with self.assertRaises(ValueError): m.reviewed_membership_decisions()
    def test_singleton_case_semantics_survive_an_erroneously_broadened_binding(self):
        original_proposal = m.js(ROOT / "source_batches/france_b/individual_case_proposals.json")[0]
        original_approval = m.js(ROOT / "inputs/france_individual_case_approvals.json")[0]
        original_qa = m.js(ROOT / "source_audits/france_b2_individual_case_independent_QA.json")
        for attack in ("wrong_DOB", "alias_collision", "unread_body", "invented_archive_envelope", "false_case_QA", "membership_warning_change_QA"):
            with self.subTest(attack=attack), tempfile.TemporaryDirectory(prefix="academy-v14-case-") as folder:
                root = Path(folder)
                (root / "inputs").mkdir(); (root / "source_batches/france_b").mkdir(parents=True); (root / "selection_queues").mkdir()
                shutil.copyfile(ROOT / "selection_queues/france_b.csv", root / "selection_queues/france_b.csv")
                proposal, approval, qa = copy.deepcopy(original_proposal), copy.deepcopy(original_approval), copy.deepcopy(original_qa)
                if attack == "wrong_DOB":
                    proposal["new_values"]["accepted_dob_iso"] = "1958-05-09"
                    approval["new_values"] = copy.deepcopy(proposal["new_values"])
                if attack == "alias_collision": proposal["identity_checks"]["no_unresolved_alias_or_profile_collision"] = False
                if attack == "unread_body": proposal["source_evidence"][0]["body_verified"] = False
                if attack == "invented_archive_envelope":
                    proposal["source_evidence"][1].update(http_status=200, retrieved_utc="2026-11-01T00:00:00Z")
                if attack == "false_case_QA": qa["case_checks"][0]["singleton_prior_DOB_claim_passed"] = False
                if attack == "membership_warning_change_QA": qa["case_checks"][0]["membership_fields_and_warnings_unchanged"] = False
                path = root / "source_batches/france_b/individual_case_proposals.json"
                m.dump(path, [proposal]); approval["individual_case_proposals_sha256"] = m.sha(path)
                qa["individual_case_proposals_sha256"] = m.sha(path)
                m.dump(root / "inputs/france_individual_case_approvals.json", [approval])
                with patch.object(m, "approved_binding", return_value=qa):
                    with self.assertRaises(ValueError): m.reviewed_individual_case_decisions(root)
    def test_membership_events_cannot_use_foreign_roles_relative_years_or_reception_dates(self):
        salomon = next(d for d in m.js(ROOT / "source_batches/france_a/decisions.json") if d["candidate_group_id"] == "PROFILE2_738d6d5c74a7a874")
        before = next(r for r in self.fr if r["candidate_group_id"] == salomon["candidate_group_id"])
        for changes in (dict(role="foreign_associate"), dict(role="correspondent"), dict(event_year=2025),
                        dict(event_year_is_relative=True), dict(event_type="reception_as_of"), dict(event_subject_role="author"),
                        dict(source_role="secondary_reference")):
            attack = copy.deepcopy(salomon); attack["evidence"][0].update(changes)
            with self.subTest(changes=changes), self.assertRaises(ValueError): m.validate_france_positive(attack, before)
    def test_production_preserves_every_untouched_field_and_both_history_prefixes(self):
        cases, decisions = m.reviewed_individual_case_decisions(), m.reviewed_membership_decisions()
        rows, _, _, ledger, _ = m.france(decisions, individual_cases=cases)
        changed = {d["candidate_group_id"] for d in cases + decisions}
        by = {r["candidate_group_id"]: r for r in rows}
        for old in self.fr:
            if old["candidate_group_id"] not in changed: self.assertEqual(by[old["candidate_group_id"]], old)
            for field in ("exact_dob_claims", "exact_dob_conflict", "firstparty_day_claims", "has_firstparty_day_claim", "source_families", "source_urls", "review_flags", "v12_dob_review_status", "v12_dob_review_control_sha256"):
                self.assertEqual(by[old["candidate_group_id"]][field], old[field])
        old_ledger = m.readcsv(m.BASE / "outputs/france_membership_decisions.csv")
        self.assertEqual(ledger[:len(old_ledger)], old_ledger)
        old_cases = m.readcsv(m.BASE / "outputs/france_case_adjudications.csv")
        self.assertEqual(m.france_case_adjudications(cases)[:len(old_cases)], old_cases)
    def test_birthday_only_scope_preserves_all_membership_warnings_and_maternal_record(self):
        cases = m.reviewed_individual_case_decisions()
        rows, _, _, _, _ = m.france(m.reviewed_membership_decisions(), individual_cases=cases)
        by = {r["candidate_group_id"]: r for r in rows}
        mutable = m.CASE_FIELDS | {"completion_remaining_dimensions", "completion_status"}
        for key in m.selections()["france"] & {d["candidate_group_id"] for d in cases}:
            old = next(r for r in self.fr if r["candidate_group_id"] == key)
            self.assertEqual({k: by[key][k] for k in old if k not in mutable}, {k: v for k, v in old.items() if k not in mutable})
            self.assertEqual((by[key]["membership_accepted"], by[key]["election_date_conflict"]), ("0", ""))
            self.assertIn("header_body_election_year_conflict", by[key]["review_flags"])
        self.assertEqual(by["CTHS_111838"], next(r for r in self.fr if r["candidate_group_id"] == "CTHS_111838"))
        forged = [dict(candidate_group_id=cases[0]["candidate_group_id"], membership_accepted=0)]
        with patch.object(m, "reviewed_membership_decisions", return_value=forged):
            with self.assertRaisesRegex(ValueError, "Birthday-only B scope cannot change any membership"):
                m.france(forged, individual_cases=cases)

    def test_no_government_source_class_or_title_year_can_authorize_election(self):
        d = next(d for d in m.js(ROOT / "source_batches/france_a/decisions.json") if str(d["membership_accepted"]) == "1")
        before = next(r for r in self.fr if r["candidate_group_id"] == d["candidate_group_id"])
        attack = copy.deepcopy(d)
        attack["evidence"][0].update(source_url="https://www.legifrance.gouv.fr/fixture", source_role="government_approved_election_firstparty", academy_authored_or_issued_original=False)
        with self.assertRaises(ValueError): m.validate_france_positive(attack, before)
        attack = copy.deepcopy(d); attack["evidence"][0].update(http_status=403, body_verified=False)
        with self.assertRaises(ValueError): m.validate_france_positive(attack, before)
        self.assertEqual(d["accepted_full_member_election_year"], 2024)
        self.assertIsNone(d["accepted_full_member_election_date"])
        original_js = m.js
        approvals = m.js(ROOT / "inputs/france_membership_approvals.json")
        approvals[0]["identity_support_source_sha256s"] = ["0" * 64]
        with patch.object(m, "js", side_effect=lambda p: approvals if p == ROOT / "inputs/france_membership_approvals.json" else original_js(p)):
            with self.assertRaises(ValueError): m.reviewed_membership_decisions()

if __name__ == "__main__":
    unittest.main()
