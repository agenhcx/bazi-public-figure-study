#!/usr/bin/env python3
from pathlib import Path
from collections import Counter
from decimal import Decimal
import gzip,hashlib,json
W=Path('/workspace/scratch/7e8aa4e0d4af');Q=W/'academy_v7_workers/qa';P=W/'academy_v7_workers/geography';S=W/'uk_birthplace_checkout/studies/scientist_birthplace_completion_v7'
def read(p):return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def key(r):return r['cohort'],r['record_id']
def canonical_sha(r):return hashlib.sha256(json.dumps(r,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
def run():
 sr=json.loads((Q/'source_review.json').read_text());assert sr['status']=='PASS'
 originals={rel:read(W/rel) for rel in sr['source_fact_files']};observations=read(P/'source_observation_reviews.jsonl');reviews=read(P/'geographic_reviews.jsonl');summary=json.loads((P/'geographic_summary.json').read_text())
 assert len(observations)==30 and len(reviews)==len({key(r) for r in reviews})==29
 assert Counter(r['source_grade'] for r in observations)=={'S1':26,'S2':4}
 assert Counter(r['source_grade'] for r in reviews)=={'S1':26,'S2':3}
 assert Counter(r['hemisphere'] for r in observations)=={'north':30} and Counter(r['hemisphere'] for r in reviews)=={'north':29}
 for r in observations:
  f=originals[r['source_fact_file']][r['source_fact_line_zero_based']]
  assert r['source_fact_file_sha256']==sha(W/r['source_fact_file'])
  assert key(r)==key(f) and r['native_dob']==f['native_dob'] and r['raw_birthplace']==f['raw_birthplace']
  assert r['source_evidence_excerpt']==f['evidence_quote'] and r['source_original_bytes_sha256']==f['source_sha256']
  assert r['source_grade']==f['source_grade'] and r['geography_source_grade']=='S3'
  assert r['query_used'] is False and r['country_assigned'] is False and r['birthpoint_coordinates_assigned'] is False
  assert r['native_fields_modified'] is False and r['person_QID_assigned_or_modified'] is False and r['unique_place_entity_assigned'] is False
  if r['name']!='André Cournand':assert r['explicit_region'] and r['source_cityNow_coordinate_used'] is False
 for r in reviews:
  assert r['country'] is None and r['lat'] is None and r['lon'] is None and r['place_entity_candidates']==[]
  assert r['source_observation_count']==len(r['source_observations'])
  assert all(key(x)==key(r) and x['hemisphere']=='north' for x in r['source_observations'])
  assert r['statistical_cross_cohort_deduplication'] is False and r['query_used'] is False
 coords=read(P/'source_coordinate_evidence.jsonl');assert len(coords)==1;c=coords[0]
 med=json.loads((W/'academy_v7_workers/nobel_chem_med/original_medicine_response.bin').read_bytes())['laureates'];a=next(a for a in med if a['id']=='360');city=a['birth']['place']['cityNow']
 assert a['birth']['place']['city']['en']==city['en']==c['birth_city_label']==c['cityNow_label']=='Paris'
 assert city['latitude']==c['source_latitude_string']=='48.860093' and city['longitude']==c['source_longitude_string']=='2.355954'
 assert Decimal(city['latitude']).is_finite() and Decimal(city['latitude'])>0 and abs(Decimal(city['latitude']))<=90 and abs(Decimal(city['longitude']))<=180
 for field in ['precision','rank','globe']:
  assert field not in city and c['source_'+field] is None and c['source_'+field+'_supplied'] is False
 assert c['France_wide_north_assumption_used'] is False and c['Nobel_output_row_point_inherited'] is False and c['precision_or_accuracy_not_inferred_from_decimal_digits'] is True
 assert c['birthpoint_coordinates_assigned'] is False and c['country_assigned'] is False and c['unique_place_entity_assigned'] is False
 assert (P/'query_ledger.jsonl').read_bytes()==b'' and (P/'candidate_reviews.jsonl').read_bytes()==b''
 assert summary['new_geography_queries']==summary['new_geography_source_captures']==summary['old_queries_retried']==summary['person_queries']==0
 for rel,h in summary['inputs_sha256'].items():assert sha(W/rel)==h
 with gzip.open(S/'inputs/new_birthplace_facts.jsonl.gz','rt') as f:facts=[json.loads(x) for x in f]
 assert len(facts)==29 and sum(f['source_observation_count'] for f in facts)==30
 assert Counter(f['source_grade'] for f in facts)=={'S1':26,'S2':3}
 for f in facts:
  for ref in f['source_observations']:
   source=originals[ref['source_fact_file']][ref['row_index_zero_based']]
   assert ref['row_canonical_json_sha256']==canonical_sha(source) and ref['source_fact_file_sha256']==sha(W/ref['source_fact_file'])
 h=next(f for f in facts if f['name']=='Alfred D. Hershey');memo=originals['academy_v7_workers/vol80/retained_facts.jsonl'][0]
 assert h['source_grade']=='S1' and h['source_observation_count']==2 and h['additional_source_supports']==[memo]
 assert all(not f.get('additional_source_supports') for f in facts if f['name']!='Alfred D. Hershey')
 outsummary=json.loads((S/'outputs/summary.json').read_text());assert outsummary['retained_source_observation_count']==30 and outsummary['retained_source_observation_grade_counts']=={'S1':26,'S2':4}
 report={'status':'PASS','source_observations':30,'unique_NAS_target_rows':29,'source_observation_grades':{'S1':26,'S2':4},'primary_row_grades':{'S1':26,'S2':3},'source_observation_hemispheres':{'north':30},'unique_row_hemispheres':{'north':29},'region_extent_observations':29,'attached_official_cityNow_reference_observations':1,'Cournand_original_Paris_city_labels_and_exact_lat_lon_strings_verified':True,'Cournand_missing_precision_rank_globe_preserved_no_accuracy_invention':True,'no_France_wide_country_centroid_death_affiliation_or_old_Nobel_point_inference':True,'Hershey_additional_S2_observation_retained_verbatim_and_both_row_SHA_refs_exact':True,'Hershey_one_NAS_statistical_row_with_two_supports':True,'new_geography_queries':0,'new_geography_HTTP_captures':0,'new_country_birthpoint_unique_place_person_QID_assignments':0,'no_native_DOB_adoption_or_statistical_cross_cohort_deduplication':True,'geographic_reviews_sha256':sha(P/'geographic_reviews.jsonl'),'QA_HTTP_requests':0}
 (Q/'geography_review.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':run()
