#!/usr/bin/env python3
"""One root-authorized exact observed official Nobel API capture; no search or retry."""
from pathlib import Path
import datetime,gzip,hashlib,json,urllib.error,urllib.request
ROOT=Path(__file__).resolve().parents[2];B=Path(__file__).resolve().parent
master=ROOT/'uk_birthplace_checkout/studies/scientist_birthplace_completion_v4/outputs/birthplace_rows.jsonl.gz'
assert hashlib.sha256(master.read_bytes()).hexdigest()=='abbce4e99ad51252dd5e127a0609bc6c4950c121afa2dd126bfc2187b39cd4e8'
with gzip.open(master,'rt') as f:
 rows=[json.loads(l) for l in f if l.strip()]
nobel=next(r for r in rows if r['cohort']=='Nobel_science' and r['record_id']=='43')
url=nobel['birthplace_source_url']
assert url=='https://api.nobelprize.org/2.1/laureates?nobelPrizeCategory=phy&limit=1000&offset=0&sort=asc&format=json'
ledger=B/'anderson_corroboration_intent.jsonl';assert not ledger.exists(),'No retry; durable intent already exists'
intent={'ordinal':1,'time_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'operation':'fresh_official_birthplace_geographic_qualification_source','request_url':url,'url_provenance':'exact observed public physics collection API URL in frozen Nobel_science id43 row','authorization':'root explicitly authorized one fresh original HTTP capture; no search or retry','target_native_cohort':'NAS','target_record_id':'https://www.nasonline.org/directory-entry/carl-d-anderson-qydvwd/','official_source_object_id':'43','no_search':True,'no_retry':True,'not_a_NYC_geography_query_retry':True}
ledger.write_text(json.dumps(intent,sort_keys=True)+'\n')
meta={'request_url':url,'request_method':'GET','captured_at_utc':None,'capture_kind':'original_HTTP_response_bytes','request_ordinal':1,'search_requests':0,'retries':0,'metadata_policy':'Only public URL, status, content type, body hash/length and safe date/content header allowlist retained; no cookies, IP addresses, credentials or full headers.'}
headers={'Accept':'application/json','User-Agent':'scientist-birthplace-source-corroboration/5 (research; one authorized capture)'}
try:
 with urllib.request.urlopen(urllib.request.Request(url,headers=headers),timeout=55) as r:
  data=r.read();meta.update(status=r.status,final_url=r.url,safe_response_headers={k.lower():v for k,v in r.headers.items() if k.lower() in {'content-type','content-length','date','last-modified','etag','content-encoding'}})
except urllib.error.HTTPError as e:
 data=e.read();meta.update(status=e.code,error_type=type(e).__name__,error='HTTP status '+str(e.code))
except Exception as e:
 data=b'';meta.update(status=None,error_type=type(e).__name__,error='request failed; no retry')
p=B/'nobel_physics_corroboration_response.bin';p.write_bytes(data)
meta.update(captured_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),response_file=str(p.relative_to(ROOT)),response_bytes=len(data),response_sha256=hashlib.sha256(data).hexdigest())
try:
 payload=json.loads(data);assert meta.get('status')==200 and isinstance(payload.get('laureates'),list)
 ids=[x for x in payload['laureates'] if x.get('id')=='43'];assert len(ids)==1
 meta.update(parse_status='valid_official_API_JSON',target_id_object_count=len(ids),laureate_count=len(payload['laureates']),capture_representation='original_HTTP_JSON_bytes')
except Exception:
 meta.update(parse_status='invalid_or_failed_capture',capture_representation='original_HTTP_response_or_error_bytes' if data else 'no_response_bytes')
(B/'anderson_corroboration_capture.json').write_text(json.dumps(meta,sort_keys=True,indent=2)+'\n')
print(json.dumps(meta,indent=2))
