#!/usr/bin/env python3
"""Audit followup coverage of the frozen v29 blank-place queue after replay."""
import gzip
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(path):
    return json.loads(path.read_text())

def record_ids(value):
    found = set()
    if isinstance(value, dict):
        if value.get('record_id'):
            found.add(value['record_id'])
        for child in value.values():
            found.update(record_ids(child))
    elif isinstance(value, list):
        for child in value:
            found.update(record_ids(child))
    return found

def main():
    starting = read(ROOT/'inputs/target_ids.json')
    reviewed = read(ROOT/'inputs/reviewed_record_ids.json')
    facts = read(ROOT/'inputs/accepted_birthplaces.json')
    holds = read(ROOT/'audit/followup_holds.json')
    inherited_files = sorted(p for p in (ROOT/'audit').glob('*holds.json') if p.name != 'followup_holds.json')
    inherited = set().union(*(record_ids(read(p)) for p in inherited_files))
    current_held = record_ids(holds)
    adopted = record_ids(facts)
    assert len(starting) == len(set(starting)) == 112
    assert len(reviewed) == len(set(reviewed)) == 18
    assert len(facts) == len(adopted) == 9 and len(holds) == len(current_held) == 9
    assert not adopted & current_held and adopted | current_held == set(reviewed)
    before_never = [rid for rid in starting if rid not in inherited]
    assert set(before_never) == set(reviewed)
    remaining = []
    digest = hashlib.sha256()
    with gzip.open(ROOT/'outputs/birthplace_rows.jsonl.gz', 'rb') as stream:
        for line in stream:
            digest.update(line)
            row = json.loads(line)
            if '1835-01-01' <= row['dob'] <= '1985-12-31' and row['hemisphere'] == 'unknown' and not row.get('raw_birthplace'):
                remaining.append(row['record_id'])
    assert len(remaining) == len(set(remaining)) == 103
    assert set(remaining) == set(starting) - adopted
    after_never = [rid for rid in remaining if rid not in inherited | current_held]
    assert not after_never
    summary = read(ROOT/'outputs/summary.json')
    report = {
        'schema': 'royal_society_v29_first_pass_queue_closeout',
        'counting_unit': 'fixed UK cohort record IDs, not deduplicated independent people',
        'scope': 'native DOB1835-1985 inclusive; unknown hemisphere and blank birthplace',
        'baseline_v28_canonical_jsonl_sha256': summary['baseline_v28_canonical_jsonl_sha256'],
        'current_canonical_jsonl_sha256': digest.hexdigest(),
        'starting_blank_records': len(starting),
        'starting_already_held_records': len(set(starting) & inherited),
        'starting_never_individually_reviewed_records': len(before_never),
        'newly_reviewed_records': len(reviewed),
        'newly_adopted_birthplaces': len(adopted),
        'newly_held_records': len(current_held),
        'remaining_blank_records': len(remaining),
        'remaining_blank_records_with_inherited_or_current_followup_hold': len(set(remaining) & (inherited | current_held)),
        'remaining_never_individually_reviewed_records': len(after_never),
        'first_pass_queue_complete': True,
        'birthplace_coverage_complete': False,
        'source_exhaustion_or_final_freeze_claimed': False,
        'starting_blank_record_ids': starting,
        'previously_never_reviewed_record_ids': before_never,
        'newly_reviewed_record_ids': reviewed,
        'newly_adopted_record_ids': sorted(adopted),
        'newly_held_record_ids': sorted(current_held),
        'remaining_blank_record_ids': remaining,
        'remaining_never_reviewed_record_ids': after_never,
        'inherited_hold_audits': [p.name for p in inherited_files],
        'input_file_sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in [ROOT/'inputs/target_ids.json', ROOT/'inputs/reviewed_record_ids.json', ROOT/'inputs/accepted_birthplaces.json', ROOT/'audit/followup_holds.json']},
    }
    destination = ROOT/'audit/first_pass_queue_closeout.json'
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({k: v for k, v in report.items() if isinstance(v, (int, bool))}))

if __name__ == '__main__':
    main()
