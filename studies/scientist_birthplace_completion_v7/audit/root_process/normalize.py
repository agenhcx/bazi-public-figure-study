from pathlib import Path
from collections import defaultdict,Counter
from copy import deepcopy
import json,gzip,hashlib
root=Path('/workspace/scratch/7e8aa4e0d4af');w=root/'academy_v7_workers';s=root/'uk_birthplace_checkout/studies/scientist_birthplace_completion_v7'
def read(p):return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rowsha(r):return hashlib.sha256(json.dumps(r,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
assert json.loads((w/'qa/source_review.json').read_text())['status']=='PASS'
sourcepaths=[w/x/'retained_facts.jsonl' for x in ['vol79','vol80','nobel_physics','nobel_chem_med']]
groups=defaultdict(list)
for p in sourcepaths:
 for i,f in enumerate(read(p)):
  ref={'source_fact_file':str(p.relative_to(root)),'source_fact_file_sha256':sha(p),'row_index_zero_based':i,'row_canonical_json_sha256':rowsha(f),'source_grade':f['source_grade'],'source_url':f['source_url'],'source_sha256':f['source_sha256'],'raw_birthplace':f['raw_birthplace']}
  groups[(f['cohort'],f['record_id'])].append((f,ref))
geo=read(w/'geography/geographic_reviews.jsonl');gm={(g['cohort'],g['record_id']):g for g in geo};assert len(gm)==len(geo)==len(groups) and set(gm)==set(groups)
facts=[]
for key,supports in sorted(groups.items()):
 supports.sort(key=lambda x:({'S1':0,'S2':1,'S3':2}[x[0]['source_grade']],x[0]['source_url']))
 original=supports[0][0];f=deepcopy(original);g=gm[key]
 assert all(o['native_dob']==f['native_dob'] for o,ref in supports)
 f['geography']=deepcopy(g);f['hemisphere']=g['hemisphere'];f['geographic_basis']=g['geographic_basis'];f['identity_independent_QA_passed']=True
 f['evidence_quote']=f.get('evidence_quote',f.get('birthplace_evidence_excerpt'))
 f['evidence_locator']=f.get('evidence_locator',f.get('locator',f.get('source_locator')))
 f['source_sha256']=f.get('source_sha256',f.get('original_bytes_sha256',f.get('capture',{}).get('original_http_response_bytes_sha256')))
 f['source_urls']=list(dict.fromkeys(u for o,ref in supports for u in o.get('source_urls',[o['source_url']])))
 f['source_capture_kind']=f.get('source_capture_kind',f.get('capture_kind',f.get('capture',{}).get('capture_kind')))
 f['source_capture_scope']=f.get('source_capture_scope',f.get('capture_scope',f.get('capture',{}).get('capture_scope')))
 f['fact_role']='new_explicit_official_birthplace' if f['source_grade']=='S1' else 'new_explicit_memoir_birthplace'
 f['source_observations']=[ref for o,ref in supports];f['source_observation_count']=len(supports)
 f['additional_source_supports']=[deepcopy(o) for o,ref in supports[1:]]
 f['primary_source_selection']='S1 official structured birth.place preferred when independently matched and all geographical supports consistent; each other observation retained verbatim; one existing NAS key remains one row'
 f['root_merge_stage']='all_source_observations_and_geography_reviewed';f['root_QA_and_geography_pending']=False
 assert f['source_grade'] in {'S1','S2'} and f['evidence_quote'] and f['evidence_locator'] and f['source_sha256']
 assert all(len(o.get('evidence_quote',o.get('birthplace_evidence_excerpt','')).split())<=25 for o,ref in supports)
 facts.append(f)
data=''.join(json.dumps(f,ensure_ascii=False,sort_keys=True)+'\n' for f in facts).encode();(s/'inputs/new_birthplace_facts.jsonl.gz').write_bytes(gzip.compress(data,mtime=0))
report={'unique_updated_NAS_keys':len(facts),'retained_source_observations':sum(len(v) for v in groups.values()),'source_observation_grade_counts':dict(Counter(o['source_grade'] for values in groups.values() for o,ref in values)),'primary_source_grade_counts':dict(Counter(f['source_grade'] for f in facts)),'multi_support_keys':[{'cohort':k[0],'record_id':k[1],'observations':len(v)} for k,v in groups.items() if len(v)>1],'source_and_geographic_input_sha256':{str(p.relative_to(root)):sha(p) for p in sourcepaths+[w/'geography/geographic_reviews.jsonl']},'normalization_only':'alias fields and deterministic primary-source selection; additional source observations retained verbatim and hashed; no statistical deduplication','geographic_hemispheres':dict(Counter(f['hemisphere'] for f in facts))}
(s/'audit/root_integration.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,indent=2))
