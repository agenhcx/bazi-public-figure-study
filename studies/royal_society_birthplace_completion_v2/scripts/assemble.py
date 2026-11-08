#!/usr/bin/env python3
"""Reconcile birthplace evidence only; preserve frozen Royal Society DOB rows."""
from __future__ import annotations
import argparse
from collections import Counter
import csv
import gzip
import hashlib
import json
from pathlib import Path
import sys


def read_rows(path):
    opener = gzip.open if str(path).endswith('.gz') else open
    with opener(path, 'rt', encoding='utf-8-sig') as stream:
        return [json.loads(line) for line in stream if line.strip()]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def grade_rank(grade):
    return {'S1': 0, 'S2': 1,
            'S1_or_S2_existing_body_metadata_not_reopened': 2,
            'S3': 3}.get(grade, 4)


def candidate(origin, raw, grade, sign, urls, reason='', **evidence):
    value = {'origin': origin, 'raw_birthplace': raw, 'source_grade': grade,
             'hemisphere': sign, 'source_urls': [u for u in urls if u],
             'reason': reason, **evidence}
    value['candidate_id'] = hashlib.sha256(json.dumps(value, ensure_ascii=False,
                                         sort_keys=True).encode()).hexdigest()[:20]
    return value


def choose(candidates):
    """Prefer explicit S1/S2 birthplace evidence; retain lower-tier differences."""
    if not candidates:
        return None, 'no_birthplace_evidence', False
    known = [c for c in candidates if c['hemisphere'] in {'north', 'south', 'equator'}]
    if not known:
        return min(candidates, key=lambda c: grade_rank(c['source_grade'])), 'unresolved_geography', False
    rank = min(grade_rank(c['source_grade']) for c in known)
    strongest = [c for c in known if grade_rank(c['source_grade']) == rank]
    if len({c['hemisphere'] for c in strongest}) > 1:
        return None, 'same_tier_birthplace_hemisphere_conflict_hold', True
    selected = strongest[0]
    # A high-tier field explicitly giving incompatible alternatives cannot be
    # made certain merely by choosing a lower-tier point.
    hard_reasons = {'explicit_geographical_rules_cross_hemispheres',
                    'explicit_alternatives_unresolved_or_cross_hemispheres',
                    'at_sea_or_route_is_not_a_birth_country'}
    if any(grade_rank(c['source_grade']) <= rank and c['hemisphere'] == 'unknown'
           and c.get('geography', {}).get('reason') in hard_reasons for c in candidates):
        return None, 'strong_birthplace_alternatives_unresolved_hold', True
    differs = any(c['hemisphere'] not in {'unknown', selected['hemisphere']} for c in known)
    return selected, ('higher_tier_birthplace_preferred_with_discrepancy_retained'
                      if differs else 'best_available_birthplace_evidence'), differs


def wd_candidate(row, origin, classify_p19):
    places = row.get('place_evidence', [])
    if not places:
        return None
    resolutions = [classify_p19(place) for place in places]
    signs = {r['hemisphere'] for r in resolutions}
    inventory = row.get('person_birthplace_statement_inventory', [])
    nonvalue = any(s.get('rank') != 'deprecated' and s.get('snaktype') != 'value'
                   for s in inventory)
    sign = next(iter(signs)) if len(signs) == 1 and 'unknown' not in signs and not nonvalue else 'unknown'
    return candidate(origin, row.get('raw_birthplace', ''), 'S3', sign,
                     row.get('birthplace_source_urls', []),
                     'all_active_P19_places_same_hemisphere' if sign != 'unknown'
                     else 'P19_places_missing_unresolved_or_cross_hemispheres',
                     qid=row.get('qid', ''), identity_link_provenance=row.get('identity_link_provenance'),
                     birthplace_claims=row.get('birthplace_claims', []),
                     place_resolutions=resolutions, evidence_record_id=row['record_id'])


def assemble(study, output, allow_partial=False):
    repo = study.parents[1]
    prior = repo / 'studies/academy_birthplace_screen_v1'
    old_rows = [r for r in read_rows(prior / 'outputs/birthplace_rows.jsonl.gz')
                if r['cohort'] == 'UK_Royal_Society']
    assert len(old_rows) == len({r['record_id'] for r in old_rows}) == 4983
    old = {r['record_id']: r for r in old_rows}
    sys.path.insert(0, str(study / 'geography'))
    from classify_birthplace import classify_place
    from wikidata_place_extent_adapter import classify_wikidata_place_evidence
    manual_path = study / 'inputs/manual_hemisphere_resolutions.json'
    manual = {r['record_id']: r for r in json.loads(manual_path.read_text())} if manual_path.exists() else {}
    official_path = study / 'inputs/official_birthplace_fields.jsonl.gz'
    current_path = study / 'inputs/current99_birthplace_rows.jsonl.gz'
    official_rows, current_rows = read_rows(official_path), read_rows(current_path)
    official = {r['record_id']: r for r in official_rows}
    current = {r['record_id']: r for r in current_rows}
    if not allow_partial:
        assert len(official) == len(official_rows) == 4884
    assert len(current) == len(current_rows) == 99
    for r in official_rows:
        assert r['record_id'] in old and r['record_id'].startswith('RS_PAST_')
        assert r['existing_dob'] == old[r['record_id']]['dob']
    for r in current_rows:
        assert r['record_id'] in old and r['record_id'].startswith('RS_CURRENT_')
        assert r['dob'] == old[r['record_id']]['dob']
    prior_wd = {r['record_id']: r for r in read_rows(prior / 'inputs/supplements/main.jsonl.gz')
                if r['cohort'] == 'UK_Royal_Society'}
    strict_path = study / 'inputs/strict_link_birthplace_rows.jsonl.gz'
    strict = {r['record_id']: r for r in read_rows(strict_path)} if strict_path.exists() else {}
    assert set(strict) <= set(old)
    rows = []
    for rid, base in old.items():
        evidence = []
        op, cp = official.get(rid), current.get(rid)
        if op and op.get('raw_placeofbirth') and op.get('parse_status') == 'explicit_birthplace_field':
            geo = classify_place(op['raw_placeofbirth'])
            if rid in manual:
                reviewed = manual[rid]
                assert op['raw_placeofbirth'] == reviewed['raw_placeofbirth']
                assert op['source_sha256'] == reviewed['source_sha256']
                geo = {'hemisphere': reviewed['hemisphere'],
                       'reason': 'reviewed_alternatives_with_common_explicit_northern_extent',
                       'manual_review': reviewed, 'machine_annotation_retained': geo,
                       'place_alternatives_retained': True, 'lat': None, 'lon': None}
            evidence.append(candidate('official_catalogue_Place_of_birth', op['raw_placeofbirth'], 'S1',
                geo['hemisphere'], [op['source_url']], geo['reason'], geography=geo,
                source_sha256=op['source_sha256'], retrieved_utc=op['retrieved_utc'],
                field_locator=op['birthplace_field_locator']))
        if cp and cp.get('raw_birthplace'):
            geo = classify_place(cp['raw_birthplace'])
            evidence.append(candidate('current_institutional_or_edited_body', cp['raw_birthplace'],
                cp.get('birthplace_source_grade', 'unknown'), geo['hemisphere'],
                [cp['source_url']], geo['reason'], geography=geo,
                source_sha256=cp.get('source_sha256', ''), evidence_quote=cp.get('evidence_quote', ''),
                body_read_this_round=cp.get('body_read_this_round', False)))
        addendum = base.get('birthplace_body_addendum')
        if addendum:
            geo = classify_place(addendum['raw_birthplace'])
            evidence.append(candidate('prior_explicit_body_addendum', addendum['raw_birthplace'],
                addendum['birthplace_source_grade'], geo['hemisphere'],
                [addendum['birthplace_source_url']], geo['reason'], geography=geo,
                evidence_quote=addendum.get('evidence_quote', ''),
                source_sha256=addendum.get('source_sha256', '')))
        if base.get('hemisphere') in {'north', 'south', 'equator'}:
            urls = base.get('birthplace_source_urls', []) or [base.get('birthplace_source_url', '')]
            evidence.append(candidate('prior_selected_geography', base.get('raw_birthplace', ''),
                base.get('birthplace_source_grade', 'unknown'), base['hemisphere'], urls,
                base.get('reason', ''), prior_evidence_file='academy_birthplace_screen_v1'))
        for source, origin in [(prior_wd.get(rid), 'prior_P19_evidence'),
                               (strict.get(rid), 'new_strict_membership_name_DOB_P19_lookup')]:
            if source:
                assert source.get('dob', '') == base['dob']
                extra = wd_candidate(source, origin, classify_wikidata_place_evidence)
                if extra:
                    evidence.append(extra)
        selected, decision, discrepancy = choose(evidence)
        sign = selected['hemisphere'] if selected and decision not in {
            'same_tier_birthplace_hemisphere_conflict_hold',
            'strong_birthplace_alternatives_unresolved_hold'} else 'unknown'
        row = dict(base)
        row['prior_geography_selected_fields'] = {k: base.get(k) for k in [
            'raw_birthplace', 'hemisphere', 'country', 'lat', 'lon',
            'birthplace_source_grade', 'birthplace_source_url', 'birthplace_source_urls',
            'reason', 'birthplace_evidence_kind', 'source_sha256']}
        row.update(prior_hemisphere=base['hemisphere'], hemisphere=sign,
                   geography_decision=decision, birthplace_discrepancy_retained=discrepancy,
                   birthplace_evidence_candidates=evidence,
                   selected_birthplace_evidence=selected,
                   source_authorised_full_name=op.get('authorised_form_of_name', '') if op else '',
                   official_birthplace_field_status=op.get('parse_status', 'not_attempted') if op else 'not_past_catalogue_record',
                   raw_birthplace=selected['raw_birthplace'] if selected else '',
                   country='',
                   birthplace_source_grade=selected['source_grade'] if selected else 'unknown',
                   birthplace_source_url=' | '.join(selected['source_urls']) if selected else '',
                   birthplace_source_urls=selected['source_urls'] if selected else [],
                   birthplace_evidence_kind=selected['origin'] if selected else 'unresolved',
                   birthplace_claim_excerpt=selected.get('evidence_quote', '') if selected else '',
                   source_sha256=selected.get('source_sha256', '') if selected else '',
                   reason=selected.get('reason', '') if selected else decision,
                   northern_birthplace_candidate=sign == 'north',
                   southern_birthplace_separate=sign == 'south',
                   geographic_conflict_pending_review=decision.endswith('_hold'),
                   final_analysis_eligibility_assigned=False,
                   DOB_or_native_acceptance_modified=False)
        # Do not carry a prior point into a different newly selected place.
        row['lat'], row['lon'] = None, None
        for field in ['dob', 'dob_status', 'accepted_gregorian_dob', 'dob_claim_values', 'baseline_kind']:
            assert row.get(field) == base.get(field)
        rows.append(row)
    rows.sort(key=lambda r: r['record_id'])
    output.mkdir(parents=True, exist_ok=True)
    (output / 'uk_birthplace_rows.jsonl.gz').write_bytes(gzip.compress(
        ''.join(json.dumps(r, ensure_ascii=False, sort_keys=True) + '\n' for r in rows).encode(), mtime=0))
    fields = ['record_id', 'name', 'source_authorised_full_name', 'dob', 'raw_birthplace',
              'hemisphere', 'birthplace_source_grade', 'birthplace_source_url',
              'official_birthplace_field_status', 'geography_decision',
              'birthplace_discrepancy_retained', 'geographic_conflict_pending_review',
              'prior_hemisphere', 'northern_birthplace_candidate', 'final_analysis_eligibility_assigned']
    for filename, selected_rows in [('uk_birthplaces.csv', rows),
                                     ('remaining_unknown.csv', [r for r in rows if r['hemisphere'] == 'unknown'])]:
        with (output / filename).open('w', encoding='utf-8', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=fields, extrasaction='ignore')
            writer.writeheader(); writer.writerows(selected_rows)
    signs = Counter(r['hemisphere'] for r in rows)
    summary = {'schema': 'royal_society_birthplace_completion_v2', 'baseline': 4983,
               'hemisphere_counts': dict(signs), 'previous_counts': dict(Counter(r['hemisphere'] for r in old_rows)),
               'official_catalogue_rows_processed': len(official),
               'official_catalogue_nonempty_birthplace': sum(bool(r.get('raw_placeofbirth')) for r in official_rows),
               'official_catalogue_errors': sum(bool(r.get('error')) for r in official_rows),
               'current99_explicit_birthplace': sum(bool(r.get('raw_birthplace')) for r in current_rows),
               'strict_lookup_rows': len(strict), 'partial_official_preview': allow_partial,
               'manual_hemisphere_resolutions': len(manual),
               'source_grade_counts_for_selected_geography': dict(Counter(r['birthplace_source_grade'] for r in rows)),
               'native_DOB_and_eligibility_preserved': True, 'cross_cohort_deduplicated': False,
               'birth_window_changed': False, 'source_quality_DOB_groups_unchanged': True,
               'geography_source_preference': 'S1, S2, existing verified-body metadata, S3; equal-tier cross-hemisphere claims held; all weaker discrepancies retained',
               'inputs_sha256': {str(p.relative_to(repo)): digest(p) for p in
                    [official_path, current_path, prior / 'outputs/birthplace_rows.jsonl.gz',
                     prior / 'inputs/supplements/main.jsonl.gz']
                    + ([strict_path] if strict_path.exists() else [])
                    + ([manual_path] if manual_path.exists() else [])}}
    assert sum(signs.values()) == 4983
    window = [r for r in rows if 1835 <= int(r['dob'][:4]) <= 1985]
    assert len(window) == 2644
    summary['descriptive_existing_native_DOB_window_1835_1985'] = {
        'rows': len(window), 'hemisphere_counts': dict(Counter(r['hemisphere'] for r in window)),
        'not_new_calendar_or_final_cohort_adjudication': True}
    unresolved = [r for r in rows if r['hemisphere'] == 'unknown']
    summary['unknown_breakdown'] = {
        'no_explicit_birthplace_evidence': sum(not r['birthplace_evidence_candidates'] for r in unresolved),
        'explicit_place_but_geography_unresolved': sum(bool(r['birthplace_evidence_candidates']) for r in unresolved),
        'confirmed_cross_hemisphere_conflicts': sum(
            r['geography_decision'] == 'same_tier_birthplace_hemisphere_conflict_hold' for r in unresolved)}
    (output / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
    global_rows = []
    for original in json.loads((prior / 'outputs/summary.json').read_text())['by_cohort']:
        value = dict(original)
        if value['cohort'] == 'UK_Royal_Society':
            for key in ['north', 'south', 'equator', 'unknown']:
                value[key] = signs[key]
            value['source_snapshot'] = 'royal_society_birthplace_completion_v2'
        else:
            value['source_snapshot'] = 'academy_birthplace_screen_v1_unchanged'
        global_rows.append(value)
    with (output / 'all_country_birthplace_summary.csv').open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=['cohort', 'baseline_rows', 'north', 'south',
            'equator', 'unknown', 'source_snapshot'], extrasaction='ignore')
        writer.writeheader(); writer.writerows(global_rows)
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--study', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output', type=Path)
    parser.add_argument('--allow-partial', action='store_true')
    args = parser.parse_args()
    print(json.dumps(assemble(args.study, args.output or args.study / 'outputs', args.allow_partial), ensure_ascii=False))
