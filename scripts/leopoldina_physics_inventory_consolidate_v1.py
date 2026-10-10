#!/usr/bin/env python3
from __future__ import annotations
import csv,hashlib,json
from collections import Counter
from pathlib import Path
IN=Path("data/leopoldina_physics_inventory_inputs_v1");OUT=Path("data/leopoldina_physics_inventory_v1")
def read(p):
    with p.open("r",encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
def write(p,rows,fields):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open("w",encoding="utf-8-sig",newline="") as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
def sha(p):
    import hashlib
    h=hashlib.sha256()
    with p.open("rb") as f:
        for c in iter(lambda:f.read(1<<20),b""):h.update(c)
    return h.hexdigest()
def main():
    bfs=sorted(IN.rglob("buckets_s*.csv"));mfs=sorted(IN.rglob("members_s*.csv"))
    if len(bfs)!=4 or len(mfs)!=4:raise RuntimeError(f"Expected 4/4 shards got {len(bfs)}/{len(mfs)}")
    b=[];m=[]
    for p in bfs:b+=read(p)
    for p in mfs:m+=read(p)
    if sum(int(x["official_total"]) for x in b)!=383:raise RuntimeError("Physics year buckets do not reconcile to official facet 383")
    urls=[x["detail_url"] for x in m]
    if len(m)!=383 or len(set(urls))!=383:raise RuntimeError(f"Physics URL invariant failed {len(m)}/{len(set(urls))}")
    p2026=[x for x in m if int(x["election_year"])==2026]
    primary=[x for x in m if int(x["election_year"])<=2025]
    if not any("reinhard-genzel" in x["detail_url"] and x["election_year"]=="2002" for x in primary):raise RuntimeError("Reinhard Genzel missing from corrected Physics inventory")
    if not any("peter-fulde" in x["detail_url"] and x["election_year"]=="1995" for x in primary):raise RuntimeError("Peter Fulde missing from corrected Physics inventory")
    pp=OUT/"physics_member_urls_through_2025_v1.csv";write(pp,sorted(primary,key=lambda x:(int(x["election_year"]),x["member_slug"])),["election_year","primary_window","member_slug","detail_url"])
    xp=OUT/"physics_2026_excluded_v1.csv";write(xp,p2026,["election_year","primary_window","member_slug","detail_url"])
    bp=OUT/"physics_year_bucket_audit_v1.csv";write(bp,sorted(b,key=lambda x:int(x["year"])),["year","official_total","returned","primary_window"])
    summary={"dataset":"Leopoldina Physics section correction inventory v1","official_physics_facet_total":383,"through_2025":len(primary),"election_2026_excluded":len(p2026),"duplicates":0,"genzel_2002_present":1,"fulde_1995_present":1,"primary_csv_sha256":sha(pp),"bucket_audit_sha256":sha(bp),"bazi_variables_computed":0}
    (OUT/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8");print(json.dumps(summary,indent=2))
if __name__=="__main__":main()
