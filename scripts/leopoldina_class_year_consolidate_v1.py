#!/usr/bin/env python3
from __future__ import annotations
import csv,hashlib,json
from collections import Counter,defaultdict
from pathlib import Path

IN=Path("data/leopoldina_class_year_inventory_inputs_v1")
OUT=Path("data/leopoldina_roster_url_inventory_v1")
EXPECTED_CLASSES={
 "Class I: Mathematics, Natural Sciences and Engineering":1139,
 "Class II: Life Sciences":967,
 "Class III: Medicine":822,
}

def read_csv(p):
    with p.open("r",encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
def sha256(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for c in iter(lambda:f.read(1<<20),b""):h.update(c)
    return h.hexdigest()
def write_csv(p,rows,fields):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    bfs=sorted(IN.rglob("buckets_c*_s*.csv")); mfs=sorted(IN.rglob("members_c*_s*.csv"))
    if len(bfs)!=12 or len(mfs)!=12: raise RuntimeError(f"Expected 12 bucket/member shard files, got {len(bfs)}/{len(mfs)}")
    buckets=[]; members=[]
    for p in bfs:buckets.extend(read_csv(p))
    for p in mfs:members.extend(read_csv(p))
    years=sorted({int(r["year"]) for r in buckets})
    classes=sorted({r["class"] for r in buckets})
    if len(classes)!=3 or 2025 not in years:raise RuntimeError("Class/year inventory incomplete")
    # each class must have exactly one bucket per observed election year
    seen=Counter((r["class"],int(r["year"])) for r in buckets)
    bad=[k for k,v in seen.items() if v!=1]
    if bad or len(buckets)!=3*len(years):raise RuntimeError(f"Bucket coverage mismatch bad={bad[:10]} rows={len(buckets)} years={len(years)}")
    class_all=defaultdict(int); class_primary=defaultdict(int); class_2026=defaultdict(int)
    for r in buckets:
        c=r["class"]; y=int(r["year"]); n=int(r["official_total"])
        class_all[c]+=n
        if y<=2025:class_primary[c]+=n
        if y==2026:class_2026[c]+=n
    # all dated members should reconcile to class facets; any gap means members lacking election-year facet.
    gaps={c:EXPECTED_CLASSES[c]-class_all[c] for c in EXPECTED_CLASSES}
    if any(v!=0 for v in gaps.values()):
        raise RuntimeError(f"Class totals do not reconcile to election-year buckets: all={dict(class_all)} gaps={gaps}")
    urls=[r["detail_url"] for r in members]
    dup=[u for u,v in Counter(urls).items() if v>1]
    if dup:raise RuntimeError(f"Duplicate member URLs across class-year buckets: {dup[:20]}")
    if len(members)!=sum(class_all.values()):raise RuntimeError("Member rows do not equal bucket totals")
    primary=sorted([r for r in members if int(r["election_year"])<=2025],key=lambda r:(int(r["class_index"]),int(r["election_year"]),r["member_slug"]))
    post2025=sorted([r for r in members if int(r["election_year"])>2025],key=lambda r:(int(r["class_index"]),int(r["election_year"]),r["member_slug"]))
    pp=OUT/"leopoldina_science_classes_member_urls_through_2025_v1.csv"
    write_csv(pp,primary,["class_index","class","election_year","primary_window","member_slug","detail_url"])
    xp=OUT/"post2025_excluded_member_urls_v1.csv"
    write_csv(xp,post2025,["class_index","class","election_year","primary_window","member_slug","detail_url"])
    bp=OUT/"class_year_bucket_audit_v1.csv"
    write_csv(bp,sorted(buckets,key=lambda r:(int(r["class_index"]),int(r["year"]))),["class_index","class","year","official_total","returned","primary_window"])
    summary={
      "dataset":"Leopoldina science Classes I-III official member URL inventory v1",
      "source":"Official Leopoldina member directory via POST class + electionYear buckets, avoiding WAF-blocked pagination queries.",
      "observed_election_years":len(years),
      "election_year_min":min(years),"election_year_max":max(years),
      "class_facet_totals":EXPECTED_CLASSES,
      "class_all_year_bucket_totals":dict(class_all),
      "class_through_2025_totals":dict(class_primary),
      "class_2026_excluded_totals":dict(class_2026),
      "all_classified_science_member_urls":len(members),
      "primary_member_urls_through_2025":len(primary),
      "post2025_excluded":len(post2025),
      "class_year_reconciliation_gaps":gaps,
      "duplicate_urls":0,
      "primary_csv_sha256":sha256(pp),
      "post2025_csv_sha256":sha256(xp),
      "bucket_audit_sha256":sha256(bp),
      "dob_lookup_performed":0,
      "bazi_variables_computed":0,
      "next_step":"Fetch official member detail pages for frozen URL universe; parse section, election metadata, deceased status, and membership-category clues before DOB collection."
    }
    (OUT/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=="__main__":main()
