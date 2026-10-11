#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
TT stage-2 targeted historical holdout validation V2
=====================================================

RUN THIS BEFORE the all-Ten-God holdout characterization.

Purpose
-------
Validate only the three already-frozen TT targets in the 1950-1984
independent-player historical holdout:

H1 食神 enrichment
H2 七杀 enrichment
H3 劫财 enrichment
   - H3 was selected from the 1985-2008 training cohort by the frozen
     largest-positive calendar-adjusted Z rule.

No other Ten God is reported or eligible for promotion in this script.

Representations
---------------
Day Stem is reference-only.

M0_5pos_mainqi
M1_5pos_hidden
M2_8char_mainqi
M3_8char_hidden

M1 hidden-stem exposure:
  visible stems = Year + Month
M3:
  visible stems = Year + Month + Hour

Day Stem never counts as 透干.
Hidden-stem priority: main > middle > residual.
No exposed hidden stem -> fallback main qi.

M2/M3:
  unknown hour exactly marginalized uniformly across 12 double-hours.
  Full chart has 8 characters but only 7 Ten-God targets because Day Stem
  is reference-only.

Primary inference
-----------------
M0 is primary.
H1/H2/H3 directional enrichment p-values are Holm-adjusted across 3.

M1/M2/M3 are method sensitivities and do not replace M0.

Input
-----
Default:
  tt_holdout_1950_1984_PRIMARY.csv
Expected N=335, birth years 1950-1984.

Null
----
Same-birth-year uniform Gregorian calendar date.

Dependencies
------------
pip install numpy pandas lunar-python
"""

from __future__ import annotations
import argparse, json
from datetime import date, timedelta
from pathlib import Path
import numpy as np
import pandas as pd
from lunar_python import Solar

TGS=["比肩","劫财","食神","伤官","偏财","正财","七杀","正官","偏印","正印"]
TGI={x:i for i,x in enumerate(TGS)}
STEMS=list("甲乙丙丁戊己庚辛壬癸")
BRANCHES=list("子丑寅卯辰巳午未申酉戌亥")
INFO={
 "甲":("木",1),"乙":("木",0),"丙":("火",1),"丁":("火",0),"戊":("土",1),
 "己":("土",0),"庚":("金",1),"辛":("金",0),"壬":("水",1),"癸":("水",0)}
GEN={"木":"火","火":"土","土":"金","金":"水","水":"木"}
CTL={"木":"土","土":"水","水":"火","火":"金","金":"木"}
H={
 "子":["癸"],"丑":["己","癸","辛"],"寅":["甲","丙","戊"],"卯":["乙"],
 "辰":["戊","乙","癸"],"巳":["丙","戊","庚"],"午":["丁","己"],"未":["己","丁","乙"],
 "申":["庚","壬","戊"],"酉":["辛"],"戌":["戊","辛","丁"],"亥":["壬","甲"]}
MODELS=["M0_5pos_mainqi","M1_5pos_hidden","M2_8char_mainqi","M3_8char_hidden"]
TARGETS={"M0_5pos_mainqi":5.0,"M1_5pos_hidden":5.0,
         "M2_8char_mainqi":7.0,"M3_8char_hidden":7.0}
FOCUS=["食神","七杀","劫财"]

def tg(dm,t):
    de,dp=INFO[dm]; te,tp=INFO[t]; same=dp==tp
    if de==te: return "比肩" if same else "劫财"
    if GEN[de]==te: return "食神" if same else "伤官"
    if CTL[de]==te: return "偏财" if same else "正财"
    if CTL[te]==de: return "七杀" if same else "正官"
    if GEN[te]==de: return "偏印" if same else "正印"
    raise RuntimeError((dm,t))

def one(dm,t):
    v=np.zeros(10,float); v[TGI[tg(dm,t)]]=1; return v

def hour_stem(dm,hb):
    return STEMS[(2*(STEMS.index(dm)%5)+hb)%10]

def branch(dm,b,visible,hidden):
    hs=H[b]
    if not hidden: return one(dm,hs[0])
    ex=[s for s in hs if s in visible]
    return one(dm,ex[0] if ex else hs[0])

def feat(y,m,d):
    ec=Solar.fromYmdHms(int(y),int(m),int(d),12,0,0).getLunar().getEightChar()
    ys,yb=ec.getYearGan(),ec.getYearZhi()
    ms,mb=ec.getMonthGan(),ec.getMonthZhi()
    dm,db=ec.getDayGan(),ec.getDayZhi()

    stems=one(dm,ys)+one(dm,ms)
    vis={ys,ms}
    m0=stems.copy(); m1=stems.copy()
    for b in (yb,mb,db):
        m0+=branch(dm,b,vis,False)
        m1+=branch(dm,b,vis,True)

    m2=np.zeros(10,float); m3=np.zeros(10,float)
    for hb,bh in enumerate(BRANCHES):
        hs=hour_stem(dm,hb); vis8={ys,ms,hs}
        a=stems+one(dm,hs); bvec=stems+one(dm,hs)
        for b in (yb,mb,db,bh):
            a+=branch(dm,b,vis8,False)
            bvec+=branch(dm,b,vis8,True)
        m2+=a/12
        m3+=bvec/12

    out={"M0_5pos_mainqi":m0,"M1_5pos_hidden":m1,
         "M2_8char_mainqi":m2,"M3_8char_hidden":m3}
    for k,v in out.items():
        if not np.isclose(v.sum(),TARGETS[k],atol=1e-10):
            raise RuntimeError(f"feature QA failed {y}-{m}-{d} {k}: {v.sum()}")
    return out

def dates(y):
    d=date(int(y),1,1); e=date(int(y),12,31)
    while d<=e:
        yield d; d+=timedelta(days=1)

def holm(p):
    p=np.asarray(p,float); order=np.argsort(p); out=np.empty(len(p)); run=0
    for rank,i in enumerate(order):
        run=max(run,min(1,(len(p)-rank)*p[i])); out[i]=run
    return out

def load(path):
    d=pd.read_csv(path,encoding="utf-8-sig",dtype={"qid":str})
    if "dob" not in d.columns: raise RuntimeError(f"{path}: missing dob")
    dob=pd.to_datetime(d["dob"],errors="raise")
    d=d.copy(); d["_dob"]=dob; d["_year"]=dob.dt.year.astype(int)
    if len(d)!=335: raise RuntimeError(f"Expected historical holdout N=335, got {len(d)}")
    if d["_year"].min()<1950 or d["_year"].max()>1984:
        raise RuntimeError(f"Expected years 1950-1984, got {d['_year'].min()}-{d['_year'].max()}")
    return d

def calendar(years):
    out={}; ys=sorted(set(map(int,years)))
    for j,y in enumerate(ys,1):
        rows=[]
        for dt in dates(y):
            f=feat(dt.year,dt.month,dt.day)
            rows.append(np.stack([f[m] for m in MODELS]))
        out[y]=np.stack(rows)
        print(f"calendar [{j}/{len(ys)}] {y}: {len(rows)} days")
    return out

def observed(d):
    obs=np.zeros((4,10),float); cache={}; audit=[]
    for _,r in d.iterrows():
        ts=r["_dob"]; key=ts.date().isoformat()
        if key not in cache: cache[key]=feat(ts.year,ts.month,ts.day)
        f=cache[key]; rr={"dob":key,"birth_year":int(ts.year)}
        for c in ("qid","name","gender","ittf_id"):
            if c in d.columns: rr[c]=r[c]
        for mi,m in enumerate(MODELS):
            obs[mi]+=f[m]
            for x in FOCUS: rr[f"{m}__{x}"]=f[m][TGI[x]]
        audit.append(rr)
    return obs,pd.DataFrame(audit)

def exact_exp(d,cal):
    x=np.zeros((4,10),float)
    for y,n in d["_year"].value_counts().items():
        x+=int(n)*cal[int(y)].mean(axis=0)
    return x

def sim(d,cal,obs,B,batch,seed):
    rng=np.random.default_rng(seed); vc=d["_year"].value_counts().to_dict()
    sx=np.zeros_like(obs); sx2=np.zeros_like(obs)
    ge=np.zeros_like(obs,dtype=np.int64); le=np.zeros_like(obs,dtype=np.int64)
    done=0
    while done<B:
        b=min(batch,B-done); t=np.zeros((b,4,10),float)
        for y,n in vc.items():
            a=cal[int(y)]; ix=rng.integers(0,a.shape[0],size=(b,int(n)))
            t+=a[ix].sum(axis=1)
        sx+=t.sum(axis=0); sx2+=(t*t).sum(axis=0)
        ge+=(t>=obs[None,:,:]-1e-12).sum(axis=0)
        le+=(t<=obs[None,:,:]+1e-12).sum(axis=0)
        done+=b
    mean=sx/B; sd=np.sqrt(np.maximum(0,sx2/B-mean*mean))
    ph=(ge+1)/(B+1); pl=(le+1)/(B+1)
    return mean,sd,ph,pl

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--holdout",default="tt_holdout_1950_1984_PRIMARY.csv")
    ap.add_argument("--repo",default=".")
    ap.add_argument("--output-subdir",default="tt_tengod_stage2_targeted_v2")
    ap.add_argument("--sims",type=int,default=200000)
    ap.add_argument("--batch-size",type=int,default=1000)
    ap.add_argument("--seed",type=int,default=20261007)
    a=ap.parse_args()
    root=Path(a.repo).resolve(); hp=Path(a.holdout)
    if not hp.is_absolute(): hp=(root/hp).resolve()
    out=root/a.output_subdir; out.mkdir(parents=True,exist_ok=True)

    d=load(hp); cal=calendar(d["_year"].tolist())
    obs,audit=observed(d); exp=exact_exp(d,cal)
    mean,sd,ph,pl=sim(d,cal,obs,a.sims,a.batch_size,a.seed)

    origins={"食神":"H1 data-informed/traditional-compatible",
             "七杀":"H2 theory-driven",
             "劫财":"H3 training-derived candidate"}
    rows=[]
    for mi,m in enumerate(MODELS):
        raw=[ph[mi,TGI[x]] for x in FOCUS]; adj=holm(raw)
        for j,x in enumerate(FOCUS):
            ti=TGI[x]; z=(obs[mi,ti]-mean[mi,ti])/sd[mi,ti] if sd[mi,ti]>0 else np.nan
            rows.append(dict(
                hypothesis=origins[x].split()[0],ten_god=x,origin=origins[x],
                model=m,n=len(d),observed_total=obs[mi,ti],
                observed_mean=obs[mi,ti]/len(d),null_total_exact=exp[mi,ti],
                null_mean=exp[mi,ti]/len(d),delta_mean=(obs[mi,ti]-exp[mi,ti])/len(d),
                enrichment_ratio=obs[mi,ti]/exp[mi,ti],z_enrichment=z,
                p_high=ph[mi,ti],p_low=pl[mi,ti],
                p_two_sided=min(1,2*min(ph[mi,ti],pl[mi,ti])),
                holm3_directional=adj[j],
                inference_role=("PRIMARY" if m=="M0_5pos_mainqi" else "SENSITIVITY")
            ))
    res=pd.DataFrame(rows)
    res.to_csv(out/"tt_stage2_targeted_results.csv",index=False,encoding="utf-8-sig")
    audit.to_csv(out/"tt_stage2_targeted_player_features.csv",index=False,encoding="utf-8-sig")

    lines=["TT STAGE-2 TARGETED HISTORICAL HOLDOUT V2","="*78,
           f"N={len(d)}; input={hp}","M0 primary; M1/M2/M3 sensitivity.",""]
    for m in MODELS:
        lines.append(m)
        g=res[res.model.eq(m)]
        for _,r in g.iterrows():
            lines.append(f"  {r.ten_god} ({r.hypothesis}): obs={r.observed_mean:.6f} null={r.null_mean:.6f} delta={r.delta_mean:+.6f} ratio={r.enrichment_ratio:.4f} z={r.z_enrichment:+.4f} p+={r.p_high:.6g} Holm3={r.holm3_directional:.6g}")
        lines.append("")
    lines+=["INTERPRETATION RULES",
            "1) M0 is the frozen primary holdout test.",
            "2) H3 劫财 must be positive in the holdout to count as directional replication.",
            "3) M1/M2/M3 assess coding robustness only.",
            "4) Do not inspect/promote any other Ten God until this targeted result is frozen.",
            "5) After saving/committing this result, run the separate all-Ten-God characterization script."]
    summary="\n".join(lines)
    (out/"tt_stage2_targeted_summary.txt").write_text(summary,encoding="utf-8")
    (out/"tt_stage2_targeted_metadata.json").write_text(json.dumps({
        "role":"feature-specific historical holdout validation",
        "targets":["食神","七杀","劫财"],"primary":"M0_5pos_mainqi",
        "sensitivities":["M1_5pos_hidden","M2_8char_mainqi","M3_8char_hidden"],
        "day_stem":"reference_only","null":"same-birth-year Gregorian calendar",
        "sims":a.sims,"seed":a.seed},ensure_ascii=False,indent=2),encoding="utf-8")
    print("\n"+summary+"\nSaved:",out)

if __name__=="__main__":
    main()
