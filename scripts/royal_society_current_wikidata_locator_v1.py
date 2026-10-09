#!/usr/bin/env python3
from __future__ import annotations
import argparse, csv, json, re, time, urllib.parse, urllib.request, urllib.error
from pathlib import Path
from collections import Counter

ROSTER=Path("data/royal_society_roster_freeze_v1/royal_society_fellows_roster_freeze_v1.csv")
OUTBASE=Path("data/royal_society_current_wikidata_locator_v1")
API="https://www.wikidata.org/w/api.php"
UA="bazi-public-figure-study/1.0 (Royal Society current-Fellow Wikidata locator; locator-only, no BaZi)"
SCI_WORDS=("scientist","physicist","chemist","biologist","mathematician","engineer","professor","academic","physician","astronomer","geologist","botanist","zoologist","geneticist","economist","computer scientist","medical","researcher")

def api(params,retries=8):
    params=dict(params); params.setdefault("maxlag",5)
    qs=urllib.parse.urlencode(params,doseq=True); last=None
    for a in range(retries):
        try:
            req=urllib.request.Request(API+"?"+qs,headers={"User-Agent":UA,"Accept":"application/json"})
            with urllib.request.urlopen(req,timeout=60) as r:
                data=json.load(r)
                time.sleep(0.9)
                return data
        except urllib.error.HTTPError as e:
            last=e
            if e.code==429 and a+1<retries:
                ra=e.headers.get("Retry-After","")
                try: wait=float(ra)
                except: wait=min(90,10*(a+1))
                time.sleep(max(10,min(120,wait))); continue
            if a+1<retries:
                time.sleep(min(45,2**a)); continue
            raise
        except Exception as e:
            last=e
            if a+1<retries:
                time.sleep(min(45,2**a)); continue
            raise
    raise RuntimeError(repr(last))

def norm(s):
    s=(s or "").lower()
    s=re.sub(r"\b(?:sir|dame|lord|lady|professor|prof|dr|rev|reverend)\b"," ",s)
    s=re.sub(r"\b(?:frs|fmedsci|cbe|obe|kbe|fba|fellow)\b"," ",s)
    return re.sub(r"[^a-z0-9]+","",s)

def search(q,limit=5):
    return api({"action":"wbsearchentities","search":q,"language":"en","uselang":"en","type":"item","limit":limit,"format":"json"}).get("search",[])

def item_id(label):
    xs=search(label,5); n=norm(label)
    for x in xs:
        if norm(x.get("label",""))==n:return x["id"]
    return xs[0]["id"] if xs else ""

def batch_entities(ids):
    out={}; ids=list(dict.fromkeys(x for x in ids if x))
    for i in range(0,len(ids),50):
        part=ids[i:i+50]
        d=api({"action":"wbgetentities","ids":"|".join(part),"props":"claims|labels|aliases|descriptions","languages":"en","format":"json"})
        out.update(d.get("entities",{}))
    return out

def claim_items(ent,pid):
    vals=[]
    for st in ent.get("claims",{}).get(pid,[]):
        v=st.get("mainsnak",{}).get("datavalue",{}).get("value")
        if isinstance(v,dict) and "id" in v: vals.append(v["id"])
    return vals

def aliases(ent):
    return [x.get("value","") for x in ent.get("aliases",{}).get("en",[])]

def p569_statements(ent):
    out=[]
    for st in ent.get("claims",{}).get("P569",[]):
        sn=st.get("mainsnak",{}); v=sn.get("datavalue",{}).get("value")
        if not isinstance(v,dict) or "time" not in v: continue
        t=v["time"]; prec=int(v.get("precision",0) or 0)
        m=re.match(r"^[+-](\d+)-(\d\d)-(\d\d)T",t)
        if not m: continue
        y,mo,d=map(int,m.groups())
        refs=[]
        for ref in st.get("references",[]) or []:
            rr={"hash":ref.get("hash",""),"P854":[],"P248":[],"P813":[]}
            for pid in ("P854","P248","P813"):
                for snak in ref.get("snaks",{}).get(pid,[]) or []:
                    dv=snak.get("datavalue",{}).get("value")
                    if pid=="P248" and isinstance(dv,dict) and "id" in dv: rr[pid].append(dv["id"])
                    elif pid=="P813" and isinstance(dv,dict) and "time" in dv: rr[pid].append(dv["time"])
                    elif isinstance(dv,str): rr[pid].append(dv)
            refs.append(rr)
        out.append({"time":t,"precision":prec,"year":y,"month":mo,"day":d,"rank":st.get("rank","normal"),"references":refs})
    return out

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--shard-index",type=int,required=True)
    ap.add_argument("--shard-count",type=int,required=True)
    a=ap.parse_args()
    if not 0<=a.shard_index<a.shard_count: raise SystemExit("bad shard args")

    with ROSTER.open("r",encoding="utf-8-sig",newline="") as f:
        current=[r for r in csv.DictReader(f) if r["status_at_source"]=="current"]
    if len(current)!=1570: raise RuntimeError(f"Expected 1570 current Fellows, got {len(current)}")
    current=sorted(current,key=lambda r:r["cohort_key"])
    rows=[r for i,r in enumerate(current) if i%a.shard_count==a.shard_index]

    # Fixed Wikidata identifiers established by the successful 120-person diagnostic.
    rs_q="Q123885"
    frs_q="Q15631401"
    print("Royal Society item",rs_q,"FRS item",frs_q,"shard",a.shard_index,"rows",len(rows))

    searches={}; all_ids=[]
    for i,r in enumerate(rows,1):
        xs=search(r["display_name"],5)
        searches[r["cohort_key"]]=xs
        all_ids.extend(x["id"] for x in xs)
        if i%25==0: print("searched",i,"/",len(rows))

    ents=batch_entities(all_ids)
    out=[]
    for r in rows:
        target=norm(r["display_name"]); cand=[]
        for rank,x in enumerate(searches[r["cohort_key"]],1):
            e=ents.get(x["id"],{})
            lab=e.get("labels",{}).get("en",{}).get("value",x.get("label",""))
            desc=e.get("descriptions",{}).get("en",{}).get("value",x.get("description",""))
            al=aliases(e)
            exact_label=(norm(lab)==target or any(norm(z)==target for z in al))
            member=(rs_q in claim_items(e,"P463")) or (frs_q in claim_items(e,"P166"))
            sci=any(w in desc.lower() for w in SCI_WORDS)
            score=(5 if member else 0)+(3 if exact_label else 0)+(1 if sci else 0)+(1 if rank==1 else 0)
            cand.append({"id":x["id"],"rank":rank,"label":lab,"description":desc,"score":score,"member":int(member),"exact_label":int(exact_label),"science_desc":int(sci),"p569":p569_statements(e)})
        cand=sorted(cand,key=lambda z:(-z["score"],z["rank"]))
        best=cand[0] if cand else None
        second=cand[1] if len(cand)>1 else None
        high=bool(best and best["member"] and best["exact_label"])
        medium=bool(best and not high and best["exact_label"] and best["science_desc"] and best["rank"]==1 and (not second or best["score"]>second["score"]))
        resolved=high or medium
        exact=[d for d in (best["p569"] if resolved else []) if d["precision"]>=11 and d["month"]>0 and d["day"]>0]
        ref_urls=sorted({u for d in exact for rr in d["references"] for u in rr["P854"]})
        stated_in=sorted({q for d in exact for rr in d["references"] for q in rr["P248"]})
        out.append({
          "cohort_key":r["cohort_key"],"record_id":r["source_id"],"display_name":r["display_name"],
          "election_year":r.get("election_year",""),"source_url":r.get("source_url",""),
          "wikidata_qid":best["id"] if resolved else "",
          "locator_confidence":"high_membership_exact_name" if high else ("medium_exact_name_science_rank1" if medium else "unresolved"),
          "match_score":best["score"] if resolved else "",
          "candidate_label":best["label"] if resolved else "",
          "candidate_description":best["description"] if resolved else "",
          "membership_signal":best["member"] if resolved else "",
          "p569_any":int(bool(best and resolved and best["p569"])),
          "p569_exact_day":int(bool(exact)),
          "p569_exact_values":";".join(d["time"] for d in exact),
          "p569_reference_urls":";".join(ref_urls),
          "p569_stated_in_qids":";".join(stated_in),
          "acceptance_status":"locator_only_not_accepted"
        })

    d=OUTBASE/f"shard_{a.shard_index:02d}_of_{a.shard_count:02d}"; d.mkdir(parents=True,exist_ok=True)
    fields=list(out[0].keys())
    p=d/"current_wikidata_locator.csv"
    with p.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(out)
    summary={
      "dataset":"Royal Society current Fellows Wikidata locator v1",
      "shard_index":a.shard_index,"shard_count":a.shard_count,"rows":len(out),
      "resolved_locator":sum(x["wikidata_qid"]!="" for x in out),
      "high_confidence_locator":sum(x["locator_confidence"]=="high_membership_exact_name" for x in out),
      "medium_confidence_locator":sum(x["locator_confidence"].startswith("medium_") for x in out),
      "locator_with_any_p569":sum(x["p569_any"]==1 for x in out),
      "locator_with_exact_day_p569":sum(x["p569_exact_day"]==1 for x in out),
      "exact_p569_with_reference_url":sum(x["p569_exact_day"]==1 and bool(x["p569_reference_urls"]) for x in out),
      "dob_values_accepted":0,"bazi_variables_computed":0,
      "note":"Wikidata is locator-only. P569 values and references are candidate evidence for later validation under the frozen source hierarchy; none are accepted here."
    }
    (d/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=="__main__": main()
