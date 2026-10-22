#!/usr/bin/env python3
"""Bind the model analysis to exact files and an explicitly pinned environment."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform

STUDY = Path("studies/chess_single_A_v2")
LOCK_FILE = STUDY / "analysis_lock.json"
STATUS = "analysis_locked_before_research_fitting"
THREAD_ENV = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS")
CORE_FILES = (
    "config.json", "analysis_plan.md", "MODEL_RUN_GUIDE.md", "acquisition_protocol.md", "acquisition_amendment_01.md",
    "requirements-model.txt", "model_inputs.py", "models.py", "train_models.py",
    "evaluate_models.py", "plot_model_results.py", "lock_utils.py",
    "data/data_manifest.json", "data/feature_audit.json", "data/manifest.json",
    "data/summary.json", "data/independent_audit.json", "data/training_subsets.csv",
    "data/subset_manifest.json", "data/model_environment.json", "data/model_pip_freeze.txt",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object: {path.name}")
    return value


def environment_versions() -> dict:
    versions = {"python": platform.python_version()}
    for package in ("numpy", "pandas", "scipy", "scikit-learn", "sxtwl", "joblib", "threadpoolctl", "matplotlib"):
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = None
    return versions


def _relative_file(root: Path, name: str) -> Path:
    if not isinstance(name, str) or Path(name).is_absolute():
        raise ValueError("Locked file paths must be relative")
    path = (root / name).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError(f"Missing or invalid locked file: {name}")
    return path


def create_analysis_lock(repo_root: Path, *, source_data_commit: str,
                         input_preparation_commit: str, python_version: str = "3.11.17") -> dict:
    """Record expected hashes only; this function performs no model fitting."""
    root = Path(repo_root).resolve()
    config = read_json(root / STUDY / "config.json")
    if config.get("fit_allowed") is not True:
        raise ValueError("Finalized config must explicitly allow fitting before creating the lock")
    if not source_data_commit or not input_preparation_commit:
        raise ValueError("Acquisition and input preparation commits are required")
    required = {str(STUDY / name) for name in CORE_FILES}
    # Bind tests too: the recorded preflight has one exact implementation.
    required.update(str(p.relative_to(root)) for p in (root / STUDY).glob("test_*.py"))
    required.add(".github/workflows/chess_single_a_models_v2.yml")
    manifest = read_json(root / STUDY / "data/data_manifest.json")
    for role, entry in manifest.get("roles", {}).items():
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
            raise ValueError(f"Invalid derived role in input manifest: {role}")
        required.add(entry["path"])
        source = entry.get("source", {})
        if isinstance(source, dict) and isinstance(source.get("path"), str):
            required.add(source["path"])
    for reference in manifest.get("reference_inputs", []):
        path = _relative_file(root, reference["path"])
        if sha256(path) != reference.get("sha256"):
            raise ValueError(f"Legacy reference differs from the verified preparation: {reference['path']}")
        required.add(reference["path"])
    hashes = {name: sha256(_relative_file(root, name)) for name in sorted(required)}
    packages = {}
    for line in (root / STUDY / "requirements-model.txt").read_text().splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        package, version = line.strip().split("==", 1)
        packages[package] = version
    expected_environment = {"python": python_version, **packages}
    recorded_environment = read_json(root / STUDY / "data/model_environment.json")
    if any(recorded_environment.get(package) != version for package, version in expected_environment.items()):
        raise ValueError("Preflight environment does not match the pinned model environment")
    lock = {
        "status": STATUS,
        "protocol_id": "chess-single-A-v2",
        "source_data_commit": source_data_commit,
        "input_preparation_commit": input_preparation_commit,
        "analysis_tag": "chess-single-a-analysis-lock-v2",
        "prior_outcome_access_disclosed": True,
        "new_blind_preregistration_claimed": False,
        "fitting_before_this_lock": "synthetic tests only; no research-data fits",
        "environment": expected_environment,
        "thread_environment": {name: "1" for name in THREAD_ENV},
        "pythonhashseed": "0",
        "files": hashes,
    }
    target = root / LOCK_FILE
    target.write_text(json.dumps(lock, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return lock


def verify_analysis_lock(repo_root: Path, *, check_environment: bool = True) -> dict:
    root = Path(repo_root).resolve()
    lock = read_json(root / LOCK_FILE)
    if lock.get("status") != STATUS or lock.get("protocol_id") != "chess-single-A-v2":
        raise ValueError("Analysis lock is absent, incomplete, or for another protocol")
    if lock.get("prior_outcome_access_disclosed") is not True:
        raise ValueError("Prior outcome access must remain disclosed")
    hashes = lock.get("files")
    if not isinstance(hashes, dict) or not hashes:
        raise ValueError("Analysis lock has no input/code fingerprints")
    required = {str(STUDY / name) for name in CORE_FILES}
    if not required <= set(hashes):
        raise ValueError("Analysis lock omits required inputs or implementation files")
    for name, expected in hashes.items():
        if not isinstance(expected, str) or len(expected) != 64 or sha256(_relative_file(root, name)) != expected:
            raise ValueError(f"Analysis-lock fingerprint mismatch: {name}")
    config = read_json(root / STUDY / "config.json")
    if config.get("fit_allowed") is not True:
        raise ValueError("Research fitting is disabled by configuration")
    if check_environment:
        actual = environment_versions()
        for package, expected in lock.get("environment", {}).items():
            if actual.get(package) != expected:
                raise ValueError(f"Environment mismatch for {package}: expected {expected}, got {actual.get(package)}")
        for name in THREAD_ENV:
            if lock.get("thread_environment", {}).get(name) != "1" or os.environ.get(name) != "1":
                raise ValueError(f"Thread limit must be exactly one: {name}")
        if lock.get("pythonhashseed") != "0" or os.environ.get("PYTHONHASHSEED") != "0":
            raise ValueError("PYTHONHASHSEED must be zero")
    return lock


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["create", "verify", "environment"])
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--source-data-commit")
    parser.add_argument("--input-preparation-commit")
    args = parser.parse_args()
    if args.command == "environment":
        print(json.dumps(environment_versions(), indent=2))
    elif args.command == "create":
        result = create_analysis_lock(args.repo_root, source_data_commit=args.source_data_commit,
                                      input_preparation_commit=args.input_preparation_commit)
        print(json.dumps({"status": result["status"], "locked_files": len(result["files"])}))
    else:
        result = verify_analysis_lock(args.repo_root)
        print(json.dumps({"status": result["status"], "verified_files": len(result["files"])}))


if __name__ == "__main__":
    main()
