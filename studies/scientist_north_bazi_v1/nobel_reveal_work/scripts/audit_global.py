#!/usr/bin/env python3
"""Independent audit of the locked scientist global18 calculation.

The auditor uses separate population reconstruction and statistic code.  Its
fixed 10,000-draw strict-case checks are QA only, never replacement p-values.
"""
import argparse
import datetime as dt
import gzip
import hashlib
import itertools
import json
from pathlib import Path
import zipfile

import numpy as np

IDS = ['H1a_PI','H1a_SG','H1b_PI','H1b_SG','H1c_PI','H1c_SG',
       'H2a','H2b','H2c','H2d','H3a','H3b','H4_PI','H4_SG',
       'H4_GY','H4_SGY','H4_DM10','H4_WATER']
INST = ['NAS','UK_Royal_Society','DE_Leopoldina','France','Japan','CAS']
CASES = ['strict_primary','expanded','strict_broad','strict_noJie',
         'strict_yearMonth','expanded_withoutLOC','strict_withoutFields']
RQA = 10000
QA_SEED_BASE = 202611150000

def require(condition, message):
    if not bool(condition):
        raise AssertionError(message)

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def close(a,b,label,atol=2e-10):
    require(np.allclose(a,b,rtol=2e-10,atol=atol), label)

def jhash(x):
    return hashlib.sha256((json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(',',':'))+'\n').encode()).hexdigest()

def holm(values):
    p=np.asarray(values,float); order=np.argsort(p,kind='stable')
    q=np.empty(len(p)); previous=0.0
    for rank,k in enumerate(order):
        previous=max(previous,min(1.0,(len(p)-rank)*p[k]));q[k]=previous
    return q

def source_class(row, quality):
    accepted=row['DOB_support'][quality]
    require(all(x['analysis_date_coordinate']==row['analysis_DOB'] for x in accepted),'source coordinate')
    grades={x.get('DOB_source_grade') for x in accepted}
    if 'S1' in grades:return 'S1'
    if 'S2' in grades:return 'S2'
    union=any(bool(x.get('possible_DOB_source_grades')) and set(x['possible_DOB_source_grades'])<= {'S1','S2'} for x in accepted)
    if union:return 'S1_or_S2_union'
    require(quality=='expanded' and 'S3' in grades,'unclassified effective source')
    return 'S3_only'

def raw_v4(path):
    with zipfile.ZipFile(path) as z:
        prefix='scientist_north_data_freeze_v4/outputs/'
        def read(rel):return [json.loads(x) for x in gzip.decompress(z.read(prefix+rel)).splitlines()]
        data={}
        for quality in ['strict','expanded']:
            data[quality]={
                'Nobel':read(quality+'/Nobel_full_roster_matched_people.jsonl.gz'),
                'academy':read(quality+'/academy_excluding_official_Nobel.jsonl.gz'),
                'Fields':{r['person_id'] for r in read(quality+'/Fields_parallel_cohort.jsonl.gz')},
                'academy_withoutFields':{r['person_id'] for r in read(quality+'/academy_excluding_official_Nobel_and_Fields.jsonl.gz')},
                'institutions':{c:{r['person_id'] for r in read(quality+'/by_institution/'+c+'.jsonl.gz')} for c in INST}}
        data['withoutLOC']={r['person_id'] for r in read('sensitivity/expanded_without_LOC_quoted_metadata_people.jsonl.gz')}
    return data

class IndependentCalendar:
    def __init__(self,path,month=False,no_jie=False,broad=False):
        with np.load(path,allow_pickle=False) as a:
            self.pool={k:a[k] for k in a.files}
        a=self.pool
        self.dates={str(d):i for i,d in enumerate(a['dates'])}
        self.x=a['features'].astype(int).copy()
        if broad:self.x[:,2]=a['GY_broad'];self.x[:,3]=a['SGY_broad']
        self.month=month
        buckets={}
        for i in range(len(self.x)):
            if no_jie and bool(a['jie_boundary_plus_minus_one_civil_day'][i]):continue
            key=(int(a['year'][i]),int(a['month'][i]) if month else 0)
            buckets.setdefault(key,[]).append(i)
        self.buckets={k:np.asarray(v,int) for k,v in buckets.items()}
        self.means={k:self.x[v,:5].mean(axis=0) for k,v in self.buckets.items()}
        self.dmp={k:np.bincount(self.x[v,5],minlength=10)/len(v) for k,v in self.buckets.items()}
        self.tg={k:a['ten_god_counts'][v].mean(axis=0) for k,v in self.buckets.items()}
    def key(self,row):
        d=dt.date.fromisoformat(row['analysis_DOB']);return d.year,d.month if self.month else 0
    def arrays(self,rows):
        indexes=np.array([self.dates[r['analysis_DOB']] for r in rows],int)
        keys=[self.key(r) for r in rows]
        x=self.x[indexes]
        E=np.asarray([self.means[k] for k in keys]);P=np.asarray([self.dmp[k] for k in keys])
        return x,E,P,np.asarray([self.tg[k] for k in keys]),indexes

def population(data,case,model):
    quality='expanded' if case in ['expanded','expanded_withoutLOC'] else 'strict'
    groups={g:sorted(data[quality][g],key=lambda r:r['person_id']) for g in ['Nobel','academy']}
    for g in groups:
        if case=='expanded_withoutLOC':groups[g]=[r for r in groups[g] if r['person_id'] in data['withoutLOC']]
        if case=='strict_noJie':groups[g]=[r for r in groups[g] if not bool(model.pool['jie_boundary_plus_minus_one_civil_day'][model.dates[r['analysis_DOB']]])]
        if case=='strict_withoutFields' and g=='academy':groups[g]=[r for r in groups[g] if r['person_id'] in data[quality]['academy_withoutFields']]
    require(not ({r['person_id'] for r in groups['Nobel']} & {r['person_id'] for r in groups['academy']}),'Nobel/control overlap')
    groups['union']=sorted(groups['Nobel']+groups['academy'],key=lambda r:r['person_id'])
    for g,rows in groups.items():
        require(len({r['person_id'] for r in rows})==len(rows),'duplicate person')
        require(all(r['hemisphere']=='north' for r in rows),'hemisphere')
    academy=groups['academy']; W=np.zeros((len(academy),6))
    for i,row in enumerate(academy):
        tags=[j for j,c in enumerate(INST) if row['person_id'] in data[quality]['institutions'][c]]
        require(len(tags)>0,'academy with no eligible membership')
        W[i,tags]=1/len(tags)
    close(W.sum(axis=1),1,'fractional row sum')
    classes=[source_class(r,quality) for r in academy]
    return groups,W,classes

def design(rows,W):
    t=np.array([(int(r['analysis_DOB'][:4])-1900)/10 for r in rows])
    return np.column_stack([np.ones(len(rows)),t,W[:,:5]])

def h4_q(z,W):
    z=np.asarray(z,float)
    if z.ndim==1:z=z[:,None]
    totals=W.sum(axis=0)
    require(np.all(totals>0),'empty H4 institution')
    return float(np.sum(totals[:,None]*((W.T@z)/totals[:,None]-z.mean(axis=0))**2))

def comparison(nrows,arows,nx,ax,reverse=False):
    nd=np.array([int(r['analysis_DOB'][:4])//10*10 for r in nrows]);ad=np.array([int(r['analysis_DOB'][:4])//10*10 for r in arows])
    common=sorted(set(nd)&set(ad));groups=[]
    for d in common:
        n=nx[nd==d];a=ax[ad==d]
        groups.append((d,n,a))
    require(groups,'empty common decade support')
    weights=np.array([len(n)+len(a) for d,n,a in groups],float);weights/=weights.sum()
    sign=-1 if reverse else 1
    stat=sign*sum(w*(n.mean()-a.mean()) for w,(_,n,a) in zip(weights,groups))
    raw=sign*(nx.mean()-ax.mean())
    return float(stat),float(raw),groups,weights

def mc_calendar(rows,x,model,metric,rng,R=RQA):
    keys={}
    for r in rows:keys[model.key(r)]=keys.get(model.key(r),0)+1
    if metric=='DM10':
        E=sum(n*model.dmp[k] for k,n in keys.items());obs=np.bincount(x[:,5],minlength=10)
        stat=float(np.sum((obs-E)**2/E)); simulated=np.zeros((R,10),int)
        for k,n in sorted(keys.items()):simulated+=rng.multinomial(n,model.dmp[k],size=R)
        values=np.sum((simulated-E)**2/E,axis=1);tol=1e-12*max(1,abs(stat))
        return (1+np.count_nonzero(values>=stat-tol))/(R+1)
    stat=int(x[:,metric].sum()); values=np.zeros(R,int)
    for k,n in sorted(keys.items()):
        v=model.x[model.buckets[k],metric];counts=np.bincount(v,minlength=6 if metric<2 else 2)
        values+=rng.multinomial(n,counts/counts.sum(),size=R)@np.arange(len(counts))
    return (1+np.count_nonzero(values>=stat))/(R+1)

def mc_comparison(stat,groups,weights,reverse,rng,R=RQA):
    values=np.zeros(R)
    for w,(_,n,a) in zip(weights,groups):
        pooled=np.r_[n,a].astype(int);hist=np.bincount(pooled,minlength=int(pooled.max())+1)
        sampled=rng.multivariate_hypergeometric(hist,len(n),size=R)
        sums=sampled@np.arange(len(hist));values+=w*(sums/len(n)-(pooled.sum()-sums)/len(a))
    if reverse:values=-values
    tol=1e-12*max(1,abs(stat))
    return (1+np.count_nonzero(values>=stat-tol))/(R+1)

def mc_trend(stat,rows,W,E,rng,R=RQA):
    coeff=np.linalg.pinv(design(rows,W),rcond=1e-12)[1]
    center=float(coeff@E[:,2]);values=np.empty(R)
    for start in range(0,R,100):
        end=min(R,start+100);draws=rng.random((end-start,len(rows)))<E[:,2]
        values[start:end]=draws@coeff-center
    tol=1e-12*max(1,abs(stat))
    return (1+np.count_nonzero(values>=stat-tol))/(R+1)

def mc_h4(stat,z,W,strata,rng,R=RQA):
    hits=0;tol=1e-12*max(1,abs(stat));order=np.arange(len(W))
    for _ in range(R):
        for idx in strata:order[idx]=rng.permutation(idx)
        hits+=h4_q(z[order],W)>=stat-tol
    return (1+hits)/(R+1)

def synthetic():
    close(holm([.001,.02,.5]),[.003,.04,.5],'toy Holm')
    r={'analysis_DOB':'1900-01-01','DOB_support':{'strict':[{'analysis_date_coordinate':'1900-01-01','DOB_source_grade':None,'possible_DOB_source_grades':['S1','S2']} ]}}
    require(source_class(r,'strict')=='S1_or_S2_union','source union')
    W=np.array([[1,0],[.5,.5],[0,1]],float);z=np.array([1.,-1.,0.])
    close(h4_q(z,W),1/3,'fractional weighted Q')
    require(h4_q(np.ones(3),W)==0,'zero H4')
    close(mc_h4(h4_q(z,W),z,W,[np.array([i]) for i in range(3)],np.random.default_rng(7),R=20),1,'unpermutable H4 returns p1')
    rows=[{'analysis_DOB':f'{y}-01-01'} for y in [1900,1901,1910,1911]]
    a=[{'analysis_DOB':f'{y}-01-01'} for y in [1902,1903,1912,1913]]
    stat,raw,g,w=comparison(rows,a,np.array([1,0,1,0]),np.array([0,0,1,1]))
    close(stat,0,'common support contrast');close(w,[.5,.5],'common support weights')
    try:
        comparison([{'analysis_DOB':'1900-01-01'}],[{'analysis_DOB':'1950-01-01'}],np.array([1]),np.array([0]))
    except AssertionError:pass
    else:raise AssertionError('empty common support must not pool adaptively')
    # Exhaustive two-group, one-decade binary permutation has six labels.
    pooled=np.array([1,1,0,0]);allstats=[]
    for pick in itertools.combinations(range(4),2):
        mask=np.zeros(4,bool);mask[list(pick)]=True;allstats.append(pooled[mask].mean()-pooled[~mask].mean())
    close(np.mean(np.array(allstats)>=1),1/6,'exact perm tail')
    X=np.ones((4,7)); y=np.array([0.,1.,0.,1.]);b=np.linalg.lstsq(X,y,rcond=1e-12)[0]
    close(b,np.linalg.pinv(X,rcond=1e-12)@y,'rank deficient pseudoinverse')
    return {'schema':'global18_independent_synthetic_QA_v1','status':'PASS','fixed_strict_MC_checks':18,'MC_replicates_per_endpoint':RQA,'MC_seed_base':QA_SEED_BASE,'p_agreement_tolerance':'6*sqrt(pmain*(1-pmain)/99999+pqa*(1-pqa)/10000)+0.002','tests':['Holm','source_union','fractional_H4','zero_variation','unpermutable_H4','common_decade_weights','no_common_support_no_fallback','exhaustive_label_tail','rank_deficient_OLS']}

def predicted_case(data,case,model):
    groups,W,classes=population(data,case,model)
    arrays={g:model.arrays(rows) for g,rows in groups.items()}
    stats=[None]*18
    # Fixed calendar tests, with integer-sum MC but mean-excess estimands.
    mapping={0:('Nobel',0),1:('Nobel',1),2:('academy',0),3:('academy',1),
             6:('academy',2),7:('academy',3),11:('union',4)}
    for j,(g,c) in mapping.items():
        x,E,*_=arrays[g];stats[j]=float(np.mean(x[:,c]-E[:,c]))
    contrasts={}
    for j,c,reverse in [(4,0,False),(5,1,False),(8,2,True)]:
        stat,raw,parts,weights=comparison(groups['Nobel'],groups['academy'],arrays['Nobel'][0][:,c],arrays['academy'][0][:,c],reverse)
        stats[j]=stat;contrasts[j]=(raw,parts,weights,reverse)
    ax,aE,aP,*_=arrays['academy'];X=design(groups['academy'],W)
    raw_slope=float(np.linalg.lstsq(X,ax[:,2],rcond=1e-12)[0][1])
    excess_slope=float(np.linalg.lstsq(X,ax[:,2]-aE[:,2],rcond=1e-12)[0][1]);stats[9]=excess_slope
    ux,uE,uP,*_=arrays['union']; expected=uP.sum(axis=0)
    stats[10]=float(np.sum((np.bincount(ux[:,5],minlength=10)-expected)**2/expected))
    residual=np.column_stack([ax[:,:5]-aE,np.eye(10)[ax[:,5]]-aP])
    h4columns={12:[0],13:[1],14:[2],15:[3],16:list(range(5,15)),17:[4]}
    for j,cols in h4columns.items():stats[j]=h4_q(residual[:,cols],W)
    stratakeys={}
    for i,(r,c) in enumerate(zip(groups['academy'],classes)):
        key=(int(r['analysis_DOB'][:4])//10*10,c);stratakeys.setdefault(key,[]).append(i)
    strata=[np.array(v,int) for k,v in sorted(stratakeys.items())]
    return {'groups':groups,'W':W,'classes':classes,'arrays':arrays,'statistics':stats,
            'contrasts':contrasts,'raw_trend':raw_slope,'excess_trend':excess_slope,
            'rank':int(np.linalg.matrix_rank(X,tol=1e-12)),
            'h4residual':residual,'h4columns':h4columns,'strata':strata,'calendar_mapping':mapping}

def compare_description(actual,rows,arrays,model,label):
    x,E,P,TG,idx=arrays;n=len(rows)
    require(actual['n']==n,label+' n')
    require(actual['person_ids_sha256']==jhash([r['person_id'] for r in rows]),label+' IDs')
    scalar=actual['scalar_metrics'];require(len(scalar)==5,label+' scalar count')
    for j,v in enumerate(scalar):
        require(v['observed_sum']==int(x[:,j].sum()),label+' observed sum')
        close(v['observed_mean_or_rate'],x[:,j].mean(),label+' mean')
        close(v['calendar_expected_mean_or_rate'],E[:,j].mean(),label+' expectation')
        close(v['observed_minus_expected'],(x[:,j]-E[:,j]).mean(),label+' excess')
    dm=actual['day_master_distribution'];require(len(dm)==10,label+' DM count')
    obs=np.bincount(x[:,5],minlength=10);exp=P.sum(axis=0)
    for j,v in enumerate(dm):
        require(v['observed_people']==int(obs[j]),label+' DM observed')
        close(v['calendar_expected_people'],exp[j],label+' DM expectation')
        close(v['observed_fraction'],obs[j]/n,label+' DM share')
        close(v['calendar_expected_fraction'],exp[j]/n,label+' DM expected share')
    # Full ten-god output is independently constrained by the five-position pool.
    actual_tg=actual.get('ten_gods',[])
    if actual_tg:
        require(len(actual_tg)==10,label+' ten-god count')
        gods=model.pool['ten_god_counts'][idx];close(gods.sum(axis=1),5,label+' five positions')
        for j,v in enumerate(actual_tg):
            if 'observed_count_sum' in v:require(v['observed_count_sum']==int(gods[:,j].sum()),label+' TG observed')
            if 'observed_count_mean_per_person' in v:close(v['observed_count_mean_per_person'],gods[:,j].mean(),label+' TG mean')
            if 'calendar_expected_count_mean_per_person' in v:close(v['calendar_expected_count_mean_per_person'],TG[:,j].mean(),label+' TG expectation')

def independent_strict_mc(pred,model,tests):
    report=[]
    for j,name in enumerate(IDS):
        rng=np.random.Generator(np.random.PCG64(QA_SEED_BASE+j));stat=pred['statistics'][j]
        if j in pred['calendar_mapping']:
            g,c=pred['calendar_mapping'][j];p=mc_calendar(pred['groups'][g],pred['arrays'][g][0],model,c,rng)
        elif j in [4,5,8]:
            raw,parts,weights,reverse=pred['contrasts'][j];p=mc_comparison(stat,parts,weights,reverse,rng)
        elif j==9:p=mc_trend(stat,pred['groups']['academy'],pred['W'],pred['arrays']['academy'][1],rng)
        elif j==10:p=mc_calendar(pred['groups']['union'],pred['arrays']['union'][0],model,'DM10',rng)
        else:p=mc_h4(stat,pred['h4residual'][:,pred['h4columns'][j]],pred['W'],pred['strata'],rng)
        main=float(tests[j]['p_nominal'])
        tolerance=6*np.sqrt(main*(1-main)/99999+p*(1-p)/RQA)+.002
        require(abs(p-main)<=tolerance,'independent strict MC '+name)
        report.append({'test_id':name,'seed':QA_SEED_BASE+j,'replicates':RQA,'p_QA_only':p,'p_main':main,'tolerance':float(tolerance),'status':'PASS'})
        print(json.dumps({'QA_MC_completed':name,'p_QA':p,'p_main':main}),flush=True)
    return report

def check_ci(value):
    if isinstance(value,dict):
        for key in ['raw','excess','standardized']:
            if key in value:check_ci(value[key])
    else:
        ci=np.asarray(value,float)
        require(ci.shape==(2,) and np.isfinite(ci).all() and ci[0]<=ci[1],'descriptive CI bounds')

def run(args):
    synthetic()
    output=Path(args.output);require(not output.exists(),'audit output already exists')
    scope=json.loads(Path(args.scope).read_text());receipt=json.loads(Path(args.execution_receipt).read_text())
    require(receipt['remote_plan_and_code_verified_before_summary'] is True,'remote execution lock missing')
    require(receipt['scope_sha256']==sha(args.scope),'receipt scope mismatch')
    require(receipt['locked_file_manifest_sha256']==sha(args.locked_files),'receipt manifest mismatch')
    manifest=json.loads(Path(args.locked_files).read_text())
    for path,pin in manifest.items():require(sha(path)==pin,'locked file changed '+path)
    require(sha(args.v4_zip)=='53302ef5c4bbb946adcaceb70d7a7fd576c7f06d03c3e7080874654e1a2644f9','original V4 input pin')
    require(sha(args.calendar_npz)=='d150883033464ebd3afafaf764738ed3b573d0d0fb4bd252a955e403a75fcc8b','original calendar input pin')
    result=json.loads(Path(args.results).read_text())
    data=raw_v4(args.v4_zip)
    require([len(data['strict'][g]) for g in ['Nobel','academy']]==[621,5234],'primary population sizes')
    require([len(data['expanded'][g]) for g in ['Nobel','academy']]==[627,5871],'expanded population sizes')
    require(list(result['cases'])==CASES,'case order')
    cases=[];strict_mc=[]
    for case in CASES:
        model=IndependentCalendar(args.calendar_npz,month=case=='strict_yearMonth',no_jie=case=='strict_noJie',broad=case=='strict_broad')
        pred=predicted_case(data,case,model);actual=result['cases'][case]
        for j,cols in pred['h4columns'].items():
            diag=actual['H4_description'][IDS[j]]
            require(diag['institution_order']==INST,'H4 institution order')
            totals=pred['W'].sum(axis=0);close(diag['effective_weights'],totals,'H4 fractional totals')
            ax,E,P,*_=pred['arrays']['academy']
            raw=np.column_stack([ax[:,:5],np.eye(10)[ax[:,5]]])[:,cols]
            exp=np.column_stack([E,P])[:,cols]
            close(diag['raw_means'],pred['W'].T@raw/totals[:,None],'H4 raw institution means')
            close(diag['calendar_expected_means'],pred['W'].T@exp/totals[:,None],'H4 calendar institution means')
            close(diag['centered_means'],pred['W'].T@(raw-exp)/totals[:,None],'H4 residual institution means')
        for g in ['Nobel','academy','union']:compare_description(actual['populations'][g],pred['groups'][g],pred['arrays'][g],model,case+'/'+g)
        tests=actual['tests'];require([r['test_id'] for r in tests]==IDS,'18 test order')
        q=holm([r['p_nominal'] for r in tests])
        for j,t in enumerate(tests):
            close(t['observed_statistic'],pred['statistics'][j],case+'/'+IDS[j]+' statistic')
            require(t['seed']==20261113+j,'original global seed')
            require(t['replicates']==99999,'MC count')
            require(isinstance(t['extreme_count'],int) and 0<=t['extreme_count']<=99999,'valid MC extremes')
            close(t['p_nominal'],(1+t['extreme_count'])/100000,'plus-one p',1e-15)
            close(t['p_Holm18_reference'],q[j],'Holm18',1e-15)
            expected_reject=bool(case=='strict_primary' and q[j]<=.05)
            require(t['reject_primary_Holm18_0_05']==expected_reject,'primary-only rejection')
            if t.get('unadjusted95CI') is not None:
                check_ci(t['unadjusted95CI'])
            d=t['diagnostics']
            if j in [4,5,8]:
                raw,parts,weights,reverse=pred['contrasts'][j]
                close(d['raw_whole_group_contrast_in_predicted_direction'],raw,'raw direction contrast')
                require(d['raw_direction_gate']==bool(raw>0),'raw direction gate')
                require(d['common_decades']==[p[0] for p in parts],'common decade support')
                close(d['pooled_decade_weights'],weights,'common decade weights')
            if j==9:
                close(d['raw_slope_per_decade'],pred['raw_trend'],'raw trend')
                close(d['calendar_excess_slope_per_decade'],pred['excess_trend'],'excess trend')
                require(d['direction_gate']==bool(pred['raw_trend']>0 and pred['excess_trend']>0),'trend direction gate')
            gate=bool(pred['contrasts'][j][0]>0) if j in pred['contrasts'] else bool(pred['raw_trend']>0 and pred['excess_trend']>0) if j==9 else True
            require(t['supports_original_directional_prediction']==bool(expected_reject and gate),'locked support gate')
        if case=='strict_primary':strict_mc=independent_strict_mc(pred,model,tests)
        cases.append({'case':case,'status':'PASS','N':{g:len(pred['groups'][g]) for g in pred['groups']},'source_class_counts':{c:pred['classes'].count(c) for c in sorted(set(pred['classes']))},'effective_membership_weights':pred['W'].sum(axis=0).tolist(),'all_18_statistics_recomputed':True,'all_18_Holm_and_tail_count_identities_checked':True,'direct_weights_and_raw_direction_gates_checked':True,'trend_raw_excess_coefficients_checked':True,'CI_shape_finiteness_order_checked':True})
    report={'schema':'scientist_global18_independent_QA_v1','status':'PASS','cases':cases,'independent_MC':strict_mc,'MC_QA_is_not_replacement_p':True,'hashes':{'results':sha(args.results),'auditor':sha(__file__),'V4':sha(args.v4_zip),'calendar':sha(args.calendar_npz),'scope':sha(args.scope),'receipt':sha(args.execution_receipt)},'original_18_Holm_family_checked':True,'original_country36_not_modified':True}
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'status':'PASS','output':str(output),'results_sha256':sha(args.results),'audit_sha256':sha(output)}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--synthetic-qa')
    for field in ['scope','locked-files','execution-receipt','v4-zip','calendar-npz','results','output']:p.add_argument('--'+field)
    args=p.parse_args()
    if args.synthetic_qa:
        report=synthetic();Path(args.synthetic_qa).write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
    else:run(args)

