#!/usr/bin/env python3
"""Local independent replay of frozen v5 geography candidate data."""
from pathlib import Path
from collections import Counter,defaultdict
from decimal import Decimal
from datetime import datetime
import hashlib,json,gzip,re
W=Path('/workspace/scratch/7e8aa4e0d4af');P=W/'academy_v5_workers/geography';Q=W/'academy_v5_workers/qa'
def read(p):return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def key(r):return r['cohort'],r['record_id']
def run():
 summary=json.loads((P/'geographic_summary.json').read_text());cap=json.loads((P/'new_names_query_capture.json').read_text());ledger=read(P/'new_names_query_intent.jsonl');raw=P/'new_names_query_response.bin';bindings=json.loads(raw.read_bytes())['results']['bindings'];query=(P/'new_names_query.rq').read_text()
 assert len(ledger)==cap['query_attempts']==summary['new_geography_query_count']==1 and cap['retry_performed'] is False
 assert cap['status']==200 and sha(raw)==cap['response_sha256']==summary['new_query_response_sha256']
 assert len(raw.read_bytes())==cap['response_bytes'] and len(bindings)==cap['binding_count']==314
 assert sha(P/'new_names_query.rq')==summary['new_query_sha256']==ledger[0]['query_sha256']
 assert ledger[0]['exact_names']==['Berlin','Detroit'] and ledger[0]['no_person_query'] is True
 assert datetime.fromisoformat(ledger[0]['time_utc'])<datetime.fromisoformat(cap['captured_at_utc'])
 assert not re.search(r'\bLIMIT\b',query,re.I) and query.count('FILTER(')==query.count('LANG(')==4
 assert 'VALUES ?matchPredicate { rdfs:label skos:altLabel }' in query
 groups=defaultdict(list)
 for i,b in enumerate(bindings):groups[(b['requestedName']['value'],b['place']['value'])].append(i)
 assert len(groups)==151 and Counter(n for n,q in groups)=={'Berlin':119,'Detroit':32}
 rows=read(P/'candidate_reviews.jsonl');by={(r['requested_exact_English_label_or_alias'],r['entity']):r for r in rows}
 assert len(rows)==len(by)==151 and set(by)==set(groups)
 covered=[];coords={};physical=defaultdict(list)
 for k,indices in groups.items():
  r=by[k];bs=[bindings[i] for i in indices];assert r['binding_indices_zero_based']==indices and r['binding_count']==len(indices);covered.extend(indices)
  assert set(r['english_labels'])=={b['englishLabel']['value'] for b in bs if 'englishLabel' in b}
  assert set(r['english_descriptions'])=={b['englishDescription']['value'] for b in bs if 'englishDescription' in b}
  assert set(r['matched_predicates'])=={b['matchPredicate']['value'] for b in bs}
  assert {s['coordinateStatement'] for s in r['coordinate_statements']}=={b['coordinateStatement']['value'] for b in bs if 'coordinateStatement' in b}
  for s in r['coordinate_statements']:
   sb=[b for b in bs if b.get('coordinateStatement',{}).get('value')==s['coordinateStatement']]
   for field in ['coordinateValue','coordinateWkt','latitude','longitude','precision','globe','coordinateRank']:
    assert {b[field]['value'] for b in sb if field in b}=={s[field]}
   coords[s['coordinateStatement']]=s
   lat=Decimal(s['latitude']);prec=Decimal(s['precision']);assert prec>0 and lat.is_finite() and prec.is_finite() and s['globe']=='http://www.wikidata.org/entity/Q2'
   low=lat-prec;high=lat+prec;assert Decimal(s['conservative_latitude_lower_bound'])==low and Decimal(s['conservative_latitude_upper_bound'])==high
   assert s['hemisphere']==('north' if low>0 else 'south' if high<0 else 'unknown')
  assert r['country_assigned'] is False and r['birthpoint_coordinates_assigned'] is False and r['unique_place_entity_assigned'] is False
  if r['physical_place_candidate']:physical[k[0]].append(r)
  else:assert r['classification']=='excluded_non_place_homonym' and r['exclusion_reason']
 assert sorted(covered)==list(range(314))
 assert len(coords)==50 and Counter(s['coordinateRank'].rsplit('#',1)[-1] for s in coords.values())=={'NormalRank':49,'PreferredRank':1}
 assert len(physical['Berlin'])==45 and Counter(r['candidate_hemisphere'] for r in physical['Berlin'])=={'north':40,'south':1,'unknown':4}
 assert len(physical['Detroit'])==8 and Counter(r['candidate_hemisphere'] for r in physical['Detroit'])=={'north':8}
 assert by[('Berlin','http://www.wikidata.org/entity/Q4892343')]['candidate_hemisphere']=='south'
 priorfile=W/'uk_birthplace_checkout/studies/scientist_birthplace_completion_v4/audit/geography/exact_place_query_response.json.gz';prior=gzip.decompress(priorfile.read_bytes());priorhash=hashlib.sha256(prior).hexdigest();assert priorhash=='4153c960cb3710ad452d5dcbd74b3e8a2236898bb6b3658e7ae3da6b6837c38a'
 pb=json.loads(prior)['results']['bindings'];hotel=[b for b in pb if b['place']['value'].endswith('/Q39319400')];assert hotel and all('coordinateStatement' not in b for b in hotel)
 sources=read(W/'academy_v5_workers/vol75/retained_facts.jsonl')+read(W/'academy_v5_workers/vol76/retained/facts.jsonl')+read(P/'anderson_geographic_qualification_fact.jsonl');source_by={key(s):s for s in sources};reviews=read(P/'geographic_reviews.jsonl')
 assert len(reviews)==6 and {key(r) for r in reviews}==set(source_by) and Counter(r['hemisphere'] for r in reviews)=={'north':4,'unknown':2}
 assert Counter(r['source_grade'] for r in reviews)=={'S2':5,'S1':1}
 expected={'Carl D. Anderson':'north','Clinton N. Woolsey':'north','N. E. Bradbury':'north','R. B. Leighton':'north','H. H. Barschall':'unknown','Richard B. Bernstein':'unknown'}
 for r in reviews:
  s=source_by[key(r)];assert r['hemisphere']==expected[r['name']] and r['raw_birthplace']==s['raw_birthplace'] and r['native_dob']==s['native_dob']
  assert r['source_evidence_excerpt']==s.get('evidence_quote',s.get('birthplace_evidence_excerpt'))
  assert r['source_original_bytes_sha256']==s.get('source_sha256',s.get('capture',{}).get('original_http_response_bytes_sha256'))
  assert r['source_grade']==s['source_grade'] and r['geography_source_grade']=='S3'
  assert r['country_assigned'] is False and r['birthpoint_coordinates_assigned'] is False and r['unique_place_entity_assigned'] is False
  assert r['country'] is None and r['lat'] is None and r['lon'] is None
  assert r['native_fields_modified'] is False and r['person_QID_assigned_or_modified'] is False and r['statistical_cross_cohort_deduplication'] is False
  if r['name']=='R. B. Leighton':assert set(r['place_entity_candidates'])=={p['entity'] for p in physical['Detroit']}
  if r['name']=='H. H. Barschall':assert set(r['place_entity_candidates'])=={p['entity'] for p in physical['Berlin']}
  if r['name']=='Richard B. Bernstein':assert r['prior_query_original_JSON_sha256']==priorhash and r['query_used'] is False and r['prior_query_evidence_used'] is True
 for rel,h in summary['inputs_sha256'].items():assert sha(W/rel)==h
 assert summary['prior_NYC_Colorado_query_rerun'] is False and summary['statistical_cross_cohort_deduplication'] is False
 report={'status':'PASS','source_reviews':6,'source_grade_counts':{'S2':5,'S1':1},'hemisphere_counts':{'north':4,'unknown':2},'one_new_exact_Berlin_Detroit_query':True,'new_query_retries':0,'all314_raw_bindings_exactly_accounted_for':True,'all151_homonym_entities_retained':True,'all50_coordinate_statements_ranks_globes_precisions_and_bounds_verified':True,'coordinate_rank_counts':{'NormalRank':49,'PreferredRank':1},'Berlin45_physical_candidates':{'north':40,'south':1,'unknown':4},'Detroit8_physical_candidates_all_north':True,'Bernstein_NYC_prior_original_query_bytes_reused_offline':True,'Anderson_explicit_NY_qualification_source_QA_in_separate_report':True,'prior_v4_NYC_hold_objects_preserved':True,'new_country_birthpoint_person_QID_unique_place_assignments':0,'statistical_deduplication':False,'query_response_sha256':sha(raw),'geographic_reviews_sha256':sha(P/'geographic_reviews.jsonl'),'QA_network_requests':0}
 (Q/'geography_review.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':run()
