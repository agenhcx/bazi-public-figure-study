#!/usr/bin/env python3
from __future__ import annotations
import csv, hashlib, json, re
from pathlib import Path

IN=Path("data/royal_society_freeze_inputs_v1")
OUT=Path("data/royal_society_roster_freeze_v1")

def sha256(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for c in iter(lambda:f.read(1<<20),b""): h.update(c)
    return h.hexdigest()

def read_csv(p):
    with p.open("r",encoding="utf-8-sig",newline="") as f:
        return list(csv.DictReader(f))

def find_one(name):
    xs=list(IN.rglob(name))
    if len(xs)!=1:
        raise RuntimeError(f"Expected exactly one {name}, found {len(xs)}: {xs}")
    return xs[0]

def norm_name(s):
    s=str(s or "").lower()
    s=re.sub(r"\b(?:sir|dame|lord|lady|professor|prof|dr)\b"," ",s)
    return re.sub(r"[^a-z0-9]+","",s)

def hist_year(date_text,query_year):
    q=str(query_year or "").strip()
    if q.isdigit(): return int(q)
    m=re.search(r"(16|17|18|19|20)\d{2}",str(date_text or ""))
    return int(m.group(0)) if m else None

def main():
    if OUT.exists() and any(OUT.iterdir()):
        raise RuntimeError(f"Output directory nonempty: {OUT}")
    OUT.mkdir(parents=True,exist_ok=True)

    current=read_csv(find_one("royal_society_current_fellows_v1.csv"))
    past=read_csv(find_one("royal_society_past_fellows_v1.csv"))
    overlaps=read_csv(find_one("current_past_name_overlap_review_v1.csv"))

    ey_files=list(IN.rglob("current_fellows_by_election_year.csv"))
    if len(ey_files)!=4:
        raise RuntimeError(f"Expected four current election-year files, found {len(ey_files)}")
    ey=[]
    for p in ey_files: ey.extend(read_csv(p))

    if len(current)!=1570 or len(past)!=7099 or len(ey)!=1570:
        raise RuntimeError(f"Count invariant failed: current={len(current)} past={len(past)} election_year={len(ey)}")

    cur_ids=[str(r["profile_numeric_id"]) for r in current]
    ey_ids=[str(r["profile_numeric_id"]) for r in ey]
    if len(set(cur_ids))!=1570 or len(set(ey_ids))!=1570 or set(cur_ids)!=set(ey_ids):
        raise RuntimeError("Current roster and election-year ID sets do not match exactly")

    ey_map={str(r["profile_numeric_id"]):int(r["election_year"]) for r in ey}
    if min(ey_map.values())<1962 or max(ey_map.values())>2025:
        raise RuntimeError("Current election year outside frozen 1962-2025 directory window")

    # Resolve all exact-normalized-name current/past overlaps using election year.
    # A true duplicate should share the same election event; all 17 candidates
    # must instead have different election years to be retained as namesakes.
    current_by_norm={norm_name(r["display_name"]):r for r in current}
    overlap_audit=[]
    for o in overlaps:
        n=o["normalized_name"]
        c=current_by_norm.get(n)
        if not c: raise RuntimeError(f"Overlap current name not found: {o}")
        cy=ey_map[str(c["profile_numeric_id"])]
        hy=hist_year(o["historical_election_date"],"")
        same=int(hy==cy) if hy is not None else -1
        overlap_audit.append({
          **o,
          "current_profile_numeric_id":c["profile_numeric_id"],
          "current_election_year":cy,
          "historical_election_year":hy if hy is not None else "",
          "same_election_year":same,
          "resolution":"namesake_not_duplicate" if hy is not None and hy!=cy else "needs_review"
        })
    if len(overlap_audit)!=17:
        raise RuntimeError(f"Expected 17 overlap pairs, found {len(overlap_audit)}")
    unresolved=[x for x in overlap_audit if x["resolution"]!="namesake_not_duplicate"]
    if unresolved:
        raise RuntimeError(f"Unresolved current/past overlap pairs: {unresolved}")

    frozen=[]
    for r in past:
        y=hist_year(r.get("election_date_text"),r.get("election_year_query"))
        frozen.append({
          "cohort_key":"RS_PAST_"+str(r["record_id"]),
          "status_at_source":"past",
          "display_name":r["display_name"],
          "membership_category":"Fellow",
          "election_year":"" if y is None else y,
          "election_date_text":r.get("election_date_text",""),
          "lifespan_text":r.get("lifespan_text",""),
          "source_id":r["record_id"],
          "source_url":r["record_url"],
          "primary_cohort":1
        })
    for r in current:
        pid=str(r["profile_numeric_id"])
        frozen.append({
          "cohort_key":"RS_CURRENT_"+pid,
          "status_at_source":"current",
          "display_name":r["display_name"],
          "membership_category":"Fellow",
          "election_year":ey_map[pid],
          "election_date_text":"",
          "lifespan_text":"",
          "source_id":pid,
          "source_url":r["profile_url"],
          "primary_cohort":1
        })

    if len(frozen)!=8669 or len({r["cohort_key"] for r in frozen})!=8669:
        raise RuntimeError(f"Final roster invariant failed: {len(frozen)} rows")

    blank_hist=sum(r["status_at_source"]=="past" and r["election_year"]=="" for r in frozen)
    if blank_hist!=3:
        raise RuntimeError(f"Expected 3 past Fellows without election date, found {blank_hist}")

    fields=["cohort_key","status_at_source","display_name","membership_category","election_year","election_date_text","lifespan_text","source_id","source_url","primary_cohort"]
    csvp=OUT/"royal_society_fellows_roster_freeze_v1.csv"
    with csvp.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(frozen)

    auditp=OUT/"current_past_overlap_audit_v1.csv"
    afields=list(overlap_audit[0].keys())
    with auditp.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=afields);w.writeheader();w.writerows(overlap_audit)

    manifest={
      "dataset":"Royal Society primary Fellow roster freeze v1",
      "cohort_definition":"Royal Society Fellows only; current plus past/deceased Fellows; election/admission through 2025; Foreign Members, Honorary Fellows, and Royal Fellows excluded from the primary cohort.",
      "total":8669,
      "current":1570,
      "past":7099,
      "past_with_election_year":7096,
      "past_without_election_year":3,
      "current_with_election_year":1570,
      "current_election_year_coverage":1.0,
      "current_past_normalized_name_overlap_pairs":17,
      "overlap_pairs_resolved_as_namesakes":17,
      "unresolved_overlap_pairs":0,
      "roster_csv_sha256":sha256(csvp),
      "overlap_audit_sha256":sha256(auditp),
      "dob_lookup_performed":0,
      "bazi_variables_computed":0,
      "freeze_ready":1,
      "freeze_rule":"Roster membership was defined and audited before DOB collection. No BaZi variables were computed or inspected."
    }
    (OUT/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(manifest,ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
