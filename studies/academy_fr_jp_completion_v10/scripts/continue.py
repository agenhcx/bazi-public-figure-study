#!/usr/bin/env python3
"""Prepare, replay and verify reviewed v10 evidence against immutable v9 ledgers."""
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
BASE = ROOT.parent / "academy_fr_jp_completion_v9"
BASE_COMMIT = "c8d38ab3db34270d39d1c39e2aa368de612edc3f"
spec = importlib.util.spec_from_file_location("academy_v9", BASE / "scripts/continue.py")
V9 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(V9)
V4, V3, J = V9.V4, V9.V3, V9.J
js, readcsv, require = V9.js, V9.readcsv, V9.require
HOLD_TYPES = {"calendar_hold": "source_calendar_hold", "formal_source_date_conflict": "source_date_conflict_hold", "source_quality_hold_unverified_competing_year": "source_quality_hold", "calendar_and_source_year_hold": "source_calendar_hold"}
HOLD_RANK = {"source_calendar_hold": 1, "source_caveat_hold": 2, "source_quality_hold": 3, "identity_assignment_hold": 4, "source_date_conflict_hold": 5}
ORDINARY_ROLES = {"ordinary_full_member", "ordinary_full_member_nonresident"}
ACADEMY_SOURCE_ROLES = {"firstparty", "first_party", "academy_firstparty", "firstparty_academy", "first_party_academy", "academy_authored", "academy_authored_original", "academy_authored_independent_host", "academy_authored_or_issued_original", "firstparty_academy_pdf", "firstparty_academy_notice", "academy_owned_firstparty", "parent_institution_firstparty"}
# Prior exact calendar decisions are applied by immutable V9.japan before v10
# replays its reviewed baseline directly. No new routing release is implicit.
EXACT_CALENDAR_ROUTING_RELEASES = {}
REVIEWED_ATTRIBUTED_SECONDARY_TIERS = set(V9.REVIEWED_ATTRIBUTED_SECONDARY_TIERS)


EXACT_SECTION_ACTIONS = {'jpa-unlinked-0e74d049141c9fd7': {'section': '2', 'source_url': 'https://dl.ndl.go.jp/api/iiif/897383/R0000011/full/full/0/default.jpg', 'source_sha256': 'b69686b265016700d2e1c75d30cb89c50692e094c93cf848fc073af34f99dbb4', 'printed_name': '菊池大麓', 'edition_year': 1906}, 'jpa-unlinked-501b5814ef8eb21f': {'section': '2', 'source_url': 'https://dl.ndl.go.jp/api/iiif/897383/R0000011/full/full/0/default.jpg', 'source_sha256': 'b69686b265016700d2e1c75d30cb89c50692e094c93cf848fc073af34f99dbb4', 'printed_name': '三宅秀', 'edition_year': 1906}, 'jpa-unlinked-685499c7cac8c622': {'section': '2', 'source_url': 'https://dl.ndl.go.jp/api/iiif/897383/R0000011/full/full/0/default.jpg', 'source_sha256': 'b69686b265016700d2e1c75d30cb89c50692e094c93cf848fc073af34f99dbb4', 'printed_name': '大澤謙二', 'edition_year': 1906}, 'jpa-unlinked-b3170067960e401e': {'section': '2', 'source_url': 'https://dl.ndl.go.jp/api/iiif/897383/R0000011/full/full/0/default.jpg', 'source_sha256': 'b69686b265016700d2e1c75d30cb89c50692e094c93cf848fc073af34f99dbb4', 'printed_name': '箕作佳吉', 'edition_year': 1906}, 'jpa-unlinked-b6a85346dd06dbc7': {'section': '2', 'source_url': 'https://dl.ndl.go.jp/api/iiif/897383/R0000011/full/full/0/default.jpg', 'source_sha256': 'b69686b265016700d2e1c75d30cb89c50692e094c93cf848fc073af34f99dbb4', 'printed_name': '緒方正規', 'edition_year': 1906}, 'jpa-unlinked-f72252fc4e77931a': {'section': '2', 'source_url': 'https://dl.ndl.go.jp/api/iiif/897383/R0000011/full/full/0/default.jpg', 'source_sha256': 'b69686b265016700d2e1c75d30cb89c50692e094c93cf848fc073af34f99dbb4', 'printed_name': '櫻井錠二', 'edition_year': 1906}, 'jpa-unlinked-4ed3afac92825ad9': {'section': '2', 'source_url': 'https://dl.ndl.go.jp/api/iiif/897383/R0000011/full/full/0/default.jpg', 'source_sha256': 'b69686b265016700d2e1c75d30cb89c50692e094c93cf848fc073af34f99dbb4', 'printed_name': '小藤文次郎', 'edition_year': 1906}, 'jpa-unlinked-3a793d0d8e9d64db': {'section': '2', 'source_url': 'https://dl.ndl.go.jp/api/iiif/897383/R0000011/full/full/0/default.jpg', 'source_sha256': 'b69686b265016700d2e1c75d30cb89c50692e094c93cf848fc073af34f99dbb4', 'printed_name': '山川健次郎', 'edition_year': 1906}, 'jpa-unlinked-29e021ed17d66ad4': {'section': '2', 'source_url': 'https://dl.ndl.go.jp/api/iiif/897383/R0000011/full/full/0/default.jpg', 'source_sha256': 'b69686b265016700d2e1c75d30cb89c50692e094c93cf848fc073af34f99dbb4', 'printed_name': '小金井良精', 'edition_year': 1906}, 'jpa-unlinked-eabfb6c33df81d73': {'section': '2', 'source_url': 'https://dl.ndl.go.jp/api/iiif/897383/R0000012/full/full/0/default.jpg', 'source_sha256': 'd4c147ed03719be1ba7080970a4eb75d9ba6703a2a20337eb82ef57a99cf567a', 'printed_name': '寺尾壽', 'edition_year': 1906}}

EXACT_FRANCE_DOB_QUARANTINE = {
    "CTHS_112065": {
        "baseline_accepted_dob_iso": "1882-01-13",
        "observed_competing_dates": ["1882-01-13", "1882-01-18"],
        "source_claims_sha256": "b91c246142750ba7c56fb089e52f6f3b685d6c1d9a648b0cdebc684a687c61a7",
        "source_hashes": {
            "1882-01-13": "305d8c729ccba9da82c9e06dafa0261375728ed47d4c7e7f21b7b67640612107",
            "1882-01-18": "86deb7aa21ba03b79815ce3925a2214763459a0db9728a6028dc1b22affc26db",
        },
    }
}

def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_baseline(root=ROOT):
    pinned = js(root / "inputs/baseline_provenance.json")
    require(pinned["parent_git_commit"] == BASE_COMMIT, "Wrong v9 baseline commit")
    for rel, expected in pinned["baseline_sha256"].items():
        require(sha(BASE / rel) == expected, "Changed v9 baseline: " + rel)
    for rel, expected in pinned["selection_sha256"].items():
        require(sha(root / rel) == expected, "Changed fixed v10 selection: " + rel)
    V9.check_baseline()


def selections(root=ROOT):
    result = {"japan": set(), "france": set()}
    for name, expected in [("japan_sections.csv", 47), ("france_a.csv", 28), ("france_b.csv", 27), ("france_c.csv", 27)]:
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
            result[key] = dict(status=status, reason=old["reason"] + " | v10 additional hold: " + new["reason"], inherited_hold=copy.deepcopy(old), v10_additional_hold=copy.deepcopy(new))
    return result


def reviewed_section_decisions(root=ROOT):
    proposals_path = root / "source_batches/japan_scope/section_proposals.json"
    proposals = js(proposals_path)
    require(isinstance(proposals, list), "Section proposals must be a list")
    approvals_path = root / "inputs/japan_section_approvals.json"
    approvals = js(approvals_path) if approvals_path.exists() else []
    require(isinstance(approvals, list), "Section approvals must be a list")
    require(len({x.get("member_key") for x in approvals}) == len(approvals), "Duplicate section approval")
    approved = {x.get("member_key"): x for x in approvals}
    base = {r["member_key"]: r for r in readcsv(BASE / "outputs/japan_master.csv")}
    require(set(approved) <= {p.get("member_key") for p in proposals}, "Approval has no source proposal")
    result = []
    for p in proposals:
        key = p.get("member_key")
        require(key in EXACT_SECTION_ACTIONS, "Section proposal is outside exact reviewed identities")
        expected = EXACT_SECTION_ACTIONS[key]
        require(key in base and not base[key]["broad_section_supported"], "Section action may resolve only an unresolved identity")
        require(p.get("new_broad_section") == expected["section"] and p.get("source_url") == expected["source_url"]
                and p.get("source_sha256") == expected["source_sha256"]
                and p.get("source_printed_member_name") == expected["printed_name"]
                and p.get("source_edition_year") == expected["edition_year"], "Exact section source/identity binding mismatch")
        require(p.get("name_jp") == base[key]["name_jp"] and p.get("previous_broad_section_supported") == "", "Section identity/previous-state mismatch")
        year = expected["edition_year"]
        require(not base[key]["first_election_date"] or base[key]["first_election_date"] <= f"{year}-12-31", "Section source predates the preserved membership interval")
        require(not base[key]["final_retirement_date"] or base[key]["final_retirement_date"] >= f"{year}-01-01", "Section source postdates the preserved membership interval")
        label = {"1": "第一部", "2": "第二部"}[expected["section"]]
        require(p.get("decision_type") == "set_broad_section" and p.get("source_printed_broad_section") == label
                and p.get("evidence_quote") == label, "Section must be explicitly printed, not inferred")
        require(p.get("body_verified") is True and p.get("identity_body_supported") is True
                and p.get("source_image_visually_verified") is True and p.get("source_identity_bridge")
                and p.get("source_location") and p.get("source_cover_sha256"), "Section needs actual image, edition and identity review")
        require(p.get("source_role") == "academy_issued_original_member_directory_hosted_national_library"
                and urlparse(p["source_url"]).hostname == "dl.ndl.go.jp", "Section needs the reviewed Academy directory original")
        require(p.get("degree_rule_extended") is False and p.get("exact_subsection_inferred") is False
                and p.get("new_exact_subsection") is None and p.get("dob_modified") is False
                and p.get("membership_election_date_modified") is False, "Section scope cannot infer degree/subsection or change DOB/election")
        approval = approved.get(key)
        require(approval is not None and approval.get("root_approved") is True
                and approval.get("independent_section_qa_passed") is True, "Section proposal awaits explicit root and independent QA approval")
        require(all(approval.get(k) == p.get(k) for k in ["member_key", "new_broad_section", "source_url", "source_sha256"]), "Section approval source binding mismatch")
        rel = approval.get("independent_section_qa_file")
        require(isinstance(rel, str) and not Path(rel).is_absolute() and Path(rel).parts[0] == "source_audits"
                and ".." not in Path(rel).parts, "Section QA path must stay in public audit scope")
        qa_path = root / rel
        require(qa_path.is_file() and sha(qa_path) == approval.get("independent_section_qa_sha256"), "Section QA hash binding mismatch")
        require(sha(proposals_path) == approval.get("section_proposals_sha256"), "Section proposal-file hash mismatch")
        qa = js(qa_path)
        require(qa.get("independent_qa_passed") is True
                and qa.get("section_proposals_sha256") == sha(proposals_path)
                and qa.get("worker_manifest_sha256") == sha(proposals_path.parent / "MANIFEST.json"), "Section independent QA reviewed a different final source handoff")
        checks = [c for c in qa.get("proposal_checks", []) if c.get("member_key") == key and c.get("source_sha256") == p["source_sha256"]]
        require(len(checks) == 1 and all(checks[0].get(k) is True for k in ["independent_actual_image_visual_passed", "unique_preserved_identity_match_passed", "1906_year_overlap_passed", "no_backprojection_to_original_election", "no_exact_subsection_inference"])
                and checks[0].get("new_broad_section") == expected["section"]
                and checks[0].get("literal_same_column_section") == label, "Independent QA did not approve this exact section source/identity")
        result.append(dict(p, root_approved=True, independent_qa_passed=True, root_approval_record=copy.deepcopy(approval), source_batch_version="v10"))
    return result


def apply_section_decisions(rows, decisions, summary):
    require(decisions == reviewed_section_decisions(), "Prepared section decisions differ from reviewed source approvals")
    before = {r["member_key"]: r for r in readcsv(BASE / "outputs/japan_master.csv")}
    seen = set()
    for d in decisions:
        key = d["member_key"]
        require(key not in seen, "Duplicate section decision")
        seen.add(key)
        row = next(r for r in rows if r["member_key"] == key)
        require(not before[key]["broad_section_supported"] and not row["broad_section_supported"], "Existing known section cannot be overwritten")
        row["broad_section_supported"] = d["new_broad_section"]
        row["section_evidence_status"] = "v10_direct_official_academy_directory_section_" + ("ii" if d["new_broad_section"] == "2" else "i")
        row["v10_previous_section_evidence_status"] = before[key]["section_evidence_status"]
        row["v10_section_source_url"] = d["source_url"]
        row["v10_section_source_sha256"] = d["source_sha256"]
        row["v10_section_source_locator"] = d["source_location"]
        row["v10_section_evidence_as_of_year"] = d["source_edition_year"]
        row["v10_section_temporal_scope_note"] = "Direct snapshot evidence only; not back-projected to the earlier Tokyo Academy election."
    science = [r for r in rows if r["broad_section_supported"] != "1"]
    queue = [r for r in science if r["dob_status"] != "body_day_no_known_conflict" or not r["broad_section_supported"]]
    summary.update(section_status_counts=dict(collections.Counter(r["section_evidence_status"] for r in rows)),
                   broad_section_ii_supported=sum(r["broad_section_supported"] == "2" for r in rows),
                   section_i_excluded=sum(r["broad_section_supported"] == "1" for r in rows),
                   section_unresolved=sum(not r["broad_section_supported"] for r in rows),
                   nonexcluded_science_and_unresolved_candidates=len(science),
                   nonexcluded_body_day_no_known_conflict=sum(r["dob_status"] == "body_day_no_known_conflict" for r in science),
                   section_ii_and_body_day_no_known_conflict=sum(r["broad_section_supported"] == "2" and r["dob_status"] == "body_day_no_known_conflict" for r in rows),
                   nonexcluded_dob_not_day_count=sum(r["dob_status"] != "body_day_no_known_conflict" for r in science),
                   next_action_queue_count=len(queue), new_section_decisions=len(decisions),
                   scope_note="Restored482-person working universe with seven exclusions; ten exact official1906 SectionII attestations are added only for currently unresolved identities. Remaining unresolved scope is explicit; no national cohort freeze or degree-rule extension.",
                   section_decision_source_scope="Exact root/independent-QA approved Academy directory snapshot only; no degree-rule extension, DOB/election change or subsection inference.")
    return queue


def reviewed_france_dob_quarantines(root=ROOT):
    approvals_path = root / "inputs/france_dob_conflict_approvals.json"
    approvals = js(approvals_path) if approvals_path.exists() else []
    require(isinstance(approvals, list), "France DOB approvals must be a list")
    require(len({x.get("candidate_group_id") for x in approvals}) == len(approvals), "Duplicate DOB quarantine approval")
    before = {r["candidate_group_id"]: r for r in readcsv(BASE / "outputs/france_master877.csv")}
    result = []
    for a in approvals:
        key = a.get("candidate_group_id")
        require(key in EXACT_FRANCE_DOB_QUARANTINE, "DOB quarantine is outside the exact reviewed identity")
        expected = EXACT_FRANCE_DOB_QUARANTINE[key]
        require(a.get("decision_type") == "quarantine_existing_dob_on_body_conflict"
                and a.get("root_approved") is True and a.get("independent_qa_passed") is True,
                "DOB quarantine needs root and independent QA approval")
        require(before[key]["identity_accepted"] == before[key]["dob_accepted"] == "1"
                and before[key]["accepted_dob_iso"] == expected["baseline_accepted_dob_iso"]
                and a.get("baseline_accepted_dob_iso") == expected["baseline_accepted_dob_iso"]
                and a.get("observed_competing_dates") == expected["observed_competing_dates"], "DOB quarantine previous value/date binding mismatch")
        def public_file(field):
            rel = a.get(field)
            require(isinstance(rel, str) and not Path(rel).is_absolute() and Path(rel).parts[0] == "source_audits"
                    and ".." not in Path(rel).parts, "DOB evidence path must stay in public audit scope")
            path = root / rel
            require(path.is_file(), "DOB evidence file is missing")
            return path
        claims_path = public_file("source_claims_file")
        qa_path = public_file("independent_qa_file")
        require(sha(claims_path) == a.get("source_claims_sha256") == expected["source_claims_sha256"], "DOB source-pair hash mismatch")
        require(sha(qa_path) == a.get("independent_qa_sha256"), "DOB independent QA hash mismatch")
        claims = js(claims_path)
        require(isinstance(claims, list) and len(claims) == 2 and {c.get("date_iso") for c in claims} == set(expected["observed_competing_dates"]), "DOB quarantine needs both observed competing body dates")
        for c in claims:
            require(c.get("candidate_group_id") == key and c.get("source_sha256") == expected["source_hashes"][c["date_iso"]]
                    and c.get("body_verified") is True and c.get("identity_body_supported") is True
                    and c.get("raw_birth_statement") and c.get("source_locator") and c.get("identity_note"), "DOB source identity/body/hash binding mismatch")
        qa = js(qa_path)
        require(qa.get("independent_qa_passed") is True and qa.get("candidate_group_id") == key
                and qa.get("source_claims_sha256") == sha(claims_path)
                and set(qa.get("source_dates_body_verified", [])) == set(expected["observed_competing_dates"]), "DOB independent QA reviewed a different source pair")
        require(a.get("body_sources_share_reference") is True and a.get("sources_not_assumed_independent") is True
                and qa.get("sources_not_assumed_independent") is True, "Related DOB sources cannot be counted as independent votes")
        result.append(dict(a, source_claims=claims, source_batch_version="v10", accepted_new_dob_iso=None))
    return result


def apply_france_dob_quarantines(rows, decisions):
    require(decisions == reviewed_france_dob_quarantines(), "Prepared DOB quarantines differ from reviewed source approvals")
    by = {r["candidate_group_id"]: r for r in rows}
    for d in decisions:
        row = by[d["candidate_group_id"]]
        require(row["dob_accepted"] == "1" and row["accepted_dob_iso"] == d["baseline_accepted_dob_iso"], "DOB quarantine may suspend only the exact old approval")
        row["v10_previous_accepted_dob_iso"] = row["accepted_dob_iso"]
        row["v10_previous_exact_dob_claims"] = row["exact_dob_claims"]
        row["exact_dob_claims"] = "|".join(sorted(set(row["exact_dob_claims"].split("|")) | set(d["observed_competing_dates"])))
        row["exact_dob_conflict"] = "1"
        row["dob_accepted"] = "0"
        row["accepted_dob_iso"] = ""
        row["v10_dob_review_status"] = "source_date_conflict_hold_no_day_selected"
        row["v10_dob_review_reason"] = d["reason"]
        row["v10_dob_conflict_source_urls"] = [c["source_url"] for c in d["source_claims"]]
        row["v10_dob_conflict_source_claims_file_sha256"] = d["source_claims_sha256"]
        row["completion_remaining_dimensions"] = "|".join(k for k in ["identity", "membership", "dob"] if row[k+"_accepted"] != "1")
        row["completion_status"] = "reviewed_with_holds"
        row["role_cutoff_and_dob_supported"] = False
    return rows


def prepare(root=ROOT):
    check_baseline(root)
    chosen = selections(root)
    config = js(root / "inputs/batch_selection.json")
    source = root / "source_batches"
    jp_cross = set(config.get("japan_cross_source_member_keys", []))
    require(not (jp_cross & chosen["japan"]), "Japan cross-source addenda must be counted outside fixed47")
    base_jp = {r["member_key"]: r for r in readcsv(BASE / "outputs/japan_master.csv")}
    require(jp_cross <= base_jp.keys(), "Unknown Japan cross-source identity")
    delta = []
    for rel in config["japan_claim_files"]:
        for i, row in enumerate(js(source / rel)):
            require(row["member_key"] in chosen["japan"] | jp_cross, "Unselected v10 Japan claim")
            delta.append(dict(row, source_batch_record=rel + ":" + str(i), source_batch_version="v10"))
    processed = set()
    all_jp_outcomes = set()
    for rel in config["japan_processed_files"]:
        dispositions = processing_dispositions(source / rel, "member_key")
        require(not (all_jp_outcomes & dispositions.keys()), "Duplicate Japan disposition across source files")
        all_jp_outcomes.update(dispositions)
        processed.update(k for k, status in dispositions.items() if completed_status(status))
    require(all_jp_outcomes == chosen["japan"], "All47 fixed Japan candidates need explicit outcomes, including not_searched")
    require(processed <= chosen["japan"], "Unknown reviewed Japan ID")
    source_processed = set(processed)
    dob_processed = {c["member_key"] for c in delta} & source_processed
    for rel in config["japan_processed_files"]:
        for row in processing_rows(source / rel):
            if any(str(row.get(k, "")).lower() == "true" for k in ["dob_search_performed", "dob_body_review_performed"]):
                dob_processed.add(row["member_key"])
    require(dob_processed <= source_processed, "DOB review needs a completed source outcome")
    processed = dob_processed
    new_holds = {}
    for rel in config["japan_hold_files"]:
        new_holds = merge_holds(new_holds, normalize_holds(js(source / rel)))
    require(set(new_holds) <= chosen["japan"] | jp_cross, "Unselected v10 Japan hold")
    section_decisions = reviewed_section_decisions(root)
    decisions = []
    for rel in config["france_decision_files"]:
        decisions.extend(dict(d, source_batch_file=rel, source_batch_version="v10") for d in js(source / rel))
    cross = set(config.get("france_cross_source_candidate_ids", []))
    require(not (cross & chosen["france"]), "Cross-source addendum must be counted outside fixed82")
    base_fr = {r["candidate_group_id"]: r for r in readcsv(BASE / "outputs/france_master877.csv")}
    for key in cross:
        require(key in base_fr and base_fr[key]["identity_accepted"] == base_fr[key]["dob_accepted"] == "1"
                and base_fr[key]["membership_accepted"] == "0" and base_fr[key]["election_date_conflict"] != "1",
                "Cross-source ID must be an unchanged identity/DOB-approved strict gap without conflict")
    require({d["candidate_group_id"] for d in decisions} <= chosen["france"] | cross, "Unselected v10 France decision")
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
    require(all_fr_outcomes == chosen["france"], "All82 fixed France candidates need explicit outcomes, including not_searched")
    require(fr_processed <= chosen["france"], "Unknown reviewed France ID")
    old_claims = js(BASE / "inputs/japan_claims.json")
    old_holds = inherited_holds()
    for release in calendar_routing_releases(delta, root=root):
        del old_holds[release["member_key"]]
    old_processed = js(BASE / "inputs/japan_processed_ids.json")
    return {"france_dob_conflict_decisions.json": reviewed_france_dob_quarantines(root),
            "japan_section_decisions.json": section_decisions,
            "japan_claims.json": old_claims + delta,
            "japan_delta_claims.json": delta,
            "japan_holds.json": merge_holds(old_holds, new_holds),
            "japan_delta_holds.json": new_holds,
            "japan_processed_ids.json": sorted(set(old_processed) | processed),
            "japan_delta_processed_ids.json": sorted(processed),
            "france_decisions.json": decisions,
            "france_processed_ids.json": sorted(fr_processed),
            "inherited_france_decisions.json": readcsv(BASE / "outputs/france_membership_decisions.csv")}


def previous_japan():
    # Recover the entire approved v9 ledger, including its original-V2 Terao
    # routing override and exact attributed-reproduction classification.
    return V9.japan(js(BASE / "inputs/japan_delta_claims.json"), js(BASE / "inputs/japan_delta_holds.json"),
                    js(BASE / "inputs/japan_delta_processed_ids.json"))


def inherited_holds(base_rows=None):
    """Seed effective status/reason from actual v9 state, retaining old overlay metadata."""
    overlays = copy.deepcopy(js(BASE / "inputs/japan_holds.json"))
    if base_rows is None:
        base_rows = previous_japan()[0]
    result = {}
    for row in base_rows:
        if row["dob_status"].endswith("_hold"):
            key = row["member_key"]
            old = overlays.get(key)
            value = copy.deepcopy(old) if old else {}
            if old and (old.get("status"), old.get("reason")) != (row["dob_status"], row.get("dob_hold_note", "")):
                value["inherited_predecessor_overlay_record"] = copy.deepcopy(old)
            value.update(status=row["dob_status"], reason=row.get("dob_hold_note", ""),
                         inherited_effective_baseline_study="studies/academy_fr_jp_completion_v9")
            result[key] = value
    return result


def calendar_routing_releases(delta, base_rows=None, base_ledger=None, root=ROOT):
    path = root / "inputs/calendar_routing_decisions.json"
    if not path.exists():
        return []
    decisions = js(path)
    require(isinstance(decisions, list), "Calendar routing decisions must be a list")
    require(not decisions, "No new v10 calendar routing source has root approval")
    return []


def secondary_reference(claim):
    return V3.secondary_reference(claim) or claim.get("source_tier") in REVIEWED_ATTRIBUTED_SECONDARY_TIERS


def classify_day_evidence(rows, ledger, summary):
    grouped = collections.defaultdict(list)
    for claim in ledger:
        if claim["precision"] == "day" and claim["calendar_comparable"]:
            grouped[claim["member_key"]].append(claim)
    for row in rows:
        days = grouped[row["member_key"]]
        row["has_institution_or_university_day_claim"] = any(not secondary_reference(c) for c in days)
        row["has_edited_reference_day_claim"] = any(V4.edited_reference(c) for c in days)
        row["has_other_attributed_secondary_day_claim"] = any(secondary_reference(c) and not V4.edited_reference(c) for c in days)
        row["day_evidence_tier"] = ("institution_or_university_supported" if row["has_institution_or_university_day_claim"] else "edited_reference_only" if row["has_edited_reference_day_claim"] else "other_attributed_secondary_only") if row["dob_status"] == "body_day_no_known_conflict" else "not_day_without_known_conflict"
    days = [r for r in rows if r["dob_status"] == "body_day_no_known_conflict"]
    summary.update(institutional_or_university_supported_day_no_known_conflict=sum(r["has_institution_or_university_day_claim"] for r in days),
                   edited_reference_only_day_no_known_conflict=sum(r["day_evidence_tier"] == "edited_reference_only" for r in days),
                   other_attributed_secondary_only_day_no_known_conflict=sum(r["day_evidence_tier"] == "other_attributed_secondary_only" for r in days),
                   secondary_only_day_no_known_conflict=sum(not r["has_institution_or_university_day_claim"] for r in days),
                   reviewed_v10_attributed_reproduction_tiers=sorted(REVIEWED_ATTRIBUTED_SECONDARY_TIERS),
                   source_tier_classification_note="Legacy classification plus the exact root-reviewed third-party university-publication reproduction tier; an attributed reproduction is not promoted to institution-hosted or edited-reference evidence.")


def japan(delta, new_holds, new_processed, section_decisions=None):
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
    routing_releases = calendar_routing_releases(delta, base_rows, base_ledger)
    cumulative_holds = merge_holds(inherited_holds(base_rows), new_holds)
    # Recompute from the approved structured v9 ledger, not V4's older input
    # overlays. This naturally retains all four exact prior routing outcomes
    # while still detecting any new comparable date disagreement.
    authority = {r["member_key"]: copy.deepcopy(r["ndl_authority_name_only_candidates"]) for r in base_rows}
    birth_processed = {r["member_key"] for r in base_rows if r["body_source_reviewed"]} | set(new_processed)
    rows, ledger, queue, recomputed = J.assemble(base_rows, base_ledger + delta, cumulative_holds, birth_processed, authority)
    for row in rows:
        row["body_source_reviewed"] = row.pop("institutionally_processed")
        if row["dob_status"] == "not_institutionally_processed":
            row["dob_status"] = "not_body_source_processed"
    recomputed["dob_status_counts"]["not_body_source_processed"] = recomputed["dob_status_counts"].pop("not_institutionally_processed", 0)
    recomputed["body_birth_people"] = recomputed.pop("institutional_body_birth_people")
    summary = copy.deepcopy(baseline)
    summary.update(recomputed)
    summary["source_tier_claim_counts"] = dict(collections.Counter(c["source_tier"] for c in ledger))
    summary["source_tier_note"] = "Institution/university/organization, edited-reference-only and other attributed-secondary day evidence remain separate."
    classify_day_evidence(rows, ledger, summary)
    for r in rows:
        for version in range(4, 10):
            field = f"v{version}_source_claim_added"
            r[field] = by[r["member_key"]][field]
        r["v10_source_claim_added"] = any(c["member_key"] == r["member_key"] for c in delta)
        require(r["broad_section_supported"] == by[r["member_key"]]["broad_section_supported"], "v10 cannot alter Japan scope")
        released = next((d for d in routing_releases if d["member_key"] == r["member_key"]), None)
        if released:
            require(r["dob_status"] == "body_day_no_known_conflict" and r["source_date_components_iso"] == released["source_date_components_iso"], "Exact routing release did not produce the source-supplied day")
        elif by[r["member_key"]]["dob_status"].endswith("_hold"):
            require(r["dob_status"].endswith("_hold"), "Inherited Japan hold released")
            require(HOLD_RANK[r["dob_status"]] >= HOLD_RANK[by[r["member_key"]]["dob_status"]], "Inherited Japan hold downgraded")
        old = by[r["member_key"]]
        if old["dob_status"] == r["dob_status"] == "body_day_no_known_conflict":
            require(r["source_date_components_iso"] == old["source_date_components_iso"], "Inherited selected Japan day changed")
    new_by_claim = {c["claim_id"]: c for c in ledger}
    require(all(new_by_claim.get(c["claim_id"]) == c for c in base_ledger), "Inherited claim or claim field changed")
    summary.update(baseline_day_no_known_conflict=baseline["body_day_no_known_conflict"],
                   day_status_net_change=summary["body_day_no_known_conflict"] - baseline["body_day_no_known_conflict"],
                   new_raw_source_claim_rows=len(delta), inherited_v9_raw_source_claim_rows=len(js(BASE / "inputs/japan_claims.json")),
                   newly_processed_v10_candidates=len(set(new_processed)), new_section_decisions=0,
                   approved_calendar_routing_releases=len(routing_releases), calendar_routing_release_sources=routing_releases,
                   calendar_routing_release_note="Exact root-approved source-supplied pairs only, including the separately approved original V2 calendar-routing overlay; no collector conversion, majority adjudication or generic hold release.")
    if section_decisions:
        queue = apply_section_decisions(rows, section_decisions, summary)
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
            and "relative" not in kind and "derived" not in kind and "arithmetic" not in kind
            and subject not in {"author", "notice_author", "speaker"}
            and e.get("event_is_as_of") is not True and e.get("event_belongs_to_author") is not True
            and e.get("event_year_is_derived") is not True and e.get("event_year_is_relative") is not True
            and e.get("event_year_is_calculated") is not True)


def validate_france_positive(d, before):
    require(d.get("previous_conflict_explicitly_resolved") is not True, "v10 cannot release inherited France election conflicts")
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


def france(decisions, dob_quarantines=None):
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
            r["v10_" + field] = r["v3_" + field] if r["candidate_group_id"] in changed else ""
            for version in ["v3_", "v4_", "v5_", "v6_", "v7_", "v8_", "v9_"]:
                r[version + field] = old.get(version + field, "")
        if r["candidate_group_id"] in changed:
            r["source_evidence_review_version"] = "France_v10_membership_continuation_20261030"
        else:
            r["membership_as_of_year"] = old.get("membership_as_of_year", "")
        require(old.get("election_date_conflict") != "1" or r["election_date_conflict"] == "1", "Inherited France conflict lost")
    # Retain the full predecessor decision ledger, including held source events, as immutable history.
    ledger = readcsv(BASE / "outputs/france_membership_decisions.csv") + delta_ledger
    summary.update(baseline_all_three_accepted=js(BASE / "outputs/summary.json")["france"]["all_three_accepted"],
                   all_three_net_change=len(accepted) - js(BASE / "outputs/summary.json")["france"]["all_three_accepted"],
                   inherited_v9_membership_decision_rows=len(ledger) - len(delta_ledger),
                   source_backed_decisions=len(decisions))
    if dob_quarantines:
        apply_france_dob_quarantines(rows, dob_quarantines)
        accepted = [r for r in rows if all(r[k+"_accepted"] == "1" for k in ["identity", "membership", "dob"])]
        gaps = [r for r in rows if r not in accepted]
        summary["current"]["dob_accepted"] = sum(r["dob_accepted"] == "1" for r in rows)
        summary["all_three_accepted"] = len(accepted)
        summary["all_three_remaining_gaps"] = len(gaps)
        summary["all_three_net_change"] = len(accepted) - js(BASE / "outputs/summary.json")["france"]["all_three_accepted"]
        summary["role_cutoff_and_dob_supported"] = sum(bool(r["role_cutoff_and_dob_supported"]) for r in rows)
    summary["known_exact_DOB_conflict_rows"] = sum(r["exact_dob_conflict"] == "1" for r in rows)
    summary["new_exact_DOB_conflict_quarantines"] = len(dob_quarantines or [])
    summary["DOB_quarantined_candidate_ids"] = [d["candidate_group_id"] for d in (dob_quarantines or [])]
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


def final_japan():
    """Reconstruct this study's complete approved final state for a successor."""
    return japan(js(ROOT / "inputs/japan_delta_claims.json"), js(ROOT / "inputs/japan_delta_holds.json"),
                 js(ROOT / "inputs/japan_delta_processed_ids.json"), js(ROOT / "inputs/japan_section_decisions.json"))


def assemble(output):
    require(not output.exists(), "Fresh output directory required")
    check_baseline()
    expected = prepare()
    for name, value in expected.items():
        require(js(ROOT / "inputs" / name) == value, "Prepared input changed: " + name)
    jm, jl, jq, j = final_japan()
    jp_cross = set(js(ROOT / "inputs/batch_selection.json").get("japan_cross_source_member_keys", []))
    j["cross_source_additional_member_keys"] = sorted({c["member_key"] for c in js(ROOT / "inputs/japan_delta_claims.json") if c["member_key"] in jp_cross})
    j["cross_source_additional_candidates"] = len(j["cross_source_additional_member_keys"])
    fm, fa, fg, fd, f = france(js(ROOT / "inputs/france_decisions.json"), js(ROOT / "inputs/france_dob_conflict_decisions.json"))
    f["newly_processed_v10_candidates"] = len(js(ROOT / "inputs/france_processed_ids.json"))
    cross = set(js(ROOT / "inputs/batch_selection.json").get("france_cross_source_candidate_ids", []))
    f["cross_source_additional_candidate_ids"] = sorted(d["candidate_group_id"] for d in js(ROOT / "inputs/france_decisions.json") if d["candidate_group_id"] in cross)
    f["cross_source_additional_candidates"] = len(f["cross_source_additional_candidate_ids"])
    output.mkdir(parents=True)
    for name, rows in [("japan_master.csv", jm), ("japan_birth_claims.csv", jl), ("japan_next_action_queue.csv", jq), ("france_master877.csv", fm), ("france_accepted_all_three.csv", fa), ("france_remaining_gaps.csv", fg), ("france_membership_decisions.csv", fd)]:
        J.write_csv(output / name, rows)
    scope_processing = processing_summary()
    j["newly_source_processed_v10_candidates"] = scope_processing["japan"]["actually_processed_dispositions"]
    j["newly_DOB_processed_v10_candidates"] = len(js(ROOT / "inputs/japan_delta_processed_ids.json"))
    j["processing_boundary_note"] = "Section-source queries/body reviews are not birthday searches. DOB processing IDs change only for explicit birth-source review, not scope-only activity."
    summary = dict(date="2026-10-30", baseline_commit=BASE_COMMIT, japan=j, france=f,
                   fixed_selection_counts={"japan": 47, "france": 82}, actual_processed_counts={"japan": scope_processing["japan"]["actually_processed_dispositions"], "france": len(js(ROOT / "inputs/france_processed_ids.json"))}, japan_dob_processed_count=len(js(ROOT / "inputs/japan_delta_processed_ids.json")), processing_status_breakdown=scope_processing, professor_collection="paused", fields_collection="preserved_parked", collection_complete=False,
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
    require(summary["fixed_selection_counts"] == {"japan": 47, "france": 82}, "Fixed selection coverage changed")
    require(summary["actual_processed_counts"] == {"japan": summary["processing_status_breakdown"]["japan"]["actually_processed_dispositions"], "france": len(js(ROOT / "inputs/france_processed_ids.json"))}, "Actual processing accounting mismatch")
    require(summary["japan_dob_processed_count"] == len(js(ROOT / "inputs/japan_delta_processed_ids.json")), "DOB processing accounting mismatch")
    require(summary["processing_status_breakdown"]["france"]["explicit_outcome_rows"] == 82, "France outcomes incomplete")
    require(summary["processing_status_breakdown"]["japan"]["explicit_outcome_rows"] == 47, "Japan outcomes incomplete")
    require(summary["processing_status_breakdown"]["japan"]["actually_processed_dispositions"] == summary["actual_processed_counts"]["japan"], "Unsearched Japan rows counted as processed")
    require(summary["processing_status_breakdown"]["france"]["actually_processed_dispositions"] == summary["actual_processed_counts"]["france"], "Unsearched France rows counted as processed")
    require(j["restored_candidate_universe"] == 482 and j["broad_section_ii_supported"] + j["section_i_excluded"] + j["section_unresolved"] == 482, "Japan scope accounting changed")
    require(j["new_section_decisions"] == len(js(ROOT / "inputs/japan_section_decisions.json")), "Section decision accounting mismatch")
    require(j["baseline_day_no_known_conflict"] == 368, "Wrong Japan baseline")
    require(j["body_day_no_known_conflict"] == j["institutional_or_university_supported_day_no_known_conflict"] + j["edited_reference_only_day_no_known_conflict"] + j["other_attributed_secondary_only_day_no_known_conflict"], "Source tier totals mismatch")
    require(j["nonexcluded_body_day_no_known_conflict"] + j["nonexcluded_dob_not_day_count"] == j["nonexcluded_science_and_unresolved_candidates"], "Japan DOB accounting mismatch")
    require((f["candidate_groups"], f["current"]["identity_accepted"], f["current"]["dob_accepted"]) == (877, 755, js(BASE / "outputs/summary.json")["france"]["current"]["dob_accepted"] - len(js(ROOT / "inputs/france_dob_conflict_decisions.json"))), "France nonmembership dimensions changed outside exact DOB quarantine")
    require(f["current"]["membership_accepted"] >= 394 and f["all_three_accepted"] >= 392, "France approvals lost")
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
    print(f"{len(actual)} pinned v10 files verified; v9 evidence and fixed processing scope preserved")


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
