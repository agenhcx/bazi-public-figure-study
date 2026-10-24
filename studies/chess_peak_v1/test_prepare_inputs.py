from pathlib import Path
import tempfile
import unittest
import zipfile
import json
from unittest.mock import patch

from prepare_inputs import pack_checkpoint, safe_extract, sha256, get_adjudication_archives


class CheckpointTest(unittest.TestCase):
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
