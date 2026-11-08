"""Cheap isolated recovery checks. Never call a historical loader or CLI."""
import ast
import copy
import datetime
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile

W = Path(__file__).resolve().parents[1]
OLD = W / 'academy_repo/studies/royal_society_birthplace_completion_v41'
NEW = OLD.with_name('royal_society_birthplace_completion_v42')
OUT = Path(__file__).with_name('v42_recovered_structure.json')
checks = []

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

def run():
    old_functions, old_assignments = parts(OLD / 'scripts/replay.py')
    new_functions, new_assignments = parts(NEW / 'scripts/replay.py')
    check('all61_historical_functions_literal', len(old_functions) == 61 and all(new_functions.get(k) == v for k, v in old_functions.items()))
    check('all128_historical_assignments_literal', len(old_assignments) == 128 and all(v in new_assignments for v in old_assignments))
    check('exact_additive65_functions136_assignments', len(new_functions) == 65 and len(new_assignments) == 136 and set(new_functions) - set(old_functions) == {'load_v41', 'apply_v42_geography', 'write_csv_v42', 'main_v42'})
    check('recovered_replay_matches_original_observed_code_hash', digest(NEW / 'scripts/replay.py') == '01b29beee4f90dc8f10f1c4322f4d345683ec26601d82c2a690730c37c8eb290')
    current = {'accepted_geography.json', 'geography_target_ids.json', 'geography_followup_ids.json', 'reviewed_record_ids.json'}
    check('all_frozen_V41_input_bytes_preserved', all((NEW / 'inputs' / p.name).read_bytes() == p.read_bytes() for p in (OLD / 'inputs').iterdir() if p.name not in current))
    check('five_V41_carriers_exact', all((NEW / 'inputs' / ('v41_' + n)).read_bytes() == (OLD / 'inputs' / n).read_bytes() for n in current) and (NEW / 'inputs/v41_followup_holds.json').read_bytes() == (OLD / 'audit/followup_holds.json').read_bytes())
    ids = json.loads((NEW / 'inputs/geography_followup_ids.json').read_text())
    targets = json.loads((NEW / 'inputs/geography_target_ids.json').read_text())
    needed = set(ids)
    for version in range(37, 41):
        needed.add(json.loads((NEW / ('inputs/v' + str(version) + '_accepted_geography.json')).read_text())[0]['record_id'])
    rows = {}
    target_expected = []
    count = 0
    with gzip.open(OLD / 'outputs/birthplace_rows.jsonl.gz', 'rt') as handle:
        for line in handle:
            row = json.loads(line)
            count += 1
            if row['record_id'] in needed:
                rows[row['record_id']] = row
            if '1835-01-01' <= row['dob'] <= '1985-12-31' and row['hemisphere'] == 'unknown' and row.get('raw_birthplace'):
                target_expected.append(row['record_id'])
    check('stored_baseline4983_and_target54_fixed6', count == 4983 and targets == sorted(target_expected) and len(targets) == 54 and len(ids) == len(set(ids)) == 6 and set(ids) <= set(targets))
    check('all_cheap_fixture_rows_found', set(rows) == needed)
    facts = json.loads((NEW / 'inputs/accepted_geography.json').read_text())
    reviewed = json.loads((NEW / 'inputs/reviewed_record_ids.json').read_text())
    holds = json.loads((NEW / 'audit/followup_holds.json').read_text())
    check('current_zero_facts_six_reviewed_and_held', facts == [] and len(reviewed) == len(set(reviewed)) == 6 and set(reviewed) == set(ids) and len(holds) == 6 and {hold['record_id'] for hold in holds} == set(ids))
    check('actual_historical_scope_files_original_paths_and_bytes', all((NEW / 'audit' / path.name).read_bytes() == path.read_bytes() for path in (OLD / 'audit').glob('method_application_scope*.json')))
    check('actual_V36_preregistration_bytes_preserved', (NEW / 'audit/method_preregistration.json').read_bytes() == (OLD / 'audit/method_preregistration.json').read_bytes())
    check('actual_current_scope_original_exact_bytes', (NEW / 'audit/method_application_scope_v42.json').read_bytes() == Path(__file__).with_name('method_application_scope_v42.json').read_bytes())
    inventory_names = ['active_source_DOB_conflicts.json', 'birthplace_source_conflicts.json', 'source_derived_age_inconsistencies.json', 'provisional_parsed_date_discrepancies.json', 'lifespan_endpoint_discrepancies.json', 'cross_source_reported_age_contrasts.json', 'source_date_precision_holds.json', 'omitted_middle_name_admission.json', 'source_ordinal_age_wording_observations.json']
    check('all_nine_current_issue_inventory_bytes_preserved', all((NEW / 'audit' / name).read_bytes() == (OLD / 'audit' / name).read_bytes() for name in inventory_names))
    with tempfile.TemporaryDirectory(prefix='v42_recovered_structure_') as temp:
        root = Path(temp)
        (root / 'scripts').mkdir()
        (root / 'audit').mkdir()
        shutil.copyfile(NEW / 'scripts/replay.py', root / 'scripts/replay.py')
        for path in (NEW / 'audit').glob('method_application_scope*.json'):
            shutil.copyfile(path, root / 'audit' / path.name)
        shutil.copyfile(NEW / 'audit/method_preregistration.json', root / 'audit/method_preregistration.json')
        spec = importlib.util.spec_from_file_location('recovered_v42_structure', root / 'scripts/replay.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        check('ROOT_derived_from_temporary_script_without_substitution', module.ROOT == root)
        gates = [(37, 'method_application_scope.json', module.apply_v37_geography)] + [(v, 'method_application_scope_v' + str(v) + '.json', getattr(module, 'apply_v' + str(v) + '_geography')) for v in range(38, 43)]
        check('all_six_scope_hashes_at_original_runtime_paths', all(digest(root / 'audit' / n) == getattr(module, 'V' + str(v) + '_APPLICATION_SCOPE_SHA256') for v, n, _ in gates))
        check('unchanged_V36_method_hash', digest(root / 'audit/method_preregistration.json') == module.V42_METHOD_PREREGISTRATION_SHA256 == 'b76b7ad55125b1cf2dffe7d847d013f7fb8c2a6c8868c66f1e3060efae471147')
        for version, name, gate in gates:
            path = root / 'audit' / name
            original = path.read_bytes()
            path.write_bytes(original + b' ')
            try:
                reject('V' + str(version) + '_scope_hash_gate', lambda gate=gate: gate([], [], [], []), 'Current application scope changed')
            finally:
                path.write_bytes(original)
        path = root / 'audit/method_preregistration.json'
        original = path.read_bytes()
        path.write_bytes(original + b' ')
        try:
            for version, _, gate in gates:
                reject('V' + str(version) + '_base_hash_gate', lambda gate=gate: gate([], [], [], []), 'Historical V36 preregistration changed')
        finally:
            path.write_bytes(original)

        def fact_for(record_id, mode):
            row = rows[record_id]
            observation = dict(source_url='https://example.invalid/synthetic-person', source_node_label='Synthetic person', edge_property='Synthetic direct born-region wording', tool_ref='synthetic_no_acquisition', locator='Synthetic only', acquisition_role='synthetic_fixture', target_kind='literal', target_label='Synthetic whole region', target_uri=None)
            fact = dict(record_id=record_id, native_dob=row['dob'], authority_name=row['source_authorised_full_name'], frozen_raw_birthplace=row['raw_birthplace'], source_grade='S3', method_id=module.V42_METHOD_ID, proof_mode=mode, method_preregistration_sha256=module.V42_METHOD_PREREGISTRATION_SHA256, method_application_scope_sha256=module.V42_APPLICATION_SCOPE_SHA256, source_birthdate=row['dob'], observed_source_full_name=row['source_authorised_full_name'], source_url=observation['source_url'], source_locator='Synthetic only', source_quote='Synthetic only', source_birthdate_precision='synthetic_exact_day', identity_review=['Synthetic only'], place_binding_review=['Synthetic only'], geographic_basis='Synthetic only', reviewed_hemisphere='north', proof_chain=[observation])
            if mode != module.V42_PROOF_MODES[0]:
                observation.update(edge_property='P19' if mode == module.V42_PROOF_MODES[2] else 'Synthetic acquired born-place hyperlink', target_kind='entity', target_label='Synthetic locality', target_uri='https://example.invalid/synthetic-locality')
                second = dict(source_url=observation['target_uri'], source_node_label='Synthetic locality', edge_property='P131' if mode == module.V42_PROOF_MODES[2] else 'Synthetic region wording', tool_ref='synthetic_no_acquisition', locator='Synthetic only', acquisition_role='synthetic_fixture', target_kind='entity' if mode == module.V42_PROOF_MODES[2] else 'literal', target_label='Synthetic whole region', target_uri='https://example.invalid/synthetic-region' if mode == module.V42_PROOF_MODES[2] else None)
                fact['proof_chain'].append(second)
            return fact

        for mode, record_id in zip(module.V42_PROOF_MODES, ids):
            fact = fact_for(record_id, mode)
            after, changes = module.apply_v42_geography([rows[record_id]], [fact], [record_id], [record_id])
            context = after[0].pop(module.V42_GEOGRAPHY_FIELD)
            for key in context['previous_absent_geography_fields']:
                after[0].pop(key, None)
            after[0].update(context['previous_geography_fields'])
            check('synthetic_mode_accept_and_exact_rollback_' + mode, after == [rows[record_id]] and len(changes) == 1)
        fact = fact_for(ids[0], module.V42_PROOF_MODES[0])
        def one(value):
            return module.apply_v42_geography([rows[ids[0]]], [value], [ids[0]], [ids[0]])
        for key, value, expected in [('method_application_scope_sha256', 'wrong', 'Fact is not bound to current application scope'), ('method_preregistration_sha256', 'wrong', 'Fact is not bound to unchanged method preregistration'), ('observed_source_full_name', '', 'Actual observed source full name is required'), ('source_birthdate', '1800-01-01', 'Actual source exact DOB must match native'), ('proof_chain', [], 'Actual source/edge chain is required')]:
            bad = copy.deepcopy(fact)
            bad[key] = value
            reject('new_fact_guard_' + key, lambda bad=bad: one(bad), expected)
        for key in ['source_url', 'source_node_label', 'edge_property', 'tool_ref', 'locator', 'acquisition_role', 'target_label']:
            bad = copy.deepcopy(fact)
            bad['proof_chain'][0][key] = ''
            reject('proof_observation_guard_' + key, lambda bad=bad: one(bad), 'Incomplete source/edge observation')
        for version in range(37, 41):
            historical = json.loads((NEW / ('inputs/v' + str(version) + '_accepted_geography.json')).read_text())[0]
            record_id = historical['record_id']
            restored = copy.deepcopy(rows[record_id])
            context = restored.pop(getattr(module, 'V' + str(version) + '_GEOGRAPHY_FIELD'))
            for key in context['previous_absent_geography_fields']:
                restored.pop(key, None)
            restored.update(context['previous_geography_fields'])
            gate = getattr(module, 'apply_v' + str(version) + '_geography')
            reapplied, changes = gate([restored], [historical], [record_id], [record_id])
            check('historical_V' + str(version) + '_storedrow_exact_rollback_reapply', reapplied == [rows[record_id]] and len(changes) == 1)
            for key, expected in [('method_application_scope_sha256', 'Fact is not bound to current application scope'), ('method_preregistration_sha256', 'Fact is not bound to unchanged method preregistration')]:
                bad = copy.deepcopy(historical)
                bad[key] = 'wrong'
                reject('historical_V' + str(version) + '_fact_binding_' + key, lambda bad=bad, gate=gate, record_id=record_id, restored=restored: gate([restored], [bad], [record_id], [record_id]), expected)
    return dict(written_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), status='pass', check_count=len(checks), checks=checks, replay_script_sha256=digest(NEW / 'scripts/replay.py'), original_replay_bytes_reproduced=True, historical_functions_preserved=61, historical_assignments_preserved=128, total_functions=65, total_assignments=136, expensive_historical_loads_run=0, CLI_runs=0, original_112_check_preflight='Historical attestation only; not rerun or reconstructed as original report bytes', source_semantics_validated=False, environment_interruption_cause='unknown')

if __name__ == '__main__':
    report = run()
    OUT.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))
