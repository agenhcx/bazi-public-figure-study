from pathlib import Path
from datetime import datetime,timezone
from html.parser import HTMLParser
from urllib.parse import urljoin
import json,gzip,hashlib,urllib.request,re,unicodedata
P=Path(__file__).parent;now=lambda:datetime.now(timezone.utc).isoformat();url='https://www.nationalacademies.org/read/10269'
if (P/'raw_transient/toc.html').exists():
 data=(P/'raw_transient/toc.html').read_bytes();meta=json.loads((P/'toc_capture.json').read_text())
else:
 intent={'utc':now(),'kind':'official_TOC','url':url,'discovered_by':'system2 search1; observed turn2118search1 official ReadOnline URL','intent':'single original TOC capture; route all543unknowns; no fullmemberbirthdaysearch'}
 with (P/'intent_ledger.jsonl').open('a') as f:f.write(json.dumps(intent)+'\n');f.flush()
 with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=25) as r:
  data=r.read();meta={'requested_url':url,'final_url':r.url,'HTTP_status':r.status,'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),'retrieved_utc':now(),'capture_kind':'original_HTML_bytes'}
 (P/'raw_transient/toc.html').write_bytes(data);(P/'toc_capture.json').write_text(json.dumps(meta,indent=2))
class Parse(HTMLParser):
 def __init__(self):super().__init__();self.link=None;self.links=[];self.text=[];self.skip=0
 def handle_starttag(self,t,a):
  a=dict(a)
  if t in ['script','style']:self.skip+=1
  if t=='a' and a.get('href'):self.link=[a['href'],'']
  if t in ['p','div','h1','h2','h3','h4','li','tr','section']:self.text.append('\n')
 def handle_endtag(self,t):
  if t in ['script','style']:self.skip-=1
  if t=='a' and self.link:self.links.append({'url':urljoin(url,self.link[0]),'text':' '.join(self.link[1].split())});self.link=None
  if t in ['p','div','h1','h2','h3','h4','li','tr','section']:self.text.append('\n')
 def handle_data(self,d):
  if not self.skip:self.text.append(d)
  if self.link:self.link[1]+=d+' '
p=Parse();p.feed(data.decode());(P/'raw_transient/toc.txt').write_text('\n'.join(' '.join(x.split()) for x in ''.join(p.text).splitlines() if x.strip()))
links=[]
for x in p.links:
 if '/read/10269/chapter/' in x['url'] and x['text'] and x not in links:links.append(x)
(P/'toc_links.json').write_text(json.dumps(links,indent=2))
base=Path('/workspace/scratch/7e8aa4e0d4af/uk_birthplace_checkout/studies/scientist_birthplace_completion_v6/outputs/birthplace_rows.jsonl.gz');assert hashlib.sha256(base.read_bytes()).hexdigest()=='8e880fcf4a659a1c8753a5a0ad4c06552ddd9d0d545334b0e81a2459907d7356'
rows=[json.loads(l) for l in gzip.open(base,'rt')];nas=[r for r in rows if r['cohort']=='NAS'];unknown=[r for r in nas if r['hemisphere']=='unknown'];assert len(nas)==2242 and len(unknown)==543
norm=lambda s:re.findall('[a-z]+',unicodedata.normalize('NFKD',s).encode('ascii','ignore').decode().lower())
def compatible(a,b):
 a=norm(a);b=norm(b)
 if not a or not b or a[-1]!=b[-1] or a[0][0]!=b[0][0]:return False
 if len(a[0])>1 and len(b[0])>1 and a[0]!=b[0]:return False
 return all(x[0]==y[0] for x,y in zip(a[1:-1],b[1:-1]))
subjects=[]
for x in links:
 if '#p' not in x['url'] or not re.search('/chapter/(?:[2-9]|1[0-9]|2[01])#',x['url']) or not re.search('[A-Za-z]',x['text']):continue
 canonical=x['url'].split('#')[0]
 if any(y['url']==canonical for y in subjects):continue
 subjects.append({'url':canonical,'text':x['text'].title(),'printed_TOC_text':x['text'],'observed_anchor_url':x['url']})
subjects.sort(key=lambda x:int(re.search('/chapter/(\\d+)',x['url']).group(1)));assert len(subjects)==20,(len(subjects),subjects)
(P/'toc_subjects.json').write_text(json.dumps(subjects,indent=2));matches=[];coverage=[]
for r in unknown:
 hits=[s for s in subjects if compatible(r['name'],s['text'])]
 coverage.append({'cohort':'NAS','record_id':r['record_id'],'name':r['name'],'native_dob':r['dob'],'routing_status':'observed_TOC_candidate_body_pending' if hits else 'no_compatible_observed_TOC_route','TOC_routes':hits})
 for h in hits:matches.append({'chapter':int(re.search('/chapter/(\\d+)',h['url']).group(1)),'toc':h,'baseline_row_snapshot':r,'compatible_among2242':[{'name':x['name'],'dob':x['dob'],'record_id':x['record_id']} for x in nas if compatible(x['name'],h['text'])]})
(P/'bulk_matches.json').write_text(json.dumps(matches,indent=2));(P/'coverage.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in coverage));print(json.dumps({'TOC':meta,'subjects':len(subjects),'matches':[{k:x[k] for k in ['chapter','toc','compatible_among2242']} for x in matches]},indent=2))
