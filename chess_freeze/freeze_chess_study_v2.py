#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Freeze chess cohorts + preregistration, then optionally commit/tag/push.
NO BaZi calculation is performed.

Expected upstream files:
  chess_dob/repaired_v2_top_1994_M.csv
  chess_dob/repaired_v2_top_1994_F.csv
  chess_dob/enriched_top_2013_M.csv
  chess_dob/enriched_top_2013_F.csv
  1994_final_audit_resolved_v1.csv
    (or chess_dob/1994_final_audit_resolved_v1.csv)

Primary DOB rule:
  1994: exclude all credible exact-date source conflicts and all unresolved
        cases. Previously missing but later non-conflicting exact DOBs may stay.
  2013: require pre-reveal exact_dob_final; no imputation.

Sensitivity:
  1994 manually adjudicated source-conflict cases are included, but unresolved
  cases remain excluded.

Default Git actions:
  git add ONLY generated freeze files + this script (if inside repo)
  git commit
  git tag -a chess-preregister-v1
  git push origin <current-branch>
  git push origin chess-preregister-v1

Use --no-git to generate/validate files only.\n\nThis v2 script supports keeping chess data OUTSIDE the existing Git repo.\nExample from C:\\chenxi\\bazi_project\\chess:\n  python freeze_chess_study_v3.py --repo ..\\1986wiki
"""

from __future__ import annotations
import argparse
import json
import shutil
import subprocess
from pathlib import Path
import pandas as pd

EXPECTED = {
    "1994_M_source": 511,
    "1994_F_source": 202,
    "2013_M_source": 506,
    "2013_F_source": 201,
    "audit": 43,
    "1994_M_clean": 494,
    "1994_F_clean": 188,
    "1994_M_adj": 508,
    "1994_F_adj": 196,
    "2013_M_clean": 492,
    "2013_F_clean": 197,
}


def run(cmd, cwd, check=True):
    print("$", " ".join(cmd))
    p = subprocess.run(
        cmd, cwd=str(cwd), text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT
    )
    if p.stdout:
        print(p.stdout.rstrip())
    if check and p.returncode != 0:
        raise RuntimeError(
            f"Command failed ({p.returncode}): {' '.join(cmd)}"
        )
    return p.stdout.strip()


def validate_git_repo(path: Path) -> Path:
    path = path.resolve()
    if not path.exists():
        raise FileNotFoundError(f"Git repository path does not exist: {path}")

    top = Path(
        run(["git", "rev-parse", "--show-toplevel"], path)
        .splitlines()[-1]
    ).resolve()

    # Require the user-provided path to be inside the intended repo, but use
    # the canonical top-level returned by Git for all mutations.
    try:
        path.relative_to(top)
    except ValueError:
        raise RuntimeError(
            f"--repo path {path} resolved to unexpected Git root {top}"
        )

    return top


def require_data(data_dir: Path, filename: str) -> Path:
    p = (data_dir / filename).resolve()
    if not p.exists():
        raise FileNotFoundError(f"Required data file not found: {p}")
    return p


def require_audit(project_dir: Path, data_dir: Path, explicit: str | None) -> Path:
    candidates = []
    if explicit:
        candidates.append(Path(explicit))
    candidates.extend([
        project_dir / "1994_final_audit_resolved_v1.csv",
        data_dir / "1994_final_audit_resolved_v1.csv",
    ])

    for p in candidates:
        p = p.resolve()
        if p.exists():
            return p

    raise FileNotFoundError(
        "Could not find 1994_final_audit_resolved_v1.csv. Tried:\n  "
        + "\n  ".join(str(Path(x).resolve()) for x in candidates)
    )


def read_csv(path: Path) -> pd.DataFrame:
    d = pd.read_csv(path)
    if "fide_id" in d.columns:
        d["fide_id"] = pd.to_numeric(d["fide_id"], errors="raise").astype(int)
    return d


def b(v) -> bool:
    if isinstance(v, bool):
        return v
    if pd.isna(v):
        return False
    return str(v).strip().lower() in {"true", "1", "yes", "y"}


def dob(v):
    if pd.isna(v) or not str(v).strip():
        return None
    return pd.to_datetime(str(v).strip(), errors="raise").strftime("%Y-%m-%d")


def assert_n(label, actual, expected):
    if actual != expected:
        raise RuntimeError(
            f"{label}: expected {expected}, got {actual}. "
            "Upstream cohort/version differs from the frozen design."
        )


def assert_unique(df, label):
    if df["fide_id"].duplicated().any():
        bad = df[df["fide_id"].duplicated(False)][["fide_id", "name"]]
        raise RuntimeError(f"{label}: duplicate IDs:\n{bad.to_string(index=False)}")


def load_audit(path: Path) -> pd.DataFrame:
    a = pd.read_csv(path)
    need = {"fide_id_1994", "audit_reasons", "final_dob_manual", "exclude"}
    miss = need - set(a.columns)
    if miss:
        raise RuntimeError(f"Audit file missing columns: {sorted(miss)}")
    a["fide_id_1994"] = pd.to_numeric(a["fide_id_1994"], errors="raise").astype(int)
    assert_n("audit rows", len(a), EXPECTED["audit"])
    if a["fide_id_1994"].duplicated().any():
        raise RuntimeError("Duplicate fide_id_1994 in audit file")
    a["_conflict"] = a["audit_reasons"].fillna("").str.contains(
        "profile_vs_wikidata_disagree", regex=False
    )
    a["_exclude"] = a["exclude"].map(b)
    a["_manual_dob"] = a["final_dob_manual"].map(dob)
    bad = a[(~a["_exclude"]) & a["_manual_dob"].isna()]
    if len(bad):
        raise RuntimeError("Resolved audit rows with blank DOB")
    return a


def freeze_1994(src: pd.DataFrame, audit: pd.DataFrame, sex: str):
    amap = audit.set_index("fide_id_1994").to_dict("index")
    primary, adjudicated = [], []

    for _, row in src.iterrows():
        rec = row.to_dict()
        fid = int(row["fide_id"])
        base = dob(row.get("exact_dob_final_v2"))
        a = amap.get(fid)

        if a is None:
            if base is None:
                raise RuntimeError(f"1994 {sex}: non-audit player lacks DOB: {fid}")
            x = rec.copy()
            x.update({
                "exact_dob_frozen": base,
                "dob_freeze_status": "primary_clean_upstream_exact",
                "dob_source_conflict": False,
            })
            primary.append(x)
            y = x.copy()
            y["dob_freeze_status"] = "sensitivity_same_as_primary"
            adjudicated.append(y)
            continue

        conflict = bool(a["_conflict"])
        unresolved = bool(a["_exclude"])
        manual = a["_manual_dob"]

        # PRIMARY: source conflicts are excluded even if manually adjudicated.
        if (not conflict) and (not unresolved):
            x = rec.copy()
            x.update({
                "exact_dob_frozen": manual,
                "dob_freeze_status": "primary_clean_manual_nonconflicting_fill",
                "dob_source_conflict": False,
                "dob_resolution_source_level": a.get("source_level", pd.NA),
                "dob_resolution_note": a.get("resolution_note", ""),
            })
            primary.append(x)

        # SENSITIVITY: use adjudicated conflicts, but never unresolved DOBs.
        if not unresolved:
            y = rec.copy()
            y.update({
                "exact_dob_frozen": manual,
                "dob_freeze_status": (
                    "sensitivity_manual_adjudicated_conflict"
                    if conflict else "sensitivity_manual_nonconflicting_fill"
                ),
                "dob_source_conflict": conflict,
                "dob_resolution_source_level": a.get("source_level", pd.NA),
                "dob_resolution_note": a.get("resolution_note", ""),
            })
            adjudicated.append(y)

    return finalize(pd.DataFrame(primary), "1994-01", sex), finalize(
        pd.DataFrame(adjudicated), "1994-01", sex
    )


def freeze_2013(src: pd.DataFrame, sex: str):
    if "exact_dob_final" not in src.columns:
        raise RuntimeError(f"2013 {sex}: exact_dob_final missing")
    d = src.copy()
    d["exact_dob_frozen"] = d["exact_dob_final"].map(dob)
    d = d[d["exact_dob_frozen"].notna()].copy()
    d["dob_freeze_status"] = "primary_clean_wikidata_exact"
    d["dob_source_conflict"] = False
    return finalize(d, "2013-01", sex)


def finalize(d: pd.DataFrame, snapshot: str, sex: str):
    d = d.copy()
    d["snapshot"] = snapshot
    d["analysis_sex"] = sex
    d["rating"] = pd.to_numeric(d["rating"], errors="raise")
    d.sort_values(["rating", "name", "fide_id"], ascending=[False, True, True], inplace=True)
    d.reset_index(drop=True, inplace=True)
    d["analysis_rank_within_sex"] = d["rating"].rank(
        method="min", ascending=False
    ).astype("Int64")
    sd = d["rating"].std(ddof=1)
    d["elo_z_within_snapshot_sex"] = (d["rating"] - d["rating"].mean()) / sd
    n = len(d)
    d["rank_percentile_within_snapshot_sex"] = (
        (n - d["analysis_rank_within_sex"]) / (n - 1) if n > 1 else 1.0
    )
    return d


def stats(d):
    years = pd.to_datetime(d["exact_dob_frozen"]).dt.year
    return {
        "n": int(len(d)),
        "mean_elo": float(d["rating"].mean()),
        "median_elo": float(d["rating"].median()),
        "min_elo": int(d["rating"].min()),
        "max_elo": int(d["rating"].max()),
        "birth_year_min": int(years.min()),
        "birth_year_max": int(years.max()),
    }


def prereg(summary):
    return f'''# Chess BaZi Study — Preregistration v1

## Freeze point

This file is generated **before any chess BaZi calculation or reveal**.
Population construction and DOB auditing were completed first.

## Frozen historical snapshots

### January 1994

Selection before DOB filtering:
- active men: Top 500 classical Elo + all cutoff ties;
- active women: Top 200 classical Elo + all cutoff ties;
- Garry Kasparov and Nigel Short were restored before reranking because their
  omission from the official 1994 FIDE list followed the 1993 FIDE/PCA split.

PRIMARY clean DOB rule:
1. exact Gregorian YYYY-MM-DD required;
2. unresolved DOB excluded;
3. any credible exact-date source conflict is excluded from PRIMARY, even if a
   manual adjudication favors one candidate;
4. previously missing but later non-conflicting exact DOB may be retained;
5. no guessing, majority voting, or post-reveal date adjudication.

Frozen PRIMARY:
- men: **{summary['primary']['1994_M']['n']}**
- women: **{summary['primary']['1994_F']['n']}**

A separate adjudicated 1994 sensitivity cohort retains resolved source-conflict
cases. It is not primary.

### January 2013

Selection before DOB filtering:
- active men: Top 500 classical Elo + all cutoff ties;
- active women: Top 200 classical Elo + all cutoff ties.

Only pre-reveal exact day-level DOBs are retained.

Frozen PRIMARY:
- men: **{summary['primary']['2013_M']['n']}**
- women: **{summary['primary']['2013_F']['n']}**

## Primary period comparison

Compare January 1994 (near the midpoint of the traditional 七运 period) with
January 2013 (near the midpoint of 八运). The labels define the predefined
historical-period comparison; they do not establish causality.

## Primary performance endpoint

Primary continuous endpoint:

`elo_z_within_snapshot_sex = (Elo - group mean) / group SD`

Secondary descriptive endpoints:
- raw classical Elo;
- within-snapshot-sex rank percentile;
- explicitly labeled elite-tail sensitivity analyses.

## Pre-reveal hypotheses

### H1 — temporal element-gradient replication
Test the previously generated hypothesis that Metal Day Masters are relatively
more represented earlier and Earth Day Masters relatively more represented later.

### H2 — predefined historical-period distribution
Test whether Day-Master element distribution differs between the frozen 1994
and 2013 chess snapshots.

### H3 — measurable three-pillar exposure
Because exact birth times are not available at useful coverage, PRIMARY does
not label players 伤官格 or 偏印格. Use predefined measurable three-pillar proxies
for 伤官 exposure and 偏印 exposure.

### Negative controls
Retain the previously defined negative controls:
- year-stem 食神 frequency;
- Food-God performance;
- age-12 Food-God / Seven-Killings Dayun enrichment, only if implemented with
  the definition fixed before viewing chess BaZi results.

## Calendar/null comparison
BaZi distributions must be compared against a calendar-matched null rather than
naive uniform 20% five-element expectations.

## Sex
Male and female populations have different selection thresholds. Report sex
separately descriptively; pooled performance uses snapshot × sex standardized
Elo.

## DOB sensitivity
PRIMARY: clean exact-DOB cohort only.
Sensitivity: manually adjudicated 1994 DOB cohort.
Unresolved DOBs are never imputed.

## Elo-threshold sensitivity
Top-N-with-ties is PRIMARY. Fixed thresholds such as Elo >= 2500 are secondary
sensitivity analyses because the rating pool changed between 1994 and 2013.

## Engine-era issue
Engine adoption (including Stockfish and earlier engines) is recognized as a
historical confound but is not used to redefine the 1994/2013 primary windows
after the fact. Any such analysis is secondary/exploratory unless separately
preregistered before BaZi reveal.

## Reveal rule
After this file is committed and tagged:
1. frozen PRIMARY cohort files are immutable;
2. BaZi is calculated once from `exact_dob_frozen`;
3. newly noticed patterns are exploratory;
4. the chess cohort is not repeatedly mined for new confirmatory hypotheses.

## Frozen files
PRIMARY:
- `chess_freeze/primary_clean_top_1994_M.csv`
- `chess_freeze/primary_clean_top_1994_F.csv`
- `chess_freeze/primary_clean_top_2013_M.csv`
- `chess_freeze/primary_clean_top_2013_F.csv`

Sensitivity:
- `chess_freeze/sensitivity_adjudicated_top_1994_M.csv`
- `chess_freeze/sensitivity_adjudicated_top_1994_F.csv`

Provenance:
- `chess_freeze/1994_final_audit_resolved_v1.csv`
- `chess_freeze/chess_cohort_freeze_summary.json`

**No BaZi values are contained in this freeze.**
'''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--repo",
        required=True,
        help=(
            "Path to the EXISTING Git repository that should receive the "
            "freeze commit, e.g. ..\\1986wiki"
        ),
    )
    ap.add_argument(
        "--project-dir",
        default=".",
        help=(
            "Local chess working directory containing chess_dob "
            "(default: current directory)"
        ),
    )
    ap.add_argument(
        "--data-dir",
        default=None,
        help=(
            "Directory containing repaired/enriched cohort CSVs. "
            "Default: <project-dir>/chess_dob"
        ),
    )
    ap.add_argument(
        "--audit",
        default=None,
        help=(
            "Optional explicit path to 1994_final_audit_resolved_v1.csv. "
            "Default search: project-dir then data-dir."
        ),
    )
    ap.add_argument(
        "--output-subdir",
        default="chess_freeze",
        help="Destination subdirectory INSIDE the Git repo",
    )
    ap.add_argument("--tag", default="chess-preregister-v1")
    ap.add_argument(
        "--commit-message",
        default="Freeze chess clean cohorts and preregistration before BaZi reveal",
    )
    ap.add_argument("--remote", default="origin")
    ap.add_argument("--no-git", action="store_true")
    args = ap.parse_args()

    project_dir = Path(args.project_dir).resolve()
    data_dir = (
        Path(args.data_dir).resolve()
        if args.data_dir
        else (project_dir / "chess_dob").resolve()
    )
    repo = validate_git_repo(Path(args.repo))

    print("Chess project dir:", project_dir)
    print("Chess data dir:   ", data_dir)
    print("Git repository:   ", repo)

    # Show exactly where the push will go before doing any work.
    remote_url = run(
        ["git", "remote", "get-url", args.remote],
        repo,
        check=False,
    ).strip()
    if not args.no_git and not remote_url:
        raise RuntimeError(
            f"Git remote {args.remote!r} is not configured in {repo}"
        )
    if remote_url:
        print(f"Git remote {args.remote}: {remote_url}")

    if not args.no_git:
        staged_pre = [
            x.strip().replace("\\", "/")
            for x in run(
                ["git", "diff", "--cached", "--name-only"], repo
            ).splitlines()
            if x.strip()
        ]
        if staged_pre:
            output_prefix = (
                args.output_subdir.replace("\\", "/").strip("/") + "/"
            )
            unrelated = [
                x for x in staged_pre
                if not x.startswith(output_prefix)
            ]
            if unrelated:
                raise RuntimeError(
                    "Git index contains staged files outside the chess freeze "
                    "output. Commit/unstage them first:\n"
                    + "\n".join(unrelated)
                )
            print(
                "Detected staged chess-freeze files from a previous interrupted "
                "run; will verify the exact staged set before commit."
            )

        if run(["git", "tag", "--list", args.tag], repo).strip():
            raise RuntimeError(f"Tag already exists: {args.tag}")

    f94m = require_data(data_dir, "repaired_v2_top_1994_M.csv")
    f94f = require_data(data_dir, "repaired_v2_top_1994_F.csv")
    f13m = require_data(data_dir, "enriched_top_2013_M.csv")
    f13f = require_data(data_dir, "enriched_top_2013_F.csv")
    faud = require_audit(project_dir, data_dir, args.audit)

    s94m, s94f, s13m, s13f = map(read_csv, [f94m, f94f, f13m, f13f])
    audit = load_audit(faud)

    assert_n("1994 M source", len(s94m), EXPECTED["1994_M_source"])
    assert_n("1994 F source", len(s94f), EXPECTED["1994_F_source"])
    assert_n("2013 M source", len(s13m), EXPECTED["2013_M_source"])
    assert_n("2013 F source", len(s13f), EXPECTED["2013_F_source"])
    for d, label in [(s94m,"1994 M"),(s94f,"1994 F"),(s13m,"2013 M"),(s13f,"2013 F")]:
        assert_unique(d, label)

    p94m, a94m = freeze_1994(s94m, audit, "M")
    p94f, a94f = freeze_1994(s94f, audit, "F")
    p13m = freeze_2013(s13m, "M")
    p13f = freeze_2013(s13f, "F")

    checks = [
        ("1994 M clean", len(p94m), EXPECTED["1994_M_clean"]),
        ("1994 F clean", len(p94f), EXPECTED["1994_F_clean"]),
        ("1994 M adj", len(a94m), EXPECTED["1994_M_adj"]),
        ("1994 F adj", len(a94f), EXPECTED["1994_F_adj"]),
        ("2013 M clean", len(p13m), EXPECTED["2013_M_clean"]),
        ("2013 F clean", len(p13f), EXPECTED["2013_F_clean"]),
    ]
    for label, actual, expected in checks:
        assert_n(label, actual, expected)

    for d, label in [(p94m,"p94m"),(p94f,"p94f"),(a94m,"a94m"),(a94f,"a94f"),(p13m,"p13m"),(p13f,"p13f")]:
        assert_unique(d, label)
        if d["exact_dob_frozen"].isna().any():
            raise RuntimeError(f"{label}: null exact_dob_frozen")

    out = (repo / args.output_subdir).resolve()

    # Refuse to write outside the selected Git repo.
    try:
        out.relative_to(repo)
    except ValueError:
        raise RuntimeError(
            f"--output-subdir resolves outside the Git repository: {out}"
        )

    out.mkdir(parents=True, exist_ok=True)
    outputs = {
        "p94m": out / "primary_clean_top_1994_M.csv",
        "p94f": out / "primary_clean_top_1994_F.csv",
        "a94m": out / "sensitivity_adjudicated_top_1994_M.csv",
        "a94f": out / "sensitivity_adjudicated_top_1994_F.csv",
        "p13m": out / "primary_clean_top_2013_M.csv",
        "p13f": out / "primary_clean_top_2013_F.csv",
    }
    for d, key in [(p94m,"p94m"),(p94f,"p94f"),(a94m,"a94m"),(a94f,"a94f"),(p13m,"p13m"),(p13f,"p13f")]:
        d.to_csv(outputs[key], index=False, encoding="utf-8-sig")

    audit_copy = out / "1994_final_audit_resolved_v1.csv"
    shutil.copy2(faud, audit_copy)

    summary = {
        "stage": "chess cohort/preregistration freeze; no BaZi",
        "primary_rule_1994": "exclude unresolved DOB and all credible exact-date source conflicts",
        "sensitivity_rule_1994": "include manually adjudicated conflicts; unresolved remain excluded",
        "primary_rule_2013": "require pre-reveal exact_dob_final; no imputation",
        "primary": {
            "1994_M": stats(p94m), "1994_F": stats(p94f),
            "2013_M": stats(p13m), "2013_F": stats(p13f),
        },
        "sensitivity": {
            "1994_M_adjudicated": stats(a94m),
            "1994_F_adjudicated": stats(a94f),
        },
        "excluded_from_1994_primary": {
            "source_conflict_unique": int(audit["_conflict"].sum()),
            "unresolved_unique": int(audit["_exclude"].sum()),
        },
        "performance_endpoint_primary": "elo_z_within_snapshot_sex",
        "secondary_performance_fields": [
            "rating", "analysis_rank_within_sex",
            "rank_percentile_within_snapshot_sex"
        ],
    }

    summary_path = out / "chess_cohort_freeze_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    prereg_path = out / "CHESS_PREREGISTRATION.md"
    prereg_path.write_text(prereg(summary), encoding="utf-8")

    generated = list(outputs.values()) + [audit_copy, summary_path, prereg_path]
    print("\n=== FREEZE SUMMARY ===")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print("\nGenerated:")
    for p in generated:
        print(" ", p.relative_to(repo))

    if args.no_git:
        print("\n--no-git: files generated; Git untouched.")
        return

    # Track the exact generator used for the freeze even though the working
    # script may live outside the Git repo.
    generator_copy = out / "freeze_chess_study_v2.py"
    shutil.copy2(Path(__file__).resolve(), generator_copy)
    generated.append(generator_copy)

    add_paths = [str(p.relative_to(repo)) for p in generated]

    run(["git", "add", "--", *add_paths], repo)
    staged = {
        x.strip().replace("\\", "/")
        for x in run(
            ["git", "diff", "--cached", "--name-only"], repo
        ).splitlines()
        if x.strip()
    }
    expected_staged = {
        str(Path(x).as_posix())
        for x in add_paths
    }
    if staged != expected_staged:
        raise RuntimeError(
            "Staged-file safety mismatch. "
            f"Expected={sorted(expected_staged)} "
            f"Actual={sorted(staged)}"
        )

    run(["git", "commit", "-m", args.commit_message], repo)
    run([
        "git", "tag", "-a", args.tag, "-m",
        "Freeze chess primary/sensitivity cohorts and preregistration before BaZi reveal"
    ], repo)

    branch = run(["git", "branch", "--show-current"], repo).splitlines()[-1].strip()
    if not branch:
        raise RuntimeError("Detached HEAD: refusing automatic push")
    run(["git", "push", args.remote, branch], repo)
    run(["git", "push", args.remote, args.tag], repo)
    commit = run(["git", "rev-parse", "HEAD"], repo).splitlines()[-1]

    print("\n=== DONE ===")
    print("Commit:", commit)
    print("Tag:   ", args.tag)
    print("Branch:", branch)
    print("Chess cohorts are frozen before BaZi reveal.")


if __name__ == "__main__":
    main()
