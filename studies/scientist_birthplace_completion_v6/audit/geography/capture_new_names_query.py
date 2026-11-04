#!/usr/bin/env python3
"""One authorized v6 combined exact-label/alias query, only after every source lane freezes.

A finalized query_plan.json and query file are required. This script has no retry path.
"""
from pathlib import Path
import datetime,hashlib,json,urllib.error,urllib.parse,urllib.request
ROOT=Path(__file__).resolve().parents[2];B=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
plan=json.loads((B/'query_plan.json').read_text())
assert plan['all_source_lanes_frozen'] is True and plan['query_authorized'] is True
names=plan['exact_English_label_or_alias_names'];assert names and len(names)==len(set(names))
cache=json.loads((B/'baseline_and_cache_map.json').read_text())
assert not set(names)&{c['exact_English_label_or_alias'] for c in cache['cache']},'Old exact-name queries are reuse-only'
for source in plan['frozen_source_inputs']:
 assert sha(ROOT/source['path'])==source['sha256']
queryfile=B/'new_names_query.rq';query=queryfile.read_bytes();assert sha(queryfile)==plan['query_sha256']
assert b'LIMIT ' not in query.upper() and b'P19' not in query and b'P569' not in query
ledger=B/'new_names_query_intent.jsonl';assert not ledger.exists(),'No retry; durable query intent already exists'
endpoint='https://query.wikidata.org/sparql';url=endpoint+'?'+urllib.parse.urlencode({'query':query.decode(),'format':'json'})
intent={'ordinal':1,'time_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'operation':'combined_exact_English_label_or_alias_place_SPARQL','endpoint':endpoint,'exact_names':names,'query_file':str(queryfile.relative_to(ROOT)),'query_sha256':sha(queryfile),'authorization':'root authorized at most one combined exact new-name query after all v6 source fact lanes freeze','frozen_source_inputs':plan['frozen_source_inputs'],'no_LIMIT':True,'no_person_query':True,'all_homonyms_retained':True,'all_direct_coordinate_ranks_and_globes_retained':True,'no_retry':True,'old_v4_v5_place_query_rerun':False}
ledger.write_text(json.dumps(intent,sort_keys=True)+'\n')
meta={'request':intent,'request_url':url,'captured_at_utc':None,'capture_kind':'original_HTTP_response_bytes','query_attempts':1,'retry_performed':False,'metadata_policy':'Public request URL, status and safe date/content header allowlist only; no full headers, cookies, IP addresses or credentials.'}
try:
 with urllib.request.urlopen(urllib.request.Request(url,headers={'Accept':'application/sparql-results+json','User-Agent':'scientist-birthplace-geography-review/6 (research; one new-name query)'}),timeout=55) as r:
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
