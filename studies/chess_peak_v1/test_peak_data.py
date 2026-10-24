"""Synthetic peak/provenance checks only; no acquisition or model fitting."""
import csv
from datetime import datetime
import gzip
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
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

def list_supplement_fixture(root, base, people, cid="22", apply=True):
    """Exercise the actual availability-only helper with a sealed synthetic payload."""
    import apply_list_supplements as supplements
    p, rows, ledger = people[cid], [], []
    periods = [f"{year}-{month:02d}" for year in (2010, 2011) for month in (1, 3, 5, 7, 9, 11)]
    periods += [f"2012-{month:02d}" for month in (1, 3, 5, 7, 8, 9, 10, 11, 12)]
    periods += [f"2013-{month:02d}" for month in range(1, 13)]
    for month in ["2003-07", "2009-11", *periods]:
        primary = month >= "2010-01"
        source = "fide_official_list_archive" if primary else "olimpbase_transcription"
        month_tag = datetime.strptime(month, "%Y-%m").strftime("%b%Y").lower()
        url = (f"https://ratings.fide.com/download/standard_{month_tag}frl.zip" if primary
            else "https://www.olimpbase.org/Elo/data/elo2002-2009.zip")
        digest = hashlib.sha256(month.encode()).hexdigest()
        member = f"standard_{month_tag}frl.txt" if primary else month + ".txt"
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
    if apply:
        with patch.object(supplements, "load_roster", return_value=(list(people.values()), {})):
            supplements.apply_list_supplements(root, base)
    return payload

def gap_bridge_fixture(root, base, people, cid="22", alias=None, apply=True, absent_period=None, zero_prefix=False, api_last_period="2025-01"):
    import collect_fide as collector
    import apply_list_supplements as supplements
    p = people[cid]
    payload = list_supplement_fixture(root, base, people, cid, apply=False)
    periods = data._official_bridge_periods("2015-02")
    payload["standard_history"] = [row for row in payload["standard_history"] if row["source"] == "olimpbase_transcription"]
    payload["archive_ledger"] = [row for row in payload["archive_ledger"] if row["source"] == "olimpbase_transcription"]
    source_name = alias or p["name"]
    for month in periods:
        tag = datetime.strptime(month, "%Y-%m").strftime("%b%Y").lower()
        url = f"https://ratings.fide.com/download/standard_{tag}frl.zip"
        digest, member = hashlib.sha256(month.encode()).hexdigest(), f"standard_{tag}frl.txt"
        header = "  ID_NUMBER NAME                             TITLE COUNTRY RATE  GAMES BIRTHDAY   FLAG"
        line = "  " + f"{cid:<10}{source_name:<33}{'g':<6}{'LAT':<8}{p['snapshot_elo']:<6}{3:<6}{int(p['exact_dob_frozen'][:4]):<11}n   "
        ledger = {"period": month, "url": url, "sha256": digest, "member": member, "source": "fide_official_list_archive",
            "source_line_number": 2, "source_line": line, "header": header, "bytes": 100}
        if month == absent_period:
            ledger.update(player_unlisted=True, searched_canonical_id=cid, source_line_number=None, source_line=None, selected_row=None)
        else:
            payload["standard_history"].append({"month": month, "standard_elo": p["snapshot_elo"], "source_point": True,
                "source": "fide_official_list_archive", "source_url": url, "archive_sha256": digest, "archive_member": member,
                "source_line_number": 2, "source_line": line, "source_header": header,
                "source_name": source_name, "source_birth_year": int(p["exact_dob_frozen"][:4])})
        payload["archive_ledger"].append(ledger)
    end_stamp = int(api_last_period.replace("-", ""))
    raw_points = [value for value in (([2015010000] if zero_prefix else []) + [2015022510, 2016012530, 2023122540, 2025012550])
        if value // 10000 <= end_stamp]
    if raw_points[-1] // 10000 != end_stamp:
        raw_points.append(end_stamp * 10000 + 2540)
    raw = json.dumps({"standard": raw_points}).encode()
    metadata = collector.save_cache(base, cid, raw, {"source_provider": "lichess_fide_history",
        "source_url": collector.lichess_url(cid), "http_status": 200, "fetched_at_utc": "2026-01-01T00:00:00+00:00"})
    evidence = collector._coverage_evidence(base, cid, raw, metadata)
    parsed = collector.parse_lichess_history(raw, cid, snapshot=p["snapshot"])
    original = {"canonical_id": cid, "source_raw_sha256": metadata["raw_sha256"], "source_provider": "lichess_fide_history",
        "label_cutoff_month": data.CUTOFF, "standard_history": parsed["all_standard_history"],
        "history_compression": parsed["history_compression"], "peak_months_complete": False}
    original_path = base / "normalized" / f"{cid}.json"
    data.write_json(original_path, original)
    entry_path = base / "entries" / f"{cid}.json"
    prior = {**p, "status": "history_acquired_requires_snapshot_audit", "source_provider": "lichess_fide_history",
        "source_url": collector.lichess_url(cid), "raw_sha256": metadata["raw_sha256"], "raw_bytes": len(raw),
        "normalized_history_file": f"normalized/{cid}.json", "normalized_history_sha256": data.sha256(original_path),
        "snapshot_in_history": False, "snapshot_history_elo": None, "snapshot_audit_required": True,
        "snapshot_audit_reasons": ["frozen_snapshot_month_absent_from_official_chart_history", "rating_history_coverage_unresolved"],
        "source_coverage_audit": {"rule_id": data.COVERAGE_RULE, "reasons": ["lichess_missing_frozen_snapshot"],
            "unresolved": True, "selected_provider": "lichess_fide_history", "direct_source_coverage_checked": False,
            "sources": [evidence], "official_outcome": "unavailable"}}
    data.write_json(entry_path, prior)
    proof = {**{key: evidence[key] for key in ("source_provider", "raw_file", "raw_sha256", "gzip_sha256", "metadata_file", "metadata_sha256")},
        "source_url": collector.lichess_url(cid), "original_normalized_file": f"normalized/{cid}.json",
        "normalized_file": f"list-supplements/evidence/{cid}.api-normalized.json", "normalized_sha256": data.sha256(original_path),
        "original_entry_file": f"entries/{cid}.json", "entry_file": f"list-supplements/evidence/{cid}.api-entry.json",
        "entry_sha256": data.sha256(entry_path), "first_period": "2015-02", "last_available_period": api_last_period,
        "retained_through_cutoff_n": sum(row["month"] <= data.CUTOFF for row in original["standard_history"]),
        "excluded_future_point_n": sum(row["month"] > data.CUTOFF for row in original["standard_history"])}
    payload["api_history_evidence"] = proof
    for index, row in enumerate(original["standard_history"]):
        if row["month"] <= data.CUTOFF:
            raw_index = next(i for i, value in enumerate(raw_points)
                if str(value // 10000) == row["month"].replace("-", "") and value % 10000 == row["standard_elo"])
            payload["standard_history"].append({**row, "source": "lichess_fide_history", "source_url": collector.lichess_url(cid),
                "source_raw_sha256": metadata["raw_sha256"], "api_history_point_index": index,
                "api_raw_point_index": raw_index, "api_raw_packed_value": raw_points[raw_index]})
    payload["coverage"].update(mode=data.GAP_MODE, official_list_periods=periods,
        official_list_first=periods[0], official_list_last=periods[-1], **data.source_end_coverage(api_last_period),
        complete_through_cutoff=api_last_period >= data.CUTOFF)
    payload["coverage"].pop("career_termination_verified")
    payload["coverage"].pop("post_death_monthly_2014_2023_not_claimed", None)
    payload.pop("career_termination")
    frozen = next(row for row in payload["standard_history"] if row["month"] == p["snapshot"])
    payload["frozen_snapshot"] = {"month": p["snapshot"], "rating": p["snapshot_elo"], "archive_url": frozen["source_url"],
        **{key: frozen[key] for key in ("archive_sha256", "archive_member", "source_line_number", "source_line")}}
    if alias:
        payload["identity_aliases"] = [{"canonical_id": cid, "frozen_name": p["name"], "source_name": alias,
            "frozen_dob": p["exact_dob_frozen"], "source_birth_year": int(p["exact_dob_frozen"][:4]),
            "decision": "explicit_registered_name_variant_with_same_exact_FIDE_ID_and_original_list_birthyear",
            "witness_points": [next(row for row in payload["standard_history"] if row["source"] == "fide_official_list_archive")]}]
    path = root / data.STUDY / "supplements" / f"fixture_{cid}.json"
    data.write_json(path, payload)
    reseal_acquisition(base)
    if apply:
        with patch.object(supplements, "load_roster", return_value=(list(people.values()), {})):
            supplements.apply_list_supplements(root, base)
    return payload

def point_adjudication_fixture(root, base, people, historical, cid="22"):
    """A small real ZIP for each original published point, with fixed columns."""
    p, evidence = people[cid], []
    for month, elo in (("2001-01", 2532), ("2001-04", 2596)):
        tag = {"2001-01": "JAN01", "2001-04": "APR01"}[month]
        header = f"  ID_NUMBER NAME                             TITLE COUNTRY {tag} GAMES BIRTHDAY   FLAG"
        birthday = ".".join(reversed(p["exact_dob_frozen"].split("-")))
        line = "  " + f"{cid:<10}{p['name']:<33}{'g':<6}{'LAT':<8}{elo:<6}{3:<6}{birthday:<11}n   "
        archive_path = root / data.DATA / "source_archives" / (tag.lower() + "frl.zip")
        archive_path.parent.mkdir(parents=True, exist_ok=True)
        member = tag + "FRL.TXT"
        with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(member, (header + "\r\n" + line + "\r\n").encode("latin-1"))
        evidence.append({"month": month, "standard_elo": elo, "source_point": True, "source": "fide_official_list_archive",
            "source_url": f"https://ratings.fide.com/download/{tag.lower()}frl.zip",
            "archive_file": archive_path.relative_to(root).as_posix(), "archive_sha256": data.sha256(archive_path),
            "archive_member": member, "source_line_number": 2, "source_line": line, "source_header": header,
            "source_header_period_mismatch": False, "publication_period_evidence": "Exact URL, member and header month",
            "identity_anchor": "Exact ID/name and original birthday field", "source_country": "LAT",
            "source_birth_date": p["exact_dob_frozen"]})
    document = {"protocol_id": "chess-peak-original-list-point-adjudication-v1", "canonical_id": cid, "name": p["name"],
        "period": "2001-01", "selected_rating": 2532, "rejected_ratings": [2601], "decision": data.POINT_ADJUDICATION_POLICY,
        "evidence": evidence[0], "corroborating_points": [evidence[1]], "method": "Original list source priority before analysis",
        "original_records_preserved": True, "identity_evidence": {"canonical_id": cid, "source_name": p["name"],
            "frozen_dob": p["exact_dob_frozen"]}}
    path = root / data.STUDY / "adjudications" / f"fixture_{cid}_2001-01.json"
    data.write_json(path, document)
    acquisition_fixture(base, people, {cid: "lichess_fide_history"})
    normalized_path = base / "normalized" / f"{cid}.json"
    normalized = data.read_json(normalized_path)
    normalized["standard_history"] += [{"month": "2001-01", "standard_elo": 2601, "source_point": True},
        {"month": "2001-04", "standard_elo": 2596, "source_point": True}]
    normalized["standard_history"].sort(key=lambda row: row["month"])
    data.write_json(normalized_path, normalized)
    entry_path = base / "entries" / f"{cid}.json"
    entry = data.read_json(entry_path)
    entry["normalized_history_sha256"] = data.sha256(normalized_path)
    data.write_json(entry_path, entry)
    reseal_acquisition(base)
    historical["records"] += [record("2001-01", 2532, cid, "olimpbase_transcription"),
        record("2001-04", 2596, cid, "olimpbase_transcription")]
    return path, document

class CombineTests(unittest.TestCase):
    def test_cross_file_corroboration_cannot_override_another_original_point(self):
        modern = [record("2001-01", 2601), record("2001-04", 2602), record("2013-01", 2500), record("2023-12", 2700)]
        historical = [record("2001-01", 2532, source="olimpbase_transcription"), record("2001-04", 2596, source="olimpbase_transcription")]
        def adjudication(month, selected, rejected, extra=()):
            return {"canonical_id": "11", "period": month, "selected_rating": selected, "rejected_ratings": [rejected],
                "decision": data.POINT_ADJUDICATION_POLICY, "source_file": month + ".json", "source_file_sha256": "f" * 64,
                "verified_points": [record(month, selected, source="fide_official_list_archive"), *extra]}
        jan = adjudication("2001-01", 2532, 2601, [record("2001-04", 2533, source="fide_official_list_archive")])
        apr = adjudication("2001-04", 2596, 2602)
        for decisions in ({"2001-04": apr, "2001-01": jan}, {"2001-01": jan, "2001-04": apr}):
            with self.assertRaisesRegex(ValueError, "cross-file corroboration"):
                data.combine_person(person(), modern, historical, adjudications=decisions)

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
    def test_old_gamesborn_layout_keeps_fixed_columns_under_july_caption(self):
        p = person()
        line = f"{p['canonical_id']:>8}  {p['name']:<34}{'g':<4}{'LAT':<5}{2500:<6}{5:<5}{1980:<6}"
        row = {"month": "2011-07", "standard_elo": 2500, "source_name": p["name"], "source_birth_year": 1980,
            "source_line": line, "source_header": "ID number Name                              TitlFed  July11 GamesBorn  Flag",
            "source_header_period_mismatch": False}
        self.assertEqual(data._primary_supplement_identity(row, p), p["name"])
        row["standard_elo"] = 1980  # Present as birthday, not the rating column.
        with self.assertRaisesRegex(ValueError, "parsed rating column"):
            data._primary_supplement_identity(row, p)

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
        self.assertEqual(frame.loc["22", "verified_source_window_end"], "2013-12")
        self.assertTrue(frame.loc["22", "source_tail_incomplete"])
        self.assertTrue(frame.loc["22", "career_termination_verified"])
        history = pd.read_csv(self.root / manifest["normalized_history"]["path"], dtype={"canonical_id": str})
        selected = history[history.canonical_id == "22"]
        self.assertEqual(set(selected.sources), {"fide_official_list_archive", "olimpbase_transcription"})

    def test_ordinary_api_early_end_is_uniformly_flagged_without_dropping_or_extending(self):
        path = self.acquisition / "normalized/22.json"
        normalized = data.read_json(path)
        normalized["standard_history"] = [row for row in normalized["standard_history"] if row["month"] <= "2013-01"]
        normalized["standard_history"].append({"month": "2020-06", "standard_elo": 2530})
        data.write_json(path, normalized)
        entry_path = self.acquisition / "entries/22.json"
        entry = data.read_json(entry_path)
        entry["normalized_history_sha256"] = data.sha256(path)
        data.write_json(entry_path, entry)
        reseal_acquisition(self.acquisition)
        manifest = self.build()
        frame = data.load_frame(self.root, "development").set_index("canonical_id")
        self.assertEqual(frame.loc["22", "rating"], 2530)
        self.assertEqual(frame.loc["22", "verified_source_window_end"], "2020-06")
        self.assertTrue(frame.loc["22", "source_tail_incomplete"])
        self.assertFalse(frame.loc["22", "source_window_reaches_cutoff"])
        self.assertFalse(frame.loc["22", "career_termination_verified"])
        self.assertEqual(frame.loc["22", "history_last_period"], "2020-06")
        self.assertEqual(frame.loc["11", "verified_source_window_end"], "2024-01")
        self.assertTrue(frame.loc["11", "source_window_reaches_cutoff"])
        audit = manifest["source_end_coverage"]
        self.assertEqual(audit["early_ending_n"], 1)
        self.assertEqual(audit["early_ending_person_ids_by_role"], {"development": ["22"], "primary_new": []})
        history = pd.read_csv(self.root / manifest["normalized_history"]["path"], dtype={"canonical_id": str})
        self.assertEqual(max(history[history.canonical_id == "22"].period), "2020-06")

    def test_gap_api_early_end_accepted_as_recorded_peak_with_no_tail_extrapolation(self):
        gap_bridge_fixture(self.root, self.acquisition, self.people, api_last_period="2020-12")
        manifest = self.build()
        frame = data.load_frame(self.root, "development").set_index("canonical_id")
        self.assertEqual(frame.loc["22", "rating"], 2540)
        self.assertEqual(frame.loc["22", "verified_source_window_end"], "2020-12")
        self.assertTrue(frame.loc["22", "source_tail_incomplete"])
        self.assertFalse(frame.loc["22", "career_termination_verified"])
        self.assertEqual(frame.loc["22", "history_last_period"], "2020-12")
        self.assertEqual(manifest["source_end_coverage"]["early_ending_n"], 1)
        history = pd.read_csv(self.root / manifest["normalized_history"]["path"], dtype={"canonical_id": str})
        self.assertEqual(max(history[history.canonical_id == "22"].period), "2020-12")
        self.assertIn("not guarantee continuous", manifest["source_end_coverage"]["cutoff_meaning"])

    def test_gap_bridge_retains_complete_api_window_and_original_provenance(self):
        payload = gap_bridge_fixture(self.root, self.acquisition, self.people, zero_prefix=True)
        manifest = self.build()
        details = manifest["list_supplements"]["22"]
        self.assertEqual(details["coverage"]["mode"], data.GAP_MODE)
        self.assertIsNone(details["career_termination"])
        self.assertEqual(details["adjudication"]["prior_source_coverage_audit"]["unresolved"], True)
        self.assertEqual(details["api_history_evidence"]["proof"], payload["api_history_evidence"])
        frame = data.load_frame(self.root, "development").set_index("canonical_id")
        self.assertEqual(frame.loc["22", "rating"], 2540)
        self.assertEqual(frame.loc["22", "snapshot_rating"], 2500)
        self.assertEqual(frame.loc["22", "official_list_history_n"], 46)
        self.assertEqual(frame.loc["22", "lichess_history_n"], 3)
        self.assertEqual(frame.loc["22", "olimpbase_history_n"], 2)
        self.assertEqual(frame.loc["22", "history_last_period"], "2023-12")
        self.assertEqual(frame.loc["22", "verified_source_window_end"], "2025-01")
        self.assertTrue(frame.loc["22", "source_window_reaches_cutoff"])
        history = pd.read_csv(self.root / manifest["normalized_history"]["path"], dtype={"canonical_id": str})
        api = history[(history.canonical_id == "22") & (history.period == "2023-12")].iloc[0]
        source = json.loads(api.source_records)[0]
        self.assertEqual(source["source"], "lichess_fide_history")
        self.assertEqual(source["source_raw_sha256"], payload["api_history_evidence"]["raw_sha256"])
        self.assertNotEqual(source["source_raw_sha256"], source["compiled_source_raw_sha256"])
        self.assertEqual(source["api_history_point_index"], 2)
        self.assertEqual(source["api_raw_point_index"], 3)
        self.assertFalse(source["peak_months_complete"])

    def test_gap_bridge_explicit_alias_and_unlisted_period_are_evidence_not_ratings(self):
        payload = gap_bridge_fixture(self.root, self.acquisition, self.people, alias="Player 22, Dr.", absent_period="2010-01")
        manifest = self.build()
        frame = data.load_frame(self.root, "development").set_index("canonical_id")
        self.assertEqual(frame.loc["22", "official_list_history_n"], 45)
        self.assertEqual(frame.loc["22", "rating"], 2540)
        details = manifest["list_supplements"]["22"]
        self.assertEqual(details["identity_aliases"], payload["identity_aliases"])
        self.assertEqual(len(details["coverage"]["official_list_periods"]), 46)
        self.assertTrue(next(row for row in details["archive_ledger"] if row["period"] == "2010-01")["player_unlisted"])

    def test_gap_bridge_missing_period_or_unregistered_alias_stops(self):
        payload = gap_bridge_fixture(self.root, self.acquisition, self.people, alias="Player 22, Dr.", apply=False)
        path = self.root / data.STUDY / "supplements/fixture_22.json"
        payload.pop("identity_aliases")
        data.write_json(path, payload)
        import apply_list_supplements as supplements
        before = (self.acquisition / "entries/22.json").read_bytes()
        old_normalized = (self.acquisition / "normalized/22.json").read_bytes()
        with patch.object(supplements, "load_roster", return_value=(list(self.people.values()), {})):
            with self.assertRaisesRegex(ValueError, "without an explicit verified alias"):
                supplements.apply_list_supplements(self.root, self.acquisition)
        self.assertEqual((self.acquisition / "entries/22.json").read_bytes(), before)
        self.assertEqual((self.acquisition / "normalized/22.json").read_bytes(), old_normalized)

    def test_gap_bridge_cannot_skip_a_published_list_or_forge_absence_identity(self):
        payload = gap_bridge_fixture(self.root, self.acquisition, self.people, apply=False, absent_period="2010-01")
        path = self.root / data.STUDY / "supplements/fixture_22.json"
        payload["archive_ledger"] = [item for item in payload["archive_ledger"] if item["period"] != "2010-03"]
        payload["standard_history"] = [row for row in payload["standard_history"] if row["month"] != "2010-03"]
        data.write_json(path, payload)
        import apply_list_supplements as supplements
        before = (self.acquisition / "entries/22.json").read_bytes()
        old_normalized = (self.acquisition / "normalized/22.json").read_bytes()
        with patch.object(supplements, "load_roster", return_value=(list(self.people.values()), {})):
            with self.assertRaisesRegex(ValueError, "lacks a required published period"):
                supplements.apply_list_supplements(self.root, self.acquisition)
        self.assertEqual((self.acquisition / "entries/22.json").read_bytes(), before)
        self.assertEqual((self.acquisition / "normalized/22.json").read_bytes(), old_normalized)

    def test_gap_bridge_cannot_omit_raw_points_or_relabel_a_point_as_official(self):
        payload = gap_bridge_fixture(self.root, self.acquisition, self.people, apply=False)
        path = self.root / data.STUDY / "supplements/fixture_22.json"
        import apply_list_supplements as supplements
        before_entry = (self.acquisition / "entries/22.json").read_bytes()
        before_normalized = (self.acquisition / "normalized/22.json").read_bytes()
        for mutation in ("omit", "index", "packed", "provider"):
            with self.subTest(mutation=mutation):
                changed = json.loads(json.dumps(payload))
                api_rows = [row for row in changed["standard_history"] if row["source"] == "lichess_fide_history"]
                if mutation == "omit":
                    changed["standard_history"].remove(api_rows[-1])
                elif mutation == "index":
                    api_rows[0]["api_history_point_index"] = 1
                elif mutation == "packed":
                    api_rows[0]["api_raw_packed_value"] += 1
                else:
                    api_rows[0]["source"] = "fide_official_list_archive"
                data.write_json(path, changed)
                with patch.object(supplements, "load_roster", return_value=(list(self.people.values()), {})):
                    with self.assertRaises(ValueError):
                        supplements.apply_list_supplements(self.root, self.acquisition)
                self.assertEqual((self.acquisition / "entries/22.json").read_bytes(), before_entry)
                self.assertEqual((self.acquisition / "normalized/22.json").read_bytes(), before_normalized)

    def test_gap_primary_rating_and_publication_month_checked_before_replacement(self):
        payload = gap_bridge_fixture(self.root, self.acquisition, self.people, apply=False)
        path = self.root / data.STUDY / "supplements/fixture_22.json"
        before = (self.acquisition / "entries/22.json").read_bytes()
        import apply_list_supplements as supplements
        for mutation in ("rating", "month"):
            changed = json.loads(json.dumps(payload))
            row = next(item for item in changed["standard_history"] if item["source"] == "fide_official_list_archive")
            ledger = next(item for item in changed["archive_ledger"] if item["source"] == "fide_official_list_archive")
            if mutation == "rating":
                row["standard_elo"] = 1980  # The original source line contains this birthday token.
            else:
                row["month"] = ledger["period"] = "2010-03"
            data.write_json(path, changed)
            with patch.object(supplements, "load_roster", return_value=(list(self.people.values()), {})):
                with self.assertRaisesRegex(ValueError, "parsed rating column|publication URL/member month"):
                    supplements.apply_list_supplements(self.root, self.acquisition)
            self.assertEqual((self.acquisition / "entries/22.json").read_bytes(), before)

    def test_original_list_adjudication_retains_rejected_cache_and_identifies_peak(self):
        path, document = point_adjudication_fixture(self.root, self.acquisition, self.people, self.historical)
        before = json.loads(json.dumps(self.historical))
        manifest = self.build()
        self.assertEqual(manifest["point_adjudication_n"], 1)
        self.assertEqual(manifest["point_adjudications"][0]["source_file_sha256"], data.sha256(path))
        resolution = manifest["point_adjudication_resolutions"][0]
        self.assertEqual(resolution["selected_rating"], 2532)
        self.assertEqual(resolution["identified_peak"], 2596)
        frame = data.load_frame(self.root, "development").set_index("canonical_id")
        self.assertEqual(frame.loc["22", "rating"], 2596)
        self.assertEqual(frame.loc["22", "adjudicated_periods"], "2001-01")
        self.assertEqual(frame.loc["22", "ambiguous_period_n"], 0)
        self.assertEqual(frame.loc["22", "peak_periods"], "2001-04")
        history = pd.read_csv(self.root / manifest["normalized_history"]["path"], dtype={"canonical_id": str})
        jan = history[(history.canonical_id == "22") & (history.period == "2001-01")].iloc[0]
        self.assertEqual(jan.rating, 2532)
        self.assertEqual(json.loads(jan.candidate_ratings), [2532, 2601])
        self.assertTrue(jan.adjudicated_period)
        self.assertFalse(jan.ambiguous_period)
        rejected = next(item for item in json.loads(jan.source_records) if item["rating"] == 2601)
        self.assertEqual(rejected["point_adjudication_status"], "rejected_derived_rating")
        self.assertEqual(rejected["source"], "lichess_fide_history")
        self.assertEqual(self.historical, before)

    def test_original_list_evidence_rejects_archive_tampering_and_unlisted_candidates(self):
        path, document = point_adjudication_fixture(self.root, self.acquisition, self.people, self.historical)
        for field, value in (("canonical_id", "999"), ("period", "2001-07"),
                ("decision", "choose_the_lower_rating"), ("selected_rating", 2533), ("rejected_ratings", [2601, 2700])):
            with self.subTest(field=field):
                changed = json.loads(json.dumps(document))
                changed[field] = value
                data.write_json(path, changed)
                with self.assertRaises((ValueError, data.DatasetBuildError)):
                    self.build()
                self.assertFalse((self.root / data.DATA / "data_manifest.json").exists())
        data.write_json(path, document)
        archive = self.root / document["evidence"]["archive_file"]
        archive.write_bytes(archive.read_bytes() + b"changed ZIP bytes")
        with self.assertRaisesRegex(ValueError, "archive fingerprint"):
            self.build()

    def test_original_list_parses_rating_column_not_any_matching_number(self):
        path, document = point_adjudication_fixture(self.root, self.acquisition, self.people, self.historical)
        evidence = document["evidence"]
        # Keep the claimed2532 elsewhere but put2533 in the actual JAN01 column.
        line = evidence["source_line"][:59] + f"{2533:<6}{2532:<6}" + evidence["source_line"][71:]
        evidence["source_line"] = line
        archive = self.root / evidence["archive_file"]
        with zipfile.ZipFile(archive, "w") as z:
            z.writestr(evidence["archive_member"], (evidence["source_header"] + "\n" + line + "\n").encode("latin-1"))
        evidence["archive_sha256"] = data.sha256(archive)
        data.write_json(path, document)
        with self.assertRaisesRegex(ValueError, "parsed identity, month or rating"):
            self.build()

    def test_original_point_cannot_be_used_without_evidence_or_after_source_change(self):
        path, document = point_adjudication_fixture(self.root, self.acquisition, self.people, self.historical)
        path.unlink()
        with self.assertRaises(data.DatasetBuildError):
            self.build()
        data.write_json(path, document)
        self.build()
        path.write_text(path.read_text() + " ")
        with self.assertRaisesRegex(ValueError, "point-adjudication source changed"):
            data.load_frame(self.root, "development")

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
