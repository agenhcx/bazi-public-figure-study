#!/usr/bin/env python3
from __future__ import annotations
import csv, json, re, time, urllib.parse, urllib.request
from collections import Counter
from pathlib import Path

IN=Path("data/royal_society_current_locator_consolidated_input")
OUT=Path("data/royal_society_current_locator_identity_audit_v1")
API="https://www.wikidata.org/w/api.php"
UA="bazi-public-figure-study/1.0 (Royal Society current locator identity audit; no BaZi)"

def read_csv(p):
    with p.open("r",encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))

def write_csv(p,rows,fields):
    with p.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore");w.writeheader();w.writerows(rows)

def entities(qids):
    out={};qids=list(dict.fromkeys(qids))
    for i in range(0,len(qids),50):
        qs=urllib.parse.urlencode({"action":"wbgetentities","ids":"|".join(qids[i:i+50]),"props":"claims","format":"json"})
        req=urllib.request.Request(API+"?"+qs,headers={"User-Agent":UA})
        with urllib.request.urlopen(req,timeout=45) as r:out.update(json.load(r).get("entities",{}))
        if (i//50+1)%5==0:print("entity batches",i//50+1,"/",((len(qids)+49)//50))
        time.sleep(.15)
    return out

def time_claims(ent,pid):
    vals=[]
    for st in ent.get("claims",{}).get(pid,[]) or []:
        v=st.get("mainsnak",{}).get("datavalue",{}).get("value")
        if isinstance(v,dict) and "time" in v:
            m=re.match(r"^[+-](\d+)-(\d\d)-(\d\d)T",v["time"])
            if m:vals.append({"raw":v["time"],"year":int(m.group(1)),"month":int(m.group(2)),"day":int(m.group(3)),"precision":int(v.get("precision",0) or 0)})
    return vals

def first_exact_birth_year(s):
    m=re.search(r"\+(\d{4})-(\d\d)-(\d\d)T",s or "")
    return int(m.group(1)) if m else None

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    files=list(IN.rglob("resolved_locator_v1.csv"))
    if len(files)!=1:raise RuntimeError(f"expected one resolved locator csv, found {files}")
    rows=read_csv(files[0])
    if len(rows)!=1076:raise RuntimeError(f"expected 1076 resolved locators, got {len(rows)}")
    ents=entities([r["wikidata_qid"] for r in rows])

    audit=[];flagged=[]
    for r in rows:
        ent=ents.get(r["wikidata_qid"],{})
        deaths=time_claims(ent,"P570")
        births=time_claims(ent,"P569")
        by=first_exact_birth_year(r.get("p569_exact_values",""))
        try:ey=int(r.get("election_year") or 0) or None
        except:ey=None
        age=(ey-by) if (ey and by) else None
        reasons=[]
        if deaths:reasons.append("wikidata_has_date_of_death")
        if by is not None and by<1900:reasons.append("exact_birth_before_1900")
        if age is not None and age<18:reasons.append("age_at_election_under_18")
        if age is not None and age>100:reasons.append("age_at_election_over_100")
        rec={
          "cohort_key":r["cohort_key"],"display_name":r["display_name"],"election_year":r.get("election_year",""),
          "source_url":r.get("source_url",""),"wikidata_qid":r["wikidata_qid"],"locator_confidence":r.get("locator_confidence",""),
          "candidate_description":r.get("candidate_description",""),"p569_exact_values":r.get("p569_exact_values",""),
          "birth_year_from_locator_exact":by if by is not None else "",
          "age_at_election_from_exact":age if age is not None else "",
          "p570_values":";".join(x["raw"] for x in deaths),
          "p570_count":len(deaths),"identity_flag":int(bool(reasons)),"flag_reasons":";".join(reasons),
          "audit_status":"manual_review_required" if reasons else "no_red_flag_from_death_age_audit"
        }
        audit.append(rec)
        if reasons:flagged.append(rec)

    fields=list(audit[0].keys())
    write_csv(OUT/"locator_identity_audit.csv",audit,fields)
    write_csv(OUT/"flagged_locator_identity_review.csv",flagged,fields)
    rc=Counter(x["flag_reasons"] for x in flagged)
    summary={
      "dataset":"Royal Society current Wikidata locator identity audit v1",
      "resolved_locators":len(rows),
      "flagged_for_manual_review":len(flagged),
      "wikidata_has_date_of_death":sum(x["p570_count"]>0 for x in audit),
      "exact_birth_before_1900":sum((isinstance(x["birth_year_from_locator_exact"],int) and x["birth_year_from_locator_exact"]<1900) for x in audit),
      "age_at_election_over_100":sum((isinstance(x["age_at_election_from_exact"],int) and x["age_at_election_from_exact"]>100) for x in audit),
      "age_at_election_under_18":sum((isinstance(x["age_at_election_from_exact"],int) and x["age_at_election_from_exact"]<18) for x in audit),
      "flag_reason_combinations":dict(rc),
      "dob_values_accepted":0,"bazi_variables_computed":0,
      "note":"Audit is conservative: any P570 on a current-roster match or impossible age chronology requires manual identity review. No locator is automatically discarded here."
    }
    (OUT/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
