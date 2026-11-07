from pathlib import Path
import datetime as dt
import hashlib
import json

ROOT = Path(__file__).resolve().parent
RAW = ROOT / 'raw'
NOW = dt.datetime.now(dt.timezone.utc).isoformat()
BASELINE_SHA256 = '2ad00462255629a603bc4a95aa64158141b5a9b105359baece528a163aa93d92'

def jsonl(path, rows):
    path.write_text(''.join(json.dumps(r, ensure_ascii=False, sort_keys=True) + '\n' for r in rows))

def capture(file):
    p = RAW / file
    b = p.read_bytes()
    return {'raw_source_file': str(p), 'source_sha256': hashlib.sha256(b).hexdigest(),
            'source_capture_kind': 'web_tool_text_capture_json',
            'source_capture_scope': 'Exact persisted JSON tool response containing normalized web/PDF text and tool metadata; not original publisher bytes.',
            'retrieved_utc': dt.datetime.fromtimestamp(p.stat().st_mtime, dt.timezone.utc).isoformat(),
            'retrieved_utc_basis': 'Persisted tool-response capture timestamp, shortly after request.'}

baseline = json.loads((ROOT / 'baseline_targets.json').read_text())
native = {r['record_id']: r for r in baseline}
facts = [
    {
        'cohort': 'Fields_main', 'record_id': 'fields-12ddab1dd74af07f',
        'native_dob': '1981-11-21', 'name': 'Akshay Venkatesh',
        'raw_birthplace': 'New Delhi, India', 'source_grade': 'S1',
        'source_url': 'https://www.ias.edu/sites/default/files/math/faculty/akshay/akshaycv-2018.pdf',
        'source_urls': ['https://www.ias.edu/sites/default/files/math/faculty/akshay/akshaycv-2018.pdf'],
        'source_author': 'Akshay Venkatesh (self CV hosted by Institute for Advanced Study)',
        'evidence_quote': 'Born 1981 in New Delhi, India.',
        'evidence_locator': 'PDF page 1 (P0), Personal, web-extracted line L6; heading L0; Awards/Recognition L16.',
        'source_birth_date_text': '1981', 'source_birth_date_precision': 'year',
        'identity_review': {
            'status': 'matched_by_exact_full_name_and_official_fields_award_context',
            'name_evidence': 'CV title gives exact full name Akshay Venkatesh.',
            'birth_date_review': 'Source birth year 1981 agrees with native year; source does not support month/day and native DOB remains unchanged.',
            'official_fields_context': 'Same self CV explicitly lists Fields Medal, 2018 under Awards/Recognition (L16).',
            'identity_independent_of_birthplace': True,
            'native_dob_modified': False, 'qid_modified': False,
            'calendar_eligibility_and_dob_groups_modified': False,
        },
        **capture('fields_body_001.webcapture.json'),
    },
    {
        'cohort': 'Fields_main', 'record_id': 'fields-c847084f96ea991e',
        'native_dob': '1974-08-08', 'name': 'Manjul Bhargava',
        'raw_birthplace': 'Canada', 'source_grade': 'S1',
        'source_url': 'https://www.mathunion.org/fileadmin/IMU/Prizes/Fields/2014/news_release_bhargava.pdf',
        'source_urls': [
            'https://www.mathunion.org/fileadmin/IMU/Prizes/Fields/2014/news_release_bhargava.pdf',
            'https://www.mathunion.org/imu-awards/fields-medal/fields-medals-2014',
        ],
        'source_author': 'International Mathematical Union (official prize press biography; individual byline not stated)',
        'evidence_quote': 'Born in 1974 in Canada, Manjul Bhargava',
        'evidence_locator': 'PDF page 5 (P4), Biography, web-extracted L162-L166; L163 contains quoted clause.',
        'source_birth_date_text': '1974', 'source_birth_date_precision': 'year',
        'raw_birthplace_precision_note': 'Country-level source wording only; no city inferred or promoted from discovery snippets.',
        'identity_review': {
            'status': 'matched_by_exact_full_name_and_official_fields_award_context',
            'name_evidence': 'Official IMU press biography heading and birth clause give exact full name Manjul Bhargava.',
            'birth_date_review': 'Source birth year 1974 agrees with native year; source does not support month/day and native DOB remains unchanged.',
            'official_fields_context': 'Official Fields Medals 2014 page names Manjul Bhargava (L22-L24) and links this press release (link 7 at L26).',
            'official_fields_context_capture': capture('fields_body_005.webcapture.json'),
            'identity_independent_of_birthplace': True,
            'native_dob_modified': False, 'qid_modified': False,
            'calendar_eligibility_and_dob_groups_modified': False,
        },
        **capture('fields_body_006.webcapture.json'),
    },
]

coverage = []
byid = {r['record_id']: r for r in facts}
for r in baseline:
    if r['record_id'] in byid:
        coverage.append({'cohort': r['cohort'], 'record_id': r['record_id'], 'name': r['name'], 'native_dob': r['dob'],
                         'status': 'accepted_source_fact_pending_root_qa_and_geographic_review',
                         'raw_birthplace': byid[r['record_id']]['raw_birthplace'], 'source_grade': 'S1'})
    elif r['name'] == 'Stanislav Smirnov':
        coverage.append({'cohort': r['cohort'], 'record_id': r['record_id'], 'name': r['name'], 'native_dob': r['dob'],
                         'status': 'unknown', 'reason': 'Official UniGE lead body returned access denied; no birthplace body observed; no retry.',
                         'unaccepted_lead': r['unaccepted_discovery_leads'], 'failure_capture': capture('fields_body_002.webcapture.json')})
    else:
        coverage.append({'cohort': r['cohort'], 'record_id': r['record_id'], 'name': r['name'], 'native_dob': r['dob'],
                         'status': 'unknown', 'reason': 'Official IMU interview body has no explicit birthplace; final official exposition request timed out; no retry.',
                         'unaccepted_discovery_leads': [{'url': 'https://www.ihes.fr/~duminil/publi/CV_publist_Duminil.pdf', 'status': 'snippet_only_date_without_birthplace'},
                                                        {'url': 'https://www.mathunion.org/fileadmin/IMU/Prizes/Fields/2022/HDC_FM.pdf', 'status': 'body_request_timeout'}],
                         'interview_capture': capture('fields_body_007.webcapture.json'), 'failure_capture': capture('fields_body_008.webcapture.json')})

outcomes = [
    ('discovery-001', '3 discovery queries completed', 'discovery_001.webcapture.json'),
    ('discovery-002', '1 discovery query completed', 'fields_search_002.webcapture.json'),
    ('body-001', 'accepted: explicit birthplace and birth year; official Fields award context in self CV', 'fields_body_001.webcapture.json'),
    ('body-002', 'access denied body; no retry', 'fields_body_002.webcapture.json'),
    ('body-003', 'official Fields identity context only; no explicit birthplace', 'fields_body_003.webcapture.json'),
    ('body-004', 'official Fields identity context and onward links only; no explicit birthplace', 'fields_body_004.webcapture.json'),
    ('body-005', 'official Fields identity context and press-release link only; no explicit birthplace', 'fields_body_005.webcapture.json'),
    ('body-006', 'accepted: explicit country-level birthplace and birth year in official IMU biography', 'fields_body_006.webcapture.json'),
    ('body-007', 'official IMU interview; no explicit birthplace', 'fields_body_007.webcapture.json'),
    ('body-008', 'HTTP 400 wrapper / Timeout fetching reported by web tool; no retry', 'fields_body_008.webcapture.json'),
]
jsonl(ROOT / 'request_outcomes.jsonl', [{'attempt_id': a, 'outcome': b, 'recorded_utc': NOW, **capture(c)} for a,b,c in outcomes])
jsonl(ROOT / 'accepted.jsonl', facts)
jsonl(ROOT / 'coverage.jsonl', coverage)
summary = {
    'baseline_sha256': BASELINE_SHA256, 'targets': 4, 'accepted_source_facts': len(facts), 'remaining_unknown': 2,
    'discovery_queries_used': 4, 'actual_body_reads_used': 8, 'frozen_utc': NOW,
    'stop_reason': 'Read cap reached; bounded pass frozen without retries.',
    'geography_country_or_point_assignments_made': False,
    'native_dob_formal_identity_calendar_eligibility_dobgroups_qids_modified': False,
    'original_publisher_bytes_preserved': False,
    'capture_note': 'Web tool normalized text responses preserved with SHA256; hashes identify capture JSON, not original PDF/HTML bytes.',
    'review_gate': 'Accepted file contains source facts only; root QA then geographic review are still required.',
    'artifact_policy': 'accepted/coverage/summary contain facts, short quotations and metadata only; complete fetched tool responses are confined to raw caches.',
}
(ROOT / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
for fact in facts:
    row = native[fact['record_id']]
    assert fact['name'] == row['name'] and fact['cohort'] == row['cohort'] and fact['native_dob'] == row['dob']
    assert len(fact['evidence_quote'].split()) <= 25
    assert hashlib.sha256(Path(fact['raw_source_file']).read_bytes()).hexdigest() == fact['source_sha256']
    assert not any(k in fact for k in ['country','lat','lon','hemisphere','dob','qid','eligibility'])
assert len(facts) == 2 and len(coverage) == 4
ledger = [json.loads(x) for x in (ROOT/'attempt_ledger.jsonl').read_text().splitlines()]
assert sum(len(x.get('queries', [])) for x in ledger) == 4
assert sum(x['kind'] == 'body_read' for x in ledger) == 8
print(json.dumps(summary, ensure_ascii=False))
