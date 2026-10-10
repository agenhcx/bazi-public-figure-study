#!/usr/bin/env python3
from __future__ import annotations
import argparse, csv, json, re, time, urllib.parse, urllib.request, urllib.error
from pathlib import Path

IN=Path("data/royal_society_current_p569_provenance_input")
OUTBASE=Path("data/royal_society_current_authority_validation_v1")
WD="https://www.wikidata.org/w/api.php"
UA="bazi-public-figure-study/1.0 (Royal Society authority DOB validation; no BaZi)"

SPECS={
  "Integrated Authority File":("P227","gnd"),
  "BnF authorities":("P268","bnf"),
}

MONTHS=["January","February","March","April","May","June","July","August","September","October","November","December"]

def read_csv(p):
    with p.open("r",encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))

def write_csv(p,rows,fields):
    with p.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore");w.writeheader();w.writerows(rows)

def wd_entities(qids):
    out={}; qids=list(dict.fromkeys(qids))
    for i in range(0,len(qids),50):
        qs=urllib.parse.urlencode({"action":"wbgetentities","ids":"|".join(qids[i:i+50]),"props":"claims","format":"json"})
        req=urllib.request.Request(WD+"?"+qs,headers={"User-Agent":UA})
        with urllib.request.urlopen(req,timeout=45) as r: out.update(json.load(r).get("entities",{}))
        time.sleep(.2)
    return out

def claim_string(ent,pid):
    for st in ent.get("claims",{}).get(pid,[]) or []:
        v=st.get("mainsnak",{}).get("datavalue",{}).get("value")
        if isinstance(v,str) and v:return v
    return ""

def source_urls(kind,aid):
    if kind=="gnd":
        return [f"https://d-nb.info/gnd/{aid}/about/lds",f"https://explore.gnd.network/gnd/{aid}"]
    if kind=="bnf":
        return [f"https://catalogue.bnf.fr/ark:/12148/cb{aid}",f"https://data.bnf.fr/ark:/12148/cb{aid}"]
    return []

def fetch(url,retries=2):
    last=""
    for a in range(retries):
        try:
            req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"text/html,application/rdf+xml,application/xml,application/json,text/plain,*/*;q=0.5"})
            with urllib.request.urlopen(req,timeout=35) as r:
                raw=r.read(2_000_000); ct=(r.headers.get("Content-Type") or "").lower()
                return {"status":getattr(r,"status",200),"final_url":r.geturl(),"content_type":ct,"text":raw.decode("utf-8",errors="replace")}
        except urllib.error.HTTPError as e:
            last=f"HTTP {e.code}"
            if e.code in (429,500,502,503,504) and a+1<retries: time.sleep(2+a*3); continue
            return {"status":e.code,"final_url":url,"content_type":"","text":"","error":last}
        except Exception as e:
            last=f"{type(e).__name__}: {e}"
            if a+1<retries: time.sleep(2+a*3);continue
            return {"status":"","final_url":url,"content_type":"","text":"","error":last}
    return {"status":"","final_url":url,"content_type":"","text":"","error":last}

def unique_candidate(s):
    vals=[]
    for x in (s or "").split(";"):
        m=re.match(r"^[+-](\d{4})-(\d\d)-(\d\d)T",x.strip())
        if m: vals.append("-".join(m.groups()))
    u=sorted(set(vals))
    return u[0] if len(u)==1 else ""

def date_match(text,iso):
    if not text or not iso:return ""
    y,m,d=map(int,iso.split("-")); mn=MONTHS[m-1]
    pats=[
      ("iso",rf"(?<!\d){y:04d}-{m:02d}-{d:02d}(?!\d)"),
      ("named_dmy",rf"(?<!\w){d}\s+{mn}\s+{y}(?!\d)"),
      ("named_mdy",rf"(?<!\w){mn}\s+{d},?\s+{y}(?!\d)"),
      ("numeric_dmy",rf"(?<!\d)0?{d}[./-]0?{m}[./-]{y}(?!\d)"),
    ]
    for style,p in pats:
        if re.search(p,text,re.I):return style
    return ""

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--shard-index",type=int,required=True);ap.add_argument("--shard-count",type=int,required=True);a=ap.parse_args()
    files=list(IN.rglob("p569_stated_in_sources_v1.csv"))
    if len(files)!=1:raise RuntimeError(f"expected one provenance input, got {files}")
    src=read_csv(files[0])

    # one row per person/source; require an exact unique P569 candidate
    selected=[];seen=set()
    for r in src:
        if r["source_label"] not in SPECS:continue
        iso=unique_candidate(r["p569_exact_values"])
        if not iso:continue
        k=(r["cohort_key"],r["source_label"])
        if k in seen:continue
        seen.add(k);selected.append(r)
    selected=sorted(selected,key=lambda r:(r["cohort_key"],r["source_label"]))
    rows=[r for i,r in enumerate(selected) if i%a.shard_count==a.shard_index]
    ents=wd_entities([r["wikidata_qid"] for r in rows])

    out=[]
    for idx,r in enumerate(rows,1):
        pid,kind=SPECS[r["source_label"]]; aid=claim_string(ents.get(r["wikidata_qid"],{}),pid); iso=unique_candidate(r["p569_exact_values"])
        attempts=[];matched=None
        for u in source_urls(kind,aid) if aid else []:
            f=fetch(u); style=date_match(f.get("text",""),iso)
            rec={"url":u,"status":f.get("status",""),"content_type":f.get("content_type",""),"text_len":len(f.get("text","")),"date_match_style":style}
            attempts.append(rec)
            if style:
                matched=rec;break
            time.sleep(.25)
        if matched is None:matched=attempts[0] if attempts else {}
        accepted=bool(aid and matched.get("date_match_style"))
        out.append({
          "cohort_key":r["cohort_key"],"display_name":r["display_name"],"wikidata_qid":r["wikidata_qid"],
          "candidate_dob":iso,"source_label":r["source_label"],"authority_pid":pid,"authority_id":aid,
          "validated_source_url":matched.get("url",""),"http_status":matched.get("status",""),
          "content_type":matched.get("content_type",""),"date_match_style":matched.get("date_match_style",""),
          "accepted_authority_record":int(accepted),
          "acceptance_reason":"P569 cites authority source; matching person authority ID; original authority record visibly contains same unique exact DOB" if accepted else "",
          "attempts_json":json.dumps(attempts,ensure_ascii=False)
        })
        if idx%10==0:print("validated",idx,"/",len(rows))

    d=OUTBASE/f"shard_{a.shard_index:02d}_of_{a.shard_count:02d}";d.mkdir(parents=True,exist_ok=True)
    fields=list(out[0].keys()) if out else []
    write_csv(d/"authority_validation.csv",out,fields)
    summary={
      "dataset":"Royal Society current authority DOB validation v1",
      "shard_index":a.shard_index,"shard_count":a.shard_count,
      "rows":len(out),"accepted_rows":sum(x["accepted_authority_record"] for x in out),
      "accepted_unique_people":len({x["cohort_key"] for x in out if x["accepted_authority_record"]}),
      "by_source":{},
      "bazi_variables_computed":0
    }
    for label in SPECS:
        rr=[x for x in out if x["source_label"]==label]
        summary["by_source"][label]={"rows":len(rr),"accepted":sum(x["accepted_authority_record"] for x in rr)}
    (d/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
