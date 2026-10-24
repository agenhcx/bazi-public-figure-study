"""Synthetic peak/provenance checks only; no acquisition or model fitting."""
import csv
import gzip
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import pandas as pd
import peak_data as data

def person(cid="11", role="development", snapshot="2013-01", snapshot_elo=2500):
    return {"canonical_id": cid, "role": role, "name": f"Player {cid}",
        "exact_dob_frozen": "1980-02-03", "snapshot": snapshot, "snapshot_elo": snapshot_elo,
        "wikidata_person_qids": [f"Q{cid}"]}

def record(month, elo, cid="11", source="fide_official_chart"):
    return {"canonical_id": cid, "period": month, "rating": elo, "source": source}

def original_row(p):
    return {"canonical_id": p["canonical_id"], "snapshot": p["snapshot"],
        "exact_dob_frozen": p["exact_dob_frozen"], "rating": p["snapshot_elo"],
        "year_stem": "庚", "year_branch": "申", "month_stem": "己", "month_branch": "丑",
        "day_stem": "甲", "day_branch": "子", "year_pillar": "庚申", "month_pillar": "己丑", "day_pillar": "甲子"}

def acquisition_fixture(base, people, providers=None, derived_ids=()):
    """One synthetic shard with raw, normalized, entry and manifest hash layers."""
    base.mkdir(parents=True, exist_ok=True)
    for cid, p in people.items():
        provider = (providers or {}).get(cid, "fide_official_chart")
        raw = json.dumps({"fixture_identity": cid}).encode()
        raw_sha = hashlib.sha256(raw).hexdigest()
        (base / "raw").mkdir(exist_ok=True)
        (base / "raw" / f"{cid}.json.gz").write_bytes(gzip.compress(raw, mtime=0))
        normalized = {"canonical_id": cid, "label_cutoff_month": data.CUTOFF,
            "source_raw_sha256": raw_sha, "standard_history": [
                {"month": "2003-04", "standard_elo": p["snapshot_elo"]},
                {"month": p["snapshot"], "standard_elo": p["snapshot_elo"]},
                {"month": "2023-12", "standard_elo": p["snapshot_elo"] + 20},
                {"month": "2024-01", "standard_elo": p["snapshot_elo"] + 300}]}
        if provider == "lichess_fide_history":
            normalized.update(source_provider=provider, peak_months_complete=False,
                history_compression="first_and_last_point_of_each_equal_rating_streak_retained")
            for point in normalized["standard_history"]:
                point["source_point"] = True
                if cid in derived_ids and point["month"] == p["snapshot"]:
                    point.update(source_point=False, derived_state=True, derived_from_month="2003-04",
                        derivation="piecewise_constant_state_from_compressed_FIDE_rating_history")
        normalized_path = base / "normalized" / f"{cid}.json"
        data.write_json(normalized_path, normalized)
        entry = {**p, "status": "history_acquired", "source_url": f"https://ratings.fide.com/a_chart_data.phtml?event={cid}&period=0",
            "raw_sha256": raw_sha, "normalized_history_file": f"normalized/{cid}.json",
            "normalized_history_sha256": data.sha256(normalized_path)}
        if provider == "lichess_fide_history":
            entry.update(source_provider=provider, source_url=f"https://lichess.org/api/fide/player/{cid}/ratings",
                peak_months_complete=False)
        data.write_json(base / "entries" / f"{cid}.json", entry)
    manifest = {"protocol_id": "chess-peak-history-acquisition-v1",
        "status": "official_chart_histories_acquired_pending_historical_merge", "cutoff_month": data.CUTOFF,
        "model_fitting_performed": False, "failed_n": 0, "selected_n": len(people), "completed_n": len(people),
        "full_shard_expected_n": len(people), "shard_index": 0, "shard_count": 1,
        "files": {p.relative_to(base).as_posix(): data.sha256(p) for p in sorted(base.rglob("*"))
            if p.is_file() and p.name != "acquisition_manifest.json"}}
    if providers:
        manifest["source_provider_counts"] = {provider: sum(providers.get(cid, "fide_official_chart") == provider
            for cid in people) for provider in data.FIDE_PROVIDERS}
        if manifest["source_provider_counts"]["lichess_fide_history"]:
            manifest["status"] = "rating_histories_acquired_pending_historical_merge"
    data.write_json(base / "acquisition_manifest.json", manifest)

def reseal_acquisition(base):
    path = base / "acquisition_manifest.json"
    manifest = data.read_json(path)
    manifest["files"] = {p.relative_to(base).as_posix(): data.sha256(p)
        for p in sorted(base.rglob("*")) if p.is_file() and p != path}
    data.write_json(path, manifest)

def coverage_audit_fixture(base, cid="11", outcome="selected_snapshot_verified"):
    """Retain both providers' evidence for a fixed-rule coverage check."""
    entry_path = base / "entries" / f"{cid}.json"
    entry = data.read_json(entry_path)
    provider = entry.get("source_provider", "fide_official_chart")
    unresolved, checked, expected_provider = {
        "selected_snapshot_verified": (False, True, "fide_official_chart"),
        "unavailable": (True, False, "lichess_fide_history"),
        "missing_frozen_snapshot": (True, True, "lichess_fide_history")}[outcome]
    if provider != expected_provider:
        raise AssertionError("Fixture provider differs from coverage outcome")
    evidence = []
    for source_provider in data.FIDE_PROVIDERS:
        if outcome == "unavailable" and source_provider == "fide_official_chart":
            continue
        raw = (gzip.decompress((base / "raw" / f"{cid}.json.gz").read_bytes()) if source_provider == provider
            else json.dumps({"fixture_identity": cid, "source_provider": source_provider}).encode())
        raw_path = base / "coverage-evidence" / f"{cid}.{source_provider}.json.gz"
        raw_path.parent.mkdir(exist_ok=True)
        raw_path.write_bytes(gzip.compress(raw, mtime=0))
        metadata = {"canonical_id": cid, "source_provider": source_provider,
            "raw_sha256": hashlib.sha256(raw).hexdigest(), "raw_bytes": len(raw),
            "gzip_sha256": data.sha256(raw_path)}
        metadata_path = raw_path.with_suffix(".metadata.json")
        data.write_json(metadata_path, metadata)
        evidence.append({**{key: metadata[key] for key in ("source_provider", "raw_sha256", "raw_bytes", "gzip_sha256")},
            "raw_file": raw_path.relative_to(base).as_posix(),
            "metadata_file": metadata_path.relative_to(base).as_posix(), "metadata_sha256": data.sha256(metadata_path)})
    entry["source_coverage_audit"] = {"rule_id": data.COVERAGE_RULE,
        "reasons": ["lichess_missing_frozen_snapshot", "lichess_late_history_for_older_person"],
        "unresolved": unresolved, "selected_provider": provider, "direct_source_coverage_checked": checked,
        "sources": evidence, "official_outcome": outcome}
    entry["snapshot_audit_required"] = unresolved
    data.write_json(entry_path, entry)
    reseal_acquisition(base)
    return entry["source_coverage_audit"]

class CombineTests(unittest.TestCase):
    def test_historical_peak_and_future_exclusion_and_matching_overlap(self):
        official = [record("2013-01", 2500), record("2023-12", 2600), record("2026-01", 2990)]
        old = [record("1994-01", 2780, source="olimpbase_transcription"),
            record("2013-01", 2500, source="olimpbase_transcription")]
        label, rows, ignored = data.combine_person(person(), official, old)
        self.assertEqual(label["rating"], 2780)
        self.assertEqual(label["peak_periods"], "1994-01")
        self.assertEqual(label["peak_sources"], "olimpbase_transcription")
        self.assertEqual(label["history_n"], 3)
        self.assertEqual(label["pre2003_history_n"], 1)
        self.assertEqual(ignored, 1)
        self.assertEqual(rows[1]["sources"], "fide_official_chart;olimpbase_transcription")
        self.assertEqual(label["feature_reference_snapshot"], "2024-01")

    def test_all_tied_peak_months_preserved(self):
        label, _, _ = data.combine_person(person(), [record("2013-01", 2500),
            record("2023-10", 2679), record("2023-11", 2679)], [])
        self.assertEqual(label["peak_periods"], "2023-10;2023-11")

    def test_derived_snapshot_state_is_not_an_observed_peak_month(self):
        source = "lichess_fide_history"
        snapshot = record("2013-01", 2600, source=source)
        snapshot.update(derived_state=True, source_point=False, derived_from_month="2003-04",
            derivation="piecewise_constant_state_from_compressed_FIDE_rating_history")
        label, _, _ = data.combine_person(person(snapshot_elo=2600), [
            record("2003-04", 2600, source=source), snapshot, record("2023-12", 2500, source=source)], [])
        self.assertEqual(label["rating"], 2600)
        self.assertEqual(label["peak_periods"], "2003-04")
        self.assertEqual(label["derived_snapshot_record_n"], 1)
        self.assertFalse(label["peak_periods_complete"])

    def test_conflicting_month_and_snapshot_mismatch_stop(self):
        with self.assertRaisesRegex(ValueError, "Conflicting ratings"):
            data.combine_person(person(), [record("2013-01", 2500), record("2023-12", 2600)],
                [record("2013-01", 2499, source="olimpbase_transcription")])
        with self.assertRaisesRegex(ValueError, "snapshot rating differs"):
            data.combine_person(person(), [record("2013-01", 2499), record("2023-12", 2700)], [])
        with self.assertRaisesRegex(ValueError, "snapshot month absent"):
            data.combine_person(person(), [record("2023-12", 2700)], [])

    def test_below_peak_conflict_has_no_chosen_rating_or_peak_date(self):
        official = [record("2013-01", 2500), record("2023-12", 2600)]
        historical = [record("1980-01", 2410, source="olimpbase_transcription"),
            record("1980-01", 2470, source="olimpbase_transcription")]
        original = json.loads(json.dumps(historical))
        label, rows, _ = data.combine_person(person(), official, historical)
        self.assertEqual(label["rating"], 2600)
        self.assertEqual(label["peak_periods"], "2023-12")
        self.assertEqual(label["ambiguous_period_n"], 1)
        self.assertEqual(label["ambiguous_periods"], "1980-01")
        self.assertEqual(label["period_conflict_resolution_policy"], data.CONFLICT_POLICY)
        unresolved = rows[0]
        self.assertIsNone(unresolved["rating"])
        self.assertEqual(unresolved["candidate_ratings"], [2410, 2470])
        self.assertEqual(len(unresolved["source_records"]), 2)
        self.assertTrue(all(x["period_rating_not_selected"] for x in unresolved["source_records"]))
        self.assertEqual(historical, original)  # Source payload bytes/hash must remain meaningful.

    def test_upper_bound_equal_to_peak_does_not_invent_a_peak_date(self):
        label, rows, _ = data.combine_person(person(), [record("2013-01", 2500), record("2023-12", 2600)],
            [record("1980-01", 2500, source="olimpbase_transcription"),
             record("1980-01", 2600, source="olimpbase_transcription")])
        self.assertEqual(label["peak_periods"], "2023-12")
        self.assertIsNone(rows[0]["rating"])

    def test_above_peak_and_no_unambiguous_source_peak_stop(self):
        with self.assertRaisesRegex(ValueError, "can change the confirmed peak"):
            data.combine_person(person(), [record("2013-01", 2500), record("2023-12", 2600)],
                [record("1980-01", 2500, source="olimpbase_transcription"),
                 record("1980-01", 2700, source="olimpbase_transcription")])
        with self.assertRaisesRegex(ValueError, "No unambiguous"):
            data.combine_person(person(), [record("2013-01", 2500)],
                [record("2013-01", 2510, source="olimpbase_transcription")])

    def test_other_identity_invalid_rating_and_unknown_source_rejected(self):
        for bad in [record("2013-01", 2500, cid="22"), record("2013-01", 0),
            record("2013-01", True), record("2013-13", 2500), record("2013-01", 2500, source="wikipedia_peak")]:
            with self.assertRaises(ValueError):
                data.combine_person(person(), [bad], [])

class AcquisitionTests(unittest.TestCase):
    def test_coverage_check_evidence_and_resolved_decision_are_verified(self):
        with tempfile.TemporaryDirectory() as temporary:
            base, people = Path(temporary), {"11": person()}
            acquisition_fixture(base, people)
            coverage = coverage_audit_fixture(base)
            audit = {}
            entries, _ = data.read_acquisition(base, people, dataset_audit=audit)
            self.assertEqual(entries["11"]["entry"]["source_coverage_audit"], coverage)
            self.assertEqual(audit["source_coverage_audits"], {"11": coverage})
            self.assertEqual(audit["source_coverage_resolved_n"], 1)
            self.assertEqual(audit["source_coverage_unresolved_n"], 0)
            path = base / coverage["sources"][0]["raw_file"]
            path.write_bytes(gzip.compress(b"changed coverage evidence", mtime=0))
            reseal_acquisition(base)
            with self.assertRaisesRegex(ValueError, "coverage evidence fingerprint"):
                data.read_acquisition(base, people)

    def test_explicit_unresolved_coverage_or_snapshot_audit_blocks_ready(self):
        for outcome in ("unavailable", "missing_frozen_snapshot"):
            with self.subTest(outcome=outcome), tempfile.TemporaryDirectory() as temporary:
                base, people = Path(temporary), {"11": person()}
                acquisition_fixture(base, people, {"11": "lichess_fide_history"})
                coverage_audit_fixture(base, outcome=outcome)
                audit = {}
                with self.assertRaisesRegex(data.DatasetBuildError, "remains unresolved"):
                    data.read_acquisition(base, people, dataset_audit=audit)
                self.assertEqual(audit["source_coverage_unresolved_n"], 1)
                self.assertEqual(audit["snapshot_audit_required_person_ids"], ["11"])
        with tempfile.TemporaryDirectory() as temporary:
            base, people = Path(temporary), {"11": person()}
            acquisition_fixture(base, people)  # Legacy absence remains allowed until explicit flag.
            entry_path = base / "entries/11.json"
            entry = data.read_json(entry_path)
            entry["snapshot_audit_required"] = True
            data.write_json(entry_path, entry)
            reseal_acquisition(base)
            with self.assertRaisesRegex(data.DatasetBuildError, "remains unresolved"):
                data.read_acquisition(base, people)

    def test_coverage_decision_cannot_claim_resolution_without_official_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            base, people = Path(temporary), {"11": person()}
            acquisition_fixture(base, people)
            coverage_audit_fixture(base)
            path = base / "entries/11.json"
            entry = data.read_json(path)
            entry["source_coverage_audit"]["direct_source_coverage_checked"] = False
            data.write_json(path, entry)
            reseal_acquisition(base)
            with self.assertRaisesRegex(ValueError, "coverage decision"):
                data.read_acquisition(base, people)

    def test_all_three_source_fingerprints_and_entry_fields_verified(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            people = {"11": person()}
            acquisition_fixture(base, people)
            rows, provenance = data.read_acquisition(base, people)
            self.assertEqual(len(rows["11"]["records"]), 4)
            self.assertEqual(len(provenance), 1)
            (base / "raw/11.json.gz").write_bytes(gzip.compress(b"changed", mtime=0))
            with self.assertRaisesRegex(ValueError, "file changed"):
                data.read_acquisition(base, people)

    def test_partial_shard_and_missing_people_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            people = {"11": person()}
            acquisition_fixture(base, people)
            with self.assertRaisesRegex(ValueError, "all fixed people"):
                data.read_acquisition(base, {**people, "22": person("22")})
            path = base / "acquisition_manifest.json"
            manifest = data.read_json(path)
            manifest["status"] = "partial_pilot_history_acquisition"
            data.write_json(path, manifest)
            with self.assertRaisesRegex(ValueError, "incomplete or failed"):
                data.read_acquisition(base, people)

    def test_mirror_provenance_and_derived_snapshot_are_preserved(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            people = {"11": person()}
            acquisition_fixture(base, people, {"11": "lichess_fide_history"}, derived_ids={"11"})
            acquired, _ = data.read_acquisition(base, people)
            rows = acquired["11"]["records"]
            derived = next(row for row in rows if row.get("derived_state"))
            self.assertEqual(derived["period"], "2013-01")
            self.assertEqual(derived["derived_from_month"], "2003-04")
            self.assertFalse(derived["source_point"])
            self.assertFalse(derived["peak_months_complete"])
            self.assertEqual(derived["source"], "lichess_fide_history")
            label, _, _ = data.combine_person(people["11"], rows, [])
            self.assertEqual(label["rating"], 2520)
            self.assertEqual(label["fide_history_n"], 3)
            self.assertEqual(label["official_chart_history_n"], 0)
            self.assertEqual(label["lichess_history_n"], 3)
            self.assertEqual(label["derived_snapshot_record_n"], 1)
            self.assertFalse(label["peak_periods_complete"])

    def test_mirror_cannot_invent_snapshot_state_or_complete_tie_claim(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            people = {"11": person()}
            acquisition_fixture(base, people, {"11": "lichess_fide_history"}, derived_ids={"11"})
            path = base / "normalized/11.json"
            normalized = data.read_json(path)
            normalized["standard_history"][1]["derived_from_month"] = "2002-01"
            data.write_json(path, normalized)
            entry_path = base / "entries/11.json"
            entry = data.read_json(entry_path)
            entry["normalized_history_sha256"] = data.sha256(path)
            data.write_json(entry_path, entry)
            reseal_acquisition(base)
            with self.assertRaisesRegex(ValueError, "Invalid piecewise-constant"):
                data.read_acquisition(base, people)
            normalized["standard_history"][1]["derived_from_month"] = "2003-04"
            normalized["peak_months_complete"] = True
            data.write_json(path, normalized)
            entry["normalized_history_sha256"] = data.sha256(path)
            data.write_json(entry_path, entry)
            reseal_acquisition(base)
            with self.assertRaisesRegex(ValueError, "Compressed source cannot claim"):
                data.read_acquisition(base, people)

class DatasetTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.people = {"11": person(), "22": person("22"), "33": person("33", "primary_new", "2023-01", 2400)}
        self.frames = {r: pd.DataFrame([original_row(p) for p in self.people.values() if p["role"] == r]) for r in data.ROLES}
        self.role_ids = {r: sorted(self.frames[r].canonical_id.tolist()) for r in data.ROLES}
        self.role_qids = {r: sorted(q for p in self.people.values() if p["role"] == r for q in p["wikidata_person_qids"]) for r in data.ROLES}
        self.sources = {}
        for role in data.ROLES:
            self.sources[role] = {}
            for kind in ("cohort", "model_input"):
                path = self.root / f"original_{role}_{kind}.csv"
                self.frames[role].to_csv(path, index=False)
                self.sources[role][kind] = {"path": path.relative_to(self.root).as_posix(), "sha256": data.sha256(path)}
        self.acquisition = self.root / "acquisition"
        acquisition_fixture(self.acquisition, self.people)
        self.historical = {"status": "complete", "records": [record("1994-01", 2800, source="olimpbase_transcription")],
            "audit": {"fatal_issues": [], "status": "complete"},
            "coverage": {"first_official_period": "1971-07", "last_selected_period": "2003-04",
                "published_periods": ["1971-07", "2003-04"], "period_count": 2},
            "archives": {"pre2002": {"sha256": "a" * 64, "coverage": "available published lists"}}}
        self.patches = [patch.object(data, "EXPECTED_COUNTS", {"development": 2, "primary_new": 1}),
            patch.object(data, "_load_originals", return_value=(self.frames, self.people, self.sources, self.role_ids, self.role_qids)),
            patch.object(data, "_a_loader", side_effect=lambda root, role: self.frames[role].copy())]
        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.temporary.cleanup()

    def build(self):
        return data.build_dataset(self.root, self.acquisition, self.historical)

    def mutate_frame(self, role, change):
        manifest_path = self.root / data.DATA / "data_manifest.json"
        manifest = data.read_json(manifest_path)
        info = manifest["roles"][role]
        path = self.root / info["path"]
        frame = pd.read_csv(path, dtype=str)
        change(frame)
        frame.to_csv(path, index=False)
        info["sha256"] = data.sha256(path)
        data.write_json(manifest_path, manifest)

    def test_complete_build_preserves_original_inputs_and_common_cutoff(self):
        manifest = self.build()
        self.assertEqual(manifest["status"], data.STATUS)
        self.assertEqual(manifest["canonical_id_overlap"], 0)
        self.assertEqual(manifest["wikidata_person_overlap"], 0)
        self.assertFalse(manifest["completed_career_peak_claimed"])
        first, second = data.load_frame(self.root, "development"), data.load_frame(self.root, "primary_new")
        self.assertEqual(first.rating.tolist(), [2800, 2520])
        self.assertEqual(second.rating.tolist(), [2420])
        self.assertEqual(first.snapshot_rating.tolist(), [2500, 2500])
        self.assertEqual(first.snapshot.tolist(), ["2013-01", "2013-01"])
        self.assertEqual(second.snapshot.tolist(), ["2023-01"])
        self.assertEqual(set(first.feature_reference_snapshot) | set(second.feature_reference_snapshot), {"2024-01"})
        for name in data.ORIGINAL_FIELDS:
            if name != "rating":
                self.assertEqual(first[name].tolist(), self.frames["development"][name].tolist())
        history = pd.read_csv(self.root / manifest["normalized_history"]["path"])
        self.assertNotIn("2024-01", set(history.period))
        with self.assertRaisesRegex(ValueError, "Refusing to replace"):
            self.build()

    def test_coverage_audits_and_counts_preserved_in_dataset_manifest(self):
        coverage = coverage_audit_fixture(self.acquisition)
        manifest = self.build()
        self.assertEqual(manifest["source_coverage_checked_n"], 1)
        self.assertEqual(manifest["source_coverage_resolved_n"], 1)
        self.assertEqual(manifest["source_coverage_unresolved_n"], 0)
        audit = data.read_json(self.root / manifest["audit"]["path"])
        self.assertEqual(audit["source_coverage_audits"], {"11": coverage, "22": None, "33": None})
        self.assertEqual(audit["snapshot_audit_required_n"], 0)
        self.assertEqual(len(data.load_frame(self.root, "development")), 2)

    def test_unresolved_coverage_retained_in_failure_audit_without_ready_manifest(self):
        acquisition_fixture(self.acquisition, self.people, {"22": "lichess_fide_history"})
        coverage = coverage_audit_fixture(self.acquisition, cid="22", outcome="missing_frozen_snapshot")
        with self.assertRaisesRegex(data.DatasetBuildError, "remains unresolved"):
            self.build()
        audit = data.read_json(self.root / data.DATA / "dataset_build_audit.json")
        self.assertEqual(audit["source_coverage_audits"]["22"], coverage)
        self.assertEqual(audit["source_coverage_checked_n"], 1)
        self.assertEqual(audit["source_coverage_resolved_n"], 0)
        self.assertEqual(audit["source_coverage_unresolved_n"], 1)
        self.assertEqual(audit["source_coverage_unresolved_person_ids"], ["22"])
        self.assertFalse((self.root / data.DATA / "data_manifest.json").exists())

    def test_complete_mixed_provider_dataset_has_mirror_counts_and_no_fake_monthly_ties(self):
        acquisition_fixture(self.acquisition, self.people, {"22": "lichess_fide_history"}, derived_ids={"22"})
        manifest = self.build()
        self.assertEqual(manifest["history_source_provider_counts"], {"fide_official_chart": 2, "lichess_fide_history": 1})
        self.assertEqual(manifest["derived_snapshot_person_n"], 1)
        self.assertEqual(manifest["peak_month_ties_incomplete_n"], 1)
        frame = data.load_frame(self.root, "development").set_index("canonical_id")
        self.assertEqual(frame.loc["22", "history_source_provider"], "lichess_fide_history")
        self.assertEqual(frame.loc["22", "derived_snapshot_record_n"], 1)
        self.assertFalse(frame.loc["22", "peak_periods_complete"])
        history = pd.read_csv(self.root / manifest["normalized_history"]["path"])
        derived = next(json.loads(row)[0] for row in history.source_records if json.loads(row)[0].get("derived_state"))
        self.assertEqual(derived["derived_from_month"], "2003-04")

    def test_input_hash_and_original_person_tampering_rejected(self):
        self.build()
        self.mutate_frame("development", lambda f: f.__setitem__("exact_dob_frozen", ["1980-02-04", "1980-02-03"]))
        with self.assertRaisesRegex(ValueError, "changed original person field"):
            data.load_frame(self.root, "development")

    def test_below_snapshot_and_cross_role_identity_tampering_rejected(self):
        self.build()
        self.mutate_frame("development", lambda f: f.__setitem__("rating", ["2499", "2520"]))
        with self.assertRaisesRegex(ValueError, "below original snapshot"):
            data.load_frame(self.root, "development")
        path = self.root / data.DATA / "data_manifest.json"
        manifest = data.read_json(path)
        manifest["roles"]["primary_new"]["wikidata_person_qids"] = ["Q11"]
        data.write_json(path, manifest)
        with self.assertRaisesRegex(ValueError, "identities overlap"):
            data.load_frame(self.root, "development")

    def test_failed_identity_audit_writes_failure_without_ready_manifest(self):
        self.historical["audit"]["fatal_issues"] = [{"type": "ambiguous_historical_alias"}]
        with self.assertRaisesRegex(ValueError, "unresolved fatal"):
            self.build()
        audit = data.read_json(self.root / data.DATA / "dataset_build_audit.json")
        self.assertEqual(audit["status"], "failed_requires_audit")
        self.assertFalse((self.root / data.DATA / "data_manifest.json").exists())

    def test_incomplete_historical_coverage_cannot_produce_ready_manifest(self):
        self.historical["coverage"]["first_official_period"] = "2002-01"
        with self.assertRaisesRegex(ValueError, "coverage is incomplete"):
            self.build()
        self.assertFalse((self.root / data.DATA / "data_manifest.json").exists())

    def test_above_peak_conflicts_audited_without_dropping_people(self):
        self.historical["records"].append(record("2003-04", 2900, source="olimpbase_transcription"))
        with self.assertRaises(data.DatasetBuildError):
            self.build()
        audit = data.read_json(self.root / data.DATA / "dataset_build_audit.json")
        self.assertEqual(audit["people"], 3)
        self.assertEqual(audit["labeled_people"], 2)
        self.assertEqual(audit["issues"][0]["canonical_id"], "11")
        self.assertFalse((self.root / data.DATA / "data_manifest.json").exists())

    def test_below_peak_conflict_retained_in_ready_dataset_and_audit(self):
        self.historical["records"].extend([record("1980-01", 2410, source="olimpbase_transcription"),
            record("1980-01", 2470, source="olimpbase_transcription")])
        self.historical["audit"]["unresolved_period_conflicts"] = [{"canonical_id": "11", "period": "1980-01",
            "candidate_ratings": [2410, 2470]}]
        manifest = self.build()
        self.assertEqual(manifest["ambiguous_period_n"], 1)
        self.assertEqual(manifest["ambiguous_period_people_n"], 1)
        self.assertEqual(manifest["period_conflict_resolution_policy"], data.CONFLICT_POLICY)
        frame = data.load_frame(self.root, "development").set_index("canonical_id")
        self.assertEqual(frame.loc["11", "rating"], 2800)
        self.assertEqual(frame.loc["11", "ambiguous_period_n"], 1)
        self.assertEqual(frame.loc["11", "ambiguous_periods"], "1980-01")
        history = pd.read_csv(self.root / manifest["normalized_history"]["path"], dtype={"canonical_id": str})
        row = history[(history.canonical_id == "11") & (history.period == "1980-01")].iloc[0]
        self.assertTrue(pd.isna(row.rating))
        self.assertEqual(json.loads(row.candidate_ratings), [2410, 2470])
        candidates = json.loads(row.source_records)
        self.assertEqual([x["rating"] for x in candidates], [2410, 2470])
        self.assertTrue(all(x["period_rating_not_selected"] for x in candidates))
        audit = data.read_json(self.root / manifest["audit"]["path"])
        self.assertEqual(audit["ambiguous_period_resolutions"][0]["confirmed_peak"], 2800)

if __name__ == "__main__":
    unittest.main()
