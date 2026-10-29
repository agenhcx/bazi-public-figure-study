#!/usr/bin/env python3
"""Normalize immutable worker transcriptions, preserving source precision and holds."""
import argparse
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def js(p):
    return json.loads(p.read_text(encoding="utf-8"))


def csv_rows(p):
    with p.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def normalize(root):
    claims, processed, holds = [], set(), {}
    overrides = js(root / "inputs/japan_claim_overrides.json")
    false_hashes = set(overrides["invalid_body_hashes"])
    allowed_pairs = set(overrides["source_supplied_pair_warning_overrides"])
    for path in sorted((root / "source_batches").glob("*/claims.json")):
        family = path.parent.name
        for i, c in enumerate(js(path)):
            key = c["member_key"]
            processed.add(key)
            warning = c.get("calendar_warning", "")
            comparable = not warning or key in allowed_pairs
            cal = c.get("calendar", "not_stated")
            if cal in {"lunar_explicit", "japanese_era_pre1873_unspecified"}:
                comparable = False
            raw = c.get("raw_birth_statement", c.get("date_raw", ""))
            support = c.get("identity_support", c.get("identity_note", ""))
            body = c.get("source_body_verified", c.get("body_verified", False))
            digest = c.get("source_sha256")
            correction = ""
            if digest in false_hashes:
                correction = "Original hash was a Site Unavailable response, not the cited source body; web-body observation retained."
                digest = None
            item = dict(member_key=key, name_jp=c["name_jp"],
                        year=c.get("year", c.get("birth_year")), month=c.get("month", c.get("birth_month")), day=c.get("day", c.get("birth_day")),
                        precision=c["precision"], calendar=cal, calendar_comparable=comparable,
                        raw_birth_statement=raw, source_url=c["source_url"], source_tier=c["source_tier"],
                        identity_support=support, body_verified=body, identity_body_supported=bool(body and support),
                        source_sha256=digest, source_hash_correction=correction,
                        evidence_extraction_sha256=c.get("evidence_capture_sha256"), evidence_extraction_is_original_html=c.get("evidence_capture_is_original_html"),
                        source_location=c.get("source_location", c.get("source_locator", c.get("source_page", ""))),
                        retrieved_utc=c.get("retrieved_utc"), retrieved_date=c.get("retrieved_date"),
                        source_family=family, snapshot_record=i,
                        calendar_note=c.get("calendar_note", c.get("source_note", "")), calendar_warning=warning,
                        source_supplied_equivalence=key in allowed_pairs or ("parallel" in c.get("source_note", "") and not warning))
            claims.append(item)
            if warning and key not in allowed_pairs:
                holds[key] = dict(status="source_caveat_hold" if "multiple_birth" in warning else "source_calendar_hold", reason=warning)
        pp = path.parent / "processed.csv"
        if pp.exists():
            for r in csv_rows(pp):
                if r.get("status") not in {"not_processed", "prior_seed_skipped", "existing_seed_skipped"}:
                    processed.add(r["member_key"])
    seed = js(root / "inputs/japan_seed5.json")
    records = seed if isinstance(seed, list) else seed["records"]
    for record in records:
        processed.add(record["member_key"])
        for c in record["claims"]:
            claims.append(dict(member_key=record["member_key"], name_jp=record["name_jp"],
                               year=c["year"], month=c["month"], day=c["day"], precision=c["precision"], calendar=c["calendar"],
                               calendar_comparable=c["calendar"] not in {"lunar_explicit", "julian_explicit"},
                               raw_birth_statement=c["date_raw"], source_url=c["source_url"], source_tier=c.get("source_tier", "restored_institutional_seed"),
                               identity_support=c["identity_note"], body_verified=c["source_status"] == "body_observed", identity_body_supported=True,
                               source_sha256=c.get("source_sha256"), source_family="previous_seed5",
                               source_original_calendar_birth=record.get("source_original_calendar_birth"),
                               calendar_note=c.get("calendar_wording_raw", c.get("calendar_note", ""))))
    kyoto = root / "source_batches/japan_kyoto_bulk/claims.csv"
    if kyoto.exists():
        for c in csv_rows(kyoto):
            key = c["member_key"]
            processed.add(key)
            if c["birth_precision"] == "missing":
                continue
            comparable = c["calendar"] == "western_calendar_from_database_policy"
            item = dict(member_key=key, name_jp=c["name_jp"],
                        year=int(c["birth_year_component"]), month=int(c["birth_month_component"]) if c["birth_month_component"] else None,
                        day=int(c["birth_day_component"]) if c["birth_day_component"] else None,
                        precision=c["birth_precision"], calendar=c["calendar"], calendar_comparable=comparable,
                        raw_birth_statement=c["source_birth_raw"], source_url=c["source_url"], source_tier=c["source_tier"],
                        identity_support=c["identity_evidence"], body_verified=True, identity_body_supported=True,
                        source_sha256=c["source_capture_sha256"], retrieved_utc=c["retrieved_at"],
                        source_family="japan_kyoto_bulk", calendar_policy_url=c["calendar_policy_url"],
                        identity_evidence_status=c["identity_evidence_status"], calendar_note="Calendar follows database legend; no collector conversion.")
            claims.append(item)
            if c["identity_evidence_status"] == "name_professional_context_support_requires_crosscheck":
                independent = any(v["member_key"] == key and v["source_family"] != "japan_kyoto_bulk" for v in claims)
                if not independent:
                    holds.setdefault(key, dict(status="identity_assignment_hold", reason="Kyoto archive name and career context observed; independent same-person crosscheck still pending."))
        extra = root / "source_batches/japan_kyoto_bulk/tamaru_additional_claim.csv"
        if extra.exists():
            for c in csv_rows(extra):
                # The municipal statement has a pre-1873 unspecified calendar.
                # Its year differs by ten years from the Kyoto transcription.
                parts = [int(v) for v in c["birth_iso_components"].split("-")]
                claims.append(dict(member_key=c["member_key"], name_jp=c["name_jp"], year=parts[0], month=parts[1], day=parts[2],
                                   precision=c["birth_precision"], calendar="pre1873_calendar_not_stated", calendar_comparable=False,
                                   raw_birth_statement=c["source_birth_raw"],
                                   source_url=c["source_url"], source_tier="municipal_government_biography",
                                   identity_support=c.get("identity_evidence", "Named theoretical physicist biography with matching academic career."),
                                   body_verified=True, identity_body_supported=True,
                                   source_sha256=c.get("source_capture_sha256"), retrieved_utc=c.get("retrieved_at"), source_family="japan_kyoto_bulk_ancillary"))
    holds.update(overrides["person_holds"])
    for key in overrides.get("independently_crosschecked_identity_keys", []):
        if holds.get(key, {}).get("status") == "identity_assignment_hold":
            del holds[key]
    return claims, sorted(processed), holds


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=ROOT)
    p.add_argument("--output-dir", type=Path, required=True)
    a = p.parse_args()
    if a.output_dir.exists():
        raise ValueError("Output directory must be fresh")
    claims, processed, holds = normalize(a.root)
    a.output_dir.mkdir(parents=True)
    for name, obj in [("japan_body_claims.json", claims), ("japan_processed_ids.json", processed), ("japan_dob_holds.json", holds)]:
        (a.output_dir / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(dict(claim_rows=len(claims), processed_ids=len(processed), explicit_holds=len(holds))))


if __name__ == "__main__":
    main()
