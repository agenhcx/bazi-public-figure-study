#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

EXPECTED = {
    "award_row_count": 662,
    "unique_person_count": 658,
    "exact_birth_date_person_count": 645,
    "files": {
        "nobel_science_awards.csv": "23e4c43d54eb8987fcd8743da53c8a3040c68520d0dde57b27aecf25d8182066",
        "nobel_science_people.csv": "3fdacad1158e6705624f5f0aab54de62dc48ce14e0f7e010f8b2c5576b7c41b7",
        "nobel_science_summary.csv": "f0e065fa0f1989c6affbf713e6cdbbd6f751ed796c0dd2c6f6e8c3ec5db63f22",
    },
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_csv(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="data/nobel_science_master")
    args = ap.parse_args()
    root = Path(args.dir)

    required = [root / x for x in EXPECTED["files"]]
    required.append(root / "manifest.json")
    missing = [str(p) for p in required if not p.exists()]
    if missing:
        raise RuntimeError(f"Missing frozen-master reconstruction outputs: {missing}")

    awards = read_csv(root / "nobel_science_awards.csv")
    people = read_csv(root / "nobel_science_people.csv")
    exact = sum(str(r.get("birth_date_exact", "")).strip() == "1" for r in people)

    checks = {
        "award_row_count": len(awards),
        "unique_person_count": len(people),
        "exact_birth_date_person_count": exact,
    }
    failures = []
    for k, expected in (
        ("award_row_count", EXPECTED["award_row_count"]),
        ("unique_person_count", EXPECTED["unique_person_count"]),
        ("exact_birth_date_person_count", EXPECTED["exact_birth_date_person_count"]),
    ):
        if checks[k] != expected:
            failures.append(f"{k}: got {checks[k]}, expected {expected}")

    file_checks = {}
    for name, expected_sha in EXPECTED["files"].items():
        got = sha256(root / name)
        ok = got == expected_sha
        file_checks[name] = {"got_sha256": got, "expected_sha256": expected_sha, "match": int(ok)}
        if not ok:
            failures.append(f"{name} SHA256 mismatch")

    report = {
        "dataset": "Nobel science master frozen-v1 reconstruction verification",
        "directory": str(root),
        "count_checks": checks,
        "file_checks": file_checks,
        "freeze_match": int(not failures),
        "failures": failures,
        "bazi_variables_computed": 0,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))

    if failures:
        raise SystemExit(
            "Frozen Nobel master verification FAILED. Do not enrich or use this reconstruction until differences are reviewed."
        )

    print("Frozen Nobel master verification PASSED.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
