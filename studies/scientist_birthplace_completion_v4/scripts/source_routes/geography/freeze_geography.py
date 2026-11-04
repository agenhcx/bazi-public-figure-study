#!/usr/bin/env python3
"""Review frozen S2 source facts for hemisphere only using one frozen S3 place query.

This script performs no network operations and never edits source facts or baseline rows.
"""
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path
import datetime, gzip, hashlib, json
ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent
BASE=ROOT/'uk_birthplace_checkout/studies/scientist_birthplace_completion_v3/outputs/birthplace_rows.jsonl.gz'
BASE_SHA='6df02f0b3a535c8b5447ee704ddc96f473509ed9c2df84b25d6b40064a5dff44'
SOURCES={
 'vol73':(ROOT/'academy_v4_workers/vol73/retained_facts.jsonl','75706e12eb3eab775845713991946913f91535d748bda6c9ef5a681fa3508cb3'),
 'vol74':(ROOT/'academy_v4_workers/vol74/retained/facts.jsonl','0f62174c38c5d0bae17ea742aef8c614c09e21764fe5351e828cfc2f7282cad1'),
}
EARTH='http://www.wikidata.org/entity/Q2'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(name,value):
 p=OUT/name;p.write_text(json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2)+'\n')
def lines(name,rows):
 (OUT/name).write_text(''.join(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n' for r in rows))
def rel(p):return str(p.relative_to(ROOT))
def v(b,k):return b.get(k,{}).get('value')
def vals(rows,k):return sorted({v(r,k) for r in rows if k in r})
def distinct_records(rows,keys):
 d={}
 for r in rows:
  rec={k:v(r,k) for k in keys if k in r};d[json.dumps(rec,sort_keys=True)]=rec
 return list(d.values())
assert sha(BASE)==BASE_SHA
with gzip.open(BASE,'rt') as f:baseline=[json.loads(x) for x in f if x.strip()]
bykey={(r['cohort'],r['record_id']):r for r in baseline}
assert len(bykey)==len(baseline)
facts=[];input_paths=[BASE]
for lane,(path,locked_sha) in SOURCES.items():
 assert sha(path)==locked_sha
 input_paths.append(path)
 for line in path.read_text().splitlines():
  if not line.strip():continue
  f=json.loads(line);f['_lane']=lane;f['_path']=path;facts.append(f)
assert len(facts)==len({(f['cohort'],f['record_id']) for f in facts})
for f in facts:
 old=bykey[(f['cohort'],f['record_id'])]
 assert f['source_grade']=='S2' and old['hemisphere']=='unknown'
 assert f['native_dob']==old['dob'] and f['name']==old['name']
 snapshot=f.get('frozen_baseline_row',f.get('baseline_row_snapshot'))
 assert snapshot==old
 if f['_lane']=='vol73':
  chapter=f['locator']['chapter'];raw=ROOT/f'academy_v4_workers/vol73/raw/chapter_{chapter:02d}.html'
  assert sha(raw)==f['original_bytes_sha256']==f['source_sha256']
 else:
  raw=ROOT/f['capture']['raw_file'];assert sha(raw)==f['capture']['original_http_response_bytes_sha256']
 input_paths.append(raw)
# Both bare-city source clauses have been inspected in their retained actual contexts.
contexts=[]
for chapter,target,term,rejected in [
 (3,'New York City','Born on September 3, 1905, in New York City',{'United States':'describes father arrival, not target birth'}),
 (21,'Colorado Springs','WILLIAM G. YOUNG was born in Colorado Springs on July 30, 1902',{'California':'qualifies target deathplace Laguna Hills, not birthplace'})]:
 text=ROOT/f'academy_v4_workers/vol73/raw/chapter_{chapter:02d}.txt';t=text.read_text();assert term in t
 input_paths.append(text)
 contexts.append({'raw_birthplace':target,'context_file':rel(text),'context_file_sha256':sha(text),'source_born_clause_retained':term,'state_or_country_qualifier_in_actual_target_born_clause':False,'unrelated_context_not_promoted':rejected,'exact_name_query_required':True,'same_birth_paragraph_explicit_city_type_backreference':False if target=='New York City' else None,'same_birth_paragraph_city_word_context':'Only occurs within proper name New York City; no this-city or independent city-type backreference' if target=='New York City' else None})
lines('source_context_checks.jsonl',contexts)
meta=json.loads((OUT/'exact_place_query_capture.json').read_text())
ledger=[json.loads(x) for x in (OUT/'query_ledger.jsonl').read_text().splitlines() if x.strip()]
assert len(ledger)==1 and meta['query_attempts']==1 and meta['retry_performed'] is False
qpath=OUT/'exact_place_query.rq';response=OUT/'exact_place_query_response.bin'
assert sha(qpath)==ledger[0]['query_sha256']
assert sha(response)==meta['response_sha256']
assert meta['status']==200 and meta['parse_status']=='valid_SPARQL_JSON'
query=qpath.read_text();assert 'LIMIT ' not in query.upper()
assert 'P19' not in query and 'P569' not in query
bindings=json.loads(response.read_bytes())['results']['bindings']
assert len(bindings)==meta['binding_count']
groups=defaultdict(list)
for i,b in enumerate(bindings):groups[(v(b,'requestedName'),v(b,'place'))].append((i,b))
assert {n for n,p in groups}=={'Colorado Springs','New York City'}
# Reviewed exhaustive physical-place classification for this saved response only.
# City, mint, and hotel candidates are retained; a missing hotel coordinate forces hold.
physical={'Q49258','Q60','Q127430833','Q39319400'}
creative_types={'photograph','plaque','single','song','musical work/composition','album','painting','print','portfolio','television series episode','video game','level'}
candidates=[]
for (name,entity),indexed in sorted(groups.items()):
 indices=[i for i,b in indexed];rows=[b for i,b in indexed];qid=entity.rsplit('/',1)[-1]
 types=set(vals(rows,'instanceOfLabel'))
 isphysical=qid in physical
 if isphysical:classification='physical_geographic_place';exclusion=None
 elif types and types<=creative_types:
  classification='excluded_non_place_homonym';exclusion='creative work, image, or art object; entity is not a geographic birthplace place'
 elif types=={'art exhibition'}:
  classification='excluded_non_place_homonym';exclusion='exhibition event, not a geographic place entity'
 elif types=={'musical group'}:
  classification='excluded_non_place_homonym';exclusion='musical organization, not a geographic place'
 elif types=={'government agency'}:
  classification='excluded_non_place_homonym';exclusion='government organization, not a facility/address/place entity in the returned type and description'
 elif types=={'Wikimedia disambiguation page'}:
  classification='excluded_non_place_homonym';exclusion='Wikimedia disambiguation page, not a geographic place'
 else:raise AssertionError(('Unreviewed exact-name homonym',qid,types))
 coords=distinct_records([r for r in rows if 'coordinateStatement' in r],['coordinateStatement','coordinateWkt','coordinateRank','coordinateValue','latitude','longitude','globe','precision'])
 coordreviews=[]
 for c in coords:
  cr=dict(c);cr['evidence_role']='S3_geography_only_not_birthpoint'
  if c.get('globe')!=EARTH:cr.update(status='non_Earth_or_globe_missing_retained',hemisphere='unknown')
  else:
   try:
    lat=Decimal(c['latitude']);lon=Decimal(c['longitude']);precision=Decimal(c['precision'])
    valid=lat.is_finite() and lon.is_finite() and precision.is_finite() and -90<=lat<=90 and -180<=lon<=180 and precision>0 and precision<=180
    if not valid:raise ValueError('invalid coordinate or precision')
    sign='north' if lat-precision>0 else ('south' if lat+precision<0 else 'unknown')
    cr.update(status='valid_direct_Earth_coordinate' if sign!='unknown' else 'precision_interval_crosses_or_touches_equator',hemisphere=sign,conservative_latitude_lower_bound=str(lat-precision),conservative_latitude_upper_bound=str(lat+precision))
   except (KeyError,InvalidOperation,ValueError):cr.update(status='missing_or_invalid_coordinate_or_precision',hemisphere='unknown')
  coordreviews.append(cr)
 if not isphysical:hem='not_applicable_non_place_homonym'
 elif not coords:hem='unknown'
 elif any(c['status']!='valid_direct_Earth_coordinate' for c in coordreviews):hem='unknown'
 else:
  signs={c['hemisphere'] for c in coordreviews};hem=next(iter(signs)) if len(signs)==1 else 'unknown'
 candidate={'requested_exact_English_label_or_alias':name,'entity':entity,'english_labels':vals(rows,'englishLabel'),'english_descriptions':vals(rows,'englishDescription'),'binding_indices_zero_based':indices,'binding_count':len(rows),'matched_predicates':vals(rows,'matchPredicate'),'all_raw_bindings_retained_in':rel(response),'classification':classification,'physical_place_candidate':isphysical,'exclusion_reason':exclusion,'instance_statements':distinct_records([r for r in rows if 'instanceStatement' in r],['instanceStatement','instanceOf','instanceRank','instanceOfLabel']),'country_statements':distinct_records([r for r in rows if 'countryStatement' in r],['countryStatement','country','countryRank','countryLabel']),'coordinate_statements':coordreviews,'coordinate_statement_count':len(coords),'explicit_region_extent_usable':False if qid=='Q39319400' else None,'cached_country_extent_review':'Only P17 United States; no all-northern region basis inferred' if qid=='Q39319400' else None,'candidate_hemisphere':hem,'unique_place_entity_assigned':False,'country_assigned':False,'birthpoint_coordinates_assigned':False}
 candidates.append(candidate)
lines('candidate_reviews.jsonl',candidates)
# Stable, coarse extents named in the actual source-born clauses; no city point is used.
# No numeric extent precision is claimed. No country is inferred or assigned.
explicit_regions={
 'Wilton, New Hampshire':('New Hampshire','state','entire named state lies north of the equator'),
 'Ansley, Nebraska':('Nebraska','state','entire named state lies north of the equator'),
 'Platte, South Dakota':('South Dakota','state','entire named state lies north of the equator'),
 'Kingston, Ontario, Canada':('Ontario, Canada','province_and_country','both explicitly named geographic extents lie wholly north of the equator'),
 'Somerset, Kentucky':('Kentucky','state','entire named state lies north of the equator'),
 'a farm near Hudson, Ohio':('Ohio','state','entire named state lies north of the equator; farm and near-locality wording preserved'),
 'Tap, a village in Hungary':('Hungary','country','named country extent, including historical Hungary at native birth year, lies wholly north of the equator; village wording preserved'),
}
reviews=[]
for f in sorted(facts,key=lambda f:(f['cohort'],f['record_id'])):
 place=f['raw_birthplace'];quote=f.get('evidence_quote',f.get('birthplace_evidence_excerpt'))
 source_sha=f.get('source_sha256') or f['capture']['original_http_response_bytes_sha256']
 r={'cohort':f['cohort'],'record_id':f['record_id'],'name':f['name'],'native_dob':f['native_dob'],'raw_birthplace':place,'source_grade':'S2','birthplace_fact_source_grade':'S2','geography_source_grade':'S3','source_fact_file':rel(f['_path']),'source_fact_file_sha256':sha(f['_path']),'source_url':f['source_url'],'source_original_bytes_sha256':source_sha,'source_born_clause':quote,'country_assigned':False,'birthpoint_coordinates_assigned':False,'unique_place_entity_assigned':False,'native_fields_modified':False,'person_QID_assigned_or_modified':False,'DOB_calendar_eligibility_flags_modified':False,'source_birthplace_grain_preserved':True,'country':None,'lat':None,'lon':None}
 if place in explicit_regions:
  region,kind,basis=explicit_regions[place]
  assert region.split(',')[0] in quote
  r.update(hemisphere='north',status='hemisphere_only_accepted',method='explicit_target_born_clause_region_extent',explicit_region=region,explicit_region_kind=kind,geographic_basis=basis,place_entity_candidates=[],query_used=False,city_point_mapping_used=False)
 else:
  cs=[c for c in candidates if c['requested_exact_English_label_or_alias']==place];assert cs
  pcs=[c for c in cs if c['physical_place_candidate']]
  signs={c['candidate_hemisphere'] for c in pcs}
  sign=next(iter(signs)) if len(signs)==1 and 'unknown' not in signs else 'unknown'
  reason='all retained exact-name physical place candidates have valid direct Earth coordinates with precision safely north of equator' if sign=='north' else 'exact-name physical place collision includes missing coordinates: hotel Q39319400; do not select famous city or infer from country/NAS/parent/death context'
  r.update(hemisphere=sign,status='hemisphere_only_accepted' if sign!='unknown' else 'held_unknown',method='single_exact_English_label_or_alias_place_query',geographic_basis=reason,query_used=True,query_sha256=sha(qpath),query_response_sha256=sha(response),all_homonym_entity_count=len(cs),physical_place_candidate_count=len(pcs),place_entity_candidates=[c['entity'] for c in pcs],candidate_hemisphere_set=sorted(signs),candidate_review_file='academy_v4_workers/geography/candidate_reviews.jsonl',city_point_mapping_used=False)
 reviews.append(r)
lines('geographic_reviews.jsonl',reviews)
locks={'baseline_sha256':BASE_SHA,'root_explicit_both_source_lane_freeze_received':True,'source_lanes':{k:{'path':rel(p),'sha256':s} for k,(p,s) in SOURCES.items()},'files':[{'path':rel(p),'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(set(input_paths))],'source_fact_count':len(facts),'cohort_key_count':len({(f['cohort'],f['record_id']) for f in facts}),'source_facts_not_modified':True,'native_baseline_not_modified':True}
write('input_locks.json',locks)
summary={'schema':'scientist_birthplace_completion_v4_NAS_geographic_review','frozen':True,'fact_count':len(facts),'source_grade_counts':dict(Counter(f['source_grade'] for f in facts)),'hemisphere_counts':dict(Counter(r['hemisphere'] for r in reviews)),'status_counts':dict(Counter(r['status'] for r in reviews)),'explicit_born_clause_extent_count':sum(not r['query_used'] for r in reviews),'geographic_lookup_grade':'S3 separate from S2 birthplace fact evidence','query_count':1,'NAS_geography_query_count':1,'query_retries':0,'person_queries':0,'exact_requested_names':['New York City','Colorado Springs'],'query_bindings':len(bindings),'retained_homonym_entity_count':len(candidates),'physical_place_candidate_count':sum(c['physical_place_candidate'] for c in candidates),'query_capture_representation':'original_HTTP_SPARQL_JSON_response_bytes; not a web-tool projection','query_response_sha256':sha(response),'query_sha256':sha(qpath),'new_country_assignments':0,'new_birthpoint_coordinate_assignments':0,'new_unique_place_entity_assignments':0,'native_DOB_calendar_identity_eligibility_flags_QIDs_changes':0,'no_NAS_nationality_parent_upbringing_deathplace_inference':True,'held':[{'name':r['name'],'raw_birthplace':r['raw_birthplace'],'reason':r['geographic_basis']} for r in reviews if r['hemisphere']=='unknown'],'inputs_sha256':{rel(p):sha(p) for p in [BASE,*[x[0] for x in SOURCES.values()]]}}
write('geographic_summary.json',summary)
print(json.dumps(summary,ensure_ascii=False,indent=2))
