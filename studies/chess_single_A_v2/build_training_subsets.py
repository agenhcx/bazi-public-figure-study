#!/usr/bin/env python3
"""Fix the prespecified 2013 training subsets after complete acquisition.

Standard-library only. This reads IDs and ratings for subset construction; it
does not calculate BaZi features, fit models, or evaluate 2023 prediction scores.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess


COMPLETE = "acquisition_complete_no_models_fitted"
SIZES = [500, 800, 1000]
SEED = 20261024
SOURCE_FILES = {
    "2013_M": "cohort_2013_M.csv",
    "2023_M_NEW_TARGET": "cohort_2023_M_NEW_TARGET.csv",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: dict) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2,
                               sort_keys=True) + "\n", encoding="utf-8")
    temp.replace(path)


def canonical_id(row: dict) -> str:
    value = str(row.get("identity_bridge_modern_fide_id", "")).strip()
    if not value or value.lower() in {"nan", "none"}:
        value = str(row.get("fide_id", "")).strip()
    if not re.fullmatch(r"[0-9]+", value) or int(value) <= 0:
        raise ValueError(f"Invalid canonical FIDE ID: {value!r}")
    return str(int(value))


def read_cohort(path: Path) -> list[dict]:
    records = []
    seen = set()
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames or not {"fide_id", "rating"} <= set(reader.fieldnames):
            raise ValueError(f"Missing ID/rating columns in {path.name}")
        if len(reader.fieldnames) != len(set(reader.fieldnames)):
            raise ValueError(f"Duplicate CSV column in {path.name}")
        for number, row in enumerate(reader, start=2):
            if None in row or any(value is None for value in row.values()):
                raise ValueError(f"Malformed CSV row {number} in {path.name}")
            fid = canonical_id(row)
            if fid in seen:
                raise ValueError(f"Duplicate canonical ID {fid} in {path.name}")
            raw_rating = str(row["rating"]).strip()
            if not re.fullmatch(r"[0-9]+", raw_rating) or int(raw_rating) <= 0:
                raise ValueError(f"Invalid rating for ID {fid} in {path.name}")
            records.append({"canonical_id": fid, "rating": int(raw_rating)})
            seen.add(fid)
    return records


def random_order(rows: list[dict], seed: int) -> list[dict]:
    def key(row):
        fid = row["canonical_id"]
        digest = hashlib.sha256(f"{seed}\n{fid}".encode("utf-8")).hexdigest()
        return digest, fid
    return sorted(rows, key=key)


def ranked_subset(rows: list[dict], target: int) -> tuple[list[dict], int]:
    ordered = sorted(rows, key=lambda row: (-row["rating"], row["canonical_id"]))
    if len(ordered) < target:
        raise ValueError(f"Insufficient development rows for ranked target {target}")
    cutoff = ordered[target - 1]["rating"]
    return [row for row in ordered if row["rating"] >= cutoff], cutoff


def relative_path(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def executing_commit(root: Path) -> tuple[str, str]:
    if os.environ.get("GITHUB_SHA", "").strip():
        return os.environ["GITHUB_SHA"].strip(), "GITHUB_SHA"
    try:
        result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root,
                                capture_output=True, text=True, check=False)
    except OSError:
        return "local_uncommitted", "unavailable"
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip(), "git_rev_parse_HEAD"
    return "local_uncommitted", "unavailable"


def build_subsets(repo_root: Path, data_dir: Path | None = None,
                  config_path: Path | None = None) -> dict:
    root = repo_root.resolve()
    data = (data_dir or Path("studies/chess_single_A_v2/data"))
    data = (data if data.is_absolute() else root / data).resolve()
    config_path = config_path or Path("studies/chess_single_A_v2/config.json")
    config_path = (config_path if config_path.is_absolute() else root / config_path).resolve()
    data.mkdir(parents=True, exist_ok=True)
    subset_path = data / "training_subsets.csv"
    subset_manifest_path = data / "subset_manifest.json"
    # A failed rerun cannot leave a stale file labeled as a newly complete build.
    subset_path.unlink(missing_ok=True)
    write_json(subset_manifest_path, {"status": "subset_build_incomplete_no_models_fitted"})

    acquisition_path, summary_path = data / "manifest.json", data / "summary.json"
    acquisition = json.loads(acquisition_path.read_text(encoding="utf-8"))
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if acquisition.get("status") != COMPLETE or summary.get("status") != COMPLETE:
        raise ValueError("Acquisition manifest and summary must both be complete")
    collector_commit = acquisition.get("executing_commit")
    if not isinstance(collector_commit, str) or not collector_commit.strip():
        raise ValueError("Missing executing collector commit in acquisition manifest")
    if summary.get("development_new_overlap") != 0 or summary.get("cross_snapshot_conflicts") != 0:
        raise ValueError("Acquisition reports overlap or unresolved cross-snapshot conflicts")

    config = json.loads(config_path.read_text(encoding="utf-8"))
    rules = config.get("training_subsets", {})
    if (config.get("protocol_id") != "chess-single-A-v2"
            or rules.get("random_nested_sizes") != SIZES
            or rules.get("ranked_secondary_thresholds") != SIZES
            or rules.get("random_seed") != SEED
            or rules.get("primary") != "random_1000"):
        raise ValueError("Configuration does not match the fixed v2 subset design")

    outputs = acquisition.get("outputs", [])
    output_hashes = {}
    for output in outputs:
        filename = output.get("file")
        if filename in output_hashes:
            raise ValueError(f"Duplicate output fingerprint in acquisition manifest: {filename}")
        output_hashes[filename] = output.get("sha256")
    sources, cohorts = {}, {}
    for role, filename in SOURCE_FILES.items():
        path = data / filename
        actual_hash = sha256(path)
        entry = summary.get("cohorts", {}).get(role, {})
        if entry.get("sha256") != actual_hash or output_hashes.get(filename) != actual_hash:
            raise ValueError(f"Source fingerprint mismatch: {filename}")
        rows = read_cohort(path)
        if len(rows) < 1000 or entry.get("n") != len(rows):
            raise ValueError(f"Source count mismatch or fewer than 1000 people: {filename}")
        if entry.get("cutoff_elo") != min(row["rating"] for row in rows):
            raise ValueError(f"Source cutoff mismatch: {filename}")
        sources[role] = {"path": relative_path(path, root), "sha256": actual_hash,
                         "n": len(rows)}
        cohorts[role] = rows
    development = cohorts["2013_M"]
    overlap = ({row["canonical_id"] for row in development}
               & {row["canonical_id"] for row in cohorts["2023_M_NEW_TARGET"]})
    if overlap:
        raise ValueError(f"Expanded development/NEW identity overlap: {len(overlap)}")

    selections = []
    shuffled = random_order(development, SEED)
    for target in SIZES:
        selections.append((f"random_{target}", shuffled[:target], target, None))
    for target in SIZES:
        selected, cutoff = ranked_subset(development, target)
        selections.append((f"ranked_{target}_with_ties", selected, target, cutoff))

    temp = subset_path.with_suffix(".csv.tmp")
    subset_info = {}
    with temp.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["label", "canonical_id", "order"],
                                lineterminator="\n")
        writer.writeheader()
        for label, rows, target, cutoff in selections:
            ids = [row["canonical_id"] for row in rows]
            for order, fid in enumerate(ids, start=1):
                writer.writerow({"label": label, "canonical_id": fid, "order": order})
            subset_info[label] = {
                "requested_n": target, "actual_n": len(rows),
                "selector": "sha256_nested_prefix" if cutoff is None else "rating_with_cutoff_ties",
                "cutoff_elo": cutoff,
                "rating_min": min(row["rating"] for row in rows),
                "rating_max": max(row["rating"] for row in rows),
                "ordered_ids_sha256": hashlib.sha256(("\n".join(ids) + "\n").encode("utf-8")).hexdigest(),
            }
    temp.replace(subset_path)

    commit, commit_source = executing_commit(root)
    result = {
        "status": "subsets_fixed_no_models_fitted",
        "protocol_id": config["protocol_id"],
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "builder_executing_commit": commit,
        "builder_commit_source": commit_source,
        "builder_sha256": sha256(Path(__file__).resolve()),
        "source_executing_collector_commit": collector_commit,
        "source_acquisition_manifest_sha256": sha256(acquisition_path),
        "source_acquisition_summary_sha256": sha256(summary_path),
        "config": {"path": relative_path(config_path, root), "sha256": sha256(config_path)},
        "sources": sources,
        "random_seed": SEED,
        "random_order": "ascending SHA256(UTF-8 str(seed) + newline + canonical_id), then canonical_id",
        "primary_training_subset": "random_1000",
        "development_new_overlap": 0,
        "subsets": subset_info,
        "output": {"path": relative_path(subset_path, root), "sha256": sha256(subset_path)},
        "interpretation": "one prespecified nested random draw; ranked comparisons also change Elo/population range",
    }
    write_json(subset_manifest_path, result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--data-dir", type=Path, default=Path("studies/chess_single_A_v2/data"))
    parser.add_argument("--config", type=Path, default=Path("studies/chess_single_A_v2/config.json"))
    args = parser.parse_args()
    result = build_subsets(args.repo_root, args.data_dir, args.config)
    print(json.dumps({"status": result["status"], "development_new_overlap": 0,
                      "subset_counts": {key: value["actual_n"] for key, value in result["subsets"].items()},
                      "training_subsets_sha256": result["output"]["sha256"]}, indent=2))


if __name__ == "__main__":
    main()
