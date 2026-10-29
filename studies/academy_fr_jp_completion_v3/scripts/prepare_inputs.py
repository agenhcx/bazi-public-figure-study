#!/usr/bin/env python3
"""Collect pinned source transcriptions and reviewed overlays; no web parsing."""
import argparse
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(p):
    return json.loads(p.read_text(encoding="utf-8"))


def prepare(root):
    selection = read(root / "inputs/batch_selection.json")
    batches = root / "source_batches"
    claims = []
    for rel in selection["claim_files"]:
        records = read(batches / rel)
        if not isinstance(records, list):
            raise ValueError("Expected list of source claims: " + rel)
        for index, c in enumerate(records):
            item = dict(c, source_batch_record=rel + ":" + str(index))
            claims.append(item)
    processed = {c["member_key"] for c in claims}
    for rel in selection["processed_files"]:
        with (batches / rel).open(encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                status = r.get("status", r.get("round_status", ""))
                if not status:
                    raise ValueError("Missing processing status: " + rel)
                if not status.startswith("not_"):
                    processed.add(r["member_key"])
    decisions = read(batches / selection["identity_decisions"])
    for rel in selection["hold_files"]:
        for key, hold in read(batches / rel).items():
            evidence = next(c for c in claims if c["member_key"] == key)
            decisions.append(dict(member_key=key, name_jp=evidence["name_jp"], decision_type="add_dob_hold",
                                  hold_status=hold["status"], reason=hold["reason"], body_verified=True,
                                  source_url=evidence["source_url"], evidence_quote=evidence["raw_birth_statement"],
                                  identity_bridge=evidence["identity_support"], source_batch_record=rel))
    france = []
    for rel in selection["france_decisions"]:
        for d in read(batches / rel):
            d["source_batch_file"] = rel
            # Independent visual QA establishes the role/event binding in the
            # original 1944 Marchal speech, beyond its later printed heading.
            if d["name"] == "FAGE Louis":
                d["independent_role_binding_addendum"] = "The original speech is expressly dated24July1944, and its first paragraph calls Fage Marchal's Academy successor. This binds the role to the historical event rather than relying solely on a potentially later author title; the competing1947 statement stays unresolved. See source_audits/france_historical_independent_qa.json."
            france.append(d)
    return {
        "japan_claims.json": claims,
        "japan_decisions.json": decisions,
        "japan_processed_ids.json": sorted(processed),
        "france_decisions.json": france,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=ROOT)
    p.add_argument("--output-dir", type=Path, required=True)
    a = p.parse_args()
    if a.output_dir.exists():
        raise ValueError("Fresh output directory required")
    data = prepare(a.root)
    a.output_dir.mkdir(parents=True)
    for name, value in data.items():
        (a.output_dir / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({name: len(value) for name, value in data.items()}))


if __name__ == "__main__":
    main()
