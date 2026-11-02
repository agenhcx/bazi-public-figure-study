from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
from collections import defaultdict
from urllib.request import urlopen,Request
from urllib.parse import urlparse
from urllib.error import HTTPError
from datetime import datetime,timezone
import csv,json,time,hashlib,threading,re,subprocess
from html.parser import HTMLParser
class TextParser(HTMLParser):
 def __init__(self):super().__init__();self.skip=0;self.parts=[]
 def handle_starttag(self,tag,attrs):
  if tag in {'script','style','noscript'}:self.skip+=1
 def handle_endtag(self,tag):
  if tag in {'script','style','noscript'} and self.skip:self.skip-=1
 def handle_data(self,data):
  if not self.skip and data.strip():self.parts.append(data.strip())

ROOT=Path('/workspace/scratch/7e8aa4e0d4af/uk_birthplace_checkout')
OUT=Path(__file__).parent
CACHE=OUT/'cache';CACHE.mkdir(exist_ok=True)
P=ROOT/'data/royal_society_dob_freeze_v1/royal_society_current_exact_dob_final_v1.csv'
rows=list(csv.DictReader(P.open(encoding='utf-8-sig')))
locks=defaultdict(threading.Lock);last=defaultdict(float)
def fetch(row):
 rid=row['cohort_key'];url=row['provenance_source_url'];u=url.replace('http://','https://',1) if url.startswith('http://') else url
 meta=CACHE/(rid+'.json');tx=CACHE/(rid+'.txt')
 if meta.exists() and tx.exists():return json.loads(meta.read_text())
 rec=dict(record_id=rid,name=row['display_name'],dob=row['exact_dob'],original_url=url,request_url=u,error='',retrieved_utc=datetime.now(timezone.utc).isoformat())
 for attempt in range(2):
  try:
   host=urlparse(u).netloc
   with locks[host]:
    pause=.35-(time.monotonic()-last[host])
    if pause>0:time.sleep(pause)
    last[host]=time.monotonic()
   with urlopen(Request(u,headers={'User-Agent':'AcademyBirthplaceScreen/2.0 (public research; github.com/agenhcx/bazi-public-figure-study)'}),timeout=25) as res:
    b=res.read();rec.update(status=res.status,final_url=res.geturl(),content_type=res.headers.get('Content-Type',''))
   rec.update(source_sha256=hashlib.sha256(b).hexdigest(),bytes=len(b))
   pdf=b.startswith(b'%PDF');raw=CACHE/(rid+('.pdf' if pdf else '.html'));raw.write_bytes(b)
   if pdf:
    dest=CACHE/(rid+'.txt');p=subprocess.run(['pdftotext','-layout',str(raw),str(dest)],capture_output=True,timeout=25)
    if p.returncode:raise ValueError('pdftotext failed')
    text=dest.read_text(errors='replace')
   else:
    parser=TextParser();parser.feed(b.decode('utf-8',errors='replace'));text='\n'.join(parser.parts)
   tx.write_text(text);rec['text_file']=tx.name
   flat=re.sub(r'\s+',' ',text)
   rec['birth_contexts']=[flat[max(0,m.start()-90):m.end()+230] for m in re.finditer(r'\bborn\b|place of birth|birthplace|Geburtsort|geboren|naissance|né le|né à',flat,re.I)][:15]
   break
  except Exception as e:
   rec['error']=type(e).__name__+':'+str(e)[:250]
   if attempt==0:time.sleep(1.2)
 if 'text_file' in rec:rec['error']=''
 meta.write_text(json.dumps(rec,ensure_ascii=False,indent=2)+'\n')
 return rec
out=[]
with ThreadPoolExecutor(max_workers=8) as pool:
 for f in as_completed([pool.submit(fetch,r) for r in rows]):
  r=f.result();out.append(r)
  if len(out)%20==0:print(json.dumps({'processed':len(out),'errors':sum(bool(x['error']) for x in out)}),flush=True)
out.sort(key=lambda r:r['record_id'])
(OUT/'http_observations.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'total':len(out),'errors':sum(bool(r['error']) for r in out),'has_birth_context':sum(bool(r.get('birth_contexts')) for r in out)}),flush=True)
