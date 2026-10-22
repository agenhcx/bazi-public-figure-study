"""Bind this post-result diagnostic separately from the unchanged A1 lock."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import zipfile

STUDY = Path("studies/chess_single_A_v2")
REL = STUDY / "diagnostics_v1"
LOCK = REL / "diagnostic_lock.json"
TAG = "chess-single-a-diagnostics-lock-v1"
ANALYSIS_SHA = "4ee147676368294e93630d9e801333f5498059a7ae615d8abc532aee40c7277c"
SEAL_SHA = "b7b31cab6b7bd4099570638f3fe443a41a17cec10efeedea8d519604c0420656"
BUNDLE_SHA = "445c2b7cbe79ad31c8eec8e414d1c765da615bc84cfaf87d2e4a5428231f5c2f"
CORE = [REL / name for name in (
    "PLAN.md", "diagnostic_lock.py", "audit_existing.py", "mlp_budget.py",
    "synthetic_controls.py", "summarize.py", "test_diagnostic_lock.py",
    "test_audit_existing.py", "test_mlp_budget.py", "test_synthetic_controls.py",
    "test_summarize.py",
)] + [Path(".github/workflows/chess_single_a_diagnostics_v1.yml")]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def create(root: Path) -> dict:
    root = root.resolve()
    if sha256(root / STUDY / "analysis_lock.json") != ANALYSIS_SHA:
        raise ValueError("The original A1 analysis lock differs")
    lock = {
        "protocol_id": "chess-single-A-training-diagnostics-v1",
        "status": "fixed_post_result_diagnostics_before_new_fitting",
        "analysis_tag": TAG,
        "prior_2013_and_2023_results_seen": True,
        "new_blind_preregistration_claimed": False,
        "external_predictive_scoring_allowed": False,
        "original_analysis_commit": "83e2e82f57b37cf5ed5308ea6218ba317b032180",
        "original_results_commit": "488539eaac33b863eaa0505ee152ac47df53dce0",
        "original_analysis_lock_sha256": ANALYSIS_SHA,
        "original_models_seal_sha256": SEAL_SHA,
        "original_checkpoint_bundle_sha256": BUNDLE_SHA,
        "files": {p.as_posix(): sha256(root / p) for p in CORE},
    }
    (root / LOCK).write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n")
    return lock


def verify(root: Path, *, check_original=True) -> dict:
    root = root.resolve()
    lock = json.loads((root / LOCK).read_text())
    if lock.get("status") != "fixed_post_result_diagnostics_before_new_fitting":
        raise ValueError("Diagnostic lock is not ready")
    if lock.get("external_predictive_scoring_allowed") is not False:
        raise ValueError("External scoring is not authorized by this diagnostic")
    if set(lock["files"]) != {p.as_posix() for p in CORE}:
        raise ValueError("Incomplete diagnostic source-file lock")
    for name, digest in lock["files"].items():
        path = (root / name).resolve()
        if not path.is_relative_to(root) or sha256(path) != digest:
            raise ValueError(f"Diagnostic file hash mismatch: {name}")
    if sha256(root / STUDY / "analysis_lock.json") != ANALYSIS_SHA:
        raise ValueError("Original A1 analysis-lock mismatch")
    if check_original:
        sys.path.insert(0, str(root / STUDY))
        from lock_utils import verify_analysis_lock
        verify_analysis_lock(root)
    return lock


def extract_checkpoint(root: Path, output: Path) -> None:
    bundle = root / STUDY / "results/training_checkpoint_bundle.zip"
    if sha256(bundle) != BUNDLE_SHA:
        raise ValueError("Original checkpoint bundle mismatch")
    output.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(bundle) as archive:
        for entry in archive.infolist():
            relative = Path(entry.filename)
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError("Unsafe checkpoint path")
        if hashlib.sha256(archive.read("fitted_models_lock.json")).hexdigest() != SEAL_SHA:
            raise ValueError("Original fitted-model seal mismatch")
        archive.extractall(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["create", "verify", "extract"])
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    if args.command == "create":
        result = create(args.repo_root)
    elif args.command == "verify":
        result = verify(args.repo_root)
    else:
        if args.output_dir is None:
            parser.error("extract requires --output-dir")
        verify(args.repo_root)
        extract_checkpoint(args.repo_root, args.output_dir)
        result = {"status": "original_checkpoints_extracted_and_verified"}
    print(json.dumps({"status": result["status"]}))


if __name__ == "__main__":
    main()
