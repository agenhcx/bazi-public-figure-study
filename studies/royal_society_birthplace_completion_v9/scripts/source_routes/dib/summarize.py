#!/usr/bin/env python3
"""Reproduce the bounded canonical-name DIB screen offline; no network."""
import csv
import gzip
import hashlib
import json
from pathlib import Path
import re
import unicodedata

HERE = Path(__file__).resolve().parent
BASELINE = HERE.parents[1] / 'uk_birthplace_checkout/studies/royal_society_birthplace_completion_v8/outputs/uk_birthplace_rows.jsonl.gz'
EXPECTED = 'b13ba1336b5912e58cfc38aa79aa668772ece189623f32a23625e67eaabd4c92'
HONORIFICS = {'sir', 'dame', 'dr', 'doctor', 'prof', 'professor', 'lord', 'lady', 'prince'}

def normalize(value):
    ascii_text = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode().lower()
    return ' '.join(word for word in re.sub(r'[^a-z0-9 ]', ' ', ascii_text).split() if word not in HONORIFICS)

def natural_order(value):
    surname, given = value.split(',', 1) if ',' in value else ('', value)
    return normalize(given + ' ' + surname)

def strip_lifespan(value):
    return re.sub(r'\([^)]*\d[^)]*\)', '', value).strip()

def canonical_name(row):
    """Official catalogue is surname; [honorific;] givens (life); [description]."""
    authorised = row.get('source_authorised_full_name', '').strip()
    if authorised:
        parts = [part.strip() for part in authorised.split(';')]
        if re.search(r'\([^)]*\d', parts[0]):
            return strip_lifespan(parts[0]), 'source_authorised_full_name: named ruler/mononym segment'
        surname = parts[0]
        givens = []
        for part in parts[1:]:
            clean = strip_lifespan(part)
            if normalize(clean):
                givens.append(clean)
            if re.search(r'\([^)]*\d', part):
                break
        return ' '.join(givens + [surname]), 'source_authorised_full_name: surname plus given segments before lifespan'
    review = row.get('geography_lookup_identity_review') or {}
    return review.get('native_name') or row['name'], 'current native full name'

def directory_variants(heading):
    """Candidate routing variants retain or omit observed parenthetical given names."""
    variants = {natural_order(heading)}
    groups = re.findall(r'\(([^()]*)\)', heading)
    variants.add(natural_order(re.sub(r'\([^()]*\)', '', heading)))
    if ',' in heading:
        surname = heading.split(',', 1)[0]
        for group in groups:
            if not re.search(r'\d', group):
                variants.add(normalize(group + ' ' + surname))
    return {value for value in variants if value}

def main():
    assert hashlib.sha256(BASELINE.read_bytes()).hexdigest() == EXPECTED
    rows = [json.loads(line) for line in gzip.open(BASELINE, 'rt')]
    unknown = [row for row in rows if row['hemisphere'] == 'unknown']
    window = [row for row in unknown if '1835-01-01' <= row['dob'] <= '1985-12-31']
    source = json.loads((HERE / 'observed_directory_headings.json').read_text())
    names = source['headings']
    unknown_by_name = {}
    canonical_rows = []
    for row in unknown:
        full_name, provenance = canonical_name(row)
        canonical = normalize(full_name)
        assert canonical
        unknown_by_name.setdefault(canonical, []).append(row)
        canonical_rows.append({'record_id': row['record_id'], 'dob': row['dob'],
                               'in_1835_1985_window': '1835-01-01' <= row['dob'] <= '1985-12-31',
                               'baseline_display_name': row['name'], 'source_authorised_full_name': row.get('source_authorised_full_name', ''),
                               'canonical_full_name': full_name, 'normalized_canonical_full_name': canonical,
                               'provenance': provenance})
    with (HERE / 'canonical_name_screen.csv').open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(canonical_rows[0]))
        writer.writeheader()
        writer.writerows(canonical_rows)
    matches = {}
    canonical_matches = {}
    with (HERE / 'directory_screen.csv').open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['directory_url', 'heading', 'normalized_full_name', 'observed_name_variants', 'canonical_exact_match_record_ids', 'any_observed_variant_match_record_ids'])
        writer.writeheader()
        for heading in names:
            canonical = natural_order(heading)
            exact = unknown_by_name.get(canonical, [])
            variants = directory_variants(heading)
            candidate_rows = {row['record_id']: row for variant in variants for row in unknown_by_name.get(variant, [])}
            matches.update(candidate_rows)
            canonical_matches.update({row['record_id']: row for row in exact})
            writer.writerow({'directory_url': 'https://www.dib.ie/biographies/a', 'heading': heading,
                             'normalized_full_name': canonical, 'observed_name_variants': '|'.join(sorted(variants)),
                             'canonical_exact_match_record_ids': '|'.join(r['record_id'] for r in exact),
                             'any_observed_variant_match_record_ids': '|'.join(sorted(candidate_rows))})
    (HERE / 'candidate_matches.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in matches.values()))
    (HERE / 'projection.jsonl').write_text('')
    summary = {
        'route': 'Dictionary of Irish Biography, Royal Irish Academy',
        'status': 'frozen_zero',
        'baseline_sha256': EXPECTED,
        'baseline_rows': len(rows),
        'baseline_unknown': len(unknown),
        'window_unknown_1835_1985': len(window),
        'web_discovery_queries': 1,
        'read_only_discovery_requests': 5,
        'accepted': 0,
        'candidate_article_requests': 0,
        'canonical_name_rows': len(canonical_rows),
        'catalogue_authorised_full_name_rows': sum(bool(row.get('source_authorised_full_name')) for row in unknown),
        'current_native_full_name_rows': sum(not bool(row.get('source_authorised_full_name')) for row in unknown),
        'canonical_exact_unknown_name_matches': len(canonical_matches),
        'canonical_exact_window_name_matches': sum('1835-01-01' <= row['dob'] <= '1985-12-31' for row in canonical_matches.values()),
        'observed_name_variant_candidate_matches': len(matches),
        'observed_name_variant_window_candidate_matches': sum('1835-01-01' <= row['dob'] <= '1985-12-31' for row in matches.values()),
        'screened_directory_records': len(names),
        'actual_screen_scope': 'Only the 25 parsed headings returned by the official A directory first page; Abbadie through Adair. Compared against 647 canonical full names reconstructed from 644 official surname/given catalogue strings and 3 current native full names, including all 213 window rows. Canonical exact and observed parenthetical given-name variant screens each returned zero candidates.',
        'matching_method': 'Official semicolon surname/givens reordered into natural order; lifespan and trailing titles/descriptions excluded; accents, punctuation and honorifics normalized. Directory comma surname/givens reordered identically; optional observed parenthetical given-name variants also screened. Baseline display name is not used for past-fellow full-name matching. Existing QID labels/aliases are not used.',
        'unsearched_scope': 'Remaining letters, subsequent alphabetic pages, APIs, sitemaps, subject articles, additional unobserved name variants.',
        'offline_QA_correction': 'Earlier screen used baseline name, which omits surnames for many past fellows; superseded by this canonical full-name screen without new network requests.',
        'blocked_cause': 'Direct original-byte reads of official home and /biographies/all returned HTTP 307 errors. Web /biographies/all returned 403. Parsed home and /biographies/a were readable, but cannot establish original article bytes SHA. No retry, authentication, endpoint guessing, or person-specific search performed.',
        'source_status': 'Official public alphabetic directory exists and parsed first page is readable; complete bulk accessibility not established.',
        'immutable_baseline_preserved': True,
        'geography_assigned': False,
        'copyright_note': 'Discovery response caches are transient source material; no biography article text accepted or projected.'
    }
    (HERE / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    coverage = {
        'route_status': 'frozen_zero', 'unit': 'directory headings',
        'screened': {'official_directory_url': source['source_url'],
                     'returned_heading_count': len(names), 'range_first': names[0], 'range_last': names[-1],
                     'matching_method': summary['matching_method'],
                     'baseline_canonical_full_name_rows_compared': len(unknown),
                     'catalogue_authorised_full_name_rows': summary['catalogue_authorised_full_name_rows'],
                     'current_native_full_name_rows': summary['current_native_full_name_rows'],
                     'in_window_canonical_full_name_rows_compared': len(window),
                     'canonical_exact_matches': len(canonical_matches),
                     'observed_parenthetical_name_variant_candidates': len(matches)},
        'article_bodies_read': 0, 'accepted_evidence': 0,
        'unsearched': ['24 remaining letter links', 'any subsequent alphabetic pages',
                       'additional unobserved name variants', 'individual subject articles', 'API and sitemap discovery'],
        'negative_evidence_limit': 'No canonical or observed-parenthetical-variant full-name match in this small returned directory slice; this does not establish absence from DIB.',
        'offline_QA_correction': summary['offline_QA_correction']
    }
    (HERE / 'coverage.json').write_text(json.dumps(coverage, indent=2) + '\n')
    ledger = [json.loads(line) for line in (HERE / 'request_ledger.jsonl').read_text().splitlines()]
    queries = [json.loads(line) for line in (HERE / 'query_ledger.jsonl').read_text().splitlines()]
    assert len(canonical_rows) == 647 and len(window) == 213 and len(names) == 25
    assert len({row['record_id'] for row in canonical_rows}) == 647
    assert len(matches) == 0 and len(canonical_matches) == 0
    verification = {
        'passed': True, 'baseline_sha256': EXPECTED, 'baseline_sha_matches_expected': True,
        'baseline_rows': len(rows), 'baseline_unknown': len(unknown),
        'projection_records': 0, 'directory_records': len(names),
        'canonical_full_name_rows': len(canonical_rows), 'canonical_window_full_name_rows': len(window),
        'past_catalogue_authorised_full_name_rows': summary['catalogue_authorised_full_name_rows'],
        'current_native_full_name_rows': summary['current_native_full_name_rows'],
        'past_given_only_display_name_not_used': True,
        'existing_QID_labels_and_aliases_not_used': True,
        'canonical_exact_unknown_name_matches': len(canonical_matches),
        'canonical_exact_window_name_matches': summary['canonical_exact_window_name_matches'],
        'observed_parenthetical_name_variant_candidate_matches': len(matches),
        'queries': len(queries), 'discovery_requests': len(ledger),
        'discovery_budget_respected': len(queries) <= 4 and len(ledger) <= 5,
        'new_requests_during_offline_QA_correction': 0,
        'original_biography_bytes_fetched': 0, 'original_biography_sha256': None,
        'web_tool_text_projection_sha256': {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                                            for path in (HERE / 'transient_source_cache').glob('*.json')},
        'source_hash_semantics': 'The web_tool_text_projection_sha256 values hash serialized parsed tool responses, not original HTTP page bytes. Neither HTTP 307 error nor web 403 response is biography evidence. No source SHA is assigned to an accepted biography.',
        'baseline_mutations': 0, 'geography_assignments': 0,
        'formal_identity_or_DOB_or_calendar_or_eligibility_or_tier_or_QID_mutations': 0,
        'offline_QA_correction': summary['offline_QA_correction']
    }
    (HERE / 'verification.json').write_text(json.dumps(verification, indent=2) + '\n')
    print(json.dumps(summary, indent=2))

if __name__ == '__main__':
    main()
