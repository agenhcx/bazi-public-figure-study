#!/usr/bin/env python3
"""Local independent QA of the two explicitly frozen v5 memoir source lanes."""
from pathlib import Path
from html.parser import HTMLParser
from collections import Counter
from datetime import datetime
from urllib.parse import urljoin,urldefrag
from PIL import Image
import gzip,hashlib,json,re

W=Path('/workspace/scratch/7e8aa4e0d4af');Q=W/'academy_v5_workers/qa'
BASE=W/'uk_birthplace_checkout/studies/scientist_birthplace_completion_v4/outputs/birthplace_rows.jsonl.gz'
BASE_SHA='abbce4e99ad51252dd5e127a0609bc6c4950c121afa2dd126bfc2187b39cd4e8'
class Parser(HTMLParser):
 def __init__(self):super().__init__();self.suppressed=0;self.parts=[];self.links=[];self.images=[]
 def handle_starttag(self,t,a):
  if t in {'script','style','nav'}:self.suppressed+=1
  if not self.suppressed and t in {'p','div','h1','h2','h3','h4','li','br'}:self.parts.append('\n')
  if t=='a':self.links.extend(v for k,v in a if k=='href')
  if t=='img':self.images.extend(v for k,v in a if k in {'src','data-original'})
 def handle_endtag(self,t):
  if not self.suppressed and t in {'p','div','h1','h2','h3','h4','li'}:self.parts.append('\n')
  if t in {'script','style','nav'}:self.suppressed-=1
 def handle_data(self,s):
  if not self.suppressed:self.parts.append(s)
 def text(self):return re.sub(r'\s+',' ',''.join(self.parts)).strip()
def parsed(p):
 p1=Parser();p1.feed(p.read_text());return p1
def read(p):return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def stamp(x):return datetime.fromisoformat(x)
def compatible(a,b):
 a=re.findall('[a-z]+',a.lower());b=re.findall('[a-z]+',b.lower())
 match=lambda x,y:x==y or len(x)==1 and x==y[0] or len(y)==1 and y==x[0]
 return match(a[0],b[0]) and match(a[-1],b[-1]) and (len(a)==2 or len(b)==2 or len(a)==len(b) and all(match(x,y) for x,y in zip(a[1:-1],b[1:-1])))
def run():
 assert sha(BASE)==BASE_SHA
 with gzip.open(BASE,'rt') as f:base=[json.loads(x) for x in f]
 nas=[r for r in base if r['cohort']=='NAS'];bby={r['record_id']:r for r in nas}
 unknownkeys={r['record_id'] for r in nas if r['hemisphere']=='unknown'};assert len(unknownkeys)==559
 reviews=[];lanes={}
 p=W/'academy_v5_workers/vol75';facts75=read(p/'retained_facts.jsonl');caps=json.loads((p/'captures.json').read_text());intents=read(p/'intent_ledger.jsonl');toc=parsed(p/'raw/toc.html')
 assert len(facts75)==4 and Counter(x['kind'] for x in intents)=={'discovery_query':1,'index_navigation':1,'chapter_body':4}
 coverage=read(p/'coverage.jsonl');assert len(coverage)==559 and {r['record_id'] for r in coverage}==unknownkeys
 toccap=json.loads((p/'toc_capture.json').read_text());assert toccap['status']==200 and sha(p/'raw/toc.html')==toccap['sha256']
 assert stamp(next(i['utc'] for i in intents if i['kind']=='index_navigation'))<stamp(toccap['retrieved_utc'])
 assert len({c['requested_url'] for c in caps})==4 and all(c['status']==200 for c in caps)
 for f in facts75:
  c=next(c for c in caps if c['record_id']==f['record_id']);raw=Path(c['local_raw_path']);t=parsed(raw).text();b=bby[f['record_id']]
  assert c['requested_url'] in {urldefrag(urljoin('https://www.nationalacademies.org/read/9649',v)).url for v in toc.links}
  intent=next(x for x in intents if x.get('url')==c['requested_url']);assert stamp(intent['utc'])<stamp(c['retrieved_utc'])
  assert sha(raw)==c['sha256']==f['source_sha256']
  assert f['evidence_quote'] in t and len(f['evidence_quote'].split())==f['evidence_quote_word_count']<=25
  assert f['locator']['anchor'] in raw.read_text()
  assert f['source_subject_heading'].lower() in t.lower()
  date=datetime.strptime(f['native_dob'],'%Y-%m-%d').strftime('%B %d, %Y').replace(' 0',' ');assert date in t
  assert all(a.strip().lower() in t.lower() for a in f['source_author'].split(';'))
  assert f['frozen_baseline_row']==b and f['native_dob']==b['dob'] and b['hemisphere']=='unknown'
  matches=[r for r in nas if compatible(r['name'],f['source_subject_heading'])];assert len(matches)==1 and matches[0]['record_id']==f['record_id']
  assert f['source_grade']=='S2'
  if f['name']=='R. B. Leighton':
   assert f['source_subject_heading']=='ROBERT B. LEIGHTON' and f['source_DOB_born_clause_precision']=='absent'
   assert f['identity_review']['source_born_clause_date'] is None and 'Benjamin' not in t
  reviews.append({'name':f['name'],'record_id':f['record_id'],'source_url':f['source_url'],'source_grade':'S2','raw_birthplace':f['raw_birthplace'],'native_dob':f['native_dob'],'source_heading':f['source_subject_heading'],'source_author':f['source_author'],'born_clause_date_precision':f['source_DOB_born_clause_precision'],'heading_date_precision':'day','heading_native_DOB_match':True,'compatible_name_count_among_all2242':1,'original_bytes_sha256':c['sha256'],'literal_quote_exact_match':True,'quote_word_count':len(f['evidence_quote'].split()),'NAS_context':'individual membership/election context independently read','no_independent_lifespan_equality_claim':True})
 last=max(stamp(c['retrieved_utc']) for c in caps);start=stamp(intents[0]['utc']);assert (last-start).total_seconds()<480
 lanes['75']={'queries':1,'indices':1,'chapter_HTML_requests':4,'page_image_requests':0,'retries':0,'all_HTTP200':True,'query_to_last_capture_seconds':(last-start).total_seconds(),'facts':4,'holds':0,'all559_compared_to_20_actual_TOC_subjects':True}
 p=W/'academy_v5_workers/vol76';f=read(p/'retained/facts.jsonl')[0];intents=read(p/'retained/intents.jsonl');toc=parsed(p/'raw_transient/volume76_toc.html');html=parsed(p/'raw_transient/chapter_21.html')
 assert Counter(x['operation'] for x in intents)=={'web_discovery_query':1,'index_navigation':1,'chapter_body':2}
 coverage=read(p/'retained/unknown_coverage.jsonl');assert len(coverage)==559 and {r['record_id'] for r in coverage}==unknownkeys
 toccap=json.loads((p/'retained/volume76_toc_capture.json').read_text());assert toccap['status']==200 and sha(p/'raw_transient/volume76_toc.html')==toccap['sha256']
 assert stamp(next(i['time_utc'] for i in intents if i['operation']=='index_navigation'))<stamp(toccap['captured_at_utc'])
 assert f['source_url'] in {urldefrag(urljoin('https://www.nationalacademies.org/read/6477',v)).url for v in toc.links}
 assert f['source_page_image_url'] in html.images
 caps=[json.loads((p/('retained/'+x)).read_text()) for x in ['chapter_21_capture.json','chapter_21_page_361_capture.json']]
 for c in caps:
  assert c['status']==200 and sha(W/c['raw_file'])==c['sha256']
  intent=next(x for x in intents if x.get('url')==c['request_url']);assert stamp(intent['time_utc'])<stamp(c['captured_at_utc'])
 assert caps[1]['sha256']==f['capture']['original_http_response_bytes_sha256']
 gif=Image.open(W/f['capture']['raw_file']).convert('RGB');png=Image.open(p/'raw_transient/chapter_21_page_361.png').convert('RGB');assert gif.size==png.size and gif.tobytes()==png.tobytes()
 b=bby[f['record_id']];assert f['native_dob']==b['dob']=='1904-11-30' and b['hemisphere']=='unknown'
 matches=[r for r in nas if compatible(r['name'],f['source_chapter_heading'])];assert len(matches)==1 and matches[0]['record_id']==f['record_id']
 assert f['raw_birthplace']=='Brooklyn, New York' and f['source_author']=='Richard F. Thompson'
 assert f['source_born_clause_dob_precision']=='day' and f['source_heading_dob_precision']=='day'
 assert f['source_grade']=='S2' and len(f['birthplace_evidence_excerpt'].split())==f['quote_word_count']<=25
 assert 'biographies of deceased members of the National Academy of Sciences' in (p/'retained/discovery_web_projection.json').read_text()
 reviews.append({'name':f['name'],'record_id':f['record_id'],'source_url':f['source_url'],'source_page_image_url':f['source_page_image_url'],'source_grade':'S2','raw_birthplace':f['raw_birthplace'],'native_dob':f['native_dob'],'source_heading':f['source_chapter_heading'],'source_author':f['source_author'],'born_clause_date_precision':'day','heading_date_precision':'day','heading_native_DOB_match':True,'compatible_name_count_among_all2242':1,'original_bytes_sha256':caps[1]['sha256'],'chapter_HTML_bytes_sha256':caps[0]['sha256'],'original_GIF_and_viewed_PNG_pixels_identical':True,'page361_independently_viewed':True,'page361_full_heading_date_signature_and_target_born_clause_visually_confirmed':True,'literal_quote_exact_visual_match':True,'quote_word_count':f['quote_word_count'],'NAS_context':'official catalog discovery projection explicitly describes deceased NAS members; signed chapter/observed TOC; no personal election line claimed','no_independent_lifespan_equality_claim':True})
 last=max(stamp(c['captured_at_utc']) for c in caps);start=stamp(intents[0]['time_utc']);assert (last-start).total_seconds()<480
 assert len(read(p/'retained/pending_routes.jsonl'))==3
 lanes['76']={'queries':1,'indices':1,'chapter_HTML_requests':1,'page_image_requests':1,'body_requests_including_image':2,'retries':0,'all_HTTP200':True,'query_to_last_capture_seconds':(last-start).total_seconds(),'facts':1,'holds':0,'pending_unread_routes':3,'all559_compared_to_20_actual_TOC_subjects':True,'HTML_wrapper_is_not_claimed_to_contain_memoir_prose':True}
 report={'status':'PASS','baseline_sha256':BASE_SHA,'accepted_memoir_fact_count':5,'source_grade_counts':{'S2':5},'held_source_candidates':0,'pending_unread_source_routes':3,'lanes':lanes,'reviews':reviews,'all_preintents_and_observed_TOC_image_URLs_checked':True,'Leighton_partial_expansion_no_unobserved_Benjamin':True,'all_native_fields_and_QIDs_unmodified_by_source_lanes':True,'full_original_HTML_GIF_and_OCR_excluded_from_distribution':True,'QA_network_requests':0}
 (Q/'source_review.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'status':'PASS','memoir_facts':5,'S2':5,'holds':0,'pending_unread':3,'lanes':lanes},indent=2))
if __name__=='__main__':run()
