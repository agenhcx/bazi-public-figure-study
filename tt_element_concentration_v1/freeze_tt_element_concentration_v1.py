#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
import argparse, shutil, subprocess
from pathlib import Path

PLAN_TAG='tt-element-concentration-plan-v1'
OUTDIR='tt_element_concentration_v1'
REQUIRED_TAGS=['tt-holdout-lock-v1','tt-performance-lock-v1','chess-preregister-v3-date-sanity','chess-element-concentration-results-v1']
PLAN=r'''# Table-Tennis Elemental-Concentration Cross-Domain Plan V1

## Evidence status
This hypothesis was imported after the chess elemental-concentration results were revealed.
Therefore this is **cross-domain exploratory validation**, with the analysis plan frozen before the first TT concentration calculation. It is not part of the original TT H1-H5 confirmatory family.

## Fixed hypothesis and representation
Use exactly the same six known positions as chess:
- year stem; year branch main qi
- month stem; month branch main qi
- day stem; day branch main qi

No birth hour, hidden secondary stems, transformations, 格局 reclassification, or post-result weighting.
Branch main qi: 子癸 丑己 寅甲 卯乙 辰戊 巳丙 午丁 未己 申庚 酉辛 戌戊 亥壬.
BaZi convention: Gregorian DOB at 12:00 noon, lunar-python, year/month/day only.

Primary metric: `distinct_elements_6pos` (1-5).
Secondary robustness: `dominant_element_share`, `hhi_element_concentration`, `element_entropy`, `all_five_present_6pos`.
These secondary metrics are correlated robustness measures, not independent replications.

## H1 — historical TT selection (PRIMARY)
Frozen 1950-1984 historical holdout, expected N=335.
Prediction: mean distinct_elements_6pos < same-birth-year Gregorian-calendar null.
Secondary directions: dominant share > null; HHI > null; entropy < null; all-five-present < null.
20,000 calendar simulations by default.
Sex-specific results descriptive.

## H2 — historical TT performance (PRIMARY)
Frozen historical performance subset, expected N=112.
Use existing within-gender x birth-decade `strength_percentile`.
Prediction: Spearman rho(distinct_elements_6pos, strength_percentile) < 0.
Secondary directions: dominant share >0; HHI >0; entropy <0; all-five-present <0.
50,000 permutations by default.
Sex-specific results descriptive.

## H3 — 1985-2008 training extension (SECONDARY)
Training cohort expected N=384. Selection uses same calendar null.
Performance uses reliable dynamic peak Elo and `peak_elo_gender_z`.
This cohort was already used for hypothesis generation and cannot independently confirm the hypothesis.

## Provenance
Historical preferred archived reveal outputs:
- tt_holdout_reveal_v1_player_bazi.csv (N=335)
- tt_holdout_reveal_v1_performance_player_data.csv (N=112)
Original frozen inputs are also accepted if still available.

Training inputs are read from exact Git blobs at tag `chess-preregister-v3-date-sanity`:
- studies/table_tennis/data/tabletennis_reference_enriched.csv
- studies/table_tennis/data/ttr_elo_player_summary.csv

## Interpretation rule
Historical holdout/performance are primary for this cross-domain extension.
Training is secondary. Do not switch the primary metric after reveal. Do not promote a favorable secondary metric over a null/reversed distinct-elements primary. No new weights, hidden stems, transformations, subgroups, or rescue analyses after reveal.
Seed: 20260928.
'''

def run(cmd,cwd,check=True):
    print('$',' '.join(cmd)); p=subprocess.run(cmd,cwd=str(cwd),text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    if p.stdout: print(p.stdout.rstrip())
    if check and p.returncode!=0: raise RuntimeError('Command failed: '+' '.join(cmd))
    return p.stdout.strip()

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--repo',default=r'..\1986wiki'); ap.add_argument('--remote',default='origin'); ap.add_argument('--no-git',action='store_true'); a=ap.parse_args()
    repo=Path(run(['git','rev-parse','--show-toplevel'],Path(a.repo))).resolve()
    for tag in REQUIRED_TAGS:
        if not run(['git','tag','--list',tag],repo).strip(): raise RuntimeError(f'Required prior tag missing: {tag}')
    if not a.no_git:
        staged=run(['git','diff','--cached','--name-only'],repo).strip()
        if staged: raise RuntimeError('Git index already has staged files:\n'+staged)
        if run(['git','tag','--list',PLAN_TAG],repo).strip(): raise RuntimeError(f'Tag already exists: {PLAN_TAG}')
    out=repo/OUTDIR; out.mkdir(parents=True,exist_ok=True)
    plan=out/'EXPLORATORY_PLAN_TT_ELEMENT_CONCENTRATION_V1.md'; plan.write_text(PLAN,encoding='utf-8')
    copy=out/'freeze_tt_element_concentration_v1.py'; shutil.copy2(Path(__file__).resolve(),copy)
    print('\n=== TT ELEMENT-CONCENTRATION PLAN WRITTEN ==='); print(plan)
    if a.no_git: return
    rels=[plan.relative_to(repo).as_posix(),copy.relative_to(repo).as_posix()]
    run(['git','add','--',*rels],repo)
    actual={x.replace('\\','/') for x in run(['git','diff','--cached','--name-only'],repo).splitlines() if x.strip()}; expected=set(rels)
    if actual!=expected: raise RuntimeError(f'Staging mismatch: expected={sorted(expected)} actual={sorted(actual)}')
    run(['git','commit','-m','Freeze TT elemental-concentration cross-domain analysis plan'],repo)
    run(['git','tag','-a',PLAN_TAG,'-m','Freeze TT concentration plan before first TT calculation'],repo)
    branch=run(['git','branch','--show-current'],repo)
    run(['git','push',a.remote,branch],repo); run(['git','push',a.remote,PLAN_TAG],repo)
    print('\n=== TT ELEMENT-CONCENTRATION PLAN FROZEN ==='); print('Commit:',run(['git','rev-parse','HEAD'],repo)); print('Tag:   ',PLAN_TAG)
if __name__=='__main__': main()
