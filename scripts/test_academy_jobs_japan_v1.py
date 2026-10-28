#!/usr/bin/env python3
"""Safety and regression checks for the bounded Japan follow-up jobs."""
from __future__ import annotations

import copy
import shutil
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import Mock, patch

import academy_jobs_japan_integration_v1 as integration
import academy_jobs_japan_replay_v1 as replay

REPO = Path(__file__).resolve().parents[1]


class JapanJobTests(unittest.TestCase):
    def test_actual_integration_preserves_missing_english_and_unresolved(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            result = integration.run(REPO, output)
            self.assertEqual(result["effective_unresolved_rows"], 36)
            self.assertEqual(result["upstream_blank_english_names_preserved"], 1)
            rows = integration.read_csv(output / "integrated_section_evidence_v1.csv")
            degree_rows = [row for row in rows if row["integration_evidence_origin"] == "frozen_broad_degree_rule"]
            self.assertEqual(len(degree_rows), 199)
            self.assertTrue(all(row["integration_exact_subsection"] == "" for row in degree_rows))
            self.assertTrue(all(row["integration_raw_evidence_verified"] == "0" for row in rows))
            ota = next(row for row in rows if row["member_key"] == "jpa-unlinked-e0aae7738ae3f733")
            self.assertEqual(ota["integration_broad_section"], "unresolved")

    def test_exact_person_name_mismatch_is_rejected(self):
        accepted = integration.read_csv(REPO / integration.ACCEPTED)
        remaining = copy.deepcopy(integration.read_csv(REPO / integration.REMAINING))
        next(row for row in remaining if row["member_key"] == integration.CASES[0]["member_key"])["name_jp"] = "different person"
        with self.assertRaisesRegex(ValueError, "Exact residual key/name mismatch"):
            integration.validate_partition(accepted, remaining)

    def test_changed_frozen_input_fails_before_results(self):
        with tempfile.TemporaryDirectory() as temporary:
            isolated = Path(temporary)
            for name in integration.PINNED_INPUTS:
                target = isolated / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(REPO / name, target)
            with (isolated / integration.ACCEPTED).open("ab") as stream:
                stream.write(b"changed")
            output = isolated / "output"
            output.mkdir()
            with self.assertRaisesRegex(ValueError, "Pinned input SHA256 mismatch"):
                integration.run(isolated, output)
            self.assertEqual(list(output.iterdir()), [])

    def test_output_cannot_target_frozen_data(self):
        with self.assertRaisesRegex(ValueError, "fresh subdirectory"):
            integration.prepare_output(REPO, Path("data/academy_jobs_japan_inputs_v1"))
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(ValueError):
                integration.prepare_output(REPO, Path(temporary))

    def test_rate_limit_stops_after_one_get_without_retry(self):
        opener = Mock()
        opener.open.side_effect = urllib.error.HTTPError(replay.SOURCE_URLS["hiratsuka"], 429, "Too Many Requests", {}, None)
        with tempfile.TemporaryDirectory() as temporary, patch.object(replay.urllib.request, "build_opener", return_value=opener), patch.object(replay.time, "sleep") as delay:
            with self.assertRaises(replay.SourceBlockedError) as caught:
                replay.rehydrate_sources(REPO, Path(temporary))
            self.assertEqual(opener.open.call_count, 1)
            self.assertEqual(opener.open.call_args.kwargs["timeout"], 20)
            self.assertEqual(caught.exception.blocked_source, "hiratsuka")
            self.assertEqual(caught.exception.attempts[0]["http_status"], 429)
            delay.assert_not_called()

    def test_changed_inventory_prevents_any_rehydration(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            inputs = root / "inputs"
            shutil.copytree(REPO / "data/academy_jobs_japan_inputs_v1", inputs)
            inventory = next(inputs.glob("*hiratsuka_source_fetch*/*.csv"))
            with inventory.open("ab") as stream:
                stream.write(b"changed")
            output = root / "output"
            output.mkdir()
            with patch.object(replay, "rehydrate_sources") as request:
                with self.assertRaisesRegex(ValueError, "Archived input SHA256 mismatch"):
                    replay.run(REPO, inputs, output, root / "raw", True)
                request.assert_not_called()

    def test_missing_raw_does_not_claim_completed_replay(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            with self.assertRaises(FileNotFoundError):
                replay.run(REPO, REPO / "data/academy_jobs_japan_inputs_v1", output)
            self.assertFalse((output / "replayed_evidence_decisions_v1.csv").exists())

    def test_derived_text_uses_original_windows_snapshot_bytes(self):
        body = "<p>甲&nbsp;乙</p>".encode("utf-8")
        self.assertEqual(replay.visible_text(body, "yoshikawa"), "甲 乙\r\n".encode("utf-8"))
        self.assertEqual(replay.visible_text(body, "doi"), "甲 乙\r\n".encode("utf-8"))


if __name__ == "__main__":
    unittest.main()
