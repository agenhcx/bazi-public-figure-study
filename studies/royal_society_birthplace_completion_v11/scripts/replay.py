#!/usr/bin/env python3
"""Replay a bounded geographic-context supplement to the exact UK v10 master."""
import copy
import csv
import gzip
import hashlib
import io
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_BASE = 'e44f6dc02cc0cafece9b792164f016da0f08de5736ac62442d176d45b19a5799'
ALLOWED_CHANGED = {'hemisphere', 'geo_resolution_status', 'geography_decision',
                   'reason', 'northern_birthplace_candidate', 'southern_birthplace_separate',
                   'birthplace_followup_v11'}

def encode_gzip(rows):
    data = ''.join(json.dumps(r, ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n' for r in rows).encode()
    return gzip.compress(data, compresslevel=9, mtime=0)

def in_window(row):
    return '1835' <= row.get('dob', '')[:4] <= '1985'

def main():
    base_path = ROOT / 'inputs' / 'uk_birthplace_rows_v10.jsonl.gz'
    raw = base_path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == EXPECTED_BASE
    baseline = [json.loads(line) for line in gzip.decompress(raw).splitlines()]
    assert len(baseline) == 4983
    ids = [r['record_id'] for r in baseline]
    assert len(set(ids)) == len(ids)
    assert Counter(r['hemisphere'] for r in baseline) == {'north': 4155, 'south': 183, 'unknown': 645}
    facts = json.loads((ROOT / 'inputs' / 'accepted_context.json').read_text())
    by_id = {f['record_id']: f for f in facts}
    assert len(by_id) == len(facts) == 3
    updated, changes = [], []
    for before in baseline:
        after = copy.deepcopy(before)
        fact = by_id.get(before['record_id'])
        if fact:
            assert before['hemisphere'] == 'unknown'
            assert before['dob'] == fact['native_dob']
            assert before['source_authorised_full_name'] == fact['authority_name']
            assert fact['reviewed_hemisphere'] == 'north'
            assert before['raw_birthplace']
            after.update(hemisphere='north', geo_resolution_status='resolved_by_v11_explicit_region_context',
                         geography_decision='v11_explicit_birthplace_region_context',
                         reason='explicit_birthplace_context_wholly_northern_region',
                         northern_birthplace_candidate=True, southern_birthplace_separate=False,
                         birthplace_followup_v11=fact)
            changes.append({'record_id': before['record_id'], 'native_name': before['name'],
                            'dob': before['dob'], 'prior_raw_birthplace': before['raw_birthplace'],
                            'before_hemisphere': before['hemisphere'], 'after_hemisphere': 'north',
                            'qualified_context': fact['qualified_context'],
                            'new_context_source_grade': fact['source_grade'],
                            'source_url': fact['source_url']})
        for key in before:
            if key not in ALLOWED_CHANGED:
                assert after[key] == before[key], (before['record_id'], key)
        if not fact:
            assert before == after
        updated.append(after)
    assert [r['record_id'] for r in updated] == ids
    assert len(changes) == 3
    overall = dict(Counter(r['hemisphere'] for r in updated))
    window = [r for r in updated if in_window(r)]
    window_counts = dict(Counter(r['hemisphere'] for r in window))
    assert overall == {'north': 4158, 'south': 183, 'unknown': 642}
    assert len(window) == 2644
    assert window_counts == {'north': 2258, 'south': 178, 'unknown': 208}
    summary = {'schema': 'royal_society_birthplace_completion_v11',
               'baseline_sha256': EXPECTED_BASE, 'baseline_commit': '557e228fe61222bb57440204b7902cfc398b200f',
               'records': len(updated), 'counting_unit': 'fixed UK cohort records',
               'reviewed_records': 12, 'newly_classified': 3,
               'new_explicit_region_context_observations': 3,
               'new_first_birthplace_records': 0,
               'new_context_source_grades': {'S1': 1, 'S2': 2},
               'overall': overall, 'native_dob_window': '1835-1985 inclusive',
               'native_dob_window_records': len(window), 'native_dob_window_counts': window_counts,
               'unchanged_complete_rows': 4980, 'native_fields_and_prior_evidence_preserved': True,
               'original_birthplace_and_DOB_source_grades_preserved': True,
               'holds': {'no_new_qualifier_or_unavailable': 7,
                         'new_birthplace_conflict': 1, 'potential_DOB_conflict_pending_original_page': 1},
               'other_cohorts_modified': False, 'country_or_personal_coordinates_assigned': False,
               'DOB_calendar_identity_eligibility_modified': False,
               'cross_cohort_deduplication': False, 'BaZi_or_outcomes': False, 'final_cohort_freeze': False,
               'recovery_note': 'UK independently recovered from Git; comprehensive v8 NAS/DE increments not reconstructed.'}
    out = ROOT / 'outputs'
    out.mkdir(exist_ok=True)
    (out / 'birthplace_rows.jsonl.gz').write_bytes(encode_gzip(updated))
    (out / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
    (out / 'changes.json').write_text(json.dumps(changes, ensure_ascii=False, indent=2) + '\n')
    fields = ['record_id', 'name', 'dob', 'raw_birthplace', 'hemisphere', 'birthplace_source_grade', 'qualified_context', 'context_source_grade', 'context_source_url']
    for filename, rows in [('birthplaces.csv', updated), ('remaining_unknown_window.csv', [r for r in window if r['hemisphere'] == 'unknown'])]:
        buf = io.StringIO(newline='')
        writer = csv.DictWriter(buf, fieldnames=fields, lineterminator='\n')
        writer.writeheader()
        for row in rows:
            f = row.get('birthplace_followup_v11', {})
            v = {k: row.get(k, '') for k in fields}
            v.update(qualified_context=f.get('qualified_context', ''), context_source_grade=f.get('source_grade', ''), context_source_url=f.get('source_url', ''))
            writer.writerow(v)
        (out / filename).write_text(buf.getvalue())
    print(json.dumps(summary, ensure_ascii=False))

if __name__ == '__main__':
    main()
