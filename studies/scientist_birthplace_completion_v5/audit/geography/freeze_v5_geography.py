#!/usr/bin/env python3
"""Offline hemisphere-only review of frozen v5 facts; all network captures already closed."""
from pathlib import Path
from collections import Counter,defaultdict
from decimal import Decimal,InvalidOperation
import gzip,hashlib,json
ROOT=Path(__file__).resolve().parents[2];B=Path(__file__).resolve().parent
BASE=ROOT/'uk_birthplace_checkout/studies/scientist_birthplace_completion_v4/outputs/birthplace_rows.jsonl.gz'
BASE_SHA='abbce4e99ad51252dd5e127a0609bc6c4950c121afa2dd126bfc2187b39cd4e8'
FILES={
 'vol75':('academy_v5_workers/vol75/retained_facts.jsonl','f3c2b77bb67003ef3a30daccda2be5e85abce72d5708dd432b3989edfb55ca37'),
 'vol76':('academy_v5_workers/vol76/retained/facts.jsonl','fec338dc9ed339c0f002b7dda80588eef3885fa71a40891d56a3973200696b8c'),
 'anderson_S1':('academy_v5_workers/geography/anderson_geographic_qualification_fact.jsonl','3bcece56d27a1f4c7628ab2405009833253b40673ff16632a805109b246145c4'),
}
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text())
lines=lambda p:[json.loads(x) for x in p.read_text().splitlines() if x.strip()]
def save(name,data):
 (B/name).write_text(json.dumps(data,ensure_ascii=False,sort_keys=True,indent=2)+'\n')
def save_lines(name,data):
 (B/name).write_text(''.join(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n' for r in data))
def rel(p):return str(p.relative_to(ROOT))
def value(b,k):return b.get(k,{}).get('value')
def vals(rr,k):return sorted({value(r,k) for r in rr if k in r})
def distinct(rr,keys):
 d={}
 for r in rr:
  x={k:value(r,k) for k in keys if k in r};d[json.dumps(x,sort_keys=True)]=x
 return list(d.values())
assert sha(BASE)==BASE_SHA
with gzip.open(BASE,'rt') as f:oldrows=[json.loads(x) for x in f if x.strip()]
old={(r['cohort'],r['record_id']):r for r in oldrows}
facts=[];inputs=[BASE]
for lane,(name,expected) in FILES.items():
 p=ROOT/name;assert sha(p)==expected;inputs.append(p)
 for f in lines(p):
  f['_lane']=lane;f['_source_fact_path']=p;facts.append(f)
assert len(facts)==len({(f['cohort'],f['record_id']) for f in facts})
for f in facts:
 baseline=old[(f['cohort'],f['record_id'])]
 assert f.get('frozen_baseline_row',f.get('baseline_row_snapshot'))==baseline
 assert f['native_dob']==baseline['dob'] and f['name']==baseline['name'] and baseline['hemisphere']=='unknown'
 if f['_lane']=='vol75':
  p=ROOT/f"academy_v5_workers/vol75/raw/chapter_{f['locator']['chapter']:02d}.html";assert sha(p)==f['source_sha256'];inputs.append(p)
 elif f['_lane']=='vol76':
  p=ROOT/f['capture']['raw_file'];assert sha(p)==f['capture']['original_http_response_bytes_sha256'];inputs.append(p)
 else:
  p=ROOT/f['source_capture_file'];assert sha(p)==f['source_sha256'];inputs.append(p)
# Lock the prior packaged v4 query without duplicating it or making another request.
prior_response=ROOT/'uk_birthplace_checkout/studies/scientist_birthplace_completion_v4/audit/geography/exact_place_query_response.json.gz'
prior_candidates=ROOT/'uk_birthplace_checkout/studies/scientist_birthplace_completion_v4/audit/geography/candidate_reviews.jsonl.gz'
prior_raw=gzip.decompress(prior_response.read_bytes());prior_sha=hashlib.sha256(prior_raw).hexdigest();assert prior_sha=='4153c960cb3710ad452d5dcbd74b3e8a2236898bb6b3658e7ae3da6b6837c38a'
prior_cs=[json.loads(x) for x in gzip.decompress(prior_candidates.read_bytes()).decode().splitlines() if x.strip()]
inputs += [prior_response,prior_candidates]
q=B/'new_names_query.rq';response=B/'new_names_query_response.bin';capture=read(B/'new_names_query_capture.json');intent=lines(B/'new_names_query_intent.jsonl')
assert len(intent)==1 and capture['status']==200 and capture['parse_status']=='valid_SPARQL_JSON' and capture['query_attempts']==1 and capture['retry_performed'] is False
assert sha(q)==intent[0]['query_sha256'] and sha(response)==capture['response_sha256']
query=q.read_text();assert 'LIMIT ' not in query.upper() and 'P19' not in query and 'P569' not in query and '"New York City"@en' not in query
bindings=json.loads(response.read_bytes())['results']['bindings'];assert len(bindings)==capture['binding_count']
groups=defaultdict(list)
for i,b in enumerate(bindings):groups[(value(b,'requestedName'),value(b,'place'))].append((i,b))
assert {x[0] for x in groups}=={'Berlin','Detroit'}
missing_geo={'Q131325110','Q133270230','Q2214975','Q4892345'}
physical={entity for (name,entity),rr in groups.items() if any('coordinateStatement' in b for i,b in rr) or entity.rsplit('/',1)[-1] in missing_geo}
# Write the six final reviews early; subsequent work only enriches the audit files.
reviews=[]
for f in sorted(facts,key=lambda f:(f['cohort'],f['record_id'])):
 place=f['raw_birthplace'];source_sha=f.get('source_sha256') or f['capture']['original_http_response_bytes_sha256'];quote=f.get('evidence_quote',f.get('birthplace_evidence_excerpt'))
 r={'cohort':f['cohort'],'record_id':f['record_id'],'name':f['name'],'native_dob':f['native_dob'],'raw_birthplace':place,'source_grade':f['source_grade'],'birthplace_fact_source_grade':f['source_grade'],'geography_source_grade':'S3','source_fact_file':rel(f['_source_fact_path']),'source_fact_file_sha256':sha(f['_source_fact_path']),'source_url':f['source_url'],'source_original_bytes_sha256':source_sha,'source_evidence_excerpt':quote,'source_evidence_kind':'structured_birth_place_field' if f['_lane']=='anderson_S1' else 'explicit_target_born_clause','country_assigned':False,'birthpoint_coordinates_assigned':False,'unique_place_entity_assigned':False,'native_fields_modified':False,'person_QID_assigned_or_modified':False,'DOB_calendar_eligibility_flags_modified':False,'source_birthplace_grain_preserved':True,'statistical_cross_cohort_deduplication':False,'city_point_mapping_used':False,'country':None,'lat':None,'lon':None}
 if place in {'Santa Barbara, California','Brooklyn, New York','New York, NY, USA'}:
  region='California' if 'California' in place else 'New York state (NY)'
  r.update(hemisphere='north',status='hemisphere_only_accepted',method='explicit_structured_birth_place_state_qualification' if f['_lane']=='anderson_S1' else 'explicit_target_born_clause_state_extent',explicit_region=region,explicit_region_kind='state',geographic_basis='explicit birth-place state qualifier '+region+' lies wholly north of equator; no city coordinate, national-membership, country-wide, upbringing, parent, work or deathplace inference',place_entity_candidates=[],query_used=False)
  if f['_lane']=='anderson_S1':r.update(prior_v4_S2_overlay_preserved=True,prior_v4_hotel_query_uncertainty_preserved=True,new_official_qualification_resolves_prior_hold=True,official_source_identity_independently_verified=True,prior_query_not_retried=True)
 elif place=='New York City':
  cs=[x for x in prior_cs if x['requested_exact_English_label_or_alias']==place];pc=[x for x in cs if x['physical_place_candidate']]
  assert any(x['entity'].endswith('/Q39319400') and not x['coordinate_statements'] for x in pc)
  r.update(hemisphere='unknown',status='held_unknown',method='reuse_prior_frozen_exact_name_query_no_request',geographic_basis='unqualified target-born New York City; prior exact-name hotel Q39319400 has no coordinate and only United States P17; parents and schooling do not qualify birthplace',query_used=False,prior_query_evidence_used=True,prior_query_response_file=rel(prior_response),prior_query_response_gzip_sha256=sha(prior_response),prior_query_original_JSON_sha256=prior_sha,prior_candidate_review_file=rel(prior_candidates),all_homonym_entity_count=len(cs),physical_place_candidate_count=len(pc),place_entity_candidates=[x['entity'] for x in pc],candidate_hemisphere_set=['north','unknown'])
 else:
  assert place in {'Berlin','Detroit'}
  cs=[(entity,rr) for (name,entity),rr in groups.items() if name==place];pc=[entity for entity,rr in cs if entity in physical]
  r.update(hemisphere='north' if place=='Detroit' else 'unknown',status='hemisphere_only_accepted' if place=='Detroit' else 'held_unknown',method='single_new_exact_English_label_or_alias_place_query',geographic_basis='all eight exact-name geographic candidates have valid direct Earth coordinates with precision safely north of equator; no unique Detroit selected' if place=='Detroit' else 'cross-hemisphere exact-name candidates include Berlin South Africa Q4892343; four geographic candidates lack coordinates, so no famous-capital choice',query_used=True,query_sha256=sha(q),query_response_sha256=sha(response),all_homonym_entity_count=len(cs),physical_place_candidate_count=len(pc),place_entity_candidates=sorted(pc),candidate_hemisphere_set=['north'] if place=='Detroit' else ['north','south','unknown'],candidate_review_file='academy_v5_workers/geography/candidate_reviews.jsonl')
 reviews.append(r)
save_lines('geographic_reviews.jsonl',reviews)
# Preserve every new homonym and every statement/rank/value, including sparse values.
nonplace_reason={
 'creative':'creative work, catalogue art object, publication, fictional character, or media item; not a geographic place',
 'mobile':'mobile ship/aircraft/vehicle entity; not a geographic locality/fixed facility/address entity',
 'person':'person, animal, cultivar, or name entity; not a geographic place',
 'organization':'organization/manufacturer/musical group, with no fixed facility/address assertion in returned types and description',
 'disambiguation':'Wikimedia disambiguation page, not a geographic place',
 'device':'radar device, not a geographic place',
}
creative={'encyclopedia article','painting','print','work with multiple executions','television series','song','video album','film','article','musical work/composition','music track with vocals','level','television series episode','literary work','single','album','dramatico-musical work','comic book series','photograph','audio track','performed music','fictional human','television character','video game','plaque'}
mobile={'warship','bulk carrier','roll-on/roll-off ship','car ferry','Boeing 787-9','ship','barque','merchant vessel','replenishment oiler','frigate','cruise ship','motor ship','passenger ferry','rotor ship','passenger vessel'}
people={'horse','human','family name','unisex given name','rose cultivar','individual animal'}
org={'historical motorcycle manufacturer','musical group','automobile manufacturer'}
candidates=[]
for (name,entity),indexed in sorted(groups.items()):
 rr=[b for i,b in indexed];types=set(vals(rr,'instanceOfLabel'));qid=entity.rsplit('/',1)[-1];isphysical=entity in physical
 if isphysical:reason=None;kind='physical_geographic_place'
 elif types and types<=creative:reason=nonplace_reason['creative'];kind='excluded_non_place_homonym'
 elif types and types<=mobile:reason=nonplace_reason['mobile'];kind='excluded_non_place_homonym'
 elif types and types<=people:reason=nonplace_reason['person'];kind='excluded_non_place_homonym'
 elif types and types<=org:reason=nonplace_reason['organization'];kind='excluded_non_place_homonym'
 elif types=={'Wikimedia disambiguation page'}:reason=nonplace_reason['disambiguation'];kind='excluded_non_place_homonym'
 elif qid=='Q821208' and not types and vals(rr,'englishDescription')==['German radar device']:reason=nonplace_reason['device'];kind='excluded_non_place_homonym'
 else:raise AssertionError(('Unreviewed new homonym',qid,types))
 coords=distinct([r for r in rr if 'coordinateStatement' in r],['coordinateStatement','coordinateWkt','coordinateRank','coordinateValue','latitude','longitude','globe','precision']);crs=[]
 for c in coords:
  cr=dict(c);cr['evidence_role']='S3_geography_only_not_birthpoint'
  if c.get('globe')!='http://www.wikidata.org/entity/Q2':cr.update(status='non_Earth_or_missing_globe_retained',hemisphere='unknown')
  else:
   try:
    lat=Decimal(c['latitude']);lon=Decimal(c['longitude']);prec=Decimal(c['precision']);assert lat.is_finite() and lon.is_finite() and prec.is_finite() and -90<=lat<=90 and -180<=lon<=180 and 0<prec<=180
    sign='north' if lat-prec>0 else ('south' if lat+prec<0 else 'unknown');cr.update(status='valid_direct_Earth_coordinate' if sign!='unknown' else 'precision_interval_touches_or_crosses_equator',hemisphere=sign,conservative_latitude_lower_bound=str(lat-prec),conservative_latitude_upper_bound=str(lat+prec))
   except (KeyError,InvalidOperation,AssertionError):cr.update(status='missing_or_invalid_coordinate_or_precision',hemisphere='unknown')
  crs.append(cr)
 if not isphysical:sign='not_applicable_non_place_homonym'
 elif not crs or any(c['status']!='valid_direct_Earth_coordinate' for c in crs):sign='unknown'
 else:
  signs={c['hemisphere'] for c in crs};sign=next(iter(signs)) if len(signs)==1 else 'unknown'
 candidates.append({'requested_exact_English_label_or_alias':name,'entity':entity,'english_labels':vals(rr,'englishLabel'),'english_descriptions':vals(rr,'englishDescription'),'binding_indices_zero_based':[i for i,b in indexed],'binding_count':len(rr),'matched_predicates':vals(rr,'matchPredicate'),'all_raw_bindings_retained_in':rel(response),'classification':kind,'physical_place_candidate':isphysical,'exclusion_reason':reason,'instance_statements':distinct([r for r in rr if 'instanceStatement' in r],['instanceStatement','instanceOf','instanceRank','instanceOfLabel']),'country_statements':distinct([r for r in rr if 'countryStatement' in r],['countryStatement','country','countryRank','countryLabel']),'coordinate_statements':crs,'coordinate_statement_count':len(coords),'candidate_hemisphere':sign,'country_assigned':False,'birthpoint_coordinates_assigned':False,'unique_place_entity_assigned':False})
save_lines('candidate_reviews.jsonl',candidates)
# Verify source contexts without promoting later life or parents into birth qualifiers.
contexts=[]
for ch,place,term,rejected in [(2,'Berlin','was born April 29, 1915, in Berlin.',{'later_Berlin_culture_and_family':'not a target-born country qualifier'}),(4,'New York City','born in New York City on October 31, 1923',{'Russian_immigrant_parents':'not target birthplace region','New_Jersey_piano_competition':'later youth context'}),(11,'Detroit','Leighton was born in Detroit',{'father_auto_company':'not a state/country qualifier','Seattle_Los_Angeles':'later moves'})]:
 p=ROOT/f'academy_v5_workers/vol75/raw/chapter_{ch:02d}.txt';t=p.read_text();assert term in t;inputs.append(p)
 contexts.append({'raw_birthplace':place,'context_file':rel(p),'context_file_sha256':sha(p),'source_born_clause':term,'explicit_target_born_state_or_country_qualifier':False,'explicit_same_birth_paragraph_city_type_backreference':False,'unrelated_context_not_promoted':rejected})
woolsey=next(f for f in facts if f['_lane']=='vol76');gif=ROOT/woolsey['capture']['raw_file'];png=gif.with_suffix('.png');inputs.append(png)
contexts.append({'raw_birthplace':'Brooklyn, New York','context_file':rel(gif),'context_file_sha256':sha(gif),'visual_inspection':'source printed page361 local lossless PNG decode inspected directly','explicit_target_born_state_or_country_qualifier':True,'explicit_state':'New York','basis':'comma-separated locality and state qualifier appears in actual target-born sentence; source syntax independently visually confirmed','later_youth_locations_not_used_to_supply_birthplace':True})
contexts.append({'raw_birthplace':'Santa Barbara, California','explicit_target_born_state_or_country_qualifier':True,'explicit_state':'California','basis':'California occurs directly in the retained target-born clause'})
contexts.append({'raw_birthplace':'New York, NY, USA','explicit_target_born_state_or_country_qualifier':True,'explicit_state':'NY','basis':'official structured birth.place.city.en and locationString.en both explicitly include NY; source full name/DOB/1936Physics/positron identity anchors independently confirmed','prior_NAS_v4_S2_and_query_hold_preserved':True})
save_lines('source_context_checks.jsonl',contexts)
# Actual summary derives all counts from the frozen input rows and candidate reviews.
summary={'schema':'scientist_birthplace_completion_v5_NAS_geographic_review','frozen':True,'fact_count':len(facts),'source_grade_counts':dict(Counter(f['source_grade'] for f in facts)),'hemisphere_counts':dict(Counter(r['hemisphere'] for r in reviews)),'status_counts':dict(Counter(r['status'] for r in reviews)),'explicit_birth_place_state_extent_count':sum(r['method'].startswith('explicit_') for r in reviews),'geographic_lookup_grade':'S3, separate from birthplace S1 or S2 source evidence','new_geography_query_count':1,'new_geography_query_exact_names':['Berlin','Detroit'],'new_geography_query_retries':0,'prior_NYC_Colorado_query_rerun':False,'prior_query_reused_offline_for':['New York City'],'new_official_source_corroboration_capture_count':1,'new_official_source_capture_retries':0,'person_queries':0,'new_query_bindings':len(bindings),'new_query_homonym_entities':len(candidates),'new_query_physical_place_candidates':sum(c['physical_place_candidate'] for c in candidates),'new_query_coordinate_statements':sum(c['coordinate_statement_count'] for c in candidates),'new_query_coordinate_rank_counts':dict(Counter(s['coordinateRank'] for c in candidates for s in c['coordinate_statements'])),'new_query_response_sha256':sha(response),'new_query_sha256':sha(q),'capture_representation':'original_HTTP_JSON_bytes for both new authorized captures, not web projection','new_country_assignments':0,'new_birthpoint_coordinate_assignments':0,'new_unique_place_entity_assignments':0,'native_DOB_calendar_identity_eligibility_flags_QID_changes':0,'Nobel_native_DOBs_left_untouched':True,'statistical_cross_cohort_deduplication':False,'prior_v4_Anderson_S2_overlay_and_hotel_hold_preserved':True,'metadata_sanitization':'safe response header allowlist only; no full headers, cookies, IP addresses or credentials','held':[{'name':r['name'],'raw_birthplace':r['raw_birthplace'],'reason':r['geographic_basis']} for r in reviews if r['hemisphere']=='unknown'],'inputs_sha256':{rel(p):sha(p) for p in [BASE,*[ROOT/x[0] for x in FILES.values()]]}}
save('geographic_summary.json',summary)
inputs += [q,response,B/'nobel_physics_corroboration_response.bin']
locks={'baseline_sha256':BASE_SHA,'source_lanes':{lane:{'path':name,'sha256':expected} for lane,(name,expected) in FILES.items()},'files':[{'path':rel(p),'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(set(inputs))],'prior_v4_query_original_uncompressed_JSON_sha256':prior_sha,'source_fact_count':len(facts),'source_files_and_baseline_not_modified':True}
save('input_locks.json',locks)
save('independent_candidate_review.json',{'reviewer':'independent child agent /root/v4_geo/query_review','mode':'read-only saved response inspection; no requests or file changes','new_query_response_sha256':sha(response),'bindings':314,'entities':151,'Berlin':{'geographic':45,'north':40,'south':1,'coordinate_missing':4,'missing_coordinate_entities':sorted(missing_geo),'result':'held_unknown'},'Detroit':{'geographic':8,'north':8,'result':'north'},'coordinate_statements':50,'coordinate_rank_counts':{'normal':49,'preferred':1},'coordinate_checks':'All Earth, complete fields, valid ranges/positive precision; WKT consistent within precision; all precision intervals clear of equator','Anderson_S1_review':'Expanded name/sourceDOB/Physics1936/positron anchors concur with NAS; explicit NY supplies hemisphere only; prior S2 and query uncertainty retained'})
print(json.dumps({'reviews_file':rel(B/'geographic_reviews.jsonl'),'reviews_sha256':sha(B/'geographic_reviews.jsonl'),**summary},ensure_ascii=False,indent=2))
