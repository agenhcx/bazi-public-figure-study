import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import diagnostic_lock as lock


class LockTests(unittest.TestCase):
    def test_source_tampering_and_missing_coverage_are_blocked(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name in lock.CORE:
                (root / name).parent.mkdir(parents=True, exist_ok=True)
                (root / name).write_text(name.as_posix())
            original = root / lock.STUDY / "analysis_lock.json"
            original.write_text("original-lock")
            digest = hashlib.sha256(original.read_bytes()).hexdigest()
            with patch.object(lock, "ANALYSIS_SHA", digest):
                value = lock.create(root)
                self.assertFalse(value["external_predictive_scoring_allowed"])
                lock.verify(root, check_original=False)
                (root / lock.CORE[0]).write_text("changed after lock")
                with self.assertRaisesRegex(ValueError, "hash mismatch"):
                    lock.verify(root, check_original=False)

    def test_checkpoint_archive_path_escape_is_blocked(self):
        import zipfile
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / lock.STUDY / "results/training_checkpoint_bundle.zip"
            source.parent.mkdir(parents=True)
            with zipfile.ZipFile(source, "w") as archive:
                archive.writestr("../escape", "bad")
            with patch.object(lock, "BUNDLE_SHA", lock.sha256(source)):
                with self.assertRaisesRegex(ValueError, "Unsafe"):
                    lock.extract_checkpoint(root, root / "out")


if __name__ == "__main__":
    unittest.main()
