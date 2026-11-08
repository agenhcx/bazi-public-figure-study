import concurrent.futures, datetime, hashlib, json, pathlib, re, urllib.request, urllib.parse, subprocess
from html.parser import HTMLParser
class Extract(HTMLParser):
    def __init__(self): super().__init__(); self.out=[]
    def handle_data(self,data): self.out.append(data)
def htmltext(b):
    x=Extract(); x.feed(b.decode('utf-8',errors='replace')); return '\n'.join(x.out)
ROOT=pathlib.Path(__file__).resolve().parent
def urlfix(u):
    s=urllib.parse.urlsplit(u)
    return urllib.parse.urlunsplit((s.scheme,s.netloc,urllib.parse.quote(urllib.parse.unquote(s.path),safe='/:%'),s.query,s.fragment))
def fetch(item):
    u,n=item; t=datetime.datetime.now(datetime.timezone.utc).isoformat()
    ident=hashlib.sha256(u.encode()).hexdigest()[:16]
    try:
        req=urllib.request.Request(urlfix(u),headers={'User-Agent':'Mozilla/5.0'})
        with urllib.request.urlopen(req,timeout=25) as r:
            b=r.read(); status=r.status; ct=r.headers.get('Content-Type',''); final=r.url
        pdf=b.startswith(b'%PDF-')
        p=ROOT/'private'/(ident+('.pdf' if pdf else '.html'))
        p.write_bytes(b)
        if pdf:
            tp=p.with_suffix('.txt'); subprocess.run(['pdftotext','-layout',str(p),str(tp)],capture_output=True)
            text=tp.read_text(errors='replace') if tp.exists() else ''
        else:
            text=htmltext(b)
            p.with_suffix('.txt').write_text(text)
        compact=re.sub(r'\s','',text)
        match=any(re.sub(r'\s','',x) in compact for x in n)
        valid=(pdf or match) and not ('Error' in text[:100] and not match)
        return {'source_url':u,'retrieved_utc':t,'http_status':status,'final_url':final,'content_type':ct,'bytes':len(b),'private_path':str(p.relative_to(ROOT)),'identity_text_observed':match,'valid_original_body_captured':valid,'source_sha256':hashlib.sha256(b).hexdigest() if valid else None,'note':'PDF may require visual identity verification' if pdf and not match else ''}
    except Exception as e:
        return {'source_url':u,'retrieved_utc':t,'valid_original_body_captured':False,'source_sha256':None,'error':str(e)}
if __name__=='__main__':
    obs=json.loads((ROOT/'observations.json').read_text())
    import csv
    queue=list(csv.DictReader((ROOT.parent/'queues/japan_3.csv').open()))
    urls={o['url']:[queue[o['i']]['name_jp'].replace(' ','' )] for o in obs if o.get('url')}
    extra=ROOT/'extra_sources.json'
    if extra.exists(): urls.update(json.loads(extra.read_text()))
    oldp=ROOT/'source_capture_log.json'; old=json.loads(oldp.read_text()) if oldp.exists() else []
    seen={x['source_url'] for x in old}; todo=[x for x in urls.items() if x[0] not in seen]
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex: new=list(ex.map(fetch,todo))
    oldp.write_text(json.dumps(old+new,ensure_ascii=False,indent=2))
    print(json.dumps([{'url':x['source_url'],'valid':x['valid_original_body_captured'],'bytes':x.get('bytes'),'error':x.get('error')} for x in new],ensure_ascii=False))
