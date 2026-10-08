#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import importlib.metadata
import json
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
from lunar_python import Solar

INPUT = Path("data/nas_science_core_dob_crosswalk/nas_science_core_dob_crosswalk_v16.csv")
TT_REFERENCE = Path("studies/table_tennis/data/tabletennis_reference_enriched.csv")
OUTDIR = Path("data/nas_bazi_features_v1")
OUT = OUTDIR / "nas_science_core_bazi_features_v1.csv"
BOUNDARY = OUTDIR / "nas_bazi_boundary_cases_v1.csv"
SUMMARY = OUTDIR / "summary_nas_bazi_features_v1.json"

EXPECTED_INPUT_SHA256 = "f577b22bf646b4b5355a133cc265d4d9ccf253f501bac98b6afddce874fc4561"

GAN_ELEMENT = {
    "甲":"木","乙":"木","丙":"火","丁":"火","戊":"土","己":"土",
    "庚":"金","辛":"金","壬":"水","癸":"水",
}
GAN_POLARITY = {
    "甲":"阳","乙":"阴","丙":"阳","丁":"阴","戊":"阳","己":"阴",
    "庚":"阳","辛":"阴","壬":"阳","癸":"阴",
}
GENERATES = {"木":"火","火":"土","土":"金","金":"水","水":"木"}
CONTROLS = {"木":"土","土":"水","水":"火","火":"金","金":"木"}

BRANCH_MAIN_GAN = {
    "子":"癸","丑":"己","寅":"甲","卯":"乙","辰":"戊","巳":"丙",
    "午":"丁","未":"己","申":"庚","酉":"辛","戌":"戊","亥":"壬",
}
TEN_GODS = ["比肩","劫财","食神","伤官","偏财","正财","七杀","正官","偏印","正印"]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def present(v) -> bool:
    return str(v or "").strip() not in ("", "nan", "None")


def ten_god(day_gan: str, target_gan: str) -> str:
    de = GAN_ELEMENT[day_gan]
    te = GAN_ELEMENT[target_gan]
    same = GAN_POLARITY[day_gan] == GAN_POLARITY[target_gan]

    if te == de:
        return "比肩" if same else "劫财"
    if GENERATES[de] == te:
        return "食神" if same else "伤官"
    if CONTROLS[de] == te:
        return "偏财" if same else "正财"
    if CONTROLS[te] == de:
        return "七杀" if same else "正官"
    if GENERATES[te] == de:
        return "偏印" if same else "正印"
    raise RuntimeError((day_gan, target_gan))


def pillars(y: int, m: int, d: int, hour: int = 12, minute: int = 0):
    ec = Solar.fromYmdHms(int(y), int(m), int(d), int(hour), int(minute), 0).getLunar().getEightChar()
    return {
        "year": ec.getYear(),
        "month": ec.getMonth(),
        "day": ec.getDay(),
    }


def parts(p: str):
    p = str(p).strip()
    if len(p) < 2:
        raise ValueError(f"Bad pillar: {p!r}")
    return p[0], p[1]


def validate_against_table_tennis():
    if not TT_REFERENCE.exists():
        raise RuntimeError(f"Missing validation file: {TT_REFERENCE}")

    tt = pd.read_csv(TT_REFERENCE, encoding="utf-8-sig")
    required = {
        "dob","year_pillar","month_pillar","day_pillar",
        "year_stem_tg","month_stem_tg","month_order_tg","month_main_stem"
    }
    missing = sorted(required - set(tt.columns))
    if missing:
        raise RuntimeError(f"TT validation missing columns: {missing}")

    pillar_mismatches = []
    tengod_mismatches = []

    for i, r in tt.iterrows():
        dt = pd.Timestamp(r["dob"])
        p = pillars(dt.year, dt.month, dt.day, 12, 0)

        expected = {
            "year_pillar": str(r["year_pillar"]),
            "month_pillar": str(r["month_pillar"]),
            "day_pillar": str(r["day_pillar"]),
        }
        got = {
            "year_pillar": p["year"],
            "month_pillar": p["month"],
            "day_pillar": p["day"],
        }
        if got != expected:
            pillar_mismatches.append({
                "row": int(i), "name": r.get("name",""), "dob": str(r["dob"]),
                "expected": expected, "got": got
            })
            continue

        yg, yz = parts(p["year"])
        mg, mz = parts(p["month"])
        dg, dz = parts(p["day"])
        mm = BRANCH_MAIN_GAN[mz]

        tg_expected = {
            "year_stem_tg": str(r["year_stem_tg"]),
            "month_stem_tg": str(r["month_stem_tg"]),
            "month_order_tg": str(r["month_order_tg"]),
            "month_main_stem": str(r["month_main_stem"]),
        }
        tg_got = {
            "year_stem_tg": ten_god(dg, yg),
            "month_stem_tg": ten_god(dg, mg),
            "month_order_tg": ten_god(dg, mm),
            "month_main_stem": mm,
        }
        if tg_got != tg_expected:
            tengod_mismatches.append({
                "row": int(i), "name": r.get("name",""), "dob": str(r["dob"]),
                "expected": tg_expected, "got": tg_got
            })

    if pillar_mismatches or tengod_mismatches:
        raise RuntimeError(
            "Project-consistency validation failed: "
            f"pillar_mismatches={len(pillar_mismatches)}, "
            f"tengod_mismatches={len(tengod_mismatches)}; "
            f"pillar_examples={pillar_mismatches[:3]}; "
            f"tengod_examples={tengod_mismatches[:3]}"
        )

    return {
        "validation_rows": int(len(tt)),
        "pillar_mismatches": 0,
        "tengod_mismatches": 0,
    }


def boundary_flags(dt: date):
    y, m, d = dt.year, dt.month, dt.day

    early = pillars(y, m, d, 0, 30)
    late = pillars(y, m, d, 22, 30)
    noon = pillars(y, m, d, 12, 0)

    prev = dt - timedelta(days=1)
    nxt = dt + timedelta(days=1)
    pprev = pillars(prev.year, prev.month, prev.day, 12, 0)
    pnext = pillars(nxt.year, nxt.month, nxt.day, 12, 0)

    same_date_year_transition = int(early["year"] != late["year"])
    same_date_month_transition = int(early["month"] != late["month"])

    year_pm1 = int(
        pprev["year"] != noon["year"] or
        noon["year"] != pnext["year"]
    )
    month_pm1 = int(
        pprev["month"] != noon["month"] or
        noon["month"] != pnext["month"]
    )

    return {
        "same_date_year_transition": same_date_year_transition,
        "same_date_month_transition": same_date_month_transition,
        "year_boundary_pm1": year_pm1,
        "month_boundary_pm1": month_pm1,
        "year_or_month_boundary_pm1": int(year_pm1 or month_pm1),
    }


def feature_row(r):
    dob = str(r.get("final_exact_dob") or "").strip()
    dt = date.fromisoformat(dob)
    p = pillars(dt.year, dt.month, dt.day, 12, 0)

    yg, yz = parts(p["year"])
    mg, mz = parts(p["month"])
    dg, dz = parts(p["day"])

    ym = BRANCH_MAIN_GAN[yz]
    mm = BRANCH_MAIN_GAN[mz]
    dm = BRANCH_MAIN_GAN[dz]

    position_tg = {
        "year_stem_tengod": ten_god(dg, yg),
        "month_stem_tengod": ten_god(dg, mg),
        "year_branch_main_tengod": ten_god(dg, ym),
        "month_branch_main_tengod": ten_god(dg, mm),
        "day_branch_main_tengod": ten_god(dg, dm),
    }
    five = list(position_tg.values())
    counts = Counter(five)

    out = {
        "profile_url": r.get("profile_url",""),
        "name": r.get("name",""),
        "final_exact_dob": dob,
        "election_year": r.get("election_year",""),
        "deceased": r.get("deceased",""),
        "primary_section": r.get("primary_section",""),
        "affiliation": r.get("affiliation",""),
        "dob_status": r.get("dob_status",""),
        "year_pillar": p["year"],
        "month_pillar": p["month"],
        "day_pillar": p["day"],
        "year_stem": yg,
        "year_branch": yz,
        "month_stem": mg,
        "month_branch": mz,
        "day_stem": dg,
        "day_branch": dz,
        "day_master": dg,
        "day_master_element": GAN_ELEMENT[dg],
        "day_master_polarity": GAN_POLARITY[dg],
        "year_branch_main_stem": ym,
        "month_branch_main_stem": mm,
        "day_branch_main_stem": dm,
        **position_tg,
        "month_order_tengod": position_tg["month_branch_main_tengod"],
    }
    for tg in TEN_GODS:
        out[f"fivepos_count_{tg}"] = int(counts.get(tg, 0))
        out[f"fivepos_present_{tg}"] = int(counts.get(tg, 0) > 0)

    out.update(boundary_flags(dt))
    return out


def main():
    OUTDIR.mkdir(parents=True, exist_ok=True)

    if not INPUT.exists():
        raise RuntimeError(f"Missing frozen v16 input: {INPUT}")

    input_sha = sha256(INPUT)
    if input_sha != EXPECTED_INPUT_SHA256:
        raise RuntimeError(
            f"v16 SHA mismatch: got {input_sha}, expected {EXPECTED_INPUT_SHA256}"
        )

    validation = validate_against_table_tennis()

    df = pd.read_csv(INPUT, encoding="utf-8-sig")
    if len(df) != 3051:
        raise RuntimeError(f"Expected 3051 NAS rows, got {len(df)}")

    exact = df[df["final_exact_dob"].apply(present)].copy()
    if len(exact) != 2238:
        raise RuntimeError(f"Expected 2238 exact-DOB rows, got {len(exact)}")

    rows = [feature_row(r) for _, r in exact.iterrows()]
    out = pd.DataFrame(rows)

    for tg in TEN_GODS:
        col = f"fivepos_count_{tg}"
        if not out[col].between(0,5).all():
            raise RuntimeError(f"Bad count range in {col}")

    count_cols = [f"fivepos_count_{tg}" for tg in TEN_GODS]
    if not (out[count_cols].sum(axis=1) == 5).all():
        raise RuntimeError("Five-position Ten-God counts do not sum to 5")

    if out["final_exact_dob"].duplicated().all():
        raise RuntimeError("Unexpected DOB duplication invariant failure")

    out.to_csv(OUT, index=False, encoding="utf-8-sig")

    boundary = out.loc[
        out["year_or_month_boundary_pm1"] == 1,
        [
            "profile_url","name","final_exact_dob","year_pillar","month_pillar",
            "same_date_year_transition","same_date_month_transition",
            "year_boundary_pm1","month_boundary_pm1","year_or_month_boundary_pm1",
        ],
    ].copy()
    boundary.to_csv(BOUNDARY, index=False, encoding="utf-8-sig")

    lib_version = importlib.metadata.version("lunar-python")

    summary = {
        "dataset": "NAS science-core BaZi mechanical feature derivation v1",
        "input": str(INPUT),
        "input_sha256": input_sha,
        "input_rows": int(len(df)),
        "exact_dob_rows_transformed": int(len(out)),
        "unresolved_rows_not_transformed": int(len(df) - len(out)),
        "lunar_python_version": lib_version,
        "table_tennis_project_consistency_validation": validation,
        "same_date_year_transition_rows": int(out["same_date_year_transition"].sum()),
        "same_date_month_transition_rows": int(out["same_date_month_transition"].sum()),
        "year_boundary_pm1_rows": int(out["year_boundary_pm1"].sum()),
        "month_boundary_pm1_rows": int(out["month_boundary_pm1"].sum()),
        "year_or_month_boundary_pm1_rows": int(out["year_or_month_boundary_pm1"].sum()),
        "primary_feature_definition": {
            "month_order_tengod": "day master relative to month-branch main qi",
            "five_positions": [
                "year stem",
                "month stem",
                "year-branch main qi",
                "month-branch main qi",
                "day-branch main qi"
            ],
            "hour_pillar_used": False,
            "hidden_stem_expansion_used": False
        },
        "output_csv_sha256": sha256(OUT),
        "boundary_csv_sha256": sha256(BOUNDARY),
        "bazi_variables_computed": int(len(out)),
        "inference_performed": False,
        "note": "Mechanical transformation only. No frequency, enrichment, p-value, or hypothesis test is computed in this step."
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
