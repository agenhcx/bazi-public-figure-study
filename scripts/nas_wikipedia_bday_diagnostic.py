#!/usr/bin/env python3
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import html
import json
import re
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

INPUT = Path("data/nas_science_core_dob_crosswalk/nas_science_core_dob_crosswalk_v6.csv")
OUT = Path("data/nas_science_core_dob_crosswalk")
WIKIDATA_API = "https://www.wikidata.org/w/api.php"
WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"
USER_AGENT = "bazi-public-figure-study/1.0 (NAS DOB source validation; no BaZi computation)"
VALIDATION_SAMPLE_N = 300
MAX_WORKERS = 6

def read_csv(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

def write_csv(path: Path, rows, fields):
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

def present(v) -> bool:
    return str(v or "").strip() not in ("", "nan", "None")

def as_int(v, default=0):
    try:
        return int(float(str(v)))
    except Exception:
        return default

def http_json(url: str, retries: int = 4):
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            last = e
            if attempt + 1 < retries:
                time.sleep(1.0 * (2 ** attempt))
    raise RuntimeError(f"HTTP failed after {retries} attempts: {url}\n{last}")

def reliable_qid(row):
    if present(row.get("wikidata_qid")):
        return row["wikidata_qid"].strip(), row.get("wikidata_match_method", "") or "wikidata_crosswalk"
    if present(row.get("global_candidate_qid")) and as_int(row.get("global_affiliation_match")) == 1:
        return row["global_candidate_qid"].strip(), "global_exact_name_plus_affiliation"
    return "", ""

def qid_to_enwiki(qids):
    out = {}
    qids = sorted(set(q for q in qids if q))
    for i in range(0, len(qids), 50):
        batch = qids[i:i+50]
        params = {
            "action": "wbgetentities",
            "ids": "|".join(batch),
            "props": "sitelinks",
            "sitefilter": "enwiki",
            "format": "json",
        }
        url = WIKIDATA_API + "?" + urllib.parse.urlencode(params)
        obj = http_json(url)
        for qid, ent in obj.get("entities", {}).items():
            title = ent.get("sitelinks", {}).get("enwiki", {}).get("title", "")
            if title:
                out[qid] = title
    return out

BDAY_RE = re.compile(
    r'<span\b[^>]*class=["\'][^"\']*\bbday\b[^"\']*["\'][^>]*>(.*?)</span>',
    re.I | re.S,
)
TAG_RE = re.compile(r"<[^>]+>")

def extract_bdays(page_html: str):
    vals = set()
    for raw in BDAY_RE.findall(page_html or ""):
        txt = TAG_RE.sub("", raw)
        txt = html.unescape(txt).strip()
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", txt):
            try:
                dt.date.fromisoformat(txt)
                vals.add(txt)
            except ValueError:
                pass
    return sorted(vals)

def fetch_page_bday(title: str):
    params = {
        "action": "parse",
        "page": title,
        "prop": "text",
        "format": "json",
        "formatversion": "2",
        "redirects": "1",
    }
    url = WIKIPEDIA_API + "?" + urllib.parse.urlencode(params)
    try:
        obj = http_json(url)
        if "error" in obj:
            return {"title": title, "ok": 0, "error": json.dumps(obj["error"], ensure_ascii=False), "bdays": []}
        page_html = obj.get("parse", {}).get("text", "")
        return {"title": title, "ok": 1, "error": "", "bdays": extract_bdays(page_html)}
    except Exception as e:
        return {"title": title, "ok": 0, "error": str(e), "bdays": []}

def election_age(election_year, dob):
    try:
        return int(election_year) - dt.date.fromisoformat(dob).year
    except Exception:
        return None

def validation_hash(row):
    return hashlib.sha256(row["profile_url"].encode("utf-8")).hexdigest()

def main():
    if not INPUT.exists():
        raise RuntimeError(f"Missing input: {INPUT}")
    rows = read_csv(INPUT)
    if len(rows) != 3051:
        raise RuntimeError(f"Expected 3051 science-core rows, got {len(rows)}")

    missing = [r for r in rows if not present(r.get("final_exact_dob"))]
    exact = [r for r in rows if present(r.get("final_exact_dob"))]

    missing_rel = []
    for r in missing:
        qid, basis = reliable_qid(r)
        if qid:
            missing_rel.append((r, qid, basis))

    validation_eligible = []
    for r in exact:
        qid, basis = reliable_qid(r)
        if qid:
            validation_eligible.append((r, qid, basis))
    validation_eligible.sort(key=lambda x: validation_hash(x[0]))
    validation_sample = validation_eligible[:VALIDATION_SAMPLE_N]

    target_qids = sorted({q for _, q, _ in missing_rel + validation_sample})
    qid_titles = qid_to_enwiki(target_qids)

    unique_titles = sorted(set(qid_titles.values()))
    page_results = {}
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futs = {ex.submit(fetch_page_bday, title): title for title in unique_titles}
        for fut in as_completed(futs):
            title = futs[fut]
            page_results[title] = fut.result()

    result_rows = []

    def add_result(row, qid, basis, purpose):
        title = qid_titles.get(qid, "")
        pr = page_results.get(title, {"ok": 0, "error": "no_enwiki_sitelink", "bdays": []}) if title else {"ok":0,"error":"no_enwiki_sitelink","bdays":[]}
        bdays = pr.get("bdays", [])
        existing = row.get("final_exact_dob", "").strip()
        unique_bday = bdays[0] if len(bdays) == 1 else ""
        age = election_age(row.get("election_year", ""), unique_bday) if unique_bday else None
        plausible = int(age is not None and 25 <= age <= 100)
        comparison = ""
        if purpose == "validation" and existing and unique_bday:
            comparison = "match" if existing == unique_bday else "conflict"
        candidate_ok = int(
            purpose == "missing"
            and len(bdays) == 1
            and plausible == 1
        )
        result_rows.append({
            "profile_url": row.get("profile_url", ""),
            "name": row.get("name", ""),
            "election_year": row.get("election_year", ""),
            "primary_section": row.get("primary_section", ""),
            "affiliation": row.get("affiliation", ""),
            "purpose": purpose,
            "qid": qid,
            "identity_basis": basis,
            "enwiki_title": title,
            "page_fetch_ok": pr.get("ok", 0),
            "page_error": pr.get("error", ""),
            "wikipedia_bday_values": "|".join(bdays),
            "wikipedia_bday_count": len(bdays),
            "existing_final_exact_dob": existing,
            "validation_comparison": comparison,
            "wikipedia_age_at_election": age if age is not None else "",
            "wikipedia_age_plausible": plausible,
            "candidate_for_supplement": candidate_ok,
        })

    for r, qid, basis in validation_sample:
        add_result(r, qid, basis, "validation")
    for r, qid, basis in missing_rel:
        add_result(r, qid, basis, "missing")

    out_csv = OUT / "nas_wikipedia_bday_diagnostic.csv"
    fields = list(result_rows[0].keys()) if result_rows else []
    write_csv(out_csv, result_rows, fields)

    val = [r for r in result_rows if r["purpose"] == "validation"]
    val_comp = [r for r in val if r["validation_comparison"] in ("match", "conflict")]
    miss = [r for r in result_rows if r["purpose"] == "missing"]

    summary = {
        "source": "English Wikipedia rendered infobox bday via MediaWiki API",
        "wikidata_api": WIKIDATA_API,
        "wikipedia_api": WIKIPEDIA_API,
        "input_science_core_rows": len(rows),
        "input_final_exact_dob_rows": len(exact),
        "input_missing_exact_dob_rows": len(missing),
        "missing_rows_with_reliable_qid": len(missing_rel),
        "validation_eligible_rows_with_reliable_qid": len(validation_eligible),
        "validation_sample_n": len(validation_sample),
        "unique_qids_queried": len(target_qids),
        "enwiki_sitelinks_found": sum(q in qid_titles for q in target_qids),
        "unique_enwiki_pages_fetched": len(unique_titles),
        "page_fetch_successes": sum(int(x.get("ok", 0)) for x in page_results.values()),
        "validation_rows_with_unique_bday": sum(int(r["wikipedia_bday_count"] == 1) for r in val),
        "validation_comparable_rows": len(val_comp),
        "validation_exact_matches": sum(r["validation_comparison"] == "match" for r in val),
        "validation_exact_conflicts": sum(r["validation_comparison"] == "conflict" for r in val),
        "validation_match_rate": round(
            sum(r["validation_comparison"] == "match" for r in val) / len(val_comp), 6
        ) if val_comp else None,
        "missing_rows_with_unique_bday": sum(int(r["wikipedia_bday_count"] == 1) for r in miss),
        "missing_rows_candidate_for_supplement": sum(int(r["candidate_for_supplement"]) for r in miss),
        "bazi_variables_computed": 0,
        "decision_note": "Diagnostic only. Do not write Wikipedia dates into the master until validation concordance is reviewed.",
    }
    (OUT / "summary_wikipedia_bday_diagnostic.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
