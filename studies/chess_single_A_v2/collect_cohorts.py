#!/usr/bin/env python3
"""Acquire expanded chess cohorts; never fit models or compute BaZi statistics.

Frozen metadata decisions take precedence over current Wikidata. New queries
require best-rank, exact Gregorian DOB and an unambiguous northern birthplace.
All eligible ties are kept. Failed requests stop, leaving resumable cache.
"""
from __future__ import annotations

import argparse
import csv
from datetime import date, datetime, timezone
import hashlib
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import re
import subprocess
import time
import zipfile

import pandas as pd
try:
    import requests
except ImportError:  # Offline unit tests do not require an HTTP client.
    requests = None

SOURCE_REVISION = "20f743ef8eda060d34121530323893dffc938aa6"
ARCHIVE_HASHES = {
    "2013": "5f7e6e215d323da848857138054866e41f0e0f5e21160c6553a7fc1cfd74e78a",
    "2023": "a2123b8d3b8520456ef5ece135442b2491586ba10b69c95c720c7885a70664bb",
}
ENDPOINT = "https://query.wikidata.org/sparql"
GREGORIAN = "Q1985727"
SEED_PATHS = {
    "2013": ["chess_north_v2/candidate_audit_2013_M.csv",
             "chess_north_v3/primary_north_top_2013_M.csv"],
    "2023": ["chess_2023_cohorts_v1/candidate_audit_2023_M.csv"],
}
LEGACY_PATHS = [f"chess_north_v3/primary_north_top_{year}_{sex}.csv"
                for year in (1994, 2013) for sex in ("M", "F")]
EVIDENCE_FIELDS = ["hemisphere_status", "wikidata_person_qids", "birthplace_qids",
                   "birthplace_labels", "birthplace_latitudes", "birthplace_longitudes"]
METADATA_FIELDS = set(EVIDENCE_FIELDS) | {"identity_bridge_modern_fide_id", "exact_dob_frozen",
    "birthplace_hemisphere", "evidence_eligible", "evidence_source", "dob_calendar_status",
    "evidence_retrieved_utc", "legacy_snapshot_eligible", "evidence_reused_from_snapshot"}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def canonical_id(row) -> str:
    value = str(row.get("identity_bridge_modern_fide_id", "")).strip()
    if not value or value.lower() in {"nan", "none"}:
        value = str(row["fide_id"]).strip()
    if not re.fullmatch(r"[0-9]+", value) or int(value) <= 0:
        raise ValueError(f"Invalid canonical FIDE ID {value!r}")
    return str(int(value))


def truth(value) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes"}


def valid_dob(value: str, year: str, known_year=None):
    value = str(value).strip()
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return None, "invalid_or_missing_exact_dob"
    if parsed.isoformat() != value:
        return None, "invalid_iso_dob"
    if parsed > date(int(year), 1, 1):
        return None, "dob_after_snapshot"
    if known_year is not None and not pd.isna(known_year):
        ky = str(known_year).strip()
        if re.fullmatch(r"\d+(?:\.0)?", ky) and int(float(ky)) > 0:
            if parsed.year != int(float(ky)):
                return None, "birth_year_mismatch"
    return value, "exact_dob_year_agrees"


def import_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def parse_population(path: Path, year: str, parser, minimum_rows=80000):
    raw_bytes = path.read_bytes()
    try:
        text = raw_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw_bytes.decode("latin-1")
    lines = text.splitlines()
    candidates = [(i, line) for i, line in enumerate(lines[:20])
                  if "name" in line.lower() and "flag" in line.lower()
                  and "sex" in line.lower() and "id" in line.lower()]
    if len(candidates) != 1:
        raise ValueError("Expected one FIDE fixed-width header in first20 lines")
    header_index, header = candidates[0]
    expected_label = f"JAN{year[-2:]}"
    if not re.search(rf"\b(?:{expected_label}|SRtng)\b", header, flags=re.I):
        raise ValueError(f"FIDE rating header does not match {expected_label}")
    table = parser._parse_fixed_width_lines(header, lines[header_index + 1:])
    if len(table) < minimum_rows:
        raise ValueError(f"FIDE population unexpectedly small: {len(table)}")
    for column in ("fide_id", "rating"):
        valid = table[column].astype(str).str.fullmatch(r"[0-9]+")
        if not valid.all():
            raise ValueError(f"Noninteger {column} in {int((~valid).sum())} FIDE rows")
        table[column] = table[column].astype("int64")
    table["sex"] = table["sex"].astype(str).str.upper().str.strip()
    if not table["sex"].isin(["M", "F"]).all():
        raise ValueError("Unrecognized sex code in FIDE population")
    if not table["rating"].between(0, 3500).all():
        raise ValueError("Implausible FIDE Elo values")
    if (table["fide_id"] <= 0).any() or table["fide_id"].duplicated().any():
        raise ValueError("Nonpositive or duplicate FIDE IDs")
    flag = table["flag"].astype(str).str.lower()
    table["active"] = ~flag.str.contains("i", regex=False)
    table = table[table["active"] & (table["rating"] > 0) & table["sex"].eq("M")].copy()
    table["fide_id"] = table["fide_id"].astype(str)
    table["snapshot"] = f"{year}-01"
    table.sort_values(["rating", "name", "fide_id"], ascending=[False, True, True], inplace=True)
    return table.reset_index(drop=True)


def download_population(year: str, cache: Path, session, timeout=20):
    archive = cache / f"standard_jan{year[-2:]}frl.zip"
    url = f"https://ratings.fide.com/download/{archive.name}"
    if not archive.exists():
        response = session.get(url, timeout=timeout)
        response.raise_for_status()
        if not zipfile.is_zipfile(io.BytesIO(response.content)):
            raise ValueError(f"FIDE response is not a ZIP for {year}")
        temp = archive.with_suffix(".download")
        temp.write_bytes(response.content)
        temp.replace(archive)
    if sha256(archive) != ARCHIVE_HASHES[year]:
        raise ValueError(f"FIDE {year} archive differs from the observed frozen archive hash")
    with zipfile.ZipFile(archive) as z:
        names = [n for n in z.namelist() if n.lower().endswith(".txt")]
        if len(names) != 1:
            raise ValueError("FIDE archive must contain exactly one text member")
        member = names[0]
        text_path = cache / f"population_{year}.txt"
        data = z.read(member)
        if not text_path.exists() or text_path.read_bytes() != data:
            text_path.write_bytes(data)
    return text_path, {"url": url, "archive": str(archive), "archive_sha256": sha256(archive),
                       "zip_member": member, "text_sha256": sha256(text_path)}


def load_seeds(root: Path):
    seeds = {"2013": {}, "2023": {}}
    inputs = []
    for year, paths in SEED_PATHS.items():
        for rel in paths:
            path = root / rel
            if not path.exists():
                raise FileNotFoundError(f"Required frozen seed missing: {rel}")
            inputs.append({"path": rel, "sha256": sha256(path)})
            with path.open(encoding="utf-8-sig", newline="") as f:
                for row in csv.DictReader(f):
                    fid = canonical_id(row)
                    dob = row.get("exact_dob_frozen") or row.get("exact_dob_north_v2") or ""
                    eligible = truth(row.get("eligible_north_primary_v2", row.get("eligible_north_2023", "")))
                    meta = {key: row.get(key, "") for key in EVIDENCE_FIELDS}
                    meta.update({"identity_bridge_modern_fide_id": fid, "exact_dob_frozen": dob,
                                 "birthplace_hemisphere": row.get("birthplace_hemisphere", "unknown"),
                                 "evidence_eligible": eligible, "evidence_source": rel,
                                 "legacy_snapshot_eligible": eligible,
                                 "dob_calendar_status": "legacy_frozen_convention_not_requeried",
                                 "evidence_retrieved_utc": "legacy_frozen"})
                    previous = seeds[year].get(fid)
                    if previous is not None:
                        for field in ("exact_dob_frozen", "birthplace_hemisphere"):
                            if previous[field] != meta[field]:
                                raise ValueError(f"Conflicting frozen seed {year}/{fid}/{field}: {previous['evidence_source']} versus {rel}")
                    seeds[year][fid] = meta
    return seeds, inputs


def load_legacy_ids(root: Path):
    ids = set()
    inputs = []
    for rel in LEGACY_PATHS:
        path = root / rel
        inputs.append({"path": rel, "sha256": sha256(path)})
        with path.open(encoding="utf-8-sig", newline="") as f:
            ids.update(canonical_id(row) for row in csv.DictReader(f))
    return ids, inputs


def query_text(ids):
    values = " ".join(json.dumps(fid) for fid in ids)
    return """PREFIX wdt:<http://www.wikidata.org/prop/direct/>
PREFIX p:<http://www.wikidata.org/prop/>
PREFIX psv:<http://www.wikidata.org/prop/statement/value/>
PREFIX wikibase:<http://wikiba.se/ontology#>
SELECT ?fide ?person ?dob ?precision ?calendar ?before ?after ?birthplace ?lat ?lon WHERE {
 VALUES ?fide { VALUES_HERE }
 ?person wdt:P1440 ?fide .
 OPTIONAL { ?person p:P569 ?statement . ?statement a wikibase:BestRank ; psv:P569 ?value .
  ?value wikibase:timeValue ?dob ; wikibase:timePrecision ?precision ; wikibase:timeCalendarModel ?calendar .
  OPTIONAL {?value wikibase:timeBefore ?before} OPTIONAL {?value wikibase:timeAfter ?after}
 }
 OPTIONAL { ?person wdt:P19 ?birthplace . OPTIONAL {
  ?birthplace p:P625/psv:P625 ?coord .
  ?coord wikibase:geoLatitude ?lat ; wikibase:geoLongitude ?lon ;
         wikibase:geoGlobe <http://www.wikidata.org/entity/Q2> . } }
} ORDER BY ?fide ?person ?birthplace""".replace("VALUES_HERE", values)


def fetch_records(ids, session, cache, cache_path, timeout=20, retries=3, delay=.5):
    """Only successful responses, including genuine zero matches, enter cache."""
    missing = [fid for fid in ids if fid not in cache]
    if not missing:
        return
    last_error = None
    for attempt in range(retries):
        try:
            response = session.get(ENDPOINT, params={"query": query_text(missing), "format": "json"}, timeout=timeout)
            response.raise_for_status()
            payload = response.json()
            bindings = payload["results"]["bindings"]
            if not isinstance(bindings, list):
                raise ValueError("Invalid SPARQL bindings")
            parsed = {fid: [] for fid in missing}
            for binding in bindings:
                fid = str(binding["fide"]["value"])
                if fid not in parsed:
                    raise ValueError("SPARQL returned an unrequested FIDE ID")
                parsed[fid].append({key: value["value"] for key, value in binding.items()})
            now = datetime.now(timezone.utc).isoformat()
            for fid in missing:
                cache[fid] = {"retrieved_utc": now, "records": parsed[fid]}
            write_json(cache_path, cache)
            if delay:
                time.sleep(delay)
            print(f"[wikidata] successful IDs={len(missing)}, total_cached={len(cache)}", flush=True)
            return
        except (OSError, ValueError, KeyError) as error:
            last_error = error
            if attempt + 1 < retries:
                time.sleep(min(8, 2 ** (attempt + 1)))
    raise RuntimeError(f"Wikidata acquisition failed; no negative cache written: {last_error}")


def metadata_from_records(fid, item):
    records = item["records"]
    qids = sorted({r["person"].rsplit("/", 1)[-1] for r in records})
    exact = set()
    disallowed_calendar = False
    for record in records:
        if "dob" not in record:
            continue
        calendar = record.get("calendar", "").rsplit("/", 1)[-1]
        if calendar != GREGORIAN:
            disallowed_calendar = True
            continue
        if (int(record.get("precision", "0")) >= 11
                and int(record.get("before", "0")) == 0
                and int(record.get("after", "0")) == 0):
            exact.add(record["dob"].lstrip("+")[:10])
    lats = sorted({float(r["lat"]) for r in records if r.get("lat") is not None
                   and math.isfinite(float(r["lat"])) and -90 <= float(r["lat"]) <= 90})
    hemis = {"north" if lat > 0 else "south" if lat < 0 else "equator" for lat in lats}
    hemi = next(iter(hemis)) if len(qids) == 1 and len(hemis) == 1 else "unknown"
    eligible = len(qids) == 1 and len(exact) == 1 and hemi == "north" and not disallowed_calendar
    return {"identity_bridge_modern_fide_id": fid,
            "exact_dob_frozen": next(iter(exact)) if len(exact) == 1 else "",
            "birthplace_hemisphere": hemi, "evidence_eligible": eligible,
            "evidence_source": "new_wikidata_best_rank_query",
            "dob_calendar_status": "non_gregorian_conflict" if disallowed_calendar else "explicit_gregorian_required",
            "evidence_retrieved_utc": item["retrieved_utc"],
            "wikidata_person_qids": ";".join(qids),
            "birthplace_qids": ";".join(sorted({r["birthplace"].rsplit("/", 1)[-1] for r in records if r.get("birthplace")})),
            "birthplace_labels": "", "birthplace_latitudes": ";".join(map(str, lats)),
            "birthplace_longitudes": ";".join(sorted({r["lon"] for r in records if r.get("lon")})),
            "hemisphere_status": "unique_hemisphere" if len(hemis) == 1 else "unknown_or_conflicting"}


def adjudicate(row, evidence, year):
    result = dict(row)
    # Evidence never overrides the Elo, year, sex, or name in this snapshot.
    result.update({key: value for key, value in evidence.items() if key in METADATA_FIELDS})
    dob, status = valid_dob(result["exact_dob_frozen"], year, row.get("birth_year"))
    result["eligible"] = bool(evidence["evidence_eligible"] and dob and evidence["birthplace_hemisphere"] == "north")
    result["dob_validation_status"] = status
    result["exclusion_reason"] = "" if result["eligible"] else (
        status if not dob else "frozen_or_current_evidence_ineligible")
    result["snapshot"] = f"{year}-01"
    return result


class Resolver:
    def __init__(self, seeds, session, cache, cache_path, timeout, retries, delay):
        self.seeds, self.session, self.cache, self.cache_path = seeds, session, cache, cache_path
        self.timeout, self.retries, self.delay = timeout, retries, delay

    def evidence(self, fid, year):
        if fid in self.seeds[year]:
            return self.seeds[year][fid]
        other = "2023" if year == "2013" else "2013"
        if fid in self.seeds[other]:
            reused = dict(self.seeds[other][fid])
            # The old snapshot's year/date check is not a property of the
            # evidence. Reapply those checks to the current FIDE row below.
            qids = [qid for qid in reused.get("wikidata_person_qids", "").split(";") if qid]
            reused["evidence_eligible"] = bool(reused["exact_dob_frozen"]
                and reused["birthplace_hemisphere"] == "north" and len(qids) == 1)
            reused["evidence_reused_from_snapshot"] = f"{other}-01"
            return reused
        return metadata_from_records(fid, self.cache[fid])

    def prefetch(self, ids):
        wanted = [fid for fid in ids if not any(fid in s for s in self.seeds.values())]
        fetch_records(wanted, self.session, self.cache, self.cache_path,
                      self.timeout, self.retries, self.delay)


def top_with_ties(rows, target, excluded=frozenset()):
    eligible = [r for r in rows if r["eligible"] and canonical_id(r) not in excluded]
    eligible.sort(key=lambda r: (-int(r["rating"]), str(r["name"]), canonical_id(r)))
    if len(eligible) < target:
        return None, None
    cutoff = int(eligible[target - 1]["rating"])
    return [r for r in eligible if int(r["rating"]) >= cutoff], cutoff


def scan(population, year, resolver, target, excluded, audit_path, batch_size=50, new_target=None):
    new_target = target if new_target is None else new_target
    if target < 1 or new_target < 1:
        raise ValueError("FULL and NEW targets must be positive")
    rows = population.to_dict("records")
    audit = []
    full = new = None
    position = 0
    while position < len(rows):
        end = min(position + batch_size, len(rows))
        # Finish the complete boundary Elo group before evaluating the cutoff.
        while end < len(rows) and rows[end]["rating"] == rows[end - 1]["rating"]:
            end += 1
        batch = rows[position:end]
        resolver.prefetch([str(row["fide_id"]) for row in batch])
        for row in batch:
            fid = str(row["fide_id"])
            rec = adjudicate(row, resolver.evidence(fid, year), year)
            rec["excluded_from_new"] = canonical_id(rec) in excluded
            audit.append(rec)
        pd.DataFrame(audit).to_csv(audit_path, index=False, encoding="utf-8")
        full, full_cutoff = top_with_ties(audit, target)
        new, new_cutoff = top_with_ties(audit, new_target, excluded)
        print(f"[{year}] scanned={len(audit)} eligible={sum(r['eligible'] for r in audit)} new_eligible={sum(r['eligible'] and not r['excluded_from_new'] for r in audit)}", flush=True)
        if full is not None and new is not None:
            return full, new, audit, full_cutoff, new_cutoff
        position = end
    raise RuntimeError(f"Unable to reach fixed FULL target={target}, NEW target={new_target} in {year}")


def find_conflicts(cohorts):
    seen, conflicts = {}, []
    for group, rows in cohorts.items():
        for row in rows:
            fid = canonical_id(row)
            values = (row["exact_dob_frozen"], row["birthplace_hemisphere"])
            if fid in seen and seen[fid][1] != values:
                conflicts.append({"canonical_id": fid, "first_group": seen[fid][0],
                                  "second_group": group, "first_dob": seen[fid][1][0],
                                  "second_dob": values[0], "first_hemisphere": seen[fid][1][1],
                                  "second_hemisphere": values[1]})
            else:
                seen[fid] = (group, values)
    return conflicts


def check_snapshot_anchors(population, old_path, year):
    """Catch parser/list substitution using every previously audited player."""
    old = pd.read_csv(old_path, dtype=str, keep_default_na=False)
    lookup = {str(row["fide_id"]): row for row in population.to_dict("records")}
    for row in old.to_dict("records"):
        fid = str(row["fide_id"])
        if fid not in lookup or int(lookup[fid]["rating"]) != int(row["rating"]):
            raise ValueError(f"{year} snapshot does not reproduce frozen ID/rating: {fid}")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[2])
    ap.add_argument("--output-dir", type=Path, default=Path("studies/chess_single_A_v2/data"))
    ap.add_argument("--cache-dir", type=Path, default=Path("studies/chess_single_A_v2/cache"))
    ap.add_argument("--2013-txt", dest="txt2013", type=Path)
    ap.add_argument("--2023-txt", dest="txt2023", type=Path)
    ap.add_argument("--target", type=int, default=1000)
    ap.add_argument("--new-target", type=int, default=None,
                    help="2023 NEW target before ties; defaults to --target")
    ap.add_argument("--batch-size", type=int, default=50)
    ap.add_argument("--timeout", type=int, default=20)
    ap.add_argument("--retries", type=int, default=3)
    ap.add_argument("--delay", type=float, default=.5)
    args = ap.parse_args()
    args.new_target = args.target if args.new_target is None else args.new_target
    if args.target < 1 or args.new_target < 1 or args.batch_size < 1:
        ap.error("FULL target, NEW target and batch size must be positive")
    if requests is None:
        raise RuntimeError("Live acquisition requires requests; install the pinned workflow dependencies")
    root = args.repo_root.resolve()
    out = args.output_dir if args.output_dir.is_absolute() else root / args.output_dir
    cache_dir = args.cache_dir if args.cache_dir.is_absolute() else root / args.cache_dir
    out.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc).isoformat()
    write_json(out / "summary.json", {"status": "acquisition_incomplete", "started_utc": started})
    write_json(out / "manifest.json", {"status": "acquisition_incomplete", "started_utc": started})
    for filename in ("cohort_2013_M.csv", "cohort_2023_M_FULL.csv", "cohort_2023_M_NEW_TARGET.csv", "conflicts.csv", "training_subsets.csv", "subset_manifest.json", "independent_audit.json"):
        (out / filename).unlink(missing_ok=True)
    parser = import_module(root / "chess_2023_cohorts_v1/build_chess_2023_cohorts_v2.py", "legacy_fide_parser")
    seeds, seed_inputs = load_seeds(root)
    legacy_ids, legacy_inputs = load_legacy_ids(root)
    cache_path = cache_dir / "wikidata_records.json"
    cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
    session = requests.Session()
    session.headers.update({"User-Agent": "ChessCohortReplication/2.0 (public academic reproducibility; GitHub agenhcx/bazi-public-figure-study)",
                            "Accept": "application/sparql-results+json, application/json, application/zip"})
    commit = os.environ.get("GITHUB_SHA")
    if not commit:
        proc = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True)
        commit = proc.stdout.strip() if proc.returncode == 0 else "local_uncommitted"
    protocol = Path(__file__).with_name("acquisition_protocol.md")
    if not protocol.is_file():
        raise FileNotFoundError("Required acquisition_protocol.md is missing")
    manifest = {"status": "acquisition_incomplete", "started_utc": started,
                "legacy_source_revision": SOURCE_REVISION, "executing_commit": commit,
                "collector_sha256": sha256(Path(__file__)),
                "protocol_sha256": sha256(protocol),
                "query_template_sha256": hashlib.sha256(query_text([]).encode()).hexdigest(),
                "seed_inputs": seed_inputs,
                "legacy_exclusion_inputs": legacy_inputs, "population_sources": {},
                "rules": {"target": args.target, "new_target": args.new_target,
                          "cutoff_ties": "all_eligible", "sex": "M",
                          "snapshots": ["2013-01", "2023-01"], "active": True,
                          "new_dob_calendar": "Gregorian Q1985727; best-rank day precision; no uncertainty",
                          "legacy_metadata": "frozen evidence inherited, never requeried",
                          "new_excludes": "expanded2013 entire cohort plus all legacy1994/2013 primary IDs"}}
    populations = {}
    for year, explicit in (("2013", args.txt2013), ("2023", args.txt2023)):
        if explicit:
            path = explicit.resolve()
            provenance = {"local_text_input": str(path), "text_sha256": sha256(path)}
        else:
            path, provenance = download_population(year, cache_dir, session, args.timeout)
        populations[year] = parse_population(path, year, parser)
        manifest["population_sources"][year] = provenance
        write_json(out / "manifest.json", manifest)
        print(f"[{year}] active_standard_male_population={len(populations[year])}", flush=True)
    check_snapshot_anchors(populations["2013"], root / "chess_north_v3/primary_north_top_2013_M.csv", "2013")
    check_snapshot_anchors(populations["2023"], root / "chess_2023_cohorts_v1/candidate_audit_2023_M.csv", "2023")
    resolver = Resolver(seeds, session, cache, cache_path, args.timeout, args.retries, args.delay)
    dev, _, audit13, cut13, _ = scan(populations["2013"], "2013", resolver, args.target,
                                    set(), out / "candidate_audit_2013_M.csv", args.batch_size)
    dev_ids = {canonical_id(row) for row in dev}
    with (root / "chess_north_v3/primary_north_top_2013_M.csv").open(encoding="utf-8-sig", newline="") as f:
        old_development_ids = {canonical_id(row) for row in csv.DictReader(f)}
    if not old_development_ids <= dev_ids:
        raise RuntimeError("Expanded2013 does not retain every previously frozen2013 player")
    exclusions = legacy_ids | dev_ids
    pd.DataFrame([{"canonical_id": fid, "in_legacy_primary": fid in legacy_ids,
                   "in_expanded_2013": fid in dev_ids} for fid in sorted(exclusions)]).to_csv(
                       out / "excluded_legacy_ids.csv", index=False)
    full, new, audit23, cutfull, cutnew = scan(populations["2023"], "2023", resolver, args.target,
                                            exclusions, out / "candidate_audit_2023_M.csv", args.batch_size,
                                            new_target=args.new_target)
    cohorts = {"2013_M": dev, "2023_M_FULL": full, "2023_M_NEW_TARGET": new}
    conflicts = find_conflicts(cohorts)
    if conflicts:
        pd.DataFrame(conflicts).to_csv(out / "conflicts.csv", index=False)
        write_json(out / "summary.json", {"status": "blocked_conflicts", "conflict_count": len(conflicts)})
        raise RuntimeError("Cross-snapshot conflicts; see conflicts.csv; no final cohorts written")
    if dev_ids & {canonical_id(row) for row in new}:
        raise RuntimeError("Development/NEW_TARGET identity overlap")
    cutoffs = {"2013_M": cut13, "2023_M_FULL": cutfull, "2023_M_NEW_TARGET": cutnew}
    summary = {"status": "acquisition_complete_no_models_fitted", "target": args.target,
               "new_target": args.new_target,
               "legacy_exclusion_count": len(legacy_ids), "expanded_exclusion_count": len(exclusions),
               "development_new_overlap": 0, "cross_snapshot_conflicts": 0,
               "candidates_scanned": {"2013": len(audit13), "2023": len(audit23)}, "cohorts": {}}
    for group, rows in cohorts.items():
        ids = [canonical_id(row) for row in rows]
        if len(ids) != len(set(ids)):
            raise RuntimeError(f"Duplicate canonical IDs in {group}")
        path = out / f"cohort_{group}.csv"
        pd.DataFrame(rows).to_csv(path, index=False, encoding="utf-8")
        summary["cohorts"][group] = {"n": len(rows), "cutoff_elo": cutoffs[group], "sha256": sha256(path),
                                    "legacy_metadata_n": sum(row["evidence_source"] != "new_wikidata_best_rank_query" for row in rows)}
    summary["development_full_overlap"] = len(dev_ids & {canonical_id(row) for row in full})
    summary["new_full_overlap"] = len({canonical_id(row) for row in new} & {canonical_id(row) for row in full})
    write_json(out / "summary.json", summary)
    manifest["outputs"] = [{"file": p.name, "sha256": sha256(p)} for p in sorted(out.glob("*.csv"))]
    manifest["wikidata_cache_sha256"] = sha256(cache_path) if cache_path.exists() else None
    manifest["status"] = "acquisition_complete_no_models_fitted"
    manifest["completed_utc"] = datetime.now(timezone.utc).isoformat()
    write_json(out / "manifest.json", manifest)
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
