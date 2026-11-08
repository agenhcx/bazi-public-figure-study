"""Independent concrete V46 data QA. Preparation is inert; no replay is imported or run."""
from __future__ import annotations

import ast
import collections
import copy
import csv
import datetime
import gzip
import hashlib
import itertools
import json
from pathlib import Path
import uuid

W = Path('/workspace/scratch/262552d8c0f0')
RID = 'RS_PAST_NA4250'
CONTEXT = 'birthplace_followup_v46'
BASE_GZIP = '433749a0b7ff0bfc62db8993f662cd928a4bc023418a54600259fdbea0b1537a'
BASE_CANONICAL = 'a0c04e44631478f82e562deab64d699fc273e6fc99fa35ba23f8a61d7e1f8717'
SCOPE_SHA = '6051c4a3f9887bbba4556595f9dfbbfd8c5bb6ab552d586e9cf67f217597c7bc'
BP = {'raw_birthplace', 'birthplace_source_grade', 'birthplace_source_url',
      'birthplace_source_urls', 'birthplace_claim_excerpt', 'birthplace_claim_status',
      'birthplace_evidence_kind'}
GEO = {'hemisphere', 'geo_resolution_status', 'geography_decision', 'reason',
       'northern_birthplace_candidate', 'southern_birthplace_separate'}
OUTPUTS = {'birthplace_rows.jsonl.gz', 'birthplaces.csv', 'remaining_unknown_window.csv',
           'summary.json', 'changes.json'}


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda: source.read(1048576), b''):
            digest.update(block)
    return digest.hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def canon(row):
    return (json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n').encode()


def objects(path):
    with gzip.open(path, 'rt', encoding='utf-8') as source:
        for line in source:
            if line.strip():
                yield json.loads(line)


def inside(row):
    return '1835-01-01' <= row['dob'] <= '1985-12-31'


def run(*, outputs_ready=False, source_qa_sha256=None, replay_receipts=None):
    assert outputs_ready is True, 'Wait for root DATAREADY; do not execute the replay here'
    assert isinstance(source_qa_sha256, str) and len(source_qa_sha256) == 64
    assert replay_receipts is not None and len(replay_receipts) == 2
    old = W / 'academy_repo/studies/royal_society_birthplace_completion_v44'
    current = W / 'academy_repo/studies/royal_society_birthplace_completion_v46'
    sources = W / 'academy_repo/studies/royal_society_original_source_followup_v46'
    checks = []

    def check(name, value):
        assert value, name
        checks.append(name)

    # Inspect source, never import a replay or reconstruct historical versions.
    old_tree = ast.parse((old / 'scripts/replay.py').read_text())
    new_tree = ast.parse((current / 'scripts/replay.py').read_text())
    old_apply = next(n for n in old_tree.body if isinstance(n, ast.FunctionDef) and n.name == 'apply_first_birthplaces')
    new_apply = copy.deepcopy(next(n for n in new_tree.body if isinstance(n, ast.FunctionDef) and n.name == 'apply_first_birthplaces'))
    additions = 0
    for node in ast.walk(new_apply):
        if isinstance(node, ast.Set) and any(isinstance(e, ast.Constant) and e.value == 'v29' for e in node.elts):
            kept = [e for e in node.elts if not (isinstance(e, ast.Constant) and e.value == 'v46')]
            additions += len(node.elts) - len(kept)
            node.elts = kept
    check('inherited_first_birthplace_function_only_three_v46_version_additions', additions == 3 and ast.dump(old_apply) == ast.dump(new_apply))
    forbidden = [n for n in ast.walk(new_tree) if isinstance(n, ast.ImportFrom) and n.module and ('replay' in n.module or 'v44' in n.module)]
    check('new_replay_has_no_historical_replay_import', not forbidden)

    pointer_path = current / 'audit/source_stage_pointer.json'
    pointer = read(pointer_path)
    scope = read(current / 'audit/source_scope.json')
    qa_path = current / 'audit/source_qa.json'
    check('immutable_independent_SourceQA_hash', sha(qa_path) == sha(sources / 'audit/source_qa.json') == pointer['source_qa_sha256'] == source_qa_sha256)
    qa = read(qa_path)
    check('SourceQA_pass_and_frozen_scope', qa['status'].upper() == 'PASS' and qa['scope_sha256'] == sha(current / 'audit/source_scope.json') == SCOPE_SHA)
    fact_path = current / 'inputs/accepted_birthplaces.json'
    facts = read(fact_path)
    check('one_Morris_fact_and_no_geography_only_facts', len(facts) == 1 and facts[0]['record_id'] == RID and read(current / 'inputs/accepted_geography.json') == [])
    fact = facts[0]
    check('source_fact_copies_exact_and_pointer_bound', sha(fact_path) == sha(sources / 'audit/accepted_birthplaces.json') == pointer['accepted_birthplaces_sha256'] and sha(current / 'inputs/accepted_geography.json') == sha(sources / 'audit/accepted_geography.json') == pointer['accepted_geography_sha256'])
    check('source_adjudication_and_scope_copies_exact', sha(current / 'audit/source_adjudication.json') == sha(sources / 'audit/parent_adjudication.json') == pointer['source_adjudication_sha256'] and sha(current / 'audit/source_scope.json') == sha(sources / 'scope.json'))
    check('native_day_preserved_source_YEAR_only', fact['native_dob'] == '1934-04-17' and fact['source_birthdate'] == '1934' and fact['source_birthdate_precision'] == 'year_in_actual_person_lifespan_header' and fact['source_DOB_matches_native_at_stated_precision'] is True and fact['source_independent_exact_native_day_confirmation'] is False)
    check('concrete_adopted_Australia_S3_south', fact['raw_birthplace'] == 'Australia' and fact['source_grade'] == 'S3' and fact['reviewed_hemisphere'] == 'south' and fact['source_grade_role'] == 'person_birthplace_support_only')
    immutable_paths = [qa_path, pointer_path, fact_path, current / 'inputs/accepted_geography.json', current / 'audit/source_scope.json', current / 'audit/source_adjudication.json', current / 'scripts/replay.py', sources / 'scope.json', sources / 'audit/parent_adjudication.json', sources / 'audit/accepted_birthplaces.json', sources / 'audit/accepted_geography.json']
    scope_native = {}
    for group in 'abc':
        snapshot = current / 'audit' / ('native_scope_' + group + '.json')
        check('native_scope_snapshot_exact_' + group, sha(snapshot) == sha(sources / 'audit' / snapshot.name) == sha(W / ('v46_scope_' + group + '.json')))
        immutable_paths.append(snapshot)
        for row in read(snapshot):
            assert row['record_id'] not in scope_native
            scope_native[row['record_id']] = row
        check('SourceQA_worker_evidence_pins_' + group, sha(sources / 'audit' / ('v46_sources_' + group + '.json')) == qa['worker_evidence_pins'][group]['report_sha256'] and sha(sources / 'audit' / ('v46_intent_' + group + '.json')) == qa['worker_evidence_pins'][group]['intent_sha256'])
    check('all_five_native_source_scope_records_bound', set(scope_native) == set(scope['fixed_record_ids']) and len(scope_native) == 5)
    check('SourceQA_root_evidence_pins', sha(sources / 'audit/root_followups.json') == qa['root_followups_sha256'] and sha(sources / 'audit/v46_root_intent.json') == qa['root_intent_sha256'] and sha(fact_path) == qa['accepted_birthplaces_sha256'] and sha(sources / 'audit/parent_adjudication.json') == qa['parent_adjudication_sha256'])
    immutable_paths.extend(path for path in sources.rglob('*') if path.is_file())
    inventory_pins = {}
    for name, expected in scope['issue_inventory_pins'].items():
        paths = [old / 'audit' / name, current / 'audit' / ('baseline_' + name), sources / 'audit' / ('baseline_' + name)]
        check('inventory_exact_' + name, all(sha(path) == expected for path in paths))
        immutable_paths.extend(paths)
        inventory_pins[name] = expected
    check('all_nine_issue_inventories_preserved', len(inventory_pins) == 9)
    frozen_pins = {str(path): sha(path) for path in immutable_paths}

    old_master = old / 'outputs/birthplace_rows.jsonl.gz'
    new_master = current / 'outputs/birthplace_rows.jsonl.gz'
    check('baseline_gzip_pin', sha(old_master) == BASE_GZIP)
    before_digest = hashlib.sha256()
    after_digest = hashlib.sha256()
    overall = collections.Counter()
    window = collections.Counter()
    diagnostics = collections.Counter()
    ids = []
    seen = set()
    changed = []
    unknown_ids = []
    morris_before = morris_after = None
    for before, after in itertools.zip_longest(objects(old_master), objects(new_master)):
        assert before is not None and after is not None, 'Master row count differs'
        rid = after['record_id']
        assert rid == before['record_id'] and rid not in seen and after['cohort'] == before['cohort'] == 'UK_Royal_Society'
        seen.add(rid)
        ids.append(rid)
        before_digest.update(canon(before))
        after_digest.update(canon(after))
        if rid in scope_native:
            assert before == scope_native[rid], ('Native source snapshot differs from baseline', rid)
        if rid != RID:
            assert after == before, ('Untargeted complete object changed', rid)
        else:
            morris_before, morris_after = before, after
            assert before['dob'] == after['dob'] == fact['native_dob'] == '1934-04-17'
            assert before['source_authorised_full_name'] == after['source_authorised_full_name'] == fact['authority_name']
            assert before['hemisphere'] == 'unknown' and not before.get('raw_birthplace') and CONTEXT not in before
            assert set(after) - set(before) == {CONTEXT} and set(before) <= set(after)
            assert all(after[key] == before[key] for key in before if key not in BP | GEO)
            previous = {key: before[key] for key in sorted(BP | GEO) if key in before}
            absent = sorted((BP | GEO) - set(before))
            expected_context = copy.deepcopy(fact)
            expected_context.update(previous_birthplace_fields=previous, previous_absent_birthplace_fields=absent, source_grade_role='person_birthplace_support_only', native_DOB_source_grade_unchanged=True, prior_selected_evidence_kept_as_history=True)
            assert after[CONTEXT] == expected_context
            expected_fields = {'raw_birthplace': 'Australia', 'birthplace_source_grade': 'S3', 'birthplace_source_url': fact['source_url'], 'birthplace_source_urls': list(dict.fromkeys([fact['source_url'], *fact.get('source_urls', [fact['source_url']])])), 'birthplace_claim_excerpt': fact['source_quote'], 'birthplace_claim_status': 'recovered_explicit_birthplace_v46', 'birthplace_evidence_kind': 'v46_reviewed_explicit_person_birthplace', 'hemisphere': 'south', 'geo_resolution_status': 'resolved_by_v46_explicit_birthplace_region', 'geography_decision': 'v46_reviewed_explicit_birthplace_region', 'reason': 'explicit_birthplace_context_wholly_southern_region', 'northern_birthplace_candidate': False, 'southern_birthplace_separate': True}
            assert {key: after[key] for key in BP | GEO} == expected_fields
            restored = copy.deepcopy(after)
            del restored[CONTEXT]
            restored.update(previous)
            for key in absent:
                restored.pop(key, None)
            assert restored == before
        if after != before:
            changed.append(rid)
        blank = not after.get('raw_birthplace')
        unknown = after['hemisphere'] == 'unknown'
        overall[after['hemisphere']] += 1
        diagnostics['all_blank_raw_birthplace'] += blank
        diagnostics['all_unknown'] += unknown
        diagnostics['all_unknown_with_blank_raw_birthplace'] += unknown and blank
        diagnostics['all_unknown_with_nonblank_raw_birthplace'] += unknown and not blank
        if inside(after):
            window[after['hemisphere']] += 1
            diagnostics['window_blank_raw_birthplace'] += blank
            diagnostics['window_unknown'] += unknown
            diagnostics['window_unknown_with_blank_raw_birthplace'] += unknown and blank
            diagnostics['window_unknown_with_nonblank_raw_birthplace'] += unknown and not blank
            if unknown:
                unknown_ids.append(rid)
    check('4983_ordered_unique_records_only_Morris_changed', len(ids) == len(seen) == 4983 and changed == [RID] and morris_after is not None)
    check('4982_untargeted_complete_objects_exact', len(ids) - len(changed) == 4982)
    check('baseline_canonical_pin_and_exact_rollback', before_digest.hexdigest() == BASE_CANONICAL and morris_before is not None)
    check('all_native_source_snapshot_IDs_present_in_baseline', set(scope_native) <= seen)
    check('actual_overall_and_window_counts', overall == {'north': 4205, 'south': 188, 'unknown': 590} and window == {'north': 2305, 'south': 183, 'unknown': 156} and sum(window.values()) == 2644)
    check('actual_blank_and_stored_unknown_counts', diagnostics == {'all_blank_raw_birthplace': 524, 'window_blank_raw_birthplace': 102, 'all_unknown': 590, 'all_unknown_with_blank_raw_birthplace': 524, 'all_unknown_with_nonblank_raw_birthplace': 66, 'window_unknown': 156, 'window_unknown_with_blank_raw_birthplace': 102, 'window_unknown_with_nonblank_raw_birthplace': 54})

    with (old / 'outputs/birthplaces.csv').open(newline='') as old_handle, (current / 'outputs/birthplaces.csv').open(newline='') as new_handle:
        old_csv, new_csv = csv.DictReader(old_handle), csv.DictReader(new_handle)
        columns = old_csv.fieldnames
        check('CSV_200_old_columns_plus_one_context_in_order', len(columns) == 200 and new_csv.fieldnames == columns + [CONTEXT])
        csv_ids = []
        for before, after in itertools.zip_longest(old_csv, new_csv):
            assert before is not None and after is not None and before['record_id'] == after['record_id']
            csv_ids.append(after['record_id'])
            projected = {key: after[key] for key in columns}
            if after['record_id'] == RID:
                expected = dict(before)
                expected.update(raw_birthplace='Australia', hemisphere='south', birthplace_source_grade='S3')
                assert projected == expected and json.loads(after[CONTEXT]) == morris_after[CONTEXT]
            else:
                assert projected == before and after[CONTEXT] == ''
        check('CSV_all4982_untargeted_rows_and_Morris_old_column_meanings_exact', csv_ids == ids)
    with (old / 'outputs/remaining_unknown_window.csv').open(newline='') as old_handle, (current / 'outputs/remaining_unknown_window.csv').open(newline='') as new_handle:
        old_csv, new_csv = csv.DictReader(old_handle), csv.DictReader(new_handle)
        check('remaining_CSV_201_same_column_schema', old_csv.fieldnames == columns and new_csv.fieldnames == columns + [CONTEXT])
        old_remaining = []
        def retained_old_unknown_rows():
            for row in old_csv:
                old_remaining.append(row['record_id'])
                if row['record_id'] != RID:
                    yield row
        remaining_ids = []
        for before, after in itertools.zip_longest(retained_old_unknown_rows(), new_csv):
            assert before is not None and after is not None and {key: after[key] for key in columns} == before and after[CONTEXT] == ''
            remaining_ids.append(after['record_id'])
        check('remaining156_old_rows_exact_Morris_only_removed', len(old_remaining) == 157 and old_remaining.count(RID) == 1 and remaining_ids == unknown_ids and len(remaining_ids) == 156)

    summary = read(current / 'outputs/summary.json')
    check('summary_counts_and_precision_match_actual_data', summary['records'] == 4983 and summary['overall'] == dict(overall) and summary['native_dob_window_counts'] == dict(window) and summary['remaining_blank_current_fields'] == dict(diagnostics) and summary['new_first_birthplace_records'] == 1 and summary['new_geography_only_resolutions'] == 0 and summary['unchanged_complete_rows'] == 4982 and summary['source_qa_sha256'] == source_qa_sha256 and summary['CSV_columns'] == 201 and summary['existing_CSV_columns_preserved'] == 200 and summary['baseline_gzip_sha256'] == BASE_GZIP and summary['baseline_canonical_sha256'] == BASE_CANONICAL)
    packaged_baseline = current / 'inputs/baseline_v44_birthplace_rows.jsonl.gz'
    check('packaged_baseline_gzip_if_present_exact', not packaged_baseline.exists() or sha(packaged_baseline) == BASE_GZIP)
    expected_change = {'record_id': RID, 'native_name': morris_before['name'], 'dob': '1934-04-17', 'before_raw_birthplace': morris_before.get('raw_birthplace', ''), 'after_raw_birthplace': 'Australia', 'before_birthplace_source_grade': morris_before.get('birthplace_source_grade', ''), 'after_birthplace_source_grade': 'S3', 'before_hemisphere': 'unknown', 'after_hemisphere': 'south', 'new_geographic_resolution': True, 'source_url': fact['source_url'], 'source_grade_role': 'person_birthplace_support_only', 'native_DOB_source_grade_unchanged': True}
    check('changes_exact_single_reviewed_fact_delta', read(current / 'outputs/changes.json') == [expected_change])

    production_pins = {name: sha(current / 'outputs' / name) for name in sorted(OUTPUTS)}
    receipts = []
    for path in replay_receipts:
        receipt = read(path)
        output_dir = Path(receipt['output_dir']).resolve()
        check('root_CLI_exit0_' + str(len(receipts) + 1), receipt['exit_code'] == 0 and output_dir != (current / 'outputs').resolve() and Path(receipt['log_path']).is_file() and sha(receipt['log_path']) == receipt['log_sha256'])
        check('isolated_CLI_five_output_hashes_' + str(len(receipts) + 1), set(receipt['output_sha256']) == OUTPUTS and receipt['output_sha256'] == {name: sha(output_dir / name) for name in OUTPUTS} == production_pins)
        command = receipt['command']
        check('isolated_CLI_actual_script_pointer_and_destination_' + str(len(receipts) + 1), receipt['replay_script_sha256'] == sha(current / 'scripts/replay.py') and receipt['source_pointer_sha256'] == sha(pointer_path) and isinstance(command, list) and str(current / 'scripts/replay.py') in command and '--output-dir' in command and Path(command[command.index('--output-dir') + 1]).resolve() == output_dir)
        receipts.append({'receipt_path': str(Path(path).resolve()), 'receipt_sha256': sha(path), **receipt})
    first, second = receipts
    check('two_distinct_isolated_CLIs_executed_sequentially', Path(first['output_dir']).resolve() != Path(second['output_dir']).resolve() and datetime.datetime.fromisoformat(first['start_utc']) <= datetime.datetime.fromisoformat(first['end_utc']) <= datetime.datetime.fromisoformat(second['start_utc']) <= datetime.datetime.fromisoformat(second['end_utc']))
    check('reviewed_source_evidence_and_SourceQA_immutable_through_data_QA', all(sha(path) == digest for path, digest in frozen_pins.items()) and sha(qa_path) == source_qa_sha256)

    report = {'schema': 'UK_v46_independent_data_QA_v1', 'status': 'PASS', 'written_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'source_qa_sha256': source_qa_sha256, 'source_qa_report_mutated': False, 'checker_sha256': sha(Path(__file__)), 'checks_passed': len(checks), 'checks': checks, 'baseline_canonical_sha256': before_digest.hexdigest(), 'current_canonical_sha256': after_digest.hexdigest(), 'complete_objects': 4983, 'changed_record_ids': changed, 'unchanged_complete_objects': 4982, 'original_birthplace_fields_mutable': sorted(BP), 'geographic_fields_mutable': sorted(GEO), 'sole_new_context_field': CONTEXT, 'native_DOB': '1934-04-17', 'source_birthdate': '1934', 'source_birthdate_precision': fact['source_birthdate_precision'], 'source_exact_native_day_confirmation': False, 'overall': dict(overall), 'window_counts': dict(window), 'blank_diagnostics': dict(diagnostics), 'CSV_columns': 201, 'existing_CSV_columns_preserved': 200, 'remaining_unknown_CSV_rows': 156, 'nine_issue_inventory_sha256': inventory_pins, 'reviewed_source_file_sha256': frozen_pins, 'production_output_sha256': production_pins, 'root_serial_replay_receipts': receipts, 'replay_imported_or_executed_by_this_checker': False, 'historical_pipeline_imported_or_replayed': False, 'production_or_source_evidence_mutated': False}
    output = W / 'v46_independent_data_qa.json'
    temporary = output.with_name(output.name + '.' + uuid.uuid4().hex + '.writing')
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    temporary.replace(output)
    return {'report_path': str(output), 'report_sha256': sha(output), 'checks_passed': len(checks), 'current_canonical_sha256': report['current_canonical_sha256'], 'production_output_sha256': production_pins}
