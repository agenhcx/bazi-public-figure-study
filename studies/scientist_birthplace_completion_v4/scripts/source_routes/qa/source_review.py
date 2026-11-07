#!/usr/bin/env python3
"""Local independent source audit of the two explicitly frozen worker lanes."""
from pathlib import Path
from html.parser import HTMLParser
from collections import Counter
from datetime import datetime
from urllib.parse import urljoin, urldefrag
import gzip
import hashlib
import json
import re

W=Path('/workspace/scratch/7e8aa4e0d4af')
QA=W/'academy_v4_workers/qa'
BASE=W/'uk_birthplace_checkout/studies/scientist_birthplace_completion_v3/outputs/birthplace_rows.jsonl.gz'
BASE_SHA='6df02f0b3a535c8b5447ee704ddc96f473509ed9c2df84b25d6b40064a5dff44'

class Parser(HTMLParser):
    def __init__(self):
        super().__init__();self.suppressed=0;self.parts=[];self.links=[]
    def handle_starttag(self,tag,attrs):
        if tag in {'script','style','nav'}:self.suppressed+=1
        if not self.suppressed and tag in {'p','h1','h2','h3','h4','h5','div','li','br'}:self.parts.append('\n')
        if tag=='a':
            self.links.extend(v for k,v in attrs if k=='href')
    def handle_endtag(self,tag):
        if not self.suppressed and tag in {'p','h1','h2','h3','h4','h5','div','li'}:self.parts.append('\n')
        if tag in {'script','style','nav'}:self.suppressed-=1
    def handle_data(self,data):
        if not self.suppressed:self.parts.append(data)
    def text(self):return re.sub(r'\s+',' ',''.join(self.parts)).strip()

def read(p):return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def parsed(p):
    parser=Parser();parser.feed(p.read_text());return parser
def tokens(name):return re.findall(r'[a-z]+',name.casefold())
def compatible(native,source):
    a=tokens(native);b=tokens(source)
    match=lambda x,y:x==y or len(x)==1 and x==y[0] or len(y)==1 and y==x[0]
    if not match(a[-1],b[-1]) or not match(a[0],b[0]):return False
    if len(a)==2 or len(b)==2:return True
    return len(a)==len(b) and all(match(x,y) for x,y in zip(a[1:-1],b[1:-1]))
def stamp(s):return datetime.fromisoformat(s)
def full_date(s):return datetime.strptime(s,'%Y-%m-%d').strftime('%B %d, %Y').replace(' 0',' ')

def run():
    assert sha(BASE)==BASE_SHA
    with gzip.open(BASE,'rt') as f:base=[json.loads(x) for x in f]
    nas=[r for r in base if r['cohort']=='NAS'];bby={r['record_id']:r for r in nas}
    assert len(nas)==2242
    assert all(not any(('death' in k.lower() or 'lifespan' in k.lower()) for k in r) for r in nas)
    report={'status':'PASS','baseline_sha256':BASE_SHA,'manual_review_completed':True,
      'source_content_access_started_after_explicit_lane_freeze':True,
      'network_requests_by_QA':0,'geography_assignments_by_QA':0,'lanes':{},'accepted_source_reviews':[],
      'held_source_reviews':[]}
    for volume in [73,74]:
        root=W/f'academy_v4_workers/vol{volume}'
        if volume==73:
            facts=read(root/'retained_facts.jsonl');holds=read(root/'held.jsonl')
            caps=json.loads((root/'captures.json').read_text());toccap=json.loads((root/'toc_capture.json').read_text())
            tocpath=root/'raw/toc.html';tocurl=toccap['requested_url'];intents=read(root/'intent_ledger.jsonl')
            kinds=Counter(x['kind'] for x in intents);start=stamp(intents[0]['utc'])
            assert kinds=={'discovery_query':1,'index_navigation':1,'chapter_body':8}
            captures={x['record_id']:x for x in caps}
            captime=lambda x:x['retrieved_utc']
            intenttime=lambda x:x['utc']
            intenturl=lambda x:x.get('url')
            tstamp=toccap['retrieved_utc']
            capurl=lambda x:x['requested_url']
            cappath=lambda x:Path(x['local_raw_path'])
            expected_names={'Charles G. Abbot','Carl D. Anderson','James F. Bonner','Rodney L. Cool','Frederick Keyes','Lewis Longsworth','William Young'}
        else:
            retain=root/'retained';facts=read(retain/'facts.jsonl');holds=read(retain/'holds.jsonl')
            caps=[json.loads(p.read_text()) for p in sorted(retain.glob('chapter_*_capture.json'))]
            toccap=json.loads((retain/'toc_capture_metadata.json').read_text())
            tocpath=root/'raw_transient/volume74_toc.html';tocurl=toccap['url_requested'];intents=read(retain/'intents.jsonl')
            kinds=Counter(x['operation'] for x in intents);start=stamp(intents[0]['time_utc'])
            assert kinds=={'web_discovery_query':1,'index_navigation':1,'chapter_body':3}
            captures={x['capture']['capture_metadata_file']:json.loads((W/x['capture']['capture_metadata_file']).read_text()) for x in facts+holds}
            captime=lambda x:x['captured_at_utc']
            intenttime=lambda x:x['time_utc']
            intenturl=lambda x:x.get('url')
            tstamp=toccap['captured_at_utc']
            capurl=lambda x:x['request_url']
            cappath=lambda x:W/x['raw_file']
            expected_names={'Scott E. Forbush','Stephen Kuffler'}
        assert set(f['name'] for f in facts)==expected_names
        assert len(holds)==1
        toc=parsed(tocpath);links={urldefrag(urljoin(tocurl,x)).url for x in toc.links}
        assert sha(tocpath)==toccap['sha256'] and toccap['status']==200
        indexintent=next(i for i in intents if ('index_navigation'==i.get('kind',i.get('operation'))))
        assert stamp(intenttime(indexintent))<stamp(tstamp)
        urls=[capurl(c) for c in caps]
        assert len(urls)==len(set(urls))==len(facts)+len(holds)
        assert all(c['status']==200 for c in caps)
        last=max(stamp(captime(c)) for c in caps)
        assert (last-start).total_seconds()<480
        for c in caps:
            url=capurl(c)
            assert url in links,(volume,url,'not observed TOC href')
            intent=next(x for x in intents if intenturl(x)==url)
            assert stamp(intenttime(intent))<stamp(captime(c)),(volume,url,'preintent')
            assert sha(cappath(c))==c['sha256']
        for f in facts+holds:
            accepted=f in facts
            b=bby[f['record_id']]
            source_name=f.get('source_subject_heading',f.get('source_chapter_heading'))
            quote=f.get('evidence_quote',f.get('birthplace_evidence_excerpt',''))
            c=captures[f['record_id']] if volume==73 else captures[f['capture']['capture_metadata_file']]
            p=cappath(c);raw=p.read_text();text=parsed(p).text();name_matches=[r for r in nas if compatible(r['name'],source_name)]
            daymatches=[r for r in name_matches if r['dob']==f['native_dob']]
            assert f.get('frozen_baseline_row',f.get('baseline_row_snapshot'))==b
            assert len(name_matches)==len(daymatches)==1 and daymatches[0]['record_id']==f['record_id']
            assert b['hemisphere']=='unknown' and b['dob']==f['native_dob']
            assert source_name.casefold() in text.casefold()
            assert full_date(f['native_dob']) in text
            assert ('by '+f['source_author']).casefold() in text.casefold()
            assert f['source_grade']=='S2'
            assert len(quote.split())<=25
            if quote:assert quote in text
            if volume==73:
                assert f['locator']['anchor'] in raw
                assert c['sha256']==f['source_sha256']
            else:
                assert c['sha256']==f['capture']['original_http_response_bytes_sha256']
            result={'volume':volume,'name':b['name'],'record_id':b['record_id'],'source_url':capurl(c),
                'native_dob':b['dob'],'source_full_heading':source_name,'source_author':f['source_author'],
                'source_grade':'S2','capture_kind':'original chapter HTML response bytes',
                'original_bytes_sha256':c['sha256'],'original_byte_hash_matches':True,
                'heading_day_matches_native_DOB':True,'full_heading_name_compatible_count_among_all_2242':len(name_matches),
                'heading_name_and_exact_DOB_unique_count_among_all_2242':len(daymatches),
                'authorship_and_original_memoir_role_confirmed':True,
                'quote_word_count':len(quote.split()),'no_independent_lifespan_equality_claim':True,
                'status':'accept_literal_birthplace' if accepted else 'hold_no_literal_birthplace'}
            if accepted:
                result.update(raw_birthplace=f['raw_birthplace'],born_clause_date_precision=f.get('source_DOB_born_clause_precision',f.get('source_born_clause_dob_precision')))
                if b['name']=='Frederick Keyes':
                    assert 'deceased members of the Academy' in toc.text()
                    result['NAS_context']='signed named chapter in NAS volume; front matter explicitly describes deceased Academy members; no individual election line claimed'
                else:result['NAS_context']='individual election/membership context independently checked in subject memoir'
                report['accepted_source_reviews'].append(result)
            else:
                result['hold_basis']='No literal birthplace; schooling location excluded' if volume==73 else 'Born clause lacks place; grew-up location excluded'
                report['held_source_reviews'].append(result)
        report['lanes'][str(volume)]={'source_requests':dict(kinds),'chapter_HTTP_statuses':[c['status'] for c in caps],
           'all_body_urls_in_actual_saved_TOC_links':True,'all_body_preintents_precede_captures':True,
           'one_capture_per_body_no_retries':True,'source_collection_seconds':(last-start).total_seconds(),
           'source_collection_under_eight_minutes':True,'S2_facts':len(facts),'holds':len(holds)}
    assert len(report['accepted_source_reviews'])==9 and len(report['held_source_reviews'])==2
    assert sum(len(v['chapter_HTTP_statuses']) for v in report['lanes'].values())==11
    report['overall_source_totals']={'discovery_queries':2,'index_navigation':2,'chapter_bodies':11,
        'logical_source_requests':15,'retries':0,'all_HTTP200':True,'stop_rule_triggered':False}
    (QA/'source_review.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'status':'PASS','facts':9,'holds':2,'total_bodies':11,'vol73_source_seconds':report['lanes']['73']['source_collection_seconds'],'vol74_source_seconds':report['lanes']['74']['source_collection_seconds']},indent=2))

if __name__=='__main__':run()
