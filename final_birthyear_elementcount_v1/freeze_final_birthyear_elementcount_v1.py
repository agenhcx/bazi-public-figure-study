#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
import argparse, shutil, subprocess
from pathlib import Path

PLAN_TAG="final-birthyear-elementcount-plan-v1"
OUTDIR="final_birthyear_elementcount_v1"
REQ=[
    "chess-element-concentration-results-v1",
    "tt-element-concentration-results-v1",
]

PLAN=r"""# Final Birth-Year × Element-Count Temporal Analysis Plan V1

## Status
Final post-hoc exploratory follow-up. This analysis is frozen before the first
calculation of birth-year correlations in the pooled unique-player datasets.

After this analysis, no additional BaZi feature mining will be performed in the
current Music / Table Tennis / Chess project.

## Question
Across ALL available unique players within each domain separately, is birth year
associated with the number of distinct five elements represented in the same
six-position Y/M/D representation already used in the concentration analyses?

Important sign convention:
- "later-born players are MORE concentrated" means FEWER distinct elements.
- Therefore the directional hypothesis is:
  Spearman rho(birth_year, distinct_elements_6pos) < 0.

A positive rho means later-born players have MORE distinct elements, i.e. the
opposite of the concentration hypothesis.

## Domains

### Chess
Use every row already frozen in:
`chess-element-concentration-results-v1:
 chess_element_concentration_v1/element_concentration_player_features.csv`

This contains the eight previously analyzed strata:
1994 M/F, 2013 M/F, 2023 FULL M/F, 2023 NEW_TARGET M/F.

Pool them, then deduplicate so each identifiable person contributes exactly once.
Snapshot membership and FULL/NEW_TARGET status do not enter the test.

Expected source-row count before deduplication: 2807.

### Table tennis
Use:
`tt-element-concentration-results-v1:
 tt_element_concentration_v1/tt_element_concentration_historical_players.csv`
and
`tt-element-concentration-results-v1:
 tt_element_concentration_v1/tt_element_concentration_training_players.csv`

Pool and deduplicate by player identity. Historical and training cohorts were
constructed as non-overlapping; expected unique N after pooling is 719.

## Identity / deduplication rule
Each person contributes once.

Chess identity priority:
1. identity_bridge_modern_fide_id, if present
2. wikidata_person_qids, if present
3. fide_id, if present
4. normalized name + exact frozen DOB fallback

TT identity priority:
1. qid, if present
2. ttr_site_player_id, if present
3. normalized name + DOB fallback

If duplicate identity rows disagree on DOB or `distinct_elements_6pos`, abort.
Otherwise keep one row and retain a source-membership summary.

## Primary analysis: literal pooled birth-year association
Within Chess and TT separately:

Spearman rho:
`birth_year ~ distinct_elements_6pos`

Directional hypothesis:
rho < 0.

Report:
- N unique persons
- birth-year range
- rho
- permutation one-sided p for rho < 0
- permutation two-sided p

Permutation count: 50,000.
Seed: 20260928.

This is the literal answer to the temporal question.

## Essential calendar-adjusted analysis
Because BaZi feature frequencies can vary mechanically with Gregorian birth year,
calculate the exact Gregorian-calendar distribution for every represented birth
year using the same convention:
- Gregorian civil date
- 12:00 noon
- lunar-python
- year/month/day only
- same six positions and branch-main-qi mapping

For each birth year y calculate:
- calendar mean of `distinct_elements_6pos`
- calendar SD

For each real player:
`distinct_z_vs_birthyear_calendar =
 (observed_distinct - calendar_mean_y) / calendar_sd_y`

Then test:
`Spearman(birth_year, distinct_z_vs_birthyear_calendar) < 0`

This is the key analysis for whether a temporal association exceeds the calendar's
own birth-year structure.

## Secondary sensitivity
For each domain:
1. collapse to one row per birth year,
2. calculate the mean calendar-adjusted z among players born that year,
3. Spearman correlation of birth year with the year-level mean z.

This gives each represented birth year equal weight.

Also report male and female pooled-person correlations descriptively when sex is
available. They are not separate confirmatory claims.

## Interpretation
- A raw negative correlation without a calendar-adjusted negative correlation is
  not evidence of an athlete-specific temporal concentration shift.
- A negative adjusted correlation in one domain only is domain-specific exploratory
  evidence, not a general BaZi law.
- Concordant negative adjusted correlations in both Chess and TT are a cross-domain
  exploratory pattern requiring future independent validation.
- Null or opposite results are retained.
- No new cutoffs, feature definitions, subgroups, or alternate concentration
  metrics will be introduced after reveal.
"""

def run(cmd,cwd):
    print("$"," ".join(cmd))
    p=subprocess.run(cmd,cwd=str(cwd),text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    if p.stdout: print(p.stdout.rstrip())
    if p.returncode: raise RuntimeError("Command failed: "+" ".join(cmd))
    return p.stdout.strip()

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--repo",default=r"..\1986wiki")
    ap.add_argument("--remote",default="origin")
    ap.add_argument("--no-git",action="store_true")
    a=ap.parse_args()
    repo=Path(run(["git","rev-parse","--show-toplevel"],Path(a.repo))).resolve()
    for t in REQ:
        if run(["git","tag","--list",t],repo)!=t:
            raise RuntimeError(f"Required result tag missing: {t}")
    if not a.no_git:
        if run(["git","diff","--cached","--name-only"],repo):
            raise RuntimeError("Git index already has staged files")
        if run(["git","tag","--list",PLAN_TAG],repo):
            raise RuntimeError(f"Tag already exists: {PLAN_TAG}")

    out=repo/OUTDIR
    out.mkdir(parents=True,exist_ok=True)
    plan=out/"FINAL_BIRTHYEAR_ELEMENTCOUNT_PLAN_V1.md"
    plan.write_text(PLAN,encoding="utf-8")
    copy=out/"freeze_final_birthyear_elementcount_v1.py"
    shutil.copy2(Path(__file__).resolve(),copy)
    print("\n=== FINAL TEMPORAL PLAN WRITTEN ===")
    print(plan)

    if a.no_git:
        return

    rels=[plan.relative_to(repo).as_posix(),copy.relative_to(repo).as_posix()]
    run(["git","add","--",*rels],repo)
    actual={x.replace("\\","/") for x in run(["git","diff","--cached","--name-only"],repo).splitlines() if x.strip()}
    if actual!=set(rels):
        raise RuntimeError(f"Staging mismatch: expected={sorted(rels)} actual={sorted(actual)}")
    run(["git","commit","-m","Freeze final birth-year element-count temporal analysis plan"],repo)
    run(["git","tag","-a",PLAN_TAG,"-m","Freeze final temporal analysis before first calculation"],repo)
    branch=run(["git","branch","--show-current"],repo)
    if not branch: raise RuntimeError("Detached HEAD")
    run(["git","push",a.remote,branch],repo)
    run(["git","push",a.remote,PLAN_TAG],repo)
    print("\n=== FINAL TEMPORAL PLAN FROZEN ===")
    print("Commit:",run(["git","rev-parse","HEAD"],repo))
    print("Tag:   ",PLAN_TAG)

if __name__=="__main__":
    main()
