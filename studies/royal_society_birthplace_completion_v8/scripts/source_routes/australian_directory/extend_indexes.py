from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urljoin
import urllib.request,urllib.error,json,time,datetime,hashlib,re
O=Path(__file__).parent;(O/'indexes').mkdir(exist_ok=True);deadline=time.monotonic()+400;last=0.;stopped=False
class L(HTMLParser):
 def __init__(self):super().__init__();self.a=None;self.links=[]
 def handle_starttag(self,t,a):
  if t=='a':self.a={**dict(a),'label':''}
 def handle_data(self,d):
  if self.a is not None:self.a['label']+=d
 def handle_endtag(self,t):
  if t=='a' and self.a is not None:self.a['label']=' '.join(self.a['label'].split());self.links.append(self.a);self.a=None
logs=[];alllinks=[]
def fetch(u,name):
 global last,stopped
 if stopped or time.monotonic()>deadline:return None
 delay=1.1-(time.monotonic()-last)
 if delay>0:time.sleep(delay)
 last=time.monotonic();z={'url':u,'retrieved_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source_file':'indexes/'+name+'.html','attempted':True}
 try:
  with urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'BirthplaceEvidenceResearch/1.0'}),timeout=25) as h:b=h.read();z['http_status']=h.status
  (O/z['source_file']).write_bytes(b);z['sha256']=hashlib.sha256(b).hexdigest();p=L();p.feed(b.decode('utf-8',errors='replace'))
  for a in p.links:
   if a.get('href'):alllinks.append({'label':a['label'],'url':urljoin(u,a['href']),'directory_url':u,'directory_source_sha256':z['sha256']})
  logs.append(z);(O/'expanded_index_ledger.jsonl').write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in logs));print(name,z['http_status'],len(b),flush=True);return p.links
 except urllib.error.HTTPError as e:
  z.update(http_status=e.code,error=str(e));stopped=e.code==429
 except Exception as e:z['error']=type(e).__name__+':'+str(e)
 logs.append(z);(O/'expanded_index_ledger.jsonl').write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in logs));print(name,z.get('http_status'),z.get('error'),flush=True);return None
# Both letter URLs were present in the already-fetched official Browse gateway.
for letter in ['m','l']:fetch('https://www.eoas.info/browse'+letter+'.htm','eoas_'+letter)
base='https://science.org.au/our-focus/history-australian-science/fellows-biographical-memoirs';p=L();p.feed((O/'aas_index.html').read_text());links=p.links
alllinks.extend({'label':a['label'],'url':urljoin(base,a['href']),'directory_url':base,'directory_source_sha256':json.loads((O/'aas_index_request.json').read_text())['sha256']} for a in links if a.get('href'))
seen={base};memoirsets=set();pages=1
while pages<24 and len(logs)<25 and not stopped:
 nextlinks=[a for a in links if a.get('aria-label','').lower()=='next' and a.get('href')]
 if not nextlinks:break
 u=urljoin(base,nextlinks[0]['href'])
 if u in seen:break
 got=fetch(u,'aas_page_'+str(pages));seen.add(u)
 if got is None:break
 current=tuple(sorted(set(urljoin(u,a['href']) for a in got if '/fellows-biographical-memoirs/' in a.get('href',''))))
 if current in memoirsets:break
 memoirsets.add(current);links=got;pages+=1
(O/'expanded_index_links.json').write_text(json.dumps(alllinks,ensure_ascii=False,indent=2))
(O/'expanded_index_summary.json').write_text(json.dumps({'new_directory_requests':len(logs),'AAS_pages_including_initial':pages,'AAS_expected_total_cards':239,'new_HTTP200':sum(x.get('http_status')==200 for x in logs),'HTTP429':sum(x.get('http_status')==429 for x in logs),'stop_on429':stopped,'deadline_reached':time.monotonic()>deadline,'new_request_limit':25,'time_end_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()},indent=2))
print('FINISHED',len(logs),'pages',pages,flush=True)
