#!/usr/bin/env python3
"""Incremental lookup-only P19 -> P625 supplement. Frozen DOB/identity values stay unchanged.

Person network requests project only P19. Existing v1 place evidence is a labelled,
provenanced cached projection, never presented as a newly retrieved raw API entity.
New HTTP entities and P19 projections are normalized per QID so seed growth only
fetches new QIDs. No geography inference from citizenship, country or institutions.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
from copy import deepcopy
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
from datetime import datetime, timezone

DEFAULT_REPO = Path('/workspace/scratch/7e8aa4e0d4af/uk_birthplace_checkout')
DEFAULT_WORK = Path('/workspace/scratch/7e8aa4e0d4af/uk_birthplace_v2_workers/strict_places')
DEFAULT_SEEDS = DEFAULT_WORK.parent / 'strict_links/strict_lookup_seeds.jsonl'
QID = re.compile(r'Q[1-9][0-9]*\Z')


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def dumps(v):
    return (json.dumps(v, ensure_ascii=False, sort_keys=True, allow_nan=False) + '\n').encode()


def sha(v):
    return hashlib.sha256(v).hexdigest()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_bytes(dumps(value))
    tmp.replace(path)


def import_core(repo):
    script = repo / 'studies/academy_birthplace_screen_v1/scripts/academy_birthplace_wikidata_v1_sparql_people.py'
    spec = importlib.util.spec_from_file_location('frozen_v1_birthplace_core', script)
    core = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(core)
    return core, script


def ref_list(count):
    # Count-only placeholders are internal to the reconstructed projection. They
    # are never returned as source references; output restores the prior fields.
    return [{} for _ in range(count or 0)]


def project_prior_entity(qid, pe):
    claims = {'P625': [], 'P31': [], 'P17': []}
    for c in pe.get('coordinates', []):
        claims['P625'].append({'id': c.get('claim_id'), 'rank': c.get('rank'),
            'references': ref_list(c.get('reference_count')),
            'mainsnak': {'property': 'P625', 'snaktype': 'value', 'datavalue': {'value': {
                'latitude': c.get('lat'), 'longitude': c.get('lon'),
                'precision': c.get('precision'), 'globe': c.get('globe')}}}})
    for prop, key in [('P31', 'instance_of_claims'), ('P17', 'country_claims_descriptive_only')]:
        for c in pe.get(key, []):
            claims[prop].append({'id': c.get('claim_id'), 'rank': c.get('rank'),
                'references': ref_list(c.get('reference_count')),
                'mainsnak': {'property': prop, 'snaktype': 'value',
                    'datavalue': {'value': {'id': c['qid']}}}})
    return {'id': qid, 'claims': claims, 'labels': {'en': {'language': 'en', 'value': pe.get('label', '')}}}


def prior_signature(pe):
    return dumps({k: pe.get(k) for k in ['label', 'coordinates', 'instance_of_claims', 'country_claims_descriptive_only', 'skipped_coordinate_reasons']})


def load_prior(repo):
    evidence, locators = {}, defaultdict(list)
    sources, conflicts = [], []
    for name in ['main', 'japan']:
        path = repo / f'studies/academy_birthplace_screen_v1/inputs/supplements/{name}.jsonl.gz'
        raw_sha = sha(path.read_bytes())
        sources.append({'path': str(path.relative_to(repo)), 'input_sha256': raw_sha})
        with gzip.open(path, 'rt', encoding='utf-8') as f:
            for row_number, line in enumerate(f, 1):
                row = json.loads(line)
                for place_index, pe in enumerate(row.get('place_evidence', [])):
                    qid = pe.get('qid')
                    if not QID.fullmatch(str(qid)):
                        raise ValueError(f'invalid prior QID at {path}:{row_number}')
                    locators[qid].append({'input_path': str(path.relative_to(repo)), 'input_sha256': raw_sha,
                        'line_1based': row_number, 'json_pointer': f'/place_evidence/{place_index}',
                        'cohort': row.get('cohort'), 'record_id': row.get('record_id')})
                    if qid in evidence and prior_signature(evidence[qid]) != prior_signature(pe):
                        conflicts.append(qid)
                    evidence.setdefault(qid, pe)
    if conflicts:
        raise ValueError('Prior place evidence conflicts: ' + ','.join(sorted(set(conflicts))))
    return evidence, dict(locators), sources


def build_client(core, cache, prior, prior_locators, args):
    class IncrementalClient(core.Client):
        def __init__(self):
            super().__init__(cache / 'http', interval=args.interval, retries=args.retries,
                timeout=args.timeout, max_requests=args.max_requests,
                max_runtime_seconds=args.max_runtime_seconds, person_sparql=True,
                person_sparql_batch_size=args.person_batch_size)
            self.normalized = cache / 'normalized'
            self.stats = Counter()
            self.ledger = cache / 'request_ledger.jsonl'
            self.run_id = args.run_id
            self.prior_output = {}

        def request_json(self, url):
            before = self.request_count
            record = {'run_id': self.run_id, 'started_utc': utc_now(), 'url': url}
            try:
                payload, meta = super().request_json(url)
                record.update({'ok': True, 'response': meta})
                self.stats['http_response_cache_hits' if before == self.request_count else 'http_network_successes'] += 1
                return payload, meta
            except Exception as exc:
                record.update({'ok': False, 'error': str(exc)})
                self.stats['http_failed_logical_requests'] += 1
                raise
            finally:
                record.update({'completed_utc': utc_now(), 'network_attempts': self.request_count - before})
                self.stats['http_network_attempts'] += self.request_count - before
                self.ledger.parent.mkdir(parents=True, exist_ok=True)
                with self.ledger.open('ab') as f:
                    f.write(dumps(record))

        def cache_path(self, kind, qid):
            return self.normalized / kind / (qid + '.json')

        def read_normalized(self, kind, qid):
            path = self.cache_path(kind, qid)
            if not path.exists():
                return None
            raw = path.read_bytes()
            data = json.loads(raw)
            if data.get('qid') != qid or data.get('kind') != kind:
                raise ValueError('normalized cache identity mismatch: ' + str(path))
            if data.get('entity') is not None and sha(dumps(data['entity'])) != data.get('entity_sha256'):
                raise ValueError('normalized cache entity checksum mismatch: ' + str(path))
            if data.get('error') and args.retry_failures:
                return None
            data['_cache_path'] = str(path)
            data['_cache_sha256'] = sha(raw)
            return data

        def save_normalized(self, kind, qid, entity=None, response=None, error=None):
            envelope = {'schema': 'birthplace_entity_normalized_v1', 'kind': kind, 'qid': qid,
                'created_utc': utc_now(), 'entity': entity, 'entity_sha256': sha(dumps(entity)) if entity is not None else None,
                'source_response': response, 'error': error,
                'evidence_mode': 'P19_only_SPARQL_projection' if kind == 'people' else 'new_HTTP_wbgetentities_entity',
                'DOB_or_identity_retrieved': False}
            write_json(self.cache_path(kind, qid), envelope)

        def normalized_meta(self, cached):
            response = deepcopy(cached.get('source_response') or {})
            response['normalized_per_qid_cache'] = {'qid': cached['qid'], 'kind': cached['kind'],
                'path': cached['_cache_path'], 'cache_sha256': cached['_cache_sha256'],
                'entity_sha256': cached.get('entity_sha256'), 'cache_created_utc': cached.get('created_utc')}
            return response

        def people(self, qids):
            result, metas, errors, new = {}, {}, {}, []
            ordered = sorted(set(qids), key=lambda q: int(q[1:]))
            self.stats['person_qids_requested'] += len(ordered)
            for qid in ordered:
                cached = self.read_normalized('people', qid)
                if cached:
                    self.stats['person_qid_cache_hits'] += 1
                    if cached.get('error'):
                        errors[qid] = cached['error']
                    else:
                        result[qid], metas[qid] = cached['entity'], self.normalized_meta(cached)
                else:
                    new.append(qid)
            self.stats['person_qids_new'] += len(new)
            if new:
                fresh, fresh_meta, fresh_err = core.Client.people(self, new)
                for qid in new:
                    if qid in fresh:
                        self.save_normalized('people', qid, fresh[qid], fresh_meta[qid])
                    else:
                        self.save_normalized('people', qid, error=fresh_err.get(qid, 'unknown_person_fetch_error'))
                result.update(fresh); metas.update(fresh_meta); errors.update(fresh_err)
            return result, metas, errors

        def entities(self, qids):
            result, metas, errors, new = {}, {}, {}, []
            ordered = sorted(set(qids), key=lambda q: int(q[1:]))
            self.stats['place_qids_requested'] += len(ordered)
            for qid in ordered:
                if qid in prior:
                    self.stats['place_qid_prior_cache_hits'] += 1
                    pe = prior[qid]
                    if pe.get('error'):
                        errors[qid] = 'cached_prior_evidence:' + pe['error']
                        continue
                    source_response = deepcopy(pe.get('response') or {})
                    meta = {'cached_prior_evidence': True, 'evidence_mode': 'cached_prior_evidence',
                        'is_new_raw_API_response': False, 'reconstructed_projection_properties': ['P625', 'P31', 'P17', 'English_label'],
                        'prior_input_locators': prior_locators[qid], 'original_response': source_response,
                        'url': source_response.get('url'), 'retrieved_utc': source_response.get('retrieved_utc'),
                        'response_sha256': source_response.get('response_sha256')}
                    result[qid], metas[qid] = project_prior_entity(qid, pe), meta
                    restored = deepcopy(pe); restored['response'] = meta
                    self.prior_output[qid] = restored
                    continue
                cached = self.read_normalized('places', qid)
                if cached:
                    self.stats['place_qid_new_normalized_cache_hits'] += 1
                    if cached.get('error'):
                        errors[qid] = cached['error']
                    else:
                        result[qid], metas[qid] = cached['entity'], self.normalized_meta(cached)
                else:
                    new.append(qid)
            self.stats['place_qids_new_to_fetch'] += len(new)
            if new:
                fresh, fresh_meta, fresh_err = core.Client.entities(self, new)
                for qid in new:
                    if qid in fresh:
                        self.save_normalized('places', qid, fresh[qid], fresh_meta[qid])
                    else:
                        self.save_normalized('places', qid, error=fresh_err.get(qid, 'unknown_place_fetch_error'))
                result.update(fresh); metas.update(fresh_meta); errors.update(fresh_err)
            return result, metas, errors
    return IncrementalClient()


def frozen_dob(seed):
    # Existing frozen value wins; no network DOB is consulted by this runner.
    for key in ['original_DOB', 'existing_dob', 'dob']:
        if key in seed and seed[key] not in [None, '']:
            return seed[key]
    return ''


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input', type=Path, default=DEFAULT_SEEDS)
    p.add_argument('--repo', type=Path, default=DEFAULT_REPO)
    p.add_argument('--work', type=Path, default=DEFAULT_WORK)
    p.add_argument('--run-id', default=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    p.add_argument('--person-batch-size', type=int, default=200)
    p.add_argument('--interval', type=float, default=.4)
    p.add_argument('--timeout', type=float, default=45)
    p.add_argument('--retries', type=int, default=2)
    p.add_argument('--max-requests', type=int, default=100)
    p.add_argument('--max-runtime-seconds', type=float, default=1200)
    p.add_argument('--retry-failures', action='store_true', help='Explicitly retry prior failed new QIDs; never retries prior v1 places.')
    args = p.parse_args()
    if not 1 <= args.person_batch_size <= 250:
        p.error('--person-batch-size must be 1..250')
    core, core_path = import_core(args.repo)
    raw = args.input.read_bytes()
    seeds = [json.loads(line) for line in raw.decode('utf-8-sig').splitlines() if line.strip()]
    for i, seed in enumerate(seeds):
        if not seed.get('record_id') or not seed.get('cohort') or not QID.fullmatch(str(seed.get('qid', ''))):
            raise ValueError(f'Input row {i+1} requires existing safe QID, cohort and record_id')
        if seed.get('dob') not in [None, '', frozen_dob(seed)]:
            raise ValueError(f'Frozen DOB disagreement in input row {i+1}')
    run_dir = args.work / 'runs' / args.run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    snapshot = run_dir / 'input_seeds.jsonl'
    snapshot.write_bytes(raw)
    prior, locators, prior_sources = load_prior(args.repo)
    client = build_client(core, args.work / 'cache', prior, locators, args)
    core_seeds = [dict(seed, dob=frozen_dob(seed)) for seed in seeds]
    screened = core.screen(core_seeds, client)
    if len(screened) != len(seeds):
        raise AssertionError('Row conservation failure')
    rows = []
    for seed, supplement in zip(seeds, screened):
        row = deepcopy(seed)
        row.update(supplement)
        # Preserve every seed field outside the explicitly generated geography
        # projection, including every DOB/calendar/identity/acceptance field.
        for key, value in seed.items():
            if key not in supplement or any(x in key.lower() for x in ['dob', 'identity', 'acceptance', 'eligib', 'calendar']):
                row[key] = value
        row['dob'] = frozen_dob(seed)
        row['original_DOB'] = frozen_dob(seed)
        row['dob_or_acceptance_modified'] = False
        row['original_identity_flags_preserved'] = True
        row['identity_acceptance_assigned'] = seed.get('identity_acceptance_assigned', False)
        row['final_analysis_eligibility_assigned'] = seed.get('final_analysis_eligibility_assigned', False)
        row['lookup_only'] = True
        row['place_evidence'] = [deepcopy(client.prior_output.get(pe['qid'], pe)) for pe in row['place_evidence']]
        row['strict_places_provenance'] = {'seed_input_sha256': sha(raw), 'seed_input_snapshot': str(snapshot),
            'seed_record_locator': {'cohort': seed['cohort'], 'record_id': seed['record_id']},
            'runner_sha256': sha(Path(__file__).read_bytes()), 'core_sha256': sha(core_path.read_bytes()),
            'birthplace_lookup_only': True, 'DOB_or_identity_retrieved': False}
        if row['dob'] != frozen_dob(seed):
            raise AssertionError('Frozen DOB changed')
        rows.append(row)
    output = run_dir / 'strict_birthplace_rows.jsonl'
    output.write_bytes(b''.join(dumps(row) for row in rows))
    summary = {'schema': 'uk_strict_lookup_incremental_P19_places_v1', 'created_utc': utc_now(),
        'run_id': args.run_id, 'input': str(args.input), 'input_sha256': sha(raw),
        'input_snapshot': str(snapshot), 'output': str(output), 'output_sha256': sha(output.read_bytes()),
        'script_sha256': sha(Path(__file__).read_bytes()), 'core_script_sha256': sha(core_path.read_bytes()),
        'selected_seed_rows': len(seeds), 'output_rows': len(rows),
        'unique_person_qids': len({s['qid'] for s in seeds}), 'prior_place_qids_available': len(prior),
        'prior_place_inputs': prior_sources, 'stats': dict(client.stats),
        'network_attempts': client.request_count,
        'hemisphere_counts': dict(Counter(row['hemisphere'] for row in rows)),
        'reason_counts': dict(Counter(row['reason'] for row in rows)),
        'source_grade': 'S3', 'DOB_and_identity_unchanged': True,
        'notes': ['Only P19 is queried for people; no online DOB/identity acceptance changes.',
            'All prior 2583 place QIDs reused from original v1 evidence; no-coordinate entries stay missing.',
            'New entities are cached per QID; network failures are retained as unknown rows and cached unless explicit retry requested.',
            'Core conservative multiple-place/multiple-coordinate results remain unknown for root postprocessing.',
            'P17 is descriptive evidence only; no nationality or country centroid geography inference.']}
    write_json(run_dir / 'summary.json', summary)
    write_json(args.work / 'latest_summary.json', summary)
    latest = args.work / 'strict_birthplace_rows.jsonl'
    latest.write_bytes(output.read_bytes())
    print(json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
