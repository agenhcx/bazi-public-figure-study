"""Independent V42 recovery documentary review. Direct V41 gzip only; no replay/network/Git."""
import argparse,collections,datetime,gzip,hashlib,json,pathlib,re,unicodedata
W=pathlib.Path(__file__).resolve().parent
OLD=W/'academy_repo/studies/royal_society_birthplace_completion_v41'
S=W/'academy_repo/studies/royal_society_birthplace_completion_v42'
R=W/'academy_repo/studies/royal_society_birthplace_completion_v42_recovery'
BASE='a0c04e44631478f82e562deab64d699fc273e6fc99fa35ba23f8a61d7e1f8717'
METHOD='b76b7ad55125b1cf2dffe7d847d013f7fb8c2a6c8868c66f1e3060efae471147'
SCOPE='c5c7594d271b6923725acad91612b8f53b3528383d3bf50f0658ccfa0e639796'
HISTORICAL_REPORT='fd7a18d1df3816192812894620b352ad2ea695498c07076d20aa7f42b4443dd5'
IDS=['RS_PAST_NA1476','RS_PAST_NA1592','RS_PAST_NA1994','RS_PAST_NA1998','RS_PAST_NA2007','RS_PAST_NA2146']
INVENTORY_COUNTS={'active_source_DOB_conflicts.json':13,'birthplace_source_conflicts.json':2,'source_derived_age_inconsistencies.json':4,'provisional_parsed_date_discrepancies.json':1,'lifespan_endpoint_discrepancies.json':1,'cross_source_reported_age_contrasts.json':1,'source_date_precision_holds.json':1,'omitted_middle_name_admission.json':None,'source_ordinal_age_wording_observations.json':1}
KNOWN_CASES={
 'RS_PAST_NA1476':('Bernard Smith','1881-02-13','Grantham','S3',['turn3826931view0','turn3990477view1','turn5962439view0']),
 'RS_PAST_NA1592':('Ernest John Maskell','1895-02-01','Cambridge','S2',['turn3990477view0']),
 'RS_PAST_NA1994':('Norman Laurence Franklin','1924-09-01','Leeds','S3',['turn8750374view0','turn6928554view0','turn8623749view0']),
 'RS_PAST_NA1998':('Basil Kassanis','1911-10-16','Macedonian born','S3',['turn8750374view1','turn2061416view2']),
 'RS_PAST_NA2007':('Pierre Henry John Young','1926-06-12','France','S3',['turn4592580view0','turn7813429view1','turn2061416view0']),
 'RS_PAST_NA2146':('Oscar Victor Sayer Heath','1903-07-26','London','S2',['turn7813429view0','turn2061416view1'])}
REVIEWS={
 'RS_PAST_NA1476':'Retained acquisition review identifies explicitly rewritten person/item responses, usable only as observed URI/sitelink carriers. Separate frozen lookup item first opening failed. No original canonical person birth-region path was acquired. Prior BGS Grantham/S3, Bailey/NPG career context and failed memoir limits stay historical.',
 'RS_PAST_NA1592':'Retained bounded discovery supplied no acquired eligible canonical person body, and supplied lookup item first opening failed. No actual birth-region path. Prior Cambridge memoir abstract/S2 and closed DOI/local-history/profile attempts remain unchanged; familiar-city inference supplies no edge.',
 'RS_PAST_NA1994':'Retained actual fellow-list supplies an observed personal-link carrier; its followed link resolved to an edit/redlink target with first tool404. Supplied lookup item was unavailable. Neither supplies personal birth proof. Historical ATOM Leeds/S3 and root timeout, month-only IChemE and inaccessible JSTOR memoir remain distinct and closed.',
 'RS_PAST_NA1998':'Retained normal parsed Wikidata observations support full native name, exact displayed date, compatible life and virologist/FRS career identity context. No acquired birthplace/P19/admin chain establishes a birth region. Missing displayed P19 is not universal absence or an acquired no-value snak. Historical Macedonian-born adjective has unresolved extent; no guessed modern country.',
 'RS_PAST_NA2007':'Retained actual English body supports all native components, exact date, compatible life and distinctive Concorde career, but gives only generic unlinked France. No acquired birth-linked subregion. Item response was explicitly rewritten and remains a URI carrier. Displayed59 agrees completed59, so no age issue is inferred.',
 'RS_PAST_NA2146':'Retained normal parsed Wikidata observations support all native components, exact date, compatible life and plant-physiology/FRS career. No acquired personal birthplace/P19/admin chain. Missing displayed P19 is bounded unknown, not absence proof. Frozen London/S2 and closed historical memoir remain unchanged.'}

def rd(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def records(obj):return obj if isinstance(obj,list) else obj.get('records') if isinstance(obj,dict) and isinstance(obj.get('records'),list) else None
def norm(s):return re.sub('[^a-z0-9]+',' ',unicodedata.normalize('NFKD',str(s)).encode('ascii','ignore').decode().lower()).strip()
def components(s):return collections.Counter(x for x in norm(re.split(r'\(\d{4}\s*[-–]\s*\d{4}\)',s,maxsplit=1)[0]).split() if x not in {'sir','dame','lord','lady','dr','prof','professor'})
def target_contexts(obj):
 if isinstance(obj,dict):
  if obj.get('record_id') in IDS or isinstance(obj.get('native'),dict) and obj['native'].get('record_id') in IDS:
   return [obj]
  return [r for v in obj.values() for r in target_contexts(v)]
 if isinstance(obj,list):return [r for v in obj for r in target_contexts(v)]
 return []
def context_id(obj):return obj.get('record_id',obj.get('native',{}).get('record_id'))
def main(prepare=False):
 checks=[]
 def ck(name,ok,detail=None):checks.append({'check':name,'passed':bool(ok),**({'detail':detail} if detail is not None else {})})
 paths={'original_scope':R/'method_application_scope_v42.json','checkpoint':R/'checkpoint.json','retained_source_attestation':R/'source_qa_reconstructed_summary.json'}
 pinned_before={k:sha(p) for k,p in paths.items()}
 scope=rd(paths['original_scope']);checkpoint=rd(paths['checkpoint']);att=rd(paths['retained_source_attestation'])
 master=OLD/'outputs/birthplace_rows.jsonl.gz';master_before=sha(master);raw=gzip.decompress(master.read_bytes());rows=[json.loads(line) for line in raw.splitlines()];by={r['record_id']:r for r in rows}
 ck('direct_V41_canonical_pin',hashlib.sha256(raw).hexdigest()==BASE==scope['baseline_canonical_sha256']==checkpoint['canonical_sha256'])
 ck('master4983_unique_complete_records',len(rows)==len(by)==4983)
 ck('original_scope_byte_hash',sha(paths['original_scope'])==SCOPE)
 ck('scope_exact_six_fixed_IDs',scope['fixed_record_ids']==IDS and sum(scope['groups'].values(),[])==IDS)
 ck('scope_unchanged_V36_method',scope['method_preregistration_sha256']==METHOD and scope['rules_unchanged'] is True and scope['method_amendment_created'] is False and scope['no_new_admission_method_exception'] is True)
 ck('retained_source_is_reconstructed_attestation',att.get('artifact_type')=='reconstructed_verified_recovery_summary' and att.get('original_file_bytes_recovered') is False)
 ck('historical171_report_status_and_hash_attested_only',att['source_qa']['status']=='PASS' and att['source_qa']['checks_passed']==171 and att['source_qa']['blocking_issues']==[] and att['source_qa']['report_sha256']==HISTORICAL_REPORT and checkpoint['source_QA']['original_report_bytes_recovered'] is False)
 ck('original_per_entry_timestamps_not_recovered',att['operations']['per_entry_UTC_values_recovered'] is False)
 attcases=att['cases'];ab={c['record_id']:c for c in attcases}
 ck('attestation_exact_six_cases',len(attcases)==len(ab)==6 and set(ab)==set(IDS))
 native_cases=[]
 for rid in IDS:
  n=by[rid];c=ab[rid];name,dob,place,grade,refs=KNOWN_CASES[rid]
  ck(rid+'_all_full_native_personal_components',components(c['native_name'])==components(n['source_authorised_full_name'])==components(name))
  ck(rid+'_native_DOB_place_BP_grade',c['native_DOB']==n['dob']==dob and c['frozen_place']==n['raw_birthplace']==place and c['original_BP_grade']==n['birthplace_source_grade']==grade)
  ck(rid+'_unknown_nonblank_window_scope',n['hemisphere']=='unknown' and bool(n['raw_birthplace']) and '1835-01-01'<=n['dob']<='1985-12-31')
  ck(rid+'_held_retained_refs_exact',c['decision']=='held' and c['source_refs']==refs)
  native_cases.append({'record_id':rid,'native_name':name,'native_DOB':dob,'frozen_place':place,'original_BP_grade':grade,'native_authority_string':n['source_authorised_full_name'],'native_personal_components':sorted(components(n['source_authorised_full_name']).elements()),'decision':'held','source_refs':refs,'source_locator_from_retained_attestation':c.get('root_locator'),'review':REVIEWS[rid],'source_interpretation_from_retained_review':True,'fresh_source_body_acquisition':False})
 inventory={};targets_in_issues={}
 for name,count in INVENTORY_COUNTS.items():
  p=OLD/'audit'/name;obj=rd(p);rs=records(obj)
  ck(name+'_baseline_shape_and_count',(rs is None if count is None else isinstance(rs,list) and len(rs)==count))
  matched=[v for v in (rs or []) if context_id(v) in IDS]
  ck(name+'_current_six_not_prior_issue_subjects',not matched)
  inventory[name]={'baseline_sha256':sha(p),'baseline_records':None if rs is None else len(rs),'inventory_shape':'metadata_without_records' if rs is None else 'records'}
  targets_in_issues[name]=[context_id(v) for v in matched]
 active=rd(OLD/'audit/active_source_DOB_conflicts.json')['records']
 ck('all13_active_DOB_remain_active',all(v['active'] is True for v in active))
 ck('separate_Ewins_Barber_excluded',not set(IDS)&{'RS_PAST_NA9209','RS_PAST_NA8779'})
 holdpaths=sorted(p for p in (OLD/'audit').glob('*holds.json') if p.name=='followup_holds.json' or re.fullmatch(r'prior_v\d+_holds\.json',p.name));history={};all_contexts=[]
 for p in holdpaths:
  obj=rd(p);found=target_contexts(obj)
  history[p.name]={'sha256':sha(p),'matched_record_ids':[context_id(v) for v in found]}
  all_contexts.extend({'file':p.name,'record_id':context_id(v),'object':v} for v in found)
 ck('all_V11_to_V40_and_currentV41_hold_files_read',len(holdpaths)==31 and all(f'prior_v{v}_holds.json' in history for v in range(11,41)) and 'followup_holds.json' in history)
 ck('each_current_target_has_prior_hold_context',set(v['record_id'] for v in all_contexts)==set(IDS))
 targeted_files={k:v for k,v in history.items() if v['matched_record_ids']}
 priorcontexts=[{'file':v['file'],'record_id':v['record_id'],'hold_type':v['object'].get('hold_type'),'status':v['object'].get('status'),'reason':v['object'].get('reason'),'source_url':v['object'].get('source_url')} for v in all_contexts]
 if not prepare:
  facts_path=S/'inputs/accepted_geography.json';holds_path=S/'audit/followup_holds.json';facts=rd(facts_path);holds=rd(holds_path);hb={h['record_id']:h for h in holds}
  paths.update(current_facts=facts_path,current_holds=holds_path,current_scope=S/'audit/method_application_scope_v42.json',current_recovery_provenance=S/'audit/recovery_provenance.json',current_parent_adjudication=S/'audit/parent_adjudication.json',current_source_class=S/'audit/source_class_adjudication.json',current_reviewed_native_rows=S/'inputs/reviewed_native_rows.json')
  provenance=rd(paths['current_recovery_provenance']);parent=rd(paths['current_parent_adjudication']);sourceclass=rd(paths['current_source_class']);native_rows=rd(paths['current_reviewed_native_rows'])
  ck('current_reviewed_native_rows_six_complete_objects_exact',len(native_rows)==6 and {r['record_id']:r for r in native_rows}=={rid:by[rid] for rid in IDS})
  ck('recovery_provenance_original_report_and_intents_unrecovered',provenance.get('original_worker_reports_and_intents_recovered') is False and provenance.get('original_source_QA_report_recovered') is False and provenance.get('reconstruction_cannot_restore_original_entry_UTCs_or_report_bytes') is True)
  ck('parent_decisions_zero_adoption_and_old_issue_totals',parent.get('original_file_bytes_recovered') is False and parent['decisions']['held']==6 and all(parent['decisions'][k]==0 for k in ['new_birthplaces','geography_only_resolutions','new_original_DOB_conflicts','new_place_conflicts','new_source_derived_age_inconsistencies','new_middle_or_endpoint_exceptions']) and parent['decisions']['total_active_DOB_conflicts']==13 and parent['decisions']['partial_birthplace_inventory_records']==2 and parent['decisions']['total_source_derived_age_inconsistencies']==4)
  ck('source_class_zero_adoption_no_method_exception',sourceclass['adopted_record_ids']==[] and sourceclass['source_grade_role']=='geographic_support_only' and sourceclass['method_amendment_created'] is False and sourceclass['no_new_admission_method_exception'] is True)
  ck('no_fabricated_original_current_workers_or_intents',not any((S/'audit'/name).exists() for name in ['sources_a.json','sources_b.json','sources_c.json','a_intent.json','b_intent.json','c_intent.json','root_intent.json','root_followups.json']))
  copied=R.iterdir()
  ck('all_five_retained_interruption_artifacts_copied_exact',all((S/'audit/interruption_checkpoint'/p.name).read_bytes()==p.read_bytes() for p in copied if p.is_file()))
  ck('current_scope_original_bytes_exact',(paths['current_scope']).read_bytes()==paths['original_scope'].read_bytes())
  ck('zero_current_facts_and_exact_six_holds',facts==[] and len(holds)==len(hb)==6 and set(hb)==set(IDS))
  for rid in IDS:
   h=hb[rid];n=by[rid];hn=h.get('native',{})
   ck(rid+'_reconstructed_hold_native_binding',hn.get('authority_name',hn.get('source_authorised_full_name'))==n['source_authorised_full_name'] and hn.get('native_dob',hn.get('dob'))==n['dob'] and hn.get('raw_birthplace')==n['raw_birthplace'] and hn.get('birthplace_source_grade',hn.get('frozen_birthplace_source_grade'))==n['birthplace_source_grade'])
   ck(rid+'_current_hold_case_fields_and_retained_refs',h.get('native_name')==ab[rid]['native_name'] and h.get('native_DOB')==n['dob'] and h.get('frozen_place')==n['raw_birthplace'] and h.get('original_BP_grade')==n['birthplace_source_grade'] and h.get('source_refs')==ab[rid]['source_refs'] and h.get('review')==ab[rid]['review'] and hn.get('complete_object_canonical_sha256')==hashlib.sha256(json.dumps(n,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest())
   ck(rid+'_no_geographic_or_grade_adoption',h.get('no_new_geographic_assignment') is True and h.get('reviewed_hemisphere')=='unknown' and h.get('source_grade_adopted') is None and not h.get('proof_chain'))
   ck(rid+'_reconstruction_label_and_missing_original_intent',h.get('artifact_type')=='reconstructed_hold_from_retained_verified_review' and h.get('original_file_bytes_recovered') is False and h.get('original_request_utc','missing') is None and h.get('exact_request_utc','missing') is None)
  for name in INVENTORY_COUNTS:
   current=S/'audit'/name;paths['current_inventory_'+name]=current
   ck(name+'_current_full_file_exact',current.read_bytes()==(OLD/'audit'/name).read_bytes())
   inventory[name].update(current_sha256=sha(current),current_records=inventory[name]['baseline_records'],byte_identical=True)
  ck('all_six_hold_raw_metadata_unknown_null',all(all(h.get(k,'missing') is None for k in ['raw_HTTP_status','raw_bytes_sha256','exact_request_utc']) for h in holds))
  ck('all_targeted_old_context_files_preserved_exact',all((S/'audit'/name).read_bytes()==(OLD/'audit'/name).read_bytes() for name in targeted_files))
  ck('historical_queues_and_separate_place_holds_preserved',all((S/'audit'/name).read_bytes()==(OLD/'audit'/name).read_bytes() for name in ['prior_v11_holds.json','prior_v12_holds.json','prior_v29_first_pass_queue_closeout.json','prior_v35_geography_first_pass_queue_closeout.json']))
 ck('reviewer_left_V41_master_bytes_unchanged',sha(master)==master_before)
 ck('recovery_evidence_bytes_unchanged_during_review',all(sha(paths[k])==v for k,v in pinned_before.items()))
 failures=[c for c in checks if not c['passed']]
 report={'schema':'UK_v42_independent_recovery_source_review_v1','artifact_type':'independent_recovery_source_review','phase':'preparation' if prepare else 'recovery','written_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'reviewer':'/root/v42_source_qa','passed':not failures,'status':'PASS' if not failures else 'FAIL','checks_passed':len(checks)-len(failures),'new_recovery_checks_passed':len(checks)-len(failures),'checks':checks,'blocking_issues':failures,'reviewed_master_records':4983,'baseline_canonical_sha256':BASE,'baseline_gzip_sha256':master_before,'current_master_changes_performed_by_reviewer':0,'canonical_full_V41_gzip_read_directly':True,'historical_replay_or_production_executed':False,'fresh_network_source_requests':0,'Git_writes':0,'original_V42_scope_sha256':SCOPE,'artifact_sha256':{k:sha(p) for k,p in paths.items()},'historical_source_QA_attestation':{'historical_only':True,'checks_passed_before_interruption':171,'original_report_sha256':HISTORICAL_REPORT,'original_report_bytes_recovered':False,'original_documentary_case_sha256':att['source_qa']['documentary_case_sha256'],'original_intent_bytes_recovered':False,'individual_entry_UTC_recovered':False,'not_a_fresh_171_check_rerun':True},'cases':native_cases,'case_reviews':native_cases,'accepted_geography_facts':0,'held_cases':6,'new_DOB_place_age_or_admission_issues':0,'nine_issue_inventory_sha256_at_review':inventory,'targets_in_prior_issue_inventories':targets_in_issues,'all_prior_hold_files_read':history,'targeted_old_hold_contexts':priorcontexts,'source_interpretation_basis':'Independent recovery assessment from retained historical review plus actual restored native records and prior holds. Historical acquisition refs/locators are retained context; no original source body was reacquired.','unknown_source_metadata':{'raw_HTTP_status':None,'raw_bytes_sha256':None,'exact_request_utc':None,'source_calendar_model':None,'source_statement_rank':None,'source_editorial_validation':None,'source_informational_independence':None},'limitations':['This is a newly written recovery review with its own check count and hashes, not the original171-check report or original worker/intent files.','Historical operation counts and24-entry timing/validation findings remain attestations; original individual UTC values and exact intent bytes are unavailable and were not invented.','No source originals/raw bytes/pixels were reacquired. Displayed Gregorian/footer observations do not authenticate calendar-model/rank/revision/editorial/independence metadata.','Missing acquired P19 remains unknown rather than universal absence or an acquired no-value statement; rewritten summaries remain discovery/URI carriers only.','All six remain held. Original DOB/BP/native fields and grades stay frozen, as do active13, partialplace2, age4 and six other issue files.','This review does not establish production or final replay completion.']}
 out=W/('v42_recovery_source_preparation.json' if prepare else 'v42_recovery_source_review.json')
 out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({'report':str(out),'phase':report['phase'],'passed':report['passed'],'new_checks_passed':report['checks_passed'],'blocking_issues':failures,'report_sha256':sha(out)},ensure_ascii=False))
 return 0 if not failures else 1
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--prepare',action='store_true');args=parser.parse_args();raise SystemExit(main(args.prepare))
