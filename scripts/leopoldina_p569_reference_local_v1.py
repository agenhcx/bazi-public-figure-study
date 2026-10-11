#!/usr/bin/env python3
from __future__ import annotations

import csv
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
QLEVER = "https://qlever.dev/api/wikidata"
UA = "bazi-public-figure-study/1.0 (Leopoldina local P569 provenance inventory; no BaZi computation)"
BATCH_SIZE = int(os.environ.get("LEOPOLDINA_REF_BATCH_SIZE", "50"))
SLEEP_SECONDS = float(os.environ.get("LEOPOLDINA_REF_SLEEP", "1.5"))
LIMIT = int(os.environ.get("LEOPOLDINA_REF_LIMIT", "0"))

try:
    import certifi
except ImportError:
    certifi = None

LIBRARY_DOMAINS = {
    "d-nb.info",
    "lobid.org",
    "id.loc.gov",
    "loc.gov",
    "viaf.org",
    "data.bnf.fr",
    "catalogue.bnf.fr",
    "idref.fr",
    "catalogue.bnf.fr",
    "aleph.nkp.cz",
}
WIKI_DOMAINS = {
    "wikidata.org",
    "www.wikidata.org",
    "wikipedia.org",
    "de.wikipedia.org",
    "en.wikipedia.org",
    "commons.wikimedia.org",
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
            with urlopen_verified(req, timeout=240) as r:
                raw = r.read().decode("utf-8-sig")
            break
        except urllib.error.HTTPError as e:
            last = e
            if attempt + 1 >= retries or e.code not in {429, 500, 502, 503, 504}:
                raise
            retry_after = e.headers.get("Retry-After", "")
            try:
                delay = float(retry_after)
            except Exception:
                delay = min(90.0, 2.0 ** attempt + 1.0)
            print(f"QLever HTTP {e.code}; retry in {delay:.1f}s")
            time.sleep(delay)
        except urllib.error.URLError as e:
            last = e
            if attempt + 1 >= retries:
                raise
            delay = min(60.0, 2.0 ** attempt + 1.0)
            print(f"QLever network error; retry in {delay:.1f}s: {e}")
            time.sleep(delay)
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
            elif v.startswith('"'):
                m = re.match(r'^"(.*)"(?:\^\^<[^>]+>|@[A-Za-z-]+)?$', v)
                if m:
                    v = m.group(1)
            item[h] = v
        out.append(item)
    return out

def chunks(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i+n]

def sparql_string(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'

def parse_date(v):
    m = re.search(r"([12]\d{3})-(\d{2})-(\d{2})", v or "")
    return m.group(0) if m else ""

def as_int(v):
    try:
        return int(float(str(v)))
    except Exception:
        return None

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

def cache_path(batch_index):
    return CACHE / f"batch_{batch_index:04d}.json"

def fetch_batch(batch_index, slugs):
    cp = cache_path(batch_index)
    if cp.exists():
        obj = json.loads(cp.read_text(encoding="utf-8"))
        cached_slugs = obj.get("slugs", [])
        if cached_slugs == slugs:
            print(f"batch {batch_index}: cache hit ({len(slugs)} members)")
            return obj.get("rows", [])
        raise RuntimeError(f"Cache slug mismatch in {cp}; delete that cache file and rerun.")

    values = " ".join(sparql_string(x) for x in slugs)
    query = f"""
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX p: <http://www.wikidata.org/prop/>
PREFIX psv: <http://www.wikidata.org/prop/statement/value/>
PREFIX pr: <http://www.wikidata.org/prop/reference/>
PREFIX prov: <http://www.w3.org/ns/prov#>
PREFIX wikibase: <http://wikiba.se/ontology#>
SELECT ?person ?memberId ?dob ?precision ?refNode ?refUrl ?statedIn WHERE {{
  VALUES ?memberId {{ {values} }}
  ?person wdt:P10299 ?memberId ;
          p:P569 ?dobStatement .
  ?dobStatement psv:P569 ?dobNode .
  ?dobNode wikibase:timeValue ?dob ;
           wikibase:timePrecision ?precision .
  OPTIONAL {{
    ?dobStatement prov:wasDerivedFrom ?refNode .
    OPTIONAL {{ ?refNode pr:P854 ?refUrl . }}
    OPTIONAL {{ ?refNode pr:P248 ?statedIn . }}
  }}
}}
"""
    rows = qlever_tsv(query)
    cp.parent.mkdir(parents=True, exist_ok=True)
    cp.write_text(json.dumps({"slugs": slugs, "rows": rows}, ensure_ascii=False), encoding="utf-8")
    print(f"batch {batch_index}: fetched {len(rows)} rows for {len(slugs)} members")
    return rows

def main():
    if not IN.exists():
        raise RuntimeError(
            f"Missing {IN}. Run python scripts/leopoldina_dob_local_v1.py first."
        )
    candidates = read_csv(IN)
    if LIMIT > 0:
        candidates = candidates[:LIMIT]
    if not candidates:
        raise RuntimeError("No candidate rows found.")
    if LIMIT == 0 and len(candidates) != 2497:
        raise RuntimeError(f"Expected 2497 v1 candidates, got {len(candidates)}")

    required = {"member_slug", "candidate_exact_dob", "wikidata_qids", "display_name", "deceased_marker", "election_year"}
    missing = required - set(candidates[0])
    if missing:
        raise RuntimeError(f"Candidate CSV missing required columns: {sorted(missing)}")

    candidate_by_slug = {r["member_slug"]: r for r in candidates}
    if len(candidate_by_slug) != len(candidates):
        raise RuntimeError("Candidate member_slug is not unique")

    OUT.mkdir(parents=True, exist_ok=True)
    CACHE.mkdir(parents=True, exist_ok=True)

    all_raw = []
    sorted_slugs = sorted(candidate_by_slug)
    total_batches = (len(sorted_slugs) + BATCH_SIZE - 1) // BATCH_SIZE
    for batch_index, batch in enumerate(chunks(sorted_slugs, BATCH_SIZE)):
        rows = fetch_batch(batch_index, batch)
        all_raw.extend(rows)
        print(f"progress: {batch_index+1}/{total_batches} batches; raw rows={len(all_raw)}")
        if batch_index + 1 < total_batches:
            time.sleep(SLEEP_SECONDS)

    agg = defaultdict(lambda: {
        "reference_nodes": set(),
        "reference_urls": set(),
        "stated_in_qids": set(),
        "matching_statement_rows": 0,
        "other_day_p569_dates": set(),
    })
    exploded = []

    for x in all_raw:
        slug = (x.get("memberId") or "").strip()
        if slug not in candidate_by_slug:
            continue
        candidate = candidate_by_slug[slug]["candidate_exact_dob"]
        d = parse_date(x.get("dob", ""))
        p = as_int(x.get("precision"))
        if not d or p is None or p < 11:
            continue
        if d != candidate:
            agg[slug]["other_day_p569_dates"].add(d)
            continue

        ref_node = (x.get("refNode") or "").strip()
        ref_url = (x.get("refUrl") or "").strip()
        stated = (x.get("statedIn") or "").strip().rsplit("/", 1)[-1]
        if ref_node:
            agg[slug]["reference_nodes"].add(ref_node)
        if ref_url:
            agg[slug]["reference_urls"].add(ref_url)
        if stated:
            agg[slug]["stated_in_qids"].add(stated)
        agg[slug]["matching_statement_rows"] += 1

        exploded.append({
            "member_slug": slug,
            "display_name": candidate_by_slug[slug]["display_name"],
            "candidate_exact_dob": candidate,
            "wikidata_qids": candidate_by_slug[slug]["wikidata_qids"],
            "ref_node": ref_node,
            "ref_url": ref_url,
            "ref_domain": domain(ref_url),
            "ref_domain_class": classify_domain(domain(ref_url)),
            "stated_in_qid": stated,
            "accepted_exact_dob": "",
            "bazi_variables_computed": 0,
        })

    summary_rows = []
    domain_counts = Counter()
    domain_class_counts = Counter()

    for slug in sorted_slugs:
        r = candidate_by_slug[slug]
        a = agg[slug]
        urls = sorted(a["reference_urls"])
        domains = sorted({domain(u) for u in urls if domain(u)})
        classes = sorted({classify_domain(d) for d in domains})
        for d in domains:
            domain_counts[d] += 1
            domain_class_counts[classify_domain(d)] += 1

        has_nonlibrary = int(any(classify_domain(d) == "nonlibrary_url" for d in domains))
        has_library = int(any(classify_domain(d) == "library_locator" for d in domains))
        has_wiki = int(any(classify_domain(d) == "wiki_nonindependent" for d in domains))
        has_any_ref = int(bool(a["reference_nodes"]))
        has_any_url = int(bool(urls))
        has_stated = int(bool(a["stated_in_qids"]))

        if has_nonlibrary:
            provenance_queue = "inspect_nonlibrary_reference_url"
        elif has_library or has_wiki or has_stated or has_any_ref:
            provenance_queue = "locator_or_reference_only"
        else:
            provenance_queue = "no_reference_metadata"

        summary_rows.append({
            "member_slug": slug,
            "display_name": r["display_name"],
            "deceased_marker": r["deceased_marker"],
            "election_year": r["election_year"],
            "wikidata_qids": r["wikidata_qids"],
            "candidate_exact_dob": r["candidate_exact_dob"],
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
            "provenance_queue": provenance_queue,
            "final_exact_dob": "",
            "acceptance_status": "not_adjudicated",
            "bazi_variables_computed": 0,
        })

    fields = list(summary_rows[0].keys())
    write_csv(OUT / "candidate_reference_summary_v1.csv", summary_rows, fields)

    exploded_fields = [
        "member_slug","display_name","candidate_exact_dob","wikidata_qids",
        "ref_node","ref_url","ref_domain","ref_domain_class","stated_in_qid",
        "accepted_exact_dob","bazi_variables_computed"
    ]
    write_csv(OUT / "reference_inventory_exploded_v1.csv", exploded, exploded_fields)

    domain_rows = [
        {"domain": d, "candidate_rows": n, "domain_class": classify_domain(d)}
        for d, n in domain_counts.most_common()
    ]
    write_csv(OUT / "reference_domain_counts_v1.csv", domain_rows, ["domain","candidate_rows","domain_class"])

    queues = defaultdict(list)
    for r in summary_rows:
        queues[r["provenance_queue"]].append(r)
    for q, rows in queues.items():
        write_csv(OUT / f"{q}_v1.csv", rows, fields)

    summary = {
        "dataset": "Leopoldina local P569 reference provenance inventory v1",
        "input_candidate_rows": len(candidates),
        "input_candidate_sha256": sha256(IN),
        "batch_size": BATCH_SIZE,
        "batch_count": total_batches,
        "cache_directory": str(CACHE),
        "raw_query_rows": len(all_raw),
        "candidate_rows_with_any_reference_node": sum(int(r["has_any_reference_node"]) for r in summary_rows),
        "candidate_rows_with_any_reference_url": sum(int(r["has_any_reference_url"]) for r in summary_rows),
        "candidate_rows_with_nonlibrary_reference_url": sum(int(r["has_nonlibrary_reference_url"]) for r in summary_rows),
        "candidate_rows_with_library_locator_url": sum(int(r["has_library_locator_url"]) for r in summary_rows),
        "candidate_rows_with_wiki_reference_url": sum(int(r["has_wiki_reference_url"]) for r in summary_rows),
        "candidate_rows_with_stated_in": sum(int(r["has_stated_in"]) for r in summary_rows),
        "queue_counts": {k: len(v) for k, v in sorted(queues.items())},
        "top_reference_domains": domain_counts.most_common(30),
        "domain_class_candidate_counts": dict(sorted(domain_class_counts.items())),
        "acceptance_rule": (
            "Inventory only. A P569 reference URL or stated-in claim is not accepted automatically. "
            "Library authorities remain locator-only; non-library reference URLs proceed to content-level verification."
        ),
        "final_exact_dob_written": 0,
        "bazi_variables_computed": 0,
    }
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
