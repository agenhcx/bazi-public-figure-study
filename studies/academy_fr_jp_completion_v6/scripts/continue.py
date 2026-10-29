#!/usr/bin/env python3
"""Prepare, replay and verify reviewed v6 evidence against immutable v5 ledgers."""
import argparse
import collections
import copy
import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
import tempfile
from urllib.parse import urlparse

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT.parent / "academy_fr_jp_completion_v5"
BASE_COMMIT = "fe72fe259ee6aaf90f55c469ba7778a69588044d"
spec = importlib.util.spec_from_file_location("academy_v5", BASE / "scripts/continue.py")
V5 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(V5)
V4, V3, J = V5.V4, V5.V3, V5.J
js, readcsv, require = V5.js, V5.readcsv, V5.require
HOLD_TYPES = {"calendar_hold": "source_calendar_hold", "formal_source_date_conflict": "source_date_conflict_hold", "source_quality_hold_unverified_competing_year": "source_quality_hold", "calendar_and_source_year_hold": "source_calendar_hold"}
HOLD_RANK = {"source_calendar_hold": 1, "source_caveat_hold": 2, "source_quality_hold": 3, "identity_assignment_hold": 4, "source_date_conflict_hold": 5}
ORDINARY_ROLES = {"ordinary_full_member", "ordinary_full_member_nonresident"}
ACADEMY_SOURCE_ROLES = {"firstparty", "first_party", "academy_firstparty", "firstparty_academy", "first_party_academy", "academy_authored", "academy_authored_original", "academy_authored_independent_host", "academy_authored_or_issued_original", "firstparty_academy_pdf", "firstparty_academy_notice", "academy_owned_firstparty", "parent_institution_firstparty"}


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_baseline(root=ROOT):
    pinned = js(root / "inputs/baseline_provenance.json")
    require(pinned["parent_git_commit"] == BASE_COMMIT, "Wrong v5 baseline commit")
    for rel, expected in pinned["baseline_sha256"].items():
        require(sha(BASE / rel) == expected, "Changed v5 baseline: " + rel)
    for rel, expected in pinned["selection_sha256"].items():
        require(sha(root / rel) == expected, "Changed fixed v6 selection: " + rel)
    V5.check_baseline()


def selections(root=ROOT):
    result = {"japan": set(), "france": set()}
    for name, expected in [("japan_a.csv", 17), ("japan_b.csv", 17), ("france_a.csv", 66), ("france_b.csv", 65), ("france_c.csv", 65)]:
        country = "japan" if name.startswith("japan") else "france"
        field = "member_key" if country == "japan" else "candidate_group_id"
        rows = readcsv(root / "selection_queues" / name)
        ids = {r[field] for r in rows}
        require(len(rows) == len(ids) == expected, "Fixed selection cardinality mismatch: " + name)
        require(not (ids & result[country]), "Overlapping fixed queues")
        result[country].update(ids)
    return result


def processing_rows(path):
    raw = readcsv(path) if path.suffix == ".csv" else js(path)
    if isinstance(raw, dict):
        raw = raw.get("rows", raw.get("records", raw.get("queue_status", raw)))
    if isinstance(raw, dict):
        raw = [dict(v, **({"member_key": k} if k.startswith("jpa") else {"candidate_group_id": k})) for k, v in raw.items() if isinstance(v, dict)]
    require(isinstance(raw, list), "Processing records must be a list")
    return raw


def completed_status(status):
    return not status.startswith("not_") and status not in {"unprocessed", "pending"}


def processing_dispositions(path, field):
    result = {}
    for row in processing_rows(path):
        status = next((row[k] for k in ["status", "round_status", "outcome", "new_route_status", "processing_status"] if row.get(k)), "")
        require(isinstance(status, str) and status and field in row, "Missing processing identity/status: " + str(path))
        require(row[field] not in result, "Duplicate processing disposition: " + row[field])
        result[row[field]] = status
    return result


def reviewed_ids(path, field):
    return {key for key, status in processing_dispositions(path, field).items() if completed_status(status)}


def normalize_holds(raw):
    if isinstance(raw, dict):
        records = [dict(v, member_key=k) for k, v in raw.items() if k.startswith("jpa") and isinstance(v, dict)]
    else:
        require(isinstance(raw, list), "Hold list/mapping required")
        records = raw
    result = {}
    for record in records:
        # Search failures and alternate historical calendar expressions are not member-wide holds.
        if record.get("global_member_hold") is False or record.get("hold_scope") in {"claim", "search_outcome"}:
            continue
        status = record.get("status") or record.get("hold_status") or HOLD_TYPES.get(record.get("hold_type"))
        require(status is not None, "Unrecognized member-wide hold type: " + str(record.get("hold_type")))
        require(status in HOLD_RANK, "Unknown birth hold")
        key = record["member_key"]
        value = dict(status=status, reason=record.get("reason") or record.get("resolution") or record.get("note") or "")
        if record.get("existing_modern_claim_explicitly_challenged") is True:
            value["existing_modern_claim_explicitly_challenged"] = True
        require(value["reason"], "Hold needs an explicit reason")
        if key in result:
            result = merge_holds(result, {key: value})
        else:
            result[key] = value
    return result


def merge_holds(inherited, added):
    result = copy.deepcopy(inherited)
    for key, new in added.items():
        require(new.get("status") in HOLD_RANK, "Unknown birth hold")
        if key not in result:
            result[key] = copy.deepcopy(new)
        elif result[key] != new:
            old = result[key]
            # Never release/downgrade an inherited hold. Preserve both reasons even when strengthening it.
            status = max([old["status"], new["status"]], key=HOLD_RANK.get)
            result[key] = dict(status=status, reason=old["reason"] + " | v6 additional hold: " + new["reason"], inherited_hold=copy.deepcopy(old), v6_additional_hold=copy.deepcopy(new))
    return result


def prepare(root=ROOT):
    check_baseline(root)
    chosen = selections(root)
    config = js(root / "inputs/batch_selection.json")
    source = root / "source_batches"
    jp_cross = set(config.get("japan_cross_source_member_keys", []))
    require(not (jp_cross & chosen["japan"]), "Japan cross-source addenda must be counted outside fixed34")
    base_jp = {r["member_key"]: r for r in readcsv(BASE / "outputs/japan_master.csv")}
    require(jp_cross <= base_jp.keys(), "Unknown Japan cross-source identity")
    delta = []
    for rel in config["japan_claim_files"]:
        for i, row in enumerate(js(source / rel)):
            require(row["member_key"] in chosen["japan"] | jp_cross, "Unselected v6 Japan claim")
            delta.append(dict(row, source_batch_record=rel + ":" + str(i), source_batch_version="v6"))
    processed = set()
    all_jp_outcomes = set()
    for rel in config["japan_processed_files"]:
        dispositions = processing_dispositions(source / rel, "member_key")
        require(not (all_jp_outcomes & dispositions.keys()), "Duplicate Japan disposition across source files")
        all_jp_outcomes.update(dispositions)
        processed.update(k for k, status in dispositions.items() if completed_status(status))
    require(all_jp_outcomes == chosen["japan"], "All34 fixed Japan candidates need explicit outcomes, including not_searched")
    require(processed <= chosen["japan"], "Unknown reviewed Japan ID")
    new_holds = {}
    for rel in config["japan_hold_files"]:
        new_holds = merge_holds(new_holds, normalize_holds(js(source / rel)))
    require(set(new_holds) <= chosen["japan"] | jp_cross, "Unselected v6 Japan hold")
    decisions = []
    for rel in config["france_decision_files"]:
        decisions.extend(dict(d, source_batch_file=rel, source_batch_version="v6") for d in js(source / rel))
    cross = set(config.get("france_cross_source_candidate_ids", []))
    require(not (cross & chosen["france"]), "Cross-source addendum must be counted outside fixed196")
    base_fr = {r["candidate_group_id"]: r for r in readcsv(BASE / "outputs/france_master877.csv")}
    for key in cross:
        require(key in base_fr and base_fr[key]["identity_accepted"] == base_fr[key]["dob_accepted"] == "1"
                and base_fr[key]["membership_accepted"] == "0" and base_fr[key]["election_date_conflict"] != "1",
                "Cross-source ID must be an unchanged identity/DOB-approved strict gap without conflict")
    require({d["candidate_group_id"] for d in decisions} <= chosen["france"] | cross, "Unselected v6 France decision")
    for d in decisions:
        if d["candidate_group_id"] in cross:
            require(V3.flag(d["membership_accepted"]) == "1", "Cross-source addendum needs actual strict-positive evidence")
            validate_france_positive(d, base_fr[d["candidate_group_id"]])
    fr_processed, all_fr_outcomes = set(), set()
    for rel in config["france_processed_files"]:
        dispositions = processing_dispositions(source / rel, "candidate_group_id")
        require(not (all_fr_outcomes & dispositions.keys()), "Duplicate France disposition across source files")
        all_fr_outcomes.update(dispositions)
        fr_processed.update(k for k, status in dispositions.items() if completed_status(status))
    require(all_fr_outcomes == chosen["france"], "All196 fixed France candidates need explicit outcomes, including not_searched")
    require(fr_processed <= chosen["france"], "Unknown reviewed France ID")
    old_claims = js(BASE / "inputs/japan_claims.json")
    old_holds = js(BASE / "inputs/japan_holds.json")
    old_processed = js(BASE / "inputs/japan_processed_ids.json")
    return {"japan_claims.json": old_claims + delta,
            "japan_delta_claims.json": delta,
            "japan_holds.json": merge_holds(old_holds, new_holds),
            "japan_delta_holds.json": new_holds,
            "japan_processed_ids.json": sorted(set(old_processed) | processed),
            "japan_delta_processed_ids.json": sorted(processed),
            "france_decisions.json": decisions,
            "france_processed_ids.json": sorted(fr_processed),
            "inherited_france_decisions.json": readcsv(BASE / "outputs/france_membership_decisions.csv")}


def previous_japan():
    return V5.japan(js(BASE / "inputs/japan_delta_claims.json"), js(BASE / "inputs/japan_delta_holds.json"), js(BASE / "inputs/japan_delta_processed_ids.json"))


def japan(delta, new_holds, new_processed):
    base_rows, base_ledger, _, baseline = previous_japan()
    by = {r["member_key"]: r for r in base_rows}
    require(set(new_processed) <= by.keys(), "Unknown processed Japan identity")
    require(set(new_holds) <= by.keys(), "Unknown Japan hold identity")
    for c in delta:
        J.validate_claim(c, by)
        require(not any(h in c["source_url"] for h in ["wikipedia.org", "wikidata.org"]), "Crowd-source evidence not allowed")
        original_hash = c.get("source_sha256")
        if original_hash is None:
            exceptions = js(ROOT / "inputs/batch_selection.json").get("web_body_capture_exceptions", [])
            approved = [e for e in exceptions if all(c.get(k) == e.get(k) for k in ["member_key", "source_url", "extracted_body_sha256", "source_original_capture_http_status", "web_body_ref"])
                        and re.fullmatch(r"turn\d+(?:view|fetch|search)\d+", e.get("root_verification_ref", "")) is not None]
            require(len(approved) == 1, "Null original hash is not an explicitly approved source exception")
            require(c.get("source_capture_status") == "original_capture_failed_body_verified_via_web"
                    and type(c.get("source_original_capture_http_status")) is int
                    and 400 <= c["source_original_capture_http_status"] <= 599
                    and re.fullmatch(r"turn\d+(?:view|fetch)\d+", c.get("web_body_ref", "")) is not None
                    and re.fullmatch(r"[0-9a-f]{64}", c.get("extracted_body_sha256", "")) is not None,
                    "Null original hash needs exact approved failure/web-body evidence; derived text is not original bytes")
        else:
            require(re.fullmatch(r"[0-9a-f]{64}", original_hash) is not None, "New source needs original captured-body SHA256")
        require(c.get("retrieved_utc") or c.get("retrieved_date"), "New source needs retrieval time")
        reviewed_tiers = js(ROOT / "inputs/batch_selection.json").get("reviewed_source_tiers", [])
        require(c.get("source_tier") in set(baseline["source_tier_claim_counts"]) | set(reviewed_tiers), "Unreviewed source tier")
    for key, h in new_holds.items():
        if h["status"] == "source_calendar_hold" and by[key]["dob_status"] == "body_day_no_known_conflict":
            require(h.get("existing_modern_claim_explicitly_challenged") is True, "Historical alternate cannot erase supported modern date")
    cumulative_holds = merge_holds(js(BASE / "inputs/japan_holds.json"), new_holds)
    rows, ledger, queue, summary = V4.japan(js(BASE / "inputs/japan_claims.json") + delta, cumulative_holds,
                                          sorted(set(js(BASE / "inputs/japan_processed_ids.json")) | set(new_processed)))
    for r in rows:
        r["v4_source_claim_added"] = by[r["member_key"]]["v4_source_claim_added"]
        r["v5_source_claim_added"] = by[r["member_key"]]["v5_source_claim_added"]
        r["v6_source_claim_added"] = any(c["member_key"] == r["member_key"] for c in delta)
        require(r["broad_section_supported"] == by[r["member_key"]]["broad_section_supported"], "v6 cannot alter Japan scope")
        if by[r["member_key"]]["dob_status"].endswith("_hold"):
            require(r["dob_status"].endswith("_hold"), "Inherited Japan hold released")
            require(HOLD_RANK[r["dob_status"]] >= HOLD_RANK[by[r["member_key"]]["dob_status"]], "Inherited Japan hold downgraded")
    require({c["claim_id"] for c in base_ledger} <= {c["claim_id"] for c in ledger}, "Inherited claim lost")
    summary.update(baseline_day_no_known_conflict=baseline["body_day_no_known_conflict"],
                   day_status_net_change=summary["body_day_no_known_conflict"] - baseline["body_day_no_known_conflict"],
                   new_raw_source_claim_rows=len(delta), inherited_v5_raw_source_claim_rows=len(js(BASE / "inputs/japan_claims.json")),
                   newly_processed_v6_candidates=len(set(new_processed)), new_section_decisions=0)
    return rows, ledger, queue, summary


def academy_original(e):
    role = str(e.get("source_role", "")).lower().replace("-", "_").replace(" ", "_")
    host = (urlparse(e.get("source_url", "")).hostname or "").lower()
    academy_host = host in {"academie-sciences.fr", "www.academie-sciences.fr", "comptes-rendus.academie-sciences.fr",
                            "institutdefrance.fr", "www.institutdefrance.fr", "podcasts.institutdefrance.fr"}
    stated_authorship = e.get("academy_authored_or_issued_original") is True
    return (role in ACADEMY_SOURCE_ROLES and (academy_host or stated_authorship)) or (stated_authorship and academy_host)


def ordinary_subject_event(e):
    """Metadata cannot re-label an as-of bound or the notice author's title as an election."""
    non_events = {"as_of", "asof", "status_as_of", "dated_role_bound", "author_title", "author_membership",
                  "membership_attested_by_year", "presidency_attesting_membership",
                  "perpetual_secretary_appointment_attesting_membership_by_year"}
    kind = str(e.get("event_type", e.get("event_kind", ""))).lower().replace("-", "_").replace(" ", "_")
    subject = str(e.get("event_subject_role", e.get("subject_role", ""))).lower()
    return (kind not in non_events and "as_of" not in kind and "asof" not in kind
            and subject not in {"author", "notice_author", "speaker"}
            and e.get("event_is_as_of") is not True and e.get("event_belongs_to_author") is not True
            and e.get("event_year_is_derived") is not True)


def validate_france_positive(d, before):
    require(d.get("previous_conflict_explicitly_resolved") is not True, "v6 cannot release inherited France election conflicts")
    if V3.flag(d["membership_accepted"]) != "1":
        return
    require(before.get("election_date_conflict") != "1", "Inherited France conflict must stay held")
    precision = d.get("accepted_full_member_election_precision")
    accepted_date = d.get("accepted_full_member_election_date")
    accepted_year = d.get("accepted_full_member_election_year")
    if precision == "day":
        require(isinstance(accepted_date, str), "Accepted day required")
        day = datetime.date.fromisoformat(accepted_date)
        require(accepted_year in (None, "", day.year, str(day.year)), "Accepted day/year disagree")
        year = day.year
    else:
        require(precision == "year" and type(accepted_year) is int and not accepted_date, "Exact year precision required")
        year = accepted_year
    matching = []
    for e in d.get("evidence", []):
        if not (e.get("body_verified") is True and ordinary_subject_event(e) and e.get("role") in ORDINARY_ROLES and e.get("quote") and e.get("identity_note") and academy_original(e)):
            continue
        event_date, event_year = e.get("event_date"), e.get("event_year")
        if precision == "day":
            same = e.get("event_precision") == "day" and event_date == accepted_date and event_year in (None, "", year, str(year))
        else:
            same = e.get("event_precision") in {"day", "year"} and event_year in (year, str(year))
            if event_date:
                same = same and datetime.date.fromisoformat(event_date).year == year
        if same:
            matching.append(e)
    require(matching, "Strict France acceptance needs a matching Academy-original ordinary-full-member event; correspondent/foreign events cannot substitute")


def france(decisions):
    base_rows = readcsv(BASE / "outputs/france_master877.csv")
    before = {r["candidate_group_id"]: r for r in base_rows}
    for d in decisions:
        require(d["candidate_group_id"] in before, "Unknown France identity")
        validate_france_positive(d, before[d["candidate_group_id"]])
    rows, accepted, gaps, delta_ledger, summary = V3.france(base_rows, decisions)
    changed = {d["candidate_group_id"] for d in decisions}
    fields = ["membership_decision_status", "membership_review_reason", "evidence_urls", "election_source_conflict_retained"]
    for r in rows:
        old = before[r["candidate_group_id"]]
        for field in fields:
            r["v6_" + field] = r["v3_" + field] if r["candidate_group_id"] in changed else ""
            for version in ["v3_", "v4_", "v5_"]:
                r[version + field] = old.get(version + field, "")
        if r["candidate_group_id"] in changed:
            r["source_evidence_review_version"] = "France_v6_membership_continuation_20261029"
        else:
            r["membership_as_of_year"] = old.get("membership_as_of_year", "")
        require(old.get("election_date_conflict") != "1" or r["election_date_conflict"] == "1", "Inherited France conflict lost")
    # Keep v5 review rows, including Louis's impossible inherited source event, as immutable history.
    ledger = readcsv(BASE / "outputs/france_membership_decisions.csv") + delta_ledger
    summary.update(baseline_all_three_accepted=js(BASE / "outputs/summary.json")["france"]["all_three_accepted"],
                   all_three_net_change=len(accepted) - js(BASE / "outputs/summary.json")["france"]["all_three_accepted"],
                   inherited_v5_membership_decision_rows=len(ledger) - len(delta_ledger),
                   source_backed_decisions=len(decisions))
    return rows, accepted, gaps, ledger, summary



def processing_summary(root=ROOT):
    config = js(root / "inputs/batch_selection.json")
    result = {}
    for country, field in [("japan", "member_key"), ("france", "candidate_group_id")]:
        by_file, activity, outcomes = {}, {}, {}
        total = collections.Counter()
        for rel in config[country + "_processed_files"]:
            dispositions = processing_dispositions(root / "source_batches" / rel, field)
            counts = collections.Counter(dispositions.values())
            by_file[rel] = dict(counts)
            total.update(counts)
            outcomes.update(dispositions)
            summary_path = root / "source_batches" / Path(rel).parent / "summary.json"
            if summary_path.exists():
                activity[str(summary_path.relative_to(root))] = {k:v for k,v in js(summary_path).items() if type(v) in (int, float)}
        result[country] = dict(status_counts=dict(total), by_file=by_file,
                               explicit_outcome_rows=len(outcomes),
                               actually_processed_dispositions=sum(completed_status(s) for s in outcomes.values()),
                               not_processed_ids=sorted(k for k,s in outcomes.items() if not completed_status(s)),
                               batch_cache_scan_only_dispositions=sum(n for s, n in total.items() if "cache_scan_only_no_targeted_search" in s),
                               explicit_targeted_status_dispositions=sum(n for s, n in total.items() if s.startswith("targeted_")),
                               collector_reported_numeric_activity=activity,
                               note="Selection/outcome coverage is not completed processing or individual new-query coverage. Not-searched rows remain unprocessed. Exact status labels and collector-reported search metrics are separate; source-backed approval alone does not imply a targeted new search.")
    return result


def assemble(output):
    require(not output.exists(), "Fresh output directory required")
    check_baseline()
    expected = prepare()
    for name, value in expected.items():
        require(js(ROOT / "inputs" / name) == value, "Prepared input changed: " + name)
    jm, jl, jq, j = japan(js(ROOT / "inputs/japan_delta_claims.json"), js(ROOT / "inputs/japan_delta_holds.json"), js(ROOT / "inputs/japan_delta_processed_ids.json"))
    jp_cross = set(js(ROOT / "inputs/batch_selection.json").get("japan_cross_source_member_keys", []))
    j["cross_source_additional_member_keys"] = sorted({c["member_key"] for c in js(ROOT / "inputs/japan_delta_claims.json") if c["member_key"] in jp_cross})
    j["cross_source_additional_candidates"] = len(j["cross_source_additional_member_keys"])
    fm, fa, fg, fd, f = france(js(ROOT / "inputs/france_decisions.json"))
    f["newly_processed_v6_candidates"] = len(js(ROOT / "inputs/france_processed_ids.json"))
    cross = set(js(ROOT / "inputs/batch_selection.json").get("france_cross_source_candidate_ids", []))
    f["cross_source_additional_candidate_ids"] = sorted(d["candidate_group_id"] for d in js(ROOT / "inputs/france_decisions.json") if d["candidate_group_id"] in cross)
    f["cross_source_additional_candidates"] = len(f["cross_source_additional_candidate_ids"])
    output.mkdir(parents=True)
    for name, rows in [("japan_master.csv", jm), ("japan_birth_claims.csv", jl), ("japan_next_action_queue.csv", jq), ("france_master877.csv", fm), ("france_accepted_all_three.csv", fa), ("france_remaining_gaps.csv", fg), ("france_membership_decisions.csv", fd)]:
        J.write_csv(output / name, rows)
    summary = dict(date="2026-10-29", baseline_commit=BASE_COMMIT, japan=j, france=f,
                   fixed_selection_counts={"japan": 34, "france": 196}, actual_processed_counts={"japan": len(js(ROOT / "inputs/japan_delta_processed_ids.json")), "france": len(js(ROOT / "inputs/france_processed_ids.json"))}, processing_status_breakdown=processing_summary(), professor_collection="paused", fields_collection="preserved_parked", collection_complete=False,
                   analysis_cohort_frozen=False, bazi_variables_computed=0)
    dump(output / "summary.json", summary)
    return summary


def verify():
    actual = {str(p.relative_to(ROOT)): sha(p) for p in ROOT.rglob("*") if p.is_file() and p != ROOT / "MANIFEST.json" and "__pycache__" not in p.parts}
    require(actual == js(ROOT / "MANIFEST.json")["files"], "Inventory/hash mismatch")
    require(not any("private" in Path(p).parts or p.endswith((".pdf", ".html", ".png", ".jpg", ".pyc")) for p in actual), "Raw/private source in deliverable")
    for rel in actual:
        parts = Path(rel).parts
        if parts[0] == "source_batches":
            require(len(parts) == 3 and (Path(rel).suffix in {".json", ".csv"} or parts[-1] in {"README.md", "README.txt"}), "Only top-level public source metadata is deliverable: " + rel)
    check_baseline()
    for name, value in prepare().items():
        require(js(ROOT / "inputs" / name) == value, "Prepared input mismatch: " + name)
    summary = js(ROOT / "outputs/summary.json")
    j, f = summary["japan"], summary["france"]
    require(summary["fixed_selection_counts"] == {"japan": 34, "france": 196}, "Fixed selection coverage changed")
    require(summary["actual_processed_counts"] == {"japan": len(js(ROOT / "inputs/japan_delta_processed_ids.json")), "france": len(js(ROOT / "inputs/france_processed_ids.json"))}, "Actual processing accounting mismatch")
    require(summary["processing_status_breakdown"]["france"]["explicit_outcome_rows"] == 196, "France outcomes incomplete")
    require(summary["processing_status_breakdown"]["japan"]["explicit_outcome_rows"] == 34, "Japan outcomes incomplete")
    require(summary["processing_status_breakdown"]["japan"]["actually_processed_dispositions"] == summary["actual_processed_counts"]["japan"], "Unsearched Japan rows counted as processed")
    require(summary["processing_status_breakdown"]["france"]["actually_processed_dispositions"] == summary["actual_processed_counts"]["france"], "Unsearched France rows counted as processed")
    require((j["restored_candidate_universe"], j["broad_section_ii_supported"], j["section_i_excluded"], j["section_unresolved"]) == (482, 428, 7, 47), "Japan scope changed")
    require(j["baseline_day_no_known_conflict"] == 359, "Wrong Japan baseline")
    require(j["body_day_no_known_conflict"] == j["institutional_or_university_supported_day_no_known_conflict"] + j["edited_reference_only_day_no_known_conflict"] + j["other_attributed_secondary_only_day_no_known_conflict"], "Source tier totals mismatch")
    require(j["nonexcluded_body_day_no_known_conflict"] + j["nonexcluded_dob_not_day_count"] == 475, "Japan DOB accounting mismatch")
    require((f["candidate_groups"], f["current"]["identity_accepted"], f["current"]["dob_accepted"]) == (877, 755, 744), "France nonmembership dimension changed")
    require(f["current"]["membership_accepted"] >= 315 and f["all_three_accepted"] >= 313, "France approvals lost")
    require(f["known_election_conflict_rows"] >= 25, "Inherited France chronology holds lost")
    require(f["all_three_accepted"] + f["all_three_remaining_gaps"] == 877, "France gap accounting mismatch")
    require(not summary["analysis_cohort_frozen"] and summary["bazi_variables_computed"] == 0, "Analysis gate changed")
    require(j["calendar_conversions_performed"] == j["default_date_components_filled"] == j["analysis_record_count"] == 0, "Japan collection gates changed")
    require(all(r["final_cohort_accepted"] == "False" and r["bazi_variables_computed"] == "0" for r in readcsv(ROOT / "outputs/japan_master.csv")), "Japan final cohort gate changed")
    with tempfile.TemporaryDirectory(prefix=".verify-replay-", dir=ROOT) as folder:
        replay = Path(folder) / "outputs"
        assemble(replay)
        require({p.name for p in replay.iterdir()} == {p.name for p in (ROOT / "outputs").iterdir()}, "Output inventory differs from deterministic replay")
        for path in replay.iterdir():
            require(path.read_bytes() == (ROOT / "outputs" / path.name).read_bytes(), "Output byte replay mismatch: " + path.name)
    print(f"{len(actual)} pinned v6 files verified; v5 evidence and fixed processing scope preserved")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["prepare", "assemble", "verify"])
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    if args.mode == "verify":
        verify()
    elif args.mode == "prepare":
        require(args.output_dir is not None and not args.output_dir.exists(), "Fresh output directory required")
        values = prepare()
        args.output_dir.mkdir(parents=True)
        for name, value in values.items():
            dump(args.output_dir / name, value)
    else:
        require(args.output_dir is not None, "Output directory required")
        summary = assemble(args.output_dir)
        print(json.dumps({"japan_day": summary["japan"]["body_day_no_known_conflict"], "france_membership": summary["france"]["current"]["membership_accepted"]}))


if __name__ == "__main__":
    main()
