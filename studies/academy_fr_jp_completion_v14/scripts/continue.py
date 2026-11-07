#!/usr/bin/env python3
"""Prepare, replay and verify exactly reviewed v14 evidence against v13."""
import argparse
import collections
import datetime
import re
from urllib.parse import urlparse, parse_qs
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT.parent / "academy_fr_jp_completion_v13"
BASE_COMMIT = "85697a4dea8792ee3170061dd14cef071b339d4d"
spec = importlib.util.spec_from_file_location("academy_v13", BASE / "scripts/continue.py")
V13 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(V13)
V4, V3, J = V13.V4, V13.V3, V13.J
V12 = V13.V12
ORDINARY_ROLES = V13.ORDINARY_ROLES
normalized_credit = V13.normalized_credit
reject_same_event_nonordinary_role_conflict = V13.reject_same_event_nonordinary_role_conflict
js, readcsv, require = V13.js, V13.readcsv, V13.require
HOLD_RANK = V13.HOLD_RANK
UNRESOLVED_BIRTHYEAR_STATUS = V13.UNRESOLVED_BIRTHYEAR_STATUS
CASE_FIELDS = V13.CASE_FIELDS
ARCHIVE_PARENT_METHOD_SHA256 = V13.ARCHIVE_PARENT_METHOD_SHA256
INHERITED_CSV_FILES = V13.INHERITED_CSV_FILES
# Source-origin validators remain available for read-only triage. None of the
# predecessor's acceptance maps or root approvals authorize a new v14 action.
source_capture_valid = V13.source_capture_valid
academy_original = V13.academy_original
cths_notice_component_origin = V13.cths_notice_component_origin
ordinary_subject_event = V13.ordinary_subject_event
processing_rows = V13.processing_rows
completed_status = V13.completed_status
normalize_holds = V13.normalize_holds
EXACT_BATCH_HANDOFFS = {'france_a': {'decisions_sha256': 'c6fde3839092eef76f2d4af520f465fba5214567c07d83218827fd246a293111',
              'independent_qa_file': 'source_audits/independent_qa_france_a.json',
              'independent_qa_sha256': '0ea80eea175ea77a89287bc44560bec02120876d4a22ca8aa29e9e000c724352',
              'worker_manifest_sha256': 'e93943844e2a32e224a5247045f66d51853517bd5821fd77212586bd83e30c6e'},
 'france_b': {'decisions_sha256': '37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570',
              'independent_qa_file': 'source_audits/france_b2_individual_case_independent_QA.json',
              'independent_qa_sha256': 'ec1835973e87a98a1d4b807f08d57425f2ce7e4303b455b26fbe4813b44522ed',
              'worker_manifest_sha256': '9250f89532cc921fe2d0509a0775ea29b7f18f45fb1dcbf02f7d8dc9fddf3cfb'}}
EXACT_MEMBERSHIP_ACCEPTANCES = {'PROFILE2_738d6d5c74a7a874': {'accepted_full_member_election_date': None,
                               'accepted_full_member_election_precision': 'year',
                               'accepted_full_member_election_year': 2024,
                               'candidate_group_id': 'PROFILE2_738d6d5c74a7a874',
                               'decisions_file': 'source_batches/france_a/decisions.json',
                               'decisions_sha256': 'c6fde3839092eef76f2d4af520f465fba5214567c07d83218827fd246a293111',
                               'identity_support_source_sha256s': ['88454da95d22aa070792f00cdf9743b66cd296be559015c0f9b82b09627ed213'],
                               'independent_qa_file': 'source_audits/independent_qa_france_a.json',
                               'independent_qa_passed': True,
                               'independent_qa_sha256': '0ea80eea175ea77a89287bc44560bec02120876d4a22ca8aa29e9e000c724352',
                               'root_approved': True,
                               'source_sha256s': ['49b7537f96b7d65290094113b013cb346ca5c3e1cc31d6fcf11e1edb7bf68fa6'],
                               'worker_manifest_sha256': 'e93943844e2a32e224a5247045f66d51853517bd5821fd77212586bd83e30c6e'}}
EXACT_INDIVIDUAL_CASE_ACCEPTANCES = {'CTHS_128379': {'candidate_group_id': 'CTHS_128379',
                 'decisions_file': 'source_batches/france_b/decisions.json',
                 'decisions_sha256': '37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570',
                 'independent_qa_file': 'source_audits/france_b2_individual_case_independent_QA.json',
                 'independent_qa_passed': True,
                 'independent_qa_sha256': 'ec1835973e87a98a1d4b807f08d57425f2ce7e4303b455b26fbe4813b44522ed',
                 'individual_case_proposals_sha256': '03b86ee8c9f88d020dd3085d98649e3a9a0556dc1eda8b20c98a727553415c0b',
                 'membership_decisions_sha256': '37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570',
                 'new_values': {'accepted_canonical_person_name': 'Hélène Bouchiat',
                                'accepted_dob_iso': '1958-05-08',
                                'dob_accepted': '1',
                                'identity_accepted': '1'},
                 'previous_values': {'accepted_canonical_person_name': '',
                                     'accepted_dob_iso': '',
                                     'dob_accepted': '0',
                                     'identity_accepted': '0'},
                 'root_approved': True,
                 'source_sha256s': ['7a290a6f3483b5120a0477ce39b10f8f3d9fb8607b09f2d840e7a655285c9f23',
                                    'c1641aa4c0b680bdd06702bbcff9ad72edbe63bb2734c2fabe6b66e7630b2e3a'],
                 'worker_manifest_sha256': '9250f89532cc921fe2d0509a0775ea29b7f18f45fb1dcbf02f7d8dc9fddf3cfb'},
 'PROFILE2_08407b6d0479b1d0': {'candidate_group_id': 'PROFILE2_08407b6d0479b1d0',
                               'decisions_file': 'source_batches/france_b/decisions.json',
                               'decisions_sha256': '37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570',
                               'independent_qa_file': 'source_audits/france_b2_individual_case_independent_QA.json',
                               'independent_qa_passed': True,
                               'independent_qa_sha256': 'ec1835973e87a98a1d4b807f08d57425f2ce7e4303b455b26fbe4813b44522ed',
                               'individual_case_proposals_sha256': '03b86ee8c9f88d020dd3085d98649e3a9a0556dc1eda8b20c98a727553415c0b',
                               'membership_decisions_sha256': '37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570',
                               'new_values': {'accepted_canonical_person_name': 'Nicole Le Douarin',
                                              'accepted_dob_iso': '1930-08-20',
                                              'dob_accepted': '1',
                                              'identity_accepted': '1'},
                               'previous_values': {'accepted_canonical_person_name': '',
                                                   'accepted_dob_iso': '',
                                                   'dob_accepted': '0',
                                                   'identity_accepted': '0'},
                               'root_approved': True,
                               'source_sha256s': ['100f475558746df381f38e55cd54f780801973912966acb1cd09c6cd6cc94309'],
                               'worker_manifest_sha256': '9250f89532cc921fe2d0509a0775ea29b7f18f45fb1dcbf02f7d8dc9fddf3cfb'}}


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inventory(root):
    return {str(p.relative_to(root)): sha(p) for p in sorted(root.rglob("*"))
            if p.is_file() and p != root / "MANIFEST.json" and "__pycache__" not in p.parts}


def safe_path(root, value, prefix):
    require(isinstance(value, str) and value, "Missing relative metadata path")
    rel = Path(value)
    require(not rel.is_absolute() and ".." not in rel.parts and rel.parts[0] == prefix,
            "Metadata path must stay in " + prefix)
    path = root / rel
    require(path.is_file() and path.resolve().is_relative_to((root / prefix).resolve()),
            "Missing or escaping metadata file: " + value)
    return path


def check_baseline(root=ROOT):
    pinned = js(root / "inputs/baseline_provenance.json")
    require(pinned["parent_git_commit"] == BASE_COMMIT, "Wrong v13 baseline commit")
    current = inventory(BASE)
    current["MANIFEST.json"] = sha(BASE / "MANIFEST.json")
    require(current == pinned["baseline_sha256"], "Changed v13 baseline inventory or bytes")
    require(inventory(BASE) == js(BASE / "MANIFEST.json")["files"], "v13 metadata inventory changed")
    for rel, expected in pinned.get("selection_sha256", {}).items():
        require(sha(root / rel) == expected, "Changed root-frozen v14 selection: " + rel)
    config = js(root / "inputs/selection_config.json")
    if config["selection_frozen"]:
        paths = {"inputs/selection_config.json"} | {entry["path"] for country in ("japan", "france") for entry in config.get(country, [])}
        require(set(pinned["selection_sha256"]) == paths, "Frozen selection is not fully pinned")
    V13.check_baseline()


def baseline_summary():
    return js(BASE / "outputs/summary.json")


def previous_japan():
    """Use the complete predecessor final state, including all old scope changes."""
    return V13.final_japan()


def selections(root=ROOT, allow_unfrozen_empty=False):
    config = js(root / "inputs/selection_config.json")
    result = {"japan": set(), "france": set()}
    require(type(config.get("selection_frozen")) is bool, "Selection freeze flag must be explicit")
    if not config["selection_frozen"]:
        require(allow_unfrozen_empty and all(not config.get(c) for c in result)
                and config.get("expected_totals") == {"japan": 0, "france": 0},
                "v14 selection is awaiting the root-reviewed queue freeze")
        return result
    baselines = {"japan": {r["member_key"] for r in previous_japan()[0]},
                 "france": {r["candidate_group_id"] for r in readcsv(BASE / "outputs/france_master877.csv")}}
    for country in result:
        field = "member_key" if country == "japan" else "candidate_group_id"
        for entry in config.get(country, []):
            rows = readcsv(safe_path(root, entry["path"], "selection_queues"))
            require(all(row.get(field) for row in rows), "Missing fixed selection identity")
            ids = {row[field] for row in rows}
            require(len(rows) == len(ids) == entry["count"], "Fixed selection cardinality mismatch")
            require(not ids & result[country], "Overlapping fixed queues")
            require(ids <= baselines[country], "Unknown fixed selection identity")
            result[country].update(ids)
        require(len(result[country]) == config["expected_totals"][country], "Fixed country selection total mismatch")
    return result


def processing_dispositions(path, field):
    result = {}
    for row in processing_rows(path):
        status = next((row[k] for k in ("status", "round_status", "outcome", "new_route_status", "processing_status", "review_status") if row.get(k)), "")
        require(isinstance(status, str) and status and row.get(field), "Missing processing identity/status: " + str(path))
        require(row[field] not in result, "Duplicate processing disposition: " + row[field])
        result[row[field]] = status
    return result


def reviewed_ids(path, field):
    return {key for key, status in processing_dispositions(path, field).items() if completed_status(status)}


def inherited_holds(base_rows=None):
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
                         inherited_effective_baseline_study="studies/academy_fr_jp_completion_v13")
            require(value["status"] in HOLD_RANK, "Inherited hold lost its status")
            result[key] = value
    return result


def birthyear_control(key):
    return V13.birthyear_control(key)


def block_unresolved_birthyear(row):
    require(birthyear_control(row["candidate_group_id"]) is None
            and not any(k.endswith("_dob_review_status") and v == UNRESOLVED_BIRTHYEAR_STATUS
                        for k, v in row.items()),
            "Unresolved actual-source birthyear conflict blocks new identity/DOB/membership approval")


def no_new_acceptance(records, label):
    require(isinstance(records, list), label + " must be a list")
    require(not records, "No new v14 " + label + " has exact root and independent source-QA approval")
    return []


def source_hashes(evidence):
    hashes = set()
    for source in evidence:
        if source.get("source_sha256"):
            hashes.add(source["source_sha256"])
        for component in source.get("source_capture_components", []):
            hashes.add(component.get("source_sha256"))
    require(all(re.fullmatch(r"[0-9a-f]{64}", str(h)) for h in hashes), "Malformed source hash")
    return sorted(hashes)

def reviewed_handoff(batch, root=ROOT):
    expected = EXACT_BATCH_HANDOFFS.get(batch)
    require(expected is not None, "Source handoff awaits exact root approval: " + batch)
    folder = root / "source_batches" / batch
    manifest = folder / "MANIFEST.json"
    require(sha(manifest) == expected["worker_manifest_sha256"], "Worker manifest differs from exact root scope")
    declared = js(manifest)["files"]
    if isinstance(declared, list):
        require(len({f["path"] for f in declared}) == len(declared), "Duplicate worker manifest path")
        declared = {f["path"]: f["sha256"] for f in declared}
    actual = {str(p.relative_to(folder)): sha(p) for p in folder.iterdir() if p.is_file() and p.name != "MANIFEST.json"}
    require(actual == declared, "Source handoff inventory/hash mismatch: " + batch)
    require(sha(folder / "decisions.json") == expected["decisions_sha256"], "Source decisions differ from exact root scope")
    qa_path = safe_path(root, expected["independent_qa_file"], "source_audits")
    require(sha(qa_path) == expected["independent_qa_sha256"], "Source-batch independent QA hash mismatch")
    qa = js(qa_path)
    require(qa.get("independent_qa_passed") is True and qa.get("worker_manifest_sha256") == sha(manifest)
            and qa.get("decisions_sha256") == sha(folder / "decisions.json"), "Source-batch QA reviewed a different final handoff")
    return folder

def approved_binding(approval, expected, decision_path, root=ROOT):
    require(expected is not None and approval == expected, "Acceptance differs from exact root-approved source scope")
    require(approval.get("root_approved") is True and approval.get("independent_qa_passed") is True,
            "Acceptance awaits root and independent actual-source QA")
    require(approval.get("decisions_file") == str(decision_path.relative_to(root))
            and sha(decision_path) == approval.get("decisions_sha256")
            and sha(decision_path.parent / "MANIFEST.json") == approval.get("worker_manifest_sha256"),
            "Acceptance decision/worker-manifest binding mismatch")
    qa_path = safe_path(root, approval["independent_qa_file"], "source_audits")
    require(sha(qa_path) == approval.get("independent_qa_sha256"), "Independent QA hash mismatch")
    qa = js(qa_path)
    require(qa.get("independent_qa_passed") is True
            and qa.get("decisions_sha256") == sha(decision_path)
            and qa.get("worker_manifest_sha256") == sha(decision_path.parent / "MANIFEST.json"),
            "Independent QA reviewed a different final source handoff")
    return qa

def inherited_france_role_evidence():
    grouped = collections.defaultdict(list)
    for record in readcsv(BASE / "outputs/france_membership_decisions.csv"):
        evidence = record.get("evidence", [])
        if isinstance(evidence, str):
            evidence = json.loads(evidence) if evidence else []
        if isinstance(evidence, list):
            grouped[record["candidate_group_id"]].extend(e for e in evidence if isinstance(e, dict))
    return grouped

def validate_france_positive(d, before, prior_evidence=None):
    require(d.get("previous_conflict_explicitly_resolved") is not True, "v13 cannot release inherited France election conflicts")
    if V3.flag(d["membership_accepted"]) != "1":
        return
    block_unresolved_birthyear(before)
    require(before.get("election_date_conflict") != "1", "Inherited France conflict must stay held")
    require(d["candidate_group_id"] not in V12.EXACT_UNRESOLVED_ROLE_CONTROLS,
            "Exact unresolved source-role control cannot be promoted by a generic member row")
    precision = d.get("accepted_full_member_election_precision")
    accepted_date, accepted_year = d.get("accepted_full_member_election_date"), d.get("accepted_full_member_election_year")
    if precision == "day":
        day = datetime.date.fromisoformat(accepted_date)
        require(accepted_year in (None, "", day.year, str(day.year)), "Accepted day/year disagree")
        year = day.year
    else:
        require(precision == "year" and type(accepted_year) is int and not accepted_date, "Exact year precision required")
        year = accepted_year
    prior = inherited_france_role_evidence().get(d["candidate_group_id"], []) if prior_evidence is None else prior_evidence
    reject_same_event_nonordinary_role_conflict(d, year, accepted_date, prior)
    matching = []
    for e in d.get("evidence", []):
        parsed = urlparse(e.get("source_url", ""))
        if parsed.hostname in {"cths.fr", "www.cths.fr"} and parse_qs(parsed.query).get("id") != [d["candidate_group_id"].removeprefix("CTHS_")]:
            continue
        if not (source_capture_valid(e) and ordinary_subject_event(e) and e.get("role") in ORDINARY_ROLES
                and e.get("source_role") in V12.ACADEMY_SOURCE_ROLES
                and e.get("quote") and e.get("identity_note") and academy_original(e)):
            continue
        event_date, event_year = e.get("event_date"), e.get("event_year")
        same = (e.get("event_precision") == "day" and event_date == accepted_date and event_year in (None, "", year, str(year))) if precision == "day" else (e.get("event_precision") in {"day", "year"} and event_year in (year, str(year)))
        if same and event_date:
            same = datetime.date.fromisoformat(event_date).year == year
        if same:
            matching.append(e)
    require(matching, "Strict France acceptance needs a matching Academy-original ordinary-full-member event")


def reviewed_individual_case_decisions(root=ROOT):
    path = root / "source_batches/france_b/individual_case_proposals.json"
    proposals = js(path) if path.exists() else []
    require(isinstance(proposals, list) and len({p.get("candidate_group_id") for p in proposals}) == len(proposals),
            "Duplicate or malformed individual-case proposals")
    by_proposal = {p["candidate_group_id"]: p for p in proposals}
    approvals = js(root / "inputs/france_individual_case_approvals.json")
    require(isinstance(approvals, list) and len({a.get("candidate_group_id") for a in approvals}) == len(approvals),
            "Duplicate or malformed individual-case approvals")
    before = {r["candidate_group_id"]: r for r in readcsv(BASE / "outputs/france_master877.csv")}
    eligible_path = root / "selection_queues/france_b.csv"
    eligible = {r["candidate_group_id"] for r in readcsv(eligible_path)} if eligible_path.exists() else set()
    result = []
    for a in approvals:
        key = a.get("candidate_group_id")
        require(key in before, "Unknown individual-case identity")
        old = before[key]
        block_unresolved_birthyear(old)
        require(key in eligible and key in by_proposal and key in EXACT_INDIVIDUAL_CASE_ACCEPTANCES,
                "Individual-case approval is outside exact reviewed B identities")
        proposal, expected = by_proposal[key], EXACT_INDIVIDUAL_CASE_ACCEPTANCES[key]
        qa = approved_binding(a, expected, path.parent / "decisions.json", root)
        previous = {k: old[k] for k in CASE_FIELDS}
        changes = proposal.get("new_values")
        require(proposal.get("decision_type") == "accept_individual_identity_dob" and proposal.get("name") == old["display_name"],
                "Individual-case preserved identity mismatch")
        require(proposal.get("previous_values") == previous == a.get("previous_values") and isinstance(changes, dict)
                and changes and set(changes) <= CASE_FIELDS and changes == a.get("new_values"),
                "Individual-case old/new value binding mismatch")
        require(proposal.get("prior_exact_dob_claims") == old["exact_dob_claims"] and old["exact_dob_conflict"] != "1",
                "Individual case cannot bypass an inherited birthday conflict")
        for flag in ("identity_accepted", "dob_accepted"):
            if flag in changes:
                require(old[flag] == "0" and changes[flag] == "1", "Individual case may approve only an old zero flag")
        if "accepted_canonical_person_name" in changes:
            require(changes.get("identity_accepted") == "1" and changes["accepted_canonical_person_name"],
                    "Canonical identity needs explicit new identity approval")
        require(changes.get("identity_accepted", old["identity_accepted"]) == "1" and proposal.get("identity_bridge"),
                "Individual case needs a supported unique identity")
        require(all(proposal.get("identity_checks", {}).get(k) is True for k in
                    ("unique_preserved_group_match", "no_unresolved_alias_or_profile_collision", "same_subject_name_dob_career_verified")),
                "Individual case has an unresolved identity/alias bridge")
        singleton = old["exact_dob_claims"]
        if "accepted_dob_iso" in changes or "dob_accepted" in changes:
            require(changes.get("dob_accepted") == "1" and changes.get("accepted_dob_iso") == singleton
                    and re.fullmatch(r"\d{4}-\d{2}-\d{2}", singleton)
                    and proposal.get("dob_matches_singleton_prior_raw_claim") is True,
                    "DOB case must approve only its singleton unchanged prior raw claim")
            datetime.date.fromisoformat(singleton)
        sources = proposal.get("source_evidence")
        require(isinstance(sources, list) and sources, "Individual case needs actual source bodies")
        for e in sources:
            require(source_capture_valid(e) and e.get("identity_body_supported") is True
                    and e.get("source_locator") and e.get("observed_subject_name") and e.get("identity_support")
                    and e.get("source_role") and e.get("source_independence_group"),
                    "Individual-case actual-source metadata is incomplete")
        hashes = source_hashes(sources)
        require(any(e.get("observed_dob_iso") == changes.get("accepted_dob_iso") for e in sources),
                "Approved birthday is absent from actual case-source readings")
        require(sha(path) == a.get("individual_case_proposals_sha256")
                and hashes == a.get("source_sha256s") and qa.get("individual_case_proposals_sha256") == sha(path),
                "Individual-case proposal/source hashes differ from exact approval")
        checks = [c for c in qa.get("case_checks", []) if c.get("candidate_group_id") == key]
        required = ("previous_values_match_baseline", "identity_source_body_bridge_passed", "uniqueness_and_alias_collision_checks_passed",
                    "all_actual_sources_rehashed_and_body_read", "no_old_source_flags_changed", "singleton_prior_DOB_claim_passed", "membership_fields_and_warnings_unchanged")
        require(len(checks) == 1 and checks[0].get("source_sha256s") == hashes
                and all(checks[0].get(k) is True for k in required), "Independent QA did not approve this exact unique case")
        result.append(dict(proposal, root_approved=True, independent_qa_passed=True,
                           root_approval_record=copy.deepcopy(a), source_batch_version="v14"))
    return result

def reviewed_membership_decisions(root=ROOT):
    config = js(root / "inputs/batch_selection.json")
    approvals = js(root / "inputs/france_membership_approvals.json")
    require(isinstance(approvals, list) and len({a.get("candidate_group_id") for a in approvals}) == len(approvals),
            "Duplicate or malformed membership approvals")
    approval_by = {a["candidate_group_id"]: a for a in approvals}
    require(js(root / "inputs/cths_component_approvals.json") == [a for a in approvals if "cths_parent_notice_sha256" in a],
            "Component approvals differ from exact membership source-pair bindings")
    result, positive_ids, seen = [], set(), set()
    for rel in config["france_decision_files"]:
        path = safe_path(root, "source_batches/" + rel, "source_batches")
        reviewed_handoff(path.parent.name, root)
        decisions = js(path)
        require(isinstance(decisions, list), "Membership source decisions must be a list")
        for raw in decisions:
            key = raw.get("candidate_group_id")
            require(key and key not in seen, "Unknown or duplicate France source decision")
            seen.add(key)
            if V3.flag(raw["membership_accepted"]) == "1":
                positive_ids.add(key)
                a = approval_by.get(key)
                require(a is not None, "Positive membership awaits exact root and independent source-QA approval")
                qa = approved_binding(a, EXACT_MEMBERSHIP_ACCEPTANCES.get(key), path, root)
                require(all(raw.get(k) == a.get(k) for k in ("accepted_full_member_election_date", "accepted_full_member_election_year", "accepted_full_member_election_precision")),
                        "Membership event differs from exact root approval")
                hashes = source_hashes(raw.get("evidence", []))
                require(hashes == a.get("source_sha256s"), "Membership actual-source hashes differ from root approval")
                checks = [c for c in qa.get("decision_checks", []) if c.get("candidate_group_id") == key]
                require(len(checks) == 1 and checks[0].get("source_sha256s") == hashes
                        and checks[0].get("ordinary_role_direct_start_passed") is True
                        and (checks[0].get("identity_DOB_unchanged") is True or checks[0].get("identity_DOB_case_condition_required") is True),
                        "Independent QA did not approve this exact ordinary subject event")
                identity_hashes = sorted({e["identity_support_source_sha256"] for e in raw.get("evidence", []) if e.get("identity_support_source_sha256")})
                if identity_hashes:
                    require(a.get("identity_support_source_sha256s") == identity_hashes
                            and checks[0].get("identity_support_source_sha256s") == identity_hashes,
                            "Membership identity-support source differs from root and independent QA binding")
                for evidence in raw.get("evidence", []):
                    if evidence.get("http_status") is None:
                        require(checks[0].get("archived_parent_provenance_passed") is True
                                and checks[0].get("unknown_original_time_and_status_preserved") is True,
                                "Archived original lacks independent unknown-envelope provenance QA")
                    if evidence.get("cths_notice_component_bundle_verified") is True:
                        fields = ("cths_parent_notice_sha256", "cths_expanded_biography_sha256")
                        require(all(evidence.get(k) == a.get(k) == checks[0].get(k) for k in fields)
                                and checks[0].get("independent_component_bundle_passed") is True,
                                "Component source-pair QA differs from exact approval")
                        if evidence.get("cths_archive_parent_provenance_branch") is True:
                            provenance = evidence.get("cths_parent_notice_archive_provenance", {})
                            require(checks[0].get("archived_parent_provenance_passed") is True
                                    and checks[0].get("unknown_original_time_and_status_preserved") is True
                                    and checks[0].get("cths_archive_parent_method_contract_sha256") == ARCHIVE_PARENT_METHOD_SHA256
                                    and all(checks[0].get(k) == provenance.get(k) for k in ("archive_sha256", "archive_member", "archive_member_sha256")),
                                    "Archived parent component lacks exact independent provenance QA")
                    if evidence.get("shared_capture_owner"):
                        for field in ("shared_capture_request_manifest", "shared_capture_source_manifest"):
                            shared = safe_path(root, evidence[field], "source_batches")
                            require(sha(shared) == evidence[field + "_sha256"], "Cross-batch source-sharing metadata changed")
                        shared_manifest = root / "source_batches" / evidence["shared_capture_owner"] / "MANIFEST.json"
                        require(sha(shared_manifest) == evidence.get("shared_capture_worker_manifest_sha256"),
                                "Cross-batch source-sharing worker manifest changed")
            result.append(dict(raw, source_batch_file=rel, source_batch_version="v13"))
    require(set(approval_by) == positive_ids, "Membership approval identities differ from actual positive source handoffs")
    return result

def reviewed_section_decisions(root=ROOT):
    return no_new_acceptance(js(root / "inputs/japan_section_approvals.json"), "Japan section acceptance")


def reviewed_france_dob_quarantines(root=ROOT):
    return no_new_acceptance(js(root / "inputs/france_dob_conflict_approvals.json"), "DOB quarantine")


def calendar_routing_releases(root=ROOT):
    return no_new_acceptance(js(root / "inputs/calendar_routing_decisions.json"), "calendar routing release")


def japan(delta, new_holds, new_processed, section_decisions=None):
    require(isinstance(delta, list) and not delta, "New raw DOB claims are not authorized in v14")
    require(isinstance(new_holds, dict) and not new_holds, "New Japan holds await exact root-reviewed source scope")
    require(isinstance(new_processed, list) and not new_processed, "Japan hard routes remain parked")
    no_new_acceptance(section_decisions if section_decisions is not None else [], "Japan section acceptance")
    rows, ledger, queue, old = previous_japan()
    summary = copy.deepcopy(old)
    summary.update(baseline_day_no_known_conflict=old["body_day_no_known_conflict"],
                   day_status_net_change=0, new_raw_source_claim_rows=0,
                   inherited_v13_raw_source_claim_rows=len(ledger), newly_processed_v14_candidates=0,
                   new_section_decisions=0, approved_calendar_routing_releases=0,
                   calendar_routing_release_sources=[], newly_source_processed_v14_candidates=0,
                   newly_DOB_processed_v14_candidates=0)
    return copy.deepcopy(rows), copy.deepcopy(ledger), copy.deepcopy(queue), summary


def final_japan():
    """Stable successor API for the complete approved v14 Japan state."""
    return japan(js(ROOT / "inputs/japan_delta_claims.json"), js(ROOT / "inputs/japan_delta_holds.json"),
                 js(ROOT / "inputs/japan_delta_processed_ids.json"), js(ROOT / "inputs/japan_section_decisions.json"))


def france_case_adjudications(individual_cases=None):
    additions = individual_cases if individual_cases is not None else []
    require(isinstance(additions, list), "Individual-case decisions must be a list")
    if additions:
        require(additions == reviewed_individual_case_decisions(), "Prepared cases differ from exact reviewed source approvals")
    return readcsv(BASE / "outputs/france_case_adjudications.csv") + copy.deepcopy(additions)

def france(decisions, dob_quarantines=None, individual_cases=None):
    require(isinstance(decisions, list), "France decisions must be a list")
    no_new_acceptance(dob_quarantines if dob_quarantines is not None else [], "DOB quarantine")
    individual_cases = individual_cases if individual_cases is not None else []
    require(isinstance(individual_cases, list), "Individual-case decisions must be a list")
    rows = readcsv(BASE / "outputs/france_master877.csv")
    before = copy.deepcopy(rows)
    by = {r["candidate_group_id"]: r for r in rows}
    for decision in decisions + individual_cases:
        require(decision.get("candidate_group_id") in by, "Unknown France identity")
        block_unresolved_birthyear(by[decision["candidate_group_id"]])
    if individual_cases:
        require(individual_cases == reviewed_individual_case_decisions(), "Prepared cases differ from exact reviewed source approvals")
    for d in individual_cases:
        row = by[d["candidate_group_id"]]
        require({k: row[k] for k in CASE_FIELDS} == d["previous_values"], "Individual case previous state changed")
        row.update(d["new_values"])
        row.update(v14_previous_individual_case_values=copy.deepcopy(d["previous_values"]),
                   v14_individual_case_status="root_and_independent_source_review_approved", v14_individual_case_reason=d["reason"],
                   v14_individual_case_source_sha256s=source_hashes(d["source_evidence"]))
        row["completion_remaining_dimensions"] = "|".join(k for k in ("identity", "membership", "dob") if row[k + "_accepted"] != "1")
        row["completion_status"] = "accepted_all_three" if not row["completion_remaining_dimensions"] else "reviewed_with_holds"
    if decisions:
        require(decisions == reviewed_membership_decisions(), "Prepared memberships differ from exact reviewed source approvals")
    birthday_only = {r["candidate_group_id"] for r in readcsv(ROOT / "selection_queues/france_b.csv")}
    require(not {d["candidate_group_id"] for d in decisions} & birthday_only,
            "Birthday-only B scope cannot change any membership flag or warning")
    prior_roles = inherited_france_role_evidence()
    for d in decisions:
        validate_france_positive(d, by[d["candidate_group_id"]], prior_roles.get(d["candidate_group_id"], []))
    delta_ledger = []
    if decisions:
        reduced, _, _, delta_ledger, _ = V3.france(rows, decisions)
        reduced_by = {r["candidate_group_id"]: r for r in reduced}
        mutable = ("membership_accepted", "accepted_full_member_election_date", "accepted_full_member_election_year",
                   "accepted_election_precision", "membership_role_supported", "election_cutoff_stable", "election_date_conflict",
                   "membership_as_of_year", "completion_remaining_dimensions", "completion_status", "role_cutoff_and_dob_supported")
        for d in decisions:
            key = d["candidate_group_id"]
            row, new = by[key], reduced_by[key]
            row.update({field: new[field] for field in mutable})
            for field in ("membership_decision_status", "membership_review_reason", "evidence_urls", "election_source_conflict_retained"):
                row["v14_" + field] = new["v3_" + field]
            row["source_evidence_review_version"] = "France_v14_membership_continuation_20261101"
    changed_cases = {d["candidate_group_id"] for d in individual_cases}
    changed_memberships = {d["candidate_group_id"] for d in decisions}
    mutable_case = CASE_FIELDS | {"completion_remaining_dimensions", "completion_status"}
    mutable_membership = {"membership_accepted", "accepted_full_member_election_date", "accepted_full_member_election_year",
                          "accepted_election_precision", "membership_role_supported", "election_cutoff_stable", "election_date_conflict",
                          "membership_as_of_year", "completion_remaining_dimensions", "completion_status", "role_cutoff_and_dob_supported",
                          "source_evidence_review_version"}
    for old, after in zip(before, rows):
        key = old["candidate_group_id"]
        allowed = (mutable_case if key in changed_cases else set()) | (mutable_membership if key in changed_memberships else set())
        require(all(after[k] == value for k, value in old.items() if k not in allowed), "Inherited France field changed outside exact reviewed scope")
        for dimension in ("identity", "dob", "membership"):
            flag = dimension + "_accepted"
            require(old[flag] != "1" or after[flag] == "1", "An inherited France approval was lost")
        if old["dob_accepted"] == "1":
            require(after["accepted_dob_iso"] == old["accepted_dob_iso"], "An inherited accepted DOB changed")
        if old["identity_accepted"] == "1":
            require(after["accepted_canonical_person_name"] == old["accepted_canonical_person_name"], "An inherited accepted identity changed")
        if old["membership_accepted"] == "1":
            require(all(after[k] == old[k] for k in ("accepted_full_member_election_date", "accepted_full_member_election_year", "accepted_election_precision")),
                    "An inherited ordinary membership date changed")
        require(old["election_date_conflict"] != "1" or after["election_date_conflict"] == "1", "Inherited chronology hold was lost")
    accepted = [r for r in rows if all(r[k + "_accepted"] == "1" for k in ("identity", "dob", "membership"))]
    gaps = [r for r in rows if r not in accepted]
    old_ledger = readcsv(BASE / "outputs/france_membership_decisions.csv")
    ledger = old_ledger + delta_ledger
    summary = copy.deepcopy(baseline_summary()["france"])
    baseline = {k + "_accepted": sum(r[k + "_accepted"] == "1" for r in before) for k in ("identity", "membership", "dob")}
    current = {k + "_accepted": sum(r[k + "_accepted"] == "1" for r in rows) for k in ("identity", "membership", "dob")}
    summary.update(candidate_groups=len(rows), baseline=baseline, current=current,
                   new_strict_memberships=current["membership_accepted"] - baseline["membership_accepted"],
                   all_three_accepted=len(accepted), all_three_remaining_gaps=len(gaps),
                   baseline_all_three_accepted=baseline_summary()["france"]["all_three_accepted"],
                   all_three_net_change=len(accepted) - baseline_summary()["france"]["all_three_accepted"],
                   inherited_v13_membership_decision_rows=len(old_ledger),
                   inherited_v13_case_adjudication_rows=len(readcsv(BASE / "outputs/france_case_adjudications.csv")),
                   membership_cases_reviewed=len(decisions), source_backed_decisions=len(decisions),
                   new_exact_DOB_conflict_quarantines=0, DOB_quarantined_candidate_ids=[],
                   new_individual_case_adjudications=len(individual_cases),
                   identity_approval_net_change=current["identity_accepted"] - baseline["identity_accepted"],
                   dob_approval_net_change=current["dob_accepted"] - baseline["dob_accepted"],
                   unresolved_birthyear_control_rows=sum(r.get("v12_dob_review_status") == UNRESOLVED_BIRTHYEAR_STATUS for r in rows),
                   known_election_conflict_rows=sum(r["election_date_conflict"] == "1" for r in rows),
                   known_exact_DOB_conflict_rows=sum(r["exact_dob_conflict"] == "1" for r in rows),
                   role_supported=sum(r["membership_role_supported"] == "1" for r in rows),
                   cutoff_stable=sum(r["election_cutoff_stable"] == "1" for r in rows),
                   role_cutoff_and_dob_supported=sum(str(r["role_cutoff_and_dob_supported"]) == "True" for r in rows))
    return rows, accepted, gaps, ledger, summary

def prepare(root=ROOT):
    check_baseline(root)
    chosen = selections(root, allow_unfrozen_empty=True)
    config = js(root / "inputs/batch_selection.json")
    require(js(root / "inputs/batch_source_approvals.json") == EXACT_BATCH_HANDOFFS,
            "Source-batch approvals differ from exact root scope")
    require(all(not config.get(field) for field in ("japan_claim_files", "japan_processed_files", "japan_hold_files",
                "reviewed_source_tiers", "france_cross_source_candidate_ids", "japan_cross_source_member_keys",
                "japan_dob_search_member_keys", "web_body_capture_exceptions")), "Japan hard routes and unapproved addenda remain parked")
    require(not chosen["japan"], "No Japan source activity is authorized")
    require(config.get("france_individual_case_proposal_files", []) in ([], ["france_b/individual_case_proposals.json"]),
            "Existing-singleton cases are bounded to the B2 handoff")
    calendar_routing_releases(root)
    case_decisions = reviewed_individual_case_decisions(root)
    decisions = reviewed_membership_decisions(root)
    require({d["candidate_group_id"] for d in decisions} <= chosen["france"], "Unselected France membership decision")
    require({d["candidate_group_id"] for d in case_decisions} <= chosen["france"], "Unselected France individual case")
    all_outcomes, processed = {}, set()
    for rel in config["france_processed_files"]:
        path = safe_path(root, "source_batches/" + rel, "source_batches")
        reviewed_handoff(path.parent.name, root)
        dispositions = processing_dispositions(path, "candidate_group_id")
        require(not all_outcomes.keys() & dispositions.keys(), "Duplicate France disposition across source files")
        all_outcomes.update(dispositions)
        processed.update(k for k, status in dispositions.items() if completed_status(status))
    require(set(all_outcomes) == chosen["france"], "All fixed France candidates need explicit outcomes, including not_searched")
    rows, claims, _, _ = previous_japan()
    return {
        "france_individual_case_decisions.json": case_decisions,
        "france_dob_conflict_decisions.json": reviewed_france_dob_quarantines(root),
        "japan_section_decisions.json": reviewed_section_decisions(root),
        "japan_claims.json": claims,
        "japan_delta_claims.json": [],
        "japan_holds.json": inherited_holds(rows),
        "japan_delta_holds.json": {},
        "japan_processed_ids.json": js(BASE / "inputs/japan_processed_ids.json"),
        "japan_delta_processed_ids.json": [],
        "france_decisions.json": decisions,
        "france_processed_ids.json": sorted(processed),
        "inherited_france_decisions.json": readcsv(BASE / "outputs/france_membership_decisions.csv"),
        "inherited_france_case_adjudications.json": readcsv(BASE / "outputs/france_case_adjudications.csv"),
    }

def ledger_copy(name):
    return readcsv(BASE / "outputs" / name)


def processing_summary(root=ROOT):
    config = js(root / "inputs/batch_selection.json")
    result = {}
    for country, field in (("japan", "member_key"), ("france", "candidate_group_id")):
        by_file, activity, outcomes = {}, {}, {}
        total = collections.Counter()
        for rel in config[country + "_processed_files"]:
            path = root / "source_batches" / rel
            dispositions = processing_dispositions(path, field)
            require(not outcomes.keys() & dispositions.keys(), "Duplicate source processing outcome")
            counts = collections.Counter(dispositions.values())
            by_file[rel] = dict(counts); total.update(counts); outcomes.update(dispositions)
            summary_path = path.parent / "summary.json"
            if summary_path.exists():
                activity[str(summary_path.relative_to(root))] = {k: v for k, v in js(summary_path).items() if type(v) in (int, float)}
        result[country] = dict(status_counts=dict(total), by_file=by_file, explicit_outcome_rows=len(outcomes),
                               actually_processed_dispositions=sum(completed_status(s) for s in outcomes.values()),
                               not_processed_ids=sorted(k for k, s in outcomes.items() if not completed_status(s)),
                               collector_reported_numeric_activity=activity,
                               note="Fixed selection, source attempts, own-subject body reviews, individual queries and approvals are distinct. B2 is identity/DOB-only and cannot change membership warnings. Read-only bulk-route triage adds no selected or processed cases.")
    return result

def verify_baseline_inheritance():
    check_baseline()
    old_japan, old_claims, old_queue, _ = previous_japan()
    rows, claims, queue, summary = japan([], {}, [])
    require(rows == old_japan and claims == old_claims and queue == old_queue,
            "Empty delta changed an inherited Japan field, claim or queue")
    old_france = readcsv(BASE / "outputs/france_master877.csv")
    fm, fa, fg, fd, f = france([])
    require(fm == old_france, "Empty delta changed an inherited France field")
    require(fd == readcsv(BASE / "outputs/france_membership_decisions.csv"), "Inherited membership history changed")
    require(france_case_adjudications() == readcsv(BASE / "outputs/france_case_adjudications.csv"),
            "Inherited individual-case history changed")
    for current, filename in [(fa, "france_accepted_all_three.csv"), (fg, "france_remaining_gaps.csv")]:
        old = readcsv(BASE / "outputs" / filename)
        require(len(current) == len(old) and all({k: after[k] for k in before} == before
                for before, after in zip(old, current)), "France derived tables changed")
    controls = [r for r in fm if r.get("v12_dob_review_status") == UNRESOLVED_BIRTHYEAR_STATUS]
    for row in controls:
        require(all(row[k + "_accepted"] == "0" for k in ("identity", "dob", "membership")),
                "Unresolved birthday control was promoted")
        control = birthyear_control(row["candidate_group_id"])
        require(control is not None, "Inherited machine-readable birthyear control lost its pinned source metadata")
    return dict(baseline_commit=BASE_COMMIT, verification_scope="empty_delta_baseline",
                inherited_japan_rows=len(rows), inherited_japan_claims=len(claims),
                inherited_japan_day_statuses=summary["body_day_no_known_conflict"],
                inherited_japan_effective_holds=len(inherited_holds(rows)),
                inherited_japan_section_ii=summary["broad_section_ii_supported"],
                inherited_japan_section_i=summary["section_i_excluded"],
                inherited_japan_unresolved=summary["section_unresolved"],
                inherited_japan_DOB_pending=summary["nonexcluded_dob_not_day_count"],
                inherited_japan_queue=len(queue), inherited_france_rows=len(fm),
                inherited_france_current=f["current"], inherited_france_all_three=len(fa),
                inherited_france_gaps=len(fg), inherited_france_membership_history=len(fd),
                inherited_france_case_adjudications=len(france_case_adjudications()),
                inherited_machine_readable_birthyear_controls=len(controls),
                every_old_field_claim_and_ledger_preserved=True, new_decisions=0,
                new_identity_DOB_approvals_applied_in_this_baseline_check=0)


def assemble(output):
    require(not output.exists(), "Fresh output directory required")
    expected = prepare()
    for name, value in expected.items():
        require(js(ROOT / "inputs" / name) == value, "Prepared input changed: " + name)
    verify_baseline_inheritance()
    _, _, _, j = final_japan()
    cases = js(ROOT / "inputs/france_individual_case_decisions.json")
    fm, fa, fg, fd, f = france(js(ROOT / "inputs/france_decisions.json"), js(ROOT / "inputs/france_dob_conflict_decisions.json"), cases)
    case_ledger = france_case_adjudications(cases)
    scope = processing_summary()
    chosen = selections(allow_unfrozen_empty=True)
    frozen = js(ROOT / "inputs/selection_config.json")["selection_frozen"]
    f["newly_processed_v14_candidates"] = len(js(ROOT / "inputs/france_processed_ids.json"))
    summary = dict(date="2026-11-01", baseline_commit=BASE_COMMIT,
                   stage="root_frozen_bounded_collection" if frozen else "empty_baseline_awaiting_root_frozen_source_scope",
                   selection_frozen=frozen, japan=j, france=f,
                   fixed_selection_counts={k: len(v) for k, v in chosen.items()},
                   actual_processed_counts={"japan": scope["japan"]["actually_processed_dispositions"], "france": len(js(ROOT / "inputs/france_processed_ids.json"))},
                   japan_dob_processed_count=0, processing_status_breakdown=scope,
                   professor_collection="paused", fields_collection="preserved_parked", japan_hard_routes="parked",
                   collection_complete=False, analysis_cohort_frozen=False, bazi_variables_computed=0,
                   outreach_count=0, new_raw_DOB_claims_authorized=False,
                   new_raw_DOB_claims=0, existing_singleton_DOB_cases_approved=len(cases))
    output.mkdir(parents=True)
    for name in INHERITED_CSV_FILES[:3]:
        shutil.copyfile(BASE / "outputs" / name, output / name)
    if not cases and not js(ROOT / "inputs/france_decisions.json"):
        for name in INHERITED_CSV_FILES[3:]: shutil.copyfile(BASE / "outputs" / name, output / name)
    else:
        for name, rows in (("france_master877.csv", fm), ("france_accepted_all_three.csv", fa),
                           ("france_remaining_gaps.csv", fg), ("france_membership_decisions.csv", fd),
                           ("france_case_adjudications.csv", case_ledger)):
            J.write_csv(output / name, rows)
    dump(output / "summary.json", summary)
    return summary

def verify():
    actual = inventory(ROOT)
    require(actual == js(ROOT / "MANIFEST.json")["files"], "Inventory/hash mismatch")
    for rel in actual:
        require("private" not in Path(rel).parts and not rel.endswith((".pdf", ".html", ".png", ".jpg", ".pyc")),
                "Raw/private source in deliverable")
        if Path(rel).parts[0] == "source_batches":
            require(len(Path(rel).parts) == 3 and Path(rel).suffix in (".json", ".csv", ".md", ".txt"),
                    "Only top-level public source metadata is deliverable")
    verify_baseline_inheritance()
    for name, value in prepare().items():
        require(js(ROOT / "inputs" / name) == value, "Prepared input mismatch: " + name)
    for name in INHERITED_CSV_FILES[:3]:
        require((ROOT / "outputs" / name).read_bytes() == (BASE / "outputs" / name).read_bytes(),
                "Japan output changed inherited CSV bytes: " + name)
    for name in ("france_membership_decisions.csv", "france_case_adjudications.csv"):
        old = readcsv(BASE / "outputs" / name); new = readcsv(ROOT / "outputs" / name)
        require(len(new) >= len(old) and all({k: after[k] for k in before} == before for before, after in zip(old, new)),
                "An inherited France ledger field changed")
    summary = js(ROOT / "outputs/summary.json")
    chosen = selections(allow_unfrozen_empty=True)
    scope = processing_summary()
    require(summary["fixed_selection_counts"] == {k: len(v) for k, v in chosen.items()}, "Fixed selection accounting changed")
    require(summary["actual_processed_counts"] == {k: scope[k]["actually_processed_dispositions"] for k in scope},
            "Source processing accounting mismatch")
    require(all(scope[k]["explicit_outcome_rows"] == len(chosen[k]) for k in chosen), "Fixed outcomes incomplete")
    cases = js(ROOT / "inputs/france_individual_case_decisions.json")
    f = summary["france"]
    require(f["current"]["identity_accepted"] == baseline_summary()["france"]["current"]["identity_accepted"] + sum(d["new_values"].get("identity_accepted") == "1" for d in cases)
            and f["current"]["dob_accepted"] == baseline_summary()["france"]["current"]["dob_accepted"] + sum(d["new_values"].get("dob_accepted") == "1" for d in cases),
            "France identity/DOB changed outside approved singleton cases")
    require(f["current"]["membership_accepted"] == baseline_summary()["france"]["current"]["membership_accepted"] + len(EXACT_MEMBERSHIP_ACCEPTANCES),
            "France membership gains differ from exact approvals")
    require(f["all_three_accepted"] + f["all_three_remaining_gaps"] == f["candidate_groups"], "France gap accounting changed")
    require(not summary["analysis_cohort_frozen"] and summary["bazi_variables_computed"] == summary["outreach_count"] == summary["new_raw_DOB_claims"] == 0,
            "Collection-only gate changed")
    with tempfile.TemporaryDirectory(prefix="academy-v14-replay-") as folder:
        replay = Path(folder) / "outputs"
        assemble(replay)
        require({p.name for p in replay.iterdir()} == {p.name for p in (ROOT / "outputs").iterdir()}, "Output inventory differs from replay")
        for path in replay.iterdir():
            require(path.read_bytes() == (ROOT / "outputs" / path.name).read_bytes(), "Output replay mismatch: " + path.name)
    print(f"{len(actual)} pinned v14 files verified; complete v13 state and both French histories preserved")

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("baseline", "prepare", "assemble", "verify"))
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    if args.mode == "baseline":
        print(json.dumps(verify_baseline_inheritance(), ensure_ascii=False))
    elif args.mode == "verify":
        verify()
    elif args.mode == "prepare":
        require(args.output_dir is not None and not args.output_dir.exists(), "Fresh output directory required")
        values = prepare()
        args.output_dir.mkdir(parents=True)
        for name, value in values.items():
            dump(args.output_dir / name, value)
    else:
        require(args.output_dir is not None, "Output directory required")
        print(json.dumps(assemble(args.output_dir), ensure_ascii=False))


if __name__ == "__main__":
    main()
