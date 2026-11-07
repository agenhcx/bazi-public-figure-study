"""Local-only projection of successful responses and whole-target matching."""
from pathlib import Path
import gzip, json, re, hashlib, collections, unicodedata
from census import ROOT, BASE, Links
from urllib.parse import urljoin

BASELINE=ROOT.parent.parent/'uk_birthplace_checkout/studies/royal_society_birthplace_completion_v8/outputs/uk_birthplace_rows.jsonl.gz'
EXPECTED='b13ba1336b5912e58cfc38aa79aa668772ece189623f32a23625e67eaabd4c92'
def write_jsonl(path, rows):
    with path.open('w') as f:
        for r in rows: f.write(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n')
def tokens(text):
    text=unicodedata.normalize('NFKD',text).encode('ascii','ignore').decode().lower()
    return {x for x in re.findall(r'[a-z]+',text) if x not in {'sir','dame','lord','baron','professor','prof','dr','jnr','c'}}
def prefix_lifespan(text):
    life=re.search(r'\((?:c\.\s*)?(\d{3,4})\??\s*-\s*(?:c\.\s*)?(\d{3,4})?\??\s*\)',text)
    return (text[:life.start()].strip() if life else text.split(';')[0].strip(),int(life[1]) if life else None,int(life[2]) if life and life[2] else None)

requests=[json.loads(x) for x in (ROOT/'requests.jsonl').read_text().splitlines()]
directory=[];counts=[]
for rec in requests:
    if rec['kind']!='navigation_index' or rec.get('status_code')!=200: continue
    letter=re.search(r'browse([a-z])_people',rec['url'])[1].upper()
    parser=Links(); parser.feed((ROOT/'raw'/f'index_{letter.lower()}.httpbody').read_text())
    links=[x for x in parser.links if re.fullmatch(r'biogs/P\d+b\.htm',x['href'])]
    counts.append({'letter':letter,'biography_link_count':len(links),'unique_biography_urls':len({x['href'] for x in links}),'source_url':rec['url'],'source_sha256':rec['source_sha256']})
    for link in links:
        name,birth,death=prefix_lifespan(link['text'])
        directory.append({'index_letter':letter,'index_text':link['text'],'index_name_prefix':name,'index_birth_year':birth,'index_death_year':death,'source_url':urljoin(BASE,link['href']),'index_url':rec['url'],'index_source_sha256':rec['source_sha256']})
write_jsonl(ROOT/'directory_projection.jsonl',directory)
(ROOT/'directory_census.json').write_text(json.dumps({'indices':counts,'successful_letter_indices':len(counts),'biography_links':len(directory),'unique_biography_urls':len({x['source_url'] for x in directory}),'scope':'Successful directory link projections only; no biography body read in this route. HTTP errors are not coverage.'},indent=2)+'\n')

sha=hashlib.sha256(BASELINE.read_bytes()).hexdigest()
assert sha==EXPECTED,(sha,EXPECTED)
rows=[json.loads(x) for x in gzip.open(BASELINE,'rt')]
unknown=[r for r in rows if r.get('hemisphere')=='unknown']
assert len(rows)==4983 and len(unknown)==647
coverage=[];candidates=[]
successful={x['letter'] for x in counts}
for row in unknown:
    official=row.get('source_authorised_full_name') or row['name']
    name,birth,death=prefix_lifespan(official)
    baseline_tokens=tokens(name)
    # Native names of current fellows have no catalogue title/lifespan wrapper.
    if row['record_id'].startswith('RS_CURRENT_'): baseline_tokens=tokens(row['name'])
    year=int(row['dob'][:4]);in_window=1835<=year<=1985
    surname=official.split(';')[0].strip() if ';' in official else row['name'].split()[-1]
    expected_letter=unicodedata.normalize('NFKD',surname)[0].upper()
    matches=[]
    for entry in directory:
        if entry['index_birth_year']!=year: continue
        name_tokens=tokens(entry['index_name_prefix'])
        if len(baseline_tokens)<2 or not baseline_tokens.issubset(name_tokens): continue
        if death and entry['index_death_year'] and death!=entry['index_death_year']: continue
        known_urls=set(row.get('birthplace_source_urls',[]))|{row.get('birthplace_source_url','')}
        for e in row.get('birthplace_evidence_candidates',[]):known_urls.update(e.get('source_urls',[]))
        existing=entry['source_url'] in known_urls
        candidate={'record_id':row['record_id'],'native_dob':row['dob'],'name':row['name'],'official_full_name':official,'in_window':in_window,'native_birth_year':year,'native_death_year_from_catalogue':death,'index_entry':entry,'frozen_name_tokens':sorted(baseline_tokens),'matching_basis':'All frozen full-name tokens appear in index full-name prefix, same native birth year, no observed lifespan conflict. Candidate only; biography identity and explicit birthplace unverified.','already_frozen_eoas_birthplace_source':existing,'decision':'excluded_existing_frozen_source' if existing else 'held_network_boundary_no_body','selected_for_body':False,'exclusion_reason':'Same EOAS URL already retained as frozen birthplace source; no new source fact.' if existing else 'Network stopped by root after repeated 503; body not requested; no birthplace fact inferred from index.'}
        matches.append(candidate);candidates.append(candidate)
    status='directory_name_lifespan_candidate_only' if matches else 'no_full_name_birthyear_match_in_successful_indices'
    if not matches and expected_letter not in successful:
        status='expected_surname_index_not_covered_in_successful_responses'
    coverage.append({'record_id':row['record_id'],'native_dob':row['dob'],'name':row['name'],'official_full_name':official,'in_window':in_window,'expected_surname_letter':expected_letter,'expected_surname_index_successful':expected_letter in successful,'successful_indices_compared':sorted(successful),'directory_link_rows_compared':len(directory),'match_count':len(matches),'candidate_urls':sorted({c['index_entry']['source_url'] for c in matches}),'coverage_status':status,'body_read':False,'decision':'held_network_boundary_no_body' if matches else 'excluded_no_observed_candidate_within_successful_directory_boundary','DOB_or_acceptance_modified':False,'formal_identity_flags_modified':False})
write_jsonl(ROOT/'candidate_projection.jsonl',candidates)
write_jsonl(ROOT/'whole_target_coverage.jsonl',coverage)
write_jsonl(ROOT/'accepted.jsonl',[])
(ROOT/'offline_match_summary.json').write_text(json.dumps({'baseline_file_sha256':sha,'rows':len(rows),'unknown_targets':len(unknown),'window_targets':sum(x['in_window'] for x in coverage),'directory_link_rows':len(directory),'unique_directory_urls':len({x['source_url'] for x in directory}),'candidate_links':len(candidates),'candidate_target_count':len({x['record_id'] for x in candidates}),'window_candidate_target_count':len({x['record_id'] for x in candidates if x['in_window']}),'existing_frozen_source_candidate_count':sum(x['already_frozen_eoas_birthplace_source'] for x in candidates),'coverage_status_counts':dict(collections.Counter(x['coverage_status'] for x in coverage)),'source_facts_accepted':0,'body_requests':0,'geography_assigned':False,'DOB_or_acceptance_modified':False,'formal_identity_flags_modified':False},indent=2)+'\n')
print((ROOT/'offline_match_summary.json').read_text())
for c in candidates: print(json.dumps(c,ensure_ascii=False))
