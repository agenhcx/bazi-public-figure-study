"""Collect all fixed people before association analysis; checkpoint on failure."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import urllib.request
import zipfile

from collect_fide import run_acquisition, load_roster, write_json
from collect_historical import extract_history
from peak_data import build_dataset

ARCHIVES = {
    'pre2002': ('https://www.olimpbase.org/Elo/data/elo1967-2001.zip',
                'a93c69d1e3218769935aba92db50877a2e9c26cc62d377c1b663f37a786fe89b'),
    '2002_2009': ('https://www.olimpbase.org/Elo/data/elo2002-2009.zip',
                  '41131d4b573f033ccf8f2df927f820046cfbee305051b83145c2955220d89003'),
}


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def safe_extract(archive, destination):
    destination = Path(destination).resolve()
    with zipfile.ZipFile(archive) as z:
        for name in z.namelist():
            if Path(name).is_absolute() or not (destination / name).resolve().is_relative_to(destination):
                raise ValueError('Unsafe acquisition checkpoint path')
        z.extractall(destination)


def get_archives(work):
    folder = Path(work) / 'archives'
    folder.mkdir(parents=True, exist_ok=True)
    paths = {}
    for key, (url, digest) in ARCHIVES.items():
        path = folder / url.rsplit('/', 1)[-1]
        if not path.exists():
            request = urllib.request.Request(url, headers={'User-Agent': 'ChessPeakResearch/1.0'})
            with urllib.request.urlopen(request, timeout=60) as response:
                if response.status != 200:
                    raise ValueError('Historical archive download failed')
                data = response.read(60 * 1024 * 1024 + 1)
            if len(data) > 60 * 1024 * 1024 or hashlib.sha256(data).hexdigest() != digest:
                raise ValueError('Historical source archive fingerprint differs')
            path.write_bytes(data)
        if sha256(path) != digest:
            raise ValueError('Cached historical archive changed')
        paths[key] = path
    return paths


def pack_checkpoint(work, target):
    work, target = Path(work).resolve(), Path(target).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    files = []
    for folder in ('fide', 'prepared_audit'):
        if (work / folder).exists():
            files.extend(p for p in (work / folder).rglob('*') if p.is_file()
                         and p.name != 'STOP' and not p.name.endswith('.tmp'))
    for name in ('historical_history.json', 'persons.csv', 'preparation_status.json'):
        if (work / name).is_file():
            files.append(work / name)
    with zipfile.ZipFile(target, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for p in sorted(set(files)):
            info = zipfile.ZipInfo(p.relative_to(work).as_posix(), date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            z.writestr(info, p.read_bytes())
    if target.stat().st_size >= 50 * 1024 * 1024:
        raise ValueError('Acquisition checkpoint exceeds repository size budget')
    metadata = {
        'file': target.name, 'bytes': target.stat().st_size, 'files': len(set(files)),
        'sha256': sha256(target),
        'historical_original_archives': {k: {'url': u, 'sha256': d} for k, (u, d) in ARCHIVES.items()},
        'historical_archival_scope': 'selected source rows retained; full public archives can be SHA-verified again',
    }
    target.with_suffix('.json').write_text(json.dumps(metadata, indent=2) + '\n')
    return metadata


def prepare(root, work, *, resume=None, workers=2, rate=2.0, prefer_provider='lichess'):
    root, work = Path(root).resolve(), Path(work).resolve()
    work.mkdir(parents=True, exist_ok=True)
    if resume and Path(resume).is_file():
        safe_extract(resume, work)
    output = root / 'studies/chess_peak_v1/data'
    status = {'status': 'preparing_peak_inputs', 'predictive_fitting_performed': False}
    try:
        people, _ = load_roster(root)
        with (work / 'persons.csv').open('w', newline='', encoding='utf-8') as stream:
            writer = csv.DictWriter(stream, fieldnames=['canonical_id', 'name', 'exact_dob_frozen'])
            writer.writeheader()
            writer.writerows({k: p[k] for k in writer.fieldnames} for p in people)
        historical = extract_history(get_archives(work), people)
        write_json(work / 'historical_history.json', historical)
        if historical['audit']['fatal_issues']:
            raise ValueError('Historical identity audit requires resolution')
        histories = run_acquisition(root, work / 'fide', workers=workers,
            requests_per_second=rate, prefer_provider=prefer_provider)
        if histories['failed_n'] or histories['snapshot_audit_n']:
            raise ValueError(f"Rating histories have {histories['failed_n']} failures and {histories['snapshot_audit_n']} snapshot audits")
        manifest = build_dataset(root, work / 'fide', work / 'historical_history.json')
        status.update(status='peak_inputs_complete_before_fitting',
                      counts={r: manifest['roles'][r]['n'] for r in ('development', 'primary_new')})
        return manifest
    except Exception as error:
        status.update(status='peak_input_preparation_requires_resolution',
                      error_type=type(error).__name__, error=str(error))
        raise
    finally:
        write_json(work / 'preparation_status.json', status)
        if output.exists():
            audit_folder = work / 'prepared_audit'
            audit_folder.mkdir(exist_ok=True)
            for p in output.glob('*.json'):
                (audit_folder / p.name).write_bytes(p.read_bytes())
        pack_checkpoint(work, work / 'checkpoint/acquisition_checkpoint.zip')
        if status['status'] == 'peak_inputs_complete_before_fitting':
            for p in (work / 'checkpoint').iterdir():
                (output / p.name).write_bytes(p.read_bytes())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo-root', type=Path, default=Path.cwd())
    parser.add_argument('--work-dir', type=Path, required=True)
    parser.add_argument('--resume', type=Path)
    parser.add_argument('--workers', type=int, default=2)
    parser.add_argument('--requests-per-second', type=float, default=2.0)
    parser.add_argument('--prefer-provider', choices=['fide', 'lichess'], default='lichess')
    args = parser.parse_args()
    result = prepare(args.repo_root, args.work_dir, resume=args.resume, workers=args.workers,
                     rate=args.requests_per_second, prefer_provider=args.prefer_provider)
    print(json.dumps({'status': result['status']}))


if __name__ == '__main__':
    main()
