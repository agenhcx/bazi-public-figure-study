import pathlib,json,datetime,urllib.request,hashlib,sys
from html.parser import HTMLParser
B=pathlib.Path('academy_v5_workers/vol76');kind=sys.argv[1];url=sys.argv[2];stem=sys.argv[3];purpose=sys.argv[4]
ledger=[json.loads(x) for x in (B/'retained/intents.jsonl').read_text().splitlines()];same=[x for x in ledger if x['operation']==kind];limit={'index_navigation':3,'chapter_body':6}[kind];assert len(same)<limit
assert not any(x.get('url')==url for x in same),'no retries authorized'
intent={'time_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'operation':kind,'ordinal':len(same)+1,'url':url,'purpose':purpose,'retry_authorized':False}
with (B/'retained/intents.jsonl').open('a') as f:f.write(json.dumps(intent)+'\n')
try:
 with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=30) as r:
  b=r.read();meta={'request_url':url,'final_url':r.url,'status':r.status,'public_headers':{k:v for k,v in r.headers.items() if k.lower() in ['content-type','content-length','date','last-modified','etag']},'capture_kind':'original_http_response_bytes','captured_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b),'raw_file':str(B/f'raw_transient/{stem}.html'),'scope':'entire requested HTML response only'}
 (B/f'raw_transient/{stem}.html').write_bytes(b)
 class P(HTMLParser):
  def __init__(self):super().__init__();self.text=[];self.skip=0;self.anchor=None;self.links=[];self.images=[]
  def handle_starttag(self,t,a):
   d=dict(a)
   if t in ['script','style']:self.skip+=1
   if t=='a':self.anchor=[d.get('href'),[]]
   if t=='img':self.images.append(d)
  def handle_endtag(self,t):
   if t in ['script','style']:self.skip=max(0,self.skip-1)
   if t=='a' and self.anchor:self.links.append([self.anchor[0],' '.join(' '.join(self.anchor[1]).split())]);self.anchor=None
  def handle_data(self,d):
   if not self.skip and d.strip():self.text.append(' '.join(d.split()))
   if self.anchor:self.anchor[1].append(d)
 p=P();p.feed(b.decode());(B/f'raw_transient/{stem}.txt').write_text('\n'.join(p.text));(B/f'retained/{stem}_capture.json').write_text(json.dumps(meta,indent=2));(B/f'retained/{stem}_observed_links.json').write_text(json.dumps([x for x in p.links if x[0] and '/read/6477' in x[0]],indent=2));(B/f'raw_transient/{stem}_observed_images.json').write_text(json.dumps(p.images,indent=2));print(json.dumps(meta));
 for i,t in enumerate(p.text):
  if kind=='index_navigation' and (' 1-' in t or ' 18-' in t or t in ['Contents']):continue
  if kind=='chapter_body' and any(x in t.lower() for x in [' born','elected','national academy','by ']):print(i,t[:2200])
except Exception as e:
 err={'request_url':url,'error':str(e),'type':type(e).__name__,'time_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'no_retry':True};(B/f'retained/{stem}_capture.json').write_text(json.dumps(err,indent=2));print(err)
