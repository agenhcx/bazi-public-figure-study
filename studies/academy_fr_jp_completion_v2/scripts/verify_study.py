#!/usr/bin/env python3
"""Check pinned metadata and cross-country accounting without source requests."""
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def js(path):
    return json.loads(path.read_text(encoding="utf-8"))


def rows(path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def main():
    manifest = js(ROOT / "MANIFEST.json")
    actual = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in ROOT.rglob("*") if p.is_file() and p.name != "MANIFEST.json"
              and "__pycache__" not in p.parts}
    # Nested manifests are also pinned in the outer inventory.
    for p in ROOT.rglob("MANIFEST.json"):
        if p != ROOT / "MANIFEST.json":
            actual[str(p.relative_to(ROOT))] = hashlib.sha256(p.read_bytes()).hexdigest()
    assert actual == manifest["files"], "Study inventory or bytes changed"
    assert not any("private/" in p or p.endswith((".pdf", ".html", ".png", ".jpg", ".pyc")) for p in actual)
    j = js(ROOT / "japan_outputs/summary.json")
    f = js(ROOT / "france/outputs/summary.json")
    combined = js(ROOT / "round_summary.json")
    assert combined["japan"] == j
    assert combined["france"]["current"] == f["current"]
    assert j["restored_candidate_universe"] == 482
    assert j["broad_section_ii_supported"] + j["section_i_excluded"] + j["section_unresolved"] == 482
    assert j["nonexcluded_body_day_no_known_conflict"] + j["nonexcluded_dob_not_day_count"] == 475
    japanese = rows(ROOT / "japan_outputs/japan_master.csv")
    assert len({x["member_key"] for x in japanese}) == 482
    assert all(x["final_cohort_accepted"] == "False" and x["bazi_variables_computed"] == "0" for x in japanese)
    assert f["current"] == {"identity_accepted": 755, "membership_accepted": 246, "dob_accepted": 744, "bazi_computed": 0, "all_three_accepted": 244}
    assert len(rows(ROOT / "france/outputs/france_candidate_master877.csv")) == 877
    assert len(rows(ROOT / "france/outputs/france_accepted_all_three.csv")) == 244
    assert len(rows(ROOT / "france/outputs/france_remaining_gaps.csv")) == 633
    assert len(rows(ROOT / "france/outputs/france_external_case_exclusions.csv")) == 1
    assert combined["bazi_variables_computed"] == 0 and not combined["analysis_cohort_frozen"]
    print(f"{len(actual)} file hashes verified; country totals, exclusions and analysis gates consistent")


if __name__ == "__main__":
    main()
