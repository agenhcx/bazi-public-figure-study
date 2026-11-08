"""Cheap additive V44 checks: no historical loader and no replay CLI."""
import ast
from collections import Counter
import copy
import csv
import datetime
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import time
import traceback

W = Path(__file__).resolve().parent
OLD = W / 'academy_repo/studies/royal_society_birthplace_completion_v43'
NEW = OLD.with_name('royal_society_birthplace_completion_v44')
OUT = W / 'v44_replay_preflight.json'
CURRENT = {'accepted_geography.json', 'geography_target_ids.json', 'geography_followup_ids.json', 'reviewed_record_ids.json'}
checks = []
start = time.monotonic()

def check(name, condition):
    assert condition, name
    checks.append(name)

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def parts(path):
    source = path.read_text()
    tree = ast.parse(source)
    return ({n.name: ast.get_source_segment(source, n) for n in tree.body if isinstance(n, ast.FunctionDef)}, [ast.get_source_segment(source, n) for n in tree.body if isinstance(n, ast.Assign)])

def reject(name, fn, expected):
    actual = None
    try:
        fn()
    except AssertionError as error:
        actual = str(error)
    check(name, actual == expected)

def rollback(rows, field):
    result = copy.deepcopy(rows)
    for row in result:
        context = row.pop(field, None)
        if context:
            for key in context['previous_absent_geography_fields']:
                row.pop(key, None)
            row.update(context['previous_geography_fields'])
    return result

def run():
    old_functions, old_assignments = parts(OLD / 'scripts/replay.py')
    new_functions, new_assignments = parts(NEW / 'scripts/replay.py')
    check('all69_historical_functions_literal', len(old_functions) == 69 and all(new_functions.get(k) == v for k, v in old_functions.items()))
    check('all144_historical_assignments_literal', len(old_assignments) == 144 and all(v in new_assignments for v in old_assignments))
    check('exact_additive73_functions152_assignments', len(new_functions) == 73 and len(new_assignments) == 152 and set(new_functions) - set(old_functions) == {'load_v43', 'apply_v44_geography', 'write_csv_v44', 'main_v44'})
    check('baseline_V43_code_hash_verified', digest(OLD / 'scripts/replay.py') == '4b8c93bae7503a6b32f5e25e5c7700159bc71fe804838a6f747a8f5742e94fe4')
    check('CLI_entry_calls_additive_main_v44', (NEW / 'scripts/replay.py').read_text().endswith("if __name__ == '__main__':\n    main_v44()\n"))
    check('current_main_requires_five_followups_and_reviewed_rows', "len(followup_ids) == len(set(followup_ids)) == 5" in new_functions['main_v44'] and "len(reviewed_ids) == len(set(reviewed_ids)) == 5" in new_functions['main_v44'] and 'five fixed followups' in new_functions['main_v44'] and 'Five fixed individual followups' in new_functions['main_v44'])
    expected_loader = old_functions['load_v42'].replace('v42', 'v43').replace('V42', 'V43').replace('baseline = load_v41()', 'baseline = load_v42()')
    check('historical_V43_loader_preserves_six_hold_scope', new_functions['load_v43'] == expected_loader and 'len(holds) == len(held_ids) == 6' in new_functions['load_v43'])
    mapping = {path.name: 'v43_' + path.name if path.name in CURRENT else path.name for path in (OLD / 'inputs').iterdir()}
    check('all129_prior_inputs_mapped_without_dropping_native_snapshot', len(mapping) == 129 and set(CURRENT) <= set(mapping) and all((NEW / 'inputs' / target).read_bytes() == (OLD / 'inputs' / source).read_bytes() for source, target in mapping.items()))
    check('five_V43_current_carriers_and_holds_byte_exact', all((NEW / 'inputs' / ('v43_' + name)).read_bytes() == (OLD / 'inputs' / name).read_bytes() for name in CURRENT) and (NEW / 'inputs/v43_followup_holds.json').read_bytes() == (OLD / 'audit/followup_holds.json').read_bytes())
    native_snapshot = json.loads((NEW / 'inputs/v42_reviewed_native_rows.json').read_text())
    check('native_snapshot_original_SHA256', digest(NEW / 'inputs/v42_reviewed_native_rows.json') == '421972d5602749d5df23d8d240e76883b0509e12803e882b17f3209120039065')
    ids = json.loads((NEW / 'inputs/geography_followup_ids.json').read_text())
    targets = json.loads((NEW / 'inputs/geography_target_ids.json').read_text())
    old_ids = json.loads((NEW / 'inputs/v43_geography_followup_ids.json').read_text())
    plan = json.loads((W / 'v44_plan.json').read_text())
    scope = json.loads((W / 'v44_method_application_scope.json').read_text())
    check('fixed_five_followups_match_plan_scope_in_order', ids == sum(plan['geography_followup_groups'].values(), []) == scope['fixed_record_ids'] and len(ids) == len(set(ids)) == 5 and set(ids) <= set(targets))
    check('prospective_review_count_five_groups221', plan['fixed_review_count'] == scope['fixed_review_count'] == 5 and scope['group_sizes'] == [2, 2, 1] and [len(group) for group in scope['groups'].values()] == [2, 2, 1])
    check('native_snapshot_six_V42_ids_same_path_preserved', len(native_snapshot) == 6 and (NEW / 'inputs/v42_reviewed_native_rows.json').read_bytes() == (OLD / 'inputs/v42_reviewed_native_rows.json').read_bytes())
    needed = set(ids) | set(old_ids) | {row['record_id'] for row in native_snapshot}
    for version in range(37, 41):
        needed.add(json.loads((NEW / ('inputs/v' + str(version) + '_accepted_geography.json')).read_text())[0]['record_id'])
    rows, target_expected = {}, []
    count = all_blank = window_blank = window_count = 0
    overall, window = Counter(), Counter()
    canonical = hashlib.sha256()
    with gzip.open(OLD / 'outputs/birthplace_rows.jsonl.gz', 'rt') as handle:
        for line in handle:
            row = json.loads(line)
            canonical.update((json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n').encode())
            count += 1
            overall[row['hemisphere']] += 1
            all_blank += not row.get('raw_birthplace')
            in_window = '1835-01-01' <= row['dob'] <= '1985-12-31'
            if in_window:
                window_count += 1
                window[row['hemisphere']] += 1
                window_blank += not row.get('raw_birthplace')
            if row['record_id'] in needed:
                rows[row['record_id']] = row
            if in_window and row['hemisphere'] == 'unknown' and row.get('raw_birthplace'):
                target_expected.append(row['record_id'])
    check('stored_V43_canonical_hash_exact_without_historical_load', canonical.hexdigest() == 'a0c04e44631478f82e562deab64d699fc273e6fc99fa35ba23f8a61d7e1f8717')
    check('stored_baseline4983_counts_and_blank_boundaries', count == 4983 and overall == {'north': 4205, 'south': 187, 'unknown': 591} and window_count == 2644 and window == {'north': 2305, 'south': 182, 'unknown': 157} and all_blank == 525 and window_blank == 103)
    check('target54_matches_streamed_stored_baseline', targets == sorted(target_expected) and len(targets) == 54)
    check('all_cheap_fixture_rows_found', set(rows) == needed)
    native_binding = scope['native_identity_bindings']['RS_CURRENT_10965']
    jerry = rows['RS_CURRENT_10965']
    check('CURRENT_empty_authority_native_Jerry_Adams_prospective_binding_frozen', ids[0] == 'RS_CURRENT_10965' and jerry['name'] == native_binding['native_personal_name'] == 'Jerry Adams' and jerry['source_authorised_full_name'] == native_binding['native_authority_field'] == '' and native_binding['new_admission_exception'] is False and native_binding == plan['native_identity_bindings']['RS_CURRENT_10965'])
    check('archived_native_snapshot_equals_stored_complete_objects', all(row == rows[row['record_id']] for row in native_snapshot))
    check('V43_zero_fact_six_hold_partition_preserved', json.loads((NEW / 'inputs/v43_accepted_geography.json').read_text()) == [] and len(json.loads((NEW / 'inputs/v43_followup_holds.json').read_text())) == 6 and {row['record_id'] for row in json.loads((NEW / 'inputs/v43_followup_holds.json').read_text())} == set(old_ids) and json.loads((NEW / 'inputs/v43_reviewed_record_ids.json').read_text()) == old_ids)
    check('scope_hash_and_baseline_match_plan', digest(W / 'v44_method_application_scope.json') == plan['method_application_scope_sha256'] == '3575db7b377008a55d4c6876c23ce6b6f67fc8b50dce40b7dddc01fcf8523e65' and scope['baseline_commit'] == plan['baseline_commit'] == '0f50abe91b8e4c1f7faf13f652cf988a5c3303df' and scope['baseline_canonical_sha256'] == plan['baseline_canonical_sha256'] == canonical.hexdigest())
    with tempfile.TemporaryDirectory(prefix='v44_cheap_preflight_') as temp:
        root = Path(temp)
        (root / 'scripts').mkdir()
        (root / 'audit').mkdir()
        shutil.copyfile(NEW / 'scripts/replay.py', root / 'scripts/replay.py')
        for path in (OLD / 'audit').glob('method_application_scope*.json'):
            shutil.copyfile(path, root / 'audit' / path.name)
        shutil.copyfile(OLD / 'audit/method_preregistration.json', root / 'audit/method_preregistration.json')
        shutil.copyfile(W / 'v44_method_application_scope.json', root / 'audit/method_application_scope_v44.json')
        spec = importlib.util.spec_from_file_location('v44_cheap_structure', root / 'scripts/replay.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        check('ROOT_derived_from_temporary_script_without_substitution', module.ROOT == root)
        gates = [(37, 'method_application_scope.json', module.apply_v37_geography)] + [(v, 'method_application_scope_v' + str(v) + '.json', getattr(module, 'apply_v' + str(v) + '_geography')) for v in range(38, 45)]
        check('all_eight_scope_hashes_at_original_runtime_paths', len(gates) == 8 and all(digest(root / 'audit' / name) == getattr(module, 'V' + str(version) + '_APPLICATION_SCOPE_SHA256') for version, name, _ in gates))
        check('all_seven_legacy_scope_bytes_equal_prospective_scope_pins', all(digest(root / 'audit' / name) == expected for name, expected in scope['legacy_application_scope_file_sha256'].items()))
        check('unchanged_V36_method_hash_and_proof_modes', digest(root / 'audit/method_preregistration.json') == module.V44_METHOD_PREREGISTRATION_SHA256 == 'b76b7ad55125b1cf2dffe7d847d013f7fb8c2a6c8868c66f1e3060efae471147' and module.V44_PROOF_MODES == module.V43_PROOF_MODES and module.V44_METHOD_ID == module.V43_METHOD_ID)
        expected_apply = old_functions['apply_v43_geography'].replace('v43', 'v44').replace('V43', 'V44').replace('V42_SOURCE_COMMIT', 'V43_SOURCE_COMMIT').replace('EXPECTED_V42_CANONICAL', 'EXPECTED_V43_CANONICAL')
        check('current_admission_guards_exact_prior_version_substitution', new_functions['apply_v44_geography'] == expected_apply)
        for version, name, gate in gates:
            path = root / 'audit' / name
            original = path.read_bytes()
            path.write_bytes(original + b' ')
            try:
                reject('V' + str(version) + '_scope_hash_gate_empty_arguments', lambda gate=gate: gate([], [], [], []), 'Current application scope changed')
            finally:
                path.write_bytes(original)
        path = root / 'audit/method_preregistration.json'
        original = path.read_bytes()
        path.write_bytes(original + b' ')
        try:
            for version, _, gate in gates:
                reject('V' + str(version) + '_base_hash_gate_empty_arguments', lambda gate=gate: gate([], [], [], []), 'Historical V36 preregistration changed')
        finally:
            path.write_bytes(original)

        def fact_for(record_id, mode, hemisphere):
            row = rows[record_id]
            edge = dict(source_url='https://example.invalid/v44-synthetic-person', source_node_label='Synthetic person', edge_property='Synthetic direct born-region wording', tool_ref='synthetic_no_acquisition', locator='Synthetic only', acquisition_role='synthetic_fixture', target_kind='literal', target_label='Synthetic whole region', target_uri=None)
            fact = dict(record_id=record_id, native_dob=row['dob'], authority_name=row['source_authorised_full_name'], frozen_raw_birthplace=row['raw_birthplace'], source_grade='S3', method_id=module.V44_METHOD_ID, proof_mode=mode, method_preregistration_sha256=module.V44_METHOD_PREREGISTRATION_SHA256, method_application_scope_sha256=module.V44_APPLICATION_SCOPE_SHA256, source_birthdate=row['dob'], observed_source_full_name=row['source_authorised_full_name'] or row['name'], source_url=edge['source_url'], source_locator='Synthetic only', source_quote='Synthetic only', source_birthdate_precision='synthetic_exact_day', identity_review=['Synthetic only'], place_binding_review=['Synthetic only'], geographic_basis='Synthetic only', reviewed_hemisphere=hemisphere, proof_chain=[edge])
            if not row['source_authorised_full_name']:
                fact['native_full_name'] = row['name']
            if mode != module.V44_PROOF_MODES[0]:
                edge.update(edge_property='P19' if mode == module.V44_PROOF_MODES[2] else 'Synthetic observed born-place hyperlink', target_kind='entity', target_label='Synthetic locality', target_uri='https://example.invalid/v44-synthetic-locality')
                fact['proof_chain'].append(dict(source_url=edge['target_uri'], source_node_label='Synthetic locality', edge_property='P131' if mode == module.V44_PROOF_MODES[2] else 'Synthetic region wording', tool_ref='synthetic_no_acquisition', locator='Synthetic only', acquisition_role='synthetic_fixture', target_kind='entity' if mode == module.V44_PROOF_MODES[2] else 'literal', target_label='Synthetic whole region', target_uri='https://example.invalid/v44-synthetic-region' if mode == module.V44_PROOF_MODES[2] else None))
            return fact

        fixture_ids = [ids[0], ids[2], ids[4]]
        facts = [fact_for(record_id, mode, hemisphere) for record_id, mode, hemisphere in zip(fixture_ids, module.V44_PROOF_MODES, ['north', 'south', 'north'])]
        before = [rows[record_id] for record_id in fixture_ids]
        after, changes = module.apply_v44_geography(before, facts, targets, ids)
        check('three_synthetic_proof_modes_accept', len(changes) == 3 and {change['after_hemisphere'] for change in changes} == {'north', 'south'})
        check('three_mode_complete_object_rollback_exact', rollback(after, module.V44_GEOGRAPHY_FIELD) == before)
        check('only_six_GEO_FIELDS_plus_new_context_may_change', len(module.GEO_FIELDS) == 6 and all(set(b) - set(a) == {module.V44_GEOGRAPHY_FIELD} and all(a[key] == b[key] for key in a if key not in module.GEO_FIELDS) for a, b in zip(before, after)))
        check('geographic_support_only_original_DOB_BP_roles_frozen', all(row[module.V44_GEOGRAPHY_FIELD]['source_grade_role'] == 'geographic_support_only' and row[module.V44_GEOGRAPHY_FIELD]['native_DOB_source_grade_unchanged'] and row[module.V44_GEOGRAPHY_FIELD]['original_birthplace_fields_and_source_grades_unchanged'] for row in after))
        check('CURRENT_fallback_acceptance_preserves_native_name_and_empty_authority', facts[0]['authority_name'] == '' and facts[0]['native_full_name'] == 'Jerry Adams' and after[0]['name'] == 'Jerry Adams' and after[0]['source_authorised_full_name'] == '' and rollback([after[0]], module.V44_GEOGRAPHY_FIELD) == [jerry])
        untouched_id = ids[1]
        untouched, no_changes = module.apply_v44_geography([rows[untouched_id]], [], targets, ids)
        check('untargeted_complete_row_unchanged', untouched == [rows[untouched_id]] and no_changes == [])
        fact = facts[0]
        def one(value, row=None):
            return module.apply_v44_geography([rows[fixture_ids[0]] if row is None else row], [value], [fixture_ids[0]], [fixture_ids[0]])
        missing_native_name = copy.deepcopy(fact)
        missing_native_name.pop('native_full_name')
        reject('CURRENT_missing_native_full_name_rejected', lambda: one(missing_native_name), '')
        wrong_native_name = copy.deepcopy(fact)
        wrong_native_name['native_full_name'] = 'Jerry McKee Adams'
        reject('CURRENT_alias_cannot_replace_native_full_name', lambda: one(wrong_native_name), '')
        repaired_authority = copy.deepcopy(fact)
        repaired_authority['authority_name'] = 'Jerry Adams'
        reject('CURRENT_native_empty_authority_cannot_be_repaired', lambda: one(repaired_authority), 'Native authority name must match exactly')
        for key, value, expected in [('method_id', 'wrong', 'Missing or wrong prospective method'), ('proof_mode', 'wrong', 'Unsupported prospective proof mode'), ('source_grade', 'S2', 'Prospective v44 method is S3 geography support only'), ('method_application_scope_sha256', 'wrong', 'Fact is not bound to current application scope'), ('method_preregistration_sha256', 'wrong', 'Fact is not bound to unchanged method preregistration'), ('observed_source_full_name', '', 'Actual observed source full name is required'), ('source_birthdate', '1800-01-01', 'Actual source exact DOB must match native'), ('native_dob', '1800-01-01', 'Native DOB must match exactly'), ('authority_name', 'wrong', 'Native authority name must match exactly'), ('frozen_raw_birthplace', 'wrong', 'Stored birthplace must match exactly'), ('proof_chain', [], 'Actual source/edge chain is required'), ('source_birthdate_precision', '', 'Explicit source date precision is required'), ('reviewed_hemisphere', 'unknown', 'Geography-only acceptance must resolve a hemisphere'), ('previous_geography_fields', {}, 'Previous geography fields must match exactly'), ('previous_absent_geography_fields', ['invented'], 'Previous absent geography fields must match exactly'), ('source_quote', '', 'Empty quote needs structured birth evidence'), ('source_quote', ' '.join(['synthetic'] * 26), ''), ('source_url', '', ''), ('source_locator', '', ''), ('identity_review', [], ''), ('place_binding_review', [], ''), ('geographic_basis', '', '')]:
            bad = copy.deepcopy(fact)
            bad[key] = value
            reject('new_fact_guard_' + key + '_' + str(len(checks)), lambda bad=bad: one(bad), expected)
        for key in ['source_url', 'source_node_label', 'edge_property', 'tool_ref', 'locator', 'acquisition_role', 'target_label']:
            bad = copy.deepcopy(fact)
            bad['proof_chain'][0][key] = ''
            reject('proof_observation_guard_' + key, lambda bad=bad: one(bad), 'Incomplete source/edge observation')
        for variant, expected in [('unknown_target_kind', 'Target kind must be explicit'), ('entity_without_URI', 'Entity target needs actual URI'), ('literal_with_URI', 'Literal region must not receive an invented URI'), ('nonterminal_literal', 'Nonterminal chain target must be an actual entity'), ('linked_single_edge', 'Linked place proof needs person and target observations'), ('P19_terminal_literal', 'P19/P131 proof requires actual entity targets throughout'), ('P19_missing_P131', 'P19/P131 proof needs both acquired edges')]:
            bad = copy.deepcopy(fact)
            edge = bad['proof_chain'][0]
            if variant == 'unknown_target_kind':
                edge['target_kind'] = 'guessed'
            elif variant == 'entity_without_URI':
                edge['target_kind'] = 'entity'
            elif variant == 'literal_with_URI':
                edge['target_uri'] = 'https://example.invalid/invented'
            elif variant == 'nonterminal_literal':
                bad['proof_mode'] = module.V44_PROOF_MODES[1]
                bad['proof_chain'].append(copy.deepcopy(edge))
            elif variant == 'linked_single_edge':
                bad['proof_mode'] = module.V44_PROOF_MODES[1]
            else:
                bad = fact_for(fixture_ids[0], module.V44_PROOF_MODES[2], 'north')
                if variant == 'P19_terminal_literal':
                    bad['proof_chain'][-1].update(target_kind='literal', target_uri=None)
                else:
                    bad['proof_chain'][-1]['edge_property'] = 'P17'
            reject('proof_shape_guard_' + variant, lambda bad=bad: one(bad), expected)
        mini = copy.deepcopy(rows[fixture_ids[0]])
        mini.pop('reason', None)
        mini.pop('northern_birthplace_candidate', None)
        mini_after, _ = one(fact, mini)
        check('absent_GEO_FIELDS_rollback_exact', rollback(mini_after, module.V44_GEOGRAPHY_FIELD) == [mini] and {'reason', 'northern_birthplace_candidate'} <= set(mini_after[0][module.V44_GEOGRAPHY_FIELD]['previous_absent_geography_fields']))
        old_csv, new_csv = root / 'prior194.csv', root / 'current200.csv'
        module.write_csv_v43(old_csv, after)
        module.write_csv_v44(new_csv, after)
        with old_csv.open(newline='') as handle:
            old_header, *old_cells = list(csv.reader(handle))
        with new_csv.open(newline='') as handle:
            new_header, *new_cells = list(csv.reader(handle))
        check('CSV194_prior_positions_and_cell_meanings_preserved', len(old_header) == 194 and len(new_header) == 200 and new_header[:194] == old_header and all(a == b[:194] for a, b in zip(old_cells, new_cells)))
        check('CSV_six_current_columns_and_context_values_correct', all(name.startswith('v44_') for name in new_header[194:]) and all(len(cells) == 200 and cells[-6:] == [row[module.V44_GEOGRAPHY_FIELD]['reviewed_hemisphere'], 'S3', row[module.V44_GEOGRAPHY_FIELD]['source_url'], 'synthetic_exact_day', 'geographic_support_only', 'v44'] for cells, row in zip(new_cells, after)))
        for version in range(37, 41):
            historical = json.loads((NEW / ('inputs/v' + str(version) + '_accepted_geography.json')).read_text())[0]
            record_id = historical['record_id']
            restored = rollback([rows[record_id]], getattr(module, 'V' + str(version) + '_GEOGRAPHY_FIELD'))[0]
            gate = getattr(module, 'apply_v' + str(version) + '_geography')
            reapplied, old_changes = gate([restored], [historical], [record_id], [record_id])
            check('historical_V' + str(version) + '_storedrow_exact_rollback_reapply', reapplied == [rows[record_id]] and len(old_changes) == 1)
            for key, expected in [('method_application_scope_sha256', 'Fact is not bound to current application scope'), ('method_preregistration_sha256', 'Fact is not bound to unchanged method preregistration')]:
                bad = copy.deepcopy(historical)
                bad[key] = 'wrong'
                reject('historical_V' + str(version) + '_fact_binding_' + key, lambda bad=bad, gate=gate, record_id=record_id, restored=restored: gate([restored], [bad], [record_id], [record_id]), expected)
    return dict(written_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), status='pass', check_count=len(checks), checks=checks, elapsed_seconds=round(time.monotonic() - start, 3), replay_script_sha256=digest(NEW / 'scripts/replay.py'), scope_sha256=digest(W / 'v44_method_application_scope.json'), historical_functions_preserved=69, historical_assignments_preserved=144, total_functions=73, total_assignments=152, archived_input_files=129, native_snapshot_carried_exact=True, prior_CSV_columns_preserved=194, CSV_columns=200, fixed_nonblank_unknown_window_pool=54, fixed_followups=5, expensive_historical_loads_run=0, CLI_runs=0, production_current_decisions_audits_outputs_written=False, source_semantics_validated=False, limits='Synthetic observations are not acquired source facts. This fresh cheap check streams stored V43 objects and exercises isolated structural/hash/rollback/CSV contracts only. Root source QA and production/final sequential CLI runs remain separate. V42 original171/112/48/56 attestations, fresh101source/55structure/58preflight+twoCLI+sixfinish recovery results, and V43 original188source/92cheap/61finalpreflight+twoCLI+sixfinish results remain distinct historical evidence.')

if __name__ == '__main__':
    try:
        report = run()
    except Exception as error:
        report = dict(written_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), status='fail', check_count=len(checks), checks=checks, elapsed_seconds=round(time.monotonic() - start, 3), error_type=type(error).__name__, error=str(error), traceback=traceback.format_exc(), expensive_historical_loads_run=0, CLI_runs=0)
        history_path = W / 'v44_replay_preflight_failures.json'
        history = json.loads(history_path.read_text()) if history_path.exists() else []
        history.append(report)
        history_path.write_text(json.dumps(history, indent=2) + '\n')
        OUT.write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps(report))
        raise
    OUT.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))
