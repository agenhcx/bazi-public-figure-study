from pathlib import Path
from datetime import datetime,timezone
import json,gzip,hashlib,urllib.request,urllib.error
P=Path(__file__).parent;now=lambda:datetime.now(timezone.utc).isoformat();b=Path('uk_birthplace_checkout/studies/scientist_birthplace_completion_v6/outputs/birthplace_rows.jsonl.gz');bsha=hashlib.sha256(b.read_bytes()).hexdigest();assert bsha=='8e880fcf4a659a1c8753a5a0ad4c06552ddd9d0d545334b0e81a2459907d7356'
rows=[json.loads(l)for l in gzip.open(b,'rt')];nobel=[r for r in rows if r['cohort']=='Nobel_science'];routes=[]
for cat in ('che','med'):
 observed=[r for r in nobel if 'nobelPrizeCategory='+cat+'&'in r.get('birthplace_source_url','')];urls=sorted({r['birthplace_source_url']for r in observed});assert len(urls)==1
 routes.append({'category':cat,'observed_url':urls[0],'baseline_route_evidence_record_id':observed[0]['record_id'],'baseline_route_evidence_row':observed[0],'baseline_sha256':bsha,'baseline_rows_using_exact_route':len(observed)})
(P/'observed_source_routes.json').write_text(json.dumps(routes,ensure_ascii=False,indent=2));captures=[]
for seq,route in enumerate(routes,1):
 intent={'utc':now(),'kind':'official_category_API_original_body','sequence':seq,'category':route['category'],'url':route['observed_url'],'intent':'One fresh original public API body using exactly an observed baseline Nobel_science source URL; no individual pages/search/retries. Stop any429/403/503.','observed_from_baseline_record_id':route['baseline_route_evidence_record_id'],'baseline_sha256':bsha}
 with(P/'intent_ledger.jsonl').open('a')as f:f.write(json.dumps(intent)+'\n');f.flush()
 try:
  with urllib.request.urlopen(urllib.request.Request(route['observed_url'],headers={'User-Agent':'Mozilla/5.0','Accept':'application/json'}),timeout=35)as r:
   data=r.read();meta={'category':route['category'],'requested_url':route['observed_url'],'final_url':r.url,'status':r.status,'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),'retrieved_utc':now(),'capture_kind':'original_JSON_API_response_bytes','scope':'complete_official_public_category_laureates_API_response','headers':{k:v for k,v in r.headers.items()if k.lower()in('content-type','content-length','last-modified','etag')}}
  fn=P/'raw'/('nobel_'+route['category']+'_original_response.bin');fn.write_bytes(data);meta['local_raw_path']=str(fn.resolve());j=json.loads(data);meta['laureate_objects_count']=len(j.get('laureates',[]));captures.append(meta);print('CAPTURE',json.dumps(meta),flush=True)
 except urllib.error.HTTPError as e:
  captures.append({'category':route['category'],'url':route['observed_url'],'status':e.code,'error':str(e),'retrieved_utc':now()});print('HTTPERROR',e.code,flush=True)
  if e.code in(429,403,503):
   (P/'captures.json').write_text(json.dumps(captures,indent=2));break
 except Exception as e:
  captures.append({'category':route['category'],'url':route['observed_url'],'error':str(e),'retrieved_utc':now()});print('ERROR',str(e),flush=True)
 (P/'captures.json').write_text(json.dumps(captures,indent=2))
(P/'captures.json').write_text(json.dumps(captures,indent=2))
clock=json.loads((P/'clock.json').read_text());clock['source_acquisition_end_utc']=now();clock['source_acquisition_elapsed_seconds']=(datetime.fromisoformat(clock['source_acquisition_end_utc'])-datetime.fromisoformat(clock['source_clock_start_utc'])).total_seconds();assert clock['source_acquisition_elapsed_seconds']<480;(P/'clock.json').write_text(json.dumps(clock,indent=2))
