from pathlib import Path
import tempfile
import unittest
import zipfile
import json
from unittest.mock import patch

from prepare_inputs import (pack_checkpoint, safe_extract, sha256, get_adjudication_archives,
                            load_completed_acquisition)


class CheckpointTest(unittest.TestCase):
    def test_completed_cache_can_finish_offline_but_cannot_change(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            source = base / 'one-source.json'
            source.write_text('original source bytes')
            manifest = {'protocol_id': 'chess-peak-history-acquisition-v1', 'cutoff_month': '2023-12',
                'shard_count': 1, 'selected_n': 1, 'completed_n': 1, 'full_shard_expected_n': 1,
                'files': {'one-source.json': sha256(source)}}
            (base / 'acquisition_manifest.json').write_text(json.dumps(manifest))
            with patch('prepare_inputs.run_acquisition', side_effect=AssertionError('no history requests')):
                self.assertEqual(load_completed_acquisition(base, 1), manifest)
            source.write_text('changed')
            with self.assertRaises(ValueError):
                load_completed_acquisition(base, 1)

    def test_stopped_or_partial_cache_cannot_finish_offline(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            (base / 'one').write_text('source')
            manifest = {'protocol_id': 'chess-peak-history-acquisition-v1', 'cutoff_month': '2023-12',
                'shard_count': 1, 'selected_n': 1, 'completed_n': 1, 'full_shard_expected_n': 1,
                'files': {'one': sha256(base / 'one')}}
            for change in ({'stop_reason': 'rate limit'}, {'completed_n': 0}, {'selected_n': 0}):
                (base / 'acquisition_manifest.json').write_text(json.dumps({**manifest, **change}))
                with self.assertRaises(ValueError):
                    load_completed_acquisition(base, 1)

    def test_original_list_archives_reuse_verified_cache_and_reject_tampering(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = root / 'studies/chess_peak_v1/data/source_archives/jan01frl.zip'
            archive.parent.mkdir(parents=True)
            with zipfile.ZipFile(archive, 'w') as z:
                z.writestr('JAN01FRL.TXT', 'one original list row')
            evidence = {'source_url': 'https://ratings.fide.com/download/jan01frl.zip',
                'archive_file': archive.relative_to(root).as_posix(), 'archive_sha256': sha256(archive)}
            folder = root / 'studies/chess_peak_v1/adjudications'
            folder.mkdir()
            (folder / 'point.json').write_text(json.dumps({'evidence': evidence}))
            with patch('prepare_inputs.urllib.request.urlopen', side_effect=AssertionError('no network')):
                result = get_adjudication_archives(root)
            self.assertEqual(result[evidence['archive_file']]['sha256'], evidence['archive_sha256'])
            archive.write_bytes(b'changed source')
            with self.assertRaises(ValueError):
                get_adjudication_archives(root)

    def test_original_list_archive_cannot_escape_data_evidence_folder(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            folder = root / 'studies/chess_peak_v1/adjudications'
            folder.mkdir(parents=True)
            evidence = {'source_url': 'https://ratings.fide.com/download/jan01frl.zip',
                'archive_file': '../outside.zip', 'archive_sha256': '0' * 64}
            (folder / 'point.json').write_text(json.dumps({'evidence': evidence}))
            with patch('prepare_inputs.urllib.request.urlopen', side_effect=AssertionError('no network')):
                with self.assertRaises(ValueError):
                    get_adjudication_archives(root)

    def test_selected_sources_preserved_and_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            work = Path(temp) / 'work'
            (work / 'fide/raw').mkdir(parents=True)
            (work / 'archives').mkdir()
            (work / 'fide/raw/1.json.gz').write_bytes(b'fixture')
            (work / 'archives/full.zip').write_bytes(b'not duplicated')
            (work / 'historical_history.json').write_text('selected source rows')
            target = Path(temp) / 'checkpoint.zip'
            metadata = pack_checkpoint(work, target)
            with zipfile.ZipFile(target) as z:
                self.assertEqual(set(z.namelist()), {'fide/raw/1.json.gz', 'historical_history.json'})
            self.assertEqual(metadata['sha256'], sha256(target))
            safe_extract(target, Path(temp) / 'restored')
            bad = Path(temp) / 'bad.zip'
            with zipfile.ZipFile(bad, 'w') as z:
                z.writestr('../escape', 'bad')
            with self.assertRaises(ValueError):
                safe_extract(bad, Path(temp) / 'restored')


if __name__ == '__main__':
    unittest.main()
