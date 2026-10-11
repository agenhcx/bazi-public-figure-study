#!/usr/bin/env python3
from __future__ import annotations
import csv,json,hashlib
from collections import Counter,defaultdict
from pathlib import Path

IN=Path("data/leopoldina_detail_birthphrase_inputs_v1")
OUT=Path("data/leopoldina_detail_birthphrase_candidates_v1")
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
    cfs=sorted(IN.rglob("candidates_s*.csv")); efs=sorted(IN.rglob("errors_s*.csv"))
    if len(cfs)!=16 or len(efs)!=16:raise RuntimeError(f"Expected 16 candidate/error shards, got {len(cfs)}/{len(efs)}")
    rows=[];errors=[]
    for p in cfs:rows.extend(read_csv(p))
    for p in efs:errors.extend(read_csv(p))
    by=defaultdict(list)
    for r in rows:by[r["member_slug"]].append(r)
    audit=[]
    for slug,rs in sorted(by.items()):
        dates=sorted({r["candidate_dob"] for r in rs})
        classes=sorted({r["pattern_class"] for r in rs})
        audit.append({
          "member_slug":slug,"display_name":rs[0]["display_name"],"election_year":rs[0]["election_year"],"deceased_marker":rs[0]["deceased_marker"],
          "candidate_dates":" | ".join(dates),"candidate_date_count":len(dates),"pattern_classes":" | ".join(classes),
          "candidate_row_count":len(rs),"review_status":"unique_candidate_review" if len(dates)==1 else "multiple_candidates_review"
        })
    rp=OUT/"candidate_rows_v1.csv"; write_csv(rp,sorted(rows,key=lambda r:(r["member_slug"],r["candidate_dob"],r["pattern_class"])),list(rows[0].keys()) if rows else ["member_slug"])
    ap=OUT/"member_candidate_audit_v1.csv"; write_csv(ap,audit,["member_slug","display_name","election_year","deceased_marker","candidate_dates","candidate_date_count","pattern_classes","candidate_row_count","review_status"])
    ep=OUT/"http_errors_v1.csv"; write_csv(ep,errors,["member_slug","display_name","detail_url","http_status","error"])
    pc=Counter(r["pattern_class"] for r in rows)
    summary={
      "dataset":"Leopoldina official detail-page explicit birth-phrase candidate scan v1",
      "candidate_rows":len(rows),"candidate_members":len(by),
      "unique_candidate_members":sum(int(r["candidate_date_count"])==1 for r in audit),
      "multiple_candidate_members":sum(int(r["candidate_date_count"])>1 for r in audit),
      "pattern_counts":dict(sorted(pc.items())),"http_errors":len(errors),
      "candidate_rows_sha256":sha256(rp),"member_audit_sha256":sha256(ap),"http_errors_sha256":sha256(ep),
      "acceptance_status":"candidate_only_pending_context_audit","bazi_variables_computed":0
    }
    (OUT/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
