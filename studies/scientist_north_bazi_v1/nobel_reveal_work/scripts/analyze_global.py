#!/usr/bin/env python3
"""Execution-gated implementation of the original scientist global18 family.

No real-data outcomes are read during import or synthetic QA. Calendar marginal
histogram simulations and category-collapsed label permutations are exactly
distribution-equivalent to whole-person sampling for the individual endpoint.
Independent endpoint RNG streams preclude joint-vector null interpretations.
"""
import argparse
from collections import Counter,defaultdict
import copy
import datetime as dt
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import time
import zipfile
import numpy as np

WORK=Path(__file__).resolve().parents[1]
V4_SHA='53302ef5c4bbb946adcaceb70d7a7fd576c7f06d03c3e7080874654e1a2644f9'
POOL_SHA='d150883033464ebd3afafaf764738ed3b573d0d0fb4bd252a955e403a75fcc8b'
COUNTRIES=['NAS','UK_Royal_Society','DE_Leopoldina','France','Japan','CAS']
STEMS=list('甲乙丙丁戊己庚辛壬癸')
GODS=['比肩','劫财','食神','伤官','偏财','正财','七杀','正官','偏印','正印']
METRICS=['PI_count','SG_count','GY','SGY','water_DM']
IDS=['H1a_PI','H1a_SG','H1b_PI','H1b_SG','H1c_PI','H1c_SG','H2a','H2b','H2c','H2d','H3a','H3b','H4_PI','H4_SG','H4_GY','H4_SGY','H4_DM10','H4_WATER']
CASES=['strict_primary','expanded','strict_broad','strict_noJie','strict_yearMonth','expanded_withoutLOC','strict_withoutFields']
R=99999;B=10000


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def canonical(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n'
def require(c,m):
 if not c:raise ValueError(m)
def idhash(rows):return hashlib.sha256(canonical(sorted(r['person_id'] for r in rows)).encode()).hexdigest()
def safe(x):
 if isinstance(x,np.ndarray):return x.tolist()
 if isinstance(x,np.generic):return x.item()
 if isinstance(x,dict):return {str(k):safe(v) for k,v in x.items()}
 if isinstance(x,(tuple,list)):return [safe(v) for v in x]
 return x

def base_module():
 p=WORK/'original/reveal_v1/scripts/analyze_country.py';s=importlib.util.spec_from_file_location('_global_original_country',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m


def verify_gate(args):
 receipt=json.loads(Path(args.execution_receipt).read_text());scope=json.loads(Path(args.scope).read_text());manifest=json.loads(Path(args.locked_files).read_text())
 require(receipt.get('remote_plan_and_code_verified_before_summary') is True or receipt.get('remote_Git_lock_verified_before_inference') is True,'Remote execution lock missing')
 require(bool(re.fullmatch('[0-9a-f]{40}',receipt.get('commit',receipt.get('lock_commit_sha','')))),'Commit SHA missing')
 require(receipt.get('scope_sha256')==sha(args.scope),'Scope changed')
 require(receipt.get('locked_file_manifest_sha256')==sha(args.locked_files),'Manifest changed')
 for p,h in manifest.items():require(sha(p)==h,'Locked file changed: '+p)
 require(str(Path(__file__).resolve().relative_to(Path.cwd())) in manifest or str(Path(__file__).resolve()) in manifest,'Engine not locked')
 require(scope.get('global18_authorized',False) is True,'Global18 not authorized')
 require(sha(args.v4_zip)==V4_SHA and sha(args.calendar_npz)==POOL_SHA,'Input pin mismatch')
 return receipt,scope


def load_data(v4,poolpath):
 m=base_module();pool=m.load_pool(poolpath);idx={d:i for i,d in enumerate(pool['dates'].tolist())};pre='scientist_north_data_freeze_v4/outputs/'
 with zipfile.ZipFile(v4) as z:
  def get(n):return [json.loads(l) for l in gzip.decompress(z.read(pre+n)).splitlines()]
  inputs={}
  for quality in ['strict','expanded']:
   n=get(quality+'/Nobel_full_roster_matched_people.jsonl.gz');a=get(quality+'/academy_excluding_official_Nobel.jsonl.gz')
   memberships={c:{r['person_id'] for r in get(quality+'/by_institution/'+c+'.jsonl.gz')} for c in COUNTRIES}
   for p in n+a:
    p['_pool_idx']=idx[p['analysis_DOB']]
    p['_memberships']=[c for c in COUNTRIES if p['person_id'] in memberships[c]]
    supp=[s for s in p['DOB_support'][quality] if s['analysis_date_coordinate']==p['analysis_DOB']]
    grades={s.get('DOB_source_grade') for s in supp}
    p['_source_class']='S1' if 'S1' in grades else 'S2' if 'S2' in grades else 'S1_or_S2_union' if p['included_strict'] else 'S3_only'
    if p['_source_class']=='S1_or_S2_union':require(any(set(s.get('possible_DOB_source_grades',[]))<=set(['S1','S2']) and s.get('possible_DOB_source_grades') for s in supp),'Strict union support not bound')
   inputs[quality]={'Nobel':sorted(n,key=lambda r:r['person_id']),'academy':sorted(a,key=lambda r:r['person_id'])}
  loc={r['person_id'] for r in get('sensitivity/expanded_without_LOC_quoted_metadata_people.jsonl.gz')}
  nofields={r['person_id'] for r in get('strict/academy_excluding_official_Nobel_and_Fields.jsonl.gz')}
 require([len(inputs[q][g]) for q in ['strict','expanded'] for g in ['Nobel','academy']]==[621,5234,627,5871],'Locked population sizes changed')
 for q in inputs:
  require(not {r['person_id'] for r in inputs[q]['Nobel']} & {r['person_id'] for r in inputs[q]['academy']},'Award/control overlap')
  require(all(r['_memberships'] for r in inputs[q]['academy']),'Academy without qualified membership')
 return pool,inputs,loc,nofields


def case_rows(case,inputs,pool,loc,nofields):
 q='expanded' if case in ['expanded','expanded_withoutLOC'] else 'strict';n=inputs[q]['Nobel'];a=inputs[q]['academy']
 if case=='strict_noJie':
  n=[r for r in n if not bool(pool['jie_boundary_plus_minus_one_civil_day'][r['_pool_idx']])];a=[r for r in a if not bool(pool['jie_boundary_plus_minus_one_civil_day'][r['_pool_idx']])]
 if case=='expanded_withoutLOC':n=[r for r in n if r['person_id'] in loc];a=[r for r in a if r['person_id'] in loc]
 if case=='strict_withoutFields':a=[r for r in a if r['person_id'] in nofields]
 return {'Nobel':n,'academy':a,'union':sorted(n+a,key=lambda r:r['person_id'])},q


def arrays(rows,pool,broad=False):
 ids=np.asarray([r['_pool_idx'] for r in rows]);x=pool['features'][ids].astype(np.int64).copy()
 if broad:x[:,2]=pool['GY_broad'][ids];x[:,3]=pool['SGY_broad'][ids]
 return x,pool['ten_god_counts'][ids].astype(np.int64)


def member_weights(rows):
 w=np.zeros((len(rows),6))
 for i,r in enumerate(rows):
  cs=r['_memberships'];require(bool(cs),'Missing institution vector')
  for c in cs:w[i,COUNTRIES.index(c)]=1/len(cs)
 require(np.allclose(w.sum(axis=1),1,atol=1e-15),'Weights not fractional unit rows')
 return w


def describe(rows,x,gods,e,edm,egods):
 n=len(rows);scalar=[]
 for j,name in enumerate(METRICS):
  obs=float(x[:,j].mean());exp=float(e[:,j].mean())
  scalar.append({'metric':name,'observed_sum':int(x[:,j].sum()),'observed_mean_or_rate':obs,'calendar_expected_mean_or_rate':exp,'observed_minus_expected':obs-exp,'unit':'count_per_person_of_five_positions' if j<2 else 'fraction_of_people'})
 return {'n':n,'person_ids_sha256':idhash(rows),'birthyear_min':min(r['analysis_DOB'][:4] for r in rows),'birthyear_max':max(r['analysis_DOB'][:4] for r in rows),'scalar_metrics':scalar,
 'ten_gods':[{'ten_god':g,'observed_count_sum':int(gods[:,j].sum()),'observed_count_mean_per_person':float(gods[:,j].mean()),'calendar_expected_count_mean_per_person':float(egods[:,j].mean()),'observed_share_of_five_positions':float(gods[:,j].mean()/5),'calendar_expected_share_of_five_positions':float(egods[:,j].mean()/5),'excess_count_mean_per_person':float((gods[:,j]-egods[:,j]).mean())} for j,g in enumerate(GODS)],
 'day_master_distribution':[{'stem':s,'observed_people':int(np.sum(x[:,5]==j)),'calendar_expected_people':float(edm[:,j].sum()),'observed_fraction':float(np.mean(x[:,5]==j)),'calendar_expected_fraction':float(edm[:,j].mean())} for j,s in enumerate(STEMS)]}


def mc_calendar(rows,x,edm,model,index,metric):
 rng=np.random.Generator(np.random.PCG64(20261113+index));strata=Counter(model.key(r) for r in rows);n=len(rows)
 if metric=='DM10':
  expected=edm.sum(axis=0);obs=np.bincount(x[:,5],minlength=10);stat=float(np.sum((obs-expected)**2/expected));sim=np.zeros((R,10),dtype=np.int64)
  for key,count in sorted(strata.items()):sim+=rng.multinomial(count,model.lookup[key]['DM'],size=R)
  vals=np.sum((sim-expected)**2/expected,axis=1);tol=1e-12*max(1,abs(stat));ext=int(np.count_nonzero(vals>=stat-tol));diag={'observed_counts':obs,'expected_counts':expected,'floating_inclusive_tolerance':tol}
 else:
  j=metric;obs=int(x[:,j].sum());sim=np.zeros(R,dtype=np.int64);expected_sum=0.
  for key,count in sorted(strata.items()):
   pmf=model.lookup[key]['pmfs'][j];expected_sum+=count*float(model.lookup[key]['E'][j])
   sim+=rng.multinomial(count,pmf,size=R)@np.arange(6,dtype=np.int64) if j<2 else rng.binomial(count,float(pmf[1]),size=R)
  ext=int(np.count_nonzero(sim>=obs));stat=(obs-expected_sum)/n;diag={'observed_integer_sum':obs,'expected_sum':expected_sum,'inclusive_integer_tail':True}
 return stat,ext,diag


def direct_inputs(nrows,arows,nx,ax,j,direction):
 nd=np.asarray([int(r['analysis_DOB'][:4])//10*10 for r in nrows]);ad=np.asarray([int(r['analysis_DOB'][:4])//10*10 for r in arows]);common=sorted(set(nd)&set(ad));total=sum(int(np.sum(nd==d)+np.sum(ad==d)) for d in common)
 info=[];stat=0.
 for d in common:
  yn=nx[nd==d,j];ya=ax[ad==d,j];w=(len(yn)+len(ya))/total;stat+=direction*w*(yn.mean()-ya.mean());info.append((d,w,yn,ya))
 raw=direction*(nx[:,j].mean()-ax[:,j].mean())
 return float(stat),float(raw),info


def mc_direct(nrows,arows,nx,ax,index,j,direction):
 stat,raw,info=direct_inputs(nrows,arows,nx,ax,j,direction);rng=np.random.Generator(np.random.PCG64(20261113+index));sim=np.zeros(R)
 for d,w,yn,ya in info:
  allvalues=np.r_[yn,ya];hist=np.bincount(allvalues,minlength=6 if j<2 else 2);values=np.arange(len(hist));selected=rng.multivariate_hypergeometric(hist,len(yn),size=R,method='marginals')@values
  sim+=direction*w*(selected/len(yn)-(allvalues.sum()-selected)/len(ya))
 tol=1e-12*max(1,abs(stat));ext=int(np.count_nonzero(sim>=stat-tol));diag={'common_decades':[v[0] for v in info],'pooled_decade_weights':[v[1] for v in info],'raw_whole_group_contrast_in_predicted_direction':raw,'raw_direction_gate':raw>0,'floating_inclusive_tolerance':tol,'method':'within_birthdecade_person_labels_equivalent_multivariate_hypergeometric_endpoint_histograms'}
 return stat,ext,diag,raw


def trend_design(rows):
 w=member_weights(rows);year=np.asarray([int(r['analysis_DOB'][:4]) for r in rows]);return np.column_stack([np.ones(len(rows)),(year-1900)/10,w[:,:5]])


def mc_trend(rows,x,e,model,index):
 design=trend_design(rows);raw,res,rank,s=np.linalg.lstsq(design,x[:,2],rcond=1e-12);ex=np.linalg.lstsq(design,x[:,2]-e[:,2],rcond=1e-12)[0]
 u,sv,vt=np.linalg.svd(design,full_matrices=False);inv=np.where(sv>sv.max()*1e-12,1/sv**2,0);b=(vt.T*inv)@vt;weights=design@b[:,1]
 require(abs(weights@x[:,2]-raw[1])<1e-10 and abs(weights@(x[:,2]-e[:,2])-ex[1])<1e-10,'Trend SVD coefficient equivalence failed')
 rng=np.random.Generator(np.random.PCG64(20261113+index));groups=defaultdict(list)
 for i,r in enumerate(rows):groups[(model.key(r),tuple(design[i]))].append(i)
 sim=np.zeros(R)
 for (key,_),ii in sorted(groups.items()):
  a=np.asarray(ii);weight=float(weights[a[0]]);require(np.ptp(weights[a])<1e-16,'Identical design coefficient mismatch')
  sim+=weight*rng.binomial(len(a),float(model.lookup[key]['pmfs'][2][1]),size=R)
 sim-=weights@e[:,2];stat=float(ex[1]);tol=1e-12*max(1,abs(stat));ext=int(np.count_nonzero(sim>=stat-tol))
 return stat,ext,{'raw_slope_per_decade':float(raw[1]),'calendar_excess_slope_per_decade':stat,'design_rank':int(rank),'design_columns':['intercept','(birthyear-1900)/10']+COUNTRIES[:5],'rcond':1e-12,'slope_unit':'fraction_of_people_per_birth_decade','direction_gate':float(raw[1])>0 and stat>0,'floating_inclusive_tolerance':tol,'calendar_grouping':'identical_exact_model_key_and_design_row'},float(raw[1])


def h4_vectors(x,e,edm,j):
 if j=='DM10':return np.eye(10)[x[:,5]]-edm,np.eye(10)[x[:,5]],edm
 return (x[:,j]-e[:,j])[:,None],x[:,j,None].astype(float),e[:,j,None]


def h4_stat(z,w):
 eff=w.sum(axis=0);require(np.all(eff>0),'H4 institution empty');means=w.T@z/eff[:,None];pooled=z.mean(axis=0);return float(np.sum(eff[:,None]*(means-pooled)**2)),eff,means


def mc_h4(rows,x,e,edm,index,j):
 z,raw,exp=h4_vectors(x,e,edm,j);w=member_weights(rows);stat,eff,means=h4_stat(z,w);rng=np.random.Generator(np.random.PCG64(20261113+index));strata=defaultdict(list)
 for i,r in enumerate(rows):strata[(int(r['analysis_DOB'][:4])//10*10,r['_source_class'])].append(i)
 groups=[np.asarray(v,dtype=np.int64) for k,v in sorted(strata.items())];pooled=z.mean(axis=0);tol=1e-12*max(1,abs(stat));ext=0;vary=False
 for start in range(0,R,256):
  b=min(256,R-start);sums=np.zeros((b,6,z.shape[1]))
  for ii in groups:
   if len(ii)<=1:sums+=np.broadcast_to((w[ii].T@z[ii])[None],sums.shape);continue
   perm=rng.permuted(np.broadcast_to(np.arange(len(ii)),(b,len(ii))).copy(),axis=1)
   shifted=z[ii][perm]
   # Entire person residual vectors move; memberships stay attached to slots.
   sums+=np.einsum('rni,nj->rji',shifted,w[ii],optimize=True)
  distances=np.sum(eff[None,:,None]*(sums/eff[None,:,None]-pooled[None,None,:])**2,axis=(1,2));ext+=int(np.count_nonzero(distances>=stat-tol));vary=vary or bool(np.ptp(distances)>tol)
 diag={'institution_order':COUNTRIES,'effective_weights':eff,'centered_means':means,'raw_means':w.T@raw/eff[:,None],'calendar_expected_means':w.T@exp/eff[:,None],'pooled_centered_mean':pooled,'stratum_count':len(groups),'singleton_strata':sum(len(ii)==1 for ii in groups),'permutable_people':sum(len(ii) for ii in groups if len(ii)>1),'permutation_distribution_varies':vary,'floating_inclusive_tolerance':tol,'entire_person_vector_moved':True}
 return stat,ext,diag


def ci(values):return np.quantile(values,[.025,.975],method='linear').tolist()


def bootstrap_pop(x,e,rng):
 n=len(x);raw=np.zeros((B,5));ex=np.zeros((B,5))
 for start in range(0,B,128):
  stop=min(B,start+128);ii=rng.integers(0,n,size=(stop-start,n));raw[start:stop]=x[ii,:5].mean(axis=1);ex[start:stop]=(x[ii,:5]-e[ii]).mean(axis=1)
 return np.quantile(raw,[.025,.975],axis=0,method='linear').T.tolist(),np.quantile(ex,[.025,.975],axis=0,method='linear').T.tolist()


def bootstrap_direct(nrows,arows,nx,ax,rng):
 nd=np.asarray([int(r['analysis_DOB'][:4])//10*10 for r in nrows]);ad=np.asarray([int(r['analysis_DOB'][:4])//10*10 for r in arows]);common=sorted(set(nd)&set(ad));tot=sum(np.sum(nd==d)+np.sum(ad==d) for d in common);weights={d:(np.sum(nd==d)+np.sum(ad==d))/tot for d in common};ans=np.zeros((B,3));raw=np.zeros((B,3));js=[0,1,2];sign=np.array([1,1,-1])
 for d in sorted(set(nd)|set(ad)):
  pools=[nx[nd==d][:,js],ax[ad==d][:,js]];means=[]
  for g,p in enumerate(pools):
   v=np.zeros((B,3))
   if len(p):
    for start in range(0,B,256):
     stop=min(B,start+256);ii=rng.integers(0,len(p),size=(stop-start,len(p)));v[start:stop]=p[ii].mean(axis=1)
   means.append(v);raw+=((1 if g==0 else -1)*len(p)/(len(nx) if g==0 else len(ax)))*v
  if d in weights:ans+=weights[d]*(means[0]-means[1])
 return {name:{'standardized':ci(ans[:,i]*sign[i]),'raw':ci(raw[:,i]*sign[i])} for i,name in enumerate(['H1c_PI','H1c_SG','H2c'])}


def bootstrap_trend(rows,x,e,rng):
 design=trend_design(rows);profile=np.column_stack([design,x[:,2],e[:,2]]);unique,counts=np.unique(profile,axis=0,return_counts=True);X=unique[:,:7];Y=unique[:,7:9].copy();Y[:,1]=Y[:,0]-Y[:,1];gram=(X[:,:,None]*X[:,None,:]).reshape(len(X),49);rhs=(X[:,:,None]*Y[:,None,:]).reshape(len(X),14);out=np.empty((B,2));n=len(rows)
 for start in range(0,B,128):
  stop=min(B,start+128);mult=rng.multinomial(n,counts/n,size=stop-start);grams=(mult@gram).reshape(-1,7,7);rhss=(mult@rhs).reshape(-1,7,2)
  for k in range(stop-start):
   # Refit the complete resampled design; profiles collapse only rows identical
   # in every predictor and both outcomes. This is whole-person bootstrap.
   if np.linalg.cond(grams[k])<1e12:
    coef=np.linalg.solve(grams[k],rhss[k])
   else:
    sw=np.sqrt(mult[k]);coef=np.linalg.lstsq(X*sw[:,None],Y*sw[:,None],rcond=1e-12)[0]
   out[start+k]=coef[1]
 return {'raw':ci(out[:,0]),'excess':ci(out[:,1]),'method':'person_multinomial_counts_of_identical_complete_design_outcome_profiles_refit_each_draw','profile_count':len(X)}


def holm(p):
 a=np.asarray(p);order=np.argsort(a,kind='stable');adj=np.empty(len(a));v=0.
 for k,i in enumerate(order):v=max(v,(len(a)-k)*a[i]);adj[i]=min(1,v)
 return adj.tolist()


def testrow(index,kind,stat,ext,diag,raw=None,excess=None):
 return {'test_id':IDS[index],'index':index,'kind':kind,'observed_statistic':float(stat),'raw_effect':None if raw is None else float(raw),'excess_effect':None if excess is None else float(excess),'p_nominal':(ext+1)/(R+1),'seed':20261113+index,'generator':'PCG64','replicates':R,'extreme_count':int(ext),'diagnostics':diag,'unadjusted95CI':None}


def run_case(case,rows,quality,pool,model,cache):
 start=time.time();broad=case=='strict_broad';arr={};pop={}
 for g,rr in rows.items():
  x,tg=arrays(rr,pool,broad);e,edm,etg=model.expectations(rr);arr[g]=(x,tg,e,edm,etg);pop[g]=describe(rr,x,tg,e,edm,etg)
 tests=[None]*18
 for index,g,j in [(0,'Nobel',0),(1,'Nobel',1),(2,'academy',0),(3,'academy',1),(6,'academy',2),(7,'academy',3),(10,'union','DM10'),(11,'union',4)]:
  print(json.dumps({'case':case,'test':IDS[index],'started':True}),flush=True)
  if case=='strict_broad' and j not in [2,3]:
   tests[index]=copy.deepcopy(cache['strict_primary']['tests'][index]);tests[index]['reused_identical_primary_endpoint']=True;continue
  x,_,e,edm,_=arr[g];stat,ext,diag=mc_calendar(rows[g],x,edm,model,index,j);raw=None if j=='DM10' else x[:,j].mean();tests[index]=testrow(index,'H3_DM10' if j=='DM10' else 'calendar',stat,ext,diag,raw,stat if j!='DM10' else None)
 for index,j,sign in [(4,0,1),(5,1,1),(8,2,-1)]:
  if case=='strict_broad' and j!=2:tests[index]=copy.deepcopy(cache['strict_primary']['tests'][index]);tests[index]['reused_identical_primary_endpoint']=True;continue
  print(json.dumps({'case':case,'test':IDS[index],'started':True}),flush=True);stat,ext,diag,raw=mc_direct(rows['Nobel'],rows['academy'],arr['Nobel'][0],arr['academy'][0],index,j,sign);tests[index]=testrow(index,'direct',stat,ext,diag,raw,None)
 print(json.dumps({'case':case,'test':'H2d','started':True}),flush=True);stat,ext,diag,raw=mc_trend(rows['academy'],arr['academy'][0],arr['academy'][2],model,9);tests[9]=testrow(9,'trend',stat,ext,diag,raw,stat)
 for index,j in [(12,0),(13,1),(14,2),(15,3),(16,'DM10'),(17,4)]:
  if case=='strict_broad' and j not in [2,3]:tests[index]=copy.deepcopy(cache['strict_primary']['tests'][index]);tests[index]['reused_identical_primary_endpoint']=True;continue
  print(json.dumps({'case':case,'test':IDS[index],'started':True}),flush=True);stat,ext,diag=mc_h4(rows['academy'],arr['academy'][0],arr['academy'][2],arr['academy'][3],index,j);tests[index]=testrow(index,'H4',stat,ext,diag)
 print(json.dumps({'case':case,'bootstrap_started':True}),flush=True);rng=np.random.Generator(np.random.PCG64(2026111301));ci_order=[]
 for g in ['Nobel','academy','union']:
  rawcis,excis=bootstrap_pop(arr[g][0],arr[g][2],rng);ci_order.append('population_'+g+'_5_metrics_joint_person_draws')
  for j,m in enumerate(pop[g]['scalar_metrics']):m['raw_unadjusted95CI']=rawcis[j];m['excess_unadjusted95CI']=excis[j]
 for index,g,j in [(0,'Nobel',0),(1,'Nobel',1),(2,'academy',0),(3,'academy',1),(6,'academy',2),(7,'academy',3),(11,'union',4)]:tests[index]['unadjusted95CI']={'excess':pop[g]['scalar_metrics'][j]['excess_unadjusted95CI'],'raw':pop[g]['scalar_metrics'][j]['raw_unadjusted95CI']}
 directcis=bootstrap_direct(rows['Nobel'],rows['academy'],arr['Nobel'][0],arr['academy'][0],rng);ci_order.append('direct_three_endpoints_joint_group_by_decade_person_draws')
 for index in [4,5,8]:tests[index]['unadjusted95CI']=directcis[IDS[index]]
 tests[9]['unadjusted95CI']=bootstrap_trend(rows['academy'],arr['academy'][0],arr['academy'][2],rng);ci_order.append('academy_GY_trend_complete_design_refit_person_bootstrap')
 adjusted=holm([t['p_nominal'] for t in tests]);primary=case=='strict_primary'
 for t,p in zip(tests,adjusted):
  gate=t['diagnostics'].get('raw_direction_gate',True) and t['diagnostics'].get('direction_gate',True)
  t.update({'p_Holm18_reference':p,'primary_family_member':primary,'reject_primary_Holm18_0_05':bool(primary and p<=.05),'supports_original_directional_prediction':bool(primary and p<=.05 and gate),'sensitivity_does_not_rescue_primary':not primary})
 answer={'case':case,'definition':{'source':quality,'cooccurrence':'broad' if broad else 'narrow','calendar_condition':'year_month' if model.month else 'year','symmetric_Jie_pm1_exclusion':model.no_jie,'Fields_exclusion':'academy_only' if case=='strict_withoutFields' else False,'LOC_exclusion':case=='expanded_withoutLOC'},'populations':pop,'tests':tests,'H4_description':{t['test_id']:t['diagnostics'] for t in tests if t['kind']=='H4'},'bootstrap':{'seed':2026111301,'generator':'PCG64','replicates':B,'unit':'complete_person_with_membership_vector','case_stream_reset':True,'execution_order':ci_order,'quantiles':[.025,.975],'quantile_method':'linear','multiple_testing_adjusted':False},'elapsed_seconds':time.time()-start}
 print(json.dumps({'case':case,'completed':True,'elapsed_seconds':answer['elapsed_seconds']}),flush=True);return answer


def synthetic_qa():
 # No cohort input opened. Enumerate every possible label choice for a tiny
 # two-stratum example, verify direct formula and finite permutation moments.
 import itertools
 nrows=[{'analysis_DOB':'2001-01-01'},{'analysis_DOB':'2011-01-01'}];arows=[{'analysis_DOB':'2002-01-01'},{'analysis_DOB':'2012-01-01'}];nx=np.array([[1,0,1,0,0,0],[2,1,0,0,0,0]]);ax=np.array([[0,1,0,0,0,0],[0,0,1,0,0,0]])
 stat,raw,info=direct_inputs(nrows,arows,nx,ax,0,1);assert stat==1.5 and raw==1.5
 vals=[]
 for choose in itertools.product([0,1],repeat=2):
  vals.append(sum(w*((np.r_[yn,ya])[k]-(np.r_[yn,ya])[1-k]) for k,(d,w,yn,ya) in zip(choose,info)))
 assert abs(np.mean(vals))<1e-15 and max(vals)==stat
 assert np.allclose(holm([.01,.04,.03]),[.03,.06,.06])
 z=np.array([[1.],[2.],[3.],[4.]]);w=np.array([[1,0],[0,1],[.5,.5],[1,0.]])
 q,eff,means=h4_stat(z,w);assert np.allclose(eff,[2.5,1.5]);assert abs(q-np.sum(eff[:,None]*(means-z.mean(axis=0))**2))<1e-15
 assert np.allclose(w.sum(axis=1),1)
 rng=np.random.Generator(np.random.PCG64(44));hh=rng.multivariate_hypergeometric([2,1,3],3,size=100,method='marginals');assert np.all(hh.sum(axis=1)==3) and np.all(hh<=np.array([2,1,3]))
 # Weighted-person-bootstrap sufficient moments equal literal repeated rows.
 X=np.array([[1.,0,0],[1,1,0],[1,0,1],[1,1,1]]);y=np.array([1.,2,3,4]);c=np.array([2,1,3,1]);literal=np.repeat(np.arange(4),c);a=np.linalg.lstsq(X[literal],y[literal],rcond=1e-12)[0];b=np.linalg.solve(X.T@(c[:,None]*X),X.T@(c*y));assert np.allclose(a,b)
 Xdef=np.column_stack([X,X[:,1]])
 cdef=np.array([1,0,3,2]);literaldef=np.repeat(np.arange(4),cdef);swdef=np.sqrt(cdef);adef=np.linalg.lstsq(Xdef[literaldef],y[literaldef],rcond=1e-12)[0];bdef=np.linalg.lstsq(Xdef*swdef[:,None],y*swdef,rcond=1e-12)[0];assert np.allclose(adef,bdef)
 return {'status':'PASS','rank_deficient_weighted_bootstrap_equivalence':True,'real_input_loaded':False,'direct_exhaustive_two_strata':True,'Holm_reference':True,'fractional_H4_formula':True,'category_hypergeometric_bounds':True,'bootstrap_complete_design_equivalence':True,'fixed_R':R,'fixed_B':B,'endpoint_order':IDS}


def main(args):
 if args.synthetic_qa:
  print(json.dumps(synthetic_qa(),ensure_ascii=False,indent=2));return
 receipt,scope=verify_gate(args);require(not Path(args.output).exists(),'Result exists; no overwrite');pool,inputs,loc,nofields=load_data(args.v4_zip,args.calendar_npz);m=base_module();models={'year':m.CalendarModel(pool),'broad':m.CalendarModel(pool,broad=True),'noJie':m.CalendarModel(pool,no_jie=True),'yearMonth':m.CalendarModel(pool,month=True)};cache={}
 checkpoints=Path(args.output).with_suffix('.checkpoints');checkpoints.mkdir(exist_ok=False)
 for case in CASES:
  rows,quality=case_rows(case,inputs,pool,loc,nofields);model=models[{'strict_broad':'broad','strict_noJie':'noJie','strict_yearMonth':'yearMonth'}.get(case,'year')];cache[case]=run_case(case,rows,quality,pool,model,cache)
  (checkpoints/(case+'.json')).write_text(json.dumps(safe(cache[case]),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
 result={'schema':'scientist_Nobel_global18_reveal_v1','test_order':IDS,'case_order':CASES,'primary_family':{'source':'strict','cooccurrence':'narrow','calendar':'year','adjustment':'Holm18','alpha':.05},'cases':cache,'scope':scope,'execution_receipt':receipt,'source_pins':{'engine_sha256':sha(__file__),'V4_zip_sha256':sha(args.v4_zip),'calendar_npz_sha256':sha(args.calendar_npz),'original_helper_sha256':sha(WORK/'original/reveal_v1/scripts/analyze_country.py')},'completed_at_utc':dt.datetime.now(dt.timezone.utc).isoformat()}
 Path(args.output).write_text(json.dumps(safe(result),ensure_ascii=False,indent=2,allow_nan=False)+'\n');print(json.dumps({'status':'PASS','output':args.output,'cases':len(cache),'primary_Holm18_rejections':sum(t['reject_primary_Holm18_0_05'] for t in cache['strict_primary']['tests'])}))


if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--scope');p.add_argument('--locked-files');p.add_argument('--execution-receipt');p.add_argument('--v4-zip');p.add_argument('--calendar-npz');p.add_argument('--output');p.add_argument('--synthetic-qa',action='store_true');main(p.parse_args())
