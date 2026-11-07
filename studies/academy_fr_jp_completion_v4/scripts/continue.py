#!/usr/bin/env python3
"""Replay a bounded v4 source batch against the unchanged v3 country ledgers."""
import argparse
import collections
import copy
import csv
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT.parent / "academy_fr_jp_completion_v3"
spec = importlib.util.spec_from_file_location("academy_v3", BASE / "scripts/assemble.py")
V3 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(V3)
J = V3.J
js, readcsv, require = V3.js, V3.csv_rows, V3.require


def dump(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def check_baseline():
    for rel, expected in js(ROOT / "inputs/baseline_provenance.json")["baseline_sha256"].items():
        require(hashlib.sha256((BASE / rel).read_bytes()).hexdigest() == expected, "Changed v3 baseline: " + rel)
    V3.check_baseline()


def prepare(root=ROOT):
    selected = js(root / "inputs/batch_selection.json")
    batches = root / "source_batches"
    claims = []
    for rel in selected["japan_claim_files"]:
        for i, record in enumerate(js(batches / rel)):
            claims.append(dict(record, source_batch_record=rel + ":" + str(i)))
    processed = {c["member_key"] for c in claims}
    for rel in selected["japan_processed_files"]:
        for r in readcsv(batches / rel):
            status = r.get("status") or r.get("round_status") or r.get("outcome") or r.get("new_route_status") or ""
            require(bool(status), "Missing processing status: " + rel)
            if not status.startswith("not_"):
                processed.add(r["member_key"])
    holds = {}
    for rel in selected["japan_hold_files"]:
        raw = js(batches / rel)
        if isinstance(raw, list):
            records = raw
        else:
            records = [dict(value, member_key=key) for key, value in raw.items() if key.startswith("jpa") and isinstance(value, dict)]
        for record in records:
            if record.get("global_member_hold") is False:
                continue
            status = record.get("status", record.get("hold_status"))
            if status is None:
                status = {"calendar_hold": "source_calendar_hold", "formal_source_date_conflict": "source_date_conflict_hold", "source_quality_hold_unverified_competing_year": "source_quality_hold"}.get(record.get("hold_type"))
            if status is None:
                continue
            key = record["member_key"]
            record = dict(status=status, reason=record.get("reason", record.get("resolution", record.get("note", ""))))
            require(key not in holds or holds[key] == record, "Incompatible hold overlays")
            require(record["status"] in {"source_date_conflict_hold", "source_quality_hold", "source_calendar_hold", "source_caveat_hold"}, "Unknown birth hold")
            holds[key] = record
    france = []
    for rel in selected["france_decision_files"]:
        france.extend(dict(d, source_batch_file=rel) for d in js(batches / rel))
    for rel in selected.get("france_refinement_files", []):
        for update in js(batches / rel):
            current = next(d for d in france if d["candidate_group_id"] == update["candidate_group_id"])
            current.update(update)
            current["refinement_source_file"] = rel
    overlay_path = root / "inputs/integration_overlays.json"
    if overlay_path.exists():
        for update in js(overlay_path):
            current = next(d for d in france if d["candidate_group_id"] == update["candidate_group_id"])
            current.update(update)
            current["root_integration_overlay_applied"] = True
    return {"japan_claims.json": claims, "japan_processed_ids.json": sorted(processed), "japan_holds.json": holds, "france_decisions.json": france}


def previous_japan():
    return V3.japan(js(BASE / "inputs/japan_decisions.json"), js(BASE / "inputs/japan_claims.json"), js(BASE / "inputs/japan_processed_ids.json"))


def edited_reference(c):
    tier = c.get("source_tier", "").lower()
    return any(term in tier for term in ["dictionary", "kotobank", "edited_reference", "biographical_reference"])


def japan(delta, new_holds, new_processed):
    base_master, base_claims, _, _, baseline = previous_japan()
    old = V3.BASE
    holds = copy.deepcopy(js(old / "inputs/japan_dob_holds.json"))
    for d in js(BASE / "inputs/japan_decisions.json"):
        if d["decision_type"] == "release_identity_assignment_hold":
            del holds[d["member_key"]]
        elif d["decision_type"] == "add_dob_hold":
            holds[d["member_key"]] = {"status": d["hold_status"], "reason": d["reason"]}
        else:
            raise ValueError("Unrecognized predecessor decision")
    for key, h in new_holds.items():
        require(any(c["member_key"] == key for c in delta), "Hold needs a source claim in this batch")
        before = next(r for r in base_master if r["member_key"] == key)
        if h["status"] == "source_calendar_hold" and before["dob_status"] == "body_day_no_known_conflict":
            require(h.get("existing_modern_claim_explicitly_challenged") is True,
                    "An unconverted alternate expression cannot silently invalidate an already supported modern source date")
        holds[key] = h
    for c in delta:
        require(c.get("body_verified") is True and c.get("identity_body_supported") is True, "Birth delta requires actual body and same-person support")
        require(type(c.get("calendar_comparable")) is bool, "Explicit calendar routing required")
        require(not any(h in c.get("source_url", "") for h in ["wikipedia.org", "wikidata.org"]), "Unreviewed crowd-source date")
    processed = set(js(old / "inputs/japan_processed_ids.json")) | set(js(BASE / "inputs/japan_processed_ids.json")) | set(new_processed)
    people = {r["member_key"] for r in base_master}
    require(processed <= people, "Unknown processed identity")
    authority = {}
    for name in ["ndl_candidate_matches435.csv", "ndl_candidate_matches40.csv"]:
        authority.update({r["member_key"]: r for r in readcsv(old / "inputs" / name)})
    master, ledger, queue, summary = J.assemble(base_master, base_claims + delta, holds, processed, authority)
    grouped = collections.defaultdict(list)
    for c in ledger:
        grouped[c["member_key"]].append(c)
    for r in master:
        r["body_source_reviewed"] = r.pop("institutionally_processed")
        if r["dob_status"] == "not_institutionally_processed":
            r["dob_status"] = "not_body_source_processed"
        days = [c for c in grouped[r["member_key"]] if c["precision"] == "day" and c["calendar_comparable"]]
        r["has_institution_or_university_day_claim"] = any(not V3.secondary_reference(c) for c in days)
        r["has_edited_reference_day_claim"] = any(edited_reference(c) for c in days)
        r["has_other_attributed_secondary_day_claim"] = any(V3.secondary_reference(c) and not edited_reference(c) for c in days)
        r["day_evidence_tier"] = ("institution_or_university_supported" if r["has_institution_or_university_day_claim"] else "edited_reference_only" if r["has_edited_reference_day_claim"] else "other_attributed_secondary_only") if r["dob_status"] == "body_day_no_known_conflict" else "not_day_without_known_conflict"
        r["v3_identity_hold_released"] = r.pop("identity_hold_released_this_round", False)
        r["v4_source_claim_added"] = any(c["member_key"] == r["member_key"] for c in delta)
    counts = summary["dob_status_counts"]
    counts["not_body_source_processed"] = counts.pop("not_institutionally_processed", 0)
    summary["body_birth_people"] = summary.pop("institutional_body_birth_people")
    days = [r for r in master if r["dob_status"] == "body_day_no_known_conflict"]
    summary.update(baseline_day_no_known_conflict=baseline["body_day_no_known_conflict"],
                   day_status_net_change=len(days) - baseline["body_day_no_known_conflict"],
                   institutional_or_university_supported_day_no_known_conflict=sum(r["has_institution_or_university_day_claim"] for r in days),
                   edited_reference_only_day_no_known_conflict=sum(r["day_evidence_tier"] == "edited_reference_only" for r in days),
                   other_attributed_secondary_only_day_no_known_conflict=sum(r["day_evidence_tier"] == "other_attributed_secondary_only" for r in days),
                   secondary_only_day_no_known_conflict=sum(not r["has_institution_or_university_day_claim"] for r in days),
                   source_tier_claim_counts=dict(collections.Counter(c["source_tier"] for c in ledger)),
                   new_raw_source_claim_rows=len(delta), new_section_decisions=0,
                   source_tier_note="Institution/university/organization, edited-reference-only, and other attributed reproduction-only day evidence are separate. No source majority, calendar conversion or final cohort acceptance.")
    summary["scope_note"] = baseline["scope_note"]
    return master, ledger, queue, summary


def france(decisions):
    base = readcsv(BASE / "outputs/france_master877.csv")
    master, accepted, gaps, ledger, summary = V3.france(base, decisions)
    old_by = {r["candidate_group_id"]: r for r in base}
    changed = {d["candidate_group_id"] for d in decisions}
    keys = ["v3_membership_decision_status", "v3_membership_review_reason", "v3_evidence_urls", "v3_election_source_conflict_retained"]
    for r in master:
        old = old_by[r["candidate_group_id"]]
        updated = r["candidate_group_id"] in changed
        for k in keys:
            r[k.replace("v3_", "v4_", 1)] = r[k] if updated else ""
            r[k] = old.get(k, "")
        if not updated:
            r["membership_as_of_year"] = old.get("membership_as_of_year", "")
        else:
            r["source_evidence_review_version"] = "France_v4_membership_continuation_20261029"
    summary["baseline_all_three_accepted"] = V3.js(BASE / "outputs/summary.json")["france"]["all_three_accepted"]
    summary["all_three_net_change"] = len(accepted) - summary["baseline_all_three_accepted"]
    return master, accepted, gaps, ledger, summary


def assemble(output):
    require(not output.exists(), "Fresh output directory required")
    check_baseline()
    jm, jl, jq, j = japan(js(ROOT / "inputs/japan_claims.json"), js(ROOT / "inputs/japan_holds.json"), js(ROOT / "inputs/japan_processed_ids.json"))
    fm, fa, fg, fd, f = france(js(ROOT / "inputs/france_decisions.json"))
    output.mkdir(parents=True)
    for name, data in [("japan_master.csv", jm), ("japan_birth_claims.csv", jl), ("japan_next_action_queue.csv", jq), ("france_master877.csv", fm), ("france_accepted_all_three.csv", fa), ("france_remaining_gaps.csv", fg), ("france_membership_decisions.csv", fd)]:
        J.write_csv(output / name, data)
    summary = {"date": "2026-10-29", "baseline_commit": "f5058c523402f1ed6df19df815400969a9c0a4de", "japan": j, "france": f,
               "professor_collection": "paused", "fields_collection": "preserved_parked", "collection_complete": False,
               "analysis_cohort_frozen": False, "bazi_variables_computed": 0}
    dump(output / "summary.json", summary)
    return summary


def verify():
    actual = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in ROOT.rglob("*") if p.is_file() and p != ROOT / "MANIFEST.json" and "__pycache__" not in p.parts}
    require(actual == js(ROOT / "MANIFEST.json")["files"], "Inventory/hash mismatch")
    require(not any("private/" in p or p.endswith((".pdf", ".html", ".png", ".jpg", ".pyc")) for p in actual), "Raw/private source in deliverable")
    check_baseline()
    s = js(ROOT / "outputs/summary.json")
    j, f = s["japan"], s["france"]
    require(j["restored_candidate_universe"] == 482 and j["nonexcluded_science_and_unresolved_candidates"] == 475, "Roster changed")
    require(j["section_unresolved"] == 47 and j["broad_section_ii_supported"] == 428 and j["section_i_excluded"] == 7, "Section decisions changed")
    require(j["body_day_no_known_conflict"] == j["institutional_or_university_supported_day_no_known_conflict"] + j["edited_reference_only_day_no_known_conflict"] + j["other_attributed_secondary_only_day_no_known_conflict"], "Source tier mismatch")
    require(j["nonexcluded_body_day_no_known_conflict"] + j["nonexcluded_dob_not_day_count"] == 475, "Date accounting mismatch")
    require((j["body_day_no_known_conflict"], j["institutional_or_university_supported_day_no_known_conflict"], j["edited_reference_only_day_no_known_conflict"], j["other_attributed_secondary_only_day_no_known_conflict"]) == (310, 195, 114, 1), "Reviewed day/source-tier totals changed")
    require(f["current"]["identity_accepted"] == 755 and f["current"]["dob_accepted"] == 744 and f["candidate_groups"] == 877, "France nonmembership dimension changed")
    require(f["all_three_accepted"] + f["all_three_remaining_gaps"] == 877, "France gap accounting mismatch")
    require(f["current"]["membership_accepted"] == 290 and f["all_three_accepted"] == 288, "Reviewed France approvals changed")
    require(not s["analysis_cohort_frozen"] and s["bazi_variables_computed"] == 0, "Analysis gate changed")
    print(f'{len(actual)} pinned files verified; baseline and country accounting preserved')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("mode", choices=["prepare", "assemble", "verify"])
    p.add_argument("--output-dir", type=Path)
    a = p.parse_args()
    if a.mode == "verify":
        verify()
    elif a.mode == "prepare":
        require(a.output_dir is not None and not a.output_dir.exists(), "Fresh output directory required")
        a.output_dir.mkdir(parents=True)
        for name, obj in prepare().items():
            dump(a.output_dir / name, obj)
    else:
        require(a.output_dir is not None, "Output directory required")
        s = assemble(a.output_dir)
        print(json.dumps({"japan_day": s["japan"]["body_day_no_known_conflict"], "france_membership": s["france"]["current"]["membership_accepted"]}))


if __name__ == "__main__":
    main()
