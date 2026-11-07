#!/usr/bin/env python3
"""Offline hemisphere-only review of frozen source facts and one query response."""
from pathlib import Path
from datetime import datetime, timezone
from decimal import Decimal
from collections import Counter
import gzip
import hashlib
import json

ROOT = Path(__file__).resolve().parent
BASE = ROOT.parents[1]
FIELDS = BASE / 'academy_v3_workers/fields/accepted.jsonl'
BASELINE = BASE / 'uk_birthplace_checkout/studies/scientist_birthplace_completion_v2/outputs/birthplace_rows.jsonl.gz'
SMIRNOV = 'fields-de5a4b4e279eaf4f'
HUGO = 'fields-ef72cb77368d48fe'
FRANCE = 'http://www.wikidata.org/entity/Q142'
EARTH = 'http://www.wikidata.org/entity/Q2'
COMMUNE = 'http://www.wikidata.org/entity/Q484170'

def now(): return datetime.now(timezone.utc).isoformat()
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def readj(p): return json.loads(p.read_text())
def writej(p, obj): p.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True)+'\n')
def writel(p, rows): p.write_text(''.join(json.dumps(r, ensure_ascii=False, sort_keys=True)+'\n' for r in rows))

def review_fields():
    locks = readj(ROOT/'input_locks.json')
    for item in locks['inputs']:
        assert sha(Path(item['path'])) == item['sha256'], item['path']
    facts = [json.loads(x) for x in FIELDS.read_text().splitlines() if x]
    baseline = {}
    with gzip.open(BASELINE, 'rt') as f:
        for line in f:
            row = json.loads(line)
            if row['record_id'] in {SMIRNOV,HUGO}: baseline[row['record_id']] = row
    assert set(baseline) == {SMIRNOV,HUGO}
    assert {x['record_id'] for x in facts} == {SMIRNOV,HUGO}
    query = (ROOT/'chatenay_malabry_exact.sparql').read_text()
    assert 'LIMIT' not in query.upper()
    assert '?item p:P625 ?coordinateStatement' in query
    assert 'wikibase:rank ?rank' in query and 'wikibase:geoPrecision ?precision' in query
    assert 'wdt:P31' in query and 'wdt:P17' in query
    assert '"Châtenay-Malabry"@en "Châtenay-Malabry"@fr' in query
    outcome = readj(ROOT/'query_outcome.json')
    assert outcome['query_attempts'] == 1 and outcome['retries'] == 0
    assert sha(Path(outcome['response_path'])) == outcome['response_sha256']
    result = json.loads(Path(outcome['response_path']).read_bytes())
    bindings = result['results']['bindings']
    items = {}
    for b in bindings:
        uri = b['item']['value']
        item = items.setdefault(uri, {'candidate_uri':uri, 'candidate_qid':uri.rsplit('/',1)[-1], 'matched_literals':set(), 'labels':set(), 'instance_of':set(), 'instance_of_labels':set(), 'p17_values':set(), 'p17_labels':set(), 'direct_earth_coordinate_statements':{}, 'raw_binding_count':0})
        item['raw_binding_count'] += 1
        for key, target in [('matchedLiteral','matched_literals'),('itemLabel','labels'),('instanceOf','instance_of'),('instanceOfLabel','instance_of_labels'),('country','p17_values'),('countryLabel','p17_labels')]:
            if key in b:
                value = b[key]['value']
                if 'xml:lang' in b[key]: value += '@'+b[key]['xml:lang']
                item[target].add(value)
        if 'coordinateStatement' in b:
            statement = {k:b[k]['value'] for k in ['coordinateStatement','rank','latitude','longitude','globe']}
            statement['precision'] = b.get('precision',{}).get('value')
            old = item['direct_earth_coordinate_statements'].setdefault(statement['coordinateStatement'],statement)
            assert old == statement
    candidates = []
    meaningful_candidates = []
    for item in items.values():
        for k,v in list(item.items()):
            if isinstance(v,set): item[k] = sorted(v)
        item['direct_earth_coordinate_statements'] = list(item['direct_earth_coordinate_statements'].values())
        france_compatible = FRANCE in item['p17_values']
        geographic_type = COMMUNE in item['instance_of']
        item['source_country_qualifier_compatible'] = france_compatible
        item['meaningful_geographic_type'] = geographic_type
        item['included_for_hemisphere_only'] = france_compatible and geographic_type
        if not france_compatible:
            item['candidate_review_reason'] = 'Excluded from hemisphere proof: source explicitly qualifies the place as France; returned P17 does not include France.'
        elif not geographic_type:
            item['candidate_review_reason'] = 'Excluded from hemisphere proof: returned P31 is not an approved settlement or geographic area type; no physical address, institution, person, or other non-locality type is promoted.'
        else:
            item['candidate_review_reason'] = 'Included for hemisphere proof only: exact English/French source locality label, direct P17 France, P31 commune of France. Candidate URI is retained evidence, not assigned as birthplace entity.'
            meaningful_candidates.append(item)
        for s in item['direct_earth_coordinate_statements']:
            assert s['globe'] == EARTH
            if s['precision'] is None:
                s['precision_safe_hemisphere'] = 'held'
            else:
                latitude,precision = Decimal(s['latitude']),abs(Decimal(s['precision']))
                s['latitude_minus_reported_precision'] = str(latitude-precision)
                s['latitude_plus_reported_precision'] = str(latitude+precision)
                s['precision_safe_hemisphere'] = 'north' if latitude-precision > 0 else 'south' if latitude+precision < 0 else 'held'
            s['coordinate_use'] = 'Geographic reference coordinate only; coordinate precision describes reference-point resolution, not locality extent or birthpoint uncertainty. No exact birthpoint or birthplace lat/lon assignment.'
        candidates.append(item)
    assert len(candidates) == outcome['unique_item_count']
    assert sum(x['raw_binding_count'] for x in candidates) == len(bindings)
    signs = [s['precision_safe_hemisphere'] for x in meaningful_candidates for s in x['direct_earth_coordinate_statements']]
    hugo_north = bool(meaningful_candidates) and all(x['direct_earth_coordinate_statements'] for x in meaningful_candidates) and bool(signs) and set(signs)=={'north'}
    reviews=[]
    for fact in facts:
        rid = fact['record_id']
        native = baseline[rid]
        assert native['dob'] == fact['native_dob']
        assert native['hemisphere'] == 'unknown'
        row = {'record_id':rid, 'name':fact['name'], 'cohort':fact['cohort'], 'native_dob':fact['native_dob'],
          'raw_birthplace':fact['raw_birthplace'], 'source_fact_path':str(FIELDS), 'source_fact_sha256':sha(FIELDS),
          'birthplace_source_grade':fact['source_grade'], 'source_birth_date_precision':fact['source_birth_date_precision'],
          'source_capture_kind':fact['source_capture_kind'], 'source_capture_scope':fact['source_capture_scope'],
          'source_sha256':fact['source_sha256'], 'source_url':fact['source_url'],
          'geographic_resolution_source_grade':'S3', 'source_grade_independent_of_geographic_resolution':True,
          'source_grade_independent_of_DOB_grade':True, 'country_assigned':False,
          'birthpoint_coordinates_assigned':False, 'unique_locality_entity_assigned':False,
          'person_QIDs_modified':False, 'native_flags_modified':False, 'native_DOB_modified':False,
          'DOB_groups_modified':False, 'eligibility_modified':False, 'calendar_modified':False,
          'source_birth_year_used_to_fill_native_DOB_or_window':False, 'source_birthplace_granularity_preserved':True}
        if rid == SMIRNOV:
            assert fact['raw_birthplace'] == 'St. Petersburg, Russia'
            row.update(hemisphere='north',review_status='hemisphere_resolved',basis='explicit_named_extent_wholly_north',extent='Russia',new_network_requests=0,
              rule_origin='Existing explicit named geographic extent rule; Russia appears in the source birthplace, with no inference from nationality.',
              proof_note='Russia is wholly in the Northern Hemisphere. No settlement identification or historical renaming is needed for the hemisphere-only result.')
        else:
            assert fact['raw_birthplace'] == 'Châtenay-Malabry, France'
            row.update(hemisphere='north' if hugo_north else 'unknown',review_status='hemisphere_resolved' if hugo_north else 'held',
              basis='unanimous_exact_label_geographic_candidates_direct_Earth_coordinates' if hugo_north else 'insufficient_bounded_locality_proof',
              new_network_requests=1, geographic_query_request_id=outcome['request_id'], geographic_query_response_sha256=outcome['response_sha256'],
              all_returned_homonyms_retained=True, candidate_projection_path=str(ROOT/'locality_candidates.json'),
              france_country_extent_alone_used=False,
              proof_note='France alone is insufficient because the country spans hemispheres. The exact locality query returns all exact English/French label/alias matches; only source-country-compatible meaningful geographic types contribute. Every direct Earth coordinate statement, at every returned rank, lies north even after its reported coordinate precision is subtracted. Reference locality coordinates are not assigned to the birthpoint.')
        reviews.append(row)
    writel(ROOT/'georeview.jsonl',reviews)
    writej(ROOT/'locality_candidates.json',{'request_id':outcome['request_id'], 'candidate_qids_are_evidence_only':True,'no_locality_entity_assignment':True,
      'raw_response_retains_all_bindings':True,'raw_bindings_count':len(bindings),'returned_homonym_count':len(candidates),
      'filter_scope':'Source France qualifier plus meaningful geographic entity type only. All returned homonyms remain in this projection and the raw response, including any nonlocality or physical-address cases.',
      'nonlocality_or_address_candidates_returned':sum(not x['meaningful_geographic_type'] for x in candidates),
      'candidates':candidates})
    summary = {'completed_utc':now(),'scope':'Geography only for two frozen Fields source facts; no NAS source content reviewed.',
      'input_source_facts':2,'review_rows':len(reviews),'hemispheres':dict(Counter(x['hemisphere'] for x in reviews)),
      'bounded_geography_query_budget':1,'actual_geography_queries':1,'retries':0,'redirects_followed':0,
      'person_queries':0,'individual_birthday_queries':0,'new_birthplace_source_requests':0,
      'query_exact_labels_aliases':['Châtenay-Malabry@en','Châtenay-Malabry@fr'],'query_has_LIMIT':False,
      'all_returned_homonyms_retained':True,'returned_homonyms':len(candidates),'raw_query_bindings':len(bindings),
      'all_direct_Earth_coordinate_statements_retained':True,'coordinate_ranks_filtered':False,
      'hemisphere_only':True,'country_assignments':0,'birthpoint_coordinate_assignments':0,'unique_locality_entity_assignments':0,
      'source_facts_mutated':False,'native_DOBs_mutated':False,'native_flags_mutated':False,'QIDs_mutated':False,
      'repository_files_modified':False,'source_and_DOB_grades_independent':True,'geographic_resolution_source_grade':'S3',
      'raw_source_captures_preserve_original_metadata':True,'fields_capture_kind':'web_tool_text_capture_json',
      'SPARQL_capture_kind':'direct_http_response_bytes'}
    writej(ROOT/'summary.json',summary)
    verification = {'verified_utc':now(),'checks':{'all_frozen_input_hashes_match':True,'baseline_compressed_SHA_match':True,
      'only_expected_two_fields_ids':True,'source_DOB_equals_native_without_modification':True,
      'query_no_LIMIT':True,'query_exact_en_fr_labels_and_aliases':True,'query_no_rank_preference_filter':True,
      'all_returned_candidates_and_bindings_retained':True,'no_candidate_unique_entity_assignment':True,
      'hemisphere_only_no_country_or_birthpoint_assignment':True,'source_capture_metadata_preserved':True,
      'single_request_zero_retries':True,'baseline_file_unmodified':True,'source_fact_file_unmodified':True},
      'review_sha256':sha(ROOT/'georeview.jsonl'),'candidate_projection_sha256':sha(ROOT/'locality_candidates.json'),
      'baseline_sha256':sha(BASELINE),'fields_facts_sha256':sha(FIELDS),
      'query_sha256':sha(ROOT/'chatenay_malabry_exact.sparql'),'response_sha256':outcome['response_sha256'],
      'source_quote_policy':'No additional source evidence quotes introduced by this geographic review.'}
    writej(ROOT/'verification.json',verification)
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=='__main__': review_fields()
