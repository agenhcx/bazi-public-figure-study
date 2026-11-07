from pathlib import Path
from datetime import datetime,timezone
from html.parser import HTMLParser
import json,urllib.request,hashlib,re,gzip,unicodedata
P=Path(__file__).parent;now=lambda:datetime.now(timezone.utc).isoformat();url='https://www.nationalacademies.org/read/9681'
with(P/'intent_ledger.jsonl').open('a')as f:f.write(json.dumps({'utc':now(),'kind':'index_navigation','sequence':1,'url':url,'intent':'Capture observed official Volume77TOC and realchapterlinks; bulkmatchall555unknowns before bodies.'})+'\n')
try:
 with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=25)as r:
  data=r.read();meta={'requested_url':url,'final_url':r.url,'status':r.status,'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),'retrieved_utc':now(),'capture_kind':'original_html_bytes','scope':'Volume77frontmatterandTOC','headers':{k:v for k,v in r.headers.items()if k.lower()in('content-type','content-length','last-modified','etag')}}
 (P/'raw'/'toc.html').write_bytes(data);(P/'toc_capture.json').write_text(json.dumps(meta,indent=2));print('CAPTURE',meta,flush=True)
except Exception as e:print(type(e).__name__,str(e));raise SystemExit(1)
class Links(HTMLParser):
 def __init__(self):super().__init__();self.href=None;self.t=[];self.links=[]
 def handle_starttag(self,t,a):
  if t=='a':self.href=dict(a).get('href');self.t=[]
 def handle_data(self,d):
  if self.href:self.t.append(d)
 def handle_endtag(self,t):
  if t=='a'and self.href:
   if'/read/9681/chapter/'in self.href:self.links.append({'url':self.href,'text':' '.join(' '.join(self.t).split())})
   self.href=None
q=Links();q.feed(data.decode('utf8','replace'));links=[]
for x in q.links:
 if x not in links:links.append(x)
(P/'toc_links.json').write_text(json.dumps(links,indent=2))
def norm(s):
 t=re.sub('[^a-z ]',' ',unicodedata.normalize('NFKD',s).encode('ascii','ignore').decode().lower()).split()
 while t and t[-1]in('jr','sr','ii','iii','iv'):t.pop()
 return t
def compat(n,t):
 n=norm(n);t=norm(t)
 if not n or not t or n[-1]!=t[-1]:return False
 if not(n[0]==t[0]or(len(n[0])==1 and t[0].startswith(n[0]))or(len(t[0])==1 and n[0].startswith(t[0]))):return False
 j=1
 for a in n[1:-1]:
  while j<len(t)-1 and not(a==t[j]or(len(a)==1 and t[j].startswith(a))or(len(t[j])==1 and a.startswith(t[j]))):j+=1
  if j==len(t)-1:return False
  j+=1
 return True
toc=[]
for x in links:
 if re.fullmatch(r'https://www.nationalacademies.org/read/9681/chapter/\d+',x['url'])and re.search(r' \d+[–-]\d+$',x['text']):toc.append({'url':x['url'],'heading':re.sub(r' \d+[–-]\d+$','',x['text']),'page_range':re.search(r' (\d+[–-]\d+)$',x['text']).group(1),'chapter':int(x['url'].rsplit('/',1)[1])})
rows=[json.loads(l)for l in gzip.open('uk_birthplace_checkout/studies/scientist_birthplace_completion_v5/outputs/birthplace_rows.jsonl.gz','rt')];nas=[x for x in rows if x['cohort']=='NAS'];unknown=[x for x in nas if x['hemisphere']=='unknown'];coverage=[];matches=[]
for row in unknown:
 m=[t for t in toc if compat(row['name'],t['heading'])];coverage.append({'record_id':row['record_id'],'name':row['name'],'native_dob':row['dob'],'matched_toc':m,'status':'name_initials_route_match'if m else'not_matched_to_this_volume_TOC'})
 for t in m:matches.append({'toc':t,'chapter':t['chapter'],'frozen_baseline_row':row,'all_2242_name_compatible':[{'name':a['name'],'record_id':a['record_id'],'native_dob':a['dob']}for a in nas if compat(a['name'],t['heading'])],'routing_name_method':'normalizedfirst+last,orderedcompatiblemiddlefullnamesorinitials;omittedmiddleandsuffixallowed;DOBnotinferred'})
assert len(unknown)==555
(P/'coverage.jsonl').write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n'for x in coverage));(P/'bulk_matches.json').write_text(json.dumps(matches,ensure_ascii=False,indent=2));(P/'toc_subjects.json').write_text(json.dumps(toc,indent=2));print('TOC',len(toc),flush=True);print('MATCHES',[(x['chapter'],x['frozen_baseline_row']['name'],x['frozen_baseline_row']['dob'],len(x['all_2242_name_compatible']))for x in matches],flush=True)
