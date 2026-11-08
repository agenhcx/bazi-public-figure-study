from pathlib import Path
from html.parser import HTMLParser
import urllib.request,urllib.error,datetime,time,json,hashlib
O=Path(__file__).parent;(O/'raw').mkdir(exist_ok=True)
R=json.loads((O/'expanded_selection.json').read_text())['selected'];idx=[json.loads(l) for l in (O/'expanded_index_ledger.jsonl').read_text().splitlines()];start=datetime.datetime.fromisoformat(idx[0]['retrieved_utc']);deadline=start+datetime.timedelta(minutes=8)
class T(HTMLParser):
 def __init__(self):super().__init__();self.skip=0;self.text=[]
 def handle_starttag(self,t,a):
  if t in ['style','script']:self.skip+=1
  if t in ['div','p','br','li','dt','dd','h1','h2','h3','tr','th','td']:self.text.append('\n')
 def handle_endtag(self,t):
  if t in ['style','script']:self.skip=max(0,self.skip-1)
  if t in ['div','p','li','dt','dd','h1','h2','h3','tr','th','td']:self.text.append('\n')
 def handle_data(self,d):
  if not self.skip:self.text.append(d)
last=0.;stop=any(x.get('http_status')==429 for x in idx);logs=[]
for r in R:
 z=dict(r)
 if stop or datetime.datetime.now(datetime.timezone.utc)>=deadline:z.update(attempted=False,hold_reason='not_attempted_after_index429_or_extension_deadline');logs.append(z);continue
 delay=1.1-(time.monotonic()-last)
 if delay>0:time.sleep(delay)
 last=time.monotonic();z.update(attempted=True,retrieved_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
 try:
  timeout=min(25,max(1,(deadline-datetime.datetime.now(datetime.timezone.utc)).total_seconds()))
  with urllib.request.urlopen(urllib.request.Request(r['url'],headers={'User-Agent':'BirthplaceEvidenceResearch/1.0'}),timeout=timeout) as h:b=h.read();z['http_status']=h.status;z['final_url']=h.url
  stem=r['record_id'];path=O/'raw'/(stem+'.html');path.write_bytes(b);z.update(raw_source_file=str(path.relative_to(O)),source_sha256=hashlib.sha256(b).hexdigest());p=T();p.feed(b.decode('utf8',errors='replace'));text='\n'.join(' '.join(x.split()) for x in ''.join(p.text).splitlines() if x.strip());(O/'raw'/(stem+'.txt')).write_text(text);z['text_file']='raw/'+stem+'.txt'
 except urllib.error.HTTPError as e:
  z.update(http_status=e.code,error=str(e));stop=e.code==429
 except Exception as e:z['error']=type(e).__name__+':'+str(e)
 logs.append(z);(O/'body_request_ledger.jsonl').write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in logs));print(z['record_id'],z.get('http_status'),z.get('error'),flush=True)
(O/'body_request_ledger.jsonl').write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in logs))
