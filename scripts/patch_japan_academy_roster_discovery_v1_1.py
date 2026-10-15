#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import shutil
from pathlib import Path

TARGET_DEFAULT = Path("scripts/japan_academy_roster_discovery_v1.py")
BASE_SHA256 = "f8b0f1e20bc7210cde292ccf222d025d01633098db1bb74cdc5c490e32c69e32"
PATCHED_SHA256 = "3f87f25eecd2f529dbf01af781a68e755c7add13bc7f64ce637fb7ce7518f2b8"
REVISION = "gannen-unpunctuated-date-hotfix-v1.1"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"Patch anchor {label!r} expected once, found {count}; no file was changed.")
    return text.replace(old, new, 1)


def patch(target: Path) -> None:
    if not target.exists():
        raise FileNotFoundError(f"Target script not found: {target}")

    raw = target.read_bytes()
    current_sha = sha256_bytes(raw)
    normalized = raw.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")

    if current_sha == PATCHED_SHA256 or f'PARSER_REVISION = "{REVISION}"' in normalized:
        print(f"ALREADY PATCHED: {target}")
        print(f"sha256={current_sha}")
        return

    if current_sha != BASE_SHA256:
        print(f"NOTICE: target SHA differs from the packaged v1 base: {current_sha}")
        print("The patch will continue only if every exact code anchor is present once.")

    text = normalized
    text = replace_once(
        text,
        'SCRIPT_VERSION = "japan-academy-roster-discovery-v1"\nBASE = ',
        f'SCRIPT_VERSION = "japan-academy-roster-discovery-v1"\nPARSER_REVISION = "{REVISION}"\nBASE = ',
        "parser revision constant",
    )
    text = replace_once(
        text,
        'ERA_DATE_RE = re.compile(\n'
        '    r"(?P<era>明治|大正|昭和|平成|令和)\\s*(?P<year>元|[0-9０-９]+)\\s*[\\.．年]\\s*"\n'
        '    r"(?P<month>[0-9０-９]+)\\s*[\\.．月]\\s*(?P<day>[0-9０-９]+)\\s*日?"\n'
        ')',
        'ERA_DATE_RE = re.compile(\n'
        '    r"(?P<era>明治|大正|昭和|平成|令和)\\s*"\n'
        '    r"(?:(?P<gannen>元)\\s*[\\.．年]?|(?P<year>[0-9０-９]+)\\s*[\\.．年])\\s*"\n'
        '    r"(?P<month>[0-9０-９]+)\\s*[\\.．月]\\s*(?P<day>[0-9０-９]+)\\s*日?"\n'
        ')',
        "Japanese era-date regex",
    )
    text = replace_once(
        text,
        '        ey = 1 if m.group("year") == "元" else fullwidth_to_int(m.group("year"))',
        '        ey = 1 if m.group("gannen") else fullwidth_to_int(m.group("year"))',
        "gannen conversion",
    )
    text = replace_once(
        text,
        '    summary = {\n        "dataset": SCRIPT_VERSION,',
        '    summary = {\n        "dataset": SCRIPT_VERSION,\n        "parser_revision": PARSER_REVISION,',
        "summary revision field",
    )
    text = replace_once(
        text,
        '    manifest = {\n        "dataset": SCRIPT_VERSION,\n        "script_version": SCRIPT_VERSION,',
        '    manifest = {\n        "dataset": SCRIPT_VERSION,\n        "script_version": SCRIPT_VERSION,\n        "parser_revision": PARSER_REVISION,',
        "manifest revision field",
    )
    text = replace_once(
        text,
        '    assert extract_jp_dates("令和元.6.28") == ["2019-06-28"]\n'
        '    assert extract_jp_dates("昭和10.7.5\\n昭和26.10.17") == ["1935-07-05", "1951-10-17"]',
        '    assert extract_jp_dates("令和元.6.28") == ["2019-06-28"]\n'
        '    assert extract_jp_dates("平成元12.12") == ["1989-12-12"]\n'
        '    assert extract_jp_dates("令和元10.2") == ["2019-10-02"]\n'
        '    assert extract_jp_dates("昭和10.7.5\\n昭和26.10.17") == ["1935-07-05", "1951-10-17"]',
        "gannen regression tests",
    )

    patched = text.encode("utf-8")
    patched_sha = sha256_bytes(patched)
    if patched_sha != PATCHED_SHA256:
        raise RuntimeError(
            f"Patched SHA mismatch: expected {PATCHED_SHA256}, got {patched_sha}; no file was changed."
        )

    backup = target.with_suffix(target.suffix + ".pre_v1_1.bak")
    if not backup.exists():
        shutil.copyfile(target, backup)
    target.write_bytes(patched)

    print(f"PATCH OK: {target}")
    print(f"backup={backup}")
    print(f"sha256={patched_sha}")
    print(f"parser_revision={REVISION}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", default=str(TARGET_DEFAULT))
    args = ap.parse_args()
    patch(Path(args.target))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
