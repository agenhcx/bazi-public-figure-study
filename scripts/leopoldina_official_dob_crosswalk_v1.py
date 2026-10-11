#!/usr/bin/env python3
from __future__ import annotations
import csv,hashlib,json
from collections import Counter,defaultdict
from pathlib import Path

ROSTER=Path("data/leopoldina_roster_freeze_v1/leopoldina_science_core_roster_freeze_v1.csv")
STATIC=Path("data/leopoldina_official_static_dob_v1/accepted_exact_dob_static_volumes_v1.csv")
STRUCT=Path("data/leopoldina_structure_row_dob_accepted_v1/accepted_exact_dob_structure_tables_v1.csv")
DETAIL=Path("data/leopoldina_detail_birthphrase_dob_accepted_v1/accepted_exact_dob_detail_birthphrases_v1.csv")
OUT=Path("data/leopoldina_dob_crosswalk_v1")

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
def era(y):
    y=int(y)
    if y<1900:return "pre-1900"
    if y<1950:return "1900-1949"
    if y<1980:return "1950-1979"
    if y<2000:return "1980-1999"
    if y<2010:return "2000-2009"
    if y<2020:return "2010-2019"
    return "2020-2025"

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    roster=read_csv(ROSTER)
    if len(roster)!=2888 or len({r["member_slug"] for r in roster})!=2888:raise RuntimeError("Frozen roster invariant failed")
    source_rows=[]
    for source,p in [
      ("official_new_member_volume",STATIC),
      ("official_structure_deceased_table",STRUCT),
      ("official_member_detail_biography",DETAIL)
    ]:
        for r in read_csv(p):source_rows.append((source,r))
    if len(source_rows)!=359:raise RuntimeError(f"Expected 359 official accepted rows, got {len(source_rows)}")
    by=defaultdict(list)
    for source,r in source_rows:
        dob=(r.get("final_exact_dob") or r.get("candidate_dob") or "").strip()
        if not dob:raise RuntimeError(f"Blank DOB in accepted source {source} {r.get('member_slug')}")
        by[r["member_slug"]].append((source,dob,r))
    overlaps={k:v for k,v in by.items() if len(v)>1}
    if overlaps:raise RuntimeError(f"Official accepted sources overlap unexpectedly: {list(overlaps)[:10]}")
    if not set(by).issubset({r["member_slug"] for r in roster}):raise RuntimeError("Official accepted row outside frozen roster")
    out=[]
    for rr in roster:
        slug=rr["member_slug"]
        row={**rr,
          "final_exact_dob":"",
          "dob_source_class":"",
          "dob_source_url":"",
          "dob_evidence_locator":"",
          "dob_decision":"",
          "dob_collection_stage":"unresolved_after_official_pass"
        }
        if slug in by:
            source,dob,r=by[slug][0]
            row["final_exact_dob"]=dob
            row["dob_source_class"]=source
            if source=="official_member_detail_biography":
                row["dob_source_url"]=r.get("detail_url","")
                row["dob_evidence_locator"]=r.get("context","")
            else:
                row["dob_source_url"]=r.get("pdf_url","")
                row["dob_evidence_locator"]=f"page={r.get('pdf_page','')}; marker={r.get('raw_birth_marker','')}"
            row["dob_decision"]=r.get("decision","")
            row["dob_collection_stage"]="exact_official"
        out.append(row)
    exact=[r for r in out if r["final_exact_dob"]]
    if len(exact)!=359:raise RuntimeError(f"Expected 359 exact official rows, got {len(exact)}")
    cp=OUT/"leopoldina_dob_crosswalk_after_official_v1.csv"
    fields=list(out[0].keys())
    write_csv(cp,out,fields)
    strata=[]
    for keyfunc,label in [
      (lambda r:r["class"],"class"),
      (lambda r:"deceased" if r["deceased_marker"]=="1" else "no_deceased_marker","deceased_marker"),
      (lambda r:era(r["election_year"]),"election_era")
    ]:
        groups=defaultdict(list)
        for r in out:groups[keyfunc(r)].append(r)
        for k,rs in sorted(groups.items()):
            n=len(rs);e=sum(bool(r["final_exact_dob"]) for r in rs)
            strata.append({"dimension":label,"stratum":k,"rows":n,"exact_official":e,"unresolved":n-e,"coverage":round(e/n,6)})
    sp=OUT/"official_missingness_strata_v1.csv"
    write_csv(sp,strata,["dimension","stratum","rows","exact_official","unresolved","coverage"])
    src=Counter(r["dob_source_class"] for r in exact)
    summary={
      "dataset":"Leopoldina DOB crosswalk after official-source pass v1",
      "roster_rows":2888,
      "exact_dob_official":359,
      "official_coverage":round(359/2888,6),
      "unresolved_after_official":2529,
      "source_counts":dict(sorted(src.items())),
      "source_overlap_rows":0,
      "crosswalk_sha256":sha256(cp),
      "missingness_strata_sha256":sha256(sp),
      "next_step":"Identity-safe Wikidata/QID locator and independent-source enrichment on unresolved rows only. Wikidata/library authority DOB values are locator evidence, not final exact-DOB acceptance.",
      "bazi_variables_computed":0
    }
    (OUT/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
