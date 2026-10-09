#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

IN = Path("data/royal_society_current_wikidata_locator_v1_inputs")
ROSTER = Path("data/royal_society_roster_freeze_v1/royal_society_fellows_roster_freeze_v1.csv")
OUT = Path("data/royal_society_current_wikidata_locator_v1_consolidated")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_csv(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows, fields):
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def main():
    if OUT.exists() and any(OUT.iterdir()):
        raise RuntimeError(f"nonempty output {OUT}")
    OUT.mkdir(parents=True, exist_ok=True)

    files = sorted(IN.rglob("current_wikidata_locator.csv"))
    if len(files) != 8:
        raise RuntimeError(f"Expected 8 shard CSVs, found {len(files)}: {files}")

    rows = []
    shard_meta = []
    for p in files:
        rr = read_csv(p)
        rows.extend(rr)
        shard_meta.append({"file": str(p), "rows": len(rr), "sha256": sha256(p)})

    if len(rows) != 1570:
        raise RuntimeError(f"Expected 1570 locator rows, found {len(rows)}")

    keys = [r["cohort_key"] for r in rows]
    dups = [k for k, v in Counter(keys).items() if v > 1]
    if len(set(keys)) != 1570 or dups:
        raise RuntimeError(f"Locator key invariant failed unique={len(set(keys))} dup={dups[:20]}")

    with ROSTER.open("r", encoding="utf-8-sig", newline="") as f:
        roster_current = [r for r in csv.DictReader(f) if r["status_at_source"] == "current"]
    roster_keys = {r["cohort_key"] for r in roster_current}
    locator_keys = set(keys)
    missing = sorted(roster_keys - locator_keys)
    extra = sorted(locator_keys - roster_keys)
    if len(roster_current) != 1570 or missing or extra:
        raise RuntimeError(
            f"Roster set invariant failed roster={len(roster_current)} locator={len(rows)} "
            f"missing={missing[:20]} extra={extra[:20]}"
        )

    rows = sorted(rows, key=lambda r: r["cohort_key"])
    resolved = [r for r in rows if (r.get("wikidata_qid") or "").strip()]
    high = [r for r in rows if r.get("locator_confidence") == "high_membership_exact_name"]
    medium = [r for r in rows if (r.get("locator_confidence") or "").startswith("medium_")]
    unresolved = [r for r in rows if not (r.get("wikidata_qid") or "").strip()]
    any_p569 = [r for r in resolved if str(r.get("p569_any", "")).strip() == "1"]
    exact = [r for r in resolved if str(r.get("p569_exact_day", "")).strip() == "1"]
    exact_ref_url = [r for r in exact if (r.get("p569_reference_urls") or "").strip()]
    exact_stated_in = [r for r in exact if (r.get("p569_stated_in_qids") or "").strip()]

    fields = list(rows[0].keys())
    fullp = OUT / "royal_society_current_wikidata_locator_v1.csv"
    resp = OUT / "resolved_locator_v1.csv"
    exactp = OUT / "exact_p569_candidate_queue_v1.csv"
    refp = OUT / "exact_p569_reference_url_queue_v1.csv"
    unp = OUT / "unresolved_locator_v1.csv"
    write_csv(fullp, rows, fields)
    write_csv(resp, resolved, fields)
    write_csv(exactp, exact, fields)
    write_csv(refp, exact_ref_url, fields)
    write_csv(unp, unresolved, fields)

    confidence = Counter((r.get("locator_confidence") or "").strip() for r in rows)

    summary = {
        "dataset": "Royal Society current Fellows Wikidata locator consolidated v1",
        "rows": len(rows),
        "unique_cohort_keys": len(locator_keys),
        "roster_set_match": True,
        "resolved_locator": len(resolved),
        "resolved_locator_coverage": len(resolved) / len(rows),
        "high_confidence_locator": len(high),
        "medium_confidence_locator": len(medium),
        "unresolved_locator": len(unresolved),
        "locator_with_any_p569": len(any_p569),
        "locator_with_exact_day_p569": len(exact),
        "exact_day_p569_coverage_all_current": len(exact) / len(rows),
        "exact_day_p569_coverage_resolved": len(exact) / len(resolved) if resolved else 0,
        "exact_p569_with_reference_url": len(exact_ref_url),
        "exact_p569_with_stated_in_qid": len(exact_stated_in),
        "confidence_counts": dict(sorted(confidence.items())),
        "shard_files": shard_meta,
        "full_csv_sha256": sha256(fullp),
        "resolved_csv_sha256": sha256(resp),
        "exact_candidate_csv_sha256": sha256(exactp),
        "reference_url_queue_sha256": sha256(refp),
        "unresolved_csv_sha256": sha256(unp),
        "dob_values_accepted": 0,
        "bazi_variables_computed": 0,
        "note": (
            "Locator-only consolidation. Wikidata P569 values remain candidate evidence and are not "
            "accepted DOBs until validated under the frozen source hierarchy."
        ),
    }

    (OUT / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
