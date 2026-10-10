#!/usr/bin/env python3
from __future__ import annotations
import csv,hashlib,json
from collections import Counter,defaultdict
from pathlib import Path

IN=Path("data/leopoldina_detail_metadata_inputs_v1")
OUT=Path("data/leopoldina_roster_freeze_candidate_v1")
URLS=Path("data/leopoldina_roster_url_inventory_v1/leopoldina_science_classes_member_urls_through_2025_v1.csv")

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
    files=sorted(IN.rglob("detail_metadata_s*.csv"))
    if len(files)!=16: raise RuntimeError(f"Expected 16 shard CSVs, got {len(files)}")
    rows=[]
    for p in files: rows.extend(read_csv(p))
    urls=read_csv(URLS)
    if len(rows)!=2888 or len(urls)!=2888: raise RuntimeError(f"Row count mismatch details={len(rows)} urls={len(urls)}")
    if len({r["detail_url"] for r in rows})!=2888: raise RuntimeError("Duplicate detail URLs in detail metadata")
    if {r["detail_url"] for r in rows}!={r["detail_url"] for r in urls}: raise RuntimeError("Detail metadata URL set differs from frozen URL inventory")
    bad=[r for r in rows if r["error"] or r["http_status"]!="200" or not r["display_name"] or not r["section"] or not r["detail_election_year"] or r["election_year_matches_inventory"]!="1"]
    if bad: raise RuntimeError(f"Bad detail rows after consolidation: {len(bad)} first={bad[:3]}")
    # A section must map to exactly one official class.
    section_classes=defaultdict(set)
    for r in rows: section_classes[r["section"]].add(r["class"])
    ambiguous={s:sorted(v) for s,v in section_classes.items() if len(v)!=1}
    if ambiguous: raise RuntimeError(f"Section maps to multiple classes: {ambiguous}")
    section_rows=[]
    for s in sorted(section_classes):
        cls=next(iter(section_classes[s]))
        subset=[r for r in rows if r["section"]==s]
        section_rows.append({"section":s,"class":cls,"members_through_2025":len(subset),"deceased_marker":sum(int(r["deceased_marker"]) for r in subset)})
    # Heading-only honorary marker must be manually reviewed if present.
    honorary=[r for r in rows if r["heading_contains_honorary"]=="1"]
    roster=sorted(rows,key=lambda r:(int(r["class_index"]),int(r["election_year"]),r["display_name"],r["member_slug"]))
    rp=OUT/"leopoldina_science_core_roster_candidate_v1.csv"
    write_csv(rp,roster,list(roster[0].keys()))
    sp=OUT/"section_class_map_v1.csv"
    write_csv(sp,section_rows,["section","class","members_through_2025","deceased_marker"])
    hp=OUT/"honorary_heading_review_v1.csv"
    if honorary:
        write_csv(hp,honorary,list(honorary[0].keys()))
    else:
        write_csv(hp,[],list(roster[0].keys()))
    cc=Counter(r["class"] for r in roster)
    summary={
      "dataset":"Leopoldina Classes I-III roster freeze candidate v1",
      "primary_window":"election/admission through 2025; 2026 excluded upstream",
      "rows":len(roster),
      "unique_detail_urls":len({r["detail_url"] for r in roster}),
      "class_counts":dict(sorted(cc.items())),
      "sections":len(section_rows),
      "section_class_ambiguities":0,
      "http_or_field_errors":0,
      "election_year_mismatches":0,
      "deceased_marker_count":sum(int(r["deceased_marker"]) for r in roster),
      "active_without_deceased_marker":sum(int(r["deceased_marker"])==0 for r in roster),
      "honorary_heading_review_rows":len(honorary),
      "roster_csv_sha256":sha256(rp),
      "section_map_sha256":sha256(sp),
      "honorary_review_sha256":sha256(hp),
      "dob_lookup_performed":0,
      "bazi_variables_computed":0,
      "freeze_ready_if_honorary_review_clear":int(len(honorary)==0)
    }
    (OUT/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=="__main__":main()
