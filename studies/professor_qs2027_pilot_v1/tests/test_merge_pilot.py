#!/usr/bin/env python3
"""Protocol and evidence-boundary regression checks; no external requests."""
from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "merge_pilot.py"
SPEC = importlib.util.spec_from_file_location("merge_pilot", SCRIPT)
pilot = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(pilot)
FROZEN = "2026-10-28T00:00:00+00:00"
CHECKED = "2026-10-28T00:01:00+00:00"


def row(country="US", institution="mit", subject="physics", name="Example A", profile="https://example.edu/a"):
    return {"person_key": pilot.person_key(country, institution, subject, name, profile),
            "name": name, "title_raw": "Assistant Professor", "staff_category": "faculty",
            "profile_url": profile, "roster_source_url": "https://example.edu/faculty",
            "sampling_eligible": True, "role_evidence_note": "Listed under academic faculty."}


def result(key):
    return {"person_key": key, "status": "not_found", "profile_fetch_attempts": 1,
            "cv_fetch_attempts": 0, "search_query_count": 0, "claims": [],
            "sources": [{"url": "https://example.edu/a", "status": "body_observed",
                         "access_method": "GET", "note": "No printed birth date."}],
            "checked_at_utc": CHECKED}


def department(country, institution, subject):
    rows = [row(country, institution, subject)]
    return {"institution_id": institution, "department": subject,
            "roster_status": "captured_complete_visible_scope",
            "roster_source_urls": ["https://example.edu/faculty"],
            "scope_note": "One visible academic faculty record; test fixture only.",
            "retrieved_at_utc": FROZEN, "rows": rows,
            "sampling_manifest": pilot.freeze_roster(rows, FROZEN),
            "dob_pilot": [result(rows[0]["person_key"])]}


def countries():
    return [{"schema_version": 1, "country": country,
             "departments": [department(country, institution, subject)
                             for institution in institutions for subject in pilot.DEPARTMENTS]}
            for country, institutions in pilot.COUNTRY_INSTITUTIONS.items()]


def add_claim(value, *, precision="day", calendar="not_stated", year=1960, month=2, day=3, body=True):
    if precision == "year":
        month = day = None
    elif precision == "month":
        day = None
    claim = {"date_raw": "Printed birth date", "year": year, "month": month, "day": day,
             "precision": precision, "calendar": calendar, "source_url": "https://example.edu/a",
             "source_type": "institutional_profile", "excerpt": "Born 3 February 1960.",
             "source_status": "body_observed" if body else "search_snippet_only"}
    value["claims"].append(claim)
    if body:
        value["status"] = precision + "_claim_found"
    return claim


class PilotBoundaryTests(unittest.TestCase):
    def test_sparse_visible_rosters_do_not_get_filled_or_claim_108_completed(self):
        summary, tables = pilot.build(countries(), {})
        self.assertEqual(summary["actual_dob_pilot_size"], 18)
        self.assertEqual(summary["unfilled_sample_slots"], 90)
        self.assertEqual(len(tables["observed_roster_v1.csv"]), 18)
        self.assertFalse(summary["full_department_historical_roster_completeness_claimed"])

    def test_duplicate_identity_is_rejected_before_output(self):
        data = countries()
        d = data[0]["departments"][0]
        d["rows"].append(copy.deepcopy(d["rows"][0]))
        d["sampling_manifest"] = pilot.freeze_roster(d["rows"], FROZEN)
        with self.assertRaisesRegex(pilot.InputError, "duplicate identity"):
            pilot.build(data, {})

    def test_roster_mutation_after_sampling_is_detected(self):
        data = countries()
        data[0]["departments"][0]["rows"][0]["title_raw"] = "Changed after freeze"
        with self.assertRaisesRegex(pilot.InputError, "roster_sha256"):
            pilot.build(data, {})

    def test_selected_person_cannot_be_replaced_after_seeing_dob(self):
        data = countries()
        data[0]["departments"][0]["dob_pilot"][0]["person_key"] = "prof-other"
        with self.assertRaisesRegex(pilot.InputError, "without substitutions"):
            pilot.build(data, {})

    def test_unknown_birth_year_is_preserved_and_not_declared_ineligible(self):
        summary, tables = pilot.build(countries(), {})
        self.assertEqual(summary["birth_window_status_counts"], {"unknown": 18})
        self.assertTrue(all(row["birth_window_status"] == "unknown" for row in tables["dob_availability_pilot_v1.csv"]))
        self.assertFalse(summary["hierarchy_age_distributions_matched"])

    def test_snippet_date_does_not_raise_availability(self):
        data = countries()
        add_claim(data[0]["departments"][0]["dob_pilot"][0], body=False)
        summary, _ = pilot.build(data, {})
        self.assertEqual(summary["body_supported_availability_precision_counts"]["unknown"], 18)
        self.assertEqual(summary["body_supported_availability_precision_counts"]["day"], 0)

    def test_unstated_calendar_day_claim_is_not_formal_acceptance(self):
        data = countries()
        add_claim(data[0]["departments"][0]["dob_pilot"][0])
        summary, tables = pilot.build(data, {})
        self.assertEqual(summary["body_supported_availability_precision_counts"]["day"], 1)
        self.assertEqual(summary["day_claims_with_unstated_calendar"], 1)
        self.assertEqual(summary["accepted_exact_dob_count"], 0)
        self.assertFalse(any(row["accepted_exact_dob"] for row in tables["dob_availability_pilot_v1.csv"]))

    def test_lunar_components_are_preserved_without_gregorian_conversion(self):
        data = countries()
        add_claim(data[0]["departments"][0]["dob_pilot"][0], calendar="lunar_explicit", month=2, day=30)
        summary, _ = pilot.build(data, {})
        self.assertTrue(summary["day_claims_with_explicit_lunar_calendar"])
        self.assertFalse(summary["calendar_conversion_performed"])
        data[0]["departments"][0]["dob_pilot"][0]["claims"][0]["calendar"] = "gregorian_explicit"
        with self.assertRaisesRegex(pilot.InputError, "invalid Gregorian date"):
            pilot.build(data, {})

    def test_blocked_directory_stays_present_with_zero_observed_people(self):
        data = countries()
        d = data[1]["departments"][0]
        d.update(roster_status="blocked", rows=[], dob_pilot=[])
        d["sampling_manifest"] = pilot.freeze_roster([], FROZEN)
        summary, tables = pilot.build(data, {})
        self.assertEqual(summary["departments"], 18)
        self.assertEqual(summary["actual_dob_pilot_size"], 17)
        self.assertEqual(summary["directory_status_counts"]["blocked"], 1)
        self.assertEqual(len(tables["department_coverage_v1.csv"]), 18)

    def test_partial_directory_counts_are_not_treated_as_complete(self):
        data = countries()
        data[1]["departments"][0]["roster_status"] = "captured_partial"
        summary, tables = pilot.build(data, {})
        self.assertEqual(summary["directory_status_counts"]["captured_partial"], 1)
        uk = next(row for row in tables["country_coverage_v1.csv"] if row["country"] == "UK")
        self.assertEqual(uk["partial_or_blocked_directories"], 1)

    def test_repeated_searches_violate_the_pilot_budget(self):
        data = countries()
        data[0]["departments"][0]["dob_pilot"][0]["search_query_count"] = 2
        with self.assertRaisesRegex(pilot.InputError, "bounded pilot budget"):
            pilot.build(data, {})

    def test_more_than_one_search_result_body_confirmation_is_rejected(self):
        data = countries()
        data[0]["departments"][0]["dob_pilot"][0]["search_result_body_fetch_attempts"] = 2
        with self.assertRaisesRegex(pilot.InputError, "search_result_body_fetch_attempts"):
            pilot.build(data, {})

    def test_body_confirmation_counter_is_recorded_without_inventing_legacy_requests(self):
        data = countries()
        data[0]["departments"][0]["dob_pilot"][0]["search_result_body_fetch_attempts"] = 1
        summary, tables = pilot.build(data, {})
        self.assertEqual(summary["recorded_request_attempt_counts"]["search_result_body_fetch_attempts"], 1)
        self.assertEqual(sum(row["search_result_body_fetch_attempts"] for row in tables["dob_availability_pilot_v1.csv"]), 1)

    def test_conflicting_dates_and_years_are_not_arbitrarily_resolved(self):
        data = countries()
        value = data[0]["departments"][0]["dob_pilot"][0]
        add_claim(value, year=1960)
        add_claim(value, year=1961)
        summary, tables = pilot.build(data, {})
        self.assertEqual(summary["day_claims_with_printed_component_differences"], 1)
        record = next(row for row in tables["dob_availability_pilot_v1.csv"] if row["person_key"] == value["person_key"])
        self.assertEqual(record["birth_window_status"], "conflicting_birth_year_claims")
        self.assertFalse(record["accepted_exact_dob"])

    def test_default_day_cannot_be_added_to_month_precision(self):
        data = countries()
        claim = add_claim(data[0]["departments"][0]["dob_pilot"][0], precision="month")
        claim["day"] = 1
        with self.assertRaisesRegex(pilot.InputError, "default day"):
            pilot.build(data, {})

    def test_same_institution_name_is_a_candidate_not_an_automatic_merge(self):
        data = countries()
        summary, tables = pilot.build(data, {})
        names = [candidate for candidate in tables["cross_department_identity_review_v1.csv"]
                 if candidate["match_basis"] == "same_institution_exact_normalized_name"]
        self.assertEqual(len(names), 9)
        self.assertTrue(all(candidate["review_status"] == "candidate_only_not_merged" for candidate in names))
        self.assertEqual(summary["observed_roster_membership_rows"], 18)
        self.assertEqual(summary["higher_tier_overlap_status"], "not_systematically_checked")

    def test_official_directory_date_remains_a_body_supported_claim(self):
        data = countries()
        claim = add_claim(data[2]["departments"][0]["dob_pilot"][0])
        claim["source_type"] = "institutional_directory"
        summary, _ = pilot.build(data, {})
        self.assertEqual(summary["body_supported_availability_precision_counts"]["day"], 1)
        self.assertEqual(summary["accepted_exact_dob_count"], 0)

    def test_same_department_same_name_multiple_urls_is_a_review_candidate(self):
        data = countries()
        d = data[0]["departments"][0]
        d["rows"][0] = row(name="Within Department Duplicate")
        d["rows"].append(row(name="Within Department Duplicate", profile="https://example.edu/other-subject/a"))
        d["sampling_manifest"] = pilot.freeze_roster(d["rows"], FROZEN)
        d["dob_pilot"] = [result(key) for key in d["sampling_manifest"]["selected_person_keys"]]
        summary, tables = pilot.build(data, {})
        within = [candidate for candidate in tables["cross_department_identity_review_v1.csv"] if candidate["scope"] == "within_department"]
        self.assertTrue(any(candidate["match_basis"] == "same_institution_exact_normalized_name" for candidate in within))
        self.assertEqual(summary["observed_roster_membership_rows"], 19)

    def test_missing_start_time_is_diagnostic_not_an_invented_timestamp(self):
        summary, tables = pilot.build(countries(), {})
        self.assertEqual(summary["dob_check_timing_evidence_counts"], {"completion_timestamp_only_start_unverified": 18})
        self.assertFalse(summary["pre_dob_sampling_start_times_fully_documented"])
        self.assertTrue(all(row["timing_evidence_status"] == "completion_timestamp_only_start_unverified" for row in tables["dob_availability_pilot_v1.csv"]))

    def test_recorded_start_must_follow_freeze_and_precede_completion(self):
        data = countries()
        value = data[0]["departments"][0]["dob_pilot"][0]
        value["dob_check_started_at_utc"] = "2026-10-28T00:00:30+00:00"
        summary, _ = pilot.build(data, {})
        self.assertEqual(summary["dob_check_timing_evidence_counts"]["start_timestamp_recorded_after_sampling_freeze"], 1)
        for bad_start in ("2026-10-27T23:59:59+00:00", "2026-10-28T00:02:00+00:00"):
            value["dob_check_started_at_utc"] = bad_start
            with self.assertRaisesRegex(pilot.InputError, "DOB-check start"):
                pilot.build(data, {})

    def test_blocked_source_ledger_cannot_support_body_observed_claim(self):
        data = countries()
        value = data[0]["departments"][0]["dob_pilot"][0]
        add_claim(value)
        value["sources"][0]["status"] = "blocked"
        with self.assertRaisesRegex(pilot.InputError, "successful body-observation"):
            pilot.build(data, {})

    def test_verified_metadata_correction_retains_original_selection_time_and_positive_overlap(self):
        data = countries()
        d = data[0]["departments"][0]
        old_rows, old_manifest = copy.deepcopy(d["rows"]), copy.deepcopy(d["sampling_manifest"])
        corrected_at = "2026-10-28T00:02:00+00:00"
        d["rows"][0]["title_raw"] = "Corrected faculty role metadata"
        d["sampling_manifest"] = pilot.freeze_roster(d["rows"], corrected_at)
        d["prior_sampling_snapshot"] = {"rows": old_rows, "sampling_manifest": old_manifest,
                                         "correction_reason": "Source-role metadata corrected; sample unchanged.",
                                         "corrected_at_utc": corrected_at}
        d["dob_pilot"][0]["observed_higher_tier_overlaps"] = [{"tier": "Nobel", "source_url": "https://example.edu/prize", "note": "Official profile reports a Nobel Prize."}]
        summary, tables = pilot.build(data, {})
        self.assertEqual(summary["post_freeze_metadata_corrected_departments"], 1)
        self.assertEqual(summary["higher_tier_overlap_status_counts"]["observed_positive_not_exhaustive"], 1)
        record = next(row for row in tables["department_coverage_v1.csv"] if row["country"] == "US" and row["institution_id"] == "mit" and row["department"] == "physics")
        self.assertEqual(record["selected_keys_frozen_at_utc"], FROZEN)
        self.assertEqual(record["current_roster_hash_bound_at_utc"], corrected_at)

    def test_prior_metadata_snapshot_hash_tampering_is_rejected(self):
        data = countries()
        d = data[0]["departments"][0]
        d["prior_sampling_snapshot"] = {"rows": copy.deepcopy(d["rows"]), "sampling_manifest": copy.deepcopy(d["sampling_manifest"]),
                                         "correction_reason": "Metadata correction", "corrected_at_utc": FROZEN}
        d["prior_sampling_snapshot"]["rows"][0]["title_raw"] = "Tampered original metadata"
        with self.assertRaisesRegex(pilot.InputError, "prior sampling manifest roster_sha256"):
            pilot.build(data, {})

    def test_prior_metadata_snapshot_cannot_change_selected_identities(self):
        data = countries()
        d = data[0]["departments"][0]
        old_rows = [row(name="Different originally selected person", profile="https://example.edu/different")]
        d["prior_sampling_snapshot"] = {"rows": old_rows, "sampling_manifest": pilot.freeze_roster(old_rows, FROZEN),
                                         "correction_reason": "Metadata correction", "corrected_at_utc": FROZEN}
        with self.assertRaisesRegex(pilot.InputError, "cannot change selected identities"):
            pilot.build(data, {})


if __name__ == "__main__":
    unittest.main()
