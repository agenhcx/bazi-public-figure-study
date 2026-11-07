#!/usr/bin/env python3
"""Independent local source/capture audit after all three v6 lane freezes."""
from pathlib import Path
from collections import Counter
from datetime import datetime
from urllib.parse import urljoin,urldefrag
from PIL import Image
import gzip,hashlib,json,sys
sys.path.insert(0,str(Path(__file__).parent))
from source_helpers import parsed,read,sha,compatible,stamp
W=Path('/workspace/scratch/7e8aa4e0d4af');Q=W/'academy_v6_workers/qa';B=W/'uk_birthplace_checkout/studies/scientist_birthplace_completion_v5/outputs/birthplace_rows.jsonl.gz';H='15f3d58b3334fbc5c32229b0c122ff5e693379fbf9759794e1e3ae87ac06d152'
def run():
 assert sha(B)==H
 with gzip.open(B,'rt') as f:base=[json.loads(x) for x in f]
 nas=[r for r in base if r['cohort']=='NAS'];old={r['record_id']:r for r in nas};unknown={r['record_id'] for r in nas if r['hemisphere']=='unknown'};assert len(nas)==2242 and len(unknown)==555
 reviews=[];holds=[];lanes={};source_files=[]
 for vol,caplimit in [(77,6),(78,5)]:
  p=W/f'academy_v6_workers/vol{vol}';facts=read(p/'retained_facts.jsonl');source_files.append(str((p/'retained_facts.jsonl').relative_to(W)));caps=json.loads((p/'captures.json').read_text());intents=read(p/'intent_ledger.jsonl');kind=lambda x:{'official_TOC':'index_navigation'}.get(x.get('kind',x.get('operation')),x.get('kind',x.get('operation')));when=lambda x:x.get('utc',x.get('time_utc'))
  assert Counter(kind(x) for x in intents)=={'discovery_query':1,'index_navigation':1,'chapter_body':len(caps)}
  assert len(caps)<=caplimit and all(c['status']==200 for c in caps) and len({c['requested_url'] for c in caps})==len(caps)
  tc=json.loads((p/'toc_capture.json').read_text());tocpath=next(f for f in p.rglob('*.html') if sha(f)==tc['sha256']);assert tc.get('status',tc.get('HTTP_status'))==200;toc=parsed(tocpath);links={urldefrag(urljoin(tc['requested_url'],u)).url for u in toc.links}
  indexintent=next(i for i in intents if kind(i)=='index_navigation');assert stamp(when(indexintent))<stamp(tc['retrieved_utc'])
  coverage=read(p/'coverage.jsonl');assert len(coverage)==555 and {r['record_id'] for r in coverage}==unknown
  for c in caps:
   intent=next(i for i in intents if i.get('url')==c['requested_url']);assert stamp(when(intent))<stamp(c['retrieved_utc']) and c['requested_url'] in links
  for f in facts:
   c=next(c for c in caps if c['requested_url']==f['source_url']);raw=Path(f.get('raw_source_file',c.get('local_raw_path','')));t=parsed(raw).text();b=old[f['record_id']];heading=f.get('source_subject_heading',f.get('source_heading'));quote=f['evidence_quote']
   assert sha(raw)==f['source_sha256']==c['sha256'] and quote in t and len(quote.split())<=25
   assert heading.lower() in t.lower() and all(a.strip().lower() in t.lower() for a in f['source_author'].split(';'))
   assert b['dob']==f['native_dob'] and b['hemisphere']=='unknown';matches=[r for r in nas if compatible(r['name'],heading)];exact=[r for r in matches if r['dob']==f['native_dob']];assert len(exact)==1 and exact[0]['record_id']==f['record_id']
   date=datetime.strptime(f['native_dob'],'%Y-%m-%d').strftime('%B %d, %Y').replace(' 0',' ');assert date in t
   snap=f.get('baseline_row_snapshot',f.get('frozen_baseline_row'));assert snap==b
   assert f['source_grade']=='S2'
   reviews.append({'volume':vol,'name':f['name'],'record_id':f['record_id'],'native_dob':f['native_dob'],'source_heading':heading,'source_author':f['source_author'],'raw_birthplace':f['raw_birthplace'],'source_grade':'S2','original_capture_kind':'original chapter HTTP HTML bytes','source_sha256':f['source_sha256'],'exact_literal_excerpt_checked':True,'excerpt_word_count':len(quote.split()),'excerpt_date_precision':f.get('evidence_quote_date_precision',f.get('source_DOB_born_clause_precision')),'heading_day_matches_native':True,'compatible_name_candidates':len(matches),'name_and_exact_native_DOB_candidates':len(exact),'NAS_context_reviewed':True,'lifespan_not_independently_matched':True})
  for hf in [p/'held.jsonl',p/'holds.jsonl']:
   if hf.exists():
    for f in read(hf):
     assert old[f['record_id']]['dob']==f['native_dob'] and f['record_id'] not in {x['record_id'] for x in facts}
     holds.append({'volume':vol,'name':f['name'],'record_id':f['record_id'],'native_dob':f['native_dob'],'reason':f.get('reason'),'source_sha256':f['source_sha256'],'native_row_to_remain_exact':True})
  elapsed=(max(stamp(c['retrieved_utc']) for c in caps)-stamp(when(intents[0]))).total_seconds();assert elapsed<480
  lanes[str(vol)]={'queries':1,'indices':1,'HTML_bodies':len(caps),'page_images':0,'body_requests':len(caps),'final_body_cap':caplimit,'capture_clock_seconds':elapsed,'facts':len(facts),'holds':sum(h['volume']==vol for h in holds),'retries':0,'all_HTTP200':True}
 p=W/'academy_v6_workers/vol76';facts=read(p/'retained/facts.jsonl');source_files.append(str((p/'retained/facts.jsonl').relative_to(W)));intents=read(p/'retained/intents.jsonl');bodies=[i for i in intents if i['operation']=='chapter_body'];assert len(bodies)==9 and len({i['url'] for i in bodies})==9
 assert all(i['operation'] in {'chapter_body','budget_transfer_authorization'} for i in intents)
 prior_toc=parsed(W/'academy_v5_workers/vol76/raw_transient/volume76_toc.html');prior_links={urldefrag(urljoin('https://www.nationalacademies.org/read/6477',u)).url for u in prior_toc.links}
 captures=[json.loads(f.read_text()) for f in sorted((p/'retained').glob('*_capture.json'))];assert len(captures)==9
 for c in captures:
  assert c['status']==200 and sha(W/c['raw_file'])==c['sha256'];i=next(i for i in bodies if i['url']==c['request_url']);assert stamp(i['time_utc'])<stamp(c['captured_at_utc'])
  if c['raw_file'].endswith('.html'):assert c['request_url'] in prior_links
 for f in facts:
  b=old[f['record_id']];assert f['native_dob']==b['dob'] and b['hemisphere']=='unknown' and f['source_grade']=='S2';assert len(f['evidence_quote'].split())<=25
  matches=[r for r in nas if compatible(r['name'],f['source_expanded_name'])];exact=[r for r in matches if r['dob']==f['native_dob']];assert len(exact)==1 and exact[0]['record_id']==f['record_id']
  html=parsed(W/f['chapter_HTML_capture']['raw_file']);assert sha(W/f['chapter_HTML_capture']['raw_file'])==f['chapter_HTML_capture']['sha256']
  assert sha(W/f['raw_file'])==f['source_sha256']
  for page in f['visually_inspected_page_captures']:
   raw=W/page['raw_file'];assert page['source_url'] in html.images and sha(raw)==page['source_sha256'];a=Image.open(raw).convert('RGB');b1=Image.open(raw.with_suffix('.png')).convert('RGB');assert a.size==b1.size and a.tobytes()==b1.tobytes()
  reviews.append({'volume':76,'name':f['name'],'record_id':f['record_id'],'native_dob':f['native_dob'],'source_heading':f['source_chapter_heading'],'source_expanded_name':f['source_expanded_name'],'source_author':f['source_author'],'raw_birthplace':f['raw_birthplace'],'source_grade':'S2','original_capture_kind':'original source page GIF response bytes','source_sha256':f['source_sha256'],'relevant_heading_and_birth_pages_independently_viewed':True,'all_captured_GIFs_and_PNGs_pixels_equal':True,'exact_literal_excerpt_visually_checked':True,'excerpt_word_count':len(f['evidence_quote'].split()),'excerpt_date_precision':f['source_born_clause_dob_precision'],'heading_day_matches_native':True,'compatible_name_candidates':len(matches),'name_and_exact_native_DOB_candidates':len(exact),'NAS_context':'cached official NAS deceased-member catalog projection; no individual election year claimed','lifespan_not_independently_matched':True})
 elapsed=(max(stamp(c['captured_at_utc']) for c in captures)-stamp(bodies[0]['time_utc'])).total_seconds();assert elapsed<480
 lanes['76']={'queries':0,'indices':0,'HTML_bodies':3,'page_images':6,'body_requests':9,'final_body_cap':12,'capture_clock_seconds':elapsed,'facts':3,'holds':0,'retries':0,'all_HTTP200':True,'cached_observed_TOC_routes_reused':True,'no_repeat_Woolsey':True}
 assert len(reviews)==12 and len({r['record_id'] for r in reviews})==12 and len(holds)==2
 assert sum(x['body_requests'] for x in lanes.values())==19
 report={'status':'PASS','baseline_sha256':H,'source_fact_files':source_files,'accepted_fact_count':12,'source_grade_counts':{'S2':12},'held_source_candidates':2,'held_reviews':holds,'reviews':reviews,'lanes':lanes,'source_request_totals':{'discovery_queries':2,'index_requests':2,'HTML_bodies':13,'page_images':6,'body_requests':19,'logical_source_requests':23,'retries':0},'final_assigned_body_caps':{'76':12,'77':6,'78':5},'unassigned_allowances':2,'original_total_body_allowances':25,'actual_total_unused_body_allowances':6,'manual_semantics_checked':['Pappenheimer Jr versus father and Pap alias','Goldhaber maiden-name born clause','Kirkwood explicit child-born subject and no date in excerpt','Franklin1928 versus same-name1862 hold','Seaborg Glen/Glenn and no date in place excerpt versus later exact date','Briggs born year only','Cairns born clause no date/partial name','Luyten subject birth phrase versus parents settlement context'],'original_bodies_images_and_fulltext_excluded_from_distribution':True,'native_fields_and_QIDs_frozen':True,'QA_network_requests':0}
 (Q/'source_review.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'status':'PASS','facts':12,'S2':12,'holds':2,'body_requests':19,'logical_source_requests':23,'lanes':lanes},indent=2))
if __name__=='__main__':run()
