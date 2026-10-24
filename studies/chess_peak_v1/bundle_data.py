"""Split peak data for transport and restore it without replacing source files."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import tempfile

PROTOCOL = "chess-peak-data-bundles-v1"
DATA = Path("studies/chess_peak_v1/data")
DEFAULT_PART_SIZE = 786432
MAX_FILE_BYTES = 50 * 1024 * 1024
BLOCK_SIZE = 64 * 1024
MANIFEST_NAME = "bundle_manifest.json"


def _size(value, *, positive=False):
    if type(value) is not int or value < (1 if positive else 0) or value > MAX_FILE_BYTES:
        raise ValueError("Bundle byte count is invalid or exceeds 50 MiB")
    return value


def _digest(value):
    if not isinstance(value, str) or re.fullmatch(r"[a-f0-9]{64}", value) is None:
        raise ValueError("Bundle SHA256 is invalid")
    return value


def _data_root(root):
    root = Path(root).resolve()
    data = root / DATA
    if not data.is_dir() or data.resolve() != data:
        raise ValueError("Peak data directory is absent or contains a symlink")
    return root, data


def _no_symlinks(path, data):
    if not path.is_relative_to(data):
        raise ValueError("Bundle path escapes peak data")
    current = path
    while current != data:
        if current.is_symlink():
            raise ValueError("Bundle paths cannot contain symlinks")
        if current != path and current.exists() and not current.is_dir():
            raise ValueError("Bundle path parent is not a directory")
        current = current.parent
    if not path.resolve().is_relative_to(data):
        raise ValueError("Bundle path escapes peak data")


def _path(root, data, relative, *, part=False):
    if (not isinstance(relative, str) or not relative or "\\" in relative or "\x00" in relative
            or PurePosixPath(relative).is_absolute() or PurePosixPath(relative).as_posix() != relative
            or any(piece in (".", "..") for piece in relative.split("/"))):
        raise ValueError("Bundle path must be a canonical relative POSIX path")
    prefix = (DATA / "bundles").as_posix() + "/" if part else DATA.as_posix() + "/"
    if not relative.startswith(prefix):
        raise ValueError("Bundle path is outside the permitted peak data directory")
    path = root / relative
    if not part and (path == data / MANIFEST_NAME or path.is_relative_to(data / "bundles")):
        raise ValueError("A restored source cannot target bundles or the bundle manifest")
    _no_symlinks(path, data)
    return path


def _hash_file(path, expected_bytes=None):
    if not path.is_file() or path.is_symlink():
        raise ValueError("Bundle source or part is absent or is not a regular file")
    actual = path.stat().st_size
    _size(actual)
    if expected_bytes is not None and actual != expected_bytes:
        raise ValueError("Bundle file byte count differs")
    total, digest = 0, hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(BLOCK_SIZE):
            total += len(chunk)
            _size(total)
            digest.update(chunk)
    if total != actual or (expected_bytes is not None and total != expected_bytes):
        raise ValueError("Bundle file changed while being read")
    return total, digest.hexdigest()


def _verify_file(path, expected_bytes, expected_sha):
    total, actual_sha = _hash_file(path, expected_bytes)
    if actual_sha != expected_sha:
        raise ValueError("Bundle file SHA256 differs")
    return total


def _part_name(sha, basename, index):
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", basename).lstrip(".")[:160] or "file"
    return f"{sha[:16]}_{safe}.part{index:03d}"


def _publish_without_overwrite(temporary, target, expected_bytes, expected_sha):
    """An atomic exclusive link prevents a concurrent target from being replaced."""
    try:
        os.link(temporary, target, follow_symlinks=False)
    except FileExistsError:
        _verify_file(target, expected_bytes, expected_sha)


def _temporary(parent, prefix):
    fd, name = tempfile.mkstemp(prefix=prefix, suffix=".tmp", dir=parent)
    return os.fdopen(fd, "wb"), Path(name)


def pack_data(root, part_size=DEFAULT_PART_SIZE):
    """Keep originals and atomically seal deterministic transport parts last."""
    part_size = _size(part_size, positive=True)
    root, data = _data_root(root)
    bundles = data / "bundles"
    _no_symlinks(bundles, data)
    if bundles.exists() and not bundles.is_dir():
        raise ValueError("Bundle output is not a directory")
    bundles.mkdir(exist_ok=True)
    manifest_path = data / MANIFEST_NAME
    _no_symlinks(manifest_path, data)
    sources = []
    for source in sorted(data.rglob("*")):
        if source == manifest_path or source.is_relative_to(bundles):
            continue
        _no_symlinks(source, data)
        if source.is_dir():
            continue
        if not source.is_file():
            raise ValueError("Peak data contains a nonregular source")
        sources.append(source)
    records = []
    for source in sources:
        relative = source.relative_to(root).as_posix()
        _path(root, data, relative)
        size, whole_sha = _hash_file(source)
        record = {"path": relative, "bytes": size, "sha256": whole_sha, "parts": []}
        if size > part_size:
            whole_check, read_bytes, index = hashlib.sha256(), 0, 1
            with source.open("rb") as stream:
                while read_bytes < size:
                    target = bundles / _part_name(whole_sha, source.name, index)
                    _no_symlinks(target, data)
                    output, temporary = _temporary(bundles, ".bundle-part-")
                    part_bytes, part_sha = 0, hashlib.sha256()
                    try:
                        with output:
                            while part_bytes < part_size and (chunk := stream.read(min(BLOCK_SIZE, part_size - part_bytes))):
                                part_bytes += len(chunk)
                                read_bytes += len(chunk)
                                _size(read_bytes)
                                part_sha.update(chunk)
                                whole_check.update(chunk)
                                output.write(chunk)
                        if part_bytes == 0:
                            raise ValueError("Bundle source became shorter while splitting")
                        digest = part_sha.hexdigest()
                        _publish_without_overwrite(temporary, target, part_bytes, digest)
                        record["parts"].append({"path": target.relative_to(root).as_posix(), "bytes": part_bytes, "sha256": digest})
                    finally:
                        temporary.unlink(missing_ok=True)
                    index += 1
                if stream.read(1) or read_bytes != size or whole_check.hexdigest() != whole_sha:
                    raise ValueError("Bundle source changed between hashing and splitting")
        records.append(record)
    manifest = {"protocol_id": PROTOCOL, "part_size": part_size, "max_file_bytes": MAX_FILE_BYTES, "files": records}
    fd, name = tempfile.mkstemp(prefix=".bundle-manifest-", suffix=".tmp", dir=bundles)
    temporary = Path(name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(manifest, stream, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
            stream.write("\n")
        _size(temporary.stat().st_size)
        _no_symlinks(manifest_path, data)
        os.replace(temporary, manifest_path)
    finally:
        temporary.unlink(missing_ok=True)
    return manifest


def _read_manifest(root, data):
    manifest_path = data / MANIFEST_NAME
    _no_symlinks(manifest_path, data)
    _hash_file(manifest_path)
    def unique_keys(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Bundle manifest contains duplicate JSON keys")
            result[key] = value
        return result
    def invalid_constant(value):
        raise ValueError("Bundle manifest contains an invalid JSON number")
    with manifest_path.open(encoding="utf-8") as stream:
        manifest = json.load(stream, object_pairs_hook=unique_keys, parse_constant=invalid_constant)
    if (not isinstance(manifest, dict) or manifest.get("protocol_id") != PROTOCOL
            or set(manifest) != {"protocol_id", "part_size", "max_file_bytes", "files"}
            or manifest.get("max_file_bytes") != MAX_FILE_BYTES or not isinstance(manifest.get("files"), list)):
        raise ValueError("Bundle manifest protocol/schema is invalid")
    part_size = _size(manifest.get("part_size"), positive=True)
    originals, shared_parts, records = set(), {}, []
    for record in manifest["files"]:
        if not isinstance(record, dict) or set(record) != {"path", "bytes", "sha256", "parts"}:
            raise ValueError("Bundle source record is invalid")
        target = _path(root, data, record.get("path"))
        if record["path"] in originals:
            raise ValueError("Bundle manifest repeats an original source")
        originals.add(record["path"])
        size, whole_sha = _size(record.get("bytes")), _digest(record.get("sha256"))
        parts = record.get("parts")
        if not isinstance(parts, list) or bool(parts) != (size > part_size):
            raise ValueError("Bundle part inventory differs from source size")
        if parts and len(parts) != (size + part_size - 1) // part_size:
            raise ValueError("Bundle part count is inconsistent")
        checked = []
        for index, part in enumerate(parts, 1):
            if not isinstance(part, dict) or set(part) != {"path", "bytes", "sha256"}:
                raise ValueError("Bundle part record is invalid")
            path = _path(root, data, part.get("path"), part=True)
            expected_name = _part_name(whole_sha, target.name, index)
            if path.parent != data / "bundles" or path.name != expected_name:
                raise ValueError("Bundle parts are not in the declared contiguous order")
            count, digest = _size(part.get("bytes"), positive=True), _digest(part.get("sha256"))
            expected_count = min(part_size, size - (index - 1) * part_size)
            if count != expected_count:
                raise ValueError("Bundle part byte count/order is inconsistent")
            previous = shared_parts.setdefault(part["path"], (count, digest))
            if previous != (count, digest):
                raise ValueError("Bundle manifest reuses a part with conflicting fingerprints")
            checked.append((path, count, digest))
        records.append((target, size, whole_sha, checked))
    targets = {record[0] for record in records}
    if any(parent in targets for target in targets for parent in target.parents):
        raise ValueError("Bundle original paths cannot be ancestors of other originals")
    return manifest, records


def _stream_parts(parts, expected_bytes, expected_sha, output=None):
    whole, total = hashlib.sha256(), 0
    for path, count, expected_part_sha in parts:
        if not path.is_file() or path.is_symlink() or path.stat().st_size != count:
            raise ValueError("Bundle part is absent or its byte count differs")
        digest, seen = hashlib.sha256(), 0
        with path.open("rb") as stream:
            while chunk := stream.read(BLOCK_SIZE):
                seen += len(chunk)
                total += len(chunk)
                _size(total)
                if seen > count or total > expected_bytes:
                    raise ValueError("Bundle part exceeds its declared byte count")
                digest.update(chunk)
                whole.update(chunk)
                if output is not None:
                    output.write(chunk)
        if seen != count or digest.hexdigest() != expected_part_sha:
            raise ValueError("Bundle part byte count or SHA256 differs")
    if total != expected_bytes or whole.hexdigest() != expected_sha:
        raise ValueError("Restored bundle whole-file byte count or SHA256 differs")


def restore_bundles(root):
    """Verify all transport inputs, then exclusively publish missing originals."""
    root, data = _data_root(root)
    manifest, records = _read_manifest(root, data)
    for target, size, digest, parts in records:
        _no_symlinks(target, data)
        if target.exists():
            _verify_file(target, size, digest)
        elif not parts:
            raise ValueError("Direct-published bundle source is absent")
        if parts:
            _stream_parts(parts, size, digest)
    for target, size, digest, parts in records:
        if target.exists():
            _verify_file(target, size, digest)
            continue
        _no_symlinks(target, data)
        target.parent.mkdir(parents=True, exist_ok=True)
        _no_symlinks(target.parent, data)
        output, temporary = _temporary(target.parent, ".bundle-restore-")
        try:
            with output:
                _stream_parts(parts, size, digest, output)
            _no_symlinks(target, data)
            _publish_without_overwrite(temporary, target, size, digest)
        finally:
            temporary.unlink(missing_ok=True)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("pack", "restore"))
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--part-size", type=int, default=DEFAULT_PART_SIZE)
    args = parser.parse_args()
    result = pack_data(args.repo_root, args.part_size) if args.command == "pack" else restore_bundles(args.repo_root)
    print(json.dumps({"protocol_id": result["protocol_id"], "files": len(result["files"])}))


if __name__ == "__main__":
    main()
