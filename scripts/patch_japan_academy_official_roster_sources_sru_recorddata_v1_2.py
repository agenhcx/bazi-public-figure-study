#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import shutil
from pathlib import Path

TARGET_DEFAULT = Path("scripts/collect_japan_academy_official_roster_sources_v1.py")
BASE_SHA256 = "761775d8d57a2c585ba488b62d664306f168696ba9a50ca68b50ab076d9e39fd"
PATCHED_SHA256 = "7eb28527686a3c363712b6af265032854172479d532e2b2ca816f01a0ae1980f"
PREVIOUS_REVISION = "seed-collision-promotion-hotfix-v1.1"
REVISION = "sru-recorddata-rdf-hotfix-v1.2"


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
        print(f"NOTICE: target SHA differs from expected v1.1 base: {current_sha}")
        print("The patch will continue only if every exact code anchor is present once.")

    text = replace_once(
        text,
        f'COLLECTOR_REVISION = "{PREVIOUS_REVISION}"',
        f'COLLECTOR_REVISION = "{REVISION}"',
        "collector revision",
    )

    text = replace_once(
        text,
        '''def joined(values: list[str] | None) -> str:
''',
        '''def unpack_sru_record_data(record_data: ET.Element) -> ET.Element:
    # Return the embedded DC-NDL/RDF root for both XML- and string-packed SRU records.
    if list(record_data):
        return record_data
    payload = (record_data.text or "").strip()
    if not payload:
        return record_data
    if payload.startswith("<"):
        try:
            return ET.fromstring(payload)
        except ET.ParseError as e:
            raise RuntimeError(f"Could not parse string-packed SRU recordData: {e}") from e
    return record_data


def joined(values: list[str] | None) -> str:
''',
        "string-packed SRU unpacker",
    )

    text = replace_once(
        text,
        '''        vals = collect_element_values(record_data)
''',
        '''        record_root = unpack_sru_record_data(record_data)
        vals = collect_element_values(record_root)
''',
        "recordData parsing",
    )

    text = replace_once(
        text,
        '''    bibliography_by_pid: dict[str, dict[str, str]] = {}
''',
        '''    sru_records_with_titles = sum(bool(r.get("titles")) for r in sru_records)
    sru_records_with_pids = sum(bool(r.get("pids")) for r in sru_records)
    if not seed_only and sru_records:
        if sru_records_with_titles == 0:
            raise RuntimeError(
                "SRU returned records but no titles were parsed. "
                "The recordData packing format is unsupported or changed."
            )
        if sru_records_with_pids == 0:
            raise RuntimeError(
                "SRU returned records but no NDL digital PIDs were parsed."
            )

    bibliography_by_pid: dict[str, dict[str, str]] = {}
''',
        "SRU parse diagnostics",
    )

    text = replace_once(
        text,
        '''        "sru_records_returned_before_dedup": len(sru_records),
        "bibliographic_pids_after_dedup": len(bibliography),
''',
        '''        "sru_records_returned_before_dedup": len(sru_records),
        "sru_records_with_titles": sru_records_with_titles,
        "sru_records_with_pids": sru_records_with_pids,
        "bibliographic_pids_after_dedup": len(bibliography),
''',
        "summary SRU diagnostics",
    )

    text = replace_once(
        text,
        '''    assert total == 1 and rows[0]["pids"] == "1137238"
    assert classify_series(rows[0]["titles"] + rows[0]["creators"]) == "imperial_academy"
''',
        '''    assert total == 1 and rows[0]["pids"] == "1137238"
    assert classify_series(rows[0]["titles"] + rows[0]["creators"]) == "imperial_academy"
    string_packed = (
        b'<?xml version="1.0" encoding="UTF-8"?>'
        b'<zs:searchRetrieveResponse xmlns:zs="http://www.loc.gov/zing/srw/">'
        b'<zs:numberOfRecords>1</zs:numberOfRecords><zs:records><zs:record>'
        b'<zs:recordPacking>string</zs:recordPacking><zs:recordData>'
        b'&lt;rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" '
        b'xmlns:dc="http://purl.org/dc/elements/1.1/" '
        b'xmlns:dcterms="http://purl.org/dc/terms/"&gt;'
        b'&lt;rdf:Description&gt;'
        b'&lt;dc:title&gt;&#24093;&#22269;&#23398;&#22763;&#38498;&#19968;&#35239; '
        b'&#26157;&#21644;8&#24180;&lt;/dc:title&gt;'
        b'&lt;dc:creator&gt;&#24093;&#22269;&#23398;&#22763;&#38498;&lt;/dc:creator&gt;'
        b'&lt;dcterms:description&gt;https://dl.ndl.go.jp/pid/1137238&lt;/dcterms:description&gt;'
        b'&lt;/rdf:Description&gt;&lt;/rdf:RDF&gt;</zs:recordData>'
        b'</zs:record></zs:records></zs:searchRetrieveResponse>'
    )
    total2, rows2 = parse_sru(string_packed, "q2", 'title="y"')
    assert total2 == 1 and rows2[0]["pids"] == "1137238"
    assert "帝国学士院一覧" in rows2[0]["titles"]
''',
        "string-packed SRU regression test",
    )

    patched = text.encode("utf-8")
    patched_sha = sha256_bytes(patched)
    if patched_sha != PATCHED_SHA256:
        raise RuntimeError(
            f"Patched SHA mismatch: expected {PATCHED_SHA256}, got {patched_sha}; "
            "no file was changed."
        )

    backup = target.with_suffix(target.suffix + ".pre_sru_recorddata_v1_2.bak")
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
