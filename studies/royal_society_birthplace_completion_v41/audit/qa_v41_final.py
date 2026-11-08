"""Independent local-only final QA. Run only after root's production clean-exit signal."""
import ast, concurrent.futures, copy, csv, datetime, gc, gzip, hashlib
import importlib.util, json, pathlib, shutil, subprocess, sys, tempfile, traceback
from collections import Counter

sys.dont_write_bytecode = True
W = pathlib.Path('/workspace/scratch/262552d8c0f0')
S = W / 'academy_repo/studies/royal_society_birthplace_completion_v41'
OLD = S.with_name('royal_society_birthplace_completion_v40')
EXPECTED_BASE = 'a0c04e44631478f82e562deab64d699fc273e6fc99fa35ba23f8a61d7e1f8717'
BASE_COMMIT = 'e9bf9e01a20d3cb651a78ac90d2b5c9ca8fdad1c'
BASE_METHOD = 'b76b7ad55125b1cf2dffe7d847d013f7fb8c2a6c8868c66f1e3060efae471147'
SCOPE_HASHES = {
    'method_application_scope.json': 'ae080b06f8abad9ed7575783486795c977e44ce5e5024bfa2096e16816a44d94',
    'method_application_scope_v38.json': 'bd7540715a6b4649ffe79371e38ee2b650bd0176013fbb5418efa02b8995fad0',
    'method_application_scope_v39.json': 'cc12b3159a035064dbde6a35e0778642fdb25d988e9e399617b216062127b17e',
    'method_application_scope_v40.json': 'b44c66bc0d7883aeef9650578d0b339a65b563942da3fe72976b05c0094cc1fc',
    'method_application_scope_v41.json': 'd6ebcba7aa672c1a4877857bd4e9b4072af2ae159c04fd0dddf4d7766d2e3176',
}
GEO_FIELDS = {'hemisphere', 'geo_resolution_status', 'geography_decision', 'reason',
              'northern_birthplace_candidate', 'southern_birthplace_separate'}
SIDECARS = ['active_source_DOB_conflicts.json', 'birthplace_source_conflicts.json',
    'source_derived_age_inconsistencies.json', 'provisional_parsed_date_discrepancies.json',
    'lifespan_endpoint_discrepancies.json', 'cross_source_reported_age_contrasts.json',
    'source_date_precision_holds.json', 'omitted_middle_name_admission.json',
    'source_ordinal_age_wording_observations.json']
checks = []
def read(p): return json.loads(p.read_text())
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def rows(p): return [json.loads(x) for x in gzip.decompress(p.read_bytes()).splitlines()]
def canonical(rs): return b''.join((json.dumps(r, ensure_ascii=False, sort_keys=True, separators=(',', ':'))+'\n').encode() for r in rs)
def check(name, condition):
    assert condition, name
    checks.append(name)
def module_at(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
def window(r): return '1835-01-01' <= r['dob'] <= '1985-12-31'
def issue_records(obj): return obj.get('records', []) if isinstance(obj, dict) else obj
def sourceqa_inventory_counts(old_obj, new_obj):
    metadata = isinstance(old_obj, dict) and 'records' not in old_obj
    assert metadata == (isinstance(new_obj, dict) and 'records' not in new_obj)
    return {'baseline_records': None if metadata else len(issue_records(old_obj)),
            'current_records': None if metadata else len(issue_records(new_obj)),
            'inventory_shape': 'metadata_without_records' if metadata else 'records'}

def inventory_counts_match(actual, old_obj, new_obj):
    expected = sourceqa_inventory_counts(old_obj, new_obj)
    if not isinstance(actual, dict) or actual.get('inventory_shape') != expected['inventory_shape']:
        return False
    for k in ['baseline_records', 'current_records']:
        if k not in actual:
            return False
        if expected[k] is None:
            if actual[k] not in (None, 'N/A', 'N_A'):
                return False
        elif type(actual[k]) is not int or actual[k] != expected[k]:
            return False
    return True

def main():
    E = read(W/'v41_final_qa_expectations.json')
    expected_final = E['final_canonical_sha256']; expected_ids = set(E['accepted_record_ids'])
    expected_source_counts = E['source_counts']
    approved_issue_appends = E.get('approved_issue_appends', {})
    check('only explicit root-authorized issue append inventories allowed; omitted-middle metadata always exact',
          isinstance(approved_issue_appends, dict) and set(approved_issue_appends) <= set(SIDECARS)-{'omitted_middle_name_admission.json'})
    check('root final canonical adopted IDs and source-count expectations supplied before QA',
          len(expected_final) == 64 and isinstance(E['accepted_record_ids'], list) and isinstance(expected_source_counts, dict))
    pinfile = S/'audit/main_output_before_QA_sha256.json'
    pins = read(pinfile)['files']; pinfile_sha = sha(pinfile)
    check('five completed production output pins match before QA',
          set(pins) == {'birthplace_rows.jsonl.gz', 'birthplaces.csv', 'changes.json', 'remaining_unknown_window.csv', 'summary.json'}
          and all(sha(S/'outputs'/name) == h for name, h in pins.items()))
    reviewed_paths = [p for p in S.rglob('*') if p.is_file() and 'outputs' not in p.relative_to(S).parts and '__pycache__' not in p.parts]
    reviewed_input_pins = {str(p.relative_to(S)): sha(p) for p in reviewed_paths}
    before = rows(OLD/'outputs/birthplace_rows.jsonl.gz'); after = rows(S/'outputs/birthplace_rows.jsonl.gz')
    final_canonical = hashlib.sha256(canonical(after)).hexdigest()
    check('V40 baseline and V41 current canonical match root pins',
          hashlib.sha256(canonical(before)).hexdigest() == EXPECTED_BASE and final_canonical == expected_final)
    m = module_at('v41IndependentFinalQA', S/'scripts/replay.py')
    reconstructed = m.load_v40()
    check('self-contained V40 reconstruction all4983 complete objects exact',
          len(before) == len(after) == len(reconstructed) == 4983 and reconstructed == before)
    del reconstructed
    prior_current_inputs = {'accepted_geography.json', 'geography_followup_ids.json', 'geography_target_ids.json', 'reviewed_record_ids.json'}
    check('all inherited source inputs byte exact with prior current inputs versioned V40',
          all(p.read_bytes() == (S/'inputs'/('v40_'+p.name if p.name in prior_current_inputs else p.name)).read_bytes()
              for p in (OLD/'inputs').iterdir() if p.is_file())
          and (S/'inputs/v40_followup_holds.json').read_bytes() == (OLD/'audit/followup_holds.json').read_bytes())
    old_source = (OLD/'scripts/replay.py').read_text(); new_source = (S/'scripts/replay.py').read_text()
    old_ast = ast.parse(old_source); new_ast = ast.parse(new_source)
    old_funcs = {n.name: ast.get_source_segment(old_source, n) for n in old_ast.body if isinstance(n, ast.FunctionDef)}
    new_funcs = {n.name: ast.get_source_segment(new_source, n) for n in new_ast.body if isinstance(n, ast.FunctionDef)}
    check('all old functions including historical write_csv and main remain verbatim',
          len(old_funcs) == 57 and all(new_funcs.get(k) == v for k, v in old_funcs.items()))
    old_assign = {ast.dump(n.targets[0]): ast.get_source_segment(old_source, n) for n in old_ast.body if isinstance(n, ast.Assign) and len(n.targets) == 1}
    new_assign = {ast.dump(n.targets[0]): ast.get_source_segment(new_source, n) for n in new_ast.body if isinstance(n, ast.Assign) and len(n.targets) == 1}
    check('all old assignments hashes scopes and constants remain verbatim', len(old_assign) == 120 and all(new_assign.get(k) == v for k, v in old_assign.items()))
    guards = [node for node in new_ast.body if isinstance(node, ast.If) and isinstance(node.test, ast.Compare) and isinstance(node.test.left, ast.Name) and node.test.left.id == '__name__']
    entry_calls = [node.func.id for guard in guards for node in ast.walk(guard) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)]
    check('new current CLI entrypoint invokes main_v41 without historical main', callable(m.main_v41) and callable(m.write_csv_v41) and entry_calls == ['main_v41'])
    check('record order unique keys and UK cohort remain fixed',
          [r['record_id'] for r in before] == [r['record_id'] for r in after]
          and len({r['record_id'] for r in after}) == 4983 and {r['cohort'] for r in after} == {'UK_Royal_Society'})
    facts = read(S/'inputs/accepted_geography.json'); holds = read(S/'audit/followup_holds.json')
    ids = read(S/'inputs/reviewed_record_ids.json'); followups = read(S/'inputs/geography_followup_ids.json')
    targets = read(S/'inputs/geography_target_ids.json'); plan = read(S/'audit/plan.json')
    check('production plan preserves complete prospective V41 plan bytes and fixed groups',
          (S/'audit/plan.json').read_bytes() == (W/'v41_plan.json').read_bytes()
          and plan['geography_followup_groups'] == read(W/'v41_plan.json')['geography_followup_groups'])
    fids = {f['record_id'] for f in facts}; hids = {h['record_id'] for h in holds}; n = len(facts)
    inputfacts = {f['record_id']: f for f in facts}
    expected_targets = [r['record_id'] for r in before if window(r) and r['hemisphere'] == 'unknown' and r.get('raw_birthplace')]
    check('54 stored-place unknown targets and6 fixed complete disjoint outcomes',
          targets == expected_targets and len(targets) == len(set(targets)) == 54
          and len(ids) == len(set(ids)) == 6 and set(ids) == set(followups) == fids | hids
          and len(facts) == len(fids) and fids == expected_ids and len(holds) == len(hids) == 6-n
          and not fids & hids and set(ids) <= set(targets))
    check('three groups two each match prospective plan with no first-place inputs',
          len(plan['geography_followup_groups']) == 3 and all(len(g) == 2 for g in plan['geography_followup_groups'].values())
          and set(sum(plan['geography_followup_groups'].values(), [])) == set(ids)
          and plan['first_birthplace_followup_groups'] == {} and not (S/'inputs/accepted_birthplaces.json').exists())
    check('exact six mutable geography fields and current context declared', m.GEO_FIELDS == GEO_FIELDS and m.V41_GEOGRAPHY_FIELD == 'geography_followup_v41')
    changed = [a['record_id'] for b, a in zip(before, after) if b != a]
    check('changed complete object set exactly equals accepted IDs', set(changed) == fids and len(changed) == n and sum(b == a for b, a in zip(before, after)) == 4983-n)
    for b, a in zip(before, after):
        rid = a['record_id']
        if rid not in fids:
            assert a == b, rid; continue
        assert b['hemisphere'] == 'unknown' and b['raw_birthplace'] and window(b)
        assert set(b) <= set(a) and set(a)-set(b) <= GEO_FIELDS | {'geography_followup_v41'}
        assert all(a[k] == b[k] for k in b if k not in GEO_FIELDS), rid
        f = a['geography_followup_v41']
        assert a['hemisphere'] == inputfacts[rid]['reviewed_hemisphere'], rid
        assert f['native_dob'] == b['dob'] and f['authority_name'] == b['source_authorised_full_name']
        assert f['frozen_raw_birthplace'] == b['raw_birthplace'] and f['frozen_birthplace_source_grade'] == b['birthplace_source_grade']
        assert f['source_grade_role'] == 'geographic_support_only' and f['native_DOB_source_grade_unchanged'] is True and f['original_birthplace_fields_and_source_grades_unchanged'] is True
        prior = f['previous_geography_fields']; absent = f['previous_absent_geography_fields']
        assert prior == {k: b[k] for k in GEO_FIELDS if k in b} and set(absent) == GEO_FIELDS-set(b)
        expected_context = copy.deepcopy(inputfacts[rid])
        expected_context.update(previous_geography_fields=prior, previous_absent_geography_fields=sorted(absent),
                                source_grade_role='geographic_support_only', native_DOB_source_grade_unchanged=True,
                                original_birthplace_fields_and_source_grades_unchanged=True)
        assert f == expected_context, rid
        restored = copy.deepcopy(a); del restored['geography_followup_v41']; restored.update(prior)
        for k in absent: restored.pop(k, None)
        assert restored == b, rid
    check('all native BP identity tier prior-context objects frozen with exact rollback', True)
    bb = {r['record_id']: r for r in before}; aa = {r['record_id']: r for r in after}
    blank_ids = [r['record_id'] for r in before if window(r) and not r.get('raw_birthplace')]
    check('all103 window blank and525 overall blank complete objects unchanged',
          len(blank_ids) == 103 and sum(not r.get('raw_birthplace') for r in before) == 525
          and all(b == a for b, a in zip(before, after) if not b.get('raw_birthplace')))
    check('all current holds preserve complete master objects', all(bb[r] == aa[r] for r in hids))
    check('all original raw birthplaces and grades remain exact',
          all(a['raw_birthplace'] == b['raw_birthplace'] and a.get('birthplace_source_grade') == b.get('birthplace_source_grade') for b, a in zip(before, after)))
    scope_path = S/'audit/method_application_scope_v41.json'; scope = read(scope_path)
    check('base method and all5 application scopes match independent fixed hashes',
          sha(S/'audit/method_preregistration.json') == BASE_METHOD
          and all(sha(S/'audit'/name) == h for name, h in SCOPE_HASHES.items())
          and all((S/'audit'/name).read_bytes() == (OLD/'audit'/name).read_bytes() for name in SCOPE_HASHES if name != scope_path.name))
    check('current scope reuses rules with exact prospective IDs and baseline',
          set(scope['fixed_record_ids']) == set(ids) and scope['baseline_commit'] == BASE_COMMIT
          and scope['baseline_canonical_sha256'] == EXPECTED_BASE and scope['method_preregistration_sha256'] == BASE_METHOD
          and scope['rules_unchanged'] is True and scope['method_amendment_created'] is False
          and scope['scope_application_extension'] is True and scope['no_new_admission_method_exception'] is True)
    ff = {f['record_id']: f for f in facts}; modes = set(read(S/'audit/method_preregistration.json')['proof_modes'])
    for rid, f in ff.items():
        assert f['source_grade'] == 'S3' and f['source_grade_role'] == 'geographic_support_only'
        assert f['method_id'] == 'uk-geography-canonical-community-reference-pilot-v1'
        assert f['method_preregistration_sha256'] == BASE_METHOD and f['method_application_scope_sha256'] == SCOPE_HASHES[scope_path.name]
        assert f['source_birthdate'] == f['native_dob'] == bb[rid]['dob']
        assert f['frozen_raw_birthplace'] == bb[rid]['raw_birthplace'] and f['frozen_birthplace_source_grade'] == bb[rid]['birthplace_source_grade']
        assert f['source_body_ref'] and f['source_locator'] and f['identity_review'] and f['place_binding_review'] and f['geographic_basis']
        assert f['reviewed_hemisphere'] in {'north', 'south'} and f['proof_mode'] in modes
        assert f['source_quote_word_count'] == len(f['source_quote'].split()) <= 25
        assert all(f.get(k) is None for k in ['raw_HTTP_status', 'raw_bytes_sha256', 'exact_request_utc'])
        chain = f['proof_chain']; assert chain
        for i, edge in enumerate(chain):
            assert all(isinstance(edge.get(k), str) and edge[k].strip() for k in ['source_url', 'source_node_label', 'edge_property', 'tool_ref', 'locator', 'acquisition_role', 'target_label'])
            assert edge['target_kind'] in {'entity', 'literal'}
            assert bool(edge['target_uri']) if edge['target_kind'] == 'entity' else edge['target_uri'] is None
            if i < len(chain)-1:
                assert edge['target_kind'] == 'entity' and edge['target_uri'] == chain[i+1]['source_url']
        if f['proof_mode'] == 'explicit_person_born_place_hyperlink_then_actual_target_place_region':
            assert len(chain) >= 2 and chain[0]['target_kind'] == 'entity'
            assert chain[0]['target_uri'] == chain[1]['source_url']
        if f['proof_mode'] == 'actual_person_P19_entity_then_actual_P131_admin_chain_to_whole_region':
            assert len(chain) >= 2 and all(e['target_kind'] == 'entity' for e in chain)
    check('current facts bind frozen identity DOB scope roles and actual typed proof chains', True)
    new_hemi = Counter(f['reviewed_hemisphere'] for f in facts); new_grades = Counter(f['source_grade'] for f in facts)
    overall = Counter(r['hemisphere'] for r in after); win = [r for r in after if window(r)]; wc = Counter(r['hemisphere'] for r in win)
    summary = read(S/'outputs/summary.json')
    check('independent overall and2644 native-window totals',
          overall == {'north': 4205+new_hemi['north'], 'south': 187+new_hemi['south'], 'unknown': 591-n}
          and len(win) == 2644 and wc == {'north': 2305+new_hemi['north'], 'south': 182+new_hemi['south'], 'unknown': 157-n}
          and summary['overall'] == overall and summary['native_dob_window_counts'] == wc)
    diag = {'all_blank_raw_birthplace': sum(not r.get('raw_birthplace') for r in after), 'window_blank_raw_birthplace': sum(not r.get('raw_birthplace') for r in win),
        'all_unknown': sum(r['hemisphere'] == 'unknown' for r in after), 'all_unknown_with_blank_raw_birthplace': sum(r['hemisphere'] == 'unknown' and not r.get('raw_birthplace') for r in after),
        'all_unknown_with_nonblank_raw_birthplace': sum(r['hemisphere'] == 'unknown' and bool(r.get('raw_birthplace')) for r in after),
        'window_unknown': sum(r['hemisphere'] == 'unknown' for r in win), 'window_unknown_with_blank_raw_birthplace': sum(not r.get('raw_birthplace') for r in win if r['hemisphere'] == 'unknown'),
        'window_unknown_with_nonblank_raw_birthplace': sum(bool(r.get('raw_birthplace')) for r in win if r['hemisphere'] == 'unknown')}
    check('all blank and stored-place unknown diagnostics recomputed',
          diag == summary['remaining_blank_current_fields'] and diag['window_unknown_with_blank_raw_birthplace'] == 103
          and diag['window_unknown_with_nonblank_raw_birthplace'] == 54-n and diag['all_unknown_with_blank_raw_birthplace'] == 525 and diag['all_unknown_with_nonblank_raw_birthplace'] == 66-n)
    check('summary current baseline zero newBP geographic grades scope and unchanged rows exact',
          summary['baseline_v40_source_commit'] == BASE_COMMIT and summary['baseline_v40_canonical_jsonl_sha256'] == EXPECTED_BASE
          and summary['new_birthplaces'] == summary['new_first_birthplace_records'] == summary['new_primary_person_birthplace_observations'] == summary['new_geographic_resolutions_from_new_birthplaces'] == 0
          and summary['new_geographic_resolutions'] == summary['new_geography_only_resolutions'] == n and summary['new_birthplace_source_grade_counts'] == {}
          and summary['new_geographic_support_grade_counts'] == new_grades and summary['fixed_geography_followups'] == summary['actual_unique_reviewed_records'] == 6
          and summary['fixed_first_birthplace_source_followups'] == 0 and summary['frozen_nonblank_unknown_window_geography_pool'] == 54
          and summary['followup_held_records'] == 6-n and summary['unchanged_complete_rows'] == 4983-n and not summary['DOB_calendar_identity_eligibility_modified'])
    changes = read(S/'outputs/changes.json')
    check('changes contain only accepted geography refinements with originalBP unchanged',
          len(changes) == n and {c['record_id'] for c in changes} == fids
          and all(c['change_type'] == 'geography_only' and c['before_raw_birthplace'] == c['after_raw_birthplace'] == bb[c['record_id']]['raw_birthplace']
                  and c['before_birthplace_source_grade'] == c['after_birthplace_source_grade'] == bb[c['record_id']]['birthplace_source_grade']
                  and c['geographic_support_grade'] == ff[c['record_id']]['source_grade'] and c['source_grade_role'] == 'geographic_support_only' for c in changes))
    with (OLD/'outputs/birthplaces.csv').open(newline='') as fh: oldcsv = list(csv.DictReader(fh)); oldcols = list(oldcsv[0])
    with (S/'outputs/birthplaces.csv').open(newline='') as fh: newcsv = list(csv.DictReader(fh)); newcols = list(newcsv[0])
    check('CSV176 prior columns retain positions plus6 current columns equals182',
          len(oldcols) == 176 and len(newcols) == 182 and newcols[:176] == oldcols
          and newcols[176:] == ['v41_geographic_hemisphere', 'v41_geographic_support_grade', 'v41_geography_source_url', 'v41_source_birthdate_precision', 'v41_geographic_support_grade_role', 'v41_geo_context_version'])
    for b, a in zip(oldcsv, newcsv):
        assert b['record_id'] == a['record_id']
        assert all(b[col] == a[col] for col in oldcols if not (a['record_id'] in fids and col == 'hemisphere')), a['record_id']
    for r, a in zip(after, newcsv):
        assert all(a[k] == r[k] for k in ['record_id', 'dob', 'raw_birthplace', 'hemisphere'])
        f = r.get('geography_followup_v41', {})
        expected_csv = [f.get('reviewed_hemisphere', ''), f.get('source_grade', ''), f.get('source_url', ''), f.get('source_birthdate_precision', ''), f.get('source_grade_role', ''), 'v41' if f else '']
        assert [a[k] for k in newcols[176:]] == expected_csv
    check('all4983 CSV rows preserve prior meanings except accepted current hemisphere', len(oldcsv) == len(newcsv) == 4983)
    with (S/'outputs/remaining_unknown_window.csv').open(newline='') as fh:
        unknown_reader = csv.DictReader(fh); unknowncols = unknown_reader.fieldnames; unknowncsv = list(unknown_reader)
    unknownids = [r['record_id'] for r in win if r['hemisphere'] == 'unknown']
    check('remaining unknown CSV equals all182 current master CSV values and native-window order',
          len(unknowncsv) == 157-n and unknowncols == newcols and [r['record_id'] for r in unknowncsv] == unknownids
          and unknowncsv == [row for row in newcsv if row['record_id'] in set(unknownids)])
    issue_appends = {}
    for name in SIDECARS:
        old_obj = read(OLD/'audit'/name); new_obj = read(S/'audit'/name)
        old_records = issue_records(old_obj); new_records = issue_records(new_obj)
        appended = new_records[len(old_records):]; issue_appends[name] = len(appended)
        assert new_records[:len(old_records)] == old_records and len(new_records) >= len(old_records), name
        if appended:
            if isinstance(old_obj, dict):
                assert isinstance(new_obj, dict) and {k: v for k, v in old_obj.items() if k != 'records'} == {k: v for k, v in new_obj.items() if k != 'records'}, name
            assert name in approved_issue_appends and [r['record_id'] for r in appended] == approved_issue_appends[name], name
            assert all(r['record_id'] in hids and r['record_id'] not in fids for r in appended), name
            snap = S/'audit'/('prior_v40_'+name)
            assert snap.exists() and snap.read_bytes() == (OLD/'audit'/name).read_bytes(), name
        else:
            assert not approved_issue_appends.get(name), name
            assert (S/'audit'/name).read_bytes() == (OLD/'audit'/name).read_bytes(), name
    conf = read(S/'audit/active_source_DOB_conflicts.json'); oldconf = read(OLD/'audit/active_source_DOB_conflicts.json')
    age_old = issue_records(read(OLD/'audit/source_derived_age_inconsistencies.json')); age_current = issue_records(read(S/'audit/source_derived_age_inconsistencies.json'))
    check('all9 sidecars exact unless explicit held-only qualified append with prior snapshot', len(SIDECARS) == 9 and len(oldconf['records']) == 13 and len(age_old) == 4)
    check('Waterfield Spath Desty Pedler and partialplace records preserve complete old observations',
          age_current[:4] == age_old and len(read(OLD/'audit/birthplace_source_conflicts.json')['records']) == 2 and len(read(S/'audit/birthplace_source_conflicts.json')['records']) >= 2)
    spath = next(r for r in age_old if r['record_id'] == 'RS_PAST_NA1611')
    birth = datetime.date.fromisoformat(spath['observed_source_birthdate']); death = datetime.date.fromisoformat(spath['observed_source_death_date'])
    computed = death.year-birth.year-((death.month, death.day) < (birth.month, birth.day))
    check('Spath retains nativeDOB and completed74 against stated75 as age-only issue',
          computed == spath['arithmetic_age_from_observed_dates'] == 74 and spath['observed_reported_age'] == 75
          and bb['RS_PAST_NA1611'] == aa['RS_PAST_NA1611'] and aa['RS_PAST_NA1611']['dob'] == spath['observed_source_birthdate'])
    check('all prior activeDOB and current conflict subjects preserve complete master objects',
          not {c['record_id'] for c in oldconf['records']} & set(ids)
          and all(bb[c['record_id']] == aa[c['record_id']] for c in conf['records'])
          and all(bb[c['record_id']] == aa[c['record_id']] for c in read(S/'audit/birthplace_source_conflicts.json')['records']))
    check('historical Adam nativeDOB and untargeted complete object remain unchanged', bb['RS_PAST_NA4918'] == aa['RS_PAST_NA4918'] and aa['RS_PAST_NA4918']['dob'] == '1891-11-05' and 'RS_PAST_NA4918' not in ids)
    priorfiles = list((OLD/'audit').glob('prior_*'))
    check('all inherited historical audit files remain byte exact', bool(priorfiles) and all(p.read_bytes() == (S/'audit'/p.name).read_bytes() for p in priorfiles))
    historical = read(S/'audit/prior_v29_first_pass_queue_closeout.json')
    check('V29 historical first-pass audit retains V29 canonical and same103 blank IDs',
          historical['current_canonical_jsonl_sha256'] == 'e528b4afce6ded29ff6af749b4d46a8d7b9d0bce7d57d34ac8f1366421bbce73'
          and historical['current_canonical_jsonl_sha256'] != final_canonical and historical['remaining_blank_record_ids'] == blank_ids
          and historical['first_pass_queue_complete'] is True and historical['birthplace_coverage_complete'] is False)
    h35 = S/'audit/prior_v35_geography_first_pass_queue_closeout.json'
    check('V35 historical queue remains exact oldhash and no misleading current closeout',
          h35.read_bytes() == (OLD/'audit'/h35.name).read_bytes() and sha(h35) == '56fd3053935afc42fe2f9cf301bb66bc2bc6839fa9483467cd03e602fb61be3b'
          and read(h35)['baseline_canonical_jsonl_sha256'] == '271a32070f8dae8c54933f1ebaacc5ae141427a3448f8f1562000f8842a0c632'
          and not (S/'audit/geography_first_pass_queue_closeout.json').exists())
    check('separate Ewins Barber holds and Thompson historical notes remain inherited exact',
          {e['record_id'] for e in plan['preselection_conflict_exclusions']} == {'RS_PAST_NA9209', 'RS_PAST_NA8779'}
          and not {'RS_PAST_NA9209', 'RS_PAST_NA8779'} & set(ids)
          and all((S/'audit'/name).read_bytes() == (OLD/'audit'/name).read_bytes() for name in ['thompson_historical_context.json', 'thompson_context_provenance_note.json']))
    prereg = S/'audit/method_preregistration.json'
    check('historical V36 preregistration retains original six IDs and exact bytes',
          sha(prereg) == BASE_METHOD and prereg.read_bytes() == (W/'v36_method_preregistration.json').read_bytes()
          and set(read(prereg)['fixed_record_ids']) == set(read(S/'inputs/v36_reviewed_record_ids.json')))
    sourceclass = read(S/'audit/source_class_adjudication.json')
    check('current source class reuses base method and scope with geography-only role',
          sourceclass['method_amendment_created'] is False and sourceclass['no_new_admission_method_exception'] is True
          and sourceclass['method_preregistration_sha256'] == BASE_METHOD and sourceclass['method_application_scope_sha256'] == sha(scope_path)
          and sourceclass['source_grade_role'] == 'geographic_support_only' and set(sourceclass['adopted_record_ids']) == fids)
    sourceqa = read(S/'audit/independent_source_qa.json')
    check('sourceQA passed with exact shape checks facts and sixGEO roles',
          sourceqa['passed'] is True and sourceqa['phase'] == 'final' and sourceqa['blocking_issues'] == [] and sourceqa['checks_passed'] == len(sourceqa['checks'])
          and all(c['passed'] for c in sourceqa['checks']) and sourceqa['accepted_fact_path'] == 'inputs/accepted_geography.json'
          and sourceqa['accepted_fact_sha256_at_review'] == sourceqa['accepted_geography_sha256_at_review'] == sha(S/'inputs/accepted_geography.json')
          and set(sourceqa['declared_six_GEO_FIELDS']) == GEO_FIELDS and sourceqa['no_new_admission_method_exception'] is True
          and sourceqa['explicit_prospective_admission_method_amendment'] is False)
    qa_bindings = {'followup_holds_sha256_at_review': 'audit/followup_holds.json',
        'parent_adjudication_sha256_at_review': 'audit/parent_adjudication.json',
        'root_followups_sha256_at_review': 'audit/root_followups.json',
        'root_intent_sha256_at_review': 'audit/root_intent.json',
        'active_DOB_conflicts_sha256_at_review': 'audit/active_source_DOB_conflicts.json',
        'birthplace_source_conflicts_sha256_at_review': 'audit/birthplace_source_conflicts.json',
        'source_derived_age_inconsistencies_sha256_at_review': 'audit/source_derived_age_inconsistencies.json',
        'source_class_adjudication_sha256_at_review': 'audit/source_class_adjudication.json',
        'method_preregistration_sha256_at_review': 'audit/method_preregistration.json',
        'method_schema_sha256_at_review': 'METHOD_SCHEMA.md',
        'method_application_scope_sha256_at_review': 'audit/method_application_scope_v41.json',
        'legacy_V37_method_application_scope_sha256_at_review': 'audit/method_application_scope.json',
        'legacy_V38_method_application_scope_sha256_at_review': 'audit/method_application_scope_v38.json',
        'legacy_V39_method_application_scope_sha256_at_review': 'audit/method_application_scope_v39.json',
        'legacy_V40_method_application_scope_sha256_at_review': 'audit/method_application_scope_v40.json',
        'historical_v35_geography_first_pass_queue_closeout_sha256_at_review': 'audit/prior_v35_geography_first_pass_queue_closeout.json',
        'historical_v29_first_pass_queue_closeout_sha256_at_review': 'audit/prior_v29_first_pass_queue_closeout.json'}
    check('sourceQA binds all current source roles schema inventories base legacy and current scopes', all(sourceqa[k] == sha(S/path) for k, path in qa_bindings.items()))
    check('sourceQA binds each current worker report and prospective intent',
          sourceqa['worker_source_report_sha256_at_review'] == {g: sha(S/'audit'/f'sources_{g}.json') for g in 'abc'}
          and sourceqa['worker_intent_sha256_at_review'] == {g: sha(S/'audit'/f'{g}_intent.json') for g in 'abc'})
    check('sourceQA exact adopted IDs and actual proof modes without UK-only terminal whitelist',
          {f['record_id'] for f in sourceqa['accepted_geographic_bindings']} == fids
          and {f['proof_mode'] for f in sourceqa['accepted_geographic_bindings']} == {f['proof_mode'] for f in facts})
    for binding in sourceqa['accepted_geographic_bindings']:
        f = ff[binding['record_id']]
        assert binding['native_DOB'] == f['native_dob'] and binding['native_authority'] == f['authority_name']
        assert binding['source_birthdate'] == f['source_birthdate'] and binding['frozen_raw_birthplace'] == f['frozen_raw_birthplace']
        assert binding['frozen_BP_source_grade'] == f['frozen_birthplace_source_grade'] and binding['proof_chain'] == f['proof_chain']
        assert binding['new_geographic_grade'] == f['source_grade'] and binding['new_hemisphere'] == f['reviewed_hemisphere'] and binding['proof_mode'] == f['proof_mode']
    check('sourceQA current native bindings proofchain hemisphere and support grade equal exact facts', True)
    inv_hashes = sourceqa['nine_issue_inventory_sha256_at_review']; inv_counts = sourceqa['nine_issue_inventory_counts_at_review']
    check('sourceQA independently binds all9 baseline current inventory files and counts',
          set(inv_hashes) == set(inv_counts) == set(SIDECARS)
          and all(inv_hashes[name] == {'baseline_sha256': sha(OLD/'audit'/name), 'current_sha256': sha(S/'audit'/name)}
              and inventory_counts_match(inv_counts[name], read(OLD/'audit'/name), read(S/'audit'/name)) for name in SIDECARS))
    documentary_path = S/'audit/v41_source_documentary_case_review.json'
    documentary = read(documentary_path); protocol = sourceqa['documentary_protocol_review']
    documentary_pins = {
        'audit/v41_source_documentary_case_review.json': sourceqa['documentary_semantic_case_review_sha256_at_review'],
        'audit/'+protocol['quote_prefinal_report_path']: protocol['quote_prefinal_report_sha256'],
        'audit/'+protocol['worker_operation_prefinal_report_path']: protocol['worker_operation_prefinal_report_sha256']}
    check('sourceQA documentary case quote and operation artifacts bind exact production copies',
          all(sha(S/path) == h and (S/path).read_bytes() == (W/pathlib.Path(path).name).read_bytes() for path, h in documentary_pins.items()))
    check('sourceQA exact six documentary cases retain native identity DOB and frozen place',
          sourceqa['documentary_semantic_case_reviews'] == documentary['case_reviews']
          and len(documentary['case_reviews']) == 6 and {c['record_id'] for c in documentary['case_reviews']} == set(ids)
          and all(c['native_name'] == bb[c['record_id']]['name']+' '+bb[c['record_id']]['source_authorised_full_name'].split(';', 1)[0] and c['native_DOB'] == bb[c['record_id']]['dob']
                  and c['frozen_place'] == bb[c['record_id']]['raw_birthplace'] for c in documentary['case_reviews']))
    artifact_paths = {'facts': 'inputs/accepted_geography.json', 'holds': 'audit/followup_holds.json',
        'parent': 'audit/parent_adjudication.json', 'root': 'audit/root_followups.json', 'root_intent': 'audit/root_intent.json',
        **{'worker_'+g: 'audit/sources_'+g+'.json' for g in 'abc'}, **{'worker_intent_'+g: 'audit/'+g+'_intent.json' for g in 'abc'}}
    check('documentary case review binds exact retained facts holds parent root and all worker reports and intents',
          documentary['artifact_sha256'] == {key: sha(S/path) for key, path in artifact_paths.items()})
    dist = [p for p in S.rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    check('no full-source caches PDF images or raw-source artifacts distributed',
          not any(p.suffix.lower() in {'.html', '.htm', '.pdf', '.png', '.jpg', '.jpeg', '.webp', '.har', '.ttl', '.rdf'} for p in dist)
          and not any('cache' in p.name.lower() for p in dist))
    docs = {name: (S/name).read_text() for name in ['README.md', 'CONTINUATION.md']}
    doc_hashes = {name: sha(S/name) for name in docs}
    check('final README and continuation carry current canonical version and no placeholder labels',
          all(expected_final in v and 'v41' in v.lower() and not any(t in v for t in ['AWAIT_', 'PLACEHOLDER', 'PENDING']) for v in docs.values()))
    parent = read(S/'audit/parent_adjudication.json'); root = read(S/'audit/root_followups.json')
    check('parent adjudication reflects current baseline and geography-only outcomes',
          parent['baseline_commit'] == BASE_COMMIT and parent['decisions']['new_birthplaces'] == 0
          and parent['decisions']['geography_only_resolutions'] == n and parent['decisions']['held'] == 6-n)
    check('actual source request accounting equals root declared final counts', parent['source_counts'] == expected_source_counts)
    workers = [read(W/f'v41_sources_{g}.json') for g in 'abc']
    qops = sum(sum(len(q.get('queries', [q.get('query')])) for q in r['query_ledger']) for r in workers)
    navs = [o for r in workers for o in r['navigation_ledger']]
    opens = sum(o.get('kind', o.get('operation')) in {'open', 'cached_context_open'} for o in navs)
    clicks = sum(o.get('kind', o.get('operation')) == 'click' for o in navs)
    finds = sum(len(r.get('parsed_find_ledger', [])) for r in workers); rc = root['counts']
    recomputed = {'worker_queries': qops, 'root_queries': rc['discovery_queries'], 'total_queries': qops+rc['discovery_queries'],
        'worker_navigation_attempts': len(navs), 'worker_source_open_operations': opens, 'worker_click_operations': clicks,
        'root_source_opens': rc['source_open_operations'], 'root_click_operations': rc['click_operations'],
        'total_navigation_attempts': len(navs)+rc['source_open_operations']+rc['click_operations'],
        'total_source_open_operations': opens+rc['source_open_operations'], 'total_click_operations': clicks+rc['click_operations'],
        'worker_parsed_finds': finds, 'root_parsed_finds': rc['parsed_finds'], 'total_parsed_finds': finds+rc['parsed_finds'],
        'screenshots': sum(r['retrieval_counts']['screenshots'] for r in workers)+rc['screenshots'], 'raw_GETs': sum(r['retrieval_counts']['raw_GETs'] for r in workers)+rc['raw_GETs']}
    check('source tool counts independently recomputed from worker ledgers and root observations',
          recomputed == expected_source_counts
          and rc['source_open_operations'] == sum(o['operation'] == 'open' for o in root['observations'])
          and rc['click_operations'] == sum(o['operation'] == 'click' for o in root['observations'])
          and rc['discovery_queries'] == sum(o['operation'] == 'query' or o['operation'].endswith('_query') for o in root['observations'])
          and rc['parsed_finds'] == sum(o['operation'] in {'find', 'parsed_find'} for o in root['observations'])
          and len(root['observations']) == rc['source_open_operations']+rc['click_operations']+rc['discovery_queries']+rc['parsed_finds']
          and opens+clicks == len(navs))
    check('worker reports copied byte exact', all((S/'audit'/f'sources_{g}.json').read_bytes() == (W/f'v41_sources_{g}.json').read_bytes() for g in 'abc'))
    check('parent issue totals agree with exact-preserved sidecars and any qualified appends',
          parent['decisions']['new_source_derived_age_inconsistencies'] == issue_appends['source_derived_age_inconsistencies.json']
          and parent['decisions']['total_source_derived_age_inconsistencies'] == len(age_current)
          and parent['decisions']['new_original_DOB_conflicts'] == issue_appends['active_source_DOB_conflicts.json']
          and parent['decisions']['total_active_DOB_conflicts'] == len(conf['records']))
    def replay_run(i):
        with tempfile.TemporaryDirectory(prefix=f'v41independentQA{i}_') as td:
            p = pathlib.Path(td)/'study'; shutil.copytree(S/'inputs', p/'inputs')
            shutil.copytree(S/'scripts', p/'scripts', ignore=shutil.ignore_patterns('__pycache__')); (p/'audit').mkdir()
            for name in ['followup_holds.json', 'method_preregistration.json', *SCOPE_HASHES]:
                shutil.copyfile(S/'audit'/name, p/'audit'/name)
            result = subprocess.run([sys.executable, str(p/'scripts/replay.py')], capture_output=True, text=True)
            assert result.returncode == 0, (i, result.returncode, result.stderr)
            hashes = {name: sha(p/'outputs'/name) for name in pins}
            assert hashes == pins, (i, hashes)
            return {'run': i, 'clean_exit': True, 'five_hashes': hashes, 'matched_original_pins': True}
    print(json.dumps({'stage': 'structural_checks_passed', 'categories': len(checks)}), flush=True)
    terminals = {f['record_id']: {'label': f['proof_chain'][-1]['target_label'], 'kind': f['proof_chain'][-1]['target_kind'], 'uri': f['proof_chain'][-1]['target_uri']} for f in facts}
    quote_words = {f['record_id']: f['source_quote_word_count'] for f in facts}
    # Release every large graph, including local loop references, before two parallel child processes.
    del before, after, bb, aa, win, oldcsv, newcsv, unknowncsv, m, old_ast, new_ast, old_source, new_source
    for name in ['b', 'a', 'r', 'f', 'restored', 'prior', 'chain', 'edge']:
        if name in locals():
            if name == 'b': b = None
            elif name == 'a': a = None
            elif name == 'r': r = None
            elif name == 'f': f = None
            elif name == 'restored': restored = None
            elif name == 'prior': prior = None
            elif name == 'chain': chain = None
            elif name == 'edge': edge = None
    gc.collect()
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex: runs = list(ex.map(replay_run, [1, 2]))
    check('two isolated clean replays match all5 original output pins', len(runs) == 2 and all(r['matched_original_pins'] for r in runs))
    check('production5 outputs and preQA pinfile untouched after QA', all(sha(S/'outputs'/name) == h for name, h in pins.items()) and sha(pinfile) == pinfile_sha)
    check('all reviewed production inputs code scope evidence and sourceQA files untouched during QA',
          all(sha(S/name) == h for name, h in reviewed_input_pins.items()))
    check('final documentation hashes unchanged throughout QA', all(sha(S/name) == h for name, h in doc_hashes.items()))
    report = {'schema': 'UK_v41_geography_only_independent_final_QA_v1', 'reviewer': '/root/v41_final_qa',
        'written_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'status': 'PASS', 'validation_categories_passed': len(checks), 'checks': checks,
        'baseline_canonical_sha256': EXPECTED_BASE, 'final_canonical_sha256': final_canonical, 'records': 4983,
        'changed_complete_objects': n, 'unchanged_complete_objects': 4983-n, 'new_birthplaces': 0, 'geography_only_resolutions': n,
        'accepted_record_ids': sorted(fids), 'source_counts': recomputed,
        'inherited_old_function_count': len(old_funcs), 'inherited_old_assignment_count': len(old_assign), 'current_cli_entrypoint': 'main_v41',
        'documentary_artifact_sha256': documentary_pins, 'sourceQA_documentary_warnings': protocol['retained_warnings'],
        'nine_issue_inventory_sha256_at_review': inv_hashes, 'nine_issue_inventory_counts_at_review': inv_counts, 'overall': dict(overall), 'window_counts': dict(wc), 'blank_diagnostics': diag,
        'main_pre_QA_output_pins': pins, 'pre_QA_pinfile_sha256': pinfile_sha, 'reviewed_input_file_sha256': reviewed_input_pins,
        'isolated_replay_runs': runs, 'main_outputs_rerun_or_mutated': False,
        'root_authorized_issue_appends': approved_issue_appends,
        'issue_inventory_appends': issue_appends, 'active_DOB_conflict_count': len(conf['records']), 'source_derived_age_inconsistency_count': len(age_current),
        'all13_prior_active_DOB_conflict_objects_unchanged': True, 'historical_v29_closeout_hash_preserved': True,
        'historical_v35_closeout_hash_preserved': True, 'explicit_prospective_admission_method_amendment': False,
        'method_application_scope_sha256': sha(scope_path), 'historical_application_scope_sha256': {name: h for name, h in SCOPE_HASHES.items() if name != scope_path.name},
        'quote_words': quote_words, 'geographic_terminal_observations': terminals,
        'documentation_checks': {'files': list(docs), 'counts_scope_limits_consistent': True, 'final_file_sha256': doc_hashes,
            'review_method': 'Direct final README/CONTINUATION reading plus full-object equality, rollback and isolated replay checks. Actual whole-region/source semantics reviewed separately by sourceQA; no UK-only label whitelist or literal-word rejection heuristic.'},
        'limitations': ['Local structural and replay verification only; no network or original-source acquisition or rawHTTP inspection.',
            'Source meanings, source genre, lineage and whole-region geographic sufficiency are independently reviewed in independent_source_qa.json.',
            'S3 roles are geographic_support_only; original DOB/BP fields and tiers remain frozen.',
            'All9 issue inventories preserve old records and exact files unless root explicitly authorizes held-only qualified appends with a prior_v40 file snapshot. V35/V29 queues stay historical; all103 blank-window and525 overall-blank complete objects remain unchanged.',
            'No production facts, inputs, code, outputs, runtime files or Git changed by this reviewer; scratch harness/report/log only.']}
    (W/'v41_final_qa_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'status': 'PASS', 'checks': len(checks), 'two_replays': True, 'canonical': final_canonical}), flush=True)

if __name__ == '__main__':
    try:
        main()
    except BaseException as exc:
        failure = {'schema': 'UK_v41_independent_final_QA_failure_v1', 'status': 'FAIL',
            'written_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'checks_passed_before_failure': checks,
            'error_type': type(exc).__name__, 'error': str(exc), 'traceback': traceback.format_exc(),
            'production_mutated_by_reviewer': False, 'no_network': True}
        (W/'v41_final_qa_failure_report.json').write_text(json.dumps(failure, ensure_ascii=False, indent=2)+'\n')
        raise
