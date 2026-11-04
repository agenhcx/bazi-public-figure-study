#!/usr/bin/env python3
"""Independent offline verification of frozen v5 geography and official source qualification."""
from pathlib import Path
from collections import Counter
from decimal import Decimal
import gzip,hashlib,json,re
ROOT=Path(__file__).resolve().parents[2];B=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text())
lines=lambda p:[json.loads(x) for x in p.read_text().splitlines() if x.strip()]
locks=read(B/'input_locks.json');summary=read(B/'geographic_summary.json')
for f in locks['files']:
 p=ROOT/f['path'];assert sha(p)==f['sha256'] and p.stat().st_size==f['bytes']
basefile=next(ROOT/f['path'] for f in locks['files'] if f['path'].endswith('birthplace_rows.jsonl.gz'))
with gzip.open(basefile,'rt') as f:baseline=[json.loads(x) for x in f if x.strip()]
key=lambda r:(r['cohort'],r['record_id'])
base={key(r):r for r in baseline}
facts=[]
for source in locks['source_lanes'].values():
 p=ROOT/source['path'];assert sha(p)==source['sha256'];facts+=lines(p)
byfact={key(f):f for f in facts};reviews=lines(B/'geographic_reviews.jsonl');byreview={key(r):r for r in reviews}
assert len(byfact)==len(facts)==len(reviews)==len(byreview)==summary['fact_count']
assert set(byfact)==set(byreview)
for k,f in byfact.items():
 r=byreview[k];old=base[k]
 assert f.get('frozen_baseline_row',f.get('baseline_row_snapshot'))==old
 assert f['native_dob']==r['native_dob']==old['dob'] and f['name']==r['name']==old['name']
 assert f['raw_birthplace']==r['raw_birthplace']
 assert f['source_grade']==r['source_grade']==r['birthplace_fact_source_grade']
 assert r['geography_source_grade']=='S3'
 assert all(r[x] is False for x in ['country_assigned','birthpoint_coordinates_assigned','unique_place_entity_assigned','native_fields_modified','person_QID_assigned_or_modified','DOB_calendar_eligibility_flags_modified','statistical_cross_cohort_deduplication','city_point_mapping_used'])
 assert r['country'] is r['lat'] is r['lon'] is None and r['source_birthplace_grain_preserved'] is True
 assert len(f.get('evidence_quote',f.get('birthplace_evidence_excerpt')).split())<=25
assert Counter(r['hemisphere'] for r in reviews)==summary['hemisphere_counts']
assert Counter(f['source_grade'] for f in facts)==summary['source_grade_counts']
# The fresh official source object establishes source identity; no native Nobel date adoption.
anderson=next(f for f in facts if f['source_grade']=='S1');nas=base[key(anderson)];nobel=base[('Nobel_science','43')]
assert nobel['dob']=='' and nas['dob']=='1905-09-03'
assert anderson['prior_v4_S2_overlay_to_preserve_completely']=={k:nas[k] for k in ['v4_birthplace_fact_evidence','v4_geographic_review','v4_geography_before_overlay']}
assert nas['hemisphere']=='unknown' and nas['v4_geographic_review']['status']=='held_unknown'
api_capture=read(B/'anderson_corroboration_capture.json');api_intent=lines(B/'anderson_corroboration_intent.jsonl');assert len(api_intent)==1
assert api_capture['status']==200 and api_capture['retries']==0 and api_capture['search_requests']==0
api_path=ROOT/api_capture['response_file'];assert sha(api_path)==api_capture['response_sha256']==anderson['source_sha256']==nobel['birthplace_source_sha256']
objects=json.loads(api_path.read_bytes())['laureates'];target=[x for x in objects if x.get('id')=='43'];assert len(target)==1;s=target[0]
assert s['fullName']['en']=='Carl David Anderson'==nas['v4_birthplace_fact_evidence']['source_subject_heading']
assert s['knownName']['en']==nas['name'] and s['birth']['date']==nas['dob']
assert any(p['awardYear']=='1936' and p['category']['en']=='Physics' and p['motivation']['en']=='for his discovery of the positron' for p in s['nobelPrizes'])
assert s['birth']['place']['city']['en']=='New York, NY'
assert s['birth']['place']['locationString']['en']==anderson['raw_birthplace']=='New York, NY, USA'
assert byreview[key(anderson)]['hemisphere']=='north' and byreview[key(anderson)]['query_used'] is False
assert anderson['Nobel_cohort_row_modified'] is False and anderson['Nobel_native_DOB_still_blank'] is True
# Exactly one new bounded place query, never the old NYC/Colorado query or a person query.
query_capture=read(B/'new_names_query_capture.json');query_intent=lines(B/'new_names_query_intent.jsonl');assert len(query_intent)==1
assert query_capture['status']==200 and query_capture['query_attempts']==1 and query_capture['retry_performed'] is False
query=(B/'new_names_query.rq').read_text();assert '"Berlin"@en "Detroit"@en' in query
assert not any(x in query for x in ['"New York City"@en','"Colorado Springs"@en','P19','P569'])
assert 'LIMIT ' not in query.upper()
for required in ['p:P625','psv:P625','wikibase:rank','wikibase:geoGlobe','wikibase:geoPrecision','p:P31','p:P17','rdfs:label skos:altLabel']:
 assert required in query
assert sha(B/'new_names_query.rq')==query_intent[0]['query_sha256']==summary['new_query_sha256']
assert sha(B/'new_names_query_response.bin')==query_capture['response_sha256']==summary['new_query_response_sha256']
raw=json.loads((B/'new_names_query_response.bin').read_bytes())['results']['bindings'];candidates=lines(B/'candidate_reviews.jsonl');value=lambda r,k:r.get(k,{}).get('value')
covered=[];coordinate_ids=set();physical=[]
for c in candidates:
 indices=c['binding_indices_zero_based'];assert len(indices)==c['binding_count'];covered+=indices;rr=[raw[i] for i in indices]
 assert {(value(r,'requestedName'),value(r,'place')) for r in rr}=={(c['requested_exact_English_label_or_alias'],c['entity'])}
 raw_ids={value(r,'coordinateStatement') for r in rr if 'coordinateStatement' in r}
 assert raw_ids=={x['coordinateStatement'] for x in c['coordinate_statements']} and len(raw_ids)==c['coordinate_statement_count'];coordinate_ids.update(raw_ids)
 for statement in c['coordinate_statements']:
  original={(k,value(r,k)) for r in rr if value(r,'coordinateStatement')==statement['coordinateStatement'] for k in ['coordinateStatement','coordinateWkt','coordinateRank','coordinateValue','latitude','longitude','globe','precision'] if k in r}
  assert original<={(k,v) for k,v in statement.items()}
  assert statement['globe']=='http://www.wikidata.org/entity/Q2' and statement['status']=='valid_direct_Earth_coordinate'
  lat=Decimal(statement['latitude']);lon=Decimal(statement['longitude']);precision=Decimal(statement['precision'])
  assert precision>0 and -90<=lat<=90 and -180<=lon<=180
  assert statement['hemisphere']==('north' if lat-precision>0 else 'south' if lat+precision<0 else 'unknown')
  wkt=re.search(r'Point\(([^ ]+) ([^)]+)\)',statement['coordinateWkt']);assert wkt
  assert abs(Decimal(wkt.group(1))-lon)<=precision and abs(Decimal(wkt.group(2))-lat)<=precision
 if c['physical_place_candidate']:physical.append(c)
 else:assert c['exclusion_reason']
 assert all(c[x] is False for x in ['country_assigned','birthpoint_coordinates_assigned','unique_place_entity_assigned'])
assert sorted(covered)==list(range(len(raw)))
assert len(candidates)==len({(value(r,'requestedName'),value(r,'place')) for r in raw})==summary['new_query_homonym_entities']
assert len(raw)==query_capture['binding_count']==summary['new_query_bindings']
assert len(coordinate_ids)==summary['new_query_coordinate_statements']
assert len(physical)==summary['new_query_physical_place_candidates']
for name in ['Berlin','Detroit']:
 pc=[c for c in physical if c['requested_exact_English_label_or_alias']==name]
 r=next(r for r in reviews if r['raw_birthplace']==name)
 assert len(pc)==r['physical_place_candidate_count']
 assert {c['candidate_hemisphere'] for c in pc}==set(r['candidate_hemisphere_set'])
 assert r['hemisphere']==('north' if name=='Detroit' else 'unknown')
# Prior query remains read-only and its sparse hotel statement is unchanged.
bernstein=next(r for r in reviews if r['raw_birthplace']=='New York City');prior=ROOT/bernstein['prior_query_response_file']
assert sha(prior)==bernstein['prior_query_response_gzip_sha256']
prior_bytes=gzip.decompress(prior.read_bytes());assert hashlib.sha256(prior_bytes).hexdigest()==bernstein['prior_query_original_JSON_sha256']
hotel=[r for r in json.loads(prior_bytes)['results']['bindings'] if value(r,'place')=='http://www.wikidata.org/entity/Q39319400']
assert hotel and all('coordinateStatement' not in r for r in hotel) and {value(r,'country') for r in hotel}=={'http://www.wikidata.org/entity/Q30'}
assert bernstein['hemisphere']=='unknown' and bernstein['query_used'] is False
# New metadata stores only safe public headers and URLs; HTTP source bytes are kept separately.
allow={'content-type','content-length','date','last-modified','etag','content-encoding'}
for m in [api_capture,query_capture]:
 assert set(m.get('safe_response_headers',{}))<=allow
 assert 'response_headers' not in m and 'headers' not in m
 assert all('cookie' not in k.lower() and 'ip_address' not in k.lower() and 'authorization'!=k.lower() for k in m)
result={'passed':True,'offline_only':True,'frozen_source_fact_count':len(facts),'review_count':len(reviews),'source_grade_counts':summary['source_grade_counts'],'hemisphere_counts':summary['hemisphere_counts'],'all_input_SHA_locks_match':True,'all_native_cohort_ID_name_DOB_and_source_raw_places_preserved':True,'Anderson_S1_independent_identity_and_explicit_NY_state_qualification_passed':True,'Anderson_complete_prior_v4_S2_overlay_and_query_uncertainty_preserved':True,'Nobel_native_DOB_blank_and_row_untouched':True,'all_new_query_bindings_homonyms_coordinates_and_ranks_retained':True,'all_new_coordinate_WKT_precision_and_hemisphere_checks_passed':True,'prior_NYC_query_not_retried_and_hotel_hold_preserved':True,'new_exact_name_geography_queries':1,'new_official_source_captures':1,'capture_retries':0,'person_queries':0,'country_birthpoint_unique_entity_and_native_flags_changes':0,'cross_cohort_statistical_deduplication':False,'new_capture_metadata_safe_allowlist_verified':True}
(B/'geography_verification.json').write_text(json.dumps(result,sort_keys=True,indent=2)+'\n');print(json.dumps(result,indent=2))
