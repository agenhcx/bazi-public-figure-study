#!/usr/bin/env python3
"""Offline UK birthplace overlay. Frozen native DOB/identity/calendar fields stay intact."""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
from copy import deepcopy
import csv, gzip, hashlib, importlib.util, json
from pathlib import Path


def read(path):
    with (gzip.open(path, 'rt', encoding='utf-8') if str(path).endswith('.gz') else open(path, encoding='utf-8')) as f:
        return [json.loads(line) for line in f if line.strip()]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, rows):
    data=''.join(json.dumps(r, ensure_ascii=False, sort_keys=True)+'\n' for r in rows).encode()
    path.write_bytes(gzip.compress(data,mtime=0) if str(path).endswith('.gz') else data)


def rank(grade):
    return {'S1':0,'S2':1,'S1_or_S2_existing_body_metadata_not_reopened':2,'S3':3}.get(grade,4)


def candidate_id(c):
    return hashlib.sha256(json.dumps({k:v for k,v in c.items() if k!='candidate_id'},ensure_ascii=False,sort_keys=True).encode()).hexdigest()[:20]


def choose(candidates):
    if not candidates: return None, 'no_birthplace_evidence', False
    known=[c for c in candidates if c['hemisphere'] in {'north','south','equator'}]
    if not known: return min(candidates,key=lambda c:rank(c['source_grade'])), 'unresolved_geography', any(c.get('birthplace_discrepancy_retained',False) for c in candidates)
    best=min(rank(c['source_grade']) for c in known)
    strong=[c for c in known if rank(c['source_grade'])==best]
    if len({c['hemisphere'] for c in strong})>1:
        return None,'same_tier_birthplace_hemisphere_conflict_hold',True
    hard={'explicit_geographical_rules_cross_hemispheres','explicit_alternatives_unresolved_or_cross_hemispheres','at_sea_or_route_is_not_a_birth_country'}
    if any(rank(c['source_grade'])<=best and c['hemisphere']=='unknown' and c.get('geography',{}).get('reason') in hard for c in candidates):
        return None,'strong_birthplace_alternatives_unresolved_hold',True
    selected=strong[0]
    discrepancy=any(c['hemisphere'] not in {'unknown',selected['hemisphere']} for c in known) or any(c.get('birthplace_discrepancy_retained') for c in candidates)
    return selected, ('higher_tier_birthplace_preferred_with_discrepancy_retained' if discrepancy else 'best_available_birthplace_evidence'), bool(discrepancy)


def assemble(study,output):
    repo=study.parents[1]
    v2=repo/'studies/royal_society_birthplace_completion_v2'
    basepath=v2/'outputs/uk_birthplace_rows.jsonl.gz'
    assert sha(basepath)=='739c0bf9ae48e61bd7a59378f186027c0cd87e9e248d1efc3ee0c8c8d9a5e773'
    oldrows=read(basepath); old={r['record_id']:r for r in oldrows}
    assert len(oldrows)==len(old)==4983
    ext=read(study/'inputs/geo_extent29.jsonl.gz');loc=read(study/'inputs/geo_localities46.jsonl.gz')
    geo75={r['record_id']:r for r in ext+loc}
    original75={r['record_id'] for r in oldrows if r['hemisphere']=='unknown' and r['birthplace_evidence_candidates']}
    assert len(ext)==29 and len(loc)==46 and len(geo75)==75 and set(geo75)==original75
    resolved={rid:r for rid,r in geo75.items() if r['hemisphere'] in {'north','south'}}
    assert Counter(r['hemisphere'] for r in resolved.values())=={'north':48,'south':2}
    facts=read(study/'inputs/new_official_birthplaces.jsonl.gz')+read(study/'inputs/new_wikipedia_birthplaces.jsonl.gz')
    geography=read(study/'inputs/new_fact_geography.jsonl.gz')
    # Candidate lookup uses source URL as well as ID because two routes can cover one person.
    geo={(r['record_id'],r['source_url']):r for r in geography}
    assert len(facts)==len(geo)==113
    wikiqa={r['record_id']:r for r in read(study/'audit/wiki_identity_review.jsonl.gz')}
    assert len(wikiqa)==93
    current_audit={r['record_id']:r for r in read(study/'inputs/current99_identity_audit.jsonl.gz')}
    assert len(current_audit)==99
    additions=defaultdict(list)
    for f in facts:
        rid=f['record_id'];b=old[rid]
        assert b['hemisphere']=='unknown' and not b['birthplace_evidence_candidates']
        assert f.get('dob',f.get('native_dob'))==b['dob']
        g=geo[(rid,f['source_url'])]
        assert g['raw_birthplace']==f['raw_birthplace']
        if f['source_grade']=='S3':
            qa=wikiqa[rid]
            assert qa['identity_status_for_geography']=='supported_named_subject', (rid,qa)
        c={'origin':'new_explicit_edited_memoir_or_ODNB' if f['source_grade']=='S2' else 'new_QID_bound_wikipedia_Born_or_body',
           'raw_birthplace':f['raw_birthplace'],'source_grade':f['source_grade'],
           'hemisphere':g['hemisphere'],'reason':g['basis'],
           'source_urls':f.get('source_urls') or [f['source_url']],
           'source_sha256':f.get('source_sha256',''),'evidence_quote':f.get('evidence_quote',''),
           'evidence_locator':f.get('evidence_locator',f.get('section_or_field_locator','')),
           'geography':g,'birthplace_fact_evidence':f,
           'birthplace_discrepancy_retained':bool(f.get('birthplace_discrepancy_retained')),
           'birthplace_source_grade_independent_of_DOB_grade':True}
        c['candidate_id']=candidate_id(c);additions[rid].append(c)
    rows=[];changes=[];quarantine=[]
    for rid,base in old.items():
        row=deepcopy(base);candidates=deepcopy(base['birthplace_evidence_candidates'])
        needs_reselect=rid in resolved or rid in additions
        if rid in resolved:
            review=resolved[rid]
            assert base['raw_birthplace']==review['raw_birthplace']
            locked_id=review.get('selected_evidence_candidate_id') or review.get('original_selected_candidate_id') or review.get('locked_selected_evidence_candidate_id')
            assert locked_id==base['selected_birthplace_evidence']['candidate_id']
            index=next(i for i,c in enumerate(candidates) if c['candidate_id']==locked_id)
            c=deepcopy(candidates[index])
            c['v2_evidence_before_geographic_resolution']=deepcopy(c)
            c['parent_candidate_id']=locked_id
            c['hemisphere']=review['hemisphere']
            c['reason']=review.get('geographic_basis',review.get('basis'))
            c['geography']={'hemisphere':review['hemisphere'],'reason':'reviewed_birthplace_extent_or_locality',
                            'geographic_resolution_source_grade':'S3','review':review,
                            'lat':None,'lon':None,'country_assigned':False}
            c['candidate_id']=candidate_id(c);candidates[index]=c
        if rid in additions:candidates.extend(additions[rid])
        if rid in current_audit:
            audit=current_audit[rid]
            status=audit['identity_status_for_geography_only']
            row['geography_lookup_identity_review']=audit
            row['active_geography_lookup_qid']=audit.get('active_geography_lookup_qid',audit.get('wikidata_canonical_qid') or base.get('lookup_qid',''))
            if status=='held_review_unknown':
                row['active_geography_lookup_qid']=''
                row['geography_lookup_identity_pending']=True
            if status.startswith('quarantined') or status in {'confirmed_mismatch_parent_verified','held_review_name_dob_conflict'}:
                invalid={c['candidate_id'] for c in audit['qid_derived_geography_candidates']}
                bad=[c for c in candidates if c['candidate_id'] in invalid]
                assert len(bad)==len(invalid),(rid,invalid)
                row['quarantined_birthplace_evidence_candidates']=bad
                row['active_geography_lookup_qid']=''
                row['geography_lookup_qid_quarantined']=True
                candidates=[c for c in candidates if c['candidate_id'] not in invalid]
                quarantine.extend({'record_id':rid,'candidate':c,'reason':'wrong_person_name_DOB_or_external_ID'} for c in bad)
                needs_reselect=True
        if needs_reselect:
            selected,decision,discrepancy=choose(candidates)
            sign=selected['hemisphere'] if selected and not decision.endswith('_hold') else 'unknown'
            row['v2_geography_before_this_overlay']={k:deepcopy(base.get(k)) for k in ['raw_birthplace','hemisphere','country','lat','lon','birthplace_source_grade','birthplace_source_urls','selected_birthplace_evidence','geography_decision']}
            row.update(hemisphere=sign,geography_decision=decision,
                birthplace_discrepancy_retained=discrepancy,birthplace_evidence_candidates=candidates,
                selected_birthplace_evidence=selected,raw_birthplace=selected['raw_birthplace'] if selected else '',
                country='',lat=None,lon=None,
                birthplace_source_grade=selected['source_grade'] if selected else 'unknown',
                birthplace_source_urls=selected['source_urls'] if selected else [],
                birthplace_source_url=' | '.join(selected['source_urls']) if selected else '',
                birthplace_evidence_kind=selected['origin'] if selected else 'unresolved',
                birthplace_claim_excerpt=selected.get('evidence_quote','') if selected else '',
                source_sha256=selected.get('source_sha256','') if selected else '',
                reason=selected.get('reason','') if selected else decision,
                northern_birthplace_candidate=sign=='north',southern_birthplace_separate=sign=='south',
                geographic_conflict_pending_review=decision.endswith('_hold'))
        # Every pre-existing field outside this explicit geography layer remains byte-equivalent as JSON values.
        geo_fields={'hemisphere','raw_birthplace','country','lat','lon','birthplace_source_grade','birthplace_source_urls','birthplace_source_url','birthplace_evidence_kind','birthplace_claim_excerpt','source_sha256','reason','northern_birthplace_candidate','southern_birthplace_separate','geographic_conflict_pending_review','geography_decision','birthplace_discrepancy_retained','birthplace_evidence_candidates','selected_birthplace_evidence'}
        assert all(row.get(k)==v for k,v in base.items() if k not in geo_fields),(rid,'nongeography mutation')
        assert row['dob']==base['dob']
        if row['hemisphere']!=base['hemisphere'] or needs_reselect:
            changes.append({'record_id':rid,'name':row['name'],'dob':row['dob'],
                'before_hemisphere':base['hemisphere'],'after_hemisphere':row['hemisphere'],
                'before_raw_birthplace':base['raw_birthplace'],'after_raw_birthplace':row['raw_birthplace'],
                'birthplace_source_grade':row['birthplace_source_grade'],
                'reason':row['geography_decision'],'invalid_QID_evidence_removed':bool(row.get('geography_lookup_qid_quarantined'))})
        rows.append(row)
    rows.sort(key=lambda r:r['record_id']);output.mkdir(parents=True,exist_ok=True)
    dump(output/'uk_birthplace_rows.jsonl.gz',rows);dump(output/'changes.jsonl.gz',changes)
    dump(output/'quarantined_candidates.jsonl.gz',quarantine)
    fields=['record_id','name','source_authorised_full_name','dob','raw_birthplace','hemisphere','birthplace_source_grade','birthplace_source_url','geography_decision','birthplace_discrepancy_retained','geography_lookup_qid_quarantined','active_geography_lookup_qid','northern_birthplace_candidate','final_analysis_eligibility_assigned']
    for fn,items in [('uk_birthplaces.csv',rows),('remaining_unknown.csv',[r for r in rows if r['hemisphere']=='unknown']),('changed_records.csv',changes)]:
        cols=list(changes[0]) if fn=='changed_records.csv' else fields
        with (output/fn).open('w',encoding='utf-8',newline='') as f:
            w=csv.DictWriter(f,fieldnames=cols,extrasaction='ignore');w.writeheader();w.writerows(items)
    counts=Counter(r['hemisphere'] for r in rows);prev=Counter(r['hemisphere'] for r in oldrows)
    unknown=[r for r in rows if r['hemisphere']=='unknown'];window=[r for r in rows if 1835<=int(r['dob'][:4])<=1985]
    assert len(window)==2644
    summary={'schema':'royal_society_birthplace_completion_v3','baseline':len(rows),
        'previous_counts':dict(prev),'hemisphere_counts':dict(counts),
        'hemisphere_net_change':{k:counts[k]-prev[k] for k in ['north','south','unknown']},
        'previous_unknown_newly_classified':sum(old[r['record_id']]['hemisphere']=='unknown' and r['hemisphere']!='unknown' for r in rows),
        'prior_known_reverted_to_unknown':sum(old[r['record_id']]['hemisphere']!='unknown' and r['hemisphere']=='unknown' for r in rows),
        'unknown_breakdown':{'no_active_explicit_birthplace_evidence':sum(not r['birthplace_evidence_candidates'] for r in unknown),
            'explicit_place_but_geography_unresolved':sum(bool(r['birthplace_evidence_candidates']) for r in unknown)},
        'existing75_review':{'reviewed':75,'resolved':50,'north':48,'south':2,'held':25},
        'new_birthplace_facts':{'official_or_edited_S2':20,'wikipedia_S3':93,'unique_people':len(additions),
            'route_overlap_people':sum(len(v)>1 for v in additions.values()),
            'unique_people_classified':sum(rowsign['hemisphere']!='unknown' for rowsign in rows if rowsign['record_id'] in additions)},
        'current99_identity_audit':dict(Counter(r['identity_status_for_geography_only'] for r in current_audit.values())),
        'quarantined_current_people':sum(bool(r.get('geography_lookup_qid_quarantined')) for r in rows),
        'quarantined_candidates':len(quarantine),
        'source_grade_counts_for_selected_geography':dict(Counter(r['birthplace_source_grade'] for r in rows)),
        'descriptive_existing_native_DOB_window_1835_1985':{'rows':len(window),'hemisphere_counts':dict(Counter(r['hemisphere'] for r in window)),'not_new_calendar_or_final_cohort_adjudication':True},
        'native_DOB_calendar_identity_eligibility_fields_preserved':True,
        'birth_window_changed':False,'source_quality_DOB_groups_unchanged':True,
        'cross_cohort_deduplicated':False,'final_cohort_frozen':False,
        'source_hash_scope':'Source evidence SHA identifies retrieved bytes or explicitly labelled tool excerpt captures. Full Wikipedia HTML/Crossref abstracts not included. Inputs are evidence projections with their own file hashes.',
        'inputs_sha256':{str(p.relative_to(repo)):sha(p) for p in [basepath]+sorted((study/'inputs').glob('*'))+list((study/'audit').glob('wiki_identity_review.jsonl.gz'))}}
    (output/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    with (v2/'outputs/all_country_birthplace_summary.csv').open() as f:globalrows=list(csv.DictReader(f))
    for r in globalrows:
        if r['cohort']=='UK_Royal_Society':
            for k in ['north','south','equator','unknown']:r[k]=counts[k]
            r['source_snapshot']='royal_society_birthplace_completion_v3'
    with (output/'all_country_birthplace_summary.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(globalrows[0]));w.writeheader();w.writerows(globalrows)
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--study',type=Path,default=Path(__file__).resolve().parents[1]);parser.add_argument('--output',type=Path)
    args=parser.parse_args();print(json.dumps(assemble(args.study,args.output or args.study/'outputs'),ensure_ascii=False))
