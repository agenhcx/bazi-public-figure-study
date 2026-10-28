#!/usr/bin/env python3
"""Validate and summarize a bounded professor roster/DOB availability pilot.

This module performs no networking, date inference, calendar conversion,
cross-person merging, formal DOB acceptance, or BaZi computation.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from datetime import date, datetime
import hashlib
import json
from pathlib import Path
import sys
import unicodedata
from urllib.parse import urldefrag, urlsplit

SEED = "professor-qs2027-pilot-v1"
COUNTRY_INSTITUTIONS = {
    "US": ("mit", "stanford", "harvard"),
    "UK": ("imperial", "oxford", "cambridge"),
    "CN": ("pku", "tsinghua", "fudan"),
}
DEPARTMENTS = ("physics", "chemistry")
ROSTER_STATUSES = {"captured_complete_visible_scope", "captured_partial", "blocked"}
STAFF_CATEGORIES = {"faculty", "teaching_faculty", "research_faculty", "emeritus", "visiting", "honorary", "unknown_role"}
CALENDARS = {"not_stated", "gregorian_explicit", "lunar_explicit"}
SOURCE_TYPES = {"institutional_profile", "institutional_cv", "first_person_cv", "institutional_biography", "institutional_directory"}
PRECISION_ORDER = {"unknown": 0, "year": 1, "month": 2, "day": 3}
EXPECTED_KEYS = {(c, institution, department) for c, institutions in COUNTRY_INSTITUTIONS.items() for institution in institutions for department in DEPARTMENTS}


class InputError(ValueError):
    """An input violates the declared collection or sampling protocol."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise InputError(message)


def normalized_name(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def canonical_profile_url(value: str) -> str:
    return urldefrag(value.strip())[0]


def person_key(country: str, institution_id: str, department: str, name: str, profile_url: str) -> str:
    text = "|".join((country, institution_id, department, normalized_name(name), canonical_profile_url(profile_url)))
    return "prof-" + hashlib.sha256(text.encode("utf-8")).hexdigest()[:20]


def sample_score(key: str) -> str:
    return hashlib.sha256((SEED + "|" + key).encode("utf-8")).hexdigest()


def roster_sha256(rows: list[dict]) -> str:
    text = json.dumps(sorted(rows, key=lambda row: row["person_key"]), ensure_ascii=False,
                      sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def freeze_roster(rows: list[dict], frozen_at_utc: str) -> dict:
    """Return the common deterministic pre-DOB sampling manifest."""
    ordered = sorted((row["person_key"] for row in rows if row["sampling_eligible"]), key=sample_score)
    selected = ordered[:6]
    return {"algorithm": "sha256_seeded_order_v1", "seed": SEED,
            "planned_sample_size": 6, "sample_size": len(selected),
            "ordered_person_keys": ordered, "selected_person_keys": selected,
            "roster_sha256": roster_sha256(rows), "frozen_at_utc": frozen_at_utc}


def utc_timestamp(value: object, context: str) -> datetime:
    require(isinstance(value, str) and bool(value), f"{context}: timestamp missing")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise InputError(f"{context}: invalid ISO timestamp") from error
    require(result.tzinfo is not None and result.utcoffset().total_seconds() == 0,
            f"{context}: timestamp must explicitly be UTC")
    return result


def http_url(value: object, context: str, *, allow_empty: bool = False) -> None:
    require(isinstance(value, str), f"{context}: URL must be a string")
    if allow_empty and not value:
        return
    parsed = urlsplit(value)
    require(parsed.scheme in {"https", "http"} and bool(parsed.hostname) and not parsed.username and not parsed.password,
            f"{context}: expected a public HTTP(S) URL without credentials")


def validate_claim(claim: dict, context: str) -> None:
    require(isinstance(claim, dict), f"{context}: claim must be an object")
    precision = claim.get("precision")
    require(precision in {"day", "month", "year"}, f"{context}: invalid precision")
    require(claim.get("calendar") in CALENDARS, f"{context}: calendar marker missing or invalid")
    require(claim.get("source_type") in SOURCE_TYPES, f"{context}: invalid source type")
    require(claim.get("source_status") in {"body_observed", "search_snippet_only"}, f"{context}: invalid source status")
    for field in ("date_raw", "excerpt"):
        require(isinstance(claim.get(field), str) and bool(claim[field].strip()), f"{context}: {field} missing")
    require(len(claim["excerpt"].split()) <= 25 and len(claim["excerpt"]) <= 350,
            f"{context}: retain only a short factual date excerpt")
    http_url(claim.get("source_url"), context)
    year, month, day = (claim.get(field) for field in ("year", "month", "day"))
    require(type(year) is int and 1 <= year <= 9999, f"{context}: explicit year required")
    if precision == "year":
        require(month is None and day is None, f"{context}: year precision cannot contain month/day")
    else:
        require(type(month) is int and 1 <= month <= 12, f"{context}: explicit month required")
        if precision == "month":
            require(day is None, f"{context}: month precision cannot contain a default day")
        else:
            require(type(day) is int and 1 <= day <= 31, f"{context}: explicit day required")
            # Gregorian-explicit claims can be validated as Gregorian dates.
            # Lunar/unstated claims retain printed components, with no conversion.
            if claim["calendar"] == "gregorian_explicit":
                try:
                    date(year, month, day)
                except ValueError as error:
                    raise InputError(f"{context}: invalid Gregorian date") from error


def availability(result: dict) -> dict:
    body = [claim for claim in result["claims"] if claim["source_status"] == "body_observed"]
    precision = max((claim["precision"] for claim in body), key=PRECISION_ORDER.get, default="unknown")
    years = sorted({claim["year"] for claim in body})
    if not years:
        window = "unknown"
    elif len(years) > 1:
        window = "conflicting_birth_year_claims"
    elif years[0] < 1835:
        window = "before_window"
    elif years[0] > 1985:
        window = "after_window"
    else:
        window = "inside_window"
    full_dates = {(claim["year"], claim["month"], claim["day"]) for claim in body if claim["precision"] == "day"}
    calendars = {claim["calendar"] for claim in body if claim["precision"] == "day"}
    return {"availability_precision": precision, "body_supported_claim_count": len(body),
            "snippet_only_claim_count": len(result["claims"]) - len(body),
            "explicit_birth_year_claims": ";".join(map(str, years)),
            "birth_window_status": window,
            "printed_day_component_difference": len(full_dates) > 1,
            "day_claim_calendar_markers": ";".join(sorted(calendars)),
            "explicit_lunar_day_claim_present": "lunar_explicit" in calendars,
            "unstated_calendar_day_claim_present": "not_stated" in calendars,
            "accepted_exact_dob": False}


def validate_prior_sampling_snapshot(country: str, department: dict, current_frozen_at: datetime) -> datetime:
    """Validate a documented post-freeze metadata correction without backdating.

    The current rows/hash remain bound at their actual correction time. Only an
    independently recomputable prior selection with identical sampled keys may
    supply the earlier sampling time. Historical non-HTTP URLs are retained in
    that hash/key reconstruction; they are not treated as fetchable sources.
    """
    prior = department.get("prior_sampling_snapshot")
    if prior is None:
        return current_frozen_at
    context = f"{country}/{department['institution_id']}/{department['department']}/prior_snapshot"
    require(isinstance(prior, dict), f"{context}: prior snapshot must be an object")
    require(isinstance(prior.get("correction_reason"), str) and bool(prior["correction_reason"].strip()),
            f"{context}: metadata correction reason missing")
    corrected_at = utc_timestamp(prior.get("corrected_at_utc"), context)
    require(corrected_at == current_frozen_at, f"{context}: corrected_at must equal the current manifest freeze, without backdating")
    old_rows = prior.get("rows")
    require(isinstance(old_rows, list), f"{context}: complete prior rows missing")
    keys = []
    for old_row in old_rows:
        require(isinstance(old_row, dict) and isinstance(old_row.get("name"), str)
                and isinstance(old_row.get("profile_url"), str)
                and type(old_row.get("sampling_eligible")) is bool,
                f"{context}: incomplete prior identity/sampling row")
        expected_key = person_key(country, department["institution_id"], department["department"],
                                  old_row["name"], old_row["profile_url"])
        require(old_row.get("person_key") == expected_key, f"{context}: prior identity key differs")
        keys.append(old_row["person_key"])
    require(len(keys) == len(set(keys)), f"{context}: duplicate prior identity keys")
    old_manifest = prior.get("sampling_manifest")
    require(isinstance(old_manifest, dict), f"{context}: prior sampling manifest missing")
    original_frozen_at = utc_timestamp(old_manifest.get("frozen_at_utc"), context)
    require(original_frozen_at <= corrected_at, f"{context}: prior freeze cannot follow the correction")
    expected_manifest = freeze_roster(old_rows, old_manifest["frozen_at_utc"])
    for field, value in expected_manifest.items():
        require(old_manifest.get(field) == value, f"{context}: prior sampling manifest {field} differs from original rows/seed")
    require(old_manifest["selected_person_keys"] == department["sampling_manifest"]["selected_person_keys"],
            f"{context}: a post-freeze metadata correction cannot change selected identities or their order")
    return original_frozen_at


def validate_department(country: str, department: dict) -> None:
    institution_id, subject = department.get("institution_id"), department.get("department")
    context = f"{country}/{institution_id}/{subject}"
    require((country, institution_id, subject) in EXPECTED_KEYS, f"{context}: outside the fixed 18-department scope")
    require(department.get("roster_status") in ROSTER_STATUSES, f"{context}: invalid roster status")
    require(isinstance(department.get("scope_note"), str) and bool(department["scope_note"].strip()), f"{context}: visible source scope must be described")
    utc_timestamp(department.get("retrieved_at_utc"), context)
    source_urls = department.get("roster_source_urls")
    require(isinstance(source_urls, list) and bool(source_urls), f"{context}: directory sources missing")
    for url in source_urls:
        http_url(url, context)
    rows = department.get("rows")
    require(isinstance(rows, list), f"{context}: rows must be a list")
    if department["roster_status"] == "blocked":
        require(not rows, f"{context}: blocked cannot claim captured roster rows; use partial for indexed/partial observations")
    elif department["roster_status"] == "captured_complete_visible_scope":
        require(bool(rows), f"{context}: an empty parse cannot establish a complete visible faculty scope")
    keys = []
    for row in rows:
        require(isinstance(row, dict), f"{context}: roster row must be an object")
        require(isinstance(row.get("name"), str) and bool(row["name"].strip()), f"{context}: name missing")
        http_url(row.get("profile_url"), context, allow_empty=True)
        require(row["profile_url"] == canonical_profile_url(row["profile_url"]), f"{context}: profile URL not canonical under the declared rule")
        http_url(row.get("roster_source_url"), context)
        require(row["roster_source_url"] in source_urls, f"{context}: row source not listed in directory source inventory")
        require(row.get("staff_category") in STAFF_CATEGORIES, f"{context}: invalid staff category")
        require(type(row.get("sampling_eligible")) is bool, f"{context}: sampling_eligible must be explicit boolean")
        require(isinstance(row.get("title_raw"), str), f"{context}: title_raw missing")
        require(isinstance(row.get("role_evidence_note"), str), f"{context}: role evidence note missing")
        require(not (row["staff_category"] == "unknown_role" and row["sampling_eligible"]), f"{context}: unverified role cannot enter pilot sampling")
        expected = person_key(country, institution_id, subject, row["name"], row["profile_url"])
        require(row.get("person_key") == expected, f"{context}: person identity key mismatch")
        keys.append(row["person_key"])
    require(len(keys) == len(set(keys)), f"{context}: duplicate identity keys")
    manifest = department.get("sampling_manifest")
    require(isinstance(manifest, dict), f"{context}: pre-DOB sampling manifest missing")
    frozen_at = utc_timestamp(manifest.get("frozen_at_utc"), context)
    expected_manifest = freeze_roster(rows, manifest["frozen_at_utc"])
    for field, value in expected_manifest.items():
        require(manifest.get(field) == value, f"{context}: sampling manifest {field} differs from the fixed roster/seed")
    frozen_at = validate_prior_sampling_snapshot(country, department, frozen_at)
    results = department.get("dob_pilot")
    require(isinstance(results, list), f"{context}: dob_pilot must be a list")
    result_keys = [result.get("person_key") for result in results]
    require(len(result_keys) == len(set(result_keys)) and set(result_keys) == set(manifest["selected_person_keys"]),
            f"{context}: DOB results must match every selected identity exactly once, without substitutions")
    for result in results:
        case_context = context + "/" + str(result["person_key"])
        require(result.get("status") in {"day_claim_found", "month_claim_found", "year_claim_found", "not_found", "blocked"}, f"{case_context}: invalid result status")
        for field in ("profile_fetch_attempts", "cv_fetch_attempts", "search_query_count"):
            require(type(result.get(field)) is int and 0 <= result[field] <= 1, f"{case_context}: {field} exceeds the bounded pilot budget or is missing")
        confirmation_attempts = result.get("search_result_body_fetch_attempts", 0)
        require(type(confirmation_attempts) is int and 0 <= confirmation_attempts <= 1,
                f"{case_context}: search_result_body_fetch_attempts exceeds the bounded pilot budget")
        checked_at = utc_timestamp(result.get("checked_at_utc"), case_context)
        require(frozen_at <= checked_at, f"{case_context}: sampling freeze cannot be later than recorded DOB-check completion")
        if "dob_check_started_at_utc" in result:
            started_at = utc_timestamp(result["dob_check_started_at_utc"], case_context)
            require(frozen_at <= started_at <= checked_at,
                    f"{case_context}: DOB-check start must be after sampling freeze and no later than completion")
        overlaps = result.get("observed_higher_tier_overlaps", [])
        require(isinstance(overlaps, list), f"{case_context}: observed higher-tier overlaps must be an array")
        for overlap in overlaps:
            require(isinstance(overlap, dict), f"{case_context}: overlap evidence must be an object")
            http_url(overlap.get("source_url"), case_context)
            require(isinstance(overlap.get("tier"), str) and bool(overlap["tier"].strip()),
                    f"{case_context}: observed overlap tier missing")
            require(any(isinstance(overlap.get(field), str) and overlap[field].strip() for field in ("excerpt", "note")),
                    f"{case_context}: observed overlap evidence note missing")
        require(isinstance(result.get("claims"), list), f"{case_context}: claims list missing")
        sources = result.get("sources")
        require(isinstance(sources, list), f"{case_context}: source-attempt ledger missing")
        source_set = set()
        body_observed_urls = set()
        for source in sources:
            require(isinstance(source, dict), f"{case_context}: source ledger item must be an object")
            http_url(source.get("url"), case_context)
            require(all(isinstance(source.get(field), str) and source[field] for field in ("status", "access_method", "note")), f"{case_context}: source attempt accounting incomplete")
            source_set.add(source["url"])
            if source["status"] == "body_observed":
                body_observed_urls.add(source["url"])
        for claim in result["claims"]:
            validate_claim(claim, case_context)
            require(claim["source_url"] in source_set, f"{case_context}: claim has no matching source-attempt ledger")
            if claim["source_status"] == "body_observed":
                require(claim["source_url"] in body_observed_urls,
                        f"{case_context}: body claim has no matching successful body-observation ledger entry")
        observed = availability(result)
        expected_status = observed["availability_precision"] + "_claim_found"
        if observed["availability_precision"] == "unknown":
            require(result["status"] in {"not_found", "blocked"}, f"{case_context}: snippet-only/absent evidence cannot count as an observed DOB")
        else:
            require(result["status"] == expected_status, f"{case_context}: status disagrees with observed body precision")


def validate_country(data: dict) -> list[dict]:
    require(isinstance(data, dict) and data.get("schema_version") == 1, "Expected country schema_version=1")
    country = data.get("country")
    require(country in COUNTRY_INSTITUTIONS, "Unknown country")
    departments = data.get("departments")
    require(isinstance(departments, list), f"{country}: departments must be a list")
    keys = [(country, value.get("institution_id"), value.get("department")) for value in departments]
    expected = {key for key in EXPECTED_KEYS if key[0] == country}
    require(len(keys) == 6 and set(keys) == expected, f"{country}: every one of the fixed six departments must appear exactly once, including blocked directories")
    for department in departments:
        validate_department(country, department)
    return departments


def write_csv(path: Path, rows: list[dict], fields: list[str] | None = None) -> None:
    if fields is None:
        fields = list(dict.fromkeys(field for row in rows for field in row))
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def build(countries: list[dict], input_files: dict[str, str]) -> tuple[dict, dict[str, list[dict]]]:
    require(len(countries) == 3 and {data.get("country") for data in countries} == set(COUNTRY_INSTITUTIONS),
            "Provide exactly the US, UK and CN country records")
    roster, pilot, department_rows = [], [], []
    profile_groups: dict[str, list[dict]] = defaultdict(list)
    same_institution_name_groups: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    all_person_keys = []
    for data in sorted(countries, key=lambda x: x["country"]):
        country = data["country"]
        for department in sorted(validate_country(data), key=lambda d: (d["institution_id"], d["department"])):
            institution_id, subject = department["institution_id"], department["department"]
            selected = set(department["sampling_manifest"]["selected_person_keys"])
            correction = department.get("prior_sampling_snapshot")
            names = {row["person_key"]: row for row in department["rows"]}
            precision_counts = Counter()
            window_counts = Counter()
            result_counts = Counter()
            for row in department["rows"]:
                record = {"country": country, "institution_id": institution_id, "department": subject,
                          **row, "selected_for_dob_pilot": row["person_key"] in selected,
                          "directory_capture_status": department["roster_status"]}
                roster.append(record)
                all_person_keys.append(row["person_key"])
                if row["profile_url"]:
                    profile_groups[row["profile_url"]].append(record)
                same_institution_name_groups[(country, institution_id, normalized_name(row["name"]))].append(record)
            for result in department["dob_pilot"]:
                observed = availability(result)
                source = names[result["person_key"]]
                pilot.append({"country": country, "institution_id": institution_id, "department": subject,
                              "person_key": result["person_key"], "name": source["name"],
                              "title_raw": source["title_raw"], "staff_category": source["staff_category"],
                              "profile_url": source["profile_url"], "result_status": result["status"],
                              "higher_tier_overlap_status": ("observed_positive_not_exhaustive" if result.get("observed_higher_tier_overlaps") else "not_systematically_checked"),
                              "observed_higher_tier_overlaps_json": json.dumps(result.get("observed_higher_tier_overlaps", []), ensure_ascii=False, sort_keys=True, separators=(",", ":")),
                              "post_freeze_metadata_correction": correction is not None,
                              "timing_evidence_status": ("start_timestamp_recorded_after_sampling_freeze"
                                                         if "dob_check_started_at_utc" in result
                                                         else "completion_timestamp_only_start_unverified"),
                              **observed, "profile_fetch_attempts": result["profile_fetch_attempts"],
                              "cv_fetch_attempts": result["cv_fetch_attempts"],
                              "search_query_count": result["search_query_count"],
                              "search_result_body_fetch_attempts": result.get("search_result_body_fetch_attempts", 0)})
                precision_counts[observed["availability_precision"]] += 1
                window_counts[observed["birth_window_status"]] += 1
                result_counts[result["status"]] += 1
            department_rows.append({"country": country, "institution_id": institution_id, "department": subject,
                                    "roster_status": department["roster_status"], "observed_roster_rows": len(department["rows"]),
                                    "sampling_eligible_rows": sum(row["sampling_eligible"] for row in department["rows"]),
                                    "planned_sample_size": 6, "actual_sample_size": len(selected),
                                    **{precision + "_availability": precision_counts[precision] for precision in PRECISION_ORDER},
                                    "inside_birth_window": window_counts["inside_window"],
                                    "birth_year_unknown": window_counts["unknown"],
                                    "birth_year_conflicting": window_counts["conflicting_birth_year_claims"],
                                    "before_birth_window": window_counts["before_window"], "after_birth_window": window_counts["after_window"],
                                    "blocked_dob_checks": result_counts["blocked"], "accepted_exact_dob": 0,
                                    "post_freeze_metadata_correction": correction is not None,
                                    "selected_keys_frozen_at_utc": correction["sampling_manifest"]["frozen_at_utc"] if correction else department["sampling_manifest"]["frozen_at_utc"],
                                    "current_roster_hash_bound_at_utc": department["sampling_manifest"]["frozen_at_utc"],
                                    "metadata_correction_reason": correction["correction_reason"] if correction else "",
                                    "scope_note": department["scope_note"],
                                    "roster_source_urls": " | ".join(department["roster_source_urls"])})
    require(len(all_person_keys) == len(set(all_person_keys)), "Duplicate person keys across departments/countries")
    precision = Counter(row["availability_precision"] for row in pilot)
    windows = Counter(row["birth_window_status"] for row in pilot)
    statuses = Counter(row["roster_status"] for row in department_rows)
    reused = [{"profile_url": url, "membership_rows": len(rows), "person_keys": ";".join(row["person_key"] for row in rows)}
              for url, rows in sorted(profile_groups.items()) if len(rows) > 1]
    identity_candidates = []
    for url, rows in sorted(profile_groups.items()):
        if len(rows) > 1:
            identity_candidates.append({"match_basis": "exact_profile_url", "country": ";".join(sorted({row["country"] for row in rows})),
                                        "institution_id": ";".join(sorted({row["institution_id"] for row in rows})),
                                        "match_value": url, "membership_rows": len(rows),
                                        "person_keys": ";".join(row["person_key"] for row in rows),
                                        "scope": ("cross_institution" if len({row["institution_id"] for row in rows}) > 1
                                                  else "cross_department" if len({row["department"] for row in rows}) > 1
                                                  else "within_department"),
                                        "review_status": "candidate_only_not_merged"})
    for (country, institution_id, name), rows in sorted(same_institution_name_groups.items()):
        if len(rows) > 1:
            identity_candidates.append({"match_basis": "same_institution_exact_normalized_name", "country": country,
                                        "institution_id": institution_id, "match_value": name,
                                        "membership_rows": len(rows), "person_keys": ";".join(row["person_key"] for row in rows),
                                        "scope": "cross_department" if len({row["department"] for row in rows}) > 1 else "within_department",
                                        "review_status": "candidate_only_not_merged"})
    country_rows = []
    for country in sorted(COUNTRY_INSTITUTIONS):
        p = [row for row in pilot if row["country"] == country]
        d = [row for row in department_rows if row["country"] == country]
        counts = Counter(row["availability_precision"] for row in p)
        country_rows.append({"country": country, "institutions": 3, "departments": len(d),
                             "observed_roster_membership_rows": sum(row["observed_roster_rows"] for row in d),
                             "planned_dob_sample": 36, "actual_dob_sample": len(p),
                             **{key + "_availability": counts[key] for key in PRECISION_ORDER},
                             "partial_or_blocked_directories": sum(row["roster_status"] != "captured_complete_visible_scope" for row in d),
                             "accepted_exact_dob": 0})
    summary = {"dataset": "professor-qs2027-pilot-v1", "status": "validated_availability_pilot",
               "countries": ["US", "UK", "CN"], "universities": 9, "departments": 18,
               "ranking_edition": "QS World University Rankings 2027 overall",
               "observed_roster_membership_rows": len(roster),
               "unique_department_person_keys": len(set(all_person_keys)),
               "person_identity_definition": "Keys include department and profile URL. Counts are affiliation/person-record checks, not guaranteed independent people. Exact profile reuse and same-institution normalized names are flagged without merging, including within-department multi-URL records.",
               "cross_department_profile_reuse_groups": len(reused),
               "cross_department_identity_review_candidates": sum(row["scope"] != "within_department" for row in identity_candidates),
               "identity_review_candidate_groups": len(identity_candidates),
               "within_department_identity_review_candidates": sum(row["scope"] == "within_department" for row in identity_candidates),
               "planned_dob_pilot_size": 108, "actual_dob_pilot_size": len(pilot),
               "unfilled_sample_slots": 108 - len(pilot),
               "directory_status_counts": dict(sorted(statuses.items())),
               "body_supported_availability_precision_counts": {key: precision[key] for key in PRECISION_ORDER},
               "birth_year_window": [1835, 1985], "birth_window_status_counts": dict(sorted(windows.items())),
               "day_claims_with_printed_component_differences": sum(row["printed_day_component_difference"] for row in pilot),
               "day_claims_with_unstated_calendar": sum(row["unstated_calendar_day_claim_present"] for row in pilot),
               "day_claims_with_explicit_lunar_calendar": sum(row["explicit_lunar_day_claim_present"] for row in pilot),
               "recorded_request_attempt_counts": {
                   field: sum(row[field] for row in pilot)
                   for field in ("profile_fetch_attempts", "cv_fetch_attempts", "search_query_count", "search_result_body_fetch_attempts")
               },
               "dob_check_timing_evidence_counts": dict(sorted(Counter(row["timing_evidence_status"] for row in pilot).items())),
               "pre_dob_sampling_start_times_fully_documented": bool(pilot) and all(row["timing_evidence_status"] == "start_timestamp_recorded_after_sampling_freeze" for row in pilot),
               "search_result_body_confirmation_budget_per_person": 1,
               "accepted_exact_dob_count": 0, "final_cohort_frozen": False,
               "full_department_historical_roster_completeness_claimed": False,
               "hierarchy_age_distributions_matched": False,
               "cross_tier_membership_overlap_adjudicated": False,
               "higher_tier_overlap_status": "observed_positive_not_exhaustive" if any(row["higher_tier_overlap_status"] == "observed_positive_not_exhaustive" for row in pilot) else "not_systematically_checked",
               "higher_tier_overlap_status_counts": dict(sorted(Counter(row["higher_tier_overlap_status"] for row in pilot).items())),
               "post_freeze_metadata_corrected_departments": sum(row["post_freeze_metadata_correction"] for row in department_rows),
               "post_freeze_metadata_corrected_person_record_checks": sum(row["post_freeze_metadata_correction"] for row in pilot),
               "bazi_variables_computed": 0, "statistical_analysis_performed": False,
               "merge_external_requests": 0, "calendar_conversion_performed": False,
               "input_sha256": input_files,
               "limitations": [
                   "Counts describe observed official-directory scope; partial/blocked sources do not establish full faculty denominators.",
                   "DOB availability requires an observed body claim; snippets remain discovery metadata only.",
                   "All day-level dates are claims, not formally accepted Gregorian birthdays; calendar markers and disagreements are preserved.",
                   "Unknown birth year remains in the roster and pilot, without exclusion or age inference.",
                   "The 1835-1985 support window does not itself match Nobel/academy age or era distributions.",
                   "This feasibility pilot does not define or freeze the final professor comparison cohort.",
                   "A completion timestamp alone does not prove when DOB checking started. Missing start times remain explicitly unverified, without inventing timestamps or discarding the availability observations.",
                   "Documented metadata corrections bind current rows at their actual correction time. Earlier sampling time is used only after recomputing the complete prior snapshot and verifying identical selected keys; current hashes are not represented as having existed earlier.",
                   "One institution-hosted body confirmation from the bounded search result is permitted per sampled person; legacy absent counters mean zero. No repeated query or retry is authorized."
               ]}
    return summary, {"observed_roster_v1.csv": roster, "dob_availability_pilot_v1.csv": pilot,
                     "department_coverage_v1.csv": department_rows, "country_coverage_v1.csv": country_rows,
                     "cross_department_profile_reuse_v1.csv": reused,
                     "cross_department_identity_review_v1.csv": identity_candidates}


def run(input_paths: list[Path], output_dir: Path) -> dict:
    require(not output_dir.exists() or (output_dir.is_dir() and not any(output_dir.iterdir())),
            "Output directory must be new or empty")
    countries, hashes = [], {}
    for path in input_paths:
        content = path.read_bytes()
        data = json.loads(content.decode("utf-8-sig"))
        countries.append(data)
        logical_name = str(data.get("country", "unknown")) + "/" + path.name
        require(logical_name not in hashes, "Duplicate country input in reproducible hash accounting")
        hashes[logical_name] = hashlib.sha256(content).hexdigest()
    summary, tables = build(countries, hashes)
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, rows in tables.items():
        fields = None
        if name == "cross_department_profile_reuse_v1.csv":
            fields = ["profile_url", "membership_rows", "person_keys"]
        elif name == "cross_department_identity_review_v1.csv":
            fields = ["match_basis", "country", "institution_id", "match_value", "membership_rows", "person_keys", "scope", "review_status"]
        write_csv(output_dir / name, rows, fields)
    (output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown = "# Professor QS2027 availability pilot\n\n"
    markdown += (f"Validated 18 departmental records; observed roster membership rows: **{summary['observed_roster_membership_rows']}**. "
                 f"Actual DOB pilot: **{summary['actual_dob_pilot_size']} / 108 planned**.\n\n")
    markdown += "| Country | Observed roster rows | Pilot N | Day claims | Month claims | Year claims | Unknown | Partial/blocked directories |\n| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |\n"
    for row in tables["country_coverage_v1.csv"]:
        markdown += "| " + " | ".join(str(row[key]) for key in ("country", "observed_roster_membership_rows", "actual_dob_sample", "day_availability", "month_availability", "year_availability", "unknown_availability", "partial_or_blocked_directories")) + " |\n"
    markdown += "\nPrecision counts require observed source bodies and describe availability only. Accepted exact DOBs: **0** (formal adjudication not performed).\n\n"
    markdown += "\n".join("- " + limitation for limitation in summary["limitations"]) + "\n\nBaZi calculations: **0**. Merge network requests: **0**.\n"
    (output_dir / "summary.md").write_text(markdown, encoding="utf-8")
    files = sorted(path for path in output_dir.iterdir() if path.is_file())
    (output_dir / "SHA256SUMS").write_text("".join(hashlib.sha256(path.read_bytes()).hexdigest() + "  " + path.name + "\n" for path in files), encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, nargs="+", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        summary = run(args.inputs, args.output_dir)
    except (InputError, OSError, json.JSONDecodeError) as error:
        print(json.dumps({"status": "failed", "error": str(error), "accepted_exact_dob_count": 0,
                          "final_cohort_frozen": False, "bazi_variables_computed": 0}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps({key: value for key, value in summary.items() if key not in {"input_sha256", "limitations"}}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
