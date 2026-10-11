#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

WIKIDATA_API = "https://www.wikidata.org/w/api.php"
QLEVER = "https://qlever.dev/api/wikidata"
UA = "bazi-public-figure-study/1.0 (DOB calendar-model audit; no BaZi computation)"
BATCH_SIZE = int(os.environ.get("DOB_AUDIT_BATCH_SIZE", "40"))
SLEEP_SECONDS = float(os.environ.get("DOB_AUDIT_SLEEP", "0.6"))
WIKIDATA_MAXLAG = int(os.environ.get("WIKIDATA_MAXLAG", "15"))
JULIAN_CALENDAR_QID = "Q1985786"
GREGORIAN_CALENDAR_QID = "Q1985727"
SWEDISH_CALENDAR_QID = "Q1130275"

try:
    import certifi
except ImportError:
    certifi = None


def read_csv(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows, fields=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    if fields is None:
        fields = list(rows[0].keys()) if rows else []
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


def chunks(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i+n]


def valid_qid(v):
    return bool(re.fullmatch(r"Q\d+", str(v or "").strip()))


def split_qids(v):
    return sorted(set(re.findall(r"Q\d+", str(v or ""))))


def present(v):
    return str(v or "").strip() not in {"", "nan", "None", "null"}


def first_present(row, names):
    for name in names:
        if name in row and present(row.get(name)):
            return str(row.get(name)).strip()
    return ""


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
    raise RuntimeError(
        "TLS certificate verification failed with every trusted CA source. "
        "Update certifi or fix VPN/proxy HTTPS interception; verification is intentionally not disabled. "
        f"Details: {detail}"
    )


def wikidata_entities(qids, retries=8):
    if not qids:
        return {"entities": {}}
    data = urllib.parse.urlencode({
        "action": "wbgetentities",
        "ids": "|".join(qids),
        "props": "claims",
        "format": "json",
        "formatversion": "2",
        "maxlag": str(WIKIDATA_MAXLAG),
    }).encode()
    last = None
    for attempt in range(retries):
        req = urllib.request.Request(
            WIKIDATA_API,
            data=data,
            method="POST",
            headers={
                "User-Agent": UA,
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        try:
            with urlopen_verified(req, timeout=120) as r:
                obj = json.loads(r.read().decode("utf-8"))
            if isinstance(obj, dict) and obj.get("error"):
                code = str(obj["error"].get("code", ""))
                if code == "maxlag" and attempt + 1 < retries:
                    try:
                        lag = float(obj["error"].get("lag", 0) or 0)
                    except Exception:
                        lag = 0.0
                    delay = max(5.0, min(60.0, lag + 2.0))
                    print(f"Wikidata maxlag exceeded (reported {lag:.1f}s); retry in {delay:.1f}s")
                    time.sleep(delay)
                    continue
                raise RuntimeError(f"Wikidata API error: {obj['error']}")
            return obj
        except urllib.error.HTTPError as e:
            last = e
            if attempt + 1 >= retries or e.code not in {429, 500, 502, 503, 504}:
                raise
            try:
                delay = float(e.headers.get("Retry-After", ""))
            except Exception:
                delay = min(60.0, 2.0 ** attempt + 1.0)
            print(f"Wikidata HTTP {e.code}; retry in {delay:.1f}s")
            time.sleep(delay)
        except urllib.error.URLError as e:
            last = e
            if attempt + 1 >= retries:
                raise
            delay = min(60.0, 2.0 ** attempt + 1.0)
            print(f"Wikidata network error; retry in {delay:.1f}s: {e}")
            time.sleep(delay)
    raise RuntimeError(f"Wikidata API failed after retries: {last}")


def run_sparql(query: str, retries=6):
    body = urllib.parse.urlencode({"query": query, "action": "tsv_export"}).encode("utf-8")
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
            with urlopen_verified(req, timeout=300) as resp:
                raw = resp.read()
            break
        except (urllib.error.HTTPError, urllib.error.URLError) as e:
            last = e
            retryable = not isinstance(e, urllib.error.HTTPError) or e.code in {429, 500, 502, 503, 504}
            if not retryable or attempt + 1 >= retries:
                raise
            delay = min(45.0, 2.0 ** attempt + 1.0)
            print(f"QLever transient error; retry in {delay:.1f}s: {e}")
            time.sleep(delay)
    else:
        raise RuntimeError(f"QLever request failed after {retries} attempts: {last}")

    rows = list(csv.reader(raw.decode("utf-8-sig").splitlines(), delimiter="\t"))
    if not rows:
        return []
    headers = [x.lstrip("?").strip() for x in rows[0]]
    out = []
    for row in rows[1:]:
        if not row:
            continue
        row = row + [""] * (len(headers) - len(row))
        item = {}
        for i, h in enumerate(headers):
            s = (row[i] or "").strip()
            if s.startswith("<") and s.endswith(">"):
                s = s[1:-1]
            elif len(s) >= 2 and s.startswith('"'):
                end = s.rfind('"')
                if end > 0:
                    s = s[1:end]
            s = re.sub(r"@[A-Za-z][A-Za-z0-9-]*$", "", s)
            item[h] = s
        out.append(item)
    return out


def sparql_literal(s):
    return json.dumps(str(s), ensure_ascii=False)


def map_external_ids(prop: str, ids, chunk_size=250):
    found = defaultdict(set)
    ids = sorted(set(str(x) for x in ids if present(x)))
    for batch_no, batch in enumerate(chunks(ids, chunk_size), start=1):
        vals = " ".join(sparql_literal(x) for x in batch)
        query = f"""
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
SELECT DISTINCT ?id ?person WHERE {{
  VALUES ?id {{ {vals} }}
  ?person wdt:{prop} ?id .
}}
"""
        for row in run_sparql(query):
            qid = str(row.get("person") or "").rsplit("/", 1)[-1]
            ext = str(row.get("id") or "")
            if valid_qid(qid) and ext:
                found[ext].add(qid)
        print(f"{prop} bridge: {batch_no} batch(es), mapped IDs={len(found)}")
        if batch_no * chunk_size < len(ids):
            time.sleep(SLEEP_SECONDS)
    return {k: sorted(v) for k, v in found.items()}


def julian_to_gregorian_date(year, month, day):
    a = (14 - month) // 12
    y = year + 4800 - a
    m = month + 12 * a - 3
    jdn = day + (153 * m + 2) // 5 + 365 * y + y // 4 - 32083

    a2 = jdn + 32044
    b = (4 * a2 + 3) // 146097
    c = a2 - (146097 * b) // 4
    d = (4 * c + 3) // 1461
    e = c - (1461 * d) // 4
    m2 = (5 * e + 2) // 153
    gday = e - (153 * m2 + 2) // 5 + 1
    gmonth = m2 + 3 - 12 * (m2 // 10)
    gyear = 100 * b + d - 4800 + (m2 // 10)
    return dt.date(gyear, gmonth, gday)


def swedish_to_gregorian_date(year, month, day):
    # Sweden's special calendar was one day ahead of the Julian calendar
    # from 1700-03-01 until the exceptional 1712-02-30 restored Julian dating.
    if (year, month, day) == (1712, 2, 30):
        return dt.date(1712, 3, 11)
    d = dt.date(year, month, day)
    if dt.date(1700, 3, 1) <= d <= dt.date(1712, 2, 29):
        return julian_to_gregorian_date(year, month, day) - dt.timedelta(days=1)
    return None


def qualifier_entity_qids(claim):
    out = set()
    for snaks in (((claim or {}).get("qualifiers") or {}).values()):
        for snak in snaks or []:
            value = (((snak or {}).get("datavalue") or {}).get("value"))
            if isinstance(value, dict):
                qid = str(value.get("id") or "")
                if valid_qid(qid):
                    out.add(qid)
    return sorted(out)


def parse_wikidata_time(value, qualifier_qids=None):
    if not isinstance(value, dict):
        return None
    qualifier_qids = sorted(set(qualifier_qids or []))
    raw = str(value.get("time") or "")
    precision = value.get("precision")
    calendar_qid = str(value.get("calendarmodel") or "").rsplit("/", 1)[-1]
    m = re.match(r"^([+-])(\d+)-(\d{2})-(\d{2})T", raw)
    if not m:
        return None
    sign, ys, ms, ds = m.groups()
    if sign == "-":
        return None
    year, month, day = int(ys), int(ms), int(ds)
    raw_date = ""
    normalized = ""
    method = ""
    if precision is not None and int(precision) >= 11:
        if (year, month, day) == (1712, 2, 30) and SWEDISH_CALENDAR_QID in qualifier_qids:
            raw_date = "1712-02-30"
            normalized = swedish_to_gregorian_date(year, month, day).isoformat()
            method = "swedish_calendar_to_gregorian"
        else:
            try:
                d = dt.date(year, month, day)
                raw_date = d.isoformat()
                if SWEDISH_CALENDAR_QID in qualifier_qids:
                    converted = swedish_to_gregorian_date(year, month, day)
                    if converted is not None:
                        normalized = converted.isoformat()
                        method = "swedish_calendar_to_gregorian"
                    else:
                        normalized = ""
                        method = "unsupported_special_calendar_range"
                elif calendar_qid == JULIAN_CALENDAR_QID:
                    normalized = julian_to_gregorian_date(year, month, day).isoformat()
                    method = "julian_to_gregorian"
                else:
                    normalized = raw_date
                    method = "identity_nonjulian"
            except ValueError:
                pass
    return {
        "raw_time": raw,
        "precision": precision,
        "calendar_model_qid": calendar_qid,
        "raw_date": raw_date,
        "normalized_gregorian_date": normalized,
        "normalization_method": method,
        "qualifier_entity_qids": "|".join(qualifier_qids),
        "special_calendar_qids": "|".join(q for q in qualifier_qids if q == SWEDISH_CALENDAR_QID),
    }


def entity_map(obj):
    entities = (obj or {}).get("entities", {})
    if isinstance(entities, list):
        return {str(x.get("id") or ""): x for x in entities if x.get("id")}
    if isinstance(entities, dict):
        return entities
    return {}


def extract_p569_claims(entity):
    out = []
    claims = (((entity or {}).get("claims") or {}).get("P569", []) or [])
    for idx, claim in enumerate(claims):
        value = ((((claim or {}).get("mainsnak") or {}).get("datavalue") or {}).get("value"))
        qq = qualifier_entity_qids(claim)
        parsed = parse_wikidata_time(value, qq)
        if not parsed:
            continue
        parsed["claim_index"] = idx
        parsed["rank"] = str((claim or {}).get("rank") or "")
        out.append(parsed)
    return out


def cache_entity_batches(qids, cache_dir: Path):
    cache_dir.mkdir(parents=True, exist_ok=True)
    qids = sorted(set(qids))
    out = {}
    total = (len(qids) + BATCH_SIZE - 1) // BATCH_SIZE
    for i, batch in enumerate(chunks(qids, BATCH_SIZE)):
        cp = cache_dir / f"entities_{i:04d}.json"
        signature = list(batch)
        refresh = True
        if cp.exists():
            obj = json.loads(cp.read_text(encoding="utf-8"))
            if obj.get("qids") == signature:
                api = obj.get("api_response", {})
                refresh = False
                print(f"entity batch {i+1}/{total}: cache hit ({len(batch)} QIDs)")
            else:
                print(f"entity batch {i+1}/{total}: stale cache signature; refreshing")
        if refresh:
            api = wikidata_entities(batch)
            cp.write_text(json.dumps({"qids": signature, "api_response": api}, ensure_ascii=False), encoding="utf-8")
            print(f"entity batch {i+1}/{total}: fetched {len(batch)} QIDs")
            if i + 1 < total:
                time.sleep(SLEEP_SECONDS)
        out.update(entity_map(api))
    return out


def record(dataset, key, name, stored_dob, source_path, qids=None, bridge_property="", bridge_value="", note=""):
    return {
        "dataset": dataset,
        "record_key": str(key or ""),
        "display_name": str(name or ""),
        "stored_dob": str(stored_dob or "").strip(),
        "source_path": str(source_path),
        "qids": sorted(set(qids or [])),
        "bridge_property": bridge_property,
        "bridge_value": str(bridge_value or ""),
        "input_note": note,
    }


def load_leopoldina(limit=0):
    path = Path("data/leopoldina_dob_local_v1/candidate_unique_day_p569_v1.csv")
    if not path.exists():
        return [], {"status": "not_found", "path": str(path)}
    rows = read_csv(path)
    if limit:
        rows = rows[:limit]
    out = [record(
        "leopoldina_candidate",
        r.get("member_slug"), r.get("display_name"), r.get("candidate_exact_dob"), path,
        split_qids(r.get("wikidata_qids")), note="candidate-stage DOB; audit only, not final acceptance"
    ) for r in rows if present(r.get("candidate_exact_dob"))]
    return out, {"status": "loaded", "path": str(path), "sha256": sha256(path), "rows": len(out)}


def load_table_tennis(limit=0):
    path = Path("table_tennis_players_1985_2008.csv")
    if not path.exists():
        return [], {"status": "not_found", "path": str(path)}
    rows = read_csv(path)
    if limit:
        rows = rows[:limit]
    out = [record("table_tennis_1985_2008", r.get("qid"), r.get("name"), r.get("dob"), path, split_qids(r.get("qid")))
           for r in rows if present(r.get("dob"))]
    return out, {"status": "loaded", "path": str(path), "sha256": sha256(path), "rows": len(out)}


def load_chess(limit=0):
    paths = [
        Path("chess_north_v3/primary_north_top_1994_M.csv"),
        Path("chess_north_v3/primary_north_top_1994_F.csv"),
        Path("chess_north_v3/primary_north_top_2013_M.csv"),
        Path("chess_north_v3/primary_north_top_2013_F.csv"),
    ]
    out = []
    meta = {"status": "loaded", "files": []}
    for path in paths:
        if not path.exists():
            meta["files"].append({"path": str(path), "status": "not_found"})
            continue
        rows = read_csv(path)
        if limit:
            rows = rows[:limit]
        for r in rows:
            dob = first_present(r, ["exact_dob_frozen", "exact_dob_north_v2", "birth_date"])
            if not dob:
                continue
            key = f"{r.get('snapshot','')}|{r.get('analysis_sex', r.get('sex',''))}|{r.get('fide_id','')}"
            out.append(record("chess_1994_2013_north", key, r.get("name"), dob, path, split_qids(r.get("wikidata_person_qids"))))
        meta["files"].append({"path": str(path), "status": "loaded", "sha256": sha256(path), "rows": len(rows)})
    meta["rows"] = len(out)
    if not out:
        meta["status"] = "not_found_or_empty"
    return out, meta


def find_nas_crosswalk():
    candidates = [
        Path("data/nas_science_core_dob_crosswalk/nas_science_core_dob_crosswalk_v17.csv"),
        Path("data/nas_science_core_dob_crosswalk/nas_science_core_dob_crosswalk_v16.csv"),
        Path("data/nas_science_core_dob_crosswalk_v17.csv"),
        Path("data/nas_science_core_dob_crosswalk_v16.csv"),
    ]
    for p in candidates:
        if p.exists():
            return p
    hits = sorted(Path("data").rglob("nas_science_core_dob_crosswalk_v*.csv")) if Path("data").exists() else []
    if hits:
        hits.sort(key=lambda p: ("v17" in p.name, "v16" in p.name, p.name), reverse=True)
        return hits[0]
    return None


def nas_id_from_url(url):
    m = re.search(r"/members/(\d+)(?:\.html)?", str(url or ""))
    return m.group(1) if m else ""


def load_nas(limit=0):
    path = find_nas_crosswalk()
    if path is None:
        return [], {"status": "not_found", "expected": "local frozen NAS v17/v16 crosswalk CSV"}
    rows = read_csv(path)
    out = []
    pending_ids = []
    staged = []
    for r in rows:
        dob = first_present(r, ["final_exact_dob", "exact_dob", "dob_exact_iso"])
        if not dob:
            continue
        qids = split_qids(first_present(r, ["wikidata_qid", "wikidata_qids", "qid"]))
        bridge = ""
        if not qids:
            bridge = nas_id_from_url(first_present(r, ["profile_url", "source_url"]))
            if bridge:
                pending_ids.append(bridge)
        staged.append((r, dob, qids, bridge))
    if limit:
        staged = staged[:limit]
        pending_ids = [b for _, _, q, b in staged if not q and b]
    bridge_map = map_external_ids("P5380", pending_ids) if pending_ids else {}
    for r, dob, qids, bridge in staged:
        if not qids and bridge:
            qids = bridge_map.get(bridge, [])
        key = first_present(r, ["profile_url", "name", "display_name", "cohort_key"])
        name = first_present(r, ["name", "display_name"])
        out.append(record("nas_science_core", key, name, dob, path, qids, "P5380" if bridge else "", bridge,
                          note="audit does not alter NAS v17 frozen DOB"))
    return out, {
        "status": "loaded",
        "path": str(path),
        "sha256": sha256(path),
        "rows": len(out),
        "warning": "Input is v16 rather than final v17" if "v16" in path.name and "v17" not in path.name else "",
    }


def find_dob_col(row):
    return first_present(row, ["exact_dob", "dob_exact_iso", "final_exact_dob", "candidate_exact_dob", "birth_date", "dob"])


def load_royal_society(limit=0):
    roster_path = Path("data/royal_society_roster_freeze_v1/royal_society_fellows_roster_freeze_v1.csv")
    current_path = Path("data/royal_society_dob_freeze_v1/royal_society_current_exact_dob_final_v1.csv")
    past_path = Path("data/royal_society_past_dob_closeout_v1/accepted_exact_dob_final_v1.csv")
    missing = [str(p) for p in (roster_path, current_path, past_path) if not p.exists()]
    if missing:
        return [], {"status": "not_found", "missing": missing}
    roster = read_csv(roster_path)
    roster_by_key = {r.get("cohort_key", ""): r for r in roster}
    staged = []
    for path, prop in ((current_path, "P2070"), (past_path, "P8612")):
        for r in read_csv(path):
            dob = find_dob_col(r)
            if not dob:
                continue
            key = first_present(r, ["cohort_key", "record_id"])
            rr = roster_by_key.get(key, {})
            source_id = first_present(rr, ["source_id"]) or first_present(r, ["record_id"])
            name = first_present(r, ["display_name", "name"]) or first_present(rr, ["display_name"])
            staged.append((path, prop, key, name, dob, source_id))
    if limit:
        staged = staged[:limit]
    by_prop = defaultdict(list)
    for _, prop, _, _, _, source_id in staged:
        if source_id:
            by_prop[prop].append(source_id)
    bridges = {prop: map_external_ids(prop, ids) for prop, ids in by_prop.items()}
    out = []
    bridge_rows = []
    for path, prop, key, name, dob, source_id in staged:
        qids = bridges.get(prop, {}).get(source_id, [])
        out.append(record("royal_society", key, name, dob, path, qids, prop, source_id,
                          note="exact Royal Society identifier bridge; audit only"))
        bridge_rows.append({"cohort_key": key, "display_name": name, "bridge_property": prop, "bridge_value": source_id,
                            "wikidata_qids": "|".join(qids), "qid_count": len(qids)})
    return out, {
        "status": "loaded", "rows": len(out),
        "roster_sha256": sha256(roster_path), "current_sha256": sha256(current_path), "past_sha256": sha256(past_path),
        "bridge_rows": bridge_rows,
    }


def discover_nobel():
    hits = []
    for p in Path(".").rglob("*"):
        if p.is_file() and "nobel" in p.name.lower() and p.suffix.lower() in {".csv", ".json"}:
            if "dob_calendar_model_audit" not in str(p):
                hits.append(str(p))
    return sorted(hits)


def load_nobel(limit=0):
    hits = discover_nobel()
    return [], {"status": "not_connected", "candidate_local_files": hits,
                "reason": "Frozen Nobel master is not tracked in this repository; no file is guessed automatically."}


def load_datasets(names, limit=0):
    loaders = {
        "leopoldina": load_leopoldina,
        "royal_society": load_royal_society,
        "nas": load_nas,
        "chess": load_chess,
        "table_tennis": load_table_tennis,
        "nobel": load_nobel,
    }
    records = []
    meta = {}
    for name in names:
        loader = loaders[name]
        print(f"Loading dataset: {name}")
        rr, mm = loader(limit=limit)
        records.extend(rr)
        meta[name] = mm
        print(f"  {name}: {len(rr)} audit row(s), status={mm.get('status')}")
    return records, meta


def audit_record(rec, entities):
    qids = rec["qids"]
    qid_status = "none" if not qids else ("single" if len(qids) == 1 else "multiple")
    claim_rows = []
    for qid in qids:
        for claim in extract_p569_claims(entities.get(qid, {})):
            x = dict(claim)
            x["qid"] = qid
            claim_rows.append(x)

    exact = [x for x in claim_rows if x.get("precision") is not None and int(x["precision"]) >= 11 and x.get("raw_date")]
    raw_dates = sorted(set(x["raw_date"] for x in exact if x.get("raw_date")))
    norm_dates = sorted(set(x["normalized_gregorian_date"] for x in exact if x.get("normalized_gregorian_date")))
    models = sorted(set(x["calendar_model_qid"] for x in exact if x.get("calendar_model_qid")))
    julian = [x for x in exact if x.get("calendar_model_qid") == JULIAN_CALENDAR_QID]
    special = [x for x in exact if x.get("special_calendar_qids")]
    stored = rec["stored_dob"]

    if not qids:
        status = "no_qid_bridge"
        review = 1
    elif len(qids) > 1:
        matching_qids = sorted(set(x["qid"] for x in exact if x.get("normalized_gregorian_date") == stored))
        status = "multiple_qids_one_or_more_match" if matching_qids else "multiple_qids_no_match"
        review = 1
    elif not exact:
        status = "qid_no_exact_day_p569"
        review = 1
    elif stored in norm_dates:
        match_claims = [x for x in exact if x.get("normalized_gregorian_date") == stored]
        if len(norm_dates) > 1:
            status = "aligned_but_multiple_exact_p569_dates"
            review = 1
        elif any(x.get("special_calendar_qids") and x.get("raw_date") != stored for x in match_claims):
            status = "aligned_after_special_calendar_normalization"
            review = 1
        elif any(x.get("calendar_model_qid") == JULIAN_CALENDAR_QID and not x.get("special_calendar_qids") and x.get("raw_date") != stored for x in match_claims):
            status = "aligned_after_julian_normalization"
            review = 0
        elif any(x.get("calendar_model_qid") == GREGORIAN_CALENDAR_QID for x in match_claims):
            status = "aligned_gregorian"
            review = 0
        else:
            status = "aligned_other_or_unspecified_calendar"
            review = 1
    elif stored in [x.get("raw_date") for x in special]:
        status = "stored_matches_special_calendar_claim_requires_source_adjudication"
        review = 1
    elif stored in [x.get("raw_date") for x in julian if not x.get("special_calendar_qids")]:
        status = "stored_matches_raw_julian_claim_requires_source_adjudication"
        review = 1
    else:
        status = "stored_date_not_in_current_p569"
        review = 1

    row = {
        "dataset": rec["dataset"],
        "record_key": rec["record_key"],
        "display_name": rec["display_name"],
        "stored_dob": stored,
        "source_path": rec["source_path"],
        "wikidata_qids": "|".join(qids),
        "qid_count": len(qids),
        "qid_status": qid_status,
        "bridge_property": rec["bridge_property"],
        "bridge_value": rec["bridge_value"],
        "p569_claim_count": len(claim_rows),
        "exact_day_p569_claim_count": len(exact),
        "raw_exact_dates": "|".join(raw_dates),
        "normalized_gregorian_dates": "|".join(norm_dates),
        "calendar_model_qids": "|".join(models),
        "has_julian_exact_claim": int(bool(julian)),
        "has_special_calendar_claim": int(bool(special)),
        "special_calendar_qids": "|".join(sorted(set(q for x in special for q in str(x.get("special_calendar_qids") or "").split("|") if q))),
        "normalization_methods": "|".join(sorted(set(x.get("normalization_method") for x in exact if x.get("normalization_method")))),
        "julian_raw_dates": "|".join(sorted(set(x["raw_date"] for x in julian if x.get("raw_date")))),
        "julian_normalized_gregorian_dates": "|".join(sorted(set(x["normalized_gregorian_date"] for x in julian if x.get("normalized_gregorian_date")))),
        "audit_status": status,
        "needs_review": review,
        "input_note": rec["input_note"],
        "final_exact_dob_written": "",
        "bazi_variables_computed": 0,
    }
    exploded = []
    for x in claim_rows:
        exploded.append({
            "dataset": rec["dataset"], "record_key": rec["record_key"], "display_name": rec["display_name"],
            "stored_dob": stored, "qid": x["qid"], "claim_index": x["claim_index"], "rank": x["rank"],
            "precision": x["precision"], "calendar_model_qid": x["calendar_model_qid"],
            "qualifier_entity_qids": x.get("qualifier_entity_qids", ""), "special_calendar_qids": x.get("special_calendar_qids", ""),
            "normalization_method": x.get("normalization_method", ""), "raw_time": x["raw_time"],
            "raw_date": x["raw_date"], "normalized_gregorian_date": x["normalized_gregorian_date"],
            "bazi_variables_computed": 0,
        })
    return row, exploded


def dataset_summary(rows):
    out = []
    by = defaultdict(list)
    for r in rows:
        by[r["dataset"]].append(r)
    for ds, rr in sorted(by.items()):
        statuses = Counter(r["audit_status"] for r in rr)
        out.append({
            "dataset": ds,
            "audit_rows": len(rr),
            "single_qid_rows": sum(r["qid_status"] == "single" for r in rr),
            "no_qid_rows": sum(r["qid_status"] == "none" for r in rr),
            "multiple_qid_rows": sum(r["qid_status"] == "multiple" for r in rr),
            "rows_with_exact_day_p569": sum(int(r["exact_day_p569_claim_count"]) > 0 for r in rr),
            "rows_with_julian_exact_claim": sum(int(r["has_julian_exact_claim"]) for r in rr),
            "aligned_after_julian_normalization": statuses.get("aligned_after_julian_normalization", 0),
            "aligned_after_special_calendar_normalization": statuses.get("aligned_after_special_calendar_normalization", 0),
            "stored_matches_raw_julian_claim_requires_source_adjudication": statuses.get("stored_matches_raw_julian_claim_requires_source_adjudication", 0),
            "stored_matches_special_calendar_claim_requires_source_adjudication": statuses.get("stored_matches_special_calendar_claim_requires_source_adjudication", 0),
            "stored_date_not_in_current_p569": statuses.get("stored_date_not_in_current_p569", 0),
            "review_rows": sum(int(r["needs_review"]) for r in rr),
            "status_counts_json": json.dumps(dict(sorted(statuses.items())), ensure_ascii=False, sort_keys=True),
            "bazi_variables_computed": 0,
        })
    return out


def self_test():
    assert julian_to_gregorian_date(1875, 12, 29).isoformat() == "1876-01-10"
    assert julian_to_gregorian_date(1906, 5, 30).isoformat() == "1906-06-12"
    val = {"time": "+1875-12-29T00:00:00Z", "precision": 11,
           "calendarmodel": "http://www.wikidata.org/entity/Q1985786"}
    got = parse_wikidata_time(val)
    assert got["normalized_gregorian_date"] == "1876-01-10"
    swe = {"time": "+1701-11-27T00:00:00Z", "precision": 11,
           "calendarmodel": "http://www.wikidata.org/entity/Q1985786"}
    got_swe = parse_wikidata_time(swe, [SWEDISH_CALENDAR_QID])
    assert got_swe["normalized_gregorian_date"] == "1701-12-07"
    assert got_swe["normalization_method"] == "swedish_calendar_to_gregorian"
    print("DOB calendar-model self-test OK")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--datasets", default="nobel,nas,royal_society,leopoldina,chess,table_tennis",
                    help="Comma-separated: nobel,nas,royal_society,leopoldina,chess,table_tennis")
    ap.add_argument("--out", default="data/dob_calendar_model_audit_v1_1")
    ap.add_argument("--limit", type=int, default=0, help="Optional per-loader smoke limit; 0 = full")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        self_test()
        return

    allowed = {"nobel", "nas", "royal_society", "leopoldina", "chess", "table_tennis"}
    names = [x.strip() for x in args.datasets.split(",") if x.strip()]
    bad = sorted(set(names) - allowed)
    if bad:
        raise RuntimeError(f"Unknown datasets: {bad}")

    out_dir = Path(args.out)
    cache_dir = out_dir / "cache"
    records, input_meta = load_datasets(names, limit=args.limit)
    qids = sorted(set(q for r in records for q in r["qids"] if valid_qid(q)))
    print(f"Audit records={len(records)}; unique QIDs={len(qids)}")
    entities = cache_entity_batches(qids, cache_dir) if qids else {}

    audited = []
    exploded = []
    for i, rec in enumerate(records, start=1):
        row, claims = audit_record(rec, entities)
        audited.append(row)
        exploded.extend(claims)
        if i % 500 == 0 or i == len(records):
            print(f"Audited {i}/{len(records)} rows")

    row_fields = [
        "dataset", "record_key", "display_name", "stored_dob", "source_path", "wikidata_qids", "qid_count", "qid_status",
        "bridge_property", "bridge_value", "p569_claim_count", "exact_day_p569_claim_count", "raw_exact_dates",
        "normalized_gregorian_dates", "calendar_model_qids", "has_julian_exact_claim", "has_special_calendar_claim",
        "special_calendar_qids", "normalization_methods", "julian_raw_dates", "julian_normalized_gregorian_dates",
        "audit_status", "needs_review", "input_note", "final_exact_dob_written",
        "bazi_variables_computed",
    ]
    write_csv(out_dir / "calendar_model_audit_rows_v1.csv", audited, row_fields)
    claim_fields = [
        "dataset", "record_key", "display_name", "stored_dob", "qid", "claim_index", "rank", "precision",
        "calendar_model_qid", "qualifier_entity_qids", "special_calendar_qids", "normalization_method",
        "raw_time", "raw_date", "normalized_gregorian_date", "bazi_variables_computed",
    ]
    write_csv(out_dir / "p569_claims_exploded_v1.csv", exploded, claim_fields)
    write_csv(out_dir / "julian_claim_review_v1_1.csv", [r for r in audited if int(r["has_julian_exact_claim"]) or int(r["has_special_calendar_claim"])], row_fields)
    write_csv(out_dir / "date_or_identity_review_v1.csv", [r for r in audited if int(r["needs_review"])], row_fields)

    ds_summary = dataset_summary(audited)
    summary_fields = list(ds_summary[0].keys()) if ds_summary else ["dataset"]
    write_csv(out_dir / "dataset_summary_v1.csv", ds_summary, summary_fields)

    rs_bridge = input_meta.get("royal_society", {}).pop("bridge_rows", None)
    if rs_bridge is not None:
        write_csv(out_dir / "royal_society_exact_id_bridge_v1.csv", rs_bridge,
                  ["cohort_key", "display_name", "bridge_property", "bridge_value", "wikidata_qids", "qid_count"])

    summary = {
        "dataset": "Cross-study DOB calendar-model audit v1.1",
        "audit_policy": (
            "Audit only. Wikidata identities use exact QIDs or exact external-ID bridges; no fuzzy matching. "
            "Wikidata JSON P569 calendarmodel and entity-valued claim qualifiers are preserved. Ordinary Julian "
            "Q1985786 day-level dates are converted to proleptic Gregorian absolute dates for comparison; the "
            "Swedish-calendar Q1130275 sourcing circumstance uses its special 1700-1712 rule. A stored date matching "
            "a raw historical-calendar claim is a source-adjudication trigger, not proof of error. No frozen DOB is "
            "automatically changed; any correction requires a separately versioned DOB amendment."
        ),
        "date_coordinate": "proleptic Gregorian absolute date",
        "julian_calendar_qid": JULIAN_CALENDAR_QID,
        "gregorian_calendar_qid": GREGORIAN_CALENDAR_QID,
        "swedish_calendar_qid": SWEDISH_CALENDAR_QID,
        "requested_datasets": names,
        "input_metadata": input_meta,
        "audit_rows": len(audited),
        "unique_qids_fetched": len(qids),
        "entity_qids_returned": len(entities),
        "rows_with_julian_exact_claim": sum(int(r["has_julian_exact_claim"]) for r in audited),
        "stored_matches_raw_julian_claim_requires_source_adjudication": sum(r["audit_status"] == "stored_matches_raw_julian_claim_requires_source_adjudication" for r in audited),
        "stored_matches_special_calendar_claim_requires_source_adjudication": sum(r["audit_status"] == "stored_matches_special_calendar_claim_requires_source_adjudication" for r in audited),
        "rows_requiring_review": sum(int(r["needs_review"]) for r in audited),
        "dataset_summary": ds_summary,
        "automatic_dob_changes": 0,
        "final_exact_dob_written": 0,
        "bazi_variables_computed": 0,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
