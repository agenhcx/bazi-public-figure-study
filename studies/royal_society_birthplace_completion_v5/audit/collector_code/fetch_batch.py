from pathlib import Path
import json,urllib.request,urllib.parse,urllib.error,hashlib,datetime,time,threading,concurrent.futures,html,re
O=Path(__file__).parent;(O/'crossref_raw').mkdir(exist_ok=True)
C=json.loads((O/'cohort.json').read_text());gate=threading.Lock();last=0.;stop=threading.Event();starts=[]
def fetch(r):
 global last
 with gate:
  if stop.is_set() or (O/'shared_429_stop.json').exists() or (O.parent/'CROSSREF_SHARED_STOP.json').exists():return {**r,'attempted_this_round':False,'error':'held_after_HTTP429_stop'}
  delay=1.1-(time.monotonic()-last)
  if delay>0:time.sleep(delay)
  if (O/'shared_429_stop.json').exists() or (O.parent/'CROSSREF_SHARED_STOP.json').exists():return {**r,'attempted_this_round':False,'error':'not_attempted_shared_Crossref429'}
  last=time.monotonic();starts.append(last);started=last
 q=urllib.parse.urlencode({'rows':3,'query':r['memoir_query'],'select':'DOI,title,abstract,publisher,container-title,URL,link,published-print'})
 u='https://api.crossref.org/journals/2053-9118/works?'+q;p=O/'crossref_raw'/(r['record_id']+'.json')
 z={**r,'attempted_this_round':True,'request_url':u,'retrieved_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'request_start_monotonic':started}
 try:
  with urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'BirthplaceEvidenceResearch/1.0'}),timeout=25) as h:data=h.read();z['http_status']=h.status
  p.write_bytes(data);z['source_sha256']=hashlib.sha256(data).hexdigest();z['raw_source_file']=str(p.relative_to(O));z['items']=json.loads(data)['message']['items']
 except urllib.error.HTTPError as e:
  z['http_status']=e.code;z['error']=str(e)
  if e.code==429:
   stop.set()
   shared=O.parent/'CROSSREF_SHARED_STOP.json'
   if not shared.exists():shared.write_text(json.dumps({'reason':'HTTP429 observed in early_memoirs','record_id':r['record_id'],'recorded_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()},indent=2))
 except Exception as e:z['error']=type(e).__name__+':'+str(e)
 return z
A=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
 fs={ex.submit(fetch,r):r for r in C}
 for f in concurrent.futures.as_completed(fs):
  z=f.result();A.append(z)
  (O/'crossref_results.jsonl').write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in sorted(A,key=lambda x:x['record_id'])))
  print(json.dumps({'done':len(A),'record_id':z['record_id'],'http_status':z.get('http_status'),'error':z.get('error'),'first_title':(z.get('items') or [{}])[0].get('title')},ensure_ascii=False),flush=True)
(O/'fetch_summary.json').write_text(json.dumps({'selected':len(C),'attempted':sum(x['attempted_this_round'] for x in A),'max_in_flight':2,'required_minimum_request_start_interval_seconds':1.1,'observed_minimum_start_interval_seconds':min(b-a for a,b in zip(starts,starts[1:])) if len(starts)>1 else None,'retries':0,'HTTP429_stop':stop.is_set()},indent=2))
