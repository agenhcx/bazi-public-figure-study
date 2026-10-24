import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from apply_list_supplements import apply_list_supplements, PROVIDER, PAYLOAD_PROTOCOL


class ListSupplementTests(unittest.TestCase):
    def gap_fixture(self, temp):
        from test_peak_data import person, acquisition_fixture, gap_bridge_fixture
        root, base = Path(temp), Path(temp) / 'acquisition'
        people = {'22': person('22')}
        acquisition_fixture(base, people)
        payload = gap_bridge_fixture(root, base, people, apply=False)
        path = root / 'studies/chess_peak_v1/supplements/fixture_22.json'
        return root, base, people['22'], path, payload

    def test_gap_preserves_original_entry_normalized_and_raw_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            root, base, person, _, payload = self.gap_fixture(temp)
            old_entry = (base / 'entries/22.json').read_bytes()
            old_normalized = (base / 'normalized/22.json').read_bytes()
            raw_path = base / payload['api_history_evidence']['raw_file']
            old_raw = raw_path.read_bytes()
            with patch('apply_list_supplements.load_roster', return_value=([person], {})):
                result = apply_list_supplements(root, base)
                again = apply_list_supplements(root, base)
            self.assertEqual(result['snapshot_audit_n'], 0)
            self.assertEqual(result, again)
            entry = json.loads((base / 'entries/22.json').read_text())
            self.assertEqual(entry['list_supplement']['status'], 'applied_after_api_window_coverage_gap')
            self.assertIsNone(entry['list_supplement']['career_termination'])
            self.assertTrue(entry['list_supplement']['prior_source_coverage_audit']['unresolved'])
            self.assertEqual((base / 'list-supplements/evidence/22.api-entry.json').read_bytes(), old_entry)
            self.assertEqual((base / 'list-supplements/evidence/22.api-normalized.json').read_bytes(), old_normalized)
            self.assertEqual(raw_path.read_bytes(), old_raw)

    def test_gap_cannot_override_snapshot_identity_or_numeric_conflicts(self):
        from test_peak_data import reseal_acquisition
        for mutation in ('snapshot_value', 'numeric_error', 'reason', 'not_unresolved'):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temp:
                root, base, person, _, _ = self.gap_fixture(temp)
                path = base / 'entries/22.json'
                prior = json.loads(path.read_text())
                if mutation == 'snapshot_value':
                    prior.update(snapshot_in_history=True, snapshot_history_elo=2501)
                elif mutation == 'numeric_error':
                    prior['error_type'] = 'SourceIntegrityError'
                elif mutation == 'reason':
                    prior['snapshot_audit_reasons'].append('official_chart_snapshot_rating_differs_from_frozen_snapshot')
                else:
                    prior['source_coverage_audit']['unresolved'] = False
                path.write_text(json.dumps(prior))
                reseal_acquisition(base)
                before = path.read_bytes()
                with patch('apply_list_supplements.load_roster', return_value=([person], {})):
                    apply_list_supplements(root, base)
                self.assertEqual(path.read_bytes(), before)
                self.assertFalse((base / 'list-supplements/raw/22.json.gz').exists())

    def test_sealed_ledger_and_duplicate_targets_checked_before_any_replacement(self):
        with tempfile.TemporaryDirectory() as temp:
            root, base, person, path, payload = self.gap_fixture(temp)
            before = (base / 'entries/22.json').read_bytes()
            duplicate = path.with_name('duplicate_22.json')
            duplicate.write_bytes(path.read_bytes())
            with patch('apply_list_supplements.load_roster', return_value=([person], {})):
                with self.assertRaisesRegex(ValueError, 'Multiple supplement'):
                    apply_list_supplements(root, base)
            self.assertEqual((base / 'entries/22.json').read_bytes(), before)
            duplicate.unlink()
            normalized = base / 'normalized/22.json'
            normalized.write_bytes(normalized.read_bytes() + b' ')
            with patch('apply_list_supplements.load_roster', return_value=([person], {})):
                with self.assertRaisesRegex(ValueError, 'changed before supplementation'):
                    apply_list_supplements(root, base)
            self.assertEqual((base / 'entries/22.json').read_bytes(), before)

    def test_resealed_normalized_source_still_must_match_original_raw_parse(self):
        from test_peak_data import reseal_acquisition
        with tempfile.TemporaryDirectory() as temp:
            root, base, person, path, payload = self.gap_fixture(temp)
            normalized_path = base / 'normalized/22.json'
            normalized = json.loads(normalized_path.read_text())
            normalized['standard_history'][0]['standard_elo'] += 1
            normalized_path.write_text(json.dumps(normalized))
            digest = hashlib.sha256(normalized_path.read_bytes()).hexdigest()
            entry_path = base / 'entries/22.json'
            prior = json.loads(entry_path.read_text())
            prior['normalized_history_sha256'] = digest
            entry_path.write_text(json.dumps(prior))
            payload['api_history_evidence']['normalized_sha256'] = digest
            payload['api_history_evidence']['entry_sha256'] = hashlib.sha256(entry_path.read_bytes()).hexdigest()
            path.write_text(json.dumps(payload))
            reseal_acquisition(base)
            before = entry_path.read_bytes()
            with patch('apply_list_supplements.load_roster', return_value=([person], {})):
                with self.assertRaisesRegex(ValueError, 'fresh raw parse'):
                    apply_list_supplements(root, base)
            self.assertEqual(entry_path.read_bytes(), before)

    def fixture(self, temp, *, status='failed', error_type='FetchFailure'):
        from test_peak_data import acquisition_fixture, list_supplement_fixture, reseal_acquisition
        root = Path(temp)
        folder = root / 'studies/chess_peak_v1/supplements'
        base = root / 'acquisition'
        person = {'canonical_id': '4142527', 'role': 'development', 'name': 'Kurnosov, Igor',
            'exact_dob_frozen': '1985-05-30', 'snapshot': '2013-01', 'snapshot_elo': 2648,
            'wikidata_person_qids': ['Q959747']}
        acquisition_fixture(base, {'4142527': person})
        payload = list_supplement_fixture(root, base, {'4142527': person}, cid='4142527', apply=False)
        for row in payload['standard_history']:
            if row['month'] == '2010-05':
                row['standard_elo'] = 2680
                row['source_line'] = '4142527;Kurnosov, Igor;2680'
        for item in payload['archive_ledger']:
            if item['period'] == '2010-05':
                item['source_line'] = '4142527;Kurnosov, Igor;2680'
        prior = {**person, 'status': status, 'error_type': error_type}
        (base / 'entries/4142527.json').write_text(json.dumps(prior))
        path = folder / 'fixture_4142527.json'
        path.write_text(json.dumps(payload))
        manifest = {'shard_count': 1, 'completed_n': 1, 'selected_n': 1,
            'full_shard_expected_n': 1, 'failed_n': int(status == 'failed'),
            'snapshot_audit_n': 0, 'status': 'history_acquisition_failed',
            'files': {'entries/4142527.json': hashlib.sha256((base / 'entries/4142527.json').read_bytes()).hexdigest()}}
        (base / 'acquisition_manifest.json').write_text(json.dumps(manifest))
        reseal_acquisition(base)
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
