#!/usr/bin/env python3
"""Issue the sole preauthorized exact-name place query and save response bytes, without retries."""
import datetime, hashlib, json, pathlib, urllib.error, urllib.parse, urllib.request
B=pathlib.Path(__file__).resolve().parent
ledger=B/'query_ledger.jsonl'
assert not ledger.exists(), 'No retry: query ledger already exists'
query=(B/'exact_place_query.rq').read_bytes()
endpoint='https://query.wikidata.org/sparql'
url=endpoint+'?'+urllib.parse.urlencode({'query':query.decode(),'format':'json'})
intent={'time_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'ordinal':1,'cohort':'NAS','operation':'combined_exact_English_label_or_alias_place_SPARQL','endpoint':endpoint,'exact_labels':['New York City','Colorado Springs'],'query_file':str(B/'exact_place_query.rq'),'query_sha256':hashlib.sha256(query).hexdigest(),'person_queries':0,'limit_used':False,'retry_authorized':False,'all_homonyms_retained':True,'coordinate_rank_filter':False,'globe_filter':False,'P31_or_P17_filter':False,'authorization':'root preauthorized at most one combined exact-label/alias query after both source lanes frozen'}
ledger.write_text(json.dumps(intent,sort_keys=True)+'\n')
meta={'request':intent,'request_url':url,'request_headers':{'Accept':'application/sparql-results+json','User-Agent':'scientist-birthplace-geography-review/4 (research; one exact-name query)'},'capture_kind':'original_HTTP_response_bytes','captured_at_utc':None,'query_attempts':1,'retry_performed':False}
try:
 req=urllib.request.Request(url,headers=meta['request_headers'])
 with urllib.request.urlopen(req,timeout=55) as response:
  raw=response.read();meta.update(status=response.status,final_url=response.url,response_headers=dict(response.headers))
except urllib.error.HTTPError as e:
 raw=e.read();meta.update(status=e.code,error_type=type(e).__name__,error=str(e),response_headers=dict(e.headers))
except Exception as e:
 raw=b'';meta.update(status=None,error_type=type(e).__name__,error=str(e))
meta['captured_at_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
responsefile=B/'exact_place_query_response.bin'
responsefile.write_bytes(raw)
meta.update(response_file=str(responsefile),response_bytes=len(raw),response_sha256=hashlib.sha256(raw).hexdigest())
try:
 parsed=json.loads(raw)
 assert isinstance(parsed.get('results',{}).get('bindings'),list)
 assert meta.get('status')==200
 meta.update(parse_status='valid_SPARQL_JSON',binding_count=len(parsed['results']['bindings']),response_representation='original_HTTP_SPARQL_JSON_response_bytes')
except Exception as e:
 meta.update(parse_status='failed_or_invalid_SPARQL_JSON',parse_error=str(e),response_representation='original_HTTP_error_or_response_bytes' if raw else 'no_response_bytes')
(B/'exact_place_query_capture.json').write_text(json.dumps(meta,indent=2)+'\n')
print(json.dumps({k:v for k,v in meta.items() if k not in ['request_url','request','request_headers','response_headers']},indent=2))
