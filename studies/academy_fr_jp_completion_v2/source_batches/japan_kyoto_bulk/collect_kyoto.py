#!/usr/bin/env python3
"""Collect public Kyoto pre-1950 faculty index and intersect academy candidates."""
from pathlib import Path
import urllib.request,urllib.parse,http.cookiejar,re,csv,json,hashlib,datetime,time,concurrent.futures,threading
from html.parser import HTMLParser
ROOT=Path(__file__).resolve().parent
BASE='https://kensaku.kua1.archives.kyoto-u.ac.jp/rireki/'
class Text(HTMLParser):
 def __init__(self):super().__init__();self.parts=[]
 def handle_data(self,d):self.parts.append(d)
def txt(s):
 p=Text();p.feed(s);return re.sub(r'\s+',' ',' '.join(p.parts)).strip()
def norm(s):return re.sub(r'[\s\u3000]+','',s)
def read_candidates():
 root=next((base for a in [ROOT,*ROOT.parents] for base in [a,a/'academy_completion_checkout'] if (base/'studies/academy_reopen_fr_jp_v1/inputs/japan_science_candidates.csv').exists()),None)
 if root is None:raise FileNotFoundError('Cannot locate the repository containing the frozen Japan candidate input')
 p=root/'studies/academy_reopen_fr_jp_v1/inputs/japan_science_candidates.csv'
 r=list(csv.DictReader(p.open(encoding='utf-8-sig')))
 p40=root/'data/academy_jobs_japan_inputs_v1/japan_academy_remaining40_direct_evidence_queue_v1/remaining40_direct_evidence_queue_v1.csv'
 r40=list(csv.DictReader(p40.open(encoding='utf-8-sig')))
 for x in r:x['candidate_input_scope']='restored435'
 for x in r40:x['candidate_input_scope']='legacy40'
 return r+r40
log_lock=threading.Lock()
jar=http.cookiejar.CookieJar();opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar));log=[]
def fetch(url,filename,data=None):
 p=ROOT/'private'/filename
 if p.exists():b=p.read_bytes();meta={'url':url,'method':'POST' if data else 'GET','cache_replay':True,'retrieved_at':datetime.datetime.fromtimestamp(p.stat().st_mtime,datetime.timezone.utc).isoformat(),'http_status':200}
 else:
  r=opener.open(urllib.request.Request(url,data=urllib.parse.urlencode(data).encode() if data else None,headers={'User-Agent':'AcademyResearch/1.0 public source collection'}),timeout=60);b=r.read();p.write_bytes(b);meta={'url':url,'method':'POST' if data else 'GET','retrieved_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'http_status':r.status}
 meta.update({'sha256':hashlib.sha256(b).hexdigest(),'raw_capture':str(p),'bytes':len(b)})
 with log_lock:
  log.append(meta);(ROOT/'request_log.json').write_text(json.dumps(log,ensure_ascii=False,indent=2))
 return b.decode('utf-8'),meta

def parse_index(body):
 ret=[]
 for tr in re.findall(r'<tr\b[^>]*>(.*?)</tr>',body,re.S|re.I):
  idmatch=re.search(r'name="detail_btn"\s+value="(\d+)"',tr)
  if not idmatch:continue
  cells=re.findall(r'<td\b[^>]*>(.*?)</td>',tr,re.S|re.I)
  ret.append({'kyoto_id':idmatch.group(1),'source_name':txt(cells[1]),'department_index':txt(cells[2])})
 return ret

def main():
 (ROOT/'private').mkdir(exist_ok=True);candidates=read_candidates();index=[]
 for page in range(1,7):
  if page==1:
   data={'sc_in[name]':'','sc_in[section_cd]':'','sc_in[in_office]':'','sc_in[freeword_target]':'0','sc_in[freeword]':'','sc_in[limit]':'200'}
   fetch(BASE,'search_seed_post.html',data)
   body,meta=fetch(BASE+'?c=index&page=1&limit=200','index_01_200.html')
  else:body,meta=fetch(BASE+f'?c=index&page={page}&limit=200',f'index_{page:02}.html')
  entries=parse_index(body);print('index',page,len(entries),flush=True);index+=entries;time.sleep(.4)
 ids=[r['kyoto_id'] for r in index];assert len(ids)==1025 and len(set(ids))==1025,(len(ids),len(set(ids)))
 # Keep whole index temporary. Publish only candidate intersections, not other professors.
 (ROOT/'private'/'index1025.json').write_text(json.dumps(index,ensure_ascii=False,indent=2))
 matches=[]
 for c in candidates:
  found=[r for r in index if norm(r['source_name'])==norm(c['name_jp'])]
  for k in found:matches.append(c|k)
 (ROOT/'candidate_index_matches.json').write_text(json.dumps(matches,ensure_ascii=False,indent=2));print('matches',len(matches),flush=True)
 def detail_fetch(pair):
  i,k=pair;u=BASE+'?c=detail&id='+k['kyoto_id']
  try:body,meta=fetch(u,'detail_'+k['kyoto_id']+'.html');print('detail',i,k['name_jp'],len(body),flush=True)
  except Exception as e:print('ERROR',k['name_jp'],repr(e),flush=True)
  time.sleep(.4)
 with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:list(ex.map(detail_fetch,enumerate(matches)))
 print('Index and matched detail retrieval complete',flush=True)
if __name__=='__main__':main()
