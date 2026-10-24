"""Use audited list archives when a fixed person's history APIs are unavailable."""
from __future__ import annotations

from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import re

from collect_fide import CUTOFF, PROTOCOL, load_roster, utc_now, write_bytes, write_json

PROVIDER = 'fide_official_list_archive'
PAYLOAD_PROTOCOL = 'chess-peak-official-list-supplement-v1'
AUDIT_PROTOCOL = 'chess-peak-list-supplement-adjudication-v1'


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def apply_list_supplements(repo_root, acquisition_dir, manifest=None):
    root, base = Path(repo_root).resolve(), Path(acquisition_dir).resolve()
    manifest_path = base / 'acquisition_manifest.json'
    current = json.loads(manifest_path.read_text()) if manifest is None else dict(manifest)
    folder = root / 'studies/chess_peak_v1/supplements'
    if not folder.is_dir():
        return current
    # A supplement cannot make a stopped/partial collection appear complete.
    if (current.get('stop_reason') or current.get('shard_count') != 1
            or current.get('completed_n') != current.get('selected_n')
            or current.get('selected_n') != current.get('full_shard_expected_n')):
        return current
    people = {p['canonical_id']: p for p in load_roster(root)[0]}
    applied = []
    for path in sorted(folder.glob('*.json')):
        raw = path.read_bytes()
        payload = json.loads(raw)
        if payload.get('protocol_id') != PAYLOAD_PROTOCOL:
            raise ValueError('Unrecognized list-supplement protocol')
        cid = str(payload['canonical_id'])
        if cid not in people:
            raise ValueError('List supplement changes the fixed person set')
        person = people[cid]
        entry_path = base / 'entries' / (cid + '.json')
        prior_bytes = entry_path.read_bytes()
        prior = json.loads(prior_bytes)
        if prior.get('status') != 'failed':
            continue
        if prior.get('error_type') not in ('FetchFailure', 'HistoryUnavailable'):
            # Identity, chronology, numeric and snapshot conflicts are not outages.
            continue
        for key in ('canonical_id', 'role', 'name', 'exact_dob_frozen', 'snapshot',
                    'snapshot_elo', 'wikidata_person_qids'):
            if prior.get(key) != person[key]:
                raise ValueError('Prior unavailable entry changed a frozen person field')
        if payload.get('name') != person['name']:
            raise ValueError('List-supplement name differs from the frozen roster')
        snapshot = payload['frozen_snapshot']
        if (snapshot.get('month') != person['snapshot']
                or snapshot.get('rating') != person['snapshot_elo']):
            raise ValueError('List supplement disagrees with the frozen snapshot')
        history = payload.get('standard_history', [])
        if not history or not payload.get('archive_ledger') or not payload.get('coverage') or not payload.get('career_termination'):
            raise ValueError('List supplement lacks history or coverage provenance')
        by_month = {}
        for row in history:
            month, rating = row.get('month'), row.get('standard_elo')
            if (not isinstance(month, str) or not re.fullmatch(r'\d{4}-(0[1-9]|1[0-2])', month)
                    or not '1971-07' <= month <= CUTOFF
                    or isinstance(rating, bool) or not isinstance(rating, int) or not 0 < rating <= 3500
                    or month < person['exact_dob_frozen'][:7]):
                raise ValueError('Invalid list-supplement rating or chronology')
            if row.get('source') not in (PROVIDER, 'olimpbase_transcription'):
                raise ValueError('List supplement has an unknown per-row source')
            if month in by_month and by_month[month] != rating:
                raise ValueError('List supplement contains a conflicting published month')
            by_month[month] = rating
        primary = [r for r in history if r['source'] == PROVIDER]
        snapshot_rows = [r for r in primary if r['month'] == person['snapshot']]
        if not snapshot_rows or any(r['standard_elo'] != person['snapshot_elo'] for r in snapshot_rows):
            raise ValueError('No independent official-list snapshot witness')
        anchor = max(primary, key=lambda r: r['standard_elo'])
        if not re.fullmatch(r'https://ratings\.fide\.com/download/[A-Za-z0-9_-]+\.zip', anchor['source_url']):
            raise ValueError('Official list anchor has an unexpected URL')
        raw_name = f'list-supplements/raw/{cid}.json.gz'
        prior_name = f'list-supplements/evidence/{cid}.api-entry.json'
        normalized_name = f'normalized/{cid}.json'
        write_bytes(base / prior_name, prior_bytes)
        write_bytes(base / raw_name, gzip.compress(raw, compresslevel=6, mtime=0))
        normalized = {'canonical_id': cid, 'source_provider': PROVIDER,
            'source_raw_sha256': sha256(raw), 'standard_history': history,
            'label_cutoff_month': CUTOFF, 'future_months_retained_in_source_only': False,
            'history_compression': 'selected exact published list rows with archive fingerprints',
            'peak_months_complete': False}
        write_json(base / normalized_name, normalized)
        rows_by_source = dict(Counter(r['source'] for r in history))
        audit = {'protocol_id': AUDIT_PROTOCOL, 'status': 'applied_after_api_history_unavailable',
            'supplement_file': path.relative_to(root).as_posix(), 'supplement_sha256': sha256(raw),
            'prior_api_entry_file': prior_name, 'prior_api_entry_sha256': sha256(prior_bytes),
            'reason': 'no_usable_history_from_fide_chart_or_lichess',
            'source_selection': 'source_availability_not_rating_magnitude',
            'primary_snapshot_verified': True, 'original_identity_unchanged': True,
            'rows_by_source': rows_by_source, 'coverage': payload['coverage'],
            'career_termination': payload['career_termination']}
        eligible = [r for r in history if r['month'] <= CUTOFF]
        entry = {**person, 'protocol_id': PROTOCOL, 'cutoff_month': CUTOFF,
            'status': 'history_acquired', 'source_provider': PROVIDER,
            'source_url': anchor['source_url'], 'fetched_at_utc': utc_now(),
            'raw_history_file': raw_name, 'raw_sha256': sha256(raw), 'raw_bytes': len(raw),
            'normalized_history_file': normalized_name,
            'normalized_history_sha256': sha256((base / normalized_name).read_bytes()),
            'snapshot_in_history': True, 'snapshot_history_elo': person['snapshot_elo'],
            'snapshot_audit_required': False, 'snapshot_audit_reasons': [],
            'history_start': min(by_month), 'history_end': max(by_month),
            'standard_history_n': len(eligible),
            'observed_fide_history_peak_elo_through_2023': max(r['standard_elo'] for r in eligible),
            'peak_months_complete': False, 'coverage_needs_pre2003': True,
            'lifetime_peak_claimed': False, 'list_supplement': audit}
        write_json(entry_path, entry)
        applied.append(cid)
    if not applied:
        return current
    entries = [json.loads(p.read_text()) for p in sorted((base / 'entries').glob('*.json'))]
    counts = {p: 0 for p in ('fide_official_chart', 'lichess_fide_history', PROVIDER)}
    for entry in entries:
        if entry['status'] != 'failed':
            counts[entry.get('source_provider', 'fide_official_chart')] += 1
    current.update(failed_n=sum(e['status'] == 'failed' for e in entries),
        snapshot_audit_n=sum(bool(e.get('snapshot_audit_required')) for e in entries),
        snapshot_disagreement_n=sum(bool(e.get('snapshot_disagreement')) for e in entries),
        source_provider_counts=counts, list_supplements_applied=applied)
    current['status'] = ('history_acquisition_failed' if current['failed_n']
                         else 'rating_histories_acquired_pending_historical_merge')
    current['files'] = {p.relative_to(base).as_posix(): sha256(p.read_bytes())
        for p in sorted(base.rglob('*')) if p.is_file()
        and p.name not in ('acquisition_manifest.json', 'STOP') and not p.name.endswith('.tmp')}
    write_json(manifest_path, current)
    return current
