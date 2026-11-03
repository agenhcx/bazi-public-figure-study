"""Freeze independent QA facts about the fixed direct global v2 baseline."""
from pathlib import Path
import collections
import gzip
import hashlib
import json

ROOT=Path('/workspace/scratch/7e8aa4e0d4af')
QA=ROOT/'academy_v3_workers/qa'
BASE=ROOT/'uk_birthplace_checkout/studies/scientist_birthplace_completion_v2/outputs/birthplace_rows.jsonl.gz'
SHA='2b7897d0c4e2655ecb6f10311e1bdf7b06b8eeae3f181e9bebe92cbc7f066ee0'
def canon(x):return json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()
raw=BASE.read_bytes()
assert hashlib.sha256(raw).hexdigest()==SHA
rows=[json.loads(x) for x in gzip.decompress(raw).splitlines() if x]
assert len(rows)==len({(r['cohort'],r['record_id']) for r in rows})==11094
cohorts=sorted({r['cohort'] for r in rows})
assert len(cohorts)==8
counts={c:{'records':sum(r['cohort']==c for r in rows),'hemispheres':dict(collections.Counter(r['hemisphere'] for r in rows if r['cohort']==c))} for c in cohorts}
assert counts['UK_Royal_Society']=={'records':4983,'hemispheres':{'north':4155,'unknown':645,'south':183}}
assert counts['Nobel_science']=={'records':655,'hemispheres':{'north':634,'south':21}}
assert counts['Fields_main']=={'records':63,'hemispheres':{'north':57,'south':4,'unknown':2}}
assert counts['NAS']=={'records':2242,'hemispheres':{'unknown':574,'north':1637,'south':31}}
assert all(r['dob']=='' and r.get('accepted_gregorian_dob','')=='' for r in rows if r['cohort']=='CAS')
assert all(r['dob']=='' for r in rows if r['cohort']=='Nobel_science')
overlays=[r for r in rows if 'v2_birthplace_fact_evidence' in r]
assert len(overlays)==3
assert {(r['cohort'],r['record_id']) for r in overlays}=={('Fields_main','fields-12ddab1dd74af07f'),('Fields_main','fields-c847084f96ea991e'),('Nobel_science','1052')}
report={'status':'PASS','direct_baseline':str(BASE),'sha256':SHA,'records':len(rows),'cohorts':counts,
        'unit':'cohort records; no cross-cohort deduplication',
        'canonical_cohort_object_sha256':{c:hashlib.sha256(b'\n'.join(canon(r) for r in rows if r['cohort']==c)).hexdigest() for c in cohorts},
        'v2_three_award_overlay_records':[{'cohort':r['cohort'],'record_id':r['record_id'],'object_sha256':hashlib.sha256(canon(r)).hexdigest()} for r in overlays],
        'CAS_accepted_Gregorian_blank':1230,'Nobel_native_DOB_blank':655,
        'new_facts_count':'dynamic; pending source freezes'}
QA.mkdir(parents=True,exist_ok=True)
(QA/'baseline_qa_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'status':'PASS','records':len(rows),'cohorts':len(cohorts),'v2_overlays':len(overlays)}))
