#!/usr/bin/env python3
"""Offline factual extraction from two official, already downloaded CSV exports."""
import argparse
import collections
import csv
import datetime
import hashlib
import json
from pathlib import Path
import re

EXPECTED = {'physics': '89d9a17437557c5b1bce325c2b806b91f9df0cbdf5c4baa612182d2c51bdce4e',
            'chemistry': '5cbc1ddb0c28736aa46332222f919bc5227bea95902d2b9be5462c38a9edeecd'}


def parse_date(raw):
    raw = raw.strip()
    if not raw:
        return {'precision': 'missing', 'source_date_components_iso': '', 'birth_year': None}
    if re.fullmatch(r'\d{4}', raw):
        return {'precision': 'year', 'source_date_components_iso': raw, 'birth_year': int(raw)}
    if re.fullmatch(r'\d{2}\.\d{2}\.\d{4}', raw):
        day, month, year = map(int, raw.split('.'))
        # Syntactic validity only; this does not adjudicate historical calendars.
        datetime.date(year, month, day)
        return {'precision': 'day', 'source_date_components_iso': f'{year:04}-{month:02}-{day:02}', 'birth_year': year}
    return {'precision': 'unparsed', 'source_date_components_iso': '', 'birth_year': None}


def assemble(subject_rows):
    people = {}
    memberships = []
    for subject, rows in subject_rows.items():
        for row in rows:
            url = row['purl'].strip()
            if not url.startswith(('http://purl.uni-rostock.de/cpr/', 'https://purl.uni-rostock.de/cpr/')):
                raise ValueError('Unexpected or missing catalogue PURL')
            if not row['profkat.idx_profname.headline'].strip():
                raise ValueError('Missing source name')
            key = url.split('/cpr/', 1)[1]
            memberships.append({'catalogue_id': key, 'subject': subject, 'source_purl': url})
            fact = {'catalogue_id': key, 'name_raw': row['profkat.idx_profname.headline'],
                    'birthdate_raw': row['profkat.birthdate'], 'birthplace_raw': row['profkat.birthplace'],
                    'role_raw': row['profkat.last_professorship'], 'faculty_raw': row['profkat.last_faculty'],
                    'period_raw': row['profkat.period'], 'gnd_raw': row['profkat.gnd'], 'source_purl': url}
            if key in people:
                previous = {k: v for k, v in people[key].items() if k != 'subjects'}
                if previous != fact:
                    raise ValueError(f'Conflicting duplicate PURL {key}; do not select a winner')
                people[key]['subjects'].append(subject)
            else:
                people[key] = dict(fact, subjects=[subject])
    out = []
    for key in sorted(people):
        row = people[key]
        row['subjects'] = '|'.join(sorted(set(row['subjects'])))
        row.update(parse_date(row['birthdate_raw']))
        y = row['birth_year']
        row['birth_year_window_1835_1985'] = 'unknown' if y is None else ('inside' if 1835 <= y <= 1985 else 'outside')
        row['full_date_window_candidate'] = row['precision'] == 'day' and row['birth_year_window_1835_1985'] == 'inside'
        row['calendar'] = 'not_stated'
        row['honorary_title_indicator'] = 'honorar' in row['role_raw'].casefold() or 'ehren' in row['role_raw'].casefold()
        row['professor_title_indicator'] = 'professor' in row['role_raw'].casefold()
        row['role_review_status'] = 'source_catalogue_candidate_only'
        row['individually_dob_verified'] = False
        row['academy_nobel_overlap_checked'] = False
        out.append(row)
    counts = dict(collections.Counter(r['precision'] for r in out))
    summary = {'institution': 'University of Rostock', 'country': 'Germany',
               'membership_rows': len(memberships), 'distinct_catalogue_purls': len(out),
               'shared_subject_purls': sum('|' in r['subjects'] for r in out),
               'precision_counts': counts,
               'full_date_window_candidates': sum(r['full_date_window_candidate'] for r in out),
               'honorary_title_indicators': sum(r['honorary_title_indicator'] for r in out),
               'missing_role_count': sum(not r['role_raw'] for r in out),
               'individual_dob_requests': 0, 'calendar_conversion': False,
               'analysis_cohort_frozen': False, 'bazi_variables_computed': 0,
               'population_note': 'Historical/current catalogue candidates; ranks unrestricted, honorary indicators retained. Not an adjudicated professor-only control cohort; no higher-tier overlap exclusion.'}
    return out, memberships, summary


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--physics', required=True, type=Path)
    p.add_argument('--chemistry', required=True, type=Path)
    p.add_argument('--output-dir', required=True, type=Path)
    a = p.parse_args()
    if a.output_dir.exists():
        p.error('Output directory must be fresh')
    by_subject = {}
    provenance = []
    for name in EXPECTED:
        path = getattr(a, name)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != EXPECTED[name]:
            p.error(f'{name} source hash differs from pinned downloaded export')
        with path.open(encoding='utf-8-sig', newline='') as f:
            by_subject[name] = list(csv.DictReader(f))
        provenance.append({'subject': name, 'sha256': digest, 'bytes': path.stat().st_size, 'rows': len(by_subject[name])})
    rows, memberships, summary = assemble(by_subject)
    a.output_dir.mkdir(parents=True)
    for name, values in [('catalogue_candidates', rows), ('subject_memberships', memberships),
                         ('full_date_window_candidates', [r for r in rows if r['full_date_window_candidate']])]:
        (a.output_dir / (name + '.json')).write_text(json.dumps(values, ensure_ascii=False, indent=2) + '\n')
        with (a.output_dir / (name + '.csv')).open('w', encoding='utf-8-sig', newline='') as f:
            w = csv.DictWriter(f, fieldnames=list(values[0]) if values else list(rows[0]))
            w.writeheader()
            w.writerows(values)
    (a.output_dir / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
    (a.output_dir / 'input_checks.json').write_text(json.dumps(provenance, indent=2) + '\n')
    manifest = {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(a.output_dir.iterdir())}
    (a.output_dir / 'MANIFEST.json').write_text(json.dumps({'algorithm': 'sha256', 'files': manifest}, indent=2) + '\n')
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
