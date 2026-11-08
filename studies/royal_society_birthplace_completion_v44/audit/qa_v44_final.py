"""Independent V44 QA: streamed stored rows, then two separate sequential isolated CLIs.
No replay import or preliminary load_v43 reconstruction. Production is read-only.
"""
from __future__ import annotations
import argparse,ast,collections,copy,csv,datetime,gc,gzip,hashlib,itertools,json,pathlib,re,shutil,subprocess,sys,tempfile,traceback,unicodedata,uuid
sys.dont_write_bytecode=True
W=pathlib.Path('/workspace/scratch/262552d8c0f0');S=W/'academy_repo/studies/royal_society_birthplace_completion_v44';OLD=S.with_name('royal_society_birthplace_completion_v43')
BASE_COMMIT='0f50abe91b8e4c1f7faf13f652cf988a5c3303df';BASE_CANONICAL='a0c04e44631478f82e562deab64d699fc273e6fc99fa35ba23f8a61d7e1f8717';BASE_METHOD='b76b7ad55125b1cf2dffe7d847d013f7fb8c2a6c8868c66f1e3060efae471147'
FIXED_IDS={'RS_CURRENT_10965','RS_PAST_NA6847','RS_PAST_NA780','RS_PAST_NA8736','RS_PAST_NA8744'}
SCOPE_HASHES={'method_application_scope.json':'ae080b06f8abad9ed7575783486795c977e44ce5e5024bfa2096e16816a44d94','method_application_scope_v38.json':'bd7540715a6b4649ffe79371e38ee2b650bd0176013fbb5418efa02b8995fad0','method_application_scope_v39.json':'cc12b3159a035064dbde6a35e0778642fdb25d988e9e399617b216062127b17e','method_application_scope_v40.json':'b44c66bc0d7883aeef9650578d0b339a65b563942da3fe72976b05c0094cc1fc','method_application_scope_v41.json':'d6ebcba7aa672c1a4877857bd4e9b4072af2ae159c04fd0dddf4d7766d2e3176','method_application_scope_v42.json':'c5c7594d271b6923725acad91612b8f53b3528383d3bf50f0658ccfa0e639796','method_application_scope_v43.json':'b25ef3f4bbf1f3e5dddd48531812a60e40d1383b897a0d3d044b0604e62db212','method_application_scope_v44.json':'3575db7b377008a55d4c6876c23ce6b6f67fc8b50dce40b7dddc01fcf8523e65'}
SIDECARS=['active_source_DOB_conflicts.json','birthplace_source_conflicts.json','source_derived_age_inconsistencies.json','provisional_parsed_date_discrepancies.json','lifespan_endpoint_discrepancies.json','cross_source_reported_age_contrasts.json','source_date_precision_holds.json','omitted_middle_name_admission.json','source_ordinal_age_wording_observations.json']
OUTPUTS={'birthplace_rows.jsonl.gz','birthplaces.csv','changes.json','remaining_unknown_window.csv','summary.json'}
GEO={'hemisphere','geo_resolution_status','geography_decision','reason','northern_birthplace_candidate','southern_birthplace_separate'}
CURRENT_COLS=['v44_geographic_hemisphere','v44_geographic_support_grade','v44_geography_source_url','v44_source_birthdate_precision','v44_geographic_support_grade_role','v44_geo_context_version']
checks=[]
def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def read(p):return json.loads(p.read_text())
def write(p,obj):
 t=p.with_name(p.name+'.'+uuid.uuid4().hex+'.writing');t.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n');t.replace(p)
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def ck(name,value):
 if not value:raise AssertionError(name)
 checks.append(name)
def canon(r):return (json.dumps(r,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n').encode()
def win(r):return '1835-01-01'<=r['dob']<='1985-12-31'
def objects(p):
 with gzip.open(p,'rt') as f:
  for line in f:
   if line.strip():yield json.loads(line)
def csvrows(p):
 with p.open(newline='') as f:yield from csv.DictReader(f)
def relative_path(s):
 p=pathlib.PurePosixPath(s);assert not p.is_absolute() and '..' not in p.parts,s;return S/pathlib.Path(p)
def records(obj):return obj if isinstance(obj,list) else obj.get('records') if isinstance(obj,dict) and isinstance(obj.get('records'),list) else None
def parts(s):
 text=re.split(r'\(\d{4}\s*[-–]\s*\d{4}\)',s,maxsplit=1)[0];text=unicodedata.normalize('NFKD',text).encode('ascii','ignore').decode().lower()
 return collections.Counter(x for x in re.sub('[^a-z0-9]+',' ',text).split() if x not in {'sir','dame','lord','lady','dr','prof','professor'})
def reviewed_pins():return {str(p.relative_to(S)):sha(p) for p in sorted(S.rglob('*')) if p.is_file() and 'outputs' not in p.relative_to(S).parts and '__pycache__' not in p.parts}
def check_freeze(report):
 ck('reviewed_production_files_unchanged',all((S/n).is_file() and sha(S/n)==h for n,h in report['reviewed_input_file_sha256'].items()))
 ck('five_production_output_pins_unchanged',all(sha(S/'outputs'/n)==h for n,h in report['main_output_pins'].items()))
 ck('production_pinfile_unchanged',sha(S/'audit/main_output_before_QA_sha256.json')==report['main_pinfile_sha256'])
def expectation(path):
 e=read(path)
 ck('root_canonical_accepted_ids_and_source_counts_supplied',isinstance(e['final_canonical_sha256'],str) and len(e['final_canonical_sha256'])==64 and isinstance(e['accepted_record_ids'],list) and len(e['accepted_record_ids'])==len(set(e['accepted_record_ids'])) and set(e['accepted_record_ids'])<=FIXED_IDS and isinstance(e['source_counts'],dict))
 ck('explicit_qualified_issue_appends_mapping',isinstance(e['approved_issue_appends'],dict) and set(e['approved_issue_appends'])<=set(SIDECARS)-{'omitted_middle_name_admission.json'})
 ck('root_normal_source_QA_binding',isinstance(e['source_qa_path'],str) and len(e['source_qa_sha256'])==64)
 ck('root_firstpass_closeout_binding',isinstance(e['closeout_path'],str) and len(e['closeout_sha256'])==64)
 return e

def documentary(e):
 facts=read(S/'inputs/accepted_geography.json');holds=read(S/'audit/followup_holds.json');fb={f['record_id']:f for f in facts};hb={h['record_id']:h for h in holds}
 ck('current_fact_hold_unique_complete_partition',len(fb)==len(facts) and len(hb)==len(holds) and not set(fb)&set(hb) and set(fb)|set(hb)==FIXED_IDS and set(fb)==set(e['accepted_record_ids']))
 ck('holds_no_current_geography_or_adopted_grade',all(h['reviewed_hemisphere']=='unknown' and h.get('source_grade_adopted') is None and not h.get('proof_chain') and h['no_new_geographic_assignment'] is True for h in holds))
 qpath=relative_path(e['source_qa_path']);q=read(qpath)
 ck('new_source_QA_passed_actual_pinned_report',sha(qpath)==e['source_qa_sha256'] and q['phase']=='final' and q['passed'] is True and q['blocking_issues']==[] and q['checks_passed']==len(q['checks'])>0 and all(c['passed'] is True for c in q['checks']))
 ck('source_QA_facts_holds_scopes_and_workers_actual',q['accepted_fact_sha256_at_review']==q['accepted_geography_sha256_at_review']==sha(S/'inputs/accepted_geography.json') and q['followup_holds_sha256_at_review']==sha(S/'audit/followup_holds.json') and q['method_application_scope_sha256_at_review']==SCOPE_HASHES['method_application_scope_v44.json'] and q['worker_source_report_sha256_at_review']=={g:sha(S/'audit'/f'sources_{g}.json') for g in 'abc'} and q['worker_intent_sha256_at_review']=={g:sha(S/'audit'/f'{g}_intent.json') for g in 'abc'})
 ck('source_QA_adopted_bindings_exact_current_facts',set(v['record_id'] for v in q['accepted_geographic_bindings'])==set(fb) and all(v['proof_chain']==fb[v['record_id']]['proof_chain'] and v['new_hemisphere']==fb[v['record_id']]['reviewed_hemisphere'] and v['new_geographic_grade']=='S3' for v in q['accepted_geographic_bindings']))
 cases=q['documentary_semantic_case_reviews'];cb={v['record_id']:v for v in cases}
 ck('five_documentary_case_reviews_exact_partition',len(cb)==len(cases)==5 and set(cb)==FIXED_IDS and all(cb[r]['decision']=='accepted_S3_geography_only' for r in fb) and all(cb[r]['decision']=='held' for r in hb))
 tail={'parent_adjudication_sha256_at_review':'audit/parent_adjudication.json','root_followups_sha256_at_review':'audit/root_followups.json','root_intent_sha256_at_review':'audit/root_intent.json','source_class_adjudication_sha256_at_review':'audit/source_class_adjudication.json','method_preregistration_sha256_at_review':'audit/method_preregistration.json','method_schema_sha256_at_review':'METHOD_SCHEMA.md'}
 ck('source_QA_tail_actual_file_bindings',all(q[k]==sha(S/p) for k,p in tail.items()))
 deviations=read(S/'audit/source_protocol_deviations.json')
 ck('source_QA_same_work_deviation_retained_without_admission',q['source_protocol_deviations_sha256_at_review']==sha(S/'audit/source_protocol_deviations.json') and q['all_collection_work_closures_clean'] is False and len(q['source_protocol_deviations'])==len(deviations)==1 and all(v['record_id'] in hb and v['record_id'] not in fb and v['claims_or_absence_adopted'] is False and v['geographic_admission'] is False for v in q['source_protocol_deviations']) and deviations==read(S/'audit/parent_adjudication.json')['source_protocol_deviations']==read(S/'audit/source_class_adjudication.json')['source_protocol_deviations'])
 ck('source_QA_eight_scope_bindings',all(q[('method_application_scope_sha256_at_review' if n=='method_application_scope_v44.json' else 'legacy_V'+('37' if n=='method_application_scope.json' else re.search(r'v(\d+)',n)[1])+'_method_application_scope_sha256_at_review')]==h for n,h in SCOPE_HASHES.items()))
 protocol=q['documentary_protocol_review'];docpins={'audit/v44_source_documentary_case_review.json':q['documentary_semantic_case_review_sha256_at_review'],'audit/'+protocol['quote_prefinal_report_path']:protocol['quote_prefinal_report_sha256'],'audit/'+protocol['worker_operation_prefinal_report_path']:protocol['worker_operation_prefinal_report_sha256']}
 ck('documentary_case_quote_operation_artifact_pins',all(sha(S/p)==h and (S/p).read_bytes()==(W/pathlib.Path(p).name).read_bytes() for p,h in docpins.items()))
 parent=read(S/'audit/parent_adjudication.json')
 ck('parent_actual_source_counts_and_partition',parent['source_counts']==e['source_counts'] and parent['decisions']['geography_only_resolutions']==len(facts) and parent['decisions']['held']==len(holds) and parent['decisions']['new_birthplaces']==0)
 return facts,holds,q,cases

def preflight(epath):
 ck('no_CLI_receipts_before_preflight',not any((W/f'v44_final_qa_replay_{i}.json').exists() for i in [1,2]))
 e=expectation(epath);facts,holds,source,cases=documentary(e);fb={f['record_id']:f for f in facts};hids={h['record_id'] for h in holds};n=len(facts)
 pins=read(S/'audit/main_output_before_QA_sha256.json')['files'];ck('five_original_production_pins_match',set(pins)==OUTPUTS and all(sha(S/'outputs'/name)==h for name,h in pins.items()))
 oldsrc=(OLD/'scripts/replay.py').read_text();newsrc=(S/'scripts/replay.py').read_text();ot=ast.parse(oldsrc);nt=ast.parse(newsrc)
 of={v.name:ast.get_source_segment(oldsrc,v) for v in ot.body if isinstance(v,ast.FunctionDef)};nf={v.name:ast.get_source_segment(newsrc,v) for v in nt.body if isinstance(v,ast.FunctionDef)}
 oa={ast.dump(v.targets[0]):ast.get_source_segment(oldsrc,v) for v in ot.body if isinstance(v,ast.Assign) and len(v.targets)==1};na={ast.dump(v.targets[0]):ast.get_source_segment(newsrc,v) for v in nt.body if isinstance(v,ast.Assign) and len(v.targets)==1}
 ck('old69_functions_current73_inherited_verbatim',len(of)==69 and len(nf)==73 and all(nf.get(k)==v for k,v in of.items()))
 ck('old144_assignments_current152_inherited_verbatim',len(oa)==144 and len(na)==152 and all(na.get(k)==v for k,v in oa.items()))
 ck('four_additive_current_functions',set(nf)-set(of)=={'load_v43','apply_v44_geography','write_csv_v44','main_v44'})
 guards=[v for v in nt.body if isinstance(v,ast.If) and isinstance(v.test,ast.Compare) and isinstance(v.test.left,ast.Name) and v.test.left.id=='__name__'];calls=[v.func.id for g in guards for v in ast.walk(g) if isinstance(v,ast.Call) and isinstance(v.func,ast.Name)]
 ck('CLI_only_main_v44',calls==['main_v44']);del oldsrc,newsrc,ot,nt,of,nf,oa,na,guards,calls
 ck('base_method_and_all_eight_scope_paths',sha(S/'audit/method_preregistration.json')==BASE_METHOD and all(sha(S/'audit'/k)==v for k,v in SCOPE_HASHES.items()))
 ck('all_seven_legacy_scopes_exact',all(sha(S/'audit'/k)==sha(OLD/'audit'/k) for k in SCOPE_HASHES if k!='method_application_scope_v44.json'))
 scope=read(S/'audit/method_application_scope_v44.json');ck('scope_fixed_ids_baseline_unchanged_method',set(scope['fixed_record_ids'])==FIXED_IDS and scope['baseline_commit']==BASE_COMMIT and scope['baseline_canonical_sha256']==BASE_CANONICAL and scope['rules_unchanged'] is True and scope['no_new_admission_method_exception'] is True)
 current_inputs={'accepted_geography.json','geography_followup_ids.json','geography_target_ids.json','reviewed_record_ids.json','reviewed_native_rows.json'}
 ck('all_inherited_inputs_exact_with_V43_current_snapshots',all(sha(p)==sha(S/'inputs'/('v43_'+p.name if p.name in current_inputs else p.name)) for p in (OLD/'inputs').iterdir() if p.is_file()))
 ck('prior_V43_holds_input_snapshot_exact',sha(S/'inputs/v43_followup_holds.json')==sha(OLD/'audit/followup_holds.json'))
 ids=read(S/'inputs/reviewed_record_ids.json');ck('five_unique_current_review_and_followups',len(ids)==5 and set(ids)==FIXED_IDS and ids==read(S/'inputs/geography_followup_ids.json'))
 oldhist=[p for p in (OLD/'audit').rglob('*') if p.is_file() and p.relative_to(OLD/'audit').parts[0].startswith('prior_')];ck('all_inherited_prior_audit_files_exact',all(sha(p)==sha(S/'audit'/p.relative_to(OLD/'audit')) for p in oldhist))
 recovery=[p for p in (OLD/'audit').rglob('*') if p.is_file() and ('recovery' in p.name or any('interruption_checkpoint' in part for part in p.parts))]
 def retained_previous(p):
  rel=p.relative_to(OLD/'audit');first=rel.parts[0]
  return S/'audit'/pathlib.Path(first if first.startswith('prior_') else 'prior_v43_'+first,*rel.parts[1:])
 ck('baseline_V43_recovery_evidence_retained_exact',bool(recovery) and all(sha(p)==sha(retained_previous(p)) for p in recovery))
 ck('separate_Ewins_Barber_and_historical_queues_exact',all(sha(S/'audit'/k)==sha(OLD/'audit'/k) for k in ['prior_v11_holds.json','prior_v12_holds.json','prior_v29_first_pass_queue_closeout.json','prior_v35_geography_first_pass_queue_closeout.json']) and not (S/'audit/geography_first_pass_queue_closeout.json').exists())
 inventories={};appends={}
 for name in SIDECARS:
  old=read(OLD/'audit'/name);new=read(S/'audit'/name);oldrs=records(old);newrs=records(new);approved=e['approved_issue_appends'].get(name,[])
  if oldrs is None:ck(name+'_metadata_file_exact',newrs is None and sha(OLD/'audit'/name)==sha(S/'audit'/name) and not approved);added=[]
  else:
   ck(name+'_old_records_and_explicit_append_ids',isinstance(newrs,list) and newrs[:len(oldrs)]==oldrs and [v['record_id'] for v in newrs[len(oldrs):]]==approved);added=newrs[len(oldrs):]
   if added:
    ck(name+'_only_qualified_fixed_subjects_with_prior_snapshot',all(v['record_id'] in FIXED_IDS for v in added) and sha(S/'audit'/('prior_v43_'+name))==sha(OLD/'audit'/name) and (not isinstance(old,dict) or {k:v for k,v in old.items() if k!='records'}=={k:v for k,v in new.items() if k!='records'}))
    if name in {'active_source_DOB_conflicts.json','birthplace_source_conflicts.json'}:ck(name+'_conflict_subjects_held',all(v['record_id'] in hids for v in added))
   else:ck(name+'_whole_file_exact_default',sha(OLD/'audit'/name)==sha(S/'audit'/name))
  appends[name]=len(added);inventories[name]={'baseline_sha256':sha(OLD/'audit'/name),'current_sha256':sha(S/'audit'/name),'baseline_records':None if oldrs is None else len(oldrs),'current_records':None if newrs is None else len(newrs),'inventory_shape':'metadata_without_records' if oldrs is None else 'records'}
 ck('source_QA_all_nine_inventory_hash_count_bindings',all(source['nine_issue_inventory_sha256_at_review'][k]=={x:v for x,v in o.items() if x.endswith('sha256')} and source['nine_issue_inventory_counts_at_review'][k]=={x:v for x,v in o.items() if not x.endswith('sha256')} for k,o in inventories.items()))
 ck('old_active13_partial2_age4_preserved',inventories['active_source_DOB_conflicts.json']['baseline_records']==13 and inventories['birthplace_source_conflicts.json']['baseline_records']==2 and inventories['source_derived_age_inconsistencies.json']['baseline_records']==4)
 initial=set(read(S/'inputs/v36_geography_target_ids.json'));reviewed=set(read(S/'audit/method_preregistration.json')['fixed_record_ids'])
 for filename in SCOPE_HASHES:reviewed.update(read(S/'audit'/filename)['fixed_record_ids'])
 ck('firstpass_initial62_and53_distinct_reviewed_with_currentfive',len(initial)==62 and len(reviewed)==53 and reviewed<=initial and FIXED_IDS<=reviewed)
 hb=hashlib.sha256();ha=hashlib.sha256();hi=hashlib.sha256();seen=set();native={};targets=[];changed=[];overall=collections.Counter();window=collections.Counter();diag=collections.Counter();count=0;remaining_initial_unknown=set();all_unknown_ids=set();window_unknown_ids=set();window_nonblank_unknown_ids=set()
 for b,a in itertools.zip_longest(objects(OLD/'outputs/birthplace_rows.jsonl.gz'),objects(S/'outputs/birthplace_rows.jsonl.gz')):
  assert b is not None and a is not None,'master row count mismatch';rid=a['record_id'];assert rid==b['record_id'] and rid not in seen;seen.add(rid);count+=1
  assert a['cohort']=='UK_Royal_Society'
  if rid in fb:
   assert b['hemisphere']=='unknown' and b.get('raw_birthplace') and win(b)
   assert set(b)<=set(a) and set(a)-set(b)<=GEO|{'geography_followup_v44'}
   assert all(a[k]==b[k] for k in b if k not in GEO),rid
   prior={k:b[k] for k in GEO if k in b};absent=sorted(GEO-set(b));f=a['geography_followup_v44'];expected=copy.deepcopy(fb[rid]);expected.update(previous_geography_fields=prior,previous_absent_geography_fields=absent,source_grade_role='geographic_support_only',native_DOB_source_grade_unchanged=True,original_birthplace_fields_and_source_grades_unchanged=True)
   hemisphere=fb[rid]['reviewed_hemisphere'];directional={'north':'northern','south':'southern'}[hemisphere]
   geographic={'hemisphere':hemisphere,'geo_resolution_status':'resolved_by_v44_explicit_person_birth_context','geography_decision':'v44_geography_only_explicit_person_birth_context','reason':'explicit_birthplace_context_wholly_'+directional+'_context','northern_birthplace_candidate':hemisphere=='north','southern_birthplace_separate':hemisphere=='south'}
   assert f==expected and {k:a[k] for k in GEO}==geographic,rid
   restored=copy.deepcopy(a);del restored['geography_followup_v44'];restored.update(prior)
   for key in absent:restored.pop(key,None)
   assert restored==b,rid
   assert a!=b;changed.append(rid)
  else:assert a==b,('untargeted or held row changed',rid)
  if rid in FIXED_IDS:native[rid]=b
  if b['hemisphere']=='unknown' and b.get('raw_birthplace') and win(b):targets.append(rid)
  hb.update(canon(b));ha.update(canon(a));hi.update((rid+'\n').encode());overall[a['hemisphere']]+=1
  blank=not a.get('raw_birthplace');unknown=a['hemisphere']=='unknown';inside=win(a)
  if rid in initial and unknown:remaining_initial_unknown.add(rid)
  if unknown:all_unknown_ids.add(rid)
  if unknown and inside:
   window_unknown_ids.add(rid)
   if not blank:window_nonblank_unknown_ids.add(rid)
  diag['all_blank_raw_birthplace']+=blank;diag['all_unknown']+=unknown;diag['all_unknown_with_blank_raw_birthplace']+=unknown and blank;diag['all_unknown_with_nonblank_raw_birthplace']+=unknown and not blank
  if inside:
   window[a['hemisphere']]+=1;diag['window_blank_raw_birthplace']+=blank;diag['window_unknown']+=unknown;diag['window_unknown_with_blank_raw_birthplace']+=unknown and blank;diag['window_unknown_with_nonblank_raw_birthplace']+=unknown and not blank
 ck('4983_unique_ordered_records_and_accepted_only_exact_rollback',count==len(seen)==4983 and set(changed)==set(fb) and len(changed)==n)
 ck('baseline_and_final_canonical_match_independent_pins',hb.hexdigest()==BASE_CANONICAL and ha.hexdigest()==e['final_canonical_sha256'])
 ck('54_target_ids_exact_baseline_order',read(S/'inputs/geography_target_ids.json')==targets and len(targets)==54)
 ck('five_documentary_full_personal_name_DOB_place_grade_bindings',len(native)==5 and all(bool(parts(c['native_name'])) and parts(c['native_name'])==parts(native[c['record_id']]['source_authorised_full_name'] or native[c['record_id']]['name']) and c['native_DOB']==native[c['record_id']]['dob'] and c['frozen_place']==native[c['record_id']]['raw_birthplace'] and c['original_BP_grade']==native[c['record_id']]['birthplace_source_grade'] for c in cases))
 current=native['RS_CURRENT_10965'];identity=scope['native_identity_bindings']['RS_CURRENT_10965']
 ck('CURRENT_native_authority_empty_name_full_aliases_preserved',current['source_authorised_full_name']==identity['native_authority_field']=='' and current['name']==identity['native_personal_name']=='Jerry Adams' and identity['frozen_full_aliases']==current['geography_lookup_identity_review']['wikidata_aliases'] and identity['new_admission_exception'] is False)
 active={v['record_id'] for v in records(read(S/'audit/active_source_DOB_conflicts.json')) if v['active']};partial={v['record_id'] for v in records(read(S/'audit/birthplace_source_conflicts.json'))};blocked=initial&(active|partial|{'RS_PAST_NA9209','RS_PAST_NA8779'});unreviewed=initial-reviewed
 ck('firstpass_all_current_nonblocked_covered_nine_unreviewed_blocked',len(unreviewed)==9 and unreviewed==blocked-reviewed and initial-blocked<=reviewed and 'RS_PAST_NA4918' in reviewed&blocked)
 ck('firstpass_remaining_unknown_is_reviewed_holds_plus_unreviewed_blocked',len(remaining_initial_unknown)==54-n and remaining_initial_unknown==(reviewed&remaining_initial_unknown)|unreviewed and len(reviewed&remaining_initial_unknown)==45-n and len(initial-remaining_initial_unknown)==8+n)
 closeout=relative_path(e['closeout_path']);ck('firstpass_closeout_actual_root_pin',sha(closeout)==e['closeout_sha256'])
 coverage={'initial_record_ids':sorted(initial),'reviewed_record_ids':sorted(reviewed),'unreviewed_blocked_record_ids':sorted(unreviewed),'currently_blocked_record_ids':sorted(blocked),'currently_nonblocked_record_ids':sorted(initial-blocked),'reviewed_blocked_record_ids':sorted(reviewed&blocked),'remaining_unknown_record_ids':sorted(remaining_initial_unknown),'reviewed_remaining_unknown_record_ids':sorted(reviewed&remaining_initial_unknown),'resolved_record_ids':sorted(initial-remaining_initial_unknown),'source_exhausted':False,'final_freeze':False,'closeout_path':e['closeout_path'],'closeout_sha256':e['closeout_sha256']}
 closeobj=read(closeout);setbindings={k:set(v) for k,v in coverage.items() if k.endswith('_record_ids')};setbindings.update(unreviewed_record_ids=unreviewed,notblocked_and_unreviewed_record_ids=set(),current_master_all_unknown_record_ids=all_unknown_ids,current_master_window_unknown_record_ids=window_unknown_ids,current_master_window_nonblank_unknown_record_ids=window_nonblank_unknown_ids)
 ck('firstpass_closeout_sets_equal_independently_streamed_and_derived_sets',all(isinstance(closeobj[k],list) and len(closeobj[k])==len(set(closeobj[k])) and set(closeobj[k])==v for k,v in setbindings.items()))
 ck('firstpass_closeout_coverage_distinct_from_completeness_exhaustion_freeze',all(closeobj[k] is False for k in ['all_initial_records_reviewed','birthplace_coverage_complete','geography_coverage_complete','source_exhausted','all_biographies_or_sources_read','final_freeze']) and all(closeobj[k] is True for k in ['nonblocked_first_pass_queue_complete','all_current_nonblocked_initial_records_reviewed']))
 expected_close_counts={'initial':len(initial),'reviewed':len(reviewed),'unreviewed':len(unreviewed),'currently_blocked':len(blocked),'currently_nonblocked':len(initial-blocked),'reviewed_blocked':len(reviewed&blocked),'unreviewed_blocked':len(unreviewed),'notblocked_and_unreviewed':len(initial-blocked-reviewed),'remaining_unknown_within_initial':len(remaining_initial_unknown),'reviewed_remaining_unknown':len(reviewed&remaining_initial_unknown),'resolved_within_initial':len(initial-remaining_initial_unknown),'resolved_before_V44':len(initial)-len(targets),'newly_resolved_in_V44':n,'current_master_all_unknown':len(all_unknown_ids),'current_master_window_unknown':len(window_unknown_ids),'current_master_window_nonblank_unknown':len(window_nonblank_unknown_ids),'window_blank_outside_scope':diag['window_blank_raw_birthplace'],'overall_blank_outside_scope':diag['all_blank_raw_birthplace']}
 ck('firstpass_closeout_counts_equal_independent_sets_and_master',closeobj['counts']==expected_close_counts and closeobj['current_canonical_sha256']==ha.hexdigest() and closeobj['baseline_canonical_sha256']==hb.hexdigest())
 north=sum(f['reviewed_hemisphere']=='north' for f in facts);south=n-north
 ck('overall_and2644_window_counts_recomputed',overall=={'north':4205+north,'south':187+south,'unknown':591-n} and window=={'north':2305+north,'south':182+south,'unknown':157-n})
 ck('103_window_blank_525_overall_blank_unchanged',diag['window_blank_raw_birthplace']==diag['window_unknown_with_blank_raw_birthplace']==103 and diag['all_blank_raw_birthplace']==diag['all_unknown_with_blank_raw_birthplace']==525 and diag['window_unknown_with_nonblank_raw_birthplace']==54-n)
 summary=read(S/'outputs/summary.json');ck('summary_actual_counts_and_diagnostics',summary['overall']==dict(overall) and summary['native_dob_window_counts']==dict(window) and summary['remaining_blank_current_fields']==dict(diag))
 ck('summary_current_baseline_changes_and_frozen_fields',summary['baseline_v43_source_commit']==BASE_COMMIT and summary['baseline_v43_canonical_jsonl_sha256']==BASE_CANONICAL and summary['new_birthplaces']==0 and summary['new_geographic_resolutions']==summary['new_geography_only_resolutions']==n and summary['followup_held_records']==5-n and summary['unchanged_complete_rows']==4983-n and summary['new_birthplace_source_grade_counts']=={} and summary['new_geographic_support_grade_counts']==({'S3':n} if n else {}) and summary['DOB_calendar_identity_eligibility_modified'] is False)
 changes=read(S/'outputs/changes.json');ck('changes_exact_adopted_geography_only',len(changes)==n and {v['record_id'] for v in changes}==set(fb) and all(v['change_type']=='geography_only' and v['before_raw_birthplace']==v['after_raw_birthplace']==native[v['record_id']]['raw_birthplace'] and v['before_birthplace_source_grade']==v['after_birthplace_source_grade']==native[v['record_id']]['birthplace_source_grade'] for v in changes))
 with (OLD/'outputs/birthplaces.csv').open(newline='') as f:oldcols=csv.DictReader(f).fieldnames
 with (S/'outputs/birthplaces.csv').open(newline='') as f:newcols=csv.DictReader(f).fieldnames
 ck('CSV194_historical_plus6_current_equals200',len(oldcols)==194 and newcols==oldcols+CURRENT_COLS and len(newcols)==200)
 ci=hashlib.sha256();cc=0
 for b,a in itertools.zip_longest(csvrows(OLD/'outputs/birthplaces.csv'),csvrows(S/'outputs/birthplaces.csv')):
  assert b is not None and a is not None and b['record_id']==a['record_id'];rid=a['record_id'];f=fb.get(rid,{})
  assert all(a[k]==v for k,v in b.items() if not (rid in fb and k=='hemisphere')),rid
  expected=[f.get('reviewed_hemisphere',''),f.get('source_grade',''),f.get('source_url',''),f.get('source_birthdate_precision',''),f.get('source_grade_role',''),'v44' if f else '']
  assert [a[k] for k in CURRENT_COLS]==expected,rid
  if f:assert a['hemisphere']==f['reviewed_hemisphere']
  ci.update((rid+'\n').encode());cc+=1
 ck('4983_CSV_prior_values_and_current200_column_meanings',cc==4983 and ci.digest()==hi.digest())
 uc=0;expected_unknown=(r for r in csvrows(S/'outputs/birthplaces.csv') if win(r) and r['hemisphere']=='unknown')
 for a,b in itertools.zip_longest(csvrows(S/'outputs/remaining_unknown_window.csv'),expected_unknown):assert a is not None and a==b,'remaining unknown CSV mismatch';uc+=1
 ck('remaining_unknown_CSV_exact_all200_values',uc==157-n)
 docs={k:(S/k).read_text() for k in ['README.md','CONTINUATION.md']};ck('final_docs_current_canonical_and_no_placeholders',all(e['final_canonical_sha256'] in v and not any(x in v for x in ['AWAIT_','PLACEHOLDER','PENDING']) for v in docs.values()))
 ck('no_full_source_caches_or_images',not any(p.is_file() and p.suffix.lower() in {'.html','.htm','.pdf','.png','.jpg','.jpeg','.webp','.har','.ttl','.rdf'} for p in S.rglob('*')))
 report={'schema':'UK_v44_independent_final_preflight_v1','status':'PASS','written_utc':utc(),'preflight_run_id':str(uuid.uuid4()),'new_checks_passed':len(checks),'new_checks':checks.copy(),'expectations_path':str(epath),'expectations_sha256':sha(epath),'harness_sha256':sha(pathlib.Path(__file__)),'main_output_pins':pins,'main_pinfile_sha256':sha(S/'audit/main_output_before_QA_sha256.json'),'reviewed_input_file_sha256':reviewed_pins(),'canonical_sha256':ha.hexdigest(),'complete_objects':count,'changed_complete_objects':n,'accepted_record_ids':sorted(fb),'held_record_ids':sorted(hids),'issue_appends':appends,'overall':dict(overall),'window_counts':dict(window),'blank_diagnostics':dict(diag),'nine_issue_inventory':inventories,'production_mutated':False,'replay_module_imported':False,'baseline_reconstruction_before_CLI':False,'CLI_invocations':0}
 report['first_pass_coverage']=coverage
 write(W/'v44_final_qa_preflight.json',report);print(json.dumps({'status':'PASS','phase':'preflight','new_checks':len(checks),'accepted':n}),flush=True)


def replay(number,epath):
 prepath=W/'v44_final_qa_preflight.json';report=read(prepath);prehash=sha(prepath)
 ck('successful_current_preflight_required',report['status']=='PASS' and sha(epath)==report['expectations_sha256'] and sha(pathlib.Path(__file__))==report['harness_sha256'])
 dest=W/f'v44_final_qa_replay_{number}.json';ck('no_repeat_recorded_replay',not dest.exists())
 if number==2:
  previous=read(W/'v44_final_qa_replay_1.json');ck('first_actual_clean_replay_before_second',previous['status']=='PASS' and previous['CLI_returncode']==0 and previous['run']==1 and previous['preflight_report_sha256']==prehash and previous['preflight_run_id']==report['preflight_run_id'] and sha(pathlib.Path(previous['CLI_log_path']))==previous['CLI_log_sha256'])
 check_freeze(report);started=utc();temporary=tempfile.TemporaryDirectory(prefix=f'v44_QA_{number}_');p=pathlib.Path(temporary.name)/'study'
 try:
  shutil.copytree(S/'inputs',p/'inputs');shutil.copytree(S/'scripts',p/'scripts',ignore=shutil.ignore_patterns('__pycache__'));(p/'audit').mkdir()
  for name in ['followup_holds.json','method_preregistration.json',*SCOPE_HASHES]:shutil.copyfile(S/'audit'/name,p/'audit'/name)
  gc.collect();log=W/f'v44_isolated_cli_{number}.log'
  write(dest,{'schema':'UK_v44_isolated_CLI_receipt_v1','status':'STARTED','run':number,'started_utc':started,'CLI_returncode':None,'preflight_report_sha256':prehash,'preflight_run_id':report['preflight_run_id'],'isolated_study_path':str(p),'CLI_log_path':str(log),'production_mutated':False})
  print(json.dumps({'phase':'isolated_CLI','run':number,'started_utc':started,'sequential':True}),flush=True)
  with log.open('w') as out:result=subprocess.run([sys.executable,'-B',str(p/'scripts/replay.py')],stdout=out,stderr=subprocess.STDOUT,check=False)
  returned=utc();receipt={'schema':'UK_v44_isolated_CLI_receipt_v1','run':number,'started_utc':started,'returned_utc':returned,'CLI_returncode':result.returncode,'sequential':True,'CLI_log_path':str(log),'CLI_log_sha256':sha(log),'new_checks':checks.copy(),'preflight_report_sha256':prehash,'preflight_run_id':report['preflight_run_id'],'expectations_sha256':report['expectations_sha256'],'production_mutated':False}
  write(dest,dict(receipt,status='FAIL' if result.returncode else 'EXIT_0_PENDING_HASH_CHECK'));ck('isolated_CLI_actual_clean_exit',result.returncode==0)
  hashes={name:sha(p/'outputs'/name) for name in report['main_output_pins']};ck('isolated_CLI_all_five_outputs_match_pins',hashes==report['main_output_pins']);check_freeze(report)
  receipt.update(status='PASS',five_output_sha256=hashes,new_checks=checks.copy(),new_checks_passed=len(checks),completed_utc=utc());write(dest,receipt)
  print(json.dumps({'status':'PASS','phase':'isolated_CLI','run':number,'actual_returncode':result.returncode}),flush=True)
 finally:temporary.cleanup()

def finish(epath):
 prepath=W/'v44_final_qa_preflight.json';pre=read(prepath);prehash=sha(prepath);runs=[read(W/f'v44_final_qa_replay_{i}.json') for i in [1,2]]
 ck('same_harness_and_expectations_as_preflight',sha(epath)==pre['expectations_sha256'] and sha(pathlib.Path(__file__))==pre['harness_sha256'])
 ck('two_receipts_bound_to_preflight_and_actual_logs',all(r['run']==i and r['preflight_report_sha256']==prehash and r['preflight_run_id']==pre['preflight_run_id'] and sha(pathlib.Path(r['CLI_log_path']))==r['CLI_log_sha256'] for i,r in zip([1,2],runs)))
 ck('two_observed_clean_sequential_CLI_receipts',all(r['status']=='PASS' and r['CLI_returncode']==0 and r['sequential'] is True and r['five_output_sha256']==pre['main_output_pins'] for r in runs) and runs[0]['returned_utc']<=runs[1]['started_utc']);check_freeze(pre)
 report={'schema':'UK_v44_independent_final_QA_v1','status':'PASS','written_utc':utc(),'new_preflight_checks_passed':pre['new_checks_passed'],'new_preflight_checks':pre['new_checks'],'new_finish_checks_passed':len(checks),'new_finish_checks':checks.copy(),'preflight_run_id':pre['preflight_run_id'],'preflight_report_sha256':prehash,'new_isolated_CLI_runs':runs,'baseline_commit':BASE_COMMIT,'baseline_canonical_sha256':BASE_CANONICAL,'final_canonical_sha256':pre['canonical_sha256'],'complete_objects':4983,'changed_complete_objects':pre['changed_complete_objects'],'unchanged_complete_objects':4983-pre['changed_complete_objects'],'accepted_record_ids':pre['accepted_record_ids'],'held_record_ids':pre['held_record_ids'],'issue_appends':pre['issue_appends'],'main_output_pins':pre['main_output_pins'],'main_pinfile_sha256':pre['main_pinfile_sha256'],'reviewed_input_file_sha256':pre['reviewed_input_file_sha256'],'expectations_sha256':pre['expectations_sha256'],'harness_sha256':pre['harness_sha256'],'production_mutated':False,'network_or_Git_used':False,'replay_module_imported':False,'baseline_reconstruction_before_CLI':False,'limits':['Source meanings and whole-region sufficiency are assessed in the pinned independent source QA; no new source requests by final reviewer.','Original DOB/BP/native fields and grades remain frozen; accepted changes are six geography fields plus versioned context with exact rollback.','V42 recovery audits retain their distinction between historical attestations and actually executed recovery checks.']}
 report['first_pass_coverage']=pre['first_pass_coverage']
 write(W/'v44_final_qa_report.json',report);print(json.dumps({'status':'PASS','phase':'final','new_preflight_checks':pre['new_checks_passed'],'new_finish_checks':len(checks),'sequential_CLI_exits':[r['CLI_returncode'] for r in runs]}),flush=True)

if __name__=='__main__':
 parser=argparse.ArgumentParser();mode=parser.add_mutually_exclusive_group(required=True);mode.add_argument('--preflight',action='store_true');mode.add_argument('--replay',type=int,choices=[1,2]);mode.add_argument('--finish',action='store_true');parser.add_argument('--expectations',type=pathlib.Path,default=W/'v44_final_qa_expectations.json');args=parser.parse_args()
 try:
  if args.preflight:preflight(args.expectations)
  elif args.replay:replay(args.replay,args.expectations)
  else:finish(args.expectations)
 except BaseException as exc:
  write(W/f'v44_final_qa_failure_{"preflight" if args.preflight else "replay_"+str(args.replay) if args.replay else "finish"}.json',{'schema':'UK_v44_independent_QA_failure_v1','status':'FAIL','written_utc':utc(),'error_type':type(exc).__name__,'error':str(exc),'traceback':traceback.format_exc(),'new_checks_passed_before_failure':checks,'production_mutated':False});raise
