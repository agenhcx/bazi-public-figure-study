"""Compare a frozen assembled global JSONL against the independently composed baseline."""
from pathlib import Path
import argparse
import collections
import gzip
import hashlib
import json

ROOT=Path('/workspace/scratch/7e8aa4e0d4af')
OUT=ROOT/'academy_next_workers/qa'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rows(p):
    b=p.read_bytes()
    if p.suffix=='.gz':b=gzip.decompress(b)
    return [json.loads(x) for x in b.splitlines() if x]
def key(r):return (r['cohort'],r['record_id'])
def canon(r):return json.dumps(r,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()

p=argparse.ArgumentParser()
p.add_argument('global_rows',type=Path)
a=p.parse_args()
v1p=ROOT/'uk_birthplace_checkout/studies/academy_birthplace_screen_v1/outputs/birthplace_rows.jsonl.gz'
ukp=ROOT/'uk_birthplace_checkout/studies/royal_society_birthplace_completion_v10/outputs/uk_birthplace_rows.jsonl.gz'
assert sha(v1p)=='2ad00462255629a603bc4a95aa64158141b5a9b105359baece528a163aa93d92'
assert sha(ukp)=='e44f6dc02cc0cafece9b792164f016da0f08de5736ac62442d176d45b19a5799'
v1,uk,final=rows(v1p),rows(ukp),rows(a.global_rows)
composed=[x for x in v1 if x['cohort']!='UK_Royal_Society']+uk
before={key(x):x for x in composed}
after={key(x):x for x in final}
assert len(composed)==len(before)==len(final)==len(after)==11094
assert before.keys()==after.keys()
assert len(uk)==4983
assert all(canon(x)==canon(after[key(x)]) for x in uk)
changed={k for k in before if canon(before[k])!=canon(after[k])}
expected={('Fields_main','fields-12ddab1dd74af07f'),('Fields_main','fields-c847084f96ea991e'),('Nobel_science','1052')}
assert changed==expected,(changed,expected)
allowed_existing_changes={'raw_birthplace','hemisphere','reason','birthplace_evidence_kind',
    'birthplace_source_grade','birthplace_source_url','birthplace_source_sha256',
    'birthplace_locator','birthplace_evidence_excerpt','northern_birthplace_candidate',
    'locality_resolution'}
diffs=[]
for k in sorted(changed):
    b,f=before[k],after[k]
    altered={x for x in b if x not in f or canon(b[x])!=canon(f[x])}
    assert not altered-allowed_existing_changes,(k,altered-allowed_existing_changes)
    assert not set(b)-set(f),(k,'preexisting fields deleted')
    assert b['hemisphere']=='unknown' and f['hemisphere']=='north'
    assert f['birthplace_source_grade']=='S1' and f['lat'] is None and f['lon'] is None
    assert f['country']==b['country']==''
    for n in f:
        if n not in b and any(s in n.lower() for s in ['dob','calendar','eligib','identity','qid','date']):
            assert not any(s in n.lower() for s in ['accepted_gregorian','native_dob','canonical_dob','dob_group','dob_tier']), (k,n,'new DOB field')
    diffs.append({'cohort':k[0],'record_id':k[1],'name':f['name'],
        'preexisting_fields_changed':sorted(altered),'fields_added':sorted(set(f)-set(b)),
        'raw_birthplace':f['raw_birthplace'],'native_dob':f['dob']})
assert after[('Fields_main','fields-12ddab1dd74af07f')]['raw_birthplace']=='New Delhi, India'
assert after[('Fields_main','fields-c847084f96ea991e')]['raw_birthplace']=='Canada'
assert after[('Nobel_science','1052')]['raw_birthplace']=='Los Angeles, CA, USA'
assert all(r.get('dob','')=='' and r.get('accepted_gregorian_dob','')=='' for r in final if r['cohort']=='CAS')
assert all(r['dob']=='' for r in final if r['cohort']=='Nobel_science')
assert all(canon(r)==canon(before[key(r)]) for r in final if r['cohort'] not in {'Fields_main','Nobel_science'})
counts={c:dict(collections.Counter(x['hemisphere'] for x in final if x['cohort']==c)) for c in sorted({x['cohort'] for x in final})}
assert counts['UK_Royal_Society']=={'north':4155,'unknown':645,'south':183}
assert counts['Fields_main']=={'north':57,'south':4,'unknown':2}
assert counts['Nobel_science']=={'north':634,'south':21}
assert dict(collections.Counter(x['hemisphere'] for x in final))=={'unknown':1766,'north':9077,'south':251}
report={'status':'PASS','global_path':str(a.global_rows.resolve()),'global_sha256':sha(a.global_rows),
    'row_count':len(final),'cohort_count':len(counts),'key':'(cohort, record_id)',
    'cross_cohort_deduplication':False,'uk_objects_canonical_byte_equivalent':4983,
    'unchanged_composed_baseline_objects':len(final)-len(changed),'changed':diffs,
    'all_preexisting_non_geographic_fields_unchanged':True,'all_preexisting_countries_and_coordinates_unchanged':True,
    'cas_1230_dob_and_accepted_gregorian_blank':True,'nobel_655_native_dob_blank':True,
    'baseline_identity_qid_lookup_quarantine_home_flags_unchanged':True,
    'cohort_hemisphere_counts':counts,
    'total_hemisphere_counts':dict(collections.Counter(x['hemisphere'] for x in final))}
(OUT/'global_row_qa_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'status':'PASS','rows':len(final),'changed':len(changed),'counts':report['total_hemisphere_counts']}))
