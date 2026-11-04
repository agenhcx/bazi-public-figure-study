#!/usr/bin/env python3
"""Offline verification of v7 per-target geography and all supporting source observations."""
from pathlib import Path
from collections import Counter
from decimal import Decimal
import gzip,hashlib,json
ROOT=Path(__file__).resolve().parents[2];B=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text())
lines=lambda p:[json.loads(x) for x in p.read_text().splitlines() if x.strip()]
key=lambda r:(r['cohort'],r['record_id'])
def pointer(obj,path):
 for part in path.split('/')[1:]:
  part=part.replace('~1','/').replace('~0','~');obj=obj[int(part)] if isinstance(obj,list) else obj[part]
 return obj
locks=read(B/'input_locks.json');summary=read(B/'geographic_summary.json')
for f in locks['files']:
 p=ROOT/f['path'];assert sha(p)==f['sha256'] and p.stat().st_size==f['bytes']
basepath=next(ROOT/f['path'] for f in locks['files'] if f['path'].endswith('birthplace_rows.jsonl.gz'))
assert sha(basepath)==locks['baseline_sha256']=='8e880fcf4a659a1c8753a5a0ad4c06552ddd9d0d545334b0e81a2459907d7356'
with gzip.open(basepath,'rt') as f:base_rows=[json.loads(x) for x in f if x.strip()]
base={key(r):r for r in base_rows};assert len(base)==len(base_rows)
assert all(r['dob']=='' for r in base_rows if r['cohort']=='Nobel_science')
api={}
for expected,name in locks['API_original_bodies'].items():
 p=ROOT/name;assert sha(p)==expected;api[expected]=json.loads(p.read_bytes())
facts={};facts_by_key={}
for lane,s in locks['source_lanes'].items():
 p=ROOT/s['path'];assert sha(p)==s['sha256']
 for ordinal,f in enumerate(lines(p)):
  identifier=f'{lane}:{ordinal:03d}';facts[identifier]=f;facts_by_key.setdefault(key(f),[]).append(identifier)
observations=lines(B/'source_observation_reviews.jsonl');obs={r['source_observation_id']:r for r in observations}
reviews=lines(B/'geographic_reviews.jsonl');review_by={key(r):r for r in reviews};contexts=lines(B/'source_context_checks.jsonl');context_by={r['source_observation_id']:r for r in contexts}
assert len(facts)==len(observations)==len(obs)==len(contexts)==len(context_by)==summary['source_observation_count']==locks['source_observation_count']
assert len(facts_by_key)==len(reviews)==len(review_by)==summary['unique_reviewed_NAS_targets']==locks['unique_reviewed_NAS_keys']
assert set(facts)==set(obs)==set(context_by) and set(facts_by_key)==set(review_by)
regions={'MA':'Massachusetts','ID':'Idaho','NE':'Nebraska','DC':'District of Columbia','MI':'Michigan','CT':'Connecticut','MN':'Minnesota','TX':'Texas','NY':'New York','IL':'Illinois','AL':'Alabama'}
for identifier,f in facts.items():
 o=obs[identifier];c=context_by[identifier];prior=base[key(f)]
 assert f.get('frozen_baseline_row',f.get('baseline_row_snapshot'))==prior
 assert prior['hemisphere']=='unknown' and prior['name']==f['name']==o['name'] and prior['dob']==f['native_dob']==o['native_dob']
 assert key(o)==key(f)==key(c)
 assert f['source_grade']==o['source_grade']==o['birthplace_fact_source_grade']==c['source_grade']
 assert o['geography_source_grade']=='S3' and o['hemisphere']=='north'
 assert f['raw_birthplace']==o['raw_birthplace']==c['raw_birthplace'] and f['evidence_quote']==o['source_evidence_excerpt']==c['source_evidence_excerpt']
 assert len(f['evidence_quote'].split())<=25
 assert f['source_sha256']==o['source_original_bytes_sha256']==c['source_original_bytes_sha256']
 assert sha(ROOT/o['source_original_file'])==f['source_sha256']
 assert c['source_birth_scope_confirmed'] is True and c['parent_nationality_upbringing_work_death_context_used'] is False
 assert all(o[x] is False for x in ['country_assigned','birthpoint_coordinates_assigned','unique_place_entity_assigned','native_fields_modified','person_QID_assigned_or_modified','DOB_calendar_eligibility_flags_modified','statistical_cross_cohort_deduplication','query_used','prior_place_query_used','city_point_mapping_used'])
 assert o['source_birthplace_grain_preserved'] is True
 if f['source_grade']=='S1':
  payload=api[f['source_sha256']];loc=f['evidence_locator'];subject=payload['laureates'][f['source_identity_fields']['API_array_index']]
  assert subject['id']==f['source_identity_fields']['API_id']==o['original_API_id']
  assert subject['birth']['date']==f['native_dob'] and subject['fullName']['en']==f['source_identity_fields']['fullName.en']
  assert pointer(payload,loc['JSON_pointer'])==f['raw_birthplace']==subject['birth']['place']['locationString']['en']
  assert loc['object_selector']==f"laureates[id={subject['id']}]"
  place=subject['birth']['place'];assert o['original_API_birth_place_text_fields']==f['source_birth_place_text_fields']
  assert place['city']['en']==o['original_API_birth_place_text_fields']['city.en'] and place['country']['en']==o['original_API_birth_place_text_fields']['country.en']
  if place['country']['en']=='USA':
   code=place['city']['en'].rsplit(',',1)[-1].strip().replace('.','');assert regions[code]==o['explicit_region']
   assert o['method']=='explicit_structured_birth_place_region_extent' and o['source_cityNow_coordinate_used'] is False
  elif subject['id']!='360':
   assert place['country']['en'] in {'Germany','Prussia','India','Romania','United Kingdom'}
   assert o['explicit_region']==place['country']['en'] and o['source_cityNow_coordinate_used'] is False
  else:
   assert o['method']=='original_official_birth_place_cityNow_latitude' and o['source_cityNow_coordinate_used'] is True
  assert f['Nobel_cohort_row_modified'] is False and f['Nobel_native_DOB_all_still_blank'] is True
 else:
  assert f['raw_birthplace'] in f['evidence_quote'] and o['explicit_region'] in f['evidence_quote']
  assert o['method']=='explicit_target_birth_clause_region_extent' and o['source_cityNow_coordinate_used'] is False
  expected=f.get('evidence_quote_date_precision',f.get('source_DOB_born_clause_precision'));assert o['evidence_quote_date_precision']==expected=='day'
# Every observation is retained once in the flat audit and once under its existing NAS key.
covered=[]
for k,r in review_by.items():
 identifiers=r['all_source_observation_ids'];covered+=identifiers
 assert set(identifiers)==set(facts_by_key[k]) and r['source_observation_count']==len(identifiers)==len(r['source_observations'])
 assert {o['source_observation_id']:o for o in r['source_observations']}=={i:obs[i] for i in identifiers}
 primary=obs[r['primary_source_observation_id']]
 assert primary in r['source_observations'] and r['source_grade']==primary['source_grade'] and r['raw_birthplace']==primary['raw_birthplace']
 if any(obs[i]['source_grade']=='S1' for i in identifiers):assert primary['source_grade']=='S1'
 assert r['all_raw_birthplaces']==[o['raw_birthplace'] for o in r['source_observations']]
 assert r['all_source_grades']==sorted({o['source_grade'] for o in r['source_observations']})
 assert r['all_observed_hemispheres']==['north'] and r['multiple_source_observations_consistent'] is True and r['hemisphere']=='north'
 assert r['source_identity_QA_separate_from_geography'] is True
 assert all(r[x] is False for x in ['country_assigned','birthpoint_coordinates_assigned','unique_place_entity_assigned','native_fields_modified','person_QID_assigned_or_modified','DOB_calendar_eligibility_flags_modified','statistical_cross_cohort_deduplication','query_used','prior_place_query_used','city_point_mapping_used'])
 assert r['country'] is r['lat'] is r['lon'] is None and r['place_entity_candidates']==[]
assert sorted(covered)==sorted(facts)
overlap=[r for r in reviews if r['source_observation_count']>1];assert len(overlap)==1
hershey=overlap[0];assert hershey['name']=='Alfred D. Hershey' and hershey['source_grade']=='S1'
assert hershey['all_raw_birthplaces']==['Owosso, MI, USA','Owosso, Michigan'] and hershey['all_source_grades']==['S1','S2']
# The only coordinate evidence is the explicitly authorized attached source city reference.
coords=lines(B/'source_coordinate_evidence.jsonl');assert len(coords)==1
ce=coords[0];f=facts[ce['source_observation_id']];payload=api[f['source_sha256']];current=pointer(payload,ce['source_coordinate_JSON_pointer'])
assert ce['official_API_id']=='360' and ce['name']=='André Cournand'
assert current['en']==ce['birth_city_label']==ce['cityNow_label']=='Paris'
assert current['latitude']==ce['source_latitude_string']=='48.860093' and current['longitude']==ce['source_longitude_string']=='2.355954'
lat=Decimal(current['latitude']);lon=Decimal(current['longitude']);assert lat.is_finite() and lon.is_finite() and -90<=lat<=90 and -180<=lon<=180 and lat>0
for field in ['precision','rank','globe']:
 assert field not in current and ce['source_'+field] is None and ce['source_'+field+'_supplied'] is False
assert ce['precision_or_accuracy_not_inferred_from_decimal_digits'] is True
assert all(ce[x] is False for x in ['France_wide_north_assumption_used','Nobel_output_row_point_inherited','country_assigned','birthpoint_coordinates_assigned','unique_place_entity_assigned','person_QID_used_or_assigned'])
assert obs[ce['source_observation_id']]['source_coordinate_evidence']==ce
assert sum(o['source_cityNow_coordinate_used'] for o in observations)==1
# Special source grain and literal historical labels are untouched.
assert next(r for r in reviews if r['name']=='Gerald Clemence')['raw_birthplace']=='near Greenville, Rhode Island'
assert 'on a farm that had been in the family since the settlement of the village' in next(r for r in reviews if r['name']=='D. Stanley Tarbell')['raw_birthplace']
assert next(r for r in reviews if r['name']=='H. Gobind Khorana')['raw_birthplace']=='Raipur, India'
assert next(r for r in reviews if r['name']=='H. A. Bethe')['raw_birthplace']=='Strasbourg, Germany (now France)'
assert next(r for r in reviews if r['name']=='Hans G. Dehmelt')['raw_birthplace']=='Görlitz, Prussia (now Germany)'
assert next(r for r in reviews if r['name']=='S. Chandrasekhar')['raw_birthplace']=='Lahore, India (now Pakistan)'
# No query or capture was performed in the geography lane, and old cache bodies are unchanged.
assert (B/'candidate_reviews.jsonl').read_bytes()==b'' and (B/'query_ledger.jsonl').read_bytes()==b''
assert not (B/'new_names_query_intent.jsonl').exists() and not (B/'new_names_query_response.bin').exists()
plan=read(B/'query_plan.json');assert plan['all_source_lanes_frozen'] is True and plan['query_authorized'] is False and plan['exact_English_label_or_alias_names']==[] and plan['new_query_count']==0
cache=read(B/'baseline_and_cache_map.json')
for c in cache['place_query_cache']:
 p=ROOT/c['raw_response_file'];assert sha(p)==c['raw_response_file_sha256']
 body=gzip.decompress(p.read_bytes()) if p.name.endswith('.gz') else p.read_bytes();assert hashlib.sha256(body).hexdigest()==c['original_uncompressed_JSON_body_sha256']
 assert sha(ROOT/c['candidate_review_file'])==c['candidate_review_file_sha256']
assert Counter(o['source_grade'] for o in observations)==summary['source_observation_grade_counts']
assert Counter(r['source_grade'] for r in reviews)==summary['primary_target_source_grade_counts']
assert Counter(r['hemisphere'] for r in reviews)==summary['unique_target_hemisphere_counts']
nas_before=Counter(r['hemisphere'] for r in base_rows if r['cohort']=='NAS');nas_after=nas_before.copy()
for r in reviews:nas_after['unknown']-=1;nas_after[r['hemisphere']]+=1
assert nas_before['unknown']==summary['baseline_NAS_unknown']==543
assert nas_after['unknown']==summary['expected_NAS_unknown_after_these_unique_reviews']==514
result={'passed':True,'offline_only':True,'source_observations':len(observations),'unique_existing_NAS_target_reviews':len(reviews),'source_observation_grade_counts':summary['source_observation_grade_counts'],'primary_target_grade_counts':summary['primary_target_source_grade_counts'],'unique_target_hemisphere_counts':summary['unique_target_hemisphere_counts'],'all_source_and_baseline_input_SHA256_locks_match':True,'all_API_original_birth_scope_locators_and_native_DOB_consistency_checks_pass':True,'source_identity_QA_separate':True,'all_source_supports_verbatim_preserved_and_each_target_once':True,'Hershey_S1_primary_and_S2_support_both_retained':True,'source_grades_S1_S2_separate_from_geography_S3':True,'Cournand_original_attached_cityNow_only_and_missing_precision_rank_globe_preserved':True,'no_France_USA_countrywide_or_country_centroid_or_Nobel_row_point_inference':True,'Nobel_native_DOB_all_still_blank':True,'old_v2_v6_overlays_and_place_query_cache_bodies_locked':True,'new_geography_queries':0,'old_queries_retried':0,'new_geography_source_captures':0,'native_ID_DOB_calendar_eligibility_flags_QID_country_birthpoint_unique_entity_changes':0,'statistical_cross_cohort_deduplication':False,'expected_NAS_counts_after_integration':dict(nas_after)}
(B/'geography_verification.json').write_text(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2)+'\n');print(json.dumps(result,indent=2))
