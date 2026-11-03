"""Independent read-only audit of frozen next-batch worker artifacts."""
from pathlib import Path
import collections
import gzip
import hashlib
import json
import re

ROOT = Path('/workspace/scratch/7e8aa4e0d4af')
OUT = ROOT / 'academy_next_workers/qa'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def jl(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]

def webtext(path):
    obj = json.loads(path.read_text())
    return '\n'.join(x.get('text', '') for x in obj['content'] if x['type'] == 'text')

basepath = ROOT/'uk_birthplace_checkout/studies/academy_birthplace_screen_v1/outputs/birthplace_rows.jsonl.gz'
ukpath = ROOT/'uk_birthplace_checkout/studies/royal_society_birthplace_completion_v10/outputs/uk_birthplace_rows.jsonl.gz'
assert sha(basepath) == '2ad00462255629a603bc4a95aa64158141b5a9b105359baece528a163aa93d92'
assert sha(ukpath) == 'e44f6dc02cc0cafece9b792164f016da0f08de5736ac62442d176d45b19a5799'
base = [json.loads(x) for x in gzip.decompress(basepath.read_bytes()).splitlines()]
bykey = {(r['cohort'],r['record_id']):r for r in base}
assert len(base) == len(bykey) == 11094

fields = jl(ROOT/'academy_next_workers/fields/accepted.jsonl')
nobel = jl(ROOT/'academy_next_workers/nobel/retained/birthplace_facts.jsonl')
assert len(fields) == 2 and len(nobel) == 1
facts = fields+nobel
expected = {
    ('Fields_main','fields-12ddab1dd74af07f'): ('Akshay Venkatesh','1981-11-21','New Delhi, India'),
    ('Fields_main','fields-c847084f96ea991e'): ('Manjul Bhargava','1974-08-08','Canada'),
    ('Nobel_science','1052'): ('John M. Martinis','','Los Angeles, CA, USA'),
}
checks=[]
for f in facts:
    key=(f['cohort'],f['record_id'])
    assert (f['name'],f['native_dob'],f['raw_birthplace']) == expected[key]
    row=bykey[key]
    assert row['name']==f['name'] and row['dob']==f['native_dob'] and row['hemisphere']=='unknown'
    p=Path(f['raw_source_file'])
    assert sha(p)==f['source_sha256'] and f['source_grade']=='S1'
    txt=webtext(p) if p.suffix=='.json' else p.read_text()
    assert f['evidence_quote'] in txt and len(f['evidence_quote'].split())<=25
    assert f['source_author']
    if f['cohort']=='Fields_main':
        assert f['source_birth_date_precision']=='year'
        assert f['source_birth_date_text']==row['dob'][:4]
        assert f['identity_review']['identity_independent_of_birthplace']
        if f['name']=='Akshay Venkatesh':
            assert 'Vita – Akshay Venkatesh' in txt and 'Fields Medal, 2018' in txt
        else:
            assert 'The Work of Manjul Bhargava' in txt
            ctx=f['identity_review']['official_fields_context_capture']
            cp=Path(ctx['raw_source_file'])
            assert sha(cp)==ctx['source_sha256']
            assert 'Manjul Bhargava is awarded a Fields Medal' in webtext(cp)
    else:
        assert re.search(r'JOHN M\. MARTINIS\s*\nL104: Born 1958 in Los Angeles, CA, USA\.',txt)
        assert 'The Nobel Prize Laureates in Physics for 2025' in txt
        assert 'Text: Anna Davour' in txt and '©The Royal Swedish Academy of Sciences' in txt
        assert f['identity_review']['native_dob_preserved_blank'] and row['dob']==''
        assert f['visual_verification']['status']=='unavailable'
        assert f['visual_verification']['original_pdf_byte_sha256'] is None
    checks.append({'cohort':key[0],'record_id':key[1],'name':f['name'],
                   'native_dob':f['native_dob'],'raw_birthplace':f['raw_birthplace'],
                   'source_sha256':sha(p),'source_primary_and_explicit_birthplace':'pass',
                   'independent_full_name_and_prize_context':'pass',
                   'source_birth_date_precision':'year',
                   'native_dob_adoption':'none','source_capture_only_not_publisher_bytes':True})

fl=jl(ROOT/'academy_next_workers/fields/attempt_ledger.jsonl')
fo=jl(ROOT/'academy_next_workers/fields/request_outcomes.jsonl')
assert sum(len(x['queries']) for x in fl if x['kind']=='discovery_queries')==4
assert sum(x['kind']=='body_read' for x in fl)==8
assert len(fo)==10 and {x['attempt_id'] for x in fl}=={x['attempt_id'] for x in fo}
for x in fo:
    assert sha(Path(x['raw_source_file']))==x['source_sha256']
assert 'Access Denied' in webtext(ROOT/'academy_next_workers/fields/raw/fields_body_002.webcapture.json')
assert not re.search(r'\bborn\b|birthplace',webtext(ROOT/'academy_next_workers/fields/raw/fields_body_007.webcapture.json'),re.I)
assert 'Timeout fetching' in webtext(ROOT/'academy_next_workers/fields/raw/fields_body_008.webcapture.json')

nl=jl(ROOT/'academy_next_workers/nobel/retained/request_ledger.jsonl')
ni=[x for x in nl if x['event']=='request_intent']
assert collections.Counter(x['type'] for x in ni)=={'web_discovery':2,'biography_body_read':1,'original_pdf_download':1,'pdf_page_visual_read':1}
nr=[x for x in nl if x['event']=='request_result']
assert len(nr)==5

selection=jl(ROOT/'academy_next_workers/nas/retained/selection.jsonl')
eligible=[x for x in base if x['cohort']=='NAS' and x['hemisphere']=='unknown'
          and re.fullmatch(r'\d{4}-\d{2}-\d{2}',x.get('dob',''))
          and '1835'<=x['dob'][:4]<='1985'
          and x['record_id'].startswith('https://www.nasonline.org/directory-entry/')]
eligible.sort(key=lambda x:(x['dob'],x['name'],x['record_id']))
assert [x['record_id'] for x in selection]==[x['record_id'] for x in eligible[:6]]
assert all(s['frozen_baseline_row']==bykey[('NAS',s['record_id'])] for s in selection)
nasledger=jl(ROOT/'academy_next_workers/nas/retained/request_ledger.jsonl')
nasintents=[x for x in nasledger if x['event']=='intent']
assert len(nasintents)==6 and [x['url'] for x in nasintents]==[x['record_id'] for x in selection]
nasresults=[x for x in nasledger if x['event']=='result']
assert len(nasresults)==6
timeout=[]
for r in nasresults:
    p=ROOT/r['raw_source_file']
    assert sha(p)==r['web_projection_sha256']
    txt=webtext(p)
    assert not re.search(r'\bborn\b|birthplace',txt,re.I)
    if 'Timeout fetching' in txt:
        timeout.append(r['request_id'])
    else:
        assert re.search(r'Biographical Memoir Available\s*\nL\d+:\s*\nL\d+: No',txt)
assert timeout==['nas_profile_04']
assert len([x for x in nasledger if x['event']=='classification_correction' and x['request_id']=='nas_profile_04'])==1
assert not jl(ROOT/'academy_next_workers/nas/retained/source_facts.jsonl')

report={
    'status':'PASS',
    'scope':'Frozen source-fact and request coverage review only; global assembled output audit pending.',
    'new_network_requests':0,
    'facts':checks,
    'fields_coverage':{'targets':4,'accepted':2,'unknown':2,'discovery_queries':4,'body_requests':8,
                       'negative_evidence':'Smirnov access-denied body; Duminil-Copin interview no explicit birthplace and final exposition timeout.'},
    'nobel_coverage':{'targets':1,'accepted':1,'discovery_queries':2,'successful_body_text_reads':1,
                      'logical_retrievals_of_same_url':3,'original_pdf_download':'HTTP403',
                      'pdf_visual_attempt':'text placeholder only; no image pixels',
                      'identity':'full name plus official Physics 2025 context; native DOB intentionally blank'},
    'nas_coverage':{'eligible_unknown_pool':len(eligible),'selected_and_requested_profiles':6,
                    'exact_earliest_selection_rule_verified':True,'accessible_cached_projections':5,
                    'profile_timeouts':1,'queries':0,'memoir_body_reads':0,'explicit_birthplace_facts':0,
                    'observed_person_specific_memoir_links':0,
                    'coverage_limit':'Six selected profiles only; not all 574 unknown rows screened.'},
    'capture_limitations':'Hashes identify retained web-tool text/JSON captures, not original publisher PDF/HTML bytes; NAS projections do not expose live HTTP status.',
    'baseline_hashes_verified':{'global_v1':sha(basepath),'uk_v10':sha(ukpath)},
}
OUT.mkdir(parents=True,exist_ok=True)
(OUT/'source_qa_report.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
print(json.dumps({'status':'PASS','facts':len(facts),'nas_selected':len(selection),'report':str(OUT/'source_qa_report.json')}))
