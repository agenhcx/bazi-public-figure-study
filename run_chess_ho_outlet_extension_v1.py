#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations
import argparse, calendar, json
from pathlib import Path
import numpy as np
import pandas as pd
import sxtwl

STEMS=list('甲乙丙丁戊己庚辛壬癸')
STEM_ELEMENT=['木','木','火','火','土','土','金','金','水','水']
STEM_YANG=[1,0,1,0,1,0,1,0,1,0]
MAIN={0:9,1:5,2:0,3:1,4:4,5:2,6:3,7:5,8:6,9:7,10:4,11:8}
GEN={'木':'火','火':'土','土':'金','金':'水','水':'木'}
CTL={'木':'土','土':'水','水':'火','火':'金','金':'木'}

FROZEN={
 '2013_M_DISCOVERY':{'Direct Resource':0.874,'Indirect Resource':1.125,'Any Resource':0.936,'Seven Killings':0.969,'Direct Officer':1.224},
 '2023_M_FULL':{'Direct Resource':0.936,'Indirect Resource':1.055,'Any Resource':0.978,'Seven Killings':0.955,'Direct Officer':1.128},
 '2023_M_NEW_TARGET':{'Direct Resource':0.946,'Indirect Resource':1.001,'Any Resource':0.972,'Seven Killings':0.875,'Direct Officer':0.878},
}

FEATURES=['Direct Resource','Indirect Resource','Any Resource','Seven Killings','Direct Officer','Direct Wealth','Indirect Wealth','Any Wealth','Any Major Outlet']


def ten_god(dm:int,t:int)->str:
    de,te=STEM_ELEMENT[dm],STEM_ELEMENT[t]
    same=STEM_YANG[dm]==STEM_YANG[t]
    if te==de: return '比肩' if same else '劫财'
    if GEN[de]==te: return '食神' if same else '伤官'
    if CTL[de]==te: return '偏财' if same else '正财'
    if CTL[te]==de: return '七杀' if same else '正官'
    if GEN[te]==de: return '偏印' if same else '正印'
    raise RuntimeError((dm,t))


def states(y:int,m:int,d:int)->dict:
    x=sxtwl.fromSolar(y,m,d)
    yg,mg,dg=x.getYearGZ(),x.getMonthGZ(),x.getDayGZ()
    dm=int(dg.tg)
    targets=[int(yg.tg),MAIN[int(yg.dz)],int(mg.tg),MAIN[int(mg.dz)],MAIN[int(dg.dz)]]
    p=set(ten_god(dm,t) for t in targets)
    dr='正印' in p; ir='偏印' in p; sk='七杀' in p; do='正官' in p
    dw='正财' in p; iw='偏财' in p; ho='伤官' in p
    return {
      'Hurting Officer':int(ho),'Direct Resource':int(dr),'Indirect Resource':int(ir),'Any Resource':int(dr or ir),
      'Seven Killings':int(sk),'Direct Officer':int(do),'Direct Wealth':int(dw),'Indirect Wealth':int(iw),
      'Any Wealth':int(dw or iw),'Any Major Outlet':int(dr or ir or dw or iw or sk),
    }


def year_table(y:int)->pd.DataFrame:
    rows=[]
    for m in range(1,13):
        for d in range(1,calendar.monthrange(y,m)[1]+1):
            r=states(y,m,d); r['date']=f'{y:04d}-{m:02d}-{d:02d}'; rows.append(r)
    return pd.DataFrame(rows)


def load_cohort(path:Path,label:str)->pd.DataFrame:
    if not path.exists(): raise FileNotFoundError(path)
    df=pd.read_csv(path)
    if 'exact_dob_frozen' not in df.columns: raise RuntimeError(f'{label}: missing exact_dob_frozen')
    dt=pd.to_datetime(df['exact_dob_frozen'].astype(str).str[:10],errors='raise')
    df=df.copy(); df['_year']=dt.dt.year.astype(int); df['_month']=dt.dt.month.astype(int); df['_day']=dt.dt.day.astype(int)
    ss=[states(int(y),int(m),int(d)) for y,m,d in zip(df['_year'],df['_month'],df['_day'])]
    return pd.concat([df.reset_index(drop=True),pd.DataFrame(ss)],axis=1)


def cond_mc(hplus:pd.DataFrame,cache:dict[int,pd.DataFrame],feature:str,n_sims:int,seed:int)->dict:
    n=len(hplus); obs=float(hplus[feature].sum()); sims=np.zeros(n_sims,float); rng=np.random.default_rng(seed)
    for y,n_y in hplus['_year'].value_counts().sort_index().items():
        cand=cache[int(y)]
        cand=cand[cand['Hurting Officer']==1]
        vals=cand[feature].to_numpy(float)
        idx=rng.integers(0,len(vals),size=(n_sims,int(n_y)))
        sims+=vals[idx].sum(axis=1)
    mu=float(sims.mean()); sd=float(sims.std(ddof=1)); obs_mean=obs/n; null_mean=mu/n
    p_hi=float((1+(sims>=obs).sum())/(n_sims+1)); p_lo=float((1+(sims<=obs).sum())/(n_sims+1))
    return {'n_HO_positive':int(n),'observed_mean':obs_mean,'null_mean':null_mean,'ratio':obs_mean/null_mean,
            'z':(obs-mu)/sd,'p_enrich':p_hi,'p_deplete':p_lo,'p_two_sided':min(1.0,2*min(p_hi,p_lo)),'null_sd_sum':sd}


def holm2(p1:float,p2:float)->tuple[float,float]:
    p=[p1,p2]; order=np.argsort(p); out=[0.0,0.0]; running=0.0
    for rank,idx in enumerate(order):
        val=(2-rank)*p[idx]; running=max(running,val); out[idx]=min(1.0,running)
    return out[0],out[1]


def find_2013(repo:Path)->Path:
    cands=[repo/'chess_freeze'/'primary_clean_top_2013_M.csv']+list(repo.rglob('primary_clean_top_2013_M.csv'))
    seen=[]
    for p in cands:
        if p.exists() and p not in seen: seen.append(p)
    if len(seen)==1: return seen[0]
    if not seen: raise FileNotFoundError('Cannot find primary_clean_top_2013_M.csv; use --file-2013')
    print('Multiple 2013 files found:'); [print(' ',p) for p in seen]; raise RuntimeError('Use --file-2013 explicitly')


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--repo',default='.')
    ap.add_argument('--file-2013',default=None)
    ap.add_argument('--file-2023-full',default=r'chess_2023_cohorts_v1\primary_2023_M_FULL.csv')
    ap.add_argument('--file-2023-new',default=r'chess_2023_cohorts_v1\validation_2023_M_NEW_TARGET.csv')
    ap.add_argument('--output-subdir',default='chess_ho_outlet_extension_v1')
    ap.add_argument('--null-sims',type=int,default=50000)
    ap.add_argument('--seed',type=int,default=20261010)
    ap.add_argument('--sanity-tolerance',type=float,default=0.03)
    a=ap.parse_args(); repo=Path(a.repo).resolve(); out=repo/a.output_subdir; out.mkdir(parents=True,exist_ok=True)
    paths={'2013_M_DISCOVERY':Path(a.file_2013).resolve() if a.file_2013 else find_2013(repo),
           '2023_M_FULL':(repo/a.file_2023_full).resolve(),'2023_M_NEW_TARGET':(repo/a.file_2023_new).resolve()}
    print('Inputs:'); [print(f'  {k}: {v}') for k,v in paths.items()]
    cohorts={k:load_cohort(v,k) for k,v in paths.items()}
    years=sorted({int(y) for df in cohorts.values() for y in df['_year']})
    cache={}
    for y in years:
        print('calendar',y); cache[y]=year_table(y)

    results={}; rows=[]
    for ci,(label,df) in enumerate(cohorts.items()):
        hp=df[df['Hurting Officer']==1].copy(); print(f'\n{label}: N={len(df)}, HO+={len(hp)}'); results[label]={}
        for fi,f in enumerate(FEATURES):
            r=cond_mc(hp,cache,f,a.null_sims,a.seed+100000*ci+1009*(fi+1)); results[label][f]=r; rows.append({'cohort':label,'feature':f,**r})
            print(f"  {f:20s} obs={r['observed_mean']:.4f} null={r['null_mean']:.4f} R={r['ratio']:.3f} Z={r['z']:+.3f} p+={r['p_enrich']:.4f} p2={r['p_two_sided']:.4f}")

    print('\nSANITY CHECK')
    maxdiff=0.0
    for label,d in FROZEN.items():
        for f,target in d.items():
            got=results[label][f]['ratio']; diff=abs(got-target); maxdiff=max(maxdiff,diff)
            print(f'{label:22s} {f:18s} frozen={target:.3f} got={got:.3f} diff={diff:.3f}')
    if maxdiff>a.sanity_tolerance:
        raise RuntimeError(f'SANITY FAILED: max diff {maxdiff:.4f} > {a.sanity_tolerance:.4f}; do not interpret E1/E2')
    print(f'SANITY PASSED: max |ΔR|={maxdiff:.4f}')

    prim=results['2023_M_NEW_TARGET']; h1,h2=holm2(prim['Any Wealth']['p_enrich'],prim['Any Major Outlet']['p_enrich'])
    prim['Any Wealth']['holm2_enrich']=h1; prim['Any Major Outlet']['holm2_enrich']=h2
    for row in rows:
        row['holm2_enrich']=np.nan
        if row['cohort']=='2023_M_NEW_TARGET' and row['feature']=='Any Wealth': row['holm2_enrich']=h1
        if row['cohort']=='2023_M_NEW_TARGET' and row['feature']=='Any Major Outlet': row['holm2_enrich']=h2
    pd.DataFrame(rows).to_csv(out/'chess_ho_outlet_extension_results.csv',index=False,encoding='utf-8-sig')
    payload={'analysis_role':'post_reveal_frozen_methodological_extension','primary_cohort':'2023_M_NEW_TARGET','model':'M0_5pos_mainqi',
             'conditioning':'exact birth year + HO presence','null_sims':a.null_sims,'seed':a.seed,'sanity_max_ratio_diff':maxdiff,'results':results}
    (out/'chess_ho_outlet_extension_results.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')

    lines=['CHESS HURTING-OFFICER OUTLET EXTENSION V1','='*72,'','Primary: 2023_M_NEW_TARGET; M0 five informative positions.','',f'Sanity max |ΔR|={maxdiff:.6f} PASS','']
    for label in ['2013_M_DISCOVERY','2023_M_FULL','2023_M_NEW_TARGET']:
        lines += [label,'-'*len(label)]
        for f in ['Direct Wealth','Indirect Wealth','Any Wealth','Any Major Outlet']:
            r=results[label][f]; extra=''
            if label=='2023_M_NEW_TARGET' and f=='Any Wealth': extra=f" Holm2={h1:.6g}"
            if label=='2023_M_NEW_TARGET' and f=='Any Major Outlet': extra=f" Holm2={h2:.6g}"
            lines.append(f"{f}: obs={r['observed_mean']:.6f} null={r['null_mean']:.6f} R={r['ratio']:.4f} Z={r['z']:+.4f} p+={r['p_enrich']:.6g} p-={r['p_deplete']:.6g} p2={r['p_two_sided']:.6g}{extra}")
        lines.append('')
    lines += ['INTERPRETATION GUARDRAILS','-------------------------','1. Necessary-component tests, not complete classical 格局.','2. No 身强/身弱, 用神, 喜忌 judgment.','3. R>1 = enrichment; R<1 = depletion direction.','4. E1/E2 are post-reveal methodological extension, not original preregistered confirmation.']
    (out/'chess_ho_outlet_extension_summary.txt').write_text('\n'.join(lines),encoding='utf-8')

    print('\nPRIMARY HEADLINE')
    for f in ['Any Wealth','Any Major Outlet']:
        r=prim[f]; print(f"{f:20s} R={r['ratio']:.4f} Z={r['z']:+.4f} p+={r['p_enrich']:.6g} p-={r['p_deplete']:.6g} p2={r['p_two_sided']:.6g} Holm2={r['holm2_enrich']:.6g}")
    print('\nSaved:',out)

if __name__=='__main__': main()
