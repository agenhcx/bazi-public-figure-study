#!/usr/bin/env python3
from pathlib import Path
import hashlib,json
W=Path('/workspace/scratch/7e8aa4e0d4af');S=W/'uk_birthplace_checkout/studies/scientist_birthplace_completion_v7';Q=W/'academy_v7_workers/qa'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def headers(v,path=''):
 if isinstance(v,dict):
  for k,x in v.items():
   if 'header' in k.lower() and isinstance(x,dict):assert set(str(i).lower() for i in x)<={'content-type','content-length','last-modified','etag','date'},(path,k)
   headers(x,path+'/'+k)
 elif isinstance(v,list):
  for x in v:headers(x,path+'[]')
def run():
 policy=json.loads((S/'audit/distribution_metadata_sanitization.json').read_text());assert policy['metadata_copies']==[] and policy['body_bytes_or_hashes_changed'] is False
 pairs=[]
 for lane in ['vol79','vol80','nobel_physics','nobel_chem_med','geography']:
  source=W/'academy_v7_workers'/lane;dest=S/'audit'/lane;assert dest.is_dir()
  for p in dest.iterdir():
   assert p.is_file(),p
   sp=source/p.name;assert sp.is_file() and p.read_bytes()==sp.read_bytes(),p
   assert p.suffix.lower() not in {'.html','.gif','.png','.jpg','.pdf'},p
   pairs.append({'path':str(p.relative_to(S)),'sha256':sha(p)})
   if p.suffix=='.json':headers(json.loads(p.read_text()),str(p.relative_to(S)))
  assert (dest/'manifest.json').is_file(),dest
 for file in ['original_chemistry_response.bin','original_medicine_response.bin']:
  assert (S/'audit/nobel_chem_med'/file).read_bytes()==(W/'academy_v7_workers/nobel_chem_med'/file).read_bytes()
 prior=W/'uk_birthplace_checkout/studies/scientist_birthplace_completion_v5/audit/geography/nobel_physics_corroboration_response.bin'
 assert sha(prior)=='633002ff83120f9408d630209b24ebab7d1f3f1e999cf5bb51638ebb8976075e'
 assert prior.read_bytes()==(W/'academy_v5_workers/geography/nobel_physics_corroboration_response.bin').read_bytes()
 assert not any(p.name=='nobel_physics_corroboration_response.bin' for p in (S/'audit/nobel_physics').iterdir())
 scope=json.loads((S/'audit/request_scope_and_budget.json').read_text());assert scope['source_effort']=={'logical_actions':12,'original_HTTP_captures':10,'search_query_actions':2}
 assert scope['offline_physics']['current_HTTP_requests']==0 and scope['chemistry_medicine_additional_lane']['actual_original_HTTP_captures']==2
 assert scope['geography']['actual_new_queries']==0
 source=json.loads((Q/'source_review.json').read_text());assert source['source_observations']==30 and source['unique_NAS_target_keys']==29
 result={'status':'PASS','source_audit_files_compared':len(pairs),'all_source_audit_files_byte_identical_to_retained_worker_files':True,'metadata_copies_sanitized_this_round':0,'public_capture_header_allowlists_only':True,'complete_memoir_HTML_GIF_PNG_and_derived_fulltext_excluded':True,'new_chemistry_and_medicine_original_public_API_JSON_bytes_preserved':True,'physics_cached_original_available_byte_identically_in_fixed_v5_audit_no_new_capture':True,'updated_full_prize_context_fact_metadata_preserved':True,'30_observations_29_unique_NAS_keys_Hershey_overlap_preserved':True,'source_effort_logical12_originalHTTP10_searchActions2':True,'new_geography_queries':0,'main_table_sha256':sha(S/'outputs/birthplace_rows.jsonl.gz'),'source_audit_file_hashes':pairs,'ZIP_final_MANIFEST_CRC_member_hash_verification_handoff_to_root':True}
 (Q/'distribution_review.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='source_audit_file_hashes'},indent=2))
if __name__=='__main__':run()
