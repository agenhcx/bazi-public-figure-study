#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
TT all-Ten-God post-validation characterization V1
===================================================

RUN ONLY AFTER tt_tengod_stage2_targeted_v2/tt_stage2_targeted_summary.txt exists
and the targeted holdout result has been saved/frozen.

This script then characterizes ALL 10 Ten Gods in:
  TRAINING 1985-2008, canonical N=384
  HISTORICAL_HOLDOUT 1950-1984, canonical N=335

This is descriptive context after hypothesis testing, not a new hypothesis
selection step.

Models:
  M0_5pos_mainqi
  M1_5pos_hidden
  M2_8char_mainqi
  M3_8char_hidden

Day Stem = reference only.
Hidden rule = priority exposed main > middle > residual, fallback main qi.
Hour = exact uniform marginalization over 12 double-hours.
Null = same-birth-year Gregorian calendar.

Dependencies:
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
STEMS=list("甲乙丙丁戊己庚辛壬癸"); BRANCHES=list("子丑寅卯辰巳午未申酉戌亥")
INFO={"甲":("木",1),"乙":("木",0),"丙":("火",1),"丁":("火",0),"戊":("土",1),"己":("土",0),"庚":("金",1),"辛":("金",0),"壬":("水",1),"癸":("水",0)}
GEN={"木":"火","火":"土","土":"金","金":"水","水":"木"}; CTL={"木":"土","土":"水","水":"火","火":"金","金":"木"}
H={"子":["癸"],"丑":["己","癸","辛"],"寅":["甲","丙","戊"],"卯":["乙"],"辰":["戊","乙","癸"],"巳":["丙","戊","庚"],"午":["丁","己"],"未":["己","丁","乙"],"申":["庚","壬","戊"],"酉":["辛"],"戌":["戊","辛","丁"],"亥":["壬","甲"]}
MODELS=["M0_5pos_mainqi","M1_5pos_hidden","M2_8char_mainqi","M3_8char_hidden"]
TARGETS={"M0_5pos_mainqi":5.0,"M1_5pos_hidden":5.0,"M2_8char_mainqi":7.0,"M3_8char_hidden":7.0}

def tg(dm,t):
    de,dp=INFO[dm]; te,tp=INFO[t]; same=dp==tp
    if de==te:return "比肩" if same else "劫财"
    if GEN[de]==te:return "食神" if same else "伤官"
    if CTL[de]==te:return "偏财" if same else "正财"
    if CTL[te]==de:return "七杀" if same else "正官"
    if GEN[te]==de:return "偏印" if same else "正印"
    raise RuntimeError

def one(dm,t):
    v=np.zeros(10);v[TGI[tg(dm,t)]]=1;return v

def hour_stem(dm,hb):return STEMS[(2*(STEMS.index(dm)%5)+hb)%10]

def branch(dm,b,vis,hidden):
    hs=H[b]
    if not hidden:return one(dm,hs[0])
    ex=[s for s in hs if s in vis]
    return one(dm,ex[0] if ex else hs[0])

def feat(y,m,d):
    ec=Solar.fromYmdHms(int(y),int(m),int(d),12,0,0).getLunar().getEightChar()
    ys,yb=ec.getYearGan(),ec.getYearZhi();ms,mb=ec.getMonthGan(),ec.getMonthZhi();dm,db=ec.getDayGan(),ec.getDayZhi()
    stems=one(dm,ys)+one(dm,ms);vis={ys,ms}
    m0=stems.copy();m1=stems.copy()
    for b in (yb,mb,db):m0+=branch(dm,b,vis,False);m1+=branch(dm,b,vis,True)
    m2=np.zeros(10);m3=np.zeros(10)
    for hb,bh in enumerate(BRANCHES):
        hs=hour_stem(dm,hb);vis8={ys,ms,hs};a=stems+one(dm,hs);bvec=stems+one(dm,hs)
        for b in (yb,mb,db,bh):a+=branch(dm,b,vis8,False);bvec+=branch(dm,b,vis8,True)
        m2+=a/12;m3+=bvec/12
    out={"M0_5pos_mainqi":m0,"M1_5pos_hidden":m1,"M2_8char_mainqi":m2,"M3_8char_hidden":m3}
    for k,v in out.items():
        if not np.isclose(v.sum(),TARGETS[k]):raise RuntimeError(f"QA {y}-{m}-{d} {k}")
    return out

def dates(y):
    d=date(int(y),1,1);e=date(int(y),12,31)
    while d<=e:yield d;d+=timedelta(days=1)

def holm(p):
    p=np.asarray(p,float);o=np.argsort(p);out=np.empty(len(p));run=0
    for rank,i in enumerate(o):run=max(run,min(1,(len(p)-rank)*p[i]));out[i]=run
    return out

def load(path,label,n,ymin,ymax,dobcol):
    d=pd.read_csv(path,encoding="utf-8-sig",dtype={"qid":str})
    if dobcol not in d.columns:raise RuntimeError(f"{path}: missing {dobcol}")
    dob=pd.to_datetime(d[dobcol],errors="raise");d=d.copy();d["_dob"]=dob;d["_year"]=dob.dt.year.astype(int);d["_cohort"]=label
    if len(d)!=n:raise RuntimeError(f"{label}: expected N={n}, got {len(d)}")
    if d["_year"].min()<ymin or d["_year"].max()>ymax:raise RuntimeError(f"{label}: unexpected years")
    return d

def calendar(years):
    out={};ys=sorted(set(map(int,years)))
    for j,y in enumerate(ys,1):
        rr=[]
        for dt in dates(y):
            f=feat(dt.year,dt.month,dt.day);rr.append(np.stack([f[m] for m in MODELS]))
        out[y]=np.stack(rr);print(f"calendar [{j}/{len(ys)}] {y}: {len(rr)} days")
    return out

def observed(d):
    obs=np.zeros((4,10));cache={};audit=[]
    for _,r in d.iterrows():
        ts=r["_dob"];key=ts.date().isoformat()
        if key not in cache:cache[key]=feat(ts.year,ts.month,ts.day)
        f=cache[key];rr={"cohort":r["_cohort"],"dob":key,"birth_year":int(ts.year)}
        for c in ("qid","name","gender","ittf_id"):
            if c in d.columns:rr[c]=r[c]
        for mi,m in enumerate(MODELS):
            obs[mi]+=f[m]
            for ti,x in enumerate(TGS):rr[f"{m}__{x}"]=f[m][ti]
        audit.append(rr)
    return obs,pd.DataFrame(audit)

def exact_exp(d,cal):
    x=np.zeros((4,10))
    for y,n in d["_year"].value_counts().items():x+=int(n)*cal[int(y)].mean(axis=0)
    return x

def sim(d,cal,obs,B,batch,seed):
    rng=np.random.default_rng(seed);vc=d["_year"].value_counts().to_dict();sx=np.zeros_like(obs);sx2=np.zeros_like(obs);ge=np.zeros_like(obs,dtype=np.int64);le=np.zeros_like(obs,dtype=np.int64);done=0
    while done<B:
        b=min(batch,B-done);t=np.zeros((b,4,10))
        for y,n in vc.items():
            a=cal[int(y)];ix=rng.integers(0,a.shape[0],size=(b,int(n)));t+=a[ix].sum(axis=1)
        sx+=t.sum(axis=0);sx2+=(t*t).sum(axis=0);ge+=(t>=obs[None,:,:]-1e-12).sum(axis=0);le+=(t<=obs[None,:,:]+1e-12).sum(axis=0);done+=b
    mean=sx/B;sd=np.sqrt(np.maximum(0,sx2/B-mean*mean));ph=(ge+1)/(B+1);pl=(le+1)/(B+1)
    return mean,sd,ph,pl

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--repo",default=".")
    ap.add_argument("--training",default="table_tennis_players_1985_2008.csv")
    ap.add_argument("--holdout",default="tt_holdout_1950_1984_PRIMARY.csv")
    ap.add_argument("--validation-summary",default="tt_tengod_stage2_targeted_v2/tt_stage2_targeted_summary.txt")
    ap.add_argument("--output-subdir",default="tt_all_tengod_distribution_v1")
    ap.add_argument("--sims",type=int,default=200000);ap.add_argument("--batch-size",type=int,default=1000);ap.add_argument("--seed",type=int,default=20261007)
    a=ap.parse_args();root=Path(a.repo).resolve()
    def rp(s):p=Path(s);return p if p.is_absolute() else (root/p).resolve()
    vs=rp(a.validation_summary)
    if not vs.exists():raise RuntimeError(f"REFUSING TO RUN: targeted holdout summary not found: {vs}")
    out=root/a.output_subdir;out.mkdir(parents=True,exist_ok=True)
    cohorts={
      "TRAINING_1985_2008":load(rp(a.training),"TRAINING_1985_2008",384,1985,2008,"dob"),
      "HISTORICAL_HOLDOUT_1950_1984":load(rp(a.holdout),"HISTORICAL_HOLDOUT_1950_1984",335,1950,1984,"dob")}
    years=[]
    for d in cohorts.values():years.extend(d["_year"].tolist())
    cal=calendar(years);rows=[];audits=[]
    for ci,(label,d) in enumerate(cohorts.items()):
        obs,audit=observed(d);audits.append(audit);exp=exact_exp(d,cal);mean,sd,ph,pl=sim(d,cal,obs,a.sims,a.batch_size,a.seed+ci)
        for mi,m in enumerate(MODELS):
            p2=np.minimum(1,2*np.minimum(ph[mi],pl[mi]));h=holm(p2)
            for ti,x in enumerate(TGS):
                z=(obs[mi,ti]-mean[mi,ti])/sd[mi,ti] if sd[mi,ti]>0 else np.nan
                rows.append(dict(cohort=label,n=len(d),model=m,ten_god=x,targets_per_player=TARGETS[m],
                    observed_total=obs[mi,ti],observed_mean=obs[mi,ti]/len(d),observed_share=obs[mi,ti]/(len(d)*TARGETS[m]),
                    null_total_exact=exp[mi,ti],null_mean=exp[mi,ti]/len(d),null_share=exp[mi,ti]/(len(d)*TARGETS[m]),
                    delta_mean=(obs[mi,ti]-exp[mi,ti])/len(d),enrichment_ratio=obs[mi,ti]/exp[mi,ti],
                    z_enrichment=z,p_high=ph[mi,ti],p_low=pl[mi,ti],p_two_sided=p2[ti],holm10_two_sided=h[ti]))
    res=pd.DataFrame(rows);res["rank_z"]=res.groupby(["cohort","model"])["z_enrichment"].rank(method="min",ascending=False).astype(int)
    res.to_csv(out/"tt_all_tengod_distribution_long.csv",index=False,encoding="utf-8-sig")
    res.sort_values(["cohort","model","rank_z"]).to_csv(out/"tt_all_tengod_distribution_ranked.csv",index=False,encoding="utf-8-sig")
    pd.concat(audits,ignore_index=True).to_csv(out/"tt_all_tengod_player_features.csv",index=False,encoding="utf-8-sig")

    # cross-cohort comparison
    comp=[]
    for m in MODELS:
        for x in TGS:
            arow=res[(res.cohort=="TRAINING_1985_2008")&(res.model==m)&(res.ten_god==x)].iloc[0]
            brow=res[(res.cohort=="HISTORICAL_HOLDOUT_1950_1984")&(res.model==m)&(res.ten_god==x)].iloc[0]
            comp.append(dict(model=m,ten_god=x,training_z=arow.z_enrichment,holdout_z=brow.z_enrichment,
                             training_ratio=arow.enrichment_ratio,holdout_ratio=brow.enrichment_ratio,
                             same_direction=((arow.delta_mean>=0)==(brow.delta_mean>=0))))
    pd.DataFrame(comp).to_csv(out/"tt_cross_cohort_tengod_consistency.csv",index=False,encoding="utf-8-sig")

    lines=["TT ALL-TEN-GOD DISTRIBUTION V1","="*78,"Post-validation descriptive characterization; no new hypothesis mining.",""]
    for c in cohorts:
        lines.append(c)
        for m in MODELS:
            lines.append(f"  {m}")
            g=res[(res.cohort==c)&(res.model==m)].sort_values("rank_z")
            for _,r in g.iterrows():
                lines.append(f"    #{int(r.rank_z)} {r.ten_god}: obs={r.observed_mean:.6f} null={r.null_mean:.6f} share={100*r.observed_share:.3f}% ratio={r.enrichment_ratio:.4f} z={r.z_enrichment:+.4f} p2={r.p_two_sided:.6g}")
            lines.append("")
    lines+=["GUARDRAIL","These rankings are descriptive after targeted validation.",
            "Do not promote a new TT hypothesis from the all-Ten-God holdout table."]
    summary="\n".join(lines);(out/"tt_all_tengod_distribution_summary.txt").write_text(summary,encoding="utf-8")
    print("\n"+summary+"\nSaved:",out)

if __name__=="__main__":
    main()
