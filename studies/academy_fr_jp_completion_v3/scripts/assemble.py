#!/usr/bin/env python3
"""Apply reviewed source deltas to pinned v2 country ledgers, without network."""
import argparse
import collections
import copy
import csv
import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import unicodedata

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT.parent / "academy_fr_jp_completion_v2"


def js(p):
    return json.loads(p.read_text(encoding="utf-8"))


def csv_rows(p):
    with p.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def dump(p, value):
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def require(ok, message):
    if not ok:
        raise ValueError(message)


def module(p, name):
    spec = importlib.util.spec_from_file_location(name, p)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


J = module(BASE / "scripts/build_japan.py", "previous_japan")


def check_baseline():
    meta = js(ROOT / "inputs/baseline_provenance.json")
    for rel, expected in meta["baseline_sha256"].items():
        require(hashlib.sha256((BASE / rel).read_bytes()).hexdigest() == expected, "Changed v2 baseline: " + rel)


def secondary_reference(c):
    tier = c.get("source_tier", "").lower()
    return ("dictionary" in tier or "commercial" in tier or "kotobank" in tier or "edited_reference" in tier)


def japan(decisions, delta_claims, new_processed):
    rows = J.roster(BASE / "inputs")
    by = {r["member_key"]: r for r in rows}
    holds = js(BASE / "inputs/japan_dob_holds.json")
    prior_holds = copy.deepcopy(holds)
    seen_actions = set()
    decision_ledger = []
    for d in decisions:
        key = d["member_key"]
        require(key in by and d["name_jp"] == by[key]["name_jp"], "Japan decision identity mismatch")
        action = d["decision_type"]
        require((key, action) not in seen_actions, "Duplicate Japan action")
        seen_actions.add((key, action))
        require(d.get("body_verified") is True and d.get("source_url", "").startswith("https://"), "Decision requires observed source body")
        require(d.get("evidence_quote") and (d.get("identity_bridge") or d.get("reason")), "Decision needs quoted evidence and identity/reason")
        if action == "release_identity_assignment_hold":
            require(holds.get(key, {}).get("status") == "identity_assignment_hold", "Identity release cannot lift another kind of hold")
            require(d.get("identity_body_supported") is True, "Identity release needs same-person body support")
            del holds[key]
        elif action == "set_broad_section":
            section = str(d["new_broad_section"])
            require(section in {"1", "2"}, "Invalid broad section")
            require(not by[key]["broad_section_supported"], "New scope action may not overwrite prior direct evidence")
            by[key]["previous_section_evidence_status"] = by[key]["section_evidence_status"]
            by[key]["broad_section_supported"] = section
            by[key]["section_evidence_status"] = "v3_explicit_institution_section_evidence"
            by[key]["section_evidence_source_url"] = d["source_url"]
            if d.get("exact_subsection"):
                require(d.get("exact_subsection_explicit") is True, "Subsection cannot be inferred")
                by[key]["exact_subsection_supported"] = str(d["exact_subsection"])
        elif action == "add_dob_hold":
            require(d["hold_status"] in {"source_quality_hold", "source_date_conflict_hold", "source_calendar_hold", "source_caveat_hold"}, "Unknown DOB hold")
            holds[key] = {"status": d["hold_status"], "reason": d["reason"]}
        else:
            raise ValueError("Unknown Japan action: " + action)
        decision_ledger.append(dict(d, final_cohort_accepted=False, bazi_variables_computed=0))
    all_claims = js(BASE / "inputs/japan_body_claims.json") + delta_claims
    for c in delta_claims:
        require(c.get("body_verified") is True and c.get("identity_body_supported") is True, "Unverified delta birth claim")
        require(c.get("calendar_comparable") in {True, False} and type(c.get("calendar_comparable")) is bool, "Explicit calendar routing required")
        require("wikipedia.org" not in c.get("source_url", "") and "wikidata.org" not in c.get("source_url", ""), "Crowd-source date cannot enter edited/institution body layer")
    processed = set(js(BASE / "inputs/japan_processed_ids.json")) | set(new_processed)
    require(processed <= by.keys(), "Unknown processed Japan IDs")
    authority = {}
    for name in ["ndl_candidate_matches435.csv", "ndl_candidate_matches40.csv"]:
        for r in csv_rows(BASE / "inputs" / name):
            authority[r["member_key"]] = r
    master, ledger, queue, summary = J.assemble(rows, all_claims, holds, processed, authority)
    grouped = collections.defaultdict(list)
    for c in ledger:
        grouped[c["member_key"]].append(c)
    for row in master:
        cs = grouped[row["member_key"]]
        row["body_source_reviewed"] = row.pop("institutionally_processed")
        if row["dob_status"] == "not_institutionally_processed":
            row["dob_status"] = "not_body_source_processed"
        source_day = [c for c in cs if c["precision"] == "day" and c["calendar_comparable"]]
        row["has_institution_or_university_day_claim"] = any(not secondary_reference(c) for c in source_day)
        row["has_edited_reference_day_claim"] = any(secondary_reference(c) for c in source_day)
        row["day_evidence_tier"] = ("institution_or_university_supported" if row["has_institution_or_university_day_claim"] else "edited_reference_only") if row["dob_status"] == "body_day_no_known_conflict" else "not_unresolved_day_approved"
        row["identity_hold_released_this_round"] = prior_holds.get(row["member_key"], {}).get("status") == "identity_assignment_hold" and row["member_key"] not in holds
    # The old key included only institution-sourced batches. New edited
    # dictionaries are explicit source bodies, with their own separate tier.
    summary["body_birth_people"] = summary.pop("institutional_body_birth_people")
    status_counts = summary["dob_status_counts"]
    status_counts["not_body_source_processed"] = status_counts.pop("not_institutionally_processed", 0)
    day_rows = [r for r in master if r["dob_status"] == "body_day_no_known_conflict"]
    summary.update(
        baseline_day_no_known_conflict=js(BASE / "japan_outputs/summary.json")["body_day_no_known_conflict"],
        institutional_or_university_supported_day_no_known_conflict=sum(r["has_institution_or_university_day_claim"] for r in day_rows),
        edited_reference_only_day_no_known_conflict=sum(not r["has_institution_or_university_day_claim"] for r in day_rows),
        identity_holds_released_this_round=sum(r["identity_hold_released_this_round"] for r in master),
        new_source_claim_rows=len(delta_claims), source_tier_claim_counts=dict(collections.Counter(c["source_tier"] for c in ledger)),
        source_tier_note="Edited commercial biographical dictionaries are separate from institution/university records; none are name-only authority assignments. Body day status is source evidence, not final cohort or explicit Gregorian-calendar acceptance.",
    )
    summary["scope_note"] = "Restored 482-person universe, seven Section I exclusions, 47 section holds unless an explicit new source action proves otherwise; not a frozen national eligible cohort."
    return master, ledger, queue, decision_ledger, summary


def name_tokens(s):
    s = unicodedata.normalize("NFKD", s).casefold()
    s = "".join(c for c in s if not unicodedata.combining(c))
    return sorted(re.findall(r"[a-z]+", s))


def flag(value):
    require(value in {0, 1, False, True, "0", "1"}, "Nonbinary decision flag")
    return str(int(value))


def france(base_rows, decisions):
    output = copy.deepcopy(base_rows)
    by = {r["candidate_group_id"]: r for r in output}
    require(len(by) == len(output), "Duplicate France candidate ID")
    seen = set()
    ledger = []
    for row in output:
        row.update(v3_membership_decision_status="", v3_membership_review_reason="", v3_evidence_urls=[],
                   membership_as_of_year="", v3_election_source_conflict_retained="")
    for d in decisions:
        cid = d["candidate_group_id"]
        require(cid in by and cid not in seen, "Unknown or duplicate France decision")
        seen.add(cid)
        row = by[cid]
        names = [row["display_name"], row.get("accepted_canonical_person_name", "")]
        require(any(name_tokens(d["name"]) == name_tokens(n) for n in names if n), "France decision name mismatch")
        require(row["identity_accepted"] == "1" and row["dob_accepted"] == "1", "This round cannot bypass prior identity/DOB holds")
        require(row["membership_accepted"] == "0" and d.get("reviewed") is True, "France action must review an existing membership gap")
        accepted = flag(d["membership_accepted"])
        role, cutoff, conflict = (flag(d[k]) for k in ["membership_role_supported", "election_cutoff_stable", "election_date_conflict"])
        evidence = d.get("evidence", [])
        require(isinstance(evidence, list), "France evidence list required")
        positive = [e for e in evidence if e.get("body_verified") is True and e.get("source_url", "").startswith("https://")]
        if accepted == "1":
            require(role == "1" and cutoff == "1" and conflict == "0", "Strict membership cannot bypass role/cutoff/conflict gates")
            require(row.get("election_date_conflict") != "1" or d.get("previous_conflict_explicitly_resolved") is True, "New source cannot silently lift an inherited election conflict")
            require(positive and any(e.get("quote") and e.get("identity_note") for e in positive), "Strict acceptance requires actual source and same-person wording")
            precision = d["accepted_full_member_election_precision"]
            day, year = d.get("accepted_full_member_election_date"), d.get("accepted_full_member_election_year")
            if precision == "day":
                parsed = datetime.date.fromisoformat(day)
                require(parsed.year <= 2025, "Election after cutoff")
                require(year in (None, "", parsed.year, str(parsed.year)), "Conflicting accepted election year/day")
                year = parsed.year
            elif precision == "year":
                require(not day and type(year) is int and 1 <= year <= 2025, "Year precision cannot create a day")
            else:
                raise ValueError("Strict acceptance requires observed election year/day")
            require(int(year) >= int(row["accepted_dob_iso"][:4]), "Election precedes accepted birth year")
            row.update(membership_accepted="1", accepted_full_member_election_date=day or "",
                       accepted_full_member_election_year=str(year), accepted_election_precision=precision)
        # A newly observed correspondent/foreign-associate event is not a
        # lifetime negative and cannot erase an earlier supported full role.
        aggregate_role = "1" if role == "1" or row.get("membership_role_supported") == "1" else "0"
        aggregate_cutoff = "1" if cutoff == "1" or row.get("election_cutoff_stable") == "1" else "0"
        aggregate_conflict = conflict if d.get("previous_conflict_explicitly_resolved") is True else ("1" if conflict == "1" or row.get("election_date_conflict") == "1" else "0")
        row.update(membership_role_supported=aggregate_role, election_cutoff_stable=aggregate_cutoff,
                   election_date_conflict=aggregate_conflict,
                   v3_membership_decision_status=d["decision_status"], v3_membership_review_reason=d["reason"],
                   v3_evidence_urls=sorted({e["source_url"] for e in positive}),
                   membership_as_of_year=d.get("membership_as_of_year") or "",
                   v3_election_source_conflict_retained=conflict,
                   source_evidence_review_version="France_v3_membership_continuation_20261029")
        row["completion_remaining_dimensions"] = "|".join(k for k in ["identity", "membership", "dob"] if row[k + "_accepted"] != "1")
        row["completion_status"] = "accepted_all_three" if not row["completion_remaining_dimensions"] else "reviewed_with_holds"
        ledger.append(dict(d, bazi_computed=0, analysis_cohort_frozen=False))
    for before, after in zip(base_rows, output):
        for key in ["identity_accepted", "dob_accepted", "accepted_dob_iso", "bazi_computed"]:
            require(before[key] == after[key], "Membership delta changed identity/DOB/analysis")
        if before["membership_accepted"] == "1":
            require(after["membership_accepted"] == "1", "Prior membership approval overwritten")
        after["role_cutoff_and_dob_supported"] = all(after[k] == "1" for k in ["identity_accepted", "dob_accepted", "membership_role_supported", "election_cutoff_stable"])
    accepted_rows = [r for r in output if all(r[k + "_accepted"] == "1" for k in ["identity", "membership", "dob"])]
    gaps = [r for r in output if r not in accepted_rows]
    baseline = {k: sum(r[k] == "1" for r in base_rows) for k in ["identity_accepted", "membership_accepted", "dob_accepted"]}
    current = {k: sum(r[k] == "1" for r in output) for k in baseline}
    summary = dict(candidate_groups=len(output), baseline=baseline, current=current,
                   new_strict_memberships=current["membership_accepted"] - baseline["membership_accepted"],
                   all_three_accepted=len(accepted_rows), all_three_remaining_gaps=len(gaps),
                   membership_cases_reviewed=len(decisions), role_supported=sum(r["membership_role_supported"] == "1" for r in output),
                   cutoff_stable=sum(r["election_cutoff_stable"] == "1" for r in output),
                   role_cutoff_and_dob_supported=sum(r["role_cutoff_and_dob_supported"] for r in output),
                   known_election_conflict_rows=sum(r["election_date_conflict"] == "1" for r in output),
                   role_date_note="Role/cutoff support and election chronology are separate. Strict approvals are not relaxed. Nonordinary observed events do not prove lifetime nonmembership.",
                   collection_complete=False, national_missing_birthdays=None, analysis_cohort_frozen=False, bazi_computed=0)
    return output, accepted_rows, gaps, ledger, summary


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output-dir", type=Path, required=True)
    a = p.parse_args()
    require(not a.output_dir.exists(), "Fresh output directory required")
    check_baseline()
    jm, jl, jq, jd, jsum = japan(js(ROOT / "inputs/japan_decisions.json"), js(ROOT / "inputs/japan_claims.json"), js(ROOT / "inputs/japan_processed_ids.json"))
    fm, fa, fg, fd, fsum = france(csv_rows(BASE / "france/outputs/france_candidate_master877.csv"), js(ROOT / "inputs/france_decisions.json"))
    a.output_dir.mkdir(parents=True)
    for name, values in [("japan_master.csv", jm), ("japan_birth_claims.csv", jl), ("japan_next_action_queue.csv", jq),
                         ("japan_decision_ledger.csv", jd), ("france_master877.csv", fm), ("france_accepted_all_three.csv", fa),
                         ("france_remaining_gaps.csv", fg), ("france_membership_decisions.csv", fd)]:
        J.write_csv(a.output_dir / name, values)
    summary = dict(date="2026-10-29", baseline_commit="a7297e662502ce821c9289dc7d5226b82208b92d", japan=jsum, france=fsum,
                   professor_collection="paused", fields_collection="preserved_parked", collection_complete=False,
                   analysis_cohort_frozen=False, bazi_variables_computed=0)
    dump(a.output_dir / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
