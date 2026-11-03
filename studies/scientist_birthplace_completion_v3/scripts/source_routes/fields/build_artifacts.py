from pathlib import Path
import datetime as dt
import hashlib
import json

ROOT = Path(__file__).resolve().parent
RAW = ROOT / 'raw'
NOW = dt.datetime.now(dt.timezone.utc).isoformat()
META = json.loads((ROOT / 'baseline_and_bounds.json').read_text())

def capture(name):
    p = RAW / name
    return {'raw_source_file': str(p), 'source_sha256': hashlib.sha256(p.read_bytes()).hexdigest(),
            'source_capture_kind': 'web_tool_text_capture_json',
            'source_capture_scope': 'Persisted JSON tool response, including normalized extracted body text and tool metadata. Hash is not original HTML/PDF bytes.',
            'retrieved_utc': dt.datetime.fromtimestamp(p.stat().st_mtime, dt.timezone.utc).isoformat(),
            'retrieved_utc_basis': 'Tool-response cache write timestamp shortly after the request.',
            'visual_verification': {'attempted': False, 'note': 'Normalized body text verified; no rendered-image or original-byte claim.'}}

def write_jsonl(name, rows):
    (ROOT / name).write_text(''.join(json.dumps(r, ensure_ascii=False, sort_keys=True)+'\n' for r in rows))

immutable = {'native_dob_modified': False, 'formal_identity_modified': False, 'calendar_modified': False,
             'eligibility_modified': False, 'dob_groups_modified': False, 'qids_modified': False,
             'native_flags_modified': False}

smirnov = {
    'cohort': 'Fields_main', 'record_id': 'fields-de5a4b4e279eaf4f', 'name': 'Stanislav Smirnov',
    'native_dob': '1970-09-03', 'raw_birthplace': 'St. Petersburg, Russia',
    'raw_birthplace_precision': 'City and country exactly as stated; historical naming not normalized.',
    'source_grade': 'S1', 'source_grade_rationale': 'Original official ICM2010 prize biography archived on the International Mathematical Union domain; grade is independent of DOB tier.',
    'evidence_kind': 'explicit_born_statement',
    'source_url': 'https://www.mathunion.org/fileadmin/IMU/ICM2010/offline/www.icm2010.in/prize-winners-2010/fields-medal-stanislav-smirnov.html',
    'source_urls': ['https://www.mathunion.org/fileadmin/IMU/ICM2010/offline/www.icm2010.in/prize-winners-2010/fields-medal-stanislav-smirnov.html'],
    'source_author': 'International Congress of Mathematicians 2010 (institutional biography; no individual byline), archived by International Mathematical Union',
    'source_last_modified_text': 'August 19, 2010',
    'evidence_quote': 'Stanislav Smirnov was born in 1970 in St. Petersburg, Russia.',
    'evidence_locator': 'Brief Biodata, web-extracted L65-L66. Independent award/name context at L58-L62; last-modified statement L81.',
    'source_birth_date_text': '1970', 'source_birth_date_precision': 'year',
    'identity_review': {'status': 'matched_pending_root_qa', 'exact_full_name': True,
        'name_context': 'Exact full name in Fields Medal heading and biodata.',
        'official_fields_context': 'L60 independently states award of the 2010 Fields medal to Stanislav Smirnov.',
        'birth_date_compatibility': 'Source year 1970 agrees with native year; native month and day are not asserted by this source or upgraded.',
        'independent_of_birthplace': True, **immutable},
    'review_status': 'source_fact_pending_root_qa_then_geographic_review',
    **capture('fields_v3_body_001.webcapture.json'),
}

hugo = {
    'cohort': 'Fields_main', 'record_id': 'fields-ef72cb77368d48fe', 'name': 'Hugo Duminil-Copin',
    'native_dob': '1985-08-26', 'raw_birthplace': 'Châtenay-Malabry, France',
    'raw_birthplace_precision': 'Town and country exactly as stated in structured birth row; no Paris substitution or geographic assignment.',
    'source_grade': 'S1', 'source_grade_rationale': 'Official institutional laureate profile published by Heidelberg Laureate Forum Foundation, identified in the page footer; grade is independent of DOB tier.',
    'evidence_kind': 'structured_birth_row',
    'source_url': 'https://www.heidelberg-laureate-forum.org/laureate/hugo-duminil-copin/',
    'source_urls': ['https://www.heidelberg-laureate-forum.org/laureate/hugo-duminil-copin/',
                    'https://www.cnrs.fr/sites/default/files/press_info/2022-07/210705_CP_HDC_fr_VF.pdf'],
    'source_author': 'Heidelberg Laureate Forum Foundation (official institutional laureate profile; no individual author shown)',
    'evidence_quote': '* August 26, 1985, Châtenay-Malabry, France',
    'raw_source_birth_row': '* August 26, 1985, Châtenay-Malabry, France',
    'evidence_locator': 'Exact-name heading L72; standalone birth-row heading L74; Fields Medal 2022 L80; publisher footer L108.',
    'source_birth_date_text': 'August 26, 1985', 'source_birth_date_precision': 'day',
    'structured_birth_context_review': 'Asterisk-prefixed date/place tuple is the standalone heading immediately beneath the exact name. It is not a footnote or death row. Original wording retained without adding born.',
    'identity_review': {'status': 'matched_pending_root_qa', 'exact_full_name': True,
        'name_context': 'L72 gives Hugo Duminil-Copin immediately above the birth row.',
        'official_fields_context': 'L80 independently gives Fields Medal 2022; award citation follows at L82.',
        'birth_date_compatibility': 'Structured source date equals existing native 1985-08-26; no native DOB or precision modification.',
        'independent_of_birthplace': True,
        'additional_official_dob_corroboration': {'source_url': 'https://www.cnrs.fr/sites/default/files/press_info/2022-07/210705_CP_HDC_fr_VF.pdf',
            'source_author': 'IHES institutional press release hosted by CNRS; no individual byline',
            'evidence_quote': 'Né le 26 août 1985',
            'evidence_locator': 'PDF page 1 (P0), biographical section, web-extracted L28-L29.',
            'scope_note': 'Date compatibility only; this press release states no birthplace.', **capture('fields_v3_body_004.webcapture.json')},
        **immutable},
    'offline_context_review': 'Independent offline reviewer confirmed name/birth-row/Fields-year structure and institutional footer; root QA remains required.',
    'review_status': 'source_fact_pending_root_qa_then_geographic_review',
    **capture('fields_v3_body_003.webcapture.json'),
}

facts = [smirnov, hugo]
write_jsonl('accepted.jsonl', facts)
write_jsonl('coverage.jsonl', [{'cohort': f['cohort'], 'record_id': f['record_id'], 'name': f['name'],
    'native_dob': f['native_dob'], 'raw_birthplace': f['raw_birthplace'], 'source_grade': f['source_grade'],
    'evidence_kind': f['evidence_kind'], 'status': f['review_status']} for f in facts])

outcomes = [
    ('discovery-001', '2 discovery queries completed; no further discovery queries', 'discovery_001.webcapture.json'),
    ('body-001', 'Official IMU/ICM2010 body explicitly supports Smirnov birthplace and year; separate Fields 2010 context', 'fields_v3_body_001.webcapture.json'),
    ('body-002', 'Official CNRS journal article has Fields 2022 identity context but no birthplace', 'fields_v3_body_002.webcapture.json'),
    ('body-003', 'Official HLF laureate profile supports structured birth row and exact native DOB plus Fields 2022', 'fields_v3_body_003.webcapture.json'),
    ('body-004', 'Official CNRS-hosted IHES press release supports native exact DOB, no birthplace; final permitted body request', 'fields_v3_body_004.webcapture.json'),
]
write_jsonl('request_outcomes.jsonl', [{'attempt_id': a, 'outcome': o, 'recorded_utc': NOW, **capture(c)} for a,o,c in outcomes])
summary = {'baseline_sha256_supplied': META['baseline_sha256'], 'baseline_hash_verification': META['baseline_hash_verification'],
    'targets': 2, 'new_source_facts': 2, 'remaining_without_source_fact': 0, 'root_qa_pending': 2,
    'discovery_queries_used': 2, 'new_body_requests_used': 4, 'retries': 0,
    'prior_blocked_empty_or_timeout_urls_reread': False,
    'stop_reason': 'Both targets have source facts; bounded pass frozen at body cap.', 'frozen_utc': NOW,
    'geography_country_or_point_assignments_made': False, **immutable,
    'capture_note': 'SHA256 values identify web-tool normalized JSON captures, not original publisher HTML/PDF bytes. No visual verification attempted.',
    'review_gate': 'Root QA must independently review source/identity evidence before acceptance; geographic review follows separately.',
    'artifact_policy': 'Source facts, short quotations and metadata only outside transient raw caches; no repository/Git writes.'}
(ROOT / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\n')

targets = {r['record_id']: r for r in META['targets']}
for f in facts:
    t = targets[f['record_id']]
    assert all(f[k] == t[k] for k in ['cohort','record_id','name','native_dob'])
    assert len(f['evidence_quote'].split()) <= 25
    assert hashlib.sha256(Path(f['raw_source_file']).read_bytes()).hexdigest() == f['source_sha256']
    assert not any(k in f for k in ['country','hemisphere','lat','lon','dob','qid','eligibility'])
ledger = [json.loads(x) for x in (ROOT/'attempt_ledger.jsonl').read_text().splitlines()]
assert sum(len(x.get('queries',[])) for x in ledger) == 2
assert sum(x['kind'] == 'body_read' for x in ledger) == 4
assert len(facts) == 2
print(json.dumps(summary, ensure_ascii=False))
