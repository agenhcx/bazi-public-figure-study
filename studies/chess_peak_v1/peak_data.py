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
import unicodedata
import zipfile
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
    "ambiguous_period_n", "ambiguous_periods", "period_conflict_resolution_policy",
    "adjudicated_period_n", "adjudicated_periods",
    "history_first_period", "history_last_period", "history_n", "fide_history_n",
    "official_chart_history_n", "lichess_history_n", "official_list_history_n", "olimpbase_history_n", "pre2003_history_n", "history_coverage")
OUTPUT_FIELDS = ("canonical_id", "snapshot", "exact_dob_frozen", "snapshot_rating", "rating") + ORIGINAL_FIELDS[4:] + EXTRA_FIELDS
COVERAGE = "available_FIDE_history_direct_or_Lichess_mirror_and_archived_lists_1971_07_to_2023_12"
API_PROVIDERS = ("fide_official_chart", "lichess_fide_history")
FIDE_PROVIDERS = (*API_PROVIDERS, "fide_official_list_archive")
CONFLICT_POLICY = "retain_all_candidates_only_when_upper_bound_not_above_unambiguous_peak"
COVERAGE_RULE = "lichess-frozen-snapshot-and-older-window-v1"
COVERAGE_REASONS = {"lichess_missing_frozen_snapshot", "lichess_late_history_for_older_person"}
SNAPSHOT_DISAGREEMENT_RULE = "direct-official-frozen-snapshot-disagreement-v1"
POINT_ADJUDICATION_POLICY = "original_official_rating_list_has_priority_over_derived_sources"

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
                "snapshot_elo": int(row["rating"]), "wikidata_person_qids": qids,
                "source_roster": source["path"], "source_roster_sha256": source["sha256"]}
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

def _verify_source_evidence(base, file_hashes, cid, source):
    if not isinstance(source, dict) or source.get("source_provider") not in API_PROVIDERS:
        raise ValueError("Invalid rating-history coverage evidence provider")
    raw_name, metadata_name = source.get("raw_file"), source.get("metadata_file")
    if raw_name not in file_hashes or metadata_name not in file_hashes:
        raise ValueError("Unsealed rating-history coverage evidence")
    raw_path, metadata_path = safe_file(base, raw_name), safe_file(base, metadata_name)
    raw = gzip.decompress(raw_path.read_bytes())
    if (sha256(raw_path) != source.get("gzip_sha256")
            or sha256(metadata_path) != source.get("metadata_sha256")
            or hashlib.sha256(raw).hexdigest() != source.get("raw_sha256")
            or type(source.get("raw_bytes")) is not int or len(raw) != source["raw_bytes"]):
        raise ValueError("Rating-history coverage evidence fingerprint differs")
    metadata = read_json(metadata_path)
    if (metadata.get("canonical_id") != cid or metadata.get("source_provider") != source["source_provider"]
            or any(metadata.get(key) != source[key] for key in ("raw_sha256", "raw_bytes", "gzip_sha256"))):
        raise ValueError("Rating-history coverage evidence metadata differs")
    return raw, metadata

def _verify_source_coverage_audit(base, file_hashes, entry, provider):
    """Verify the fixed coverage check without choosing a source by its peak."""
    if "source_coverage_audit" not in entry:
        return  # Previously sealed entries have no coverage-check record.
    coverage = entry["source_coverage_audit"]
    if not isinstance(coverage, dict):
        raise ValueError("Invalid rating-history source coverage audit")
    reasons = coverage.get("reasons")
    outcome = coverage.get("official_outcome")
    expected = {"selected_snapshot_verified": (False, True, "fide_official_chart"),
        "selected_snapshot_disagreement_verified": (False, True, "fide_official_chart"),
        "unavailable": (True, False, "lichess_fide_history"),
        "missing_frozen_snapshot": (True, True, "lichess_fide_history")}
    if (coverage.get("rule_id") != COVERAGE_RULE or not isinstance(reasons, list) or not reasons
            or len(reasons) != len(set(reasons)) or any(reason not in COVERAGE_REASONS for reason in reasons)
            or outcome not in expected or type(coverage.get("unresolved")) is not bool
            or type(coverage.get("direct_source_coverage_checked")) is not bool
            or coverage.get("selected_provider") != provider
            or (coverage["unresolved"], coverage["direct_source_coverage_checked"], provider) != expected[outcome]):
        raise ValueError("Invalid rating-history source coverage decision")
    if outcome == "selected_snapshot_disagreement_verified" and not entry.get("snapshot_disagreement"):
        raise ValueError("Coverage disagreement decision lacks official snapshot proof")
    sources, source_providers = coverage.get("sources"), set()
    if not isinstance(sources, list) or not sources:
        raise ValueError("Rating-history source coverage audit has no evidence")
    for source in sources:
        source_provider = source.get("source_provider")
        if source_provider not in API_PROVIDERS or source_provider in source_providers:
            raise ValueError("Invalid rating-history coverage evidence provider")
        source_providers.add(source_provider)
        _verify_source_evidence(base, file_hashes, entry["canonical_id"], source)
        if source_provider == provider and source["raw_sha256"] != entry["raw_sha256"]:
            raise ValueError("Selected coverage evidence differs from normalized source")
    if provider not in source_providers or (not coverage["unresolved"] and source_providers != set(API_PROVIDERS)):
        raise ValueError("Rating-history coverage audit omitted retained source evidence")

def _source_name(value):
    return "".join(char for char in unicodedata.normalize("NFKD", str(value)).casefold() if char.isalnum())

def _verify_snapshot_disagreement(base, file_hashes, person, entry, normalized):
    """Recheck source bytes and frozen provenance before adding a candidate."""
    if "snapshot_disagreement" not in entry:
        return None
    proof = entry["snapshot_disagreement"]
    if not isinstance(proof, dict):
        raise ValueError("Invalid official snapshot disagreement proof")
    expected = {"rule_id": SNAPSHOT_DISAGREEMENT_RULE,
        "status": "officially_verified_pending_peak_identifiability", "canonical_id": person["canonical_id"],
        "snapshot_month": person["snapshot"], "frozen_snapshot_elo": person["snapshot_elo"],
        "frozen_name": person["name"], "frozen_source_roster": person.get("source_roster"),
        "frozen_source_roster_sha256": person.get("source_roster_sha256")}
    if (any(expected[key] is None or proof.get(key) != value for key, value in expected.items())
            or entry.get("source_provider", "fide_official_chart") != "fide_official_chart"
            or rating(proof.get("official_snapshot_elo")) == person["snapshot_elo"]
            or _source_name(proof.get("official_name", "")) != _source_name(person["name"])):
        raise ValueError("Official snapshot disagreement changed frozen identity/source fields")
    evidence = proof.get("official_evidence")
    raw, metadata = _verify_source_evidence(base, file_hashes, person["canonical_id"], evidence)
    if (evidence["source_provider"] != "fide_official_chart" or evidence["raw_sha256"] != entry["raw_sha256"]
            or normalized.get("source_raw_sha256") != evidence["raw_sha256"]
            or metadata.get("source_url") != entry["source_url"] or metadata.get("http_status") != 200):
        raise ValueError("Official snapshot proof differs from selected source bytes")
    prior = proof.get("prior_evidence")
    if not isinstance(prior, list):
        raise ValueError("Official snapshot disagreement lacks prior-evidence inventory")
    for source in prior:
        _, prior_metadata = _verify_source_evidence(base, file_hashes, person["canonical_id"], source)
        prior_url = {"fide_official_chart": f"https://ratings.fide.com/a_chart_data.phtml?event={person['canonical_id']}&period=0",
            "lichess_fide_history": f"https://lichess.org/api/fide/player/{person['canonical_id']}/ratings"}[source["source_provider"]]
        if prior_metadata.get("source_url") != prior_url:
            raise ValueError("Snapshot disagreement prior evidence has an unexpected provider URL")
    # Reparse the retained direct bytes rather than trusting the proof's values.
    from collect_fide import parse_history, _month
    parsed = parse_history(raw, person["canonical_id"])
    points = {row["month"]: row["standard_elo"] for row in parsed["all_standard_history"]}
    normalized_points = {row["month"]: row["standard_elo"] for row in normalized["standard_history"]}
    if (points != normalized_points or len(normalized_points) != len(normalized["standard_history"])
            or points.get(person["snapshot"]) != proof["official_snapshot_elo"]
            or any(row.get("derived_state") for row in normalized["standard_history"])):
        raise ValueError("Official snapshot proof disagrees with raw or normalized rating values")
    chart = json.loads(raw.decode("utf-8-sig"))
    snapshot_names, witnessed = [], False
    witness_month = period(proof.get("identity_witness_month"))
    for row in chart:
        month = _month(next(row[key] for key in ("date_2", "date", "period", "month", "rating_date") if key in row))
        name_matches = _source_name(row.get("name", "")) == _source_name(person["name"])
        if month == person["snapshot"]:
            if not name_matches:
                raise ValueError("Official snapshot row name differs from frozen identity")
            snapshot_names.append(row["name"])
        if (month == witness_month and row.get("id_number") not in (None, "")
                and canonical_id(row["id_number"]) == person["canonical_id"] and name_matches):
            witnessed = True
    if proof["official_name"] not in snapshot_names or not witnessed:
        raise ValueError("Official snapshot disagreement lacks matching direct ID/name witness")
    return proof

def _official_archive_url(value):
    return isinstance(value, str) and re.fullmatch(r"https://ratings\.fide\.com/download/[A-Za-z0-9_.-]+\.zip", value, re.IGNORECASE) is not None

def _named_archive_period(value, suffix):
    match = re.fullmatch(r"(?:standard_)?([a-z]{3})([0-9]{2}|[0-9]{4})frl\." + suffix, value.lower())
    if match is None:
        raise ValueError("Original-list evidence filename does not identify its published period")
    return datetime.strptime("".join(match.groups()), "%b%y" if len(match[2]) == 2 else "%b%Y").strftime("%Y-%m")

def _verify_original_list_point(root, person, evidence):
    """Bind a point to exact original ZIP bytes and its fixed-width fields."""
    if (not isinstance(evidence, dict) or evidence.get("source") != "fide_official_list_archive"
            or evidence.get("source_point") is not True or not _official_archive_url(evidence.get("source_url"))
            or evidence.get("source_header_period_mismatch") is not False
            or not evidence.get("publication_period_evidence") or not evidence.get("identity_anchor")):
        raise ValueError("Point adjudication lacks original official-list evidence")
    month, elo = period(evidence["month"]), rating(evidence["standard_elo"])
    if month > CUTOFF or month < person["exact_dob_frozen"][:7]:
        raise ValueError("Original-list evidence point has invalid chronology")
    archive_name = evidence.get("archive_file")
    if not isinstance(archive_name, str) or not archive_name.startswith((DATA / "source_archives").as_posix() + "/"):
        raise ValueError("Original-list ZIP is outside the recorded source archive directory")
    archive_path = safe_file(root, archive_name)
    if sha256(archive_path) != evidence.get("archive_sha256"):
        raise ValueError("Original-list archive fingerprint differs")
    member = evidence.get("archive_member")
    if (not isinstance(member, str) or _named_archive_period(Path(member).name, "txt") != month
            or _named_archive_period(evidence["source_url"].rsplit("/", 1)[-1], "zip") != month):
        raise ValueError("Original-list ZIP URL/member period differs")
    with zipfile.ZipFile(archive_path) as archive:
        if archive.namelist().count(member) != 1:
            raise ValueError("Original-list archive member is absent or duplicated")
        lines = archive.read(member).decode("latin-1").splitlines()
    line_number = evidence.get("source_line_number")
    if (type(line_number) is not int or not 1 < line_number <= len(lines)
            or lines[0] != evidence.get("source_header")
            or lines[line_number - 1] != evidence.get("source_line")):
        raise ValueError("Original-list header or exact source line differs")
    columns = list(re.finditer(r"\S+", lines[0]))
    names = [item.group() for item in columns]
    month_columns = [item for item in names if re.fullmatch(r"[A-Za-z]{3}[0-9]{2,4}", item)]
    if (len(names) != len(set(names)) or not {"ID_NUMBER", "NAME", "COUNTRY"} <= set(names)
            or len(month_columns) != 1):
        raise ValueError("Original-list header lacks unambiguous identity/rating columns")
    rating_column = month_columns[0]
    header_month = datetime.strptime(rating_column, "%b%y" if len(rating_column) == 5 else "%b%Y").strftime("%Y-%m")
    values = {item.group(): lines[line_number - 1][item.start():columns[i + 1].start() if i + 1 < len(columns) else None].strip()
        for i, item in enumerate(columns)}
    if (header_month != month or canonical_id(values["ID_NUMBER"]) != person["canonical_id"]
            or _source_name(values["NAME"]) != _source_name(person["name"])
            or rating(values[rating_column]) != elo or values["COUNTRY"] != evidence.get("source_country")):
        raise ValueError("Original-list parsed identity, month or rating differs")
    birthday = values.get("BIRTHDAY", "")
    if birthday:
        parsed_birth = datetime.strptime(birthday, "%d.%m.%Y").date().isoformat()
        if parsed_birth != person["exact_dob_frozen"] or evidence.get("source_birth_date") != parsed_birth:
            raise ValueError("Original-list birth witness differs from frozen identity")
    elif evidence.get("source_birth_date") is not None:
        raise ValueError("Original-list evidence invents an absent birthday field")
    return {**evidence, "canonical_id": person["canonical_id"], "period": month, "rating": elo,
        "source_archive_sha256": evidence["archive_sha256"], "source_archive_file": archive_name}

def load_point_adjudications(repo_root, people):
    """Load only source-priority decisions whose original list is reverified."""
    root, by_person, provenance = Path(repo_root).resolve(), {}, []
    for path in sorted((root / STUDY / "adjudications").glob("*.json")):
        document = read_json(path)
        cid = canonical_id(document.get("canonical_id"))
        if cid not in people or document.get("name") != people[cid]["name"]:
            raise ValueError("Point adjudication changes the frozen person identity")
        person, month = people[cid], period(document.get("period"))
        selected, rejected = rating(document.get("selected_rating")), document.get("rejected_ratings")
        if (document.get("protocol_id") != "chess-peak-original-list-point-adjudication-v1"
                or document.get("decision") != POINT_ADJUDICATION_POLICY
                or document.get("original_records_preserved") is not True or not document.get("method")
                or not isinstance(rejected, list) or not rejected or any(type(value) is not int for value in rejected)
                or rejected != sorted(set(rating(value) for value in rejected)) or selected in rejected
                or month > CUTOFF or month == person["snapshot"]):
            raise ValueError("Invalid or unsupported original-list point adjudication")
        evidence = _verify_original_list_point(root, person, document.get("evidence"))
        if evidence["period"] != month or evidence["rating"] != selected:
            raise ValueError("Point adjudication target differs from original evidence")
        corroborating = document.get("corroborating_points")
        if not isinstance(corroborating, list):
            raise ValueError("Point adjudication lacks its corroborating evidence inventory")
        corroboration = [_verify_original_list_point(root, person, item) for item in corroborating]
        points = [evidence, *corroboration]
        if len({point["period"] for point in points}) != len(points):
            raise ValueError("Point adjudication repeats a published period")
        identity = document.get("identity_evidence", {})
        if (identity.get("canonical_id") != cid or identity.get("source_name") != person["name"]
                or identity.get("frozen_dob") != person["exact_dob_frozen"]
                or not any(point.get("source_birth_date") == person["exact_dob_frozen"] for point in points)):
            raise ValueError("Point adjudication lacks independent frozen-birthday corroboration")
        record = {"canonical_id": cid, "period": month, "selected_rating": selected, "rejected_ratings": rejected,
            "source_file": path.relative_to(root).as_posix(), "source_file_sha256": sha256(path),
            "decision": POINT_ADJUDICATION_POLICY, "document": document, "verified_points": points}
        if month in by_person.setdefault(cid, {}):
            raise ValueError("Duplicate original-list adjudication for one person/month")
        by_person[cid][month] = record
        provenance.append(record)
    return by_person, provenance

def _verify_list_supplement(base, file_hashes, person, entry, normalized, raw, repo_root):
    """Verify an availability-only archive supplement and its transcribed rows."""
    if repo_root is None:
        raise ValueError("Official-list supplement requires the frozen repository source")
    adjudication = entry.get("list_supplement")
    expected = {"protocol_id": "chess-peak-list-supplement-adjudication-v1",
        "status": "applied_after_api_history_unavailable", "reason": "no_usable_history_from_fide_chart_or_lichess",
        "source_selection": "source_availability_not_rating_magnitude", "primary_snapshot_verified": True,
        "original_identity_unchanged": True}
    if not isinstance(adjudication, dict) or any(adjudication.get(key) != value for key, value in expected.items()):
        raise ValueError("Official-list supplement lacks availability-only adjudication")
    original = safe_file(repo_root, adjudication.get("supplement_file"))
    if sha256(original) != adjudication.get("supplement_sha256") or raw != original.read_bytes():
        raise ValueError("Compiled list supplement differs from frozen repository bytes")
    prior_name = adjudication.get("prior_api_entry_file")
    if prior_name not in file_hashes:
        raise ValueError("Unsealed prior API-unavailable evidence")
    prior_path = safe_file(base, prior_name)
    if sha256(prior_path) != adjudication.get("prior_api_entry_sha256"):
        raise ValueError("Prior API-unavailable evidence changed")
    prior = read_json(prior_path)
    if (prior.get("status") != "failed" or prior.get("error_type") not in ("FetchFailure", "HistoryUnavailable")
            or any(prior.get(key) != person[key] for key in ("canonical_id", "role", "name", "exact_dob_frozen", "snapshot", "snapshot_elo"))):
        raise ValueError("List supplement cannot replace usable or identity-conflicting API history")
    payload = json.loads(raw.decode("utf-8-sig"))
    if (payload.get("protocol_id") != "chess-peak-official-list-supplement-v1"
            or payload.get("canonical_id") != person["canonical_id"] or payload.get("name") != person["name"]
            or payload.get("standard_history") != normalized.get("standard_history")):
        raise ValueError("Compiled list supplement identity or normalized rows differ")
    rows, ledger = payload["standard_history"], payload.get("archive_ledger")
    if not rows or not isinstance(ledger, list) or not ledger:
        raise ValueError("List supplement lacks its source-row ledger")
    allowed = {"fide_official_list_archive", "olimpbase_transcription"}
    keys = ("source_url", "archive_sha256", "archive_member", "source_line_number", "source_line")
    for source in ledger:
        if any(left in source and right in source and source[left] != source[right]
                for left, right in (("source_url", "url"), ("archive_sha256", "sha256"), ("archive_member", "member"))):
            raise ValueError("List supplement ledger aliases disagree")
        source_kind = source.get("source")
        url = source.get("source_url", source.get("url"))
        digest = source.get("archive_sha256", source.get("sha256"))
        if (source_kind not in allowed or not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest)
                or not source.get("archive_member", source.get("member")) or not source.get("header")
                or type(source.get("bytes")) is not int or source["bytes"] <= 0
                or (source_kind == "fide_official_list_archive" and not _official_archive_url(url))
                or (source_kind == "olimpbase_transcription" and url != "https://www.olimpbase.org/Elo/data/elo2002-2009.zip")):
            raise ValueError("List supplement source ledger is invalid")
        period(source.get("period"))
    for row in rows:
        month, elo = period(row["month"]), rating(row["standard_elo"])
        if (month > CUTOFF or row.get("source") not in allowed or row.get("source_point") is not True
                or type(row.get("source_line_number")) is not int or row["source_line_number"] < 1
                or not isinstance(row.get("source_line"), str) or not row["source_line"]):
            raise ValueError("Invalid source-specific list supplement row")
        matches = [item for item in ledger if item.get("period") == month and item.get("source") == row["source"]
            and item.get("source_url", item.get("url")) == row["source_url"]
            and item.get("archive_sha256", item.get("sha256")) == row["archive_sha256"]
            and item.get("archive_member", item.get("member")) == row["archive_member"]
            and item.get("source_line_number", item.get("row_line_number")) == row["source_line_number"]
            and item.get("source_line", item.get("row_text")) == row["source_line"]
            and item.get("player_unlisted") is not True]
        if not matches:
            raise ValueError("Normalized supplement row lacks exact archive-ledger provenance")
        if row["source"] == "fide_official_list_archive" and (person["canonical_id"] not in re.findall(r"[0-9]+", row["source_line"])
                or str(elo) not in re.findall(r"[0-9]+", row["source_line"])
                or _source_name(person["name"]) not in _source_name(row["source_line"])):
            raise ValueError("Official archive line lacks the frozen identity and rating tokens")
    counts = {source: sum(row["source"] == source for row in rows) for source in allowed}
    reported = adjudication.get("rows_by_source", {})
    if set(reported) - allowed or {source: reported.get(source, 0) for source in allowed} != counts or not counts["fide_official_list_archive"]:
        raise ValueError("Supplement primary/secondary row counts differ")
    frozen = payload.get("frozen_snapshot", {})
    frozen_match = [row for row in rows if row["month"] == person["snapshot"]
        and row["source"] == "fide_official_list_archive" and row["standard_elo"] == person["snapshot_elo"]
        and all(frozen.get(key.replace("source_url", "archive_url")) == row[key] for key in keys)]
    if (frozen.get("month") != person["snapshot"] or frozen.get("rating") != person["snapshot_elo"] or not frozen_match
            or not any(row["source"] == "fide_official_list_archive" and row["source_url"] == entry["source_url"] for row in rows)):
        raise ValueError("Supplement lacks exact primary frozen-snapshot and anchor evidence")
    coverage, termination = payload.get("coverage"), payload.get("career_termination")
    if (not isinstance(coverage, dict) or adjudication.get("coverage") != coverage
            or not isinstance(termination, dict) or adjudication.get("career_termination") != termination):
        raise ValueError("Supplement coverage or career-termination provenance differs")
    official_periods = coverage.get("official_list_periods", [])
    required_periods = [f"{year}-{month:02d}" for year in (2010, 2011) for month in (1, 3, 5, 7, 9, 11)]
    required_periods += [f"2012-{month:02d}" for month in (1, 3, 5, 7, 8, 9, 10, 11, 12)]
    required_periods += [f"2013-{month:02d}" for month in range(1, 13)]
    if (not official_periods or official_periods != sorted(set(official_periods))
            or official_periods != required_periods
            or coverage.get("official_list_first") != official_periods[0]
            or coverage.get("official_list_last") != official_periods[-1]
            or any(not "2010-01" <= period(month) <= "2013-12" for month in official_periods)
            or not {row["month"] for row in rows if row["source"] == "fide_official_list_archive"} <= set(official_periods)):
        raise ValueError("Supplement official-list coverage is inconsistent")
    if {item["period"] for item in ledger if item["source"] == "fide_official_list_archive"} != set(required_periods):
        raise ValueError("Supplement official-list source ledger lacks a required published period")
    historic_months = sorted(row["month"] for row in rows if row["source"] == "olimpbase_transcription")
    if historic_months and (coverage.get("historical_transcription_first") != historic_months[0]
            or coverage.get("historical_transcription_last") != historic_months[-1]):
        raise ValueError("Supplement historical-transcription coverage is inconsistent")
    if (termination.get("birth_date") != person["exact_dob_frozen"]
            or termination.get("source_type") != "official_national_federation_obituary"
            or termination.get("source_url") != "https://www.ruchess.ru/news/all/pogib_igor_kurnosov/"
            or not re.fullmatch(r"[a-f0-9]{64}", str(termination.get("source_sha256", "")))
            or termination.get("posthumous_2014_2023_monthly_coverage_claimed") is not False
            or not termination.get("excerpt") or not termination.get("coverage_note")):
        raise ValueError("Supplement career-termination evidence is incomplete")
    if date.fromisoformat(termination["date"]) > date.fromisoformat(CUTOFF + "-01"):
        raise ValueError("Career-termination evidence is after label cutoff")
    date.fromisoformat(termination["source_publication_date"])
    return {"adjudication": adjudication, "archive_ledger": ledger, "coverage": coverage,
        "career_termination": termination, "raw_sha256": entry["raw_sha256"], "source_url": entry["source_url"]}

def _coverage_summary(entries):
    audits = {cid: item["entry"].get("source_coverage_audit") for cid, item in sorted(entries.items())}
    present = [item for item in audits.values() if item is not None]
    snapshot_ids = [cid for cid, item in sorted(entries.items()) if item["entry"].get("snapshot_audit_required") is True]
    disagreements = {cid: item["snapshot_disagreement"] for cid, item in sorted(entries.items()) if item.get("snapshot_disagreement")}
    supplements = {cid: item["list_supplement"] for cid, item in sorted(entries.items()) if item.get("list_supplement")}
    return {"source_coverage_audits": audits, "source_coverage_checked_n": len(present),
        "source_coverage_resolved_n": sum(item["unresolved"] is False for item in present),
        "source_coverage_unresolved_n": sum(item["unresolved"] is True for item in present),
        "source_coverage_unresolved_person_ids": [cid for cid, item in audits.items() if item is not None and item["unresolved"]],
        "snapshot_audit_required_n": len(snapshot_ids), "snapshot_audit_required_person_ids": snapshot_ids,
        "snapshot_disagreement_n": len(disagreements), "snapshot_disagreement_proofs": disagreements,
        "list_supplement_n": len(supplements), "list_supplements": supplements}

def read_acquisition(acquisition_dir, people, dataset_audit=None, repo_root=None):
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
            for field in ("source_roster", "source_roster_sha256"):
                if field in person and entry.get(field) != person[field]:
                    raise ValueError(f"Rating-history entry changed frozen person field: {field}")
            provider = entry.get("source_provider", "fide_official_chart")
            url = {"fide_official_chart": f"https://ratings.fide.com/a_chart_data.phtml?event={cid}&period=0",
                "lichess_fide_history": f"https://lichess.org/api/fide/player/{cid}/ratings"}.get(provider)
            if provider == "fide_official_list_archive" and _official_archive_url(entry.get("source_url")):
                url = entry["source_url"]
            if url is None or entry.get("source_url") != url:
                raise ValueError("Rating-history source URL/provider differs from requested person")
            if "snapshot_audit_required" in entry and type(entry["snapshot_audit_required"]) is not bool:
                raise ValueError("Invalid rating-history snapshot audit flag")
            _verify_source_coverage_audit(base, file_hashes, entry, provider)
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
            raw_name = entry.get("raw_history_file", f"raw/{cid}.json.gz")
            if ((provider == "fide_official_list_archive" and raw_name != f"list-supplements/raw/{cid}.json.gz")
                    or (provider != "fide_official_list_archive" and raw_name != f"raw/{cid}.json.gz")):
                raise ValueError("Unexpected rating-history raw response path")
            if raw_name not in file_hashes:
                raise ValueError("Unsealed rating-history raw response")
            raw = gzip.decompress(safe_file(base, raw_name).read_bytes())
            if hashlib.sha256(raw).hexdigest() != entry["raw_sha256"]:
                raise ValueError("Rating-history raw-response fingerprint differs")
            supplement = (_verify_list_supplement(base, file_hashes, person, entry, normalized, raw, repo_root)
                if provider == "fide_official_list_archive" else None)
            disagreement = _verify_snapshot_disagreement(base, file_hashes, person, entry, normalized)
            rows = normalized["standard_history"]
            if provider != "fide_official_list_archive" and any("source" in row and row["source"] != provider for row in rows):
                raise ValueError("API history cannot override its source provider per row")
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
                "source": row["source"] if supplement else provider, "source_url": row["source_url"] if supplement else url,
                "source_raw_sha256": entry["raw_sha256"],
                "peak_months_complete": complete, "history_compression": normalized.get("history_compression")}
                for row in rows]
            if disagreement:
                records.append({"canonical_id": cid, "period": person["snapshot"], "rating": person["snapshot_elo"],
                    "source": "frozen_cohort_snapshot", "source_roster": person["source_roster"],
                    "source_roster_sha256": person["source_roster_sha256"], "source_name": person["name"],
                    "snapshot_disagreement_rule_id": SNAPSHOT_DISAGREEMENT_RULE,
                    "official_source_raw_sha256": entry["raw_sha256"]})
            entries[cid] = {"entry": entry, "records": records, "snapshot_disagreement": disagreement, "list_supplement": supplement}
            if dataset_audit is not None:
                dataset_audit.update(_coverage_summary(entries))
        if "source_provider_counts" in manifest:
            reported = manifest["source_provider_counts"]
            if set(reported) - set(FIDE_PROVIDERS) or {p: reported.get(p, 0) for p in FIDE_PROVIDERS} != provider_counts:
                raise ValueError("Rating-history provider counts disagree with source entries")
        provenance.append({"manifest_path": manifest_path.relative_to(acquisition_dir).as_posix(),
            "manifest_sha256": sha256(manifest_path), "shard_index": manifest["shard_index"],
            "selected_n": manifest["selected_n"], "files_n": len(file_hashes), "source_provider_counts": provider_counts})
    if len(shard_counts) != 1 or shard_indices != set(range(next(iter(shard_counts)))):
        raise ValueError("Rating-history acquisition shard set is incomplete")
    if set(entries) != set(people):
        raise ValueError("Rating histories do not cover all fixed people")
    coverage_summary = _coverage_summary(entries)
    if coverage_summary["source_coverage_unresolved_n"] or coverage_summary["snapshot_audit_required_n"]:
        raise DatasetBuildError("Rating-history source coverage or frozen snapshot audit remains unresolved")
    return entries, provenance

def combine_person(person, official_records, historical_records, snapshot_disagreement=None, adjudications=None):
    """Identify peak values without choosing between conflicting source rows.

    A conflicting month may remain unresolved only when every candidate is at
    or below a directly observed, unambiguous peak in another month. Such a
    month has no chosen rating and cannot supply a measured peak date.
    """
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
        if source not in (*FIDE_PROVIDERS, "olimpbase_transcription", "frozen_cohort_snapshot"):
            raise ValueError("History has an unknown source convention")
        if source == "frozen_cohort_snapshot" and (snapshot_disagreement is None or month != person["snapshot"]
                or elo != person["snapshot_elo"] or record.get("source_roster") != person.get("source_roster")
                or record.get("source_roster_sha256") != person.get("source_roster_sha256")
                or record.get("snapshot_disagreement_rule_id") != SNAPSHOT_DISAGREEMENT_RULE):
            raise ValueError("Frozen snapshot candidate lacks verified official disagreement proof")
        entry = by_month.setdefault(month, {"canonical_id": cid, "period": month, "rating": elo,
            "sources": set(), "source_records": [], "candidate_ratings": set()})
        entry["candidate_ratings"].add(elo)
        entry["sources"].add(source)
        entry["source_records"].append(dict(record))
    decisions = adjudications or {}
    for month, adjudication in decisions.items():
        source_month = by_month.get(month)
        if (month == person["snapshot"] or source_month is None or adjudication["canonical_id"] != cid
                or adjudication["period"] != month or adjudication["decision"] != POINT_ADJUDICATION_POLICY
                or len(source_month["candidate_ratings"]) < 2
                or adjudication["selected_rating"] not in source_month["candidate_ratings"]
                or set(adjudication["rejected_ratings"]) != source_month["candidate_ratings"] - {adjudication["selected_rating"]}
                or any(rec["source"] == "fide_official_list_archive" and rec["rating"] != adjudication["selected_rating"]
                    for rec in source_month["source_records"])):
            raise ValueError("Original-list adjudication does not exactly resolve known derived-source candidates")
    # Check the original candidate inventory before adding any corroboration,
    # then check every decision again against all added original-list points.
    for adjudication in decisions.values():
        for point in adjudication["verified_points"]:
            entry = by_month.setdefault(point["period"], {"canonical_id": cid, "period": point["period"], "rating": point["rating"],
                "sources": set(), "source_records": [], "candidate_ratings": set()})
            entry["candidate_ratings"].add(point["rating"])
            entry["sources"].add("fide_official_list_archive")
            entry["source_records"].append({**point, "point_adjudication_source_file": adjudication["source_file"],
                "point_adjudication_source_file_sha256": adjudication["source_file_sha256"]})
    for month, adjudication in decisions.items():
        source_month = by_month[month]
        if (source_month["candidate_ratings"] != {adjudication["selected_rating"], *adjudication["rejected_ratings"]}
                or any(rec["source"] == "fide_official_list_archive" and rec["rating"] != adjudication["selected_rating"]
                    for rec in source_month["source_records"])):
            raise ValueError("Original-list known candidates changed after cross-file corroboration")
        source_month["adjudication"] = adjudication
    if not by_month:
        raise ValueError("No published standard rating before cutoff")
    rows = [by_month[key] for key in sorted(by_month)]
    for row in rows:
        row["candidate_ratings"] = sorted(row["candidate_ratings"])
        adjudication = row.get("adjudication")
        row["adjudicated_period"] = adjudication is not None
        row["ambiguous_period"] = len(row["candidate_ratings"]) > 1 and not row["adjudicated_period"]
        row["rating"] = adjudication["selected_rating"] if adjudication else (None if row["ambiguous_period"] else row["candidate_ratings"][0])
        row["candidate_lower"] = row["candidate_ratings"][0]
        row["candidate_upper"] = row["candidate_ratings"][-1]
    unambiguous = [row for row in rows if not row["ambiguous_period"]
        and any(not rec.get("derived_state", False) for rec in row["source_records"])]
    if not unambiguous:
        raise ValueError("No unambiguous directly retained rating remains to identify peak")
    peak = max(row["rating"] for row in unambiguous)
    snapshot = by_month.get(person["snapshot"])
    if snapshot is None:
        raise ValueError("Frozen snapshot month absent from merged histories")
    if snapshot_disagreement:
        if (snapshot_disagreement["canonical_id"] != cid or snapshot_disagreement["snapshot_month"] != person["snapshot"]
                or snapshot_disagreement["frozen_snapshot_elo"] != person["snapshot_elo"]
                or not snapshot["ambiguous_period"] or "frozen_cohort_snapshot" not in snapshot["sources"]
                or not any(rec["source"] == "fide_official_chart" and rec["rating"] == snapshot_disagreement["official_snapshot_elo"]
                    for rec in snapshot["source_records"])):
            raise ValueError("Snapshot disagreement proof does not match merged candidates")
    elif snapshot["ambiguous_period"]:
        raise ValueError("Conflicting ratings for frozen snapshot month")
    elif snapshot["rating"] != person["snapshot_elo"]:
        raise ValueError("History snapshot rating differs from frozen snapshot")
    if peak < person["snapshot_elo"]:
        raise ValueError("Observed peak is below frozen snapshot rating")
    ambiguous = [row for row in rows if row["ambiguous_period"]]
    if any(row["candidate_upper"] > peak for row in ambiguous):
        raise ValueError("Unresolved source-period conflict can change the confirmed peak value")
    for row in rows:
        row["resolution_policy"] = POINT_ADJUDICATION_POLICY if row["adjudicated_period"] else (
            CONFLICT_POLICY if row["ambiguous_period"] else "unambiguous_source_value")
        if row["adjudicated_period"]:
            for rec in row["source_records"]:
                rec.update(point_adjudication_policy=POINT_ADJUDICATION_POLICY,
                    point_adjudication_status="supports_selected_rating" if rec["rating"] == row["rating"] else "rejected_derived_rating",
                    point_selected_rating=row["rating"], point_observed_source_candidate_ratings=list(row["candidate_ratings"]),
                    point_adjudication_source_file=row["adjudication"]["source_file"],
                    point_adjudication_source_file_sha256=row["adjudication"]["source_file_sha256"])
        if row["ambiguous_period"]:
            for rec in row["source_records"]:
                rec.update(period_conflict_handling=CONFLICT_POLICY,
                    period_candidate_ratings=list(row["candidate_ratings"]),
                    period_candidate_lower=row["candidate_lower"], period_candidate_upper=row["candidate_upper"],
                    period_rating_not_selected=True)
    # Reconstructed states align snapshots; they are not observed peak dates.
    peak_rows = [row for row in rows if not row["ambiguous_period"] and row["rating"] == peak
        and any(not rec.get("derived_state", False) for rec in row["source_records"])]
    if not peak_rows:
        raise ValueError("Peak value has no directly retained source point")
    providers = sorted({source for row in rows for source in row["sources"] if source in FIDE_PROVIDERS})
    derived_n = sum(bool(rec.get("derived_state")) for rec in official_records if rec["period"] <= CUTOFF)
    info = {"rating": peak, "label_end_period": CUTOFF, "feature_reference_snapshot": REFERENCE_SNAPSHOT,
        "peak_periods": ";".join(row["period"] for row in peak_rows),
        "peak_sources": ";".join(sorted({rec["source"] for row in peak_rows for rec in row["source_records"] if rec["rating"] == peak})),
        "peak_periods_complete": "lichess_fide_history" not in providers
            and all(rec.get("peak_months_complete", True) for rec in official_records if rec["source"] in FIDE_PROVIDERS)
            and not any(row["candidate_upper"] == peak for row in ambiguous),
        "history_source_provider": ";".join(providers), "derived_snapshot_record_n": derived_n,
        "ambiguous_period_n": len(ambiguous), "ambiguous_periods": ";".join(row["period"] for row in ambiguous),
        "period_conflict_resolution_policy": CONFLICT_POLICY,
        "adjudicated_period_n": sum(row["adjudicated_period"] for row in rows),
        "adjudicated_periods": ";".join(row["period"] for row in rows if row["adjudicated_period"]),
        "history_first_period": rows[0]["period"], "history_last_period": rows[-1]["period"], "history_n": len(rows),
        "fide_history_n": sum(bool(set(FIDE_PROVIDERS) & row["sources"]) for row in rows),
        "official_chart_history_n": sum("fide_official_chart" in row["sources"] for row in rows),
        "lichess_history_n": sum("lichess_fide_history" in row["sources"] for row in rows),
        "official_list_history_n": sum("fide_official_list_archive" in row["sources"] for row in rows),
        "olimpbase_history_n": sum("olimpbase_transcription" in row["sources"] for row in rows),
        "pre2003_history_n": sum(row["period"] < "2003-04" for row in rows), "history_coverage": COVERAGE}
    for row in rows:
        row["sources"] = ";".join(sorted(row["sources"]))
        row.pop("adjudication", None)
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
        audit["point_adjudication_inputs"] = [{"path": path.relative_to(root).as_posix(), "sha256": sha256(path)}
            for path in sorted((root / STUDY / "adjudications").glob("*.json"))]
        adjudications, adjudication_provenance = load_point_adjudications(root, people)
        audit["point_adjudications"] = adjudication_provenance
        audit["point_adjudication_n"] = len(adjudication_provenance)
        audit["point_adjudication_policy"] = POINT_ADJUDICATION_POLICY
        official, provenance = read_acquisition(acquisition_dir, people, dataset_audit=audit, repo_root=root)
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
                info, records, ignored = combine_person(person, official[cid]["records"], old_by_id[cid],
                    snapshot_disagreement=official[cid]["snapshot_disagreement"], adjudications=adjudications.get(cid))
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
        audit["period_conflict_resolution_policy"] = CONFLICT_POLICY
        audit["ambiguous_period_person_ids"] = [cid for cid in sorted(labels) if labels[cid]["ambiguous_period_n"]]
        audit["ambiguous_period_n"] = sum(labels[cid]["ambiguous_period_n"] for cid in labels)
        audit["ambiguous_period_resolutions"] = [{"canonical_id": row["canonical_id"], "period": row["period"],
            "candidate_ratings": row["candidate_ratings"], "candidate_upper": row["candidate_upper"],
            "confirmed_peak": labels[row["canonical_id"]]["rating"], "rating_selected": False,
            "resolution_policy": CONFLICT_POLICY} for row in history_rows if row["ambiguous_period"]]
        audit["snapshot_disagreements"] = [{"canonical_id": cid, "snapshot_month": proof["snapshot_month"],
            "candidate_ratings": sorted([proof["frozen_snapshot_elo"], proof["official_snapshot_elo"]]),
            "identified_peak": labels[cid]["rating"] if cid in labels else None,
            "snapshot_rating_selected": False, "resolution_policy": CONFLICT_POLICY,
            "frozen_source_roster_sha256": proof["frozen_source_roster_sha256"],
            "official_source_raw_sha256": proof["official_evidence"]["raw_sha256"]}
            for cid, proof in audit["snapshot_disagreement_proofs"].items()]
        audit["point_adjudication_resolutions"] = [{"canonical_id": item["canonical_id"], "period": item["period"],
            "selected_rating": item["selected_rating"], "rejected_ratings": item["rejected_ratings"],
            "decision": POINT_ADJUDICATION_POLICY, "source_file": item["source_file"], "source_file_sha256": item["source_file_sha256"],
            "identified_peak": labels[item["canonical_id"]]["rating"] if item["canonical_id"] in labels else None}
            for item in adjudication_provenance]
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
        writer = csv.DictWriter(text, fieldnames=("canonical_id", "period", "rating", "sources", "candidate_ratings",
            "ambiguous_period", "adjudicated_period", "candidate_lower", "candidate_upper", "resolution_policy", "source_records"))
        writer.writeheader()
        for row in history_rows:
            writer.writerow({**row, "candidate_ratings": json.dumps(row["candidate_ratings"]),
                "source_records": json.dumps(row["source_records"], ensure_ascii=False, sort_keys=True)})
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
            "ambiguous_period_n": audit["ambiguous_period_n"],
            "ambiguous_period_people_n": len(audit["ambiguous_period_person_ids"]),
            "period_conflict_resolution_policy": CONFLICT_POLICY,
            **{key: audit[key] for key in ("source_coverage_checked_n", "source_coverage_resolved_n",
                "source_coverage_unresolved_n", "snapshot_audit_required_n")},
            "snapshot_disagreement_n": audit["snapshot_disagreement_n"],
            "snapshot_disagreements": audit["snapshot_disagreements"],
            "list_supplement_n": audit["list_supplement_n"], "list_supplements": audit["list_supplements"],
            "point_adjudication_n": len(adjudication_provenance), "point_adjudication_policy": POINT_ADJUDICATION_POLICY,
            "point_adjudications": adjudication_provenance, "point_adjudication_resolutions": audit["point_adjudication_resolutions"],
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
    if manifest.get("period_conflict_resolution_policy") != CONFLICT_POLICY:
        raise ValueError("Peak source-conflict policy differs")
    if (manifest.get("point_adjudication_policy") != POINT_ADJUDICATION_POLICY
            or manifest.get("point_adjudication_n") != len(manifest.get("point_adjudications", []))):
        raise ValueError("Peak original-list point-adjudication inventory differs")
    for item in manifest["point_adjudications"]:
        if sha256(safe_file(root, item["source_file"])) != item["source_file_sha256"]:
            raise ValueError("Frozen point-adjudication source changed")
        for point in item["verified_points"]:
            if sha256(safe_file(root, point["source_archive_file"])) != point["source_archive_sha256"]:
                raise ValueError("Frozen original-list source archive changed")
    checked, resolved, unresolved, snapshot_required = (manifest.get(key) for key in
        ("source_coverage_checked_n", "source_coverage_resolved_n", "source_coverage_unresolved_n", "snapshot_audit_required_n"))
    if (any(type(value) is not int or value < 0 for value in (checked, resolved, unresolved, snapshot_required))
            or checked != resolved + unresolved or unresolved or snapshot_required):
        raise ValueError("Peak source coverage or snapshot audit is unresolved")
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
        for name in ("history_n", "fide_history_n", "official_chart_history_n", "lichess_history_n", "official_list_history_n", "olimpbase_history_n", "pre2003_history_n", "derived_snapshot_record_n"):
            if not re.fullmatch(r"[0-9]+", row[name]):
                raise ValueError("Invalid history count")
            row[name] = int(row[name])
        if row["history_n"] < len(months) or row["fide_history_n"] <= 0:
            raise ValueError("Peak history has insufficient source records")
        if not re.fullmatch(r"[0-9]+", row["ambiguous_period_n"]):
            raise ValueError("Invalid ambiguous-period count")
        row["ambiguous_period_n"] = int(row["ambiguous_period_n"])
        ambiguous_months = row["ambiguous_periods"].split(";") if row["ambiguous_periods"] else []
        if (len(ambiguous_months) != row["ambiguous_period_n"] or ambiguous_months != sorted(set(ambiguous_months))
                or any(period(x) > CUTOFF for x in ambiguous_months) or set(ambiguous_months) & set(months)
                or row["ambiguous_period_n"] + len(months) > row["history_n"]
                or row["period_conflict_resolution_policy"] != CONFLICT_POLICY):
            raise ValueError("Ambiguous source months are inconsistent with the identified peak")
        if not re.fullmatch(r"[0-9]+", row["adjudicated_period_n"]):
            raise ValueError("Invalid original-list adjudication count")
        row["adjudicated_period_n"] = int(row["adjudicated_period_n"])
        adjudicated_months = row["adjudicated_periods"].split(";") if row["adjudicated_periods"] else []
        expected_months = sorted(item["period"] for item in manifest["point_adjudications"] if item["canonical_id"] == row["canonical_id"])
        if (len(adjudicated_months) != row["adjudicated_period_n"] or adjudicated_months != expected_months
                or set(adjudicated_months) & set(ambiguous_months) or row["snapshot"] in adjudicated_months):
            raise ValueError("Original-list adjudicated periods differ from verified source inventory")
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
