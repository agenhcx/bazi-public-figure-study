#!/usr/bin/env python3
from __future__ import annotations
import csv,json,re
from pathlib import Path

ROOT=Path("data")
NAMES=["Catherine Dulac","P. Roy Vagelos","Debra Ann Fischer","T. Mark Harrison","Amita Sehgal"]
OUT=ROOT/"nas_viaf_validation_conflict_master_provenance_v1.json"

def locate(name):
    p=ROOT/name
    if p.exists():return p
    for x in ROOT.rglob(name):return x
    raise FileNotFoundError(name)

def read_csv(p):
    with p.open("r",encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))

v16=read_csv(locate("nas_science_core_dob_crosswalk_v16.csv"))
viaf=read_csv(locate("nas_viaf_dob_diagnostic_v1.csv"))
vmap={r.get("name",""):r for r in v16}
xmap={r.get("name",""):r for r in viaf if r.get("cohort")=="validation"}

keep_re=re.compile(r"(dob|birth|source|proven|url|qid|status|note|candidate|manual|wikipedia|wikidata|loc|gnd|bnf|authority|official|supplement|basis)",re.I)
out=[]
for name in NAMES:
    vr=vmap.get(name,{})
    xr=xmap.get(name,{})
    master={k:v for k,v in vr.items() if str(v or "").strip() and (keep_re.search(k) or k in {"name","election_year","affiliation","deceased","final_exact_dob"})}
    via={k:v for k,v in xr.items() if str(v or "").strip() and (keep_re.search(k) or k in {"name","viaf_candidate_dob","master_exact_dob","validation_match","contributing_authority_sids"})}
    out.append({"name":name,"v16":master,"viaf_validation":via})
payload={"dataset":"NAS VIAF validation-conflict master-provenance audit v1","rows":out,"bazi_variables_computed":0}
OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(payload,ensure_ascii=False,indent=2))
