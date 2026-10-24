"""Join frozen people to audited published standard-rating histories.

No models are fitted or scored here. Both roster-origin cohorts use the same
published-list cutoff. Source snapshots stay unchanged; any later date control
must use feature_reference_snapshot rather than the roster-origin year.
"""
from __future__ import annotations
import argparse
import csv
from datetime import date, datetime, timezone
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import sys
import pandas as pd

STUDY = Path("studies/chess_peak_v1")
DATA = STUDY / "data"
OLD = Path("studies/chess_single_A_v2")
CUTOFF = "2023-12"
REFERENCE_SNAPSHOT = "2024-01"
STATUS = "peak_inputs_complete_before_fitting"
ROLES = ("development", "primary_new")
EXPECTED_COUNTS = {"development": 1000, "primary_new": 500}
ORIGINAL_FIELDS = ("canonical_id", "snapshot", "exact_dob_frozen", "rating", "year_stem",
    "year_branch", "month_stem", "month_branch", "day_stem", "day_branch", "year_pillar",
    "month_pillar", "day_pillar")
EXTRA_FIELDS = ("label_end_period", "feature_reference_snapshot", "peak_periods", "peak_sources",
    "peak_periods_complete", "history_source_provider", "derived_snapshot_record_n",
    "history_first_period", "history_last_period", "history_n", "fide_history_n",
    "official_chart_history_n", "lichess_history_n", "olimpbase_history_n", "pre2003_history_n", "history_coverage")
OUTPUT_FIELDS = ("canonical_id", "snapshot", "exact_dob_frozen", "snapshot_rating", "rating") + ORIGINAL_FIELDS[4:] + EXTRA_FIELDS
COVERAGE = "available_FIDE_history_direct_or_Lichess_mirror_and_archived_lists_1971_07_to_2023_12"
FIDE_PROVIDERS = ("fide_official_chart", "lichess_fide_history")

class DatasetBuildError(ValueError):
    """The complete fixed cohort cannot yet be assigned audited labels."""

def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def json_sha256(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False).encode()).hexdigest()

def ids_sha256(ids):
    return hashlib.sha256(("\n".join(map(str, ids)) + "\n").encode()).hexdigest()

def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))

def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True,
        allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)

def safe_file(base, relative):
    base = Path(base).resolve()
    if not isinstance(relative, str) or Path(relative).is_absolute():
        raise ValueError("Recorded file path must be relative")
    path = (base / relative).resolve()
    if not path.is_relative_to(base) or not path.is_file():
        raise ValueError(f"Missing or unsafe recorded file: {relative}")
    return path

def canonical_id(value):
    text = str(value).strip()
    if not re.fullmatch(r"[0-9]+", text) or int(text) <= 0:
        raise ValueError("Invalid canonical FIDE identity")
    return str(int(text))

def period(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}", value):
        raise ValueError("Invalid published-list month")
    date.fromisoformat(value + "-01")
    return value

def rating(value):
    if isinstance(value, bool) or not re.fullmatch(r"[0-9]+", str(value)):
        raise ValueError("History rating must be a positive integer")
    result = int(value)
    if not 0 < result <= 3500:
        raise ValueError("History rating outside valid range")
    return result

def _a_loader(root, role):
    source = str(Path(root) / OLD)
    if source not in sys.path:
        sys.path.insert(0, source)
    from model_inputs import load_model_frame
    return load_model_frame(Path(root), role)

def _load_originals(root):
    root = Path(root).resolve()
    manifest = read_json(root / OLD / "data/data_manifest.json")
    frames, people, cohort_sources = {}, {}, {}
    for role in ROLES:
        frame = _a_loader(root, role)
        if len(frame) != EXPECTED_COUNTS[role]:
            raise ValueError(f"Original fixed cohort size differs: {role}")
        frames[role] = frame
        info = manifest["roles"][role]
        source = info["source"]
        source_path = safe_file(root, source["path"])
        if sha256(source_path) != source["sha256"]:
            raise ValueError("Original cohort source fingerprint differs")
        with source_path.open(encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.DictReader(stream))
        if len(rows) != len(frame):
            raise ValueError("Original cohort and input counts differ")
        by_id = {}
        for row in rows:
            cid = canonical_id(row.get("identity_bridge_modern_fide_id", "").strip() or row["fide_id"])
            if cid in by_id or cid in people:
                raise ValueError("Duplicate person within or across fixed cohorts")
            qids = sorted(set(re.split(r"[;,|\s]+", row["wikidata_person_qids"].strip())))
            if not qids or any(not re.fullmatch(r"Q[1-9][0-9]*", qid) for qid in qids):
                raise ValueError("Missing or invalid frozen Wikidata identity")
            by_id[cid] = row
            people[cid] = {"canonical_id": cid, "role": role, "name": row["name"],
                "exact_dob_frozen": row["exact_dob_frozen"], "snapshot": row["snapshot"],
                "snapshot_elo": int(row["rating"]), "wikidata_person_qids": qids}
        if set(by_id) != set(frame.canonical_id):
            raise ValueError("Original cohort identities differ from model inputs")
        for row in frame.to_dict("records"):
            old = by_id[row["canonical_id"]]
            if row["exact_dob_frozen"] != old["exact_dob_frozen"] or row["snapshot"] != old["snapshot"] or row["rating"] != int(old["rating"]):
                raise ValueError("Original source/input fields disagree")
        cohort_sources[role] = {"model_input": {"path": info["path"], "sha256": info["sha256"]},
            "cohort": {"path": source["path"], "sha256": source["sha256"]}}
    role_ids = {r: sorted(str(x) for x in frames[r].canonical_id) for r in ROLES}
    role_qids = {r: sorted(q for p in people.values() if p["role"] == r for q in p["wikidata_person_qids"]) for r in ROLES}
    if any(len(ids) != len(set(ids)) for ids in role_qids.values()) or set(role_qids[ROLES[0]]) & set(role_qids[ROLES[1]]):
        raise ValueError("Wikidata person overlap within or across fixed cohorts")
    return frames, people, cohort_sources, role_ids, role_qids

def read_acquisition(acquisition_dir, people):
    """Verify complete FIDE-history shards and explicitly named mirror sources."""
    acquisition_dir = Path(acquisition_dir).resolve()
    manifests = sorted(acquisition_dir.rglob("acquisition_manifest.json"))
    if not manifests:
        raise ValueError("No rating-history acquisition manifests found")
    entries, provenance, shard_indices, shard_counts = {}, [], set(), set()
    allowed_status = {"official_chart_histories_acquired_pending_historical_merge", "rating_histories_acquired_pending_historical_merge"}
    for manifest_path in manifests:
        base = manifest_path.parent
        manifest = read_json(manifest_path)
        if (manifest.get("protocol_id") != "chess-peak-history-acquisition-v1"
                or manifest.get("status") not in allowed_status or manifest.get("cutoff_month") != CUTOFF
                or manifest.get("model_fitting_performed") is not False or manifest.get("failed_n") != 0
                or manifest.get("selected_n") != manifest.get("full_shard_expected_n")
                or manifest.get("selected_n") != manifest.get("completed_n")):
            raise ValueError("Rating-history acquisition shard is incomplete or failed")
        if manifest.get("shard_index") in shard_indices:
            raise ValueError("Duplicate rating-history acquisition shard")
        shard_indices.add(manifest["shard_index"])
        shard_counts.add(manifest["shard_count"])
        file_hashes = manifest.get("files", {})
        if not file_hashes:
            raise ValueError("Rating-history acquisition has no fingerprint ledger")
        for name, expected in file_hashes.items():
            if sha256(safe_file(base, name)) != expected:
                raise ValueError(f"Rating-history acquisition file changed: {name}")
        paths = sorted((base / "entries").glob("*.json"))
        if len(paths) != manifest["selected_n"]:
            raise ValueError("Rating-history entry inventory is incomplete")
        provider_counts = {p: 0 for p in FIDE_PROVIDERS}
        for entry_path in paths:
            if entry_path.relative_to(base).as_posix() not in file_hashes:
                raise ValueError("Unsealed rating-history entry")
            entry = read_json(entry_path)
            cid = canonical_id(entry["canonical_id"])
            if cid in entries or cid not in people:
                raise ValueError("Duplicate or unexpected rating-history person entry")
            person = people[cid]
            for field in ("role", "name", "exact_dob_frozen", "snapshot", "snapshot_elo", "wikidata_person_qids"):
                if entry.get(field) != person[field]:
                    raise ValueError(f"Rating-history entry changed frozen person field: {field}")
            provider = entry.get("source_provider", "fide_official_chart")
            url = {"fide_official_chart": f"https://ratings.fide.com/a_chart_data.phtml?event={cid}&period=0",
                "lichess_fide_history": f"https://lichess.org/api/fide/player/{cid}/ratings"}.get(provider)
            if url is None or entry.get("source_url") != url:
                raise ValueError("Rating-history source URL/provider differs from requested person")
            provider_counts[provider] += 1
            if entry.get("status") not in ("history_acquired", "history_acquired_requires_snapshot_audit"):
                raise ValueError("Rating-history entry failed")
            normalized_name = entry["normalized_history_file"]
            if normalized_name not in file_hashes:
                raise ValueError("Unsealed normalized rating history")
            normalized_path = safe_file(base, normalized_name)
            if sha256(normalized_path) != entry["normalized_history_sha256"]:
                raise ValueError("Normalized rating history changed")
            normalized = read_json(normalized_path)
            if (normalized.get("canonical_id") != cid or normalized.get("label_cutoff_month") != CUTOFF
                    or normalized.get("source_raw_sha256") != entry.get("raw_sha256")
                    or normalized.get("source_provider", "fide_official_chart") != provider):
                raise ValueError("Normalized identity/provenance differs")
            complete = normalized.get("peak_months_complete", provider == "fide_official_chart")
            if not isinstance(complete, bool) or (provider == "lichess_fide_history" and complete):
                raise ValueError("Compressed source cannot claim complete monthly peak ties")
            raw_name = f"raw/{cid}.json.gz"
            if raw_name not in file_hashes:
                raise ValueError("Unsealed rating-history raw response")
            if hashlib.sha256(gzip.decompress(safe_file(base, raw_name).read_bytes())).hexdigest() != entry["raw_sha256"]:
                raise ValueError("Rating-history raw-response fingerprint differs")
            rows = normalized["standard_history"]
            derived_rows = [row for row in rows if row.get("derived_state")]
            if len(derived_rows) > 1 or (derived_rows and provider != "lichess_fide_history"):
                raise ValueError("Unexpected source-derived snapshot inventory")
            direct = {row["month"]: row for row in rows if not row.get("derived_state")}
            for derived in derived_rows:
                month = derived.get("month")
                previous = max((key for key in direct if key < month), default=None)
                if (month != person["snapshot"] or derived.get("source_point") is not False
                        or derived.get("derived_from_month") != previous or previous is None or month > max(direct)
                        or derived.get("standard_elo") != direct[previous]["standard_elo"]
                        or derived.get("derivation") != "piecewise_constant_state_from_compressed_FIDE_rating_history"):
                    raise ValueError("Invalid piecewise-constant snapshot derivation")
            records = [{**{k: v for k, v in row.items() if k not in ("month", "standard_elo")},
                "canonical_id": cid, "period": row["month"], "rating": row["standard_elo"],
                "source": provider, "source_url": url, "source_raw_sha256": entry["raw_sha256"],
                "peak_months_complete": complete, "history_compression": normalized.get("history_compression")}
                for row in rows]
            entries[cid] = {"entry": entry, "records": records}
        if "source_provider_counts" in manifest and manifest["source_provider_counts"] != provider_counts:
            raise ValueError("Rating-history provider counts disagree with source entries")
        provenance.append({"manifest_path": manifest_path.relative_to(acquisition_dir).as_posix(),
            "manifest_sha256": sha256(manifest_path), "shard_index": manifest["shard_index"],
            "selected_n": manifest["selected_n"], "files_n": len(file_hashes), "source_provider_counts": provider_counts})
    if len(shard_counts) != 1 or shard_indices != set(range(next(iter(shard_counts)))):
        raise ValueError("Rating-history acquisition shard set is incomplete")
    if set(entries) != set(people):
        raise ValueError("Rating histories do not cover all fixed people")
    return entries, provenance

def combine_person(person, official_records, historical_records):
    """Merge equal list months exactly; future rows never enter the peak."""
    cid, by_month, excluded_future = person["canonical_id"], {}, 0
    for record in [*official_records, *historical_records]:
        if canonical_id(record["canonical_id"]) != cid:
            raise ValueError("History row belongs to another person")
        month, elo = period(record["period"]), rating(record["rating"])
        if month > CUTOFF:
            excluded_future += 1
            continue
        if month < "1971-07":
            raise ValueError("History precedes declared archive coverage")
        source = str(record.get("source", ""))
        if source not in (*FIDE_PROVIDERS, "olimpbase_transcription"):
            raise ValueError("History has an unknown source convention")
        entry = by_month.setdefault(month, {"canonical_id": cid, "period": month, "rating": elo,
            "sources": set(), "source_records": []})
        if entry["rating"] != elo:
            raise ValueError(f"Conflicting ratings for the same published month {cid}/{month}")
        entry["sources"].add(source)
        entry["source_records"].append(record)
    if not by_month:
        raise ValueError("No published standard rating before cutoff")
    rows = [by_month[key] for key in sorted(by_month)]
    peak = max(row["rating"] for row in rows)
    snapshot = by_month.get(person["snapshot"])
    if snapshot is None:
        raise ValueError("Frozen snapshot month absent from merged histories")
    if snapshot["rating"] != person["snapshot_elo"]:
        raise ValueError("History snapshot rating differs from frozen snapshot")
    if peak < person["snapshot_elo"]:
        raise ValueError("Observed peak is below frozen snapshot rating")
    # Reconstructed states align snapshots; they are not observed peak dates.
    peak_rows = [row for row in rows if row["rating"] == peak
        and any(not rec.get("derived_state", False) for rec in row["source_records"])]
    if not peak_rows:
        raise ValueError("Peak value has no directly retained source point")
    providers = sorted({rec["source"] for rec in official_records})
    derived_n = sum(bool(rec.get("derived_state")) for rec in official_records if rec["period"] <= CUTOFF)
    info = {"rating": peak, "label_end_period": CUTOFF, "feature_reference_snapshot": REFERENCE_SNAPSHOT,
        "peak_periods": ";".join(row["period"] for row in peak_rows),
        "peak_sources": ";".join(sorted({source for row in peak_rows for source in row["sources"]})),
        "peak_periods_complete": "lichess_fide_history" not in providers,
        "history_source_provider": ";".join(providers), "derived_snapshot_record_n": derived_n,
        "history_first_period": rows[0]["period"], "history_last_period": rows[-1]["period"], "history_n": len(rows),
        "fide_history_n": sum(bool(set(FIDE_PROVIDERS) & row["sources"]) for row in rows),
        "official_chart_history_n": sum("fide_official_chart" in row["sources"] for row in rows),
        "lichess_history_n": sum("lichess_fide_history" in row["sources"] for row in rows),
        "olimpbase_history_n": sum("olimpbase_transcription" in row["sources"] for row in rows),
        "pre2003_history_n": sum(row["period"] < "2003-04" for row in rows), "history_coverage": COVERAGE}
    for row in rows:
        row["sources"] = ";".join(sorted(row["sources"]))
    return info, rows, excluded_future

def _historical_payload(historical, acquisition_dir):
    if historical is None:
        candidates = list(Path(acquisition_dir).rglob("historical_history.json"))
        if len(candidates) != 1:
            raise ValueError("One audited historical extraction is required")
        historical = candidates[0]
    payload = historical if isinstance(historical, dict) else read_json(historical)
    if not isinstance(payload, dict) or not isinstance(payload.get("records"), list):
        raise ValueError("Malformed historical extraction")
    if payload.get("status") != "complete":
        raise ValueError("Historical extraction is not complete")
    audit = payload.get("audit", {})
    if "fatal_issues" not in audit or not isinstance(audit["fatal_issues"], list):
        raise ValueError("Historical extraction lacks explicit fatal-issue audit")
    if audit["fatal_issues"]:
        raise ValueError("Historical extraction contains unresolved fatal identity/source issues")
    if not payload.get("archives"):
        raise ValueError("Historical extraction lacks archive provenance")
    coverage = payload.get("coverage", {})
    periods = coverage.get("published_periods", [])
    if (coverage.get("first_official_period") != "1971-07" or coverage.get("last_selected_period") != "2003-04"
            or not periods or periods != sorted(set(periods)) or coverage.get("period_count") != len(periods)
            or periods[0] != "1971-07" or periods[-1] != "2003-04"):
        raise ValueError("Historical extraction coverage is incomplete")
    if any(not "1971-07" <= period(row["period"]) <= "2003-04" for row in payload["records"]):
        raise ValueError("Historical row falls outside declared extraction period")
    return payload

def build_dataset(repo_root, acquisition_dir, historical=None, output_dir=None):
    root, acquisition_dir = Path(repo_root).resolve(), Path(acquisition_dir).resolve()
    output = (root / DATA if output_dir is None else Path(output_dir)).resolve()
    if not output.is_relative_to(root) or output == root:
        raise ValueError("Peak dataset output must be inside its repository")
    output.mkdir(parents=True, exist_ok=True)
    if (output / "data_manifest.json").exists():
        raise ValueError("Refusing to replace an already frozen-ready peak dataset")
    audit = {"protocol_id": "chess-peak-v1", "status": "incomplete", "cutoff_month": CUTOFF,
        "feature_reference_snapshot": REFERENCE_SNAPSHOT, "model_fitting_performed": False,
        "created_at_utc": datetime.now(timezone.utc).isoformat(), "issues": []}
    audit_path = output / "dataset_build_audit.json"
    try:
        frames, people, sources, role_ids, role_qids = _load_originals(root)
        official, provenance = read_acquisition(acquisition_dir, people)
        historic = _historical_payload(historical, acquisition_dir)
        old_by_id = {cid: [] for cid in people}
        for row in historic["records"]:
            cid = canonical_id(row["canonical_id"])
            if cid not in old_by_id:
                raise ValueError("Historical extraction includes unexpected person")
            old_by_id[cid].append(row)
        labels, history_rows, excluded_future = {}, [], 0
        for cid, person in sorted(people.items()):
            try:
                info, records, ignored = combine_person(person, official[cid]["records"], old_by_id[cid])
                labels[cid] = info
                history_rows.extend(records)
                excluded_future += ignored
            except (KeyError, TypeError, ValueError) as error:
                audit["issues"].append({"canonical_id": cid, "role": person["role"], "name": person["name"], "error": str(error)})
        audit.update(people=len(people), labeled_people=len(labels), future_history_rows_excluded=excluded_future,
            acquisition=provenance, historical_audit=historic["audit"], historical_payload_sha256=json_sha256(historic),
            historical_archives=historic["archives"], canonical_id_overlap=0, wikidata_person_overlap=0)
        audit["historical_matched_people_n"] = sum(bool(old_by_id[cid]) for cid in people)
        audit["history_source_provider_counts"] = {provider: sum(provider in labels[cid]["history_source_provider"].split(";") for cid in labels) for provider in FIDE_PROVIDERS}
        audit["derived_snapshot_person_ids"] = [cid for cid in sorted(labels) if labels[cid]["derived_snapshot_record_n"]]
        audit["peak_month_ties_incomplete_person_ids"] = [cid for cid in sorted(labels) if not labels[cid]["peak_periods_complete"]]
        audit["historical_identity_priority"] = "stable modern FIDE identity and exact normalized frozen full name or explicit audited alias anchor the canonical group; source birth discrepancies are retained and never change frozen birth features"
        audit["conservative_pre2003_flag_without_archive_rows"] = [{"canonical_id": cid, "name": people[cid]["name"],
            "exact_dob_frozen": people[cid]["exact_dob_frozen"], "fide_history_start": official[cid]["entry"].get("history_start")}
            for cid in sorted(people) if official[cid]["entry"].get("coverage_needs_pre2003") and not old_by_id[cid]]
        if audit["issues"] or set(labels) != set(people):
            raise DatasetBuildError("Peak labels have unresolved data/identity issues; see dataset_build_audit.json")
        role_info = {}
        for role in ROLES:
            rows = []
            for original in frames[role].to_dict("records"):
                row = {**original, "snapshot_rating": int(original["rating"]), **labels[original["canonical_id"]]}
                rows.append({name: row[name] for name in OUTPUT_FIELDS})
            rows.sort(key=lambda row: row["canonical_id"])
            target = output / f"model_inputs_{role}.csv"
            with target.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=OUTPUT_FIELDS)
                writer.writeheader()
                writer.writerows(rows)
            role_info[role] = {"path": target.relative_to(root).as_posix(), "sha256": sha256(target), "n": len(rows),
                "canonical_ids": role_ids[role], "canonical_ids_sha256": ids_sha256(role_ids[role]),
                "wikidata_person_qids": role_qids[role], "wikidata_qids_sha256": ids_sha256(role_qids[role]),
                "original_sources": sources[role]}
        history_path = output / "normalized_history.csv.gz"
        text = io.StringIO(newline="")
        writer = csv.DictWriter(text, fieldnames=("canonical_id", "period", "rating", "sources", "source_records"))
        writer.writeheader()
        for row in history_rows:
            writer.writerow({**row, "source_records": json.dumps(row["source_records"], ensure_ascii=False, sort_keys=True)})
        history_path.write_bytes(gzip.compress(text.getvalue().encode(), compresslevel=6, mtime=0))
        audit["status"] = "all_fixed_people_have_audited_observed_peak_labels"
        write_json(audit_path, audit)
        manifest = {"protocol_id": "chess-peak-v1", "status": STATUS, "label_end_period": CUTOFF,
            "feature_reference_snapshot": REFERENCE_SNAPSHOT, "target": "maximum available published official standard rating through fixed cutoff",
            "completed_career_peak_claimed": False, "roster_origin_is_not_a_temporal_forecast": True,
            "prior_snapshot_outcomes_seen": True, "canonical_id_overlap": 0, "wikidata_person_overlap": 0,
            "roles": role_info, "history_coverage": COVERAGE,
            "history_source_provider_counts": audit["history_source_provider_counts"],
            "derived_snapshot_person_n": len(audit["derived_snapshot_person_ids"]),
            "peak_month_ties_incomplete_n": len(audit["peak_month_ties_incomplete_person_ids"]),
            "acquisition": provenance, "historical_payload_sha256": json_sha256(historic), "historical_archives": historic["archives"],
            "audit": {"path": audit_path.relative_to(root).as_posix(), "sha256": sha256(audit_path)},
            "normalized_history": {"path": history_path.relative_to(root).as_posix(), "sha256": sha256(history_path), "n": len(history_rows)}}
        write_json(output / "data_manifest.json", manifest)
        return manifest
    except Exception as error:
        audit.update(status="failed_requires_audit", error_type=type(error).__name__, error=str(error))
        write_json(audit_path, audit)
        raise

def load_frame(repo_root, role):
    """Load one verified peak role without opening the other role's labels."""
    root = Path(repo_root).resolve()
    if role not in ROLES:
        raise ValueError("Unknown peak input role")
    manifest = read_json(root / DATA / "data_manifest.json")
    if (manifest.get("protocol_id") != "chess-peak-v1" or manifest.get("status") != STATUS
            or manifest.get("label_end_period") != CUTOFF or manifest.get("feature_reference_snapshot") != REFERENCE_SNAPSHOT
            or manifest.get("completed_career_peak_claimed") is not False or manifest.get("canonical_id_overlap") != 0
            or manifest.get("wikidata_person_overlap") != 0 or set(manifest.get("roles", {})) != set(ROLES)):
        raise ValueError("Peak dataset manifest is incomplete or changed")
    for key in ("canonical_ids", "wikidata_person_qids"):
        a, b = (manifest["roles"][r][key] for r in ROLES)
        if len(a) != len(set(a)) or len(b) != len(set(b)) or set(a) & set(b):
            raise ValueError("Peak role identities overlap")
    for other_role in ROLES:
        other = manifest["roles"][other_role]
        if ids_sha256(other["canonical_ids"]) != other["canonical_ids_sha256"] or ids_sha256(other["wikidata_person_qids"]) != other["wikidata_qids_sha256"]:
            raise ValueError("Peak role identity fingerprint differs")
    for key in ("audit", "normalized_history"):
        item = manifest[key]
        if sha256(safe_file(root, item["path"])) != item["sha256"]:
            raise ValueError("Peak history/audit fingerprint differs")
    info = manifest["roles"][role]
    path = safe_file(root, info["path"])
    if sha256(path) != info["sha256"]:
        raise ValueError("Peak input fingerprint mismatch")
    original = _a_loader(root, role).sort_values("canonical_id", kind="stable").reset_index(drop=True)
    for source in info["original_sources"].values():
        if sha256(safe_file(root, source["path"])) != source["sha256"]:
            raise ValueError("Original source fingerprint changed")
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != list(OUTPUT_FIELDS):
            raise ValueError("Peak input schema differs")
        rows = list(reader)
    ids = [canonical_id(row["canonical_id"]) for row in rows]
    if (len(rows) != EXPECTED_COUNTS[role] or len(rows) != info["n"] or ids != sorted(ids)
            or ids != info["canonical_ids"] or len(ids) != len(set(ids)) or ids != original.canonical_id.tolist()
            or ids_sha256(ids) != info["canonical_ids_sha256"]):
        raise ValueError("Peak input person count/order differs")
    for row, old in zip(rows, original.to_dict("records")):
        for name in ORIGINAL_FIELDS:
            value = int(row["snapshot_rating"]) if name == "rating" else row[name]
            if value != old[name]:
                raise ValueError(f"Peak input changed original person field: {name}")
        row["rating"], row["snapshot_rating"] = rating(row["rating"]), rating(row["snapshot_rating"])
        if row["rating"] < row["snapshot_rating"]:
            raise ValueError("Peak input is below original snapshot rating")
        if row["label_end_period"] != CUTOFF or row["feature_reference_snapshot"] != REFERENCE_SNAPSHOT or row["history_coverage"] != COVERAGE:
            raise ValueError("Peak target/reference cutoff differs")
        if row["peak_periods_complete"] not in ("True", "False"):
            raise ValueError("Invalid peak-month completeness flag")
        row["peak_periods_complete"] = row["peak_periods_complete"] == "True"
        providers = row["history_source_provider"].split(";")
        if providers != sorted(set(providers)) or any(provider not in FIDE_PROVIDERS for provider in providers):
            raise ValueError("Unknown peak-history provider")
        if "lichess_fide_history" in providers and row["peak_periods_complete"]:
            raise ValueError("Compressed peak history claims complete monthly ties")
        months = row["peak_periods"].split(";")
        if not months or months != sorted(set(months)) or any(period(x) > CUTOFF for x in months):
            raise ValueError("Peak month inventory differs")
        first, last = period(row["history_first_period"]), period(row["history_last_period"])
        if first > last or last > CUTOFF or any(x < first or x > last for x in months):
            raise ValueError("Peak history coverage is inconsistent")
        for name in ("history_n", "fide_history_n", "official_chart_history_n", "lichess_history_n", "olimpbase_history_n", "pre2003_history_n", "derived_snapshot_record_n"):
            if not re.fullmatch(r"[0-9]+", row[name]):
                raise ValueError("Invalid history count")
            row[name] = int(row[name])
        if row["history_n"] < len(months) or row["fide_history_n"] <= 0:
            raise ValueError("Peak history has insufficient source records")
        if row["derived_snapshot_record_n"] > 1 or (row["derived_snapshot_record_n"] and "lichess_fide_history" not in providers):
            raise ValueError("Invalid derived snapshot count/provider")
    return pd.DataFrame(rows, columns=OUTPUT_FIELDS)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("build", "verify"))
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--acquisition-dir", type=Path)
    parser.add_argument("--historical-json", type=Path)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    if args.command == "build":
        if args.acquisition_dir is None:
            parser.error("build requires --acquisition-dir")
        result = build_dataset(args.repo_root, args.acquisition_dir, args.historical_json, args.output_dir)
        print(json.dumps({"status": result["status"], "counts": {r: result["roles"][r]["n"] for r in ROLES}}))
    else:
        print(json.dumps({"status": STATUS, "counts": {r: len(load_frame(args.repo_root, r)) for r in ROLES}}))

if __name__ == "__main__":
    main()
