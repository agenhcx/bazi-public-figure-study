from pathlib import Path
from datetime import datetime,timezone
from html.parser import HTMLParser
import json,urllib.request,urllib.error,hashlib
P=Path(__file__).parent;now=lambda:datetime.now(timezone.utc).isoformat()
sel=json.loads((P/'selection.json').read_text());extra=sel['deferred'];sel['deferred']=[]
for x in extra:
 x.pop('deferral_reason',None);x['selection_reason']='Parent expanded cap from6to8 at23:57UTC after observing these genuine TOC routes; one original body each within8minute sourceclock; no additional discovery or retries.'
sel['selected']+=extra;sel['authorization_extension']={'chapter_body_cap':8,'source_clock_limit_minutes':8,'parent_message':'Vol74 only3matches; overall12-bodybudget; observed Keyes+Longsworth two extra chapters authorized.'}
(P/'selection.json').write_text(json.dumps(sel,indent=2))
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
captures=json.loads((P/'captures.json').read_text());errs={}
for i,x in enumerate(extra,7):
 intent={'utc':now(),'kind':'chapter_body','sequence':i,'url':x['toc']['url'],'chapter':x['chapter'],'record_id':x['frozen_baseline_row']['record_id'],'name':x['frozen_baseline_row']['name'],'intent':'One additional observed route explicitly authorized by parent: literal born/place, heading/nativeDOB/authorship/NAS identity check; zero retries.'}
 with (P/'intent_ledger.jsonl').open('a') as f:f.write(json.dumps(intent)+'\n');f.flush()
 try:
  with urllib.request.urlopen(urllib.request.Request(intent['url'],headers={'User-Agent':'Mozilla/5.0'}),timeout=25) as r:
   data=r.read();meta={'chapter':x['chapter'],'requested_url':intent['url'],'final_url':r.url,'status':r.status,'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),'retrieved_utc':now(),'capture_kind':'original_html_bytes','scope':'complete_original_chapter_HTML_response','record_id':intent['record_id']}
  fn=P/'raw'/('chapter_%02d.html'%x['chapter']);fn.write_bytes(data);meta['local_raw_path']=str(fn)
  q=Text();q.feed(data.decode('utf-8','replace'));txt='\n'.join(' '.join(v.split()) for v in ''.join(q.out).splitlines() if v.strip());(P/'raw'/('chapter_%02d.txt'%x['chapter'])).write_text(txt)
  captures.append(meta);print('CAPTURE',json.dumps(meta),flush=True)
 except urllib.error.HTTPError as e:
  code=e.code;errs[code]=errs.get(code,0)+1;captures.append({'chapter':x['chapter'],'url':intent['url'],'status':code,'error':str(e),'retrieved_utc':now()});print('HTTP_ERROR',code,flush=True)
  if code==429 or code in(403,503) and errs[code]>=2:break
 except Exception as e:captures.append({'chapter':x['chapter'],'url':intent['url'],'error':str(e),'retrieved_utc':now()});print('ERROR',str(e),flush=True)
 (P/'captures.json').write_text(json.dumps(captures,indent=2))
