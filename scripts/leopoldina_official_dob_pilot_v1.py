#!/usr/bin/env python3
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import html
import json
import re
import time
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

ROSTER = Path("data/leopoldina_roster_freeze_v1/leopoldina_science_core_roster_freeze_v1.csv")
FREEZE = Path("data/leopoldina_roster_freeze_v1.json")
OUT = Path("data/leopoldina_official_dob_pilot_v1")
UA = "bazi-public-figure-study/1.0 (Leopoldina official DOB pilot; no BaZi computation)"
SAMPLE_PER_STATUS = 120

BIRTH_RE = re.compile(r"(?i)\b(born|birth(?:day| date)?|geboren|geburt(?:sdatum)?)\b")
MONTHS = {
    "january": 1, "jan": 1, "januar": 1,
    "february": 2, "feb": 2, "februar": 2,
    "march": 3, "mar": 3, "märz": 3, "maerz": 3,
    "april": 4, "apr": 4,
    "may": 5, "mai": 5,
    "june": 6, "jun": 6, "juni": 6,
    "july": 7, "jul": 7, "juli": 7,
    "august": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10, "oktober": 10, "okt": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12, "dezember": 12, "dez": 12,
}
MONTH_ALT = "|".join(sorted((re.escape(x) for x in MONTHS), key=len, reverse=True))
DATE_PATTERNS = [
    ("dmy", re.compile(rf"\b(?P<d>0?[1-9]|[12]\d|3[01])\s*\.?\s*(?P<m>{MONTH_ALT})\s+(?P<y>1[6-9]\d{{2}}|20\d{{2}})\b", re.I)),
    ("mdy", re.compile(rf"\b(?P<m>{MONTH_ALT})\s+(?P<d>0?[1-9]|[12]\d|3[01])\s*(?:st|nd|rd|th)?\s*,?\s*(?P<y>1[6-9]\d{{2}}|20\d{{2}})\b", re.I)),
    ("iso", re.compile(r"\b(?P<y>1[6-9]\d{2}|20\d{2})[-/](?P<mnum>0?[1-9]|1[0-2])[-/](?P<d>0?[1-9]|[12]\d|3[01])\b")),
]

def read_csv(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

def write_csv(path: Path, rows, fields):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

def sha256(path: Path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

def strip_html(raw: bytes):
    s = raw.decode("utf-8", "replace")
    s = re.sub(r"(?is)<script\b.*?</script>", " ", s)
    s = re.sub(r"(?is)<style\b.*?</style>", " ", s)
    s = re.sub(r"(?s)<[^>]+>", " ", s)
    s = html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()

def fetch(url: str, retries=5):
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": UA,
                    "Accept": "text/html,application/xhtml+xml",
                    "Accept-Language": "en-US,en;q=0.9,de;q=0.8",
                },
            )
            with urllib.request.urlopen(req, timeout=75) as r:
                return r.status, r.geturl(), r.read(), ""
        except Exception as e:
            last = e
            if attempt + 1 < retries:
                time.sleep(min(16, 2 ** attempt))
    return "", url, b"", repr(last)

def evenly_spaced(rows, n):
    rows = list(rows)
    if len(rows) <= n:
        return rows
    if n <= 1:
        return [rows[0]]
    idx = []
    for i in range(n):
        j = round(i * (len(rows) - 1) / (n - 1))
        if j not in idx:
            idx.append(j)
    return [rows[j] for j in idx]

def month_num(raw: str):
    k = raw.casefold().strip()
    return MONTHS.get(k)

def normalized_dates(text: str):
    found = []
    birth_positions = [m.start() for m in BIRTH_RE.finditer(text)]
    for kind, pat in DATE_PATTERNS:
        for m in pat.finditer(text):
            try:
                y = int(m.group("y"))
                d = int(m.group("d"))
                if kind == "iso":
                    mo = int(m.group("mnum"))
                else:
                    mo = month_num(m.group("m"))
                if not mo:
                    continue
                dob = dt.date(y, mo, d).isoformat()
            except Exception:
                continue
            nearest = min((abs(m.start() - p) for p in birth_positions), default=10**9)
            if nearest > 160:
                continue
            a = max(0, min(m.start(), min(birth_positions, key=lambda p: abs(m.start()-p), default=m.start())) - 140)
            b = min(len(text), max(m.end(), min(birth_positions, key=lambda p: abs(m.start()-p), default=m.end())) + 180)
            snippet = text[a:b].strip()
            found.append((dob, nearest, snippet, m.group(0)))
    # Deduplicate by normalized date, keeping closest birth-term occurrence.
    best = {}
    for dob, dist, snippet, raw in found:
        if dob not in best or dist < best[dob][0]:
            best[dob] = (dist, snippet, raw)
    return [
        {"dob": dob, "distance": best[dob][0], "raw": best[dob][2], "snippet": best[dob][1]}
        for dob in sorted(best)
    ]

def era(year: int):
    if year <= 1900:
        return "<=1900"
    if year <= 1950:
        return "1901-1950"
    if year <= 2000:
        return "1951-2000"
    return "2001-2025"

def main():
    freeze = json.loads(FREEZE.read_text(encoding="utf-8"))
    rows = read_csv(ROSTER)
    if len(rows) != 2888:
        raise RuntimeError(f"Expected 2888 frozen roster rows, got {len(rows)}")
    if freeze.get("checksums", {}).get("roster_csv_sha256") != sha256(ROSTER):
        raise RuntimeError("Frozen Leopoldina roster hash mismatch")

    deceased = sorted(
        [r for r in rows if str(r.get("deceased_marker", "")).strip() == "1"],
        key=lambda r: (int(r["election_year"]), r["member_slug"]),
    )
    nondeceased = sorted(
        [r for r in rows if str(r.get("deceased_marker", "")).strip() != "1"],
        key=lambda r: (int(r["election_year"]), r["member_slug"]),
    )
    sample = evenly_spaced(deceased, SAMPLE_PER_STATUS) + evenly_spaced(nondeceased, SAMPLE_PER_STATUS)
    if len(sample) != min(SAMPLE_PER_STATUS, len(deceased)) + min(SAMPLE_PER_STATUS, len(nondeceased)):
        raise RuntimeError("Deterministic sample size invariant failed")

    OUT.mkdir(parents=True, exist_ok=True)
    out = []
    for i, r in enumerate(sample, 1):
        status, final_url, raw, error = fetch(r["detail_url"])
        text = strip_html(raw) if raw else ""
        candidates = normalized_dates(text) if text else []
        unique_dobs = [x["dob"] for x in candidates]
        ey = int(r["election_year"])
        candidate = unique_dobs[0] if len(unique_dobs) == 1 else ""
        age = ey - int(candidate[:4]) if candidate else None
        age_plausible = int(age is not None and 15 <= age <= 110) if candidate else ""
        rec = {
            "member_slug": r["member_slug"],
            "display_name": r["display_name"],
            "detail_url": r["detail_url"],
            "deceased_marker": r["deceased_marker"],
            "class": r["class"],
            "section": r["section"],
            "election_year": r["election_year"],
            "election_era": era(ey),
            "http_status": status,
            "final_url": final_url,
            "error": error,
            "birth_term_hits": len(BIRTH_RE.findall(text)) if text else 0,
            "candidate_count": len(unique_dobs),
            "candidate_dobs": "|".join(unique_dobs),
            "unique_candidate_dob": candidate,
            "age_at_election_if_unique": age if age is not None else "",
            "age_plausible_if_unique": age_plausible,
            "candidate_raw_strings": " || ".join(x["raw"] for x in candidates),
            "evidence_snippets": " || ".join(x["snippet"] for x in candidates[:4]),
            "accepted_exact_dob": "",
            "bazi_variables_computed": 0,
        }
        out.append(rec)
        print(
            f"{i}/{len(sample)} dead={r['deceased_marker']} year={r['election_year']} "
            f"{r['member_slug']} http={status} candidates={len(unique_dobs)}"
        )
        time.sleep(0.08)

    fields = list(out[0].keys())
    write_csv(OUT / "pilot_rows.csv", out, fields)

    by_status = {}
    for label, pred in (
        ("deceased_marker", lambda x: x["deceased_marker"] == "1"),
        ("no_deceased_marker", lambda x: x["deceased_marker"] != "1"),
    ):
        rr = [x for x in out if pred(x)]
        by_status[label] = {
            "sample_n": len(rr),
            "http_200": sum(str(x["http_status"]) == "200" for x in rr),
            "birth_term_positive": sum(int(x["birth_term_hits"]) > 0 for x in rr),
            "unique_exact_candidate": sum(bool(x["unique_candidate_dob"]) for x in rr),
            "unique_exact_candidate_age_plausible": sum(bool(x["unique_candidate_dob"]) and x["age_plausible_if_unique"] == 1 for x in rr),
            "multiple_exact_candidates": sum(int(x["candidate_count"]) > 1 for x in rr),
            "errors": sum(bool(x["error"]) for x in rr),
        }

    by_era = {}
    for e in ("<=1900", "1901-1950", "1951-2000", "2001-2025"):
        rr = [x for x in out if x["election_era"] == e]
        by_era[e] = {
            "sample_n": len(rr),
            "deceased_marker": sum(x["deceased_marker"] == "1" for x in rr),
            "unique_exact_candidate": sum(bool(x["unique_candidate_dob"]) for x in rr),
            "multiple_exact_candidates": sum(int(x["candidate_count"]) > 1 for x in rr),
        }

    ambiguous = [x for x in out if int(x["candidate_count"]) > 1]
    candidates = [x for x in out if x["unique_candidate_dob"]]
    write_csv(OUT / "unique_candidates_for_review.csv", candidates, fields)
    write_csv(OUT / "ambiguous_candidates_for_review.csv", ambiguous, fields)

    summary = {
        "dataset": "Leopoldina official-profile exact-DOB pilot v1",
        "frozen_roster_rows": len(rows),
        "frozen_roster_sha256": sha256(ROSTER),
        "sample_method": "120 evenly spaced deceased-marker rows + 120 evenly spaced no-deceased-marker rows, sorted by election_year and member_slug",
        "sample_total": len(out),
        "by_status": by_status,
        "by_election_era": by_era,
        "overall": {
            "http_200": sum(str(x["http_status"]) == "200" for x in out),
            "birth_term_positive": sum(int(x["birth_term_hits"]) > 0 for x in out),
            "unique_exact_candidate": len(candidates),
            "unique_exact_candidate_age_plausible": sum(x["age_plausible_if_unique"] == 1 for x in candidates),
            "multiple_exact_candidates": len(ambiguous),
            "errors": sum(bool(x["error"]) for x in out),
        },
        "dob_values_accepted": 0,
        "bazi_variables_computed": 0,
        "decision_rule": "Diagnostic only. Do not write DOBs. Expand only after candidate snippets are reviewed and official-page precision is established.",
    }
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
