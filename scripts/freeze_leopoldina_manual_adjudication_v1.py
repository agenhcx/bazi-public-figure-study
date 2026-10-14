#!/usr/bin/env python3
"""Freeze Leopoldina manual-source policy and produce final exact-DOB adjudication v1.

Standard library only. The script is intentionally deterministic and does not access the
network or calculate BaZi variables. It preserves all prior frozen inputs and writes a
versioned adjudication layer.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

VERSION = "leopoldina-manual-adjudication-freeze-v1"
YEAR_MIN = 1835
YEAR_MAX = 1985
EXPECTED = {
    "base_candidates": 2407,
    "machine_summary": 1523,
    "official_master": 213,
    "round1_delta": 190,
    "official_same_date_overlays": 155,
    "official_candidate_mismatches": 5,
    "official_only_primary": 52,
    "official_outside_primary": 1,
    "accepted_candidate_rows": 721,
    "accepted_combined_primary": 773,
    "unresolved_candidate_rows": 1686,
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".{os.getpid()}.tmp")
    try:
        with tmp.open("wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


def write_csv(path: Path, rows: list[dict], fields: list[str] | None = None) -> None:
    import io
    if fields is None:
        fields = list(rows[0].keys()) if rows else []
    buf = io.StringIO(newline="")
    w = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    atomic_write(path, buf.getvalue().encode("utf-8-sig"))


def write_json(path: Path, obj: object) -> None:
    atomic_write(path, (json.dumps(obj, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def norm_name(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(c for c in value if not unicodedata.combining(c)).lower()
    value = re.sub(r"\b(?:professor|prof|dr|sir|jr|phd|md|usa|ma)\b", " ", value)
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())


def split_groups(value: str) -> set[str]:
    return {x for x in (value or "").split("|") if x}


def must_unique(rows: list[dict[str, str]], key: str, label: str) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for row in rows:
        k = row.get(key, "")
        if not k or k in out:
            raise RuntimeError(f"{label}: missing or duplicate {key}: {k!r}")
        out[k] = row
    return out


def copy_frozen_decisions(src_dir: Path, out_dir: Path) -> None:
    names = [
        "manual_source_policy_categories_v1.csv",
        "manual_source_domain_registry_v1.csv",
        "archive_exceptions_v1.csv",
        "conflict_adjudications_v1.csv",
        "manual_candidate_status_overrides_v1.csv",
        "manual_followup_missingness_freeze_v1.json",
        "final_dob_adjudication_rules_v1.json",
    ]
    for name in names:
        src = src_dir / name
        if not src.exists():
            raise RuntimeError(f"Missing frozen decision file: {src}")
        atomic_write(out_dir / name, src.read_bytes())


def self_test() -> None:
    assert norm_name("Prof. Dr. Félix Eckstein (") == "felix eckstein"
    assert split_groups("a|b|a") == {"a", "b"}
    assert YEAR_MIN <= 1852 <= YEAR_MAX
    print(f"{VERSION} self-test OK")


def run(args: argparse.Namespace) -> dict:
    root = Path(args.data_root)
    inputs = root / "input_snapshots"
    out = Path(args.out)

    paths = {
        "base": inputs / "candidate_trusted_source_coverage_v2.csv",
        "machine": inputs / "candidate_content_verification_summary_v1.csv",
        "official": inputs / "accepted_exact_dob_2009_2019_v1.csv",
        "delta": inputs / "person_evidence_delta_v2.csv",
        "positive_review": inputs / "positive_source_review_v2.csv",
        "policy_candidates": inputs / "source_policy_extension_candidates_v2.csv",
        "round2_review": inputs / "round2_manual_source_review_v1.csv",
        "round3_review": inputs / "round3_manual_source_review_v1.csv",
        "round4_review": inputs / "round4_manual_source_review_v1.csv",
    }
    for p in paths.values():
        if not p.exists():
            raise RuntimeError(f"Missing input snapshot: {p}")

    base_rows = read_csv(paths["base"])
    machine_rows = read_csv(paths["machine"])
    official_rows = read_csv(paths["official"])
    delta_rows = read_csv(paths["delta"])
    positive_rows = read_csv(paths["positive_review"])
    policy_candidate_rows = read_csv(paths["policy_candidates"])
    r2 = read_csv(paths["round2_review"])
    r3 = read_csv(paths["round3_review"])
    r4 = read_csv(paths["round4_review"])

    if len(base_rows) != EXPECTED["base_candidates"]:
        raise RuntimeError(f"Expected {EXPECTED['base_candidates']} base candidates, got {len(base_rows)}")
    if len(machine_rows) != EXPECTED["machine_summary"]:
        raise RuntimeError(f"Expected {EXPECTED['machine_summary']} machine rows, got {len(machine_rows)}")
    if len(official_rows) != EXPECTED["official_master"]:
        raise RuntimeError(f"Expected {EXPECTED['official_master']} official rows, got {len(official_rows)}")
    if len(delta_rows) != EXPECTED["round1_delta"]:
        raise RuntimeError(f"Expected {EXPECTED['round1_delta']} round-1 delta rows, got {len(delta_rows)}")

    base = must_unique(base_rows, "member_slug", "base candidates")
    machine = must_unique(machine_rows, "member_slug", "machine summary")
    official = must_unique(official_rows, "member_slug", "official master")
    delta = must_unique(delta_rows, "member_slug", "round-1 delta")
    overrides = must_unique(read_csv(root / "manual_candidate_status_overrides_v1.csv"), "member_slug", "manual overrides")
    conflicts = must_unique(read_csv(root / "conflict_adjudications_v1.csv"), "member_slug", "conflict adjudications")
    archive_exceptions = must_unique(read_csv(root / "archive_exceptions_v1.csv"), "member_slug", "archive exceptions")

    # Validate frozen policy artifacts.
    categories = read_csv(root / "manual_source_policy_categories_v1.csv")
    mappings = read_csv(root / "manual_source_domain_registry_v1.csv")
    if not categories or any(r.get("decision_status") not in {"frozen", "frozen_with_condition"} for r in categories):
        raise RuntimeError("Manual source policy categories are not fully frozen")
    if not mappings or any(r.get("decision_status") != "frozen" for r in mappings):
        raise RuntimeError("Manual source domain registry is not fully frozen")
    ae = archive_exceptions.get("friedrich-ehrendorfer")
    if not ae or ae.get("http_status") != "403" or ae.get("archive_exception") != "1":
        raise RuntimeError("Expected frozen ÖAW HTTP 403 archive exception")

    allowed_machine_status = {
        "tier_a_positive", "two_plus_tier_b_positive", "one_tier_b_positive",
        "no_machine_positive", "not_attempted",
    }
    if any(r.get("machine_evidence_status") not in allowed_machine_status for r in machine_rows):
        raise RuntimeError("Unexpected machine evidence status")

    # Global official-master cross-check: never merge a date mismatch automatically.
    official_same: list[dict] = []
    official_mismatch: list[dict] = []
    official_only: list[dict] = []
    official_outside: list[dict] = []
    for o in official_rows:
        y = int(o["candidate_dob"][:4])
        b = base.get(o["member_slug"])
        if not (YEAR_MIN <= y <= YEAR_MAX):
            official_outside.append({**o, "primary_window_eligible": 0, "exclusion_reason": "birth_year_outside_1835_1985"})
            continue
        if b is None:
            official_only.append(o)
            continue
        if o["candidate_dob"] == b["candidate_exact_dob"]:
            n1, n2 = norm_name(o.get("display_name", "")), norm_name(b.get("display_name", ""))
            if n1 != n2 and n1 not in n2 and n2 not in n1:
                raise RuntimeError(f"Official same-date overlay name mismatch for {o['member_slug']}: {n1!r} vs {n2!r}")
            official_same.append({
                "member_slug": o["member_slug"], "display_name": b["display_name"],
                "wikidata_qid": b["wikidata_qid"], "candidate_exact_dob": b["candidate_exact_dob"],
                "official_exact_dob": o["candidate_dob"], "official_election_year": o["election_year"],
                "official_pdf_url": o["pdf_url"], "official_pdf_page": o["pdf_page"],
                "decision": "same_person_same_date_tier_a_overlay", "merge_allowed": 1,
            })
        else:
            likely_type = "identity_collision_hold" if o["member_slug"] == "felix-eckstein" else "official_candidate_date_mismatch_hold"
            official_mismatch.append({
                "member_slug": o["member_slug"], "display_name": o["display_name"],
                "wikidata_qid": b["wikidata_qid"], "candidate_exact_dob": b["candidate_exact_dob"],
                "official_exact_dob": o["candidate_dob"], "official_election_year": o["election_year"],
                "official_pdf_url": o["pdf_url"], "official_pdf_page": o["pdf_page"],
                "hold_type": likely_type, "decision": "do_not_merge_pending_explicit_identity_or_date_adjudication",
                "final_exact_dob": "", "automatic_acceptance": 0, "bazi_variables_computed": 0,
            })

    if len(official_same) != EXPECTED["official_same_date_overlays"]:
        raise RuntimeError(f"Expected {EXPECTED['official_same_date_overlays']} official same-date overlays, got {len(official_same)}")
    if len(official_mismatch) != EXPECTED["official_candidate_mismatches"]:
        raise RuntimeError(f"Expected {EXPECTED['official_candidate_mismatches']} official mismatches, got {len(official_mismatch)}")
    if len(official_only) != EXPECTED["official_only_primary"]:
        raise RuntimeError(f"Expected {EXPECTED['official_only_primary']} official-only primary rows, got {len(official_only)}")
    if len(official_outside) != EXPECTED["official_outside_primary"]:
        raise RuntimeError(f"Expected {EXPECTED['official_outside_primary']} official outside-window row, got {len(official_outside)}")

    official_same_slugs = {r["member_slug"] for r in official_same}
    official_mismatch_slugs = {r["member_slug"] for r in official_mismatch}

    # Candidate-level adjudication.
    candidate_out: list[dict] = []
    route_counts: Counter[str] = Counter()
    final_status_counts: Counter[str] = Counter()
    for b in base_rows:
        slug = b["member_slug"]
        m = machine.get(slug)
        initial_status = m["machine_evidence_status"] if m else "no_trusted_source_record"
        status_after_round1 = delta.get(slug, {}).get("status_if_policy_extension_approved", initial_status)
        final_status = status_after_round1
        ov = overrides.get(slug)
        if ov:
            if ov["candidate_exact_dob_original"] != b["candidate_exact_dob"]:
                raise RuntimeError(f"Override candidate mismatch for {slug}")
            final_status = ov["final_evidence_status"]
        if slug in official_same_slugs:
            final_status = "tier_a_positive"

        conflict = conflicts.get(slug)
        conflict_status = "none"
        adjudicated_dob = b["candidate_exact_dob"]
        if conflict:
            if conflict["adjudication_status"] != "resolved" or conflict["blocks_acceptance"] != "0":
                conflict_status = "unresolved_conflict_hold"
            else:
                conflict_status = "resolved_" + conflict["decision"]
                adjudicated_dob = conflict["adjudicated_exact_dob"]
        if ov and ov.get("adjudicated_exact_dob"):
            adjudicated_dob = ov["adjudicated_exact_dob"]
        if slug in official_mismatch_slugs:
            conflict_status = "official_master_candidate_mismatch_hold"

        accepted = final_status in {"tier_a_positive", "two_plus_tier_b_positive"} and not conflict_status.endswith("hold")
        if slug in official_mismatch_slugs:
            accepted = False

        same_official = slug in official_same_slugs
        if accepted:
            if slug == "rudolf-benedikt":
                route = "manual_conflict_corrected_overlay"
                decision_mode = "manual_adjudication"
                auto = 0
            elif slug in {"johannes-w-rohen", "lord-alexander-r-todd", "manfred-broy"}:
                route = "manual_conflict_resolved"
                decision_mode = "manual_adjudication"
                auto = 0
            elif same_official:
                route = "official_new_member_profile_same_date"
                decision_mode = "frozen_rule"
                auto = 1
            elif ov and final_status != initial_status:
                route = "targeted_manual_followup"
                decision_mode = "manual_evidence_frozen_rule"
                auto = 0
            elif slug in delta and status_after_round1 != initial_status:
                route = "round1_manual_policy_extension"
                decision_mode = "manual_evidence_frozen_rule"
                auto = 0
            elif initial_status == "tier_a_positive":
                route = "machine_tier_a"
                decision_mode = "frozen_rule"
                auto = 1
            elif initial_status == "two_plus_tier_b_positive":
                route = "machine_two_plus_tier_b"
                decision_mode = "frozen_rule"
                auto = 1
            else:
                route = "accepted_other_frozen_rule"
                decision_mode = "frozen_rule"
                auto = 1
            final_dob = adjudicated_dob
            acceptance_status = "accepted_exact_dob"
            route_counts[route] += 1
        else:
            final_dob = ""
            auto = 0
            decision_mode = "unresolved"
            if slug in official_mismatch_slugs:
                route = "official_master_candidate_mismatch_hold"
                acceptance_status = "hold_identity_or_date_mismatch"
            elif final_status == "one_tier_b_positive":
                route = "insufficient_one_tier_b"
                acceptance_status = "unresolved_insufficient_independent_evidence"
            elif final_status == "no_machine_positive":
                route = "no_positive_content_match"
                acceptance_status = "unresolved_no_positive_content_match"
            elif final_status == "not_attempted":
                route = "not_attempted_under_frozen_collection"
                acceptance_status = "unresolved_not_attempted"
            elif final_status == "no_trusted_source_record":
                route = "no_trusted_source_record"
                acceptance_status = "unresolved_no_trusted_source_record"
            else:
                route = "unresolved_other"
                acceptance_status = "unresolved"

        final_status_counts[final_status] += 1
        machine_a_groups = m.get("positive_tier_a_independence_groups", "") if m else ""
        machine_b_groups = m.get("positive_tier_b_independence_groups", "") if m else ""
        round1_a = delta.get(slug, {}).get("new_policy_extension_tier_a_groups", "")
        round1_b = delta.get(slug, {}).get("new_policy_extension_tier_b_groups", "")
        manual_groups = ov.get("supporting_independence_groups", "") if ov else ""
        candidate_out.append({
            "candidate_record_key": f"candidate:{b['wikidata_qid']}:{b['candidate_exact_dob']}",
            "member_slug": slug,
            "display_name": b["display_name"],
            "wikidata_qid": b["wikidata_qid"],
            "candidate_exact_dob_original": b["candidate_exact_dob"],
            "adjudicated_exact_dob": adjudicated_dob if adjudicated_dob != b["candidate_exact_dob"] else "",
            "initial_machine_evidence_status": initial_status,
            "status_after_round1_policy_freeze": status_after_round1,
            "final_evidence_status": final_status,
            "machine_tier_a_groups": machine_a_groups,
            "machine_tier_b_groups": machine_b_groups,
            "round1_new_tier_a_groups": round1_a,
            "round1_new_tier_b_groups": round1_b,
            "targeted_manual_groups": manual_groups,
            "official_new_member_same_date_overlay": int(same_official),
            "archive_exception": int(slug in archive_exceptions),
            "conflict_status": conflict_status,
            "acceptance_route": route,
            "decision_mode": decision_mode,
            "acceptance_status": acceptance_status,
            "final_exact_dob": final_dob,
            "automatic_acceptance": auto,
            "primary_birthyear_eligible": 1,
            "prior_frozen_input_modified": 0,
            "bazi_variables_computed": 0,
        })

    accepted_candidates = [r for r in candidate_out if r["acceptance_status"] == "accepted_exact_dob"]
    unresolved_candidates = [r for r in candidate_out if r["acceptance_status"] != "accepted_exact_dob"]
    if len(accepted_candidates) != EXPECTED["accepted_candidate_rows"]:
        raise RuntimeError(f"Expected {EXPECTED['accepted_candidate_rows']} accepted candidate rows, got {len(accepted_candidates)}")
    if len(unresolved_candidates) != EXPECTED["unresolved_candidate_rows"]:
        raise RuntimeError(f"Expected {EXPECTED['unresolved_candidate_rows']} unresolved candidate rows, got {len(unresolved_candidates)}")

    # Official-only accepted rows; date-mismatch rows are excluded and remain in a hold file.
    official_only_out: list[dict] = []
    for o in sorted(official_only, key=lambda x: (x["member_slug"], x["candidate_dob"])):
        official_only_out.append({
            "record_key": f"official:{o['member_slug']}:{o['election_year']}:{o['candidate_dob']}",
            "record_origin": "official_new_member_profile_only",
            "member_slug": o["member_slug"], "display_name": o["display_name"], "wikidata_qid": "",
            "class": o["class"], "section": o["section"], "election_year": o["election_year"],
            "final_exact_dob": o["candidate_dob"], "acceptance_status": "accepted_exact_dob",
            "acceptance_route": "official_new_member_profile_only", "decision_mode": "prior_explicit_official_acceptance",
            "source_url": o["pdf_url"], "source_page": o["pdf_page"],
            "automatic_acceptance": 0, "primary_birthyear_eligible": 1,
            "prior_frozen_input_modified": 0, "bazi_variables_computed": 0,
        })

    combined: list[dict] = []
    for r in accepted_candidates:
        combined.append({
            "record_key": r["candidate_record_key"], "record_origin": "adjudicated_candidate",
            "member_slug": r["member_slug"], "display_name": r["display_name"], "wikidata_qid": r["wikidata_qid"],
            "class": "", "section": "", "election_year": "",
            "final_exact_dob": r["final_exact_dob"], "acceptance_status": r["acceptance_status"],
            "acceptance_route": r["acceptance_route"], "decision_mode": r["decision_mode"],
            "source_url": "", "source_page": "", "automatic_acceptance": r["automatic_acceptance"],
            "primary_birthyear_eligible": 1, "prior_frozen_input_modified": 0, "bazi_variables_computed": 0,
        })
    combined.extend(official_only_out)
    keys = [r["record_key"] for r in combined]
    if len(keys) != len(set(keys)):
        raise RuntimeError("Duplicate combined accepted record_key")
    if len(combined) != EXPECTED["accepted_combined_primary"]:
        raise RuntimeError(f"Expected {EXPECTED['accepted_combined_primary']} combined accepted rows, got {len(combined)}")

    # Normalize and deduplicate targeted manual evidence ledger.
    targeted_by_key: dict[tuple[str, str, str], dict] = {}
    for stage, rows in (("round2", r2), ("round3", r3), ("round4", r4)):
        for r in rows:
            k = (r["member_slug"], r["source_url"], r["observed_exact_dob"])
            targeted_by_key[k] = {
                "evidence_stage": stage, "member_slug": r["member_slug"], "wikidata_qid": r["wikidata_qid"],
                "candidate_exact_dob": r["candidate_exact_dob"], "observed_exact_dob": r["observed_exact_dob"],
                "source_label": r["source_label"], "source_url": r["source_url"], "source_domain": r["source_domain"],
                "document_kind": r["document_kind"], "policy_tier": r["proposed_policy_tier"],
                "independence_group": r["independence_group"], "relation_to_candidate": r["relation_to_candidate"],
                "review_note": r["review_note"], "content_reviewed": 1,
            }
    manual_ledger: list[dict] = []
    for r in positive_rows:
        manual_ledger.append({
            "evidence_stage": "round1_cache_full_page_review", "member_slug": r["member_slug"],
            "wikidata_qid": r["wikidata_qid"], "candidate_exact_dob": r["candidate_exact_dob"],
            "observed_exact_dob": r["candidate_exact_dob"], "source_label": r["source_family"],
            "source_url": r["final_url"], "source_domain": r["final_domain"], "document_kind": "cached_source_page",
            "policy_tier": r["proposed_policy_tier"], "independence_group": r["independence_group"],
            "relation_to_candidate": "supports_candidate", "review_note": r["evidence_disposition"],
            "content_reviewed": r["content_verified_from_cache"],
        })
    manual_ledger.extend(targeted_by_key.values())

    # Write outputs.
    out.mkdir(parents=True, exist_ok=True)
    copy_frozen_decisions(root, out)
    write_csv(out / "official_master_same_date_overlays_v1.csv", official_same)
    write_csv(out / "official_master_candidate_mismatch_review_v1.csv", official_mismatch)
    write_csv(out / "official_only_accepted_dobs_v1.csv", official_only_out)
    write_csv(out / "official_records_outside_primary_window_v1.csv", official_outside)
    write_csv(out / "manual_source_evidence_ledger_v1.csv", manual_ledger)
    write_csv(out / "candidate_final_dob_adjudication_v1.csv", candidate_out)
    write_csv(out / "accepted_candidate_dobs_v1.csv", accepted_candidates)
    write_csv(out / "unresolved_candidate_dobs_v1.csv", unresolved_candidates)
    write_csv(out / "accepted_exact_dob_combined_primary_v1.csv", sorted(combined, key=lambda x: (x["final_exact_dob"], x["member_slug"], x["record_key"])))

    summary = {
        "dataset": VERSION,
        "frozen_date": "2026-10-14",
        "primary_birthyear_window": [YEAR_MIN, YEAR_MAX],
        "candidate_adjudication_rows": len(candidate_out),
        "candidate_final_evidence_status_counts": dict(sorted(final_status_counts.items())),
        "accepted_candidate_rows": len(accepted_candidates),
        "unresolved_candidate_rows": len(unresolved_candidates),
        "accepted_candidate_route_counts": dict(sorted(route_counts.items())),
        "official_same_date_tier_a_overlays": len(official_same),
        "official_candidate_mismatch_holds": len(official_mismatch),
        "official_only_accepted_primary_rows": len(official_only_out),
        "official_records_outside_primary_window": len(official_outside),
        "accepted_exact_dob_combined_primary_rows": len(combined),
        "resolved_manual_conflicts": sum(r["adjudication_status"] == "resolved" for r in conflicts.values()),
        "approved_candidate_dob_corrections": sum(r["decision"] == "replace_candidate" for r in conflicts.values()),
        "archive_exceptions": len(archive_exceptions),
        "archive_exception_states": dict(Counter(r["exception_class"] for r in archive_exceptions.values())),
        "manual_followup_closed": 1,
        "open_ended_person_search_allowed": 0,
        "prior_frozen_inputs_modified": 0,
        "final_exact_dob_written_in_new_overlay": len(combined),
        "automatic_acceptance_rows": sum(int(r["automatic_acceptance"]) for r in combined),
        "manual_or_prior_explicit_acceptance_rows": len(combined) - sum(int(r["automatic_acceptance"]) for r in combined),
        "bazi_variables_computed": 0,
        "warning": "This is a versioned adjudication overlay. It does not rewrite prior candidate, source-verification, or official-profile input files. The five official/candidate mismatches remain held and are not in the accepted combined table.",
        "input_sha256": {k: sha256(v) for k, v in paths.items()},
    }
    write_json(out / "summary.json", summary)

    # Output manifest after all data files have been written.
    output_files = sorted(p for p in out.iterdir() if p.is_file() and p.name != "manifest.json")
    manifest = {
        "dataset": VERSION,
        "generated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "script_version": VERSION,
        "files": {p.name: {"sha256": sha256(p), "bytes": p.stat().st_size} for p in output_files},
        "invariants": EXPECTED,
    }
    write_json(out / "manifest.json", manifest)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data-root", default="data/leopoldina_manual_adjudication_freeze_v1")
    p.add_argument("--out", default="data/leopoldina_manual_adjudication_freeze_v1/final")
    p.add_argument("--self-test", action="store_true")
    args = p.parse_args()
    if args.self_test:
        self_test()
        return 0
    run(args)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, ValueError, OSError, KeyError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        raise SystemExit(2)
