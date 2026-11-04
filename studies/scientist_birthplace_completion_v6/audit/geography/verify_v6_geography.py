#!/usr/bin/env python3
"""Offline verification of frozen v6 geography; no network, source editing, or overlay editing."""
from pathlib import Path
from collections import Counter
import gzip,hashlib,json
ROOT=Path(__file__).resolve().parents[2];B=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text())
lines=lambda p:[json.loads(x) for x in p.read_text().splitlines() if x.strip()]
key=lambda r:(r['cohort'],r['record_id'])
locks=read(B/'input_locks.json');summary=read(B/'geographic_summary.json')
for f in locks['files']:
 p=ROOT/f['path'];assert sha(p)==f['sha256'] and p.stat().st_size==f['bytes']
basefile=next(ROOT/f['path'] for f in locks['files'] if f['path'].endswith('birthplace_rows.jsonl.gz'))
assert sha(basefile)==locks['baseline_sha256']=='15f3d58b3334fbc5c32229b0c122ff5e693379fbf9759794e1e3ae87ac06d152'
with gzip.open(basefile,'rt') as f:base_rows=[json.loads(x) for x in f if x.strip()]
base={key(r):r for r in base_rows};assert len(base)==len(base_rows)
facts=[]
for s in locks['source_lanes'].values():
 p=ROOT/s['path'];assert sha(p)==s['sha256'];facts+=lines(p)
byfact={key(f):f for f in facts};reviews=lines(B/'geographic_reviews.jsonl');byreview={key(r):r for r in reviews};contexts=lines(B/'source_context_checks.jsonl');bycontext={key(c):c for c in contexts}
assert len(facts)==len(byfact)==len(reviews)==len(byreview)==len(contexts)==len(bycontext)==summary['fact_count']
assert set(byfact)==set(byreview)==set(bycontext)
for k,f in byfact.items():
 r=byreview[k];c=bycontext[k];prior=base[k]
 assert f.get('frozen_baseline_row',f.get('baseline_row_snapshot'))==prior
 assert f['native_dob']==r['native_dob']==prior['dob'] and f['name']==r['name']==prior['name']
 assert prior['hemisphere']=='unknown'
 assert f['raw_birthplace']==r['raw_birthplace']==c['raw_birthplace']
 assert f['source_grade']==r['source_grade']==r['birthplace_fact_source_grade']=='S2'
 assert r['geography_source_grade']=='S3' and r['method']=='explicit_target_birth_clause_region_extent'
 assert f['evidence_quote']==r['source_evidence_excerpt']==c['source_birth_clause']
 assert f['raw_birthplace'] in f['evidence_quote'] and len(f['evidence_quote'].split())<=25
 assert f['source_sha256']==r['source_original_bytes_sha256']==c['source_original_file_sha256']
 assert sha(ROOT/c['source_original_file'])==f['source_sha256']
 expected_precision=f.get('source_born_clause_dob_precision',f.get('source_DOB_born_clause_precision',f.get('evidence_quote_date_precision')))
 assert r['source_born_clause_date_precision']==c['source_born_clause_date_precision']==expected_precision
 assert c['evidence_quote_date_precision']==f.get('evidence_quote_date_precision',expected_precision)
 assert c['region_qualifier_directly_in_target_birth_clause'] is True
 assert c['regional_extent_hemisphere']==r['hemisphere']
 assert r['status']=='hemisphere_only_accepted' and r['hemisphere'] in {'north','south'}
 assert all(r[x] is False for x in ['query_used','prior_query_evidence_applied','country_assigned','birthpoint_coordinates_assigned','unique_place_entity_assigned','native_fields_modified','person_QID_assigned_or_modified','DOB_calendar_eligibility_flags_modified','statistical_cross_cohort_deduplication','city_point_mapping_used'])
 assert r['source_birthplace_grain_preserved'] is True and r['place_entity_candidates']==[]
 assert r['country'] is r['lat'] is r['lon'] is None
# Validate the only southern decision from the explicit island region, retaining source grain.
luyten=next(r for r in reviews if r['name']=='Willem J. Luyten');lc=bycontext[key(luyten)]
assert luyten['raw_birthplace']=='the city of Semarang in north-central Java' and luyten['hemisphere']=='south'
assert luyten['explicit_region_kind']=='island_region' and luyten['source_city_type_explicit'] is True
assert luyten['parents_country_context_not_appended'] is True and 'Indonesia' not in luyten['raw_birthplace'] and 'Netherlands' not in luyten['raw_birthplace']
assert lc['geography_reviewer_direct_visual_check'] is True and sha(ROOT/lc['visual_checked_file'])==lc['visual_checked_file_sha256']
# Preserve the uneven source-date precision and separate Seaborg's quote from its later date.
byname={r['name']:r for r in reviews}
assert byname['Robert W. Briggs']['source_born_clause_date_precision']=='year'
assert byname['T. L. Cairns']['source_born_clause_date_precision']=='not_stated'
assert byname['John Kirkwood']['raw_birthplace']=='the small town of Gotebo, Oklahoma' and byname['John Kirkwood']['source_born_clause_date_precision']=='absent'
seaborg=byname['Glenn T. Seaborg'];sc=bycontext[key(seaborg)]
assert seaborg['raw_birthplace']=='Ishpeming, Michigan, a small iron-mining town on the Upper Peninsula of Michigan'
assert sc['evidence_quote_date_precision']=='none' and 'first full location clause itself has no date' in sc['separate_birth_date_locator']
franklin=byname['Edward C. Franklin'];assert franklin['native_dob']=='1928-04-14' and franklin['raw_birthplace']=='Berlin, Germany' and franklin['bare_Berlin_cache_not_used'] is True
assert all(r['name']!='I. B. Cohen' for r in reviews)
# All old caches remain locked and are reference-only, without query retries.
cache=read(B/'baseline_and_cache_map.json');assert cache['stage']=='v6_offline_preparation_before_source_lane_freeze'
for c in cache['cache']:
 response=ROOT/c['raw_response_file'];assert sha(response)==c['raw_response_file_sha256']
 body=gzip.decompress(response.read_bytes()) if response.name.endswith('.gz') else response.read_bytes()
 assert hashlib.sha256(body).hexdigest()==c['original_uncompressed_JSON_body_sha256']
 payload=json.loads(body)['results']['bindings'];name=c['exact_English_label_or_alias']
 raw=[r for r in payload if r['requestedName']['value']==name]
 assert len(raw)==c['binding_count'] and len({r['place']['value'] for r in raw})==c['homonym_entity_count']
 assert sha(ROOT/c['candidate_review_file'])==c['candidate_review_file_sha256']
assert (B/'query_ledger.jsonl').read_bytes()==b'' and (B/'candidate_reviews.jsonl').read_bytes()==b''
assert not (B/'new_names_query_intent.jsonl').exists() and not (B/'new_names_query_response.bin').exists()
plan=read(B/'query_plan.json');audit=read(B/'candidate_audit.json')
assert plan['all_source_lanes_frozen'] is True and plan['query_authorized'] is False and plan['exact_English_label_or_alias_names']==[]
assert plan['new_query_count']==audit['new_query_count']==audit['new_candidate_count']==0
assert audit['old_cache_applied_to_new_facts'] is False and audit['old_queries_retried'] is False
assert Counter(r['hemisphere'] for r in reviews)==summary['hemisphere_counts']
assert Counter(f['source_grade'] for f in facts)==summary['source_grade_counts']
nas_before=Counter(r['hemisphere'] for r in base_rows if r['cohort']=='NAS');nas_after=nas_before.copy()
for r in reviews:nas_after['unknown']-=1;nas_after[r['hemisphere']]+=1
assert nas_before['unknown']==summary['baseline_NAS_unknown']==555
assert nas_after['unknown']==summary['expected_NAS_unknown_after_these_reviews']==543
result={'passed':True,'offline_only':True,'source_fact_count':len(facts),'geographic_review_count':len(reviews),'source_grade_counts':summary['source_grade_counts'],'hemisphere_counts':summary['hemisphere_counts'],'all_frozen_input_SHA256_locks_match':True,'all_native_cohort_ID_name_DOB_and_raw_place_fields_preserved':True,'source_identity_QA_separate_from_hemisphere_review':True,'all_S2_source_facts_separate_from_S3_geography':True,'all_region_qualifiers_in_actual_target_birth_clauses':True,'Luyten_Java_south_and_parent_country_exclusion_checked':True,'rural_small_town_regional_and_separate_date_grain_preserved':True,'source_quoted_date_precision_preserved_including_Seaborg_none':True,'old_v2_v5_source_overlay_baseline_and_query_caches_locked':True,'new_queries':0,'old_queries_retried':0,'new_source_captures':0,'person_queries':0,'native_calendar_eligibility_QID_country_point_entity_changes':0,'statistical_cross_cohort_deduplication':False,'expected_NAS_counts_after_integration':dict(nas_after)}
(B/'geography_verification.json').write_text(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2)+'\n');print(json.dumps(result,indent=2))
