#!/usr/bin/env python3
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
from pathlib import Path

BASE = Path("data/nas_science_core_dob_crosswalk")
INPUT = BASE / "nas_science_core_dob_crosswalk_v7.csv"
PATCH = Path("data/nas_science_core_dob_manual_supplement_v2.csv")
OUT_CSV = BASE / "nas_science_core_dob_crosswalk_v8.csv"
LOG = BASE / "nas_science_core_dob_manual_supplement_log_v2.csv"
SUMMARY = BASE / "summary_v8.json"

def read_csv(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

def write_csv(path: Path, rows, fields=None):
    if fields is None:
        fields = list(rows[0].keys()) if rows else []
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

def present(v):
    return str(v or "").strip() not in ("", "nan", "None")

def sha256(path: Path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def valid_date(value: str):
    try:
        return dt.date.fromisoformat(value).isoformat()
    except Exception as e:
        raise RuntimeError(f"Invalid exact date {value!r}") from e

def main():
    rows = read_csv(INPUT)
    patches = read_csv(PATCH)
    if len(rows) != 3051:
        raise RuntimeError(f"Expected 3051 science-core rows, got {len(rows)}")

    by_url = {r["profile_url"]: r for r in rows}
    if len(by_url) != len(rows):
        raise RuntimeError("Duplicate profile_url in v7 input")

    patch_urls = [p["profile_url"] for p in patches]
    if len(set(patch_urls)) != len(patch_urls):
        raise RuntimeError("Duplicate profile_url in supplement v2 patch")

    input_exact = sum(present(r.get("final_exact_dob")) for r in rows)
    log = []

    for p in patches:
        url = p["profile_url"]
        if url not in by_url:
            raise RuntimeError(f"Patch target not found: {url}")
        r = by_url[url]
        if r.get("name", "") != p["name"]:
            raise RuntimeError(f"Name mismatch for {url}: {r.get('name')} vs {p['name']}")

        old = (r.get("final_exact_dob") or "").strip()
        expected = (p.get("expected_old_final_exact_dob") or "").strip()
        if old != expected:
            raise RuntimeError(
                f"Old DOB mismatch for {p['name']}: got {old!r}, expected {expected!r}"
            )
        if old:
            raise RuntimeError(f"Supplement v2 may only add to blank DOBs: {p['name']}")

        new = valid_date((p.get("new_final_exact_dob") or "").strip())
        r["final_exact_dob"] = new
        r["dob_status"] = "exact_manual_supplement_v2"
        r["manual_supplement_v2_status"] = p.get("review_status", "")
        r["manual_supplement_v2_primary_source_url"] = p.get("primary_source_url", "")
        r["manual_supplement_v2_secondary_source_url"] = p.get("secondary_source_url", "")
        r["manual_supplement_v2_note"] = p.get("note", "")

        log.append({
            "profile_url": url,
            "name": p["name"],
            "old_final_exact_dob": old,
            "new_final_exact_dob": new,
            "review_status": p.get("review_status", ""),
            "primary_source_url": p.get("primary_source_url", ""),
            "secondary_source_url": p.get("secondary_source_url", ""),
            "note": p.get("note", ""),
        })

    for r in rows:
        for k in (
            "manual_supplement_v2_status",
            "manual_supplement_v2_primary_source_url",
            "manual_supplement_v2_secondary_source_url",
            "manual_supplement_v2_note",
        ):
            r.setdefault(k, "")

    exact = sum(present(r.get("final_exact_dob")) for r in rows)
    unresolved = [r for r in rows if not present(r.get("final_exact_dob"))]
    deceased = [r for r in rows if r.get("deceased") == "Y"]
    living = [r for r in rows if r.get("deceased") != "Y"]
    deceased_exact = sum(present(r.get("final_exact_dob")) for r in deceased)
    living_exact = sum(present(r.get("final_exact_dob")) for r in living)

    if exact != input_exact + len(patches):
        raise RuntimeError(
            f"Supplement delta invariant failed: input={input_exact}, "
            f"patches={len(patches)}, output={exact}"
        )
    if exact + len(unresolved) != len(rows):
        raise RuntimeError("Resolved/unresolved partition invariant failed")
    if deceased_exact + living_exact != exact:
        raise RuntimeError("Living/deceased exact-DOB partition invariant failed")

    write_csv(OUT_CSV, rows)
    write_csv(LOG, log)

    summary = {
        "dataset": "NAS science-core exact-DOB crosswalk v8 after audited manual supplement v2",
        "created_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "parent": INPUT.name,
        "science_core_rows": len(rows),
        "input_exact_dob_rows": input_exact,
        "supplement_rows": len(patches),
        "supplement_status_counts": {
            s: sum(x["review_status"] == s for x in log)
            for s in sorted(set(x["review_status"] for x in log))
        },
        "final_exact_dob_rows": exact,
        "final_exact_dob_coverage": round(exact / len(rows), 6),
        "remaining_without_exact_dob": len(unresolved),
        "deceased_rows": len(deceased),
        "deceased_final_exact_dob_rows": deceased_exact,
        "deceased_final_exact_dob_coverage": round(deceased_exact / len(deceased), 6),
        "living_rows": len(living),
        "living_final_exact_dob_rows": living_exact,
        "living_final_exact_dob_coverage": round(living_exact / len(living), 6),
        "bazi_variables_computed": 0,
        "policy_note": (
            "Supplement v2 only fills previously blank final_exact_dob fields after independent "
            "source audit. Wikipedia diagnostic candidates are never accepted merely because "
            "Wikipedia supplies a unique date; source conflicts are corrected from authoritative "
            "institutional or academy sources."
        ),
        "files": {
            OUT_CSV.name: {"sha256": sha256(OUT_CSV), "bytes": OUT_CSV.stat().st_size},
            LOG.name: {"sha256": sha256(LOG), "bytes": LOG.stat().st_size},
            PATCH.name: {"sha256": sha256(PATCH), "bytes": PATCH.stat().st_size},
        },
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
