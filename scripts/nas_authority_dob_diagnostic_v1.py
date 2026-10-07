#!/usr/bin/env python3
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

BASE = Path("data/nas_science_core_dob_crosswalk")
INPUT = BASE / "nas_science_core_dob_crosswalk_v11.csv"
AVAIL = BASE / "nas_science_core_dob_availability_v1.csv"
OUT_DIAG = BASE / "nas_authority_dob_diagnostic_v1.csv"
OUT_CAND = BASE / "nas_authority_dob_candidates_v1.csv"
OUT_CONFLICT = BASE / "nas_authority_dob_validation_conflicts_v1.csv"
OUT_SUMMARY = BASE / "summary_authority_dob_diagnostic_v1.json"

QLEVER = "https://qlever.dev/api/wikidata"
USER_AGENT = "bazi-public-figure-study/1.0 (NAS authority DOB diagnostic; no BaZi computation)"
VALIDATION_N = 300
MAX_WORKERS = 6
BETWEEN_REQUEST_SECONDS = 0.10

def read_csv(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

def write_csv(path: Path, rows, fields=None):
    if fields is None:
        fields = list(rows[0].keys()) if rows else []
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

def present(v):
    return str(v or "").strip() not in ("", "nan", "None")

def as_int(v, default=0):
    try:
        return int(float(str(v)))
    except Exception:
        return default

def reliable_qid(row):
    q = str(row.get("wikidata_qid") or "").strip()
    if q:
        return q, row.get("wikidata_match_method", "") or "wikidata_crosswalk"
    q = str(row.get("global_candidate_qid") or "").strip()
    if q and as_int(row.get("global_match_accepted")) == 1:
        return q, "global_exact_name_accepted"
    return "", ""

def valid_exact_date(s: str) -> str:
    s = str(s or "").strip()
    m = re.fullmatch(r"([12]\d{3})-(\d{2})-(\d{2})", s)
    if not m:
        m = re.fullmatch(r"([12]\d{3})(\d{2})(\d{2})", s)
    if not m:
        return ""
    try:
        return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat()
    except ValueError:
        return ""

def validation_hash(row):
    return hashlib.sha256(row["profile_url"].encode("utf-8")).hexdigest()

def qlever_tsv(query: str, retries: int = 6):
    body = urllib.parse.urlencode({"query": query, "action": "tsv_export"}).encode()
    last = None
    for attempt in range(retries):
        req = urllib.request.Request(
            QLEVER,
            data=body,
            method="POST",
            headers={
                "User-Agent": USER_AGENT,
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "text/tab-separated-values",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                raw = r.read().decode("utf-8-sig")
            break
        except (urllib.error.HTTPError, urllib.error.URLError) as e:
            last = e
            code = getattr(e, "code", None)
            if attempt + 1 >= retries or (code is not None and code not in {429, 500, 502, 503, 504}):
                raise
            time.sleep(min(30, 2 ** attempt))
    else:
        raise RuntimeError(f"QLever failed after retries: {last}")

    rr = list(csv.reader(raw.splitlines(), delimiter="\t"))
    if not rr:
        return []
    headers = [x.lstrip("?").strip() for x in rr[0]]
    out = []
    for row in rr[1:]:
        if not row:
            continue
        row += [""] * (len(headers) - len(row))
        item = {}
        for i, h in enumerate(headers):
            v = (row[i] or "").strip()
            if v.startswith("<") and v.endswith(">"):
                v = v[1:-1]
            elif len(v) >= 2 and v[0] == '"':
                end = v.rfind('"')
                if end > 0:
                    v = v[1:end]
            item[h] = v
        out.append(item)
    return out

def chunks(seq, n=180):
    for i in range(0, len(seq), n):
        yield seq[i:i+n]

def authority_ids_for_qids(qids):
    out = defaultdict(lambda: {"gnd": set(), "loc": set()})
    for batch in chunks(sorted(set(qids))):
        values = " ".join("wd:" + q for q in batch if re.fullmatch(r"Q\d+", q))
        if not values:
            continue
        query = f"""
PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
SELECT ?person ?gnd ?loc WHERE {{
  VALUES ?person {{ {values} }}
  OPTIONAL {{ ?person wdt:P227 ?gnd . }}
  OPTIONAL {{ ?person wdt:P244 ?loc . }}
}}
"""
        for r in qlever_tsv(query):
            qid = (r.get("person") or "").rsplit("/", 1)[-1]
            if not qid:
                continue
            g = (r.get("gnd") or "").strip()
            l = (r.get("loc") or "").strip()
            if g:
                out[qid]["gnd"].add(g)
            if l:
                out[qid]["loc"].add(l)
    return out

def http_json(url: str, retries: int = 5):
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=90) as r:
                obj = json.loads(r.read().decode("utf-8"))
            time.sleep(BETWEEN_REQUEST_SECONDS)
            return {"ok": 1, "status": getattr(r, "status", 200), "obj": obj, "error": ""}
        except urllib.error.HTTPError as e:
            last = e
            if e.code == 404:
                return {"ok": 0, "status": 404, "obj": None, "error": "HTTP 404"}
            if attempt + 1 >= retries or e.code not in {429, 500, 502, 503, 504}:
                break
            delay = e.headers.get("Retry-After", "")
            try:
                delay = float(delay)
            except Exception:
                delay = min(30.0, 2.0 ** attempt)
            time.sleep(max(1.0, min(60.0, delay)))
        except Exception as e:
            last = e
            if attempt + 1 >= retries:
                break
            time.sleep(min(20.0, 2.0 ** attempt))
    return {"ok": 0, "status": getattr(last, "code", ""), "obj": None, "error": repr(last)}

def parse_gnd_birth_dates(obj):
    vals = set()
    if not isinstance(obj, dict):
        return []
    raw = obj.get("dateOfBirth", [])
    if not isinstance(raw, list):
        raw = [raw]
    for x in raw:
        if isinstance(x, dict):
            for k in ("@value", "value", "label"):
                d = valid_exact_date(x.get(k, ""))
                if d:
                    vals.add(d)
        else:
            d = valid_exact_date(x)
            if d:
                vals.add(d)
    return sorted(vals)

def walk_birth_values(obj, parent_key=""):
    vals = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            lk = str(k).lower()
            if "birthdate" in lk or lk.endswith("#birthdate"):
                vals.append(v)
            vals.extend(walk_birth_values(v, lk))
    elif isinstance(obj, list):
        for x in obj:
            vals.extend(walk_birth_values(x, parent_key))
    return vals

def scalar_strings(obj):
    out = []
    if isinstance(obj, str):
        out.append(obj)
    elif isinstance(obj, dict):
        for k in ("@value", "value"):
            if isinstance(obj.get(k), str):
                out.append(obj[k])
        for v in obj.values():
            if isinstance(v, (dict, list)):
                out.extend(scalar_strings(v))
    elif isinstance(obj, list):
        for x in obj:
            out.extend(scalar_strings(x))
    return out

def parse_loc_birth_dates(obj):
    vals = set()
    for raw in walk_birth_values(obj):
        for s in scalar_strings(raw):
            d = valid_exact_date(s)
            if d:
                vals.add(d)
    return sorted(vals)

def fetch_gnd(gid):
    url = f"https://lobid.org/gnd/{urllib.parse.quote(gid)}.json"
    r = http_json(url)
    r.update({"id": gid, "url": url, "dates": parse_gnd_birth_dates(r.get("obj")) if r["ok"] else []})
    r.pop("obj", None)
    return r

def fetch_loc(lid):
    url = f"https://id.loc.gov/authorities/names/{urllib.parse.quote(lid)}.json"
    r = http_json(url)
    r.update({"id": lid, "url": url, "dates": parse_loc_birth_dates(r.get("obj")) if r["ok"] else []})
    r.pop("obj", None)
    return r

def fetch_many(ids, fn):
    out = {}
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futs = {ex.submit(fn, x): x for x in sorted(set(ids))}
        for fut in as_completed(futs):
            x = futs[fut]
            try:
                out[x] = fut.result()
            except Exception as e:
                out[x] = {"id": x, "url": "", "ok": 0, "status": "", "dates": [], "error": repr(e)}
    return out

def source_dates(ids, fetched):
    vals = set()
    successful_ids = 0
    for x in ids:
        rec = fetched.get(x, {})
        if rec.get("ok"):
            successful_ids += 1
        vals.update(rec.get("dates") or [])
    return sorted(vals), successful_ids

def choose_authority_date(gnd_dates, loc_dates):
    g_unique = gnd_dates[0] if len(gnd_dates) == 1 else ""
    l_unique = loc_dates[0] if len(loc_dates) == 1 else ""
    conflict = int(bool(g_unique and l_unique and g_unique != l_unique))
    if conflict:
        return "", "gnd_loc_conflict", conflict
    if g_unique and l_unique:
        return g_unique, "gnd_plus_loc_agree", conflict
    if g_unique:
        return g_unique, "gnd_unique", conflict
    if l_unique:
        return l_unique, "loc_unique", conflict
    return "", "", conflict

def main():
    rows = read_csv(INPUT)
    if len(rows) != 3051:
        raise RuntimeError(f"Expected 3051 v11 rows, got {len(rows)}")

    avail_by_url = {}
    if AVAIL.exists():
        avail_by_url = {r["profile_url"]: r for r in read_csv(AVAIL)}

    qid_by_url = {}
    basis_by_url = {}
    for r in rows:
        q, b = reliable_qid(r)
        if q:
            qid_by_url[r["profile_url"]] = q
            basis_by_url[r["profile_url"]] = b

    qids = sorted(set(qid_by_url.values()))
    ids_by_qid = authority_ids_for_qids(qids)

    missing = [r for r in rows if not present(r.get("final_exact_dob")) and r["profile_url"] in qid_by_url]
    known = [r for r in rows if present(r.get("final_exact_dob")) and r["profile_url"] in qid_by_url]

    validation_eligible = [
        r for r in known
        if ids_by_qid.get(qid_by_url[r["profile_url"]], {}).get("gnd")
        or ids_by_qid.get(qid_by_url[r["profile_url"]], {}).get("loc")
    ]
    validation_eligible.sort(key=validation_hash)
    validation = validation_eligible[:VALIDATION_N]

    target = validation + missing
    target_qids = {qid_by_url[r["profile_url"]] for r in target}
    gnd_ids = set()
    loc_ids = set()
    for q in target_qids:
        gnd_ids |= ids_by_qid.get(q, {}).get("gnd", set())
        loc_ids |= ids_by_qid.get(q, {}).get("loc", set())

    gnd_fetch = fetch_many(gnd_ids, fetch_gnd)
    loc_fetch = fetch_many(loc_ids, fetch_loc)

    validation_urls = {r["profile_url"] for r in validation}
    diag = []
    for r in target:
        url = r["profile_url"]
        qid = qid_by_url[url]
        ids = ids_by_qid.get(qid, {"gnd": set(), "loc": set()})
        g_dates, g_ok = source_dates(ids.get("gnd", set()), gnd_fetch)
        l_dates, l_ok = source_dates(ids.get("loc", set()), loc_fetch)
        candidate, basis, cross_conflict = choose_authority_date(g_dates, l_dates)

        purpose = "validation" if url in validation_urls else "missing"
        existing = (r.get("final_exact_dob") or "").strip()
        comparison = ""
        if purpose == "validation" and candidate:
            comparison = "match" if candidate == existing else "conflict"

        known_year = ""
        year_conflict = 0
        a = avail_by_url.get(url, {})
        if as_int(a.get("birth_year_known")) == 1:
            known_year = (a.get("birth_year") or "").strip()
            if candidate and known_year:
                year_conflict = int(candidate[:4] != known_year)

        try:
            age = int(r.get("election_year") or 0) - int(candidate[:4]) if candidate else None
        except Exception:
            age = None
        age_ok = int(age is not None and 25 <= age <= 100) if candidate else ""

        blocked_status = r.get("dob_status", "") in {
            "manual_review_unresolved_conflict",
            "wikidata_exact_conflict_review",
            "wikidata_implausible_election_age_review",
        }
        candidate_for_review = int(
            purpose == "missing"
            and bool(candidate)
            and cross_conflict == 0
            and year_conflict == 0
            and age_ok == 1
            and not blocked_status
        )

        diag.append({
            "profile_url": url,
            "name": r.get("name", ""),
            "purpose": purpose,
            "election_year": r.get("election_year", ""),
            "deceased": r.get("deceased", ""),
            "primary_section": r.get("primary_section", ""),
            "qid": qid,
            "identity_basis": basis_by_url[url],
            "gnd_ids": "|".join(sorted(ids.get("gnd", set()))),
            "loc_ids": "|".join(sorted(ids.get("loc", set()))),
            "gnd_fetch_success_ids": g_ok,
            "loc_fetch_success_ids": l_ok,
            "gnd_exact_birth_dates": "|".join(g_dates),
            "loc_exact_birth_dates": "|".join(l_dates),
            "authority_candidate_dob": candidate,
            "authority_candidate_basis": basis,
            "gnd_loc_exact_conflict": cross_conflict,
            "existing_final_exact_dob": existing,
            "validation_comparison": comparison,
            "known_birth_year": known_year,
            "authority_vs_known_year_conflict": year_conflict,
            "age_at_election": age if age is not None else "",
            "age_plausible": age_ok,
            "input_dob_status": r.get("dob_status", ""),
            "candidate_for_review": candidate_for_review,
        })

    write_csv(OUT_DIAG, diag)

    candidates = [r for r in diag if r["candidate_for_review"] == 1]
    write_csv(OUT_CAND, candidates, list(diag[0].keys()) if diag else [])

    val_conflicts = [
        r for r in diag
        if r["purpose"] == "validation" and r["validation_comparison"] == "conflict"
    ]
    write_csv(OUT_CONFLICT, val_conflicts, list(diag[0].keys()) if diag else [])

    val = [r for r in diag if r["purpose"] == "validation"]
    comparable = [r for r in val if r["validation_comparison"] in {"match", "conflict"}]
    missing_diag = [r for r in diag if r["purpose"] == "missing"]

    summary = {
        "dataset": "NAS science-core authority-control DOB diagnostic v1",
        "input": INPUT.name,
        "science_core_rows": len(rows),
        "remaining_without_exact_dob": sum(not present(r.get("final_exact_dob")) for r in rows),
        "rows_with_reliable_qid": len(qid_by_url),
        "missing_rows_with_reliable_qid": len(missing),
        "qids_queried_for_authority_ids": len(qids),
        "qids_with_gnd_id": sum(bool(v.get("gnd")) for v in ids_by_qid.values()),
        "qids_with_loc_id": sum(bool(v.get("loc")) for v in ids_by_qid.values()),
        "validation_eligible_with_authority_id": len(validation_eligible),
        "validation_sample_n": len(validation),
        "unique_gnd_ids_fetched": len(gnd_ids),
        "gnd_fetch_successes": sum(int(x.get("ok", 0)) for x in gnd_fetch.values()),
        "unique_loc_ids_fetched": len(loc_ids),
        "loc_fetch_successes": sum(int(x.get("ok", 0)) for x in loc_fetch.values()),
        "validation_comparable_rows": len(comparable),
        "validation_exact_matches": sum(r["validation_comparison"] == "match" for r in comparable),
        "validation_exact_conflicts": sum(r["validation_comparison"] == "conflict" for r in comparable),
        "validation_match_rate": (
            round(sum(r["validation_comparison"] == "match" for r in comparable) / len(comparable), 6)
            if comparable else None
        ),
        "missing_rows_with_any_authority_exact_candidate": sum(bool(r["authority_candidate_dob"]) for r in missing_diag),
        "missing_rows_gnd_loc_conflict": sum(int(r["gnd_loc_exact_conflict"]) for r in missing_diag),
        "missing_rows_authority_vs_known_year_conflict": sum(int(r["authority_vs_known_year_conflict"]) for r in missing_diag),
        "missing_rows_candidate_for_review": len(candidates),
        "bazi_variables_computed": 0,
        "decision_note": (
            "Diagnostic only. Identity linkage is QID -> Wikidata P227/P244 -> authority record; "
            "no name matching is used. Exact dates are not written to final_exact_dob in this stage. "
            "Candidates are filtered by source agreement, known-year agreement, election age, and "
            "pre-existing conflict status, then require review of validation concordance."
        ),
        "sources": {
            "GND": "lobid GND JSON-LD API via Wikidata P227",
            "LOC": "Library of Congress Linked Data Service JSON via Wikidata P244",
        },
    }
    OUT_SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
