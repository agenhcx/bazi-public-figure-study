#!/usr/bin/env python3
from __future__ import annotations

import csv
import datetime as dt
import json
import re
import unicodedata
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path

TRACKER_COMMIT = "863127a42632e10e173adcf67ab6e448bd2c2edd"
RICH_URL = f"https://raw.githubusercontent.com/acepocalypse/ntl-academies-tracker/{TRACKER_COMMIT}/snapshots/2023/20250909_134202.csv"
SLIM_URL = f"https://raw.githubusercontent.com/acepocalypse/ntl-academies-tracker/{TRACKER_COMMIT}/snapshots/2023/20250927_164900.csv"
QLEVER = "https://qlever.dev/api/wikidata"
OUT = Path("data/nas_dob_coverage_stage2")
OUT.mkdir(parents=True, exist_ok=True)

SCIENCE_CORE = {12,13,14,15,16,21,22,23,24,25,26,27,28,29,41,42,43,44}

WIKIDATA_QUERY = r"""
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX p: <http://www.wikidata.org/prop/>
PREFIX ps: <http://www.wikidata.org/prop/statement/>
PREFIX psv: <http://www.wikidata.org/prop/statement/value/>
PREFIX wikibase: <http://wikiba.se/ontology#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?person ?nasid ?label ?dob ?precision ?rank WHERE {
  ?person wdt:P5380 ?nasid .
  OPTIONAL {
    ?person rdfs:label ?label .
    FILTER(LANG(?label) = "en")
  }
  OPTIONAL {
    ?person p:P569 ?dob_stmt .
    ?dob_stmt ps:P569 ?dob ;
              psv:P569 ?dob_value ;
              wikibase:rank ?rank .
    FILTER(?rank != wikibase:DeprecatedRank)
    ?dob_value wikibase:timePrecision ?precision .
  }
}
ORDER BY ?person ?nasid
"""

def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={
        "User-Agent": "bazi-public-figure-study/1.0 (NAS DOB linkage QA)"
    })
    with urllib.request.urlopen(req, timeout=300) as r:
        return r.read()

def fetch_qlever() -> bytes:
    body = urllib.parse.urlencode({"query": WIKIDATA_QUERY, "action": "tsv_export"}).encode()
    req = urllib.request.Request(
        QLEVER,
        data=body,
        headers={
            "User-Agent": "bazi-public-figure-study/1.0 (NAS DOB linkage QA)",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "text/tab-separated-values",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=300) as r:
        return r.read()

def norm_name(s: str) -> str:
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = s.casefold()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()

def secnum(s: str):
    m = re.search(r"(?:Section\s*)?(\d+)", s or "", re.I)
    return int(m.group(1)) if m else None

def is_regular(row: dict) -> bool:
    s = row.get("membership_type", "")
    if re.search(r"International|Resigned|Rescinded", s, re.I):
        return False
    return bool(re.search(r"Member|Emeritus", s, re.I))

def clean_term(s: str) -> str:
    s = (s or "").strip()
    if s.startswith("<") and s.endswith(">"):
        return s[1:-1]
    if len(s) >= 2 and s[0] == '"' and '"' in s[1:]:
        end = s.rfind('"')
        return s[1:end].replace("\\t","\t").replace("\\n","\n").replace("\\r","\r").replace("\\\"","\"").replace("\\\\","\\")
    return s

def parse_qlever(raw: bytes):
    rows = list(csv.reader(raw.decode("utf-8-sig").splitlines(), delimiter="\t"))
    if not rows:
        raise RuntimeError("Empty QLever result")
    headers = [x.lstrip("?").strip() for x in rows[0]]
    idx = {h:i for i,h in enumerate(headers)}
    people = defaultdict(lambda: {"labels":set(),"nasids":set(),"exact":set(),"all_precision":set()})
    for r in rows[1:]:
        r = r + [""]*(len(headers)-len(r))
        person = clean_term(r[idx["person"]])
        if not person:
            continue
        d = people[person]
        label = clean_term(r[idx["label"]])
        nasid = clean_term(r[idx["nasid"]])
        dob = clean_term(r[idx["dob"]])
        p = clean_term(r[idx["precision"]])
        if label: d["labels"].add(label)
        if nasid: d["nasids"].add(nasid)
        try: precision = int(p)
        except Exception: precision = None
        if precision is not None:
            d["all_precision"].add(precision)
            if dob and precision >= 11:
                # ISO date part is sufficient; values are UTC-like lexical forms.
                m = re.match(r"([+-]?\d{4})-(\d{2})-(\d{2})", dob)
                if m:
                    yyyy = m.group(1).lstrip("+")
                    d["exact"].add(f"{yyyy}-{m.group(2)}-{m.group(3)}")
    return people, len(rows)-1

def parse_date_range(s: str):
    # NAS slim cards commonly store "Month D, YYYY - Month D, YYYY" for deceased.
    m = re.match(r"^\s*([A-Z][a-z]+\s+\d{1,2},\s+\d{4})\s*-\s*([A-Z][a-z]+\s+\d{1,2},\s+\d{4})\s*$", s or "")
    if not m:
        return None
    try:
        return dt.datetime.strptime(m.group(1), "%B %d, %Y").date().isoformat()
    except ValueError:
        return None

def read_csv_bytes(raw: bytes):
    text = raw.decode("utf-8-sig")
    return list(csv.DictReader(text.splitlines()))

rich_raw = fetch(RICH_URL)
slim_raw = fetch(SLIM_URL)
wd_raw = fetch_qlever()

(OUT/"source_rich.sha256.txt").write_text(__import__("hashlib").sha256(rich_raw).hexdigest()+"\n", encoding="utf-8")
(OUT/"source_slim.sha256.txt").write_text(__import__("hashlib").sha256(slim_raw).hexdigest()+"\n", encoding="utf-8")
(OUT/"wikidata_raw.tsv").write_bytes(wd_raw)

rich = read_csv_bytes(rich_raw)
slim = read_csv_bytes(slim_raw)
slim_by_url = {r["profile_url"]:r for r in slim}

science = [r for r in rich if is_regular(r) and secnum(r.get("primary_section","")) in SCIENCE_CORE]

nas_name_map = defaultdict(list)
for r in science:
    nas_name_map[norm_name(r["name"])].append(r)

wd_people, wd_raw_rows = parse_qlever(wd_raw)
wd_label_map = defaultdict(list)
for uri,d in wd_people.items():
    exact = sorted(d["exact"])
    if len(exact) != 1:
        continue
    for label in d["labels"]:
        wd_label_map[norm_name(label)].append({
            "uri":uri,
            "qid":uri.rsplit("/",1)[-1],
            "label":label,
            "dob":exact[0],
            "nasids":"|".join(sorted(d["nasids"])),
        })

out_rows=[]
for r in science:
    key=norm_name(r["name"])
    s=slim_by_url.get(r["profile_url"])
    nas_dob = parse_date_range(s.get("affiliation","")) if (s and r.get("deceased")=="Y") else None

    nas_unique = len(nas_name_map[key]) == 1
    wd_candidates = wd_label_map.get(key, [])
    # Deduplicate same QID repeated through multiple English labels (rare).
    uniq_wd = {}
    for x in wd_candidates:
        uniq_wd[x["qid"]] = x
    wd_candidates = list(uniq_wd.values())

    wd_match = wd_candidates[0] if nas_unique and len(wd_candidates)==1 else None
    wd_dob = wd_match["dob"] if wd_match else None

    if nas_dob and wd_dob:
        compare = "agree" if nas_dob == wd_dob else "mismatch"
    elif nas_dob:
        compare = "nas_only"
    elif wd_dob:
        compare = "wikidata_only"
    else:
        compare = "neither"

    out_rows.append({
        "profile_url":r["profile_url"],
        "name":r["name"],
        "normalized_name":key,
        "election_year":r["year"],
        "deceased":r["deceased"],
        "membership_type":r["membership_type"],
        "primary_section":r["primary_section"],
        "secondary_section":r["secondary_section"],
        "nas_name_unique":int(nas_unique),
        "nas_exact_dob_from_card":nas_dob or "",
        "wikidata_unique_exact_name_match":int(wd_match is not None),
        "wikidata_qid":wd_match["qid"] if wd_match else "",
        "wikidata_label":wd_match["label"] if wd_match else "",
        "wikidata_nas_member_ids":wd_match["nasids"] if wd_match else "",
        "wikidata_exact_dob":wd_dob or "",
        "dob_overlap_status":compare,
    })

fields=list(out_rows[0].keys())
with (OUT/"nas_science_core_dob_linkage.csv").open("w",encoding="utf-8-sig",newline="") as f:
    w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(out_rows)

agree=sum(r["dob_overlap_status"]=="agree" for r in out_rows)
mismatch=sum(r["dob_overlap_status"]=="mismatch" for r in out_rows)
nas_only=sum(r["dob_overlap_status"]=="nas_only" for r in out_rows)
wd_only=sum(r["dob_overlap_status"]=="wikidata_only" for r in out_rows)
neither=sum(r["dob_overlap_status"]=="neither" for r in out_rows)
nas_exact=sum(bool(r["nas_exact_dob_from_card"]) for r in out_rows)
wd_exact=sum(bool(r["wikidata_exact_dob"]) for r in out_rows)
combined_unique = nas_exact + wd_only

summary={
    "tracker_commit":TRACKER_COMMIT,
    "rich_snapshot_url":RICH_URL,
    "slim_snapshot_url":SLIM_URL,
    "science_core_rows":len(out_rows),
    "science_core_unique_normalized_names":sum(len(v)==1 for v in nas_name_map.values()),
    "science_core_ambiguous_normalized_name_groups":sum(len(v)>1 for v in nas_name_map.values()),
    "nas_card_exact_dob_rows":nas_exact,
    "wikidata_unique_exact_name_match_rows":wd_exact,
    "overlap_agree_rows":agree,
    "overlap_mismatch_rows":mismatch,
    "nas_only_rows":nas_only,
    "wikidata_only_new_rows":wd_only,
    "neither_rows":neither,
    "combined_exact_dob_rows_if_wikidata_accepted_after_validation":combined_unique,
    "combined_exact_dob_rate":round(combined_unique/len(out_rows),6),
    "wikidata_overlap_agreement_rate":round(agree/(agree+mismatch),6) if agree+mismatch else None,
    "wikidata_persons_with_p5380":len(wd_people),
    "wikidata_raw_result_rows":wd_raw_rows,
    "matching_rule":"Exact normalized English-label match only; NAS normalized name must be unique within science_core; exactly one Wikidata QID with exactly one non-deprecated day-precision P569 value.",
    "important_note":"This is DOB coverage/linkage QA only. It does not finalize DOBs and computes no BaZi variables."
}
(OUT/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")

mismatch_rows=[r for r in out_rows if r["dob_overlap_status"]=="mismatch"]
with (OUT/"wikidata_nas_dob_mismatches.csv").open("w",encoding="utf-8-sig",newline="") as f:
    w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(mismatch_rows)

print(json.dumps(summary,indent=2))
