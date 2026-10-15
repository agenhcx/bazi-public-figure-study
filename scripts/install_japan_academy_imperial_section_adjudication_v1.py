#!/usr/bin/env python3
from __future__ import annotations

import hashlib
from pathlib import Path

TARGET = Path("scripts/freeze_japan_academy_imperial_section_adjudication_v1.py")
EXPECTED_SHA256 = "884bdea208a5c8a82445933d27cea6b572e588accedd8797344099b54e26827c"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    if not TARGET.exists():
        raise RuntimeError(
            f"Direct adjudication script is missing: {TARGET}. "
            "Run 'git pull --ff-only origin main' first."
        )
    actual = sha256_file(TARGET)
    if actual != EXPECTED_SHA256:
        raise RuntimeError(
            f"Direct adjudication script SHA mismatch: expected {EXPECTED_SHA256}, got {actual}."
        )
    print(f"DIRECT SCRIPT VERIFIED: {TARGET}")
    print(f"sha256={actual}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
