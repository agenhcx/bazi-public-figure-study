"""Freeze a zero-yield bounded NAS pilot from already saved web projections.

This code does no network work and never alters the baseline or its rows.
"""
import collections
import datetime
import gzip
import hashlib
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
RETAINED = ROOT / 'retained'
BASELINE = ROOT.parents[1] / 'uk_birthplace_checkout/studies/academy_birthplace_screen_v1/outputs/birthplace_rows.jsonl.gz'
EXPECTED_SHA = '2ad00462255629a603bc4a95aa64158141b5a9b105359baece528a163aa93d92'


def write_json(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + '\n')


def main():
    assert hashlib.sha256(BASELINE.read_bytes()).hexdigest() == EXPECTED_SHA
    baseline = [json.loads(x) for x in gzip.open(BASELINE, 'rt')]
    nas = [r for r in baseline if r['cohort'] == 'NAS']
    selected = [json.loads(x) for x in (RETAINED / 'selection.jsonl').read_text().splitlines()]
    expected = sorted([
        r for r in nas
        if r.get('hemisphere') == 'unknown'
        and '1835-01-01' <= r['dob'] <= '1985-12-31'
        and r['record_id'].startswith('https://www.nasonline.org/directory-entry/')
    ], key=lambda r: (r['dob'], r['name'], r['record_id']))[:6]
    assert [r['frozen_baseline_row'] for r in selected] == expected
    ledger = [json.loads(x) for x in (RETAINED / 'request_ledger.jsonl').read_text().splitlines()]
    intents = [x for x in ledger if x['event'] == 'intent']
    results = {x['request_id']: x for x in ledger if x['event'] == 'result'}
    assert len(intents) == len(results) == 6
    assert len({x['url'] for x in intents}) == 6
    coverage = []
    for number, row in enumerate(selected, 1):
        request_id = f'nas_profile_{number:02d}'
        request = results[request_id]
        path = ROOT.parents[1] / request['raw_source_file']
        assert hashlib.sha256(path.read_bytes()).hexdigest() == request['web_projection_sha256']
        projection = json.loads(path.read_text())
        text = '\n'.join(c['text'] for c in projection['content'] if c['type'] == 'text')
        error = 'Failed to fetch' in text or text.startswith('Internal Error')
        numbered = {int(n): body for n, body in re.findall(r'^L(\d+): ?(.*)$', text, re.M)}
        explicit_born = [(n, body) for n, body in numbered.items() if re.search(r'\bborn\b|\bbirthplace\b|\bbirth place\b', body, re.I)]
        assert not explicit_born
        if not error:
            title = text.split(' – NAS', 1)[0]
            assert title == row['name']
            date_lines = [(n, body) for n, body in numbered.items() if re.search(r'\w+ \d+, \d{4} - ', body)]
            assert len(date_lines) == 1
            n, lifespan = date_lines[0]
            source_dob = datetime.datetime.strptime(lifespan.split(' - ')[0], '%B %d, %Y').date().isoformat()
            assert source_dob == row['native_dob']
            memoir_label = next(n for n, body in numbered.items() if body == 'Biographical Memoir Available')
            memoir_available = next(body for n, body in numbered.items() if n > memoir_label and body)
            assert memoir_available == 'No'
            election_label = next(n for n, body in numbered.items() if body == 'Election Year')
            election_year = next(body for n, body in numbered.items() if n > election_label and body)
            assert re.fullmatch(r'\d{4}', election_year)
            identity = {'review_status': 'profile_title_and_native_day_dob_match', 'profile_display_name': title,
                        'profile_lifespan': lifespan, 'profile_election_year': election_year,
                        'formal_identity_modified': False, 'qid_used_or_modified': False}
            locator = f'Birth / Deceased Date L{n}; memoir availability L{memoir_label}; Election Year L{election_label}'
            status = 'accessible_no_explicit_target_birthplace_no_observed_memoir_link'
            scope = 'all lines returned by web tool for official profile; original response bytes unavailable'
        else:
            identity = {'review_status': 'not_reviewable_fetch_timeout', 'formal_identity_modified': False,
                        'qid_used_or_modified': False}
            lifespan = None
            election_year = None
            memoir_available = None
            source_dob = None
            locator = 'web tool fetch error projection'
            status = 'fetch_timeout_no_retry'
            scope = 'web tool error projection only; no profile body retrieved'
        coverage.append({
            'cohort': 'NAS', 'record_id': row['record_id'], 'name': row['name'],
            'native_dob': row['native_dob'], 'native_dob_status': row['native_dob_status'],
            'profile_lifespan': lifespan, 'profile_election_year': election_year,
            'source_dob': source_dob, 'source_dob_precision': 'day' if source_dob else None,
            'source_dob_used_to_modify_native': False, 'source_author': 'National Academy of Sciences',
            'source_url': row['record_id'], 'source_urls': [row['record_id']],
            'source_grade_if_birthplace_had_been_explicit': 'S1_official_profile',
            'status': status, 'raw_birthplace': None, 'evidence_quote': None,
            'explicit_target_born_phrase_count': len(explicit_born), 'biographical_memoir_available': memoir_available,
            'observed_person_specific_memoir_links': [], 'memoir_requests': 0,
            'locator': locator, 'request_id': request_id,
            'capture_kind': 'web_tool_error_projection' if error else 'web_tool_text_projection',
            'capture_scope': scope, 'original_bytes_sha256': None,
            'web_projection_sha256': request['web_projection_sha256'],
            'retrieved_utc': request['retrieved_utc'], 'raw_source_file': request['raw_source_file'],
            'identity_review': identity,
        })
    (RETAINED / 'source_facts.jsonl').write_text('')
    (RETAINED / 'coverage.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False, sort_keys=True) + '\n' for r in coverage))
    correction = {'event': 'classification_correction', 'request_id': 'nas_profile_04',
                  'reason': 'web tool returned isError=false but text states Internal Error and (400) Timeout fetching',
                  'corrected_transport_status': 'fetch_timeout_no_retry',
                  'corrected_capture_kind': 'web_tool_error_projection',
                  'corrected_capture_scope': 'error projection only; no profile body retrieved',
                  'retrieved_utc': datetime.datetime.now(datetime.timezone.utc).isoformat()}
    if not any(x['event'] == 'classification_correction' for x in ledger):
        with (RETAINED / 'request_ledger.jsonl').open('a') as f:
            f.write(json.dumps(correction, sort_keys=True) + '\n')
    summary = {
        'pilot_status': 'frozen_zero_yield', 'baseline_sha256_before_and_after': EXPECTED_SHA,
        'nas_native_day_rows': len(nas),
        'baseline_hemisphere_counts': dict(collections.Counter(r['hemisphere'] for r in nas)),
        'native_day_rows_in_observed_1835_1985_window': sum('1835-01-01' <= r['dob'] <= '1985-12-31' for r in nas),
        'selected': 6, 'profile_requests': 6, 'accessible_profile_projections': 5,
        'profile_timeouts': 1, 'retries': 0, 'memoir_body_reads': 0,
        'all_requested_body_reads': 6, 'successful_profile_body_projections': 5,
        'discovery_queries': 0, 'explicit_target_birthplace_facts': 0,
        'observed_person_specific_memoir_links': 0,
        'interpretation': 'Five frozen official directory routes returned profile projections, but provided no explicit birthplace or person-specific memoir link. Edward C. Franklin profile request timed out. Route openness is partial; this bounded route offers zero birthplace yield.',
        'limitations': 'Web projection captures only: no original HTTP bytes or live HTTP status were exposed; crawl ages ranged from five days to 1.1 years. No invented routes or other-domain hops were used.',
        'native_dob_accepted_gregorian_formal_identity_eligibility_dobtier_qid_changes': 0,
        'geography_country_point_assignments': 0, 'baseline_rows_modified': 0,
        'freeze_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    write_json(RETAINED / 'summary.json', summary)
    (RETAINED / 'summary.txt').write_text(
        'NAS six-row official-route pilot frozen with zero new birthplace facts.\n'
        'Five profile projections accessible; Edward C. Franklin timed out once, without retry.\n'
        'All five accessible profiles match native DOB and supply election/lifespan context.\n'
        'All five say Biographical Memoir Available: No; zero observed person-specific memoir links.\n'
        'Six sequential profile requests; six durable preceding intent records; zero discovery queries; zero memoir reads.\n'
        'No geography, identities, QIDs, DOBs, tiers, calendars or eligibility changed.\n'
        'Only web projections retained; projection SHA256 values do not claim original HTTP bytes.\n'
    )
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
