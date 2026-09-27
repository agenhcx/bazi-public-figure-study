#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
sanitize_chess_north_v2.py

PRE-REVEAL temporal sanity patch for the already-frozen north-v2 cohorts.

Why:
The north-v2 summary showed birth_year_max=1997 inside the January-1994
male cohort. A player cannot be born after the historical snapshot, so at
least one remaining identity/DOB join is invalid.

This script DOES NOT calculate BaZi.

It:
1) reads the four frozen north-v2 primary cohort CSVs;
2) hard-excludes any DOB later than the snapshot date;
3) recalculates Top500 men / Top200 women + Elo cutoff ties;
4) aborts if the existing v2 files no longer contain enough valid players;
5) reports age ranges for sanity;
6) writes a v3 amendment + sanitized cohort files;
7) optionally commits/tags/pushes to Git.

It does NOT overwrite chess_north_v2.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path

import pandas as pd


FILES = {
    "1994_M": ("primary_north_top_1994_M.csv", "1994-01-01", 500),
    "1994_F": ("primary_north_top_1994_F.csv", "1994-01-01", 200),
    "2013_M": ("primary_north_top_2013_M.csv", "2013-01-01", 500),
    "2013_F": ("primary_north_top_2013_F.csv", "2013-01-01", 200),
}


def run(cmd, cwd, check=True):
    print("$", " ".join(cmd))
    p = subprocess.run(
        cmd,
        cwd=str(cwd),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if p.stdout:
        print(p.stdout.rstrip())
    if check and p.returncode != 0:
        raise RuntimeError(
            f"Command failed ({p.returncode}): {' '.join(cmd)}"
        )
    return p.stdout.strip()


def git_root(path: Path) -> Path:
    out = run(
        ["git", "rev-parse", "--show-toplevel"],
        path,
    )
    return Path(out.splitlines()[-1]).resolve()


def norm_dob_series(s: pd.Series) -> pd.Series:
    d = pd.to_datetime(s, errors="coerce")
    if d.isna().any():
        bad = s[d.isna()]
        raise RuntimeError(
            "Unparseable exact_dob_frozen values:\n"
            + bad.to_string()
        )
    return d


def top_n_with_ties(df: pd.DataFrame, target: int) -> tuple[pd.DataFrame, int]:
    d = df.sort_values(
        ["rating", "name", "fide_id"],
        ascending=[False, True, True],
    ).reset_index(drop=True)

    if len(d) < target:
        raise RuntimeError(
            f"Only {len(d)} valid rows remain, below target {target}. "
            "A full-population rebuild is required."
        )

    cutoff = int(d.iloc[target - 1]["rating"])
    out = d[d["rating"] >= cutoff].copy()

    # Safety: all tied players at the new cutoff must already exist in v2.
    # Since v2 was itself constructed by complete Elo groups, this holds as
    # long as the new cutoff is >= the old v2 cutoff.
    return out.reset_index(drop=True), cutoff


def age_years(dob: pd.Series, snapshot: str) -> pd.Series:
    snap = pd.Timestamp(snapshot)
    return (snap - dob).dt.days / 365.2425


def amendment(summary: dict) -> str:
    lines = [
        "# Chess BaZi Study — Preregistration Amendment v3",
        "## Temporal DOB Sanity Patch",
        "",
        "**Status:** committed before any chess BaZi calculation/reveal.",
        "",
        "The v2 Northern-Hemisphere population rule remains unchanged.",
        "This amendment adds one hard data-integrity condition:",
        "",
        "> A player's exact DOB must be on or before the historical snapshot date.",
        "",
        "Any DOB later than the snapshot is treated as an identity/DOB data error,",
        "not as a valid observation. Such rows are excluded before BaZi calculation.",
        "",
        "After exclusion, the cohort is reselected as Top500 men / Top200 women",
        "plus all valid Elo cutoff ties using only the already-frozen v2 population.",
        "",
        "If the v2 files do not contain enough valid rows to satisfy the target,",
        "the sanitizer aborts instead of silently changing the population rule.",
        "",
        "No BaZi values were inspected before adding this rule.",
        "",
        "## Frozen v3 cohorts",
        "",
    ]
    for key in ["1994_M", "1994_F", "2013_M", "2013_F"]:
        x = summary["cohorts"][key]
        lines.append(
            f"- {key}: n={x['n']}, cutoff Elo={x['cutoff_elo']}, "
            f"age range={x['age_years_min']:.2f}–{x['age_years_max']:.2f}"
        )

    lines += [
        "",
        "The original `chess-preregister-v1` and",
        "`chess-preregister-v2-hemisphere` tags remain unchanged for provenance.",
        "",
        "**No chess BaZi values were used to construct this amendment.**",
        "",
    ]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--repo",
        default=r"..\1986wiki",
        help="existing Git repo containing chess_north_v2",
    )
    ap.add_argument(
        "--source-subdir",
        default="chess_north_v2",
    )
    ap.add_argument(
        "--output-subdir",
        default="chess_north_v3",
    )
    ap.add_argument(
        "--tag",
        default="chess-preregister-v3-date-sanity",
    )
    ap.add_argument(
        "--commit-message",
        default="Add pre-reveal DOB temporal sanity patch to chess cohorts",
    )
    ap.add_argument("--remote", default="origin")
    ap.add_argument("--no-git", action="store_true")
    args = ap.parse_args()

    repo = git_root(Path(args.repo).resolve())
    source = repo / args.source_subdir
    outdir = repo / args.output_subdir

    if not source.exists():
        raise FileNotFoundError(source)

    print("Git repo:", repo)
    print("Source:  ", source)
    print("Output:  ", outdir)

    outdir.mkdir(parents=True, exist_ok=True)

    summary = {
        "stage": "pre-reveal DOB temporal sanity patch; no BaZi",
        "hard_rule": "exact DOB must be <= snapshot date",
        "source_population": args.source_subdir,
        "cohorts": {},
        "invalid_rows": [],
    }

    generated = []

    for key, (fname, snapshot, target) in FILES.items():
        path = source / fname
        if not path.exists():
            raise FileNotFoundError(path)

        df = pd.read_csv(path)
        required = {"fide_id", "name", "rating", "exact_dob_frozen"}
        missing = required - set(df.columns)
        if missing:
            raise RuntimeError(f"{fname}: missing columns {sorted(missing)}")

        dob = norm_dob_series(df["exact_dob_frozen"])
        snap = pd.Timestamp(snapshot)

        invalid_mask = dob > snap
        invalid = df[invalid_mask].copy()

        if len(invalid):
            invalid["_snapshot"] = snapshot
            invalid["_reason"] = "dob_after_snapshot_impossible"
            invalid["_parsed_dob"] = dob[invalid_mask].dt.strftime("%Y-%m-%d")
            summary["invalid_rows"].extend(
                invalid[
                    ["fide_id", "name", "rating", "_parsed_dob", "_snapshot", "_reason"]
                ].to_dict("records")
            )

        valid = df[~invalid_mask].copy()
        valid_dob = dob[~invalid_mask].reset_index(drop=True)
        valid = valid.reset_index(drop=True)

        selected, cutoff = top_n_with_ties(valid, target)
        selected_dob = norm_dob_series(selected["exact_dob_frozen"])

        selected["age_years_at_snapshot"] = age_years(
            selected_dob, snapshot
        )

        # Absolute hard sanity check.
        if (selected["age_years_at_snapshot"] < 0).any():
            raise RuntimeError(f"{key}: negative age survived sanitation")

        selected["dob_temporal_sanity_status"] = "valid_pre_snapshot"

        outpath = outdir / fname
        selected.to_csv(
            outpath,
            index=False,
            encoding="utf-8-sig",
        )
        generated.append(outpath)

        summary["cohorts"][key] = {
            "source_n": int(len(df)),
            "invalid_future_dob_n": int(invalid_mask.sum()),
            "valid_before_reselection_n": int(len(valid)),
            "target": target,
            "n": int(len(selected)),
            "cutoff_elo": int(cutoff),
            "n_above_cutoff": int((selected["rating"] > cutoff).sum()),
            "n_at_cutoff": int((selected["rating"] == cutoff).sum()),
            "birth_year_min": int(selected_dob.dt.year.min()),
            "birth_year_max": int(selected_dob.dt.year.max()),
            "age_years_min": float(selected["age_years_at_snapshot"].min()),
            "age_years_max": float(selected["age_years_at_snapshot"].max()),
        }

    # Save invalid-row audit.
    invalid_df = pd.DataFrame(summary["invalid_rows"])
    invalid_path = outdir / "temporal_sanity_invalid_rows.csv"
    invalid_df.to_csv(
        invalid_path,
        index=False,
        encoding="utf-8-sig",
    )
    generated.append(invalid_path)

    summary_path = outdir / "date_sanity_summary.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    generated.append(summary_path)

    amendment_path = outdir / "CHESS_PREREGISTRATION_AMENDMENT_V3.md"
    amendment_path.write_text(
        amendment(summary),
        encoding="utf-8",
    )
    generated.append(amendment_path)

    script_copy = outdir / "sanitize_chess_north_v2.py"
    shutil.copy2(Path(__file__).resolve(), script_copy)
    generated.append(script_copy)

    print("\n=== DATE SANITY SUMMARY ===")
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    if args.no_git:
        print("\n--no-git: generated and validated; Git untouched.")
        return

    # Git safety.
    staged_pre = [
        x.strip().replace("\\", "/")
        for x in run(
            ["git", "diff", "--cached", "--name-only"],
            repo,
        ).splitlines()
        if x.strip()
    ]
    if staged_pre:
        raise RuntimeError(
            "Git index already has staged files; clear them first:\n"
            + "\n".join(staged_pre)
        )

    if run(["git", "tag", "--list", args.tag], repo).strip():
        raise RuntimeError(f"Tag already exists: {args.tag}")

    add_paths = [str(p.relative_to(repo)) for p in generated]

    run(["git", "add", "--", *add_paths], repo)

    staged = {
        x.strip().replace("\\", "/")
        for x in run(
            ["git", "diff", "--cached", "--name-only"],
            repo,
        ).splitlines()
        if x.strip()
    }
    expected = {Path(x).as_posix() for x in add_paths}

    if staged != expected:
        raise RuntimeError(
            f"Staged-file mismatch.\nExpected={sorted(expected)}\n"
            f"Actual={sorted(staged)}"
        )

    run(["git", "commit", "-m", args.commit_message], repo)
    run(
        [
            "git", "tag", "-a", args.tag,
            "-m",
            "Freeze chess DOB temporal sanity patch before BaZi reveal",
        ],
        repo,
    )

    branch = run(["git", "branch", "--show-current"], repo).splitlines()[-1].strip()
    if not branch:
        raise RuntimeError("Detached HEAD; refusing push")

    run(["git", "push", args.remote, branch], repo)
    run(["git", "push", args.remote, args.tag], repo)

    commit = run(["git", "rev-parse", "HEAD"], repo).splitlines()[-1]

    print("\n=== DONE ===")
    print("Commit:", commit)
    print("Tag:   ", args.tag)
    print("Branch:", branch)
    print("Date-sanity-patched cohorts are frozen before BaZi reveal.")


if __name__ == "__main__":
    main()
