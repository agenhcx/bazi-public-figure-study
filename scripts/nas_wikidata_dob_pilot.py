#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import re
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path

ENDPOINT = "https://qlever.dev/api/wikidata"
OUT = Path("data/nas_wikidata_dob_pilot")
OUT.mkdir(parents=True, exist_ok=True)

P5380_QUERY = r"""
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
SELECT ?person ?nasid WHERE {
  ?person wdt:P5380 ?nasid .
}
ORDER BY ?person ?nasid
"""

LABEL_QUERY = r"""
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?person ?label WHERE {
  ?person wdt:P5380 ?nasid ;
          rdfs:label ?label .
  FILTER(LANG(?label) = "en")
}
ORDER BY ?person
"""

DOB_QUERY = r"""
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX p: <http://www.wikidata.org/prop/>
PREFIX ps: <http://www.wikidata.org/prop/statement/>
PREFIX psv: <http://www.wikidata.org/prop/statement/value/>
PREFIX wikibase: <http://wikiba.se/ontology#>
SELECT ?person ?dob ?precision ?rank WHERE {
  ?person wdt:P5380 ?nasid ;
          p:P569 ?dob_stmt .
  ?dob_stmt ps:P569 ?dob ;
            psv:P569 ?dob_value ;
            wikibase:rank ?rank .
  FILTER(?rank != wikibase:DeprecatedRank)
  ?dob_value wikibase:timePrecision ?precision .
}
ORDER BY ?person
"""

def run_sparql(query: str) -> bytes:
    body = urllib.parse.urlencode({
        "query": query,
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
    s=(s or "").strip()
    if s.startswith("<") and s.endswith(">"):
        return s[1:-1]
    if len(s)>=2 and s[0]=='"' and '"' in s[1:]:
        end=s.rfind('"')
        return s[1:end].replace('\\t','\t').replace('\\n','\n').replace('\\r','\r').replace('\\\"','"').replace('\\\\','\\')
    # QLever TSV currently serializes simple language-tagged strings as Label@en.
    s=re.sub(r"@[A-Za-z][A-Za-z0-9-]*$", "", s)
    return s

def precision_int(s: str):
    try:
        return int(clean_term(s))
    except Exception:
        return None

def parse_tsv(raw: bytes):
    rows=list(csv.reader(raw.decode("utf-8-sig").splitlines(), delimiter="\t"))
    if not rows:
        raise RuntimeError("QLever returned no rows.")
    headers=[clean_header(x) for x in rows[0]]
    out=[]
    for r in rows[1:]:
        if not r:
            continue
        r=r+[""]*(len(headers)-len(r))
        out.append({h:clean_term(r[i]) for i,h in enumerate(headers)})
    return headers,out

raw_ids=run_sparql(P5380_QUERY)
raw_labels=run_sparql(LABEL_QUERY)
raw_dob=run_sparql(DOB_QUERY)

(OUT/"wikidata_p5380_raw.tsv").write_bytes(raw_ids)
(OUT/"wikidata_p5380_labels_raw.tsv").write_bytes(raw_labels)
(OUT/"wikidata_p5380_p569_raw.tsv").write_bytes(raw_dob)

h_ids,id_rows=parse_tsv(raw_ids)
h_labels,label_rows=parse_tsv(raw_labels)
h_dob,dob_rows=parse_tsv(raw_dob)

if not {"person","nasid"}.issubset(h_ids):
    raise RuntimeError(f"Unexpected P5380 headers: {h_ids}")
if not {"person","label"}.issubset(h_labels):
    raise RuntimeError(f"Unexpected label headers: {h_labels}")
if not {"person","dob","precision","rank"}.issubset(h_dob):
    raise RuntimeError(f"Unexpected DOB headers: {h_dob}")

people=defaultdict(lambda:{"nasids":set(),"labels":set(),"statements":[]})

for r in id_rows:
    person=r.get("person","")
    if not person:
        continue
    if r.get("nasid"):
        people[person]["nasids"].add(r["nasid"])

for r in label_rows:
    person=r.get("person","")
    if person in people and r.get("label"):
        people[person]["labels"].add(r["label"])

for r in dob_rows:
    person=r.get("person","")
    if person not in people:
        continue
    p=precision_int(r.get("precision",""))
    dob=r.get("dob","")
    rank=r.get("rank","")
    if dob and p is not None:
        people[person]["statements"].append((dob,p,rank))

collapsed=[]
for person,d in sorted(people.items()):
    stmts=d["statements"]
    exact=sorted({dob for dob,p,rank in stmts if p>=11})
    month=sorted({dob for dob,p,rank in stmts if p==10})
    year=sorted({dob for dob,p,rank in stmts if p==9})
    precisions=sorted({p for _,p,_ in stmts})
    collapsed.append({
        "wikidata_uri":person,
        "qid":person.rsplit("/",1)[-1],
        "nas_member_ids":"|".join(sorted(d["nasids"])),
        "english_labels":"|".join(sorted(d["labels"])),
        "has_non_deprecated_p569":int(bool(stmts)),
        "max_birthdate_precision":max(precisions) if precisions else "",
        "exact_day_values":"|".join(exact),
        "exact_day_value_count":len(exact),
        "exact_day_conflict":int(len(exact)>1),
        "month_precision_values":"|".join(month),
        "year_precision_values":"|".join(year),
    })

out_csv=OUT/"nas_wikidata_dob_collapsed.csv"
fields=list(collapsed[0].keys()) if collapsed else []
with out_csv.open("w",encoding="utf-8-sig",newline="") as f:
    w=csv.DictWriter(f,fieldnames=fields)
    w.writeheader(); w.writerows(collapsed)

summary={
    "source":"Wikidata via QLever",
    "endpoint":ENDPOINT,
    "query_strategy":"three independent mandatory queries joined locally: P5380 identity, English label, P569 statement/precision",
    "property_nas_id":"P5380",
    "property_date_of_birth":"P569",
    "wikidata_persons_with_p5380":len(collapsed),
    "persons_with_english_label":sum(bool(x["english_labels"]) for x in collapsed),
    "persons_with_non_deprecated_p569":sum(int(x["has_non_deprecated_p569"]) for x in collapsed),
    "persons_with_exact_day_precision_11_or_better":sum(int(x["exact_day_value_count"]>0) for x in collapsed),
    "persons_with_conflicting_exact_day_values":sum(int(x["exact_day_conflict"]) for x in collapsed),
    "raw_p5380_rows":len(id_rows),
    "raw_label_rows":len(label_rows),
    "raw_p569_rows":len(dob_rows),
    "sample_labels":[x["english_labels"] for x in collapsed if x["english_labels"]][:5],
    "bazi_variables_computed":0,
    "note":"Exact DOB requires Wikidata time precision >=11. Deprecated P569 statements are excluded. No BaZi variables are computed."
}
(OUT/"summary.json").write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding="utf-8")
print(json.dumps(summary,indent=2,ensure_ascii=False))
