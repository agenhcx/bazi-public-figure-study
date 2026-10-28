#!/usr/bin/env python3
"""Isolated checks that corrupted UK replay inputs fail with useful artifacts."""
from __future__ import annotations

from contextlib import redirect_stdout
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().with_name("academy_jobs_uk_replay_v1.py")
SPEC = importlib.util.spec_from_file_location("academy_jobs_uk_replay_test_target", SCRIPT)
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


class UKReplayTests(unittest.TestCase):
    def test_semantics_ignore_serialization_and_row_order_but_not_duplicate_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            left, right = Path(directory) / "left.csv", Path(directory) / "right.csv"
            left.write_text("a,b\n1,2\n3,4\n", encoding="utf-8-sig")
            right.write_text("b,a\n4,3\n2,1\n", encoding="utf-8")
            self.assertEqual(runner.csv_semantics(left), runner.csv_semantics(right))
            right.write_text("b,a\n4,3\n2,1\n2,1\n", encoding="utf-8")
            self.assertNotEqual(runner.csv_semantics(left), runner.csv_semantics(right))

    def run_corrupted_copy(self, mutation, expected_failure):
        original_cwd = Path.cwd()
        with tempfile.TemporaryDirectory() as directory:
            copied_root = Path(directory)
            paths = (*runner.INPUTS, *(runner.FROZEN_DIR / name for name in runner.TRACKED_CSVS))
            for relative in paths:
                target = copied_root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(runner.ROOT / relative, target)
            mutation(copied_root)
            before = {str(path): runner.sha256(copied_root / path) for path in paths}
            output = copied_root / "local_runs" / "negative_test"
            try:
                with patch.object(runner, "ROOT", copied_root), patch(
                    "sys.argv", [str(SCRIPT), "--output-dir", str(output)]
                ), redirect_stdout(io.StringIO()):
                    exit_code = runner.main()
            finally:
                os.chdir(original_cwd)
            self.assertEqual(exit_code, 1)
            summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
            failure = json.loads((output / "failure_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["status"], "failed")
            self.assertEqual(summary["counts"]["roster_rows"], 8669)
            self.assertIn(expected_failure, [item["name"] for item in failure["failed_checks"]])
            self.assertIn("Status: **failed**", (output / "summary.md").read_text(encoding="utf-8"))
            self.assertEqual(before, {str(path): runner.sha256(copied_root / path) for path in paths})

    def test_frozen_hash_mismatch_fails_and_emits_failure_artifacts(self):
        def mutate(root):
            path = root / runner.MANIFEST
            manifest = json.loads(path.read_text(encoding="utf-8"))
            manifest["reproducibility_checkpoint"]["unified_crosswalk_sha256"] = "0" * 64
            path.write_text(json.dumps(manifest), encoding="utf-8")

        self.run_corrupted_copy(mutate, "generated_sha256:royal_society_fellows_dob_crosswalk_v1.csv")

    def test_semantic_csv_mismatch_fails_even_when_rebuild_hashes_match(self):
        def mutate(root):
            path = root / runner.FROZEN_DIR / "missingness_by_status_v1.csv"
            path.write_text(path.read_text(encoding="utf-8-sig").replace("past,7099,", "past,7000,"),
                            encoding="utf-8-sig")

        self.run_corrupted_copy(mutate, "tracked_csv_semantics:missingness_by_status_v1.csv")


if __name__ == "__main__":
    unittest.main()
