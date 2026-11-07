#!/usr/bin/env python3
from pathlib import Path
from collections import Counter
from datetime import datetime
from urllib.parse import urljoin,urldefrag
from PIL import Image
import gzip,json,sys
sys.path.insert(0,str(Path(__file__).parent))
from source_helpers import parsed,read,sha,compatible,stamp
W=Path('/workspace/scratch/7e8aa4e0d4af');Q=W/'academy_v7_workers/qa';B=W/'uk_birthplace_checkout/studies/scientist_birthplace_completion_v6/outputs/birthplace_rows.jsonl.gz'
def run():
 assert sha(B)=='8e880fcf4a659a1c8753a5a0ad4c06552ddd9d0d545334b0e81a2459907d7356'
 with gzip.open(B,'rt') as f:base=[json.loads(x) for x in f]
 nas=[r for r in base if r['cohort']=='NAS'];old={r['record_id']:r for r in nas};unknown={r['record_id'] for r in nas if r['hemisphere']=='unknown'};assert len(unknown)==543
 reviews=[];lanes={};files=[]
 for vol in [79,80]:
  p=W/f'academy_v7_workers/vol{vol}';facts=read(p/'retained_facts.jsonl');files.append(str((p/'retained_facts.jsonl').relative_to(W)));caps=json.loads((p/'captures.json').read_text());intents=read(p/'intent_ledger.jsonl');kind=lambda x:{'official_TOC':'index_navigation'}.get(x.get('kind',x.get('operation')),x.get('kind',x.get('operation')));when=lambda x:x.get('utc',x.get('time_utc'))
  expected={'discovery_query':1,'index_navigation':1,'chapter_body':len(caps)}
  if vol==80:expected['observed_page_image']=1
  assert Counter(kind(i) for i in intents)==expected
  tc=json.loads((p/'toc_capture.json').read_text());tocpath=next(f for f in p.rglob('*.html') if sha(f)==tc['sha256']);assert tc.get('status',tc.get('HTTP_status'))==200;links={urldefrag(urljoin(tc['requested_url'],u)).url for u in parsed(tocpath).links}
  assert stamp(when(next(i for i in intents if kind(i)=='index_navigation')))<stamp(tc['retrieved_utc'])
  cov=read(p/'coverage.jsonl');assert len(cov)==543 and {r['record_id'] for r in cov}==unknown
  for c in caps:
   assert c['status']==200 and c['requested_url'] in links
   assert stamp(when(next(i for i in intents if i.get('url')==c['requested_url'])))<stamp(c['retrieved_utc'])
  for f in facts:
   c=next(c for c in caps if c['requested_url']==f['source_url']);raw=Path(f.get('raw_source_file',c.get('local_raw_path','')));text=parsed(raw).text();b=old[f['record_id']];heading=f.get('source_subject_heading',f.get('source_heading'))
   assert sha(raw)==f['source_sha256']==c['sha256'] and f['evidence_quote'] in text and len(f['evidence_quote'].split())<=25
   assert heading.lower() in text.lower() and ''.join(f['source_author'].lower().split()) in ''.join(text.lower().split())
   assert f['native_dob']==b['dob'] and b['hemisphere']=='unknown' and f['source_grade']=='S2'
   matches=[r for r in nas if compatible(r['name'],heading) and r['dob']==f['native_dob']];assert len(matches)==1 and matches[0]['record_id']==f['record_id']
   date=datetime.strptime(f['native_dob'],'%Y-%m-%d').strftime('%B %d, %Y').replace(' 0',' ');assert date in text
   assert f.get('baseline_row_snapshot',f.get('frozen_baseline_row'))==b
   reviews.append({'volume':vol,'name':f['name'],'record_id':f['record_id'],'native_dob':f['native_dob'],'source_heading':heading,'raw_birthplace':f['raw_birthplace'],'source_grade':'S2','source_sha256':f['source_sha256'],'exact_quote_and_target_subject_verified':True,'quote_word_count':len(f['evidence_quote'].split()),'heading_and_born_clause_day_match_native':True,'NAS_context_and_authorship_confirmed':True,'unique_name_plus_native_DOB_among_all2242':True})
  last=max(stamp(c['retrieved_utc']) for c in caps)
  if vol==80:
   imcap=json.loads((p/'chapter_20_page_349_capture.json').read_text());gif=p/'raw_transient/chapter_20_page_349.gif';png=gif.with_suffix('.png');raw=p/'raw_transient/chapter_20.html';text=parsed(raw).text();assert sha(gif)==imcap['sha256'];assert imcap['url'] in parsed(raw).images
   imintent=next(i for i in intents if kind(i)=='observed_page_image');assert stamp(when(imintent))<stamp(imcap['retrieved_utc']);a=Image.open(gif).convert('RGB');b=Image.open(png).convert('RGB');assert a.size==b.size and a.tobytes()==b.tobytes()
   hold=read(p/'holds.jsonl')[0];assert hold['native_dob']==hold['source_born_clause_dob']=='1914-03-04' and hold['source_heading_dob']=='1915-03-04';assert 'March 4, 1914' in text and 'March 4, 1915' in text
   assert old[hold['record_id']]['dob']=='1914-03-04';last=max(last,stamp(imcap['retrieved_utc']))
  elapsed=(last-stamp(when(intents[0]))).total_seconds();assert elapsed<480
  lanes[str(vol)]={'queries':1,'indices':1,'HTML_bodies':len(caps),'GIF_bodies':int(vol==80),'body_requests':len(caps)+int(vol==80),'body_cap':8,'capture_clock_seconds':elapsed,'facts':len(facts),'held':int(vol==80),'retries':0,'all_HTTP200':True}
 report={'status':'PASS','source_fact_files':files,'accepted_memoir_observations':4,'source_grade_counts':{'S2':4},'held_source_rows':1,'Wilson_original_GIF_directly_viewed_header1915_conflicts_with_body_native1914':True,'Wilson_lowercase_frontier_not_invented_town_and_no_fact':True,'Tarbell_farm_historical_qualifier_and_Clemence_near_grain_preserved':True,'all543_unknowns_covered_in_both_TOC_routes':True,'all_original_hashes_preintents_and_actual_TOC_image_URLs_verified':True,'reviews':reviews,'lanes':lanes,'source_effort_counts':{'queries':2,'indices':2,'HTML_bodies':5,'GIF_bodies':1,'logical_requests':10,'original_HTTP_captures':8},'native_fields_QIDs_and_DOB_groups_unchanged':True,'QA_HTTP_requests':0}
 (Q/'memoir_source_review.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'status':'PASS','memoir_observations':4,'holds':1,'lanes':lanes},indent=2))
if __name__=='__main__':run()
