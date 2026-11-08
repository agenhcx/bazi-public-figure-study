"""Bounded EOAS v9 route: original byte fetches, no redirect/retry, observed links."""
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urljoin
import urllib.request, urllib.error, hashlib, json, datetime, re, sys

ROOT = Path(__file__).resolve().parent
LEDGER = ROOT / 'requests.jsonl'
BASE = 'https://www.eoas.info/'

class Links(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links=[]; self.active=None
    def handle_starttag(self, tag, attrs):
        if tag == 'a': self.active = [dict(attrs).get('href', ''), []]
        elif tag == 'br' and self.active is not None: self.active[1].append(' ')
    def handle_data(self, text):
        if self.active is not None: self.active[1].append(text)
    def handle_endtag(self, tag):
        if tag == 'a' and self.active is not None:
            href, text = self.active
            self.links.append({'href': href, 'text': re.sub(r'\s+', ' ', ''.join(text)).strip()})
            self.active=None

def records():
    return [json.loads(x) for x in LEDGER.read_text().splitlines()] if LEDGER.exists() else []

def fetch(url, kind, slug, purpose):
    previous = records()
    if kind == 'navigation_index' and (ROOT/'source_boundary.json').exists(): raise RuntimeError('Alphabet route frozen by root; no further index requests')
    if kind == 'biography_body':
        authorized=json.loads((ROOT/'authorized_bodies.json').read_text())
        if url not in authorized['allowed_urls']: raise RuntimeError('Body URL not in explicit root authorization')
        bodies=[x for x in previous if x['kind']=='biography_body']
        if len(bodies)>=3: raise RuntimeError('Root bounded biography requests to 3')
        if len(bodies)>=2 and all(x.get('status_code')==503 for x in bodies[-2:]) and bodies[-1].get('source_sha256')==bodies[-2].get('source_sha256'): raise RuntimeError('Stop on consecutive identical biography HTTP 503')
    if any(x['url']==url for x in previous): raise RuntimeError('No retries: URL already attempted')
    if any(x.get('status_code')==429 for x in previous): raise RuntimeError('Global EOAS stop on 429')
    cap = 24 if kind == 'navigation_index' else 10
    if sum(x['kind']==kind for x in previous)>=cap: raise RuntimeError('Request cap reached')
    rec={'kind':kind,'purpose':purpose,'url':url,'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'attempt':1,'retries':0}
    with (ROOT/'durable_request_intents.jsonl').open('a') as handle: handle.write(json.dumps(rec,ensure_ascii=False)+'\n')
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,*args,**kwargs): return None
    opener=urllib.request.build_opener(NoRedirect)
    try:
        req=urllib.request.Request(url,headers={'Accept-Encoding':'identity','User-Agent':'Mozilla/5.0 (compatible; ResearchEvidence/1.0)'})
        try: response=opener.open(req,timeout=45)
        except urllib.error.HTTPError as error: response=error
        body=response.read()
        raw=ROOT/'raw'/f'{slug}.httpbody'
        raw.write_bytes(body)
        rec.update(status_code=response.status,response_headers=dict(response.headers),byte_count=len(body),source_sha256=hashlib.sha256(body).hexdigest(),raw_source_file=str(raw.relative_to(ROOT.parent.parent)))
    except Exception as error: rec['error']=repr(error)
    rec['finished_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
    with LEDGER.open('a') as handle: handle.write(json.dumps(rec,ensure_ascii=False)+'\n')
    print(json.dumps({k:v for k,v in rec.items() if k not in ['response_headers']}),flush=True)
    return rec

def census():
    a=Links(); a.feed((ROOT/'raw'/'index_a.httpbody').read_text())
    nav=[{'letter':x['href'][6].upper(),'url':urljoin(BASE,x['href']),'observed_on':BASE+'browsea_people.htm'} for x in a.links if re.fullmatch(r'browse[a-z]_people\.htm',x['href'])]
    assert len(nav)==26 and len({x['letter'] for x in nav})==26
    (ROOT/'navigation.json').write_text(json.dumps({'discovery':'One web search located official A index; no individual birthday queries. A index navigation links observed in original HTML.','alphabet_links':nav,'excluded_v8_letters':['L','M'],'navigation_index_cap':24,'discovery_plus_navigation_cap':25,'body_cap':10,'redirects':0,'retries':0},indent=2)+'\n')
    for item in nav:
        if item['letter'] in ['A','L','M']: continue
        rec=fetch(item['url'],'navigation_index','index_'+item['letter'].lower(),'Remaining letter index observed on A navigation')
        if rec.get('status_code')==429: break
    rows=[]; counts=[]
    for rec in records():
        if rec['kind']!='navigation_index' or rec.get('status_code')!=200: continue
        letter=re.search('browse([a-z])_people',rec['url']).group(1).upper()
        links=Links(); links.feed((ROOT/'raw'/('index_'+letter.lower()+'.httpbody')).read_text())
        biographies=[x for x in links.links if re.fullmatch(r'biogs/P\d+b\.htm',x['href'])]
        counts.append({'letter':letter,'biography_link_count':len(biographies),'unique_biography_urls':len({x['href'] for x in biographies}),'source_url':rec['url'],'source_sha256':rec['source_sha256']})
        for x in biographies: rows.append({'index_letter':letter,'index_text':x['text'],'source_url':urljoin(BASE,x['href']),'index_url':rec['url'],'index_source_sha256':rec['source_sha256']})
    with (ROOT/'directory_projection.jsonl').open('w') as handle:
        for row in rows: handle.write(json.dumps(row,ensure_ascii=False)+'\n')
    (ROOT/'directory_census.json').write_text(json.dumps({'indices':counts,'letter_indices_observed':len(counts),'biography_links':len(rows),'unique_biography_urls':len({x['source_url'] for x in rows}),'scope':'Directory links only; no claim that indexed biography bodies were read.'},indent=2)+'\n')
    print(json.dumps({'completed_indices':len(counts),'links':len(rows),'unique_urls':len({x['source_url'] for x in rows})}),flush=True)

if __name__=='__main__':
    if sys.argv[1:] == ['census']: census()
    elif len(sys.argv)==5 and sys.argv[1]=='body': fetch(sys.argv[2],'biography_body',sys.argv[3],sys.argv[4])
    else: raise SystemExit('usage: census.py census | body URL SLUG PURPOSE')
