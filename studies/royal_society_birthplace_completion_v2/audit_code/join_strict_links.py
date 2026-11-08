#!/usr/bin/env python3
"""Offline-only strict name+DOB+Royal Society membership lookup seeds.

This does not assert accepted identity, change source DOB, or assign eligibility.
Rerun as official progress advances; it never makes network requests.
"""
import argparse,collections,csv,datetime,gzip,hashlib,json,pathlib,re,unicodedata
from p569_inventory import load_inventory,gate as inventory_gate
ROOT=pathlib.Path(__file__).resolve().parent
BASE=ROOT.parent.parent/'uk_birthplace_checkout/studies/academy_birthplace_screen_v1'
OFFICIAL=ROOT.parent/'official/official_birthplace_progress.jsonl'
DEPRECATED='http://wikiba.se/ontology#DeprecatedRank'
GREGORIAN='http://www.wikidata.org/entity/Q1985727'
TITLES={'sir','dame','dr','dr.','prof','prof.','professor'}
LIFESPAN=re.compile(r'^\s*(?:[?cCfFlL .]*\d{3,4}(?:[?/]|\s)*(?:\d{1,4})?\s*)?[-–—]\s*(?:[?cC .]*\d{3,4}\s*)?\??\s*$')

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def plain(s): return unicodedata.normalize('NFKC',s or '').strip()
def norm(s):
    s=plain(s).casefold().translate(str.maketrans({'’':"'",'‘':"'",'ʼ':"'",'‐':'-','‑':'-','–':'-','—':'-'}))
    # Punctuation normalization only; preserve apostrophes and hyphens as letters' separators.
    s=s.replace('.','')
    s=re.sub(r'\s+',' ',s).strip()
    words=s.split()
    while words and words[0] in TITLES: words.pop(0)
    return ' '.join(words)

def fullname(raw):
    parts=[plain(x) for x in plain(raw).split(';')]
    if len(parts)<2 or not parts[0] or any(x in parts[0] for x in '()[]/0123456789'):
        return '', 'no_unambiguous_surname_field'
    surname=parts[0]
    i=1
    while i<len(parts) and parts[i].casefold() in TITLES: i+=1
    if i>=len(parts): return '', 'no_given_name_field'
    given=parts[i]
    if '(' in given or ')' in given:
        match=re.fullmatch(r'(.*?)\s*\(([^()]*)\)\s*',given)
        if not match or not LIFESPAN.fullmatch(match[2]):return '', 'non_lifespan_parenthetical_given_name_ambiguity'
        given=match[1].strip()
    if not given or any(x in given for x in '[]/=0123456789') or len(given.split())>10:
        return '', 'ambiguous_given_name_field'
    return given+' '+surname, 'official_authorised_surname_semicolon_given'

def read_jsonl(p):
    op=gzip.open if p.suffix=='.gz' else open
    with op(p,'rt',encoding='utf-8-sig') as f:
        for line in f:
            if line.strip():
                try: yield json.loads(line)
                except json.JSONDecodeError: pass # Concurrent writer's final partial line.

def dump_jsonl(path,rows):
    with path.open('w') as f:
        for r in rows: f.write(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n')

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--official-progress',type=pathlib.Path,default=OFFICIAL,help='Exact official JSONL source, including the completed official_birthplace_rows.jsonl when available.')
    args=parser.parse_args()
    rawpath=ROOT/'member_set_raw.json'
    raw=json.loads(rawpath.read_bytes())
    entities=collections.defaultdict(lambda:collections.defaultdict(list))
    for binding in raw['results']['bindings']:
        qid=binding['person']['value'].rsplit('/',1)[-1]
        if 'kind' in binding:
            row={k:v['value'] for k,v in binding.items() if k not in ('person','kind')}
            if row not in entities[qid][binding['kind']['value']]: entities[qid][binding['kind']['value']].append(row)
        else:
            specifications={
                'membership':{'statement':'memberStatement','property':'memberProperty','value':'memberValue','rank':'memberRank'},
                'label':{'value':'label'},'alias':{'value':'alias'},
                'dob':{'statement':'dobStatement','value':'dob','rank':'dobRank','precision':'precision','calendar':'calendar'},
                'birthplace':{'statement':'birthplaceStatement','value':'birthplace','rank':'birthplaceRank'},
                'past_id':{'statement':'pastIdStatement','value':'pastId','rank':'pastIdRank'},
            }
            for kind,mapping in specifications.items():
                row={dest:binding[source]['value'] for dest,source in mapping.items() if source in binding}
                if 'value' in row and row not in entities[qid][kind]: entities[qid][kind].append(row)
    member_index=collections.defaultdict(set)
    all_raw_name_day_index=collections.defaultdict(set)
    qualified={}
    wd_holds=collections.Counter()
    wd_hold_reasons={}
    for qid,e in entities.items():
        if not any(x.get('rank')!=DEPRECATED for x in e['membership']):continue
        for d in e['dob']:
            match=re.match(r'\+?(\d{4}-\d{2}-\d{2})T',d['value'])
            if not match:continue
            for n in e['label']+e['alias']:
                name=norm(n['value'])
                if len(name.split())>=2:all_raw_name_day_index[(name,match[1])].add(qid)
    def wd_hold(qid,reason):
        wd_holds[reason]+=1
        wd_hold_reasons[qid]=reason
    for qid,e in entities.items():
        memberships=[x for x in e['membership'] if x.get('rank')!=DEPRECATED]
        dobs=[x for x in e['dob'] if x.get('rank')!=DEPRECATED]
        # Conservatively hold even deprecated alternatives: never select among DOB values.
        values={(x['value'],x.get('precision'),x.get('calendar')) for x in e['dob']}
        if not memberships: wd_hold(qid,'no_active_membership');continue
        if not dobs: wd_hold(qid,'no_non_deprecated_DOB_statement');continue
        if len(values)!=1: wd_hold(qid,'multiple_or_no_DOB_values_including_deprecated');continue
        dob,precision,calendar=next(iter(values))
        if precision!='11' or calendar!=GREGORIAN:
            wd_hold(qid,'not_unique_day_precision_Gregorian_DOB');continue
        match=re.fullmatch(r'\+?(\d{4}-\d{2}-\d{2})T00:00:00Z',dob)
        if not match: wd_hold(qid,'non_standard_DOB_lexical_form');continue
        day=match[1]
        try: datetime.date.fromisoformat(day)
        except ValueError: wd_hold(qid,'invalid_DOB');continue
        qualified[qid]={'dob':day,'dob_claims':e['dob'],'membership_claims':memberships,'all_membership_claims':e['membership'],'past_id_claims':e['past_id'],'birthplace_claims':e['birthplace'],'names':[dict(x,kind='English_label') for x in e['label']]+[dict(x,kind='English_alias') for x in e['alias']]}
        for x in qualified[qid]['names']:
            name=norm(x['value'])
            if len(name.split())>=2: member_index[(name,day)].add(qid)

    response_sha256=sha(rawpath)
    query_sha256=sha(ROOT/'member_set.sparql')
    baseline={x['record_id']:x for x in read_jsonl(BASE/'outputs/birthplace_rows.jsonl.gz') if x['cohort']=='UK_Royal_Society'}
    occupied=collections.defaultdict(set)
    for rid,x in baseline.items():
        if x.get('lookup_qid'): occupied[x['lookup_qid']].add(rid)
    # Snapshot the growing progress once; the summary hash must identify exactly the rows joined.
    official_bytes=args.official_progress.read_bytes()
    if official_bytes and not official_bytes.endswith(b'\n'):
        official_bytes=official_bytes.rsplit(b'\n',1)[0]+b'\n' if b'\n' in official_bytes else b''
    official_snapshot=ROOT/'official_name_join_snapshot.jsonl'
    official_snapshot.write_bytes(official_bytes)
    official={x['record_id']:x for x in (json.loads(line) for line in official_bytes.decode('utf-8-sig').splitlines() if line.strip())}
    raw_qid_to_records=collections.defaultdict(set)
    for rid,o in official.items():
        b=baseline.get(rid)
        if not b or not rid.startswith('RS_PAST_'):continue
        full,_=fullname(o.get('authorised_form_of_name',''))
        if not full:continue
        for qid in all_raw_name_day_index.get((norm(full),b['dob']),set()):raw_qid_to_records[qid].add(rid)
    candidates=[];holds=[];counts=collections.Counter()
    for rid,b in sorted(baseline.items()):
        if not rid.startswith('RS_PAST_'):continue
        if b.get('lookup_qid'):counts['v1_existing_lookup_retained']+=1;continue
        o=official.get(rid)
        if not o:counts['awaiting_official_authorised_name']+=1;continue
        full,status=fullname(o.get('authorised_form_of_name',''))
        if not full: holds.append({'record_id':rid,'reason':status,'authorised_form_of_name':o.get('authorised_form_of_name','')});continue
        assert o.get('existing_dob')==b['dob'],(rid,'native_DOB_changed')
        key=(norm(full),b['dob'])
        matched=sorted(member_index.get(key,set()))
        all_raw_matched=sorted(all_raw_name_day_index.get(key,set()))
        counts['unlinked_with_official_parseable_fullname']+=1
        if not matched:
            if all_raw_matched:
                holds.append({'record_id':rid,'reason':'exact_name_and_raw_day_candidates_fail_DOB_gate','authorised_form_of_name':o['authorised_form_of_name'],'full_name':full,'DOB':b['dob'],'QIDs':all_raw_matched,'candidate_reasons':{q:wd_hold_reasons.get(q,'qualified_but_unknown_gate') for q in all_raw_matched},'candidate_DOB_claims':{q:entities[q]['dob'] for q in all_raw_matched}})
            else:counts['no_exact_fullname_plus_DOB_plus_membership_match']+=1
            continue
        if len(all_raw_matched)>1:
            holds.append({'record_id':rid,'reason':'multiple_member_QIDs_have_exact_name_and_any_raw_DOB_day','authorised_form_of_name':o['authorised_form_of_name'],'full_name':full,'DOB':b['dob'],'QIDs':all_raw_matched});continue
        if len(matched)!=1:
            holds.append({'record_id':rid,'reason':'one_official_record_multiple_exact_QID_candidates','authorised_form_of_name':o['authorised_form_of_name'],'full_name':full,'DOB':b['dob'],'QIDs':matched});continue
        qid=matched[0];e=qualified[qid]
        if len(raw_qid_to_records[qid])!=1:
            holds.append({'record_id':rid,'reason':'same_QID_matches_multiple_official_records_before_filters','QID':qid,'record_ids':sorted(raw_qid_to_records[qid])});continue
        if occupied.get(qid) and occupied[qid]!={rid}:
            holds.append({'record_id':rid,'reason':'QID_already_occupied_by_another_v1_record','QID':qid,'occupied_record_ids':sorted(occupied[qid])});continue
        pids={x['value'] for x in e['past_id_claims'] if x.get('rank')!=DEPRECATED}
        if pids and pids!={b['external_id_value']}:
            holds.append({'record_id':rid,'reason':'contradictory_existing_P8612_values','QID':qid,'P8612_values':sorted(pids)});continue
        names=[x for x in e['names'] if norm(x['value'])==key[0]]
        candidates.append({'cohort':'UK_Royal_Society','record_id':rid,'name':b['name'],'authorised_form_of_name':o['authorised_form_of_name'],'official_full_name':full,'normalized_exact_name':key[0],'dob':b['dob'],'qid':qid,'lookup_qid':qid,'wikidata_qid':qid,'identity_link_provenance':'lookup_only_strict_unique_official_fullname_exact_existing_DOB_Gregorian_day_and_WD_RoyalSociety_membership','lookup_identity_provenance':'lookup_only_strict_unique_official_fullname_exact_existing_DOB_Gregorian_day_and_WD_RoyalSociety_membership','lookup_only':True,'source_grade':'S3','birthplace_source_grade':'S3','identity_acceptance_assigned':False,'final_analysis_eligibility_assigned':False,'dob_or_native_acceptance_modified':False,'DOB_or_acceptance_modified':False,'original_identity_flags_preserved':True,'official_name_source_url':o['source_url'],'official_name_source_sha256':o['source_sha256'],'official_name_parse_rule':status,'matched_Wikidata_English_labels_or_aliases':names,'Wikidata_DOB_value_claims_from_member_query':e['dob_claims'],'Wikidata_membership_claims':e['membership_claims'],'Wikidata_membership_claims_all':e['all_membership_claims'],'Wikidata_P8612_claims_all':e['past_id_claims'],'Wikidata_P19_coordinate_claims_all':e['birthplace_claims'],'Wikidata_P19_claims_all':e['birthplace_claims'],'source_claims':{'membership':e['membership_claims'],'P569_date_value_tuples_from_member_query':e['dob_claims'],'P19':e['birthplace_claims'],'P8612':e['past_id_claims']},'source_url':'https://www.wikidata.org/wiki/'+qid,'source_query_sha256':query_sha256,'source_response_sha256':response_sha256,'baseline_identity_provenance':b.get('lookup_identity_provenance',''),'baseline_reason':b.get('reason',''),'original_DOB':b['dob']})
    claims=collections.defaultdict(set)
    for x in candidates: claims[x['qid']].add(x['record_id'])
    good=[]
    for x in candidates:
        if len(claims[x['qid']])>1: holds.append({'record_id':x['record_id'],'QID':x['qid'],'reason':'same_QID_multiple_official_records','record_ids':sorted(claims[x['qid']])})
        else:good.append(x)
    assert len({x['qid'] for x in good})==len(good)==len({x['record_id'] for x in good})
    # The original member query returns date-value tuples only. It cannot certify
    # absence of somevalue/novalue; final seeds require this separate complete inventory.
    dump_jsonl(ROOT/'strict_lookup_candidate_seeds.jsonl',good)
    inventory=load_inventory()
    inventory_covered=0;inventory_reasons=collections.Counter();inventory_statements=set()
    final=[]
    for x in good:
        entry=inventory.get(x['qid'])
        if entry:
            inventory_covered+=1
            inventory_statements.update(r.get('statement',{}).get('value') for r in entry['statement_bindings'])
        passed,reason=inventory_gate(entry,x['dob'])
        if not passed:
            inventory_reasons[reason]+=1
            holds.append({'record_id':x['record_id'],'QID':x['qid'],'reason':reason,'P569_statement_inventory':entry,'DOB':x['dob']})
            continue
        x['P569_statement_inventory_gate']='all_P569_statements_prove_unique_Gregorian_day_equal_native_DOB'
        x['Wikidata_P569_statement_inventory_all']=entry
        x['source_claims']['P569_statement_inventory_all']=entry
        x['member_query_P569_scope']='date-value tuples only; somevalue/novalue coverage supplied by separate complete statement inventory'
        final.append(x)
    counts['unique_new_candidates_before_P569_inventory']=len(good)
    good=final
    dump_jsonl(ROOT/'strict_lookup_seeds.jsonl',good)
    dump_jsonl(ROOT/'strict_lookup_holds.jsonl',holds)
    counts['strict_unique_new_lookup_seeds']=len(good)
    counts['holds']=len(holds)
    counts['new_lookup_seeds_with_current_P19']=sum(bool([y for y in x['Wikidata_P19_coordinate_claims_all'] if y.get('rank')!=DEPRECATED]) for x in good)
    summary={'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'network_requests_from_join':0,'official_progress_records':len(official),'Wikidata_member_entities':len(entities),'Wikidata_member_entities_with_unique_Gregorian_day_DOB_value_candidate_before_inventory':len(qualified),'Wikidata_DOB_value_candidate_holds':dict(wd_holds),'counts':dict(counts),'hold_reasons':dict(collections.Counter(x['reason'] for x in holds)),'official_progress_source_path':str(args.official_progress.resolve()),'official_progress_snapshot':'official_name_join_snapshot.jsonl','official_progress_sha256':sha(official_snapshot),'member_response_sha256':sha(rawpath),'member_response_P569_coverage':'date-value tuples only; does not include all somevalue/novalue statements','P569_statement_inventory':{'required_for_every_final_seed':True,'candidate_QIDs':counts['unique_new_candidates_before_P569_inventory'],'candidate_QIDs_with_complete_inventory':inventory_covered,'candidate_QIDs_pending_inventory':counts['unique_new_candidates_before_P569_inventory']-inventory_covered,'final_seed_QIDs_passing_all_statement_gate':len(good),'distinct_statements_in_candidate_inventory':len(inventory_statements-{None}),'gate_hold_reasons':dict(inventory_reasons),'cache_sha256':sha(ROOT/'p569_statement_inventory.jsonl') if (ROOT/'p569_statement_inventory.jsonl').exists() else None},'exact_normalization_rules':['Unicode NFKC and casefold','collapse whitespace','normalize typographic apostrophes and hyphens','delete full-stop punctuation without expanding initials','remove only leading fixed titles Sir,Dame,Dr,Prof,Professor','authorised name: first semicolon field surname, skip independent title fields, next field given name before lifespan','no accent removal, no surname rearrangement, no alias expansion, no fuzzy matching'],'identity_acceptance_assigned':False,'DOB_or_acceptance_modified':False}
    (ROOT/'strict_lookup_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
