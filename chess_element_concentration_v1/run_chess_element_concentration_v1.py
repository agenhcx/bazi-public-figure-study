#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Run the frozen post-reveal exploratory chess elemental-concentration analysis.

Requires:
  chess-element-concentration-plan-v1

Reads cohort bytes directly from frozen Git tags.
Default Git actions:
  commit
  annotated tag: chess-element-concentration-results-v1
  push branch and tag
"""

from __future__ import annotations
import argparse, calendar, io, json, math, shutil, subprocess
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import rankdata
import sxtwl

PLAN_TAG="chess-element-concentration-plan-v1"
RESULT_TAG="chess-element-concentration-results-v1"
HIST_TAG="chess-preregister-v3-date-sanity"
Y2023_TAG="chess-2023-cohorts-frozen-v1"
OUTDIR="chess_element_concentration_v1"

STEMS=list("甲乙丙丁戊己庚辛壬癸")
STEM_ELEMENT=np.array(["木","木","火","火","土","土","金","金","水","水"],dtype=object)
BRANCH_MAIN_STEM=np.array([9,5,0,1,4,2,3,5,6,7,4,8],dtype=int)
ELEMENTS=["木","火","土","金","水"]
METRICS=[
    ("distinct_elements_6pos","less"),
    ("dominant_element_share","greater"),
    ("hhi_element_concentration","greater"),
    ("element_entropy","less"),
    ("all_five_present_6pos","less"),
]
EXPECTED={
    "1994_M":501,"1994_F":201,"2013_M":501,"2013_F":200,
    "2023_M_FULL":501,"2023_F_FULL":202,
    "2023_M_NEW_TARGET":501,"2023_F_NEW_TARGET":200,
}

def run(cmd,cwd,check=True):
    print("$"," ".join(cmd))
    p=subprocess.run(cmd,cwd=str(cwd),text=True,
                     stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    if p.stdout: print(p.stdout.rstrip())
    if check and p.returncode!=0:
        raise RuntimeError("Command failed: "+" ".join(cmd))
    return p.stdout.strip()

def run_bytes(cmd,cwd):
    p=subprocess.run(cmd,cwd=str(cwd),stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    if p.returncode!=0:
        raise RuntimeError(p.stderr.decode("utf-8","replace"))
    return p.stdout

def git_root(p):
    return Path(run(["git","rev-parse","--show-toplevel"],p)).resolve()

def tree_paths(repo,tag):
    out=run(["git","ls-tree","-r","--name-only",tag],repo)
    return [x.strip() for x in out.splitlines() if x.strip()]

def read_csv_tag_path(repo,tag,path):
    paths=set(tree_paths(repo,tag))
    if path not in paths:
        raise RuntimeError(f"{tag}: required frozen path missing: {path}")
    b=run_bytes(["git","show",f"{tag}:{path}"],repo)
    d=pd.read_csv(io.BytesIO(b))
    print(f"[input] {tag}:{path} n={len(d)}")
    return d, path

def concentration_features(y,m,d):
    x=sxtwl.fromSolar(int(y),int(m),int(d))
    yg,mg,dg=x.getYearGZ(),x.getMonthGZ(),x.getDayGZ()
    stem_idx=[
        yg.tg, int(BRANCH_MAIN_STEM[yg.dz]),
        mg.tg, int(BRANCH_MAIN_STEM[mg.dz]),
        dg.tg, int(BRANCH_MAIN_STEM[dg.dz])
    ]
    els=[str(STEM_ELEMENT[i]) for i in stem_idx]
    counts={e:els.count(e) for e in ELEMENTS}
    vals=np.array([counts[e] for e in ELEMENTS],float)
    p=vals/6.0
    positive=p[p>0]
    distinct=int((vals>0).sum())
    return {
        "elements_6pos":"|".join(els),
        "wood_count_6pos":counts["木"],
        "fire_count_6pos":counts["火"],
        "earth_count_6pos":counts["土"],
        "metal_count_6pos":counts["金"],
        "water_count_6pos":counts["水"],
        "distinct_elements_6pos":distinct,
        "dominant_element_share":float(vals.max()/6.0),
        "hhi_element_concentration":float((p*p).sum()),
        "element_entropy":float(-(positive*np.log(positive)).sum()),
        "all_five_present_6pos":int(distinct==5),
    }

def enrich(d,label,sex,zcol):
    d=d.copy().reset_index(drop=True)
    if "exact_dob_frozen" not in d.columns:
        raise RuntimeError(f"{label}: exact_dob_frozen missing")
    if zcol not in d.columns:
        raise RuntimeError(f"{label}: {zcol} missing")
    rec=[]
    for s in d["exact_dob_frozen"].astype(str):
        dt=pd.Timestamp(s[:10])
        rec.append(concentration_features(dt.year,dt.month,dt.day))
    d=pd.concat([d,pd.DataFrame(rec)],axis=1)
    d["analysis_group"]=label
    d["analysis_sex"]=sex
    d["elo_z"]=pd.to_numeric(d[zcol],errors="raise")
    d["birth_year_analysis"]=pd.to_datetime(d["exact_dob_frozen"]).dt.year.astype(int)
    return d

def load_all(repo):
    specs=[
        # Use the FINAL v3 northern/date-sanity cohorts, not older chess_freeze files
        # that are also present in the same historical tag.
        ("1994_M",HIST_TAG,"chess_north_v3/primary_north_top_1994_M.csv","M","elo_z_within_snapshot_sex"),
        ("1994_F",HIST_TAG,"chess_north_v3/primary_north_top_1994_F.csv","F","elo_z_within_snapshot_sex"),
        ("2013_M",HIST_TAG,"chess_north_v3/primary_north_top_2013_M.csv","M","elo_z_within_snapshot_sex"),
        ("2013_F",HIST_TAG,"chess_north_v3/primary_north_top_2013_F.csv","F","elo_z_within_snapshot_sex"),
        ("2023_M_FULL",Y2023_TAG,"chess_2023_cohorts_v1/primary_2023_M_FULL.csv","M","elo_z_within_2023_sex_cohort"),
        ("2023_F_FULL",Y2023_TAG,"chess_2023_cohorts_v1/primary_2023_F_FULL.csv","F","elo_z_within_2023_sex_cohort"),
        ("2023_M_NEW_TARGET",Y2023_TAG,"chess_2023_cohorts_v1/validation_2023_M_NEW_TARGET.csv","M","elo_z_within_2023_sex_cohort"),
        ("2023_F_NEW_TARGET",Y2023_TAG,"chess_2023_cohorts_v1/validation_2023_F_NEW_TARGET.csv","F","elo_z_within_2023_sex_cohort"),
    ]
    out={}
    provenance={}
    for label,tag,base,sex,zcol in specs:
        d,path=read_csv_tag_path(repo,tag,base)
        if len(d)!=EXPECTED[label]:
            raise RuntimeError(f"{label}: n={len(d)} expected={EXPECTED[label]}")
        out[label]=enrich(d,label,sex,zcol)
        provenance[label]={"tag":tag,"path":path,"n":len(d)}
    return out,provenance

def corr_stat(x,y):
    xr=rankdata(np.asarray(x,float))
    yr=rankdata(np.asarray(y,float))
    xr=xr-xr.mean(); yr=yr-yr.mean()
    den=math.sqrt(float((xr*xr).sum()*(yr*yr).sum()))
    return float((xr*yr).sum()/den) if den else np.nan

def perm_spearman(df,xcol,direction,B,rng):
    x=df[xcol].to_numpy(float)
    y=df["elo_z"].to_numpy(float)
    sex=df["analysis_sex"].astype(str).to_numpy()
    xr=rankdata(x); yr=rankdata(y)
    xr=xr-xr.mean(); yr=yr-yr.mean()
    den=math.sqrt(float((xr*xr).sum()*(yr*yr).sum()))
    obs=float((xr*yr).sum()/den) if den else np.nan
    groups=[np.where(sex==s)[0] for s in np.unique(sex)]
    le=ge=tw=done=0
    batch=2000
    while done<B:
        b=min(batch,B-done)
        # Build permuted y-rank rows, preserving sex strata.
        Y=np.tile(yr,(b,1))
        for idx in groups:
            # Random-rank trick gives independent permutations per row.
            order=np.argsort(rng.random((b,len(idx))),axis=1)
            Y[:,idx]=yr[idx][order]
        sims=(Y@xr)/den
        le+=int((sims<=obs+1e-15).sum())
        ge+=int((sims>=obs-1e-15).sum())
        tw+=int((np.abs(sims)>=abs(obs)-1e-15).sum())
        done+=b
    pdir=(le+1)/(B+1) if direction=="less" else (ge+1)/(B+1)
    return {
        "n":len(df),"rho":obs,"direction":direction,
        "p_directional":pdir,"p_two_sided":(tw+1)/(B+1),
        "permutations":B,
    }

def all_dates(y):
    for m in range(1,13):
        for d in range(1,calendar.monthrange(int(y),m)[1]+1):
            yield m,d

def build_calendar_cache(years):
    cache={}
    for y in sorted(set(map(int,years))):
        rows=[]
        for m,d in all_dates(y):
            f=concentration_features(y,m,d)
            rows.append([f[k] for k,_ in METRICS])
        cache[y]=np.asarray(rows,float)
    return cache

def selection_mc(df,cache,B,rng):
    obs=np.array([df[k].mean() for k,_ in METRICS],float)
    sims=np.zeros((B,len(METRICS)),float)
    # Sum individual metric values, grouped efficiently by birth year.
    for y,n in df["birth_year_analysis"].value_counts().sort_index().items():
        arr=cache[int(y)]
        done=0; batch=2000
        while done<B:
            b=min(batch,B-done)
            idx=rng.integers(0,len(arr),size=(b,int(n)))
            sims[done:done+b]+=arr[idx].sum(axis=1)
            done+=b
    sims/=len(df)
    out={}
    for j,(metric,direction) in enumerate(METRICS):
        mu=float(sims[:,j].mean()); sd=float(sims[:,j].std(ddof=1))
        val=float(obs[j])
        le=(int((sims[:,j]<=val+1e-15).sum())+1)/(B+1)
        ge=(int((sims[:,j]>=val-1e-15).sum())+1)/(B+1)
        tw=min(1.0,2*min(le,ge))
        out[metric]={
            "n":len(df),"observed_mean":val,"null_mean":mu,"null_sd":sd,
            "z":float((val-mu)/sd) if sd else None,
            "direction":direction,
            "p_directional":le if direction=="less" else ge,
            "p_two_sided":tw,"simulations":B,
        }
    return out

def group_sets(data):
    g=dict(data)
    g["1994_POOLED"]=pd.concat([data["1994_M"],data["1994_F"]],ignore_index=True)
    g["2013_POOLED"]=pd.concat([data["2013_M"],data["2013_F"]],ignore_index=True)
    g["2023_FULL_POOLED"]=pd.concat([data["2023_M_FULL"],data["2023_F_FULL"]],ignore_index=True)
    g["2023_NEW_TARGET_POOLED"]=pd.concat([data["2023_M_NEW_TARGET"],data["2023_F_NEW_TARGET"]],ignore_index=True)
    return g

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--repo",default=r"..\1986wiki")
    ap.add_argument("--perf-perm",type=int,default=50000)
    ap.add_argument("--null-sims",type=int,default=20000)
    ap.add_argument("--seed",type=int,default=20260927)
    ap.add_argument("--remote",default="origin")
    ap.add_argument("--no-git",action="store_true")
    a=ap.parse_args()

    repo=git_root(Path(a.repo))
    if not run(["git","tag","--list",PLAN_TAG],repo).strip():
        raise RuntimeError(f"Plan tag missing: {PLAN_TAG}; freeze first.")
    if not a.no_git:
        if run(["git","tag","--list",RESULT_TAG],repo).strip():
            raise RuntimeError(f"Results tag already exists: {RESULT_TAG}")

    print("\nImplementation fix V1.2: loading exact frozen v3/v1 cohort paths from Git tags.")
    print("Prior aborted run stopped at cohort-size validation, before concentration features were calculated.")
    print("\n=== FIRST ELEMENT-CONCENTRATION CALCULATION ===")
    data,provenance=load_all(repo)
    groups=group_sets(data)

    years=[]
    for d in data.values():
        years+=d["birth_year_analysis"].tolist()
    cache=build_calendar_cache(years)
    rng=np.random.default_rng(a.seed)

    perf={}
    for label,d in groups.items():
        perf[label]={}
        for metric,direction in METRICS:
            perf[label][metric]=perm_spearman(d,metric,direction,a.perf_perm,rng)

    selection={}
    for label,d in groups.items():
        selection[label]=selection_mc(d,cache,a.null_sims,rng)

    eight=[
        "1994_M","1994_F","2013_M","2013_F",
        "2023_M_FULL","2023_F_FULL",
        "2023_M_NEW_TARGET","2023_F_NEW_TARGET"
    ]
    perf_neg=sum(perf[x]["distinct_elements_6pos"]["rho"]<0 for x in eight)
    sel_less=sum(
        selection[x]["distinct_elements_6pos"]["observed_mean"] <
        selection[x]["distinct_elements_6pos"]["null_mean"]
        for x in eight
    )

    result={
        "analysis_role":"post_reveal_exploratory_plan_frozen_before_feature_calculation",
        "plan_tag":PLAN_TAG,
        "historical_source_tag":HIST_TAG,
        "source_2023_tag":Y2023_TAG,
        "seed":a.seed,
        "performance_permutations":a.perf_perm,
        "calendar_null_simulations":a.null_sims,
        "provenance":provenance,
        "primary_performance":{
            "sample":"2023_NEW_TARGET_POOLED",
            "metric":"distinct_elements_6pos",
            **perf["2023_NEW_TARGET_POOLED"]["distinct_elements_6pos"],
        },
        "primary_selection":{
            "sample":"2023_NEW_TARGET_POOLED",
            "metric":"distinct_elements_6pos",
            **selection["2023_NEW_TARGET_POOLED"]["distinct_elements_6pos"],
        },
        "direction_consistency":{
            "performance_negative_rho_count_of_8":int(perf_neg),
            "selection_observed_below_null_count_of_8":int(sel_less),
        },
        "performance":perf,
        "selection":selection,
    }

    out=repo/OUTDIR
    out.mkdir(parents=True,exist_ok=True)

    # Player-level feature file. A player can appear in more than one historical snapshot;
    # keep cohort rows because Elo endpoint is snapshot-specific.
    player=pd.concat([data[k] for k in eight],ignore_index=True)
    player_path=out/"element_concentration_player_features.csv"
    player.to_csv(player_path,index=False,encoding="utf-8-sig")

    prows=[]
    for group,res in perf.items():
        for metric,r in res.items():
            prows.append({"group":group,"metric":metric,**r})
    perf_path=out/"element_concentration_performance_tests.csv"
    pd.DataFrame(prows).to_csv(perf_path,index=False,encoding="utf-8-sig")

    srows=[]
    for group,res in selection.items():
        for metric,r in res.items():
            srows.append({"group":group,"metric":metric,**r})
    sel_path=out/"element_concentration_selection_tests.csv"
    pd.DataFrame(srows).to_csv(sel_path,index=False,encoding="utf-8-sig")

    json_path=out/"element_concentration_results_v1.json"
    json_path.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")

    md=[]
    md.append("# Chess Elemental-Concentration Results V1")
    md.append("")
    md.append("Status: post-reveal exploratory; plan frozen before first concentration calculation.")
    md.append("")
    pp=result["primary_performance"]
    ps=result["primary_selection"]
    md.append("## Frozen primary performance test")
    md.append(
        f"- 2023 NEW_TARGET pooled: distinct-elements vs Elo-z "
        f"rho={pp['rho']:.5f}, directional p={pp['p_directional']:.6f}, "
        f"two-sided p={pp['p_two_sided']:.6f}"
    )
    md.append("")
    md.append("## Frozen primary selection test")
    md.append(
        f"- 2023 NEW_TARGET pooled: observed mean distinct elements="
        f"{ps['observed_mean']:.5f}, null={ps['null_mean']:.5f}, "
        f"z={ps['z']:.4f}, directional p={ps['p_directional']:.6f}"
    )
    md.append("")
    md.append("## Eight-stratum direction consistency")
    md.append(f"- Performance rho<0: {perf_neg}/8")
    md.append(f"- Selection observed<null: {sel_less}/8")
    md.append("")
    md.append("## Distinct-elements performance by stratum")
    for x in eight:
        r=perf[x]["distinct_elements_6pos"]
        md.append(f"- {x}: rho={r['rho']:.5f}, p_dir={r['p_directional']:.6f}")
    md.append("")
    md.append("## Distinct-elements selection by stratum")
    for x in eight:
        r=selection[x]["distinct_elements_6pos"]
        md.append(
            f"- {x}: obs={r['observed_mean']:.5f}, null={r['null_mean']:.5f}, "
            f"z={r['z']:.4f}, p_dir={r['p_directional']:.6f}"
        )
    md_path=out/"CHESS_ELEMENT_CONCENTRATION_RESULTS_V1.md"
    md_path.write_text("\n".join(md),encoding="utf-8")

    script_copy=out/"run_chess_element_concentration_v1.py"
    shutil.copy2(Path(__file__).resolve(),script_copy)

    print("\n=== ELEMENT CONCENTRATION HEADLINE ===")
    print(
        f"PRIMARY PERFORMANCE 2023 NEW_TARGET pooled: "
        f"rho={pp['rho']:.5f} p_dir={pp['p_directional']:.6f}"
    )
    print(
        f"PRIMARY SELECTION 2023 NEW_TARGET pooled: "
        f"obs={ps['observed_mean']:.5f} null={ps['null_mean']:.5f} "
        f"z={ps['z']:.4f} p_dir={ps['p_directional']:.6f}"
    )
    print(f"Performance direction consistency: {perf_neg}/8 rho<0")
    print(f"Selection direction consistency: {sel_less}/8 obs<null")
    print("\nPERFORMANCE DISTINCT ELEMENTS")
    for x in eight:
        r=perf[x]["distinct_elements_6pos"]
        print(f"{x}: rho={r['rho']:.5f} p_dir={r['p_directional']:.6f}")
    print("\nSELECTION DISTINCT ELEMENTS")
    for x in eight:
        r=selection[x]["distinct_elements_6pos"]
        print(
            f"{x}: obs={r['observed_mean']:.5f} null={r['null_mean']:.5f} "
            f"z={r['z']:.4f} p_dir={r['p_directional']:.6f}"
        )
    print("\nSECONDARY ROBUSTNESS — PRIMARY SAMPLE")
    for metric,_ in METRICS[1:]:
        pr=perf["2023_NEW_TARGET_POOLED"][metric]
        sr=selection["2023_NEW_TARGET_POOLED"][metric]
        print(
            f"{metric}: performance rho={pr['rho']:.5f} p={pr['p_directional']:.6f} | "
            f"selection obs={sr['observed_mean']:.5f} null={sr['null_mean']:.5f} "
            f"p={sr['p_directional']:.6f}"
        )

    if a.no_git:
        print("\n--no-git: results generated; Git untouched.")
        return

    generated=[player_path,perf_path,sel_path,json_path,md_path,script_copy]
    rels=[p.relative_to(repo).as_posix() for p in generated]
    run(["git","add","--",*rels],repo)
    actual={x.replace("\\","/") for x in run(["git","diff","--cached","--name-only"],repo).splitlines() if x.strip()}
    expected={x.replace("\\","/") for x in rels}
    if actual != expected:
        raise RuntimeError(f"Staging mismatch: expected={sorted(expected)} actual={sorted(actual)}")
    run(["git","commit","-m",
         "Add exploratory chess elemental-concentration results"],repo)
    run(["git","tag","-a",RESULT_TAG,"-m",
         "Record elemental-concentration exploratory results"],repo)
    branch=run(["git","branch","--show-current"],repo)
    if not branch:
        raise RuntimeError("Detached HEAD; refusing push")
    run(["git","push",a.remote,branch],repo)
    run(["git","push",a.remote,RESULT_TAG],repo)

    print("\n=== ELEMENT CONCENTRATION RESULTS FROZEN ===")
    print("Commit:",run(["git","rev-parse","HEAD"],repo))
    print("Tag:   ",RESULT_TAG)
    print("Output:",out)

if __name__=="__main__":
    main()
