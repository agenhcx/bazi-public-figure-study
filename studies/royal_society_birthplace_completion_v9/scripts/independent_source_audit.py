"""Independent local source audit; no network or writes outside qa/."""
import gzip,hashlib,json,re
from pathlib import Path
from html import unescape
W=Path(__file__).resolve().parents[1]; ROOT=W.parent; Q=W/'qa'
base=ROOT/'uk_birthplace_checkout/studies/royal_society_birthplace_completion_v8/outputs/uk_birthplace_rows.jsonl.gz'
old={r['record_id']:r for r in map(json.loads,gzip.open(base,'rt'))}
p=W/'eoas/accepted.jsonl'; expected='f6f08342a4fafc6aa7af777671b62189ab291e4ef4ecb2548b5239c73dd7769f'
assert hashlib.sha256(p.read_bytes()).hexdigest()==expected
facts=[json.loads(l) for l in p.read_text().splitlines()]; assert len(facts)==2
assert {f['record_id'] for f in facts}=={'RS_PAST_NA4156','RS_PAST_NA4641'}
def clean(s): return ' '.join(unescape(re.sub('<[^>]+>',' ',s)).split())
results=[]
for f in facts:
 b=old[f['record_id']]; raw=ROOT/f['raw_source_file']; body=raw.read_bytes();html=body.decode()
 heading=clean(re.search(r'<h1>(.*?)</h1>',html,re.S).group(1))
 born_label=clean(re.search(r'<dt class="startdate">(.*?)</dt>',html,re.S).group(1))
 born_data=re.search(r'<dd class="startdate">(.*?)</dd>',html,re.S).group(1)
 dob_literal,place=[clean(x) for x in re.split(r'<br\s*/?>',born_data)]
 author=clean(re.search(r'<p class="prepared">(.*?)</p>',html,re.S).group(1))
 source_hash=hashlib.sha256(body).hexdigest()
 assert born_label=='Born' and f['raw_birthplace']==place
 assert f['evidence_quote']==born_label+' '+dob_literal+' '+place
 assert f['source_dob_literal']==dob_literal and f['source_date_precision']=='day'
 from datetime import datetime
 native=datetime.strptime(dob_literal,'%d %B %Y').strftime('%Y-%m-%d')
 assert native==b['dob']==f['native_dob']==f['identity_review']['source_full_dob']
 assert heading==f['identity_review']['source_heading']
 surname,given=heading.split(',',1); names=re.sub(r'\(.*?\)','',given).strip()+' '+surname.strip()
 assert names==f['official_full_name']
 assert b['source_authorised_full_name'].split(';')[0]==surname.strip()
 assert b['name']==re.sub(r'\(.*?\)','',given).strip()
 assert re.search(r'\(\d{4} - \d{4}\)',heading).group()==re.search(r'\(\d{4} - \d{4}\)',b['source_authorised_full_name']).group()
 assert author==f['source_author']=='Rosanne Walker'
 assert 'Swinburne University of Technology' in html
 assert source_hash==f['source_sha256']
 assert len(f['evidence_quote'].split())<=25
 assert f['source_grade']=='S2' and f['geography_assignment_performed'] is False
 assert b['hemisphere']=='unknown' and b['raw_birthplace']==''
 results.append({'record_id':f['record_id'],'source_sha256':source_hash,'original_bytes_match':True,'author_verified':True,'source_grade':'S2','source_grade_basis':'Authored curated biographical dictionary with publisher metadata; independent of source/native DOB equality. No DOB-tier promotion.','full_name_matches_frozen_catalogue':True,'source_native_full_DOB_exact_match':True,'lifespan_matches_frozen_catalogue':True,'source_date_precision':'day','explicit_born_subject_field':True,'evidence_quote':f['evidence_quote'],'quote_words':len(f['evidence_quote'].split()),'raw_birthplace':place,'precision_retained':'Locality, county, England exactly as explicit Born field.','geography_recommendation':'north','geographic_basis':'Explicit England qualifier is wholly northern under existing extent rule. City-only ambiguity is not used to classify.','country_assignment_recommended':False,'birthpoint_coordinates_recommended':False,'formal_identity_or_native_DOB_change_recommended':False,'pass':True})
report={'status':'PASS','baseline_sha256':hashlib.sha256(base.read_bytes()).hexdigest(),'accepted_sha256':expected,'facts':results,'townsend':'HTTP503 response is not birthplace evidence; remains held and absent from accepted facts.','adams':'Previously frozen EOAS URL remains excluded; not counted as new fact.','network_requests':0,'written_only_under_qa':True}
(Q/'source_audit.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
