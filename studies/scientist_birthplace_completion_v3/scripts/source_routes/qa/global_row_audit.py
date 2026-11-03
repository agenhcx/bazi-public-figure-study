"""Independent dynamic v3 comparison against the fixed direct global v2 master."""
from pathlib import Path
import argparse
import collections
import gzip
import hashlib
import json

ROOT=Path('/workspace/scratch/7e8aa4e0d4af')
QA=ROOT/'academy_v3_workers/qa'
BASE=ROOT/'uk_birthplace_checkout/studies/scientist_birthplace_completion_v2/outputs/birthplace_rows.jsonl.gz'
BASE_SHA='2b7897d0c4e2655ecb6f10311e1bdf7b06b8eeae3f181e9bebe92cbc7f066ee0'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def jl(p):
    b=p.read_bytes()
    if p.suffix=='.gz':b=gzip.decompress(b)
    return [json.loads(x) for x in b.splitlines() if x]
def key(r):return r['cohort'],r['record_id']
def canon(x):return json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()

p=argparse.ArgumentParser()
p.add_argument('--study',required=True,type=Path)
p.add_argument('--facts',type=Path)
a=p.parse_args()
assert sha(BASE)==BASE_SHA
before=jl(BASE)
facts=jl(a.facts or a.study/'inputs/new_birthplace_facts.jsonl.gz')
checked=json.loads((QA/'fields_source_facts_checked.json').read_text())+json.loads((QA/'nas_source_facts_checked.json').read_text())
source_checked={key(r):r for r in checked}
assert {key(r) for r in facts}==set(source_checked)
for fact in facts:
    checked_fact=source_checked[key(fact)]
    for column in ['name','native_dob','raw_birthplace','source_grade','source_sha256','evidence_quote','source_author']:
        assert fact[column]==checked_fact[column],(key(fact),column)
    assert checked_fact['source_url'] in fact['source_urls']
final=jl(a.study/'outputs/birthplace_rows.jsonl.gz')
b={key(r):r for r in before};f={key(r):r for r in final}
assert len(before)==len(b)==len(final)==len(f)==11094
assert b.keys()==f.keys()
fk={key(r) for r in facts}
assert len(fk)==len(facts)
assert all(c in {'Fields_main','NAS'} for c,_ in fk)
assert all(b[k]['hemisphere']=='unknown' for k in fk)
changed={k for k in b if canon(b[k])!=canon(f[k])}
assert changed==fk,(changed,fk)
allowed={'hemisphere','raw_birthplace','birthplace_source_grade','birthplace_source_url',
    'birthplace_source_urls','birthplace_evidence_kind','birthplace_evidence_excerpt',
    'birthplace_locator','birthplace_source_sha256','reason','northern_birthplace_candidate',
    'southern_birthplace_separate','geographic_conflict_pending_review','birthplace_claim_excerpt',
    'locality_resolution'}
diff=[]
for k in sorted(changed):
    old,new=b[k],f[k]
    missing=set(old)-set(new)
    assert not missing,(k,missing)
    altered={c for c in old if canon(old[c])!=canon(new[c])}
    assert not altered-allowed,(k,altered-allowed)
    assert new['country']==old['country'] and canon(new['lat'])==canon(old['lat']) and canon(new['lon'])==canon(old['lon'])
    fact=next(x for x in facts if key(x)==k)
    assert new['raw_birthplace']==fact['raw_birthplace']
    assert new['birthplace_source_grade']==fact['source_grade']
    if fact['source_grade']=='S2':assert 'first_party' not in new['birthplace_evidence_kind'],(k,'S2 signed biography incorrectly labelled first party')
    assert new['dob']==fact['native_dob']==old['dob']
    if 'hemisphere' in fact:assert new['hemisphere']==fact['hemisphere']
    diff.append({'cohort':k[0],'record_id':k[1],'name':new['name'],
        'preexisting_fields_changed':sorted(altered),'fields_added':sorted(set(new)-set(old)),
        'raw_birthplace':new['raw_birthplace'],'hemisphere':new['hemisphere'],
        'native_dob':new['dob'],'birthplace_source_grade':new['birthplace_source_grade']})
for r in final:
    old=b[key(r)]
    assert r['country']==old['country'] and canon(r['lat'])==canon(old['lat']) and canon(r['lon'])==canon(old['lon'])
uk=[r for r in final if r['cohort']=='UK_Royal_Society']
assert len(uk)==4983 and all(canon(r)==canon(b[key(r)]) for r in uk)
overlays=[r for r in before if 'v2_birthplace_fact_evidence' in r]
assert len(overlays)==3 and all(canon(r)==canon(f[key(r)]) for r in overlays)
assert all(canon(r)==canon(b[key(r)]) for r in final if r['cohort'] not in {'Fields_main','NAS'})
assert all(r['dob']=='' and r.get('accepted_gregorian_dob','')=='' for r in final if r['cohort']=='CAS')
assert all(r['dob']=='' for r in final if r['cohort']=='Nobel_science')
counts={c:{'records':sum(r['cohort']==c for r in final),
    'hemispheres':dict(collections.Counter(r['hemisphere'] for r in final if r['cohort']==c))} for c in sorted({r['cohort'] for r in final})}
assert len(counts)==8
assert all(counts[c]['records']==sum(r['cohort']==c for r in before) for c in counts)
report={'status':'PASS','direct_baseline_sha256':BASE_SHA,
    'global_sha256':sha(a.study/'outputs/birthplace_rows.jsonl.gz'),
    'records':len(final),'cohorts':counts,'key':'(cohort, record_id)',
    'new_facts':len(facts),'changed_records':len(changed),'changes':diff,
    'unchanged_direct_baseline_objects':len(final)-len(changed),
    'all_preexisting_non_geographic_fields_preserved_type_sensitive':True,
    'countries_and_coordinates_all_preserved':True,'UK_opaque_equal_objects':len(uk),
    'selected_fact_payloads_match_checked_source_facts':True,
    'S2_signed_memoirs_not_labelled_first_party':True,
    'v2_award_overlay_objects_opaque_equal':3,'CAS_1230_accepted_Gregorian_blank':True,
    'Nobel_655_native_DOB_blank_and_scope_flags_preserved':True,
    'cross_cohort_deduplication':False,'total_hemispheres':dict(collections.Counter(r['hemisphere'] for r in final))}
(QA/'global_row_qa_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'status':'PASS','records':len(final),'new_facts':len(facts),'changed':len(changed)}))
