#!/usr/bin/env python3
"""Offline extent-only hemisphere review of all frozen v6 source lanes.

No network calls. Source identity QA is separate. No source or baseline file is edited.
"""
from pathlib import Path
from collections import Counter
import gzip,hashlib,json
ROOT=Path(__file__).resolve().parents[2];B=Path(__file__).resolve().parent
BASE=ROOT/'uk_birthplace_checkout/studies/scientist_birthplace_completion_v5/outputs/birthplace_rows.jsonl.gz'
BASE_SHA='15f3d58b3334fbc5c32229b0c122ff5e693379fbf9759794e1e3ae87ac06d152'
SOURCES={
 'vol76':('academy_v6_workers/vol76/retained/facts.jsonl','2ea37943b29ea38a3fe3674f9859a87a4a89a25cd87f314852c9a1dee86f1c79'),
 'vol77':('academy_v6_workers/vol77/retained_facts.jsonl','d4d65b41a8d844ea6877e8cfe009edaf24b3e77060fe4d8713a2516065856598'),
 'vol78':('academy_v6_workers/vol78/retained_facts.jsonl','ff54ce7b91180bcbd52149f60e95a893d0d368006608f637a9215125d569dc32'),
}
# Only whole geographic extents directly named in each target-born clause are used.
# No numeric boundary precision, exact city point or unique place entity is claimed.
EXTENTS={
 'Watertown, Massachusetts':('Massachusetts','state','north'),
 'Canada in the city of Edmonton, Alberta':('Canada; Alberta','country_and_province','north'),
 'the city of Semarang in north-central Java':('north-central Java within Java island','island_region','south'),
 'Cedarhurst, New York':('New York','state','north'),
 'Salem, Virginia':('Virginia','state','north'),
 'Mannheim, Germany':('Germany','country','north'),
 'Almelo, Netherlands':('Netherlands','country','north'),
 'the small town of Gotebo, Oklahoma':('Oklahoma','state','north'),
 'Berlin, Germany':('Germany','country','north'),
 'Kansas City, Missouri':('Missouri','state','north'),
 'Taylorville, Illinois':('Illinois','state','north'),
 'Ishpeming, Michigan, a small iron-mining town on the Upper Peninsula of Michigan':('Michigan; Upper Peninsula of Michigan','state_and_peninsula','north'),
}
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text())
lines=lambda p:[json.loads(x) for x in p.read_text().splitlines() if x.strip()]
def save(name,obj):
 (B/name).write_text(json.dumps(obj,ensure_ascii=False,sort_keys=True,indent=2)+'\n')
def save_lines(name,rr):
 (B/name).write_text(''.join(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n' for r in rr))
def rel(p):return str(p.relative_to(ROOT))
assert sha(BASE)==BASE_SHA
with gzip.open(BASE,'rt') as f:base=[json.loads(x) for x in f if x.strip()]
key=lambda r:(r['cohort'],r['record_id'])
old={key(r):r for r in base};assert len(base)==len(old)
facts=[];input_paths=[BASE];source_raw={}
for lane,(name,expected) in SOURCES.items():
 p=ROOT/name;assert sha(p)==expected;input_paths.append(p)
 for f in lines(p):
  assert f.get('frozen_baseline_row',f.get('baseline_row_snapshot'))==old[key(f)]
  assert f['native_dob']==old[key(f)]['dob'] and f['name']==old[key(f)]['name']
  assert f['source_grade']=='S2' and old[key(f)]['hemisphere']=='unknown'
  assert f['raw_birthplace'] in EXTENTS and f['raw_birthplace'] in f['evidence_quote']
  assert len(f['evidence_quote'].split())<=25
  if lane=='vol76':raw=ROOT/f['raw_file']
  elif lane=='vol77':raw=ROOT/f"academy_v6_workers/vol77/raw/chapter_{f['locator']['chapter']:02d}.html"
  else:raw=Path(f['raw_source_file']);raw=raw if raw.is_absolute() else ROOT/raw
  assert sha(raw)==f['source_sha256'];input_paths.append(raw)
  f['_lane']=lane;f['_fact_file']=p;facts.append(f);source_raw[key(f)]=raw
assert len(facts)==len({key(f) for f in facts})
assert set(f['raw_birthplace'] for f in facts)==set(EXTENTS)
assert not (B/'new_names_query_intent.jsonl').exists(),'No query was needed or authorized by the final plan'
reviews=[]
for f in sorted(facts,key=key):
 region,kind,sign=EXTENTS[f['raw_birthplace']]
 basis='The named geographic '+kind.replace('_',' ')+' extent lies wholly '+sign+' of the equator and directly qualifies the target birthplace.'
 if sign=='south':basis='The actual target-birth sentence locates Semarang within north-central Java. Java island lies wholly south of the equator; that subregion is therefore southern. No Semarang point or country inferred from parents is needed.'
 r={'cohort':f['cohort'],'record_id':f['record_id'],'name':f['name'],'native_dob':f['native_dob'],'raw_birthplace':f['raw_birthplace'],'hemisphere':sign,'status':'hemisphere_only_accepted','source_grade':'S2','birthplace_fact_source_grade':'S2','geography_source_grade':'S3','source_fact_file':rel(f['_fact_file']),'source_fact_file_sha256':sha(f['_fact_file']),'source_url':f['source_url'],'source_original_bytes_sha256':f['source_sha256'],'source_evidence_excerpt':f['evidence_quote'],'source_evidence_kind':'explicit_target_birth_clause','source_born_clause_date_precision':f.get('source_born_clause_dob_precision',f.get('source_DOB_born_clause_precision',f.get('evidence_quote_date_precision'))),'method':'explicit_target_birth_clause_region_extent','explicit_region':region,'explicit_region_kind':kind,'geographic_basis':basis,'query_used':False,'prior_query_evidence_applied':False,'place_entity_candidates':[],'country_assigned':False,'birthpoint_coordinates_assigned':False,'unique_place_entity_assigned':False,'native_fields_modified':False,'person_QID_assigned_or_modified':False,'DOB_calendar_eligibility_flags_modified':False,'statistical_cross_cohort_deduplication':False,'city_point_mapping_used':False,'source_birthplace_grain_preserved':True,'country':None,'lat':None,'lon':None}
 if sign=='south':r.update(source_city_type_explicit=True,source_island_region_explicit=True,parents_country_context_not_appended=True)
 if f['raw_birthplace']=='Berlin, Germany':r.update(bare_Berlin_cache_not_used=True,basis_distinction='The new source explicitly supplies Germany, so the old unqualified Berlin collision is not reused as this fact basis.')
 reviews.append(r)
# Final review rows are now ready for root integration; no subsequent step edits them.
save_lines('geographic_reviews.jsonl',reviews)
contexts=[]
for f in sorted(facts,key=key):
 region,kind,sign=EXTENTS[f['raw_birthplace']]
 caution=f.get('source_context_caution','No parent, nationality, work, upbringing, or deathplace context used as a birthplace qualifier.')
 contexts.append({'cohort':f['cohort'],'record_id':f['record_id'],'raw_birthplace':f['raw_birthplace'],'source_fact_file':rel(f['_fact_file']),'source_original_file':rel(source_raw[key(f)]),'source_original_file_sha256':sha(source_raw[key(f)]),'source_birth_clause':f['evidence_quote'],'explicit_target_birth_region':region,'region_kind':kind,'regional_extent_hemisphere':sign,'region_qualifier_directly_in_target_birth_clause':True,'source_born_clause_date_precision':next(r['source_born_clause_date_precision'] for r in reviews if key(r)==key(f)),'evidence_quote_date_precision':f.get('evidence_quote_date_precision',next(r['source_born_clause_date_precision'] for r in reviews if key(r)==key(f))),'separate_birth_date_locator':f.get('evidence_locator',{}).get('separate_birth_date_locator') if isinstance(f.get('evidence_locator'),dict) else None,'country_or_exact_city_point_added':False,'source_context_caution':caution})
luyten=next(f for f in facts if 'luyten-' in f['record_id']);png=source_raw[key(luyten)].with_suffix('.png');input_paths.append(png)
for c in contexts:
 if key(c)==key(luyten):c.update(geography_reviewer_direct_visual_check=True,visual_checked_file=rel(png),visual_checked_file_sha256=sha(png),island_reading_context='Birth sentence names city of Semarang in north-central Java; following prose refers to astronomical observations on Java.',excluded_context='Preceding Indonesia/Netherlands sentence concerns parents settling there; neither country is appended to the literal birthplace or assigned as a field.')
save_lines('source_context_checks.jsonl',contexts)
# Empty new-query/candidate files are intentional and auditable.
(B/'candidate_reviews.jsonl').write_text('');(B/'query_ledger.jsonl').write_text('')
save('query_plan.json',{'all_source_lanes_frozen':True,'query_authorized':False,'authorized_query_allowance_unused':True,'exact_English_label_or_alias_names':[],'new_query_count':0,'reason':'Every frozen target-birth clause has a sufficient explicit named state/country/province/island-region extent. No unresolved new exact name remains.','old_query_retry_prohibited':True,'frozen_source_inputs':[{'path':name,'sha256':expected} for name,expected in SOURCES.values()]})
save('candidate_audit.json',{'new_query_count':0,'new_raw_query_response_files':[],'new_candidate_count':0,'candidate_reviews_file':'academy_v6_workers/geography/candidate_reviews.jsonl','empty_candidate_file_reason':'No query necessary: all source birthplace regions suffice for hemisphere-only inference.','old_cache_map_file':'academy_v6_workers/geography/baseline_and_cache_map.json','old_cache_review_file':'academy_v6_workers/geography/independent_cache_review.json','old_queries_retried':False,'old_cache_applied_to_new_facts':False,'all_new_places_reviewed_by_extent':len(reviews),'city_entity_or_point_chosen':False})
cache=read(B/'baseline_and_cache_map.json')
for c in cache['cache']:
 for name in ['raw_response_file','candidate_review_file']:input_paths.append(ROOT/c[name])
save('input_locks.json',{'baseline_sha256':BASE_SHA,'all_three_source_lanes_explicitly_frozen_before_geography':True,'source_lanes':{lane:{'path':name,'sha256':expected} for lane,(name,expected) in SOURCES.items()},'files':[{'path':rel(p),'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(set(input_paths))],'source_fact_count':len(facts),'source_raw_place_and_grain_preserved':True,'source_originals_and_baseline_not_modified':True})
summary={'schema':'scientist_birthplace_completion_v6_NAS_geographic_review','frozen':True,'fact_count':len(facts),'source_grade_counts':dict(Counter(f['source_grade'] for f in facts)),'source_lane_counts':dict(Counter(f['_lane'] for f in facts)),'hemisphere_counts':dict(Counter(r['hemisphere'] for r in reviews)),'held_count':sum(r['hemisphere']=='unknown' for r in reviews),'all_facts_extent_qualified':True,'geographic_inference_grade':'S3, separate from all S2 source facts','new_geography_query_count':0,'old_place_queries_retried':0,'new_source_captures_by_geography_lane':0,'new_query_retries':0,'person_queries':0,'candidate_query_count':0,'new_country_assignments':0,'new_birthpoint_coordinate_assignments':0,'new_unique_place_entity_assignments':0,'native_DOB_calendar_identity_eligibility_flags_QID_changes':0,'old_v2_v5_overlays_preserved':True,'statistical_cross_cohort_deduplication':False,'baseline_NAS_unknown':sum(r['cohort']=='NAS' and r['hemisphere']=='unknown' for r in base),'expected_NAS_unknown_after_these_reviews':sum(r['cohort']=='NAS' and r['hemisphere']=='unknown' for r in base)-sum(r['hemisphere']!='unknown' for r in reviews),'Luyten_south_basis':'explicit north-central Java island region in actual target-birth clause; whole island lies south; no parents-country or exact city point inference','Franklin_Berlin_north_basis':'new actual born clause explicitly includes Germany; old unqualified Berlin query uncertainty unchanged','source_date_precision_preserved':True,'new_capture_metadata':'none, because no new request was made','inputs_sha256':{rel(p):sha(p) for p in [BASE,*[ROOT/x[0] for x in SOURCES.values()]]}}
save('geographic_summary.json',summary)
save('independent_extent_reviews.json',{'reviewer':'independent child agent /root/v4_geo/query_review','mode':'read-only frozen source facts and local Luyten page200 image; no requests/mutations','passed':True,'vol77':{'source_sha256':SOURCES['vol77'][1],'facts':5,'hemisphere_counts':{'north':5},'notes':'All qualifiers directly in target-born clauses. Kirkwood small-town grain and absent born-clause date retained; Cohen conflict excluded.'},'vol78':{'source_sha256':SOURCES['vol78'][1],'facts':4,'hemisphere_counts':{'north':4},'notes':'Berlin Germany direct qualifier suffices without query. Seaborg full town/Upper Peninsula wording and separate date locator retained.'},'vol76':{'source_sha256':SOURCES['vol76'][1],'facts':3,'hemisphere_counts':{'north':2,'south':1},'notes':'Massachusetts, Canada/Alberta direct northern extents. Page200 independently visually checked: geographic Java reading clear and wholly south. Parents countries excluded; Briggs year/Cairns absent/Luyten day precision retained.'},'combined_hemisphere_counts':dict(Counter(r['hemisphere'] for r in reviews)),'new_queries':0})
print(json.dumps({'reviews_file':rel(B/'geographic_reviews.jsonl'),'reviews_sha256':sha(B/'geographic_reviews.jsonl'),**summary},ensure_ascii=False,indent=2))
