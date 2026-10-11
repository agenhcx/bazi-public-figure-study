#!/usr/bin/env python3
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path

ROSTER = Path("data/leopoldina_roster_freeze_v1/leopoldina_science_core_roster_freeze_v1.csv")
FREEZE = Path("data/leopoldina_roster_freeze_v1.json")
OUT = Path("data/leopoldina_dob_local_v1")
QLEVER = "https://qlever.dev/api/wikidata"
UA = "bazi-public-figure-study/1.0 (Leopoldina local DOB candidate collection; no BaZi computation)"

try:
    import certifi
except ImportError:
    certifi = None

def verified_tls_contexts():
    contexts = []
    if certifi is not None:
        contexts.append(("certifi", ssl.create_default_context(cafile=certifi.where())))
    contexts.append(("system", ssl.create_default_context()))
    return contexts

def urlopen_verified(req, timeout):
    cert_errors = []
    for label, context in verified_tls_contexts():
        try:
            return urllib.request.urlopen(req, timeout=timeout, context=context)
        except urllib.error.URLError as e:
            reason = getattr(e, "reason", None)
            if isinstance(reason, ssl.SSLCertVerificationError) or "CERTIFICATE_VERIFY_FAILED" in str(e):
                cert_errors.append(f"{label}: {e}")
                continue
            raise
    detail = " | ".join(cert_errors) if cert_errors else "unknown certificate error"
    hint = (
        "TLS certificate verification failed with every trusted CA source. "
        "Run: python -m pip install --upgrade certifi . "
        "If it still fails, a VPN/proxy/security product may be presenting an expired HTTPS certificate; "
        "fix or disable that interception rather than disabling certificate verification."
    )
    raise RuntimeError(f"{hint} Details: {detail}")

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

def qlever_tsv(query: str, retries=8):
    body = urllib.parse.urlencode({"query": query, "action": "tsv_export"}).encode()
    last = None
    for attempt in range(retries):
        req = urllib.request.Request(
            QLEVER,
            data=body,
            method="POST",
            headers={
                "User-Agent": UA,
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "text/tab-separated-values",
            },
        )
        try:
            with urlopen_verified(req, timeout=300) as r:
                raw = r.read().decode("utf-8-sig")
            break
        except (urllib.error.HTTPError, urllib.error.URLError) as e:
            last = e
            code = getattr(e, "code", None)
            if attempt + 1 >= retries or (code is not None and code not in {429, 500, 502, 503, 504}):
                raise
            time.sleep(min(60, 2 ** attempt + 1))
    else:
        raise RuntimeError(f"QLever failed after retries: {last}")

    rr = list(csv.reader(raw.splitlines(), delimiter="\t"))
    if not rr:
        return []
    headers = [x.lstrip("?").strip() for x in rr[0]]
    out = []
    for row in rr[1:]:
        row += [""] * (len(headers) - len(row))
        item = {}
        for i, h in enumerate(headers):
            v = (row[i] or "").strip()
            if v.startswith("<") and v.endswith(">"):
                v = v[1:-1]
            elif v.startswith('"'):
                m = re.match(r'^"(.*)"(?:\^\^<[^>]+>|@[A-Za-z-]+)?$', v)
                if m:
                    v = m.group(1)
            item[h] = v
        out.append(item)
    return out

def parse_qid(v):
    return (v or "").rsplit("/", 1)[-1]

def parse_date(v):
    m = re.search(r"([12]\d{3})-(\d{2})-(\d{2})", v or "")
    if not m:
        return ""
    try:
        return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat()
    except ValueError:
        return ""

def as_int(v):
    try:
        return int(float(str(v)))
    except Exception:
        return None

def era(year):
    y = int(year)
    if y <= 1900:
        return "<=1900"
    if y <= 1950:
        return "1901-1950"
    if y <= 2000:
        return "1951-2000"
    return "2001-2025"

def main():
    freeze = json.loads(FREEZE.read_text(encoding="utf-8"))
    roster = read_csv(ROSTER)
    expected_hash = freeze.get("checksums", {}).get("roster_csv_sha256")
    actual_hash = sha256(ROSTER)
    if len(roster) != 2888:
        raise RuntimeError(f"Expected 2888 frozen roster rows, got {len(roster)}")
    if actual_hash != expected_hash:
        raise RuntimeError(f"Frozen roster hash mismatch: {actual_hash} != {expected_hash}")
    slugs = [r["member_slug"].strip() for r in roster]
    if len(slugs) != len(set(slugs)):
        raise RuntimeError("Frozen member_slug values are not unique")

    query = """
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX p: <http://www.wikidata.org/prop/>
PREFIX psv: <http://www.wikidata.org/prop/statement/value/>
PREFIX wikibase: <http://wikiba.se/ontology#>
SELECT ?person ?memberId ?dob ?precision ?gnd ?loc WHERE {
  ?person wdt:P10299 ?memberId .
  OPTIONAL {
    ?person p:P569 ?dobStatement .
    ?dobStatement psv:P569 ?dobNode .
    ?dobNode wikibase:timeValue ?dob ;
             wikibase:timePrecision ?precision .
  }
  OPTIONAL { ?person wdt:P227 ?gnd . }
  OPTIONAL { ?person wdt:P244 ?loc . }
}
"""
    raw = qlever_tsv(query)
    by_slug = defaultdict(lambda: {"qids": set(), "dates": set(), "gnd": set(), "loc": set()})
    for x in raw:
        slug = (x.get("memberId") or "").strip()
        if not slug:
            continue
        qid = parse_qid(x.get("person", ""))
        if qid:
            by_slug[slug]["qids"].add(qid)
        p = as_int(x.get("precision"))
        d = parse_date(x.get("dob", ""))
        if d and p is not None:
            by_slug[slug]["dates"].add((d, p))
        g = (x.get("gnd") or "").strip()
        l = (x.get("loc") or "").strip()
        if g:
            by_slug[slug]["gnd"].add(g)
        if l:
            by_slug[slug]["loc"].add(l)

    crosswalk = []
    for r in roster:
        slug = r["member_slug"].strip()
        w = by_slug.get(slug, {"qids": set(), "dates": set(), "gnd": set(), "loc": set()})
        qids = sorted(w["qids"])
        day_dates = sorted({d for d, p in w["dates"] if p >= 11})
        date_values = sorted(f"{d}@p{p}" for d, p in w["dates"])
        candidate = day_dates[0] if len(qids) == 1 and len(day_dates) == 1 else ""
        age = int(r["election_year"]) - int(candidate[:4]) if candidate else None
        age_ok = int(age is not None and 15 <= age <= 110) if candidate else ""
        status = (
            "candidate_unique_day_p569"
            if candidate and age_ok == 1
            else "review_implausible_age"
            if candidate
            else "review_multiple_qids"
            if len(qids) > 1
            else "review_multiple_day_dates"
            if len(day_dates) > 1
            else "no_p10299_match"
            if len(qids) == 0
            else "no_day_precision_p569"
        )
        crosswalk.append({
            "member_slug": slug,
            "display_name": r["display_name"],
            "detail_url": r["detail_url"],
            "deceased_marker": r["deceased_marker"],
            "class": r["class"],
            "section": r["section"],
            "election_year": r["election_year"],
            "election_era": era(r["election_year"]),
            "wikidata_qids": "|".join(qids),
            "qid_count": len(qids),
            "wikidata_date_values": "|".join(date_values),
            "day_precision_dates": "|".join(day_dates),
            "day_precision_date_count": len(day_dates),
            "candidate_exact_dob": candidate,
            "age_at_election_if_candidate": age if age is not None else "",
            "age_plausible_if_candidate": age_ok,
            "gnd_ids": "|".join(sorted(w["gnd"])),
            "loc_ids": "|".join(sorted(w["loc"])),
            "collection_status": status,
            "final_exact_dob": "",
            "acceptance_status": "not_adjudicated",
            "bazi_variables_computed": 0,
        })

    OUT.mkdir(parents=True, exist_ok=True)
    fields = list(crosswalk[0].keys())
    write_csv(OUT / "leopoldina_dob_candidate_crosswalk_v1.csv", crosswalk, fields)

    candidate = [x for x in crosswalk if x["collection_status"] == "candidate_unique_day_p569"]
    review = [x for x in crosswalk if x["collection_status"].startswith("review_")]
    unmatched = [x for x in crosswalk if x["collection_status"] == "no_p10299_match"]
    no_day = [x for x in crosswalk if x["collection_status"] == "no_day_precision_p569"]
    write_csv(OUT / "candidate_unique_day_p569_v1.csv", candidate, fields)
    write_csv(OUT / "review_queue_v1.csv", review, fields)
    write_csv(OUT / "unmatched_p10299_v1.csv", unmatched, fields)
    write_csv(OUT / "no_day_precision_p569_v1.csv", no_day, fields)

    def stats(rr):
        return {
            "rows": len(rr),
            "candidate_unique_day_p569": sum(x["collection_status"] == "candidate_unique_day_p569" for x in rr),
            "review_rows": sum(x["collection_status"].startswith("review_") for x in rr),
            "unmatched_p10299": sum(x["collection_status"] == "no_p10299_match" for x in rr),
            "no_day_precision_p569": sum(x["collection_status"] == "no_day_precision_p569" for x in rr),
        }

    summary = {
        "dataset": "Leopoldina local DOB candidate collection v1",
        "frozen_roster_rows": len(roster),
        "frozen_roster_sha256": actual_hash,
        "identity_rule": "Exact frozen official member_slug == Wikidata P10299. No name or fuzzy matching.",
        "candidate_rule": "Exactly one P10299 QID, exactly one P569 value with Wikidata timePrecision >= 11, and plausible election age 15-110.",
        "acceptance_rule": "Candidate generation only. P569 is not final evidence; final_exact_dob remains blank pending provenance adjudication under the hierarchy-wide source policy.",
        "overall": stats(crosswalk),
        "by_status": {
            "deceased_marker": stats([x for x in crosswalk if x["deceased_marker"] == "1"]),
            "no_deceased_marker": stats([x for x in crosswalk if x["deceased_marker"] != "1"]),
        },
        "by_election_era": {
            e: stats([x for x in crosswalk if x["election_era"] == e])
            for e in ("<=1900", "1901-1950", "1951-2000", "2001-2025")
        },
        "output_files": {
            "crosswalk": "leopoldina_dob_candidate_crosswalk_v1.csv",
            "candidates": "candidate_unique_day_p569_v1.csv",
            "review": "review_queue_v1.csv",
            "unmatched": "unmatched_p10299_v1.csv",
            "no_day": "no_day_precision_p569_v1.csv",
        },
        "bazi_variables_computed": 0,
    }
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
