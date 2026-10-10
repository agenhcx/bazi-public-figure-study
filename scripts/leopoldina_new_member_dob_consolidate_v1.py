#!/usr/bin/env python3
from __future__ import annotations
import csv,hashlib,json
from collections import Counter
from pathlib import Path

IN=Path("data/leopoldina_new_member_dob_inputs_v1")
OUT=Path("data/leopoldina_new_member_dob_official_v1")
YEARS=list(range(2009,2020))

def read_csv(p):
    with p.open("r",encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
def write_csv(p,rows,fields):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore");w.writeheader();w.writerows(rows)
def sha256(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for c in iter(lambda:f.read(1<<20),b""):h.update(c)
    return h.hexdigest()

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    rows=[]; summaries=[]
    for y in YEARS:
        fs=list(IN.rglob(f"dob_candidates_{y}.csv"))
        ss=list(IN.rglob(f"summary_{y}.json"))
        if len(fs)!=1 or len(ss)!=1:raise RuntimeError(f"Missing/duplicate shard for {y}: csv={fs} summary={ss}")
        rows.extend(read_csv(fs[0]));summaries.append(json.loads(ss[0].read_text(encoding="utf-8")))
    if len({r["member_slug"] for r in rows})!=len(rows):raise RuntimeError("Duplicate member slugs across election years")
    conflicts=[r for r in rows if r["decision"]=="conflict_review"]
    if conflicts:raise RuntimeError(f"Conflicts survived shards: {len(conflicts)}")
    accepted=sorted([r for r in rows if r["decision"]=="accept_official_new_member_profile_exact_dob"],key=lambda r:(int(r["election_year"]),r["member_slug"]))
    unresolved=sorted([r for r in rows if r["decision"]!="accept_official_new_member_profile_exact_dob"],key=lambda r:(int(r["election_year"]),r["member_slug"]))
    fields=list(rows[0].keys())
    ap=OUT/"accepted_exact_dob_2009_2019_v1.csv";write_csv(ap,accepted,fields)
    up=OUT/"unresolved_2009_2019_v1.csv";write_csv(up,unresolved,fields)
    yp=OUT/"year_summary_v1.csv"
    yr=[{"election_year":s["election_year"],"roster_targets":s["roster_targets"],"accepted_exact_dob":s["accepted_exact_dob"],"unresolved":s["unresolved"],"pdf_url":s["pdf_url"]} for s in summaries]
    write_csv(yp,yr,["election_year","roster_targets","accepted_exact_dob","unresolved","pdf_url"])
    summary={
      "dataset":"Leopoldina official new-member exact-DOB consolidated v1",
      "election_years":"2009-2019","roster_targets":len(rows),"accepted_exact_dob":len(accepted),"unresolved":len(unresolved),
      "coverage":round(len(accepted)/len(rows),6) if rows else 0,
      "accepted_csv_sha256":sha256(ap),"unresolved_csv_sha256":sha256(up),"year_summary_sha256":sha256(yp),
      "source_class":"official Leopoldina new-member volumes","bazi_variables_computed":0
    }
    (OUT/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=="__main__":main()
