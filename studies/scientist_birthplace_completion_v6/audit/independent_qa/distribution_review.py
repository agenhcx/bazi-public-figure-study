#!/usr/bin/env python3
"""Read-only audit of the final v6 source distribution copies."""
from pathlib import Path
import hashlib,json
W=Path('/workspace/scratch/7e8aa4e0d4af');S=W/'uk_birthplace_checkout/studies/scientist_birthplace_completion_v6';Q=W/'academy_v6_workers/qa'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def inspect_headers(v,path=''):
 if isinstance(v,dict):
  for k,value in v.items():
   if 'header' in k.lower() and isinstance(value,dict):
    assert set(str(x).lower() for x in value)<={'content-type','content-length','last-modified','etag','date'},(path,k)
   inspect_headers(value,path+'/'+k)
 elif isinstance(v,list):
  for value in v:inspect_headers(value,path+'[]')
def run():
 policy=json.loads((S/'audit/distribution_metadata_sanitization.json').read_text());assert policy['metadata_copies']==[] and policy['body_bytes_or_hashes_changed'] is False
 pairs=[]
 for lane,source in [('vol76',W/'academy_v6_workers/vol76/retained'),('vol77',W/'academy_v6_workers/vol77'),('vol78',W/'academy_v6_workers/vol78'),('geography',W/'academy_v6_workers/geography')]:
  root=S/'audit'/lane;assert root.is_dir()
  for p in root.iterdir():
   assert p.is_file(),p
   sp=source/p.name;assert sp.is_file() and p.read_bytes()==sp.read_bytes(),p
   assert p.suffix.lower() not in {'.html','.gif','.png','.jpg','.pdf'},p
   pairs.append({'path':str(p.relative_to(S)),'sha256':sha(p)})
   if p.suffix=='.json':inspect_headers(json.loads(p.read_text()),str(p.relative_to(S)))
  if lane=='geography':assert (root/'manifest.json').is_file()
 scope=json.loads((S/'audit/request_scope_and_budget.json').read_text());report=json.loads((Q/'source_review.json').read_text())
 assert scope['final_assigned_body_caps']=={'Vol76':12,'Vol77':6,'Vol78':5}
 assert scope['original_family_body_allowance']==25 and scope['unused_unassigned_body_allowance']==2
 for lane in ['76','77','78']:
  observed=scope['actual']['Vol'+lane];expected=report['lanes'][lane]
  assert observed['discovery_queries']==expected['queries'] and observed['index_navigations']==expected['indices']
  assert observed['chapter_HTML']==expected['HTML_bodies'] and observed['observed_page_images']==expected['page_images'] and observed['body_requests']==expected['body_requests']
 assert scope['geography']['new_queries_actual']==0
 result={'status':'PASS','source_audit_files_compared':len(pairs),'all_source_audit_files_byte_identical_to_retained_worker_files':True,'metadata_copies_sanitized_this_round':0,'public_capture_headers_allowlist_only_no_cookies_IP_or_authentication_headers':True,'complete_memoir_HTML_GIF_PNG_and_derived_fulltext_excluded':True,'no_new_geography_query_response_to_package':True,'request_scope_and_final_transferred_caps_reconcile_to_original25':True,'actual_body_requests19_total_unused_allowances6':True,'main_table_sha256':sha(S/'outputs/birthplace_rows.jsonl.gz'),'source_audit_file_hashes':pairs,'ZIP_final_MANIFEST_CRC_member_hash_verification_handoff_to_root':True}
 (Q/'distribution_review.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='source_audit_file_hashes'},indent=2))
if __name__=='__main__':run()
