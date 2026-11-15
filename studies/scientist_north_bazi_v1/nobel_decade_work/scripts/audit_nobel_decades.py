#!/usr/bin/env python3
"""Independent audit of the post-reveal Nobel birth-decade exploration.

No main-engine statistic or sampling function is imported.  Count-polynomial
margins are rebuilt independently, exact linear moments use grouped integer
generating functions, and QA draws are person-level conditional draws.
"""
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import datetime as dt
from fractions import Fraction
import gzip
import hashlib
import heapq
import itertools
import json
import multiprocessing as mp
from pathlib import Path
import zipfile

import numpy as np

GODS = ['比肩','劫财','食神','伤官','偏财','正财','七杀','正官','偏印','正印']
STEMS = list('甲乙丙丁戊己庚辛壬癸')
ENDPOINTS = (['TG_M0_'+g for g in GODS] + ['DM_'+s for s in STEMS] +
             ['DM_water','GY_narrow','SGY_narrow','M1_priority_PI_count','M1_priority_SG_count'])
SOURCES = ['strict','expanded']
DECADES = list(range(1830,1990,10))
V4_SHA = '53302ef5c4bbb946adcaceb70d7a7fd576c7f06d03c3e7080874654e1a2644f9'
CAL_SHA = 'd150883033464ebd3afafaf764738ed3b573d0d0fb4bd252a955e403a75fcc8b'
HID_SHA = '19e8bc8648fe8b69122161da260e1dae487816241c655bd96a1273783f1ef723'
RQA = 10000
QA_SEED = 202611170000
CTX = None


def require(c, message):
    if not bool(c): raise AssertionError(message)


def close(a, b, message, atol=3e-9):
    require(np.allclose(a,b,atol=atol,rtol=2e-10),message)


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def canonical(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n'


def trim(a, K):
    a=np.asarray(a)[:K+1]
    nz=np.flatnonzero(a)
    return a[:int(nz[-1])+1] if len(nz) else a[:1]


def conv(a,b,K): return trim(np.convolve(a,b),K)


def balanced_product(polys,K):
    heap=[]
    for i,p in enumerate(polys): heapq.heappush(heap,(len(p),i,np.asarray(p,float)))
    if not heap:return np.array([1.])
    seq=len(heap)
    while len(heap)>1:
        _,_,a=heapq.heappop(heap);_,_,b=heapq.heappop(heap)
        c=conv(a,b,K);heapq.heappush(heap,(len(c),seq,c));seq+=1
    return heap[0][2]


def person_suffix(pmfs,K):
    """Backward person-level generating functions, distinct from bin sampling."""
    n=len(pmfs);out=np.zeros((n+1,K+1));out[n,0]=1.
    for i in range(n-1,-1,-1):
        for c,p in enumerate(pmfs[i]):
            if p and c<=K:out[i,c:]+=float(p)*out[i+1,:K+1-c]
    require(out[0,K]>0,'impossible conditional total')
    return out


def sample_person_counts(pmfs,bin_index,K,R,seed):
    suffix=person_suffix(pmfs,K)
    rng=np.random.Generator(np.random.PCG64(seed));left=np.full(R,K,int)
    counts=np.zeros((R,len(DECADES)),int)
    for i,p in enumerate(pmfs):
        support=np.arange(len(p));remain=left[:,None]-support[None,:]
        weights=np.asarray(p)[None,:]*suffix[i+1,np.maximum(remain,0)]
        weights[remain<0]=0
        sums=weights.sum(axis=1)
        require(np.all(sums>0),'sampler entered impossible state')
        cumulative=np.cumsum(weights/sums[:,None],axis=1);cumulative[:,-1]=1.
        chosen=(rng.random(R)[:,None]>=cumulative).sum(axis=1)
        counts[:,bin_index[i]]+=chosen;left-=chosen
    require(np.all(left==0) and np.all(counts.sum(axis=1)==K),'sampler total not fixed')
    return counts


def conditional_margins(pmfs,bin_index,K):
    B=[]
    for j in range(len(DECADES)):
        p=np.array([1.])
        for i in np.flatnonzero(bin_index==j):p=conv(p,pmfs[int(i)],K)
        B.append(p)
    full=balanced_product(B,K)
    require(K<len(full) and full[K]>0,'impossible polynomial conditional total')
    total=float(full[K]);margins=[];mu=[];var=[]
    for j,b in enumerate(B):
        others=balanced_product([p for k,p in enumerate(B) if k!=j],K)
        k=np.arange(len(b));r=K-k;valid=(r>=0)&(r<len(others))
        weights=np.zeros(len(b));weights[valid]=b[valid]*others[r[valid]]
        mass=float(weights.sum());close(mass,total,'conditional factorization mass',1e-12)
        weights/=mass;m=float(k@weights);v=float(((k-m)**2)@weights)
        margins.append(weights);mu.append(m);var.append(v)
    close(sum(mu),K,'sum conditional means equals K')
    return B,margins,np.array(mu),np.array(var),total


def int_power(weights,n,K):
    a=np.array([int(v) for v in weights],dtype=object);out=np.array([1],dtype=object)
    while n:
        if n&1:out=conv(out,a,K)
        n//=2
        if n:a=conv(a,a,K)
    return out


def add_polys(a,b,K):
    n=min(K+1,max(len(a),len(b)));c=np.zeros(n,dtype=object)
    c[:min(len(a),n)]+=a[:n];c[:min(len(b),n)]+=b[:n]
    return trim(c,K)


def exact_linear_mean(year_hist,year_counts,K):
    """Grouped generating functions plus derivative, not person C/M recurrence."""
    C=np.array([1],dtype=object);M=np.array([0],dtype=object)
    for year,n in sorted(year_counts.items()):
        block=int_power(year_hist[year],n,K)
        x=(year//10*10-1900)//10
        block_L=np.array([int(v)*x*k for k,v in enumerate(block)],dtype=object)
        M=add_polys(conv(M,block,K),conv(C,block_L,K),K)
        C=conv(C,block,K)
    require(K<len(C) and int(C[K])>0,'impossible exact conditional total')
    num=int(M[K]) if K<len(M) else 0
    return Fraction(num,int(C[K]))


def reflected_cuts(mean,observed):
    distance=abs(Fraction(observed)-mean)
    lo=mean-distance;hi=mean+distance
    lower=lo.numerator//lo.denominator
    upper=-((-hi.numerator)//hi.denominator)
    return lower,upper


def holm(p):
    p=np.array(p,float);order=np.argsort(p,kind='stable');q=np.empty(len(p));last=0.
    for rank,i in enumerate(order):last=max(last,min(1.,(len(p)-rank)*p[i]));q[i]=last
    return q


def input_data(v4,calendar,hidden):
    with np.load(calendar,allow_pickle=False) as a:cal={k:a[k] for k in a.files}
    with np.load(hidden,allow_pickle=False) as a:hid={k:a[k] for k in a.files}
    require(np.array_equal(cal['dates'],hid['dates']),'hidden/calendar dates')
    require(cal['ten_god_names'].tolist()==GODS,'Ten-God order')
    require(cal['dm_stems'].tolist()==STEMS,'Day-Master order')
    require(hid['models'].tolist()[1]=='M1_priority_5','hidden priority axis')
    require(hid['traits'].tolist()==['PI','SG'],'hidden trait axis')
    priority=hid['count_scaled72'][:,1,:].astype(int)
    require(np.all(priority%72==0),'priority counts not integer')
    values=np.column_stack([cal['ten_god_counts'],np.eye(10,dtype=int)[cal['DM_index']],
                            cal['water_DM'],cal['GY_narrow'],cal['SGY_narrow'],priority//72])
    require(values.shape==(len(cal['dates']),25),'endpoint shape')
    require(np.all((values>=0)&(values<=5)),'endpoint bounds')
    dateidx={str(d):i for i,d in enumerate(cal['dates'])}
    groups={}
    with zipfile.ZipFile(v4) as z:
        for s in SOURCES:
            path='scientist_north_data_freeze_v4/outputs/'+s+'/Nobel_full_roster_matched_people.jsonl.gz'
            rows=sorted([json.loads(v) for v in gzip.decompress(z.read(path)).splitlines()],key=lambda r:r['person_id'])
            require(len(rows)==(621 if s=='strict' else 627),'Nobel population count')
            require(all(r['hemisphere']=='north' for r in rows),'north only')
            groups[s]=rows
    common={r['person_id']:r['analysis_DOB'] for r in groups['strict']}
    require(set(common)<={r['person_id'] for r in groups['expanded']},'strict subset of expanded')
    require(all(common[r['person_id']]==r['analysis_DOB'] for r in groups['expanded'] if r['person_id'] in common),'source DOB agreement')
    return cal,values,dateidx,groups


def predict(endpoint_index,source,cal,values,dateidx,groups):
    rows=groups[source];obsidx=np.array([dateidx[r['analysis_DOB']] for r in rows]);obs=values[obsidx,endpoint_index]
    years=np.array([int(r['analysis_DOB'][:4]) for r in rows]);binidx=(years//10*10-1830)//10
    K=int(obs.sum());year_counts=Counter(years.tolist());year_hist={};year_pmf={}
    for year in year_counts:
        v=values[cal['year']==year,endpoint_index]
        hist=np.bincount(v,minlength=6 if endpoint_index<10 or endpoint_index>=23 else 2)
        hist=trim(hist,int(np.flatnonzero(hist)[-1]));year_hist[year]=hist
        year_pmf[year]=hist/hist.sum()
    pmfs=[year_pmf[int(y)] for y in years]
    B,margins,mu,var,total=conditional_margins(pmfs,binidx,K)
    observed=np.bincount(binidx,weights=obs,minlength=16).astype(int);N=np.bincount(binidx,minlength=16)
    ordinary=np.zeros(16)
    for b,p in zip(binidx,pmfs):ordinary[b]+=np.arange(len(p))@p
    use=var>0
    Q=float(np.sum((observed[use]-mu[use])**2/var[use]))
    x=np.array([(d-1900)//10 for d in DECADES]);L=int(observed@x)
    E=exact_linear_mean(year_hist,year_counts,K)
    close(float(E),mu@x,'exact mean agrees with conditional margins')
    cuts=reflected_cuts(E,L)
    return {'rows':rows,'years':years,'bin_index':binidx,'K':K,'N':N,'observed':observed,'ordinary':ordinary,
            'mu':mu,'var':var,'pmfs':pmfs,'Q':Q,'L':L,'EL':E,'cuts':cuts,'mass':total,'year_counts':year_counts}


def field(d,names):
    for name in names:
        if name in d:return d[name]
    raise AssertionError('missing field '+str(names))


def audit_one(endpoint_index):
    cal,values,dateidx,groups,result=CTX
    name=ENDPOINTS[endpoint_index];reports=[]
    for source in SOURCES:
        p=predict(endpoint_index,source,cal,values,dateidx,groups)
        actual=result['groups'][name][source]
        require(actual['people']==len(p['rows']),'population N')
        require(actual['target_total']==p['K'],'observed total K')
        require(actual['person_ids_sha256']==hashlib.sha256(canonical(sorted(r['person_id'] for r in p['rows'])).encode()).hexdigest(),'person IDs hash')
        if 'calendar_year_counts' in actual:
            require({int(y):int(n) for y,n in actual['calendar_year_counts'].items()}==dict(p['year_counts']),'birthyear sample counts')
        require(len(actual['bins'])==16,'all16bins retained')
        adequate=[d for d in DECADES if all(sum(int(r['analysis_DOB'][:4])//10*10==d for r in groups[s])>=20 for s in SOURCES)]
        require(actual['local_decades']==adequate,'predeclared adequately sized plotting bins')
        for j,b in enumerate(actual['bins']):
            require(b['decade']==DECADES[j] and b['n']==int(p['N'][j]),'decade/N')
            close(b['observed_total'],p['observed'][j],'observed bin count')
            close(b['calendar_expected_total'],p['ordinary'][j],'ordinary calendar bin E')
            close(b['conditional_expected_total'],p['mu'][j],'conditional bin E')
            close(b['conditional_variance_total'],p['var'][j],'conditional bin variance')
            require(b['local_p_value_computed'] is False,'no local p added')
            if p['N'][j]:
                close(b['observed_mean'],p['observed'][j]/p['N'][j],'bin observed mean')
                close(b['calendar_expected_mean'],p['ordinary'][j]/p['N'][j],'bin ordinary mean')
                close(b['conditional_expected_mean'],p['mu'][j]/p['N'][j],'bin conditional mean')
        Q=actual['global_tests']['heterogeneity'];L=actual['global_tests']['linear']
        close(Q['observed_statistic'],p['Q'],'observed Q')
        require(int(field(L,['observed_integer_L','observed_L']))==p['L'],'observed L')
        E=Fraction(int(L['exact_expected_L_numerator']),int(L['exact_expected_L_denominator']))
        require(E==p['EL'],'exact grouped polynomial E(L)')
        require((L['lower_inclusive'],L['upper_inclusive'])==p['cuts'],'exact reflected linear tail')
        nz=p['N']>0;x=np.array([(d-1900)//10 for d in DECADES])[nz];sw=np.sqrt(p['N'][nz])
        X=np.column_stack([np.ones(len(x)),x])*sw[:,None]
        Y=np.column_stack([p['observed'][nz],p['ordinary'][nz],p['mu'][nz]])/p['N'][nz,None]
        slopes=np.linalg.lstsq(X,Y*sw[:,None],rcond=1e-12)[0][1]
        for key,value in [('raw_slope_score_per_decade',slopes[0]),('calendar_expected_slope_score_per_decade',slopes[1]),
                          ('conditional_expected_slope_score_per_decade',slopes[2]),('conditional_excess_slope_score_per_decade',slopes[0]-slopes[2])]:
            close(L[key],value,'weighted OLS slope '+key)
        close(actual['conditioning_total_probability_under_calendar'],p['mass'],'conditioning probability mass',1e-12)
        seed=202611160000+endpoint_index*1000+SOURCES.index(source)*100
        for t in [Q,L]:
            require(t['seed']==seed and t['replicates']==99999,'fixed main seed/R')
            ex=int(field(t,['extreme_replicates','extreme_count']))
            close(t['p_nominal'],(1+ex)/100000,'plus-one p',1e-15)
        qa=None
        if source=='strict':
            draws=sample_person_counts(p['pmfs'],p['bin_index'],p['K'],RQA,QA_SEED+endpoint_index*1000)
            use=p['var']>0;qs=np.sum((draws[:,use]-p['mu'][use])**2/p['var'][use],axis=1)
            linear=draws@np.array([(d-1900)//10 for d in DECADES])
            qt=1e-12*max(1,abs(p['Q']));pq=(1+np.count_nonzero(qs>=p['Q']-qt))/(RQA+1)
            lo,hi=p['cuts'];pl=(1+np.count_nonzero((linear<=lo)|(linear>=hi)))/(RQA+1)
            qa={}
            for key,pa,pb in [('heterogeneity',pq,Q['p_nominal']),('linear',pl,L['p_nominal'])]:
                tolerance=6*np.sqrt(pa*(1-pa)/RQA+pb*(1-pb)/99999)+.002
                require(abs(pa-pb)<=tolerance,'independent person sampler p '+name+'/'+key)
                qa[key]={'p_QA_only':float(pa),'p_main':float(pb),'agreement_tolerance':float(tolerance)}
            qa.update({'seed':QA_SEED+endpoint_index*1000,'replicates':RQA})
        reports.append({'endpoint':name,'source':source,'status':'PASS','people':len(p['rows']),'K':p['K'],
                        'all16_bin_counts_and_expectations_checked':True,'conditional_moments_checked':True,
                        'exact_linear_EL_and_cuts_checked':True,'independent_MC':qa})
    print(json.dumps({'audit_endpoint_completed':name,'status':'PASS'}),flush=True)
    return reports


def synthetic():
    raw=[[2,0,1,0,0,1],[1,2,1],[2,1],[0,1]]
    pmfs=[np.array(v,float)/sum(v) for v in raw];bins=np.array([7,7,8,9]);K=5
    outcomes=[]
    for v in itertools.product(*[range(len(p)) for p in pmfs]):
        if sum(v)!=K:continue
        w=Fraction(1)
        for j,c in enumerate(v):w*=Fraction(raw[j][c],sum(raw[j]))
        if w:outcomes.append((v,w))
    Z=sum(w for _,w in outcomes)
    _,marg,mu,var,_=conditional_margins(pmfs,bins,K)
    for b in range(16):
        enum={}
        for v,w in outcomes:
            c=sum(x for x,j in zip(v,bins) if j==b);enum[c]=enum.get(c,Fraction(0))+w/Z
        close(mu[b],sum(c*float(p) for c,p in enum.items()),'toy conditional mean')
        close(var[b],sum((c-mu[b])**2*float(p) for c,p in enum.items()),'toy conditional var')
    # The common exponential tilt cancels exactly for all conditioned outcomes.
    tilted=[]
    for v,w in outcomes:tilted.append(w*Fraction(3,2)**sum(v))
    Zt=sum(tilted)
    require(all(w/Z==t/Zt for (_,w),t in zip(outcomes,tilted)),'exponential tilt cancellation')
    # Grouped integer exact mean agrees with exhaustive finite enumeration.
    years=[1900,1901,1910,1920]
    EL=exact_linear_mean(dict(zip(years,[np.array(x) for x in raw])),Counter(years),K)
    exact=sum(sum(((y//10*10-1900)//10)*c for y,c in zip(years,v))*w/Z for v,w in outcomes)
    require(EL==exact,'exact grouped derivative linear mean')
    for obs in [-4,0,3,8]:
        lo,hi=reflected_cuts(EL,obs)
        for k in range(-20,30):require(((k<=lo)|(k>=hi))==(abs(Fraction(k)-EL)>=abs(Fraction(obs)-EL)),'rational reflection cuts')
    for Kedge in [0,3]:
        pp=[np.array([.4,.6]) for _ in range(3)];bi=np.array([7,8,9])
        _,_,_,v,_=conditional_margins(pp,bi,Kedge);require(np.all(v==0),'binary edge zero variance')
        d=sample_person_counts(pp,bi,Kedge,20,4);require(np.all(d.sum(axis=1)==Kedge),'binary edge sampler')
    require(int((0.0>=np.array([0.0,1.0])).sum())==1,'inverse CDF skips zero atom at u=0')
    try:person_suffix([np.array([1.,0.])],1)
    except AssertionError:pass
    else:raise AssertionError('impossible K not refused')
    d=sample_person_counts(pmfs,bins,K,10000,77)
    close(d.mean(axis=0),mu,'toy sampler means',.05)
    close(holm([.01,.04,.03]),[.03,.06,.06],'Holm fixture')
    return {'schema':'Nobel_decade_independent_synthetic_QA_v1','status':'PASS','real_cohort_files_read':False,
            'exhaustive_generalized_counts':True,'exponential_tilt_cancellation':True,
            'integer_grouped_derivative_EL':True,'exact_reflection_tails':True,'independent_person_sampler':True,
            'binary_edges_and_impossible_K':True,'fixed_strict_MC_replicates':RQA,'fixed_QA_seed_base':QA_SEED}


def run(args):
    global CTX
    synthetic()
    scope=json.loads(Path(args.scope).read_text());receipt=json.loads(Path(args.execution_receipt).read_text())
    require(receipt.get('remote_plan_and_code_verified_before_summary') is True,'remote execution verification')
    require(receipt['scope_sha256']==sha(args.scope),'scope hash')
    require(receipt['locked_file_manifest_sha256']==sha(args.locked_files),'manifest hash')
    manifest=json.loads(Path(args.locked_files).read_text())
    for p,h in manifest.items():require(sha(p)==h,'locked file changed '+p)
    require(str(Path(__file__).resolve().relative_to(Path.cwd())) in manifest,'auditor code not locked')
    require(sha(args.v4_zip)==V4_SHA and sha(args.calendar_npz)==CAL_SHA and sha(args.hidden_npz)==HID_SHA,'original input pins')
    require(not Path(args.output).exists(),'audit output exists')
    result=json.loads(Path(args.results).read_text())
    require(result['endpoint_order']==ENDPOINTS and result['source_order']==SOURCES,'fixed endpoint/source order')
    cal,values,dateidx,groups=input_data(args.v4_zip,args.calendar_npz,args.hidden_npz)
    CTX=(cal,values,dateidx,groups,result)
    if args.workers==1:reports=[audit_one(i) for i in range(25)]
    else:
        require(1<args.workers<=3,'audit workers bounded')
        with ProcessPoolExecutor(max_workers=args.workers,mp_context=mp.get_context('fork')) as ex:reports=list(ex.map(audit_one,range(25)))
    for source in SOURCES:
        rows=result['tests_by_source'][source];require(len(rows)==50,'full50 tests')
        q=holm([r['p_nominal'] for r in rows])
        for j,(t,p) in enumerate(zip(rows,q)):
            require(t['endpoint_id']==ENDPOINTS[j//2],'test endpoint order')
            close(t['p_Holm50_reference'],p,'Holm50',1e-14)
            require(t['primary_exploratory_family']==(source=='strict'),'strict-only exploratory family')
            require(t['reject_primary_Holm50_0_05']==bool(source=='strict' and p<=.05),'strict-only rejection flag')
            global_name='heterogeneity' if j%2==0 else 'linear'
            require(t['kind']==global_name,'global test order')
            actual=result['groups'][ENDPOINTS[j//2]][source]['global_tests'][global_name]
            close(t['p_nominal'],actual['p_nominal'],'flattened p equals case p',1e-15)
            close(actual['p_Holm50_reference'],p,'case-level Holm50',1e-14)
            require(actual['reject_primary_Holm50_0_05']==t['reject_primary_Holm50_0_05'],'case rejection flag')
    out={'schema':'Nobel_decade_independent_QA_v1','status':'PASS','cases':[r for endpoint in reports for r in endpoint],
         'all25_endpoints_both_sources_checked':True,'all16_bins_checked':True,'conditional_moments_and_exact_EL_checked':True,
         'fixed50_Holm_each_source_checked':True,'independent_sampler':'person_suffix_conditional_discrete',
         'strict_QA_replicates_per_endpoint':RQA,'QA_seed_base':QA_SEED,
         'hashes':{'results':sha(args.results),'auditor':sha(__file__),'scope':sha(args.scope),'receipt':sha(args.execution_receipt),
                   'V4':sha(args.v4_zip),'calendar':sha(args.calendar_npz),'hidden':sha(args.hidden_npz)}}
    Path(args.output).write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'status':'PASS','output':args.output,'results_sha256':sha(args.results),'QA_sha256':sha(args.output)}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--synthetic-qa',action='store_true')
    for name in ['scope','locked-files','execution-receipt','v4-zip','calendar-npz','hidden-npz','results','output']:p.add_argument('--'+name)
    p.add_argument('--workers',type=int,default=3);args=p.parse_args()
    if args.synthetic_qa:print(json.dumps(synthetic(),ensure_ascii=False,indent=2))
    else:run(args)
