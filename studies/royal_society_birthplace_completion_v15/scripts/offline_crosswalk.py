#!/usr/bin/env python3
"""Portable read-only exact-date evidence-reuse screen; no network or master writes.

Dependency: supply the original comprehensive v7 gzip separately. It is not
bundled, and its required SHA256 is enforced before screening. The targets
snapshot can be bundled as inputs/offline_screen_targets.json.

Example (one line):
python v15_offline_crosswalk_portable.py --pool comprehensive_v7.jsonl.gz --targets inputs/offline_screen_targets.json --output audit/offline_crosswalk_rerun.json

This reruns only the core frozen-table crosswalk. It produces evidence-review
candidates, never accepted full-name expansions, birthplaces or hemisphere
assignments. Later manual cached-source observations in the original audit JSON
are not recreated by this script. Paths and audit-write time naturally differ.
"""
from pathlib import Path
from datetime import date, datetime, timezone
from collections import Counter, defaultdict
import argparse
import gzip
import hashlib
import json
import re
import unicodedata

EXPECTED = 'dabb1fd38354953eb9ef4b3a6b23f98e3c5520d55f8430b04287252d5c91e158'
HONOR = {'sir', 'prof', 'professor', 'dr', 'doctor', 'dame', 'lord', 'baron',
         'baroness', 'captain', 'mr', 'mrs', 'miss', 'the', 'rev', 'reverend',
         'hon', 'honorary', 'emeritus', 'professeur', 'baronet'}

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def canonical_sha(obj):
    return sha(json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode())

def tokens(s):
    s = unicodedata.normalize('NFKD', s).casefold()
    s = ''.join(c for c in s if not unicodedata.combining(c))
    s = s.replace("'", '').replace('’', '')
    return [x for x in re.findall(r'[^\W\d_]+', s, flags=re.U) if x not in HONOR]

def authority_name(row):
    raw = row.get('source_authorised_full_name', '')
    if not raw:
        return row['name'], 'current native full name'
    parts = raw.split(';')
    surname = parts[0].strip()
    givens = []
    for part in parts[1:]:
        before = part.split('(')[0].strip()
        if tokens(before):
            givens.append(before)
        if re.search(r'\d{4}', part):
            break
    return ' '.join([*givens, surname]), 'stored UK authority surname/givens; raw string retained'

def source_tokens(row):
    return tokens(re.sub(r'\([^)]*\)', ' ', row['name']))

def exact_day(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        return False
    try:
        date.fromisoformat(value)
        return True
    except ValueError:
        return False

def initial_compatible(uk, source):
    """Every observed given component must pair exactly or by a real initial.

    Neither omitted middle names nor a surname/initial alone can produce a strong match.
    """
    full, _ = authority_name(uk)
    ut, st = tokens(full), source_tokens(source)
    authority = uk.get('source_authorised_full_name', '')
    surname = tokens(authority.split(';')[0]) if authority else ut[-1:]
    urem, srem = ut[:], st[:]
    for part in surname:
        if part not in urem or part not in srem:
            return False
        urem.remove(part)
        srem.remove(part)
    if len(urem) != len(srem) or not urem:
        return False
    # Exact components pair first; remaining single-letter matches are only leads.
    for part in urem[:]:
        if part in srem:
            urem.remove(part)
            srem.remove(part)
    if not urem:
        return True
    for part in urem:
        possible = [x for x in srem if len(x) == 1 and x == part[0]
                    or len(part) == 1 and x.startswith(part)]
        if not possible:
            return False
        srem.remove(possible[0])
    return not srem

def source_refs(row):
    return {key: value for key, value in row.items()
            if any(w in key.lower() for w in ['source', 'evidence', 'lookup', 'claim', 'geograph', 'archive', 'input'])}

def main():
    parser = argparse.ArgumentParser(
        description='Screen a separately supplied hash-locked v7 pool against a frozen targets snapshot; evidence candidates only, no network or master mutation.')
    parser.add_argument('--pool', required=True, type=Path,
                        help='Original comprehensive v7 gzip, supplied separately; required SHA256: ' + EXPECTED)
    parser.add_argument('--targets', required=True, type=Path,
                        help='Frozen targets JSON snapshot (e.g. inputs/offline_screen_targets.json)')
    parser.add_argument('--output', required=True, type=Path,
                        help='Destination JSON for the core rerun audit; must differ from both inputs')
    args = parser.parse_args()
    pool_path = args.pool.expanduser().resolve()
    targets_path = args.targets.expanduser().resolve()
    output_path = args.output.expanduser().resolve()
    if output_path in {pool_path, targets_path}:
        parser.error('--output must not overwrite --pool or --targets')
    raw = pool_path.read_bytes()
    if sha(raw) != EXPECTED:
        raise ValueError('The supplied --pool does not match the required frozen comprehensive v7 SHA256: ' + EXPECTED)
    rows = [json.loads(line) for line in gzip.decompress(raw).splitlines()]
    targets = json.loads(targets_path.read_text(encoding='utf-8'))
    assert len(rows) == 11094 and len(targets) == 169
    assert len({(r['cohort'], r['record_id']) for r in rows}) == 11094
    uk_all = [r for r in rows if r['cohort'] == 'UK_Royal_Society']
    assert len(uk_all) == 4983
    other = [r for r in rows if r['cohort'] != 'UK_Royal_Society']
    eligible = [r for r in other if exact_day(r.get('dob')) and bool(r.get('raw_birthplace'))]
    by_date, all_by_cohort, all_by_name = defaultdict(list), defaultdict(list), defaultdict(list)
    for row in other:
        all_by_cohort[row['cohort']].append(row)
        all_by_name[tuple(sorted(source_tokens(row)))].append(row)
    for row in eligible:
        by_date[row['dob']].append(row)
    coverage, strong, leads, date_holds = [], [], [], []
    for target in targets:
        assert target['hemisphere'] == 'unknown' and not target.get('raw_birthplace')
        assert exact_day(target['dob']) and '1835' <= target['dob'][:4] <= '1985'
        name, method = authority_name(target)
        tt = tokens(name)
        matches, initial = [], []
        dated = by_date[target['dob']]
        for source in dated:
            exact = Counter(tt) == Counter(source_tokens(source))
            compat = exact or initial_compatible(target, source)
            if not compat:
                continue
            cohort_rows = all_by_cohort[source['cohort']]
            exact_uk = [r for r in uk_all if r.get('dob') == target['dob'] and
                        Counter(tokens(authority_name(r)[0])) == Counter(tt)]
            exact_source = [r for r in cohort_rows if r.get('dob') == source['dob'] and
                            Counter(source_tokens(r)) == Counter(source_tokens(source))]
            compatible_uk = [r for r in uk_all if r.get('dob') == target['dob'] and initial_compatible(r, source)]
            compatible_sources = [r for r in cohort_rows if r.get('dob') == source['dob'] and initial_compatible(target, r)]
            entry = {
                'target_record_id': target['record_id'],
                'target_authority_name': target.get('source_authorised_full_name'),
                'target_comparison_full_name': name,
                'target_name_tokens': tt,
                'target_native_dob': target['dob'],
                'target_complete_object_sha256': canonical_sha(target),
                'source_cohort': source['cohort'], 'source_record_id': source['record_id'],
                'source_name_tokens': source_tokens(source),
                'native_exact_day_equal': target['dob'] == source['dob'],
                'complete_name_tokens_equal': exact,
                'initial_only_compatible_lead': not exact,
                'bidirectional_uniqueness': {
                    'all_4983_UK_exact_name_date_count': len(exact_uk),
                    'whole_source_cohort_exact_source_name_date_count': len(exact_source),
                    'all_4983_UK_initial_compatible_date_count': len(compatible_uk),
                    'whole_source_cohort_initial_compatible_date_count': len(compatible_sources),
                    'source_cohort_row_count_including_no_birthplace_rows': len(cohort_rows)},
                'source_grade': source.get('birthplace_source_grade'),
                'stored_raw_birthplace': source.get('raw_birthplace'),
                'original_target_object': target,
                'original_source_object': source,
                'source_provenance_and_claim_fields': source_refs(source),
                'source_coordinates_are_reference_geography_not_person_birthpoint': True,
                'source_geography_not_blindly_copied': True,
                'cohort_rows_not_merged_or_statistically_deduplicated': True,
                'new_acceptance': False,
                'disposition': 'full_name_exact_day_candidate_needs_source_QA' if exact else 'initial_compatible_exact_day_lead_not_accepted'}
            if exact:
                strong.append(entry); matches.append(source['cohort'] + ':' + source['record_id'])
            else:
                leads.append(entry); initial.append(source['cohort'] + ':' + source['record_id'])
        differing = [r for r in all_by_name[tuple(sorted(tt))]
                     if exact_day(r.get('dob')) and r['dob'] != target['dob']]
        for source in differing:
            date_holds.append({'target_record_id': target['record_id'], 'target_full_name': name,
                               'target_native_dob': target['dob'], 'source_cohort': source['cohort'],
                               'source_record_id': source['record_id'], 'source_name': source['name'],
                               'source_native_dob': source['dob'], 'disposition': 'same_full_name_different_date_not_bound',
                               'native_date_not_corrected': True})
        coverage.append({'record_id': target['record_id'], 'source_authorised_full_name': target.get('source_authorised_full_name'),
                         'comparison_full_name': name, 'comparison_method': method,
                         'native_dob': target['dob'], 'target_complete_object_sha256': canonical_sha(target),
                         'eligible_other_cohort_exact_date_rows_screened': len(dated),
                         'exact_full_name_date_candidate_ids': matches,
                         'initial_compatible_date_lead_ids': initial,
                         'same_full_name_different_date_holds': len(differing),
                         'disposition': 'exact_candidate_needs_QA' if matches else 'initial_lead_only' if initial else 'no_eligible_name_and_exact_day_candidate_in_frozen_pool'})
    out = {'schema': 'UK_v15_offline_crosscohort_evidence_screen_v1',
           'audit_written_utc': datetime.now(timezone.utc).isoformat(),
           'no_new_network_requests': True, 'no_master_mutation': True,
           'rerun_scope': 'Core frozen-table crosswalk only; later manual cached-source review is not recreated. Candidate evidence is not full-name or birthplace adoption.',
           'external_pool_dependency': 'Original comprehensive v7 gzip must be supplied separately; not bundled.',
           'not_crosscohort_statistical_deduplication': True,
           'input_locks': {'comprehensive_v7_path': str(pool_path), 'comprehensive_v7_sha256': sha(raw),
                           'targets_path': str(targets_path), 'targets_sha256': sha(targets_path.read_bytes()),
                           'comprehensive_records': len(rows), 'UK_records_in_fixed_pool': len(uk_all),
                           'other_cohort_rows': len(other), 'eligible_exact_day_with_stored_birthplace': len(eligible)},
           'normalization': {'comparison_only': True, 'raw_fields_retained': True,
                             'known_honorific_tokens': sorted(HONOR),
                             'unicode': 'NFKD/casefold/combining-mark removal; apostrophe joining; punctuation token split',
                             'strong': 'exact native day plus entire name-token multiset equality; no initial expansion or dropped full components',
                             'initial_lead': 'exact native day plus fully paired observed components using explicit initials; not automatic acceptance',
                             'no_transliteration_or_person_alias_invented': True},
           'pool_diagnostics': {'rows_by_cohort': dict(Counter(r['cohort'] for r in other)),
                                'eligible_by_cohort': dict(Counter(r['cohort'] for r in eligible)),
                                'excluded_no_exact_day': sum(not exact_day(r.get('dob')) for r in other),
                                'exact_day_but_blank_stored_birthplace': sum(exact_day(r.get('dob')) and not r.get('raw_birthplace') for r in other)},
           'summary': {'target_rows_screened': len(coverage), 'full_token_exact_day_candidates': len(strong),
                       'initial_compatible_exact_day_leads': len(leads), 'date_disagreement_holds': len(date_holds),
                       'accepted_birthplace_observations': 0,
                       'coverage_dispositions': dict(Counter(x['disposition'] for x in coverage))},
           'coverage': coverage, 'exact_candidates': strong, 'initial_leads': leads,
           'same_full_name_different_date_holds': date_holds,
           'limitations': ['The frozen pool has incomplete cohort coverage and incomplete birthplaces; no match is not absence of a biography or evidence elsewhere.',
                           'Source S3 person-place links require positive independent identity support, not simply a copied QID or stored hemisphere.',
                           'Source original point coordinates, if present in retained source objects, are evidence snapshots only and must not be assigned as new UK personal birthpoint coordinates.',
                           'CAS and Nobel native-DOB blanks remain blank and are excluded; no date is inferred across cohorts.',
                           'All original birthday grades, identity, calendars, cohort keys and eligibility remain frozen.']}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(out['summary'], ensure_ascii=False))

if __name__ == '__main__':
    main()
