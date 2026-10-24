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
    for source_provider in data.API_PROVIDERS:
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

def snapshot_disagreement_fixture(base, people, cid="11", official_elo=None, independent_peak=None):
    """Use the real collector evidence writer with synthetic direct chart bytes."""
    import collect_fide as collector
    p = people[cid]
    p.setdefault("source_roster", "original_roster.csv")
    p.setdefault("source_roster_sha256", "f" * 64)
    official_elo = p["snapshot_elo"] + 1 if official_elo is None else official_elo
    independent_peak = p["snapshot_elo"] + 20 if independent_peak is None else independent_peak
    chart = [{"date_2": "2003-04-01", "rating": p["snapshot_elo"], "name": p["name"], "id_number": cid},
        {"date_2": p["snapshot"] + "-01", "rating": official_elo, "name": p["name"], "id_number": None},
        {"date_2": "2023-12-01", "rating": independent_peak, "name": p["name"], "id_number": None},
        {"date_2": "2024-01-01", "rating": independent_peak + 300, "name": p["name"], "id_number": None}]
    raw = json.dumps(chart).encode()
    url = f"https://ratings.fide.com/a_chart_data.phtml?event={cid}&period=0"
    official = collector._coverage_evidence(base, cid, raw, {"source_provider": "fide_official_chart", "source_url": url, "http_status": 200})
    mirror = collector._coverage_evidence(base, cid, json.dumps({"standard": [2013010000 + p["snapshot_elo"]]}).encode(),
        {"source_provider": "lichess_fide_history", "source_url": f"https://lichess.org/api/fide/player/{cid}/ratings"})
    (base / "raw" / f"{cid}.json.gz").write_bytes(gzip.compress(raw, mtime=0))
    normalized_path = base / "normalized" / f"{cid}.json"
    normalized = {"canonical_id": cid, "source_raw_sha256": official["raw_sha256"], "source_provider": "fide_official_chart",
        "label_cutoff_month": data.CUTOFF, "peak_months_complete": True,
        "standard_history": [{"month": row["date_2"][:7], "standard_elo": row["rating"], "source_point": True} for row in chart]}
    data.write_json(normalized_path, normalized)
    proof = {"rule_id": data.SNAPSHOT_DISAGREEMENT_RULE, "status": "officially_verified_pending_peak_identifiability",
        "canonical_id": cid, "snapshot_month": p["snapshot"], "frozen_snapshot_elo": p["snapshot_elo"],
        "official_snapshot_elo": official_elo, "frozen_name": p["name"], "official_name": p["name"],
        "frozen_source_roster": p["source_roster"], "frozen_source_roster_sha256": p["source_roster_sha256"],
        "official_evidence": official, "prior_evidence": [mirror], "identity_witness_month": "2003-04"}
    entry_path = base / "entries" / f"{cid}.json"
    entry = data.read_json(entry_path)
    entry.update(source_provider="fide_official_chart", source_url=url, raw_sha256=official["raw_sha256"],
        normalized_history_sha256=data.sha256(normalized_path), snapshot_disagreement=proof,
        snapshot_audit_required=False, source_roster=p["source_roster"], source_roster_sha256=p["source_roster_sha256"])
    data.write_json(entry_path, entry)
    reseal_acquisition(base)
    return proof

def list_supplement_fixture(root, base, people, cid="22"):
    """Exercise the actual availability-only helper with a sealed synthetic payload."""
    import apply_list_supplements as supplements
    p, rows, ledger = people[cid], [], []
    periods = [f"{year}-{month:02d}" for year in (2010, 2011) for month in (1, 3, 5, 7, 9, 11)]
    periods += [f"2012-{month:02d}" for month in (1, 3, 5, 7, 8, 9, 10, 11, 12)]
    periods += [f"2013-{month:02d}" for month in range(1, 13)]
    for month in ["2003-07", "2009-11", *periods]:
        primary = month >= "2010-01"
        source = "fide_official_list_archive" if primary else "olimpbase_transcription"
        url = (f"https://ratings.fide.com/download/standard_{month.replace('-', '')}.zip" if primary
            else "https://www.olimpbase.org/Elo/data/elo2002-2009.zip")
        digest = hashlib.sha256(month.encode()).hexdigest()
        member = month + ".txt"
        elo = p["snapshot_elo"] + (20 if month == "2010-05" else 0)
        text = f"{cid};{p['name']};{elo}"
        row = {"month": month, "standard_elo": elo, "source_point": True, "source": source,
            "source_url": url, "archive_sha256": digest, "archive_member": member,
            "source_line_number": 2, "source_line": text}
        rows.append(row)
        ledger.append({"period": month, "url": url, "sha256": digest, "member": member,
            "source": source, "source_line_number": 2, "source_line": text, "header": "ID;NAME;RATING", "bytes": 100})
    snapshot = next(row for row in rows if row["month"] == p["snapshot"])
    coverage = {"official_list_periods": periods, "official_list_first": periods[0], "official_list_last": periods[-1],
        "historical_transcription_first": "2003-07", "historical_transcription_last": "2009-11",
        "post_death_monthly_2014_2023_not_claimed": True}
    termination = {"date": "2013-08-08", "birth_date": p["exact_dob_frozen"],
        "source_type": "official_national_federation_obituary", "source_url": "https://www.ruchess.ru/news/all/pogib_igor_kurnosov/",
        "source_sha256": "b" * 64, "source_publication_date": "2013-08-08", "excerpt": "Synthetic obituary fixture",
        "posthumous_2014_2023_monthly_coverage_claimed": False, "coverage_note": "Career end evidenced; later monthly lists not claimed"}
    payload = {"protocol_id": "chess-peak-official-list-supplement-v1", "canonical_id": cid, "name": p["name"],
        "standard_history": rows, "archive_ledger": ledger, "coverage": coverage, "career_termination": termination,
        "frozen_snapshot": {"month": p["snapshot"], "rating": p["snapshot_elo"], "archive_url": snapshot["source_url"],
            **{key: snapshot[key] for key in ("archive_sha256", "archive_member", "source_line_number", "source_line")}}}
    path = root / data.STUDY / "supplements" / f"fixture_{cid}.json"
    data.write_json(path, payload)
    entry_path = base / "entries" / f"{cid}.json"
    prior = data.read_json(entry_path)
    prior.update(status="failed", error_type="FetchFailure", error="Synthetic provider-unavailable fixture")
    data.write_json(entry_path, prior)
    reseal_acquisition(base)
    manifest_path = base / "acquisition_manifest.json"
    manifest = data.read_json(manifest_path)
    manifest.update(status="history_acquisition_failed", failed_n=1)
    data.write_json(manifest_path, manifest)
    with patch.object(supplements, "load_roster", return_value=(list(people.values()), {})):
        supplements.apply_list_supplements(root, base)
    return payload

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
        self.assertFalse(label["peak_periods_complete"])

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
    def test_legacy_provider_counts_can_omit_new_zero_provider(self):
        with tempfile.TemporaryDirectory() as temporary:
            base, people = Path(temporary), {"11": person()}
            acquisition_fixture(base, people, {"11": "lichess_fide_history"})
            path = base / "acquisition_manifest.json"
            manifest = data.read_json(path)
            del manifest["source_provider_counts"]["fide_official_list_archive"]
            data.write_json(path, manifest)
            entries, _ = data.read_acquisition(base, people)
            self.assertEqual(set(entries), {"11"})

    def test_real_collector_contract_stages_disagreement_and_reader_verifies_it(self):
        import collect_fide as collector
        with tempfile.TemporaryDirectory() as temporary:
            base, people = Path(temporary), {"11": person()}
            acquisition_fixture(base, people)
            snapshot_disagreement_fixture(base, people)
            official_raw = gzip.decompress((base / "raw/11.json.gz").read_bytes())
            mirror_raw = json.dumps({"standard": [2003042500, 2013012501, 2023122520]}).encode()
            collector.save_cache(base, "11", mirror_raw, {"source_provider": "lichess_fide_history",
                "source_url": collector.lichess_url("11"), "http_status": 200, "fetched_at_utc": "2026-01-01T00:00:00+00:00"})
            official_meta = {"source_provider": "fide_official_chart", "source_url": collector.chart_url("11"),
                "http_status": 200, "fetched_at_utc": "2026-01-01T00:00:00+00:00"}
            with patch.object(collector, "fetch_chart", return_value=(official_raw, official_meta)) as fetch:
                entry = collector.process_person(people["11"], base, None)
            self.assertEqual(fetch.call_count, 1)
            self.assertEqual(entry["status"], "history_acquired")
            self.assertFalse(entry["snapshot_audit_required"])
            reseal_acquisition(base)
            entries, _ = data.read_acquisition(base, people)
            acquired = entries["11"]
            label, _, _ = data.combine_person(people["11"], acquired["records"], [], acquired["snapshot_disagreement"])
            self.assertEqual(label["rating"], 2520)
            self.assertEqual(label["ambiguous_periods"], "2013-01")

    def test_official_disagreement_proof_reparsed_and_frozen_candidate_retained(self):
        with tempfile.TemporaryDirectory() as temporary:
            base, people = Path(temporary), {"11": person()}
            acquisition_fixture(base, people)
            proof = snapshot_disagreement_fixture(base, people)
            entries, _ = data.read_acquisition(base, people)
            info = entries["11"]
            self.assertEqual(info["snapshot_disagreement"], proof)
            frozen = next(row for row in info["records"] if row["source"] == "frozen_cohort_snapshot")
            self.assertEqual(frozen["rating"], 2500)
            self.assertEqual(frozen["source_roster_sha256"], people["11"]["source_roster_sha256"])
            label, rows, _ = data.combine_person(people["11"], info["records"], [], proof)
            self.assertEqual(label["rating"], 2520)
            self.assertEqual(label["peak_periods"], "2023-12")
            self.assertEqual(rows[1]["candidate_ratings"], [2500, 2501])
            self.assertIsNone(rows[1]["rating"])
            self.assertEqual(label["history_source_provider"], "fide_official_chart")

    def test_official_disagreement_proof_rejects_identity_month_values_and_source_tampering(self):
        for field, value in (("frozen_source_roster_sha256", "0" * 64), ("official_name", "Other person"),
                ("identity_witness_month", "2023-12"), ("official_snapshot_elo", 2502)):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as temporary:
                base, people = Path(temporary), {"11": person()}
                acquisition_fixture(base, people)
                snapshot_disagreement_fixture(base, people)
                path = base / "entries/11.json"
                entry = data.read_json(path)
                entry["snapshot_disagreement"][field] = value
                data.write_json(path, entry)
                reseal_acquisition(base)
                with self.assertRaises(ValueError):
                    data.read_acquisition(base, people)

    def test_official_disagreement_cannot_trust_a_resealed_normalized_value(self):
        with tempfile.TemporaryDirectory() as temporary:
            base, people = Path(temporary), {"11": person()}
            acquisition_fixture(base, people)
            snapshot_disagreement_fixture(base, people)
            path = base / "normalized/11.json"
            normalized = data.read_json(path)
            normalized["standard_history"][1]["standard_elo"] += 1
            data.write_json(path, normalized)
            entry_path = base / "entries/11.json"
            entry = data.read_json(entry_path)
            entry["normalized_history_sha256"] = data.sha256(path)
            data.write_json(entry_path, entry)
            reseal_acquisition(base)
            with self.assertRaisesRegex(ValueError, "raw or normalized rating values"):
                data.read_acquisition(base, people)

    def test_disagreement_uses_peak_identifiability_without_rating_tolerance(self):
        for official_elo, independent_peak, accepted in ((2501, 2500, False), (2501, 2501, True), (2530, 2600, True)):
            with self.subTest(official_elo=official_elo, independent_peak=independent_peak), tempfile.TemporaryDirectory() as temporary:
                base, people = Path(temporary), {"11": person()}
                acquisition_fixture(base, people)
                proof = snapshot_disagreement_fixture(base, people, official_elo=official_elo, independent_peak=independent_peak)
                entries, _ = data.read_acquisition(base, people)
                if accepted:
                    label, _, _ = data.combine_person(people["11"], entries["11"]["records"], [], proof)
                    self.assertEqual(label["rating"], independent_peak)
                    self.assertEqual(label["peak_periods"], "2023-12")
                    self.assertEqual(label["peak_periods_complete"], independent_peak > max(2500, official_elo))
                else:
                    with self.assertRaisesRegex(ValueError, "can change the confirmed peak"):
                        data.combine_person(people["11"], entries["11"]["records"], [], proof)
                with self.assertRaisesRegex(ValueError, "lacks verified official disagreement proof"):
                    data.combine_person(people["11"], entries["11"]["records"], [])

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

    def test_official_snapshot_disagreement_preserves_frozen_fields_and_audits_peak(self):
        p = self.people["22"]
        p.update(source_roster=self.sources["development"]["cohort"]["path"],
            source_roster_sha256=self.sources["development"]["cohort"]["sha256"])
        proof = snapshot_disagreement_fixture(self.acquisition, self.people, cid="22")
        manifest = self.build()
        self.assertEqual(manifest["snapshot_disagreement_n"], 1)
        detail = manifest["snapshot_disagreements"][0]
        self.assertEqual(detail["candidate_ratings"], [2500, 2501])
        self.assertEqual(detail["identified_peak"], 2520)
        self.assertFalse(detail["snapshot_rating_selected"])
        audit = data.read_json(self.root / manifest["audit"]["path"])
        self.assertEqual(audit["snapshot_disagreement_proofs"], {"22": proof})
        frame = data.load_frame(self.root, "development").set_index("canonical_id")
        self.assertEqual(frame.loc["22", "snapshot_rating"], 2500)
        self.assertEqual(frame.loc["22", "rating"], 2520)
        self.assertEqual(frame.loc["22", "ambiguous_periods"], "2013-01")
        self.assertNotIn("2013-01", frame.loc["22", "peak_periods"])

    def test_actual_supplement_helper_and_reader_keep_primary_and_secondary_sources_distinct(self):
        payload = list_supplement_fixture(self.root, self.acquisition, self.people)
        manifest = self.build()
        self.assertEqual(manifest["list_supplement_n"], 1)
        details = manifest["list_supplements"]["22"]
        self.assertEqual(details["coverage"], payload["coverage"])
        self.assertEqual(details["career_termination"], payload["career_termination"])
        self.assertEqual(details["archive_ledger"], payload["archive_ledger"])
        self.assertEqual(manifest["history_source_provider_counts"]["fide_official_list_archive"], 1)
        frame = data.load_frame(self.root, "development").set_index("canonical_id")
        self.assertEqual(frame.loc["22", "history_source_provider"], "fide_official_list_archive")
        self.assertEqual(frame.loc["22", "official_list_history_n"], 33)
        self.assertEqual(frame.loc["22", "olimpbase_history_n"], 2)
        self.assertEqual(frame.loc["22", "official_chart_history_n"], 0)
        self.assertEqual(frame.loc["22", "fide_history_n"], 33)
        self.assertFalse(frame.loc["22", "peak_periods_complete"])
        self.assertEqual(frame.loc["22", "rating"], 2520)
        history = pd.read_csv(self.root / manifest["normalized_history"]["path"], dtype={"canonical_id": str})
        selected = history[history.canonical_id == "22"]
        self.assertEqual(set(selected.sources), {"fide_official_list_archive", "olimpbase_transcription"})

    def test_list_supplement_rejects_resealed_normalized_source_override(self):
        list_supplement_fixture(self.root, self.acquisition, self.people)
        path = self.acquisition / "normalized/22.json"
        normalized = data.read_json(path)
        normalized["standard_history"][0]["source"] = "fide_official_list_archive"
        data.write_json(path, normalized)
        entry_path = self.acquisition / "entries/22.json"
        entry = data.read_json(entry_path)
        entry["normalized_history_sha256"] = data.sha256(path)
        data.write_json(entry_path, entry)
        reseal_acquisition(self.acquisition)
        with self.assertRaisesRegex(ValueError, "normalized rows differ"):
            self.build()

    def test_list_supplement_cannot_replace_identity_error_or_differ_from_repo_bytes(self):
        list_supplement_fixture(self.root, self.acquisition, self.people)
        entry_path = self.acquisition / "entries/22.json"
        entry = data.read_json(entry_path)
        prior_path = self.acquisition / entry["list_supplement"]["prior_api_entry_file"]
        prior = data.read_json(prior_path)
        prior["error_type"] = "SourceIntegrityError"
        data.write_json(prior_path, prior)
        entry["list_supplement"]["prior_api_entry_sha256"] = data.sha256(prior_path)
        data.write_json(entry_path, entry)
        reseal_acquisition(self.acquisition)
        with self.assertRaisesRegex(ValueError, "identity-conflicting"):
            self.build()
        prior["error_type"] = "FetchFailure"
        data.write_json(prior_path, prior)
        entry["list_supplement"]["prior_api_entry_sha256"] = data.sha256(prior_path)
        data.write_json(entry_path, entry)
        reseal_acquisition(self.acquisition)
        supplement = self.root / entry["list_supplement"]["supplement_file"]
        supplement.write_text(supplement.read_text() + " ")
        with self.assertRaisesRegex(ValueError, "frozen repository bytes"):
            self.build()

    def test_disagreement_above_independent_peak_stops_and_keeps_proof_audit(self):
        p = self.people["22"]
        p.update(source_roster=self.sources["development"]["cohort"]["path"],
            source_roster_sha256=self.sources["development"]["cohort"]["sha256"])
        proof = snapshot_disagreement_fixture(self.acquisition, self.people, cid="22", independent_peak=2500)
        with self.assertRaises(data.DatasetBuildError):
            self.build()
        audit = data.read_json(self.root / data.DATA / "dataset_build_audit.json")
        self.assertEqual(audit["snapshot_disagreement_proofs"]["22"], proof)
        self.assertIsNone(audit["snapshot_disagreements"][0]["identified_peak"])
        self.assertFalse((self.root / data.DATA / "data_manifest.json").exists())

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
        self.assertEqual(manifest["history_source_provider_counts"], {"fide_official_chart": 2, "lichess_fide_history": 1,
            "fide_official_list_archive": 0})
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
