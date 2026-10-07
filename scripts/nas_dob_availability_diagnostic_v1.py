#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from pathlib import Path

BASE = Path("data/nas_science_core_dob_crosswalk")
INPUT = BASE / "nas_science_core_dob_crosswalk_v7.csv"
WD = Path("data/nas_wikidata_dob_pilot/nas_wikidata_dob_collapsed.csv")

OUT_ROWS = BASE / "nas_science_core_dob_availability_v1.csv"
OUT_DECADE = BASE / "nas_science_core_dob_availability_by_election_decade_v1.csv"
OUT_SECTION = BASE / "nas_science_core_dob_availability_by_section_v1.csv"
OUT_SUMMARY = BASE / "summary_dob_availability_v1.json"

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

def year_values(s: str):
    return set(re.findall(r"([12]\d{3})-\d{2}-\d{2}", str(s or "")))

def reliable_qid(row):
    q = str(row.get("wikidata_qid") or "").strip()
    if q:
        return q
    q = str(row.get("global_candidate_qid") or "").strip()
    try:
        accepted = int(float(row.get("global_match_accepted") or 0))
    except Exception:
        accepted = 0
    return q if q and accepted == 1 else ""

rows = read_csv(INPUT)
wdrows = read_csv(WD)
if len(rows) != 3051:
    raise RuntimeError(f"Expected 3051 NAS science-core rows, got {len(rows)}")

wd_by_qid = {r["qid"]: r for r in wdrows if r.get("qid")}

out = []
for r in rows:
    exact = str(r.get("final_exact_dob") or "").strip()
    birth_year = exact[:4] if re.fullmatch(r"\d{4}-\d{2}-\d{2}", exact) else ""
    year_source = "final_exact_dob" if birth_year else ""
    year_conflict = 0

    if not birth_year:
        qid = reliable_qid(r)
        wr = wd_by_qid.get(qid, {}) if qid else {}
        vals = set()
        for col in (
            "exact_day_values",
            "month_precision_values",
            "year_precision_values",
            "direct_p569_values",
        ):
            vals |= year_values(wr.get(col, ""))
        if len(vals) == 1:
            birth_year = next(iter(vals))
            year_source = "wikidata_unique_birth_year"
        elif len(vals) > 1:
            year_conflict = 1

    try:
        ey = int(float(r.get("election_year") or ""))
    except Exception:
        ey = None
    decade = (ey // 10) * 10 if ey is not None else ""

    out.append({
        "profile_url": r.get("profile_url", ""),
        "name": r.get("name", ""),
        "election_year": r.get("election_year", ""),
        "election_decade": decade,
        "deceased": r.get("deceased", ""),
        "primary_section": r.get("primary_section", ""),
        "has_exact_dob": int(bool(exact)),
        "final_exact_dob": exact,
        "birth_year_known": int(bool(birth_year)),
        "birth_year": birth_year,
        "birth_year_source": year_source,
        "birth_year_conflict": year_conflict,
        "dob_status": r.get("dob_status", ""),
    })

write_csv(OUT_ROWS, out)

def aggregate(group_key):
    g = defaultdict(list)
    for r in out:
        g[r[group_key]].append(r)
    result = []
    for key, rr in sorted(g.items(), key=lambda kv: str(kv[0])):
        n = len(rr)
        exact = sum(x["has_exact_dob"] for x in rr)
        by = sum(x["birth_year_known"] for x in rr)
        living = sum(x["deceased"] != "Y" for x in rr)
        living_exact = sum(x["deceased"] != "Y" and x["has_exact_dob"] for x in rr)
        result.append({
            group_key: key,
            "n": n,
            "exact_dob_rows": exact,
            "exact_dob_coverage": round(exact / n, 6) if n else "",
            "birth_year_known_rows": by,
            "birth_year_coverage": round(by / n, 6) if n else "",
            "living_rows": living,
            "living_exact_dob_rows": living_exact,
            "living_exact_dob_coverage": round(living_exact / living, 6) if living else "",
        })
    return result

write_csv(OUT_DECADE, aggregate("election_decade"))
write_csv(OUT_SECTION, aggregate("primary_section"))

exact_n = sum(r["has_exact_dob"] for r in out)
birth_year_n = sum(r["birth_year_known"] for r in out)
unresolved = [r for r in out if not r["has_exact_dob"]]
unresolved_year = sum(r["birth_year_known"] for r in unresolved)
living = [r for r in out if r["deceased"] != "Y"]
dead = [r for r in out if r["deceased"] == "Y"]

summary = {
    "dataset": "NAS science-core DOB availability diagnostic v1",
    "science_core_rows": len(out),
    "exact_dob_rows": exact_n,
    "exact_dob_coverage": round(exact_n / len(out), 6),
    "birth_year_known_rows": birth_year_n,
    "birth_year_coverage": round(birth_year_n / len(out), 6),
    "rows_without_exact_dob": len(unresolved),
    "rows_without_exact_dob_but_unique_birth_year_known": unresolved_year,
    "rows_without_exact_dob_and_without_unique_birth_year": len(unresolved) - unresolved_year,
    "living_rows": len(living),
    "living_exact_dob_rows": sum(r["has_exact_dob"] for r in living),
    "living_exact_dob_coverage": round(sum(r["has_exact_dob"] for r in living) / len(living), 6),
    "living_birth_year_known_rows": sum(r["birth_year_known"] for r in living),
    "living_birth_year_coverage": round(sum(r["birth_year_known"] for r in living) / len(living), 6),
    "deceased_rows": len(dead),
    "deceased_exact_dob_rows": sum(r["has_exact_dob"] for r in dead),
    "deceased_exact_dob_coverage": round(sum(r["has_exact_dob"] for r in dead) / len(dead), 6),
    "birth_year_conflict_rows": sum(r["birth_year_conflict"] for r in out),
    "bazi_variables_computed": 0,
    "policy_note": (
        "Birth-year-only data are for support/missingness diagnostics only. "
        "They must not be used to compute BaZi variables. Exact DOB availability "
        "is assessed before any BaZi reveal."
    ),
}
OUT_SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(summary, ensure_ascii=False, indent=2))
