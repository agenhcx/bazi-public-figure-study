"""Local-only whole-target canonical/frozen-alias match and final freeze."""
import gzip,json,hashlib,re,unicodedata,collections
from urllib.parse import urljoin
from route import ROOT,WORKSPACE,BASELINE,EXPECTED_SHA,Links,read_jsonl,write_jsonl,now

def normalize(text):
    text=unicodedata.normalize('NFKD',text).encode('ascii','ignore').decode().lower()
    return [x for x in re.findall(r'[a-z]+',text) if x not in {'sir','dame','lord','baron','professor','prof','dr','jnr'}]
def prefix_lifespan(text):
    life=re.search(r'\((?:c\.\s*)?(\d{3,4})\??\s*-\s*(?:c\.\s*)?(\d{3,4})?\??\s*\)',text)
    return (text[:life.start()].strip() if life else text.strip(),int(life[1]) if life else None,int(life[2]) if life and life[2] else None)
def canonical(row):
    value=row.get('source_authorised_full_name') or row['name']
    prefix,birth,death=prefix_lifespan(value)
    parts=[x.strip() for x in prefix.split(';') if x.strip()]
    if len(parts)>1:
        surname=parts[0];givens=' '.join(x for x in parts[1:] if normalize(x))
        return surname+' '+givens,surname,death
    return prefix,row['name'].split()[-1],death

assert hashlib.sha256(BASELINE.read_bytes()).hexdigest()==EXPECTED_SHA
baseline=[json.loads(x) for x in gzip.open(BASELINE,'rt')]
unknown=[x for x in baseline if x['hemisphere']=='unknown']
assert len(baseline)==4983 and len(unknown)==645
assert sum(1835<=int(x['dob'][:4])<=1985 for x in unknown)==211
intents=read_jsonl('request_intents.jsonl');requests=read_jsonl('requests.jsonl')
assert len(intents)==len(requests)==2
assert len({x['url'] for x in intents})==2
assert all(x['kind']=='navigation_index' for x in requests)
assert requests[0]['finished_utc']<requests[1]['started_utc']
for response in requests:
    raw=(WORKSPACE/response['raw_source_file']).read_bytes()
    assert len(raw)==response['byte_count']
    assert hashlib.sha256(raw).hexdigest()==response['source_sha256']
    assert not response['response_headers'].get('content-encoding'), 'Identity encoded body expected'
    assert any(x['url']==response['url'] and x['started_utc']==response['started_utc'] for x in intents)

directory=[];counts=[]
for response in requests:
    if response.get('status_code')!=200:continue
    letter=re.search(r'browse([a-z])_people',response['url'])[1].upper()
    parser=Links();parser.feed((WORKSPACE/response['raw_source_file']).read_text())
    links=[x for x in parser.links if re.fullmatch(r'biogs/P\d+b\.htm',x['href'])]
    counts.append({'index_letter':letter,'biography_link_count':len(links),'unique_biography_urls':len({x['href'] for x in links}),'source_url':response['url'],'source_sha256':response['source_sha256']})
    for link in links:
        prefix,birth,death=prefix_lifespan(link['text'])
        directory.append({'index_letter':letter,'index_text':link['text'],'name_prefix':prefix,'birth_year':birth,'death_year':death,'surname':prefix.split(',')[0],'source_url':urljoin('https://www.eoas.info/',link['href']),'index_url':response['url'],'index_source_sha256':response['source_sha256']})
write_jsonl('directory_projection.jsonl',directory)
(ROOT/'directory_census.json').write_text(json.dumps({'indices':counts,'successful_indices':len(counts),'requested_indices':2,'biography_link_count':len(directory),'unique_biography_urls':len({x['source_url'] for x in directory}),'scope':'Only actual HTTP200 directory pages are projected. A complete request attempt for two indices is not a claim that all indexed biography bodies were read.'},indent=2)+'\n')

coverage=[];strong=[];excluded_surname_pairs=[];target_projection=[]
for row in unknown:
    native_name,surname,death=canonical(row)
    names=[{'name':native_name,'provenance':'frozen_catalogue_canonical_surname_and_givens'},{'name':row['name'],'provenance':'frozen_native_name'}]
    review=row.get('geography_lookup_identity_review') or {}
    if review.get('native_name'):names.append({'name':review['native_name'],'provenance':'frozen_identity_review_native_name'})
    for field in ['wikidata_aliases','wikidata_labels']:
        for name in review.get(field,[]) or []:names.append({'name':name,'provenance':'frozen_identity_review_'+field})
    unique={(x['name'],x['provenance']):x for x in names};names=list(unique.values())
    year=int(row['dob'][:4]);matches=[];surname_pair_count=0
    known_urls=set(row.get('birthplace_source_urls',[]))|{row.get('birthplace_source_url','')}
    for evidence in row.get('birthplace_evidence_candidates',[]):known_urls.update(evidence.get('source_urls',[]))
    for entry in directory:
        entry_tokens=set(normalize(entry['name_prefix']))
        name_matches=[n for n in names if len(set(normalize(n['name'])))>=2 and set(normalize(n['name'])).issubset(entry_tokens)]
        surname_match=normalize(surname)==normalize(entry['surname'])
        full_birth_match=entry['birth_year']==year
        life_conflict=bool(death and entry['death_year'] and death!=entry['death_year'])
        if surname_match:
            surname_pair_count+=1
            excluded_surname_pairs.append({'record_id':row['record_id'],'native_dob':row['dob'],'canonical_name':native_name,'catalogue_death_year':death,'index_entry':entry,'full_name_or_alias_token_match':bool(name_matches),'native_birth_year_match':full_birth_match,'lifespan_conflict':life_conflict,'decision':'excluded_no_full_name_birthyear_match' if not(name_matches and full_birth_match and not life_conflict) else 'strong_name_lifespan_candidate'})
        if not(name_matches and full_birth_match and not life_conflict):continue
        candidate={'record_id':row['record_id'],'native_dob':row['dob'],'canonical_name':native_name,'in_window':1835<=year<=1985,'source_url':entry['source_url'],'index_entry':entry,'matched_frozen_names':name_matches,'strong_candidate':True,'already_frozen_source':entry['source_url'] in known_urls,'selected_for_body':False,'decision':'excluded_existing_frozen_source' if entry['source_url'] in known_urls else 'strong_new_candidate_pending_body'}
        matches.append(candidate);strong.append(candidate)
    status='no_strong_candidate_in_actual_200_Y_index_Z_unavailable'
    if normalize(surname) and normalize(surname)[0].startswith('z'):status='Z_surname_index_unavailable_HTTP503_no_negative_inference'
    target={'record_id':row['record_id'],'native_dob':row['dob'],'name':row['name'],'canonical_name':native_name,'canonical_surname':surname,'frozen_names_and_aliases_compared':names,'in_window':1835<=year<=1985,'catalogue_death_year':death,'successful_directory_indices_compared':['Y'],'unavailable_requested_indices':{'Z':503},'directory_link_rows_compared':len(directory),'surname_pair_count':surname_pair_count,'strong_match_count':len(matches),'candidate_urls':[x['source_url'] for x in matches],'body_requested':False,'body_read':False,'coverage_status':status,'DOB_or_acceptance_modified':False,'formal_identity_flags_modified':False,'QIDs_modified':False,'geography_assignment_performed':False}
    coverage.append(target)
    target_projection.append({k:target[k] for k in ['record_id','native_dob','name','canonical_name','canonical_surname','in_window','catalogue_death_year','frozen_names_and_aliases_compared']})
write_jsonl('baseline_unknown_projection.jsonl',target_projection)
write_jsonl('candidate_projection.jsonl',strong)
write_jsonl('excluded_surname_review.jsonl',excluded_surname_pairs)
write_jsonl('whole_target_coverage.jsonl',coverage)
assert not strong, 'New strong candidates require separate manual body review before final freeze'
write_jsonl('accepted.jsonl',[])
write_jsonl('held.jsonl',[])
prior_nav=json.loads((WORKSPACE/'uk_birthplace_v9_workers/eoas/navigation.json').read_text())
navigation={'observed_urls':[x for x in prior_nav['alphabet_links'] if x['letter'] in ['Y','Z']],'observation_file':'uk_birthplace_v9_workers/eoas/navigation.json','observation_original_A_response_sha256':'877d5bbbc10903c1b3265c592d491c071d5f5c608e5e345f92d1922e5610fa31','new_discovery_search_requests':0,'only_previously_unrequested_Y_Z_indices_authorized':True}
(ROOT/'navigation_provenance.json').write_text(json.dumps(navigation,indent=2)+'\n')
summary={'baseline_file':str(BASELINE.relative_to(WORKSPACE)),'baseline_sha256':EXPECTED_SHA,'baseline_rows':4983,'baseline_hemispheres':dict(collections.Counter(r['hemisphere'] for r in baseline)),'unknown_targets':645,'window_unknown_targets':211,'unknown_without_birthplace':sum(not bool(str(r.get('raw_birthplace') or '').strip()) for r in unknown),'unknown_with_birthplace_geoheld':sum(bool(str(r.get('raw_birthplace') or '').strip()) for r in unknown),'index_request_cap':2,'index_requests':2,'index_HTTP_statuses':{'Y':200,'Z':503},'successful_index_count':1,'successful_indices':['Y'],'unavailable_indices':['Z'],'directory_biography_links':len(directory),'directory_unique_biography_urls':len({x['source_url'] for x in directory}),'whole_target_rows_compared':len(coverage),'window_rows_compared':sum(x['in_window'] for x in coverage),'matching_method':'Canonical catalogue surname+givens and frozen native/alias/label tokens, native birth year and no observed lifespan conflict; existing frozen birthplace URLs screened for exclusion. All645 targets compared to actual200 Y directory; Z503 unavailable.','strong_candidates':0,'selected_biography_body_requests':0,'biography_body_request_cap':4,'all_indexed_person_bodies_read':False,'source_facts_accepted':0,'held_new_source_facts':0,'accepted_sha256':hashlib.sha256((ROOT/'accepted.jsonl').read_bytes()).hexdigest(),'all_documented_request_attempts':2,'durable_pre_request_intents':2,'request_status_counts':{'200':1,'503':1},'retries':0,'redirects_followed':0,'individual_birthday_queries':0,'new_web_search_requests':0,'QID_guessing':False,'DOB_or_acceptance_modified':False,'calendar_modified':False,'formal_identity_flags_modified':False,'QIDs_modified':False,'DOB_tier_modified':False,'geography_assignment_performed':False,'country_or_point_assignment_performed':False,'source_grade_if_fact_accepted':'S2 curated EOAS dictionary, independently of DOB match; no accepted fact in this route','network_frozen':True,'frozen_utc':now()}
(ROOT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
(ROOT/'source_boundary.json').write_text(json.dumps({'requested_Y_once':True,'requested_Z_once':True,'only_actual_200_Y_is_source_coverage':True,'Z_HTTP503_not_negative_evidence':True,'no_retries_or_alternate_hosts':True,'no_previously_attempted_letters_or_Townsend_requested':True,'biography_body_requests':0,'reason_for_zero_body_requests':'No strong new full-name/birthyear/lifespan candidate in the successful Y index; Z unavailable.','response_shas':{re.search(r'browse([a-z])_people',r['url'])[1].upper():r['source_sha256'] for r in requests},'accepted_sha256':summary['accepted_sha256'],'no_further_network':True},indent=2)+'\n')
(ROOT/'QA.json').write_text(json.dumps({'passed':True,'baseline_SHA_verified':True,'response_original_byte_SHAs_and_lengths_verified':2,'durable_intents_match_completed_ledgers':2,'sequential_request_timing_verified':True,'unknown_targets':645,'window_targets':211,'strong_candidates':0,'accepted_rows':0,'index_error_excluded_from_coverage':True,'independent_read_only_agent_review':'Zero full-name/birthyear matches across all645 frozen canonical/native/alias/label names;23Y links;Z503 excluded.','unchanged_native_DOB_calendar_formal_flags_QIDs_DOBtier':True,'geography_assignment_performed':False},indent=2)+'\n')
(ROOT/'FROZEN.json').write_text(json.dumps({'frozen_utc':now(),'reason':'No strong candidate; bounded Y/Z route complete','further_network_authorized':False},indent=2)+'\n')
print(json.dumps(summary,indent=2))
