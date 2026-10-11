#!/usr/bin/env python3
from __future__ import annotations
import csv,hashlib,json
from collections import Counter,defaultdict
from pathlib import Path

ORIG=Path("data/leopoldina_detail_birthphrase_rebuild/original")
RESC=Path("data/leopoldina_detail_birthphrase_rebuild/rescue")
OUT=Path("data/leopoldina_detail_birthphrase_candidates_rebuilt_v1")

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
def summaries(root):
    out=[]
    for p in root.rglob("summary_s*.json"):
        out.append(json.loads(p.read_text(encoding="utf-8")))
    return out

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    osum=summaries(ORIG); rsum=summaries(RESC)
    oi=sorted(int(x["shard_index"]) for x in osum)
    ri=sorted(int(x["shard_index"]) for x in rsum)
    if oi!=list(range(15)):raise RuntimeError(f"Expected original shards 0..14 only, got {oi}")
    if ri!=[15,31,47,63]:raise RuntimeError(f"Expected rescue mod64 shards [15,31,47,63], got {ri}")
    if any(int(x["shard_count"])!=16 for x in osum):raise RuntimeError("Original shard_count invariant failed")
    if any(int(x["shard_count"])!=64 for x in rsum):raise RuntimeError("Rescue shard_count invariant failed")
    rescue_targets=sum(int(x["targets"]) for x in rsum)
    if rescue_targets!=165:raise RuntimeError(f"Expected original shard15 target population 165, rescue has {rescue_targets}")
    total_targets=sum(int(x["targets"]) for x in osum)+rescue_targets
    if total_targets!=2640:raise RuntimeError(f"Expected 2640 official-detail targets, got {total_targets}")

    cfiles=list(ORIG.rglob("candidates_s*.csv"))+list(RESC.rglob("candidates_s*.csv"))
    efiles=list(ORIG.rglob("errors_s*.csv"))+list(RESC.rglob("errors_s*.csv"))
    rows=[];errors=[]
    for p in cfiles:rows.extend(read_csv(p))
    for p in efiles:errors.extend(read_csv(p))
    # Exact candidate evidence rows should not duplicate across the deterministic shard split.
    keys=[(r["member_slug"],r["candidate_dob"],r["pattern_class"],r["context"],r["detail_url"]) for r in rows]
    if len(keys)!=len(set(keys)):raise RuntimeError("Duplicate candidate evidence rows after rebuild")
    by=defaultdict(list)
    for r in rows:by[r["member_slug"]].append(r)
    audit=[]
    for slug,rs in sorted(by.items()):
        dates=sorted({r["candidate_dob"] for r in rs})
        classes=sorted({r["pattern_class"] for r in rs})
        audit.append({
          "member_slug":slug,"display_name":rs[0]["display_name"],"election_year":rs[0]["election_year"],"deceased_marker":rs[0]["deceased_marker"],
          "candidate_dates":" | ".join(dates),"candidate_date_count":len(dates),
          "pattern_classes":" | ".join(classes),"candidate_row_count":len(rs),
          "review_status":"unique_candidate_review" if len(dates)==1 else "multiple_candidates_review"
        })
    fields=["member_slug","display_name","class","section","election_year","deceased_marker","candidate_dob","pattern_class","date_format","raw_date","context","detail_url","http_status","bazi_variables_computed"]
    rp=OUT/"candidate_rows_v1.csv";write_csv(rp,sorted(rows,key=lambda r:(r["member_slug"],r["candidate_dob"],r["pattern_class"])),fields)
    ap=OUT/"member_candidate_audit_v1.csv";write_csv(ap,audit,["member_slug","display_name","election_year","deceased_marker","candidate_dates","candidate_date_count","pattern_classes","candidate_row_count","review_status"])
    ep=OUT/"http_errors_v1.csv";write_csv(ep,errors,["member_slug","display_name","detail_url","http_status","error"])
    ss=OUT/"shard_rebuild_audit_v1.csv"
    sr=[]
    for x in sorted(osum,key=lambda z:int(z["shard_index"])):sr.append({**x,"source_run":38098029758,"role":"original_mod16"})
    for x in sorted(rsum,key=lambda z:int(z["shard_index"])):sr.append({**x,"source_run":38098604967,"role":"rescue_mod64_for_original_shard15"})
    write_csv(ss,sr,["shard_index","shard_count","targets","candidate_rows","candidate_members","http_errors","bazi_variables_computed","source_run","role"])
    summary={
      "dataset":"Leopoldina official detail-page explicit birth-phrase candidate scan rebuilt v1",
      "target_rows":total_targets,
      "original_success_shards":15,
      "rescued_original_shard15_targets":rescue_targets,
      "candidate_rows":len(rows),"candidate_members":len(by),
      "unique_candidate_members":sum(int(r["candidate_date_count"])==1 for r in audit),
      "multiple_candidate_members":sum(int(r["candidate_date_count"])>1 for r in audit),
      "pattern_counts":dict(Counter(r["pattern_class"] for r in rows)),
      "http_errors":len(errors),
      "candidate_rows_sha256":sha256(rp),"member_audit_sha256":sha256(ap),"http_errors_sha256":sha256(ep),"shard_audit_sha256":sha256(ss),
      "source_runs":{"original":38098029758,"shard15_rescue":38098604967},
      "acceptance_status":"candidate_only_pending_context_audit",
      "bazi_variables_computed":0
    }
    (OUT/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
