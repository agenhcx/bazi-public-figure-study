import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from apply_list_supplements import apply_list_supplements, PROVIDER, PAYLOAD_PROTOCOL


class ListSupplementTests(unittest.TestCase):
    def fixture(self, temp, *, status='failed', error_type='FetchFailure'):
        root = Path(temp)
        folder = root / 'studies/chess_peak_v1/supplements'
        folder.mkdir(parents=True)
        base = root / 'acquisition'
        (base / 'entries').mkdir(parents=True)
        person = {'canonical_id': '4142527', 'role': 'development', 'name': 'Kurnosov, Igor',
            'exact_dob_frozen': '1985-05-30', 'snapshot': '2013-01', 'snapshot_elo': 2648,
            'wikidata_person_qids': ['Q959747']}
        prior = {**person, 'status': status, 'error_type': error_type}
        (base / 'entries/4142527.json').write_text(json.dumps(prior))
        history = [{'month': month, 'standard_elo': value, 'source': PROVIDER,
            'source_point': True, 'source_url': url} for month, value, url in (
                ('2010-05', 2680, 'https://ratings.fide.com/download/may10frl.zip'),
                ('2013-01', 2648, 'https://ratings.fide.com/download/standard_jan13frl.zip'))]
        payload = {'protocol_id': PAYLOAD_PROTOCOL, 'canonical_id': '4142527',
            'name': person['name'], 'frozen_snapshot': {'month': '2013-01', 'rating': 2648},
            'standard_history': history, 'archive_ledger': [{'source': 'fixture'}],
            'coverage': {'last_period': '2013-12'},
            'career_termination': {'date': '2013-08-08'}}
        path = folder / 'kurnosov_4142527.json'
        path.write_text(json.dumps(payload))
        manifest = {'shard_count': 1, 'completed_n': 1, 'selected_n': 1,
            'full_shard_expected_n': 1, 'failed_n': int(status == 'failed'),
            'snapshot_audit_n': 0, 'status': 'history_acquisition_failed'}
        (base / 'acquisition_manifest.json').write_text(json.dumps(manifest))
        return root, base, person, path

    def test_unavailable_history_replaced_and_all_evidence_sealed(self):
        with tempfile.TemporaryDirectory() as temp:
            root, base, person, path = self.fixture(temp)
            original = (base / 'entries/4142527.json').read_bytes()
            with patch('apply_list_supplements.load_roster', return_value=([person], {})):
                result = apply_list_supplements(root, base)
            self.assertEqual(result['failed_n'], 0)
            self.assertEqual(result['source_provider_counts'][PROVIDER], 1)
            entry = json.loads((base / 'entries/4142527.json').read_text())
            self.assertEqual(entry['snapshot_elo'], 2648)
            self.assertEqual(entry['observed_fide_history_peak_elo_through_2023'], 2680)
            self.assertEqual((base / entry['list_supplement']['prior_api_entry_file']).read_bytes(), original)
            self.assertEqual(entry['raw_sha256'], hashlib.sha256(path.read_bytes()).hexdigest())
            for name, digest in result['files'].items():
                self.assertEqual(hashlib.sha256((base / name).read_bytes()).hexdigest(), digest)

    def test_valid_history_or_integrity_failure_never_replaced(self):
        for status, error_type in [('history_acquired', None), ('failed', 'SourceIntegrityError')]:
            with self.subTest(status=status, error=error_type), tempfile.TemporaryDirectory() as temp:
                root, base, person, _ = self.fixture(temp, status=status, error_type=error_type)
                original = (base / 'entries/4142527.json').read_bytes()
                with patch('apply_list_supplements.load_roster', return_value=([person], {})):
                    apply_list_supplements(root, base)
                self.assertEqual((base / 'entries/4142527.json').read_bytes(), original)

    def test_stopped_collection_cannot_be_marked_complete(self):
        with tempfile.TemporaryDirectory() as temp:
            root, base, person, _ = self.fixture(temp)
            manifest = json.loads((base / 'acquisition_manifest.json').read_text())
            manifest['stop_reason'] = 'provider requested cooldown'
            with patch('apply_list_supplements.load_roster', return_value=([person], {})):
                result = apply_list_supplements(root, base, manifest)
            self.assertEqual(result['failed_n'], 1)
            self.assertNotIn('list_supplements_applied', result)

    def test_missing_primary_snapshot_or_changed_identity_is_rejected(self):
        for mutation in ('snapshot', 'identity'):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temp:
                root, base, person, path = self.fixture(temp)
                payload = json.loads(path.read_text())
                if mutation == 'snapshot':
                    payload['standard_history'] = payload['standard_history'][:1]
                else:
                    payload['name'] = 'Another person'
                path.write_text(json.dumps(payload))
                with patch('apply_list_supplements.load_roster', return_value=([person], {})):
                    with self.assertRaises(ValueError):
                        apply_list_supplements(root, base)


if __name__ == '__main__':
    unittest.main()
