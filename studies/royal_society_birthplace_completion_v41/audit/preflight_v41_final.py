"""Read-only final report/ledger/inventory shape checks; never loads master rows or replay."""
import ast,datetime,json,pathlib,traceback
import qa_v41_final as q
W=q.W;S=q.S;OLD=q.OLD
checks=[]
def ck(name,condition):
    assert condition,name
    checks.append(name)
def main():
    E=q.read(W/'v41_final_qa_expectations.json')
    ck('expectations_have_canonical_ids_sourcecounts_and_explicit_append_mapping',
       isinstance(E['final_canonical_sha256'],str) and len(E['final_canonical_sha256'])==64
       and isinstance(E['accepted_record_ids'],list) and isinstance(E['source_counts'],dict)
       and isinstance(E.get('approved_issue_appends',{}),dict))
    source=q.read(S/'audit/independent_source_qa.json')
    inv_hashes=source['nine_issue_inventory_sha256_at_review'];inv_counts=source['nine_issue_inventory_counts_at_review']
    ck('sourceqa_passed_final_shape',source['passed'] is True and source['phase']=='final' and source['blocking_issues']==[]
       and source['checks_passed']==len(source['checks']) and all(c['passed'] for c in source['checks'])
       and isinstance(source['accepted_geographic_bindings'],list)
       and source['accepted_fact_sha256_at_review']==source['accepted_geography_sha256_at_review']==q.sha(S/'inputs/accepted_geography.json')
       and set(source['declared_six_GEO_FIELDS'])==q.GEO_FIELDS
       and source['no_new_admission_method_exception'] is True and source['explicit_prospective_admission_method_amendment'] is False)
    ck('all9_inventory_names',set(inv_hashes)==set(inv_counts)==set(q.SIDECARS))
    inventory_summary={}
    for name in q.SIDECARS:
        old=q.read(OLD/'audit'/name);new=q.read(S/'audit'/name)
        ck(name+'_sha_shape_count',inv_hashes[name]['baseline_sha256']==q.sha(OLD/'audit'/name)
           and inv_hashes[name]['current_sha256']==q.sha(S/'audit'/name)
           and q.inventory_counts_match(inv_counts[name],old,new))
        oldrs=q.issue_records(old);newrs=q.issue_records(new)
        approved=E.get('approved_issue_appends',{}).get(name,[])
        ck(name+'_oldobjects_and_authorized_appends',newrs[:len(oldrs)]==oldrs and len(newrs)>=len(oldrs)
           and [r['record_id'] for r in newrs[len(oldrs):]]==approved)
        if approved:
            ck(name+'_snapshot',name!='omitted_middle_name_admission.json'
               and (S/'audit'/('prior_v40_'+name)).read_bytes()==(OLD/'audit'/name).read_bytes())
        else:
            ck(name+'_wholefile_exact',(S/'audit'/name).read_bytes()==(OLD/'audit'/name).read_bytes())
        inventory_summary[name]=dict(inv_counts[name])
    bindings={
        'followup_holds_sha256_at_review':'audit/followup_holds.json',
        'parent_adjudication_sha256_at_review':'audit/parent_adjudication.json',
        'root_followups_sha256_at_review':'audit/root_followups.json',
        'root_intent_sha256_at_review':'audit/root_intent.json',
        'active_DOB_conflicts_sha256_at_review':'audit/active_source_DOB_conflicts.json',
        'birthplace_source_conflicts_sha256_at_review':'audit/birthplace_source_conflicts.json',
        'source_derived_age_inconsistencies_sha256_at_review':'audit/source_derived_age_inconsistencies.json',
        'source_class_adjudication_sha256_at_review':'audit/source_class_adjudication.json',
        'method_preregistration_sha256_at_review':'audit/method_preregistration.json',
        'method_schema_sha256_at_review':'METHOD_SCHEMA.md',
        'method_application_scope_sha256_at_review':'audit/method_application_scope_v41.json',
        'legacy_V37_method_application_scope_sha256_at_review':'audit/method_application_scope.json',
        'legacy_V38_method_application_scope_sha256_at_review':'audit/method_application_scope_v38.json',
        'legacy_V39_method_application_scope_sha256_at_review':'audit/method_application_scope_v39.json',
        'legacy_V40_method_application_scope_sha256_at_review':'audit/method_application_scope_v40.json',
        'historical_v35_geography_first_pass_queue_closeout_sha256_at_review':'audit/prior_v35_geography_first_pass_queue_closeout.json',
        'historical_v29_first_pass_queue_closeout_sha256_at_review':'audit/prior_v29_first_pass_queue_closeout.json'}
    ck('all_sourceqa_tail_bindings_actual',all(source[k]==q.sha(S/p) for k,p in bindings.items()))
    ck('worker_report_and_intent_binding_shapes',source['worker_source_report_sha256_at_review']=={g:q.sha(S/'audit'/f'sources_{g}.json') for g in 'abc'}
       and source['worker_intent_sha256_at_review']=={g:q.sha(S/'audit'/f'{g}_intent.json') for g in 'abc'})
    parent=q.read(S/'audit/parent_adjudication.json');root=q.read(S/'audit/root_followups.json')
    decisions=parent['decisions'];rc=root['counts'];obs=root['observations']
    needed=['new_birthplaces','geography_only_resolutions','held','new_source_derived_age_inconsistencies','total_source_derived_age_inconsistencies','new_original_DOB_conflicts','total_active_DOB_conflicts']
    ck('parent_tail_fields_actual',all(k in decisions for k in needed))
    workers=[q.read(W/f'v41_sources_{g}.json') for g in 'abc']
    for g,r in zip('abc',workers):
        ck('worker_'+g+'_report_copy',(S/'audit'/f'sources_{g}.json').read_bytes()==(W/f'v41_sources_{g}.json').read_bytes())
        ck('worker_'+g+'_ledger_shapes',isinstance(r['query_ledger'],list) and isinstance(r['navigation_ledger'],list)
           and isinstance(r.get('parsed_find_ledger',[]),list)
           and all(isinstance(i.get('queries',[i.get('query')]),list) for i in r['query_ledger'])
           and all(k in r['retrieval_counts'] for k in ['screenshots','raw_GETs']))
    qops=sum(sum(len(i.get('queries',[i.get('query')])) for i in r['query_ledger']) for r in workers)
    navs=[i for r in workers for i in r['navigation_ledger']]
    opens=sum(i.get('kind',i.get('operation')) in {'open','cached_context_open'} for i in navs)
    clicks=sum(i.get('kind',i.get('operation'))=='click' for i in navs)
    finds=sum(len(r.get('parsed_find_ledger',[])) for r in workers)
    opcounts={op:sum(i['operation']==op for i in obs) for op in sorted({i['operation'] for i in obs})}
    ck('root_query_open_click_find_operation_shape',rc['source_open_operations']==sum(i['operation']=='open' for i in obs)
       and rc['click_operations']==sum(i['operation']=='click' for i in obs)
       and rc['discovery_queries']==sum(i['operation']=='query' or i['operation'].endswith('_query') for i in obs)
       and rc['parsed_finds']==sum(i['operation'] in {'find','parsed_find'} for i in obs)
       and len(obs)==rc['source_open_operations']+rc['click_operations']+rc['discovery_queries']+rc['parsed_finds']
       and opens+clicks==len(navs))
    recomputed={'worker_queries':qops,'root_queries':rc['discovery_queries'],'total_queries':qops+rc['discovery_queries'],
        'worker_navigation_attempts':len(navs),'worker_source_open_operations':opens,'worker_click_operations':clicks,
        'root_source_opens':rc['source_open_operations'],'root_click_operations':rc['click_operations'],
        'total_navigation_attempts':len(navs)+rc['source_open_operations']+rc['click_operations'],
        'total_source_open_operations':opens+rc['source_open_operations'],'total_click_operations':clicks+rc['click_operations'],
        'worker_parsed_finds':finds,'root_parsed_finds':rc['parsed_finds'],'total_parsed_finds':finds+rc['parsed_finds'],
        'screenshots':sum(r['retrieval_counts']['screenshots'] for r in workers)+rc['screenshots'],
        'raw_GETs':sum(r['retrieval_counts']['raw_GETs'] for r in workers)+rc['raw_GETs']}
    ck('sourcecount_recomputation',recomputed==E['source_counts']==parent['source_counts'])
    ck('all_isolated_runtime_auditfiles_present',all((S/'audit'/name).is_file() for name in ['followup_holds.json','method_preregistration.json',*q.SCOPE_HASHES]))
    pins=q.read(S/'audit/main_output_before_QA_sha256.json')['files']
    ck('five_pinfile_outputs_exact',set(pins)=={'birthplace_rows.jsonl.gz','birthplaces.csv','changes.json','remaining_unknown_window.csv','summary.json'}
       and all(q.sha(S/'outputs'/name)==h for name,h in pins.items()))
    documentary=q.read(S/'audit/v41_source_documentary_case_review.json');protocol=source['documentary_protocol_review']
    documentary_pins={'audit/v41_source_documentary_case_review.json':source['documentary_semantic_case_review_sha256_at_review'],
       'audit/'+protocol['quote_prefinal_report_path']:protocol['quote_prefinal_report_sha256'],
       'audit/'+protocol['worker_operation_prefinal_report_path']:protocol['worker_operation_prefinal_report_sha256']}
    ck('all3_documentary_artifact_pins_and_exact_copies',all(q.sha(S/path)==h and (S/path).read_bytes()==(W/pathlib.Path(path).name).read_bytes() for path,h in documentary_pins.items()))
    native={r['record_id']:r for g in 'abc' for r in q.read(W/f'v41_scope_{g}.json')}
    ck('six_documentary_cases_exact_sourceqa_and_frozen_personal_name_DOB_place',
       source['documentary_semantic_case_reviews']==documentary['case_reviews'] and len(documentary['case_reviews'])==6
       and {c['record_id'] for c in documentary['case_reviews']}==set(native)
       and all(c['native_name']==native[c['record_id']]['name']+' '+native[c['record_id']]['source_authorised_full_name'].split(';',1)[0]
       and c['native_DOB']==native[c['record_id']]['dob'] and c['frozen_place']==native[c['record_id']]['raw_birthplace'] for c in documentary['case_reviews']))
    artifact_paths={'facts':'inputs/accepted_geography.json','holds':'audit/followup_holds.json','parent':'audit/parent_adjudication.json','root':'audit/root_followups.json','root_intent':'audit/root_intent.json',
       **{'worker_'+g:'audit/sources_'+g+'.json' for g in 'abc'},**{'worker_intent_'+g:'audit/'+g+'_intent.json' for g in 'abc'}}
    ck('documentary_binds_all11_actual_artifacts',documentary['artifact_sha256']=={k:q.sha(S/path) for k,path in artifact_paths.items()})
    docs={name:(S/name).read_text() for name in ['README.md','CONTINUATION.md']}
    ck('docs_current_canonical_no_placeholders',all(E['final_canonical_sha256'] in text and 'v41' in text.lower()
       and not any(t in text for t in ['AWAIT_','PLACEHOLDER','PENDING']) for text in docs.values()))
    dist=[p for p in S.rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    ck('no_distributed_source_caches',not any(p.suffix.lower() in {'.html','.htm','.pdf','.png','.jpg','.jpeg','.webp','.har','.ttl','.rdf'} for p in dist)
       and not any('cache' in p.name.lower() for p in dist))
    ast.parse((W/'qa_v41_final.py').read_text())
    report={'schema':'UK_v41_final_QA_report_shape_precheck_v1','status':'PASS','written_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
       'historical_reconstruction_or_CLI_invoked':False,'checks':checks,'source_counts':recomputed,
       'root_observation_operation_counts':opcounts,'inventory_summary':inventory_summary,
       'documentation_sha256':{name:q.sha(S/name) for name in docs},'production_mutated':False,'network_used':False}
    (W/'v41_final_qa_report_shape_precheck.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'status':'PASS','checks':len(checks),'root_operation_counts':opcounts,'source_counts':recomputed},ensure_ascii=False))
if __name__=='__main__':
    try:main()
    except BaseException as e:
        report={'schema':'UK_v41_final_QA_shape_precheck_failure_v1','status':'FAIL','written_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
           'checks_passed':checks,'error_type':type(e).__name__,'error':str(e),'traceback':traceback.format_exc(),
           'production_mutated':False,'network_used':False,'historical_reconstruction_or_CLI_invoked':False}
        (W/'v41_final_qa_shape_precheck_failure_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        raise
