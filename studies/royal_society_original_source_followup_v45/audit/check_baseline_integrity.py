"""Standalone V45 baseline integrity verification; no historical loader or replay.

Default repository root is discovered from this file's ancestors. Optional
--repo-root and --output override it and the report destination.
"""
from pathlib import Path
import argparse
from collections import Counter
import csv
import datetime
import gzip
import hashlib
import json

FROZEN_PINS = {'V44_manifest_sha256': '58a4943643317939337e836cf9bd127fd26e19337d93f7ed3ba49ae8fd00b8cc',
 'baseline_pipeline_sha256': {'outputs/birthplace_rows.jsonl.gz': '433749a0b7ff0bfc62db8993f662cd928a4bc023418a54600259fdbea0b1537a',
                              'outputs/birthplaces.csv': '1bfdff7927abe23631fbd1d5a0be0e39898d835e8fe30d3ed97a72a5f08f288c',
                              'outputs/changes.json': '37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570',
                              'outputs/remaining_unknown_window.csv': '046c86fd8e27671974c3fc5714f0a49a77c55237fb9110f306dee6f95e4e6df7',
                              'outputs/summary.json': '23d4021c0029f1804a4a8166728e8f1618b860f0f80cadc531fe36eb09565451',
                              'scripts/replay.py': 'e7e6e6ced8a9f49b9db0c6a8c3b8bb1c0ab71949d3e6a2a3548292d5c064d1aa'},
 'baseline_pointer_sha256': 'de3f5dd9b169ddf51c9354d95d90c0e5e41f41a84f5e881eb5ae9f4724454e04',
 'native_scope_sha256': {'a': 'b95a8d2ba6bdef1f05c1631149ed08cde541656f6a3cb829747bb9054c07e32a',
                         'b': '1495099a3212412e2a15e234e87a52a5d16f999b4fc40f755f88f9776707d623',
                         'c': '7c71bad3211efd7e125fdaa622d79c860a590921dbaeaa2bc1e7e7e2531198a6'},
 'scope_sha256': '9a3226a121555bb4a7586e01a2ccd394f9f46071a1e4a839e87a408b388d278b'}
INVENTORIES = ['active_source_DOB_conflicts.json', 'birthplace_source_conflicts.json', 'source_derived_age_inconsistencies.json', 'provisional_parsed_date_discrepancies.json', 'lifespan_endpoint_discrepancies.json', 'cross_source_reported_age_contrasts.json', 'source_date_precision_holds.json', 'omitted_middle_name_admission.json', 'source_ordinal_age_wording_observations.json']
checks = []

def sha(path):
    result = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()

def read(path):
    return json.loads(path.read_text())

def check(name, condition):
    assert condition, name
    checks.append(name)

def discover_repo_root():
    for parent in Path(__file__).resolve().parents:
        if (parent / 'studies/royal_society_birthplace_completion_v44').is_dir() and (parent / 'studies/royal_society_original_source_followup_v45').is_dir():
            return parent
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo-root', type=Path, help='Repository root containing studies/')
    parser.add_argument('--output', type=Path, help='Integrity report destination; defaults to stage audit/baseline_integrity_final.json')
    args = parser.parse_args()
    REPO = args.repo_root.expanduser().resolve() if args.repo_root else discover_repo_root()
    if REPO is None:
        parser.error('Cannot discover repository root; pass --repo-root explicitly')
    BASE = REPO / 'studies/royal_society_birthplace_completion_v44'
    STAGE = REPO / 'studies/royal_society_original_source_followup_v45'
    OUT = args.output.expanduser().resolve() if args.output else STAGE / 'audit/baseline_integrity_final.json'
    if not BASE.is_dir() or not STAGE.is_dir():
        parser.error('--repo-root must contain both V44 baseline and V45 source-stage studies')
    if OUT.is_relative_to(BASE):
        parser.error('Output must be outside the frozen V44 baseline')
    checks.clear()
    pointer_path = STAGE / 'audit/baseline_pointer.json'
    pointer = read(pointer_path)
    scope_path = STAGE / 'scope.json'
    scope = read(scope_path)
    check('stage_scope_matches_frozen_SHA256_pin', sha(scope_path) == FROZEN_PINS['scope_sha256'])
    check('baseline_pointer_matches_frozen_SHA256_pin', sha(pointer_path) == FROZEN_PINS['baseline_pointer_sha256'])
    check('pointer_commit_canonical_gzip_match_scope_and_verified_V44', pointer['commit'] == scope['baseline_commit'] == 'cc23cc8d35eb2bfffcbbf041310dd049b308e5ca' and pointer['canonical_sha256'] == scope['baseline_canonical_sha256'] == 'a0c04e44631478f82e562deab64d699fc273e6fc99fa35ba23f8a61d7e1f8717' and pointer['gzip_sha256'] == scope['baseline_gzip_sha256'] == '433749a0b7ff0bfc62db8993f662cd928a4bc023418a54600259fdbea0b1537a')
    check('pointer_declares_source_only_and_unchanged_V44_primary_data', pointer['master_changed'] is False and pointer['original_source_stage_only'] is True and pointer['primary_data_directory'] == str(BASE.relative_to(REPO)))
    check('scope_is_source_strategy_not_new_admission_method', scope['strategy_not_new_admission_method'] is True and scope['strategy_id'] == 'unopened_original_person_sources_after_canonical_closeout_v1' and scope['no_analysis_or_final_cohort_freeze'] is True)
    method_pins = {}
    for version, authority in scope['inherited_admission_authority'].items():
        actual = sha(REPO / authority['path'])
        check('V' + version + '_admission_authority_exact', actual == authority['sha256'])
        method_pins[version] = {'path': authority['path'], 'sha256': actual}

    manifest = BASE / 'MANIFEST.sha256'
    check('V44_manifest_matches_frozen_SHA256_pin', sha(manifest) == FROZEN_PINS['V44_manifest_sha256'])
    manifest_entries = {}
    for line in manifest.read_text().splitlines():
        expected, name = line.split('  ', 1)
        assert name not in manifest_entries
        manifest_entries[name] = expected
    actual_names = {str(path.relative_to(BASE)) for path in BASE.rglob('*') if path.is_file() and path != manifest}
    check('V44_manifest_file_set_exact', set(manifest_entries) == actual_names)
    changed = [name for name, expected in manifest_entries.items() if sha(BASE / name) != expected]
    check('all_V44_manifest_entries_unchanged', not changed)

    issue_pins = {}
    blocked = {'RS_PAST_NA9209', 'RS_PAST_NA8779'}
    for name in INVENTORIES:
        baseline = BASE / 'audit' / name
        snapshot = STAGE / 'audit' / ('baseline_' + name)
        check('exact_issue_snapshot_' + name, baseline.read_bytes() == snapshot.read_bytes())
        value = read(snapshot)
        records = value if isinstance(value, list) else value.get('records')
        issue_pins[name] = {'sha256': sha(snapshot), 'shape': type(value).__name__, 'record_count': len(records) if isinstance(records, list) else None}
        if name in INVENTORIES[:2]:
            blocked.update(row['record_id'] for row in records)
    check('issue_counts_13_DOB_2_partialplace_4_age_and_metadata_omitted_middle', issue_pins['active_source_DOB_conflicts.json']['record_count'] == 13 and issue_pins['birthplace_source_conflicts.json']['record_count'] == 2 and issue_pins['source_derived_age_inconsistencies.json']['record_count'] == 4 and issue_pins['omitted_middle_name_admission.json']['shape'] == 'dict' and issue_pins['omitted_middle_name_admission.json']['record_count'] is None)
    ids = scope['fixed_record_ids']
    check('fixed_six_records_group_order_and_no_blocked_intersection', ids == sum(scope['groups'].values(), []) and len(ids) == len(set(ids)) == 6 and not set(ids) & blocked)
    needed = set(ids)
    selected, counts, window_counts = {}, Counter(), Counter()
    canonical = hashlib.sha256()
    total = window_total = blank_total = window_blank = 0
    with gzip.open(BASE / 'outputs/birthplace_rows.jsonl.gz', 'rt') as handle:
        for line in handle:
            row = json.loads(line)
            canonical.update((json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n').encode())
            total += 1
            counts[row['hemisphere']] += 1
            blank_total += not row.get('raw_birthplace')
            if '1835-01-01' <= row['dob'] <= '1985-12-31':
                window_total += 1
                window_counts[row['hemisphere']] += 1
                window_blank += not row.get('raw_birthplace')
            if row['record_id'] in needed:
                selected[row['record_id']] = row
    check('baseline_master_canonical_and_gzip_exact', canonical.hexdigest() == pointer['canonical_sha256'] and sha(BASE / 'outputs/birthplace_rows.jsonl.gz') == pointer['gzip_sha256'])
    check('baseline4983_window2644_counts_and_blank_boundaries', total == 4983 and counts == {'north': 4205, 'south': 187, 'unknown': 591} and window_total == 2644 and window_counts == {'north': 2305, 'south': 182, 'unknown': 157} and blank_total == 525 and window_blank == 103)
    check('all_scope_rows_native_window_unknown', set(selected) == needed and all(row['hemisphere'] == 'unknown' and '1835-01-01' <= row['dob'] <= '1985-12-31' for row in selected.values()))
    check('scope_three_blank_three_storedplace_partition_exact', scope['initial_blank_ids'] == [record_id for record_id in ids if not selected[record_id]['raw_birthplace']] and scope['initial_storedplace_ids'] == [record_id for record_id in ids if selected[record_id]['raw_birthplace']] and len(scope['initial_blank_ids']) == len(scope['initial_storedplace_ids']) == 3)
    native_scope_pins = {}
    for group, group_ids in scope['groups'].items():
        path = STAGE / 'audit' / ('native_scope_' + group + '.json')
        expected = [selected[record_id] for record_id in group_ids]
        check('exact_native_complete_objects_group_' + group, read(path) == expected)
        check('native_scope_frozen_SHA256_group_' + group, sha(path) == FROZEN_PINS['native_scope_sha256'][group])
        native_scope_pins[group] = {'sha256': sha(path), 'record_ids': group_ids}

    pipeline_pins = {'scripts/replay.py': sha(BASE / 'scripts/replay.py')}
    check('V44_replay_bytes_original_verified_hash', pipeline_pins['scripts/replay.py'] == 'e7e6e6ced8a9f49b9db0c6a8c3b8bb1c0ab71949d3e6a2a3548292d5c064d1aa')
    output_names = {'birthplace_rows.jsonl.gz', 'birthplaces.csv', 'remaining_unknown_window.csv', 'summary.json', 'changes.json'}
    check('baseline_exact_five_outputs', {path.name for path in (BASE / 'outputs').iterdir()} == output_names)
    for name in sorted(output_names):
        pipeline_pins['outputs/' + name] = sha(BASE / 'outputs' / name)
    check('all_five_outputs_and_replay_match_original_snapshot_pins', pipeline_pins == FROZEN_PINS['baseline_pipeline_sha256'])
    csv_shape = {}
    for name, expected_rows in [('birthplaces.csv', 4983), ('remaining_unknown_window.csv', 157)]:
        with (BASE / 'outputs' / name).open(newline='') as handle:
            reader = csv.reader(handle)
            header = next(reader)
            rows = 0
            rectangular = True
            for row in reader:
                rows += 1
                rectangular &= len(row) == len(header)
        check('frozen_V44_CSV200_shape_' + name, len(header) == 200 and rows == expected_rows and rectangular)
        csv_shape[name] = {'columns': len(header), 'data_rows': rows}
    forbidden = ['scripts/replay.py', 'outputs/birthplace_rows.jsonl.gz', 'outputs/birthplaces.csv', 'outputs/remaining_unknown_window.csv', 'outputs/summary.json', 'outputs/changes.json']
    check('V45_has_no_new_master_pipeline_or_CSV_artifacts', all(not (STAGE / name).exists() for name in forbidden))
    check('baseline_current_facts_empty_five_holds_and_changes_empty', read(BASE / 'inputs/accepted_geography.json') == [] and len(read(BASE / 'audit/followup_holds.json')) == 5 and read(BASE / 'outputs/changes.json') == [])
    report = dict(written_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), status='pass', phase='standalone_source_stage_baseline_integrity_snapshot', check_count=len(checks), checks=checks, baseline_pointer={'path': str(pointer_path.relative_to(REPO)), 'sha256': sha(pointer_path), **pointer}, scope_sha256=sha(scope_path), manifest_sha256=sha(manifest), V44_manifest_files_verified=len(manifest_entries), V44_master_pipeline_and_CSV_unchanged=True, issue_inventory_count=9, issue_snapshots=issue_pins, native_scope_snapshots=native_scope_pins, inherited_method_pins=method_pins, baseline_pipeline_sha256=pipeline_pins, baseline_CSV_shapes=csv_shape, V45_new_master_pipeline_or_CSV_artifacts=False, canonical_records=total, native_window_records=window_total, native_window_unknown=window_counts['unknown'], baseline_raw_place_blank_window=window_blank, baseline_raw_place_nonblank_unknown_window=window_counts['unknown'] - window_blank, historical_loader_runs=0, replay_CLI_runs=0, web_requests=0, master_pipeline_or_frozen_audit_mutations_by_checker=0, audit_report_destination=str(OUT), scratch_alias_checks={'performed': False, 'checks': ['scratch v45_original_scope.json vs stage scope.json byte comparison', 'scratch v45_scope_[abc].json vs stage native_scope_[abc].json byte comparisons'], 'reason': 'Standalone committed checker does not depend on scratch aliases. Actual stage scope and native snapshots are checked against frozen SHA256 pins and complete V44 objects instead.'}, limits='This timed structural snapshot verifies local V44 manifest/pins, native scope and issue snapshot integrity. It does not adjudicate current source evidence, acquisition work identity, source grades, retrieval chronology or future accepted facts. Baseline pointer commit identity is compared with the frozen scope and known verified commit; no remote Git operation was performed.')
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'status': report['status'], 'check_count': len(checks), 'report': str(OUT), 'report_sha256': sha(OUT), 'V44_manifest_files_verified': len(manifest_entries), 'scope_sha256': report['scope_sha256'], 'baseline_replay_sha256': pipeline_pins['scripts/replay.py'], 'canonical_sha256': canonical.hexdigest(), 'gzip_sha256': pipeline_pins['outputs/birthplace_rows.jsonl.gz'], 'historical_loader_runs': 0, 'replay_CLI_runs': 0}))

if __name__ == '__main__':
    main()
