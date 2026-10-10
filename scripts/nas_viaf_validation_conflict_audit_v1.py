#!/usr/bin/env python3
from __future__ import annotations
import csv,json,re,urllib.request
from pathlib import Path

ROOT=Path("data")
NAMES=["Catherine Dulac","P. Roy Vagelos","Debra Ann Fischer","T. Mark Harrison","Amita Sehgal"]
OUT=ROOT/"nas_viaf_validation_conflict_master_provenance_v1.json"
UA="bazi-public-figure-study/1.0 (Wikidata P569 conflict provenance audit; no BaZi computation)"

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

def entity(qid):
    req=urllib.request.Request(f"https://www.wikidata.org/wiki/Special:EntityData/{qid}.json",headers={"User-Agent":UA,"Accept":"application/json"})
    with urllib.request.urlopen(req,timeout=30) as r:return json.loads(r.read().decode("utf-8"))["entities"][qid]

def ref_value(snak):
    try:return snak["datavalue"]["value"]
    except:return None

def p569_provenance(qid):
    ent=entity(qid);out=[]
    for claim in (ent.get("claims") or {}).get("P569",[]):
        try:
            dv=claim["mainsnak"]["datavalue"]["value"]
            date=str(dv.get("time","")).lstrip("+")[:10]
            precision=dv.get("precision")
        except Exception:
            date="";precision=None
        refs=[]
        for ref in claim.get("references",[]) or []:
            rd={}
            for prop,snaks in (ref.get("snaks") or {}).items():
                vals=[]
                for s in snaks:
                    v=ref_value(s)
                    if isinstance(v,dict) and "id" in v:v=v["id"]
                    elif isinstance(v,dict) and "time" in v:v=v["time"]
                    vals.append(v)
                rd[prop]=vals
            refs.append(rd)
        out.append({"date":date,"precision":precision,"rank":claim.get("rank"),"references":refs})
    return out

out=[]
for name in NAMES:
    vr=vmap.get(name,{})
    xr=xmap.get(name,{})
    master={k:v for k,v in vr.items() if str(v or "").strip() and (keep_re.search(k) or k in {"name","election_year","affiliation","deceased","final_exact_dob"})}
    via={k:v for k,v in xr.items() if str(v or "").strip() and (keep_re.search(k) or k in {"name","viaf_candidate_dob","master_exact_dob","validation_match","contributing_authority_sids"})}
    qid=vr.get("wikidata_qid") or vr.get("global_candidate_qid") or ""
    try:wdrefs=p569_provenance(qid) if qid else []
    except Exception as e:wdrefs=[{"fetch_error":repr(e)}]
    out.append({"name":name,"v16":master,"viaf_validation":via,"current_wikidata_p569_provenance":wdrefs})
payload={"dataset":"NAS VIAF validation-conflict master-provenance audit v1","rows":out,"bazi_variables_computed":0}
OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(payload,ensure_ascii=False,indent=2))
