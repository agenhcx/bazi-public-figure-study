from pathlib import Path
import json,gzip,hashlib
root=Path('/workspace/scratch/7e8aa4e0d4af');w=root/'academy_v5_workers';s=root/'uk_birthplace_checkout/studies/scientist_birthplace_completion_v5'
def read(p):return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]
for p in [w/'qa/source_review.json',w/'qa/anderson_corroboration_review.json']:
 assert json.loads(p.read_text())['status']=='PASS'
sourcepaths=[w/'vol75/retained_facts.jsonl',w/'vol76/retained/facts.jsonl',w/'geography/anderson_geographic_qualification_fact.jsonl']
facts=[f for p in sourcepaths for f in read(p)];assert len(facts)==6
geo=read(w/'geography/geographic_reviews.jsonl');assert len(geo)==6
gm={(r['cohort'],r['record_id']):r for r in geo};assert len(gm)==6
for f in facts:
 g=gm[(f['cohort'],f['record_id'])];f['geography']=g;f['hemisphere']=g['hemisphere'];f['geographic_basis']=g['geographic_basis'];f['identity_independent_QA_passed']=True
 f['evidence_quote']=f.get('evidence_quote',f.get('birthplace_evidence_excerpt'))
 f['evidence_locator']=f.get('evidence_locator',f.get('locator',f.get('source_locator')))
 f['source_sha256']=f.get('source_sha256',f.get('original_bytes_sha256',f.get('capture',{}).get('original_http_response_bytes_sha256')))
 f['source_urls']=f.get('source_urls',[f['source_url']]+([f['source_page_image_url']] if 'source_page_image_url' in f else []))
 f['source_capture_kind']=f.get('capture_kind',f.get('capture',{}).get('capture_kind'))
 f['source_capture_scope']=f.get('capture_scope',f.get('capture',{}).get('capture_scope'))
 f['fact_role']='prior_birthplace_qualification' if f['source_grade']=='S1' else 'new_explicit_memoir_birthplace'
 f['root_merge_stage']='source_and_geography_reviews_complete'
 f['root_QA_and_geography_pending']=False
 assert f['evidence_quote'] and f['evidence_locator'] and f['source_sha256']
 assert len(f['evidence_quote'].split())<=25
facts.sort(key=lambda r:(r['cohort'],r['record_id']))
data=''.join(json.dumps(f,ensure_ascii=False,sort_keys=True)+'\n' for f in facts).encode();(s/'inputs/new_birthplace_facts.jsonl.gz').write_bytes(gzip.compress(data,mtime=0))
(s/'audit').mkdir(exist_ok=True)
report={'facts':6,'S2_new_memoir_facts':5,'S1_prior_place_qualifications':1,'source_and_geographic_input_sha256':{str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sourcepaths+[w/'geography/geographic_reviews.jsonl']},'normalization_only':'field-name aliases, explicit fact-role, source+geography binding, root pass marker; native/versioned evidence unchanged','geographic_hemispheres':{x:sum(f['hemisphere']==x for f in facts) for x in ['north','south','unknown']}}
(s/'audit/root_integration.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(report,indent=2))
