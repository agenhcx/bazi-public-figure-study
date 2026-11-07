#!/usr/bin/env python3
"""Read only the Royal Society catalogue Place of birth field for a frozen roster."""
from __future__ import annotations
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import hashlib
from html.parser import HTMLParser
import html
import json
from pathlib import Path
import re
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

UA = 'AcademyBirthplaceScreen/2.0 (public research; github.com/agenhcx/bazi-public-figure-study)'

def now(): return datetime.now(timezone.utc).isoformat()
def digest(data): return hashlib.sha256(data).hexdigest()
def normalized(text): return re.sub(r'\s+', ' ', html.unescape(text)).strip()

class CatalogueFields(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tr_depth = 0
        self.row_id = ''
        self.fields = []
        self.cells = []
        self.in_cell = False
        self.cell_class = ''
        self.buffer = []
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'tr':
            self.tr_depth += 1
            if self.tr_depth == 1:
                self.row_id = normalized(attrs.get('id', ''))
                self.cells = []
        if tag == 'td' and self.tr_depth == 1:
            self.in_cell = True
            self.cell_class = attrs.get('class', '')
            self.buffer = []
        elif self.in_cell and tag in {'br', 'p', 'div', 'li'}:
            self.buffer.append(' ')
    def handle_data(self, text):
        if self.in_cell:
            self.buffer.append(text)
    def handle_endtag(self, tag):
        if tag == 'td' and self.in_cell:
            self.cells.append((self.cell_class, normalized(''.join(self.buffer))))
            self.in_cell = False
        if tag == 'tr' and self.tr_depth:
            if self.tr_depth == 1:
                titles = [v for cls, v in self.cells if 'tabletitle' in cls.split()]
                values = [v for cls, v in self.cells if 'tablevalue' in cls.split()]
                if len(titles) == 1 and len(values) == 1:
                    self.fields.append({'row_id': self.row_id, 'label': titles[0], 'value': values[0]})
            self.tr_depth -= 1

def parse(raw):
    parser = CatalogueFields()
    parser.feed(raw.decode('utf-8', errors='replace'))
    names = [r['value'] for r in parser.fields if r['label'].casefold() == 'authorised form of name']
    births = [r for r in parser.fields if r['label'].casefold() == 'place of birth']
    if not names:
        return {'parse_status': 'expected_person_record_fields_absent', 'raw_placeofbirth': '',
                'authorised_form_of_name': '', 'birthplace_field_present': False,
                'birthplace_field_locator': '', 'birthplace_field_count': len(births)}
    if len(births) > 1:
        return {'parse_status': 'multiple_birthplace_fields_hold', 'raw_placeofbirth': '',
                'authorised_form_of_name': names[0], 'birthplace_field_present': True,
                'birthplace_field_locator': '', 'birthplace_field_count': len(births),
                'birthplace_field_alternatives': births}
    if births:
        r = births[0]
        return {'parse_status': 'explicit_birthplace_field' if r['value'] else 'empty_birthplace_field',
                'raw_placeofbirth': r['value'], 'authorised_form_of_name': names[0],
                'birthplace_field_present': True, 'birthplace_field_count': 1,
                'birthplace_field_locator': 'tr#' + r['row_id'] + ' > td.tablevalue; exact label=Place of birth'}
    return {'parse_status': 'no_birthplace_field', 'raw_placeofbirth': '',
            'authorised_form_of_name': names[0], 'birthplace_field_present': False,
            'birthplace_field_locator': '', 'birthplace_field_count': 0}

class RateLimiter:
    def __init__(self, rps):
        self.interval = 1.0 / rps
        self.next_time = 0.0
        self.not_before = 0.0
        self.lock = threading.Lock()
    def wait(self):
        while True:
            with self.lock:
                target = max(self.next_time, self.not_before)
                delay = target - time.monotonic()
                if delay <= 0:
                    self.next_time = time.monotonic() + self.interval
                    return
            time.sleep(min(delay, 1.0))
    def pause(self, seconds):
        with self.lock:
            self.not_before = max(self.not_before, time.monotonic() + seconds)

def write_json(path, value):
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True) + '\n')
    temp.replace(path)

def collect(row, out, limiter, timeout, retries):
    rid = row['record_id']
    assert re.fullmatch(r'NA\d+', rid), rid
    raw_file = out / 'raw_html' / (rid + '.html')
    meta_file = out / 'response_metadata' / (rid + '.json')
    record = {'cohort': 'UK_Royal_Society', 'record_id': row['cohort_key'],
              'archive_id': rid, 'name': row['display_name'], 'existing_dob': row['dob_exact_iso'],
              'source_url': row['source_url'], 'http_status': '', 'final_url': '',
              'retrieved_utc': '', 'source_sha256': '', 'source_bytes': 0,
              'raw_placeofbirth': '', 'parse_status': 'not_attempted', 'error': '',
              'birthplace_source_grade': 'S1', 'DOB_or_acceptance_modified': False}
    raw = None
    if raw_file.exists() and meta_file.exists():
        try:
            meta = json.loads(meta_file.read_text())
            candidate = raw_file.read_bytes()
            if meta.get('source_url') == row['source_url'] and digest(candidate) == meta.get('source_sha256'):
                raw = candidate
                record.update({k: meta[k] for k in ['http_status', 'final_url', 'retrieved_utc', 'source_sha256', 'source_bytes']})
                record['cache_reused'] = True
        except (OSError, ValueError, KeyError):
            pass
    if raw is None:
        for attempt in range(retries + 1):
            limiter.wait()
            try:
                request = Request(row['source_url'], headers={'User-Agent': UA, 'Accept': 'text/html,application/xhtml+xml'})
                with urlopen(request, timeout=timeout) as response:
                    raw = response.read()
                    record.update(http_status=response.status, final_url=response.geturl(), retrieved_utc=now(),
                                  source_sha256=digest(raw), source_bytes=len(raw))
                raw_file.write_bytes(raw)
                write_json(meta_file, {k: record[k] for k in ['source_url', 'http_status', 'final_url', 'retrieved_utc', 'source_sha256', 'source_bytes']})
                record['cache_reused'] = False
                break
            except HTTPError as exc:
                record['http_status'] = exc.code
                record['error'] = 'HTTPError:' + str(exc.code)
                if exc.code not in {408, 429, 500, 502, 503, 504}:
                    break
                retry_after = exc.headers.get('Retry-After') if exc.headers else None
                if retry_after:
                    try:
                        delay = float(retry_after)
                    except ValueError:
                        try: delay = max(0, parsedate_to_datetime(retry_after).timestamp() - time.time())
                        except (ValueError, TypeError, OverflowError): delay = 5
                    if delay > 60:
                        record['error'] += ':retry_after_deferred'
                        break
                    limiter.pause(delay)
            except (URLError, TimeoutError, OSError) as exc:
                record['error'] = type(exc).__name__ + ':' + str(exc)[:220]
            if attempt < retries:
                time.sleep(min(2 ** (attempt + 1), 12))
    if raw is not None:
        record['error'] = ''
        record.update(parse(raw))
        record['raw_source_file'] = str(raw_file.relative_to(out))
        if record['parse_status'] == 'expected_person_record_fields_absent':
            record['error'] = 'HTTP_200_without_expected_person_catalogue_record'
    else:
        record['parse_status'] = 'network_failure'
    return record

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--baseline', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--workers', type=int, default=8)
    ap.add_argument('--rps', '--rate', dest='rps', type=float, default=3)
    ap.add_argument('--timeout', type=float, default=25)
    ap.add_argument('--retries', type=int, default=2)
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--priority-csv', type=Path, help='Prior screen: unknown/conflicts, then south, then other records')
    args = ap.parse_args()
    if not 1 <= args.workers <= 8 or not 0 < args.rps <= 3:
        raise SystemExit('Respect worker <= 8 and shared rps <= 3')
    with args.baseline.open(encoding='utf-8-sig', newline='') as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 4884 and len({r['cohort_key'] for r in rows}) == 4884
    for row in rows:
        assert row['dob_precision'] == 'exact_day' and row['dob_exact_iso']
    if args.priority_csv:
        with args.priority_csv.open(encoding='utf-8-sig', newline='') as stream:
            prior = {r['record_id']: r for r in csv.DictReader(stream)}
        def priority(row):
            existing = prior.get(row['cohort_key'], {})
            sign = existing.get('hemisphere', 'unknown')
            conflict = str(existing.get('geographic_conflict_pending_review', '')).lower() in {'1', 'true'}
            return (0 if sign == 'unknown' or conflict else 1 if sign == 'south' else 2, row['cohort_key'])
        rows.sort(key=priority)
    if args.limit:
        rows = rows[:args.limit]
    out = args.output
    (out / 'raw_html').mkdir(parents=True, exist_ok=True)
    (out / 'response_metadata').mkdir(exist_ok=True)
    limiter = RateLimiter(args.rps)
    started = now()
    results = []
    with (out / 'official_birthplace_progress.jsonl').open('w') as progress:
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = [pool.submit(collect, row, out, limiter, args.timeout, args.retries) for row in rows]
            for future in as_completed(futures):
                result = future.result()
                results.append(result)
                progress.write(json.dumps(result, ensure_ascii=False, sort_keys=True) + '\n')
                progress.flush()
                n = len(results)
                if n % 50 == 0 or n == len(rows):
                    checkpoint = {'started_utc': started, 'updated_utc': now(), 'completed': n, 'total': len(rows),
                                  'with_birthplace': sum(bool(r['raw_placeofbirth']) for r in results),
                                  'errors': sum(bool(r['error']) for r in results),
                                  'parse_status_counts': dict(Counter(r['parse_status'] for r in results))}
                    write_json(out / 'checkpoint.json', checkpoint)
                    if n % 200 == 0 or n == len(rows):
                        print(json.dumps(checkpoint), flush=True)
    results.sort(key=lambda r: r['record_id'])
    assert len(results) == len(rows) and len({r['record_id'] for r in results}) == len(rows)
    output = out / 'official_birthplace_rows.jsonl'
    output.write_text(''.join(json.dumps(r, ensure_ascii=False, sort_keys=True) + '\n' for r in results))
    summary = {'schema': 'royal_society_official_birthplace_fields_v2', 'started_utc': started, 'completed_utc': now(),
               'baseline_csv_sha256': digest(args.baseline.read_bytes()), 'script_sha256': digest(Path(__file__).read_bytes()),
               'output_sha256': digest(output.read_bytes()), 'rows': len(results),
               'birthplace_nonempty': sum(bool(r['raw_placeofbirth']) for r in results),
               'network_failure': sum(r['parse_status'] == 'network_failure' for r in results),
               'errors': sum(bool(r['error']) for r in results),
               'parse_status_counts': dict(Counter(r['parse_status'] for r in results)),
               'workers': args.workers, 'shared_requests_per_second': args.rps,
               'DOB_or_acceptance_modified': False,
               'rule': 'Only table row with exact label Place of birth; no nationality, death, career or origin inference.'}
    write_json(out / 'summary.json', summary)
    print(json.dumps(summary, ensure_ascii=False), flush=True)

if __name__ == '__main__':
    main()
