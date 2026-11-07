#!/usr/bin/env python3
"""Offline v7 geography per existing NAS key, retaining every frozen source observation.

No network calls, person-QID lookup, statistical deduplication, source editing, or native edits.
"""
from pathlib import Path
from collections import Counter,defaultdict
from decimal import Decimal
import gzip,hashlib,json
ROOT=Path(__file__).resolve().parents[2];B=Path(__file__).resolve().parent
BASE=ROOT/'uk_birthplace_checkout/studies/scientist_birthplace_completion_v6/outputs/birthplace_rows.jsonl.gz'
BASE_SHA='8e880fcf4a659a1c8753a5a0ad4c06552ddd9d0d545334b0e81a2459907d7356'
SOURCES={
 'vol79':('academy_v7_workers/vol79/retained_facts.jsonl','a3412d01b5784170b8a75b88231457856c26ff5b0c582ba7a3b222705487e17e'),
 'vol80':('academy_v7_workers/vol80/retained_facts.jsonl','4d986b89ec58599bc26984fc3b72f2729e352c91c42750afb59823469fcc2f1b'),
 'nobel_physics':('academy_v7_workers/nobel_physics/retained_facts.jsonl','413147916a58547bbcb848ed45ae1475e19937264265371a59ca73f3f72eb144'),
 'nobel_chem_med':('academy_v7_workers/nobel_chem_med/retained_facts.jsonl','1d2597cc930987ee2e8a755755531209771aa3d2606ee1e41dcf4a12d8071b47'),
}
API_FILES={
 '633002ff83120f9408d630209b24ebab7d1f3f1e999cf5bb51638ebb8976075e':'uk_birthplace_checkout/studies/scientist_birthplace_completion_v5/audit/geography/nobel_physics_corroboration_response.bin',
 '8fd0d5b3e4c6528b13c5993c13c14453e7d739a9fe7a57c7d2d6486d1c7040c8':'academy_v7_workers/nobel_chem_med/original_chemistry_response.bin',
 'dc4bd5e0d8f301273e8d5e4cb9955eff3c1ed316cb1f29fd468dec5b76b562d3':'academy_v7_workers/nobel_chem_med/original_medicine_response.bin',
}
MEMOIR_EXTENTS={
 'Hancock, New Hampshire, on a farm that had been in the family since the settlement of the village':('New Hampshire','state'),
 'near Greenville, Rhode Island':('Rhode Island','state'),
 'Norwich, Connecticut':('Connecticut','state'),
 'Owosso, Michigan':('Michigan','state'),
}
US_SOURCE_REGIONS={'MA':'Massachusetts','ID':'Idaho','NE':'Nebraska','DC':'District of Columbia','MI':'Michigan','CT':'Connecticut','MN':'Minnesota','TX':'Texas','NY':'New York','IL':'Illinois','AL':'Alabama'}
NORTH_SOURCE_COUNTRIES={'Germany','Prussia','India','Romania','United Kingdom'}
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text())
lines=lambda p:[json.loads(x) for x in p.read_text().splitlines() if x.strip()]
key=lambda r:(r['cohort'],r['record_id'])
def rel(p):return str(p.relative_to(ROOT))
def save(name,value):
 (B/name).write_text(json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2)+'\n')
def save_lines(name,rr):
 (B/name).write_text(''.join(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n' for r in rr))
def pointer(obj,path):
 for part in path.split('/')[1:]:
  part=part.replace('~1','/').replace('~0','~');obj=obj[int(part)] if isinstance(obj,list) else obj[part]
 return obj
assert sha(BASE)==BASE_SHA
with gzip.open(BASE,'rt') as f:base_rows=[json.loads(x) for x in f if x.strip()]
base={key(r):r for r in base_rows};assert len(base)==len(base_rows)
assert all(r['dob']=='' for r in base_rows if r['cohort']=='Nobel_science')
api={};inputs=[BASE]
for expected,name in API_FILES.items():
 p=ROOT/name;assert sha(p)==expected;api[expected]=json.loads(p.read_bytes());inputs.append(p)
facts=[]
for lane,(name,expected) in SOURCES.items():
 p=ROOT/name;assert sha(p)==expected;inputs.append(p)
 for ordinal,f in enumerate(lines(p)):
  prior=base[key(f)];assert f.get('frozen_baseline_row',f.get('baseline_row_snapshot'))==prior
  assert f['native_dob']==prior['dob'] and f['name']==prior['name'] and prior['hemisphere']=='unknown'
  assert f['source_grade'] in {'S1','S2'} and len(f['evidence_quote'].split())<=25
  f['_lane']=lane;f['_fact_file']=p;f['_ordinal']=ordinal;facts.append(f)
assert not (B/'new_names_query_intent.jsonl').exists() and not (B/'new_names_query_response.bin').exists()
observations=[];coordinate_evidence=[];contexts=[]
for f in facts:
 identifier=f"{f['_lane']}:{f['_ordinal']:03d}";structured=f['source_grade']=='S1'
 o={'source_observation_id':identifier,'cohort':f['cohort'],'record_id':f['record_id'],'name':f['name'],'native_dob':f['native_dob'],'raw_birthplace':f['raw_birthplace'],'source_grade':f['source_grade'],'birthplace_fact_source_grade':f['source_grade'],'geography_source_grade':'S3','source_lane':f['_lane'],'source_fact_file':rel(f['_fact_file']),'source_fact_file_sha256':sha(f['_fact_file']),'source_fact_line_zero_based':f['_ordinal'],'source_url':f['source_url'],'source_original_bytes_sha256':f['source_sha256'],'source_evidence_excerpt':f['evidence_quote'],'source_evidence_locator':f.get('evidence_locator',f.get('locator')),'source_evidence_kind':'official_structured_birth_place_field' if structured else 'explicit_target_birth_clause','country_assigned':False,'birthpoint_coordinates_assigned':False,'unique_place_entity_assigned':False,'native_fields_modified':False,'person_QID_assigned_or_modified':False,'DOB_calendar_eligibility_flags_modified':False,'statistical_cross_cohort_deduplication':False,'source_birthplace_grain_preserved':True,'query_used':False,'prior_place_query_used':False,'city_point_mapping_used':False}
 if structured:
  payload=api[f['source_sha256']];loc=f['evidence_locator'];index=f['source_identity_fields']['API_array_index'];subject=payload['laureates'][index]
  assert subject['id']==f['source_identity_fields']['API_id'] and subject['birth']['date']==f['native_dob']
  assert subject['fullName']['en']==f['source_identity_fields']['fullName.en']
  assert pointer(payload,loc['JSON_pointer'])==f['raw_birthplace']==subject['birth']['place']['locationString']['en']==f['evidence_quote']
  assert loc['object_selector']==f"laureates[id={subject['id']}]"
  place=subject['birth']['place'];texts={'city.en':place.get('city',{}).get('en'),'country.en':place.get('country',{}).get('en'),'cityNow.en':place.get('cityNow',{}).get('en'),'countryNow.en':place.get('countryNow',{}).get('en'),'locationString.en':place.get('locationString',{}).get('en')}
  assert texts==f['source_birth_place_text_fields']
  o.update(source_original_file=API_FILES[f['source_sha256']],original_API_id=subject['id'],original_API_array_index=index,original_API_birth_place_text_fields=texts,original_API_birth_structure_confirmed=True,evidence_quote_date_precision='not_applicable_location_field',source_birth_date_precision='day_consistency_anchor_only_not_native_DOB_adoption')
  country=place['country']['en'];city=place['city']['en']
  if country=='USA':
   code=city.rsplit(',',1)[-1].strip().replace('.','');assert code in US_SOURCE_REGIONS
   region=US_SOURCE_REGIONS[code];kind='district' if code=='DC' else 'state'
   o.update(hemisphere='north',method='explicit_structured_birth_place_region_extent',explicit_region=region,explicit_region_kind=kind,geographic_basis='The original birth.place city field explicitly supplies '+code+'; the named '+kind+' lies wholly north of the equator. No USA-wide extent or city point is used.',source_cityNow_coordinate_used=False)
  elif country in NORTH_SOURCE_COUNTRIES:
   o.update(hemisphere='north',method='explicit_structured_birth_place_region_extent',explicit_region=country,explicit_region_kind='historical_country' if country=='Prussia' else 'country',geographic_basis='The original birth.place country qualifier '+country+' has a wholly northern geographic extent. Historical/current parentheticals remain literal; no replacement by countryNow or city point.',source_cityNow_coordinate_used=False)
  else:
   assert country=='France' and subject['id']=='360' and city=='Paris'
   current=place['cityNow'];assert current['en']==city
   lat=Decimal(current['latitude']);lon=Decimal(current['longitude']);assert lat.is_finite() and lon.is_finite() and -90<=lat<=90 and -180<=lon<=180 and lat!=0
   assert not any(k in current for k in ['precision','globe','rank'])
   sign='north' if lat>0 else 'south'
   evidence={'source_observation_id':identifier,'cohort':f['cohort'],'record_id':f['record_id'],'name':f['name'],'official_API_id':subject['id'],'source_original_file':API_FILES[f['source_sha256']],'source_original_bytes_sha256':f['source_sha256'],'original_birth_place_JSON_pointer':loc['JSON_pointer'],'source_coordinate_JSON_pointer':f'/laureates/{index}/birth/place/cityNow','birth_city_label':city,'cityNow_label':current['en'],'same_birth_and_cityNow_city_label':True,'source_latitude_string':current['latitude'],'source_longitude_string':current['longitude'],'source_precision':None,'source_rank':None,'source_globe':None,'source_precision_supplied':False,'source_rank_supplied':False,'source_globe_supplied':False,'precision_or_accuracy_not_inferred_from_decimal_digits':True,'numeric_pair_finite_and_in_range':True,'hemisphere':sign,'coordinate_scope':'attached original birth.place.cityNow reference; hemisphere evidence only','excluded_scopes':['birth.place.countryNow centroid','death.place','prize affiliations','prior Nobel output-row coordinates'],'France_wide_north_assumption_used':False,'Nobel_output_row_point_inherited':False,'country_assigned':False,'birthpoint_coordinates_assigned':False,'unique_place_entity_assigned':False,'person_QID_used_or_assigned':False}
   coordinate_evidence.append(evidence)
   o.update(hemisphere=sign,method='original_official_birth_place_cityNow_latitude',explicit_region=None,explicit_region_kind=None,geographic_basis='Original official id360 birth.place.cityNow has the same Paris label as birth.place.city and its attached finite latitude 48.860093 is north. Source precision/rank/globe are not provided. No France-wide/country centroid/old Nobel-row coordinate inference or birthpoint assignment.',source_cityNow_coordinate_used=True,source_coordinate_evidence=evidence)
 else:
  region,kind=MEMOIR_EXTENTS[f['raw_birthplace']];assert region in f['evidence_quote']
  if f['_lane']=='vol79':raw=ROOT/f"academy_v7_workers/vol79/raw/chapter_{f['evidence_locator']['chapter']:02d}.html"
  else:raw=Path(f['raw_source_file'])
  assert sha(raw)==f['source_sha256'];inputs.append(raw)
  o.update(source_original_file=rel(raw),hemisphere='north',method='explicit_target_birth_clause_region_extent',explicit_region=region,explicit_region_kind=kind,geographic_basis='The actual target-birth clause explicitly names '+region+', whose whole state extent is north; original near/farm/history wording remains intact and no town-center point is substituted.',evidence_quote_date_precision=f.get('evidence_quote_date_precision',f.get('source_DOB_born_clause_precision')),source_birth_date_precision=f.get('source_born_clause_dob_precision',f.get('source_DOB_born_clause_precision')),source_cityNow_coordinate_used=False)
 observations.append(o)
 contexts.append({'source_observation_id':identifier,'cohort':f['cohort'],'record_id':f['record_id'],'name':f['name'],'raw_birthplace':f['raw_birthplace'],'source_fact_file':o['source_fact_file'],'source_fact_line_zero_based':f['_ordinal'],'source_grade':f['source_grade'],'source_evidence_excerpt':f['evidence_quote'],'source_original_file':o['source_original_file'],'source_original_bytes_sha256':f['source_sha256'],'source_evidence_kind':o['source_evidence_kind'],'geography_method':o['method'],'explicit_region':o['explicit_region'],'geography_hemisphere':o['hemisphere'],'source_birthplace_grain_preserved':True,'evidence_quote_date_precision':o['evidence_quote_date_precision'],'source_birth_date_precision':o['source_birth_date_precision'],'source_birth_scope_confirmed':True,'parent_nationality_upbringing_work_death_context_used':False,'source_coordinates_used':o['source_cityNow_coordinate_used']})
# One geography review per existing NAS key; all independent supports remain separate.
groups=defaultdict(list)
for o in observations:groups[key(o)].append(o)
reviews=[]
for k,oo in sorted(groups.items()):
 oo=sorted(oo,key=lambda o:(0 if o['source_grade']=='S1' else 1,o['source_lane'],o['source_fact_line_zero_based']))
 primary=oo[0];signs={o['hemisphere'] for o in oo};sign=next(iter(signs)) if len(signs)==1 else 'unknown'
 r={field:primary[field] for field in ['cohort','record_id','name','native_dob','raw_birthplace','source_grade','birthplace_fact_source_grade','geography_source_grade','source_fact_file','source_fact_file_sha256','source_url','source_original_bytes_sha256','source_evidence_excerpt','source_evidence_kind','method','explicit_region','explicit_region_kind','geographic_basis']}
 r.update(hemisphere=sign,status='hemisphere_only_accepted' if sign!='unknown' else 'held_conflicting_geography',source_observation_count=len(oo),primary_source_observation_id=primary['source_observation_id'],all_source_observation_ids=[o['source_observation_id'] for o in oo],all_source_grades=sorted({o['source_grade'] for o in oo}),all_raw_birthplaces=[o['raw_birthplace'] for o in oo],source_observations=oo,all_observed_hemispheres=sorted(signs),multiple_source_observations_consistent=len(signs)==1,aggregation_unit='existing NAS cohort record key; supporting observations do not add statistical rows',source_identity_QA_separate_from_geography=True,query_used=False,prior_place_query_used=False,place_entity_candidates=[],country_assigned=False,birthpoint_coordinates_assigned=False,unique_place_entity_assigned=False,native_fields_modified=False,person_QID_assigned_or_modified=False,DOB_calendar_eligibility_flags_modified=False,statistical_cross_cohort_deduplication=False,source_birthplace_grain_preserved=True,city_point_mapping_used=False,country=None,lat=None,lon=None)
 reviews.append(r)
# Final rows are ready for integration; subsequent work only adds audit/verification files.
save_lines('geographic_reviews.jsonl',reviews)
save_lines('source_observation_reviews.jsonl',observations);save_lines('source_context_checks.jsonl',contexts);save_lines('source_coordinate_evidence.jsonl',coordinate_evidence)
(B/'query_ledger.jsonl').write_text('');(B/'candidate_reviews.jsonl').write_text('')
save('query_plan.json',{'all_source_lanes_frozen':True,'query_authorized':False,'authorized_query_allowance_unused':True,'exact_English_label_or_alias_names':[],'new_query_count':0,'reason':'Every observation is resolved by direct explicit birth-place region extent or the one root-authorized original attached official birth.place.cityNow pair. No generic place-name query is needed.','old_query_retry_prohibited':True,'frozen_source_inputs':[{'path':name,'sha256':expected} for name,expected in SOURCES.values()]})
save('candidate_audit.json',{'new_query_count':0,'new_candidate_count':0,'candidate_reviews_file':'academy_v7_workers/geography/candidate_reviews.jsonl','empty_candidate_file_reason':'No new generic place-name query necessary.','official_source_cityNow_coordinate_observations':len(coordinate_evidence),'official_source_cityNow_coordinate_file':'academy_v7_workers/geography/source_coordinate_evidence.jsonl','exact_attached_source_scope_used':True,'place_entity_or_birthpoint_assigned':False,'old_cache_map_file':'academy_v7_workers/geography/baseline_and_cache_map.json','old_queries_retried':False,'old_cache_applied_to_new_facts':False})
cache=read(B/'baseline_and_cache_map.json')
for c in cache['place_query_cache']:
 for name in ['raw_response_file','candidate_review_file']:inputs.append(ROOT/c[name])
save('input_locks.json',{'baseline_sha256':BASE_SHA,'all_four_source_lanes_explicitly_frozen_before_final_geography':True,'source_lanes':{lane:{'path':name,'sha256':expected} for lane,(name,expected) in SOURCES.items()},'API_original_bodies':{expected:name for expected,name in API_FILES.items()},'files':[{'path':rel(p),'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(set(inputs))],'source_observation_count':len(facts),'unique_reviewed_NAS_keys':len(reviews),'source_files_and_baseline_not_modified':True,'all_source_raw_place_precision_and_parentheticals_preserved':True})
summary={'schema':'scientist_birthplace_completion_v7_NAS_geographic_review','frozen':True,'source_observation_count':len(observations),'unique_reviewed_NAS_targets':len(reviews),'source_observation_grade_counts':dict(Counter(o['source_grade'] for o in observations)),'primary_target_source_grade_counts':dict(Counter(r['source_grade'] for r in reviews)),'source_lane_observation_counts':dict(Counter(o['source_lane'] for o in observations)),'source_observation_hemisphere_counts':dict(Counter(o['hemisphere'] for o in observations)),'unique_target_hemisphere_counts':dict(Counter(r['hemisphere'] for r in reviews)),'multiple_source_targets':[{'name':r['name'],'cohort':r['cohort'],'record_id':r['record_id'],'source_observation_count':r['source_observation_count'],'all_source_grades':r['all_source_grades'],'all_raw_birthplaces':r['all_raw_birthplaces'],'consistent':r['multiple_source_observations_consistent']} for r in reviews if r['source_observation_count']>1],'explicit_region_extent_observations':sum(not o['source_cityNow_coordinate_used'] for o in observations),'original_official_attached_cityNow_coordinate_observations':len(coordinate_evidence),'cityNow_coordinate_precision_rank_globe_not_invented':True,'geographic_inference_grade':'S3, separate from S1 official structured sources or S2 memoirs','new_geography_queries':0,'old_queries_retried':0,'new_geography_source_captures':0,'new_source_lane_HTTP_captures':2,'cached_physics_source_lane_HTTP_captures':0,'query_retries':0,'person_queries':0,'new_country_assignments':0,'new_birthpoint_coordinate_assignments':0,'new_unique_place_entity_assignments':0,'native_ID_DOB_calendar_eligibility_flags_QID_changes':0,'Nobel_native_DOB_all_left_blank':True,'Nobel_rows_not_changed':True,'statistical_cross_cohort_deduplication':False,'source_identity_QA_separate':True,'old_v2_v6_overlays_preserved':True,'baseline_NAS_unknown':sum(r['cohort']=='NAS' and r['hemisphere']=='unknown' for r in base_rows),'expected_NAS_unknown_after_these_unique_reviews':sum(r['cohort']=='NAS' and r['hemisphere']=='unknown' for r in base_rows)-sum(r['hemisphere']!='unknown' for r in reviews),'inputs_sha256':{rel(p):sha(p) for p in [BASE,*[ROOT/x[0] for x in SOURCES.values()]]}}
save('geographic_summary.json',summary)
print(json.dumps({'reviews_sha256':sha(B/'geographic_reviews.jsonl'),**summary},ensure_ascii=False,indent=2))
