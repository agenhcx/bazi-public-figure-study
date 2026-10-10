#!/usr/bin/env python3
from __future__ import annotations
import csv, json, re, time, urllib.parse, urllib.request, urllib.error
from pathlib import Path

DIRECT=Path("data/direct_validation_inputs")
AUTH=Path("data/authority_validation_inputs")
LOC=Path("data/current_locator_input")
OUT=Path("data/royal_society_current_acceptance_identity_audit_v1")
API="https://www.wikidata.org/w/api.php"
UA="bazi-public-figure-study/1.0 (Royal Society accepted-candidate identity audit; no BaZi)"

FALLBACK=[
 {"cohort_key":"RS_CURRENT_11906","display_name":"Raghunath Mashelkar","wikidata_qid":"Q7283012","candidate_dob":"1943-01-01","candidate_sources":"authoritative_web_fallback"},
 {"cohort_key":"RS_CURRENT_12434","display_name":"Scott Tremaine","wikidata_qid":"Q363194","candidate_dob":"1950-05-25","candidate_sources":"authoritative_web_fallback"},
 {"cohort_key":"RS_CURRENT_36236","display_name":"Tebello Nyokong","wikidata_qid":"Q21448010","candidate_dob":"1951-10-20","candidate_sources":"authoritative_web_fallback"},
]

def read_csv(p):
    with p.open("r",encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
def write_csv(p,rows,fields):
    with p.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore");w.writeheader();w.writerows(rows)

def entities(qids):
    out={};qids=list(dict.fromkeys(qids));batch=20
    for i in range(0,len(qids),batch):
        part=qids[i:i+batch]
        qs=urllib.parse.urlencode({"action":"wbgetentities","ids":"|".join(part),"props":"claims","format":"json","maxlag":5})
        last=None
        for a in range(8):
            try:
                req=urllib.request.Request(API+"?"+qs,headers={"User-Agent":UA,"Accept":"application/json"})
                with urllib.request.urlopen(req,timeout=60) as r:out.update(json.load(r).get("entities",{}))
                last=None;break
            except urllib.error.HTTPError as e:
                last=e
                if e.code==429 and a<7:
                    try:wait=float(e.headers.get("Retry-After",""))
                    except:wait=5*(a+1)
                    time.sleep(max(5,min(60,wait)));continue
                if a<7:time.sleep(min(30,2**a));continue
                raise
            except Exception as e:
                last=e
                if a<7:time.sleep(min(30,2**a));continue
                raise
        print("entity batch",i//batch+1,"/",((len(qids)+batch-1)//batch))
        time.sleep(1.0)
    return out

def time_claims(ent,pid):
    vals=[]
    for st in ent.get("claims",{}).get(pid,[]) or []:
        v=st.get("mainsnak",{}).get("datavalue",{}).get("value")
        if isinstance(v,dict) and "time" in v:
            m=re.match(r"^[+-](\d+)-(\d\d)-(\d\d)T",v["time"])
            if m:vals.append(v["time"])
    return vals

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    direct_files=list(DIRECT.rglob("direct_reference_validation.csv"))
    auth_files=list(AUTH.rglob("authority_validation.csv"))
    loc_files=list(LOC.rglob("royal_society_current_wikidata_locator_v1.csv"))
    if len(direct_files)!=4:raise RuntimeError(f"expected 4 direct shards, got {direct_files}")
    if len(auth_files)!=2:raise RuntimeError(f"expected 2 authority shards, got {auth_files}")
    if len(loc_files)!=1:raise RuntimeError(f"expected 1 locator csv, got {loc_files}")

    candidates={}
    for p in direct_files:
        for r in read_csv(p):
            if str(r.get("accepted_direct_reference",""))!="1":continue
            candidates[r["cohort_key"]]={"cohort_key":r["cohort_key"],"display_name":r["display_name"],"wikidata_qid":r["wikidata_qid"],"candidate_dob":r["confirmed_candidate_date"],"candidate_sources":"direct_reference"}
    for p in auth_files:
        for r in read_csv(p):
            if str(r.get("accepted_authority_record",""))!="1":continue
            k=r["cohort_key"]
            if k in candidates:candidates[k]["candidate_sources"]+=";"+r["source_label"]
            else:candidates[k]={"cohort_key":k,"display_name":r["display_name"],"wikidata_qid":r["wikidata_qid"],"candidate_dob":r["candidate_dob"],"candidate_sources":r["source_label"]}
    for r in FALLBACK:
        k=r["cohort_key"]
        if k in candidates:candidates[k]["candidate_sources"]+=";"+r["candidate_sources"]
        else:candidates[k]=dict(r)

    loc={r["cohort_key"]:r for r in read_csv(loc_files[0])}
    rows=sorted(candidates.values(),key=lambda r:r["cohort_key"])
    if len(rows)!=55:raise RuntimeError(f"expected 55 unique acceptance candidates, got {len(rows)}")
    ents=entities([r["wikidata_qid"] for r in rows])

    audit=[];safe=[];flagged=[]
    for r in rows:
        lr=loc.get(r["cohort_key"],{})
        deaths=time_claims(ents.get(r["wikidata_qid"],{}),"P570")
        y=int(r["candidate_dob"][:4])
        try:ey=int(lr.get("election_year") or 0) or None
        except:ey=None
        age=(ey-y) if ey else None
        reasons=[]
        if deaths:reasons.append("wikidata_has_date_of_death")
        if y<1900:reasons.append("candidate_birth_before_1900")
        if age is not None and age>100:reasons.append("age_at_election_over_100")
        if age is not None and age<18:reasons.append("age_at_election_under_18")
        rec={**r,
          "election_year":ey if ey else "","source_url":lr.get("source_url",""),
          "age_at_election":age if age is not None else "",
          "p570_values":";".join(deaths),"identity_flag":int(bool(reasons)),
          "flag_reasons":";".join(reasons),
          "identity_audit_status":"manual_review_required" if reasons else "passed_death_and_chronology_screen"
        }
        audit.append(rec)
        (flagged if reasons else safe).append(rec)

    fields=list(audit[0].keys())
    write_csv(OUT/"acceptance_identity_audit.csv",audit,fields)
    write_csv(OUT/"safe_acceptance_candidates.csv",safe,fields)
    write_csv(OUT/"flagged_acceptance_candidates.csv",flagged,fields)
    summary={
      "dataset":"Royal Society current acceptance-candidate identity audit v1",
      "candidate_people":len(audit),"passed_screen":len(safe),"flagged_for_manual_review":len(flagged),
      "with_wikidata_date_of_death":sum(bool(x["p570_values"]) for x in audit),
      "birth_before_1900":sum(int(x["candidate_dob"][:4])<1900 for x in audit),
      "flagged":[{"cohort_key":x["cohort_key"],"display_name":x["display_name"],"wikidata_qid":x["wikidata_qid"],"candidate_dob":x["candidate_dob"],"reasons":x["flag_reasons"]} for x in flagged],
      "bazi_variables_computed":0
    }
    (OUT/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
