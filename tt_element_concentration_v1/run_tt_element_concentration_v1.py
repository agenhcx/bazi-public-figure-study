#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
import argparse, calendar, hashlib, io, json, math, shutil, subprocess
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import rankdata
from lunar_python import Solar

PLAN_TAG='tt-element-concentration-plan-v1'; RESULT_TAG='tt-element-concentration-results-v1'; TRAINING_TAG='chess-preregister-v3-date-sanity'; OUTDIR='tt_element_concentration_v1'
TRAINING_COHORT_PATH='studies/table_tennis/data/tabletennis_reference_enriched.csv'; TRAINING_ELO_PATH='studies/table_tennis/data/ttr_elo_player_summary.csv'
EXPECTED_HIST=335; EXPECTED_HIST_PERF=112; EXPECTED_TRAIN=384
STEM_ELEMENT={'甲':'木','乙':'木','丙':'火','丁':'火','戊':'土','己':'土','庚':'金','辛':'金','壬':'水','癸':'水'}
BRANCH_MAIN_STEM={'子':'癸','丑':'己','寅':'甲','卯':'乙','辰':'戊','巳':'丙','午':'丁','未':'己','申':'庚','酉':'辛','戌':'戊','亥':'壬'}
ELEMENTS=['木','火','土','金','水']
METRICS=[('distinct_elements_6pos','less'),('dominant_element_share','greater'),('hhi_element_concentration','greater'),('element_entropy','less'),('all_five_present_6pos','less')]

def run(cmd,cwd,check=True):
    print('$',' '.join(cmd)); p=subprocess.run(cmd,cwd=str(cwd),text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    if p.stdout: print(p.stdout.rstrip())
    if check and p.returncode!=0: raise RuntimeError('Command failed: '+' '.join(cmd))
    return p.stdout.strip()

def run_bytes(cmd,cwd):
    p=subprocess.run(cmd,cwd=str(cwd),stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    if p.returncode!=0: raise RuntimeError(p.stderr.decode('utf-8','replace'))
    return p.stdout

def sha256_file(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for c in iter(lambda:f.read(1024*1024),b''): h.update(c)
    return h.hexdigest()

def read_git_csv(repo,tag,path):
    listed=set(run(['git','ls-tree','-r','--name-only',tag],repo).splitlines())
    if path not in listed: raise RuntimeError(f'{tag}: missing {path}')
    d=pd.read_csv(io.BytesIO(run_bytes(['git','show',f'{tag}:{path}'],repo)),encoding='utf-8-sig',dtype={'qid':str})
    print(f'[git input] {tag}:{path} n={len(d)}'); return d

def fixed_find(name,roots):
    hits=[]
    for root in roots:
        root=Path(root).resolve()
        for p in [root/name,root/'studies'/'table_tennis'/name,root/'studies'/'table_tennis'/'results'/name,root/'table_tennis'/name,root/'tt'/name]:
            if p.exists() and p.is_file(): hits.append(p.resolve())
    uniq=[]; seen=set()
    for p in hits:
        k=str(p).lower()
        if k not in seen: uniq.append(p); seen.add(k)
    if len(uniq)==1: return uniq[0]
    if len(uniq)>1: raise RuntimeError('Multiple matches; pass explicit path:\n'+'\n'.join(map(str,uniq)))
    return None

def resolve_hist(args,repo):
    roots=[Path.cwd(),repo,repo.parent]
    h=Path(args.historical_holdout).resolve() if args.historical_holdout else None
    p=Path(args.historical_performance).resolve() if args.historical_performance else None
    if h is None:
        for n in ['tt_holdout_reveal_v1_player_bazi.csv','tt_holdout_1950_1984_PRIMARY.csv']:
            h=fixed_find(n,roots)
            if h: break
    if p is None:
        for n in ['tt_holdout_reveal_v1_performance_player_data.csv','tt_performance_lock_v1_H3_PRIMARY.csv']:
            p=fixed_find(n,roots)
            if p: break
    if h is None or p is None:
        raise RuntimeError('Historical files not found in fixed locations. Re-run with explicit paths, e.g.\n  --historical-holdout C:\\path\\tt_holdout_reveal_v1_player_bazi.csv\n  --historical-performance C:\\path\\tt_holdout_reveal_v1_performance_player_data.csv')
    print('[historical holdout]',h); print('[historical performance]',p); return h,p

def feat(dt):
    ec=Solar.fromYmdHms(dt.year,dt.month,dt.day,12,0,0).getLunar().getEightChar(); yp,mp,dp=ec.getYear(),ec.getMonth(),ec.getDay()
    stems=[yp[0],BRANCH_MAIN_STEM[yp[1]],mp[0],BRANCH_MAIN_STEM[mp[1]],dp[0],BRANCH_MAIN_STEM[dp[1]]]
    els=[STEM_ELEMENT[x] for x in stems]; vals=np.array([els.count(e) for e in ELEMENTS],float); p=vals/6.0; q=p[p>0]; distinct=int((vals>0).sum())
    return {'elements_6pos':'|'.join(els),'distinct_elements_6pos':distinct,'dominant_element_share':float(vals.max()/6),'hhi_element_concentration':float((p*p).sum()),'element_entropy':float(-(q*np.log(q)).sum()),'all_five_present_6pos':int(distinct==5)}

def enrich(df,label):
    d=df.copy(); dobcol=next((c for c in ['dob','exact_dob_frozen','birth_date','date_of_birth'] if c in d.columns),None)
    if not dobcol: raise RuntimeError(f'{label}: no DOB column')
    d['_dob']=pd.to_datetime(d[dobcol],errors='coerce')
    if d['_dob'].isna().any(): raise RuntimeError(f'{label}: invalid DOB rows={int(d._dob.isna().sum())}')
    d['birth_year_analysis']=d['_dob'].dt.year.astype(int)
    return pd.concat([d.reset_index(drop=True),pd.DataFrame([feat(x.date()) for x in d['_dob']])],axis=1)

def add_strength(d):
    d=d.copy()
    if 'strength_percentile' in d.columns:
        d['strength_percentile']=pd.to_numeric(d['strength_percentile'],errors='raise'); return d
    need={'highest_rank','birth_year','gender'}
    if not need.issubset(d.columns): raise RuntimeError('Historical performance lacks strength_percentile and required reconstruction columns')
    d['highest_rank']=pd.to_numeric(d['highest_rank'],errors='raise'); d['birth_year']=pd.to_numeric(d['birth_year'],errors='raise').astype(int); d['birth_decade']=(d.birth_year//10)*10
    d['performance_stratum']=d.gender.astype(str).str.lower()+'_'+d.birth_decade.astype(str); out=[]
    for _,g in d.groupby('performance_stratum',sort=False):
        g=g.copy(); n=len(g); rk=g.highest_rank.rank(method='average',ascending=True); g['strength_percentile']=0.5 if n==1 else (n-rk)/(n-1); out.append(g)
    return pd.concat(out).sort_index()

def perm_spear(x,y,direction,B,rng,batch=2000):
    x=np.asarray(x,float); y=np.asarray(y,float); ok=np.isfinite(x)&np.isfinite(y); x=x[ok]; y=y[ok]; n=len(x)
    if n<4 or len(np.unique(x))<2 or len(np.unique(y))<2: return {'n':n,'rho':np.nan,'direction':direction,'p_directional':np.nan,'p_two_sided':np.nan,'permutations':B}
    xr=rankdata(x); yr=rankdata(y); xr-=xr.mean(); yr-=yr.mean(); den=math.sqrt(float((xr*xr).sum()*(yr*yr).sum())); obs=float((xr*yr).sum()/den)
    ge=le=tw=done=0
    while done<B:
        b=min(batch,B-done); order=np.argsort(rng.random((b,n)),axis=1); sims=(yr[order]@xr)/den
        ge+=int((sims>=obs-1e-12).sum()); le+=int((sims<=obs+1e-12).sum()); tw+=int((np.abs(sims)>=abs(obs)-1e-12).sum()); done+=b
    pg=(ge+1)/(B+1); pl=(le+1)/(B+1)
    return {'n':n,'rho':obs,'direction':direction,'p_directional':pl if direction=='less' else pg,'p_two_sided':(tw+1)/(B+1),'permutations':B}

def cache(years):
    out={}; ys=sorted(set(map(int,years)))
    for i,y in enumerate(ys,1):
        print(f'calendar {i}/{len(ys)}: {y}'); rows=[]
        for m in range(1,13):
            for dd in range(1,calendar.monthrange(y,m)[1]+1):
                f=feat(pd.Timestamp(y,m,dd).date()); rows.append([f[k] for k,_ in METRICS])
        out[y]=np.asarray(rows,float)
    return out

def sel_mc(df,c,B,rng,batch=1000):
    obs=np.array([df[k].mean() for k,_ in METRICS],float); sims=np.zeros((B,len(METRICS)),float)
    for y,n in df.birth_year_analysis.value_counts().sort_index().items():
        arr=c[int(y)]; done=0
        while done<B:
            b=min(batch,B-done); idx=rng.integers(0,len(arr),size=(b,int(n))); sims[done:done+b]+=arr[idx].sum(axis=1); done+=b
    sims/=len(df); out={}
    for j,(metric,direction) in enumerate(METRICS):
        val=float(obs[j]); mu=float(sims[:,j].mean()); sd=float(sims[:,j].std(ddof=1)); le=(int((sims[:,j]<=val+1e-12).sum())+1)/(B+1); ge=(int((sims[:,j]>=val-1e-12).sum())+1)/(B+1)
        out[metric]={'n':len(df),'observed_mean':val,'null_mean':mu,'null_sd':sd,'z':(val-mu)/sd if sd else np.nan,'direction':direction,'p_directional':le if direction=='less' else ge,'p_two_sided':min(1.0,2*min(le,ge)),'simulations':B}
    return out

def sexnorm(v):
    x=str(v).strip().lower()
    if x in {'m','male','男'}: return 'M'
    if x in {'f','female','女'}: return 'F'
    return 'UNKNOWN'

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--repo',default=r'..\1986wiki'); ap.add_argument('--historical-holdout'); ap.add_argument('--historical-performance'); ap.add_argument('--perf-perm',type=int,default=50000); ap.add_argument('--null-sims',type=int,default=20000); ap.add_argument('--seed',type=int,default=20260928); ap.add_argument('--remote',default='origin'); ap.add_argument('--no-git',action='store_true'); a=ap.parse_args()
    repo=Path(run(['git','rev-parse','--show-toplevel'],Path(a.repo))).resolve()
    if not run(['git','tag','--list',PLAN_TAG],repo).strip(): raise RuntimeError('Plan tag missing; freeze first')
    if not a.no_git:
        if run(['git','diff','--cached','--name-only'],repo).strip(): raise RuntimeError('Git index already has staged files')
        if run(['git','tag','--list',RESULT_TAG],repo).strip(): raise RuntimeError(f'Tag exists: {RESULT_TAG}')
    hp,pp=resolve_hist(a,repo); hr=pd.read_csv(hp,encoding='utf-8-sig',dtype={'qid':str}); pr=pd.read_csv(pp,encoding='utf-8-sig',dtype={'qid':str})
    print(f'[historical selection input] n={len(hr)} sha256={sha256_file(hp)}'); print(f'[historical performance input] n={len(pr)} sha256={sha256_file(pp)}')
    if len(hr)!=EXPECTED_HIST: raise RuntimeError(f'Historical holdout n={len(hr)} expected={EXPECTED_HIST}')
    if len(pr)!=EXPECTED_HIST_PERF: raise RuntimeError(f'Historical performance n={len(pr)} expected={EXPECTED_HIST_PERF}')
    tr=read_git_csv(repo,TRAINING_TAG,TRAINING_COHORT_PATH); er=read_git_csv(repo,TRAINING_TAG,TRAINING_ELO_PATH)
    if len(tr)!=EXPECTED_TRAIN: raise RuntimeError(f'Training cohort n={len(tr)} expected={EXPECTED_TRAIN}')
    print('\n=== FIRST TT ELEMENT-CONCENTRATION CALCULATION ===')
    hist=enrich(hr,'hist'); histp=enrich(add_strength(pr),'hist_perf'); train=enrich(tr,'train'); elo=enrich(er,'train_elo')
    c=cache(list(hist.birth_year_analysis)+list(train.birth_year_analysis)); rng=np.random.default_rng(a.seed)
    sgroups={'HIST_POOLED':hist,'TRAIN_POOLED':train}
    for pref,d in [('HIST',hist),('TRAIN',train)]:
        if 'gender' in d:
            sx=d.gender.map(sexnorm)
            for s in ['M','F']:
                if (sx==s).any(): sgroups[f'{pref}_{s}']=d.loc[sx==s].copy()
    selection={k:sel_mc(d,c,a.null_sims,rng) for k,d in sgroups.items()}
    valid=elo.loc[pd.to_numeric(elo.peak_elo,errors='coerce').notna()].copy(); valid['peak_elo_gender_z']=pd.to_numeric(valid.peak_elo_gender_z,errors='coerce'); valid=valid.loc[valid.peak_elo_gender_z.notna()].copy()
    pgroups={'HIST_PERF_POOLED':(histp,'strength_percentile'),'TRAIN_ELO_POOLED':(valid,'peak_elo_gender_z')}
    for pref,d,outcome in [('HIST_PERF',histp,'strength_percentile'),('TRAIN_ELO',valid,'peak_elo_gender_z')]:
        if 'gender' in d:
            sx=d.gender.map(sexnorm)
            for s in ['M','F']:
                if (sx==s).any(): pgroups[f'{pref}_{s}']=(d.loc[sx==s].copy(),outcome)
    performance={}
    for label,(d,outcome) in pgroups.items():
        performance[label]={}
        for metric,direction in METRICS:
            r=perm_spear(d[metric],pd.to_numeric(d[outcome],errors='coerce'),direction,a.perf_perm,rng); r['outcome']=outcome; performance[label][metric]=r
    result={'analysis_role':'cross_domain_exploratory_validation_plan_frozen_before_first_TT_concentration_calculation','plan_tag':PLAN_TAG,'training_source_tag':TRAINING_TAG,'seed':a.seed,'performance_permutations':a.perf_perm,'calendar_null_simulations':a.null_sims,'historical_inputs':{'selection_path':str(hp),'selection_sha256':sha256_file(hp),'selection_n':len(hr),'performance_path':str(pp),'performance_sha256':sha256_file(pp),'performance_n':len(pr)},'training_inputs':{'cohort_tag_path':f'{TRAINING_TAG}:{TRAINING_COHORT_PATH}','cohort_n':len(tr),'elo_tag_path':f'{TRAINING_TAG}:{TRAINING_ELO_PATH}','elo_n_total':len(er),'elo_n_reliable':int(pd.to_numeric(er.peak_elo,errors='coerce').notna().sum())},'primary_selection':{'sample':'HIST_POOLED','metric':'distinct_elements_6pos',**selection['HIST_POOLED']['distinct_elements_6pos']},'primary_performance':{'sample':'HIST_PERF_POOLED','metric':'distinct_elements_6pos',**performance['HIST_PERF_POOLED']['distinct_elements_6pos']},'selection':selection,'performance':performance}
    out=repo/OUTDIR; out.mkdir(parents=True,exist_ok=True)
    hist.to_csv(out/'tt_element_concentration_historical_players.csv',index=False,encoding='utf-8-sig'); histp.to_csv(out/'tt_element_concentration_historical_performance_players.csv',index=False,encoding='utf-8-sig'); train.to_csv(out/'tt_element_concentration_training_players.csv',index=False,encoding='utf-8-sig'); elo.to_csv(out/'tt_element_concentration_training_elo_players.csv',index=False,encoding='utf-8-sig')
    srows=[{'group':g,'metric':m,**r} for g,res in selection.items() for m,r in res.items()]; prows=[{'group':g,'metric':m,**r} for g,res in performance.items() for m,r in res.items()]
    sp=out/'tt_element_concentration_selection_tests.csv'; ppout=out/'tt_element_concentration_performance_tests.csv'; pd.DataFrame(srows).to_csv(sp,index=False,encoding='utf-8-sig'); pd.DataFrame(prows).to_csv(ppout,index=False,encoding='utf-8-sig')
    jp=out/'tt_element_concentration_results_v1.json'; jp.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    ps=result['primary_selection']; pf=result['primary_performance']; lines=['# TT Elemental-Concentration Cross-Domain Results V1','','Status: plan frozen before first TT concentration calculation.','',f"PRIMARY selection distinct: obs={ps['observed_mean']:.5f}, null={ps['null_mean']:.5f}, z={ps['z']:.4f}, p_dir={ps['p_directional']:.6f}, p2={ps['p_two_sided']:.6f}",f"PRIMARY performance distinct: rho={pf['rho']:.5f}, p_dir={pf['p_directional']:.6f}, p2={pf['p_two_sided']:.6f}, n={pf['n']}"]
    for m,_ in METRICS[1:]:
        sr=selection['HIST_POOLED'][m]; prr=performance['HIST_PERF_POOLED'][m]; lines.append(f"{m}: selection obs={sr['observed_mean']:.5f} null={sr['null_mean']:.5f} p={sr['p_directional']:.6f}; performance rho={prr['rho']:.5f} p={prr['p_directional']:.6f}")
    md=out/'TT_ELEMENT_CONCENTRATION_RESULTS_V1.md'; md.write_text('\n'.join(lines),encoding='utf-8'); sc=out/'run_tt_element_concentration_v1.py'; shutil.copy2(Path(__file__).resolve(),sc)
    print('\n=== TT ELEMENT CONCENTRATION HEADLINE ==='); print(f"PRIMARY HISTORICAL SELECTION: distinct obs={ps['observed_mean']:.5f} null={ps['null_mean']:.5f} z={ps['z']:.4f} p_dir={ps['p_directional']:.6f} p2={ps['p_two_sided']:.6f}"); print(f"PRIMARY HISTORICAL PERFORMANCE: distinct vs strength rho={pf['rho']:.5f} p_dir={pf['p_directional']:.6f} p2={pf['p_two_sided']:.6f} n={pf['n']}")
    print('\nHISTORICAL SECONDARY ROBUSTNESS')
    for m,_ in METRICS[1:]:
        sr=selection['HIST_POOLED'][m]; prr=performance['HIST_PERF_POOLED'][m]; print(f"{m}: selection obs={sr['observed_mean']:.5f} null={sr['null_mean']:.5f} z={sr['z']:.4f} p={sr['p_directional']:.6f} | performance rho={prr['rho']:.5f} p={prr['p_directional']:.6f}")
    print('\nTRAINING SECONDARY')
    for m,_ in METRICS:
        sr=selection['TRAIN_POOLED'][m]; prr=performance['TRAIN_ELO_POOLED'][m]; print(f"{m}: selection obs={sr['observed_mean']:.5f} null={sr['null_mean']:.5f} p={sr['p_directional']:.6f} | dynamicElo rho={prr['rho']:.5f} p={prr['p_directional']:.6f} n={prr['n']}")
    print('\nSEX-SPECIFIC DISTINCT-ELEMENTS DESCRIPTIVE')
    for lab in ['HIST_M','HIST_F','TRAIN_M','TRAIN_F']:
        if lab in selection:
            r=selection[lab]['distinct_elements_6pos']; print(f"{lab} selection: obs={r['observed_mean']:.5f} null={r['null_mean']:.5f} p_dir={r['p_directional']:.6f}")
    for lab in ['HIST_PERF_M','HIST_PERF_F','TRAIN_ELO_M','TRAIN_ELO_F']:
        if lab in performance:
            r=performance[lab]['distinct_elements_6pos']; print(f"{lab} performance: rho={r['rho']:.5f} p_dir={r['p_directional']:.6f} n={r['n']}")
    if a.no_git: return
    generated=[out/'tt_element_concentration_historical_players.csv',out/'tt_element_concentration_historical_performance_players.csv',out/'tt_element_concentration_training_players.csv',out/'tt_element_concentration_training_elo_players.csv',sp,ppout,jp,md,sc]; rels=[p.relative_to(repo).as_posix() for p in generated]; run(['git','add','--',*rels],repo)
    actual={x.replace('\\','/') for x in run(['git','diff','--cached','--name-only'],repo).splitlines() if x.strip()}; expected=set(rels)
    if actual!=expected: raise RuntimeError(f'Staging mismatch: expected={sorted(expected)} actual={sorted(actual)}')
    run(['git','commit','-m','Add TT elemental-concentration cross-domain results'],repo); run(['git','tag','-a',RESULT_TAG,'-m','Record TT elemental-concentration cross-domain results'],repo); branch=run(['git','branch','--show-current'],repo); run(['git','push',a.remote,branch],repo); run(['git','push',a.remote,RESULT_TAG],repo)
    print('\n=== TT ELEMENT-CONCENTRATION RESULTS FROZEN ==='); print('Commit:',run(['git','rev-parse','HEAD'],repo)); print('Tag:   ',RESULT_TAG); print('Output:',out)
if __name__=='__main__': main()
