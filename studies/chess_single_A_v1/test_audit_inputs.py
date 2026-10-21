"""Meaningful failure-mode tests for the input-only audit."""

import csv
import json
import tempfile
import unittest
from pathlib import Path

from audit_inputs import audit_inputs, fingerprints


class InputAuditTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.rows = {
            "development": [self.make_row("101", "1990-01-05", "2013-01")],
            "primary_evaluation": [self.make_row("202", "1992-04-01", "2023-01")],
            "secondary_evaluation": [self.make_row("101", "1990-01-05", "2023-01")],
        }
        self.manifest = {
            "protocol_id": "synthetic-test-only",
            "source_commit": "test-commit",
            "files": [],
            "expected_identity_overlaps": {
                "development_primary_evaluation": 0,
                "development_secondary_evaluation": 1,
                "primary_evaluation_secondary_evaluation": 0,
            },
        }
        for role in self.rows:
            self.write_role(role)

    @staticmethod
    def make_row(identity, dob, snapshot):
        return {
            "fide_id": identity,
            "identity_bridge_modern_fide_id": identity,
            "exact_dob_frozen": dob,
            "snapshot": snapshot,
            "sex": "M",
            "rating": "2500",
            "year_pillar": "己巳",
            "month_pillar": "丙子",
            "day_pillar": "庚午",
            "day_stem": "庚",
        }

    def write_role(self, role, columns=None):
        path = self.root / (role + ".csv")
        columns = columns or list(self.rows[role][0])
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(self.rows[role])
        entry = {
            "role": role, "path": path.name,
            **fingerprints(path.read_bytes()),
            "expected_rows": len(self.rows[role]),
            "expected_snapshot": "2013-01" if role == "development" else "2023-01",
        }
        self.manifest["files"] = [
            item for item in self.manifest["files"] if item["role"] != role
        ] + [entry]

    def run_audit(self):
        return audit_inputs(self.root, self.manifest)

    def assert_error(self, code):
        report = self.run_audit()
        self.assertFalse(report["ok"])
        self.assertIn(code, {item["code"] for item in report["errors"]})

    def test_pillar_only_2023_schema_is_valid_and_report_has_no_ratings(self):
        report = self.run_audit()
        self.assertTrue(report["ok"], report["errors"])
        self.assertEqual(report["identity_overlaps"],
                         self.manifest["expected_identity_overlaps"])
        serialised = json.dumps(report)
        self.assertNotIn("2500", serialised)
        self.assertNotIn("1990-01-05", serialised)
        self.assertNotIn("year_pillar", serialised)

    def test_sha256_change_is_rejected(self):
        self.manifest["files"][0]["sha256"] = "0" * 64
        self.assert_error("fingerprint_mismatch")

    def test_git_blob_change_is_rejected(self):
        self.manifest["files"][0]["git_blob_sha"] = "0" * 40
        self.assert_error("fingerprint_mismatch")

    def test_duplicate_canonical_id_is_rejected(self):
        self.rows["development"].append(dict(self.rows["development"][0]))
        self.write_role("development")
        self.assert_error("duplicate_canonical_id")

    def test_illegal_same_pillar_yin_yang_pair_is_rejected(self):
        self.rows["primary_evaluation"][0]["month_pillar"] = "甲丑"
        self.write_role("primary_evaluation")
        self.assert_error("invalid_pillar")

    def test_existing_day_stem_must_match_day_pillar(self):
        self.rows["primary_evaluation"][0]["day_stem"] = "辛"
        self.write_role("primary_evaluation")
        self.assert_error("position_pillar_mismatch")

    def test_cross_file_identity_birthdate_conflict_is_rejected(self):
        self.rows["secondary_evaluation"][0]["exact_dob_frozen"] = "1990-01-06"
        self.write_role("secondary_evaluation")
        self.assert_error("cross_file_identity_inconsistent")

    def test_wrong_expected_overlap_is_rejected(self):
        self.manifest["expected_identity_overlaps"][
            "development_secondary_evaluation"
        ] = 0
        self.assert_error("identity_overlap_mismatch")

    def test_missing_required_header_is_rejected(self):
        columns = [key for key in self.rows["primary_evaluation"][0]
                   if key != "rating"]
        self.write_role("primary_evaluation", columns=columns)
        self.assert_error("missing_required_columns")

    def test_birthdate_after_snapshot_is_rejected(self):
        self.rows["primary_evaluation"][0]["exact_dob_frozen"] = "2023-01-02"
        self.write_role("primary_evaluation")
        self.assert_error("dob_not_before_snapshot")

    def test_compact_birthdate_is_not_accepted_as_exact_iso(self):
        self.rows["primary_evaluation"][0]["exact_dob_frozen"] = "19920401"
        self.write_role("primary_evaluation")
        self.assert_error("invalid_exact_dob")

    def test_noninteger_rating_is_rejected(self):
        self.rows["primary_evaluation"][0]["rating"] = "2500.5"
        self.write_role("primary_evaluation")
        self.assert_error("invalid_rating_integer")

    def test_canonical_bridge_takes_precedence_and_blank_bridge_falls_back(self):
        self.rows["secondary_evaluation"][0]["fide_id"] = "999"
        self.write_role("secondary_evaluation")
        self.rows["primary_evaluation"][0]["identity_bridge_modern_fide_id"] = ""
        self.write_role("primary_evaluation")
        self.assertTrue(self.run_audit()["ok"])

    def test_snapshot_mismatch_is_rejected(self):
        self.rows["primary_evaluation"][0]["snapshot"] = "2023-02"
        self.write_role("primary_evaluation")
        self.assert_error("snapshot_mismatch")

    def test_sex_mismatch_is_rejected(self):
        self.rows["primary_evaluation"][0]["sex"] = "F"
        self.write_role("primary_evaluation")
        self.assert_error("sex_mismatch")


if __name__ == "__main__":
    unittest.main()
