#!/usr/bin/env python3
from __future__ import annotations
import csv, json, re, time, urllib.parse, urllib.request
from pathlib import Path
from collections import Counter

ROSTER=Path("data/royal_society_roster_freeze_v1/royal_society_fellows_roster_freeze_v1.csv")
CLOSEOUT=Path("data/royal_society_past_dob_closeout_v1")
OUT=Path("data/royal_society_wikidata_locator_diagnostic_v1")
API="https://www.wikidata.org/w/api.php"
UA="bazi-public-figure-study/1.0 (Royal Society DOB locator diagnostic; Wikidata is locator-only, no BaZi)"

SCI_WORDS=("scientist","physicist","chemist","biologist","mathematician","engineer","professor","academic","physician","astronomer","geologist","botanist","zoologist","geneticist","economist","computer scientist","medical","researcher")

def read_csv(p):
    with p.open("r",encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))

def api(params,retries=5):
    qs=urllib.parse.urlencode(params,doseq=True)
    last=None
    for a in range(retries):
        try:
            req=urllib.request.Request(API+"?"+qs,headers={"User-Agent":UA,"Accept":"application/json"})
            with urllib.request.urlopen(req,timeout=60) as r:
                return json.load(r)
        except Exception as e:
            last=e
            if a+1<retries:time.sleep(min(12,2**a))
    raise RuntimeError(repr(last))

def norm(s):
    s=(s or "").lower()
    s=re.sub(r"\b(?:sir|dame|lord|lady|professor|prof|dr|rev|reverend)\b"," ",s)
    s=re.sub(r"\b(?:frs|fmedsci|cbe|obe|kbe|fba|fellow)\b"," ",s)
    return re.sub(r"[^a-z0-9]+","",s)

def search(q,limit=5):
    return api({"action":"wbsearchentities","search":q,"language":"en","uselang":"en","type":"item","limit":limit,"format":"json"}).get("search",[])

def exact_item_id(label):
    xs=search(label,5)
    n=norm(label)
    for x in xs:
        if norm(x.get("label",""))==n:return x["id"]
    return xs[0]["id"] if xs else ""

def batch_entities(ids):
    out={}
    ids=[x for x in dict.fromkeys(ids) if x]
    for i in range(0,len(ids),50):
        part=ids[i:i+50]
        d=api({"action":"wbgetentities","ids":"|".join(part),"props":"claims|labels|aliases|descriptions","languages":"en","format":"json"})
        out.update(d.get("entities",{}))
        time.sleep(0.08)
    return out

def claim_items(ent,pid):
    vals=[]
    for st in ent.get("claims",{}).get(pid,[]):
        dv=st.get("mainsnak",{}).get("datavalue",{})
        v=dv.get("value")
        if isinstance(v,dict) and "id" in v:vals.append(v["id"])
    return vals

def p569(ent):
    out=[]
    for st in ent.get("claims",{}).get("P569",[]):
        sn=st.get("mainsnak",{})
        dv=sn.get("datavalue",{})
        v=dv.get("value")
        if not isinstance(v,dict) or "time" not in v:continue
        t=v["time"];prec=int(v.get("precision",0) or 0)
        m=re.match(r"^[+-](\d+)-(\d\d)-(\d\d)T",t)
        if not m:continue
        y,mo,d=map(int,m.groups())
        out.append({"time":t,"precision":prec,"year":y,"month":mo,"day":d})
    return out

def aliases(ent):
    return [x.get("value","") for x in ent.get("aliases",{}).get("en",[])]

def known_year(row):
    for k in ("dob_year_from_raw","catalogue_lifespan_birth_year"):
        x=str(row.get(k,"")).strip()
        if x.isdigit():return int(x)
    return None

def strat_sample(rows,n):
    if len(rows)<=n:return list(rows)
    rows=sorted(rows,key=lambda r:r.get("cohort_key",""))
    idx=sorted(set(round(i*(len(rows)-1)/(n-1)) for i in range(n)))
    return [rows[i] for i in idx]

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    current=[]
    with ROSTER.open("r",encoding="utf-8-sig",newline="") as f:
        current=[r for r in csv.DictReader(f) if r["status_at_source"]=="current"]
    unresolved=read_csv(CLOSEOUT/"nonexact_unresolved_final_v1.csv")
    http=read_csv(CLOSEOUT/"persistent_http_error_queue_v1.csv")
    past=unresolved+http
    if len(current)!=1570 or len(unresolved)!=2211 or len(http)!=4:
        raise RuntimeError(f"Input invariant current={len(current)} unresolved={len(unresolved)} http={len(http)}")

    # Deterministic diagnostic only; no candidate DOB is accepted into the cohort.
    ps=strat_sample(past,60)
    cs=strat_sample(current,60)
    sample=[("past_unresolved",r) for r in ps]+[("current",r) for r in cs]

    rs_q=exact_item_id("Royal Society")
    frs_q=exact_item_id("Fellow of the Royal Society")
    print("Royal Society item",rs_q,"FRS item",frs_q)

    search_results={}
    all_ids=[]
    for i,(kind,r) in enumerate(sample,1):
        name=r["display_name"]
        xs=search(name,5)
        search_results[(kind,r["cohort_key"])]=xs
        all_ids.extend(x["id"] for x in xs)
        if i%20==0:print("searched",i,"/",len(sample))
        time.sleep(0.08)

    ents=batch_entities(all_ids)
    rows=[]
    for kind,r in sample:
        n=norm(r["display_name"]); ky=known_year(r)
        cand=[]
        for rank,x in enumerate(search_results[(kind,r["cohort_key"])],1):
            e=ents.get(x["id"],{})
            lab=e.get("labels",{}).get("en",{}).get("value",x.get("label",""))
            desc=e.get("descriptions",{}).get("en",{}).get("value",x.get("description",""))
            al=aliases(e)
            exact_label=(norm(lab)==n or any(norm(a)==n for a in al))
            dates=p569(e)
            years={d["year"] for d in dates}
            member=(rs_q and rs_q in claim_items(e,"P463")) or (frs_q and frs_q in claim_items(e,"P166"))
            sci=any(w in desc.lower() for w in SCI_WORDS)
            score=(3 if member else 0)+(2 if exact_label else 0)+(1 if sci else 0)
            if ky is not None:
                if ky in years:score+=4
                elif years:score-=4
            cand.append({"id":x["id"],"rank":rank,"label":lab,"description":desc,"score":score,"member":int(bool(member)),"exact_label":int(exact_label),"science_desc":int(sci),"dates":dates})
        cand=sorted(cand,key=lambda z:(-z["score"],z["rank"]))
        best=cand[0] if cand else None
        tie=bool(best and len(cand)>1 and cand[1]["score"]==best["score"])
        resolved=bool(best and best["score"]>=3 and not tie)
        exact_dates=[d for d in (best["dates"] if resolved else []) if d["precision"]>=11 and d["month"]>0 and d["day"]>0]
        rows.append({
          "sample_group":kind,"cohort_key":r["cohort_key"],"display_name":r["display_name"],
          "known_birth_year":"" if ky is None else ky,
          "wikidata_qid":best["id"] if resolved else "",
          "match_score":best["score"] if resolved else "",
          "membership_signal":best["member"] if resolved else "",
          "candidate_label":best["label"] if resolved else "",
          "candidate_description":best["description"] if resolved else "",
          "p569_any":int(bool(best and resolved and best["dates"])),
          "p569_exact_day":int(bool(exact_dates)),
          "p569_exact_values":";".join(d["time"] for d in exact_dates),
          "locator_status":"resolved_locator" if resolved else ("ambiguous" if cand else "no_search_result"),
          "acceptance_status":"locator_only_not_accepted"
        })

    fields=list(rows[0].keys())
    p=OUT/"wikidata_locator_diagnostic.csv"
    with p.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)

    summary={"dataset":"Royal Society Wikidata DOB locator diagnostic v1","sample_total":len(rows),"royal_society_qid":rs_q,"fellow_of_royal_society_qid":frs_q,"groups":{},"bazi_variables_computed":0,"dob_values_accepted":0}
    for g in ("past_unresolved","current"):
        rr=[x for x in rows if x["sample_group"]==g]
        summary["groups"][g]={
          "n":len(rr),
          "resolved_locator":sum(x["locator_status"]=="resolved_locator" for x in rr),
          "locator_with_any_p569":sum(x["p569_any"]==1 for x in rr),
          "locator_with_exact_day_p569":sum(x["p569_exact_day"]==1 for x in rr),
          "ambiguous_or_missing":sum(x["locator_status"]!="resolved_locator" for x in rr)
        }
    summary["note"]="Wikidata is used only as a locator/support source. No DOB from this diagnostic is accepted without validation against the preregistered source hierarchy."
    (OUT/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
