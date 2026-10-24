from pathlib import Path
import tempfile
import unittest
import zipfile

from prepare_inputs import pack_checkpoint, safe_extract, sha256


class CheckpointTest(unittest.TestCase):
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
