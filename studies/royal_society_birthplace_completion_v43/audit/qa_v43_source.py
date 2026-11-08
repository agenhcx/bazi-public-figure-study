"""V43 independent documentary source QA. No network, facts, production or Git edits."""
import argparse,ast,datetime,gzip,hashlib,json,pathlib,re,unicodedata
W=pathlib.Path(__file__).resolve().parent
S=W/'academy_repo/studies/royal_society_birthplace_completion_v43'; OLD=S.with_name('royal_society_birthplace_completion_v42')
BASE='b76b7ad55125b1cf2dffe7d847d013f7fb8c2a6c8868c66f1e3060efae471147'
SCOPE='b25ef3f4bbf1f3e5dddd48531812a60e40d1383b897a0d3d044b0604e62db212'
LEGACY_V42_SCOPE='c5c7594d271b6923725acad91612b8f53b3528383d3bf50f0658ccfa0e639796'
LEGACY_V41_SCOPE='d6ebcba7aa672c1a4877857bd4e9b4072af2ae159c04fd0dddf4d7766d2e3176'
LEGACY_V40_SCOPE='b44c66bc0d7883aeef9650578d0b339a65b563942da3fe72976b05c0094cc1fc'
LEGACY_V39_SCOPE='cc12b3159a035064dbde6a35e0778642fdb25d988e9e399617b216062127b17e'
LEGACY_V38_SCOPE='bd7540715a6b4649ffe79371e38ee2b650bd0176013fbb5418efa02b8995fad0'
LEGACY_SCOPE='ae080b06f8abad9ed7575783486795c977e44ce5e5024bfa2096e16816a44d94'
CANON='a0c04e44631478f82e562deab64d699fc273e6fc99fa35ba23f8a61d7e1f8717'
GEO={'hemisphere','geo_resolution_status','geography_decision','reason','northern_birthplace_candidate','southern_birthplace_separate'}
SIDE=['provisional_parsed_date_discrepancies.json','source_date_precision_holds.json','source_derived_age_inconsistencies.json','lifespan_endpoint_discrepancies.json','cross_source_reported_age_contrasts.json','omitted_middle_name_admission.json','source_ordinal_age_wording_observations.json']
PROOFS={'direct_born_region_in_actual_canonical_person_body','explicit_person_born_place_hyperlink_then_actual_target_place_region','actual_person_P19_entity_then_actual_P131_admin_chain_to_whole_region'}
checks=[];warnings=[]
def rd(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def ck(n,v,detail=None):
 r={'check':n,'passed':bool(v)}
 if detail is not None:r['detail']=detail
 checks.append(r)
def norm(s):return re.sub(r'[^a-z0-9]+',' ',unicodedata.normalize('NFKD',str(s)).encode('ascii','ignore').decode().lower()).strip()
def nativeparts(n):return [x for x in norm(re.split(r'\(\d{4}\s*-\s*\d{4}\)',n,maxsplit=1)[0]).split() if x not in {'sir','dame','lord','lady','dr','prof','professor'}]
def actual_words(f):return len(str(f or '').split())
def normalized_ops(r):
 ops=r.get('request_ledger',[])
 raw=r.get('query_ledger',r.get('query_log',[v for v in ops if opkind(v)=='search']))
 q=[]
 for b in raw:
  if 'queries' in b:q.extend({k:v for k,v in b.items() if k!='queries'}|{'query':x} for x in b['queries'])
  else:q.append(b)
 nav=r.get('navigation_ledger',r.get('navigation_log',[v for v in ops if opkind(v) in {'open','click'}]))
 finds=r.get('parsed_find_ledger',r.get('find_ledger',[v for v in ops if opkind(v)=='find']))
 return q,nav,finds
def timestamp(d):
 for k in ['written_before_requests_utc','saved_utc','written_utc','created_utc']:
  if d.get(k):
   try:
    value=datetime.datetime.fromisoformat(d[k])
    return value if value.utcoffset()==datetime.timedelta(0) else None
   except (ValueError,TypeError):return None
 return None
def descendants(d):
 yield d
 if isinstance(d,dict):
  for v in d.values():yield from descendants(v)
 elif isinstance(d,list):
  for v in d:yield from descendants(v)
def inventory_pins_present(d):
 names=SIDE+['birthplace_source_conflicts.json','active_source_DOB_conflicts.json']
 return any(isinstance(v,dict) and all(v.get(n)==sha(OLD/'audit'/n) for n in names) for v in descendants(d))
def opkind(d):
 k=d.get('operation',d.get('kind',''))
 return {'query':'search','cached_context_open':'open','context_open':'open','cached_find':'find','source_locator_query':'search'}.get(k,k)
def request(d):
 return dict(d)|d.get('exact_request',{})
def querytext(d):
 d=request(d);return d.get('query',d.get('q',d.get('exact_query')))
def inventory_records(d):
 return d if isinstance(d,list) else d.get('records') if isinstance(d,dict) and isinstance(d.get('records'),list) else None
def inventory_metadata(d):
 return {k:v for k,v in d.items() if k!='records'} if isinstance(d,dict) else None
def first(d,keys):return next((d[k] for k in keys if d.get(k) is not None),None)
def intent_matches(actual,planned):
 actual=request(actual);planned=request(planned)
 k=opkind(actual)
 if k!=opkind(planned):return False
 if k=='search':return querytext(actual)==querytext(planned) and bool(querytext(actual)) and (not actual.get('engine') or not planned.get('engine') or actual['engine']==planned['engine']) and all(actual.get(key)==planned.get(key) for key in ['domains','recency'] if key in actual or key in planned)
 if k=='click':
  al=first(actual,['link_id','exact_link_id','id']);pl=first(planned,['link_id','exact_link_id','id'])
  ar=first(actual,['from_ref','ref_id','exact_from_ref','exact_ref_id']);pr=first(planned,['from_ref','ref_id','exact_from_ref','exact_ref_id'])
  return al is not None and al==pl and ar is not None and ar==pr
 if k=='find':
  ap=first(actual,['pattern','exact_pattern']);pp=first(planned,['pattern','exact_pattern']);ar=first(actual,['from_ref','ref_id','exact_ref_id']);pr=first(planned,['from_ref','ref_id','exact_ref_id'])
  return bool(ap) and ap==pp and bool(ar) and ar==pr
 if k=='open':
  au=first(actual,['url','actual_url','observed_url','exact_url','source_url']);pu=first(planned,['url','observed_url','exact_url','ref_id','exact_ref_id','source_url'])
  ar=first(actual,['request_ref','opened_ref','ref_id','exact_ref_id']);pr=first(planned,['ref_id','exact_ref_id'])
  same_target=(au is not None and au==pu) or (ar is not None and ar==pr)
  same_selectors=all(actual[k]==planned[k] for k in ['lineno','num_lines'] if k in actual and k in planned)
  return same_target and same_selectors
 return False
def one_to_one_intents(actual,planned):
 if len(actual)!=len(planned):return False
 remaining=list(planned)
 for op in actual:
  matches=[i for i,e in enumerate(remaining) if intent_matches(op,e)]
  if not matches:return False
  remaining.pop(matches[0])
 return not remaining

def age_arithmetic_matches(age):
 try:
  b=datetime.date.fromisoformat(age['observed_source_birthdate']);d=datetime.date.fromisoformat(age['observed_source_death_date'])
  completed=d.year-b.year-((d.month,d.day)<(b.month,b.day))
  return completed==age.get('arithmetic_age_from_observed_dates') and age.get('observed_reported_age')!=completed
 except (KeyError,ValueError,TypeError):return False

def extent_supported(f,terminal):
 label=norm(terminal.get('target_label',''))
 if label in {'england','scotland','wales','northern ireland','germany','deutschland','federal republic of germany','bundesrepublik deutschland'}:return f.get('reviewed_hemisphere')=='north'
 # Other extents require a concrete existing extent gate documented in the acquired dossier.
 review=f.get('whole_region_extent_review',{})
 return isinstance(review,dict) and review.get('existing_gate_applied') is True and review.get('whole_region_single_hemisphere') is True and review.get('hemisphere')==f.get('reviewed_hemisphere') and bool(review.get('existing_gate_locator')) and bool(review.get('region_scope')) and review.get('historical_colonial_empire_used') is False and review.get('nationality_inference_used') is False

def main(final=False):
 checks.clear();warnings.clear()
 plan=rd(W/'v43_plan.json');application=rd(W/'v43_method_application_scope.json');prereg=rd(W/'v36_method_preregistration.json')
 data=gzip.decompress((OLD/'outputs/birthplace_rows.jsonl.gz').read_bytes());rows=[json.loads(x) for x in data.splitlines()];by={r['record_id']:r for r in rows};groups=plan['geography_followup_groups'];ids=sum(groups.values(),[])
 pool={r['record_id'] for r in rows if r.get('raw_birthplace') and r.get('hemisphere')=='unknown' and '1835-01-01'<=r['dob']<='1985-12-31'}
 blanks={r['record_id'] for r in rows if not r.get('raw_birthplace') and '1835-01-01'<=r['dob']<='1985-12-31'}
 ck('actual_v42_baseline_canonical_pin',hashlib.sha256(data).hexdigest()==CANON==plan['baseline_canonical_sha256']==application['baseline_canonical_sha256'])
 ck('fixed4983_unique_native_records',len(rows)==len(by)==4983)
 ck('actual54_nonblankunknown_window_pool',len(pool)==plan['fixed_nonblank_unknown_window_pool']==application['fixed_nonblank_unknown_window_pool']==54)
 ck('fixed6_scope_threegroups2',set(groups)==set('abc') and all(len(v)==2 for v in groups.values()) and len(ids)==len(set(ids))==6)
 ck('scope_within_actual_nonblankunknown_pool',set(ids)<=pool)
 ck('complete_target_scope_objects_exactbaseline',all(rd(W/f'v43_scope_{g}.json')==[by[i] for i in gi] for g,gi in groups.items()))
 ck('103blank_window_outside_scope',len(blanks)==103 and not(set(ids)&blanks))
 ck('zero_firstbirthplace_groups',plan['first_birthplace_followup_groups']=={})
 active=rd(OLD/'audit/active_source_DOB_conflicts.json')['records'];activeids={r['record_id'] for r in active}
 ck('all13_activeDOBcases_excluded',len(active)==13 and all(c['active'] is True for c in active) and not(set(ids)&activeids))
 ck('Ewins_Barber_separate_placeholds_excluded',not(set(ids)&{'RS_PAST_NA9209','RS_PAST_NA8779'}))
 partial=rd(OLD/'audit/birthplace_source_conflicts.json')['records'];ck('both_partialplacecases_excluded',len(partial)==2 and not(set(ids)&{c['record_id'] for c in partial}))
 prov=rd(OLD/'audit/provisional_parsed_date_discrepancies.json')['records'];ck('Tomes_provisional_separate_not14thactive',len(prov)==1 and prov[0]['record_id']=='RS_PAST_NA2684' and prov[0]['record_id'] not in activeids)
 inherited_ages=inventory_records(rd(OLD/'audit/source_derived_age_inconsistencies.json'))
 ck('four_inherited_agequality_cases_retained',len(inherited_ages)==4 and len({v['record_id'] for v in inherited_ages})==4)
 ck('omitted_middle_metadata_has_no_records_array',inventory_records(rd(OLD/'audit/omitted_middle_name_admission.json')) is None)
 ck('historical_V36_preregistration_exact_SHA',sha(W/'v36_method_preregistration.json')==BASE==plan['method_preregistration_sha256']==application['method_preregistration_sha256'])
 oldids=set(rd(OLD/'inputs/geography_followup_ids.json'));ck('historical_V36_policy_fixedscope_preserved',set(prereg['fixed_record_ids'])==set(rd(OLD/'audit/method_preregistration.json')['fixed_record_ids']) and set(ids).isdisjoint(set(prereg['fixed_record_ids'])))
 ck('historical_V37_application_scope_preserved_distinct_newscope',sha(OLD/'audit/method_application_scope.json')==LEGACY_SCOPE and set(ids).isdisjoint(set(rd(OLD/'audit/method_application_scope.json')['fixed_record_ids'])))
 ck('historical_V38_application_scope_preserved_distinct_newscope',sha(OLD/'audit/method_application_scope_v38.json')==LEGACY_V38_SCOPE and set(ids).isdisjoint(set(rd(OLD/'audit/method_application_scope_v38.json')['fixed_record_ids'])))
 ck('historical_V39_application_scope_preserved_distinct_newscope',sha(OLD/'audit/method_application_scope_v39.json')==LEGACY_V39_SCOPE and set(ids).isdisjoint(set(rd(OLD/'audit/method_application_scope_v39.json')['fixed_record_ids'])))
 ck('historical_V40_application_scope_preserved_distinct_newscope',sha(OLD/'audit/method_application_scope_v40.json')==LEGACY_V40_SCOPE and set(ids).isdisjoint(set(rd(OLD/'audit/method_application_scope_v40.json')['fixed_record_ids'])))
 ck('historical_V41_application_scope_preserved_distinct_newscope',sha(OLD/'audit/method_application_scope_v41.json')==LEGACY_V41_SCOPE and set(ids).isdisjoint(set(rd(OLD/'audit/method_application_scope_v41.json')['fixed_record_ids'])))
 ck('historical_V42_application_scope_preserved_distinct_newscope',sha(OLD/'audit/method_application_scope_v42.json')==LEGACY_V42_SCOPE and set(ids).isdisjoint(set(rd(OLD/'audit/method_application_scope_v42.json')['fixed_record_ids'])))
 ck('all_six_legacy_scope_paths_pinned_in_current_application',application.get('legacy_application_scope_file_sha256')=={'method_application_scope.json':LEGACY_SCOPE,'method_application_scope_v38.json':LEGACY_V38_SCOPE,'method_application_scope_v39.json':LEGACY_V39_SCOPE,'method_application_scope_v40.json':LEGACY_V40_SCOPE,'method_application_scope_v41.json':LEGACY_V41_SCOPE,'method_application_scope_v42.json':LEGACY_V42_SCOPE})
 ck('current_application_scope_exact_SHA',sha(W/'v43_method_application_scope.json')==SCOPE==plan['method_application_scope_sha256'])
 ck('per_entry_intent_UTC_explicit',application.get('per_entry_intent_UTC_required') is True)
 ck('current_application_scope_exactgroups_ids',application['fixed_record_ids']==ids and application['groups']==groups and application['status']=='prospectively_frozen_before_V43_external_queries')
 ck('bounded_application_not_source_exhaustion_or_finalfreeze',application.get('source_exhausted') is False and application.get('final_freeze') is False and plan.get('no_analysis_or_final_freeze') is True)
 ck('unchanged_method_id',prereg['method_id']==application['method_id']==plan['method_id']=='uk-geography-canonical-community-reference-pilot-v1')
 ck('V43_reuse_explicit_no_new_amendment',application['rules_unchanged'] is True and application['method_amendment_created'] is False and application['method_reused_from_version']==36 and application['scope_application_extension'] is True and application['no_new_admission_method_exception'] is True and plan['method_amendment_created'] is False and plan['no_new_admission_method_exception'] is True)
 ck('exact_original_sourceclasses',prereg['new_source_classes']==['canonical_Wikipedia_original_community_person_reference_body','canonical_Wikidata_actual_person_and_place_statements'])
 ck('exact_three_original_proofmodes',set(prereg['proof_modes'])==PROOFS)
 ck('fullnative_exactDOB_actualedges_mandatory','exactunchangednativeDOB' in prereg['mandatory_person_binding'] and 'Everyedge mustactuallyappear' in prereg['entity_chain'])
 ck('generic_UK_and_centroid_not_enough','genericukp17alone cannotreplace' in prereg['region_gate'].lower() and 'no point-centroid substitution' in prereg['region_gate'].lower())
 ck('S3_geography_only_no_DOB_BP_upgrade','S3 geographic_support_only' in prereg['source_grade_role'] and 'notupgrading originalDOBorBPgrade' in prereg['source_grade_role'])
 ck('Kiddle_not_retroapproved','do not retroactivelyadmitKiddleorclear anypriorhold' in prereg['prior_holds'])
 bindings=[];extra={}
 if final:
  facts=rd(S/'inputs/accepted_geography.json');holds=rd(S/'audit/followup_holds.json');fb={f['record_id']:f for f in facts};hb={h['record_id']:h for h in holds}
  ck('54_target_ids_equal_actual_pool',set(rd(S/'inputs/geography_target_ids.json'))==pool and len(rd(S/'inputs/geography_target_ids.json'))==54)
  ck('fixed6_followups_reviewed',rd(S/'inputs/reviewed_record_ids.json')==rd(S/'inputs/geography_followup_ids.json') and set(rd(S/'inputs/reviewed_record_ids.json'))==set(ids) and len(rd(S/'inputs/reviewed_record_ids.json'))==6)
  ck('complete_disjoint_accepted_held_partition',len(fb)==len(facts) and len(hb)==len(holds) and not(set(fb)&set(hb)) and set(fb)|set(hb)==set(ids))
  tree=ast.parse((S/'scripts/replay.py').read_text());fields=[ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='GEO_FIELDS' for t in n.targets)]
  ck('runtime_exact_six_GEO_FIELDS',fields==[GEO])
  prior_tree=ast.parse((OLD/'scripts/replay.py').read_text());old_functions={n.name:ast.dump(n,include_attributes=False) for n in prior_tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))};new_functions={n.name:ast.dump(n,include_attributes=False) for n in tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
  ck('runtime_additive_main_v43_and_historical_functions_literal',all(new_functions.get(k)==v for k,v in old_functions.items()) and 'main_v43' in new_functions and 'main' in old_functions and 'main_v42' in old_functions)
  ck('runtime_main_entrypoint_uses_main_v43',any(isinstance(n,ast.If) and any(isinstance(c,ast.Call) and isinstance(c.func,ast.Name) and c.func.id=='main_v43' for c in ast.walk(n)) for n in tree.body))
  for rid,f in fb.items():
   n=by[rid];p=rid+'_';chain=f.get('proof_chain',[]);mode=f.get('proof_mode');src=f.get('source_birthdate');source_name=norm(f.get('observed_source_full_name','')).split()
   ck(p+'native_DOB_authority_exact',f.get('native_dob')==n['dob'] and f.get('authority_name')==n['source_authorised_full_name'])
   ck(p+'primary_not_explicit_rewritten_summary',f.get('tool_header_rewritten_summary') is not True)
   ck(p+'native_key_unique',sum(r['dob']==n['dob'] and r['source_authorised_full_name']==n['source_authorised_full_name'] for r in rows)==1)
   ck(p+'full_native_personal_components_in_observed_name',all(t in source_name for t in nativeparts(n['source_authorised_full_name'])),{'native_components':nativeparts(n['source_authorised_full_name']),'observed':f.get('observed_source_full_name')})
   ck(p+'exact_source_native_DOB',src==n['dob'] and bool(f.get('source_birthdate_as_displayed')) and bool(f.get('source_birthdate_precision')))
   years=re.findall(r'(?<!\d)(?:18|19|20)\d{2}(?!\d)',n['source_authorised_full_name'])
   ck(p+'source_lifespan_compatible_authority_years',len(years)>=2 and all(y in str(f.get('source_lifespan','')) for y in years[:2]))
   ck(p+'exactday_confirmation_not_overstated',f.get('source_exact_native_month_day_confirmed') is True)
   ck(p+'frozen_rawBP_grade',f.get('frozen_raw_birthplace')==n['raw_birthplace'] and f.get('frozen_birthplace_source_grade')==n['birthplace_source_grade'])
   ck(p+'S3_geo_only_NorthSouth',f.get('source_grade')=='S3' and f.get('source_grade_role')=='geographic_support_only' and f.get('reviewed_hemisphere') in {'north','south'})
   ck(p+'DOB_BP_grades_explicitly_unchanged',f.get('native_DOB_source_grade_unchanged') is True and f.get('original_birthplace_fields_and_source_grades_unchanged') is True)
   ck(p+'method_base_current_application_hashes',f.get('method_id')==plan['method_id'] and f.get('method_preregistration_sha256')==BASE and f.get('method_application_scope_sha256')==SCOPE)
   ck(p+'canonical_original_sourcekind',f.get('source_kind') in prereg['new_source_classes'] and re.match(r'https://(?:[a-z-]+\.wikipedia\.org/wiki/|www\.wikidata\.org/)',f.get('source_url','')) is not None)
   ck(p+'identity_career_lifespan_place_roles_documented',all(bool(f.get(k)) for k in ['identity_review','source_lifespan','place_binding_review','source_birthplace_context','geographic_basis','source_locator','source_body_ref','source_grade_basis','source_body_acquisition_role','parent_source_ref']))
   ck(p+'source_quote_count_under25',actual_words(f.get('source_quote'))==f.get('source_quote_word_count') and f.get('source_quote_word_count',26)<=25)
   ck(p+'unknown_raw_metadata_null',all(f.get(k,'missing') is None for k in ['raw_HTTP_status','raw_bytes_sha256','exact_request_utc']))
   ck(p+'no_frozen_country_QID_coords_BP_replacementkeys',not(set(f)&{'country','lat','lon','wikidata_qid','lookup_qid','raw_birthplace','birthplace_source_grade','birthplace_source_url','selected_birthplace_evidence'}))
   ck(p+'no_pending_proposal_fields',not any('proposal' in k or 'pending' in k for k in f))
   ck(p+'proof_mode_allowed_chain_nonempty',mode in PROOFS and isinstance(chain,list) and bool(chain))
   ck(p+'edges_required_semantic_fields_present',all(all(bool(e.get(k)) for k in ['source_url','source_node_label','edge_property','tool_ref','locator','acquisition_role','target_kind','target_label']) and e.get('target_kind') in {'entity','literal'} and (e.get('target_kind')=='entity' and bool(e.get('target_uri')) or e.get('target_kind')=='literal' and e.get('target_uri') is None) for e in chain))
   ck(p+'all_nonterminal_edges_actual_entity_URIs',all(e.get('target_kind')=='entity' and e.get('target_uri') for e in chain[:-1]))
   ck(p+'exact_edge_continuity',all(a.get('target_uri')==b.get('source_url') for a,b in zip(chain,chain[1:])))
   ck(p+'person_start_node_actual_source',bool(chain) and chain[0].get('source_url')==f.get('source_url'))
   source_place=chain[0].get('target_label','') if chain and chain[0].get('target_kind')=='entity' else f.get('source_birthplace_context','')
   ck(p+'frozen_locality_component_in_actual_birth_context',any(norm(v) and norm(v) in norm(source_place) for v in str(n['raw_birthplace']).split(',')),{'frozen_raw_birthplace':n['raw_birthplace'],'source_birthplace_context':source_place})
   ck(p+'whole_region_terminal_supported_by_existing_extent_gate',bool(chain) and extent_supported(f,chain[-1]))
   if mode=='explicit_person_born_place_hyperlink_then_actual_target_place_region':
    ck(p+'linked_birthplace_atleast_two_edges',len(chain)>=2 and chain[0].get('target_kind')=='entity' and bool(chain[0].get('edge_property')))
    ck(p+'worker_actual_follow_ref_or_explicit_acquisition_role',bool(f.get('worker_actual_edge_follow_ref')) or any('click' in str(e.get('acquisition_role','')).lower() or 'follow' in str(e.get('acquisition_role','')).lower() for e in chain))
    ck(p+'target_city_geographic_not_employer',all('geographic' in str(e.get('source_node_type','')).lower() or any(v in str(e.get('source_node_type','')).lower() for v in ['city','settlement','district','administrative','region']) for e in chain[1:]))
   elif mode=='actual_person_P19_entity_then_actual_P131_admin_chain_to_whole_region':
    ck(p+'actual_P19_then_P131_entities',len(chain)>=2 and chain[0].get('edge_property')=='P19' and any(e.get('edge_property')=='P131' for e in chain[1:]) and all(e.get('target_kind')=='entity' for e in chain))
   elif mode=='direct_born_region_in_actual_canonical_person_body':
    ck(p+'direct_region_one_actual_person_birth_association_edge',len(chain)==1 and bool(chain[0].get('edge_property')))
   bindings.append({'record_id':rid,'native_DOB':n['dob'],'native_authority':n['source_authorised_full_name'],'observed_source_full_name':f.get('observed_source_full_name'),'source_birthdate':src,'source_birthdate_as_displayed':f.get('source_birthdate_as_displayed'),'frozen_raw_birthplace':n['raw_birthplace'],'frozen_BP_source_grade':n['birthplace_source_grade'],'source_birthplace_context':f.get('source_birthplace_context'),'new_geographic_grade':f.get('source_grade'),'new_hemisphere':f.get('reviewed_hemisphere'),'proof_mode':mode,'proof_chain':chain,'identity_review':f.get('identity_review'),'source_lifespan':f.get('source_lifespan'),'source_locator':f.get('source_locator'),'source_grade_basis':f.get('source_grade_basis'),'source_body_acquisition_role':f.get('source_body_acquisition_role'),'parent_source_ref':f.get('parent_source_ref'),'worker_source_body_ref':f.get('worker_source_body_ref'),'root_reclicked_edge':f.get('root_reclicked_edge')})
  for rid,h in hb.items():
   n=by[rid];hn=h.get('native',{})
   ck(rid+'_held_nativeDOB_authority_exact',hn.get('native_dob',hn.get('dob'))==n['dob'] and hn.get('authority_name',hn.get('source_authorised_full_name'))==n['source_authorised_full_name'])
   ck(rid+'_held_original_BP_grade_exact',first(hn,['frozen_birthplace_source_grade','birthplace_source_grade','prior_birthplace_source_grade','existing_birthplace_source_grade'])==n['birthplace_source_grade'])
   ck(rid+'_held_unknown_raw_calendar_rank_editorial_metadata_null',all(h.get(k,'missing') is None for k in ['source_calendar_model','source_statement_rank','source_editorial_validation','source_informational_independence','raw_HTTP_status','raw_bytes_sha256','exact_request_utc']))
   place=hn.get('raw_birthplace',hn.get('prior_raw_birthplace',hn.get('existing_raw_birthplace')))
   if place is not None:ck(rid+'_held_frozen_rawBP_exact',place==n['raw_birthplace'])
  inventory_changes={}; inventory_hashes={}; inventory_counts={}
  for name in SIDE+['birthplace_source_conflicts.json','active_source_DOB_conflicts.json']:
   op=OLD/'audit'/name;np=S/'audit'/name;oldobj=rd(op);newobj=rd(np)
   oldlist=inventory_records(oldobj);newlist=inventory_records(newobj)
   exact=np.read_bytes()==op.read_bytes();appended=newlist[len(oldlist):] if isinstance(oldlist,list) and isinstance(newlist,list) else []
   inventory_hashes[name]={'baseline_sha256':sha(op),'current_sha256':sha(np)};inventory_counts[name]={'baseline_records':len(oldlist) if oldlist is not None else None,'current_records':len(newlist) if newlist is not None else None,'inventory_shape':'metadata_without_records' if oldlist is None else 'records'}
   inventory_changes[name]={'byte_identical':exact,'appended_record_ids':[v.get('record_id') for v in appended]}
   ck('inventory_'+name+'_old_objects_preserved',exact if oldlist is None else isinstance(newlist,list) and newlist[:len(oldlist)]==oldlist)
   if exact:ck('inventory_'+name+'_byteexact_default',True)
   else:
    snapshot=S/'audit'/('prior_v42_'+name)
    ck('inventory_'+name+'_qualified_append_only',oldlist is not None and newlist is not None and bool(appended) and all(v.get('record_id') in set(ids) for v in appended) and len(newlist)==len(oldlist)+len(appended) and inventory_metadata(oldobj)==inventory_metadata(newobj))
    ck('inventory_'+name+'_prior_v42_exact_snapshot',snapshot.exists() and snapshot.read_bytes()==op.read_bytes())
    if name in {'active_source_DOB_conflicts.json','birthplace_source_conflicts.json'}:ck('inventory_'+name+'_appended_conflict_only_held',all(v.get('record_id') in hb and v.get('record_id') not in fb for v in appended))
  currentactive=rd(S/'audit/active_source_DOB_conflicts.json')['records']
  ck('all13_prior_activeDOB_objects_prefix_unchanged',len(currentactive)>=13 and currentactive[:13]==active)
  ck('new_activeDOB_cases_not_adopted',not(set(fb)&{v['record_id'] for v in currentactive[13:]}))
  ck('Adam_historical_conflict_still_active_unchanged',currentactive[12]==active[12] and currentactive[12]['record_id']=='RS_PAST_NA4918')
  priorages=rd(OLD/'audit/source_derived_age_inconsistencies.json');ages=rd(S/'audit/source_derived_age_inconsistencies.json')
  ck('all_four_inherited_age_objects_preserved',len(priorages)==4 and ages[:4]==priorages)
  newages=ages[len(priorages):]
  for age in newages:
   arid=age.get('record_id');an=by.get(arid,{})
   ck(str(arid)+'_new_age_quality_native_binding',arid in set(ids) and age.get('observed_source_birthdate')==an.get('dob') and all(v in norm(age.get('observed_source_full_name','')).split() for v in nativeparts(an.get('source_authorised_full_name',''))))
   ck(str(arid)+'_new_age_quality_no_repair_and_root_complete',age.get('no_source_or_native_DOB_repair') is True and age.get('parent_adjudication_required') is False and bool(age.get('parent_source_ref')))
   ck(str(arid)+'_new_age_quality_arithmetic_from_same_source_dates',age_arithmetic_matches(age))

  for name in ['prior_v11_holds.json','prior_v12_holds.json','prior_v29_first_pass_queue_closeout.json','prior_v35_geography_first_pass_queue_closeout.json']:
   ck(name+'_exacthistoricalbytes',(S/'audit'/name).read_bytes()==(OLD/'audit'/name).read_bytes())
  historical_prior_files=[p for p in (OLD/'audit').rglob('*') if p.is_file() and p.relative_to(OLD/'audit').parts[0].startswith('prior_')]
  ck('all_inherited_historical_prior_audit_files_byteexact',all((S/'audit'/p.relative_to(OLD/'audit')).exists() and (S/'audit'/p.relative_to(OLD/'audit')).read_bytes()==p.read_bytes() for p in historical_prior_files),{'historical_prior_files':len(historical_prior_files)})
  previous_current=[p for p in (OLD/'audit').rglob('*') if p.is_file() and not p.relative_to(OLD/'audit').parts[0].startswith('prior_')]
  def retained_previous_path(p):
   rel=p.relative_to(OLD/'audit');first=rel.parts[0]
   return S/'audit'/pathlib.Path('prior_v42_'+('holds.json' if first=='followup_holds.json' else first),*rel.parts[1:])
  ck('all_baseline_V42_current_audits_archived_byteexact',all(retained_previous_path(p).exists() and retained_previous_path(p).read_bytes()==p.read_bytes() for p in previous_current),{'archived_files':len(previous_current),'original_unrecovered_V42_checks_remain_historical_attestations':True})
  ck('historical_V35_queue_pin_no_current_relabel',sha(S/'audit/prior_v35_geography_first_pass_queue_closeout.json')=='56fd3053935afc42fe2f9cf301bb66bc2bc6839fa9483467cd03e602fb61be3b' and not (S/'audit/geography_first_pass_queue_closeout.json').exists())
  ck('historical_V36_class_admission_preserved',(S/'audit/prior_v36_source_class_adjudication.json').read_bytes()==(OLD/'audit/prior_v36_source_class_adjudication.json').read_bytes() and rd(S/'audit/prior_v36_source_class_adjudication.json')['method_amendment_created'] is True)
  ck('historical_base_prereg_bytes_preserved',(S/'audit/method_preregistration.json').read_bytes()==(W/'v36_method_preregistration.json').read_bytes())
  ck('current_application_scope_bytes_exact',(S/'audit/method_application_scope_v43.json').read_bytes()==(W/'v43_method_application_scope.json').read_bytes())
  ck('legacy_V37_runtime_scope_byteexact',(S/'audit/method_application_scope.json').read_bytes()==(OLD/'audit/method_application_scope.json').read_bytes() and sha(S/'audit/method_application_scope.json')==LEGACY_SCOPE)
  ck('legacy_V39_runtime_scope_byteexact',(S/'audit/method_application_scope_v39.json').read_bytes()==(OLD/'audit/method_application_scope_v39.json').read_bytes() and sha(S/'audit/method_application_scope_v39.json')==LEGACY_V39_SCOPE)
  ck('legacy_V38_runtime_scope_byteexact',(S/'audit/method_application_scope_v38.json').read_bytes()==(OLD/'audit/method_application_scope_v38.json').read_bytes() and sha(S/'audit/method_application_scope_v38.json')==LEGACY_V38_SCOPE)
  ck('legacy_V40_runtime_scope_byteexact',(S/'audit/method_application_scope_v40.json').read_bytes()==(OLD/'audit/method_application_scope_v40.json').read_bytes() and sha(S/'audit/method_application_scope_v40.json')==LEGACY_V40_SCOPE)
  ck('legacy_V41_runtime_scope_byteexact',(S/'audit/method_application_scope_v41.json').read_bytes()==(OLD/'audit/method_application_scope_v41.json').read_bytes() and sha(S/'audit/method_application_scope_v41.json')==LEGACY_V41_SCOPE)
  ck('legacy_V42_runtime_scope_byteexact',(S/'audit/method_application_scope_v42.json').read_bytes()==(OLD/'audit/method_application_scope_v42.json').read_bytes() and sha(S/'audit/method_application_scope_v42.json')==LEGACY_V42_SCOPE)
  reports=[rd(S/'audit'/f'sources_{g}.json') for g in 'abc'];ops=[normalized_ops(r) for r in reports]
  for g,r,(q,nav,finds) in zip('abc',reports,ops):
   ck(g+'_report_exact_scratch',(S/'audit'/f'sources_{g}.json').read_bytes()==(W/f'v43_sources_{g}.json').read_bytes())
   ck(g+'_queries_atmost4',len(q)<=4 and all(querytext(v) for v in q))
   ck(g+'_ledger_operation_kinds_consistent',all(opkind(v)=='search' for v in q) and all(opkind(v) in {'open','click'} for v in nav) and all(opkind(v)=='find' for v in finds))
   ck(g+'_source_navigation_atmost10',len(nav)<=10)
   ck(g+'_exact_worker_scope_partition',({c['record_id'] for c in r.get('candidates',[])}|{h['record_id'] for h in r.get('holds',[])})==set(groups[g]))
   ck(g+'_intent_exact_scratch',(S/'audit'/f'{g}_intent.json').read_bytes()==(W/f'v43_{g}_intent.json').read_bytes())
   it=rd(S/'audit'/f'{g}_intent.json');planned=it.get('requests',it.get('entries',[]))
   available_intent_times=[timestamp(v) for v in [it]+planned if timestamp(v) is not None];initial_intent_time=min(available_intent_times) if available_intent_times else None
   ck(g+'_scope_application_predates_worker_initial_intent',initial_intent_time is not None and initial_intent_time>=timestamp(application))
   ck(g+'_worker_report_current_method_scope',r.get('method_id')==plan['method_id'] and r.get('method_preregistration_sha256')==BASE and r.get('method_application_scope_sha256')==SCOPE)
   ck(g+'_nine_prior_inventory_pins_in_durable_intent',inventory_pins_present(it))
   ck(g+'_all_requests_have_exact_durable_intent',one_to_one_intents(q+nav+finds,planned),{'actual_operations':len(q)+len(nav)+len(finds),'intent_entries':len(planned)})
   missing_entry_times=sum(timestamp(e) is None for e in planned)
   ck(g+'_every_intent_entry_has_UTC_after_scope',missing_entry_times==0 and all(timestamp(e)>=timestamp(application) for e in planned if timestamp(e) is not None),{'without_per_entry_timestamp':missing_entry_times,'file_timestamp':it.get('written_utc')})
   if missing_entry_times:warnings.append({'warning':g+'_intent_entry_timing_not_independently_reconstructed','detail':f'{missing_entry_times} exact entries have no per-entry time; file time and separately validated-before-web disclosure are retained. No retrospective timestamps invented.'})
   ck(g+'_durable_intents_separately_validated_beforeweb',r.get('intent_writes_validated_exit0_separately_beforeweb') is True)
   closed_observations=[v for h in r.get('holds',[]) for v in h.get('source_observations',[]) if v.get('source_body_acquired') is False or v.get('body_acquired') is False or v.get('actual_original_body_acquired') is False]
   protocol=r.get('protocol_limits',{})
   reported_stop=(protocol.get('first_failed_or_unusable_work_not_retried') is True and protocol.get('no_rawGET_auth_bypass_or_failedwork_variants') is True) or (bool(closed_observations) and r.get('bounded_pass_complete') is True and all(v.get('stopped_without_retry_variant_or_rawGET') is True for v in closed_observations))
   ck(g+'_first_failure_closes_without_retry_or_variants',reported_stop)
   ck(g+'_reported_counts_equal_actual_ledgers',r.get('retrieval_counts',{}).get('queries')==len(q) and r.get('retrieval_counts',{}).get('navigation_attempts')==len(nav) and r.get('retrieval_counts',{}).get('parsed_finds',r.get('retrieval_counts',{}).get('cached_finds'))==len(finds))
   ck(g+'_no_raw_GET_screenshot_operations',all(r.get('retrieval_counts',{}).get(k,0)==0 for k in ['raw_GETs','screenshots']))
   known_words=r.get('source_quote_words_by_original_work',{})
   has_current_quotes=any(isinstance(v,dict) and bool(v.get('source_quote')) for v in descendants(r))
   ck(g+'_declared_perwork_quote_counts_under25',all(isinstance(v,int) and 0<=v<=25 for v in known_words.values()) and (bool(known_words) or not has_current_quotes))

  parent=rd(S/'audit/parent_adjudication.json');root=rd(S/'audit/root_followups.json');intent=rd(S/'audit/root_intent.json');sc=rd(S/'audit/source_class_adjudication.json')
  ck('parent_same_method_current_scope_hash',parent.get('method_id')==plan['method_id'] and parent.get('method_preregistration_sha256')==BASE and parent.get('method_application_scope_sha256')==SCOPE)
  ck('thisversion_no_new_admission_amendment',parent.get('method_amendment_created') is False and parent.get('no_new_admission_method_exception') is True and sc.get('method_amendment_created') is False and sc.get('no_new_admission_method_exception') is True)
  ck('class_current_method_scope_hash',sc.get('method_id')==plan['method_id'] and sc.get('method_preregistration_sha256')==BASE and sc.get('method_application_scope_sha256')==SCOPE)
  ck('class_adopted_ids_grades_modes_actual',set(sc.get('adopted_record_ids',[]))==set(fb) and sc.get('adopted_geographic_support_grades')==({'S3':len(facts)} if facts else {}) and set(sc.get('actual_qualified_proof_modes',[]))=={f['proof_mode'] for f in facts})
  ck('class_native_BP_fields_unchanged',sc.get('native_and_original_birthplace_fields_unchanged') is True)
  ck('adopted_count_matches_partition',len(facts)+len(holds)==6)
  ck('current_accepted_root_adjudication_completed',all(timestamp(f) is not None or bool(f.get('parent_adjudication_utc')) for f in facts))

  for rid,f in fb.items():
   ck(rid+'_unknown_calendar_rank_editorial_independence_null',all(f.get(k,'missing') is None for k in ['source_calendar_model','source_statement_rank','source_editorial_validation','source_informational_independence']))
   ck(rid+'_root_actual_body_role_separate_worker_role',bool(f.get('parent_source_ref')) and bool(f.get('worker_source_body_ref')) and f.get('root_reclicked_edge') in {True,False})
  ck('root_intents_after_scope_before_adjudication',all(timestamp(e) is not None and timestamp(parent) is not None and timestamp(application)<=timestamp(e)<timestamp(parent) for e in intent.get('entries',[])))
  root_observations=root.get('observations',[])
  ck('root_operations_explicit_and_known',all(opkind(v) in {'search','open','click','find'} for v in root_observations))
  ck('root_nine_inventory_pins_in_durable_preintent',inventory_pins_present(intent))
  ck('root_observed_acquisitions_exact_durable_intents',one_to_one_intents(root_observations,intent.get('entries',[])))
  actual_ledger_entries=[v for o in ops for ledger in o for v in ledger]+root_observations
  actual_refs={ref for d in actual_ledger_entries if not re.search(r'internal error|URL is not accessible|entity.*inaccessible|work.*failed|redlink=1|creation UI',str(d.get('outcome','')),re.I) for ref in [d.get('ref'),d.get('result_ref'),d.get('response_ref'),d.get('tool_ref'),*d.get('result_refs',[])] if isinstance(ref,str) and re.fullmatch(r'turn[0-9]+(?:view|search|find)[0-9]+',ref)}
  ck('new_age_quality_source_refs_observed_and_no_grade_upgrade',all(age.get('parent_source_ref') in actual_refs and age.get('worker_source_ref') in actual_refs and str(age.get('source_grade_role','')).startswith('source_quality_observation_only') and all(age.get(k,'missing') is None for k in ['source_calendar_model','source_statement_rank','source_editorial_validation','source_informational_independence','raw_HTTP_status','raw_bytes_sha256','exact_request_utc']) for age in newages))
  ck('accepted_source_and_edge_refs_actually_in_acquisition_ledgers',all(f.get('parent_source_ref') in actual_refs and f.get('worker_source_body_ref') in actual_refs and all(e.get('tool_ref') in actual_refs for e in f.get('proof_chain',[])) for f in facts))
  rc_from_ledger={'source_open_operations':sum(opkind(v)=='open' for v in root_observations),'click_operations':sum(opkind(v)=='click' for v in root_observations),'parsed_finds':sum(opkind(v)=='find' for v in root_observations),'discovery_queries':sum(opkind(v)=='search' for v in root_observations)}
  ck('root_counts_from_actual_operation_kinds',all(root.get('counts',{}).get(k,0)==v for k,v in rc_from_ledger.items()))
  ck('root_atmost18opens1query',rc_from_ledger['source_open_operations']+rc_from_ledger['click_operations']<=18 and rc_from_ledger['discovery_queries']<=1)
  ck('root_no_raw_GET_screenshot_operations',all(root.get('counts',{}).get(k,0)==0 for k in ['raw_GETs','screenshots']))
  wq=sum(len(o[0]) for o in ops);wn=sum(len(o[1]) for o in ops);wf=sum(len(o[2]) for o in ops)
  counts=parent.get('source_counts',{});rc=root.get('counts',{})
  ck('parent_worker_counts_exact_ledgers',counts.get('worker_queries')==wq and counts.get('worker_navigation_attempts')==wn and counts.get('worker_parsed_finds')==wf)
  wo=sum(sum(opkind(v)=='open' for v in o[1]) for o in ops);wc=sum(sum(opkind(v)=='click' for v in o[1]) for o in ops)
  ck('parent_open_click_counts_from_actual_ledgers',counts.get('worker_source_open_operations')==wo and counts.get('worker_click_operations')==wc and counts.get('total_source_open_operations')==wo+rc.get('source_open_operations',0) and counts.get('total_click_operations')==wc+rc.get('click_operations',0))
  ck('parent_age_counts_from_actual_inventory',parent['decisions'].get('new_source_derived_age_inconsistencies')==len(newages) and parent['decisions'].get('total_source_derived_age_inconsistencies')==len(ages))
  ck('root_counts_match_intent_entries',rc.get('source_open_operations',0)+rc.get('click_operations',0)+rc.get('parsed_finds',0)+rc.get('discovery_queries',0)==len(intent.get('entries',[])))
  ck('parent_totals_match_worker_plus_root',counts.get('total_queries')==wq+rc.get('discovery_queries',0) and counts.get('total_navigation_attempts')==wn+rc.get('source_open_operations',0)+rc.get('click_operations',0) and counts.get('total_parsed_finds')==wf+rc.get('parsed_finds',0))
  ck('all_root_quoteworkcounts_atmost25',all(isinstance(v,int) and 0<=v<=25 for v in root.get('quote_words_by_original_work',{}).values()))
  semantic_path=W/'v43_source_documentary_case_review.json';semantic=rd(semantic_path)
  semantic_cases=semantic.get('case_reviews',[]);semby={v.get('record_id'):v for v in semantic_cases}
  ck('independent_manual_semantic_review_covers_exact_six',len(semby)==len(semantic_cases)==6 and set(semby)==set(ids) and semantic.get('documentary_review_complete') is True)
  semantic_binding={'facts':sha(S/'inputs/accepted_geography.json'),'holds':sha(S/'audit/followup_holds.json'),'parent':sha(S/'audit/parent_adjudication.json'),'root':sha(S/'audit/root_followups.json'),'root_intent':sha(S/'audit/root_intent.json'),**{f'worker_{g}':sha(S/'audit'/f'sources_{g}.json') for g in 'abc'},**{f'worker_intent_{g}':sha(S/'audit'/f'{g}_intent.json') for g in 'abc'}}
  ck('independent_semantic_review_binds_actual_current_artifacts',semantic.get('artifact_sha256')==semantic_binding)
  ck('accepted_actual_person_birth_relation_and_path_semantically_reviewed',all(semby.get(rid,{}).get('decision')=='accepted_S3_geography_only' and all(semby[rid].get(k) is True for k in ['native_name_components_observed','exact_displayed_native_DOB_observed','distinctive_career_observed','compatible_acquired_lifespan','frozen_place_relation_observed','primary_canonical_body_not_rewritten_mirror','actual_birth_relation_reviewed','whole_region_extent_reviewed','worker_follow_or_direct_P19_path_reviewed','maintenance_and_representation_caveats_preserved']) for rid in fb))
  ck('held_cases_semantically_reviewed_without_absence_overclaim',all(semby.get(rid,{}).get('decision')=='held' and semby[rid].get('reason_reviewed') is True and semby[rid].get('missing_proof_not_universal_absence') is True for rid in hb))
  ck('perwork_cumulative_historical_and_current_quotes_semantically_reviewed',semantic.get('cumulative_per_original_work_quote_accounting_reviewed') is True and semantic.get('all_original_works_atmost25_distinct_English_quoted_words') is True)
  quote_path=W/semantic['quote_prefinal_report_path'];quote_review=rd(quote_path)
  operation_path=W/semantic['worker_operation_prefinal_report_path'];operation_review=rd(operation_path)
  ck('quote_review_actual_pin_pass_and_bound_inputs',sha(quote_path)==semantic['quote_prefinal_report_sha256'] and quote_review['passed'] is True and not quote_review['unattributed_quotations'] and all(v<=25 for v in quote_review['original_work_distinct_whitespace_quoted_word_counts'].values()) and all(sha(W/p)==h for p,h in quote_review['artifact_sha256'].items()))
  ck('operation_prefinal_actual_pin_all_pass',sha(operation_path)==semantic['worker_operation_prefinal_report_sha256'] and operation_review['passed'] is True and not operation_review['blocking_issues'] and all(v['passed'] is True for v in operation_review['checks']))
  ck('durable_preintent_first_failure_stops_semantically_reviewed',semantic.get('exact_durable_preintent_protocol_reviewed') is True and semantic.get('first_failed_work_closures_reviewed') is True)
  warnings.extend(semantic.get('retained_warnings',[]))
  ck('held_no_current_geography',all(h.get('no_new_geographic_assignment') is True and h.get('reviewed_hemisphere','unknown')=='unknown' and h.get('source_grade_adopted') is None and not h.get('proof_chain') for h in holds))
  ck('parent_decision_counts_match_actual_facts_holds',parent.get('decisions',{}).get('geography_only_resolutions')==len(facts) and parent['decisions'].get('held')==len(holds) and parent['decisions'].get('newNorth')==sum(f['reviewed_hemisphere']=='north' for f in facts) and parent['decisions'].get('newSouth')==sum(f['reviewed_hemisphere']=='south' for f in facts))
  ck('zero_firstbirthplaces_DOB_inventory_count_no_place_or_other_exceptions',parent['decisions'].get('new_birthplaces')==0 and parent['decisions'].get('new_original_DOB_conflicts')==len(currentactive)-13 and parent['decisions'].get('total_active_DOB_conflicts')==len(currentactive) and parent['decisions'].get('new_place_conflicts')==inventory_counts['birthplace_source_conflicts.json']['current_records']-2 and parent['decisions'].get('partial_birthplace_inventory_records')==inventory_counts['birthplace_source_conflicts.json']['current_records'] and parent['decisions'].get('new_middle_or_endpoint_exceptions')==0)
  schema_text=(S/'METHOD_SCHEMA.md').read_text();old_schema=(OLD/'METHOD_SCHEMA.md').read_text()
  ck('schema_prior_source_method_requirements_preserved',old_schema.split('\n',1)[1].strip() in schema_text)
  ck('schema_current_scope_path_and_frozen_hash_documented','audit/method_application_scope_v43.json' in schema_text and SCOPE in schema_text)
  ck('schema_current_application_scope_documented',('method_application_scope_sha256' in (S/'METHOD_SCHEMA.md').read_text() or ('Every current fact must carry the exact base method SHA256 and the current scope SHA256' in (S/'METHOD_SCHEMA.md').read_text() and 'runtime checks both files against their frozen hashes' in (S/'METHOD_SCHEMA.md').read_text())))
  ck('no_source_caches_or_images',not any(p.is_file() and p.suffix.lower() in {'.pdf','.html','.png','.jpg','.jpeg','.gif','.webp'} for p in S.rglob('*')))
  extra={'documentary_semantic_case_review_sha256_at_review':sha(semantic_path),'documentary_semantic_case_reviews':semantic_cases,'documentary_protocol_review':{k:v for k,v in semantic.items() if k not in {'artifact_sha256','case_reviews'}},'accepted_fact_path':'inputs/accepted_geography.json','followup_holds_sha256_at_review':sha(S/'audit/followup_holds.json'),'parent_adjudication_sha256_at_review':sha(S/'audit/parent_adjudication.json'),'root_followups_sha256_at_review':sha(S/'audit/root_followups.json'),'root_intent_sha256_at_review':sha(S/'audit/root_intent.json'),'worker_source_report_sha256_at_review':{g:sha(S/'audit'/f'sources_{g}.json') for g in 'abc'},'worker_intent_sha256_at_review':{g:sha(S/'audit'/f'{g}_intent.json') for g in 'abc'},'accepted_fact_sha256_at_review':sha(S/'inputs/accepted_geography.json'),'accepted_geography_sha256_at_review':sha(S/'inputs/accepted_geography.json'),'active_DOB_conflicts_sha256_at_review':sha(S/'audit/active_source_DOB_conflicts.json'),'source_derived_age_inconsistencies_sha256_at_review':sha(S/'audit/source_derived_age_inconsistencies.json'),'prior_v42_source_derived_age_inconsistencies_sha256_at_review':sha(OLD/'audit/source_derived_age_inconsistencies.json'),'birthplace_source_conflicts_sha256_at_review':sha(S/'audit/birthplace_source_conflicts.json'),'source_class_adjudication_sha256_at_review':sha(S/'audit/source_class_adjudication.json'),'historical_v35_geography_first_pass_queue_closeout_sha256_at_review':sha(S/'audit/prior_v35_geography_first_pass_queue_closeout.json'),'historical_v29_first_pass_queue_closeout_sha256_at_review':sha(S/'audit/prior_v29_first_pass_queue_closeout.json'),'method_preregistration_sha256_at_review':sha(S/'audit/method_preregistration.json'),'method_application_scope_sha256_at_review':sha(S/'audit/method_application_scope_v43.json'),'method_application_scope_path':'audit/method_application_scope_v43.json','legacy_V37_method_application_scope_sha256_at_review':sha(S/'audit/method_application_scope.json'),'legacy_V38_method_application_scope_sha256_at_review':sha(S/'audit/method_application_scope_v38.json'),'legacy_V39_method_application_scope_sha256_at_review':sha(S/'audit/method_application_scope_v39.json'),'legacy_V40_method_application_scope_sha256_at_review':sha(S/'audit/method_application_scope_v40.json'),'legacy_V41_method_application_scope_sha256_at_review':sha(S/'audit/method_application_scope_v41.json'),'legacy_V42_method_application_scope_sha256_at_review':sha(S/'audit/method_application_scope_v42.json'),'method_schema_sha256_at_review':sha(S/'METHOD_SCHEMA.md'),'accepted_geographic_bindings':bindings,'new_source_quality_observations':newages,'nine_issue_inventory_sha256_at_review':inventory_hashes,'nine_issue_inventory_counts_at_review':inventory_counts,'nine_issue_inventory_changes':inventory_changes,'inherited_issue_sidecars_byte_identical':[k for k,v in inventory_changes.items() if v['byte_identical']],'all_four_inherited_age_records_unchanged':ages[:4]==priorages,'worker_counts_from_actual_ledgers':{g:{'queries':len(o[0]),'navigation_operations':len(o[1]),'parsed_finds':len(o[2])} for g,o in zip('abc',ops)}}

 failures=[c for c in checks if not c['passed']]
 report={'schema':'UK_v43_independent_geography_source_documentary_QA_v1','reviewer':'/root/v43_source_qa','written_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'phase':'final' if final else 'preflight','passed':not failures,'checks_passed':len(checks)-len(failures),'checks':checks,'blocking_issues':failures,'warnings':warnings,'declared_six_GEO_FIELDS':sorted(GEO),'no_new_admission_method_exception':True,'explicit_prospective_admission_method_amendment':False,'historical_V36_method_amendment_preserved':True,'scope_application_extension':True,'review_scope':'Documentary source/native binding/scope/protocol review only. Workers and root acquired source observations. Reviewer did not fetch network originals, inspect raw bytes/pixels or execute production. Final QA independently checks full-object rollback and deterministic output replays.','no_network_source_code_mainoutputs_audits_or_Git_mutation_by_reviewer':True,**extra}
 out=W/('v43_source_qa_report.json' if final else 'v43_source_qa_preflight.json')
 if final and failures:
  failed=W/'v43_source_qa_initial_final_failed_report.json'
  if not failed.exists():failed.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({'report':str(out),'passed':report['passed'],'checks_passed':report['checks_passed'],'blocking_issues':failures},ensure_ascii=False))
 return 0 if not failures else 1
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--final',action='store_true');o=a.parse_args();raise SystemExit(main(o.final))
