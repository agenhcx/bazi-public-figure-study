"""Reproduce the frozen zero-yield DCB route ledger; performs no network calls."""
import csv
import gzip
import hashlib
import json
from pathlib import Path
import re
import unicodedata

ROOT = Path(__file__).resolve().parent
BASELINE = ROOT.parent.parent / 'uk_birthplace_checkout/studies/royal_society_birthplace_completion_v9/outputs/uk_birthplace_rows.jsonl.gz'
EXPECTED = 'e44f6dc02cc0cafece9b792164f016da0f08de5736ac62442d176d45b19a5799'
HONORIFICS = {'sir', 'dame', 'dr', 'doctor', 'prof', 'professor', 'lord', 'lady', 'prince'}
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()

def normalize(value):
    text = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode().lower()
    return ' '.join(w for w in re.sub(r'[^a-z0-9 ]', ' ', text).split() if w not in HONORIFICS)

def strip_lifespan(value):
    return re.sub(r'\([^)]*\d[^)]*\)', '', value).strip()

def canonical_name(row):
    """Read surname; [honorific;] givens (life); [description] offline."""
    authorised = row.get('source_authorised_full_name', '').strip()
    if not authorised:
        review = row.get('geography_lookup_identity_review') or {}
        return review.get('native_name') or row['name'], 'current_native_full_name_separate'
    parts = [part.strip() for part in authorised.split(';')]
    if re.search(r'\([^)]*\d', parts[0]):
        return strip_lifespan(parts[0]), 'authorised_named_ruler_or_mononym_segment'
    given_segments = []
    found_lifespan = False
    for part in parts[1:]:
        clean = strip_lifespan(part)
        if normalize(clean):
            given_segments.append(clean)
        if re.search(r'\([^)]*\d', part):
            found_lifespan = True
            break
    assert found_lifespan, 'Unparsed authorised lifespan: ' + authorised
    assert given_segments, 'Missing authorised givens: ' + authorised
    return ' '.join(given_segments + [parts[0]]), 'authorised_surname_plus_given_segments_through_lifespan_excluding_honorific_only_segments'

assert sha(BASELINE) == EXPECTED
rows = [json.loads(s) for s in gzip.open(BASELINE, 'rt')]
unknown = [r for r in rows if r['hemisphere'] == 'unknown']
assert len(rows) == 4983 and len(unknown) == 645

fields = ['record_id', 'canonical_full_name', 'normalized_canonical_full_name', 'canonical_name_method', 'native_name_field', 'source_authorised_full_name', 'native_dob', 'birth_year', 'in_1835_1985_window', 'cohort_name_kind', 'screening_status', 'match_count', 'reason']
coverage = []
qa_changes = []
for r in unknown:
    auth = r.get('source_authorised_full_name', '')
    parts = auth.split(';')
    prior_naive = (parts[1].split('(')[0].strip() + ' ' + parts[0].strip()).strip() if len(parts) > 1 else r['name']
    canonical, method = canonical_name(r)
    if prior_naive != canonical:
        reason = 'Retained named-person first segment containing lifespan and excluded subsequent title/description.' if method == 'authorised_named_ruler_or_mononym_segment' else 'Excluded honorific-only segment and retained authorised given-name segment containing lifespan.'
        qa_changes.append(dict(record_id=r['record_id'], source_authorised_full_name=auth, prior_naive_name=prior_naive, corrected_canonical_full_name=canonical, canonical_name_method=method, reason=reason + ' This is target preparation only; no source index screen occurred.'))
    year = int(r['dob'][:4])
    coverage.append(dict(record_id=r['record_id'], canonical_full_name=canonical, normalized_canonical_full_name=normalize(canonical), canonical_name_method=method, native_name_field=r['name'], source_authorised_full_name=auth, native_dob=r['dob'], birth_year=year, in_1835_1985_window=1835 <= year <= 1985, cohort_name_kind='past_authorised_surname_and_givens' if auth else 'current_full_name_separate', screening_status='not_screened_source_rate_limited', match_count='', reason='Official homepage returned HTTP 429 before an alphabetical index could be obtained; no absence inference.'))
with (ROOT / 'coverage.csv').open('w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(coverage)
assert len(qa_changes) == 93
assert sum(c['canonical_name_method'] == 'authorised_named_ruler_or_mononym_segment' for c in qa_changes) == 3
with (ROOT / 'canonical_name_offline_qa.csv').open('w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(qa_changes[0])); w.writeheader(); w.writerows(qa_changes)
capture = ROOT / 'raw_transient/home_web_capture.json'
provenance = {
    'source_family': 'Dictionary of Canadian Biography',
    'publisher': 'University of Toronto / Université Laval',
    'intended_source_grade': 'S2_edited_dictionary_original_author',
    'url': 'https://www.biographi.ca/en/',
    'capture_file': str(capture.relative_to(ROOT)),
    'capture_type': 'web_tool_text_projection_json',
    'capture_sha256': sha(capture),
    'original_response_bytes_sha256': None,
    'original_response_bytes_unavailable': True,
    'http_status_reported_by_web_tool': 429,
    'web_ref_id': 'turn2078view0',
    'locator': 'web open result: failure message',
    'quote': 'Failed to fetch https://www.biographi.ca/en/: (429) Too Many Requests',
    'retrieval_date': '2026-11-03',
    'request_timestamp_utc': None,
    'request_timestamp_status': 'not_recorded_in_available_capture',
    'durable_before_request': False,
    'pre_request_durable_intent_record_found': False,
    'capture_persistence_timing': 'Captured text was saved after the request; no durable pre-request intent is claimed.',
    'retrospective_attempt_ledger': 'retrospective_attempt_ledger.jsonl',
    'attempt_ledger_reconstruction': 'After-the-fact reconstruction from the visible tool-call history and saved navigation capture; not an ex-ante request ledger.',
    'usable_birthplace_source': False,
}
(ROOT / 'provenance.json').write_text(json.dumps(provenance, indent=2) + '\n')
(ROOT / 'retrospective_attempt_ledger.jsonl').write_text(''.join(json.dumps(x, ensure_ascii=False) + '\n' for x in [
    dict(attempt_ordinal=1, request_kind='web_discovery_search', query='site.biographi.ca alphabetical index biographies birth search', url=None, attempted_at_utc=None, timestamp_status='unknown_not_recorded', durable_before_request=False, pre_request_durable_intent_record_found=False, record_created_after_request=True, record_type='retrospective_reconstruction', reconstruction_basis='visible conversation tool-call history', request_count=1, response_status='search_results_returned', original_response_bytes_sha256=None, saved_response_capture=None, result_use='discovery only; no index or person-body matching'),
    dict(attempt_ordinal=2, request_kind='official_navigation_open', query=None, url='https://www.biographi.ca/en/', attempted_at_utc=None, timestamp_status='unknown_not_recorded_in_capture', durable_before_request=False, pre_request_durable_intent_record_found=False, record_created_after_request=True, record_type='retrospective_reconstruction', reconstruction_basis='visible conversation tool-call history and saved web-tool text projection', request_count=1, response_status='HTTP_429_reported_by_web_tool', original_response_bytes_sha256=None, saved_response_capture='raw_transient/home_web_capture.json', saved_response_capture_sha256=sha(capture), web_ref_id='turn2078view0', action='stop immediately; no retries')
]))
(ROOT / 'candidate_ledger.jsonl').write_text('')
summary = {
    'route': 'DCB official public alphabetical index / bulk-source discovery',
    'baseline_sha256': EXPECTED,
    'baseline_rows': 4983,
    'unknown_targets': 645,
    'unknown_targets_in_1835_1985_window': sum(c['in_1835_1985_window'] for c in coverage),
    'source_index_records_obtained': 0,
    'target_rows_actually_matched_against_index': 0,
    'target_screening_status': 'not_screened_source_rate_limited',
    'index_name_match_result': None,
    'index_name_match_result_status': 'not_evaluated_no_source_index_obtained',
    'candidates': 0,
    'accepted_birthplace_claims': 0,
    'discovery_queries': 1,
    'navigation_index_requests': 1,
    'person_body_requests': 0,
    'stop_condition': 'HTTP_429_on_first_official_navigation',
    'retry_count': 0,
    'bounded_expansion_requested': False,
    'coverage_interpretation': 'All 645 targets are enumerated for reproducibility but are not screened. Zero yield is not evidence of absence from DCB.',
    'modifications_to_native_DOB_QID_identity_geography_or_baseline': False,
    'initial_discovery_query': 'site.biographi.ca alphabetical index biographies birth search',
    'discovery_outcome': 'Search returned an official search-form result among other results; no downloadable or alphabetical index was established before the hard stop.'
}
summary.update({
    'offline_QA_correction': 'Naive parts[1] name extraction omitted authorised givens on 90 titled rows and incorrectly appended title/descriptions on 3 named-person rows with lifespan in first segment; offline parser now reads the authorised lifespan-bearing name segments.',
    'canonical_name_rows_corrected_offline': len(qa_changes),
    'titled_given_name_rows_corrected_offline': 90,
    'first_segment_named_person_rows_corrected_offline': 3,
    'past_authorised_full_name_rows_prepared_only': sum(bool(r.get('source_authorised_full_name')) for r in unknown),
    'current_native_full_name_rows_prepared_only': sum(not bool(r.get('source_authorised_full_name')) for r in unknown),
    'all_coverage_rows_not_screened': all(c['screening_status'] == 'not_screened_source_rate_limited' and c['match_count'] == '' for c in coverage),
    'offline_QA_new_network_requests': 0,
    'retrospective_attempt_ledger': 'retrospective_attempt_ledger.jsonl',
    'durable_before_request': False,
    'pre_request_durable_intent_record_found': False,
    'attempt_ledger_limit': 'Reconstructed after the requests. Available records do not establish an exact request timestamp or a durable pre-request intent record.'
})
assert summary['unknown_targets_in_1835_1985_window'] == 211
(ROOT / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
freeze_files = [p for p in sorted(ROOT.rglob('*')) if p.is_file() and p.name != 'SHA256SUMS']
(ROOT / 'SHA256SUMS').write_text(''.join(sha(p) + '  ' + str(p.relative_to(ROOT)) + '\n' for p in freeze_files))
print(json.dumps(summary, indent=2))
