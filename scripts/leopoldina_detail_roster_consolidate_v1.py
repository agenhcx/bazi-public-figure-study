#!/usr/bin/env python3
from __future__ import annotations
import csv,hashlib,json,re
from collections import Counter,defaultdict
from pathlib import Path

INVENTORY=Path("data/leopoldina_detail_input_v1/leopoldina_science_classes_member_urls_through_2025_v1.csv")
SHARDS=Path("data/leopoldina_detail_shards_input_v1")
OUT=Path("data/leopoldina_roster_freeze_v1")

def read_csv(p):
    with p.open("r",encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
def write_csv(p,rows,fields):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
def sha256(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for c in iter(lambda:f.read(1<<20),b""):h.update(c)
    return h.hexdigest()

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    inv=read_csv(INVENTORY)
    files=sorted(SHARDS.rglob("detail_shard_*.csv"))
    if len(files)!=12:raise RuntimeError(f"Expected 12 detail shards, got {len(files)}")
    rows=[]
    for p in files:rows.extend(read_csv(p))
    if len(inv)!=2888 or len(rows)!=2888:raise RuntimeError(f"Row invariant failed inventory={len(inv)} details={len(rows)}")
    inv_urls={r["detail_url"] for r in inv}; out_urls=[r["detail_url"] for r in rows]
    if set(out_urls)!=inv_urls or len(set(out_urls))!=2888:raise RuntimeError("Detail URL coverage does not match frozen inventory")
    bad=[r for r in rows if r["parse_ok"]!="1" or r["election_year_matches_inventory"]!="1" or r["http_status"]!="200"]
    if bad:raise RuntimeError(f"Detail parse failures remain: {len(bad)}")
    # Every section must map to exactly one frozen class; this also audits the class assignment.
    sec_classes=defaultdict(set); sec_counts=Counter()
    for r in rows:
        sec_classes[r["section"]].add(r["class"]);sec_counts[(r["class"],r["section"])]+=1
    ambiguous={s:sorted(v) for s,v in sec_classes.items() if len(v)!=1}
    if ambiguous:raise RuntimeError(f"Sections map to multiple classes: {ambiguous}")
    rows=sorted(rows,key=lambda r:(int(r["class_index"]),int(r["election_year"]),r["display_name"],r["member_slug"]))
    roster=[]
    for r in rows:
        roster.append({
          "cohort_key":"LEO_"+r["member_slug"],
          "display_name":r["display_name"],
          "status_at_source":"deceased" if r["deceased"]=="1" else "current",
          "membership_category":"Member",
          "class":r["class"],
          "section":r["section"],
          "election_year":r["election_year"],
          "location":r["location"],
          "source_url":r["detail_url"],
          "primary_cohort":1
        })
    if len({r["cohort_key"] for r in roster})!=2888:raise RuntimeError("Cohort keys are not unique")
    rp=OUT/"leopoldina_science_core_roster_freeze_v1.csv"
    write_csv(rp,roster,["cohort_key","display_name","status_at_source","membership_category","class","section","election_year","location","source_url","primary_cohort"])
    sm=[]
    for (c,s),n in sorted(sec_counts.items()):
        sm.append({"class":c,"section":s,"members":n})
    sp=OUT/"section_class_audit_v1.csv"
    write_csv(sp,sm,["class","section","members"])
    by_class=Counter(r["class"] for r in roster); by_status=Counter(r["status_at_source"] for r in roster)
    summary={
      "dataset":"Leopoldina primary science-core roster freeze v1",
      "cohort_definition":"Official Leopoldina member directory; Classes I-III only; election year through 2025; all countries retained because Leopoldina membership is international.",
      "rows":len(roster),
      "class_counts":dict(sorted(by_class.items())),
      "status_counts":dict(sorted(by_status.items())),
      "section_count":len(sec_classes),
      "section_to_class_ambiguous":0,
      "http_parse_failures":0,
      "election_year_mismatches":0,
      "honorary_membership_rule":"Leopoldina honorary membership is an Academy distinction awarded to existing members, not a separate admission category; later honorary distinction does not remove an otherwise eligible Member from the primary cohort.",
      "roster_csv_sha256":sha256(rp),
      "section_audit_sha256":sha256(sp),
      "dob_lookup_performed":0,
      "bazi_variables_computed":0,
      "freeze_status":"roster_frozen_dob_not_started"
    }
    (OUT/"manifest.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
