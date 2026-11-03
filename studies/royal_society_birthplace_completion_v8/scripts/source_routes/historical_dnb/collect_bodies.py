from pathlib import Path
import urllib.request,urllib.parse,urllib.error,json,hashlib,time,datetime,re
import html
def clean(x):return re.sub(r"\s+"," ",html.unescape(re.sub(r"<[^>]+>"," ",x))).strip()
O=Path(__file__).parent;last=0;ledger=[]
def get(name,title):
 global last
 delay=1.1-(time.monotonic()-last)
 if delay>0:time.sleep(delay)
 last=time.monotonic();u='https://en.wikisource.org/w/api.php?'+urllib.parse.urlencode({'action':'parse','page':title,'prop':'text|properties','format':'json','formatversion':'2','redirects':'1'})
 m={'title':title,'request_url':u,'request_started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'file':'raw/'+name+'.json'}
 try:
  with urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'BirthplaceEvidenceResearch/1.0'}),timeout=25) as h:b=h.read();m['http_status']=h.status
  (O/m['file']).write_bytes(b);m['source_sha256']=hashlib.sha256(b).hexdigest();d=json.loads(b)
  if 'parse' not in d:m['error']=d.get('error');return None,m
  soup=d['parse']['text'];text=clean(soup)
  (O/'raw'/(name+'.txt')).write_text(text)
  return (d,soup,text),m
 except urllib.error.HTTPError as e:
  m['http_status']=e.code;m['error']=str(e)
  if e.code==429:(O/'STOP_HTTP429.json').write_text(json.dumps(m));raise
  return None,m
 except Exception as e:m['error']=str(e);return None,m
 finally:
  ledger.append(m);(O/'request_ledger.jsonl').write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in ledger))
# Verified publisher-edition main index from web discovery.
z,m=get('index1927','Dictionary of National Biography, 1927 supplement')
selected=[]
targets=json.loads((O/'targets.json').read_text())
if z:
 links=[html.unescape(a) for a in re.findall(r'title="([^"]+)"',z[1]) if html.unescape(a).startswith('Dictionary of National Biography, 1927 supplement/')]
 for r in targets:
  surname=r['source_authorised_full_name'].split(';')[0]
  for title in dict.fromkeys(links):
   if title.startswith('Dictionary of National Biography, 1927 supplement/'+surname+','):
    selected.append({'record_id':r['record_id'],'title':title,'official_full_name':r['source_authorised_full_name']})
 print('INDEX_MATCHES',json.dumps(selected,ensure_ascii=False),flush=True)
# Keep exact selected surname+given identity; no unrelated same-surname body expansion.
manual={'RS_PAST_NA1510':'Dictionary of National Biography, 1912 supplement/Broadbent, William Henry','RS_PAST_NA3559':'Dictionary of National Biography, 1912 supplement/Hamilton, David James'}
for x in selected:
 rid=x['record_id'];name=x['title'].split('/')[-1]
 # remove Sir/role/birth-year material from authorised name, literal significant given name test
 official=x['official_full_name'];bits=[b.strip() for b in official.split(';')]
 given=next((b.split('(')[0].strip() for b in bits[1:] if '(' in b),'')
 if given and name.split(', ',1)[-1].casefold()==given.casefold():manual[rid]=x['title']
(O/'selection.json').write_text(json.dumps({'index1927_source':m,'matches':selected,'selected':manual},ensure_ascii=False,indent=2))
for i,(rid,title) in enumerate(manual.items()):
 if i>=9:break
 z,m=get(rid,title)
 if z:
  ps=[clean(p) for p in re.findall(r'<p(?: [^>]*)?>(.*?)</p>',z[1],re.S) if clean(p)]
  print('\nBODY',rid,title,'\n', '\n'.join(ps[:2])[:2300],flush=True)
  # exact locality anchors remain available in HTML; preserve only source locator metadata now
