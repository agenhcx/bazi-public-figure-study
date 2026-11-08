#!/usr/bin/env python3
"""Offline verification of the frozen hemisphere-only geography review; never queries."""
from collections import Counter,defaultdict
from pathlib import Path
import gzip,hashlib,json
ROOT=Path(__file__).resolve().parents[2];B=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text())
rows=lambda p:[json.loads(x) for x in p.read_text().splitlines() if x.strip()]
locks=read(B/'input_locks.json');summary=read(B/'geographic_summary.json')
for f in locks['files']:
 p=ROOT/f['path'];assert sha(p)==f['sha256'] and p.stat().st_size==f['bytes']
basefile=next(x['path'] for x in locks['files'] if x['path'].endswith('/birthplace_rows.jsonl.gz'))
with gzip.open(ROOT/basefile,'rt') as f:base=[json.loads(x) for x in f if x.strip()]
base={(r['cohort'],r['record_id']):r for r in base}
facts=[]
for lane in locks['source_lanes'].values():
 p=ROOT/lane['path'];assert sha(p)==lane['sha256'];facts+=rows(p)
key=lambda r:(r['cohort'],r['record_id'])
factsby={key(f):f for f in facts};reviews=rows(B/'geographic_reviews.jsonl');reviewby={key(r):r for r in reviews}
assert len(factsby)==len(facts)==len(reviews)==len(reviewby)==summary['fact_count']==locks['source_fact_count']
assert set(factsby)==set(reviewby)
for k,f in factsby.items():
 old=base[k];r=reviewby[k]
 assert old==f.get('frozen_baseline_row',f.get('baseline_row_snapshot'))
 assert old['dob']==f['native_dob']==r['native_dob']
 assert old['name']==f['name']==r['name']
 assert f['raw_birthplace']==r['raw_birthplace']
 assert f['source_grade']==r['source_grade']==r['birthplace_fact_source_grade']=='S2'
 assert r['geography_source_grade']=='S3'
 assert f.get('evidence_quote',f.get('birthplace_evidence_excerpt'))==r['source_born_clause']
 assert all(r[x] is False for x in ['country_assigned','birthpoint_coordinates_assigned','unique_place_entity_assigned','native_fields_modified','person_QID_assigned_or_modified','DOB_calendar_eligibility_flags_modified','city_point_mapping_used'])
 assert r['source_birthplace_grain_preserved'] is True
 assert r['country'] is r['lat'] is r['lon'] is None
 if not r['query_used']:
  assert r['method']=='explicit_target_born_clause_region_extent' and r['hemisphere']=='north'
  assert r['explicit_region'].split(',')[0] in r['source_born_clause']
# Exactly one request, no LIMIT, no rank/type/globe filtering, direct statement paths only.
ledger=rows(B/'query_ledger.jsonl');capture=read(B/'exact_place_query_capture.json');query=(B/'exact_place_query.rq').read_text()
assert len(ledger)==1 and ledger[0]['ordinal']==1
assert sha(B/'exact_place_query.rq')==capture['request']['query_sha256']==summary['query_sha256']
assert sha(B/'exact_place_query_response.bin')==capture['response_sha256']==summary['query_response_sha256']
assert capture['status']==200 and capture['parse_status']=='valid_SPARQL_JSON'
assert capture['capture_kind']=='original_HTTP_response_bytes'
assert capture['response_representation']=='original_HTTP_SPARQL_JSON_response_bytes'
assert capture['query_attempts']==1 and capture['retry_performed'] is False
assert not any(x in query.upper() for x in ['LIMIT ','P19','P569'])
for x in ['p:P625','psv:P625','wikibase:rank','wikibase:geoGlobe','wikibase:geoPrecision','p:P31','p:P17','rdfs:label skos:altLabel']:
 assert x in query
assert '"New York City"@en "Colorado Springs"@en' in query
payload=json.loads((B/'exact_place_query_response.bin').read_bytes());bindings=payload['results']['bindings'];candidates=rows(B/'candidate_reviews.jsonl')
val=lambda r,k:r.get(k,{}).get('value')
seen=[]
for c in candidates:
 indices=c['binding_indices_zero_based'];assert len(indices)==c['binding_count'];seen+=indices
 rr=[bindings[i] for i in indices]
 assert {(val(b,'requestedName'),val(b,'place')) for b in rr}=={(c['requested_exact_English_label_or_alias'],c['entity'])}
 rawcoordinateids={val(b,'coordinateStatement') for b in rr if 'coordinateStatement' in b}
 assert rawcoordinateids=={x['coordinateStatement'] for x in c['coordinate_statements']}
 assert len(rawcoordinateids)==c['coordinate_statement_count']
 for statement in c['coordinate_statements']:
  raw={(k,val(b,k)) for b in rr if val(b,'coordinateStatement')==statement['coordinateStatement'] for k in ['coordinateStatement','coordinateWkt','coordinateRank','coordinateValue','latitude','longitude','globe','precision'] if k in b}
  assert raw<={(k,v) for k,v in statement.items()}
  if statement['status']=='valid_direct_Earth_coordinate':
   assert statement['globe']=='http://www.wikidata.org/entity/Q2'
   assert statement['hemisphere']=='north' and float(statement['latitude'])-float(statement['precision'])>0
 assert all(c[x] is False for x in ['unique_place_entity_assigned','country_assigned','birthpoint_coordinates_assigned'])
 if not c['physical_place_candidate']:assert c['exclusion_reason']
assert sorted(seen)==list(range(len(bindings))) # retains every original row exactly once
assert len(candidates)==len({(val(b,'requestedName'),val(b,'place')) for b in bindings})
assert len(bindings)==capture['binding_count']==summary['query_bindings']
assert len(candidates)==summary['retained_homonym_entity_count']
physical={c['entity'].rsplit('/',1)[-1]:c for c in candidates if c['physical_place_candidate']}
assert set(physical)=={'Q49258','Q60','Q127430833','Q39319400'}
hotel=physical['Q39319400'];assert hotel['candidate_hemisphere']=='unknown' and hotel['coordinate_statements']==[]
assert {c['country'] for c in hotel['country_statements']}=={'http://www.wikidata.org/entity/Q30'}
assert hotel['explicit_region_extent_usable'] is False
for name in ['New York City','Colorado Springs']:
 cs=[c for c in candidates if c['requested_exact_English_label_or_alias']==name and c['physical_place_candidate']]
 rs=[r for r in reviews if r['raw_birthplace']==name];assert len(rs)==1
 assert rs[0]['physical_place_candidate_count']==len(cs)
 assert rs[0]['hemisphere']==('unknown' if name=='New York City' else 'north')
context=rows(B/'source_context_checks.jsonl')
assert len(context)==2
assert all(c['state_or_country_qualifier_in_actual_target_born_clause'] is False for c in context)
nyc=next(c for c in context if c['raw_birthplace']=='New York City')
assert nyc['same_birth_paragraph_explicit_city_type_backreference'] is False
assert dict(Counter(r['hemisphere'] for r in reviews))==summary['hemisphere_counts']
assert sum(not r['query_used'] for r in reviews)==summary['explicit_born_clause_extent_count']
result={'passed':True,'offline_only':True,'source_fact_count':len(facts),'geographic_review_count':len(reviews),'hemisphere_counts':summary['hemisphere_counts'],'all_native_cohort_ID_name_DOB_and_raw_places_preserved':True,'all_source_grade_S2_and_geography_grade_S3_separate':True,'all_frozen_source_and_baseline_input_SHA256_locks_match':True,'all_query_bindings_and_homonyms_retained':True,'query_count':1,'query_retry_count':0,'person_queries':0,'no_country_birthpoint_or_unique_place_entity_assignments':True,'no_native_calendar_eligibility_QID_or_flags_mutations':True,'raw_query_capture_is_original_HTTP_SPARQL_JSON_bytes':True}
(B/'geography_verification.json').write_text(json.dumps(result,sort_keys=True,indent=2)+'\n');print(json.dumps(result,indent=2))
