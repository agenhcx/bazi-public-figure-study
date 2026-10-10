#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import re
import time
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlparse

IN = Path("data/royal_society_current_wikidata_locator_consolidated_input")
OUT = Path("data/royal_society_current_p569_provenance_audit_v1")
API = "https://www.wikidata.org/w/api.php"
UA = "bazi-public-figure-study/1.0 (Royal Society P569 provenance audit; no DOB acceptance)"


def read_csv(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows, fields):
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def split_sc(s):
    return [x.strip() for x in (s or "").split(";") if x.strip()]


def domain(url):
    try:
        d = (urlparse(url).hostname or "").lower()
    except Exception:
        return ""
    return d[4:] if d.startswith("www.") else d


def api(params):
    q = dict(params)
    q.setdefault("format", "json")
    qs = urllib.parse.urlencode(q, doseq=True)
    req = urllib.request.Request(API + "?" + qs, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.load(r)
    time.sleep(0.15)
    return data


def source_meta(qids):
    out = {}
    qids = list(dict.fromkeys(qids))
    for i in range(0, len(qids), 50):
        part = qids[i:i+50]
        d = api({
            "action": "wbgetentities",
            "ids": "|".join(part),
            "props": "labels|descriptions|claims",
            "languages": "en",
        })
        for qid, ent in d.get("entities", {}).items():
            label = ent.get("labels", {}).get("en", {}).get("value", "")
            desc = ent.get("descriptions", {}).get("en", {}).get("value", "")
            urls = []
            for pid in ("P856", "P953"):
                for st in ent.get("claims", {}).get(pid, []) or []:
                    v = st.get("mainsnak", {}).get("datavalue", {}).get("value")
                    if isinstance(v, str) and v.startswith(("http://", "https://")):
                        urls.append(v)
            out[qid] = {
                "label": label,
                "description": desc,
                "urls": sorted(set(urls)),
            }
    return out


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    files = list(IN.rglob("exact_p569_candidate_queue_v1.csv"))
    if len(files) != 1:
        raise RuntimeError(f"Expected one exact candidate CSV, found {len(files)}: {files}")
    rows = read_csv(files[0])
    if len(rows) != 680:
        raise RuntimeError(f"Expected 680 exact-P569 candidates, got {len(rows)}")

    url_rows = []
    stated_rows = []
    all_qids = []
    for r in rows:
        urls = split_sc(r.get("p569_reference_urls", ""))
        qids = split_sc(r.get("p569_stated_in_qids", ""))
        for u in urls:
            url_rows.append({
                "cohort_key": r["cohort_key"],
                "display_name": r["display_name"],
                "wikidata_qid": r["wikidata_qid"],
                "p569_exact_values": r["p569_exact_values"],
                "reference_url": u,
                "reference_domain": domain(u),
            })
        for q in qids:
            all_qids.append(q)
            stated_rows.append({
                "cohort_key": r["cohort_key"],
                "display_name": r["display_name"],
                "wikidata_qid": r["wikidata_qid"],
                "p569_exact_values": r["p569_exact_values"],
                "stated_in_qid": q,
            })

    meta = source_meta(all_qids)
    for r in stated_rows:
        m = meta.get(r["stated_in_qid"], {})
        r["source_label"] = m.get("label", "")
        r["source_description"] = m.get("description", "")
        r["source_urls"] = ";".join(m.get("urls", []))
        r["source_domains"] = ";".join(sorted({domain(u) for u in m.get("urls", []) if domain(u)}))

    rows_with_url = {r["cohort_key"] for r in url_rows}
    rows_with_stated = {r["cohort_key"] for r in stated_rows}
    both = rows_with_url & rows_with_stated

    dc = Counter(r["reference_domain"] for r in url_rows if r["reference_domain"])
    qc = Counter(r["stated_in_qid"] for r in stated_rows)
    label_counts = Counter(
        (meta.get(q, {}).get("label") or q) for q in qc
    )

    domain_summary = [
        {"reference_domain": d, "reference_instances": n,
         "unique_people": len({r["cohort_key"] for r in url_rows if r["reference_domain"] == d})}
        for d, n in dc.most_common()
    ]
    source_summary = []
    for q, n in qc.most_common():
        m = meta.get(q, {})
        source_summary.append({
            "stated_in_qid": q,
            "source_label": m.get("label", ""),
            "source_description": m.get("description", ""),
            "statement_instances": n,
            "unique_people": len({r["cohort_key"] for r in stated_rows if r["stated_in_qid"] == q}),
            "source_urls": ";".join(m.get("urls", [])),
        })

    write_csv(
        OUT / "p569_reference_urls_v1.csv",
        url_rows,
        ["cohort_key", "display_name", "wikidata_qid", "p569_exact_values", "reference_url", "reference_domain"],
    )
    write_csv(
        OUT / "p569_stated_in_sources_v1.csv",
        stated_rows,
        ["cohort_key", "display_name", "wikidata_qid", "p569_exact_values", "stated_in_qid",
         "source_label", "source_description", "source_urls", "source_domains"],
    )
    write_csv(
        OUT / "reference_domain_summary_v1.csv",
        domain_summary,
        ["reference_domain", "reference_instances", "unique_people"],
    )
    write_csv(
        OUT / "stated_in_source_summary_v1.csv",
        source_summary,
        ["stated_in_qid", "source_label", "source_description", "statement_instances", "unique_people", "source_urls"],
    )

    summary = {
        "dataset": "Royal Society current exact-P569 provenance audit v1",
        "exact_p569_candidates": len(rows),
        "people_with_reference_url": len(rows_with_url),
        "people_with_stated_in": len(rows_with_stated),
        "people_with_both_reference_url_and_stated_in": len(both),
        "people_with_any_structured_provenance": len(rows_with_url | rows_with_stated),
        "people_with_no_reference_url_or_stated_in": len(rows) - len(rows_with_url | rows_with_stated),
        "reference_url_instances": len(url_rows),
        "unique_reference_domains": len(dc),
        "stated_in_instances": len(stated_rows),
        "unique_stated_in_qids": len(qc),
        "top_reference_domains": domain_summary[:25],
        "top_stated_in_sources": source_summary[:25],
        "dob_values_accepted": 0,
        "bazi_variables_computed": 0,
        "note": "Provenance audit only. Bare Wikidata P569 is not accepted as DOB evidence.",
    }
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
