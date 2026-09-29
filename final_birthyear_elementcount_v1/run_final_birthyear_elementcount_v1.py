#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
import argparse, io, json, math, re, shutil, subprocess, unicodedata, calendar
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import rankdata
from lunar_python import Solar

PLAN_TAG="final-birthyear-elementcount-plan-v1"
RESULT_TAG="final-birthyear-elementcount-results-v1"
OUTDIR="final_birthyear_elementcount_v1"

CHESS_TAG="chess-element-concentration-results-v1"
CHESS_PATH="chess_element_concentration_v1/element_concentration_player_features.csv"
TT_TAG="tt-element-concentration-results-v1"
TT_HIST="tt_element_concentration_v1/tt_element_concentration_historical_players.csv"
TT_TRAIN="tt_element_concentration_v1/tt_element_concentration_training_players.csv"

EXPECTED_CHESS_SOURCE_ROWS=2807
EXPECTED_TT_UNIQUE=719
B_DEFAULT=50000
SEED_DEFAULT=20260928

STEM_ELEMENT={"ç”²":"æœ¨","ä¹™":"æœ¨","ä¸™":"ç«","ä¸":"ç«","æˆŠ":"åœŸ","å·±":"åœŸ","åºš":"é‡‘","è¾›":"é‡‘","å£¬":"æ°´","ç™¸":"æ°´"}
BRANCH_MAIN_STEM={"å­":"ç™¸","ä¸‘":"å·±","å¯…":"ç”²","å¯":"ä¹™","è¾°":"æˆŠ","å·³":"ä¸™","åˆ":"ä¸","æœª":"å·±","ç”³":"åºš","é…‰":"è¾›","æˆŒ":"æˆŠ","äº¥":"å£¬"}

def run(cmd,cwd,check=True):
    print("$"," ".join(cmd))
    p=subprocess.run(cmd,cwd=str(cwd),text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    if p.stdout: print(p.stdout.rstrip())
    if check and p.returncode: raise RuntimeError("Command failed: "+" ".join(cmd))
    return p.stdout.strip()

def run_bytes(cmd,cwd):
    p=subprocess.run(cmd,cwd=str(cwd),stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    if p.returncode:
        raise RuntimeError(p.stderr.decode("utf-8","replace"))
    return p.stdout

def read_git_csv(repo,tag,path):
    listed=set(run(["git","ls-tree","-r","--name-only",tag],repo).splitlines())
    if path not in listed:
        raise RuntimeError(f"{tag}: missing {path}")
    b=run_bytes(["git","show",f"{tag}:{path}"],repo)
    d=pd.read_csv(io.BytesIO(b),encoding="utf-8-sig",dtype=str)
    print(f"[input] {tag}:{path} n={len(d)}")
    return d

def norm_text(x):
    if pd.isna(x): return ""
    s=unicodedata.normalize("NFKD",str(x))
    s="".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^A-Z0-9]+","",s.upper())

def first_nonblank(row, cols):
    for c in cols:
        if c in row.index:
            v=str(row[c]).strip()
            if v and v.lower() not in {"nan","none","<na>"}:
                return v
    return ""

def chess_key(row):
    v=first_nonblank(row,["identity_bridge_modern_fide_id","modern_fide_id"])
    if v: return "FID:"+re.sub(r"\D","",v)
    v=first_nonblank(row,["wikidata_person_qids","person_qid","qid"])
    if v: return "QID:"+v.split(";")[0].strip().upper()
    v=first_nonblank(row,["fide_id"])
    if v: return "RAWFID:"+re.sub(r"\D","",v)
    name=first_nonblank(row,["name","player_name"])
    dob=first_nonblank(row,["exact_dob_frozen","dob"])
    return "FALLBACK:"+norm_text(name)+"|"+dob[:10]

def tt_key(row):
    v=first_nonblank(row,["qid"])
    if v: return "QID:"+v.upper()
    v=first_nonblank(row,["ttr_site_player_id","site_id"])
    if v: return "TTR:"+re.sub(r"\D","",v)
    name=first_nonblank(row,["name","player_name"])
    dob=first_nonblank(row,["dob","_dob"])
    return "FALLBACK:"+norm_text(name)+"|"+dob[:10]

def coerce_common(d, domain, source_label):
    x=d.copy()
    if "birth_year_analysis" not in x.columns:
        dobcol="exact_dob_frozen" if "exact_dob_frozen" in x.columns else "dob"
        x["birth_year_analysis"]=pd.to_datetime(x[dobcol],errors="raise").dt.year
    x["birth_year_analysis"]=pd.to_numeric(x["birth_year_analysis"],errors="raise").astype(int)
    x["distinct_elements_6pos"]=pd.to_numeric(x["distinct_elements_6pos"],errors="raise").astype(float)
    x["_source_label"]=source_label
    if domain=="chess":
        x["_person_key"]=x.apply(chess_key,axis=1)
        dobcol="exact_dob_frozen" if "exact_dob_frozen" in x.columns else "dob"
    else:
        x["_person_key"]=x.apply(tt_key,axis=1)
        dobcol="dob" if "dob" in x.columns else "_dob"
    x["_dob_check"]=pd.to_datetime(x[dobcol],errors="raise").dt.strftime("%Y-%m-%d")
    return x

def dedup_people(d, domain):
    rows=[]
    conflicts=[]
    for key,g in d.groupby("_person_key",sort=False):
        if g["_dob_check"].nunique()!=1 or g["distinct_elements_6pos"].nunique()!=1:
            conflicts.append((key,g[["_source_label","_dob_check","distinct_elements_6pos"]].to_dict("records")))
            continue
        r=g.iloc[0].copy()
        r["source_memberships"]=";".join(sorted(set(g["_source_label"].astype(str))))
        r["source_row_count"]=len(g)
        rows.append(r)
    if conflicts:
        raise RuntimeError(f"{domain}: identity conflicts detected, first={conflicts[:3]}")
    out=pd.DataFrame(rows).reset_index(drop=True)
    print(f"[{domain}] source rows={len(d)} unique persons={len(out)} duplicate rows removed={len(d)-len(out)}")
    return out

def distinct_count_for_date(dt):
    ec=Solar.fromYmdHms(dt.year,dt.month,dt.day,12,0,0).getLunar().getEightChar()
    yp,mp,dp=ec.getYear(),ec.getMonth(),ec.getDay()
    branches="\u5b50\u4e11\u5bc5\u536f\u8fb0\u5df3\u5348\u672a\u7533\u9149\u620c\u4ea5"; mains="\u7678\u5df1\u7532\u4e59\u620a\u4e19\u4e01\u5df1\u5e9a\u8f9b\u620a\u58ec"; bm=lambda b: mains[branches.index(unicodedata.normalize("NFKC",b))]; stems=[yp[0],bm(yp[1]),mp[0],bm(mp[1]),dp[0],bm(dp[1])]
    stem_order="\u7532\u4e59\u4e19\u4e01\u620a\u5df1\u5e9a\u8f9b\u58ec\u7678"; els=[stem_order.index(unicodedata.normalize("NFKC",s))//2 for s in stems]
    return len(set(els))

def all_dates(y):
    for m in range(1,13):
        for d in range(1,calendar.monthrange(int(y),m)[1]+1):
            yield pd.Timestamp(year=int(y),month=m,day=d).date()

def build_year_null(years):
    rows=[]
    for i,y in enumerate(sorted(set(map(int,years))),1):
        vals=np.array([distinct_count_for_date(dt) for dt in all_dates(y)],float)
        rows.append({
            "birth_year":int(y),
            "calendar_distinct_mean":float(vals.mean()),
            "calendar_distinct_sd":float(vals.std(ddof=1)),
            "calendar_days":len(vals),
        })
        print(f"calendar {i}: {y}")
    return pd.DataFrame(rows)

def corr_stat(x,y):
    x=np.asarray(x,float); y=np.asarray(y,float)
    ok=np.isfinite(x)&np.isfinite(y)
    x=x[ok]; y=y[ok]
    if len(x)<4 or len(np.unique(x))<2 or len(np.unique(y))<2: return np.nan
    xr=rankdata(x); yr=rankdata(y)
    xr-=xr.mean(); yr-=yr.mean()
    den=math.sqrt(float((xr*xr).sum()*(yr*yr).sum()))
    return float((xr*yr).sum()/den) if den else np.nan

def perm_spearman(x,y,B,rng,direction="less",batch=1000):
    x=np.asarray(x,float); y=np.asarray(y,float)
    ok=np.isfinite(x)&np.isfinite(y); x=x[ok]; y=y[ok]
    n=len(x)
    xr=rankdata(x); yr=rankdata(y); xr-=xr.mean(); yr-=yr.mean()
    den=math.sqrt(float((xr*xr).sum()*(yr*yr).sum()))
    obs=float((xr*yr).sum()/den)
    ge=le=tw=done=0
    while done<B:
        b=min(batch,B-done)
        # random-key permutations; batch kept small for memory safety
        order=np.argsort(rng.random((b,n)),axis=1)
        sims=(yr[order]@xr)/den
        ge+=int((sims>=obs-1e-12).sum())
        le+=int((sims<=obs+1e-12).sum())
        tw+=int((np.abs(sims)>=abs(obs)-1e-12).sum())
        done+=b
    pg=(ge+1)/(B+1); pl=(le+1)/(B+1); pt=(tw+1)/(B+1)
    return {"n":n,"rho":obs,"direction":direction,
            "p_directional":pl if direction=="less" else pg,
            "p_two_sided":pt,"permutations":B}

def sex_norm(v):
    s=str(v).strip().lower()
    if s in {"m","male","ç”·"}: return "M"
    if s in {"f","female","å¥³"}: return "F"
    return "UNKNOWN"

def domain_tests(df,domain,B,rng):
    out=[]
    # pooled person-level raw and adjusted
    for metric,label in [
        ("distinct_elements_6pos","person_raw"),
        ("distinct_z_vs_birthyear_calendar","person_calendar_adjusted"),
    ]:
        r=perm_spearman(df["birth_year_analysis"],df[metric],B,rng,"less")
        out.append({"domain":domain,"analysis":label,"metric":metric,**r,
                    "birth_year_min":int(df.birth_year_analysis.min()),
                    "birth_year_max":int(df.birth_year_analysis.max())})

    # equal-weight birth-year sensitivity on adjusted z
    y=df.groupby("birth_year_analysis",as_index=False).agg(
        mean_adjusted_z=("distinct_z_vs_birthyear_calendar","mean"),
        n_players=("_person_key","size")
    )
    r=perm_spearman(y["birth_year_analysis"],y["mean_adjusted_z"],B,rng,"less")
    out.append({"domain":domain,"analysis":"birthyear_equal_weight_calendar_adjusted",
                "metric":"mean_adjusted_z",**r,
                "birth_year_min":int(y.birth_year_analysis.min()),
                "birth_year_max":int(y.birth_year_analysis.max())})

    # sex-specific descriptive
    if "gender" in df.columns:
        sx=df["gender"].map(sex_norm)
    elif "analysis_sex" in df.columns:
        sx=df["analysis_sex"].map(sex_norm)
    elif "sex" in df.columns:
        sx=df["sex"].map(sex_norm)
    else:
        sx=pd.Series(["UNKNOWN"]*len(df),index=df.index)

    for s in ["M","F"]:
        sub=df.loc[sx==s]
        if len(sub)>=20:
            r=perm_spearman(sub["birth_year_analysis"],sub["distinct_z_vs_birthyear_calendar"],B,rng,"less")
            out.append({"domain":domain,"analysis":f"sex_{s}_calendar_adjusted_descriptive",
                        "metric":"distinct_z_vs_birthyear_calendar",**r,
                        "birth_year_min":int(sub.birth_year_analysis.min()),
                        "birth_year_max":int(sub.birth_year_analysis.max())})
    return out,y

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--repo",default=r"..\1986wiki")
    ap.add_argument("--permutations",type=int,default=B_DEFAULT)
    ap.add_argument("--seed",type=int,default=SEED_DEFAULT)
    ap.add_argument("--remote",default="origin")
    ap.add_argument("--no-git",action="store_true")
    a=ap.parse_args()
    repo=Path(run(["git","rev-parse","--show-toplevel"],Path(a.repo))).resolve()
    if run(["git","tag","--list",PLAN_TAG],repo)!=PLAN_TAG:
        raise RuntimeError(f"Plan tag missing: {PLAN_TAG}")
    if not a.no_git:
        if run(["git","diff","--cached","--name-only"],repo):
            raise RuntimeError("Git index already has staged files")
        if run(["git","tag","--list",RESULT_TAG],repo):
            raise RuntimeError(f"Results tag already exists: {RESULT_TAG}")

    chess=read_git_csv(repo,CHESS_TAG,CHESS_PATH)
    if len(chess)!=EXPECTED_CHESS_SOURCE_ROWS:
        raise RuntimeError(f"Chess source rows={len(chess)} expected={EXPECTED_CHESS_SOURCE_ROWS}")
    chess=coerce_common(chess,"chess","chess_all_frozen_rows")
    chess=dedup_people(chess,"chess")

    th=coerce_common(read_git_csv(repo,TT_TAG,TT_HIST),"tt","historical")
    tt=coerce_common(read_git_csv(repo,TT_TAG,TT_TRAIN),"tt","training")
    tt=dedup_people(pd.concat([th,tt],ignore_index=True),"tt")
    if len(tt)!=EXPECTED_TT_UNIQUE:
        raise RuntimeError(f"TT unique persons={len(tt)} expected={EXPECTED_TT_UNIQUE}")

    print("\n=== FIRST FINAL TEMPORAL CALCULATION ===")
    years=list(chess.birth_year_analysis)+list(tt.birth_year_analysis)
    null=build_year_null(years)

    def attach(d):
        x=d.merge(null,left_on="birth_year_analysis",right_on="birth_year",how="left",validate="many_to_one")
        if x.calendar_distinct_mean.isna().any(): raise RuntimeError("Missing calendar null")
        x["distinct_residual_vs_birthyear_calendar"]=x["distinct_elements_6pos"]-x["calendar_distinct_mean"]
        x["distinct_z_vs_birthyear_calendar"]=x["distinct_residual_vs_birthyear_calendar"]/x["calendar_distinct_sd"]
        return x.drop(columns=["birth_year","birth_year_x","birth_year_y","calendar_birth_year"],errors="ignore")

    chess=attach(chess); tt=attach(tt)
    rng=np.random.default_rng(a.seed)
    rows=[]
    cr,cy=domain_tests(chess,"Chess",a.permutations,rng); rows+=cr
    tr,ty=domain_tests(tt,"TableTennis",a.permutations,rng); rows+=tr
    res=pd.DataFrame(rows)

    out=repo/OUTDIR; out.mkdir(parents=True,exist_ok=True)
    chess.to_csv(out/"chess_unique_players_temporal.csv",index=False,encoding="utf-8-sig")
    tt.to_csv(out/"tt_unique_players_temporal.csv",index=False,encoding="utf-8-sig")
    null.to_csv(out/"birthyear_calendar_distinct_null.csv",index=False,encoding="utf-8-sig")
    cy.assign(domain="Chess").to_csv(out/"chess_birthyear_means.csv",index=False,encoding="utf-8-sig")
    ty.assign(domain="TableTennis").to_csv(out/"tt_birthyear_means.csv",index=False,encoding="utf-8-sig")
    res.to_csv(out/"birthyear_elementcount_temporal_tests.csv",index=False,encoding="utf-8-sig")

    headline={}
    for domain in ["Chess","TableTennis"]:
        sub=res[res.domain==domain].set_index("analysis")
        headline[domain]={
            "raw":sub.loc["person_raw"].to_dict(),
            "calendar_adjusted":sub.loc["person_calendar_adjusted"].to_dict(),
            "year_equal_weight":sub.loc["birthyear_equal_weight_calendar_adjusted"].to_dict(),
        }
    js={
        "analysis_role":"final_posthoc_exploratory_temporal_followup_plan_frozen_before_calculation",
        "plan_tag":PLAN_TAG,
        "seed":a.seed,
        "permutations":a.permutations,
        "chess_unique_n":len(chess),
        "tt_unique_n":len(tt),
        "headline":headline,
    }
    (out/"birthyear_elementcount_temporal_results_v1.json").write_text(json.dumps(js,ensure_ascii=False,indent=2),encoding="utf-8")

    def fmt(domain):
        s=res[res.domain==domain].set_index("analysis")
        a1=s.loc["person_raw"]; a2=s.loc["person_calendar_adjusted"]; a3=s.loc["birthyear_equal_weight_calendar_adjusted"]
        return [
            f"## {domain}",
            f"- Unique N: {int(a1['n'])}; birth years {int(a1['birth_year_min'])}-{int(a1['birth_year_max'])}",
            f"- Raw birth year vs distinct-elements: rho={a1['rho']:.5f}, p_dir(<0)={a1['p_directional']:.6f}, p2={a1['p_two_sided']:.6f}",
            f"- Calendar-adjusted z vs birth year: rho={a2['rho']:.5f}, p_dir(<0)={a2['p_directional']:.6f}, p2={a2['p_two_sided']:.6f}",
            f"- Equal-weight birth-year mean adjusted z: rho={a3['rho']:.5f}, p_dir(<0)={a3['p_directional']:.6f}, p2={a3['p_two_sided']:.6f}",
        ]

    md=["# Final Birth-Year Ã— Element-Count Temporal Results V1","",
        "Directional hypothesis: later birth year -> fewer distinct elements (rho < 0).",""]
    md+=fmt("Chess")+[""]+fmt("TableTennis")
    (out/"FINAL_BIRTHYEAR_ELEMENTCOUNT_RESULTS_V1.md").write_text("\n".join(md),encoding="utf-8")
    shutil.copy2(Path(__file__).resolve(),out/"run_final_birthyear_elementcount_v1.py")

    print("\n=== FINAL BIRTHYEAR Ã— ELEMENT COUNT HEADLINE ===")
    for domain in ["Chess","TableTennis"]:
        s=res[res.domain==domain].set_index("analysis")
        r=s.loc["person_raw"]; z=s.loc["person_calendar_adjusted"]; y=s.loc["birthyear_equal_weight_calendar_adjusted"]
        print(f"{domain}: unique N={int(r['n'])}, birth years {int(r['birth_year_min'])}-{int(r['birth_year_max'])}")
        print(f"  RAW: rho={r['rho']:.5f} p_dir(<0)={r['p_directional']:.6f} p2={r['p_two_sided']:.6f}")
        print(f"  CALENDAR-ADJ: rho={z['rho']:.5f} p_dir(<0)={z['p_directional']:.6f} p2={z['p_two_sided']:.6f}")
        print(f"  YEAR-EQUAL-WEIGHT: rho={y['rho']:.5f} p_dir(<0)={y['p_directional']:.6f} p2={y['p_two_sided']:.6f}")
        for lab in [f"sex_M_calendar_adjusted_descriptive",f"sex_F_calendar_adjusted_descriptive"]:
            if lab in s.index:
                q=s.loc[lab]
                print(f"  {lab}: rho={q['rho']:.5f} p_dir={q['p_directional']:.6f} p2={q['p_two_sided']:.6f} n={int(q['n'])}")

    if a.no_git:
        print("\n--no-git: generated results; Git untouched")
        return

    files=[
        out/"chess_unique_players_temporal.csv",
        out/"tt_unique_players_temporal.csv",
        out/"birthyear_calendar_distinct_null.csv",
        out/"chess_birthyear_means.csv",
        out/"tt_birthyear_means.csv",
        out/"birthyear_elementcount_temporal_tests.csv",
        out/"birthyear_elementcount_temporal_results_v1.json",
        out/"FINAL_BIRTHYEAR_ELEMENTCOUNT_RESULTS_V1.md",
        out/"run_final_birthyear_elementcount_v1.py",
    ]
    rels=[p.relative_to(repo).as_posix() for p in files]
    run(["git","add","--",*rels],repo)
    actual={x.replace("\\","/") for x in run(["git","diff","--cached","--name-only"],repo).splitlines() if x.strip()}
    if actual!=set(rels):
        raise RuntimeError(f"Staging mismatch: expected={sorted(rels)} actual={sorted(actual)}")
    run(["git","commit","-m","Add final birth-year element-count temporal results"],repo)
    run(["git","tag","-a",RESULT_TAG,"-m","Record final birth-year element-count temporal results"],repo)
    branch=run(["git","branch","--show-current"],repo)
    if not branch: raise RuntimeError("Detached HEAD")
    run(["git","push",a.remote,branch],repo)
    run(["git","push",a.remote,RESULT_TAG],repo)
    print("\n=== FINAL TEMPORAL RESULTS FROZEN ===")
    print("Commit:",run(["git","rev-parse","HEAD"],repo))
    print("Tag:   ",RESULT_TAG)
    print("Output:",out)

if __name__=="__main__":
    main()



