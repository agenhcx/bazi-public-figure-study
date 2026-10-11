#!/usr/bin/env python3
from __future__ import annotations
import csv,json,hashlib
from collections import defaultdict,Counter
from pathlib import Path
IN=Path("data/leopoldina_structure_star_dob_inputs_v1");OUT=Path("data/leopoldina_structure_star_dob_candidates_v1")
def read_csv(p):
    with p.open("r",encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
def write_csv(p,rows,fields):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open("w",encoding="utf-8-sig",newline="") as f:w=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore");w.writeheader();w.writerows(rows)
def sha256(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for c in iter(lambda:f.read(1<<20),b""):h.update(c)
    return h.hexdigest()
def main():
    OUT.mkdir(parents=True,exist_ok=True);rows=[];summaries=[]
    for y in [2022,2023,2024,2025]:
        cf=list(IN.rglob(f"candidates_{y}.csv"));sf=list(IN.rglob(f"summary_{y}.json"))
        if len(cf)!=1 or len(sf)!=1:raise RuntimeError(f"Missing year {y}")
        rows.extend(read_csv(cf[0]));summaries.append(json.loads(sf[0].read_text(encoding="utf-8")))
    by=defaultdict(list)
    for r in rows:by[r["member_slug"]].append(r)
    audit=[]
    for slug,rs in sorted(by.items()):
        dates=sorted({r["candidate_dob"] for r in rs});yrs=sorted({r["structure_year"] for r in rs})
        audit.append({"member_slug":slug,"display_name":rs[0]["display_name"],"candidate_dates":" | ".join(dates),"candidate_date_count":len(dates),"structure_years":" | ".join(yrs),"row_count":len(rs),"review_status":"unique_candidate_review" if len(dates)==1 else "multiple_candidates_review"})
    rp=OUT/"candidate_rows_v1.csv";write_csv(rp,sorted(rows,key=lambda r:(r["member_slug"],r["candidate_dob"],r["structure_year"])),list(rows[0].keys()) if rows else ["member_slug"])
    ap=OUT/"member_candidate_audit_v1.csv";write_csv(ap,audit,["member_slug","display_name","candidate_dates","candidate_date_count","structure_years","row_count","review_status"])
    yp=OUT/"source_year_summary_v1.csv";write_csv(yp,summaries,["structure_year","pdf_url","source_status","source_error","candidate_rows","candidate_members","bazi_variables_computed"])
    summary={"dataset":"Leopoldina 2022-2025 structure-volume starred-DOB candidate scan v1","candidate_rows":len(rows),"candidate_members":len(by),"unique_candidate_members":sum(int(r["candidate_date_count"])==1 for r in audit),"multiple_candidate_members":sum(int(r["candidate_date_count"])>1 for r in audit),"source_status_counts":dict(Counter(s["source_status"] for s in summaries)),"candidate_rows_sha256":sha256(rp),"member_audit_sha256":sha256(ap),"year_summary_sha256":sha256(yp),"acceptance_status":"candidate_only_pending_context_audit","bazi_variables_computed":0}
    (OUT/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8");print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
