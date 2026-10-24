"""Bind the exploratory B1 extension without changing the original A1 lock."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys

REL = Path('studies/chess_single_B_v1')
LOCK = REL / 'b1_lock.json'
TAG = 'chess-single-b-structure-lock-v1'
A_REL = Path('studies/chess_single_A_v2')
A_SHA = '4ee147676368294e93630d9e801333f5498059a7ae615d8abc532aee40c7277c'
CORE = tuple(REL / name for name in ('PLAN.md', 'config.json', 'features.py', 'train.py', 'evaluate.py', 'lock_b1.py', 'test_features.py', 'test_train.py', 'test_evaluate.py', 'test_lock_b1.py')) + (Path('.github/workflows/chess_single_b_v1.yml'),)

def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def create_lock(root):
    root = Path(root).resolve()
    if sha256(root / A_REL / 'analysis_lock.json') != A_SHA:
        raise ValueError('Original A1 lock differs')
    config = json.loads((root / REL / 'config.json').read_text())
    if config.get('fit_allowed') is not True or config.get('prior_2013_and_2023_results_seen') is not True:
        raise ValueError('B1 authorization/prior-access disclosure missing')
    lock = {'protocol_id': 'chess-single-B-v1', 'status': 'fixed_post_A_results_before_B1_fitting', 'analysis_tag': TAG,
            'original_analysis_lock_sha256': A_SHA, 'prior_2013_and_2023_results_seen': True,
            'new_blind_preregistration_claimed': False, 'fitting_before_this_lock': 'synthetic tests only',
            'files': {p.as_posix(): sha256(root / p) for p in CORE}}
    (root / LOCK).write_text(json.dumps(lock, indent=2, sort_keys=True) + '\n')
    return lock

def verify_lock(root, *, check_environment=True):
    root = Path(root).resolve()
    lock = json.loads((root / LOCK).read_text())
    if (lock.get('protocol_id') != 'chess-single-B-v1' or lock.get('status') != 'fixed_post_A_results_before_B1_fitting'
        or lock.get('prior_2013_and_2023_results_seen') is not True or lock.get('new_blind_preregistration_claimed') is not False
        or lock.get('original_analysis_lock_sha256') != A_SHA or lock.get('analysis_tag') != TAG):
        raise ValueError('B1 lock metadata differs')
    if set(lock.get('files', {})) != {p.as_posix() for p in CORE}:
        raise ValueError('Incomplete B1 source lock')
    for name, digest in lock['files'].items():
        path = (root / name).resolve()
        if not path.is_relative_to(root) or sha256(path) != digest:
            raise ValueError(f'B1 fingerprint mismatch: {name}')
    if sha256(root / A_REL / 'analysis_lock.json') != A_SHA:
        raise ValueError('Original A1 analysis lock differs')
    sys.path.insert(0, str(root / A_REL))
    from lock_utils import verify_analysis_lock
    verify_analysis_lock(root, check_environment=check_environment)
    return lock

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['create', 'verify'])
    parser.add_argument('--repo-root', type=Path, default=Path.cwd())
    args = parser.parse_args()
    result = create_lock(args.repo_root) if args.command == 'create' else verify_lock(args.repo_root)
    print(json.dumps({'status': result['status'], 'files': len(result['files'])}))

if __name__ == '__main__':
    main()
