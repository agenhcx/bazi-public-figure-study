"""Read-only audit of frozen NAS signed memoirs and complete logical request ledger."""
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urljoin,urldefrag
import collections
import datetime
import gzip
import hashlib
import json
import re

ROOT=Path('/workspace/scratch/7e8aa4e0d4af')
WORK=ROOT/'academy_v3_workers/nas_memoirs'
RET=WORK/'retained';QA=ROOT/'academy_v3_workers/qa'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def jl(p):return [json.loads(x) for x in p.read_text().splitlines() if x]
def canon(x):return json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(',',':'))
class Text(HTMLParser):
    def __init__(self):super().__init__(convert_charrefs=True);self.parts=[];self.skip=0;self.hrefs=[]
    def handle_starttag(self,t,a):
        if t=='a':self.hrefs.extend(v for k,v in a if k=='href')
        if t in {'script','style'}:self.skip+=1
        if t in {'p','div','h1','h2','h3','h4','br','tr','td','li'} and not self.skip:self.parts.append(' ')
    def handle_endtag(self,t):
        if t in {'script','style'}:self.skip=max(0,self.skip-1)
        if t in {'p','div','h1','h2','h3','h4','br','tr','td','li'} and not self.skip:self.parts.append(' ')
    def handle_data(self,d):
        if not self.skip:self.parts.append(d)
    def text(self):return ' '.join(''.join(self.parts).split())
def html(p):
    parser=Text();parser.feed(p.read_text());return parser
def name_compatible(native,title):
    a=re.findall('[a-z]+',native.lower());b=re.findall('[a-z]+',title.lower())
    return len(a)==len(b) and a[-1]==b[-1] and all(x==y or (len(x)==1 and y.startswith(x)) for x,y in zip(a[:-1],b[:-1]))

basep=ROOT/'uk_birthplace_checkout/studies/scientist_birthplace_completion_v2/outputs/birthplace_rows.jsonl.gz'
assert sha(basep)=='2b7897d0c4e2655ecb6f10311e1bdf7b06b8eeae3f181e9bebe92cbc7f066ee0'
base={(r['cohort'],r['record_id']):r for r in [json.loads(x) for x in gzip.decompress(basep.read_bytes()).splitlines()]}
unknown_selection=jl(WORK/'unknown_selection.jsonl')
unknown_expected={k:v for k,v in base.items() if k[0]=='NAS' and v['hemisphere']=='unknown'}
assert len(unknown_selection)==len(unknown_expected)==574
assert {(r['cohort'],r['record_id']) for r in unknown_selection}==set(unknown_expected)
assert all(canon(r)==canon(unknown_expected[(r['cohort'],r['record_id'])]) for r in unknown_selection)
facts=jl(RET/'source_facts.jsonl');held=jl(RET/'held_source_candidates.jsonl')
assert len(facts)==7 and len(held)==1
expected={
    'L. A. DuBridge':('LEE ALVIN DUBRIDGE','1901-09-21','Terre Haute, Indiana'),
    'R. G. Herb':('RAYMOND GEORGE HERB','1908-01-22','Navarino on a small farm in north-central Wisconsin'),
    'Donald W. Kerst':('DONALD WILLIAM KERST','1911-11-01','Galena, Illinois'),
    'Paul J. Kramer':('PAUL JACKSON KRAMER','1904-05-08','Brookville, Indiana'),
    'W. W. Morgan':('WILLIAM WILSON MORGAN','1906-01-03','Bethesda, Tennessee'),
    'M. M. Rhoades':('MARCUS MORTON RHOADES','1903-07-24','Graham, Missouri'),
    'J. E. Varner':('JOSEPH E. VARNER','1921-10-07','Nashport, Ohio'),
}
checked=[]
for f in facts:
    assert f['cohort']=='NAS' and (f['source_title'],f['native_dob'],f['raw_birthplace'])==expected[f['name']]
    b=base[(f['cohort'],f['record_id'])]
    assert canon(f['frozen_baseline_row'])==canon(b)
    assert b['name']==f['name'] and b['dob']==f['native_dob'] and b['hemisphere']=='unknown'
    assert name_compatible(f['name'],f['source_title'])
    compatible_native_keys=[k for k,r in base.items() if k[0]=='NAS' and r['dob']==f['source_dob'] and name_compatible(r['name'],f['source_title'])]
    assert compatible_native_keys==[(f['cohort'],f['record_id'])]
    assert f['source_grade']=='S2' and f['source_kind']=='edited_signed_biographical_memoir'
    path=ROOT/f['raw_source_file'];text=html(path).text()
    assert sha(path)==f['original_bytes_sha256']
    assert f['capture_kind']=='original_HTTP_response_body' and 'HTML' in f['capture_scope']
    assert f['evidence_quote'] in text and len(f['evidence_quote'].split())<=25
    assert 'born' in f['evidence_quote'].lower()
    assert f['source_title']+' '+f['identity_review']['source_heading_lifespan']+' BY '+f['source_author'] in text
    assert datetime.datetime.strptime(f['source_dob_heading_text'],'%B %d, %Y').date().isoformat()==f['source_dob']==f['native_dob']
    assert f['source_dob_precision']=='day' and not f['source_fact_adopted_into_baseline']
    assert not f['geography_country_or_point_assignment']
    i=f['identity_review']
    assert i['source_full_target_name']==f['source_title'] and i['source_dob_agrees_with_native']
    assert not any(i[k] for k in ['accepted_gregorian_dob_modified','dob_status_or_tier_modified','eligibility_modified','formal_identity_modified','native_dob_modified','qid_used_or_modified','parent_job_nationality_education_or_deathplace_used_as_birthplace'])
    assert 'National Academy of Sciences' in text
    if f['name']=='R. G. Herb':assert f['birth_clause_dob_precision']=='year'
    if f['name'] in {'Paul J. Kramer','J. E. Varner'}:assert f['birth_clause_dob_precision']=='none'
    checked.append({**{k:f[k] for k in ['cohort','record_id','name','native_dob','raw_birthplace','source_grade','evidence_quote','source_url','source_author','source_title','source_dob_precision','birth_clause_dob_precision','capture_kind']},'source_sha256':f['original_bytes_sha256']})

h=held[0];hb=base[(h['cohort'],h['record_id'])]
assert h['name']=='S. Chandrasekhar' and h['native_dob']==hb['dob']=='1910-10-19'
assert h['source_dob']=='1910-10-13' and h['review_status']=='held_source_dob_conflict'
assert all(f['record_id']!=h['record_id'] for f in facts)
hp=ROOT/h['raw_source_file'];ht=html(hp).text()
assert sha(hp)==h['original_bytes_sha256']
assert h['source_title']+' '+h['identity_review']['source_heading_lifespan']+' BY '+h['source_author'] in ht
assert h['evidence_quote'] in ht and len(h['evidence_quote'].split())<=25

ledger=jl(RET/'request_ledger.jsonl')
intents=[x for x in ledger if x['event']=='intent'];results=[x for x in ledger if x['event']=='result']
assert len(intents)==len(results)==16
assert {x['request_id'] for x in intents}=={x['request_id'] for x in results}
queries=[x for x in intents if x['kind']=='discovery_query']
chapters=[x for x in intents if x['kind']=='approved_independently_authored_memoir_full_body']
index=[x for x in intents if x not in queries and x not in chapters]
assert len(queries)==3 and len(index)==5 and len(chapters)==8
for x in results:
    pth=ROOT/x['raw_source_file'];expected_hash=x.get('original_bytes_sha256',x.get('web_projection_sha256'))
    assert sha(pth)==expected_hash
    if x['request_id'].startswith('nas_memoirs_chapter_'):
        assert x['http_status']==200 and x['capture_kind']=='original_HTTP_response_body'
        assert pth.stat().st_size==x['bytes']
toc=html(WORK/'raw/nas_memoirs_nav_05.html')
observed={urldefrag(urljoin('https://www.nationalacademies.org/read/5859',u))[0] for u in toc.hrefs}
assert all(x['url'] in observed for x in chapters)
auth=[x for x in ledger if x['event']=='authorization']
assert len(auth)==1 and auth[0]['chapters']==[4,7,11,14,15,17,18,20]
assert all(x.get('attempt',1)==1 and not x.get('retry_allowed',False) for x in intents)
old=jl(ROOT/'academy_next_workers/nas/retained/selection.jsonl')
assert not {x.get('url') for x in intents}&{x['record_id'] for x in old}
coverage=jl(RET/'coverage.jsonl');assert len(coverage)==8
assert {x['record_id'] for x in coverage}=={x['record_id'] for x in facts+held}
summary=json.loads((RET/'summary.json').read_text())
assert summary['all_request_attempts']==16 and summary['birthplace_source_facts_ready_for_parent_merge']==7
assert summary['held_birthplace_candidates']==1 and summary['retries']==0
assert summary['initial_discovery_queries']==3 and summary['initial_index_navigation_requests']==5
assert summary['approved_memoir_chapter_full_body_requests']==summary['approved_memoir_chapter_http200_captures']==8
assert summary['unknown_nas_rows_bulk_compared']==574

report={'status':'PASS','accepted_S2_facts':len(facts),'held_candidates':len(held),
    'held_candidate':{'record_id':h['record_id'],'native_dob':h['native_dob'],'source_heading_dob':h['source_dob'],'adopted':False},
    'full_name_initials_expansion_plus_exact_DOB_and_NAS_context_verified':True,
    'name_and_exact_DOB_match_unique_within_all_2242_native_NAS_rows':True,
    'all_authors_and_literal_target_birth_clauses_verified':True,
    'birth_clause_precision_separate_from_heading_DOB':True,
    'source_quality_basis':'S2 signed edited memoirs, independently of unchanged native DOB groups.',
    'request_counts':{'discovery_queries':3,'index_navigation_requests':5,'approved_full_chapter_requests':8,'total_logical_attempts':16,'chapter_HTTP200':8,'retries':0},
    'coverage_limit':'574 unknown names were compared with observed index metadata offline; only eight approved chapter bodies were read, seven accepted and one held.',
    'all_574_selection_objects_equal_direct_baseline':True,
    'capture_semantics':'Memoir facts hash complete observed original HTTP HTML bodies; query/early-navigation projections use separate projection hashes. These are not PDF-byte or visual checks.',
    'index_script_note':'One observed embedded script endpoint was fetched within the five index requests; no downstream runtime/data expansion followed.',
    'old_six_member_profiles_reread':False,'geography_country_or_point_assignment':False,
    'facts':[{'cohort':x['cohort'],'record_id':x['record_id'],'source_sha256':x['source_sha256'],'source_grade':x['source_grade']} for x in checked]}
(QA/'nas_source_qa_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
(QA/'nas_source_facts_checked.json').write_text(json.dumps(checked,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'status':'PASS','accepted':len(facts),'held':len(held),'logical_attempts':16}))
