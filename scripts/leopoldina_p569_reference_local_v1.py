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
from urllib.parse import urlparse

IN = Path("data/leopoldina_dob_local_v1/candidate_unique_day_p569_v1.csv")
OUT = Path("data/leopoldina_p569_reference_local_v1")
CACHE = OUT / "cache"
WIKIDATA_API = "https://www.wikidata.org/w/api.php"
UA = "bazi-public-figure-study/1.0 (Leopoldina local P569 provenance inventory; no BaZi computation)"
BATCH_SIZE = int(os.environ.get("LEOPOLDINA_REF_BATCH_SIZE", "40"))
SLEEP_SECONDS = float(os.environ.get("LEOPOLDINA_REF_SLEEP", "0.8"))
LIMIT = int(os.environ.get("LEOPOLDINA_REF_LIMIT", "0"))

try:
    import certifi
except ImportError:
    certifi = None

LIBRARY_DOMAINS = {
    "d-nb.info", "lobid.org", "id.loc.gov", "loc.gov", "viaf.org",
    "data.bnf.fr", "catalogue.bnf.fr", "idref.fr", "aleph.nkp.cz",
}
WIKI_DOMAINS = {
    "wikidata.org", "www.wikidata.org", "wikipedia.org",
    "de.wikipedia.org", "en.wikipedia.org", "commons.wikimedia.org",
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
    data = urllib.parse.urlencode({
        "action": "wbgetentities",
        "ids": "|".join(qids),
        "props": "claims",
        "format": "json",
        "formatversion": "2",
        "maxlag": "5",
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
                    delay = min(60.0, 2.0 ** attempt + 1.0)
                    print(f"Wikidata maxlag; retry in {delay:.1f}s")
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

def domain(url):
    try:
        return urlparse(url).netloc.lower().removeprefix("www.")
    except Exception:
        return ""

def classify_domain(d):
    if not d:
        return "no_url"
    if d in LIBRARY_DOMAINS or any(d.endswith("." + x) for x in LIBRARY_DOMAINS):
        return "library_locator"
    if d in WIKI_DOMAINS or d.endswith(".wikipedia.org") or d.endswith(".wikimedia.org"):
        return "wiki_nonindependent"
    return "nonlibrary_url"

def valid_qid(v):
    return bool(re.fullmatch(r"Q\d+", str(v or "").strip()))

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

def snak_values(reference, prop):
    snaks = (reference or {}).get("snaks", {})
    vals = []
    for snak in snaks.get(prop, []) or []:
        dv = (snak or {}).get("datavalue")
        if not isinstance(dv, dict):
            continue
        vals.append(dv.get("value"))
    return vals

def reference_urls(reference):
    out = []
    for v in snak_values(reference, "P854"):
        if isinstance(v, str) and v.strip():
            out.append(v.strip())
    return sorted(set(out))

def reference_stated_in(reference):
    out = []
    for v in snak_values(reference, "P248"):
        if isinstance(v, dict):
            qid = str(v.get("id") or "").strip()
            if valid_qid(qid):
                out.append(qid)
    return sorted(set(out))

def cache_path(batch_index):
    return CACHE / f"batch_{batch_index:04d}.json"

def fetch_batch(batch_index, members):
    cp = cache_path(batch_index)
    cache_members = [{"slug": r["member_slug"], "qid": r["wikidata_qids"]} for r in members]
    if cp.exists():
        obj = json.loads(cp.read_text(encoding="utf-8"))
        if obj.get("members", []) == cache_members:
            print(f"batch {batch_index}: cache hit ({len(members)} members)")
            return obj.get("api_response", {})
        raise RuntimeError(f"Cache member mismatch in {cp}; delete that cache file and rerun.")

    qids = []
    for r in members:
        qid = (r.get("wikidata_qids") or "").strip()
        if not valid_qid(qid):
            raise RuntimeError(f"Expected one exact QID for {r['member_slug']}, got {qid!r}")
        qids.append(qid)

    obj = wikidata_entities(qids)
    cp.parent.mkdir(parents=True, exist_ok=True)
    cp.write_text(
        json.dumps({"members": cache_members, "api_response": obj}, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"batch {batch_index}: fetched {len(qids)} entities")
    return obj

def main():
    if not IN.exists():
        raise RuntimeError(f"Missing {IN}. Run python scripts/leopoldina_dob_local_v1.py first.")

    candidates = read_csv(IN)
    if LIMIT > 0:
        candidates = candidates[:LIMIT]
    if not candidates:
        raise RuntimeError("No candidate rows found.")
    if LIMIT == 0 and len(candidates) != 2497:
        raise RuntimeError(f"Expected 2497 v1 candidates, got {len(candidates)}")

    required = {
        "member_slug", "candidate_exact_dob", "wikidata_qids",
        "display_name", "deceased_marker", "election_year",
    }
    missing = required - set(candidates[0])
    if missing:
        raise RuntimeError(f"Candidate CSV missing required columns: {sorted(missing)}")

    candidate_by_slug = {r["member_slug"]: r for r in candidates}
    if len(candidate_by_slug) != len(candidates):
        raise RuntimeError("Candidate member_slug is not unique")
    qid_to_slug = {}
    for r in candidates:
        qid = (r["wikidata_qids"] or "").strip()
        if not valid_qid(qid):
            raise RuntimeError(f"Expected one QID for {r['member_slug']}, got {qid!r}")
        if qid in qid_to_slug:
            raise RuntimeError(f"QID {qid} maps to multiple candidate slugs")
        qid_to_slug[qid] = r["member_slug"]

    OUT.mkdir(parents=True, exist_ok=True)
    CACHE.mkdir(parents=True, exist_ok=True)

    sorted_candidates = sorted(candidates, key=lambda r: r["member_slug"])
    total_batches = (len(sorted_candidates) + BATCH_SIZE - 1) // BATCH_SIZE
    entity_by_qid = {}

    for batch_index, batch in enumerate(chunks(sorted_candidates, BATCH_SIZE)):
        obj = fetch_batch(batch_index, batch)
        entities = obj.get("entities", {})
        if isinstance(entities, list):
            entity_items = [(str(x.get("id") or ""), x) for x in entities]
        elif isinstance(entities, dict):
            entity_items = list(entities.items())
        else:
            raise RuntimeError(f"Unexpected Wikidata entities payload in batch {batch_index}")
        for qid, entity in entity_items:
            if qid in qid_to_slug:
                entity_by_qid[qid] = entity
        print(f"progress: {batch_index+1}/{total_batches} batches; cached entities={len(entity_by_qid)}")
        if batch_index + 1 < total_batches:
            time.sleep(SLEEP_SECONDS)

    agg = defaultdict(lambda: {
        "reference_nodes": set(),
        "reference_urls": set(),
        "stated_in_qids": set(),
        "other_day_p569_dates": set(),
        "matching_claim_count": 0,
    })
    exploded = []

    for qid, slug in qid_to_slug.items():
        r = candidate_by_slug[slug]
        entity = entity_by_qid.get(qid, {})
        claims = ((entity or {}).get("claims") or {}).get("P569", []) or []
        for claim in claims:
            mainsnak = (claim or {}).get("mainsnak") or {}
            dv = mainsnak.get("datavalue") or {}
            value = dv.get("value")
            dob, precision = normalize_wikidata_time(value)
            if not dob or precision is None or int(precision) < 11:
                continue
            if dob != r["candidate_exact_dob"]:
                agg[slug]["other_day_p569_dates"].add(dob)
                continue

            agg[slug]["matching_claim_count"] += 1
            references = (claim or {}).get("references") or []
            for reference in references:
                ref_hash = str((reference or {}).get("hash") or "").strip()
                urls = reference_urls(reference)
                stated = reference_stated_in(reference)
                if ref_hash:
                    agg[slug]["reference_nodes"].add(ref_hash)
                agg[slug]["reference_urls"].update(urls)
                agg[slug]["stated_in_qids"].update(stated)

                if not urls and not stated:
                    exploded.append({
                        "member_slug": slug,
                        "display_name": r["display_name"],
                        "candidate_exact_dob": r["candidate_exact_dob"],
                        "wikidata_qids": qid,
                        "ref_hash": ref_hash,
                        "ref_url": "",
                        "ref_domain": "",
                        "ref_domain_class": "no_url",
                        "stated_in_qid": "",
                        "accepted_exact_dob": "",
                        "bazi_variables_computed": 0,
                    })
                else:
                    if not urls:
                        urls = [""]
                    if not stated:
                        stated = [""]
                    for u in urls:
                        for s in stated:
                            exploded.append({
                                "member_slug": slug,
                                "display_name": r["display_name"],
                                "candidate_exact_dob": r["candidate_exact_dob"],
                                "wikidata_qids": qid,
                                "ref_hash": ref_hash,
                                "ref_url": u,
                                "ref_domain": domain(u),
                                "ref_domain_class": classify_domain(domain(u)),
                                "stated_in_qid": s,
                                "accepted_exact_dob": "",
                                "bazi_variables_computed": 0,
                            })

    summary_rows = []
    domain_counts = Counter()
    domain_class_counts = Counter()
    stated_in_counts = Counter()

    for r in sorted_candidates:
        slug = r["member_slug"]
        a = agg[slug]
        urls = sorted(a["reference_urls"])
        domains = sorted({domain(u) for u in urls if domain(u)})
        classes = sorted({classify_domain(d) for d in domains})
        for d in domains:
            domain_counts[d] += 1
            domain_class_counts[classify_domain(d)] += 1
        for qid in a["stated_in_qids"]:
            stated_in_counts[qid] += 1

        has_nonlibrary = int(any(classify_domain(d) == "nonlibrary_url" for d in domains))
        has_library = int(any(classify_domain(d) == "library_locator" for d in domains))
        has_wiki = int(any(classify_domain(d) == "wiki_nonindependent" for d in domains))
        has_any_ref = int(bool(a["reference_nodes"]))
        has_any_url = int(bool(urls))
        has_stated = int(bool(a["stated_in_qids"]))

        if has_nonlibrary:
            queue = "inspect_nonlibrary_reference_url"
        elif has_library or has_wiki or has_stated or has_any_ref:
            queue = "locator_or_reference_only"
        else:
            queue = "no_reference_metadata"

        summary_rows.append({
            "member_slug": slug,
            "display_name": r["display_name"],
            "deceased_marker": r["deceased_marker"],
            "election_year": r["election_year"],
            "wikidata_qids": r["wikidata_qids"],
            "candidate_exact_dob": r["candidate_exact_dob"],
            "matching_claim_count": a["matching_claim_count"],
            "reference_node_count": len(a["reference_nodes"]),
            "reference_url_count": len(urls),
            "reference_urls": "|".join(urls),
            "reference_domains": "|".join(domains),
            "reference_domain_classes": "|".join(classes),
            "stated_in_count": len(a["stated_in_qids"]),
            "stated_in_qids": "|".join(sorted(a["stated_in_qids"])),
            "has_any_reference_node": has_any_ref,
            "has_any_reference_url": has_any_url,
            "has_nonlibrary_reference_url": has_nonlibrary,
            "has_library_locator_url": has_library,
            "has_wiki_reference_url": has_wiki,
            "has_stated_in": has_stated,
            "other_day_p569_dates": "|".join(sorted(a["other_day_p569_dates"])),
            "provenance_queue": queue,
            "final_exact_dob": "",
            "acceptance_status": "not_adjudicated",
            "bazi_variables_computed": 0,
        })

    fields = list(summary_rows[0].keys())
    write_csv(OUT / "candidate_reference_summary_v1.csv", summary_rows, fields)

    exploded_fields = [
        "member_slug", "display_name", "candidate_exact_dob", "wikidata_qids",
        "ref_hash", "ref_url", "ref_domain", "ref_domain_class", "stated_in_qid",
        "accepted_exact_dob", "bazi_variables_computed",
    ]
    write_csv(OUT / "reference_inventory_exploded_v1.csv", exploded, exploded_fields)

    domain_rows = [
        {"domain": d, "candidate_rows": n, "domain_class": classify_domain(d)}
        for d, n in domain_counts.most_common()
    ]
    write_csv(
        OUT / "reference_domain_counts_v1.csv",
        domain_rows,
        ["domain", "candidate_rows", "domain_class"],
    )

    stated_in_rows = [
        {"stated_in_qid": qid, "candidate_rows": n}
        for qid, n in stated_in_counts.most_common()
    ]
    write_csv(
        OUT / "stated_in_qid_counts_v1.csv",
        stated_in_rows,
        ["stated_in_qid", "candidate_rows"],
    )

    queues = defaultdict(list)
    for r in summary_rows:
        queues[r["provenance_queue"]].append(r)
    for q, rows in queues.items():
        write_csv(OUT / f"{q}_v1.csv", rows, fields)

    summary = {
        "dataset": "Leopoldina local P569 reference provenance inventory v1",
        "source_api": "Wikidata MediaWiki API wbgetentities, props=claims",
        "input_candidate_rows": len(candidates),
        "input_candidate_sha256": sha256(IN),
        "batch_size": BATCH_SIZE,
        "batch_count": total_batches,
        "cache_directory": str(CACHE),
        "entities_returned": len(entity_by_qid),
        "candidate_rows_with_matching_p569_claim": sum(int(r["matching_claim_count"] > 0) for r in summary_rows),
        "candidate_rows_with_any_reference_node": sum(int(r["has_any_reference_node"]) for r in summary_rows),
        "candidate_rows_with_any_reference_url": sum(int(r["has_any_reference_url"]) for r in summary_rows),
        "candidate_rows_with_nonlibrary_reference_url": sum(int(r["has_nonlibrary_reference_url"]) for r in summary_rows),
        "candidate_rows_with_library_locator_url": sum(int(r["has_library_locator_url"]) for r in summary_rows),
        "candidate_rows_with_wiki_reference_url": sum(int(r["has_wiki_reference_url"]) for r in summary_rows),
        "candidate_rows_with_stated_in": sum(int(r["has_stated_in"]) for r in summary_rows),
        "queue_counts": {k: len(v) for k, v in sorted(queues.items())},
        "top_reference_domains": domain_counts.most_common(30),
        "top_stated_in_qids": stated_in_counts.most_common(30),
        "domain_class_candidate_counts": dict(sorted(domain_class_counts.items())),
        "acceptance_rule": (
            "Inventory only. A P569 reference URL or stated-in claim is not accepted automatically. "
            "Library authorities remain locator-only; non-library reference URLs proceed to content-level verification."
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
