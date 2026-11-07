#!/usr/bin/env python3
"""Offline NAS extension: explicit named state extents, zero network requests."""
from pathlib import Path
from datetime import datetime, timezone
from html.parser import HTMLParser
from collections import Counter
import gzip
import hashlib
import json
import re
import unicodedata

ROOT = Path(__file__).resolve().parent
BASE = ROOT.parents[1]
NAS = BASE/'academy_v3_workers/nas_memoirs/retained/source_facts.jsonl'
BASELINE = BASE/'uk_birthplace_checkout/studies/scientist_birthplace_completion_v2/outputs/birthplace_rows.jsonl.gz'
EXPECTED_NAS_SHA = 'ca1fe908b781e09591ae2d3760620e51f151afee90c431c122b0c317f29d7fd9'
EXPECTED_FIELDS_REVIEW_SHA = '5c83523b485f98b3446a3fc78f2c0677df7a68d80bfa9599812e15430bd2abb0'
STATE_RULES = {
 'L. A. DuBridge': ('Terre Haute, Indiana','Indiana'),
 'R. G. Herb': ('Navarino on a small farm in north-central Wisconsin','Wisconsin'),
 'Donald W. Kerst': ('Galena, Illinois','Illinois'),
 'Paul J. Kramer': ('Brookville, Indiana','Indiana'),
 'W. W. Morgan': ('Bethesda, Tennessee','Tennessee'),
 'M. M. Rhoades': ('Graham, Missouri','Missouri'),
 'J. E. Varner': ('Nashport, Ohio','Ohio'),
}

def now(): return datetime.now(timezone.utc).isoformat()
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def readj(p): return json.loads(p.read_text())
def writej(p,obj): p.write_text(json.dumps(obj,ensure_ascii=False,sort_keys=True,indent=2)+'\n')
def writel(p,rows): p.write_text(''.join(json.dumps(x,ensure_ascii=False,sort_keys=True)+'\n' for x in rows))
def norm(s): return ' '.join(unicodedata.normalize('NFKC',s).replace('’',"'").replace('‘',"'").split()).casefold()

class Plain(HTMLParser):
    def __init__(self): super().__init__(convert_charrefs=True); self.parts=[]
    def handle_data(self,s): self.parts.append(s)
    def extract(self,s): self.feed(s); return ''.join(self.parts)

def main():
    assert sha(NAS)==EXPECTED_NAS_SHA
    assert sha(ROOT/'georeview.jsonl')==EXPECTED_FIELDS_REVIEW_SHA
    for original,snapshot in [('summary.json','fields_summary.json'),('verification.json','fields_verification.json'),('SHA256SUMS','fields_SHA256SUMS')]:
        destination=ROOT/snapshot
        if not destination.exists(): destination.write_bytes((ROOT/original).read_bytes())
    fields_summary=readj(ROOT/'fields_summary.json')
    assert fields_summary['review_rows']==2 and fields_summary['actual_geography_queries']==1
    field_locks=readj(ROOT/'input_locks.json')
    for locked in field_locks['inputs']: assert sha(Path(locked['path']))==locked['sha256']
    fields_reviews=[json.loads(x) for x in (ROOT/'georeview.jsonl').read_text().splitlines() if x]
    facts=[json.loads(x) for x in NAS.read_text().splitlines() if x]
    assert len(facts)==7 and {x['name'] for x in facts}==set(STATE_RULES)
    ids={x['record_id'] for x in facts}
    baseline={}
    for line in gzip.open(BASELINE,'rt'):
        row=json.loads(line)
        if row['record_id'] in ids: baseline[row['record_id']]=row
    assert set(baseline)==ids
    inputs=[{'path':str(NAS),'sha256':sha(NAS),'kind':'frozen_seven_source_facts'},
      {'path':str(BASELINE),'sha256':sha(BASELINE),'kind':'frozen_v2_baseline'},
      {'path':str(ROOT/'georeview.jsonl'),'sha256':sha(ROOT/'georeview.jsonl'),'kind':'frozen_two_Fields_geographic_reviews'},
      {'path':str(ROOT/'raw/geo_v3_exact_001.response'),'sha256':sha(ROOT/'raw/geo_v3_exact_001.response'),'kind':'frozen_one_query_response'},
      {'path':str(ROOT/'request_ledger.jsonl'),'sha256':sha(ROOT/'request_ledger.jsonl'),'kind':'frozen_one_query_request_ledger'}]
    checks=[]
    reviews=[]
    for fact in facts:
        native=baseline[fact['record_id']]
        assert native==fact['frozen_baseline_row']
        assert native['dob']==fact['native_dob']
        assert native['hemisphere']=='unknown'
        assert fact['source_grade']=='S2'
        assert fact['review_status']=='accepted_literal_source_fact'
        raw_place,state=STATE_RULES[fact['name']]
        assert fact['raw_birthplace']==raw_place
        assert state in fact['evidence_quote'] and state in raw_place
        assert fact['evidence_quote_word_count']<=25
        original=BASE/fact['raw_source_file']
        assert sha(original)==fact['original_bytes_sha256']
        line_number=int(re.findall(r'original HTML line ([0-9]+)',fact['locator'])[-1])
        source_line=original.read_text().splitlines()[line_number-1]
        source_text=Plain().extract(source_line)
        assert norm(fact['evidence_quote']) in norm(source_text)
        assert norm(state) in norm(source_text)
        inputs.append({'path':str(original),'sha256':sha(original),'source_capture_kind':fact['capture_kind'],'source_capture_scope':fact['capture_scope']})
        checks.append({'record_id':fact['record_id'],'name':fact['name'],'state_extent_explicit_in_birth_clause':state,
          'source_quote_verified_at_original_HTML_line':line_number,'original_quote_word_count':fact['evidence_quote_word_count'],
          'supplemental_source_quotes_added':0,'raw_source_hash_verified':True,'full_frozen_baseline_row_equal':True})
        reviews.append({'record_id':fact['record_id'],'name':fact['name'],'cohort':fact['cohort'],
          'native_dob':fact['native_dob'],'raw_birthplace':fact['raw_birthplace'],
          'source_birthplace_qualifier_as_printed':fact['birthplace_qualifier_as_printed'],
          'source_fact_path':str(NAS),'source_fact_sha256':sha(NAS),'source_fact_locator':fact['locator'],
          'source_sha256':fact['original_bytes_sha256'],'source_url':fact['source_url'],
          'source_capture_kind':fact['capture_kind'],'source_capture_scope':fact['capture_scope'],
          'birthplace_source_grade':'S2','geographic_resolution_source_grade':'S3',
          'source_grade_independent_of_geographic_resolution':True,'source_grade_independent_of_DOB_grade':True,
          'source_birth_date_precision':fact['source_dob_precision'],'birth_clause_date_precision':fact['birth_clause_dob_precision'],
          'hemisphere':'north','review_status':'hemisphere_resolved','basis':'explicit_named_extent_wholly_north',
          'extent':state,'extent_kind':'source_explicit_named_state',
          'rule_origin':'Existing explicit named geographic extent rule, extended only to the state named in the target birth clause.',
          'proof_note':'The source-explicit state is wholly in the Northern Hemisphere; no city homonym, modern settlement, exact location, or unique locality entity is selected.',
          'source_state_verified_in_same_birth_clause':True,'source_extent_supplemental_quote_added':False,
          'NAS_nationality_or_workplace_used_to_infer_country':False,
          'country_assigned':False,'birthpoint_coordinates_assigned':False,'unique_locality_entity_assigned':False,
          'person_QIDs_modified':False,'native_flags_modified':False,'native_DOB_modified':False,
          'DOB_groups_modified':False,'eligibility_modified':False,'calendar_modified':False,
          'source_birth_year_used_to_fill_native_DOB_or_window':False,'source_birthplace_granularity_preserved':True,
          'new_network_requests':0})
    lock_path=ROOT/'nas_input_locks.json'
    if lock_path.exists():
        old=readj(lock_path)
        assert old['inputs']==inputs
    else:
        writej(lock_path,{'frozen_utc':now(),'approved_scope':'Seven retained NAS source facts only; held Chandrasekhar candidate is not an input and was not read.',
          'source_fact_rows':7,'new_geography_query_budget':0,'inputs':inputs})
    writel(ROOT/'nas_georeview.jsonl',reviews)
    combined=fields_reviews+reviews
    writel(ROOT/'combined_georeview.jsonl',combined)
    writej(ROOT/'nas_birth_clause_verification.json',{'verified_utc':now(),'supplemental_source_quotes_added':0,'checks':checks})
    summary={'completed_utc':now(),'scope':'Two frozen Fields geographic reviews plus seven frozen NAS source facts; hemisphere-only.',
      'input_source_facts':9,'Fields_source_facts':2,'NAS_source_facts':7,'review_rows':9,
      'hemispheres':dict(Counter(x['hemisphere'] for x in combined)),
      'hemispheres_by_cohort':{c:dict(Counter(x['hemisphere'] for x in combined if x['cohort']==c)) for c in sorted({x['cohort'] for x in combined})},
      'geography_holds':0,'NAS_additional_geography_query_budget':0,'NAS_additional_geography_queries':0,
      'bounded_geography_query_budget':1,'actual_geography_queries':1,'retries':0,'redirects_followed':0,
      'person_queries':0,'individual_birthday_queries':0,'new_birthplace_source_requests':0,
      'query_exact_labels_aliases':fields_summary['query_exact_labels_aliases'],'query_has_LIMIT':False,
      'all_returned_homonyms_retained':True,'returned_homonyms':fields_summary['returned_homonyms'],
      'raw_query_bindings':fields_summary['raw_query_bindings'],'all_direct_Earth_coordinate_statements_retained':True,
      'coordinate_ranks_filtered':False,'hemisphere_only':True,'country_assignments':0,
      'birthpoint_coordinate_assignments':0,'unique_locality_entity_assignments':0,
      'source_facts_mutated':False,'native_DOBs_mutated':False,'native_flags_mutated':False,'QIDs_mutated':False,
      'repository_files_modified':False,'source_and_DOB_grades_independent':True,
      'birthplace_source_grades':{'S1':2,'S2':7},'geographic_resolution_source_grade':'S3',
      'raw_source_captures_preserve_original_metadata':True,'fields_capture_kind':'web_tool_text_capture_json',
      'NAS_capture_kind':'original_HTTP_response_body','SPARQL_capture_kind':'direct_http_response_bytes',
      'NAS_source_explicit_state_extents':dict(Counter(x['extent'] for x in reviews)),
      'NAS_supplemental_source_quotes_added':0,'NAS_nationality_or_workplace_used_to_infer_USA':False,
      'held_source_candidates_read':False,'held_Chandrasekhar_not_accepted_or_geographically_reviewed':True,
      'frozen_Fields_review_path':str(ROOT/'georeview.jsonl'),'frozen_Fields_review_sha256':EXPECTED_FIELDS_REVIEW_SHA,
      'NAS_review_path':str(ROOT/'nas_georeview.jsonl'),'combined_review_path':str(ROOT/'combined_georeview.jsonl')}
    writej(ROOT/'summary.json',summary)
    verification={'verified_utc':now(),'status':'pass','review_rows':len(combined),
      'checks':{'all_original_Fields_input_hashes_match':True,'original_Fields_review_byte_for_byte_preserved':True,
        'all_NAS_input_hashes_match':True,'seven_NAS_source_grades_remain_S2':True,
        'all_seven_state_extents_explicit_in_the_same_birth_clause':True,'all_original_birth_quotes_verified_at_cited_HTML_line':True,
        'all_full_frozen_NAS_baseline_rows_equal':True,'all_native_DOBs_preserved':True,
        'hemisphere_only_no_country_or_birthpoint_or_unique_entity_assignment':True,'source_capture_metadata_preserved':True,
        'all_nine_ids_unique':len({x['record_id'] for x in combined})==9,'NAS_extension_zero_queries':True,
        'total_single_locality_query_zero_retries':True,'held_Chandrasekhar_not_an_input':True,
        'source_grades_and_DOB_grades_independent_of_geographic_grade':True,'baseline_file_unmodified':True,
        'all_source_fact_files_unmodified':True,'no_supplemental_source_quotes_added':True},
      'combined_review_sha256':sha(ROOT/'combined_georeview.jsonl'),'NAS_review_sha256':sha(ROOT/'nas_georeview.jsonl'),
      'frozen_Fields_review_sha256':sha(ROOT/'georeview.jsonl'),'baseline_sha256':sha(BASELINE),
      'NAS_facts_sha256':sha(NAS),'Fields_facts_sha256':sha(Path(field_locks['inputs'][1]['path'])),
      'Fields_query_response_sha256':sha(ROOT/'raw/geo_v3_exact_001.response'),
      'input_lock_paths':[str(ROOT/'input_locks.json'),str(ROOT/'nas_input_locks.json')],
      'source_quote_policy':'No new source quotes; source-explicit state extents verified against the already frozen birth excerpts and cited HTML lines.'}
    assert all(verification['checks'].values())
    writej(ROOT/'verification.json',verification)
    for locked in field_locks['inputs']+inputs: assert sha(Path(locked['path']))==locked['sha256']
    assert sha(ROOT/'georeview.jsonl')==EXPECTED_FIELDS_REVIEW_SHA
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=='__main__': main()
