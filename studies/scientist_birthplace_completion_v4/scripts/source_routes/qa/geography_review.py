#!/usr/bin/env python3
"""Independent local audit of frozen geographic review and original JSON response."""
from pathlib import Path
from collections import Counter,defaultdict
from datetime import datetime
from decimal import Decimal
import hashlib
import json
import re

W=Path('/workspace/scratch/7e8aa4e0d4af')
P=W/'academy_v4_workers/geography'
Q=W/'academy_v4_workers/qa'
def read(p):return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def key(r):return r['cohort'],r['record_id']

def run():
    cap=json.loads((P/'exact_place_query_capture.json').read_text())
    query=(P/'exact_place_query.rq').read_text()
    raw=P/'exact_place_query_response.bin'
    data=json.loads(raw.read_bytes());bindings=data['results']['bindings']
    ledger=read(P/'query_ledger.jsonl')
    summary=json.loads((P/'geographic_summary.json').read_text())
    assert len(ledger)==cap['query_attempts']==summary['query_count']==summary['NAS_geography_query_count']==1
    assert cap['retry_performed'] is False and summary['query_retries']==0
    assert cap['status']==200 and cap['capture_kind']=='original_HTTP_response_bytes'
    assert sha(raw)==cap['response_sha256']==summary['query_response_sha256']
    assert len(raw.read_bytes())==cap['response_bytes']
    assert sha(P/'exact_place_query.rq')==ledger[0]['query_sha256']==summary['query_sha256']
    assert len(bindings)==cap['binding_count']==summary['query_bindings']==94
    assert ledger[0]['exact_labels']==['New York City','Colorado Springs']
    assert ledger[0]['person_queries']==summary['person_queries']==0
    assert not re.search(r'\bLIMIT\b',query,re.I)
    assert query.count('FILTER(')==4 and query.count('LANG(')==4
    assert 'VALUES ?matchPredicate { rdfs:label skos:altLabel }' in query
    assert datetime.fromisoformat(ledger[0]['time_utc'])<datetime.fromisoformat(cap['captured_at_utc'])
    for file in [W/'academy_v4_workers/vol73/manifest.json',W/'academy_v4_workers/vol74/retained/summary.json']:
        d=json.loads(file.read_text());frozen=d.get('frozen_utc',d.get('frozen_at_utc'))
        assert datetime.fromisoformat(frozen)<datetime.fromisoformat(ledger[0]['time_utc'])
    for lock in json.loads((P/'input_locks.json').read_text())['files']:
        assert sha(W/lock['path'])==lock['sha256'],lock['path']
    groups=defaultdict(list)
    for i,b in enumerate(bindings):groups[(b['requestedName']['value'],b['place']['value'])].append(i)
    assert len(groups)==80
    assert Counter(n for n,q in groups)=={'New York City':78,'Colorado Springs':2}
    candidates=read(P/'candidate_reviews.jsonl')
    observed={(c['requested_exact_English_label_or_alias'],c['entity']):c for c in candidates}
    assert set(observed)==set(groups) and len(candidates)==80
    covered=[]
    physical=[]
    for k,indices in groups.items():
        c=observed[k];sub=[bindings[i] for i in indices]
        assert c['binding_indices_zero_based']==indices
        assert c['binding_count']==len(indices)
        covered.extend(c['binding_indices_zero_based'])
        assert c['country_assigned'] is False and c['birthpoint_coordinates_assigned'] is False
        assert c['unique_place_entity_assigned'] is False
        assert set(c['matched_predicates'])=={b['matchPredicate']['value'] for b in sub}
        assert set(c['english_labels'])=={b['englishLabel']['value'] for b in sub if 'englishLabel' in b}
        assert set(c['english_descriptions'])=={b['englishDescription']['value'] for b in sub if 'englishDescription' in b}
        rawcoords={b['coordinateStatement']['value'] for b in sub if 'coordinateStatement' in b}
        assert {s['coordinateStatement'] for s in c['coordinate_statements']}==rawcoords
        for s in c['coordinate_statements']:
            bs=[b for b in sub if b.get('coordinateStatement',{}).get('value')==s['coordinateStatement']]
            for field in ['coordinateValue','coordinateWkt','latitude','longitude','precision','globe','coordinateRank']:
                assert {b[field]['value'] for b in bs if field in b}=={s[field]}
            latitude=Decimal(s['latitude']);precision=Decimal(s['precision'])
            assert s['globe']=='http://www.wikidata.org/entity/Q2'
            assert precision>0 and latitude-precision>0
            assert s['hemisphere']=='north'
            assert Decimal(s['conservative_latitude_lower_bound'])==latitude-precision
            assert Decimal(s['conservative_latitude_upper_bound'])==latitude+precision
        if c['physical_place_candidate']:physical.append(k[1].rsplit('/',1)[-1])
        else:
            assert c['classification']=='excluded_non_place_homonym'
            assert c['candidate_hemisphere']=='not_applicable_non_place_homonym'
    assert sorted(covered)==list(range(94))
    assert set(physical)=={'Q49258','Q60','Q127430833','Q39319400'}
    hotel=observed[('New York City','http://www.wikidata.org/entity/Q39319400')]
    assert hotel['coordinate_statement_count']==0 and hotel['candidate_hemisphere']=='unknown'
    assert {x['instanceOfLabel'] for x in hotel['instance_statements']}=={'hotel'}
    assert {x['countryLabel'] for x in hotel['country_statements']}=={'United States'}
    city=observed[('Colorado Springs','http://www.wikidata.org/entity/Q49258')]
    assert city['coordinate_statement_count']==1 and city['candidate_hemisphere']=='north'
    assert Decimal(city['coordinate_statements'][0]['latitude'])==Decimal('38.863333333333')
    sources=read(W/'academy_v4_workers/vol73/retained_facts.jsonl')+read(W/'academy_v4_workers/vol74/retained/facts.jsonl')
    source_by={key(f):f for f in sources}
    reviews=read(P/'geographic_reviews.jsonl')
    assert len(reviews)==len({key(r) for r in reviews})==9
    assert {key(r) for r in reviews}==set(source_by)
    assert Counter(r['hemisphere'] for r in reviews)=={'north':8,'unknown':1}
    assert sum(r['query_used'] for r in reviews)==2
    for r in reviews:
        s=source_by[key(r)]
        assert r['raw_birthplace']==s['raw_birthplace']
        assert r['native_dob']==s['native_dob']
        assert r['source_born_clause']==s.get('evidence_quote',s.get('birthplace_evidence_excerpt'))
        assert r['source_original_bytes_sha256']==s.get('source_sha256',s.get('capture',{}).get('original_http_response_bytes_sha256'))
        assert r['source_grade']==r['birthplace_fact_source_grade']=='S2'
        assert r['geography_source_grade']=='S3'
        assert r['country_assigned'] is False and r['birthpoint_coordinates_assigned'] is False
        assert r['country'] is None and r['lat'] is None and r['lon'] is None
        assert r['person_QID_assigned_or_modified'] is False and r['native_fields_modified'] is False
        assert r['DOB_calendar_eligibility_flags_modified'] is False and r['unique_place_entity_assigned'] is False
        assert r['source_birthplace_grain_preserved'] is True
        if r['query_used']:
            ids={q.rsplit('/',1)[-1] for q in r['place_entity_candidates']}
            if r['name']=='Carl D. Anderson':
                assert r['hemisphere']=='unknown' and ids=={'Q60','Q127430833','Q39319400'}
            else:
                assert r['name']=='William Young' and r['hemisphere']=='north' and ids=={'Q49258'}
        else:
            assert r['explicit_region'] in r['raw_birthplace']
            assert r['hemisphere']=='north'
    for k,h in summary['inputs_sha256'].items():assert sha(W/k)==h
    result={'status':'PASS','source_fact_count':9,'hemisphere_counts':{'north':8,'unknown':1},
      'accepted_source_region_extent_count':7,'single_combined_exact_query':True,'query_retries':0,
      'response_representation':'original HTTP SPARQL JSON response bytes',
      'query_sha256':sha(P/'exact_place_query.rq'),'response_sha256':sha(raw),
      'all_94_raw_bindings_accounted_for':True,'all_80_homonym_entities_retained':True,
      'all_four_physical_place_candidates_retained':True,
      'Colorado_Springs_coordinate_and_precision_support_north':True,
      'Carl_Anderson_accepted_place_but_hemisphere_held':True,
      'hotel_Q39319400_missing_coordinates_not_discarded':True,
      'country_point_person_QID_assignments':0,'native_metadata_changes':0,
      'no_parent_death_nationality_or_upbringing_inference':True,'network_requests_by_QA':0}
    (Q/'geography_review.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))

if __name__=='__main__':run()
