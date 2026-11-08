"""Validate and freeze NAS v3 approved-eight results. No network operations."""
import collections
import datetime
import gzip
import hashlib
import html
import json
import pathlib
import re
from html.parser import HTMLParser

BASE = pathlib.Path(__file__).resolve().parents[1]
WORKSPACE = BASE.parents[1]
RETAINED = BASE / 'retained'
BASELINE = WORKSPACE / 'uk_birthplace_checkout/studies/scientist_birthplace_completion_v2/outputs/birthplace_rows.jsonl.gz'
SHA = '2b7897d0c4e2655ecb6f10311e1bdf7b06b8eeae3f181e9bebe92cbc7f066ee0'


class VisibleText(HTMLParser):
    """Keep adjacent inline drop capitals joined as the printed word."""
    def __init__(self):
        super().__init__()
        self.parts = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ['script', 'style']:
            self.skip += 1
        elif tag in ['p', 'div', 'h1', 'h2', 'h3', 'h4', 'br', 'li']:
            self.parts.append('\n')

    def handle_endtag(self, tag):
        if tag in ['script', 'style']:
            self.skip = max(0, self.skip - 1)
        elif tag in ['p', 'div', 'h1', 'h2', 'h3', 'h4', 'li']:
            self.parts.append('\n')

    def handle_data(self, value):
        if not self.skip:
            self.parts.append(value)


def read_rows(path):
    return [json.loads(x) for x in path.read_text().splitlines() if x.strip()]


def save_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n')


def main():
    assert hashlib.sha256(BASELINE.read_bytes()).hexdigest() == SHA
    baseline = [json.loads(x) for x in gzip.open(BASELINE, 'rt')]
    lookup = {(r['cohort'], r['record_id'], r['dob']): r for r in baseline}
    facts = read_rows(RETAINED / 'source_facts.jsonl')
    holds = read_rows(RETAINED / 'held_source_candidates.jsonl')
    coverage = read_rows(RETAINED / 'coverage.jsonl')
    assert (len(facts), len(holds), len(coverage)) == (7, 1, 8)
    for row in facts + holds:
        assert row['source_grade'] == 'S2'
        assert len(row['evidence_quote'].split()) <= 25
        assert row['frozen_baseline_row'] == lookup[(row['cohort'], row['record_id'], row['native_dob'])]
        raw_path = WORKSPACE / row['raw_source_file']
        assert hashlib.sha256(raw_path.read_bytes()).hexdigest() == row['original_bytes_sha256']
        visible = VisibleText()
        visible.feed(raw_path.read_text())
        original_text = ' '.join(''.join(visible.parts).split())
        assert ' '.join(row['evidence_quote'].split()) in original_text
        assert row['source_author'] in original_text
        assert row['source_fact_adopted_into_baseline'] is False
        assert row['geography_country_or_point_assignment'] is False
    assert all(r['source_dob'] == r['native_dob'] for r in facts)
    assert holds[0]['name'] == 'S. Chandrasekhar'
    assert holds[0]['source_dob'] == '1910-10-13' and holds[0]['native_dob'] == '1910-10-19'
    assert next(r for r in facts if r['name'] == 'R. G. Herb')['birth_clause_dob_precision'] == 'year'
    for name in ['Paul J. Kramer', 'J. E. Varner']:
        assert next(r for r in facts if r['name'] == name)['birth_clause_dob_precision'] == 'none'
    ledger = read_rows(RETAINED / 'request_ledger.jsonl')
    intents = [r for r in ledger if r['event'] == 'intent']
    results = [r for r in ledger if r['event'] == 'result']
    assert len(intents) == len(results) == 16
    assert sum(r['kind'] == 'discovery_query' for r in intents) == 3
    assert sum(r['kind'] == 'approved_independently_authored_memoir_full_body' for r in intents) == 8
    assert len({r['request_id'] for r in intents}) == 16
    for i, event in enumerate(ledger):
        if event['event'] == 'result':
            assert ledger[i - 1]['event'] == 'intent'
            assert ledger[i - 1]['request_id'] == event['request_id']
    body_results = [r for r in results if r['request_id'].startswith('nas_memoirs_chapter_')]
    assert len(body_results) == 8 and all(r['http_status'] == 200 for r in body_results)
    nas = [r for r in baseline if r['cohort'] == 'NAS']
    summary = {
        'status': 'frozen_after_approved_eight_fulltexts',
        'baseline_path': str(BASELINE.relative_to(WORKSPACE)),
        'baseline_sha256_before_after': SHA,
        'baseline_all_rows': len(baseline), 'baseline_nas_rows': len(nas),
        'baseline_nas_hemisphere_counts_unchanged': dict(collections.Counter(r['hemisphere'] for r in nas)),
        'unknown_nas_rows_bulk_compared': 574,
        'initial_discovery_queries': 3, 'initial_index_navigation_requests': 5,
        'approved_memoir_chapter_full_body_requests': 8,
        'approved_memoir_chapter_http200_captures': 8,
        'all_request_attempts': 16, 'retries': 0,
        'first_request_intent_utc': intents[0]['utc'],
        'last_request_result_utc': results[-1]['utc'],
        'full_body_source_grade': 'S2',
        'birthplace_source_facts_ready_for_parent_merge': 7,
        'held_birthplace_candidates': 1,
        'hold': 'S. Chandrasekhar: source heading October 13, 1910 conflicts with frozen native October 19, 1910; birthplace claim retained as held candidate only.',
        'actual_official_collection_url': 'https://www.nasonline.org/publications/biographical-memoirs/search/',
        'actual_official_collection_access': 'Original HTML and its observed embedded search script both HTTP200; member result data were not included, and no runtime/API/data endpoint was requested.',
        'actual_official_nap_contents_url': 'https://www.nationalacademies.org/read/5859',
        'memoir_routes_observed_in_original_contents_and_approved': [r['url'] for r in body_results],
        'initial_zero_fact_checkpoint': 'initial_probe_checkpoint/',
        'no_additional_runtime_api_or_index_requests': True,
        'source_precision': 'Heading DOBs retained independently; birth-clause precision separately recorded (Herb year only, Kramer and Varner none). No native DOB upgraded or altered.',
        'identity_review': 'Full target headings, exact native DOB compatibility, source lifespans, actual bylines, and NAS election/membership context retained. Baseline has no lifespan/death fields, so no independent lifespan equality is claimed.',
        'geography_country_point_assignments': 0,
        'baseline_rows_modified': 0,
        'native_dob_calendar_accepted_dob_formal_identity_eligibility_dob_groups_qid_or_source_groups_modified': 0,
        'bonner_shared_qid_and_esau_breit_holds': 'Unchanged and unused in this batch.',
        'captures': 'Complete original HTTP chapter HTML bodies with SHA256; raw bodies remain transient, relevant literal claims and source metadata retained in source_facts/held_source_candidates/coverage.',
        'qa': 'Independent local review produced seven positive matches and one date-conflict hold; final checks validated all source quotes, raw hashes, frozen rows, counts and ledger ordering.',
        'freeze_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    save_json(RETAINED / 'summary.json', summary)
    (RETAINED / 'summary.txt').write_text(
        'NAS v3 official Memoirs source probe: seven S2 literal birthplace facts ready for parent merge, one DOB-conflict hold.\n'
        'Initial budget: three discovery queries and five observed index/navigation requests.\n'
        'Approved expansion: eight observed NAP Volume72 chapter URLs, each requested once; all HTTP200.\n'
        'Zero retries, runtime/API extensions, geography/country/point assignments, or baseline changes.\n'
        'Chandrasekhar is held: source title prints October13,1910; frozen native DOB is October19,1910.\n'
        'Initial zero-fact checkpoint preserved in initial_probe_checkpoint.\n'
    )
    policy = json.loads((RETAINED / 'policy.json').read_text())
    policy['memoir_full_text_requests_authorized'] = 8
    policy['approval_received'] = 'Parent approved exactly eight observed Volume72 chapter URLs, once each, with no runtime/API/index expansion.'
    policy['memoir_source_grade'] = 'S2'
    save_json(RETAINED / 'policy.json', policy)
    manifest = []
    for path in sorted(BASE.rglob('*')):
        if path.is_file() and path != RETAINED / 'manifest.json':
            manifest.append({'path': str(path.relative_to(WORKSPACE)), 'bytes': path.stat().st_size,
                             'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                             'raw_transient': 'raw' in path.relative_to(BASE).parts})
    save_json(RETAINED / 'manifest.json', manifest)
    print(json.dumps({'facts': len(facts), 'holds': len(holds), 'coverage': len(coverage), 'manifest_files': len(manifest), 'baseline_unchanged': True}, indent=2))


if __name__ == '__main__':
    main()
