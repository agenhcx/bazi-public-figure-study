#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import shutil
from pathlib import Path

TARGET_DEFAULT = Path("scripts/collect_japan_academy_official_roster_sources_v1.py")
BASE_SHA256 = "994a0d0a0cab9e4482fefb1ef2af70ae34955465e46896be60cca0da70696a3b"
PATCHED_SHA256 = "761775d8d57a2c585ba488b62d664306f168696ba9a50ca68b50ab076d9e39fd"
REVISION = "seed-collision-promotion-hotfix-v1.1"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(
            f"Patch anchor {label!r} expected once, found {count}; no file was changed."
        )
    return text.replace(old, new, 1)


def patch(target: Path) -> None:
    if not target.exists():
        raise FileNotFoundError(f"Target script not found: {target}")

    raw = target.read_bytes()
    current_sha = sha256_bytes(raw)
    text = raw.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")

    if current_sha == PATCHED_SHA256 or f'COLLECTOR_REVISION = "{REVISION}"' in text:
        print(f"ALREADY PATCHED: {target}")
        print(f"sha256={current_sha}")
        return

    if current_sha != BASE_SHA256:
        print(f"NOTICE: target SHA differs from packaged v1 base: {current_sha}")
        print("The patch will continue only if every exact code anchor is present once.")

    text = replace_once(
        text,
        'SCRIPT_VERSION = "japan-academy-official-roster-sources-v1"\nDEFAULT_OUT = ',
        f'SCRIPT_VERSION = "japan-academy-official-roster-sources-v1"\n'
        f'COLLECTOR_REVISION = "{REVISION}"\n'
        'DEFAULT_OUT = ',
        "collector revision constant",
    )

    old_seed_block = '''        else:
            bibliography_by_pid[pid]["seed_note"] = seed["seed_note"]
            if not bibliography_by_pid[pid].get("series"):
                bibliography_by_pid[pid]["series"] = seed["series"]

    bibliography = sorted(bibliography_by_pid.values(), key=lambda r: (r.get("series", ""), r.get("issued_or_dates", ""), r["pid"]))
    official = [r for r in bibliography if r.get("official_source_candidate") == "1"]
'''
    new_seed_block = '''        else:
            # A frozen seed is an explicit official-series anchor. If the same PID
            # was already found by SRU with incomplete/variant metadata, promote
            # that existing row instead of leaving it non-official.
            bibliography_by_pid[pid]["seed_note"] = seed["seed_note"]
            bibliography_by_pid[pid]["series"] = seed["series"]
            bibliography_by_pid[pid]["official_source_candidate"] = "1"

    seed_pids = {r["pid"] for r in SEED_RECORDS}
    seed_targets = {
        pid for pid, row in bibliography_by_pid.items()
        if pid in seed_pids and row.get("official_source_candidate") == "1"
    }
    if seed_targets != seed_pids:
        missing = sorted(seed_pids - seed_targets)
        raise RuntimeError(f"Frozen seed PIDs were not promoted to manifest targets: {missing}")

    bibliography = sorted(bibliography_by_pid.values(), key=lambda r: (r.get("series", ""), r.get("issued_or_dates", ""), r["pid"]))
    official = [r for r in bibliography if r.get("official_source_candidate") == "1"]
'''
    text = replace_once(text, old_seed_block, new_seed_block, "seed collision promotion")

    text = replace_once(
        text,
        '''    summary = {
        "dataset": SCRIPT_VERSION,
        "source_snapshot_date": "2026-10-14",
''',
        '''    summary = {
        "dataset": SCRIPT_VERSION,
        "collector_revision": COLLECTOR_REVISION,
        "source_snapshot_date": "2026-10-14",
''',
        "summary revision field",
    )

    text = replace_once(
        text,
        '''        "seed_pids": [r["pid"] for r in SEED_RECORDS],
        "collection_scope": "NDL Search bibliographic metadata and NDL Digital Collection IIIF manifests only",
''',
        '''        "seed_pids": [r["pid"] for r in SEED_RECORDS],
        "seed_pids_marked_official": len(seed_targets),
        "collection_scope": "NDL Search bibliographic metadata and NDL Digital Collection IIIF manifests only",
''',
        "summary seed target count",
    )

    text = replace_once(
        text,
        '''    manifest = {
        "dataset": SCRIPT_VERSION,
        "script_version": SCRIPT_VERSION,
''',
        '''    manifest = {
        "dataset": SCRIPT_VERSION,
        "script_version": SCRIPT_VERSION,
        "collector_revision": COLLECTOR_REVISION,
''',
        "manifest revision field",
    )

    patched = text.encode("utf-8")
    patched_sha = sha256_bytes(patched)
    if patched_sha != PATCHED_SHA256:
        raise RuntimeError(
            f"Patched SHA mismatch: expected {PATCHED_SHA256}, got {patched_sha}; "
            "no file was changed."
        )

    backup = target.with_suffix(target.suffix + ".pre_seed_target_v1_1.bak")
    if not backup.exists():
        shutil.copyfile(target, backup)
    target.write_bytes(patched)

    print(f"PATCH OK: {target}")
    print(f"backup={backup}")
    print(f"sha256={patched_sha}")
    print(f"collector_revision={REVISION}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", default=str(TARGET_DEFAULT))
    args = ap.parse_args()
    patch(Path(args.target))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
