"""Bounded v10 EOAS Y/Z route. Uses only observed links; zero retries/redirects."""
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urljoin
import urllib.request, urllib.error, hashlib, json, datetime, re, sys, os
ROOT=Path(__file__).resolve().parent
WORKSPACE=ROOT.parent.parent
BASE='https://www.eoas.info/'
BASELINE=WORKSPACE/'uk_birthplace_checkout/studies/royal_society_birthplace_completion_v9/outputs/uk_birthplace_rows.jsonl.gz'
EXPECTED_SHA='e44f6dc02cc0cafece9b792164f016da0f08de5736ac62442d176d45b19a5799'

def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def read_jsonl(name):
    path=ROOT/name
    return [json.loads(x) for x in path.read_text().splitlines()] if path.exists() else []
def durable_append(name,row):
    ROOT.mkdir(parents=True,exist_ok=True)
    with (ROOT/name).open('a') as f:
        f.write(json.dumps(row,ensure_ascii=False,sort_keys=True)+'\n');f.flush();os.fsync(f.fileno())
def write_jsonl(name,rows):
    with (ROOT/name).open('w') as f:
        for row in rows:f.write(json.dumps(row,ensure_ascii=False,sort_keys=True)+'\n')

class Links(HTMLParser):
    def __init__(self):super().__init__(convert_charrefs=True);self.links=[];self.active=None
    def handle_starttag(self,tag,attrs):
        if tag=='a':self.active=[dict(attrs).get('href',''),[]]
        elif tag=='br' and self.active is not None:self.active[1].append(' ')
    def handle_data(self,text):
        if self.active is not None:self.active[1].append(text)
    def handle_endtag(self,tag):
        if tag=='a' and self.active is not None:
            href,text=self.active;self.links.append({'href':href,'text':re.sub(r'\s+',' ',''.join(text)).strip()});self.active=None

def fetch(kind,url,slug,purpose):
    if (ROOT/'FROZEN.json').exists():raise RuntimeError('Route frozen')
    intents=read_jsonl('request_intents.jsonl');ledger=read_jsonl('requests.jsonl')
    assert not any(x['url']==url for x in intents),'No retries: URL already has a durable intent'
    assert not any(x.get('status_code')==429 for x in ledger),'Global stop on 429'
    assert not (len(ledger)>=2 and all(x.get('status_code')==503 for x in ledger[-2:]) and ledger[-1].get('source_sha256')==ledger[-2].get('source_sha256')),'Stop on two consecutive identical 503 responses'
    assert sum(x['kind']==kind for x in intents)<({'navigation_index':2,'biography_body':4}[kind])
    if kind=='navigation_index':
        prior=json.loads((WORKSPACE/'uk_birthplace_v9_workers/eoas/navigation.json').read_text())
        observed=[x for x in prior['alphabet_links'] if x['letter'] in ['Y','Z']]
        assert url in {x['url'] for x in observed},'Index must be observed Y or Z URL'
    else:
        candidates=read_jsonl('candidate_projection.jsonl')
        assert any(x['source_url']==url and x['strong_candidate'] and not x['already_frozen_source'] for x in candidates),'Only strong new frozen-directory candidate bodies permitted'
    intent={'kind':kind,'url':url,'purpose':purpose,'started_utc':now(),'attempt':1,'retries':0,'redirect_follow':False}
    durable_append('request_intents.jsonl',intent)
    result=dict(intent)
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,*args,**kwargs):return None
    try:
        request=urllib.request.Request(url,headers={'Accept-Encoding':'identity','User-Agent':'Mozilla/5.0 (compatible; ResearchEvidence/1.0)'})
        try:response=urllib.request.build_opener(NoRedirect).open(request,timeout=40)
        except urllib.error.HTTPError as error:response=error
        raw=response.read();path=ROOT/'raw'/f'{slug}.httpbody';path.parent.mkdir(exist_ok=True);path.write_bytes(raw)
        result.update(status_code=response.status,response_headers=dict(response.headers),byte_count=len(raw),source_sha256=hashlib.sha256(raw).hexdigest(),raw_source_file=str(path.relative_to(WORKSPACE)))
    except BaseException as error:
        result.update(error=repr(error),status='interrupted' if isinstance(error,KeyboardInterrupt) else 'transport_error')
    result['finished_utc']=now();durable_append('requests.jsonl',result)
    print(json.dumps({k:v for k,v in result.items() if k!='response_headers'},indent=2),flush=True)
    return result

if __name__=='__main__':
    if len(sys.argv)==5:fetch(*sys.argv[1:])
    else:raise SystemExit('usage: route.py KIND URL SLUG PURPOSE')
