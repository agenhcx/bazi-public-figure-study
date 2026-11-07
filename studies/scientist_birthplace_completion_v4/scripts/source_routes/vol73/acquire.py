from pathlib import Path
from datetime import datetime,timezone
from html.parser import HTMLParser
import re,gzip,json,hashlib,urllib.request,urllib.error,time,unicodedata
P=Path(__file__).parent
now=lambda:datetime.now(timezone.utc).isoformat()
def norm(s):return ' '.join(re.sub('[^a-z ]',' ',unicodedata.normalize('NFKD',s).encode('ascii','ignore').decode().lower()).split())
def compatible(n,t):
 n=norm(n).split();t=norm(t).split()
 if not n or not t or n[-1]!=t[-1]:return False
 # first and last must agree; omitted middle names are supported only as routing.
 if not (n[0]==t[0] or len(n[0])==1 and t[0].startswith(n[0])):return False
 j=1
 for a in n[1:-1]:
  while j<len(t)-1 and not (a==t[j] or len(a)==1 and t[j].startswith(a)):j+=1
  if j==len(t)-1:return False
  j+=1
 return True
rows=[json.loads(x) for x in gzip.open('uk_birthplace_checkout/studies/scientist_birthplace_completion_v3/outputs/birthplace_rows.jsonl.gz','rt')]
nas=[x for x in rows if x['cohort']=='NAS'];unknown=[x for x in nas if x['hemisphere']=='unknown']
links=json.loads((P/'toc_links.json').read_text());toc=[]
for x in links:
 if re.fullmatch(r'https://www.nationalacademies.org/read/9650/chapter/\d+',x['url']) and re.search(r' \d+-\d+$',x['text']):
  toc.append({'url':x['url'],'heading':re.sub(r' \d+-\d+$','',x['text']),'page_range':re.search(r' (\d+-\d+)$',x['text']).group(1)})
coverage=[];matches=[]
for x in unknown:
 m=[t for t in toc if compatible(x['name'],t['heading'])]
 coverage.append({'record_id':x['record_id'],'name':x['name'],'native_dob':x['dob'],'matched_toc':m,'status':'name_initials_route_match' if m else 'not_matched_to_this_volume_TOC'})
 for t in m:
  allmatches=[{'name':a['name'],'record_id':a['record_id'],'native_dob':a['dob']} for a in nas if compatible(a['name'],t['heading'])]
  matches.append({'toc':t,'frozen_baseline_row':x,'all_2242_name_compatible':allmatches,'routing_name_method':'normalized first/last, ordered middle tokens or initials; absent middle names allowed; no DOB inference'})
selected_ids=[2,3,7,8,18,21]
selected=[];deferred=[]
for x in matches:
 ch=int(x['toc']['url'].rsplit('/',1)[1]);x['chapter']=ch
 if ch in selected_ids:
  x['selection_reason']='Unknown NAS row; observed expanded TOC heading compatible with native name; unique name-compatible among all2242; nativeDOB in1835–1985 window. Body must independently pass exact nativeDOB and subject/place review.'
  selected.append(x)
 else:x['deferral_reason']='Six-body cap; good TOC route retained for a subsequent round.';deferred.append(x)
(P/'coverage.jsonl').write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in coverage))
(P/'selection.json').write_text(json.dumps({'selected':selected,'deferred':deferred,'false_surname_route':'AlfredHenrySturtevant differs from JulianM.Sturtevant; excluded','toc_chapters':toc},ensure_ascii=False,indent=2))
print('SELECTION',[(x['chapter'],x['frozen_baseline_row']['name'],x['frozen_baseline_row']['dob'],len(x['all_2242_name_compatible'])) for x in selected],flush=True)
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
errs={};captures=[]
for i,x in enumerate(selected,1):
 intent={'utc':now(),'kind':'chapter_body','sequence':i,'url':x['toc']['url'],'chapter':x['chapter'],'record_id':x['frozen_baseline_row']['record_id'],'name':x['frozen_baseline_row']['name'],'intent':'One fresh original chapter body for explicit born/place facts and independent expanded heading, exact nativeDOB, authorship/NAS-context identity verification; zero retries.'}
 with (P/'intent_ledger.jsonl').open('a') as f:f.write(json.dumps(intent)+'\n');f.flush()
 try:
  with urllib.request.urlopen(urllib.request.Request(intent['url'],headers={'User-Agent':'Mozilla/5.0'}),timeout=25) as r:
   data=r.read();meta={'chapter':x['chapter'],'requested_url':intent['url'],'final_url':r.url,'status':r.status,'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),'retrieved_utc':now(),'capture_kind':'original_html_bytes','scope':'complete_original_chapter_HTML_response','record_id':intent['record_id']}
  fn=P/'raw'/('chapter_%02d.html'%x['chapter']);fn.write_bytes(data);meta['local_raw_path']=str(fn)
  q=Text();q.feed(data.decode('utf-8','replace'));txt='\n'.join(' '.join(v.split()) for v in ''.join(q.out).splitlines() if v.strip());(P/'raw'/('chapter_%02d.txt'%x['chapter'])).write_text(txt)
  captures.append(meta);print('CAPTURE',json.dumps(meta),flush=True)
 except urllib.error.HTTPError as e:
  code=e.code;errs[code]=errs.get(code,0)+1;captures.append({'chapter':x['chapter'],'url':intent['url'],'status':code,'error':str(e),'retrieved_utc':now()});print('HTTP_ERROR',code,flush=True)
  if code==429 or (code in (403,503) and errs[code]>=2):print('STOP_POLICY',flush=True);break
 except Exception as e:
  captures.append({'chapter':x['chapter'],'url':intent['url'],'error':str(e),'retrieved_utc':now()});print('ERROR',str(e),flush=True)
 (P/'captures.json').write_text(json.dumps(captures,indent=2))
(P/'captures.json').write_text(json.dumps(captures,indent=2))
