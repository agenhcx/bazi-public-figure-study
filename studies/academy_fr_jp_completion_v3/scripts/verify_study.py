#!/usr/bin/env python3
"""Verify complete pinned file inventory, country accounting and unchanged gates."""
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def js(p):
    return json.loads(p.read_text(encoding="utf-8"))


def rows(p):
    with p.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def main():
    inventory = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in ROOT.rglob("*") if p.is_file() and p != ROOT / "MANIFEST.json" and "__pycache__" not in p.parts}
    assert inventory == js(ROOT / "MANIFEST.json")["files"], "Inventory or hash mismatch"
    assert not any("private/" in p or p.endswith((".pdf", ".html", ".jpg", ".png", ".pyc")) for p in inventory)
    s = js(ROOT / "outputs/summary.json")
    j, f = s["japan"], s["france"]
    assert j["restored_candidate_universe"] == 482
    assert (j["broad_section_ii_supported"], j["section_i_excluded"], j["section_unresolved"]) == (428, 7, 47)
    assert j["body_day_no_known_conflict"] == 213
    assert j["institutional_or_university_supported_day_no_known_conflict"] + j["edited_reference_only_day_no_known_conflict"] == 213
    assert j["nonexcluded_body_day_no_known_conflict"] + j["nonexcluded_dob_not_day_count"] == 475
    assert j["identity_holds_released_this_round"] == 7
    assert f["current"] == {"identity_accepted": 755, "membership_accepted": 267, "dob_accepted": 744}
    assert f["all_three_accepted"] == 265 and f["all_three_remaining_gaps"] == 612
    assert f["new_strict_memberships"] == 21
    assert len(rows(ROOT / "outputs/france_master877.csv")) == 877
    assert len(rows(ROOT / "outputs/japan_master.csv")) == 482
    assert len(rows(ROOT / "outputs/japan_next_action_queue.csv")) == j["next_action_queue_count"]
    assert all(r["final_cohort_accepted"] == "False" and r["bazi_variables_computed"] == "0" for r in rows(ROOT / "outputs/japan_master.csv"))
    assert not s["analysis_cohort_frozen"] and s["bazi_variables_computed"] == 0
    assert not s["collection_complete"] and s["professor_collection"] == "paused"
    print(f"{len(inventory)} study file hashes and both country totals verified; no analysis or date padding")


if __name__ == "__main__":
    main()
