"""Independent V36–V44 canonical-method queue closeout from small audits and streamed rows.

Preparation is inert. Call run(data_ready=True) only after root confirms final V44
production data are ready. No replay module, production CLI, network or Git is used;
the only write is the separate scratch closeout artifact.
"""
from __future__ import annotations

import collections
import datetime
import gzip
import hashlib
import itertools
import json
from pathlib import Path
import uuid


WORKSPACE = Path('/workspace/scratch/262552d8c0f0')
BASE_METHOD_SHA256 = 'b76b7ad55125b1cf2dffe7d847d013f7fb8c2a6c8868c66f1e3060efae471147'
BASE_CANONICAL_SHA256 = 'a0c04e44631478f82e562deab64d699fc273e6fc99fa35ba23f8a61d7e1f8717'
CURRENT_SCOPE_SHA256 = '3575db7b377008a55d4c6876c23ce6b6f67fc8b50dce40b7dddc01fcf8523e65'
SCOPE_FILES = [
    'method_application_scope.json',
    *[f'method_application_scope_v{version}.json' for version in range(38, 45)],
]
ISSUE_FILES = [
    'active_source_DOB_conflicts.json', 'birthplace_source_conflicts.json',
    'source_derived_age_inconsistencies.json', 'provisional_parsed_date_discrepancies.json',
    'lifespan_endpoint_discrepancies.json', 'cross_source_reported_age_contrasts.json',
    'source_date_precision_holds.json', 'omitted_middle_name_admission.json',
    'source_ordinal_age_wording_observations.json',
]
HISTORICAL_QUEUE_FILES = [
    'prior_v29_first_pass_queue_closeout.json',
    'prior_v35_geography_first_pass_queue_closeout.json',
]
INDIVIDUAL_PLACE_HOLDS = {
    'RS_PAST_NA9209': 'prior_v11_holds.json',
    'RS_PAST_NA8779': 'prior_v12_holds.json',
}


def read_json(path):
    return json.loads(path.read_text())


def file_sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for chunk in iter(lambda: source.read(1048576), b''):
            digest.update(chunk)
    return digest.hexdigest()


def records(value):
    if isinstance(value, list):
        return value
    if isinstance(value, dict) and isinstance(value.get('records'), list):
        return value['records']
    raise AssertionError('Expected a record list or an object containing records')


def targeted_record(value, record_id):
    """Locate a single existing individual hold without loading historical masters."""
    if isinstance(value, dict):
        if value.get('record_id') == record_id:
            return value
        for child in value.values():
            found = targeted_record(child, record_id)
            if found is not None:
                return found
    elif isinstance(value, list):
        for child in value:
            found = targeted_record(child, record_id)
            if found is not None:
                return found
    return None


def jsonl_rows(path):
    with gzip.open(path, 'rt', encoding='utf-8') as source:
        for line in source:
            if line.strip():
                yield json.loads(line)


def canonical_bytes(row):
    return (json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n').encode()


def inside_window(row):
    return '1835-01-01' <= row['dob'] <= '1985-12-31'


def run(*, data_ready=False, workspace=WORKSPACE, output=None):
    assert data_ready is True, 'Wait for explicit root DATAREADY before inspecting final production data'
    workspace = Path(workspace).resolve()
    old = workspace / 'academy_repo/studies/royal_society_birthplace_completion_v43'
    current = workspace / 'academy_repo/studies/royal_society_birthplace_completion_v44'
    output = Path(output) if output is not None else workspace / 'v44_canonical_method_first_pass_queue_closeout.json'
    output = output.resolve()
    assert output.parent == workspace and output.name == 'v44_canonical_method_first_pass_queue_closeout.json'
    pins = {}
    checks = []

    def pin(path):
        pins[str(path.relative_to(workspace))] = file_sha256(path)
        return pins[str(path.relative_to(workspace))]

    def check(name, condition):
        assert condition, name
        checks.append(name)

    initial_path = old / 'inputs/v36_geography_target_ids.json'
    initial_values = read_json(initial_path)
    initial = set(initial_values)
    check('initial_62_distinct_from_frozen_V43_v36_input', len(initial_values) == len(initial) == 62)
    pin(initial_path)
    copied_initial = current / 'inputs/v36_geography_target_ids.json'
    check('current_initial_input_byte_exact', pin(copied_initial) == file_sha256(initial_path))

    method_path = current / 'audit/method_preregistration.json'
    check('unchanged_original_V36_preregistration_pin', pin(method_path) == BASE_METHOD_SHA256)
    method = read_json(method_path)
    reviewed = set(method['fixed_record_ids'])
    check('base_V36_fixed_six_distinct', len(method['fixed_record_ids']) == len(reviewed) == 6)
    scope_reviewed = {'V36': sorted(reviewed)}
    for filename in SCOPE_FILES:
        path = current / 'audit' / filename
        scope = read_json(path)
        values = scope['fixed_record_ids']
        version = 'V37' if filename == 'method_application_scope.json' else filename.removeprefix('method_application_scope_').removesuffix('.json').upper()
        check(version + '_scope_ids_distinct_and_disjoint', len(values) == len(set(values)) and not reviewed.intersection(values))
        if version == 'V44':
            check('V44_current_scope_pin', pin(path) == CURRENT_SCOPE_SHA256)
        else:
            check(version + '_scope_byte_exact_from_V43', pin(path) == pin(old / 'audit' / filename))
        reviewed.update(values)
        scope_reviewed[version] = sorted(values)
    check('all_53_scope_reviewed_ids_in_initial_62', len(reviewed) == 53 and reviewed <= initial)

    for filename in ISSUE_FILES:
        pin(current / 'audit' / filename)
    active_records = records(read_json(current / 'audit/active_source_DOB_conflicts.json'))
    place_records = records(read_json(current / 'audit/birthplace_source_conflicts.json'))
    active_ids = {row['record_id'] for row in active_records if row.get('active') is True}
    partial_place_ids = {row['record_id'] for row in place_records}
    individual_ids = set()
    for record_id, filename in INDIVIDUAL_PLACE_HOLDS.items():
        path = current / 'audit' / filename
        check(record_id + '_individual_hold_byte_exact', pin(path) == pin(old / 'audit' / filename))
        check(record_id + '_individual_hold_present', targeted_record(read_json(path), record_id) is not None)
        individual_ids.add(record_id)
    blocked = initial & (active_ids | partial_place_ids | individual_ids)
    unreviewed = initial - reviewed
    nonblocked = initial - blocked
    reviewed_blocked = reviewed & blocked
    notblocked_unreviewed = nonblocked - reviewed
    check('nine_unreviewed_ids_are_all_currently_blocked', len(unreviewed) == 9 and unreviewed <= blocked)
    check('no_current_nonblocked_unreviewed_ids', not notblocked_unreviewed)
    check('reviewed_Adam_conflict_remains_separate_from_unreviewed_blocked', 'RS_PAST_NA4918' in reviewed_blocked and 'RS_PAST_NA4918' not in unreviewed)
    check('reviewed_and_unreviewed_partition_initial_62', not reviewed & unreviewed and reviewed | unreviewed == initial)

    current_scope = set(scope_reviewed['V44'])
    fact_path = current / 'inputs/accepted_geography.json'
    hold_path = current / 'audit/followup_holds.json'
    facts = read_json(fact_path)
    holds = read_json(hold_path)
    accepted = {row['record_id'] for row in facts}
    held = {row['record_id'] for row in holds}
    check('actual_current_facts_holds_partition_five_scope_records', len(accepted) == len(facts) and len(held) == len(holds) and not accepted & held and accepted | held == current_scope)
    check('current_actual_conflicts_are_held', not accepted & blocked)
    pin(fact_path)
    pin(hold_path)

    old_master = old / 'outputs/birthplace_rows.jsonl.gz'
    new_master = current / 'outputs/birthplace_rows.jsonl.gz'
    old_digest = hashlib.sha256()
    new_digest = hashlib.sha256()
    old_blank_digest = hashlib.sha256()
    new_blank_digest = hashlib.sha256()
    old_unknown_initial = set()
    new_unknown_initial = set()
    all_unknown = set()
    window_unknown = set()
    window_nonblank_unknown = set()
    seen = set()
    old_counts = collections.Counter()
    new_counts = collections.Counter()
    for before, after in itertools.zip_longest(jsonl_rows(old_master), jsonl_rows(new_master)):
        check_row = before is not None and after is not None
        assert check_row, 'Stored master row lengths differ'
        record_id = after['record_id']
        assert record_id == before['record_id'] and record_id not in seen, 'Stored master ordering/uniqueness differs'
        seen.add(record_id)
        old_counts['records'] += 1
        new_counts['records'] += 1
        assert after['cohort'] == before['cohort'] == 'UK_Royal_Society'
        old_digest.update(canonical_bytes(before))
        new_digest.update(canonical_bytes(after))
        for row, counter, blank_digest in [(before, old_counts, old_blank_digest), (after, new_counts, new_blank_digest)]:
            blank = not row.get('raw_birthplace')
            counter['all_blank'] += blank
            counter['window_blank'] += blank and inside_window(row)
            if blank:
                blank_digest.update(canonical_bytes(row))
        if record_id in initial:
            assert before.get('raw_birthplace') and after.get('raw_birthplace') and inside_window(before) and inside_window(after)
            assert before['raw_birthplace'] == after['raw_birthplace'] and before['dob'] == after['dob']
            if before['hemisphere'] == 'unknown':
                old_unknown_initial.add(record_id)
            if after['hemisphere'] == 'unknown':
                new_unknown_initial.add(record_id)
        if after['hemisphere'] == 'unknown':
            all_unknown.add(record_id)
            if inside_window(after):
                window_unknown.add(record_id)
                if after.get('raw_birthplace'):
                    window_nonblank_unknown.add(record_id)
    check('both_stored_masters_4983_unique_rows', old_counts['records'] == new_counts['records'] == len(seen) == 4983)
    check('baseline_canonical_pin_independently_recomputed', old_digest.hexdigest() == BASE_CANONICAL_SHA256)
    check('initial_62_all_present_in_current_master', initial <= seen)
    check('original_eight_resolved_before_V44_actual_baseline', len(initial - old_unknown_initial) == 8 and len(old_unknown_initial) == 54)
    newly_resolved = old_unknown_initial - new_unknown_initial
    check('actual_current_resolution_delta_equals_adopted_ids', newly_resolved == accepted and not new_unknown_initial - old_unknown_initial)
    check('initial_current_unknown_equals_actual_window_nonblank_unknown', new_unknown_initial == window_nonblank_unknown)
    check('unknown_initial_partition_reviewed_holds_and_unreviewed_blocked', new_unknown_initial == (reviewed & new_unknown_initial) | unreviewed and not unreviewed - new_unknown_initial)
    check('actual_current_held_records_remain_unknown', held <= new_unknown_initial)
    check('103_window_blank_525_overall_blank_unchanged', old_counts['window_blank'] == new_counts['window_blank'] == 103 and old_counts['all_blank'] == new_counts['all_blank'] == 525 and old_blank_digest.hexdigest() == new_blank_digest.hexdigest())
    pin(old_master)
    pin(new_master)

    historical_pins = {}
    for filename in HISTORICAL_QUEUE_FILES:
        path = current / 'audit' / filename
        old_path = old / 'audit' / filename
        check(filename + '_historical_audit_byte_exact', pin(path) == pin(old_path))
        historical_pins[filename] = file_sha256(path)
    check('no_generic_historical_queue_audit_overwritten', not (current / 'audit/geography_first_pass_queue_closeout.json').exists())

    result = {
        'schema': 'UK_v44_canonical_method_first_pass_closeout_v1',
        'written_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'status': 'PASS',
        'scope_definition': 'Record-ID first-pass coverage for the original 62 nonblank birthplace geography-unknown records in the 1835-1985 inclusive native DOB window at the V36 boundary, under the unchanged V36 canonical-community reference method through V44.',
        'scope_reviewed_record_ids': scope_reviewed,
        'initial_record_ids': sorted(initial),
        'reviewed_record_ids': sorted(reviewed),
        'unreviewed_record_ids': sorted(unreviewed),
        'unreviewed_blocked_record_ids': sorted(unreviewed & blocked),
        'currently_blocked_record_ids': sorted(blocked),
        'currently_nonblocked_record_ids': sorted(nonblocked),
        'reviewed_blocked_record_ids': sorted(reviewed_blocked),
        'notblocked_and_unreviewed_record_ids': sorted(notblocked_unreviewed),
        'remaining_unknown_record_ids': sorted(new_unknown_initial),
        'reviewed_remaining_unknown_record_ids': sorted(reviewed & new_unknown_initial),
        'resolved_record_ids': sorted(initial - new_unknown_initial),
        'resolved_before_V44_record_ids': sorted(initial - old_unknown_initial),
        'newly_resolved_in_V44_record_ids': sorted(newly_resolved),
        'current_accepted_record_ids': sorted(accepted),
        'current_held_record_ids': sorted(held),
        'current_master_all_unknown_record_ids': sorted(all_unknown),
        'current_master_window_unknown_record_ids': sorted(window_unknown),
        'current_master_window_nonblank_unknown_record_ids': sorted(window_nonblank_unknown),
        'blocking_basis_record_ids': {
            'active_literal_DOB_conflict_within_initial': sorted(initial & active_ids),
            'partial_global_place_conflict_within_initial': sorted(initial & partial_place_ids),
            'separate_individual_place_holds_within_initial': sorted(initial & individual_ids),
        },
        'counts': {
            'initial': len(initial), 'reviewed': len(reviewed), 'unreviewed': len(unreviewed),
            'currently_blocked': len(blocked), 'currently_nonblocked': len(nonblocked),
            'reviewed_blocked': len(reviewed_blocked), 'unreviewed_blocked': len(unreviewed & blocked),
            'notblocked_and_unreviewed': len(notblocked_unreviewed),
            'remaining_unknown_within_initial': len(new_unknown_initial),
            'reviewed_remaining_unknown': len(reviewed & new_unknown_initial),
            'resolved_within_initial': len(initial - new_unknown_initial),
            'resolved_before_V44': len(initial - old_unknown_initial),
            'newly_resolved_in_V44': len(newly_resolved),
            'current_master_all_unknown': len(all_unknown),
            'current_master_window_unknown': len(window_unknown),
            'current_master_window_nonblank_unknown': len(window_nonblank_unknown),
            'window_blank_outside_scope': new_counts['window_blank'],
            'overall_blank_outside_scope': new_counts['all_blank'],
        },
        'nonblocked_first_pass_queue_complete': not notblocked_unreviewed,
        'all_current_nonblocked_initial_records_reviewed': nonblocked <= reviewed,
        'all_initial_records_reviewed': reviewed == initial,
        'birthplace_coverage_complete': False,
        'geography_coverage_complete': False,
        'source_exhausted': False,
        'all_biographies_or_sources_read': False,
        'final_freeze': False,
        'queue_coverage_semantic_limit': 'All current nonblocked first-pass candidates were reviewed. Nine currently blocked initial records remain unreviewed by this method. Coverage does not mean all birthplaces are resolved or sources exhausted; 103 blank-place window records remain outside this method scope.',
        'baseline_canonical_sha256': old_digest.hexdigest(),
        'current_canonical_sha256': new_digest.hexdigest(),
        'historical_queue_audit_sha256': historical_pins,
        'input_file_sha256': pins,
        'checks_passed': len(checks),
        'checks': checks,
        'master_storage_access': 'One ordered streaming pass over each stored V43 and V44 JSONL gzip; no complete master arrays, historical reconstruction, replay import, production CLI, network or Git.',
        'production_mutated': False,
        'historical_audits_overwritten': False,
    }
    temporary = output.with_name(output.name + '.' + uuid.uuid4().hex + '.writing')
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    temporary.replace(output)
    return {'closeout_local_path': str(output), 'closeout_path': 'audit/canonical_method_first_pass_queue_closeout_v44.json', 'closeout_sha256': file_sha256(output), 'counts': result['counts'], 'checks_passed': len(checks)}
