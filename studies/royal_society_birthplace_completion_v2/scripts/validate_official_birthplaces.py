#!/usr/bin/env python3
"""Verify row conservation, unchanged DOB and independently bounded source fields."""
import argparse,csv,hashlib,html,json,re
from collections import Counter
from pathlib import Path

def sha(raw):return hashlib.sha256(raw).hexdigest()
def normal(s):return re.sub(r'\s+',' ',html.unescape(s)).strip()
def table_field(text,row_id):
    rows=re.findall(r'<tr\b[^>]*\bid\s*=\s*[\"\']'+re.escape(row_id)+r'(?=[&\s\"\'])[^\"\']*[\"\'][^>]*>(.*?)</tr\s*>',text,re.I|re.S)
    out=[]
    for row in rows:
        cells=re.findall(r'<td\b[^>]*\bclass\s*=\s*[\"\']tablevalue[\"\'][^>]*>(.*?)</td\s*>',row,re.I|re.S)
        out.extend(normal(re.sub(r'<[^>]+>','',cell)) for cell in cells)
    return out

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--baseline',type=Path,required=True);ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args()
    with args.baseline.open(encoding='utf-8-sig',newline='') as f:base={r['cohort_key']:r for r in csv.DictReader(f)}
    path=args.output/'official_birthplace_rows.jsonl'
    rows=[json.loads(l) for l in path.read_text().splitlines() if l.strip()]
    assert len(rows)==4884 and len(base)==4884 and len({r['record_id'] for r in rows})==4884
    assert {r['record_id'] for r in rows}==set(base)
    independent_mismatches=[];lifespan_year_diagnostics=[]
    for r in rows:
        old=base[r['record_id']]
        assert r['archive_id']==old['record_id'] and r['existing_dob']==old['dob_exact_iso']
        assert r['name']==old['display_name'] and r['source_url']==old['source_url']
        assert r['DOB_or_acceptance_modified'] is False
        if r['source_sha256']:
            source=(args.output/r['raw_source_file']).read_bytes();assert sha(source)==r['source_sha256']
            assert len(source)==r['source_bytes']
            text=source.decode('utf-8',errors='replace')
            births=table_field(text,'PlaceOfBirth')
            expected=births[0] if len(births)==1 else ''
            if normal(r['raw_placeofbirth'])!=expected or (len(births)>1 and r['parse_status']!='multiple_birthplace_fields_hold'):
                independent_mismatches.append({'record_id':r['record_id'],'parser_value':r['raw_placeofbirth'],'row_id_regex_values':births})
            name=r.get('authorised_form_of_name','')
            year=re.search(r'\((\d{4})\s*[-–]',name)
            if year and year.group(1)!=r['existing_dob'][:4]:
                lifespan_year_diagnostics.append({'record_id':r['record_id'],'name':name,'existing_dob':r['existing_dob'],'diagnostic_only_not_a_new_DOB_decision':True})
        else:
            assert not r['raw_placeofbirth']
    result={'schema':'royal_society_birthplace_v2_integrity_validation','baseline_rows':len(base),'output_rows':len(rows),
            'all_baseline_ids_retained_once':True,'all_native_names_DOB_and_source_URLs_unchanged':True,
            'all_record_flags_preserve_native_acceptance':True,'all_stored_source_SHA256_and_byte_lengths_match':True,
            'independent_PlaceOfBirth_row_id_regex_mismatch_count':len(independent_mismatches),
            'independent_PlaceOfBirth_row_id_regex_mismatches':independent_mismatches,
            'parse_status_counts':dict(Counter(r['parse_status'] for r in rows)),
            'network_or_parse_errors':sum(bool(r['error']) for r in rows),
            'lifespan_year_diagnostics':lifespan_year_diagnostics,
            'baseline_sha256':sha(args.baseline.read_bytes()),'output_sha256':sha(path.read_bytes()),
            'validator_sha256':sha(Path(__file__).read_bytes())}
    (args.output/'validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ['independent_PlaceOfBirth_row_id_regex_mismatches','lifespan_year_diagnostics']},ensure_ascii=False))
    if independent_mismatches:raise SystemExit('Review independent field locator mismatches before accepting outputs')

if __name__=='__main__':main()
