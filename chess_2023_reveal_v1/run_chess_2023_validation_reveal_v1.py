#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations
import argparse, calendar, json, shutil, subprocess
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import f_oneway, kruskal, spearmanr
import sxtwl

PLAN_TAG="chess-2023-validation-plan-v2"
COHORT_TAG="chess-2023-cohorts-frozen-v1"
RESULT_TAG="chess-2023-reveal-results-v1"

STEMS=list("甲乙丙丁戊己庚辛壬癸")
BRANCHES=list("子丑寅卯辰巳午未申酉戌亥")
ELEMENTS=["木","火","土","金","水"]
STEM_ELEMENT=["木","木","火","火","土","土","金","金","水","水"]
STEM_YANG=[1,0,1,0,1,0,1,0,1,0]
BRANCH_MAIN_STEM=[9,5,0,1,4,2,3,5,6,7,4,8]
PREDICTED=set("乙丙戊辛壬")

FILES={
 "M_FULL":"primary_2023_M_FULL.csv",
 "F_FULL":"primary_2023_F_FULL.csv",
 "M_NEW_WITHIN_FULL":"diagnostic_2023_M_NEW_WITHIN_FULL.csv",
 "F_NEW_WITHIN_FULL":"diagnostic_2023_F_NEW_WITHIN_FULL.csv",
 "M_NEW_TARGET":"validation_2023_M_NEW_TARGET.csv",
 "F_NEW_TARGET":"validation_2023_F_NEW_TARGET.csv",
}

def run(cmd,cwd,check=True):
    print("$"," ".join(cmd))
    p=subprocess.run(cmd,cwd=str(cwd),text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    if p.stdout: print(p.stdout.rstrip())
    if check and p.returncode!=0:
        raise RuntimeError("Command failed: "+" ".join(cmd))
    return p.stdout.strip()

def git_root(p): return Path(run(["git","rev-parse","--show-toplevel"],p)).resolve()

def tg(dm,t):
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

def feat(y,m,d):
    x=sxtwl.fromSolar(int(y),int(m),int(d))
    yg,mg,dg=x.getYearGZ(),x.getMonthGZ(),x.getDayGZ()
    targets=[yg.tg,BRANCH_MAIN_STEM[yg.dz],mg.tg,BRANCH_MAIN_STEM[mg.dz],dg.tg,BRANCH_MAIN_STEM[dg.dz]]
    gods=[tg(dg.tg,z) for z in targets]
    ds=STEMS[dg.tg]
    return {
      "year_pillar":STEMS[yg.tg]+BRANCHES[yg.dz],
      "month_pillar":STEMS[mg.tg]+BRANCHES[mg.dz],
      "day_pillar":STEMS[dg.tg]+BRANCHES[dg.dz],
      "day_stem":ds,
      "day_master_element":STEM_ELEMENT[dg.tg],
      "stem_direction_score":1 if ds in PREDICTED else -1,
      "six_position_tengods":"|".join(gods),
      "shangguan_count_6pos":sum(g=="伤官" for g in gods),
      "pianyin_count_6pos":sum(g=="偏印" for g in gods),
    }

def enrich(df,label):
    rows=[]
    for _,r in df.iterrows():
        dt=pd.Timestamp(str(r["exact_dob_frozen"])[:10])
        z=feat(dt.year,dt.month,dt.day); z["analysis_group"]=label; rows.append(z)
    out=pd.concat([df.reset_index(drop=True),pd.DataFrame(rows)],axis=1)
    if (pd.to_datetime(out["exact_dob_frozen"])>pd.Timestamp("2023-01-01")).any():
        raise RuntimeError("future DOB found")
    return out

def year_table(y):
    rows=[]
    for m in range(1,13):
        for d in range(1,calendar.monthrange(y,m)[1]+1):
            f=feat(y,m,d)
            rows.append({k:f[k] for k in ["day_stem","day_master_element","stem_direction_score","shangguan_count_6pos","pianyin_count_6pos"]})
    return pd.DataFrame(rows)

def mc_sum(years,cache,col,obs,n_sims,rng):
    sims=np.zeros(n_sims,float)
    for y,n in years.value_counts().sort_index().items():
        vals=cache[int(y)][col].to_numpy(float)
        idx=rng.integers(0,len(vals),size=(n_sims,int(n)))
        sims += vals[idx].sum(axis=1)
    mu=float(sims.mean()); sd=float(sims.std(ddof=1))
    return {
      "observed_sum":float(obs),
      "observed_mean_per_player":float(obs/len(years)),
      "null_mean_sum":mu,
      "null_mean_per_player":float(mu/len(years)),
      "null_sd_sum":sd,
      "z":float((obs-mu)/sd) if sd>0 else None,
      "empirical_p_high":float((1+(sims>=obs).sum())/(n_sims+1)),
      "empirical_p_low":float((1+(sims<=obs).sum())/(n_sims+1)),
      "n_sims":n_sims,
      "null":"uniform Gregorian date within same birth year",
    }

def pair_diag(df,years,cache):
    pairs=[("乙","甲"),("丙","丁"),("戊","己"),("辛","庚"),("壬","癸")]
    out=[]
    for pred,opp in pairs:
        a=int((df.day_stem==pred).sum()); b=int((df.day_stem==opp).sum())
        pp=[]; po=[]
        for y in years:
            t=cache[int(y)]
            pp.append((t.day_stem==pred).mean()); po.append((t.day_stem==opp).mean())
        ep=float(np.mean(pp)); eo=float(np.mean(po))
        out.append({
          "predicted_stem":pred,"opposite_stem":opp,
          "predicted_count":a,"opposite_count":b,
          "observed_predicted_share":a/(a+b) if a+b else None,
          "matched_calendar_predicted_share":ep/(ep+eo),
          "direction_matches":bool(a>b),
        })
    return out

def selection(df,cache,n_sims,rng):
    years=pd.to_datetime(df.exact_dob_frozen).dt.year.astype(int)
    h1=mc_sum(years,cache,"stem_direction_score",df.stem_direction_score.sum(),n_sims,rng)
    h1["individual_pairs"]=pair_diag(df,years,cache)
    sg=mc_sum(years,cache,"shangguan_count_6pos",df.shangguan_count_6pos.sum(),n_sims,rng)
    py=mc_sum(years,cache,"pianyin_count_6pos",df.pianyin_count_6pos.sum(),n_sims,rng)
    return {
      "n":len(df),
      "day_stem_counts":{s:int((df.day_stem==s).sum()) for s in STEMS},
      "element_counts":{e:int((df.day_master_element==e).sum()) for e in ELEMENTS},
      "H1_stem_direction":h1,
      "H2_shangguan":sg,
      "pianyin_descriptive_null":py,
    }

def perm_diff(df,gcol,A,B,n_perm,rng):
    sub=df[df[gcol].isin([A,B])].copy()
    y=sub.elo_z.to_numpy(float); ga=(sub[gcol].to_numpy()==A); sex=sub.analysis_sex.to_numpy()
    obs=float(y[ga].mean()-y[~ga].mean())
    sims=np.empty(n_perm,float)
    groups={s:np.where(sex==s)[0] for s in np.unique(sex)}
    for k in range(n_perm):
        yp=y.copy()
        for _,idx in groups.items(): yp[idx]=rng.permutation(y[idx])
        sims[k]=yp[ga].mean()-yp[~ga].mean()
    return {
      "group_A":A,"group_B":B,
      "n_A":int(ga.sum()),"n_B":int((~ga).sum()),
      "mean_z_A":float(y[ga].mean()),"mean_z_B":float(y[~ga].mean()),
      "diff_A_minus_B":obs,
      "p_one_A_gt_B":float((1+(sims>=obs).sum())/(n_perm+1)),
      "p_two":float((1+(np.abs(sims)>=abs(obs)).sum())/(n_perm+1)),
      "n_perm":n_perm,
    }

def omnibus(df,col,order):
    arr=[df.loc[df[col]==g,"elo_z"].to_numpy(float) for g in order]
    arr=[a for a in arr if len(a)>=2]
    a=f_oneway(*arr); k=kruskal(*arr)
    return {"anova_F":float(a.statistic),"anova_p":float(a.pvalue),
            "kruskal_H":float(k.statistic),"kruskal_p":float(k.pvalue)}

def perf(male,female,n_perm,rng):
    m=male.copy(); f=female.copy()
    m["analysis_sex"]="M"; f["analysis_sex"]="F"
    zc="elo_z_within_2023_sex_cohort"
    m["elo_z"]=m[zc].astype(float); f["elo_z"]=f[zc].astype(float)
    p=pd.concat([m,f],ignore_index=True)
    out={
      "H3a_metal_gt_earth":perm_diff(p,"day_master_element","金","土",n_perm,rng),
      "H3b_geng_gt_wu":perm_diff(p,"day_stem","庚","戊",n_perm,rng),
      "H3_secondary":{
        "geng_vs_xin":perm_diff(p,"day_stem","庚","辛",n_perm,rng),
        "wu_vs_ji":perm_diff(p,"day_stem","戊","己",n_perm,rng),
        "five_element_omnibus":omnibus(p,"day_master_element",ELEMENTS),
        "ten_stem_omnibus":omnibus(p,"day_stem",STEMS),
        "element_means":{e:{"n":int((p.day_master_element==e).sum()),
                            "mean_elo_z":float(p.loc[p.day_master_element==e,"elo_z"].mean())} for e in ELEMENTS},
        "stem_means":{s:{"n":int((p.day_stem==s).sum()),
                         "mean_elo_z":float(p.loc[p.day_stem==s,"elo_z"].mean())} for s in STEMS},
      }
    }
    h4={}
    for featn in ["shangguan_count_6pos","pianyin_count_6pos"]:
        h4[featn]={}
        for lab,d in [("M",m),("F",f),("pooled",p)]:
            rho,pv=spearmanr(d[featn].astype(float),d.elo_z.astype(float))
            h4[featn][lab]={"rho":float(rho),"p":float(pv),"n":len(d)}
    out["H4_tengod_performance"]=h4
    return out

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--repo",default=r"..\1986wiki")
    ap.add_argument("--source-subdir",default="chess_2023_cohorts_v1")
    ap.add_argument("--output-subdir",default="chess_2023_reveal_v1")
    ap.add_argument("--null-sims",type=int,default=20000)
    ap.add_argument("--perf-perm",type=int,default=50000)
    ap.add_argument("--seed",type=int,default=20260927)
    ap.add_argument("--remote",default="origin")
    ap.add_argument("--no-git",action="store_true")
    a=ap.parse_args()

    repo=git_root(Path(a.repo)); src=repo/a.source_subdir; out=repo/a.output_subdir
    out.mkdir(parents=True,exist_ok=True)

    for tag in [PLAN_TAG,COHORT_TAG]:
        if not run(["git","tag","--list",tag],repo).strip():
            raise RuntimeError(f"missing frozen tag: {tag}")

    raw={}; years=[]
    for key,fn in FILES.items():
        d=pd.read_csv(src/fn)
        need={"fide_id","name","rating","exact_dob_frozen","elo_z_within_2023_sex_cohort"}
        miss=need-set(d.columns)
        if miss: raise RuntimeError(f"{fn}: missing {sorted(miss)}")
        raw[key]=d
        years += pd.to_datetime(d.exact_dob_frozen).dt.year.astype(int).tolist()

    print("\n=== 2023 BAZI REVEAL START ===")
    data={}
    for k,d in raw.items():
        data[k]=enrich(d,k)
        print(f"{k}: n={len(d)}")

    cache={}
    for y in sorted(set(years)):
        cache[y]=year_table(y)

    rng=np.random.default_rng(a.seed)

    groups={
      "M_FULL":data["M_FULL"],"F_FULL":data["F_FULL"],
      "FULL_POOLED":pd.concat([data["M_FULL"],data["F_FULL"]],ignore_index=True),
      "M_NEW_TARGET":data["M_NEW_TARGET"],"F_NEW_TARGET":data["F_NEW_TARGET"],
      "NEW_TARGET_POOLED":pd.concat([data["M_NEW_TARGET"],data["F_NEW_TARGET"]],ignore_index=True),
      "M_NEW_WITHIN_FULL":data["M_NEW_WITHIN_FULL"],"F_NEW_WITHIN_FULL":data["F_NEW_WITHIN_FULL"],
      "NEW_WITHIN_FULL_POOLED":pd.concat([data["M_NEW_WITHIN_FULL"],data["F_NEW_WITHIN_FULL"]],ignore_index=True),
    }
    sel={k:selection(d,cache,a.null_sims,rng) for k,d in groups.items()}
    performance={
      "FULL":perf(data["M_FULL"],data["F_FULL"],a.perf_perm,rng),
      "NEW_TARGET":perf(data["M_NEW_TARGET"],data["F_NEW_TARGET"],a.perf_perm,rng),
      "NEW_WITHIN_FULL":perf(data["M_NEW_WITHIN_FULL"],data["F_NEW_WITHIN_FULL"],a.perf_perm,rng),
    }

    result={
      "analysis_role":"prospective_2023_validation_reveal",
      "plan_tag":PLAN_TAG,"cohort_tag":COHORT_TAG,
      "seed":a.seed,"null_sims":a.null_sims,"performance_permutations":a.perf_perm,
      "selection":sel,"performance":performance,
    }

    generated=[]
    for k,d in data.items():
        p=out/f"bazi_2023_{k}.csv"; d.to_csv(p,index=False,encoding="utf-8-sig"); generated.append(p)
    rp=out/"chess_2023_validation_results.json"
    rp.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8"); generated.append(rp)
    cp=out/"run_chess_2023_validation_reveal_v1.py"; shutil.copy2(Path(__file__).resolve(),cp); generated.append(cp)

    print("\n=== 2023 VALIDATION HEADLINE ===")
    print("\nH1 DAY-STEM DIRECTION")
    for lab in ["M_FULL","F_FULL","FULL_POOLED","M_NEW_TARGET","F_NEW_TARGET","NEW_TARGET_POOLED"]:
        x=sel[lab]["H1_stem_direction"]
        dirs=sum(int(q["direction_matches"]) for q in x["individual_pairs"])
        print(f"{lab}: n={sel[lab]['n']} | score={x['observed_mean_per_player']:.4f} vs null={x['null_mean_per_player']:.4f} | z={x['z']:.3f} p_high={x['empirical_p_high']:.4f} | pair directions={dirs}/5")
        print("  stems: "+" ".join(f"{s}={sel[lab]['day_stem_counts'][s]}" for s in STEMS))

    print("\nH2 SHANGGUAN SELECTION")
    for lab in ["M_FULL","M_NEW_TARGET","F_FULL","F_NEW_TARGET"]:
        x=sel[lab]["H2_shangguan"]
        print(f"{lab}: mean={x['observed_mean_per_player']:.4f} vs null={x['null_mean_per_player']:.4f} | z={x['z']:.3f} p_high={x['empirical_p_high']:.4f}")

    print("\nH3 DAY-MASTER PERFORMANCE")
    for lab in ["FULL","NEW_TARGET","NEW_WITHIN_FULL"]:
        x=performance[lab]
        a3=x["H3a_metal_gt_earth"]; b3=x["H3b_geng_gt_wu"]
        print(f"{lab}: Metal-Earth diff={a3['diff_A_minus_B']:.4f}, p_one={a3['p_one_A_gt_B']:.4f} | 庚-戊 diff={b3['diff_A_minus_B']:.4f}, p_one={b3['p_one_A_gt_B']:.4f}")

    print("\nH4 SG/PY vs ELO")
    for lab in ["FULL","NEW_TARGET"]:
        h=performance[lab]["H4_tengod_performance"]
        print(f"{lab}: SG pooled rho={h['shangguan_count_6pos']['pooled']['rho']:.4f} p={h['shangguan_count_6pos']['pooled']['p']:.4f} | PY pooled rho={h['pianyin_count_6pos']['pooled']['rho']:.4f} p={h['pianyin_count_6pos']['pooled']['p']:.4f}")

    if a.no_git:
        print("\n--no-git: reveal complete; Git untouched.")
        return

    if run(["git","diff","--cached","--name-only"],repo).strip():
        raise RuntimeError("Git index already has staged files")
    if run(["git","tag","--list",RESULT_TAG],repo).strip():
        raise RuntimeError(f"tag exists: {RESULT_TAG}")
    rels=[str(p.relative_to(repo)) for p in generated]
    run(["git","add","--",*rels],repo)
    run(["git","commit","-m","Add prospective 2023 chess validation reveal"],repo)
    run(["git","tag","-a",RESULT_TAG,"-m","Record prospective 2023 chess validation results"],repo)
    branch=run(["git","branch","--show-current"],repo)
    run(["git","push",a.remote,branch],repo)
    run(["git","push",a.remote,RESULT_TAG],repo)
    print("\n=== 2023 VALIDATION REVEAL FROZEN ===")
    print("Commit:",run(["git","rev-parse","HEAD"],repo))
    print("Tag:   ",RESULT_TAG)
    print("Output:",out)

if __name__=="__main__":
    main()
