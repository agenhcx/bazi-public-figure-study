"""Independent source and bounded-attempt checks for frozen v3 Fields route."""
from pathlib import Path
import gzip
import hashlib
import json
import re

ROOT=Path('/workspace/scratch/7e8aa4e0d4af')
WORK=ROOT/'academy_v3_workers/fields'
QA=ROOT/'academy_v3_workers/qa'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def jl(p):return [json.loads(x) for x in p.read_text().splitlines() if x]
def web(p):return '\n'.join(c.get('text','') for c in json.loads(p.read_text())['content'] if c['type']=='text')
basep=ROOT/'uk_birthplace_checkout/studies/scientist_birthplace_completion_v2/outputs/birthplace_rows.jsonl.gz'
assert sha(basep)=='2b7897d0c4e2655ecb6f10311e1bdf7b06b8eeae3f181e9bebe92cbc7f066ee0'
base={(r['cohort'],r['record_id']):r for r in [json.loads(x) for x in gzip.decompress(basep.read_bytes()).splitlines()]}
facts=jl(WORK/'accepted.jsonl');coverage=jl(WORK/'coverage.jsonl')
assert len(facts)==len(coverage)==2
expected={
    'fields-de5a4b4e279eaf4f':('Stanislav Smirnov','1970-09-03','St. Petersburg, Russia'),
    'fields-ef72cb77368d48fe':('Hugo Duminil-Copin','1985-08-26','Châtenay-Malabry, France'),
}
checked=[]
for f in facts:
    assert f['cohort']=='Fields_main'
    assert (f['name'],f['native_dob'],f['raw_birthplace'])==expected[f['record_id']]
    b=base[(f['cohort'],f['record_id'])]
    assert b['name']==f['name'] and b['dob']==f['native_dob'] and b['hemisphere']=='unknown'
    path=Path(f['raw_source_file']);text=web(path)
    assert sha(path)==f['source_sha256']
    assert f['evidence_quote'] in text and len(f['evidence_quote'].split())<=25
    assert f['source_grade']=='S1' and f['source_author']
    assert f['source_capture_kind']=='web_tool_text_capture_json'
    assert 'not original' in f['source_capture_scope']
    assert not f['visual_verification']['attempted']
    i=f['identity_review']
    assert i['exact_full_name'] and i['independent_of_birthplace']
    assert not any(i[k] for k in ['calendar_modified','dob_groups_modified','eligibility_modified',
        'formal_identity_modified','native_dob_modified','native_flags_modified','qids_modified'])
    if f['name']=='Stanislav Smirnov':
        assert f['source_birth_date_precision']=='year' and f['source_birth_date_text']=='1970'
        assert f['evidence_kind']=='explicit_born_statement'
        assert 'L66: Stanislav Smirnov was born in 1970 in St. Petersburg, Russia.' in text
        assert 'L60: Stanislav Smirnov is being awarded the 2010 Fields medal' in text
    else:
        assert f['source_birth_date_precision']=='day' and f['source_birth_date_text']=='August 26, 1985'
        assert f['evidence_kind']=='structured_birth_row'
        assert re.search(r'L72: # Hugo Duminil-Copin\s*\nL73:\s*\nL74: ## \* August 26, 1985, Châtenay-Malabry, France',text)
        assert 'L80: 【33†Fields Medal - 2022】' in text
        assert 'Heidelberg Laureate Forum Foundation' in text
        assert not re.search(r'died|death|†.*1985',f['evidence_quote'],re.I)
        extra=i['additional_official_dob_corroboration']
        ep=Path(extra['raw_source_file'])
        assert sha(ep)==extra['source_sha256'] and extra['evidence_quote'] in web(ep)
        assert len(extra['evidence_quote'].split())<=25
    checked.append({k:f[k] for k in ['cohort','record_id','name','native_dob','raw_birthplace','source_grade','source_sha256','evidence_quote','source_url','source_author','source_birth_date_precision','evidence_kind']})
ledger=jl(WORK/'attempt_ledger.jsonl');outcomes=jl(WORK/'request_outcomes.jsonl')
assert sum(len(x['queries']) for x in ledger if x['kind']=='discovery_queries')==2
bodies=[x for x in ledger if x['kind']=='body_read'];assert len(bodies)==4
assert {x['attempt_id'] for x in ledger}=={x['attempt_id'] for x in outcomes}
for x in outcomes:assert sha(Path(x['raw_source_file']))==x['source_sha256']
policy=json.loads((WORK/'baseline_and_bounds.json').read_text())
assert not set(x['url'] for x in bodies)&set(policy['excluded_prior_urls'])
summary=json.loads((WORK/'summary.json').read_text())
assert summary['new_source_facts']==2 and summary['retries']==0
assert summary['discovery_queries_used']==2 and summary['new_body_requests_used']==4
report={'status':'PASS','accepted_facts':2,'S1':2,'discovery_queries':2,'body_requests':4,'retries':0,
    'all_five_capture_hashes_match':True,'native_DOB_groups_and_precision_unchanged':True,
    'Hugo_birth_row':'Standalone asterisk date/place heading immediately beneath exact name; not a footnote or death row.',
    'Smirnov_precision':'Source year 1970 compatible with native year only; month/day not corroborated by this source.',
    'source_grade_basis':'Original official ICM prize biography and official HLF laureate profile; grade independent of DOB evidence tier.',
    'capture_semantics':'Normalized web-tool JSON only; no original publisher bytes or visual verification claimed.',
    'country_and_coordinates_assigned':False,'geographic_scope_note':'No France-wide hemisphere inference; geographic review separate.',
    'facts':[{'cohort':x['cohort'],'record_id':x['record_id'],'source_sha256':x['source_sha256'],'source_grade':x['source_grade'],'evidence_kind':x['evidence_kind']} for x in checked]}
(QA/'fields_source_qa_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
(QA/'fields_source_facts_checked.json').write_text(json.dumps(checked,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'status':'PASS','facts':len(checked),'queries':2,'body_requests':4}))
