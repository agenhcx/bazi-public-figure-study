#!/usr/bin/env python3
"""Independent postreveal QA; does not import or alter the locked engine."""
from pathlib import Path
import json, gzip, zipfile, hashlib, datetime as dt
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
work = ROOT / 'fields_reveal_v1'
result_path = work / 'RESULTS.json'
result_bytes_before = result_path.read_bytes()
result = json.loads(result_bytes_before)
receipt = json.loads((work/'REMOTE_LOCK_RECEIPT.json').read_text())
calendar = ROOT/'fields_restore_v1/methods/scientist_US_NAS_reveal_v1/calendar_pool.npz'
hidden_path = ROOT/'fields_restore_v1/methods/scientist_US_NAS_reveal_v2_hidden_stems/hidden_pool.npz'
v4 = ROOT/'hypothesis_inputs_v1/scientist_north_data_freeze_v4.zip'
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def require(v,m):
    if not bool(v): raise AssertionError(m)
checks = {}
require(receipt['remote_lock_verified'] is True,'remote lock')
require(receipt['commit']=='76a8abbd73f05155b00f43a173d3736e8c716629','commit')
require(sha(work/'analyze_fields.py')==receipt['code_sha256']==result['source_sha256']['code'],'code')
require(sha(v4)==result['source_sha256']['V4'],'V4 SHA')
require(sha(calendar)==result['source_sha256']['calendar'],'calendar SHA')
require(sha(hidden_path)==result['source_sha256']['hidden'],'hidden SHA')
for name,digest in receipt['verified_files_sha256'].items():
    p=ROOT/name
    if not p.exists(): p=work/Path(name).name
    require(sha(p)==digest,'locked file changed '+name)
checks['locked_files_and_inputs_unchanged']=True
with np.load(calendar,allow_pickle=False) as f: C={k:f[k].copy() for k in f.files}
with np.load(hidden_path,allow_pickle=False) as f: H={k:f[k].copy() for k in f.files}
STEMS='甲乙丙丁戊己庚辛壬癸'
GODS=['比肩','劫财','食神','伤官','偏财','正财','七杀','正官','偏印','正印']
HS={'子':'癸','丑':'己癸辛','寅':'甲丙戊','卯':'乙','辰':'戊乙癸','巳':'丙戊庚','午':'丁己','未':'己丁乙','申':'庚壬戊','酉':'辛','戌':'戊辛丁','亥':'壬甲'}
def god(dm,target):
    d=STEMS.index(dm); t=STEMS.index(target)
    rel=((t//2)-(d//2))%5
    return {0:0,1:2,2:4,3:6,4:8}[rel]+int((d-t)%2!=0)
allcats={'M0':[],'M1':[]}; allcounts={'M0':[],'M1':[]}
for yp,mp,dp in zip(C['year_pillar'],C['month_pillar'],C['day_pillar']):
    visible={yp[0],mp[0]}; day=dp[0]
    for model in allcats:
        def branch(b):
            stems=HS[b]
            exposed=[s for s in stems if s in visible]
            return exposed[0] if model=='M1' and exposed else stems[0]
        seq=[yp[0],branch(yp[1]),mp[0],branch(mp[1]),branch(dp[1])]
        cats=[god(day,t) for t in seq]
        allcats[model].append(cats);allcounts[model].append(np.bincount(cats,minlength=10))
for model in allcats:
    allcats[model]=np.array(allcats[model],dtype=np.int8)
    allcounts[model]=np.array(allcounts[model],dtype=np.int16)
require(np.array_equal(allcounts['M0'],C['ten_god_counts']),'independent M0 universe')
require(np.array_equal(allcounts['M1'][:,8]*72,H['count_scaled72'][:,1,0]),'independent M1 PI universe')
require(np.array_equal(allcounts['M1'][:,3]*72,H['count_scaled72'][:,1,1]),'independent M1 SG universe')
checks['independent_full_universe_reconstruction']=True
def read_rows(z,sub):
    return [json.loads(l) for l in gzip.decompress(z.read('scientist_north_data_freeze_v4/'+sub)).splitlines()]
with zipfile.ZipFile(v4) as z:
    strict=read_rows(z,'outputs/strict/Fields_parallel_cohort.jsonl.gz')
    expanded=read_rows(z,'outputs/expanded/Fields_parallel_cohort.jsonl.gz')
    academy={r['person_id'] for r in read_rows(z,'outputs/strict/academy_excluding_official_Nobel.jsonl.gz')}
    nobel={r['person_id'] for r in read_rows(z,'outputs/strict/Nobel_full_roster_matched_people.jsonl.gz')}
rows=sorted(strict,key=lambda r:r['person_id'])
require(rows==sorted(expanded,key=lambda r:r['person_id']),'strict equals expanded')
require(len(rows)==len({r['person_id'] for r in rows})==57,'N')
require(not ({r['person_id'] for r in rows}&nobel),'Nobel disjoint')
require(all(r['hemisphere']=='north' and not r['person_level_DOB_analysis_hold'] for r in rows),'geography/hold')
checks['frozen_cohort_N57_unique_north_strict_equals_expanded']=True
checks['Fields_and_Nobel_disjoint']=True
lookup={str(d):i for i,d in enumerate(C['dates'])}
idx=np.array([lookup[r['analysis_DOB']] for r in rows])
overlap=np.array([r['person_id'] in academy for r in rows])
require(int(overlap.sum())==18,'academy overlap')
require(len(idx[~overlap])==39,'nonoverlap N39')
order=['overall_PI','overall_SG','year_PI','year_SG','month_PI','month_SG']
V={}
for model in allcats:
    c=allcats[model];count=allcounts[model]
    V[model]=np.column_stack([count[:,8],count[:,3],(c[:,:2]==8).any(1),(c[:,:2]==3).any(1),(c[:,2:4]==8).any(1),(c[:,2:4]==3).any(1)]).astype(np.int16)
def pools(indexes,ym=False):
    return [np.flatnonzero((C['year']==C['year'][i])&((C['month']==C['month'][i]) if ym else True)) for i in indexes]
P=pools(idx)
def compare_endpoint_rows(values,indexes,poolset,actual,label):
    obs=values[indexes].sum(0);exp=sum(values[p].mean(0) for p in poolset)
    require([r['endpoint'] for r in actual]==order,label+' endpoints')
    require(all(r['N']==len(indexes) for r in actual),label+' N')
    for j,r in enumerate(actual):
        den=(5 if j<2 else 1)*len(indexes)
        require(r['observed_sum']==int(obs[j]),label+' observed')
        require(abs(r['expected_sum']-exp[j])<1e-10,label+' expected')
        require(r['reporting_denominator']==den,label+' denominator')
        require(abs(r['observed_fraction']-obs[j]/den)<1e-12,label+' observed fraction')
        require(abs(r['expected_fraction']-exp[j]/den)<1e-12,label+' expected fraction')
        require(abs(r['observed_per_person']-obs[j]/len(indexes))<1e-12,label+' mean')
        require(abs(r['difference_percentage_points']-100*(obs[j]-exp[j])/den)<1e-10,label+' pp')
    return obs,exp
obs,exp=compare_endpoint_rows(V['M0'],idx,P,result['primary'],'primary')
compare_endpoint_rows(V['M1'],idx,P,result['sensitivities']['M1_priority_5'],'M1')
compare_endpoint_rows(V['M0'],idx,pools(idx,True),result['sensitivities']['M0_birth_year_and_month_null'],'yearMonth')
keep=~C['jie_boundary_plus_minus_one_civil_day'][idx].astype(bool)
compare_endpoint_rows(V['M0'],idx[keep],pools(idx[keep]),result['sensitivities']['M0_noJie_plus_minus_one_day'],'noJie')
compare_endpoint_rows(V['M0'],idx[~overlap],pools(idx[~overlap]),result['sensitivities']['M0_without_prior_academy_overlap'],'noOverlap')
checks['all_six_observed_expected_denominators_and_sensitivities']=True
def holm(p):
    ranking=np.argsort(p,kind='stable');adj=np.empty(len(p));current=0.
    for rank,i in enumerate(ranking):
        current=max(current,(len(p)-rank)*p[i]);adj[i]=min(1.,current)
    return adj
primary_p=np.array([r['raw_p_one_sided'] for r in result['primary']])
require(np.allclose(holm(primary_p),[r['holm6_p'] for r in result['primary']],atol=1e-14,rtol=0),'Holm')
require(result['primary_family_size']==6 and result['sensitivity_extra_p_values']==0,'family')
checks['Holm6_exact_and_no_extra_sensitivity_p']=True
rng=np.random.default_rng(2026111599);R=19999
sums=np.zeros((R,6),dtype=np.int16)
for p in P:
    birthdays=rng.choice(p,size=R,replace=True)
    sums+=V['M0'][birthdays]
fresh_p=(np.count_nonzero(sums>=obs,axis=0)+1)/(R+1)
mc=[]
for j,name in enumerate(order):
    p=float(primary_p[j]);q=float(fresh_p[j])
    combined=float(np.sqrt(p*(1-p)/(result['R']+1)+q*(1-q)/(R+1)))
    bound=6*combined+.002
    require(abs(p-q)<bound,'fresh MC '+name)
    # Exact finite-year convolution is a numerical audit of these same endpoints.
    pmf=np.array([1.])
    for pool in P:
        v=V['M0'][pool,j]
        per=np.bincount(v,minlength=int(v.max())+1)/len(pool)
        pmf=np.convolve(pmf,per)
    exact=float(pmf[int(obs[j]):].sum())
    se=float(np.sqrt(p*(1-p)/(result['R']+1)))
    require(abs(exact-p)<6*se+.002,'MC vs exact DP '+name)
    mc.append({'endpoint':name,'locked_raw_p':p,'fresh_raw_p':q,'absolute_difference':abs(p-q),'allowed_bound_6combinedSE_plus_0_002':bound,'exact_finite_calendar_tail_QA_only':exact})
checks['fresh_joint_MC_19999_all_six_pass']=True
checks['same_endpoint_exact_finite_calendar_convolution_QA_pass']=True
for model in ['M0','M1']:
    a=result['descriptives'][model+'_all10_TG']
    o=allcounts[model][idx].sum(0);e=sum(allcounts[model][p].mean(0) for p in P)
    require([r['label'] for r in a]==GODS,'TG labels')
    for j,r in enumerate(a):
        require(abs(r['observed_sum']-o[j])<1e-12 and abs(r['expected_sum']-e[j])<1e-10,'TG counts '+model)
        require(abs(r['observed_fraction']-o[j]/(5*57))<1e-12 and abs(r['expected_fraction']-e[j]/(5*57))<1e-12,'TG shares '+model)
ds=np.array([STEMS.index(str(x)[0]) for x in C['day_pillar']])
dm=np.eye(10)[ds];do=dm[idx].sum(0);de=sum(dm[p].mean(0) for p in P)
for j,r in enumerate(result['descriptives']['day_master']):
    require(r['label']==STEMS[j] and r['observed_sum']==do[j] and abs(r['expected_sum']-de[j])<1e-10,'DM counts')
checks['all10_TG_M0_M1_and_DM10_descriptives_exact']=True
hidden_rows=result['descriptives']['hidden_models']
require(len(hidden_rows)==16,'8 models x2 traits')
for mi,m in enumerate(H['models']):
    for ti,t in enumerate(H['traits']):
        actual=next(r for r in hidden_rows if r['model']==str(m) and r['trait']==str(t))
        count=H['count_scaled72'][:,mi,ti]/72.
        presence=H['presence_scaled12'][:,mi,ti]/12.
        ec=sum(count[p].mean() for p in P)/57
        ep=sum(presence[p].mean() for p in P)/57
        den=int(H['position_denominators'][mi])
        want={'position_denominator':den,'observed_count_mean':float(count[idx].mean()),'expected_count_mean':float(ec),'observed_position_share':float(count[idx].mean()/den),'expected_position_share':float(ec/den),'observed_person_presence':float(presence[idx].mean()),'expected_person_presence':float(ep)}
        for k,v in want.items(): require(abs(actual[k]-v)<1e-12,'hidden '+str(m)+' '+str(t)+' '+k)
checks['all_8_hidden_models_2_traits_counts_presence_and_denominators']=True
audit=json.loads((work/'INDIVIDUAL_AUDIT.json').read_text())
require(len(audit)==57,'individual audit N')
for r,i,a in zip(rows,idx,audit):
    require(a['person_id']==r['person_id'] and a['DOB']==r['analysis_DOB'],'audit identity')
    for key in ['year_pillar','month_pillar','day_pillar']:require(a[key]==str(C[key][i]),'audit pillars')
    require(a['M0_categories']==[GODS[x] for x in allcats['M0'][i]],'audit M0')
    require(a['M1_categories']==[GODS[x] for x in allcats['M1'][i]],'audit M1')
    require(a['M0_endpoints']==V['M0'][i].tolist(),'audit endpoints')
checks['individual_chart_audit_all57_exact']=True
require(result_path.read_bytes()==result_bytes_before,'results altered by audit')
out={'schema':'Fields_postreveal_independent_QA_v1','status':'PASS','created_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'remote_lock_commit':receipt['commit'],'N':57,'strict_equals_expanded':True,'noJie_retained_N':int(keep.sum()),'prior_academy_overlap_N':18,'without_prior_academy_N':39,'fresh_MC_R':R,'fresh_MC_seed':2026111599,'checks':checks,'primary_recomputed':[{ 'endpoint':name,'observed_sum':int(obs[j]),'expected_sum':float(exp[j]),'holm6_p':float(holm(primary_p)[j])} for j,name in enumerate(order)],'fresh_MC_comparisons':mc,'locked_code_SHA256':sha(work/'analyze_fields.py'),'result_SHA256':sha(result_path),'auditor_code_SHA256':sha(__file__),'no_locked_files_modified':True,'new_endpoints_or_hypotheses_added':False,'exact_tail_role':'QA reference only for same six endpoints; does not replace locked 99999-replicate p-values.','blockers':[]}
(work/'POSTREVEAL_INDEPENDENT_QA.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'status':'PASS','noJie_N':int(keep.sum()),'without_prior_academy_N':39,'postreveal_QA':str(work/'POSTREVEAL_INDEPENDENT_QA.json'),'MC_comparison':mc},ensure_ascii=False,indent=2))

