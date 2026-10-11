#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import re
from pathlib import Path

DEFAULT_AUDIT = Path("data/dob_calendar_model_audit_primary_with_nobel_v1_1/calendar_model_audit_rows_v1.csv")
DEFAULT_REGISTRY = Path("data/dob_absolute_date_adjudication_v1/canonical_gregorian_dob_registry_v1.csv")
DEFAULT_OUT = Path("data/hierarchy_primary_dob_canonical_v1")


def read_csv(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows, fields):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def sha256(path: Path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def exact_date(s):
    s = str(s or "").strip()
    try:
        d = dt.date.fromisoformat(s)
        return len(s) == 10 and d.isoformat() == s
    except Exception:
        return False


def qids(v):
    return sorted(set(re.findall(r"Q\d+", str(v or ""))))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--audit", default=str(DEFAULT_AUDIT))
    ap.add_argument("--registry", default=str(DEFAULT_REGISTRY))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    args = ap.parse_args()

    audit_path = Path(args.audit)
    registry_path = Path(args.registry)
    out = Path(args.out)

    if not audit_path.exists():
        raise RuntimeError(f"Primary DOB audit rows not found: {audit_path}")
    if not registry_path.exists():
        raise RuntimeError(f"Adjudication registry not found: {registry_path}")

    audit = read_csv(audit_path)
    registry_rows = read_csv(registry_path)
    registry = {}
    for r in registry_rows:
        qid = str(r.get("qid") or "").strip()
        if not re.fullmatch(r"Q\d+", qid):
            raise RuntimeError(f"Invalid registry QID: {qid}")
        if qid in registry:
            raise RuntimeError(f"Duplicate registry QID: {qid}")
        action = str(r.get("action") or "").strip()
        if action not in {"apply_overlay", "keep_current", "pending_manual_calendar_semantics"}:
            raise RuntimeError(f"Unsupported registry action for {qid}: {action}")
        canonical = str(r.get("canonical_gregorian_dob") or "").strip()
        if action in {"apply_overlay", "keep_current"} and not exact_date(canonical):
            raise RuntimeError(f"Confirmed registry row lacks valid canonical date: {qid} {canonical}")
        registry[qid] = r

    out_rows = []
    changed = []
    pending = []
    for row in audit:
        if str(row.get("bazi_variables_computed") or "0").strip() not in {"0", "0.0", ""}:
            raise RuntimeError("Input audit unexpectedly contains computed BaZi variables")
        stored = str(row.get("stored_dob") or "").strip()
        if not exact_date(stored):
            raise RuntimeError(f"Primary exact-DOB audit row has invalid stored_dob: {row.get('dataset')} {row.get('record_key')} {stored}")

        row_qids = qids(row.get("wikidata_qids"))
        matched = [registry[q] for q in row_qids if q in registry]
        if len(matched) > 1:
            raise RuntimeError(f"Multiple adjudication registry matches for row {row.get('record_key')}: {row_qids}")

        analysis_dob = stored
        adjudication_action = "none"
        adjudication_qid = ""
        calendar_pending = 0
        analysis_eligible_calendar = 1
        if matched:
            rr = matched[0]
            adjudication_action = rr["action"]
            adjudication_qid = rr["qid"]
            if rr["action"] == "apply_overlay":
                analysis_dob = rr["canonical_gregorian_dob"]
            elif rr["action"] == "keep_current":
                analysis_dob = rr["canonical_gregorian_dob"]
                if analysis_dob != stored:
                    raise RuntimeError(
                        f"keep_current registry disagrees with stored date for {rr['qid']}: {stored} vs {analysis_dob}"
                    )
            elif rr["action"] == "pending_manual_calendar_semantics":
                calendar_pending = 1
                analysis_eligible_calendar = 0

        x = dict(row)
        x.update({
            "analysis_dob_gregorian": analysis_dob,
            "dob_changed_by_adjudication": int(analysis_dob != stored),
            "adjudication_qid": adjudication_qid,
            "adjudication_action": adjudication_action,
            "calendar_semantics_pending": calendar_pending,
            "analysis_eligible_calendar": analysis_eligible_calendar,
            "bazi_variables_computed": 0,
        })
        out_rows.append(x)
        if analysis_dob != stored:
            changed.append(x)
        if calendar_pending:
            pending.append(x)

    out.mkdir(parents=True, exist_ok=True)
    base_fields = list(audit[0].keys()) if audit else []
    extra = [
        "analysis_dob_gregorian", "dob_changed_by_adjudication", "adjudication_qid",
        "adjudication_action", "calendar_semantics_pending", "analysis_eligible_calendar",
    ]
    fields = [f for f in base_fields if f != "bazi_variables_computed"] + extra + ["bazi_variables_computed"]
    write_csv(out / "primary_hierarchy_dob_canonical_v1.csv", out_rows, fields)
    write_csv(out / "applied_dob_changes_v1.csv", changed, fields)
    write_csv(out / "calendar_semantics_pending_v1.csv", pending, fields)

    by_dataset = {}
    for ds in sorted(set(r.get("dataset", "") for r in out_rows)):
        rr = [r for r in out_rows if r.get("dataset", "") == ds]
        by_dataset[ds] = {
            "rows": len(rr),
            "changed_by_adjudication": sum(int(r["dob_changed_by_adjudication"]) for r in rr),
            "calendar_pending": sum(int(r["calendar_semantics_pending"]) for r in rr),
            "calendar_eligible": sum(int(r["analysis_eligible_calendar"]) for r in rr),
        }

    summary = {
        "dataset": "Primary hierarchy canonical Gregorian DOB overlay v1",
        "input_audit": str(audit_path),
        "input_audit_sha256": sha256(audit_path),
        "registry": str(registry_path),
        "registry_sha256": sha256(registry_path),
        "rows": len(out_rows),
        "changed_rows": len(changed),
        "pending_rows": len(pending),
        "calendar_eligible_rows": sum(int(r["analysis_eligible_calendar"]) for r in out_rows),
        "dataset_summary": by_dataset,
        "frozen_inputs_modified": 0,
        "bazi_variables_computed": 0,
    }
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
