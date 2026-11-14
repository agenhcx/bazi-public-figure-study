#!/usr/bin/env python3
"""Independent UK six-country diagnostic audit; real data require remote lock."""
import argparse
import ast
from collections import Counter
import datetime as dt
import gzip
import hashlib
import json
import math
from pathlib import Path
import subprocess
import zipfile

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
ENGINE = ROOT / 'rs_reveal_work/scripts/analyze_rs_country.py'
OLD_COMMIT = '327cc1382828b2159a55db9c3a20231c1546345a'
OLD_PATH = 'studies/scientist_north_bazi_v1/reveal_v1/scripts/analyze_country.py'
SAME_FUNCTIONS = ['observed_arrays', 'CalendarModel', 'mc_tests', 'bootstrap_intervals', 'descriptive', 'run_case']
METRICS = ['PI_count','SG_count','GY_narrow','SGY_narrow','water_DM','DM_index']
CASES = ['strict_primary','expanded','strict_broad','strict_noJie','strict_yearMonth','expanded_withoutLOC','strict_withoutFields']
STEMS = list('甲乙丙丁戊己庚辛壬癸')
GODS = '比肩 劫财 食神 伤官 偏财 正财 七杀 正官 偏印 正印'.split()
MAIN = dict(zip('子丑寅卯辰巳午未申酉戌亥','癸己甲乙戊丙丁己庚辛戊壬'))
TG_ROWS = [
 '比肩 劫财 食神 伤官 偏财 正财 七杀 正官 偏印 正印',
 '劫财 比肩 伤官 食神 正财 偏财 正官 七杀 正印 偏印',
 '偏印 正印 比肩 劫财 食神 伤官 偏财 正财 七杀 正官',
 '正印 偏印 劫财 比肩 伤官 食神 正财 偏财 正官 七杀',
 '七杀 正官 偏印 正印 比肩 劫财 食神 伤官 偏财 正财',
 '正官 七杀 正印 偏印 劫财 比肩 伤官 食神 正财 偏财',
 '偏财 正财 七杀 正官 偏印 正印 比肩 劫财 食神 伤官',
 '正财 偏财 正官 七杀 正印 偏印 劫财 比肩 伤官 食神',
 '食神 伤官 偏财 正财 七杀 正官 偏印 正印 比肩 劫财',
 '伤官 食神 正财 偏财 正官 七杀 正印 偏印 劫财 比肩']
TG = {ds:dict(zip(STEMS,[GODS.index(x) for x in row.split()])) for ds,row in zip(STEMS,TG_ROWS)}
PINS = {'v4_zip':'53302ef5c4bbb946adcaceb70d7a7fd576c7f06d03c3e7080874654e1a2644f9',
        'calendar_npz':'d150883033464ebd3afafaf764738ed3b573d0d0fb4bd252a955e403a75fcc8b'}
ID_SHA = '15d3eadfe82ca2de2b8b0fd0430083edd7cd450c5d7086d33985c0943fbdede4'
EXACT_PRIMARY_CHECKS = [0,2,4]


def require(ok,message):
    if not bool(ok): raise AssertionError(message)


def close(a,b,message,atol=1e-8):
    require(np.allclose(a,b,rtol=1e-9,atol=atol),message)


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def ids_hash(ids):
    return hashlib.sha256((json.dumps(sorted(ids),ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n').encode()).hexdigest()


def original_functions_unchanged():
    old = subprocess.run(['git','show',OLD_COMMIT+':'+OLD_PATH],cwd=ROOT/'academy_repo',text=True,capture_output=True,check=True).stdout
    new = ENGINE.read_text()
    def nodes(source):
        return {n.name:ast.dump(n,include_attributes=False) for n in ast.parse(source).body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
    oldnodes,newnodes=nodes(old),nodes(new)
    require(all(oldnodes[x]==newnodes[x] for x in SAME_FUNCTIONS),'Original statistical function AST changed')
    return {'original_commit':OLD_COMMIT,'original_source_sha256':hashlib.sha256(old.encode()).hexdigest(),'functions_AST_identical':SAME_FUNCTIONS}


def literal(yp,mp,dp):
    gods=np.zeros((len(dp),10),dtype=np.int64);dm=np.empty(len(dp),dtype=np.int64)
    for i,(y,m,d) in enumerate(zip(yp,mp,dp)):
        y,m,d=str(y),str(m),str(d);dm[i]=STEMS.index(d[0])
        for target in [y[0],m[0],MAIN[y[1]],MAIN[m[1]],MAIN[d[1]]]: gods[i,TG[d[0]][target]]+=1
    x=np.column_stack([gods[:,8],gods[:,3],(gods[:,7]>0)&(gods[:,9]>0),(gods[:,3]>0)&(gods[:,9]>0),dm>=8,dm]).astype(np.int64)
    broad=np.column_stack([((gods[:,6]+gods[:,7])>0)&((gods[:,8]+gods[:,9])>0),(gods[:,3]>0)&((gods[:,8]+gods[:,9])>0)]).astype(np.int64)
    return x,gods,broad


def exact_upper(pmfs,observed):
    p=np.array([1.])
    for v in pmfs: p=np.convolve(p,v)
    require(abs(float(p.sum())-1)<1e-9 and np.all(p>=0),'Exact QA convolution mass')
    p/=p.sum()
    return float(p[observed:].sum())


def synthetic_qa():
    require(all(sorted(r.values())==list(range(10)) for r in TG.values()),'Literal TenGod bijection')
    close(exact_upper([np.array([.5,.5]),np.array([2/3,1/3])],2),1/6,'Exact upper example',atol=1e-15)
    close(exact_upper([np.array([.5,.5]),np.array([2/3,1/3])],1),2/3,'Exact inclusive example',atol=1e-15)
    return {'schema':'UK_country_audit_synthetic_v1','status':'PASS','study_data_loaded':False,**original_functions_unchanged(),'exact_upper_inclusive_toy':True}


def read_rows(z,rel):
    return [json.loads(line) for line in gzip.decompress(z.read('scientist_north_data_freeze_v4/'+rel)).splitlines()]


def main(args):
    if args.synthetic_qa_only:
        print(json.dumps(synthetic_qa(),ensure_ascii=False,indent=2));return
    receipt=json.loads(Path(args.execution_receipt).read_text());scope=json.loads(Path(args.scope).read_text())
    require(receipt['country']==scope['country']=='UK_Royal_Society','UK-only gate')
    require(receipt['remote_plan_and_code_verified_before_summary'] is True,'Remote execution lock missing')
    require(receipt['scope_sha256']==sha(args.scope) and receipt['locked_file_manifest_sha256']==sha(args.locked_files),'Lock hashes differ')
    for rel,digest in json.loads(Path(args.locked_files).read_text()).items(): require(sha(ROOT/rel)==digest,'Locked file changed:'+rel)
    for key in PINS: require(sha(getattr(args,key))==PINS[key],'Pinned input changed:'+key)
    result=json.loads(Path(args.results).read_text())
    require(result['schema']=='scientist_UK_Royal_Society_country_reveal_v1' and result['country']=='UK_Royal_Society','Unexpected country result')
    require(result['execution_lock_receipt']==receipt,'Result execution receipt differs')
    require(result['primary_n']==result['expanded_sensitivity_n']==2293,'UK population size differs')
    require(result['hashes']['engine_sha256']==sha(ENGINE) and result['hashes']['receipt_sha256']==sha(args.execution_receipt),'Engine/receipt hash differs')
    astcheck=original_functions_unchanged()
    with zipfile.ZipFile(args.v4_zip) as z:
        selections={};people={};fields={};inclusive={}
        for q in ['strict','expanded']:
            uk=read_rows(z,'outputs/'+q+'/by_institution/UK_Royal_Society.jsonl.gz');inclusive[q]=len(uk)
            nn={r['person_id'] for r in read_rows(z,'outputs/'+q+'/academy_excluding_official_Nobel.jsonl.gz')}
            selections[q]={r['person_id'] for r in uk}&nn
            people[q]={r['person_id']:r for r in uk if r['person_id'] in selections[q]}
            fields[q]={r['person_id'] for r in read_rows(z,'outputs/'+q+'/Fields_parallel_cohort.jsonl.gz')}
        withoutloc={r['person_id'] for r in read_rows(z,'outputs/sensitivity/expanded_without_LOC_quoted_metadata_people.jsonl.gz')}
    require(selections['strict']==selections['expanded'] and len(selections['strict'])==2293,'UK selected IDs differ')
    require(ids_hash(selections['strict'])==ID_SHA,'UK canonical ID hash differs')
    require(inclusive=={'strict':2371,'expanded':2371} and result['all_UK_counts_only_no_feature_reveal']==inclusive,'Inclusive metadata differs')
    for pid in selections['strict']:
        p=people['expanded'][pid]
        require(p['analysis_DOB']==people['strict'][pid]['analysis_DOB'],'Strict/expanded DOB differs')
        require(p['hemisphere']=='north' and not p['person_level_DOB_analysis_hold'],'Hemisphere/hold changed')
    with np.load(args.calendar_npz,allow_pickle=False) as z: pool={k:z[k] for k in z.files}
    x,gods,broad=literal(pool['year_pillar'],pool['month_pillar'],pool['day_pillar'])
    require(np.array_equal(x,pool['features']) and np.array_equal(gods,pool['ten_god_counts']),'Literal full calendar differs from carrier')
    require(np.array_equal(broad[:,0],pool['GY_broad']) and np.array_equal(broad[:,1],pool['SGY_broad']),'Literal broad cache differs')
    ix={str(d):i for i,d in enumerate(pool['dates'])};source=people['expanded']
    selections_by_case={'strict_primary':selections['strict'],'expanded':selections['expanded'],'strict_broad':selections['strict'],
      'strict_noJie':{pid for pid in selections['strict'] if not pool['jie_boundary_plus_minus_one_civil_day'][ix[source[pid]['analysis_DOB']]]},
      'strict_yearMonth':selections['strict'],'expanded_withoutLOC':selections['expanded']&withoutloc,'strict_withoutFields':selections['strict']-fields['strict']}
    require(len(selections_by_case['strict_withoutFields'])==2288,'Fields sensitivity size differs')
    require([c['case'] for c in result['cases']]==CASES,'Seven case order differs')
    reports=[]
    for ci,c in enumerate(result['cases']):
        name=c['case'];selected=sorted(selections_by_case[name]);indexes=np.array([ix[source[pid]['analysis_DOB']] for pid in selected]);n=len(selected)
        values=x[indexes].copy();month=name=='strict_yearMonth';nojie=name=='strict_noJie';wide=name=='strict_broad'
        if wide:values[:,2:4]=broad[indexes]
        require(c['n']==c['unique_person_count']==n and c['person_ids_sha256']==ids_hash(selected),'Case N/IDs differ')
        require(c['case_index']==ci and c['calendar_condition']==('year_and_month' if month else 'year'),'Case conditioning differs')
        require(c['observed_and_calendar_Jie_pm1_excluded'] is nojie and c['cooccurrence_encoding']==('broad' if wide else 'narrow'),'Case sensitivity flags differ')
        expected=[];expected_dm=[];expected_gods=[];pmf_cache={};keys=[]
        for rowindex in indexes:
            key=(int(pool['year'][rowindex]),int(pool['month'][rowindex]) if month else 0);keys.append(key)
            if key not in pmf_cache:
                mask=pool['year']==key[0]
                if month:mask &= pool['month']==key[1]
                if nojie:mask &= ~pool['jie_boundary_plus_minus_one_civil_day'].astype(bool)
                v=x[mask].copy()
                if wide:v[:,2:4]=broad[mask]
                pmf_cache[key]={'E':v[:,:5].mean(axis=0),'DM':np.bincount(v[:,5],minlength=10)/len(v),'TG':gods[mask].mean(axis=0),
                  'pmfs':[np.bincount(v[:,j],minlength=(6 if j<2 else 2))/len(v) for j in range(5)]}
            expected.append(pmf_cache[key]['E']);expected_dm.append(pmf_cache[key]['DM']);expected_gods.append(pmf_cache[key]['TG'])
        expected=np.asarray(expected);expected_dm=np.asarray(expected_dm).sum(axis=0);expected_gods=np.asarray(expected_gods).mean(axis=0)
        require(c['metric_order']==METRICS and len(c['scalar_metrics'])==5,'Metric order differs')
        for j,item in enumerate(c['scalar_metrics']):
            require(item['metric']==METRICS[j] and item['observed_sum']==int(values[:,j].sum()),'Observed scalar differs')
            close(item['observed_mean_or_rate'],values[:,j].mean(),'Observed scalar mean differs');close(item['calendar_expected_mean_or_rate'],expected[:,j].mean(),'Scalar expectation differs')
            close(item['observed_minus_expected'],(values[:,j]-expected[:,j]).mean(),'Scalar excess differs')
            for label in ['raw_mean_or_rate_unadjusted_95CI','paired_excess_unadjusted_95CI']:
                a=np.asarray(item[label]);bound=5 if j<2 else 1;low=0 if label.startswith('raw') else -bound
                require(a.shape==(2,) and np.isfinite(a).all() and low-1e-12<=a[0]<=a[1]<=bound+1e-12,'CI shape/range differs')
        for j,item in enumerate(c['ten_gods_five_position_descriptive_only']):
            require(item['ten_god']==GODS[j] and item['observed_count_sum']==int(gods[indexes,j].sum()),'God count differs')
            close(item['calendar_expected_count_mean_per_person'],expected_gods[j],'God E differs')
        dmcounts=np.bincount(values[:,5],minlength=10)
        for j,item in enumerate(c['day_master_distribution']):
            require(item['stem']==STEMS[j] and item['observed_people']==int(dmcounts[j]),'DM count differs');close(item['calendar_expected_people'],expected_dm[j],'DM E differs')
        close(sum(expected_dm),n,'Expected DM total differs')
        checks=[];primary=ci==0
        for j,test in enumerate(c['calendar_MC_tests']):
            require(test['metric']==METRICS[j] and test['seed']==2026111400+j and test['replicates']==99999 and test['generator']=='PCG64','MC method differs')
            extreme=test['extreme_replicates_including_ties'];require(isinstance(extreme,int) and 0<=extreme<=99999,'MC extreme count invalid')
            p=(extreme+1)/100000;close(test['p_nominal_plus_one'],p,'MC plusone differs',atol=1e-15);close(test['p_Bonferroni_36_reference'],min(1,36*p),'Bonf36 differs',atol=1e-15)
            require(test['FWER_family_size']==36 and test['secondary_country_family_primary_member'] is primary,'Family differs')
            require(test['primary_Bonferroni_36_reject_0_05']==(min(1,36*p)<=.05 if primary else None) and test['sensitivity_does_not_rescue_primary'] is (not primary),'Primary/sensitivity rejection semantics differ')
            if j<5:
                observed=int(values[:,j].sum());require(test['observed_integer_sum']==observed and test['tail']=='upper_inclusive_integer_sum','Scalar upper tail differs')
                if primary and j in EXACT_PRIMARY_CHECKS:
                    exact=exact_upper([pmf_cache[k]['pmfs'][j] for k in keys],observed);tol=5*math.sqrt(exact*(1-exact)/99999)+2/99999
                    require(abs(p-exact)<=tol,'Primary MC differs from exact QA beyond frozen tolerance')
                    checks.append({'metric':METRICS[j],'reported_MC_p':p,'independent_exact_upper_QA_p':exact,'tolerance':tol,'does_not_replace_reported_p':True})
            else:
                statistic=float(np.sum((dmcounts-expected_dm)**2/expected_dm));close(test['observed_Pearson_distance'],statistic,'DM Pearson differs')
                require(test['tail']=='upper_inclusive_distance','DM tail differs');close(test['floating_point_tie_tolerance'],1e-12*max(1,abs(statistic)),'DM tie tolerance differs',atol=1e-24)
        boot=c['bootstrap'];require(boot['seed']==202611150100+ci and boot['replicates']==10000 and boot['quantile_method']=='linear' and boot['multiple_comparison_adjusted'] is False,'Bootstrap settings differ')
        require(c['global_confirmatory_18_Holm_family_tested'] is False,'Global18 unexpectedly tested')
        reports.append({'case':name,'n':n,'person_ids_sha256':c['person_ids_sha256'],'all_observed_and_expectations_recomputed':True,'MC_plusone_Bonf36_seeds_checked':True,'primary_exact_tail_crosschecks':checks})
    report={'schema':'UK_country_independent_QA_v1','status':'PASS','country':'UK_Royal_Society','execution_lock_commit':receipt['commit'],**astcheck,
      'literal_calendar_rows_checked':len(x),'all_six_narrow_and_broad_calendar_carrier_features_match':True,'cases':reports,
      'only_UK_nonNobel_outcomes_aggregated':True,'original18_and_country36_unchanged':True,'exact_QA_does_not_replace_locked_MC_p':True,
      'bootstrap_QA_scope':'unchanged_AST_and_metadata_plus_valid_interval_shapes_bounds;not_full_replay',
      'DM_QA_scope':'observed_expected_counts_Pearson_and_reported_MC_formula;no_exact_multivariate_tail_claim',
      'hashes':{'results':sha(args.results),'auditor':sha(__file__),'analysis_engine':sha(ENGINE),'execution_receipt':sha(args.execution_receipt),**PINS}}
    output=Path(args.output);require(not output.exists(),'No QA overwrite');output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'status':'PASS','cases_checked':len(reports),'primary_people':2293,'output':str(output)},ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--synthetic-qa-only',action='store_true')
    for key in ['v4-zip','calendar-npz','scope','locked-files','execution-receipt','results','output']:p.add_argument('--'+key)
    main(p.parse_args())
