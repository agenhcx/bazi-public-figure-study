from pathlib import Path
from collections import Counter
import gzip,json,hashlib,re,html,subprocess,urllib.parse
repo=Path('/workspace/scratch/7e8aa4e0d4af/uk_birthplace_checkout');s=repo/'studies/royal_society_birthplace_completion_v8';prior=s.parent/'royal_society_birthplace_completion_v7';w=repo.parent/'uk_birthplace_v8_workers';out=w/'final_qa'

def read(p):
 if str(p).endswith('.gz'):
  with gzip.open(p,'rt') as f:return [json.loads(l) for l in f]
 return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def plain(t):return ' '.join(html.unescape(re.sub('<[^>]+>',' ',t)).split())
base=read(prior/'outputs/uk_birthplace_rows.jsonl.gz');old={r['record_id']:r for r in base}
assert sha(prior/'outputs/uk_birthplace_rows.jsonl.gz')=='3aa09ae1720ed7abc06b49cb49f9002aa91b0a8a65ac0c0bafe18f455dc8eff7'
assert not read(s/'inputs/geographic_reviews.jsonl.gz') and not read(s/'inputs/current_lookup_replacements.jsonl.gz')
assert sum(r['hemisphere']=='unknown' and bool(r['birthplace_evidence_candidates']) for r in base)==54
facts=[]
for folder,expected,grade in [('historical_dnb','128d5c22b7dda218d01191cbb272c9282e3ae8f5ec134e58800fc4da49961143','S3'),('australian_directory','2d02fab936c2b76763f2fc8bbc168ccad4d9f1ca4fdf63f4677b8090b1813159','S2')]:
 p=w/folder/'accepted.jsonl';assert sha(p)==expected
 for f in read(p):
  facts.append(f);assert f['source_grade']==grade and f['native_dob']==old[f['record_id']]['dob'] and f['identity_verified']
  raw=w/folder/f['raw_source_file'];assert sha(raw)==f['source_sha256']
  if raw.suffix=='.pdf':
   text=subprocess.check_output(['pdftotext','-f','1','-l','1','-layout',str(raw),'-'],text=True);text=' '.join(text.split())
   assert 'Jeremy David Pickett-Heaps 1940–2021' in text and 'Peter Beech' in text and 'Arthur Forer' in text
   assert 'was born in Bombay (Mumbai), India in June 1940' in text
   assert f['source_birth_date_precision']=='month' and f['observed_source_birth_month']=='1940-06' and f['native_dob']=='1940-06-05'
   assert 'observed_source_birth_date' not in f
  else:
   if raw.suffix=='.json':
    d=json.loads(raw.read_text())['parse'];t=d['text'];t=t.get('*') if isinstance(t,dict) else t;text=plain(t)
    assert f['scan_visually_verified'] is False and f['source_grade']=='S3' and f['scan_transclusion_title']
   else:text=plain(raw.read_text())
   assert ' '.join(f['evidence_quote'].split()) in text
  assert len(f['evidence_quote'].split())<=25
assert len(facts)==6 and Counter(f['source_grade'] for f in facts)=={'S3':2,'S2':4}
assert sum(not old[f['record_id']]['birthplace_evidence_candidates'] for f in facts)==5
# Direct DNB requests do not fetch any scan image, Page transclusion or original-book PDF.
dnbleg=read(w/'historical_dnb/request_ledger.jsonl');indexmeta=json.loads((w/'historical_dnb/index_meta.json').read_text());assert len(dnbleg)==3 and indexmeta['http_status']==200
for r in dnbleg+[indexmeta]:
 assert r.get('http_status',r.get('status'))==200 and sha(w/'historical_dnb'/r['file'])==r['source_sha256']
 assert '/w/api.php?' in r.get('request_url',r.get('source_url')) and 'Page%3A' not in r.get('request_url',r.get('source_url'))
assert len(read(w/'historical_dnb/accepted.jsonl'))==2
# Preserve initial zero-result navigation probe separately from the authorized expansion.
partial=json.loads((w/'australian_directory/partial_probe/summary.json').read_text());assert partial['index_directory_requests']==3 and partial['accepted_explicit_birthplace']==0 and partial['body_requests']==0 and not partial['index_complete']
a=w/'australian_directory';ledger=read(a/'request_ledger.jsonl');assert len(ledger)==34
assert Counter(r['kind'] for r in ledger)=={'initial_directory':3,'expanded_directory':25,'selected_body_HTML':5,'explicitly_linked_official_memoir_PDF':1}
assert all(r.get('http_status',r.get('status'))==200 for r in ledger)
files=[p for p in a.rglob('*') if p.is_file() and p.suffix in ['.html','.pdf']];hashes={sha(p) for p in files}
for r in ledger:assert (r.get('sha256') or r.get('source_sha256')) in hashes
idx=json.loads((a/'expanded_index_links.json').read_text());person_links={r['url'] for r in idx if ('/biogs/' in r['url'] and re.search(r'/[Pp]\d+[bp]\.htm',r['url'])) or ('/fellows-biographical-memoirs/' in r['url'] and re.search(r'-\d{4}-\d{4}(?:-\d+)?/?$',r['url']))}
aas_links={u for u in person_links if '/fellows-biographical-memoirs/' in u};assert len(person_links)==1372 and len(aas_links)==239
expanded=read(a/'expanded_index_ledger.jsonl');assert len(expanded)==25
assert sum('science.org.au' in r['url'] for r in expanded)==23
assert {r['url'] for r in expanded if 'eoas.info' in r['url']}=={'https://www.eoas.info/browsem.htm','https://www.eoas.info/browsel.htm'}
summary=json.loads((a/'summary.json').read_text());assert summary['AAS_pages_including_initial']==24 and summary['all_directory_requests']==28 and summary['unique_person_index_links_compared']==1372 and not summary['EOAS_full_directory_complete']
assert len(read(a/'held.jsonl'))==1
assert len(read(a/'body_request_ledger.jsonl'))==5
pdf=json.loads((a/'pdf_request.json').read_text());parent=next(r for r in read(a/'body_request_ledger.jsonl') if r['record_id']=='RS_PAST_NA4658');raw_parent=(a/parent['raw_source_file']).read_text()
assert urllib.parse.unquote(pdf['url']).split('/')[-1] in urllib.parse.unquote(raw_parent)
result={'status':'PASS_INPUTS_AND_ROUTES','prior_unresolved_geography_inventory_carried':54,'new_dedicated_old_geography_reviews':0,'new_lookup_replacements':0,'new_source_facts':6,'first_active_birthplace_additions':5,'DNB_source_facts':2,'DNB_grade':'S3 editable transcription; no original scan read','DNB_direct_API_requests_HTTP200':4,'DNB_body_requests':2,'DNB_source_SHA_and_born_quotes_verified':True,'AAS_EOAS_initial_probe_directories':3,'initial_probe_new_facts':0,'authorized_expanded_directory_requests':25,'actual_all_directory_requests_HTTP200':28,'AAS_directory_pages':24,'AAS_unique_memoir_links':239,'AA_EOAS_unique_person_links_compared':1372,'EOAS_letter_pages_only':['M','L'],'EOAS_complete_directory_claim':False,'AA_HTML_body_requests_HTTP200':5,'AA_official_explicitly_linked_PDF_requests_HTTP200':1,'AA_all34_original_response_SHA_verified':True,'AA_new_S2_facts':4,'wrong_person_body_rejected':1,'Pickett_Heaps_actual_PDF_page1_fullname_authors_and_birth_month_verified':True,'Pickett_Heaps_source_precision':'month; no day supplied or inferred','native_DOB_day_unchanged':'1940-06-05','new_QA_network_requests':0}
(out/'input_review.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False,indent=2))
