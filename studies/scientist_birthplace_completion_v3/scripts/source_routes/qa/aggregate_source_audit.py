from pathlib import Path
import hashlib
import json

QA=Path('/workspace/scratch/7e8aa4e0d4af/academy_v3_workers/qa')
def load(n):return json.loads((QA/n).read_text())
def sha(n):return hashlib.sha256((QA/n).read_bytes()).hexdigest()
fields=load('fields_source_qa_report.json');nas=load('nas_source_qa_report.json')
assert fields['status']==nas['status']=='PASS'
f=load('fields_source_facts_checked.json');n=load('nas_source_facts_checked.json')
assert len(f)==2 and len(n)==7
assert len({(x['cohort'],x['record_id']) for x in f+n})==9
report={'status':'PASS','accepted_facts':len(f+n),'source_grade_counts':{'S1':len(f),'S2':len(n)},
        'held_not_accepted':nas['held_candidate'],
        'fields':fields,'nas':nas,'new_QA_network_requests':0,
        'facts':[{'cohort':x['cohort'],'record_id':x['record_id'],'source_grade':x['source_grade'],'source_sha256':x['source_sha256']} for x in f+n],
        'report_sha256':{p:sha(p) for p in ['fields_source_qa_report.json','nas_source_qa_report.json']}}
(QA/'source_qa_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'status':'PASS','accepted_facts':len(f+n),'held':1}))
