"""Independent, memory-bounded V42 recovery QA; production is always read-only.

Use --preflight, --replay 1, --replay 2, then --finish, in that order.
Each replay mode launches exactly one isolated CLI and records its actual exit.
No replay module is imported and no preliminary baseline reconstruction runs.
"""
from __future__ import annotations
import argparse, ast, collections, csv, datetime, gc, gzip, hashlib, itertools
import json, pathlib, shutil, subprocess, sys, tempfile, traceback, uuid

sys.dont_write_bytecode = True
W = pathlib.Path('/workspace/scratch/262552d8c0f0')
S = W/'academy_repo/studies/royal_society_birthplace_completion_v42'
OLD = S.with_name('royal_society_birthplace_completion_v41')
BASE_COMMIT = '5556e7e981f29383187ea201beb1edb22ad04be0'
BASE_CANONICAL = 'a0c04e44631478f82e562deab64d699fc273e6fc99fa35ba23f8a61d7e1f8717'
BASE_METHOD = 'b76b7ad55125b1cf2dffe7d847d013f7fb8c2a6c8868c66f1e3060efae471147'
FIXED_IDS = {'RS_PAST_NA1476','RS_PAST_NA1592','RS_PAST_NA1994','RS_PAST_NA1998','RS_PAST_NA2007','RS_PAST_NA2146'}
SCOPE_HASHES = {
 'method_application_scope.json':'ae080b06f8abad9ed7575783486795c977e44ce5e5024bfa2096e16816a44d94',
 'method_application_scope_v38.json':'bd7540715a6b4649ffe79371e38ee2b650bd0176013fbb5418efa02b8995fad0',
 'method_application_scope_v39.json':'cc12b3159a035064dbde6a35e0778642fdb25d988e9e399617b216062127b17e',
 'method_application_scope_v40.json':'b44c66bc0d7883aeef9650578d0b339a65b563942da3fe72976b05c0094cc1fc',
 'method_application_scope_v41.json':'d6ebcba7aa672c1a4877857bd4e9b4072af2ae159c04fd0dddf4d7766d2e3176',
 'method_application_scope_v42.json':'c5c7594d271b6923725acad91612b8f53b3528383d3bf50f0658ccfa0e639796'}
SIDECARS = ['active_source_DOB_conflicts.json','birthplace_source_conflicts.json',
 'source_derived_age_inconsistencies.json','provisional_parsed_date_discrepancies.json',
 'lifespan_endpoint_discrepancies.json','cross_source_reported_age_contrasts.json',
 'source_date_precision_holds.json','omitted_middle_name_admission.json','source_ordinal_age_wording_observations.json']
OUTPUTS = {'birthplace_rows.jsonl.gz','birthplaces.csv','changes.json','remaining_unknown_window.csv','summary.json'}
CURRENT_COLS = ['v42_geographic_hemisphere','v42_geographic_support_grade','v42_geography_source_url',
 'v42_source_birthdate_precision','v42_geographic_support_grade_role','v42_geo_context_version']
HISTORICAL_ONLY = {'source_QA_checks':171,'original_replay_preflight_checks':112,
 'original_light_final_preflight_checks':48,'original_final_structural_checks':56,
 'original_session_id':88045,'original_final_exit_and_replay_results':'unobserved_after_environment_loss',
 'rerun_or_recreated_by_this_checker':False}
checks=[]
def utc(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def read(p): return json.loads(p.read_text())
def write(p,obj):
 temporary=p.with_name(p.name+'.'+uuid.uuid4().hex+'.writing')
 temporary.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n');temporary.replace(p)
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
 return h.hexdigest()
def ck(name,value):
 if not value: raise AssertionError(name)
 checks.append(name)
def canon(r): return (json.dumps(r,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n').encode()
def win(r): return '1835-01-01'<=r['dob']<='1985-12-31'
def objects(p):
 with gzip.open(p,'rt') as f:
  for line in f:
   if line.strip(): yield json.loads(line)
def csvrows(p):
 with p.open(newline='') as f: yield from csv.DictReader(f)
def relative_path(p):
 q=pathlib.PurePosixPath(p)
 assert not q.is_absolute() and '..' not in q.parts,p
 return S/pathlib.Path(q)
def records(obj): return obj.get('records',[]) if isinstance(obj,dict) else obj
def reviewed_pins():
 return {str(p.relative_to(S)):sha(p) for p in sorted(S.rglob('*')) if p.is_file()
  and 'outputs' not in p.relative_to(S).parts and '__pycache__' not in p.parts}
def check_freeze(report):
 ck('reviewed_existing_production_files_unchanged',all((S/n).is_file() and sha(S/n)==h for n,h in report['reviewed_input_file_sha256'].items()))
 ck('all_five_original_production_output_pins_unchanged',all(sha(S/'outputs'/n)==h for n,h in report['main_output_pins'].items()))
 ck('original_pinfile_unchanged',sha(S/'audit/main_output_before_QA_sha256.json')==report['main_pinfile_sha256'])
def expectation(path):
 e=read(path)
 ck('root_expectations_zero_admissions_no_issue_appends',e['final_canonical_sha256']==BASE_CANONICAL
    and e['accepted_record_ids']==[] and e['approved_issue_appends']=={})
 ck('root_expectation_recovery_source_review_binding',isinstance(e['recovery_source_review_path'],str)
    and len(e['recovery_source_review_sha256'])==64)
 return e

def documentary(e):
 """All recovery-source shape and exact-outcome checks precede stored-row work."""
 facts=read(S/'inputs/accepted_geography.json');holds=read(S/'audit/followup_holds.json')
 ck('current_fact_and_hold_container_types',isinstance(facts,list) and isinstance(holds,list))
 ck('zero_facts_exact_six_unique_held_ids',facts==[] and len(holds)==6
    and {h['record_id'] for h in holds}==FIXED_IDS)
 ck('six_holds_preserve_unknown_without_adopted_proof',all(h['reviewed_hemisphere']=='unknown'
    and h.get('source_grade_adopted') is None and h.get('proof_mode') is None and h.get('proof_chain',[])==[]
    and h['decision']=='held' and h['no_new_geographic_assignment'] is True
    and h['native_and_original_birthplace_fields_unchanged'] is True
    and h['source_grade_role']=='geographic_support_only' for h in holds))
 ck('reconstructed_holds_do_not_claim_original_bytes_or_timing',all(h['artifact_type']=='reconstructed_hold_from_retained_verified_review'
    and h['original_file_bytes_recovered'] is False and h['original_request_utc'] is None
    and h['exact_request_utc'] is None and h['raw_HTTP_status'] is None and h['raw_bytes_sha256'] is None for h in holds))
 path=relative_path(e['recovery_source_review_path']);d=read(path)
 ck('recovery_source_review_actual_root_pin',sha(path)==e['recovery_source_review_sha256'])
 cases=d['case_reviews']
 ck('recovery_case_shape_and_exact_ids',isinstance(cases,list) and len(cases)==6
    and {c['record_id'] for c in cases}==FIXED_IDS and all(isinstance(c,dict) for c in cases))
 # These are explicit documentary fields, not lexical tests of prose or source labels.
 ck('six_recovery_cases_explicitly_held_with_review_and_source_locators',all(c['decision']=='held'
    and isinstance(c['source_refs'],list) and bool(c['source_refs'])
    and isinstance(c['review'],str) and bool(c['review'].strip()) for c in cases))
 ck('new_recovery_source_review_has_actual_new_checks',d['artifact_type']=='independent_recovery_source_review'
    and d['phase']=='recovery' and d['passed'] is True and type(d['checks_passed']) is int
    and d['checks_passed']==d['new_recovery_checks_passed']==len(d['checks'])>0
    and d['blocking_issues']==[] and all(c['passed'] is True for c in d['checks'])
    and d['case_reviews']==d['cases'])
 artifacts=e['recovery_artifact_sha256']
 ck('root_recovery_artifact_pins_are_nonempty_mapping',isinstance(artifacts,dict) and bool(artifacts))
 ck('all_root_recovery_artifact_pins_match_actual_files',all(sha(relative_path(n))==h for n,h in artifacts.items()))
 ck('facts_holds_and_recovery_review_are_in_root_artifact_pins',{'inputs/accepted_geography.json',
    'audit/followup_holds.json',e['recovery_source_review_path']}<=set(artifacts))
 provenance=read(S/'audit/recovery_provenance.json')
 checkpoint=read(S/'audit/interruption_checkpoint/checkpoint.json')
 ck('recovery_provenance_retains_unobserved_original_results',provenance['original_worker_reports_and_intents_recovered'] is False
    and provenance['original_source_QA_report_recovered'] is False
    and provenance['original_final_replays_completion_unobserved'] is True
    and provenance['reconstruction_cannot_restore_original_entry_UTCs_or_report_bytes'] is True)
 ck('historical_checks_retained_only_as_attestations',checkpoint['source_QA']['passed']==171
    and checkpoint['source_QA']['original_report_bytes_recovered'] is False
    and checkpoint['replay_preflight']['passed']==112
    and checkpoint['replay_preflight']['original_report_bytes_recovered'] is False
    and checkpoint['independent_final_QA']['light_checks_passed']==48
    and checkpoint['independent_final_QA']['last_observed_structural_checks_passed']==56
    and checkpoint['independent_final_QA']['final_QA_exit_observed'] is False
    and checkpoint['independent_final_QA']['isolated_CLI_replay_exits_observed'] is False)
 return cases,holds

def preflight(epath):
 ck('no_recorded_CLI_receipts_before_preflight',not any((W/f'v42_recovery_final_qa_replay_{i}.json').exists() for i in [1,2]))
 e=expectation(epath);cases,holds=documentary(e)
 pins=read(S/'audit/main_output_before_QA_sha256.json')['files']
 ck('five_pin_names_and_actual_production_bytes',set(pins)==OUTPUTS
    and all(sha(S/'outputs'/n)==h for n,h in pins.items()))
 ck('new_production_pins_equal_original_observed_V42_pins',pins==read(S/'audit/interruption_checkpoint/checkpoint.json')['production_main']['five_output_sha256_pinned_after_clean_exit'])
 oldsrc=(OLD/'scripts/replay.py').read_text();newsrc=(S/'scripts/replay.py').read_text()
 ot=ast.parse(oldsrc);nt=ast.parse(newsrc)
 of={n.name:ast.get_source_segment(oldsrc,n) for n in ot.body if isinstance(n,ast.FunctionDef)}
 nf={n.name:ast.get_source_segment(newsrc,n) for n in nt.body if isinstance(n,ast.FunctionDef)}
 oa={ast.dump(n.targets[0]):ast.get_source_segment(oldsrc,n) for n in ot.body if isinstance(n,ast.Assign) and len(n.targets)==1}
 na={ast.dump(n.targets[0]):ast.get_source_segment(newsrc,n) for n in nt.body if isinstance(n,ast.Assign) and len(n.targets)==1}
 ck('current_replay_script_exact_original_recovered_SHA256',sha(S/'scripts/replay.py')=='01b29beee4f90dc8f10f1c4322f4d345683ec26601d82c2a690730c37c8eb290')
 ck('old61_functions_current65_all_inherited_verbatim',len(of)==61 and len(nf)==65 and all(nf.get(k)==v for k,v in of.items()))
 ck('old128_assignments_current136_all_inherited_verbatim',len(oa)==128 and len(na)==136 and all(na.get(k)==v for k,v in oa.items()))
 ck('only_four_additive_current_functions',set(nf)-set(of)=={'load_v41','apply_v42_geography','write_csv_v42','main_v42'})
 guards=[n for n in nt.body if isinstance(n,ast.If) and isinstance(n.test,ast.Compare)
    and isinstance(n.test.left,ast.Name) and n.test.left.id=='__name__']
 calls=[n.func.id for g in guards for n in ast.walk(g) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name)]
 ck('CLI_invokes_only_main_v42',calls==['main_v42'])
 del oldsrc,newsrc,ot,nt,of,nf,oa,na,guards,calls
 ck('unchanged_method_preregistration',sha(S/'audit/method_preregistration.json')==BASE_METHOD)
 ck('all_six_application_scope_runtime_paths_and_pins',all(sha(S/'audit'/n)==h for n,h in SCOPE_HASHES.items()))
 ck('five_legacy_application_scope_files_byte_equivalent_to_V41',all(sha(S/'audit'/n)==sha(OLD/'audit'/n) for n in SCOPE_HASHES if n!='method_application_scope_v42.json'))
 scope=read(S/'audit/method_application_scope_v42.json')
 ck('current_scope_frozen_ids_baseline_and_unamended_method',set(scope['fixed_record_ids'])==FIXED_IDS
    and scope['baseline_commit']==BASE_COMMIT and scope['baseline_canonical_sha256']==BASE_CANONICAL
    and scope['method_preregistration_sha256']==BASE_METHOD and scope['rules_unchanged'] is True
    and scope['method_amendment_created'] is False and scope['no_new_admission_method_exception'] is True)
 old_current={'accepted_geography.json','geography_followup_ids.json','geography_target_ids.json','reviewed_record_ids.json'}
 ck('all_inherited_inputs_exact_with_old_current_inputs_versioned_V41',all(
    sha(p)==sha(S/'inputs'/('v41_'+p.name if p.name in old_current else p.name))
    for p in (OLD/'inputs').iterdir() if p.is_file()))
 ck('V41_hold_input_snapshot_exact',sha(S/'inputs/v41_followup_holds.json')==sha(OLD/'audit/followup_holds.json'))
 ids=read(S/'inputs/reviewed_record_ids.json');followups=read(S/'inputs/geography_followup_ids.json')
 ck('fixed_review_and_followup_sets_exact',len(ids)==len(followups)==6 and set(ids)==set(followups)==FIXED_IDS)
 oldhist=[p for p in (OLD/'audit').glob('prior_*') if p.is_file()]
 ck('all_inherited_historical_audits_exact',bool(oldhist) and all(sha(p)==sha(S/'audit'/p.name) for p in oldhist))
 ck('separate_historical_context_files_exact',all(sha(OLD/'audit'/n)==sha(S/'audit'/n) for n in [
    'thompson_historical_context.json','thompson_context_provenance_note.json',
    'franklin_historical_context.json','franklin_context_provenance_note.json']))
 inventory={}
 for n in SIDECARS:
  ck(n+'_entire_file_exact',sha(OLD/'audit'/n)==sha(S/'audit'/n))
  obj=read(S/'audit'/n);inventory[n]=None if isinstance(obj,dict) and 'records' not in obj else len(records(obj))
 ck('inherited_issue_inventory_cardinalities',inventory['active_source_DOB_conflicts.json']==13
    and inventory['birthplace_source_conflicts.json']==2 and inventory['source_derived_age_inconsistencies.json']==4
    and inventory['omitted_middle_name_admission.json'] is None)
 # Stream each complete object once; retain only six fixed native objects.
 hb=hashlib.sha256();ha=hashlib.sha256();hi=hashlib.sha256();seen=set();native={};targets=[]
 overall=collections.Counter();window=collections.Counter();diag=collections.Counter();count=0
 for b,a in itertools.zip_longest(objects(OLD/'outputs/birthplace_rows.jsonl.gz'),objects(S/'outputs/birthplace_rows.jsonl.gz')):
  assert b is not None and a is not None,'master row count mismatch'
  assert b==a,('changed complete master object',b.get('record_id'),a.get('record_id'))
  rid=a['record_id'];assert rid not in seen;seen.add(rid);count+=1
  hb.update(canon(b));ha.update(canon(a));hi.update((rid+'\n').encode());overall[a['hemisphere']]+=1
  assert a['cohort']=='UK_Royal_Society'
  if rid in FIXED_IDS:native[rid]=a
  blank=not a.get('raw_birthplace');unknown=a['hemisphere']=='unknown';inside=win(a)
  diag['all_blank_raw_birthplace']+=blank;diag['all_unknown']+=unknown
  diag['all_unknown_with_blank_raw_birthplace']+=unknown and blank
  diag['all_unknown_with_nonblank_raw_birthplace']+=unknown and not blank
  if inside:
   window[a['hemisphere']]+=1;diag['window_blank_raw_birthplace']+=blank;diag['window_unknown']+=unknown
   diag['window_unknown_with_blank_raw_birthplace']+=unknown and blank
   diag['window_unknown_with_nonblank_raw_birthplace']+=unknown and not blank
   if unknown and not blank:targets.append(rid)
 ck('all4983_complete_objects_order_and_native_fields_exact',count==len(seen)==4983)
 ck('stored_V41_and_current_canonical_equal_expected',hb.hexdigest()==ha.hexdigest()==BASE_CANONICAL)
 ck('stored_gzip_bytes_equal_V41',sha(OLD/'outputs/birthplace_rows.jsonl.gz')==sha(S/'outputs/birthplace_rows.jsonl.gz'))
 ck('all_six_fixed_native_objects_present',set(native)==FIXED_IDS)
 ck('six_recovery_case_native_name_DOB_place_grade_bindings',all(c['native_DOB']==native[c['record_id']]['dob']
    and c['native_name']==native[c['record_id']]['name']+' '+native[c['record_id']]['source_authorised_full_name'].split(';',1)[0]
    and c['frozen_place']==native[c['record_id']]['raw_birthplace']
    and c['original_BP_grade']==native[c['record_id']]['birthplace_source_grade'] for c in cases))
 ck('six_reconstructed_hold_native_snapshots_exact',all(h['native']['authority_name']==native[h['record_id']]['source_authorised_full_name']
    and h['native']['native_dob']==native[h['record_id']]['dob']
    and h['native']['raw_birthplace']==native[h['record_id']]['raw_birthplace']
    and h['native']['frozen_birthplace_source_grade']==native[h['record_id']]['birthplace_source_grade']
    and h['native']['complete_object_canonical_sha256']==hashlib.sha256(canon(native[h['record_id']]).rstrip(b'\n')).hexdigest() for h in holds))
 ck('no_current_geo_context_added',all('geography_followup_v42' not in n for n in native.values()))
 ck('all_master_and_native_window_counts_unchanged',overall=={'north':4205,'south':187,'unknown':591}
    and window=={'north':2305,'south':182,'unknown':157})
 ck('all_blank_and_unknown_diagnostics_unchanged',diag=={
    'all_blank_raw_birthplace':525,'all_unknown':591,'all_unknown_with_blank_raw_birthplace':525,
    'all_unknown_with_nonblank_raw_birthplace':66,'window_blank_raw_birthplace':103,'window_unknown':157,
    'window_unknown_with_blank_raw_birthplace':103,'window_unknown_with_nonblank_raw_birthplace':54})
 ck('54_stored_place_target_ids_exact_order',read(S/'inputs/geography_target_ids.json')==targets and len(targets)==54)
 summary=read(S/'outputs/summary.json')
 ck('summary_actual_totals_and_diagnostics',summary['overall']==dict(overall)
    and summary['native_dob_window_counts']==dict(window) and summary['remaining_blank_current_fields']==dict(diag))
 ck('summary_current_baseline_and_zero_changes',summary['baseline_v41_source_commit']==BASE_COMMIT
    and summary['baseline_v41_canonical_jsonl_sha256']==BASE_CANONICAL
    and summary['new_birthplaces']==summary['new_geographic_resolutions']==summary['new_geography_only_resolutions']==0
    and summary['followup_held_records']==6 and summary['unchanged_complete_rows']==4983
    and summary['new_birthplace_source_grade_counts']==summary['new_geographic_support_grade_counts']=={}
    and summary['DOB_calendar_identity_eligibility_modified'] is False)
 ck('changes_table_empty',read(S/'outputs/changes.json')==[])
 with (OLD/'outputs/birthplaces.csv').open(newline='') as f:oldcols=csv.DictReader(f).fieldnames
 with (S/'outputs/birthplaces.csv').open(newline='') as f:newcols=csv.DictReader(f).fieldnames
 ck('CSV182_historical_plus_six_current_columns_equals188',len(oldcols)==182 and newcols==oldcols+CURRENT_COLS and len(newcols)==188)
 ci=hashlib.sha256();cc=0
 for b,a in itertools.zip_longest(csvrows(OLD/'outputs/birthplaces.csv'),csvrows(S/'outputs/birthplaces.csv')):
  assert b is not None and a is not None,'CSV row count mismatch'
  assert all(a[k]==v for k,v in b.items()),a.get('record_id')
  assert all(a[k]=='' for k in CURRENT_COLS),a.get('record_id')
  ci.update((a['record_id']+'\n').encode());cc+=1
 ck('all4983_CSV_old_values_order_and_blank_current_columns_exact',cc==4983 and ci.digest()==hi.digest())
 uc=0
 expected_unknown=(r for r in csvrows(S/'outputs/birthplaces.csv') if win(r) and r['hemisphere']=='unknown')
 for a,b in itertools.zip_longest(csvrows(S/'outputs/remaining_unknown_window.csv'),expected_unknown):
  assert a is not None and a==b,'remaining unknown CSV mismatch';uc+=1
 ck('remaining157_unknown_rows_equal_all188_current_CSV_values',uc==157)
 # Record only hashes and small summaries, and release all row/parser references before CLI modes.
 pinfile=S/'audit/main_output_before_QA_sha256.json'
 report={'schema':'UK_v42_recovery_independent_preflight_v1','status':'PASS','written_utc':utc(),
    'preflight_run_id':str(uuid.uuid4()),'new_checks_passed':len(checks),'new_checks':checks.copy(),'historical_attestations_only':HISTORICAL_ONLY,
    'expectations_path':str(epath),'expectations_sha256':sha(epath),'harness_sha256':sha(pathlib.Path(__file__)),
    'main_output_pins':pins,'main_pinfile_sha256':sha(pinfile),'reviewed_input_file_sha256':reviewed_pins(),
    'canonical_sha256':ha.hexdigest(),'complete_objects':count,'changed_complete_objects':0,
    'overall':dict(overall),'window_counts':dict(window),'blank_diagnostics':dict(diag),
    'nine_issue_inventory_counts':inventory,'case_ids':sorted(native),'production_mutated':False,
    'replay_module_imported':False,'baseline_reconstruction_before_CLI':False,'CLI_invocations':0}
 write(W/'v42_recovery_final_qa_preflight.json',report)
 print(json.dumps({'status':'PASS','phase':'recovery_preflight','new_checks':len(checks)}),flush=True)

def replay(number,epath):
 prepath=W/'v42_recovery_final_qa_preflight.json';report=read(prepath);prehash=sha(prepath)
 ck('successful_new_preflight_required',report['status']=='PASS' and sha(epath)==report['expectations_sha256']
    and sha(pathlib.Path(__file__))==report['harness_sha256'])
 dest=W/f'v42_recovery_final_qa_replay_{number}.json'
 ck('no_repeat_of_recorded_replay',not dest.exists())
 if number==2:
  previous=read(W/'v42_recovery_final_qa_replay_1.json')
  ck('first_replay_success_required_before_second',previous['status']=='PASS' and previous['CLI_returncode']==0
    and previous['run']==1 and previous['preflight_report_sha256']==prehash
    and previous['preflight_run_id']==report['preflight_run_id']
    and sha(pathlib.Path(previous['CLI_log_path']))==previous['CLI_log_sha256'])
 check_freeze(report)
 started=utc();temporary=tempfile.TemporaryDirectory(prefix=f'v42_recovery_QA_{number}_');p=pathlib.Path(temporary.name)/'study'
 try:
  shutil.copytree(S/'inputs',p/'inputs');shutil.copytree(S/'scripts',p/'scripts',ignore=shutil.ignore_patterns('__pycache__'))
  (p/'audit').mkdir()
  for n in ['followup_holds.json','method_preregistration.json',*SCOPE_HASHES]:shutil.copyfile(S/'audit'/n,p/'audit'/n)
  # This process never loaded complete baseline/current graphs. Only the child CLI reconstructs.
  gc.collect();log=W/f'v42_recovery_isolated_cli_{number}.log'
  print(json.dumps({'phase':'isolated_CLI','run':number,'started_utc':started,'sequential':True}),flush=True)
  write(dest,{'schema':'UK_v42_recovery_isolated_CLI_receipt_v1','status':'STARTED',
     'run':number,'started_utc':started,'CLI_returncode':None,'preflight_report_sha256':prehash,
     'preflight_run_id':report['preflight_run_id'],'isolated_study_path':str(p),
     'CLI_log_path':str(log),'production_mutated':False,'historical_session_result_reused':False})
  with log.open('w') as out:result=subprocess.run([sys.executable,'-B',str(p/'scripts/replay.py')],stdout=out,stderr=subprocess.STDOUT,check=False)
  returned=utc();receipt={'schema':'UK_v42_recovery_isolated_CLI_receipt_v1','run':number,
     'started_utc':started,'returned_utc':returned,'CLI_returncode':result.returncode,
     'sequential':True,'CLI_log_path':str(log),'CLI_log_sha256':sha(log),'new_checks':checks.copy(),
     'preflight_report_sha256':prehash,'preflight_run_id':report['preflight_run_id'],
     'expectations_sha256':report['expectations_sha256'],'production_mutated':False,
     'historical_session_result_reused':False}
  write(dest,dict(receipt,status='FAIL' if result.returncode else 'EXIT_0_PENDING_HASH_CHECK'))
  ck('isolated_CLI_actual_clean_exit',result.returncode==0)
  hashes={n:sha(p/'outputs'/n) for n in report['main_output_pins']}
  ck('isolated_CLI_all_five_outputs_match_original_pins',hashes==report['main_output_pins'])
  check_freeze(report)
  receipt.update(status='PASS',five_output_sha256=hashes,new_checks=checks.copy(),new_checks_passed=len(checks),completed_utc=utc())
  write(dest,receipt);print(json.dumps({'status':'PASS','phase':'isolated_CLI','run':number,'actual_returncode':result.returncode}),flush=True)
 finally:temporary.cleanup()

def finish(epath):
 prepath=W/'v42_recovery_final_qa_preflight.json';pre=read(prepath);prehash=sha(prepath);runs=[read(W/f'v42_recovery_final_qa_replay_{i}.json') for i in [1,2]]
 ck('same_harness_and_expectations_as_preflight',sha(epath)==pre['expectations_sha256'] and sha(pathlib.Path(__file__))==pre['harness_sha256'])
 ck('two_receipts_bound_to_current_preflight_and_actual_logs',all(r['run']==i
    and r['preflight_report_sha256']==prehash and r['preflight_run_id']==pre['preflight_run_id']
    and sha(pathlib.Path(r['CLI_log_path']))==r['CLI_log_sha256'] for i,r in zip([1,2],runs)))
 ck('two_new_observed_clean_sequential_CLI_receipts',all(r['status']=='PASS' and r['CLI_returncode']==0 and r['sequential'] is True
    and r['five_output_sha256']==pre['main_output_pins'] for r in runs)
    and runs[0]['returned_utc']<=runs[1]['started_utc'])
 check_freeze(pre)
 report={'schema':'UK_v42_recovery_independent_final_QA_v1','status':'PASS','written_utc':utc(),
    'new_preflight_checks_passed':pre['new_checks_passed'],'new_preflight_checks':pre['new_checks'],
    'new_finish_checks_passed':len(checks),'new_finish_checks':checks.copy(),
    'preflight_run_id':pre['preflight_run_id'],'preflight_report_sha256':prehash,
    'new_isolated_CLI_runs':runs,'historical_attestations_only':HISTORICAL_ONLY,
    'baseline_commit':BASE_COMMIT,'baseline_canonical_sha256':BASE_CANONICAL,'final_canonical_sha256':pre['canonical_sha256'],
    'complete_objects':4983,'changed_complete_objects':0,'unchanged_complete_objects':4983,
    'accepted_record_ids':[],'held_record_ids':sorted(FIXED_IDS),'issue_appends':{},
    'main_output_pins':pre['main_output_pins'],'main_pinfile_sha256':pre['main_pinfile_sha256'],
    'reviewed_input_file_sha256':pre['reviewed_input_file_sha256'],'expectations_sha256':pre['expectations_sha256'],
    'harness_sha256':pre['harness_sha256'],'production_mutated':False,'network_or_Git_used':False,
    'replay_module_imported':False,'baseline_reconstruction_before_CLI':False,
    'limits':['Recovered source records are labeled reconstructions, not byte-exact recovery of lost original machine reports.',
      'Historical171/112/48/56 checks are distinct attestations; this report counts only newly executed checks and two observed sequential CLI exits.',
      'No original source acquisitions were repeated by this reviewer; source meanings and missing geography proof are reviewed in the pinned recovery source review.']}
 write(W/'v42_recovery_final_qa_report.json',report)
 print(json.dumps({'status':'PASS','phase':'recovery_final','new_preflight_checks':pre['new_checks_passed'],
    'new_finish_checks':len(checks),'new_sequential_CLI_exits':[r['CLI_returncode'] for r in runs]}),flush=True)

if __name__=='__main__':
 parser=argparse.ArgumentParser();mode=parser.add_mutually_exclusive_group(required=True)
 mode.add_argument('--preflight',action='store_true');mode.add_argument('--replay',type=int,choices=[1,2]);mode.add_argument('--finish',action='store_true')
 parser.add_argument('--expectations',type=pathlib.Path,default=W/'v42_recovery_final_qa_expectations.json');args=parser.parse_args()
 try:
  if args.preflight:preflight(args.expectations)
  elif args.replay:replay(args.replay,args.expectations)
  else:finish(args.expectations)
 except BaseException as exc:
  write(W/f'v42_recovery_final_qa_failure_{"preflight" if args.preflight else "replay_"+str(args.replay) if args.replay else "finish"}.json',
    {'schema':'UK_v42_recovery_QA_failure_v1','status':'FAIL','written_utc':utc(),'error_type':type(exc).__name__,
     'error':str(exc),'traceback':traceback.format_exc(),'new_checks_passed_before_failure':checks,
     'production_mutated':False,'historical_attestations_only':HISTORICAL_ONLY})
  raise
