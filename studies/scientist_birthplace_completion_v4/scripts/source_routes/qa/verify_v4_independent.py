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

BASE_SHA = '6df02f0b3a535c8b5447ee704ddc96f473509ed9c2df84b25d6b40064a5dff44'
EXPECTED_COHORTS = {'NAS':2242,'Fields_main':63,'Nobel_science':655,
                    'CAS':1230,'UK_Royal_Society':4983,'DE_Leopoldina':778,
                    'France':775,'Japan':368}
GEO_FIELDS = {'hemisphere','raw_birthplace','country','lat','lon',
 'birthplace_source_grade','birthplace_source_url','birthplace_source_urls',
 'birthplace_evidence_kind','birthplace_evidence_excerpt','birthplace_claim_excerpt',
 'birthplace_locator','birthplace_source_sha256','source_sha256','reason',
 'northern_birthplace_candidate','southern_birthplace_separate',
 'geographic_conflict_pending_review','place_alternatives_retained','locality_resolution'}
NEW_OVERLAY_FIELDS = {'v4_geography_before_overlay','v4_birthplace_fact_evidence',
                      'v4_geographic_review'}
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
    baseline=repo/'studies/scientist_birthplace_completion_v3/outputs/birthplace_rows.jsonl.gz'
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
    source_review=json.loads((workspace/'academy_v4_workers/qa/source_review.json').read_text())
    assert source_review['status']=='PASS'
    source_originals=read(workspace/'academy_v4_workers/vol73/retained_facts.jsonl')+read(workspace/'academy_v4_workers/vol74/retained/facts.jsonl')
    source_by={key(f):f for f in source_originals}
    geography_by={key(g):g for g in read(workspace/'academy_v4_workers/geography/geographic_reviews.jsonl')}
    assert set(fby)==set(source_by)
    for k,f in fby.items():
        sf=source_by[k]
        gf=geography_by[k]
        assert f['raw_birthplace']==sf['raw_birthplace']
        assert f['evidence_quote']==sf.get('evidence_quote',sf.get('birthplace_evidence_excerpt'))
        assert f['source_sha256']==sf.get('source_sha256',sf.get('capture',{}).get('original_http_response_bytes_sha256'))
        assert f['native_dob']==sf['native_dob']
        assert f['source_grade']==sf['source_grade']=='S2'
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
        if b.get('v2_birthplace_fact_evidence') or b.get('v3_birthplace_fact_evidence'):
            prior_overlay_count+=1
            assert r==b,(k,'prior overlay object')
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
            assert r['birthplace_source_grade']=='S2',(k,'grade')
            assert r['birthplace_source_urls']==fby[k]['source_urls']
            assert r['birthplace_source_url']==' | '.join(fby[k]['source_urls'])
            assert r['birthplace_source_sha256']==fby[k]['source_sha256']
            assert r['birthplace_evidence_excerpt']==fby[k]['evidence_quote']
            assert r['birthplace_locator']==fby[k]['evidence_locator']
            assert r['birthplace_evidence_kind']=='v4_birthplace_body'
            assert r['v4_birthplace_fact_evidence']==fby[k]
            assert r['v4_geographic_review']==fby[k]['geography']
            assert r['v4_geography_before_overlay']=={field:b[field] for field in GEO_FIELDS if field in b}
            assert len(r['birthplace_evidence_excerpt'].split())<=25,(k,'quote')
            assert r['northern_birthplace_candidate']==(r['hemisphere']=='north')
            assert r['southern_birthplace_separate']==(r['hemisphere']=='south')
            if 'locality_resolution' in b:
                expected='hemisphere_only_from_new_body_qualifier' if r['hemisphere']!='unknown' else 'new_body_place_geography_held'
                assert r['locality_resolution']==expected,(k,'locality resolution')
        if r['cohort']=='UK_Royal_Society': assert r==b,(k,'UK object')
        if r['cohort']=='Nobel_science': assert r['dob']==b['dob']==''
        if r['cohort']=='CAS': assert r['accepted_gregorian_dob']==b['accepted_gregorian_dob']==''
    assert prior_overlay_count==12
    assert set(changed)==set(fby)
    assert len(changed)==9
    assert Counter(byrow['hemisphere'] for byrow in rows if byrow['cohort']=='NAS')=={'north':1652,'south':31,'unknown':559}
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
    assert summary['schema']=='scientist_birthplace_completion_v4'
    assert summary['cohort_records']==summary['unique_within_cohort_keys']==11094
    assert summary['new_fact_candidates']==len(facts)
    assert summary['new_fact_source_grade_counts']==dict(Counter(f['source_grade'] for f in facts))
    assert summary['new_fact_cohort_counts']==dict(Counter(f['cohort'] for f in facts))
    assert summary['direct_baseline']=='scientist_birthplace_completion_v3'
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
    with tempfile.TemporaryDirectory(prefix='replay_',dir=workspace/'academy_v4_workers/qa') as d:
        subprocess.run([sys.executable,str(study/'scripts/assemble.py'),'--output',d],check=True,capture_output=True,text=True)
        replay=Path(d)
        assert {p.name for p in replay.iterdir() if p.is_file()}==OUTPUTS
        for name in sorted(OUTPUTS): assert (out/name).read_bytes()==(replay/name).read_bytes(),(name,'replay bytes')
    return {'status':'PASS','baseline_sha256':BASE_SHA,'cohort_records':11094,
        'changed_rows':len(changed),'unchanged_rows':11094-len(changed),
        'changed_keys':[list(x) for x in changed],
        'before_counts':counts(before),'after_counts':counts(rows),
        'all_existing_native_fields_equal':True,'all_12_prior_overlay_objects_equal':True,
        'all_4983_UK_objects_equal':True,'Nobel_all_native_DOB_blank':True,
        'CAS_all_accepted_Gregorian_DOB_blank':True,'country_and_point_assignments':0,
        'all_CSV_cells_equal_to_source_rows':True,'summary_counts_and_native_windows_recomputed':True,
        'seven_output_byte_replay':True,'output_sha256':{n:sha(out/n) for n in sorted(OUTPUTS)}}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--workspace',type=Path,default=Path('/workspace/scratch/7e8aa4e0d4af'))
    p.add_argument('--study',type=Path);p.add_argument('--report',type=Path)
    a=p.parse_args(); study=a.study or a.workspace/'uk_birthplace_checkout/studies/scientist_birthplace_completion_v4'
    result=verify(a.workspace,study)
    text=json.dumps(result,ensure_ascii=False,indent=2)+'\n'
    if a.report:a.report.write_text(text)
    print(text,end='')
