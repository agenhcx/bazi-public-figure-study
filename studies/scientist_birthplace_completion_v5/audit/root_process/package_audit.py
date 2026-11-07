from pathlib import Path
import hashlib,json,shutil
root=Path('/workspace/scratch/7e8aa4e0d4af');workers=root/'academy_v5_workers';study=root/'uk_birthplace_checkout/studies/scientist_birthplace_completion_v5'
excluded={'__pycache__','raw','raw_transient'}
removed=[];copies=[]
private_headers={'set-cookie','cookie','authorization','proxy-authorization','x-client-ip','x-openai-public-ip','x-forwarded-for','x-real-ip','x-envoy-external-address'}
def clean(obj,path=''):
 if isinstance(obj,dict):
  out={}
  for k,v in obj.items():
   p=path+'/'+k
   if k.lower() in private_headers:removed.append(p)
   else:out[k]=clean(v,p)
  return out
 if isinstance(obj,list):return [clean(v,path+'/'+str(i)) for i,v in enumerate(obj)]
 return obj
sources=[(workers/'vol75','vol75'),(workers/'vol76/retained','vol76'),(workers/'geography','geography'),(workers/'qa','independent_qa')]
for src,tag in sources:
 for p in sorted(src.rglob('*')):
  if not p.is_file() or any(x in excluded for x in p.relative_to(src).parts):continue
  dest=study/'audit'/tag/p.relative_to(src);dest.parent.mkdir(parents=True,exist_ok=True);data=p.read_bytes();before=len(removed)
  if p.suffix=='.json':
   obj=clean(json.loads(data))
   if len(removed)>before:
    record={'file':str(dest.relative_to(study)),'original_metadata_sha256':hashlib.sha256(data).hexdigest(),'removed_paths':removed[before:]}
    copies.append(record)
    if isinstance(obj,dict):obj['distribution_metadata_note']=record
    data=(json.dumps(obj,ensure_ascii=False,indent=2)+'\n').encode()
  dest.write_bytes(data)
report={'metadata_copies':copies,'body_bytes_or_hashes_changed':False,'all_other_source_files_copied_byte_identically':True,'raw_source_HTML_images_and_derived_fulltext_excluded':True,'source_worker_manifests':'pre-distribution snapshot inventories; root MANIFEST.sha256 is authoritative for distributed paths and sanitized metadata','process_scripts':'audit snapshots depend on original scratch paths, not standalone entry points'}
(study/'audit/distribution_metadata_sanitization.json').write_text(json.dumps(report,indent=2)+'\n')
budget={'source_lanes':{'each_authorized_max':{'discovery_queries':2,'index_navigations':3,'body_requests_including_images':6},'actual_vol75':{'discovery_queries':1,'index_navigations':1,'chapter_HTML':4,'page_images':0,'retries':0},'actual_vol76':{'discovery_queries':1,'index_navigations':1,'chapter_HTML':1,'page_images':1,'retries':0},'Vol76_parent_steering':'Woolsey observed image follow-up only, then freeze; 3 other observed TOC routes pending unread','retrieval_deadline':'about8minutes each; actual acquisition ended inside deadline; freeze times recorded separately'},'geography':{'authorized_and_actual_Nobel_known_API_URL_captures':1,'new_name_exact_place_queries':1,'query_names':['Berlin','Detroit'],'prior_NYC_Colorado_query_repeated':False,'retries':0},'stop_rules':'429=>stop; two consistent403/503=>stop; none encountered','all_new_requests_have_preintent':True}
(study/'audit/request_scope_and_budget.json').write_text(json.dumps(budget,indent=2)+'\n')
print(json.dumps({'copied_studies':len(sources),'sanitized_metadata_files':len(copies),'removed_paths_only_no_values':copies},indent=2))
