"""Cheap additive V43 checks: no historical loader and no replay CLI."""
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
OLD = W / 'academy_repo/studies/royal_society_birthplace_completion_v42'
NEW = OLD.with_name('royal_society_birthplace_completion_v43')
OUT = W / 'v43_replay_preflight.json'
CURRENT = {'accepted_geography.json', 'geography_target_ids.json', 'geography_followup_ids.json', 'reviewed_record_ids.json', 'reviewed_native_rows.json'}
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
    check('all65_historical_functions_literal', len(old_functions) == 65 and all(new_functions.get(k) == v for k, v in old_functions.items()))
    check('all136_historical_assignments_literal', len(old_assignments) == 136 and all(v in new_assignments for v in old_assignments))
    check('exact_additive69_functions144_assignments', len(new_functions) == 69 and len(new_assignments) == 144 and set(new_functions) - set(old_functions) == {'load_v42', 'apply_v43_geography', 'write_csv_v43', 'main_v43'})
    check('baseline_V42_code_hash_verified', digest(OLD / 'scripts/replay.py') == '01b29beee4f90dc8f10f1c4322f4d345683ec26601d82c2a690730c37c8eb290')
    check('CLI_entry_calls_additive_main_v43', (NEW / 'scripts/replay.py').read_text().endswith("if __name__ == '__main__':\n    main_v43()\n"))
    mapping = {path.name: 'v42_' + path.name if path.name in CURRENT else path.name for path in (OLD / 'inputs').iterdir()}
    check('all124_prior_inputs_mapped_without_dropping_native_snapshot', len(mapping) == 124 and set(CURRENT) <= set(mapping) and all((NEW / 'inputs' / target).read_bytes() == (OLD / 'inputs' / source).read_bytes() for source, target in mapping.items()))
    check('six_V42_current_carriers_and_holds_byte_exact', all((NEW / 'inputs' / ('v42_' + name)).read_bytes() == (OLD / 'inputs' / name).read_bytes() for name in CURRENT) and (NEW / 'inputs/v42_followup_holds.json').read_bytes() == (OLD / 'audit/followup_holds.json').read_bytes())
    native_snapshot = json.loads((NEW / 'inputs/v42_reviewed_native_rows.json').read_text())
    check('native_snapshot_original_SHA256', digest(NEW / 'inputs/v42_reviewed_native_rows.json') == '421972d5602749d5df23d8d240e76883b0509e12803e882b17f3209120039065')
    ids = json.loads((NEW / 'inputs/geography_followup_ids.json').read_text())
    targets = json.loads((NEW / 'inputs/geography_target_ids.json').read_text())
    old_ids = json.loads((NEW / 'inputs/v42_geography_followup_ids.json').read_text())
    plan = json.loads((W / 'v43_plan.json').read_text())
    scope = json.loads((W / 'v43_method_application_scope.json').read_text())
    check('fixed_six_followups_match_plan_scope_in_order', ids == sum(plan['geography_followup_groups'].values(), []) == scope['fixed_record_ids'] and len(ids) == len(set(ids)) == 6 and set(ids) <= set(targets))
    check('native_snapshot_six_V42_ids_preserved_in_original_order', len(native_snapshot) == 6 and [row['record_id'] for row in native_snapshot] == old_ids)
    needed = set(ids) | set(old_ids)
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
    check('stored_V42_canonical_hash_exact_without_historical_load', canonical.hexdigest() == 'a0c04e44631478f82e562deab64d699fc273e6fc99fa35ba23f8a61d7e1f8717')
    check('stored_baseline4983_counts_and_blank_boundaries', count == 4983 and overall == {'north': 4205, 'south': 187, 'unknown': 591} and window_count == 2644 and window == {'north': 2305, 'south': 182, 'unknown': 157} and all_blank == 525 and window_blank == 103)
    check('target54_matches_streamed_stored_baseline', targets == sorted(target_expected) and len(targets) == 54)
    check('all_cheap_fixture_rows_found', set(rows) == needed)
    check('archived_native_snapshot_equals_stored_complete_objects', all(row == rows[row['record_id']] for row in native_snapshot))
    check('V42_zero_fact_six_hold_partition_preserved', json.loads((NEW / 'inputs/v42_accepted_geography.json').read_text()) == [] and len(json.loads((NEW / 'inputs/v42_followup_holds.json').read_text())) == 6 and {row['record_id'] for row in json.loads((NEW / 'inputs/v42_followup_holds.json').read_text())} == set(old_ids) and json.loads((NEW / 'inputs/v42_reviewed_record_ids.json').read_text()) == old_ids)
    check('scope_hash_and_baseline_match_plan', digest(W / 'v43_method_application_scope.json') == plan['method_application_scope_sha256'] == 'b25ef3f4bbf1f3e5dddd48531812a60e40d1383b897a0d3d044b0604e62db212' and scope['baseline_commit'] == plan['baseline_commit'] == 'ad014a89fad3f6fe257f7f5c3f6c50c7c5b74caf' and scope['baseline_canonical_sha256'] == plan['baseline_canonical_sha256'] == canonical.hexdigest())
    with tempfile.TemporaryDirectory(prefix='v43_cheap_preflight_') as temp:
        root = Path(temp)
        (root / 'scripts').mkdir()
        (root / 'audit').mkdir()
        shutil.copyfile(NEW / 'scripts/replay.py', root / 'scripts/replay.py')
        for path in (OLD / 'audit').glob('method_application_scope*.json'):
            shutil.copyfile(path, root / 'audit' / path.name)
        shutil.copyfile(OLD / 'audit/method_preregistration.json', root / 'audit/method_preregistration.json')
        shutil.copyfile(W / 'v43_method_application_scope.json', root / 'audit/method_application_scope_v43.json')
        spec = importlib.util.spec_from_file_location('v43_cheap_structure', root / 'scripts/replay.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        check('ROOT_derived_from_temporary_script_without_substitution', module.ROOT == root)
        gates = [(37, 'method_application_scope.json', module.apply_v37_geography)] + [(v, 'method_application_scope_v' + str(v) + '.json', getattr(module, 'apply_v' + str(v) + '_geography')) for v in range(38, 44)]
        check('all_seven_scope_hashes_at_original_runtime_paths', len(gates) == 7 and all(digest(root / 'audit' / name) == getattr(module, 'V' + str(version) + '_APPLICATION_SCOPE_SHA256') for version, name, _ in gates))
        check('all_six_legacy_scope_bytes_equal_prospective_scope_pins', all(digest(root / 'audit' / name) == expected for name, expected in scope['legacy_application_scope_file_sha256'].items()))
        check('unchanged_V36_method_hash_and_proof_modes', digest(root / 'audit/method_preregistration.json') == module.V43_METHOD_PREREGISTRATION_SHA256 == 'b76b7ad55125b1cf2dffe7d847d013f7fb8c2a6c8868c66f1e3060efae471147' and module.V43_PROOF_MODES == module.V42_PROOF_MODES and module.V43_METHOD_ID == module.V42_METHOD_ID)
        expected_apply = old_functions['apply_v42_geography'].replace('v42', 'v43').replace('V42', 'V43').replace('V41_SOURCE_COMMIT', 'V42_SOURCE_COMMIT').replace('EXPECTED_V41_CANONICAL', 'EXPECTED_V42_CANONICAL')
        check('current_admission_guards_exact_prior_version_substitution', new_functions['apply_v43_geography'] == expected_apply)
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
            edge = dict(source_url='https://example.invalid/v43-synthetic-person', source_node_label='Synthetic person', edge_property='Synthetic direct born-region wording', tool_ref='synthetic_no_acquisition', locator='Synthetic only', acquisition_role='synthetic_fixture', target_kind='literal', target_label='Synthetic whole region', target_uri=None)
            fact = dict(record_id=record_id, native_dob=row['dob'], authority_name=row['source_authorised_full_name'], frozen_raw_birthplace=row['raw_birthplace'], source_grade='S3', method_id=module.V43_METHOD_ID, proof_mode=mode, method_preregistration_sha256=module.V43_METHOD_PREREGISTRATION_SHA256, method_application_scope_sha256=module.V43_APPLICATION_SCOPE_SHA256, source_birthdate=row['dob'], observed_source_full_name=row['source_authorised_full_name'], source_url=edge['source_url'], source_locator='Synthetic only', source_quote='Synthetic only', source_birthdate_precision='synthetic_exact_day', identity_review=['Synthetic only'], place_binding_review=['Synthetic only'], geographic_basis='Synthetic only', reviewed_hemisphere=hemisphere, proof_chain=[edge])
            if mode != module.V43_PROOF_MODES[0]:
                edge.update(edge_property='P19' if mode == module.V43_PROOF_MODES[2] else 'Synthetic observed born-place hyperlink', target_kind='entity', target_label='Synthetic locality', target_uri='https://example.invalid/v43-synthetic-locality')
                fact['proof_chain'].append(dict(source_url=edge['target_uri'], source_node_label='Synthetic locality', edge_property='P131' if mode == module.V43_PROOF_MODES[2] else 'Synthetic region wording', tool_ref='synthetic_no_acquisition', locator='Synthetic only', acquisition_role='synthetic_fixture', target_kind='entity' if mode == module.V43_PROOF_MODES[2] else 'literal', target_label='Synthetic whole region', target_uri='https://example.invalid/v43-synthetic-region' if mode == module.V43_PROOF_MODES[2] else None))
            return fact

        fixture_ids = [ids[0], ids[3], ids[5]]
        facts = [fact_for(record_id, mode, hemisphere) for record_id, mode, hemisphere in zip(fixture_ids, module.V43_PROOF_MODES, ['north', 'south', 'north'])]
        before = [rows[record_id] for record_id in fixture_ids]
        after, changes = module.apply_v43_geography(before, facts, targets, ids)
        check('three_synthetic_proof_modes_accept', len(changes) == 3 and {change['after_hemisphere'] for change in changes} == {'north', 'south'})
        check('three_mode_complete_object_rollback_exact', rollback(after, module.V43_GEOGRAPHY_FIELD) == before)
        check('only_six_GEO_FIELDS_plus_new_context_may_change', len(module.GEO_FIELDS) == 6 and all(set(b) - set(a) == {module.V43_GEOGRAPHY_FIELD} and all(a[key] == b[key] for key in a if key not in module.GEO_FIELDS) for a, b in zip(before, after)))
        check('geographic_support_only_original_DOB_BP_roles_frozen', all(row[module.V43_GEOGRAPHY_FIELD]['source_grade_role'] == 'geographic_support_only' and row[module.V43_GEOGRAPHY_FIELD]['native_DOB_source_grade_unchanged'] and row[module.V43_GEOGRAPHY_FIELD]['original_birthplace_fields_and_source_grades_unchanged'] for row in after))
        untouched_id = ids[1]
        untouched, no_changes = module.apply_v43_geography([rows[untouched_id]], [], targets, ids)
        check('untargeted_complete_row_unchanged', untouched == [rows[untouched_id]] and no_changes == [])
        fact = facts[0]
        def one(value, row=None):
            return module.apply_v43_geography([rows[fixture_ids[0]] if row is None else row], [value], [fixture_ids[0]], [fixture_ids[0]])
        for key, value, expected in [('method_id', 'wrong', 'Missing or wrong prospective method'), ('proof_mode', 'wrong', 'Unsupported prospective proof mode'), ('source_grade', 'S2', 'Prospective v43 method is S3 geography support only'), ('method_application_scope_sha256', 'wrong', 'Fact is not bound to current application scope'), ('method_preregistration_sha256', 'wrong', 'Fact is not bound to unchanged method preregistration'), ('observed_source_full_name', '', 'Actual observed source full name is required'), ('source_birthdate', '1800-01-01', 'Actual source exact DOB must match native'), ('native_dob', '1800-01-01', 'Native DOB must match exactly'), ('authority_name', 'wrong', 'Native authority name must match exactly'), ('frozen_raw_birthplace', 'wrong', 'Stored birthplace must match exactly'), ('proof_chain', [], 'Actual source/edge chain is required'), ('source_birthdate_precision', '', 'Explicit source date precision is required'), ('reviewed_hemisphere', 'unknown', 'Geography-only acceptance must resolve a hemisphere'), ('previous_geography_fields', {}, 'Previous geography fields must match exactly'), ('previous_absent_geography_fields', ['invented'], 'Previous absent geography fields must match exactly'), ('source_quote', '', 'Empty quote needs structured birth evidence'), ('source_quote', ' '.join(['synthetic'] * 26), ''), ('source_url', '', ''), ('source_locator', '', ''), ('identity_review', [], ''), ('place_binding_review', [], ''), ('geographic_basis', '', '')]:
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
                bad['proof_mode'] = module.V43_PROOF_MODES[1]
                bad['proof_chain'].append(copy.deepcopy(edge))
            elif variant == 'linked_single_edge':
                bad['proof_mode'] = module.V43_PROOF_MODES[1]
            else:
                bad = fact_for(fixture_ids[0], module.V43_PROOF_MODES[2], 'north')
                if variant == 'P19_terminal_literal':
                    bad['proof_chain'][-1].update(target_kind='literal', target_uri=None)
                else:
                    bad['proof_chain'][-1]['edge_property'] = 'P17'
            reject('proof_shape_guard_' + variant, lambda bad=bad: one(bad), expected)
        mini = copy.deepcopy(rows[fixture_ids[0]])
        mini.pop('reason', None)
        mini.pop('northern_birthplace_candidate', None)
        mini_after, _ = one(fact, mini)
        check('absent_GEO_FIELDS_rollback_exact', rollback(mini_after, module.V43_GEOGRAPHY_FIELD) == [mini] and {'reason', 'northern_birthplace_candidate'} <= set(mini_after[0][module.V43_GEOGRAPHY_FIELD]['previous_absent_geography_fields']))
        old_csv, new_csv = root / 'prior188.csv', root / 'current194.csv'
        module.write_csv_v42(old_csv, after)
        module.write_csv_v43(new_csv, after)
        with old_csv.open(newline='') as handle:
            old_header, *old_cells = list(csv.reader(handle))
        with new_csv.open(newline='') as handle:
            new_header, *new_cells = list(csv.reader(handle))
        check('CSV188_prior_positions_and_cell_meanings_preserved', len(old_header) == 188 and len(new_header) == 194 and new_header[:188] == old_header and all(a == b[:188] for a, b in zip(old_cells, new_cells)))
        check('CSV_six_current_columns_and_context_values_correct', all(name.startswith('v43_') for name in new_header[188:]) and all(len(cells) == 194 and cells[-6:] == [row[module.V43_GEOGRAPHY_FIELD]['reviewed_hemisphere'], 'S3', row[module.V43_GEOGRAPHY_FIELD]['source_url'], 'synthetic_exact_day', 'geographic_support_only', 'v43'] for cells, row in zip(new_cells, after)))
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
    return dict(written_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), status='pass', check_count=len(checks), checks=checks, elapsed_seconds=round(time.monotonic() - start, 3), replay_script_sha256=digest(NEW / 'scripts/replay.py'), scope_sha256=digest(W / 'v43_method_application_scope.json'), historical_functions_preserved=65, historical_assignments_preserved=136, total_functions=69, total_assignments=144, archived_input_files=124, native_snapshot_carried_exact=True, prior_CSV_columns_preserved=188, CSV_columns=194, fixed_nonblank_unknown_window_pool=54, fixed_followups=6, expensive_historical_loads_run=0, CLI_runs=0, production_current_decisions_audits_outputs_written=False, source_semantics_validated=False, limits='Synthetic observations are not acquired source facts. This fresh cheap check streams stored V42 objects and exercises isolated structural/hash/rollback/CSV contracts only. Root source QA and production/final sequential CLI runs remain separate. V42 original171/112/48/56 attestations and fresh101source/55structure/58preflight+twoCLI+sixfinish recovery results remain distinct historical evidence.')

if __name__ == '__main__':
    try:
        report = run()
    except Exception as error:
        report = dict(written_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), status='fail', check_count=len(checks), checks=checks, elapsed_seconds=round(time.monotonic() - start, 3), error_type=type(error).__name__, error=str(error), traceback=traceback.format_exc(), expensive_historical_loads_run=0, CLI_runs=0)
        history_path = W / 'v43_replay_preflight_failures.json'
        history = json.loads(history_path.read_text()) if history_path.exists() else []
        history.append(report)
        history_path.write_text(json.dumps(history, indent=2) + '\n')
        OUT.write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps(report))
        raise
    OUT.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))
