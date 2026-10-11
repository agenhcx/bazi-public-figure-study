#!/usr/bin/env python3
from __future__ import annotations
import csv,hashlib,json,re,unicodedata
from collections import Counter,defaultdict
from datetime import date
from pathlib import Path

CAND=Path("data/leopoldina_structure_v2_checkpoint_input/candidate_rows_v2.csv")
AUDIT=Path("data/leopoldina_structure_v2_checkpoint_input/member_candidate_audit_v2.csv")
ADJ=Path("data/leopoldina_structure_row_dob_adjudication_v1.csv")
ROSTER=Path("data/leopoldina_roster_freeze_v1/leopoldina_science_core_roster_freeze_v1.csv")
OUT=Path("data/leopoldina_structure_row_dob_accepted_v1")
REJECT={"rudolf-manfred-schmidt","klaus-peter","helmut-koch"}

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
def fold(s):
    s=unicodedata.normalize("NFKD",str(s or ""));s="".join(c for c in s if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9]+"," ",s).strip()
def row_name_match(r):
    toks=[fold(x) for x in r["member_slug"].split("-") if len(fold(x))>1]
    if len(toks)<2:return False
    first,last=toks[0],toks[-1];ctx=fold(r["context"])
    return bool(re.search(rf"\b{re.escape(last)}\b.{{0,55}}\b{re.escape(first)}\b",ctx))
def main():
    OUT.mkdir(parents=True,exist_ok=True)
    rows=read_csv(CAND); audit=read_csv(AUDIT); adj=read_csv(ADJ); roster=read_csv(ROSTER)
    if len(rows)!=62 or len({r["member_slug"] for r in rows})!=61:raise RuntimeError(f"Unexpected v2 candidate cardinality rows={len(rows)} members={len({r['member_slug'] for r in rows})}")
    if len(audit)!=61:raise RuntimeError("Expected 61 member audit rows")
    amap={r["member_slug"]:r for r in adj}
    if set(REJECT)!={"rudolf-manfred-schmidt","klaus-peter","helmut-koch"}:raise RuntimeError("Rejected identity set changed")
    if amap.get("helmut-koch-1",{}).get("decision")!="accept_identity_adjudicated":raise RuntimeError("Missing Helmut Koch mathematics adjudication")
    rmap={r["member_slug"]:r for r in roster}
    # Generic surname-first/given-name audit: all retained evidence must match its official row name locally.
    matched=[]
    rejected=[]
    for r in rows:
        slug=r["member_slug"]
        if slug in REJECT:
            rejected.append({**r,"adjudication":amap[slug]["decision"],"adjudication_reason":amap[slug]["reason"]})
            continue
        if not row_name_match(r):
            raise RuntimeError(f"Unexpected name-context mismatch outside frozen reject set: {slug}")
        if slug not in rmap:raise RuntimeError(f"Candidate outside frozen roster: {slug}")
        if r["source_status"]!="available":raise RuntimeError(f"Nonavailable source row: {slug}")
        try:date.fromisoformat(r["candidate_dob"])
        except Exception:raise RuntimeError(f"Invalid DOB: {slug}")
        matched.append(r)
    # After exclusion there must be exactly one candidate row/date per member.
    by=defaultdict(list)
    for r in matched:by[r["member_slug"]].append(r)
    bad={k:sorted({x["candidate_dob"] for x in v}) for k,v in by.items() if len({x["candidate_dob"] for x in v})!=1 or len(v)!=1}
    if bad:raise RuntimeError(f"Nonunique retained member evidence: {bad}")
    if len(matched)!=58 or len(by)!=58:raise RuntimeError(f"Expected 58 accepted rows/members, got {len(matched)}/{len(by)}")
    # Explicitly ensure the duplicate-name Helmut evidence is assigned only to Mathematics/Dresden row.
    hk=[r for r in matched if r["member_slug"]=="helmut-koch-1"]
    if len(hk)!=1 or hk[0]["section"]!="Mathematics" or "Mathematik" not in hk[0]["context"]:
        raise RuntimeError("Helmut Koch mathematics adjudication invariant failed")
    ap=OUT/"accepted_exact_dob_structure_tables_v1.csv"
    fields=list(matched[0].keys())+["decision"]
    accepted=[{**r,"decision":"accept_official_structure_table_exact_dob"} for r in sorted(matched,key=lambda x:(x["member_slug"],x["candidate_dob"]))]
    write_csv(ap,accepted,fields)
    rp=OUT/"rejected_identity_candidates_v1.csv"
    write_csv(rp,rejected,list(rejected[0].keys()) if rejected else ["member_slug"])
    summary={
      "dataset":"Leopoldina official structure-table exact-DOB checkpoint v1",
      "source_run_id":38098238875,
      "source_artifact_id":11686902779,
      "source_artifact_name":"leopoldina-structure-row-dob-candidates-v2",
      "source_artifact_zip_sha256":"f4835a21be2396bc0a45129c5f355bd1b016c18592c6ddc96e49be1da7176b69",
      "candidate_rows":62,"candidate_members":61,
      "accepted_exact_dob":58,
      "rejected_identity_member_slugs":["rudolf-manfred-schmidt","klaus-peter","helmut-koch"],
      "accepted_csv_sha256":sha256(ap),"rejected_csv_sha256":sha256(rp),"adjudication_csv_sha256":sha256(ADJ),
      "acceptance_rule":"Official annual Structure und Mitglieder table row must contain the frozen member identity before the first starred exact birth date; surname-first and given-name tokens must match locally. Same-name/generic-name collisions are resolved only with explicit section/location-compatible identity evidence.",
      "bazi_variables_computed":0
    }
    (OUT/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
