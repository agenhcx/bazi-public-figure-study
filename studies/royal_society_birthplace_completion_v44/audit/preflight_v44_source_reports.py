"""Light report-shape/operation precheck; no master rows, replay, network or mutations."""
import datetime,json
import qa_v44_source as q
W=q.W;S=q.S
checks=[]
def ck(name,ok):checks.append({'check':name,'passed':bool(ok)})
def main():
 app=q.rd(W/'v44_method_application_scope.json');plan=q.rd(W/'v44_plan.json');groups={};allops=[]
 for g in 'abc':
  r=q.rd(W/f'v44_sources_{g}.json');it=q.rd(W/f'v44_{g}_intent.json');ops=q.normalized_ops(r);actual=sum([list(v) for v in ops],[]);planned=it.get('entries',it.get('requests',[]));allops+=actual
  ck(g+'_scope_actual_method',r.get('method_id')==plan['method_id'] and r.get('method_preregistration_sha256')==q.BASE and r.get('method_application_scope_sha256')==q.SCOPE and ({v['record_id'] for v in r.get('candidates',[])}|{v['record_id'] for v in r.get('holds',[])})==set(plan['geography_followup_groups'][g]))
  ck(g+'_one_to_one_exact_operations',q.one_to_one_intents(actual,planned))
  ck(g+'_every_entry_UTC_after_scope',all(q.timestamp(e) is not None and q.timestamp(e)>=q.timestamp(app) for e in planned))
  ck(g+'_all9_inventory_pins',q.inventory_pins_present(it))
  ck(g+'_separate_validation_beforeweb',r.get('intent_writes_validated_exit0_separately_beforeweb') is True)
  ck(g+'_bounded_queries_navigation',len(ops[0])<=4 and len(ops[1])<=10)
  ck(g+'_explicit_kind_ledgers',all(q.opkind(v)=='search' for v in ops[0]) and all(q.opkind(v) in {'open','click'} for v in ops[1]) and all(q.opkind(v)=='find' for v in ops[2]))
  ck(g+'_reported_same_work_deviation_is_exact_and_contained',not r.get('same_work_canonical_followthrough_disclosure') or q.documented_contained_same_work_deviation(r))
  ck(g+'_actual_report_counts',r['retrieval_counts']['queries']==len(ops[0]) and r['retrieval_counts']['navigation_attempts']==len(ops[1]) and r['retrieval_counts'].get('parsed_finds',r['retrieval_counts'].get('cached_finds'))==len(ops[2]))
  groups[g]={'queries':len(ops[0]),'navigation':len(ops[1]),'opens':sum(q.opkind(v)=='open' for v in ops[1]),'clicks':sum(q.opkind(v)=='click' for v in ops[1]),'finds':len(ops[2]),'actual_operations':len(actual),'intent_entries':len(planned)}
 root=q.rd(S/'audit/root_followups.json');intent=q.rd(S/'audit/root_intent.json');parent=q.rd(S/'audit/parent_adjudication.json');obs=root['observations']
 sourceclass=q.rd(S/'audit/source_class_adjudication.json')
 ck('actual_parent_class_no_new_method_amendment_fields',all(d.get('method_amendment_created') is False and d.get('no_new_admission_method_exception') is True for d in [parent,sourceclass]))
 ck('root_one_to_one_exact_operation_intents',q.one_to_one_intents(obs,intent['entries']))
 ck('all_worker_root_entries_UTC_before_parent',all(q.timestamp(e) is not None and q.timestamp(app)<=q.timestamp(e)<q.timestamp(parent) for e in intent['entries']+[e for g in 'abc' for e in q.rd(W/f'v44_{g}_intent.json').get('entries',[])]))
 ck('root_all9_inventory_pins',q.inventory_pins_present(intent))
 ck('root_known_actual_operation_kinds',all(q.opkind(v) in {'search','open','click','find'} for v in obs))
 semantic=q.rd(W/'v44_source_documentary_case_review.json');facts=q.rd(S/'inputs/accepted_geography.json');holds=q.rd(S/'audit/followup_holds.json');native={v['record_id']:v for g in 'abc' for v in q.rd(W/f'v44_scope_{g}.json')}
 ck('five_semantic_cases_native_person_components_DOB_place',len(semantic['case_reviews'])==5 and {c['record_id'] for c in semantic['case_reviews']}==set(native) and all(sorted(q.nativeparts(c['native_name']))==sorted(q.native_components(native[c['record_id']])) and c['native_DOB']==native[c['record_id']]['dob'] and c['frozen_place']==native[c['record_id']]['raw_birthplace'] for c in semantic['case_reviews']))
 ck('all_held_native_BP_grade_and_unknown_metadata_fields',all(q.first(h['native'],['frozen_birthplace_source_grade','birthplace_source_grade','prior_birthplace_source_grade','existing_birthplace_source_grade'])==native[h['record_id']]['birthplace_source_grade'] and all(h.get(k,'missing') is None for k in ['source_calendar_model','source_statement_rank','source_editorial_validation','source_informational_independence','raw_HTTP_status','raw_bytes_sha256','exact_request_utc']) for h in holds))
 prior=[p for p in (q.OLD/'audit').rglob('*') if p.is_file()]
 def archived(p):
  rel=p.relative_to(q.OLD/'audit');first=rel.parts[0]
  return S/'audit'/q.pathlib.Path(first if first.startswith('prior_') else 'prior_v43_'+('holds.json' if first=='followup_holds.json' else first),*rel.parts[1:])
 ck('all_previous_audits_actual_archival_paths_and_bytes',all(archived(p).exists() and archived(p).read_bytes()==p.read_bytes() for p in prior))
 quote=q.rd(W/'v44_source_qa_quote_prefinal.json')
 ck('actual_quote_prefinal_pass_under25_no_unattributed',quote['passed'] is True and quote['unattributed_quotations']==[] and all(0<=v<=25 for v in quote['original_work_distinct_whitespace_quoted_word_counts'].values()))
 paths={'facts':S/'inputs/accepted_geography.json','holds':S/'audit/followup_holds.json','parent':S/'audit/parent_adjudication.json','root':S/'audit/root_followups.json','root_intent':S/'audit/root_intent.json','protocol_deviations':S/'audit/source_protocol_deviations.json',**{f'worker_{g}':S/'audit'/f'sources_{g}.json' for g in 'abc'},**{f'worker_intent_{g}':S/'audit'/f'{g}_intent.json' for g in 'abc'}}
 ck('semantic_hashes_bind_actual12_artifacts',semantic['artifact_sha256']=={k:q.sha(p) for k,p in paths.items()})
 deviations=q.rd(paths['protocol_deviations'])
 ck('actual_root_class_deviation_disclosure_fields',deviations==parent['source_protocol_deviations']==sourceclass['source_protocol_deviations'] and len(deviations)==1 and parent['all_collection_work_closures_clean'] is sourceclass['all_collection_work_closures_clean'] is False)
 current=native['RS_CURRENT_10965'];binding=app['native_identity_bindings']['RS_CURRENT_10965']
 ck('actual_CURRENT_nonempty_native_name_empty_authority_aliases_shape',current['source_authorised_full_name']==binding['native_authority_field']=='' and current['name']==binding['native_personal_name']=='Jerry Adams' and bool(q.native_components(current)) and current['geography_lookup_identity_review']['wikidata_aliases']==binding['frozen_full_aliases'])
 ck('source_scope_original_bytes',(S/'audit/method_application_scope_v44.json').read_bytes()==(W/'v44_method_application_scope.json').read_bytes())
 ck('all_seven_legacy_scope_files_exact',all((S/'audit'/n).read_bytes()==(q.OLD/'audit'/n).read_bytes() for n in app['legacy_application_scope_file_sha256']))
 failures=[v for v in checks if not v['passed']];out={'schema':'UK_v44_source_report_shape_precheck_v1','phase':'worker_root_operation_prefinal_documentary_review','written_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'passed':not failures,'historical_reconstruction_or_CLI_invoked':False,'groups':groups,'root_operation_counts':{k:sum(q.opkind(v)==k for v in obs) for k in ['search','open','click','find']},'checks':checks,'blocking_issues':failures}
 (W/'v44_source_qa_worker_operation_prefinal.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'passed':out['passed'],'checks':len(checks),'groups':groups,'root':out['root_operation_counts'],'blocking_issues':failures}));return 0 if not failures else 1
if __name__=='__main__':raise SystemExit(main())
