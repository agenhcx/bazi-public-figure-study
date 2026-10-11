#!/usr/bin/env python3
from __future__ import annotations

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

CANDIDATES = Path("data/leopoldina_dob_local_v1/candidate_unique_day_p569_v1.csv")
PROV_DIR = Path("data/leopoldina_p569_reference_local_v1")
PERSON_CACHE = PROV_DIR / "cache"
STATED_COUNTS = PROV_DIR / "stated_in_qid_counts_v1.csv"
OUT = Path("data/leopoldina_p569_source_resolver_local_v1")
CACHE = OUT / "cache"
WIKIDATA_API = "https://www.wikidata.org/w/api.php"
UA = "bazi-public-figure-study/1.0 (Leopoldina local P569 source resolver; no BaZi computation)"
BATCH_SIZE = int(os.environ.get("LEOPOLDINA_SOURCE_BATCH_SIZE", "40"))
SLEEP_SECONDS = float(os.environ.get("LEOPOLDINA_SOURCE_SLEEP", "0.8"))
WIKIDATA_MAXLAG = int(os.environ.get("WIKIDATA_MAXLAG", "15"))

try:
    import certifi
except ImportError:
    certifi = None

# Explicitly retained from the hierarchy-wide source policy: authority/catalog
# records are useful locators but are not independently sufficient final DOB evidence.
KNOWN_LOCATOR_ONLY_SOURCE_QIDS = {
    "Q36578",      # Integrated Authority File (GND)
    "Q19938912",   # BnF authorities
    "Q13550863",   # Czech National Authority Database
    "Q23833686",   # Catalog of the German National Library
    "Q112122720",  # WorldCat Entities
}

# Some source items do not expose P1687 consistently even though their record-ID
# property is unambiguous. Overrides only help reconstruct locator URLs; they do
# not change source-policy status or acceptance.
SOURCE_PROPERTY_OVERRIDES = {
    "Q36578": ["P227"],      # GND ID
    "Q19938912": ["P268"],   # BnF ID
    "Q13550863": ["P691"],   # NL CR AUT ID
    "Q112122720": ["P10832"], # WorldCat Entities ID
}

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

def valid_qid(v):
    return bool(re.fullmatch(r"Q\d+", str(v or "").strip()))

def valid_pid(v):
    return bool(re.fullmatch(r"P\d+", str(v or "").strip()))

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

def wikidata_entities(ids, props="labels|descriptions|claims", retries=8):
    if not ids:
        return {"entities": {}}
    data = urllib.parse.urlencode({
        "action": "wbgetentities",
        "ids": "|".join(ids),
        "props": props,
        "languages": "en|de|fr",
        "languagefallback": "1",
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
                        reported_lag = float(obj["error"].get("lag", 0) or 0)
                    except Exception:
                        reported_lag = 0.0
                    delay = max(5.0, min(60.0, reported_lag + 2.0))
                    print(
                        f"Wikidata maxlag={WIKIDATA_MAXLAG}s exceeded "
                        f"(reported lag={reported_lag:.1f}s); retry in {delay:.1f}s"
                    )
                    time.sleep(delay)
                    continue
                raise RuntimeError(f"Wikidata API error: {obj['error']}")
            return obj
        except urllib.error.HTTPError as e:
            last = e
            if attempt + 1 >= retries or e.code not in {429, 500, 502, 503, 504}:
                raise
            retry_after = e.headers.get("Retry-After", "")
            try:
                delay = float(retry_after)
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

def chunks(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i+n]

def entity_map(obj):
    entities = (obj or {}).get("entities", {})
    if isinstance(entities, list):
        return {str(x.get("id") or ""): x for x in entities if x.get("id")}
    if isinstance(entities, dict):
        return entities
    return {}

def label(entity):
    labels = (entity or {}).get("labels") or {}
    for lang in ("en", "de", "fr"):
        x = labels.get(lang)
        if isinstance(x, dict) and x.get("value"):
            return str(x["value"])
    for x in labels.values():
        if isinstance(x, dict) and x.get("value"):
            return str(x["value"])
    return ""

def description(entity):
    descriptions = (entity or {}).get("descriptions") or {}
    for lang in ("en", "de", "fr"):
        x = descriptions.get(lang)
        if isinstance(x, dict) and x.get("value"):
            return str(x["value"])
    for x in descriptions.values():
        if isinstance(x, dict) and x.get("value"):
            return str(x["value"])
    return ""

def claim_values(entity, prop):
    out = []
    for claim in (((entity or {}).get("claims") or {}).get(prop, []) or []):
        snak = (claim or {}).get("mainsnak") or {}
        dv = snak.get("datavalue")
        if isinstance(dv, dict):
            out.append(dv.get("value"))
    return out

def entity_ids(entity, prop):
    out = []
    for v in claim_values(entity, prop):
        if isinstance(v, dict):
            qid = str(v.get("id") or "").strip()
            if valid_qid(qid) or valid_pid(qid):
                out.append(qid)
    return sorted(set(out))

def string_values(entity, prop):
    out = []
    for v in claim_values(entity, prop):
        if isinstance(v, str) and v.strip():
            out.append(v.strip())
    return sorted(set(out))

def normalize_wikidata_time(value):
    if not isinstance(value, dict):
        return "", None
    raw = str(value.get("time") or "")
    precision = value.get("precision")
    m = re.match(r"^[+-]([12]\d{3})-(\d{2})-(\d{2})T", raw)
    if not m:
        return "", precision
    try:
        d = dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat()
    except ValueError:
        return "", precision
    return d, precision

def ref_values(reference, prop):
    out = []
    for snak in (((reference or {}).get("snaks") or {}).get(prop, []) or []):
        dv = (snak or {}).get("datavalue")
        if isinstance(dv, dict):
            out.append(dv.get("value"))
    return out

def ref_entity_ids(reference, prop):
    out = []
    for v in ref_values(reference, prop):
        if isinstance(v, dict):
            qid = str(v.get("id") or "").strip()
            if valid_qid(qid):
                out.append(qid)
    return sorted(set(out))

def scalar_ref_value(v):
    if isinstance(v, str):
        return v
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, dict):
        if v.get("id"):
            return str(v["id"])
        if v.get("text"):
            return str(v["text"])
        if v.get("time"):
            return str(v["time"])
        if v.get("amount"):
            return str(v["amount"])
    return ""

def load_person_cache():
    if not PERSON_CACHE.exists():
        raise RuntimeError(
            f"Missing {PERSON_CACHE}. Run python scripts/leopoldina_p569_reference_local_v1.py first."
        )
    out = {}
    files = sorted(PERSON_CACHE.glob("batch_*.json"))
    if not files:
        raise RuntimeError(f"No provenance cache batches found in {PERSON_CACHE}")
    for path in files:
        obj = json.loads(path.read_text(encoding="utf-8"))
        api = obj.get("api_response")
        if not isinstance(api, dict):
            # Ignore obsolete pre-wbgetentities cache formats; a rerun of the provenance
            # collector will regenerate these batches without redoing completed valid ones.
            continue
        out.update(entity_map(api))
    if not out:
        raise RuntimeError(
            "No wbgetentities person cache entries found. Re-run "
            "python scripts/leopoldina_p569_reference_local_v1.py to refresh the cache."
        )
    return out, len(files)

def cached_entity_fetch(ids, cache_prefix):
    ids = sorted(set(ids))
    CACHE.mkdir(parents=True, exist_ok=True)
    out = {}
    total = (len(ids) + BATCH_SIZE - 1) // BATCH_SIZE
    for i, batch in enumerate(chunks(ids, BATCH_SIZE)):
        cp = CACHE / f"{cache_prefix}_{i:04d}.json"
        signature = list(batch)
        if cp.exists():
            obj = json.loads(cp.read_text(encoding="utf-8"))
            if obj.get("ids") != signature:
                raise RuntimeError(f"Cache ID mismatch in {cp}; delete that file and rerun.")
            api = obj.get("api_response", {})
            print(f"{cache_prefix} batch {i}: cache hit ({len(batch)} IDs)")
        else:
            api = wikidata_entities(batch)
            cp.write_text(
                json.dumps({"ids": signature, "api_response": api}, ensure_ascii=False),
                encoding="utf-8",
            )
            print(f"{cache_prefix} batch {i}: fetched {len(batch)} IDs")
            if i + 1 < total:
                time.sleep(SLEEP_SECONDS)
        out.update(entity_map(api))
    return out

def formatter_url(template, value):
    if not template or not value or "$1" not in template:
        return ""
    # Keep slashes and common identifier punctuation readable; this is an audit URL,
    # not an assertion that the target page has been content-verified.
    encoded = urllib.parse.quote(str(value), safe="/:;,+@._~-")
    return template.replace("$1", encoded)

def source_hint(qid, lbl, desc):
    text = (lbl + " " + desc).lower()
    if qid in KNOWN_LOCATOR_ONLY_SOURCE_QIDS:
        return "locator_only_known"
    if any(k in text for k in ("authority file", "authority database", "authority record")):
        return "locator_candidate"
    if any(k in text for k in ("encyclop", "biograph", "dictionary", "professorenkatalog", "who's who", "who named it")):
        return "content_source_candidate"
    if any(k in text for k in ("academy", "university", "official website", "archive")):
        return "institutional_or_archival_candidate"
    return "unclassified"

def main():
    if not CANDIDATES.exists():
        raise RuntimeError(f"Missing {CANDIDATES}")
    if not STATED_COUNTS.exists():
        raise RuntimeError(
            f"Missing {STATED_COUNTS}. Run python scripts/leopoldina_p569_reference_local_v1.py first."
        )

    candidates = read_csv(CANDIDATES)
    counts = read_csv(STATED_COUNTS)
    candidate_by_qid = {}
    for r in candidates:
        qid = (r.get("wikidata_qids") or "").strip()
        if valid_qid(qid):
            candidate_by_qid[qid] = r

    source_counts = {}
    source_qids = []
    for r in counts:
        qid = (r.get("stated_in_qid") or "").strip()
        if not valid_qid(qid):
            continue
        source_qids.append(qid)
        try:
            source_counts[qid] = int(r.get("candidate_rows") or 0)
        except Exception:
            source_counts[qid] = 0

    person_entities, cache_file_count = load_person_cache()
    source_entities = cached_entity_fetch(source_qids, "source_entities")

    main_pids = set()
    for qid in source_qids:
        main_pids.update(entity_ids(source_entities.get(qid, {}), "P1687"))
    property_entities = cached_entity_fetch(sorted(main_pids), "property_entities") if main_pids else {}

    source_catalog = []
    source_main_props = {}
    for qid in sorted(source_qids, key=lambda x: (-source_counts.get(x, 0), x)):
        e = source_entities.get(qid, {})
        lbl = label(e)
        desc = description(e)
        mains = sorted(set(entity_ids(e, "P1687") + SOURCE_PROPERTY_OVERRIDES.get(qid, [])))
        source_main_props[qid] = mains
        prop_labels = []
        formatters = []
        for pid in mains:
            pe = property_entities.get(pid, {})
            pl = label(pe)
            if pl:
                prop_labels.append(f"{pid}:{pl}")
            for fmt in string_values(pe, "P1630"):
                formatters.append(f"{pid}:{fmt}")
        source_catalog.append({
            "source_qid": qid,
            "candidate_rows": source_counts.get(qid, 0),
            "label": lbl,
            "description": desc,
            "instance_of_qids": "|".join(entity_ids(e, "P31")),
            "official_websites": "|".join(string_values(e, "P856")),
            "main_property_ids": "|".join(mains),
            "main_property_labels": "|".join(sorted(prop_labels)),
            "formatter_templates": "|".join(sorted(formatters)),
            "source_policy_hint": source_hint(qid, lbl, desc),
            "automatic_acceptance": "no",
        })

    OUT.mkdir(parents=True, exist_ok=True)
    source_fields = list(source_catalog[0].keys()) if source_catalog else [
        "source_qid","candidate_rows","label","description","instance_of_qids",
        "official_websites","main_property_ids","main_property_labels",
        "formatter_templates","source_policy_hint","automatic_acceptance",
    ]
    write_csv(OUT / "stated_in_source_catalog_v1.csv", source_catalog, source_fields)

    reference_rows = []
    drift_rows = []
    seen_ref_keys = set()
    qid_by_candidate_slug = {
        r["member_slug"]: (r.get("wikidata_qids") or "").strip()
        for r in candidates
    }

    drift_eligible_rows = 0
    for qid, r in candidate_by_qid.items():
        if qid not in person_entities:
            continue
        drift_eligible_rows += 1
        entity = person_entities[qid]
        claims = (((entity or {}).get("claims") or {}).get("P569", []) or [])
        candidate_dob = r["candidate_exact_dob"]
        matching_claims = []
        current_day_dates = set()

        for claim in claims:
            dv = (((claim or {}).get("mainsnak") or {}).get("datavalue") or {}).get("value")
            dob, precision = normalize_wikidata_time(dv)
            if dob and precision is not None and int(precision) >= 11:
                current_day_dates.add(dob)
                if dob == candidate_dob:
                    matching_claims.append(claim)

        if not matching_claims:
            drift_rows.append({
                "member_slug": r["member_slug"],
                "display_name": r["display_name"],
                "wikidata_qid": qid,
                "candidate_exact_dob": candidate_dob,
                "current_day_precision_dates": "|".join(sorted(current_day_dates)),
                "review_reason": "candidate_p569_no_longer_matches_current_claim",
                "final_exact_dob": "",
                "acceptance_status": "manual_review_required",
                "bazi_variables_computed": 0,
            })
            continue

        for claim_index, claim in enumerate(matching_claims):
            for ref_index, reference in enumerate((claim or {}).get("references") or []):
                ref_hash = str((reference or {}).get("hash") or "").strip()
                stated_qids = ref_entity_ids(reference, "P248")
                direct_urls = sorted(
                    str(x).strip() for x in ref_values(reference, "P854")
                    if isinstance(x, str) and x.strip()
                )
                ref_props = sorted(((reference or {}).get("snaks") or {}).keys())

                if not stated_qids:
                    stated_qids = [""]

                for source_qid in stated_qids:
                    main_props = source_main_props.get(source_qid, [])
                    record_hits = []
                    for pid in main_props:
                        pe = property_entities.get(pid, {})
                        fmts = string_values(pe, "P1630")
                        vals = [scalar_ref_value(v) for v in ref_values(reference, pid)]
                        vals = [v for v in vals if v]
                        for v in vals:
                            if fmts:
                                for fmt in fmts:
                                    record_hits.append((pid, v, fmt, formatter_url(fmt, v)))
                            else:
                                record_hits.append((pid, v, "", ""))

                    if not record_hits:
                        record_hits = [("", "", "", "")]

                    for pid, record_id, fmt, record_url in record_hits:
                        key = (
                            qid, candidate_dob, claim_index, ref_index, ref_hash,
                            source_qid, pid, record_id, record_url, "|".join(direct_urls)
                        )
                        if key in seen_ref_keys:
                            continue
                        seen_ref_keys.add(key)
                        se = source_entities.get(source_qid, {}) if source_qid else {}
                        reference_rows.append({
                            "member_slug": r["member_slug"],
                            "display_name": r["display_name"],
                            "wikidata_qid": qid,
                            "candidate_exact_dob": candidate_dob,
                            "reference_hash": ref_hash,
                            "stated_in_qid": source_qid,
                            "stated_in_label": label(se) if source_qid else "",
                            "stated_in_description": description(se) if source_qid else "",
                            "source_policy_hint": source_hint(source_qid, label(se), description(se)) if source_qid else "",
                            "source_main_property": pid,
                            "source_record_id": record_id,
                            "source_record_url": record_url,
                            "formatter_template": fmt,
                            "direct_reference_urls": "|".join(direct_urls),
                            "reference_property_ids": "|".join(ref_props),
                            "content_verified": "no",
                            "final_exact_dob": "",
                            "acceptance_status": "not_adjudicated",
                            "bazi_variables_computed": 0,
                        })

    drift_fields = [
        "member_slug","display_name","wikidata_qid","candidate_exact_dob",
        "current_day_precision_dates","review_reason","final_exact_dob",
        "acceptance_status","bazi_variables_computed",
    ]
    write_csv(OUT / "p569_candidate_drift_review_v1.csv", drift_rows, drift_fields)

    ref_fields = [
        "member_slug","display_name","wikidata_qid","candidate_exact_dob",
        "reference_hash","stated_in_qid","stated_in_label","stated_in_description",
        "source_policy_hint","source_main_property","source_record_id",
        "source_record_url","formatter_template","direct_reference_urls",
        "reference_property_ids","content_verified","final_exact_dob",
        "acceptance_status","bazi_variables_computed",
    ]
    write_csv(OUT / "resolved_reference_records_v1.csv", reference_rows, ref_fields)

    source_record_rows = [x for x in reference_rows if x["source_record_id"]]
    source_url_rows = [x for x in reference_rows if x["source_record_url"]]
    direct_url_rows = [x for x in reference_rows if x["direct_reference_urls"]]
    locator_rows = [x for x in reference_rows if x["source_policy_hint"] == "locator_only_known"]
    content_candidate_rows = [
        x for x in reference_rows
        if x["source_policy_hint"] in {"content_source_candidate", "institutional_or_archival_candidate"}
    ]

    write_csv(OUT / "resolved_source_record_urls_v1.csv", source_url_rows, ref_fields)
    write_csv(OUT / "content_source_candidate_records_v1.csv", content_candidate_rows, ref_fields)
    write_csv(OUT / "locator_only_records_v1.csv", locator_rows, ref_fields)

    source_hint_counts = Counter(x["source_policy_hint"] for x in source_catalog)
    top_sources = [
        {
            "source_qid": x["source_qid"],
            "candidate_rows": x["candidate_rows"],
            "label": x["label"],
            "source_policy_hint": x["source_policy_hint"],
            "main_property_ids": x["main_property_ids"],
        }
        for x in source_catalog[:30]
    ]

    summary = {
        "dataset": "Leopoldina local P569 stated-in source resolver v1",
        "input_candidate_rows": len(candidates),
        "input_candidate_sha256": sha256(CANDIDATES),
        "person_cache_files_seen": cache_file_count,
        "person_entities_loaded_from_cache": len(person_entities),
        "stated_in_source_qids": len(source_qids),
        "source_entities_resolved": sum(q in source_entities for q in source_qids),
        "main_wikidata_properties_resolved": len(main_pids),
        "candidate_rows_evaluated_from_person_cache": drift_eligible_rows,
        "candidate_p569_drift_rows": len(drift_rows),
        "resolved_reference_rows": len(reference_rows),
        "reference_rows_with_source_specific_id": len(source_record_rows),
        "reference_rows_with_constructed_source_record_url": len(source_url_rows),
        "reference_rows_with_direct_p854_url": len(direct_url_rows),
        "source_policy_hint_counts": dict(sorted(source_hint_counts.items())),
        "top_stated_in_sources": top_sources,
        "acceptance_rule": (
            "Resolution only. No source or DOB is accepted automatically. "
            "Known library/catalog authority sources remain locator-only. "
            "Resolved source-record URLs and direct URLs require content-level verification "
            "before final_exact_dob can be written."
        ),
        "final_exact_dob_written": 0,
        "bazi_variables_computed": 0,
    }
    (OUT / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
