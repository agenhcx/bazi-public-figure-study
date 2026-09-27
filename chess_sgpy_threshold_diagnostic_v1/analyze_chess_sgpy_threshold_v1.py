#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Post-reveal diagnostic: how common is "at least one 伤官 or 偏印"
among the six known positions?

Positions:
1 year stem
2 year branch main qi
3 month stem
4 month branch main qi
5 day stem
6 day branch main qi

No hour, no secondary hidden stems, no 三合/三会/六合 transformations.

Reads chess_first_reveal_v1/bazi_*.csv.
Compares observed binary rates to same-birth-year calendar base rates.
Also prints the highest-rated player with no 伤官 and no 偏印.
"""

from __future__ import annotations
import argparse, calendar, json, shutil, subprocess
from pathlib import Path
import numpy as np
import pandas as pd
import sxtwl

STEMS="甲乙丙丁戊己庚辛壬癸"
BRANCHES="子丑寅卯辰巳午未申酉戌亥"
STEM_ELEMENT=["木","木","火","火","土","土","金","金","水","水"]
STEM_YANG=[1,0,1,0,1,0,1,0,1,0]
BRANCH_MAIN_STEM=[9,5,0,1,4,2,3,5,6,7,4,8]
POSITIONS=[
    "year_stem","year_branch_main_qi","month_stem",
    "month_branch_main_qi","day_stem","day_branch_main_qi"
]
FILES={
    "1994_M":"bazi_1994_M.csv",
    "1994_F":"bazi_1994_F.csv",
    "2013_M":"bazi_2013_M.csv",
    "2013_F":"bazi_2013_F.csv",
}
METRICS=["has_SG","has_PY","has_SG_or_PY","has_both"]

def run(cmd,cwd,check=True):
    print("$"," ".join(cmd))
    p=subprocess.run(cmd,cwd=str(cwd),text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    if p.stdout: print(p.stdout.rstrip())
    if check and p.returncode!=0:
        raise RuntimeError(f"Command failed ({p.returncode}): {' '.join(cmd)}")
    return p.stdout.strip()

def git_root(p):
    return Path(run(["git","rev-parse","--show-toplevel"],p).splitlines()[-1]).resolve()

def tengod(dm,t):
    de,te=STEM_ELEMENT[dm],STEM_ELEMENT[t]
    same=STEM_YANG[dm]==STEM_YANG[t]
    gen={"木":"火","火":"土","土":"金","金":"水","水":"木"}
    ctl={"木":"土","土":"水","水":"火","火":"金","金":"木"}
    if te==de: return "比肩" if same else "劫财"
    if gen[de]==te: return "食神" if same else "伤官"
    if gen[te]==de: return "偏印" if same else "正印"
    if ctl[de]==te: return "偏财" if same else "正财"
    if ctl[te]==de: return "七杀" if same else "正官"
    raise RuntimeError((dm,t))

def six_gods(y,m,d):
    x=sxtwl.fromSolar(int(y),int(m),int(d))
    yg,mg,dg=x.getYearGZ(),x.getMonthGZ(),x.getDayGZ()
    ts=[
        yg.tg,BRANCH_MAIN_STEM[yg.dz],
        mg.tg,BRANCH_MAIN_STEM[mg.dz],
        dg.tg,BRANCH_MAIN_STEM[dg.dz]
    ]
    return [tengod(dg.tg,t) for t in ts]

def flags(g):
    sg=sum(x=="伤官" for x in g)
    py=sum(x=="偏印" for x in g)
    return {
        "SG_count":sg,"PY_count":py,
        "has_SG":sg>0,"has_PY":py>0,
        "has_SG_or_PY":sg+py>0,
        "has_both":sg>0 and py>0
    }

def enrich(df,key):
    rows=[]
    for _,r in df.iterrows():
        raw=str(r.get("six_position_tengods","")).strip()
        gods=raw.split("|") if raw else []
        if len(gods)!=6:
            dt=pd.Timestamp(str(r["exact_dob_frozen"])[:10])
            gods=six_gods(dt.year,dt.month,dt.day)
        z={"cohort":key,**flags(gods)}
        for p,g in zip(POSITIONS,gods):
            z[p+"_tengod"]=g
            z[p+"_is_SG"]=g=="伤官"
            z[p+"_is_PY"]=g=="偏印"
        rows.append(z)
    return pd.concat([df.reset_index(drop=True),pd.DataFrame(rows)],axis=1)

def year_table(y):
    rows=[]
    for m in range(1,13):
        for d in range(1,calendar.monthrange(y,m)[1]+1):
            gods=six_gods(y,m,d)
            z=flags(gods)
            row={**z}
            for p,g in zip(POSITIONS,gods):
                row[p+"_is_SG"]=int(g=="伤官")
                row[p+"_is_PY"]=int(g=="偏印")
            rows.append(row)
    return pd.DataFrame(rows)

def weighted_rate(years,cache,metric):
    return float(np.mean([cache[int(y)][metric].mean() for y in years]))

def mc(years,cache,metric,obs,n_sims,rng):
    sims=np.zeros(n_sims,dtype=int)
    for y,n in years.value_counts().sort_index().items():
        vals=cache[int(y)][metric].to_numpy(dtype=int)
        idx=rng.integers(0,len(vals),size=(n_sims,int(n)))
        sims += vals[idx].sum(axis=1)
    mean=float(sims.mean()); sd=float(sims.std(ddof=1))
    return {
        "observed_count":int(obs),
        "observed_rate":float(obs/len(years)),
        "weighted_exact_expected_rate":weighted_rate(years,cache,metric),
        "expected_count_mc":mean,
        "null_sd_count":sd,
        "z":float((obs-mean)/sd) if sd>0 else None,
        "empirical_p_high":float((1+(sims>=obs).sum())/(n_sims+1)),
        "empirical_p_low":float((1+(sims<=obs).sum())/(n_sims+1)),
        "n_sims":int(n_sims),
        "null":"uniform Gregorian date within same birth year",
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--repo",default=r"..\1986wiki")
    ap.add_argument("--source-subdir",default="chess_first_reveal_v1")
    ap.add_argument("--output-subdir",default="chess_sgpy_threshold_diagnostic_v1")
    ap.add_argument("--tag",default="chess-postreveal-sgpy-threshold-v1")
    ap.add_argument("--remote",default="origin")
    ap.add_argument("--seed",type=int,default=20260927)
    ap.add_argument("--null-sims",type=int,default=10000)
    ap.add_argument("--no-git",action="store_true")
    a=ap.parse_args()

    repo=git_root(Path(a.repo).resolve())
    src=repo/a.source_subdir
    out=repo/a.output_subdir
    out.mkdir(parents=True,exist_ok=True)

    cohorts={}
    years_all=[]
    for key,f in FILES.items():
        p=src/f
        if not p.exists(): raise FileNotFoundError(p)
        d=pd.read_csv(p)
        need={"fide_id","name","rating","exact_dob_frozen","elo_z_within_snapshot_sex"}
        miss=need-set(d.columns)
        if miss: raise RuntimeError(f"{f}: missing {sorted(miss)}")
        d=enrich(d,key)
        cohorts[key]=d
        years_all += pd.to_datetime(d["exact_dob_frozen"]).dt.year.astype(int).tolist()

    cache={}
    for y in sorted(set(years_all)):
        cache[y]=year_table(y)
        print(f"[calendar] {y}: {len(cache[y])} dates")

    rng=np.random.default_rng(a.seed)
    nulls={}
    summary=[]
    posrows=[]

    for key in ["1994_M","1994_F","2013_M","2013_F"]:
        d=cohorts[key]
        years=pd.to_datetime(d["exact_dob_frozen"]).dt.year.astype(int)
        summary.append({
            "cohort":key,"n":len(d),
            "SG_count_total":int(d["SG_count"].sum()),
            "PY_count_total":int(d["PY_count"].sum()),
            "has_SG_count":int(d["has_SG"].sum()),
            "has_SG_rate":float(d["has_SG"].mean()),
            "has_PY_count":int(d["has_PY"].sum()),
            "has_PY_rate":float(d["has_PY"].mean()),
            "has_SG_or_PY_count":int(d["has_SG_or_PY"].sum()),
            "has_SG_or_PY_rate":float(d["has_SG_or_PY"].mean()),
            "has_both_count":int(d["has_both"].sum()),
            "has_both_rate":float(d["has_both"].mean()),
        })
        nulls[key]={}
        for metric in METRICS:
            nulls[key][metric]=mc(
                years,cache,metric,int(d[metric].sum()),a.null_sims,rng
            )
        for p in POSITIONS:
            for short,label in [("SG","伤官"),("PY","偏印")]:
                col=p+"_is_"+short
                posrows.append({
                    "cohort":key,"position":p,"target":label,
                    "observed_count":int(d[col].sum()),
                    "observed_rate":float(d[col].mean()),
                    "same_year_calendar_expected_rate":weighted_rate(years,cache,col),
                })

    summary_df=pd.DataFrame(summary)
    pos_df=pd.DataFrame(posrows)

    allp=pd.concat(list(cohorts.values()),ignore_index=True)
    no=allp[~allp["has_SG_or_PY"]].copy()
    no_raw=no.sort_values(["rating","elo_z_within_snapshot_sex"],ascending=[False,False])
    no_z=no.sort_values(["elo_z_within_snapshot_sex","rating"],ascending=[False,False])
    if no_raw.empty: raise RuntimeError("No no-SG/no-PY player found")
    top_raw=no_raw.iloc[0]; top_z=no_z.iloc[0]

    generated=[]
    p=out/"sgpy_threshold_by_cohort.csv"; summary_df.to_csv(p,index=False,encoding="utf-8-sig"); generated.append(p)
    p=out/"sgpy_position_rates.csv"; pos_df.to_csv(p,index=False,encoding="utf-8-sig"); generated.append(p)
    p=out/"sgpy_calendar_null.json"
    p.write_text(json.dumps({
        "analysis_role":"post_reveal_exploratory_diagnostic",
        "seed":a.seed,"null_sims":a.null_sims,"metrics":nulls
    },ensure_ascii=False,indent=2),encoding="utf-8")
    generated.append(p)

    cols=[c for c in [
        "cohort","fide_id","name","rating","elo_z_within_snapshot_sex",
        "exact_dob_frozen","year_pillar","month_pillar","day_pillar",
        "six_position_tengods","SG_count","PY_count"
    ] if c in no_raw.columns]
    p=out/"no_sgpy_top_players.csv"
    no_raw[cols].head(100).to_csv(p,index=False,encoding="utf-8-sig")
    generated.append(p)

    md=[
        "# Chess 伤官/偏印 Threshold Diagnostic v1","",
        "**Post-reveal exploratory diagnostic.**","",
        "No hour, no secondary hidden stems, no 三合/三会/六合 transformation.","",
        "## Observed vs same-birth-year base rate",""
    ]
    for _,r in summary_df.iterrows():
        key=r["cohort"]; x=nulls[key]["has_SG_or_PY"]
        md.append(
            f"- **{key}**: SG={r['has_SG_rate']:.1%}, PY={r['has_PY_rate']:.1%}, "
            f"SG-or-PY={r['has_SG_or_PY_rate']:.1%}; "
            f"calendar base={x['weighted_exact_expected_rate']:.1%}, "
            f"z={x['z']:.3f}, p_high={x['empirical_p_high']:.4f}"
        )
    md += ["","## Highest-rated with neither 伤官 nor 偏印","",
        f"- Raw Elo: **{top_raw['name']}**, {top_raw['cohort']}, Elo {int(top_raw['rating'])}, "
        f"z={float(top_raw['elo_z_within_snapshot_sex']):.3f}, "
        f"{top_raw.get('year_pillar','')} {top_raw.get('month_pillar','')} {top_raw.get('day_pillar','')}",
        f"- Highest cohort-z: **{top_z['name']}**, {top_z['cohort']}, Elo {int(top_z['rating'])}, "
        f"z={float(top_z['elo_z_within_snapshot_sex']):.3f}, "
        f"{top_z.get('year_pillar','')} {top_z.get('month_pillar','')} {top_z.get('day_pillar','')}",
        ""
    ]
    p=out/"SG_PY_THRESHOLD_DIAGNOSTIC.md"; p.write_text("\n".join(md),encoding="utf-8"); generated.append(p)

    cp=out/"analyze_chess_sgpy_threshold_v1.py"
    shutil.copy2(Path(__file__).resolve(),cp); generated.append(cp)

    print("\n=== SG/PY THRESHOLD DIAGNOSTIC ===")
    for _,r in summary_df.iterrows():
        key=r["cohort"]; x=nulls[key]["has_SG_or_PY"]
        print(
            f"{key}: n={int(r['n'])} | "
            f"has_SG={r['has_SG_rate']:.2%} | "
            f"has_PY={r['has_PY_rate']:.2%} | "
            f"SG_or_PY={r['has_SG_or_PY_rate']:.2%} "
            f"(null={x['weighted_exact_expected_rate']:.2%}, "
            f"z={x['z']:.3f}, p_high={x['empirical_p_high']:.4f}) | "
            f"both={r['has_both_rate']:.2%}"
        )

    print("\n=== HIGHEST RATED WITH NO SG AND NO PY ===")
    print(
        f"RAW ELO: {top_raw['name']} | cohort={top_raw['cohort']} | "
        f"Elo={int(top_raw['rating'])} | z={float(top_raw['elo_z_within_snapshot_sex']):.3f} | "
        f"{top_raw.get('year_pillar','')} {top_raw.get('month_pillar','')} {top_raw.get('day_pillar','')} | "
        f"{top_raw.get('six_position_tengods','')}"
    )
    print(
        f"TOP Z:   {top_z['name']} | cohort={top_z['cohort']} | "
        f"Elo={int(top_z['rating'])} | z={float(top_z['elo_z_within_snapshot_sex']):.3f} | "
        f"{top_z.get('year_pillar','')} {top_z.get('month_pillar','')} {top_z.get('day_pillar','')} | "
        f"{top_z.get('six_position_tengods','')}"
    )

    print("\nTop 10 raw Elo no-SG/no-PY:")
    print(no_raw[[c for c in ["cohort","name","rating","elo_z_within_snapshot_sex","year_pillar","month_pillar","day_pillar"] if c in no_raw.columns]].head(10).to_string(index=False))

    if a.no_git:
        print("\n--no-git: generated results; Git untouched.")
        return

    staged=run(["git","diff","--cached","--name-only"],repo).strip()
    if staged: raise RuntimeError("Git index already has staged files:\n"+staged)
    if run(["git","tag","--list",a.tag],repo).strip():
        raise RuntimeError(f"Tag already exists: {a.tag}")

    rels=[str(x.relative_to(repo)) for x in generated]
    run(["git","add","--",*rels],repo)
    run(["git","commit","-m","Add post-reveal chess SG/PY threshold diagnostic"],repo)
    run(["git","tag","-a",a.tag,"-m","Record post-reveal SG/PY threshold diagnostic"],repo)
    branch=run(["git","branch","--show-current"],repo).splitlines()[-1].strip()
    run(["git","push",a.remote,branch],repo)
    run(["git","push",a.remote,a.tag],repo)
    commit=run(["git","rev-parse","HEAD"],repo).splitlines()[-1]
    print("\n=== DONE ===")
    print("Commit:",commit)
    print("Tag:   ",a.tag)
    print("Output:",out)

if __name__=="__main__":
    main()
