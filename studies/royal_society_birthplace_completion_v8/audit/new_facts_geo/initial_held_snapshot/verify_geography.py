#!/usr/bin/env python3
"""Validate v8 new-fact geography without network or mutations to source facts."""
from pathlib import Path
import gzip,json,hashlib,collections
ROOT=Path(__file__).resolve().parent
PROJECT=ROOT.parents[1]
REPO=PROJECT/'uk_birthplace_checkout'
def read(p):
 with (gzip.open(p,'rt') if str(p).endswith('.gz') else p.open()) as f:return [json.loads(l) for l in f if l.strip()]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
summary=json.loads((ROOT/'summary.json').read_text())
paths={'australian_directory':ROOT.parent/'australian_directory/accepted.jsonl','historical_dnb':ROOT.parent/'historical_dnb/accepted.jsonl'}
facts=[];routes={}
for route,path in paths.items():
 if path.exists():
  assert summary['input_sha256'][route]==sha(path)
  for f in read(path):facts.append(f);routes[(f['record_id'],f['source_url'])]=route
base={r['record_id']:r for r in read(REPO/'studies/royal_society_birthplace_completion_v7/outputs/uk_birthplace_rows.jsonl.gz')}
rows=read(ROOT/'new_fact_geography.jsonl')
assert len(rows)==len(facts)
source={(r['record_id'],r['source_url']):r for r in facts}
assert len(source)==len(facts)
for r in rows:
 f=source[(r['record_id'],r['source_url'])]
 assert r['raw_birthplace']==f['raw_birthplace']
 assert r['source_grade']==f['source_grade'] and r['source_grade'] in {'S1','S2','S3'}
 assert r['geographic_resolution_source_grade']=='S3'
 assert r['native_dob']==f.get('dob',f.get('native_dob'))==base[r['record_id']]['dob']
 assert r['source_sha256']==f['source_sha256']
 assert r['hemisphere'] in {'north','south','unknown','equator'}
 assert r['geography']['lat'] is None and r['geography']['lon'] is None
 assert r['geography']['country_assigned'] is False
 assert r['geography']['birthpoint_coordinates_assigned'] is False
 assert r['DOB_or_native_acceptance_modified'] is False
 assert r['disposition']==('held' if r['hemisphere']=='unknown' else 'accepted')
 assert len(f['evidence_quote'].split())<=25
 expected=dict(f,route=routes[(f['record_id'],f['source_url'])])
 assert r['original_birthplace_fact']==expected
 if r['record_id']=='RS_PAST_NA3559':
  assert r['hemisphere']=='unknown'
  review=next(x for x in r['geography']['exact_name_geographic_reviews'] if x['term']=='Falkirk')
  assert review['disposition']=='held'
  signs={x['point_hemisphere'] for x in review['candidate_entities'] if x['point_hemisphere'] in {'north','south'}}
  assert signs=={'north','south'}
 if r['record_id']=='RS_PAST_NA5011':
  assert r['no_unique_geographic_entity_selected'] is False
  assert r['unique_city_entity_resolved_from_qualified_historical_name_pair'] is True
  assert r['geography']['no_unique_geographic_entity_selected'] is False
  assert r['geography']['unique_city_entity_resolved_from_qualified_historical_name_pair'] is True
  assert r['source_place_name_timing_discrepancy']['flag'] is True
  assert r['source_place_name_timing_discrepancy']['native_dob_unchanged']=='1908-12-04'
  assert 'source_place_name_timing_discrepancy' not in r['original_birthplace_fact']
  assert 'source_place_name_timing_discrepancy' not in r['geography']
assert gzip.decompress((ROOT/'new_fact_geography.jsonl.gz').read_bytes())==(ROOT/'new_fact_geography.jsonl').read_bytes()
assert summary['hemisphere_counts']==dict(collections.Counter(r['hemisphere'] for r in rows))
assert summary['output_sha256']==sha(ROOT/'new_fact_geography.jsonl')
selection=ROOT/'exact_terms_selection.json'
if selection.exists():
 d=json.loads(selection.read_text());assert not set(d['new_terms'])&set(d['reused_prior_terms'])
request_counts=summary['network_requests_executed'];assert all(n<=1 for n in request_counts.values())
verification={'status':'PASS','candidate_count':len(rows),'input_DOB_and_source_grade_preserved':True,'birthplace_source_grade':'unchanged per original S1/S2/S3 evidence','geographic_source_grade':'S3','country_or_birthpoint_assigned':False,'prior_exact_names_not_requeried':True,'qualified_historical_city_resolution_explicit':True,'source_place_name_timing_annotation_outside_original_fact_and_geography':True,'native_baseline':'royal_society_birthplace_completion_v7','input_sha256':{route:sha(path) for route,path in paths.items() if path.exists()},'output_sha256':summary['output_sha256']}
(ROOT/'verification.json').write_text(json.dumps(verification,indent=2)+'\n')
print(json.dumps(verification))
