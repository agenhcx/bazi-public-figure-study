#!/usr/bin/env python3
from __future__ import annotations

import hashlib
from pathlib import Path

TARGET = Path("scripts/freeze_japan_academy_imperial_section_adjudication_v1.py")
EXPECTED_NORMALIZED_SHA256 = "884bdea208a5c8a82445933d27cea6b572e588accedd8797344099b54e26827c"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def normalized_lf_bytes(path: Path) -> bytes:
    raw = path.read_bytes()
    text = raw.decode("utf-8")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return text.encode("utf-8")


def main() -> int:
    if not TARGET.exists():
        raise RuntimeError(
            f"Direct adjudication script is missing: {TARGET}. "
            "Run 'git pull --ff-only origin main' first."
        )

    raw = TARGET.read_bytes()
    raw_sha = sha256_bytes(raw)
    normalized_sha = sha256_bytes(normalized_lf_bytes(TARGET))

    if normalized_sha != EXPECTED_NORMALIZED_SHA256:
        raise RuntimeError(
            "Direct adjudication script normalized SHA mismatch: "
            f"expected {EXPECTED_NORMALIZED_SHA256}, got {normalized_sha}; "
            f"raw_sha256={raw_sha}."
        )

    print(f"DIRECT SCRIPT VERIFIED: {TARGET}")
    print(f"normalized_sha256={normalized_sha}")
    print(f"raw_sha256={raw_sha}")
    if raw_sha != normalized_sha:
        print("note=Working-tree line endings differ from repository LF bytes (expected on Windows with CRLF checkout).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
