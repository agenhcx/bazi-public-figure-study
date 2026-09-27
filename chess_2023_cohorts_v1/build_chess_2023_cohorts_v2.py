#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
build_chess_2023_cohorts_v2.py

PRE-REVEAL cohort builder. DOES NOT calculate BaZi.

It:
1) obtains/parses the official January-2023 FIDE standard rating list;
2) identifies active male/female players and standard Elo;
3) reuses the already-frozen Wikidata identity/DOB/birthplace logic from
   chess_north_v2/build_chess_northern_cohorts_v1.py;
4) constructs:
     FULL              = Top500M / Top200F eligible + cutoff ties
     NEW_WITHIN_FULL   = FULL minus all 1994/2013 frozen FIDE IDs
     NEW_TARGET        = scan farther until 500M / 200F unseen eligible + ties
5) prints the FULL and NEW_TARGET Elo cutoffs BEFORE any BaZi reveal.

Run only AFTER tag chess-2023-validation-plan-v2 exists.

Typical:
    python build_chess_2023_cohorts_v2.py --repo ..\1986wiki

If automatic January-2023 FIDE archive download fails, provide:
    --fide-zip PATH_TO_jan23frl.zip
or
    --fide-txt PATH_TO_UNZIPPED_FIDE_LIST.txt
"""

from __future__ import annotations

import argparse
import importlib.util
import io
import json
import re
import shutil
import subprocess
import time
import zipfile
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import requests

SNAPSHOT = "2023-01-01"
TARGET = {"M": 500, "F": 200}
REQUIRED_PLAN_TAG = "chess-2023-validation-plan-v2"

# Historical FIDE archives have used month-year FRL names.
# Try several conservative candidates, then require an explicit local file.
ARCHIVE_URLS = [
    "https://ratings.fide.com/download/standard_jan23frl.zip",
    "http://ratings.fide.com/download/standard_jan23frl.zip",
]

UA = "chess-bazi-study/2023-pre-reveal-cohort-builder"


def run(cmd, cwd, check=True):
    print("$", " ".join(cmd))
    p = subprocess.run(
        cmd, cwd=str(cwd), text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT
    )
    if p.stdout:
        print(p.stdout.rstrip())
    if check and p.returncode != 0:
        raise RuntimeError("Command failed: " + " ".join(cmd))
    return p.stdout.strip()


def git_root(p: Path) -> Path:
    return Path(run(["git", "rev-parse", "--show-toplevel"], p)).resolve()


def import_north_v2(repo: Path):
    p = repo / "chess_north_v2" / "build_chess_northern_cohorts_v1.py"
    if not p.exists():
        raise FileNotFoundError(
            f"Required prior builder not found: {p}\n"
            "This script intentionally reuses its already-audited Wikidata logic."
        )
    spec = importlib.util.spec_from_file_location("northv2", p)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def download_archive(out: Path, proxy: str | None, timeout: int) -> Path:
    s = requests.Session()
    s.headers.update({"User-Agent": UA})
    if proxy:
        s.proxies.update({"http": proxy, "https": proxy})
    else:
        s.trust_env = False

    errors = []
    for url in ARCHIVE_URLS:
        try:
            print("[FIDE] try", url)
            r = s.get(url, timeout=timeout, allow_redirects=True)
            r.raise_for_status()
            b = r.content
            if len(b) < 10000 or not b.startswith(b"PK"):
                raise RuntimeError(
                    f"response is not a plausible ZIP ({len(b)} bytes)"
                )
            out.write_bytes(b)
            print("[FIDE] downloaded", out, f"({len(b):,} bytes)")
            return out
        except Exception as e:
            errors.append(f"{url}: {type(e).__name__}: {e}")

    raise RuntimeError(
        "Automatic January-2023 FIDE archive download failed.\n"
        "Download the January 2023 standard/FRL list manually from FIDE and rerun "
        "with --fide-zip or --fide-txt.\n\n" + "\n".join(errors)
    )


def extract_txt_from_zip(zpath: Path, outdir: Path) -> Path:
    with zipfile.ZipFile(zpath) as z:
        names = [
            n for n in z.namelist()
            if n.lower().endswith((".txt", ".lst"))
            and not n.endswith("/")
        ]
        if not names:
            raise RuntimeError(
                f"No .txt/.lst file in {zpath}; members={z.namelist()[:20]}"
            )
        # Prefer largest text member: monthly FRL ZIPs normally contain one.
        infos = sorted(
            (z.getinfo(n) for n in names),
            key=lambda x: x.file_size,
            reverse=True
        )
        info = infos[0]
        out = outdir / Path(info.filename).name
        out.write_bytes(z.read(info.filename))
        print("[FIDE] extracted", out, f"({info.file_size:,} bytes)")
        return out


def decode_text(path: Path) -> str:
    raw = path.read_bytes()
    for enc in ["utf-8-sig", "latin-1", "cp1252"]:
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            pass
    return raw.decode("latin-1", errors="replace")


def infer_fixed_width_columns(header: str):
    """
    Infer fixed-width column starts from the actual FIDE header.

    January 2023 standard list uses:
        ID Number ... FOA JAN23 Gms K B-day Flag

    The rating column is month-labelled (JAN23), not SRtng.
    Gms and K MUST be included as delimiters or the rating field will swallow
    those values and become non-numeric.
    """
    labels = [
        ("fide_id", r"ID\s*Number"),
        ("name", r"Name"),
        ("fed", r"Fed"),
        ("sex", r"Sex"),
        ("title", r"(?<!W)(?<!O)Tit"),
        ("wtitle", r"WTit"),
        ("otitle", r"OTit"),
        ("foa", r"FOA"),
        ("rating", r"(?:SRtng|[A-Z]{3}\d{2})"),
        ("games", r"Gms"),
        ("kfactor", r"(?<!\S)K(?=\s|$)"),
        ("birth_year", r"B-day|BORN"),
        ("flag", r"Flag"),
    ]

    found = []
    cursor = 0
    for key, pat in labels:
        m = re.search(pat, header[cursor:], flags=re.I)
        if not m:
            continue
        start = cursor + m.start()
        found.append((key, start))
        cursor = start + max(1, len(m.group(0)))

    keys = {k for k, _ in found}
    required = {
        "fide_id", "name", "fed", "sex",
        "rating", "games", "kfactor",
        "birth_year", "flag",
    }
    if not required.issubset(keys):
        raise RuntimeError(
            "Could not infer FIDE fixed-width header.\n"
            f"Header: {header!r}\n"
            f"Found: {found}\n"
            f"Missing: {sorted(required - keys)}"
        )

    return found


def _parse_fixed_width_lines(header: str, data_lines: list[str]) -> pd.DataFrame:
    cols = infer_fixed_width_columns(header)
    starts = [x[1] for x in cols]

    rows = []
    for line in data_lines:
        if not line.strip():
            continue
        rec = {}
        for j, (key, start) in enumerate(cols):
            end = starts[j + 1] if j + 1 < len(starts) else None
            rec[key] = line[start:end].strip()
        rows.append(rec)

    return pd.DataFrame(rows)


def parser_self_test():
    """Hard self-test using the exact January-2023 layout observed locally."""
    header = (
        "ID Number      Name                                                         "
        "Fed Sex Tit  WTit OTit           FOA JAN23 Gms K  B-day Flag"
    )
    rows = [
        "25121731       A C J John                                                   IND M                                1063  0   40 1987  i",
        "5045886        A K, Kalshyan                                                IND M                                1671  0   20 1964",
        "4804929        A-ALI, Sali Abbas Abdulzahra                                 IRQ F   WFM  WFM                     1876  13  20 2001  w",
    ]
    d = _parse_fixed_width_lines(header, rows)

    checks = [
        int(d.loc[0, "fide_id"]) == 25121731,
        d.loc[0, "sex"] == "M",
        int(d.loc[0, "rating"]) == 1063,
        int(d.loc[0, "games"]) == 0,
        int(d.loc[0, "kfactor"]) == 40,
        int(d.loc[0, "birth_year"]) == 1987,
        d.loc[0, "flag"] == "i",
        int(d.loc[1, "rating"]) == 1671,
        d.loc[1, "flag"] == "",
        d.loc[2, "sex"] == "F",
        int(d.loc[2, "rating"]) == 1876,
        int(d.loc[2, "games"]) == 13,
        d.loc[2, "flag"] == "w",
    ]
    if not all(checks):
        raise RuntimeError(
            "Internal FIDE parser self-test failed.\n"
            + d.to_string(index=False)
        )

    print("[parser] January-2023 fixed-width self-test: PASS")


def parse_fide_txt(path: Path) -> pd.DataFrame:
    parser_self_test()

    text = decode_text(path)
    lines = text.splitlines()
    if not lines:
        raise RuntimeError("Empty FIDE list")

    hidx = None
    for i, line in enumerate(lines[:20]):
        low = line.lower()
        # Do not require "rating" or "srtng": Jan-2023 labels the rating column JAN23.
        if (
            "id" in low
            and "name" in low
            and "fed" in low
            and "sex" in low
            and ("b-day" in low or "born" in low)
            and "flag" in low
        ):
            hidx = i
            break

    if hidx is None:
        raise RuntimeError(
            "Could not locate FIDE header in first 20 lines:\n"
            + "\n".join(lines[:20])
        )

    header = lines[hidx]
    raw = _parse_fixed_width_lines(header, lines[hidx + 1:])

    required_cols = {
        "fide_id", "name", "fed", "sex",
        "rating", "games", "kfactor",
        "birth_year", "flag",
    }
    missing = required_cols - set(raw.columns)
    if missing:
        raise RuntimeError(
            f"Parser output missing columns: {sorted(missing)}"
        )

    # Before filtering, make parsing failures explicit.
    fid_num = pd.to_numeric(raw["fide_id"], errors="coerce")
    rating_num = pd.to_numeric(raw["rating"], errors="coerce")
    birth_num = pd.to_numeric(raw["birth_year"], errors="coerce")

    fid_ok = float(fid_num.notna().mean()) if len(raw) else 0.0
    rating_ok = float(rating_num.notna().mean()) if len(raw) else 0.0

    print(
        f"[parser] raw rows={len(raw):,} | "
        f"numeric fide_id={fid_ok:.2%} | "
        f"numeric rating={rating_ok:.2%}"
    )

    if fid_ok < 0.99:
        bad = raw.loc[fid_num.isna(), ["fide_id", "name"]].head(10)
        raise RuntimeError(
            "FIDE ID fixed-width parse failed for too many rows.\n"
            + bad.to_string(index=False)
        )

    if rating_ok < 0.95:
        bad = raw.loc[
            rating_num.isna(),
            ["fide_id", "name", "rating", "games", "kfactor", "birth_year", "flag"]
        ].head(15)
        raise RuntimeError(
            "Rating fixed-width parse failed for too many rows. "
            "Likely column-boundary error.\n"
            + bad.to_string(index=False)
        )

    d = raw.copy()
    d["fide_id"] = fid_num
    d["rating"] = rating_num
    d["birth_year"] = birth_num

    d = d[
        d["fide_id"].notna()
        & d["rating"].notna()
    ].copy()

    d["fide_id"] = d["fide_id"].astype(int)
    d["rating"] = d["rating"].astype(int)

    d["sex"] = d["sex"].fillna("").astype(str).str.upper().str.strip()
    d = d[d["sex"].isin(["M", "F"])].copy()

    # Standard-rated players only.
    d = d[d["rating"] > 0].copy()

    # FIDE flag can contain combinations such as "wi"; any 'i' means inactive.
    flag = d["flag"].fillna("").astype(str).str.lower()
    d["active"] = ~flag.str.contains("i", regex=False)
    d = d[d["active"]].copy()

    if d.empty:
        raise RuntimeError(
            "Parsed active FIDE population is empty. "
            "This is a parser/filter failure, not a valid population."
        )

    if not d["rating"].between(100, 3500).all():
        bad = d.loc[
            ~d["rating"].between(100, 3500),
            ["fide_id", "name", "rating"]
        ].head(20)
        raise RuntimeError(
            "Implausible parsed ratings detected:\n"
            + bad.to_string(index=False)
        )

    if d["fide_id"].duplicated().any():
        dup = d[d["fide_id"].duplicated(False)].sort_values("fide_id")
        bad = []
        for fid, g in dup.groupby("fide_id"):
            if len(g[["name", "rating", "sex"]].drop_duplicates()) > 1:
                bad.append(fid)
        if bad:
            raise RuntimeError(
                f"Conflicting duplicate FIDE IDs: {bad[:20]}"
            )
        d = d.drop_duplicates("fide_id", keep="first")

    print("\n=== FIDE PARSER SANITY SAMPLE ===")
    cols = [
        "fide_id", "name", "fed", "sex",
        "rating", "games", "kfactor",
        "birth_year", "flag"
    ]
    print(d[cols].head(12).to_string(index=False))

    return d.reset_index(drop=True)


def find_discovery_ids(repo: Path) -> set[int]:
    root = repo / "chess_north_v3"
    if not root.exists():
        raise FileNotFoundError(root)

    seen = set()
    for year in [1994, 2013]:
        for sex in ["M", "F"]:
            matches = [
                p for p in root.glob("*.csv")
                if str(year) in p.name
                and f"_{sex}" in p.stem
                and "audit" not in p.name.lower()
            ]
            valid = []
            for p in matches:
                try:
                    d = pd.read_csv(p, nrows=5)
                except Exception:
                    continue
                if "fide_id" in d.columns:
                    valid.append(p)
            if not valid:
                raise RuntimeError(
                    f"Could not find frozen v3 primary CSV for {year}_{sex} "
                    f"under {root}"
                )
            # Prefer a file whose name explicitly looks primary/frozen/sanitized.
            valid.sort(
                key=lambda p: (
                    "primary" not in p.name.lower(),
                    "sanit" not in p.name.lower(),
                    len(p.name)
                )
            )
            p = valid[0]
            d = pd.read_csv(p)
            ids = pd.to_numeric(d["fide_id"], errors="raise").astype(int)
            seen.update(ids.tolist())
            print(f"[overlap] {year}_{sex}: {len(ids)} IDs from {p.name}")

    print(f"[overlap] unique discovery IDs: {len(seen)}")
    return seen


def adjudicate_2023(row, wd, m):
    persons = wd.get("person_qids", [])
    exacts = wd.get("exact_dobs", [])
    dob = None
    status = ""

    if len(persons) != 1:
        status = "multiple_wikidata_people" if len(persons) > 1 else "no_wikidata_match"
    elif len(exacts) != 1:
        if len(exacts) > 1:
            status = "multiple_wikidata_exact_dobs"
        elif wd.get("all_dobs"):
            status = "wikidata_non_day_precision"
        else:
            status = "no_exact_dob"
    else:
        dob = exacts[0]
        known_year = None
        if "birth_year" in row.index and pd.notna(row["birth_year"]):
            try:
                known_year = int(float(row["birth_year"]))
            except Exception:
                pass
        if known_year and int(dob[:4]) != known_year:
            status = "wikidata_year_mismatch"
            dob = None
        elif dob > SNAPSHOT:
            status = "dob_after_snapshot_impossible"
            dob = None
        else:
            status = "wikidata_exact_year_agrees"

    hemi = wd.get("hemisphere", "unknown")
    eligible = bool(
        dob is not None
        and hemi == "north"
        and status == "wikidata_exact_year_agrees"
    )

    if eligible:
        exclusion = ""
    elif dob is None:
        exclusion = f"dob:{status}"
    else:
        exclusion = f"hemisphere:{hemi}:{wd.get('hemisphere_status','')}"

    return {
        "identity_bridge_modern_fide_id": m.norm_id(row["fide_id"]),
        "exact_dob_frozen": dob,
        "dob_status_2023": status,
        "birthplace_hemisphere": hemi,
        "hemisphere_status": wd.get("hemisphere_status", ""),
        "wikidata_person_qids": ";".join(wd.get("person_qids", [])),
        "birthplace_qids": ";".join(wd.get("birthplace_qids", [])),
        "birthplace_labels": ";".join(wd.get("birthplace_labels", [])),
        "birthplace_latitudes": ";".join(map(str, wd.get("latitudes", []))),
        "birthplace_longitudes": ";".join(map(str, wd.get("longitudes", []))),
        "eligible_north_2023": eligible,
        "exclusion_reason_2023": exclusion,
    }


def scan_both_targets(
    pop: pd.DataFrame,
    sex: str,
    seen_ids: set[int],
    m,
    wd_session,
    wd_cache,
    wd_cache_path,
    batch_size,
    timeout,
    retries,
    delay,
):
    x = pop[pop["sex"].eq(sex)].copy()
    x.sort_values(
        ["rating","name","fide_id"],
        ascending=[False,True,True],
        inplace=True
    )
    x.reset_index(drop=True, inplace=True)

    eligible_all = []
    audit = []
    full_cutoff = None
    new_cutoff = None
    full_target = TARGET[sex]
    new_target = TARGET[sex]

    for rating, group in x.groupby("rating", sort=False):
        ids = [m.norm_id(v) for v in group["fide_id"].tolist()]
        ids = [v for v in ids if v]

        m.fetch_wikidata_ids(
            ids,
            session=wd_session,
            cache=wd_cache,
            cache_path=wd_cache_path,
            batch_size=batch_size,
            timeout=timeout,
            retries=retries,
            delay=delay,
        )

        for _, row in group.iterrows():
            fid = m.norm_id(row["fide_id"])
            ws = m.summarize_wikidata(
                wd_cache.get(fid, []) if fid else []
            )
            meta = adjudicate_2023(row, ws, m)
            rec = row.to_dict()
            rec.update(meta)
            rec["snapshot"] = "2023-01"
            rec["analysis_sex"] = sex
            rec["seen_in_1994_2013"] = int(row["fide_id"]) in seen_ids
            audit.append(rec)
            if meta["eligible_north_2023"]:
                eligible_all.append(rec)

        elig_df = pd.DataFrame(eligible_all)
        if not elig_df.empty:
            if full_cutoff is None and len(elig_df) >= full_target:
                full_cutoff = int(rating)
            new_n = int((~elig_df["seen_in_1994_2013"]).sum())
            if new_cutoff is None and new_n >= new_target:
                new_cutoff = int(rating)

        # We process complete Elo groups. Once both thresholds were reached,
        # this group contains all ties at the lower of the two cutoffs.
        if full_cutoff is not None and new_cutoff is not None:
            if int(rating) <= min(full_cutoff, new_cutoff):
                break

    if full_cutoff is None or new_cutoff is None:
        raise RuntimeError(
            f"Could not reach both targets for sex={sex}. "
            f"full_cutoff={full_cutoff}, new_cutoff={new_cutoff}"
        )

    elig = pd.DataFrame(eligible_all)
    full = elig[elig["rating"] >= full_cutoff].copy()
    new_target_df = elig[
        (~elig["seen_in_1994_2013"]) &
        (elig["rating"] >= new_cutoff)
    ].copy()
    new_within_full = full[~full["seen_in_1994_2013"]].copy()

    for d in [full, new_target_df, new_within_full]:
        d.sort_values(
            ["rating","name","fide_id"],
            ascending=[False,True,True],
            inplace=True
        )
        d.reset_index(drop=True, inplace=True)

    return full, new_within_full, new_target_df, pd.DataFrame(audit), full_cutoff, new_cutoff


def add_rank_and_z(d: pd.DataFrame):
    d = d.copy()
    d["analysis_rank_within_sex"] = d["rating"].rank(
        method="min", ascending=False
    ).astype(int)
    mu = d["rating"].mean()
    sd = d["rating"].std(ddof=0)
    d["elo_z_within_2023_sex_cohort"] = (
        (d["rating"] - mu) / sd if sd > 0 else 0.0
    )
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-dir", default=".")
    ap.add_argument("--repo", default=r"..\1986wiki")
    ap.add_argument("--fide-zip", default=None)
    ap.add_argument("--fide-txt", default=None)
    ap.add_argument("--proxy", default=None)
    ap.add_argument("--timeout", type=int, default=45)
    ap.add_argument("--retries", type=int, default=4)
    ap.add_argument("--batch-size", type=int, default=50)
    ap.add_argument("--delay", type=float, default=0.35)
    ap.add_argument("--output-subdir", default="chess_2023_cohorts_v1")
    ap.add_argument("--tag", default="chess-2023-cohorts-frozen-v1")
    ap.add_argument("--remote", default="origin")
    ap.add_argument("--no-git", action="store_true")
    a = ap.parse_args()

    project = Path(a.project_dir).resolve()
    repo = git_root(Path(a.repo))

    if not run(["git","tag","--list",REQUIRED_PLAN_TAG], repo).strip():
        raise RuntimeError(
            f"Required preregistration tag missing: {REQUIRED_PLAN_TAG}\n"
            "Run freeze_chess_2023_validation_v2.py first."
        )

    m = import_north_v2(repo)

    cache_dir = project / "chess_2023_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    if a.fide_txt:
        txt = Path(a.fide_txt).resolve()
    else:
        if a.fide_zip:
            zpath = Path(a.fide_zip).resolve()
        else:
            zpath = cache_dir / "jan23frl.zip"
            if not zpath.exists():
                download_archive(zpath, a.proxy, a.timeout)
        preferred_txt = cache_dir / "standard_jan23frl.txt"
        fallback_txt = cache_dir / "jan23frl.txt"

        if preferred_txt.exists():
            txt = preferred_txt
        elif fallback_txt.exists():
            txt = fallback_txt
        else:
            txt = extract_txt_from_zip(zpath, cache_dir)

    pop = parse_fide_txt(txt)
    if pop.empty:
        raise RuntimeError("Population unexpectedly empty after parser sanity checks.")
    print("\n=== JAN 2023 ACTIVE STANDARD POPULATION ===")
    print("n total:", len(pop))
    print("male:", int((pop.sex == "M").sum()))
    print("female:", int((pop.sex == "F").sum()))
    print("rating range:", int(pop.rating.min()), "..", int(pop.rating.max()))

    seen_ids = find_discovery_ids(repo)

    wd_cache_path = cache_dir / "wikidata_2023_dob_birthplace_cache.json"
    wd_cache = m.load_json_cache(wd_cache_path)
    wd_session = m.build_session(a.proxy)

    out = repo / a.output_subdir
    out.mkdir(parents=True, exist_ok=True)

    summary = {
        "snapshot": SNAPSHOT,
        "analysis_role": "pre_reveal_population_freeze",
        "required_plan_tag": REQUIRED_PLAN_TAG,
        "sexes": {},
    }
    generated = []

    for sex in ["M","F"]:
        print(f"\n=== BUILD 2023 {sex} FULL + NEW TARGETS ===")
        full, nwf, newt, audit, cfull, cnew = scan_both_targets(
            pop=pop,
            sex=sex,
            seen_ids=seen_ids,
            m=m,
            wd_session=wd_session,
            wd_cache=wd_cache,
            wd_cache_path=wd_cache_path,
            batch_size=a.batch_size,
            timeout=a.timeout,
            retries=a.retries,
            delay=a.delay,
        )

        full = add_rank_and_z(full)
        nwf = add_rank_and_z(nwf) if len(nwf) else nwf
        newt = add_rank_and_z(newt)

        files = {
            "FULL": out / f"primary_2023_{sex}_FULL.csv",
            "NEW_WITHIN_FULL": out / f"diagnostic_2023_{sex}_NEW_WITHIN_FULL.csv",
            "NEW_TARGET": out / f"validation_2023_{sex}_NEW_TARGET.csv",
            "AUDIT": out / f"candidate_audit_2023_{sex}.csv",
        }
        full.to_csv(files["FULL"], index=False, encoding="utf-8-sig")
        nwf.to_csv(files["NEW_WITHIN_FULL"], index=False, encoding="utf-8-sig")
        newt.to_csv(files["NEW_TARGET"], index=False, encoding="utf-8-sig")
        audit.to_csv(files["AUDIT"], index=False, encoding="utf-8-sig")
        generated.extend(files.values())

        summary["sexes"][sex] = {
            "target": TARGET[sex],
            "full_n": len(full),
            "full_cutoff_elo": int(cfull),
            "new_within_full_n": len(nwf),
            "new_target_n": len(newt),
            "new_target_cutoff_elo": int(cnew),
            "overlap_in_full_n": int(full["seen_in_1994_2013"].sum()),
            "new_target_max_elo": int(newt.rating.max()),
            "new_target_min_elo": int(newt.rating.min()),
            "full_max_elo": int(full.rating.max()),
            "full_min_elo": int(full.rating.min()),
            "audit_candidates_scanned": len(audit),
        }

        print(
            f"{sex} FULL: n={len(full)}, cutoff={cfull}, "
            f"overlap_old={int(full['seen_in_1994_2013'].sum())}"
        )
        print(
            f"{sex} NEW_WITHIN_FULL: n={len(nwf)}"
        )
        print(
            f"{sex} NEW_TARGET: n={len(newt)}, cutoff={cnew}, "
            f"range={int(newt.rating.max())}..{int(newt.rating.min())}"
        )

    sp = out / "chess_2023_cohort_summary.json"
    sp.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    generated.append(sp)

    script_copy = out / "build_chess_2023_cohorts_v2.py"
    shutil.copy2(Path(__file__).resolve(), script_copy)
    generated.append(script_copy)

    print("\n=== 2023 PRE-REVEAL COHORT SUMMARY ===")
    for sex in ["M","F"]:
        s = summary["sexes"][sex]
        print(
            f"{sex}: FULL n={s['full_n']} cutoff={s['full_cutoff_elo']} | "
            f"NEW_WITHIN_FULL n={s['new_within_full_n']} | "
            f"NEW_TARGET n={s['new_target_n']} cutoff={s['new_target_cutoff_elo']} | "
            f"scanned={s['audit_candidates_scanned']}"
        )

    print("\nNO BAZI HAS BEEN CALCULATED.")

    if a.no_git:
        print("--no-git: outputs generated; Git untouched.")
        return

    staged = run(["git","diff","--cached","--name-only"], repo).strip()
    if staged:
        raise RuntimeError("Git index already has staged files:\n" + staged)
    if run(["git","tag","--list",a.tag], repo).strip():
        raise RuntimeError(f"Tag already exists: {a.tag}")

    rels = [str(p.relative_to(repo)) for p in generated]
    run(["git","add","--",*rels], repo)
    run([
        "git","commit","-m",
        "Freeze January 2023 chess FULL and NEW validation cohorts"
    ], repo)
    run([
        "git","tag","-a",a.tag,"-m",
        "Freeze 2023 chess cohorts before BaZi reveal"
    ], repo)

    branch = run(["git","branch","--show-current"], repo)
    run(["git","push",a.remote,branch], repo)
    run(["git","push",a.remote,a.tag], repo)

    print("\n=== 2023 COHORTS FROZEN ===")
    print("Commit:", run(["git","rev-parse","HEAD"], repo))
    print("Tag:   ", a.tag)
    print("Output:", out)


if __name__ == "__main__":
    main()
