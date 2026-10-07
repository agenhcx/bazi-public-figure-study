#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path

ENDPOINT = "https://qlever.dev/api/wikidata"
OUT = Path("data/nas_wikidata_dob_pilot")
OUT.mkdir(parents=True, exist_ok=True)

QUERY = r"""
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

def run_query() -> bytes:
    body = urllib.parse.urlencode({
        "query": QUERY,
        "action": "tsv_export",
    }).encode("utf-8")
    req = urllib.request.Request(
        ENDPOINT,
        data=body,
        headers={
            "User-Agent": "bazi-public-figure-study/1.0 (NAS DOB coverage pilot)",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "text/tab-separated-values",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=300) as resp:
        return resp.read()

def clean_header(s: str) -> str:
    return s.lstrip("?").strip()

def clean_term(s: str) -> str:
    s = (s or "").strip()
    if s.startswith("<") and s.endswith(">"):
        return s[1:-1]
    if len(s) >= 2 and s[0] == '"' and '"' in s[1:]:
        # QLever TSV may serialize literals with quotes and datatype/lang suffix.
        end = s.rfind('"')
        return s[1:end].replace('\\t', '\t').replace('\\n', '\n').replace('\\r', '\r').replace('\\\"', '"').replace('\\\\', '\\')
    return s

def precision_int(s: str):
    s = clean_term(s)
    try:
        return int(s)
    except Exception:
        return None

raw = run_query()
raw_path = OUT / "wikidata_p5380_p569_raw.tsv"
raw_path.write_bytes(raw)

text = raw.decode("utf-8-sig")
reader = csv.reader(text.splitlines(), delimiter="\t")
rows = list(reader)
if not rows:
    raise RuntimeError("QLever returned no rows.")

headers = [clean_header(x) for x in rows[0]]
required = {"person", "nasid", "label", "dob", "precision", "rank"}
if not required.issubset(headers):
    raise RuntimeError(f"Unexpected TSV headers: {headers}")

idx = {h: i for i, h in enumerate(headers)}
people = defaultdict(lambda: {
    "nasids": set(),
    "labels": set(),
    "statements": [],
})

for r in rows[1:]:
    if not r:
        continue
    r = r + [""] * (len(headers) - len(r))
    person = clean_term(r[idx["person"]])
    if not person:
        continue
    d = people[person]
    nasid = clean_term(r[idx["nasid"]])
    label = clean_term(r[idx["label"]])
    dob = clean_term(r[idx["dob"]])
    precision = precision_int(r[idx["precision"]])
    rank = clean_term(r[idx["rank"]])
    if nasid:
        d["nasids"].add(nasid)
    if label:
        d["labels"].add(label)
    if dob and precision is not None:
        d["statements"].append((dob, precision, rank))

collapsed = []
for person, d in sorted(people.items()):
    stmts = d["statements"]
    exact = sorted({dob for dob, p, rank in stmts if p >= 11})
    month = sorted({dob for dob, p, rank in stmts if p == 10})
    year = sorted({dob for dob, p, rank in stmts if p == 9})
    precisions = sorted({p for _, p, _ in stmts})
    collapsed.append({
        "wikidata_uri": person,
        "qid": person.rsplit("/", 1)[-1],
        "nas_member_ids": "|".join(sorted(d["nasids"])),
        "english_labels": "|".join(sorted(d["labels"])),
        "has_non_deprecated_p569": int(bool(stmts)),
        "max_birthdate_precision": max(precisions) if precisions else "",
        "exact_day_values": "|".join(exact),
        "exact_day_value_count": len(exact),
        "exact_day_conflict": int(len(exact) > 1),
        "month_precision_values": "|".join(month),
        "year_precision_values": "|".join(year),
    })

out_csv = OUT / "nas_wikidata_dob_collapsed.csv"
fields = list(collapsed[0].keys()) if collapsed else []
with out_csv.open("w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    w.writerows(collapsed)

n = len(collapsed)
summary = {
    "source": "Wikidata via QLever",
    "endpoint": ENDPOINT,
    "property_nas_id": "P5380",
    "property_date_of_birth": "P569",
    "wikidata_persons_with_p5380": n,
    "persons_with_non_deprecated_p569": sum(int(x["has_non_deprecated_p569"]) for x in collapsed),
    "persons_with_exact_day_precision_11_or_better": sum(int(x["exact_day_value_count"] > 0) for x in collapsed),
    "persons_with_conflicting_exact_day_values": sum(int(x["exact_day_conflict"]) for x in collapsed),
    "persons_without_english_label": sum(int(not x["english_labels"]) for x in collapsed),
    "raw_result_rows": max(0, len(rows) - 1),
    "bazi_variables_computed": 0,
    "note": "Exact DOB availability requires Wikidata time precision >=11; deprecated birth-date statements are excluded. No BaZi variables are computed.",
}
(OUT / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
print(json.dumps(summary, indent=2))
