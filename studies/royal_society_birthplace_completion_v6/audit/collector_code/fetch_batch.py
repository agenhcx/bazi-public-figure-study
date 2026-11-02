"""Single-owner Crossref queue: no retries, stop globally on the first 429."""
from pathlib import Path
import csv,datetime,email.utils,gzip,hashlib,json,re,time,urllib.request,urllib.parse,urllib.error
O=Path(__file__).parent;ROOT=O.parents[1];(O/'crossref_raw').mkdir(exist_ok=True)
BASE=ROOT/'uk_birthplace_checkout/studies/royal_society_birthplace_completion_v5/outputs/uk_birthplace_rows.jsonl.gz'
QUEUE=BASE.parents[1]/'audit/pending_search_queue.csv'
SHARED=O.parent/'CROSSREF_SHARED_STOP.json';LOCAL=O/'STOP_REQUESTED.json'
with QUEUE.open(encoding='utf-8-sig',newline='') as f:queue=list(csv.DictReader(f))
assert len(queue)==53
queue.sort(key=lambda r:r['journal_issn']!='2053-9118')
base={r['record_id']:r for r in [json.loads(l) for l in gzip.open(BASE,'rt')]};cohort=[]
for n,q in enumerate(queue):
 b=base[q['record_id']];assert b['dob']==q['dob'] and b['hemisphere']=='unknown' and not b['birthplace_evidence_candidates']
 name=q['source_authorised_full_name'];ys=re.findall(r'\b(1[6789]\d\d|20\d\d)\b',name);assert len(ys)>=2
 parts=[x.strip() for x in name.split(';')];surname=parts[0];given=next((re.split(r'\s*\(',x)[0].strip() for x in parts[1:] if x not in ['Sir','Dame','Lord']),'');full=given+' '+surname
 query=urllib.parse.urlencode({'rows':3,'query':full+' '+ys[0]+' '+ys[-1],'select':'DOI,title,abstract,publisher,container-title,URL,link,published-print'})
 cohort.append({**q,'selection_index':n,'full_name':full,'native_dob':q['dob'],'birthyear':ys[0],'deathyear':ys[-1],'request_url':'https://api.crossref.org/journals/'+q['journal_issn']+'/works?'+query,'attempted_this_round':False,'hold_reason':'not_attempted_yet'})
(O/'cohort.json').write_text(json.dumps(cohort,ensure_ascii=False,indent=2)+'\n')
previous429={'source_record_id':'RS_PAST_NA5003','observed_start_utc':'2026-11-02T13:11:07.196727+00:00','response_headers_recorded':False,'retry_after_observation':'not_recorded_in_v5_not_inferred_absent','checked_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
previous429['elapsed_seconds_at_preflight']=(datetime.datetime.now(datetime.timezone.utc)-datetime.datetime.fromisoformat(previous429['observed_start_utc'])).total_seconds()
previous429['decision']='No captured unexpired Retry-After value available; explicitly authorized new turn after >10h cooldown. No old429 record retried; only53 previously unrequested items.'
(O/'retry_after_preflight.json').write_text(json.dumps(previous429,indent=2)+'\n')
rows=[dict(x) for x in cohort];ledger=[];started=time.monotonic();last=None;stop_reason='';deadline_seconds=8*60

def save():
 (O/'crossref_results.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows))
 (O/'request_ledger.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in ledger))

def stopped():return SHARED.exists() or LOCAL.exists()
save()
for idx,r in enumerate(rows):
 if stopped():stop_reason='shared_or_local_stop_marker';break
 if time.monotonic()-started>=deadline_seconds:stop_reason='bounded_8_minute_deadline';break
 if last is not None:
  pause=3.0-(time.monotonic()-last)
  if pause>0:time.sleep(pause)
 # Required second check after waiting and immediately before dispatch.
 if stopped():stop_reason='shared_or_local_stop_marker_after_wait';break
 if time.monotonic()-started>=deadline_seconds:stop_reason='bounded_8_minute_deadline';break
 last=time.monotonic();r['request_start_monotonic']=last;r['request_started_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat();r['attempted_this_round']=True;r['hold_reason']='';rec={k:r[k] for k in ['record_id','journal_issn','request_url','request_started_utc','request_start_monotonic']};rec['request_status']='started';ledger.append(rec);save()
 try:
  with urllib.request.urlopen(urllib.request.Request(r['request_url'],headers={'User-Agent':'BirthplaceEvidenceResearch/1.0'}),timeout=25) as h:
   raw=h.read();r['http_status']=h.status;r['response_headers']={k:v for k,v in h.headers.items()}
  path=O/'crossref_raw'/(r['record_id']+'.json');path.write_bytes(raw);r['source_sha256']=hashlib.sha256(raw).hexdigest();r['raw_source_file']=str(path.relative_to(O));r['items']=json.loads(raw)['message']['items']
 except urllib.error.HTTPError as e:
  r['http_status']=e.code;r['error']=str(e);r['response_headers']={k:v for k,v in e.headers.items()} if e.headers else {};r['retry_after']=e.headers.get('Retry-After') if e.headers else None
  body=e.read();ep=O/'crossref_raw'/(r['record_id']+'.HTTP'+str(e.code)+'.body');ep.write_bytes(body);r['error_response_sha256']=hashlib.sha256(body).hexdigest();r['error_response_file']=str(ep.relative_to(O))
  if e.code==429:
   stop_reason='HTTP429_shared_stop_no_retry';marker={'reason':stop_reason,'record_id':r['record_id'],'journal_issn':r['journal_issn'],'request_started_utc':r['request_started_utc'],'recorded_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'Retry-After':r['retry_after'],'response_headers':r['response_headers']};SHARED.write_text(json.dumps(marker,indent=2)+'\n');(O/'HTTP429_stop.json').write_text(json.dumps(marker,indent=2)+'\n')
 except Exception as e:r['error']=type(e).__name__+':'+str(e)
 r['response_completed_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat();r['retrieved_utc']=r['response_completed_utc'];rec.update(request_status='completed',http_status=r.get('http_status'),response_completed_utc=r['response_completed_utc'],source_sha256=r.get('source_sha256'),retry_after=r.get('retry_after'));save()
 print(json.dumps({'completed':sum(x.get('response_completed_utc') is not None for x in rows),'selected':53,'record_id':r['record_id'],'http_status':r.get('http_status'),'journal_issn':r['journal_issn'],'stop_reason':stop_reason},ensure_ascii=False),flush=True)
 if stop_reason.startswith('HTTP429'):break
for r in rows:
 if not r['attempted_this_round']:r['hold_reason']='not_attempted_'+(stop_reason or 'queue_bound')
save();attempted=[r for r in rows if r['attempted_this_round']];starts=[r['request_start_monotonic'] for r in attempted]
summary={'selected':53,'attempted':len(attempted),'not_attempted':53-len(attempted),'max_in_flight':1,'minimum_start_interval_seconds':min(b-a for a,b in zip(starts,starts[1:])) if len(starts)>1 else None,'required_minimum_start_interval_seconds':3.0,'retries':0,'stop_reason':stop_reason or 'all53_completed','shared_stop_marker':str(SHARED),'single_Crossref_worker_only':True,'deadline_seconds':deadline_seconds,'input_base_sha256':hashlib.sha256(BASE.read_bytes()).hexdigest(),'input_queue_sha256':hashlib.sha256(QUEUE.read_bytes()).hexdigest()}
(O/'fetch_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
