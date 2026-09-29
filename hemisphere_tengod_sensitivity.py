#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Hemisphere sensitivity analysis for the BaZi × Music project.

What it does
------------
1. Reads existing per-person occupation files for selected years.
2. Fetches Wikidata P19 (place of birth) for each person.
3. Fetches P625 coordinates for the P19 birthplace entity.
4. Classifies birthplace as north / south / equator / unknown.
5. Saves enriched per-person CSVs.
6. Reconstructs date-level Music counts for:
      - full sample
      - Northern-Hemisphere-only sample
7. Re-runs the same month-stem / month-order Ten-God analysis.
8. Writes per-year and pooled full-vs-north comparisons.

Default years are 1986-1989 so that the untouched 1990-1992 cohort is not
accidentally analyzed before you freeze/preregister any new hypotheses.

Network:
    Uses curl.exe through the proxy, matching the existing project workflow.

Example:
    python hemisphere_tengod_sensitivity.py --proxy http://127.0.0.1:10808 --years 1986 1987 1988 1989

After preregistration, if you explicitly want 1990-1992 too:
    python hemisphere_tengod_sensitivity.py --proxy http://127.0.0.1:10808 --years 1990 1991 1992
"""

import argparse
import json
import math
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlencode

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.stats.multitest import multipletests
from lunar_python import Solar


API = "https://www.wikidata.org/w/api.php"

STEM_ELEMENT = {
    "甲":"木","乙":"木","丙":"火","丁":"火","戊":"土","己":"土",
    "庚":"金","辛":"金","壬":"水","癸":"水",
}
STEM_POLARITY = {
    "甲":"阳","乙":"阴","丙":"阳","丁":"阴","戊":"阳","己":"阴",
    "庚":"阳","辛":"阴","壬":"阳","癸":"阴",
}
GENERATES = {"木":"火","火":"土","土":"金","金":"水","水":"木"}
CONTROLS = {"木":"土","土":"水","水":"火","火":"金","金":"木"}
BRANCH_MAIN_STEM = {
    "子":"癸","丑":"己","寅":"甲","卯":"乙","辰":"戊","巳":"丙",
    "午":"丁","未":"己","申":"庚","酉":"辛","戌":"戊","亥":"壬",
}
TEN_GODS = ["比肩","劫财","食神","伤官","偏财","正财","七杀","正官","偏印","正印"]


def ten_god(day_stem, other_stem):
    de, oe = STEM_ELEMENT[day_stem], STEM_ELEMENT[other_stem]
    same = STEM_POLARITY[day_stem] == STEM_POLARITY[other_stem]
    if oe == de:
        return "比肩" if same else "劫财"
    if GENERATES[de] == oe:
        return "食神" if same else "伤官"
    if CONTROLS[de] == oe:
        return "偏财" if same else "正财"
    if CONTROLS[oe] == de:
        return "七杀" if same else "正官"
    if GENERATES[oe] == de:
        return "偏印" if same else "正印"
    raise ValueError((day_stem, other_stem))


def eight_char_at(y, m, d, hour=12, minute=0):
    ec = Solar.fromYmdHms(y, m, d, hour, minute, 0).getLunar().getEightChar()
    return {
        "year": ec.getYear(),
        "month": ec.getMonth(),
        "day": ec.getDay(),
        "hour": ec.getTime(),
    }


def add_bazi_features(daily):
    rows = []
    for _, r in daily.iterrows():
        dt = pd.Timestamp(r["date"])
        y, m, d = dt.year, dt.month, dt.day

        noon = eight_char_at(y, m, d, 12, 0)
        early = eight_char_at(y, m, d, 0, 30)
        late = eight_char_at(y, m, d, 22, 30)

        transition = (
            early["year"] != late["year"]
            or early["month"] != late["month"]
        )

        mp = noon["month"]
        dp = noon["day"]
        ms, mb = mp[0], mp[1]
        ds = dp[0]
        main = BRANCH_MAIN_STEM[mb]

        rec = r.to_dict()
        rec.update({
            "year_pillar": noon["year"],
            "month_pillar": mp,
            "day_pillar": dp,
            "day_stem": ds,
            "month_stem": ms,
            "month_branch": mb,
            "month_main_stem": main,
            "month_stem_tengod": ten_god(ds, ms),
            "month_order_tengod": ten_god(ds, main),
            "pillar_transition_ambiguous": transition,
            "gregorian_year": y,
            "gregorian_month": m,
            "weekday": dt.day_name(),
        })
        rows.append(rec)
    return pd.DataFrame(rows)


def find_col(df, candidates):
    lower = {str(c).lower(): c for c in df.columns}
    for x in candidates:
        if x.lower() in lower:
            return lower[x.lower()]
    return None


def normalize_qid(v):
    if pd.isna(v):
        return None
    s = str(v).strip()
    if not s:
        return None
    if s.startswith("http"):
        s = s.rstrip("/").split("/")[-1]
    if s.startswith("Q") and s[1:].isdigit():
        return s
    return None


def detect_qid_col(df):
    c = find_col(df, [
        "qid", "person_qid", "wikidata_qid", "wikidata_id",
        "item", "person", "entity"
    ])
    if c:
        vals = df[c].map(normalize_qid)
        if vals.notna().mean() > 0.5:
            return c
    for c in df.columns:
        vals = df[c].map(normalize_qid)
        if vals.notna().mean() > 0.8:
            return c
    raise ValueError(
        "Could not detect a QID column. Columns are:\n" + ", ".join(map(str, df.columns))
    )


def detect_date_col(df):
    c = find_col(df, [
        "dob", "date", "birth_date", "birthdate",
        "date_of_birth", "birth_date_iso"
    ])
    if c:
        parsed = pd.to_datetime(df[c], errors="coerce")
        if parsed.notna().mean() > 0.5:
            return c
    for c in df.columns:
        if any(k in str(c).lower() for k in ["birth", "dob", "date"]):
            parsed = pd.to_datetime(df[c], errors="coerce")
            if parsed.notna().mean() > 0.8:
                return c
    raise ValueError(
        "Could not detect a birth-date column. Columns are:\n" + ", ".join(map(str, df.columns))
    )


def boolish_to_int(s):
    if pd.api.types.is_bool_dtype(s):
        return s.astype(int)
    if pd.api.types.is_numeric_dtype(s):
        vals = pd.to_numeric(s, errors="coerce")
        if set(vals.dropna().unique()).issubset({0, 1}):
            return vals.fillna(0).astype(int)
    txt = s.astype(str).str.strip().str.lower()
    if txt.isin(["true", "false", "1", "0", "yes", "no", "y", "n"]).mean() > 0.9:
        return txt.isin(["true", "1", "yes", "y"]).astype(int)
    return None


def detect_music_indicator(df):
    # Best case: direct category flag.
    for name in [
        "Music", "music", "is_music", "music_flag", "Music_flag",
        "Music__flag", "category_music", "broad_music"
    ]:
        if name in df.columns:
            out = boolish_to_int(df[name])
            if out is not None:
                return out, name

    # Category-list style columns.
    category_cols = [
        c for c in df.columns
        if any(k in str(c).lower() for k in ["categor", "broad", "group"])
    ]
    for c in category_cols:
        txt = df[c].fillna("").astype(str)
        hit = txt.str.contains(r"(^|[^A-Za-z])Music([^A-Za-z]|$)", case=False, regex=True)
        # Require at least a few hits so we don't accidentally use a useless column.
        if int(hit.sum()) >= 3:
            return hit.astype(int), c

    raise ValueError(
        "Could not detect individual-level Music classification.\n"
        "Please inspect the source CSV and rerun with --music-column COLUMN_NAME.\n"
        "Available columns:\n" + ", ".join(map(str, df.columns))
    )


def music_indicator_from_column(df, col):
    if col not in df.columns:
        raise ValueError(f"--music-column {col!r} not found in CSV.")
    b = boolish_to_int(df[col])
    if b is not None:
        return b
    txt = df[col].fillna("").astype(str)
    return txt.str.contains(r"(^|[^A-Za-z])Music([^A-Za-z]|$)", case=False, regex=True).astype(int)


def curl_json(url, proxy, retries=5, sleep=1.5):
    cmd = [
        "curl.exe",
        "-x", proxy,
        "-L",
        "--fail",
        "--silent",
        "--show-error",
        "--connect-timeout", "20",
        "--max-time", "90",
        url,
    ]
    last = None
    for i in range(retries):
        p = subprocess.run(cmd, capture_output=True, text=True)
        if p.returncode == 0:
            try:
                return json.loads(p.stdout)
            except Exception as e:
                last = f"JSON parse failed: {e}"
        else:
            last = p.stderr.strip() or f"curl exit={p.returncode}"
        time.sleep(sleep * (i + 1))
    raise RuntimeError(f"curl failed after {retries} attempts: {last}\nURL={url[:250]}")


def wbgetentities(ids, props, proxy, languages="en"):
    if not ids:
        return {}
    params = {
        "action": "wbgetentities",
        "ids": "|".join(ids),
        "props": props,
        "format": "json",
        "formatversion": "2",
    }
    if "labels" in props:
        params["languages"] = languages
    url = API + "?" + urlencode(params)
    obj = curl_json(url, proxy)
    entities = obj.get("entities", {})
    if isinstance(entities, list):
        return {e.get("id"): e for e in entities if e.get("id")}
    return entities


def claim_entity_id(ent, prop):
    try:
        claims = ent.get("claims", {}).get(prop, [])
        for claim in claims:
            snak = claim.get("mainsnak", {})
            dv = snak.get("datavalue", {})
            value = dv.get("value")
            if isinstance(value, dict) and value.get("id"):
                return value["id"]
    except Exception:
        pass
    return None


def claim_coordinate(ent, prop="P625"):
    try:
        claims = ent.get("claims", {}).get(prop, [])
        for claim in claims:
            snak = claim.get("mainsnak", {})
            dv = snak.get("datavalue", {})
            value = dv.get("value")
            if isinstance(value, dict) and "latitude" in value and "longitude" in value:
                return float(value["latitude"]), float(value["longitude"])
    except Exception:
        pass
    return None, None


def english_label(ent):
    try:
        labels = ent.get("labels", {})
        if "en" in labels:
            return labels["en"].get("value", "")
    except Exception:
        pass
    return ""


def load_cache(path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_cache(path, obj):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def chunks(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i+n]


def fetch_person_birthplaces(qids, proxy, cache_dir, batch_size=50, pause=0.8):
    cache_path = cache_dir / "person_p19.json"
    cache = load_cache(cache_path)

    missing = [q for q in qids if q not in cache]
    print(f"  P19 cache: {len(qids)-len(missing):,} known, {len(missing):,} to fetch")

    for bi, batch in enumerate(chunks(missing, batch_size), 1):
        ents = wbgetentities(batch, "claims", proxy)
        for q in batch:
            ent = ents.get(q, {})
            cache[q] = claim_entity_id(ent, "P19")
        save_cache(cache_path, cache)
        if bi % 10 == 0 or bi == 1:
            print(f"    P19 batches: {bi}/{math.ceil(len(missing)/batch_size) if missing else 0}")
        time.sleep(pause)

    return cache


def fetch_place_coordinates(place_qids, proxy, cache_dir, batch_size=50, pause=0.8):
    cache_path = cache_dir / "place_p625.json"
    cache = load_cache(cache_path)

    missing = [q for q in place_qids if q and q not in cache]
    print(f"  P625 cache: {len(place_qids)-len(missing):,} known, {len(missing):,} to fetch")

    for bi, batch in enumerate(chunks(missing, batch_size), 1):
        ents = wbgetentities(batch, "claims|labels", proxy)
        for q in batch:
            ent = ents.get(q, {})
            lat, lon = claim_coordinate(ent, "P625")
            cache[q] = {
                "label": english_label(ent),
                "lat": lat,
                "lon": lon,
            }
        save_cache(cache_path, cache)
        if bi % 10 == 0 or bi == 1:
            print(f"    P625 batches: {bi}/{math.ceil(len(missing)/batch_size) if missing else 0}")
        time.sleep(pause)

    return cache


def hemisphere_from_lat(lat):
    if lat is None or (isinstance(lat, float) and np.isnan(lat)):
        return "unknown"
    lat = float(lat)
    if lat > 0:
        return "north"
    if lat < 0:
        return "south"
    return "equator"


def source_file_for_year(root, year):
    candidates = [
        root / f"occupation_scan_{year}" / f"{year}_people_with_occupations.csv",
        root / f"occupation_scan_{year}" / f"{year}_people_occupations.csv",
        root / f"occupation_scan_{year}" / f"{year}_people.csv",
    ]
    for p in candidates:
        if p.exists():
            return p
    raise FileNotFoundError(
        f"No per-person occupation file found for {year}.\nTried:\n" +
        "\n".join(str(x) for x in candidates)
    )


def enrich_year(root, year, proxy, cache_dir, batch_size, pause, music_column=None):
    src = source_file_for_year(root, year)
    print(f"\n[{year}] source: {src}")

    df = pd.read_csv(src)
    qcol = detect_qid_col(df)
    dcol = detect_date_col(df)

    if music_column:
        music = music_indicator_from_column(df, music_column)
        music_source = music_column
    else:
        music, music_source = detect_music_indicator(df)

    print(f"  QID column: {qcol}")
    print(f"  Date column: {dcol}")
    print(f"  Music classification source: {music_source}")

    qids = df[qcol].map(normalize_qid)
    if qids.isna().any():
        bad = int(qids.isna().sum())
        print(f"  WARNING: {bad} rows have unrecognized QIDs; birthplace will be unknown.")

    unique_qids = sorted(qids.dropna().unique().tolist())
    p19 = fetch_person_birthplaces(
        unique_qids, proxy, cache_dir, batch_size=batch_size, pause=pause
    )
    places = sorted({v for v in p19.values() if v})
    p625 = fetch_place_coordinates(
        places, proxy, cache_dir, batch_size=batch_size, pause=pause
    )

    out = df.copy()
    out["_qid_norm"] = qids
    out["_birth_date_norm"] = pd.to_datetime(out[dcol], errors="coerce").dt.strftime("%Y-%m-%d")
    out["_music"] = music.astype(int)

    out["birthplace_qid"] = out["_qid_norm"].map(p19)
    out["birthplace_label"] = out["birthplace_qid"].map(
        lambda q: (p625.get(q) or {}).get("label", "") if q else ""
    )
    out["birth_lat"] = out["birthplace_qid"].map(
        lambda q: (p625.get(q) or {}).get("lat") if q else None
    )
    out["birth_lon"] = out["birthplace_qid"].map(
        lambda q: (p625.get(q) or {}).get("lon") if q else None
    )
    out["hemisphere"] = out["birth_lat"].map(hemisphere_from_lat)

    outdir = root / f"hemisphere_{year}"
    outdir.mkdir(parents=True, exist_ok=True)
    outpath = outdir / f"{year}_people_with_hemisphere.csv"
    out.to_csv(outpath, index=False, encoding="utf-8-sig")

    counts = out["hemisphere"].value_counts(dropna=False)
    report = [
        f"Hemisphere enrichment — {year}",
        f"source={src}",
        f"rows={len(out):,}",
        f"qid_column={qcol}",
        f"date_column={dcol}",
        f"music_source={music_source}",
        "",
    ]
    for key in ["north", "south", "equator", "unknown"]:
        report.append(f"{key}: {int(counts.get(key, 0)):,} ({100*counts.get(key,0)/len(out):.2f}%)")
    (outdir / f"{year}_hemisphere_coverage.txt").write_text(
        "\n".join(report), encoding="utf-8"
    )
    print("\n".join("  " + x for x in report[-4:]))

    return out


def daily_from_people(df, scope):
    x = df.copy()
    if scope == "north":
        x = x.loc[x["hemisphere"] == "north"].copy()
    elif scope == "south":
        x = x.loc[x["hemisphere"] == "south"].copy()
    elif scope == "known_non_south":
        x = x.loc[x["hemisphere"].isin(["north", "equator"])].copy()
    elif scope == "full":
        pass
    else:
        raise ValueError(scope)

    x = x.loc[x["_birth_date_norm"].notna()].copy()
    d = (
        x.groupby("_birth_date_norm", as_index=False)
        .agg(n_people=("_qid_norm", "size"), Music__n=("_music", "sum"))
        .rename(columns={"_birth_date_norm": "date"})
    )
    d["date"] = pd.to_datetime(d["date"])
    return d


def design_matrix(d, feature, pooled=False):
    X = pd.DataFrame(index=d.index)
    X[feature] = pd.to_numeric(d[feature]).astype(float)

    md = pd.get_dummies(
        d["gregorian_month"].astype("category"),
        prefix="month", drop_first=True, dtype=float
    )
    wd = pd.get_dummies(
        d["weekday"].astype("category"),
        prefix="weekday", drop_first=True, dtype=float
    )
    parts = [X, md, wd]

    if pooled:
        yd = pd.get_dummies(
            d["gregorian_year"].astype("category"),
            prefix="year", drop_first=True, dtype=float
        )
        parts.append(yd)

    X = pd.concat(parts, axis=1)
    return sm.add_constant(X, has_constant="add").astype(float)


def fit_binary(d, feature, pooled=False):
    mask = d[feature].astype(bool)
    n1 = int(d.loc[mask, "n_people"].sum())
    y1 = int(d.loc[mask, "Music__n"].sum())
    n0 = int(d.loc[~mask, "n_people"].sum())
    y0 = int(d.loc[~mask, "Music__n"].sum())

    if n1 == 0 or n0 == 0:
        return None

    y = np.column_stack([
        d["Music__n"].to_numpy(float),
        (d["n_people"] - d["Music__n"]).to_numpy(float),
    ])
    fit = sm.GLM(
        y, design_matrix(d, feature, pooled=pooled),
        family=sm.families.Binomial(),
    ).fit(cov_type="HC0", maxiter=200)

    beta = float(fit.params[feature])
    se = float(fit.bse[feature])
    p2 = float(fit.pvalues[feature])
    p1 = p2/2 if beta >= 0 else 1-p2/2

    return {
        "feature": feature,
        "feature_people": n1,
        "feature_music": y1,
        "feature_music_rate": y1/n1,
        "nonfeature_people": n0,
        "nonfeature_music": y0,
        "nonfeature_music_rate": y0/n0,
        "risk_ratio": (y1/n1)/(y0/n0) if y0 else np.nan,
        "adjusted_or": math.exp(beta),
        "ci95_low": math.exp(beta-1.96*se),
        "ci95_high": math.exp(beta+1.96*se),
        "glm_one_sided_p": p1,
        "glm_two_sided_p": p2,
    }


def run_all20(d, pooled=False):
    work = d.copy()
    out = []
    for loc, col in [
        ("month_stem", "month_stem_tengod"),
        ("month_order", "month_order_tengod"),
    ]:
        for tg in TEN_GODS:
            f = f"feature__{loc}__{tg}"
            work[f] = (work[col] == tg).astype(int)
            r = fit_binary(work, f, pooled=pooled)
            if r is None:
                continue
            r["location"] = loc
            r["ten_god"] = tg
            out.append(r)
    z = pd.DataFrame(out)
    if len(z):
        z["bh_q_all20"] = multipletests(
            z["glm_one_sided_p"], alpha=0.05, method="fdr_bh"
        )[1]
    return z


def analyze_scope(daily, year, scope, outdir):
    f = add_bazi_features(daily)
    f = f.loc[~f["pillar_transition_ambiguous"]].copy()

    tests = run_all20(f, pooled=False)
    tests["year"] = year
    tests["scope"] = scope

    tests.to_csv(
        outdir / f"{year}_{scope}_all20_tengod_tests.csv",
        index=False, encoding="utf-8-sig"
    )
    f.to_csv(
        outdir / f"{year}_{scope}_daily_bazi.csv",
        index=False, encoding="utf-8-sig"
    )
    return tests, f


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--proxy", default="http://127.0.0.1:10808")
    ap.add_argument("--years", nargs="+", type=int, default=[1986,1987,1988,1989])
    ap.add_argument("--batch-size", type=int, default=50)
    ap.add_argument("--pause", type=float, default=0.8)
    ap.add_argument("--music-column", default=None)
    ap.add_argument("--fetch-only", action="store_true",
                    help="Only add P19/P625/hemisphere; do not run Ten-God stats.")
    args = ap.parse_args()

    root = Path(".").resolve()
    cache_dir = root / "hemisphere_cache"
    cache_dir.mkdir(exist_ok=True)
    result_dir = root / "hemisphere_sensitivity_results"
    result_dir.mkdir(exist_ok=True)

    people_by_year = {}
    for year in args.years:
        people_by_year[year] = enrich_year(
            root, year, args.proxy, cache_dir,
            batch_size=args.batch_size,
            pause=args.pause,
            music_column=args.music_column,
        )

    if args.fetch_only:
        print("\nFetch-only complete. No Ten-God outcome analysis was run.")
        return

    all_test_rows = []
    pooled_daily = {"full": [], "north": []}

    for year, people in people_by_year.items():
        yout = result_dir / str(year)
        yout.mkdir(parents=True, exist_ok=True)

        for scope in ["full", "north"]:
            daily = daily_from_people(people, scope)
            tests, featured = analyze_scope(daily, year, scope, yout)
            all_test_rows.append(tests)
            pooled_daily[scope].append(daily)

        # South/unknown are reported descriptively only.
        hemi_counts = people.groupby("hemisphere").agg(
            people=("_qid_norm","size"),
            music=("_music","sum")
        ).reset_index()
        hemi_counts["music_rate"] = hemi_counts["music"] / hemi_counts["people"]
        hemi_counts.to_csv(
            yout / f"{year}_hemisphere_descriptive_counts.csv",
            index=False, encoding="utf-8-sig"
        )

    alltests = pd.concat(all_test_rows, ignore_index=True)
    alltests.to_csv(
        result_dir / "year_scope_all20_long.csv",
        index=False, encoding="utf-8-sig"
    )

    # Full vs north comparison by year.
    piv = alltests.pivot_table(
        index=["year","location","ten_god"],
        columns="scope",
        values=["adjusted_or","glm_one_sided_p","bh_q_all20"],
        aggfunc="first",
    )
    piv.columns = ["_".join(map(str,c)) for c in piv.columns]
    comp = piv.reset_index()
    if "adjusted_or_full" in comp.columns and "adjusted_or_north" in comp.columns:
        comp["north_minus_full_logOR"] = (
            np.log(comp["adjusted_or_north"]) - np.log(comp["adjusted_or_full"])
        )
    comp.to_csv(
        result_dir / "full_vs_north_by_year.csv",
        index=False, encoding="utf-8-sig"
    )

    # Pooled analysis across selected years.
    pooled_rows = []
    for scope in ["full", "north"]:
        daily = pd.concat(pooled_daily[scope], ignore_index=True)
        feat = add_bazi_features(daily)
        feat = feat.loc[~feat["pillar_transition_ambiguous"]].copy()
        tests = run_all20(feat, pooled=True)
        tests["scope"] = scope
        pooled_rows.append(tests)

    pooled = pd.concat(pooled_rows, ignore_index=True)
    pooled.to_csv(
        result_dir / "pooled_full_vs_north_all20.csv",
        index=False, encoding="utf-8-sig"
    )

    # Human-readable summary.
    lines = [
        "Hemisphere sensitivity — Ten-God × Music",
        f"Years: {', '.join(map(str,args.years))}",
        "",
        "Interpretation:",
        "  full  = all eligible people, including south and unknown birthplace.",
        "  north = only people whose P19 birthplace has P625 latitude > 0.",
        "  Missing P19/P625 is NOT silently treated as north.",
        "",
        "POOLED FULL VS NORTH:",
    ]

    pf = pooled.loc[pooled["scope"]=="full"].set_index(["location","ten_god"])
    pn = pooled.loc[pooled["scope"]=="north"].set_index(["location","ten_god"])
    common = pf.index.intersection(pn.index)

    rows = []
    for idx in common:
        rf = pf.loc[idx]
        rn = pn.loc[idx]
        rows.append((
            idx[0], idx[1],
            float(rf["adjusted_or"]), float(rn["adjusted_or"]),
            float(rf["glm_one_sided_p"]), float(rn["glm_one_sided_p"]),
            float(rf["bh_q_all20"]), float(rn["bh_q_all20"]),
        ))
    rows.sort(key=lambda x: x[3], reverse=True)

    for loc,tg,orf,orn,pf1,pn1,qf,qn in rows:
        lines.append(
            f"  {loc} {tg}: full OR={orf:.3f}, north OR={orn:.3f}, "
            f"full p1={pf1:.4g}, north p1={pn1:.4g}, "
            f"full q={qf:.4g}, north q={qn:.4g}"
        )

    lines += [
        "",
        "Guardrail:",
        "  This is a sensitivity analysis for already-inspected cohorts.",
        "  Do not reinterpret it as a new preregistered confirmatory test.",
    ]

    summary = result_dir / "hemisphere_sensitivity_summary.txt"
    summary.write_text("\n".join(lines), encoding="utf-8")
    print("\n" + "\n".join(lines))
    print(f"\nSaved under: {result_dir}")


if __name__ == "__main__":
    main()
