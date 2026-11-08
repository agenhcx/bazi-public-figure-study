#!/usr/bin/env python3
"""Independent fixed-baseline/full-output QA, using no external sources."""
from pathlib import Path
from collections import Counter
import argparse
import csv
import gzip
import hashlib
import json
import re
import subprocess
import sys
import tempfile

BASE_SHA = '8e880fcf4a659a1c8753a5a0ad4c06552ddd9d0d545334b0e81a2459907d7356'
EXPECTED_COHORTS = {'NAS':2242,'Fields_main':63,'Nobel_science':655,
                    'CAS':1230,'UK_Royal_Society':4983,'DE_Leopoldina':778,
                    'France':775,'Japan':368}
GEO_FIELDS = {'hemisphere','raw_birthplace','country','lat','lon',
 'birthplace_source_grade','birthplace_source_url','birthplace_source_urls',
 'birthplace_evidence_kind','birthplace_evidence_excerpt','birthplace_claim_excerpt',
 'birthplace_locator','birthplace_source_sha256','source_sha256','reason',
 'northern_birthplace_candidate','southern_birthplace_separate',
 'geographic_conflict_pending_review','place_alternatives_retained','locality_resolution'}
NEW_OVERLAY_FIELDS = {'v7_geography_before_overlay','v7_birthplace_fact_evidence',
                      'v7_geographic_review'}
OUTPUTS = {'birthplace_rows.jsonl.gz','changes.jsonl.gz','birthplaces.csv',
 'remaining_unknown.csv','changed_records.csv',
 'all_country_birthplace_summary.csv','summary.json'}
PERSON_CSV_FIELDS = ['cohort','record_id','name','dob','raw_birthplace','hemisphere',
 'birthplace_source_grade','birthplace_source_url','country','lat','lon',
 'final_analysis_eligibility_assigned']
CHANGE_CSV_FIELDS = ['cohort','record_id','name','dob','before_hemisphere',
 'after_hemisphere','before_raw_birthplace','after_raw_birthplace','birthplace_source_grade']
SUMMARY_CSV_FIELDS = ['cohort','baseline_rows','north','south','equator','unknown',
 'previous_unknown','newly_classified']

def read(p):
    with gzip.open(p,'rt',encoding='utf-8') if p.suffix=='.gz' else p.open(encoding='utf-8') as f:
        return [json.loads(x) for x in f if x.strip()]

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def key(r): return r['cohort'],r['record_id']
def csvread(p):
    with p.open(encoding='utf-8',newline='') as f:
        reader=csv.DictReader(f); rows=list(reader)
        assert reader.fieldnames and len(reader.fieldnames)==len(set(reader.fieldnames)),p
        assert all(None not in r for r in rows),p
        return reader.fieldnames,rows
def csvscalar(x): return '' if x is None else str(x)
def canonical_csv(rows, fields):
    return [{k:csvscalar(r.get(k,'')) for k in fields} for r in rows]
def counts(rows):
    return {c:dict(Counter(r['hemisphere'] for r in rows if r['cohort']==c))
            for c in sorted(EXPECTED_COHORTS)}

def verify(workspace, study):
    repo=workspace/'uk_birthplace_checkout'
    baseline=repo/'studies/scientist_birthplace_completion_v6/outputs/birthplace_rows.jsonl.gz'
    assert sha(baseline)==BASE_SHA,'direct baseline SHA'
    before=read(baseline); old={key(r):r for r in before}
    out=study/'outputs'; rows=read(out/'birthplace_rows.jsonl.gz')
    assert len(rows)==len({key(r) for r in rows})==11094
    assert {key(r) for r in rows}==set(old)
    assert Counter(r['cohort'] for r in rows)==Counter(EXPECTED_COHORTS)
    assert {p.name for p in out.iterdir() if p.is_file()}==OUTPUTS
    facts=read(study/'inputs/new_birthplace_facts.jsonl.gz')
    fby={key(f):f for f in facts}
    assert len(fby)==len(facts)
    source_review=json.loads((workspace/'academy_v7_workers/qa/source_review.json').read_text())
    assert source_review['status']=='PASS'
    source_originals=[fact for rel in source_review['source_fact_files'] for fact in read(workspace/rel)]
    source_by={}
    for sf in source_originals:source_by.setdefault(key(sf),[]).append(sf)
    geography_by={key(g):g for g in read(workspace/'academy_v7_workers/geography/geographic_reviews.jsonl')}
    assert set(fby)==set(source_by)
    for k,f in fby.items():
        candidates=source_by[k]
        primary=[sf for sf in candidates if sf['raw_birthplace']==f['raw_birthplace'] and sf.get('evidence_quote',sf.get('birthplace_evidence_excerpt'))==f['evidence_quote'] and sf.get('source_sha256',sf.get('capture',{}).get('original_http_response_bytes_sha256'))==f['source_sha256'] and sf['source_grade']==f['source_grade']]
        assert len(primary)==1,(k,'primary source must be retained exactly')
        sf=primary[0]
        for support in candidates:
            support_sha=support.get('source_sha256',support.get('capture',{}).get('original_http_response_bytes_sha256'))
            assert support_sha in json.dumps(f,ensure_ascii=False),(k,'support evidence SHA missing')
        gf=geography_by[k]
        assert f['raw_birthplace']==sf['raw_birthplace']
        assert f['evidence_quote']==sf.get('evidence_quote',sf.get('birthplace_evidence_excerpt'))
        assert f['source_sha256']==sf.get('source_sha256',sf.get('capture',{}).get('original_http_response_bytes_sha256'))
        assert f['native_dob']==sf['native_dob']
        assert f['source_grade']==sf['source_grade'] and f['source_grade'] in {'S1','S2'}
        assert sf['source_url'] in f['source_urls']
        assert f['identity_independent_QA_passed'] is True
        assert f['geography']['country_assigned'] is False
        assert f['geography']['birthpoint_coordinates_assigned'] is False
        assert f['hemisphere']==f['geography']['hemisphere']==gf['hemisphere']
        assert f['geography']['geography_source_grade']==gf['geography_source_grade']=='S3'
        assert f['geography']['query_used']==gf['query_used']
        assert f['geography']['status']==gf['status']
        assert f['geography']['place_entity_candidates']==gf['place_entity_candidates']
    changed=[]
    prior_overlay_count=0
    for r in rows:
        k=key(r); b=old[k]
        for field,value in b.items():
            if field not in GEO_FIELDS:
                assert field in r and r[field]==value,(k,'frozen field',field)
        assert set(r)-set(b)<=(GEO_FIELDS|NEW_OVERLAY_FIELDS),(k,'new field',set(r)-set(b))
        assert set(b)<=set(r),(k,'deleted field')
        if any(b.get(f'v{version}_birthplace_fact_evidence') for version in [2,3,4,5,6]):
            prior_overlay_count+=1
            for field,value in b.items():
                if re.match(r'v[23456]_',field):assert r[field]==value,(k,'prior versioned overlay object',field)
            assert r==b,(k,'prior overlay complete object')
        if r==b:
            assert k not in fby,(k,'accepted but no change')
        else:
            changed.append(k)
            assert k in fby and r['cohort']=='NAS',(k,'out-of-scope change')
            assert b['hemisphere']=='unknown',(k,'old known hemisphere')
            assert fby[k]['native_dob']==b['dob'],(k,'fact native DOB')
            assert r['country']==b['country'] and r['lat']==b['lat'] and r['lon']==b['lon'],(k,'country/point assignment')
            assert r['hemisphere'] in {'north','south','unknown'},(k,'sign')
            assert r['hemisphere']==fby[k]['hemisphere']
            assert r['raw_birthplace']==fby[k]['raw_birthplace']
            assert r['birthplace_source_grade']==fby[k]['source_grade'],(k,'grade')
            assert r['birthplace_source_urls']==fby[k]['source_urls']
            assert r['birthplace_source_url']==' | '.join(fby[k]['source_urls'])
            assert r['birthplace_source_sha256']==fby[k]['source_sha256']
            assert r['birthplace_evidence_excerpt']==fby[k]['evidence_quote']
            assert r['birthplace_locator']==fby[k]['evidence_locator']
            assert r['birthplace_evidence_kind']=='v7_explicit_birthplace_source'
            assert r['v7_birthplace_fact_evidence']==fby[k]
            assert r['v7_geographic_review']==fby[k]['geography']
            assert r['v7_geography_before_overlay']=={field:b[field] for field in GEO_FIELDS if field in b}
            assert len(r['birthplace_evidence_excerpt'].split())<=25,(k,'quote')
            assert r['northern_birthplace_candidate']==(r['hemisphere']=='north')
            assert r['southern_birthplace_separate']==(r['hemisphere']=='south')
            if 'locality_resolution' in b:
                expected='hemisphere_only_from_explicit_source_qualifier' if r['hemisphere']!='unknown' else 'new_source_place_geography_held'
                assert r['locality_resolution']==expected,(k,'locality resolution')
        if r['cohort']=='UK_Royal_Society': assert r==b,(k,'UK object')
        if r['cohort']=='Nobel_science': assert r['dob']==b['dob']==''
        if r['cohort']=='CAS': assert r['accepted_gregorian_dob']==b['accepted_gregorian_dob']==''
    assert prior_overlay_count==38
    assert set(changed)==set(fby)
    assert len(changed)==len(source_by)
    assert all(f['source_grade'] in {'S1','S2'} for f in facts)
    expected_nas=Counter(r['hemisphere'] for r in before if r['cohort']=='NAS')
    for f in facts:
        expected_nas['unknown']-=1;expected_nas[f['hemisphere']]+=1
    assert Counter(r['hemisphere'] for r in rows if r['cohort']=='NAS')==+expected_nas
    change_rows=read(out/'changes.jsonl.gz')
    assert len(change_rows)==len(changed) and {key(r) for r in change_rows}==set(changed)
    by={key(r):r for r in rows}
    for cr in change_rows:
        b=old[key(cr)]; r=by[key(cr)]
        assert cr=={'cohort':r['cohort'],'record_id':r['record_id'],'name':r['name'],'dob':r['dob'],
                    'before_hemisphere':b['hemisphere'],'after_hemisphere':r['hemisphere'],
                    'before_raw_birthplace':b['raw_birthplace'],'after_raw_birthplace':r['raw_birthplace'],
                    'birthplace_source_grade':r['birthplace_source_grade']},key(cr)
    for fname, source in [('birthplaces.csv',rows),('remaining_unknown.csv',[r for r in rows if r['hemisphere']=='unknown']),('changed_records.csv',change_rows)]:
        fields,observed=csvread(out/fname)
        assert fields==(CHANGE_CSV_FIELDS if fname=='changed_records.csv' else PERSON_CSV_FIELDS)
        assert observed==canonical_csv(source,fields),(fname,'all-row CSV equality')
    summary=json.loads((out/'summary.json').read_text())
    assert summary['schema']=='scientist_birthplace_completion_v7'
    assert summary['cohort_records']==summary['unique_within_cohort_keys']==11094
    assert summary['new_fact_candidates']==len(facts)
    assert summary['new_fact_source_grade_counts']==dict(Counter(f['source_grade'] for f in facts))
    assert summary['new_fact_cohort_counts']==dict(Counter(f['cohort'] for f in facts))
    assert summary['direct_baseline']=='scientist_birthplace_completion_v6'
    assert summary['new_country_or_birthpoint_assignments']==0
    assert summary['other_unchanged_rows']==11094-len(changed)
    assert summary['cross_cohort_deduplicated'] is False
    assert summary['final_cohort_frozen'] is False and summary['BaZi_or_outcomes_added'] is False
    assert summary['all_existing_non_geographic_fields_preserved'] is True
    assert summary['original_DOB_groups_unchanged'] is True
    assert summary['Nobel_native_DOBs_still_blank'] is True
    assert summary['UK_all_4983_rows_preserved'] is True
    country=[]
    for c in sorted(EXPECTED_COHORTS):
        current=[r for r in rows if r['cohort']==c]; prior=[r for r in before if r['cohort']==c]
        cn=Counter(r['hemisphere'] for r in current); pn=Counter(r['hemisphere'] for r in prior)
        country.append({'cohort':c,'baseline_rows':len(current),**{s:cn[s] for s in ['north','south','equator','unknown']},'previous_unknown':pn['unknown'],'newly_classified':pn['unknown']-cn['unknown']})
        day=[r for r in current if re.fullmatch(r'\d{4}-\d{2}-\d{2}',r.get('dob','') or '')]
        window=[r for r in day if 1835<=int(r['dob'][:4])<=1985]
        assert summary['observed_native_DOB_windows'][c]=={'native_nonblank_day_rows':len(day),'native_window_1835_1985_rows':len(window),'hemisphere_counts':dict(Counter(r['hemisphere'] for r in window)),'descriptive_only_not_calendar_eligibility_adjudication':True,'source_birth_years_not_used_to_fill_native_DOB_or_window':True},(c,'native window')
    assert summary['country_summary']==country
    assert summary['newly_classified']==sum(r['newly_classified'] for r in country)
    fields,csvcountry=csvread(out/'all_country_birthplace_summary.csv')
    assert fields==SUMMARY_CSV_FIELDS
    assert csvcountry==canonical_csv(country,fields)
    for rel,expected_sha in summary['inputs_sha256'].items():
        assert sha(repo/rel)==expected_sha,(rel,'input SHA')
    assert str(baseline.relative_to(repo)) in summary['inputs_sha256']
    with tempfile.TemporaryDirectory(prefix='replay_',dir=workspace/'academy_v7_workers/qa') as d:
        subprocess.run([sys.executable,str(study/'scripts/assemble.py'),'--output',d],check=True,capture_output=True,text=True)
        replay=Path(d)
        assert {p.name for p in replay.iterdir() if p.is_file()}==OUTPUTS
        for name in sorted(OUTPUTS): assert (out/name).read_bytes()==(replay/name).read_bytes(),(name,'replay bytes')
    return {'status':'PASS','baseline_sha256':BASE_SHA,'cohort_records':11094,
        'changed_rows':len(changed),'unchanged_rows':11094-len(changed),
        'changed_keys':[list(x) for x in changed],
        'before_counts':counts(before),'after_counts':counts(rows),
        'all_existing_native_fields_equal':True,'all_39_prior_birthplace_evidence_objects_and_versioned_fields_equal':True,'all_38_prior_overlay_whole_rows_equal':True,
        'all_4983_UK_objects_equal':True,'Nobel_all_native_DOB_blank':True,
        'CAS_all_accepted_Gregorian_DOB_blank':True,'country_and_point_assignments':0,
        'all_CSV_cells_equal_to_source_rows':True,'summary_counts_and_native_windows_recomputed':True,
        'seven_output_byte_replay':True,'output_sha256':{n:sha(out/n) for n in sorted(OUTPUTS)}}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--workspace',type=Path,default=Path('/workspace/scratch/7e8aa4e0d4af'))
    p.add_argument('--study',type=Path);p.add_argument('--report',type=Path)
    a=p.parse_args(); study=a.study or a.workspace/'uk_birthplace_checkout/studies/scientist_birthplace_completion_v7'
    result=verify(a.workspace,study)
    text=json.dumps(result,ensure_ascii=False,indent=2)+'\n'
    if a.report:a.report.write_text(text)
    print(text,end='')
