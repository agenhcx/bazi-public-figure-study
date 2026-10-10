#!/usr/bin/env python3
from __future__ import annotations
import csv, json, re, time, urllib.parse, urllib.request, urllib.error
from pathlib import Path

IN=Path("data/royal_society_current_p569_provenance_input")
OUT=Path("data/royal_society_current_authority_diagnostic_v1")
WD="https://www.wikidata.org/w/api.php"
UA="bazi-public-figure-study/1.0 (Royal Society authority DOB diagnostic; no BaZi)"

SPECS={
  "Integrated Authority File":("P227","gnd"),
  "BnF authorities":("P268","bnf"),
  "Library of Congress Authorities":("P244","loc"),
  "Library of Congress Name Authority File":("P244","loc"),
}

def read_csv(p):
    with p.open("r",encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))

def wd_entities(qids):
    out={}
    qids=list(dict.fromkeys(qids))
    for i in range(0,len(qids),50):
        qs=urllib.parse.urlencode({
          "action":"wbgetentities","ids":"|".join(qids[i:i+50]),
          "props":"claims","format":"json"
        })
        req=urllib.request.Request(WD+"?"+qs,headers={"User-Agent":UA})
        with urllib.request.urlopen(req,timeout=40) as r:
            out.update(json.load(r).get("entities",{}))
        time.sleep(.2)
    return out

def claim_string(ent,pid):
    for st in ent.get("claims",{}).get(pid,[]) or []:
        v=st.get("mainsnak",{}).get("datavalue",{}).get("value")
        if isinstance(v,str) and v:return v
    return ""

def urls(kind,aid):
    if kind=="gnd":
        return [
          f"https://d-nb.info/gnd/{aid}/about/lds",
          f"https://explore.gnd.network/gnd/{aid}",
        ]
    if kind=="bnf":
        return [
          f"https://catalogue.bnf.fr/ark:/12148/cb{aid}",
          f"https://data.bnf.fr/ark:/12148/cb{aid}",
        ]
    if kind=="loc":
        return [
          f"https://id.loc.gov/authorities/names/{aid}.json",
          f"https://id.loc.gov/authorities/names/{aid}.html",
        ]
    return []

def fetch(url):
    try:
        req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"text/html,application/json,application/ld+json,application/rdf+xml,text/plain,*/*;q=0.5"})
        with urllib.request.urlopen(req,timeout=30) as r:
            raw=r.read(2_000_000)
            ct=(r.headers.get("Content-Type") or "").lower()
            try:text=raw.decode("utf-8",errors="replace")
            except:text=str(raw)
            return {"status":getattr(r,"status",200),"final_url":r.geturl(),"content_type":ct,"text":text}
    except urllib.error.HTTPError as e:
        return {"status":e.code,"final_url":url,"content_type":"","text":""}
    except Exception as e:
        return {"status":type(e).__name__+":"+str(e),"final_url":url,"content_type":"","text":""}

def candidate_date(s):
    vals=[]
    for x in (s or "").split(";"):
        m=re.match(r"^[+-](\d{4})-(\d\d)-(\d\d)T",x.strip())
        if m: vals.append("-".join(m.groups()))
    return vals[0] if len(set(vals))==1 else ""

def patterns(iso):
    if not iso:return []
    y,m,d=map(int,iso.split("-"))
    names=["January","February","March","April","May","June","July","August","September","October","November","December"]
    mn=names[m-1]
    return [
      rf"(?<!\d){y:04d}-{m:02d}-{d:02d}(?!\d)",
      rf"(?<!\d){d}\s+{mn}\s+{y}(?!\d)",
      rf"(?<!\d){mn}\s+{d},?\s+{y}(?!\d)",
      rf"(?<!\d){d:02d}[./-]{m:02d}[./-]{y}(?!\d)",
      rf"(?<!\d){y}[./-]{m:02d}[./-]{d:02d}(?!\d)",
    ]

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    files=list(IN.rglob("p569_stated_in_sources_v1.csv"))
    if len(files)!=1:raise RuntimeError(f"expected one input, got {files}")
    rows=read_csv(files[0])

    sample=[]
    for label in ["Integrated Authority File","BnF authorities","Library of Congress Authorities"]:
        rr=[]
        seen=set()
        for r in sorted([x for x in rows if x["source_label"]==label],key=lambda z:z["cohort_key"]):
            if r["cohort_key"] in seen:continue
            seen.add(r["cohort_key"]); rr.append(r)
            if len(rr)==6:break
        sample.extend(rr)

    ents=wd_entities([r["wikidata_qid"] for r in sample])
    out=[]
    for r in sample:
        pid,kind=SPECS[r["source_label"]]
        aid=claim_string(ents.get(r["wikidata_qid"],{}),pid)
        iso=candidate_date(r["p569_exact_values"])
        attempts=[]
        for u in urls(kind,aid) if aid else []:
            f=fetch(u)
            txt=f["text"]
            matches=[p for p in patterns(iso) if re.search(p,txt,re.I)]
            attempts.append({"url":u,"status":f["status"],"content_type":f["content_type"],"matched":bool(matches),"text_len":len(txt)})
            if f["status"]==200 and matches:break
            time.sleep(.3)
        best=next((x for x in attempts if x["matched"]), attempts[0] if attempts else {})
        out.append({
          "cohort_key":r["cohort_key"],"display_name":r["display_name"],"wikidata_qid":r["wikidata_qid"],
          "source_label":r["source_label"],"authority_pid":pid,"authority_id":aid,
          "candidate_dob":iso,"tested_url":best.get("url",""),"http_status":best.get("status",""),
          "content_type":best.get("content_type",""),"text_len":best.get("text_len",""),
          "exact_date_match":int(bool(best.get("matched"))),
          "attempts_json":json.dumps(attempts,ensure_ascii=False),
          "acceptance_status":"diagnostic_only_not_accepted"
        })
        print(r["source_label"],r["display_name"],aid,best.get("status"),best.get("matched"))

    p=OUT/"authority_diagnostic.csv"
    fields=list(out[0].keys())
    with p.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(out)
    summary={
      "dataset":"Royal Society current authority DOB diagnostic v1",
      "sample_n":len(out),
      "by_source":{},
      "exact_matches":sum(x["exact_date_match"] for x in out),
      "dob_values_accepted":0,"bazi_variables_computed":0
    }
    for label in ["Integrated Authority File","BnF authorities","Library of Congress Authorities"]:
        rr=[x for x in out if x["source_label"]==label]
        summary["by_source"][label]={
          "n":len(rr),"authority_id_found":sum(bool(x["authority_id"]) for x in rr),
          "http_200_any":sum('"status": 200' in x["attempts_json"] for x in rr),
          "exact_date_match":sum(x["exact_date_match"] for x in rr)
        }
    (OUT/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=="__main__":main()
