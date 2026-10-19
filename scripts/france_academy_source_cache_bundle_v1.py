#!/usr/bin/env python3
"""Pack or restore checksum-verified public source cache for offline replay.

Only known collector cache basenames are accepted. Original scan images and
unrelated files are never bundled. Source HTML retains its original notices.
Python 3.10+, standard library only; no network requests.
"""
from __future__ import annotations
import argparse
import gzip
import hashlib
import io
import json
import re
import tarfile
from pathlib import Path

CACHE = Path('local_runs/france_academy_211_volume_inventory_source_cache_v1')
NAMES = re.compile(r'(?:category_page_[1-4]\.json|official_journal_archive\.html|table_\d{1,3}_\d{4}\.html(?:\.http\.json)?)\Z')
MANIFEST = 'source_cache_manifest_v1.json'


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def pack(cache, archive):
    paths = sorted(p for p in cache.iterdir() if p.is_file() and NAMES.fullmatch(p.name))
    if not paths:
        raise ValueError('No recognized source cache files')
    content = {p.name: p.read_bytes() for p in paths}
    manifest = {'version': 'france-academy-public-source-cache-bundle-v1',
                'source_types': ['public HTML index transcriptions', 'public catalogue API', 'HTTP404 observations'],
                'original_scan_images_included': False,
                'files': [{'name': name, 'size_bytes': len(raw), 'sha256': digest(raw)}
                          for name, raw in content.items()]}
    content[MANIFEST] = (json.dumps(manifest, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    archive.parent.mkdir(parents=True, exist_ok=True)
    temp = archive.with_suffix(archive.suffix + '.part')
    with temp.open('wb') as stream:
        with gzip.GzipFile(fileobj=stream, mode='wb', filename='', mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode='w') as tar:
                for name, raw in content.items():
                    info = tarfile.TarInfo(name)
                    info.size, info.mode, info.mtime = len(raw), 0o644, 0
                    tar.addfile(info, io.BytesIO(raw))
    temp.replace(archive)
    print(json.dumps({'archive': str(archive), 'source_files': len(paths),
                      'bytes': archive.stat().st_size, 'sha256': digest(archive.read_bytes())}))


def restore(archive, cache):
    with tarfile.open(archive, 'r:gz') as tar:
        members = tar.getmembers()
        if len(members) > 500 or sum(m.size for m in members) > 256_000_000:
            raise ValueError('Source bundle exceeds bounded size')
        if any(not m.isfile() or (m.name != MANIFEST and not NAMES.fullmatch(m.name)) for m in members):
            raise ValueError('Source bundle contains unexpected paths or file types')
        if len({m.name for m in members}) != len(members):
            raise ValueError('Duplicate source archive names')
        blobs = {m.name: tar.extractfile(m).read() for m in members}
    manifest = json.loads(blobs.pop(MANIFEST))
    expected = {x['name']: x for x in manifest['files']}
    if len(expected) != len(manifest['files']) or set(expected) != set(blobs):
        raise ValueError('Manifest/file-set mismatch')
    # Verify every byte before writing any local file.
    for name, raw in blobs.items():
        if digest(raw) != expected[name]['sha256'] or len(raw) != expected[name]['size_bytes']:
            raise ValueError('Source checksum mismatch: ' + name)
    cache.mkdir(parents=True, exist_ok=True)
    for name, raw in blobs.items():
        path = cache / name
        temp = path.with_suffix(path.suffix + '.part')
        temp.write_bytes(raw)
        temp.replace(path)
    print(json.dumps({'restored_source_files': len(blobs), 'cache': str(cache),
                      'all_source_sha256_verified': True, 'network_requests': 0}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--pack', type=Path, metavar='ARCHIVE')
    mode.add_argument('--restore', type=Path, metavar='ARCHIVE')
    parser.add_argument('--cache-root', type=Path, default=CACHE)
    args = parser.parse_args()
    if args.pack:
        pack(args.cache_root, args.pack)
    else:
        restore(args.restore, args.cache_root)


if __name__ == '__main__':
    main()
