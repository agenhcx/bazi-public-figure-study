#!/usr/bin/env python3
"""The single authorized v5 exact-label/alias geography query: Berlin and Detroit only."""
from pathlib import Path
import datetime,hashlib,json,urllib.error,urllib.parse,urllib.request
ROOT=Path(__file__).resolve().parents[2];B=Path(__file__).resolve().parent
queryfile=B/'new_names_query.rq';query=queryfile.read_bytes();ledger=B/'new_names_query_intent.jsonl'
assert not ledger.exists(),'No retry; durable query intent already exists'
assert b'"Berlin"@en "Detroit"@en' in query and b'"New York City"@en' not in query
endpoint='https://query.wikidata.org/sparql';url=endpoint+'?'+urllib.parse.urlencode({'query':query.decode(),'format':'json'})
intent={'ordinal':1,'time_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'operation':'combined_exact_English_label_or_alias_place_SPARQL','endpoint':endpoint,'exact_names':['Berlin','Detroit'],'query_file':str(queryfile.relative_to(ROOT)),'query_sha256':hashlib.sha256(query).hexdigest(),'authorization':'root explicitly allowed one combined query of these new names after vol75 source freeze','source_fact_file':'academy_v5_workers/vol75/retained_facts.jsonl','source_fact_file_sha256':'f3c2b77bb67003ef3a30daccda2be5e85abce72d5708dd432b3989edfb55ca37','no_LIMIT':True,'no_person_query':True,'all_homonyms_retained':True,'all_direct_coordinate_ranks_and_globes_retained':True,'no_retry':True,'prior_NYC_Colorado_query_rerun':False}
ledger.write_text(json.dumps(intent,sort_keys=True)+'\n')
meta={'request':intent,'request_url':url,'captured_at_utc':None,'capture_kind':'original_HTTP_response_bytes','query_attempts':1,'retry_performed':False,'metadata_policy':'Public request URL, status and safe date/content header allowlist only; no full headers, cookies, IP addresses or credentials.'}
try:
 with urllib.request.urlopen(urllib.request.Request(url,headers={'Accept':'application/sparql-results+json','User-Agent':'scientist-birthplace-geography-review/5 (research; one new-name query)'}),timeout=55) as r:
  raw=r.read();meta.update(status=r.status,final_url=r.url,safe_response_headers={k.lower():v for k,v in r.headers.items() if k.lower() in {'content-type','content-length','date','last-modified','etag','content-encoding'}})
except urllib.error.HTTPError as e:
 raw=e.read();meta.update(status=e.code,error_type=type(e).__name__,error='HTTP status '+str(e.code))
except Exception as e:
 raw=b'';meta.update(status=None,error_type=type(e).__name__,error='Request failed; no retry')
p=B/'new_names_query_response.bin';p.write_bytes(raw)
meta.update(captured_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),response_file=str(p.relative_to(ROOT)),response_bytes=len(raw),response_sha256=hashlib.sha256(raw).hexdigest())
try:
 payload=json.loads(raw);assert meta.get('status')==200 and isinstance(payload['results']['bindings'],list)
 meta.update(parse_status='valid_SPARQL_JSON',binding_count=len(payload['results']['bindings']),response_representation='original_HTTP_SPARQL_JSON_response_bytes')
except Exception:
 meta.update(parse_status='failed_or_invalid_SPARQL_JSON',response_representation='original_HTTP_error_or_response_bytes' if raw else 'no_response_bytes')
(B/'new_names_query_capture.json').write_text(json.dumps(meta,sort_keys=True,indent=2)+'\n')
print(json.dumps({k:v for k,v in meta.items() if k not in ['request','request_url','final_url']},indent=2))
