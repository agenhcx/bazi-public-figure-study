#!/usr/bin/env python3
"""Gated independent audit of the post-reveal NAS hidden-stem supplement.

No data are opened at module import. Historical sources are parsed selectively:
only constants and pure scoring functions are compiled; old cohort loaders,
date-transform functions, CLI entry points, and result files are never run.
Exact count-tail p values are QA references, not substituted published results.
"""
import argparse
import ast
from collections import Counter
import datetime as dt
import gzip
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import zipfile

import numpy as np

BASE = Path(__file__).resolve().parents[2]
REPO = BASE.parents[1]
STEMS = list("甲乙丙丁戊己庚辛壬癸")
BRANCHES = list("子丑寅卯辰巳午未申酉戌亥")
MODELS = ["M0_5", "M1_priority_5", "M1_share_5", "M1_any_5", "M2_main_7", "M3_priority_7", "M3_share_7", "M3_any_7"]
TRAITS = ["PI", "SG"]
TARGETS = ["偏印", "伤官"]
DENOMINATORS = [5,5,5,5,7,7,7,7]
CASES = ["strict_primary", "expanded", "strict_noJie", "strict_yearMonth"]
R, COUNT_SCALE, PRESENCE_SCALE = 99999,72,12
V4_SHA = "53302ef5c4bbb946adcaceb70d7a7fd576c7f06d03c3e7080874654e1a2644f9"
PRIOR_SHA = "34485303ee47d2402c8bd960fe5e22181f8e667664e294b99b4ae21f427d0ae4"
HISTORICAL_PINS = {
    "run_chess_c7_hiddenstem_hour_performance_sensitivity_v1.py": "93774e8a71f826d816ab113046a4dee27c95761f67701ec8e1ab21a4a2ebbeba",
    "run_tt_stage2_targeted_holdout_v2.py": "940ae56a060a4b4cb2a320ae0f70abebd41fb37680ba34c4a46e6d88aa1fcd94"}


def require(ok, message):
    if not bool(ok):
        raise AssertionError(message)


def close(a,b,message,atol=1e-10):
    require(np.allclose(a,b,rtol=1e-10,atol=atol),message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def id_hash(ids):
    value=json.dumps(sorted(ids),ensure_ascii=False,sort_keys=True,separators=(",",":"))+"\n"
    return hashlib.sha256(value.encode()).hexdigest()


def load_historical_pure_functions(repo=REPO):
    """Safe AST subset: no imports, top-level code, or historical outcomes."""
    envs=[]
    specifications=[
        ("run_chess_c7_hiddenstem_hour_performance_sensitivity_v1.py",
         {"STEMS","BRANCHES","STEM_ELEMENT","STEM_YANG","HIDDEN_STEMS"},
         {"ten_god","tg_score","hour_stem_index","branch_tg_contribution"}),
        ("run_tt_stage2_targeted_holdout_v2.py",
         {"TGS","TGI","STEMS","BRANCHES","INFO","GEN","CTL","H"},
         {"tg","one","hour_stem","branch"})]
    for filename,constants,functions in specifications:
        source=Path(repo)/filename
        require(sha(source)==HISTORICAL_PINS[filename],"Historical pure-code hash changed: "+filename)
        tree=ast.parse(source.read_text(encoding="utf-8"))
        selected=[]
        for node in tree.body:
            if isinstance(node,ast.Assign) and all(isinstance(t,ast.Name) and t.id in constants for t in node.targets):
                selected.append(node)
            elif isinstance(node,ast.FunctionDef) and node.name in functions:
                selected.append(node)
        env={"np":np}
        exec(compile(ast.Module(body=selected,type_ignores=[]),str(source)+"::pure_scoring_subset","exec"),env)
        require(constants<=set(env) and functions<=set(env),"Missing selected historical constant/function")
        envs.append(env)
    return envs


def historical_reference(year_pillar,month_pillar,day_pillar,c7,tt):
    """Eight models, two targets; count/72 and presence/12 are exact scales."""
    ys,yb=STEMS.index(year_pillar[0]),BRANCHES.index(year_pillar[1])
    ms,mb=STEMS.index(month_pillar[0]),BRANCHES.index(month_pillar[1])
    dm,db=STEMS.index(day_pillar[0]),BRANCHES.index(day_pillar[1])
    out=np.zeros((8,2,2),dtype=np.int16)
    for t,target in enumerate(TARGETS):
        base=c7["tg_score"](dm,ys,target)+c7["tg_score"](dm,ms,target)
        visible={ys,ms}  # Day Master is reference only, never exposure.
        for model,rule in enumerate(["main","priority","share","any"]):
            score=base+sum(c7["branch_tg_contribution"](dm,b,visible,target,rule) for b in [yb,mb,db])
            if rule in ["main","priority"]:
                tt_score=tt["one"](STEMS[dm],STEMS[ys])+tt["one"](STEMS[dm],STEMS[ms])
                for branch in [yb,mb,db]:
                    tt_score+=tt["branch"](STEMS[dm],BRANCHES[branch],{STEMS[ys],STEMS[ms]},rule=="priority")
                close(score,float(tt_score[8 if t==0 else 3]),"Independent TT/C7 main/priority disagreement",atol=1e-12)
            out[model,t,0]=int(round(score*COUNT_SCALE))
            out[model,t,1]=PRESENCE_SCALE*int(score>0)
            close(out[model,t,0]/COUNT_SCALE,score,"Count72 cannot exactly represent historical score",atol=1e-12)
        for model,rule in enumerate(["main","priority","share","any"],start=4):
            scores=[]
            for hb in range(12):
                hs=c7["hour_stem_index"](dm,hb)
                require(hs==STEMS.index(tt["hour_stem"](STEMS[dm],hb)),"Historical hour-stem formula differs")
                vis={ys,ms,hs}
                score=base+c7["tg_score"](dm,hs,target)
                score+=sum(c7["branch_tg_contribution"](dm,b,vis,target,rule) for b in [yb,mb,db,hb])
                scores.append(score)
            # Nonlinearity is respected: mean(I(score_hour>0)), not I(mean>0).
            mean_score=sum(scores)/12
            out[model,t,0]=int(round(mean_score*COUNT_SCALE))
            out[model,t,1]=sum(score>0 for score in scores)
            close(out[model,t,0]/COUNT_SCALE,mean_score,"Hour mean cannot be represented by count72",atol=1e-12)
    return out


def verify_gate(args):
    require(Path(args.results).is_file(),"A completed hidden supplement result is required")
    require(not Path(args.output).exists(),"Audit output already exists; no overwrite")
    receipt=json.loads(Path(args.execution_receipt).read_text())
    require(receipt.get("country")=="NAS" and receipt.get("inference_authorized") is True,"NAS-only hidden authorization missing")
    require(receipt.get("remote_Git_lock_verified_before_inference") is True,"Missing prior remote hidden lock")
    commit=receipt.get("lock_commit_sha","")
    require(re.fullmatch(r"[0-9a-f]{40}",commit),"Invalid hidden supplement commit")
    repo=Path(subprocess.check_output(["git","-C",str(BASE),"rev-parse","--show-toplevel"],text=True).strip())
    require(subprocess.check_output(["git","-C",str(repo),"rev-parse","HEAD"],text=True).strip()==commit,"Current HEAD is not locked supplement")
    pins=receipt.get("file_sha256",{})
    require(str(Path(__file__).resolve().relative_to(BASE)) in pins,"Execution receipt must pin independent hidden audit")
    require("hidden_stem_v1/scripts/hidden_features.py" in pins and any(p.endswith(".md") for p in pins),"Encoder and note not pinned")
    for rel,digest in pins.items():
        path=(BASE/rel).resolve();require(path.is_relative_to(BASE),"Execution pin escapes study root")
        require(sha(path)==digest,"Execution pin changed: "+rel)
        content=subprocess.check_output(["git","-C",str(repo),"show",commit+":"+str(path.relative_to(repo))])
        require(hashlib.sha256(content).hexdigest()==digest,"Execution file differs from committed object: "+rel)
    paths={"charts":Path(args.charts_dir)/"charts_unique_expanded.jsonl.gz","groups":Path(args.charts_dir)/"group_memberships.jsonl.gz",
           "calendar_pool":Path(args.calendar_dir)/"calendar_pool.npz","hidden_pool":Path(args.hidden_dir)/"hidden_pool.npz",
           "V4_zip":Path(args.v4_zip),"prior_NAS_results":Path(args.prior_results)}
    keys={"charts":"input_chart_sha256","groups":"input_groups_sha256","calendar_pool":"pool_npz_sha256","hidden_pool":"hidden_pool_npz_sha256"}
    for name,key in keys.items():require(sha(paths[name])==receipt.get(key),"Input SHA changed: "+name)
    require(sha(paths["V4_zip"])==V4_SHA and sha(paths["prior_NAS_results"])==PRIOR_SHA,"V4 or previous disclosed NAS result changed")
    return receipt,paths,repo


def npz(path):
    with np.load(path,allow_pickle=False) as source:return {k:source[k] for k in source.files}


def select_rows(paths,original_lock):
    needed={pop+"/"+name+".jsonl.gz" for pop in ["strict","expanded"] for name in ["by_institution/NAS","academy_excluding_official_Nobel"]}
    groups={p:set() for p in needed}
    with gzip.open(paths["groups"],"rt",encoding="utf-8") as handle:
        for line in handle:
            r=json.loads(line)
            if r["population_path"] in groups:groups[r["population_path"]].add(r["person_id"])
    ids={pop:groups[pop+"/by_institution/NAS.jsonl.gz"]&groups[pop+"/academy_excluding_official_Nobel.jsonl.gz"] for pop in ["strict","expanded"]}
    require(len(ids["strict"])==908 and len(ids["expanded"])==1462 and ids["strict"]<=ids["expanded"],"NAS fixed IDs changed")
    rows={}
    with gzip.open(paths["charts"],"rt",encoding="utf-8") as handle:
        for line in handle:
            r=json.loads(line)
            if r["person_id"] in ids["expanded"]:
                require(r["person_id"] not in rows,"Duplicate NAS chartID")
                rows[r["person_id"]]=r
    require(set(rows)==ids["expanded"],"Selected NAS chart missing")
    with zipfile.ZipFile(paths["V4_zip"]) as archive:
        source=gzip.decompress(archive.read("scientist_north_data_freeze_v4/outputs/person_data_eligibility_v4.jsonl.gz"))
    seen=set()
    for line in source.decode().splitlines():
        original=json.loads(line);pid=original["person_id"]
        if pid not in rows:continue
        r=rows[pid]
        require(all(r[k]==original[k] for k in ["analysis_DOB","DOB_support","qualified_academy_memberships","included_strict","included_expanded","person_level_DOB_analysis_hold"]),"Frozen NAS source/identity/DOB changed")
        require(r["assumptions_lock_commit"]==original_lock and r["hemisphere"]=="north" and not r["person_level_DOB_analysis_hold"],"NAS chart lock or hold changed")
        require(r["full_official_award_status"]["eligible_as_nonNobel_control_for_award_condition_only"] is True,"NAS nonNobel classification changed")
        dt.date.fromisoformat(r["analysis_DOB"]);seen.add(pid)
    require(seen==ids["expanded"],"Selected NAS original V4 records missing")
    caseids={"strict_primary":ids["strict"],"expanded":ids["expanded"],
             "strict_noJie":{pid for pid in ids["strict"] if not rows[pid]["jie_boundary_plus_minus_one_civil_day"]},"strict_yearMonth":ids["strict"]}
    require(len(caseids["strict_noJie"])==825,"NAS noJie825 set changed")
    return rows,caseids


def validate_pools(calendar,hidden):
    require(hidden["models"].tolist()==MODELS and hidden["traits"].tolist()==TRAITS,"Hidden model order changed")
    require(hidden["position_denominators"].tolist()==DENOMINATORS,"Hidden denominators changed")
    for key in ["dates","year","month","jie_boundary_day","jie_boundary_plus_minus_one_civil_day"]:
        require(np.array_equal(calendar[key],hidden[key]),"Calendar/hidden date metadata mismatch: "+key)
    counts,presence=hidden["count_scaled72"],hidden["presence_scaled12"]
    require(counts.shape==presence.shape==(55152,8,2),"Wrong hidden calendar dimensions")
    require(hidden["features"].shape==(55152,8,2,2),"Wrong combined hidden feature dimensions")
    require(np.array_equal(hidden["features"][...,0],counts) and np.array_equal(hidden["features"][...,1],presence),"Combined and named scaled feature arrays differ")
    require(np.issubdtype(counts.dtype,np.integer) and np.issubdtype(presence.dtype,np.integer),"Scaled features are not exact integers")
    require(np.all(counts>=0) and np.all(counts<=np.asarray(DENOMINATORS)[None,:,None]*COUNT_SCALE),"Hidden count beyond5/7denominator")
    require(np.all(presence>=0) and np.all(presence<=PRESENCE_SCALE),"Presence beyond0..1")
    require(np.all(counts[:,:2]%COUNT_SCALE==0),"M0/priority5 count not integral")
    require(np.array_equal(presence[:,:4],(counts[:,:4]>0)*PRESENCE_SCALE),"Five-position presence is not indicator")
    require(np.array_equal(counts[:,0,:]//COUNT_SCALE,calendar["features"][:,:2]),"M0 full-calendar count differs from preceding NAS pool")
    start=dt.date(1835,1,1);stop=dt.date(1985,12,31)
    dates=[(start+dt.timedelta(days=i)).isoformat() for i in range((stop-start).days+1)]
    require(calendar["dates"].tolist()==dates,"Calendar valid-date universe changed")
    return {date:i for i,date in enumerate(dates)}


def exact_distribution(person_keys,cache,model,trait):
    d=np.array([1.0])
    for key in person_keys:
        p=cache[key]["pmfs"][(model,trait)]
        last=np.flatnonzero(p)[-1]
        d=np.convolve(d,p[:last+1])
    require(abs(d.sum()-1)<1e-9 and np.all(d>=0),"Convolution probability mass error")
    return d/d.sum()


def conditional_arrays(rows,calendar,hidden,month,no_jie):
    keys=[];cache={}
    for row in rows:
        date=dt.date.fromisoformat(row["analysis_DOB"]);key=(date.year,date.month if month else None);keys.append(key)
        if key in cache:continue
        mask=calendar["year"]==date.year
        if month:mask&=calendar["month"]==date.month
        if no_jie:mask&=~calendar["jie_boundary_plus_minus_one_civil_day"].astype(bool)
        require(mask.any(),"Empty conditional hidden calendar")
        c=hidden["count_scaled72"][mask];p=hidden["presence_scaled12"][mask]
        pmfs={(m,t):np.bincount(c[:,m,t]//COUNT_SCALE,minlength=6).astype(float)/len(c) for m in [0,1] for t in [0,1]}
        cache[key]={"count_mean":c.mean(axis=0)/COUNT_SCALE,"presence_mean":p.mean(axis=0)/PRESENCE_SCALE,"pmfs":pmfs,"dates":len(c)}
    return keys,cache


def audit_case(case,rows,reference,calendar,hidden,index,case_index,prior_case):
    name=CASES[case_index];n=len(rows);month=name=="strict_yearMonth";nojie=name=="strict_noJie"
    require(case["case"]==name and case["case_index"]==case_index and case["n"]==n,"Case definition changed")
    require(case["person_ids_sha256"]==id_hash(r["person_id"] for r in rows)==prior_case["person_ids_sha256"],"Case IDs differ from frozen/prior NAS case")
    require(case["calendar_condition"]==("year_and_month" if month else "year") and case["Jie_pm1_excluded_from_observed_and_calendar"] is nojie,"Wrong/asymmetric null condition")
    observed=np.stack([reference[r["analysis_DOB"]] for r in rows])
    keys,cache=conditional_arrays(rows,calendar,hidden,month,nojie)
    expected_count=np.stack([cache[k]["count_mean"] for k in keys]).mean(axis=0)
    expected_presence=np.stack([cache[k]["presence_mean"] for k in keys]).mean(axis=0)
    obs_count=observed[:,:,:,0].mean(axis=0)/COUNT_SCALE
    obs_presence=observed[:,:,:,1].mean(axis=0)/PRESENCE_SCALE
    descriptions=case["model_trait_descriptions"]
    require(len(descriptions)==16,"Eight-model two-trait table not complete")
    for m in range(8):
        for t in range(2):
            entry=descriptions[2*m+t];den=DENOMINATORS[m]
            require(entry["model"]==MODELS[m] and entry["trait"]==TRAITS[t] and entry["position_denominator"]==den,"Model/trait/denominator changed")
            checks={"count_mean":obs_count[m,t],"calendar_expected_count_mean":expected_count[m,t],"count_mean_excess":obs_count[m,t]-expected_count[m,t],
                    "position_mean_share":obs_count[m,t]/den,"calendar_expected_position_mean_share":expected_count[m,t]/den,
                    "position_mean_share_excess":(obs_count[m,t]-expected_count[m,t])/den,
                    "position_mean_share_excess_percentage_points":100*(obs_count[m,t]-expected_count[m,t])/den,
                    "person_presence_probability":obs_presence[m,t],"calendar_expected_person_presence_probability":expected_presence[m,t],
                    "person_presence_probability_excess":obs_presence[m,t]-expected_presence[m,t],"person_presence_excess_percentage_points":100*(obs_presence[m,t]-expected_presence[m,t])}
            for key,value in checks.items():close(entry[key],value,"Description mismatch: "+name+"/"+MODELS[m]+"/"+TRAITS[t]+"/"+key)
            require(entry["descriptive_only"] is True and entry["hypothetical_hour_sensitivity"] is (m>=4),"Description promoted to inference")
            label="P(score>0)_averaged_over12_equal_hour_branches" if m>=4 else "P(score>0)_across_people"
            require(entry["presence_definition"]==label,"Wrong presence interpretation")
    require(case["presence_hypothesis_tests_performed"] is False and case["eight_model_multiple_test_search_performed"] is False,"Unauthorized model/presence tests")
    require(len(case["nominal_count_tests"])==4,"Wrong nominal test family")
    prior_tests={r["metric"]:r for r in prior_case["calendar_MC_tests"]};qa=[]
    for j,test in enumerate(case["nominal_count_tests"]):
        m,t=divmod(j,2);seed=2026111300+t if m==0 else 202611160000+1000*case_index+t
        require(test["model"]==MODELS[m] and test["trait"]==TRAITS[t] and test["seed"]==seed and test["replicates"]==R,"Test identity/seed/replicate changed")
        total=int(observed[:,m,t,0].sum()//COUNT_SCALE)
        require(test["observed_integer_count_sum"]==total and test["tail"]=="greater_inclusive_integer_sum","Wrong integer count/tail")
        extreme=test["extreme_replicates_including_ties"];require(isinstance(extreme,int) and 0<=extreme<=R,"Invalid extreme count")
        p=(extreme+1)/(R+1);close(test["p_nominal_plus_one"],p,"Nominal plus-one p formula wrong",atol=1e-15)
        require(test["multiple_comparison_adjusted"] is False and test["original_18_or_country36_family_member"] is False and test["confirmatory_global_claim"] is False,"Post-reveal p incorrectly promoted")
        role="previous_M0_p_reproduction" if m==0 else "post_reveal_supplement_priority5_nominal_test"
        require(test["role"]==role,"Wrong inferential role")
        distribution=exact_distribution(keys,cache,m,t)
        exact=float(distribution[total:].sum()) if total<len(distribution) else 0.0
        tolerance=5*math.sqrt(exact*(1-exact)/R)+2/R
        require(abs(p-exact)<=tolerance,"Nominal MC p fails exact inclusive conditional count-tail QA")
        if m==0:
            old=prior_tests["PI_count" if t==0 else "SG_count"]
            require(old["observed_integer_sum"]==total and old["seed"]==seed and old["replicates"]==R and old["extreme_replicates_including_ties"]==extreme and old["p_nominal_plus_one"]==test["p_nominal_plus_one"],"M0 count/seed/extreme/p does not exactly reproduce prior disclosed NAS result")
            oldmetric=prior_case["scalar_metrics"][t]
            close(obs_count[m,t],oldmetric["observed_mean_or_rate"],"M0 observed mean mismatch")
            close(expected_count[m,t],oldmetric["calendar_expected_mean_or_rate"],"M0 null mean mismatch")
        qa.append({"model":MODELS[m],"trait":TRAITS[t],"reported_nominal_MC_p_unchanged":p,"exact_upper_inclusive_QA_p":exact,"absolute_difference":abs(p-exact),"allowed_5MCse_plus_2overR":tolerance,"exact_QA_p_does_not_replace_reported_MC_p":True,"M0_prior_result_exactly_reproduced":m==0})
    return {"case":name,"n":n,"person_ids_sha256":case["person_ids_sha256"],"all16_descriptions_recomputed_from_historical_reference":True,"count_and_presence_expectations_independently_recomputed":True,"nominal_count_tail_QA":qa}


def main(args):
    receipt,paths,repo=verify_gate(args)
    result=json.loads(Path(args.results).read_text())
    require(result["schema"]=="NAS_hidden_stem_post_reveal_supplement_v1" and result["country"]=="NAS","Unexpected hidden result")
    require(result["execution_lock_receipt"]==receipt and result["models"]==MODELS and result["traits"]==TRAITS and result["case_order"]==CASES,"Hidden result receipt/schema changed")
    require(result["post_M0_reveal_supplement_not_original_confirmatory_preregistration"] is True,"Post-reveal timing not disclosed")
    require(result["source_identity_DOB_membership_support_unchanged"] is True,"Source mutation claimed")
    for name in ["charts","groups","calendar_pool","hidden_pool"]:require(result["hashes"][name+"_sha256"]==sha(paths[name]),"Result source hash mismatch: "+name)
    require(result["hashes"]["engine_sha256"]==sha(BASE/"hidden_stem_v1/scripts/analyze_hidden.py") and result["hashes"]["receipt_sha256"]==sha(args.execution_receipt),"Result engine/receipt hash differs")
    charts,caseids=select_rows(paths,receipt["original_assumptions_lock_commit"])
    calendar,hidden=npz(paths["calendar_pool"]),npz(paths["hidden_pool"]);index=validate_pools(calendar,hidden)
    c7,tt=load_historical_pure_functions(repo)
    reference={}
    for row in charts.values():
        date=row["analysis_DOB"];i=index[date]
        for pillar in ["year_pillar","month_pillar","day_pillar"]:require(row[pillar]==str(calendar[pillar][i]),"Observed and calendar pillars disagree")
        if date not in reference:reference[date]=historical_reference(row["year_pillar"],row["month_pillar"],row["day_pillar"],c7,tt)
        actual=np.stack([hidden["count_scaled72"][i],hidden["presence_scaled12"][i]],axis=-1)
        require(np.array_equal(actual,reference[date]),"Selected NAS hidden encoding differs from independent historical functions")
        require(bool(calendar["jie_boundary_plus_minus_one_civil_day"][i])==row["jie_boundary_plus_minus_one_civil_day"],"Observed/calendar Jie flag differs")
    sample=np.unique(np.linspace(0,len(index)-1,512,dtype=int))
    for i in sample:
        ref=historical_reference(str(calendar["year_pillar"][i]),str(calendar["month_pillar"][i]),str(calendar["day_pillar"][i]),c7,tt)
        require(np.array_equal(ref,np.stack([hidden["count_scaled72"][i],hidden["presence_scaled12"][i]],axis=-1)),"Deterministic512calendar reference sample differs")
    previous=json.loads(paths["prior_NAS_results"].read_text());prior={c["case"]:c for c in previous["cases"]}
    require([case["case"] for case in result["cases"]]==CASES,"Missing/reordered supplement case")
    checks=[audit_case(case,[charts[pid] for pid in sorted(caseids[name])],reference,calendar,hidden,index,i,prior[name]) for i,(name,case) in enumerate(zip(CASES,result["cases"]))]
    output={"schema":"NAS_hidden_stem_independent_QA_v1","status":"PASS","country":"NAS","execution_lock_commit":receipt["lock_commit_sha"],"historical_pure_functions_only_no_old_cohort_loads":True,"selected_NAS_people_independently_encoded":len(charts),"unique_selected_NAS_dates_independently_encoded":len(reference),"deterministic_calendar_reference_dates":len(sample),"full_calendar_M0_matches_previous_cache":True,"cases":checks,"exact_QA_p_replaces_locked_MC_p":False,"Nobel_or_other_country_hidden_feature_aggregates_computed":False,"source_inputs_and_code_SHA256":{**{k:sha(v) for k,v in paths.items()},"result":sha(args.results),"receipt":sha(args.execution_receipt),"audit_script":sha(__file__),"historical_sources":HISTORICAL_PINS},"completed_at_utc":dt.datetime.now(dt.timezone.utc).isoformat()}
    out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(output,ensure_ascii=False,indent=2,allow_nan=False)+"\n")
    print(json.dumps({"status":"PASS","country":"NAS","cases":len(checks),"output":str(out)}))


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    for option in ["charts-dir","calendar-dir","hidden-dir","v4-zip","prior-results","execution-receipt","results","output"]:parser.add_argument("--"+option,required=True)
    main(parser.parse_args())
