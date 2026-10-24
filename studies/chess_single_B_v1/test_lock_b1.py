import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace
import lock_b1

class LockTest(unittest.TestCase):
    def test_source_and_metadata_tampering_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for p in lock_b1.CORE:
                (root / p).parent.mkdir(parents=True, exist_ok=True)
                (root / p).write_text('fixture')
            (root / lock_b1.REL / 'config.json').write_text(json.dumps({'fit_allowed': True, 'prior_2013_and_2023_results_seen': True}))
            a = root / lock_b1.A_REL / 'analysis_lock.json'
            a.parent.mkdir(parents=True, exist_ok=True)
            a.write_text('original fixture')
            with patch.object(lock_b1, 'A_SHA', lock_b1.sha256(a)):
                lock_b1.create_lock(root)
                with patch.dict('sys.modules', {'lock_utils': SimpleNamespace(verify_analysis_lock=lambda *a, **k: {})}):
                    lock_b1.verify_lock(root, check_environment=False)
                    (root / lock_b1.REL / 'features.py').write_text('tampered')
                    with self.assertRaisesRegex(ValueError, 'fingerprint mismatch'):
                        lock_b1.verify_lock(root, check_environment=False)
                lock = json.loads((root / lock_b1.LOCK).read_text())
                lock['prior_2013_and_2023_results_seen'] = False
                (root / lock_b1.LOCK).write_text(json.dumps(lock))
                with self.assertRaisesRegex(ValueError, 'metadata'):
                    lock_b1.verify_lock(root, check_environment=False)

if __name__ == '__main__':
    unittest.main()
