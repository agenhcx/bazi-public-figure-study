#!/usr/bin/env python3
from __future__ import annotations
import csv,hashlib,json,re
from pathlib import Path

BASE=Path("data/leopoldina_roster_freeze_v1")
ROSTER=BASE/"leopoldina_science_core_roster_freeze_v1.csv"
MANIFEST=BASE/"manifest.json"
AUDIT=BASE/"location_parser_cleanup_audit_v1.csv"

def read_csv(p):
    with p.open("r",encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
def write_csv(p,rows,fields):
    with p.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
def sha256(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for c in iter(lambda:f.read(1<<20),b""):h.update(c)
    return h.hexdigest()

def main():
    rows=read_csv(ROSTER)
    if len(rows)!=2888:raise RuntimeError(f"Expected 2888 roster rows, got {len(rows)}")
    audit=[]
    for r in rows:
        loc=r["location"]
        m=re.fullmatch(r"(.*?)(?:\s+Election year\s+(\d{4}))",loc)
        if m:
            clean=m.group(1).strip(); y=m.group(2)
            if y!=r["election_year"]:
                raise RuntimeError(f"Location suffix year mismatch {r['cohort_key']}: {y} vs {r['election_year']}")
            audit.append({"cohort_key":r["cohort_key"],"display_name":r["display_name"],"election_year":r["election_year"],"old_location":loc,"new_location":clean})
            r["location"]=clean
    if len(audit)!=1894:
        raise RuntimeError(f"Expected 1894 deterministic location cleanups, got {len(audit)}")
    if any("Election year" in r["location"] for r in rows):
        raise RuntimeError("Location contamination remains after cleanup")
    fields=list(rows[0].keys())
    write_csv(ROSTER,rows,fields)
    write_csv(AUDIT,audit,["cohort_key","display_name","election_year","old_location","new_location"])
    m=json.loads(MANIFEST.read_text(encoding="utf-8"))
    m["roster_csv_sha256"]=sha256(ROSTER)
    m["location_parser_cleanup"]={
      "changed_rows":len(audit),
      "rule":"Strip parser-introduced suffix 'Election year YYYY' from location only when YYYY exactly equals the frozen row election_year.",
      "source_membership_changed":0,
      "class_or_section_changed":0,
      "election_year_changed":0,
      "status_changed":0,
      "audit_csv_sha256":sha256(AUDIT)
    }
    MANIFEST.write_text(json.dumps(m,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"changed_rows":len(audit),"roster_csv_sha256":m["roster_csv_sha256"],"audit_csv_sha256":m["location_parser_cleanup"]["audit_csv_sha256"],"bazi_variables_computed":m["bazi_variables_computed"]},indent=2))

if __name__=="__main__":main()
