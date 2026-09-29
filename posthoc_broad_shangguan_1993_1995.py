#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
POST-HOC DESCRIPTIVE ONLY:
1993–1995 broad month-order 伤官 (all Day Masters, including Fire).

M0: broad 伤官 + year + Gregorian month + weekday
    -> directly comparable to the original 1990–1992 broad-伤官 model.
M2: M0 + Day Stem + Month Branch
    -> stricter relational-control version.

Scopes: north / known / full.
Also reports per-year north descriptives.
"""

import math
from pathlib import Path
import numpy as np
import pandas as pd
import statsmodels.api as sm
from lunar_python import Solar

YEARS=[1993,1994,1995]

BRANCH_MAIN_STEM={
"子":"癸","丑":"己","寅":"甲","卯":"乙","辰":"戊","巳":"丙",
"午":"丁","未":"己","申":"庚","酉":"辛","戌":"戊","亥":"壬",
}
STEM_ELEMENT={"甲":"木","乙":"木","丙":"火","丁":"火","戊":"土","己":"土","庚":"金","辛":"金","壬":"水","癸":"水"}
STEM_POLARITY={"甲":"阳","乙":"阴","丙":"阳","丁":"阴","戊":"阳","己":"阴","庚":"阳","辛":"阴","壬":"阳","癸":"阴"}
GENERATES={"木":"火","火":"土","土":"金","金":"水","水":"木"}
CONTROLS={"木":"土","土":"水","水":"火","火":"金","金":"木"}

def ten_god(day,target):
    de,te=STEM_ELEMENT[day],STEM_ELEMENT[target]
    same=STEM_POLARITY[day]==STEM_POLARITY[target]
    if de==te: return "比肩" if same else "劫财"
    if GENERATES[de]==te: return "食神" if same else "伤官"
    if CONTROLS[de]==te: return "偏财" if same else "正财"
    if CONTROLS[te]==de: return "七杀" if same else "正官"
    if GENERATES[te]==de: return "偏印" if same else "正印"
    raise ValueError((day,target))

def ec_at(y,m,d,h=12,minute=0):
    ec=Solar.fromYmdHms(int(y),int(m),int(d),int(h),int(minute),0).getLunar().getEightChar()
    return ec.getYear(),ec.getMonth(),ec.getDay()

def transition_ambiguous(ts):
    y1,m1,_=ec_at(ts.year,ts.month,ts.day,0,30)
    y2,m2,_=ec_at(ts.year,ts.month,ts.day,22,30)
    return y1!=y2 or m1!=m2

def date_features(ts):
    _,mp,dp=ec_at(ts.year,ts.month,ts.day,12,0)
    ds,mb=dp[0],mp[1]
    tg=ten_god(ds,BRANCH_MAIN_STEM[mb])
    return ds,mb,int(tg=="伤官")

def music_flag(df):
    if "_music" in df.columns:
        return pd.to_numeric(df["_music"],errors="raise").astype(int)
    if "broad_categories" in df.columns:
        return df["broad_categories"].fillna("").astype(str).apply(
            lambda s:int("Music" in [x.strip() for x in s.split(";") if x.strip()])
        )
    raise ValueError("Need _music or broad_categories")

def load_data(root):
    frames=[]; cache={}
    for y in YEARS:
        p=root/f"hemisphere_{y}"/f"{y}_people_with_hemisphere.csv"
        if not p.exists(): raise FileNotFoundError(p)
        d=pd.read_csv(p,encoding="utf-8-sig")
        d["dob"]=pd.to_datetime(d["_birth_date_norm"],errors="coerce")
        d=d.loc[d["dob"].notna() & d["dob"].dt.year.eq(y)].copy()
        d["_music_eval"]=music_flag(d)
        d["gregorian_year"]=d["dob"].dt.year.astype(int)
        d["gregorian_month"]=d["dob"].dt.month.astype(int)
        d["weekday"]=d["dob"].dt.day_name()
        keep=[]; feats=[]
        for ts in d["dob"]:
            k=ts.date().isoformat()
            if k not in cache:
                cache[k]=None if transition_ambiguous(ts) else date_features(ts)
            f=cache[k]; keep.append(f is not None); feats.append(f)
        d=d.loc[keep].copy(); feats=[f for f,k in zip(feats,keep) if k]
        d["day_stem"]=[f[0] for f in feats]
        d["month_branch"]=[f[1] for f in feats]
        d["broad_shangguan"]=[f[2] for f in feats]
        frames.append(d)
    return pd.concat(frames,ignore_index=True)

def scope_filter(d,scope):
    if scope=="north": return d.loc[d["hemisphere"].eq("north")].copy()
    if scope=="known": return d.loc[d["hemisphere"].isin(["north","south","equator"])].copy()
    if scope=="full": return d.copy()
    raise ValueError(scope)

def make_daily(d):
    return d.groupby(
        ["dob","gregorian_year","gregorian_month","weekday","day_stem","month_branch","broad_shangguan"],
        as_index=False
    ).agg(n_people=("_music_eval","size"),music_n=("_music_eval","sum"))

def design(d,model):
    X=pd.DataFrame({"broad_shangguan":d["broad_shangguan"].astype(float)},index=d.index)
    cats=["gregorian_year","gregorian_month","weekday"]
    if model=="M2": cats+=["day_stem","month_branch"]
    for c in cats:
        X=pd.concat([X,pd.get_dummies(d[c].astype("category"),prefix=c,drop_first=True,dtype=float)],axis=1)
    return sm.add_constant(X,has_constant="add").astype(float)

def p1pos(z): return 0.5*math.erfc(z/math.sqrt(2))

def fit(daily,model):
    y=np.column_stack([daily["music_n"].to_numpy(float),(daily["n_people"]-daily["music_n"]).to_numpy(float)])
    r=sm.GLM(y,design(daily,model),family=sm.families.Binomial()).fit(cov_type="HC0",maxiter=200)
    b=float(r.params["broad_shangguan"]); se=float(r.bse["broad_shangguan"]); z=b/se
    return {
        "model":model,"or":math.exp(b),
        "ci95_low":math.exp(b-1.96*se),"ci95_high":math.exp(b+1.96*se),
        "p_one_sided_positive":p1pos(z),"p_two_sided":float(r.pvalues["broad_shangguan"]),
        "n_people":int(daily["n_people"].sum()),"n_music":int(daily["music_n"].sum()),"n_dates":len(daily)
    }

def main():
    root=Path(".").resolve()
    outdir=root/"posthoc_broad_shangguan_1993_1995"; outdir.mkdir(exist_ok=True)
    d=load_data(root)
    rows=[]
    for scope in ["north","known","full"]:
        daily=make_daily(scope_filter(d,scope))
        for model in ["M0","M2"]:
            rows.append({"block":"pooled_1993_1995","scope":scope,**fit(daily,model)})
    for y in YEARS:
        daily=make_daily(scope_filter(d.loc[d["gregorian_year"].eq(y)].copy(),"north"))
        for model in ["M0","M2"]:
            rows.append({"block":str(y),"scope":"north",**fit(daily,model)})
    res=pd.DataFrame(rows)
    res.to_csv(outdir/"broad_month_order_shangguan_results.csv",index=False,encoding="utf-8-sig")
    lines=[
        "POST-HOC DESCRIPTIVE: BROAD MONTH-ORDER 伤官, 1993–1995",
        "NOT a frozen 1993–1995 hypothesis.",
        "M0 = feature + year + Gregorian month + weekday",
        "M2 = M0 + Day Stem + Month Branch",
        ""
    ]
    for _,r in res.iterrows():
        lines.append(
            f"{r['block']} | {r['scope']} | {r['model']}: "
            f"OR={r['or']:.6f}, 95CI=[{r['ci95_low']:.6f},{r['ci95_high']:.6f}], "
            f"p1+={r['p_one_sided_positive']:.6g}, p2={r['p_two_sided']:.6g}, "
            f"N={int(r['n_people'])}, Music={int(r['n_music'])}"
        )
    out=outdir/"BROAD_SHANGGUAN_1993_1995_SUMMARY.txt"
    out.write_text("\n".join(lines),encoding="utf-8")
    print("\n".join(lines))
    print("\nSaved:",out)

if __name__=="__main__":
    main()
