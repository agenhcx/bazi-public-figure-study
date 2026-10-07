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

P463_QUERY = r"""
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX wd: <http://www.wikidata.org/entity/>
SELECT DISTINCT ?person WHERE {
  ?person wdt:P463 wd:Q270794 .
}
ORDER BY ?person
"""

P166_QUERY = r"""
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX wd: <http://www.wikidata.org/entity/>
SELECT DISTINCT ?person WHERE {
  ?person wdt:P166 wd:Q63315195 .
}
ORDER BY ?person
"""

CANDIDATE_PATTERN = r"""
  {
    ?person wdt:P5380 ?nasid .
  } UNION {
    ?person wdt:P463 wd:Q270794 .
  } UNION {
    ?person wdt:P166 wd:Q63315195 .
  }
"""

LABEL_QUERY = r"""
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT DISTINCT ?person ?label WHERE {
""" + CANDIDATE_PATTERN + r"""
  ?person rdfs:label ?label .
  FILTER(LANG(?label) = "en")
}
ORDER BY ?person
"""

ALT_LABEL_QUERY = r"""
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
SELECT DISTINCT ?person ?label WHERE {
""" + CANDIDATE_PATTERN + r"""
  ?person skos:altLabel ?label .
  FILTER(LANG(?label) = "en")
}
ORDER BY ?person
"""

DOB_QUERY = r"""
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX p: <http://www.wikidata.org/prop/>
PREFIX psv: <http://www.wikidata.org/prop/statement/value/>
PREFIX wikibase: <http://wikiba.se/ontology#>
SELECT DISTINCT ?person ?dob ?precision WHERE {
""" + CANDIDATE_PATTERN + r"""
  ?person p:P569 ?dob_stmt .
  ?dob_stmt psv:P569 ?dob_value .
  ?dob_value wikibase:timeValue ?dob ;
             wikibase:timePrecision ?precision .
}
ORDER BY ?person
"""

def run_sparql(query: str) -> bytes:
    body=urllib.parse.urlencode({"query":query,"action":"tsv_export"}).encode("utf-8")
    req=urllib.request.Request(
        ENDPOINT,data=body,method="POST",
        headers={
            "User-Agent":"bazi-public-figure-study/1.0 (NAS DOB coverage pilot)",
            "Content-Type":"application/x-www-form-urlencoded",
            "Accept":"text/tab-separated-values",
        },
    )
    with urllib.request.urlopen(req,timeout=300) as resp:
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
    return re.sub(r"@[A-Za-z][A-Za-z0-9-]*$","",s)

def precision_int(s: str):
    try: return int(clean_term(s))
    except Exception: return None

def parse_tsv(raw: bytes):
    rows=list(csv.reader(raw.decode("utf-8-sig").splitlines(),delimiter="\t"))
    if not rows:
        raise RuntimeError("QLever returned no rows.")
    headers=[clean_header(x) for x in rows[0]]
    out=[]
    for r in rows[1:]:
        if not r: continue
        r=r+[""]*(len(headers)-len(r))
        out.append({h:clean_term(r[i]) for i,h in enumerate(headers)})
    return headers,out

raw_p5380=run_sparql(P5380_QUERY)
raw_p463=run_sparql(P463_QUERY)
raw_p166=run_sparql(P166_QUERY)
raw_labels=run_sparql(LABEL_QUERY)
raw_alt=run_sparql(ALT_LABEL_QUERY)
raw_dob=run_sparql(DOB_QUERY)

raw_files={
    "wikidata_p5380_raw.tsv":raw_p5380,
    "wikidata_p463_nas_raw.tsv":raw_p463,
    "wikidata_p166_mnas_raw.tsv":raw_p166,
    "wikidata_nas_labels_raw.tsv":raw_labels,
    "wikidata_nas_altlabels_raw.tsv":raw_alt,
    "wikidata_nas_p569_raw.tsv":raw_dob,
}
for name,data in raw_files.items():
    (OUT/name).write_bytes(data)

h5380,r5380=parse_tsv(raw_p5380)
h463,r463=parse_tsv(raw_p463)
h166,r166=parse_tsv(raw_p166)
hlab,rlab=parse_tsv(raw_labels)
halt,ralt=parse_tsv(raw_alt)
hdob,rdob=parse_tsv(raw_dob)

if not {"person","nasid"}.issubset(h5380): raise RuntimeError(f"Unexpected P5380 headers: {h5380}")
if "person" not in h463: raise RuntimeError(f"Unexpected P463 headers: {h463}")
if "person" not in h166: raise RuntimeError(f"Unexpected P166 headers: {h166}")
if not {"person","label"}.issubset(hlab): raise RuntimeError(f"Unexpected label headers: {hlab}")
if not {"person","label"}.issubset(halt): raise RuntimeError(f"Unexpected alt-label headers: {halt}")
if not {"person","dob","precision"}.issubset(hdob): raise RuntimeError(f"Unexpected DOB headers: {hdob}")

people=defaultdict(lambda:{
    "nasids":set(),"labels":set(),"preferred_labels":set(),"alt_labels":set(),
    "sources":set(),"statements":[]
})

for r in r5380:
    p=r.get("person","")
    if not p: continue
    people[p]["sources"].add("P5380")
    if r.get("nasid"): people[p]["nasids"].add(r["nasid"])
for r in r463:
    p=r.get("person","")
    if p: people[p]["sources"].add("P463_NAS")
for r in r166:
    p=r.get("person","")
    if p: people[p]["sources"].add("P166_MNAS")
for r in rlab:
    p=r.get("person",""); label=r.get("label","")
    if p in people and label:
        people[p]["labels"].add(label); people[p]["preferred_labels"].add(label)
for r in ralt:
    p=r.get("person",""); label=r.get("label","")
    if p in people and label:
        people[p]["labels"].add(label); people[p]["alt_labels"].add(label)
for r in rdob:
    p=r.get("person","")
    if p not in people: continue
    prec=precision_int(r.get("precision","")); dob=r.get("dob","")
    if dob and prec is not None: people[p]["statements"].append((dob,prec))

collapsed=[]
for person,d in sorted(people.items()):
    stmts=d["statements"]
    exact=sorted({dob for dob,p in stmts if p>=11})
    month=sorted({dob for dob,p in stmts if p==10})
    year=sorted({dob for dob,p in stmts if p==9})
    precisions=sorted({p for _,p in stmts})
    collapsed.append({
        "wikidata_uri":person,
        "qid":person.rsplit("/",1)[-1],
        "membership_sources":"|".join(sorted(d["sources"])),
        "nas_member_ids":"|".join(sorted(d["nasids"])),
        "english_labels":"|".join(sorted(d["labels"])),
        "preferred_english_labels":"|".join(sorted(d["preferred_labels"])),
        "english_alt_labels":"|".join(sorted(d["alt_labels"])),
        "has_p569":int(bool(stmts)),
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
    w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(collapsed)

p5380_people={r["person"] for r in r5380 if r.get("person")}
p463_people={r["person"] for r in r463 if r.get("person")}
p166_people={r["person"] for r in r166 if r.get("person")}
summary={
    "source":"Wikidata via QLever",
    "endpoint":ENDPOINT,
    "candidate_universe":"P5380 OR P463=Q270794 OR P166=Q63315195",
    "wikidata_candidate_persons":len(collapsed),
    "persons_from_p5380":len(p5380_people),
    "persons_from_p463_nas":len(p463_people),
    "persons_from_p166_mnas":len(p166_people),
    "persons_with_any_english_label_or_altlabel":sum(bool(x["english_labels"]) for x in collapsed),
    "persons_with_p569":sum(int(x["has_p569"]) for x in collapsed),
    "persons_with_exact_day_precision_11_or_better":sum(int(x["exact_day_value_count"]>0) for x in collapsed),
    "persons_with_conflicting_exact_day_values":sum(int(x["exact_day_conflict"]) for x in collapsed),
    "raw_p5380_rows":len(r5380),
    "raw_p463_rows":len(r463),
    "raw_p166_rows":len(r166),
    "raw_label_rows":len(rlab),
    "raw_altlabel_rows":len(ralt),
    "raw_p569_rows":len(rdob),
    "sample_labels":[x["english_labels"] for x in collapsed if x["english_labels"]][:5],
    "bazi_variables_computed":0,
    "note":"P569 exact day requires precision >=11. Multiple exact values are retained as conflicts. No BaZi variables are computed."
}
(OUT/"summary.json").write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding="utf-8")
print(json.dumps(summary,indent=2,ensure_ascii=False))
