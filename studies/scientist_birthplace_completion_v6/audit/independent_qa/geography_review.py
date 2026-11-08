#!/usr/bin/env python3
"""Independent local QA of source-qualified hemisphere extents; no requests."""
from pathlib import Path
from collections import Counter
import hashlib,json
W=Path('/workspace/scratch/7e8aa4e0d4af');P=W/'academy_v6_workers/geography';Q=W/'academy_v6_workers/qa'
def read(p):return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def key(r):return r['cohort'],r['record_id']
def run():
 source_report=json.loads((Q/'source_review.json').read_text());assert source_report['status']=='PASS'
 facts=[f for file in source_report['source_fact_files'] for f in read(W/file)];by={key(f):f for f in facts};reviews=read(P/'geographic_reviews.jsonl');summary=json.loads((P/'geographic_summary.json').read_text());plan=json.loads((P/'query_plan.json').read_text());audit=json.loads((P/'candidate_audit.json').read_text())
 assert len(reviews)==12 and {key(r) for r in reviews}==set(by)
 assert Counter(r['hemisphere'] for r in reviews)=={'north':11,'south':1}
 expected_regions={'A. M. Pappenheimer Jr.':['New York'],'Carl W. Gottschalk':['Virginia'],'E. M. Purcell':['Illinois'],'Edward C. Franklin':['Germany'],'Gertrude S. Goldhaber':['Germany'],'Glenn T. Seaborg':['Michigan','Upper Peninsula of Michigan'],'I. M. Kolthoff':['Netherlands'],'John Kirkwood':['Oklahoma'],'Robert W. Briggs':['Massachusetts'],'T. L. Cairns':['Canada','Alberta'],'Willem J. Luyten':['north-central Java'],'William D. Phillips':['Missouri']}
 for r in reviews:
  f=by[key(r)];assert r['native_dob']==f['native_dob'] and r['raw_birthplace']==f['raw_birthplace']
  assert r['source_evidence_excerpt']==f['evidence_quote'] and r['source_original_bytes_sha256']==f['source_sha256']
  assert all(x in r['source_evidence_excerpt'] and x in r['raw_birthplace'] for x in expected_regions[r['name']])
  assert r['source_grade']==r['birthplace_fact_source_grade']=='S2' and r['geography_source_grade']=='S3'
  assert r['country_assigned'] is False and r['birthpoint_coordinates_assigned'] is False
  assert r['country'] is None and r['lat'] is None and r['lon'] is None and r['place_entity_candidates']==[]
  assert r['query_used'] is False and r['person_QID_assigned_or_modified'] is False and r['unique_place_entity_assigned'] is False
  assert r['native_fields_modified'] is False and r['DOB_calendar_eligibility_flags_modified'] is False
  if r['name']=='Willem J. Luyten':
   assert r['hemisphere']=='south' and 'Java' in r['explicit_region'] and 'Indonesia' not in r['raw_birthplace']
  else:assert r['hemisphere']=='north'
 assert summary['new_geography_query_count']==summary['new_source_captures_by_geography_lane']==summary['new_query_retries']==summary['old_place_queries_retried']==0
 assert summary['person_queries']==summary['new_country_assignments']==summary['new_birthpoint_coordinate_assignments']==summary['new_unique_place_entity_assignments']==0
 assert summary['statistical_cross_cohort_deduplication'] is False
 assert plan['query_authorized'] is False and plan['new_query_count']==0 and plan['exact_English_label_or_alias_names']==[]
 assert (P/'query_ledger.jsonl').read_bytes()==b'' and (P/'candidate_reviews.jsonl').read_bytes()==b''
 assert audit['new_raw_query_response_files']==[] and audit['new_query_count']==audit['new_candidate_count']==0
 for rel,h in summary['inputs_sha256'].items():assert sha(W/rel)==h
 report={'status':'PASS','source_facts':12,'source_grades':{'S2':12},'geography_grade':'S3 separate from source/DOB groups','hemisphere_counts':{'north':11,'south':1},'all_actual_target_birth_clauses_explicitly_region_qualified':True,'source_grain_and_excerpt_precision_preserved':True,'Luyten_north_central_Java_subregion_within_southern_Java_island':True,'Luyten_parents_Indonesia_or_Netherlands_context_not_appended_to_birthplace':True,'new_Franklin_Berlin_Germany_independent_of_old_unqualified_Berlin_holds':True,'query_count':0,'new_source_captures_by_geography_lane':0,'old_queries_retried':0,'candidate_and_query_ledgers_empty_as_expected':True,'country_point_unique_place_person_QID_assignments':0,'native_metadata_changes':0,'statistical_cross_cohort_deduplication':False,'geographic_reviews_sha256':sha(P/'geographic_reviews.jsonl'),'QA_network_requests':0}
 (Q/'geography_review.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':run()
