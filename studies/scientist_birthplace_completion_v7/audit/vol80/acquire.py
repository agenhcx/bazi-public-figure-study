from pathlib import Path
from datetime import datetime,timezone
from html.parser import HTMLParser
import json,hashlib,urllib.request,urllib.error
P=Path(__file__).parent;now=lambda:datetime.now(timezone.utc).isoformat()
class Text(HTMLParser):
 def __init__(self):super().__init__();self.out=[];self.skip=0
 def handle_starttag(self,t,a):
  if t in ('script','style'):self.skip+=1
  elif t in ('p','div','h1','h2','h3','h4','li','br','tr','section'):self.out.append('\n')
 def handle_endtag(self,t):
  if t in ('script','style'):self.skip-=1
  elif t in ('p','div','h1','h2','h3','h4','li','tr','section'):self.out.append('\n')
 def handle_data(self,d):
  if not self.skip:self.out.append(d)
selected={}
for x in json.loads((P/'bulk_matches.json').read_text()):selected[x['chapter']]=x
assert len(selected)==2
captures=[];errors={}
for ch,x in sorted(selected.items()):
 url=x['toc']['url'];intent={'utc':now(),'kind':'chapter_body','chapter':ch,'url':url,'intent':'One original chapter HTTP request; explicit born-place, authored-heading/nativeDOB/NAScontext identity, no retries; Exact native DOB and expanded full heading require independent source identity verification.'}
 with (P/'intent_ledger.jsonl').open('a') as f:f.write(json.dumps(intent)+'\n');f.flush()
 try:
  with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=25) as r:
   data=r.read();meta={'chapter':ch,'requested_url':url,'final_url':r.url,'status':r.status,'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),'retrieved_utc':now(),'capture_kind':'original_HTML_bytes','scope':'entire chapter original HTTP response'}
  (P/'raw_transient'/('chapter_%02d.html'%ch)).write_bytes(data);p=Text();p.feed(data.decode());txt='\n'.join(' '.join(t.split()) for t in ''.join(p.out).splitlines() if t.strip());(P/'raw_transient'/('chapter_%02d.txt'%ch)).write_text(txt);captures.append(meta);print(json.dumps(meta),flush=True)
 except urllib.error.HTTPError as e:
  errors[e.code]=errors.get(e.code,0)+1;captures.append({'chapter':ch,'url':url,'status':e.code,'utc':now()});print('HTTP_ERROR',e.code,flush=True)
  if e.code==429 or (e.code in [403,503] and errors[e.code]>=2):break
 except Exception as e:captures.append({'chapter':ch,'url':url,'error':str(e),'utc':now()});print('ERROR',str(e),flush=True)
 (P/'captures.json').write_text(json.dumps(captures,indent=2))
(P/'captures.json').write_text(json.dumps(captures,indent=2))
