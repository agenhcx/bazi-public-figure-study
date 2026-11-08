import pathlib,json,datetime,urllib.request,hashlib,sys
from html.parser import HTMLParser
B=pathlib.Path('academy_v4_workers/vol74');no=int(sys.argv[1]);expected=sys.argv[2]
links=json.loads((B/'retained/observed_toc_links.json').read_text());matches=[u for u,n in links if n==expected];assert matches
url=matches[0].split('#')[0]
existing=list((B/'retained').glob('chapter_*_capture.json'));assert len(existing)<6
intent={'time_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'operation':'chapter_body','ordinal':len(existing)+1,'chapter':no,'source_heading':expected,'url':url,'purpose':'Read once strong fresh official Vol74 match; extract target explicit birth and exact DOB and membership identity','url_provenance':'observed in saved official Volume74 TOC HTML','retry_authorized':False}
with (B/'retained/intents.jsonl').open('a') as f:f.write(json.dumps(intent)+'\n')
try:
 with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=30) as r:
  b=r.read();meta={'request_url':url,'final_url':r.url,'status':r.status,'headers':dict(r.headers),'capture_kind':'original_http_response_bytes','captured_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b),'raw_file':str(B/f'raw_transient/chapter_{no}.html'),'scope':'entire chapter HTML response; no otherchapterbody fetched'}
 raw=B/f'raw_transient/chapter_{no}.html';raw.write_bytes(b)
 class P(HTMLParser):
  def __init__(self):super().__init__();self.text=[];self.skip=0
  def handle_starttag(self,t,a):
   if t in ['script','style']:self.skip+=1
  def handle_endtag(self,t):
   if t in ['script','style']:self.skip=max(0,self.skip-1)
  def handle_data(self,d):
   if not self.skip and d.strip():self.text.append(' '.join(d.split()))
 p=P();p.feed(b.decode());(B/f'raw_transient/chapter_{no}.txt').write_text('\n'.join(p.text));(B/f'retained/chapter_{no}_capture.json').write_text(json.dumps(meta,indent=2));print(json.dumps(meta));
 for i,t in enumerate(p.text):
  if any(x in t.lower() for x in [' born','elected','national academy','october 19','april 10','august 24']):print(i,t[:2200])
except Exception as e:
 err={'request_url':url,'error':str(e),'type':type(e).__name__,'time_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'no_retry':True};(B/f'retained/chapter_{no}_capture.json').write_text(json.dumps(err,indent=2));print(err)
