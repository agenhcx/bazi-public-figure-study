from pathlib import Path
import urllib.request,urllib.parse,urllib.error,json,hashlib,time,datetime
O=Path(__file__).parent;(O/'raw').mkdir(exist_ok=True)
ledger=[];last=0
# One API call inspects known verified 1912 volume index links. This is not a person/DOB query.
titles=['Dictionary of National Biography, 1912 supplement/Volume '+str(i) for i in [1,2,3]]
u='https://en.wikisource.org/w/api.php?'+urllib.parse.urlencode({'action':'query','titles':'|'.join(titles),'prop':'links','pllimit':'max','format':'json','formatversion':'2'})
start=datetime.datetime.now(datetime.timezone.utc).isoformat()
try:
 with urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'BirthplaceEvidenceResearch/1.0'}),timeout=30) as r:data=r.read();status=r.status
 (O/'raw/index_links.json').write_bytes(data)
 meta={'source_url':u,'retrieved_utc':start,'http_status':status,'source_sha256':hashlib.sha256(data).hexdigest(),'file':'raw/index_links.json'}
except Exception as e:meta={'source_url':u,'retrieved_utc':start,'error':str(e)}
(O/'index_meta.json').write_text(json.dumps(meta,indent=2))
if 'error' not in meta:
 d=json.loads(data);print('continue',d.get('continue'))
 for p in d.get('query',{}).get('pages',[]):
  print(p.get('title'),len(p.get('links',[])))
  matches=[]
  targets=json.loads((O/'targets.json').read_text())
  for t in targets:
   surname=t['source_authorised_full_name'].split(';')[0]
   full=t['source_authorised_full_name']
   for a in p.get('links',[]):
    label=a.get('title','')
    if label.startswith('Dictionary of National Biography, 1912 supplement/'+surname+','):matches.append({'record_id':t['record_id'],'official_full_name':full,'title':label})
  print(json.dumps(matches,ensure_ascii=False))
