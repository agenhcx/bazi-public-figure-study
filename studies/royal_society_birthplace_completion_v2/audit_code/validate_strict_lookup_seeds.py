#!/usr/bin/env python3
"""Validate delivered seeds against frozen cohort and actual official HTML bytes."""
import copy,gzip,hashlib,json,pathlib
from join_strict_links import ROOT,norm,fullname
from p569_inventory import gate as inventory_gate

def main():
    seeds=[json.loads(line) for line in (ROOT/'strict_lookup_seeds.jsonl').open()]
    official={x['record_id']:x for x in map(json.loads,(ROOT/'official_name_join_snapshot.jsonl').open())}
    path=ROOT.parent.parent/'uk_birthplace_checkout/studies/academy_birthplace_screen_v1/outputs/birthplace_rows.jsonl.gz'
    baseline={x['record_id']:x for x in map(json.loads,gzip.open(path,'rt')) if x['cohort']=='UK_Royal_Society'}
    assert len(seeds)==len({x['qid'] for x in seeds})==len({x['record_id'] for x in seeds})
    response_cache={}
    for x in seeds:
        base=baseline[x['record_id']];o=official[x['record_id']]
        assert not base.get('lookup_qid')
        assert x['dob']==x['original_DOB']==base['dob']==o['existing_dob']
        assert x['official_full_name']==fullname(o['authorised_form_of_name'])[0]
        assert x['authorised_form_of_name']==o['authorised_form_of_name']
        assert all(norm(n['value'])==norm(x['official_full_name']) for n in x['matched_Wikidata_English_labels_or_aliases'])
        ds=x['source_claims']['P569_date_value_tuples_from_member_query']
        assert len({(d['value'],d['precision'],d['calendar']) for d in ds})==1
        assert any(d['rank']!='http://wikiba.se/ontology#DeprecatedRank' for d in ds)
        assert ds[0]['precision']=='11' and ds[0]['calendar']=='http://www.wikidata.org/entity/Q1985727'
        assert ds[0]['value'].lstrip('+').split('T')[0]==x['dob']
        ms=x['source_claims']['membership']
        assert ms and all(m['rank']!='http://wikiba.se/ontology#DeprecatedRank' for m in ms)
        allowed={('P463','http://www.wikidata.org/entity/Q123885'),('P166','http://www.wikidata.org/entity/Q15631401'),('P166','http://www.wikidata.org/entity/Q14906020')}
        assert all((m['property'],m['value']) in allowed for m in ms)
        assert x['lookup_only'] and x['source_grade']=='S3'
        assert not x['identity_acceptance_assigned'] and not x['final_analysis_eligibility_assigned'] and not x['dob_or_native_acceptance_modified']
        inventory=x['Wikidata_P569_statement_inventory_all']
        assert inventory['qid']==x['qid'] and inventory_gate(inventory,x['dob'])[0]
        assert x['P569_statement_inventory_gate']=='all_P569_statements_prove_unique_Gregorian_day_equal_native_DOB'
        source=inventory['source_response_file']
        if source not in response_cache:
            raw=(ROOT/source).read_bytes()
            assert hashlib.sha256(raw).hexdigest()==inventory['source_response_sha256']
            response_cache[source]=json.loads(raw)['results']['bindings']
            assert hashlib.sha256((ROOT/inventory['source_query_file']).read_bytes()).hexdigest()==inventory['source_query_sha256']
        source_rows=[{k:v for k,v in row.items() if k!='person'} for row in response_cache[source] if row['person']['value'].rsplit('/',1)[-1]==x['qid']]
        assert inventory['statement_bindings']==source_rows
        for row in inventory['statement_bindings']:
            assert row['noValue']['value']=='false'
            assert row['value']['type']=='literal' and row['value']['datatype']=='http://www.w3.org/2001/XMLSchema#dateTime'
            assert row['valueIsBlank']['value']=='false' and row['valueIsIRI']['value']=='false'
            assert row['timeValue']['value']==row['value']['value']
            assert row['precision']['value']=='11' and row['calendar']['value']=='http://www.wikidata.org/entity/Q1985727'
        html=ROOT.parent/'official'/o['raw_source_file']
        assert hashlib.sha256(html.read_bytes()).hexdigest()==x['official_name_source_sha256']
    summary=json.loads((ROOT/'strict_lookup_summary.json').read_text())
    assert hashlib.sha256((ROOT/'official_name_join_snapshot.jsonl').read_bytes()).hexdigest()==summary['official_progress_sha256']
    regression=[]
    if seeds:
        template=seeds[0]['Wikidata_P569_statement_inventory_all'];day=seeds[0]['dob']
        for name in ('novalue','somevalue_bnode','somevalue_skolem_IRI','missing_psv','different_time_value','missing_inventory'):
            fixture=copy.deepcopy(template)
            if name=='missing_inventory':fixture=None
            else:
                extra=copy.deepcopy(fixture['statement_bindings'][0]);extra['statement']['value']+='-regression-extra'
                if name=='novalue':extra['noValue']['value']='true'
                elif name=='somevalue_bnode':extra['value']={'type':'bnode','value':'unknown'};extra['valueIsBlank']['value']='true'
                elif name=='somevalue_skolem_IRI':extra['value']={'type':'uri','value':'http://www.wikidata.org/.well-known/genid/unknown'};extra['valueIsIRI']['value']='true'
                elif name=='missing_psv':extra.pop('timeValue',None)
                elif name=='different_time_value':extra['timeValue']['value']='1900-01-01T00:00:00Z'
                fixture['statement_bindings'].append(extra)
            assert not inventory_gate(fixture,day)[0],name
            regression.append(name)
    assert summary['P569_statement_inventory']['candidate_QIDs_pending_inventory']==0,'Refresh pending inventory before final handoff'
    checks={'validated_seeds':len(seeds),'one_to_one_QIDs_and_records':True,'all_DOB_claims_unique_Gregorian_day_and_equal_original':True,'all_P569_statements_including_nonvalue_inventory_required_and_verified':True,'inventory_raw_response_and_query_hashes_verified':True,'inventory_gate_negative_regressions_passed':regression,'all_member_claims_qualifying_and_non_deprecated':True,'all_official_source_HTML_hashes_verified':True,'lookup_only_and_no_native_acceptance_change':True,'official_snapshot_matches_summary_hash':True,'validated_seed_file_sha256':hashlib.sha256((ROOT/'strict_lookup_seeds.jsonl').read_bytes()).hexdigest()}
    (ROOT/'validation.json').write_text(json.dumps(checks,indent=2)+'\n')
    print(json.dumps(checks,indent=2))

if __name__=='__main__':main()
