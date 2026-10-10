#!/usr/bin/env python3
from __future__ import annotations
import csv, html, json, re, time, urllib.parse, urllib.request, urllib.error
from pathlib import Path

IN=Path("data/royal_society_current_p569_provenance_input")
OUT=Path("data/royal_society_current_secondary_authority_diagnostic_v1")
API="https://www.wikidata.org/w/api.php"
UA="bazi-public-figure-study/1.0 (Royal Society secondary authority diagnostic; no BaZi)"

SPECS={
  "MacTutor History of Mathematics archive":("P1563","mactutor"),
  "SNAC":("P3430","snac"),
  "Encyclopedia of Australian Science and Innovation":("P4228","eoas"),
}
MONTHS=["January","February","March","April","May","June","July","August","September","October","November","December"]

def read_csv(p):
    with p.open("r",encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
def write_csv(p,rows,fields):
    with p.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore");w.writeheader();w.writerows(rows)

def wd_entities(qids):
    out={};qids=list(dict.fromkeys(qids))
    for i in range(0,len(qids),25):
        part=qids[i:i+25]
        qs=urllib.parse.urlencode({"action":"wbgetentities","ids":"|".join(part),"props":"claims","format":"json","maxlag":5})
        for a in range(8):
            try:
                req=urllib.request.Request(API+"?"+qs,headers={"User-Agent":UA,"Accept":"application/json"})
                with urllib.request.urlopen(req,timeout=60) as r:out.update(json.load(r).get("entities",{}))
                break
            except urllib.error.HTTPError as e:
                if e.code==429 and a<7:
                    try:wait=float(e.headers.get("Retry-After",""))
                    except:wait=5*(a+1)
                    time.sleep(max(5,min(60,wait)));continue
                if a<7:time.sleep(min(30,2**a));continue
                raise
        time.sleep(.8)
    return out

def claim_string(ent,pid):
    for st in ent.get("claims",{}).get(pid,[]) or []:
        v=st.get("mainsnak",{}).get("datavalue",{}).get("value")
        if isinstance(v,str) and v:return v
    return ""

def urls(kind,aid):
    if kind=="mactutor":return [f"https://mathshistory.st-andrews.ac.uk/Biographies/{aid}/"]
    if kind=="snac":return [f"https://snaccooperative.org/ark:/99166/{aid}"]
    if kind=="eoas":return [f"https://www.eoas.info/biogs/{aid}.htm",f"http://www.eoas.info/biogs/{aid}.htm"]
    return []

def fetch(url,retries=2):
    last=""
    for a in range(retries):
        try:
            req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"text/html,application/json,text/plain,*/*;q=0.5"})
            with urllib.request.urlopen(req,timeout=30) as r:
                raw=r.read(2_000_000);ct=(r.headers.get("Content-Type") or "").lower()
                txt=raw.decode("utf-8",errors="replace")
                txt=html.unescape(txt)
                txt=re.sub(r"(?is)<script\b.*?</script>"," ",txt)
                txt=re.sub(r"(?is)<style\b.*?</style>"," ",txt)
                txt=re.sub(r"(?s)<[^>]+>"," ",txt)
                txt=re.sub(r"\s+"," ",txt)
                return {"status":getattr(r,"status",200),"final_url":r.geturl(),"content_type":ct,"text":txt}
        except urllib.error.HTTPError as e:
            last=f"HTTP {e.code}"
            if e.code in (429,500,502,503,504) and a+1<retries:
                time.sleep(2+3*a);continue
            return {"status":e.code,"final_url":url,"content_type":"","text":"","error":last}
        except Exception as e:
            last=f"{type(e).__name__}: {e}"
            if a+1<retries:time.sleep(2+3*a);continue
            return {"status":"","final_url":url,"content_type":"","text":"","error":last}
    return {"status":"","final_url":url,"content_type":"","text":"","error":last}

def candidate_date(s):
    vals=[]
    for x in (s or "").split(";"):
        m=re.match(r"^[+-](\d{4})-(\d\d)-(\d\d)T",x.strip())
        if m:vals.append("-".join(m.groups()))
    u=sorted(set(vals))
    return u[0] if len(u)==1 else ""

def date_match(text,iso):
    if not text or not iso:return ""
    y,m,d=map(int,iso.split("-"));mn=MONTHS[m-1]
    pats=[
      ("iso",rf"(?<!\d){y:04d}-{m:02d}-{d:02d}(?!\d)"),
      ("named_dmy",rf"(?<!\w)0?{d}(?:st|nd|rd|th)?\s+{mn}\s*,?\s*{y}(?!\d)"),
      ("named_mdy",rf"(?<!\w){mn}\s+0?{d}(?:st|nd|rd|th)?\s*,?\s*{y}(?!\d)"),
      ("numeric_dmy",rf"(?<!\d)0?{d}[./-]0?{m}[./-]{y}(?!\d)"),
    ]
    for style,p in pats:
        if re.search(p,text,re.I):return style
    return ""

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    files=list(IN.rglob("p569_stated_in_sources_v1.csv"))
    if len(files)!=1:raise RuntimeError(f"expected one provenance input, got {files}")
    src=read_csv(files[0])
    sample=[]
    for label in SPECS:
        rr=[];seen=set()
        for r in sorted([x for x in src if x["source_label"]==label],key=lambda z:z["cohort_key"]):
            if r["cohort_key"] in seen:continue
            seen.add(r["cohort_key"]);rr.append(r)
            if len(rr)==6:break
        sample.extend(rr)
    ents=wd_entities([r["wikidata_qid"] for r in sample])
    out=[]
    for r in sample:
        pid,kind=SPECS[r["source_label"]];aid=claim_string(ents.get(r["wikidata_qid"],{}),pid);iso=candidate_date(r["p569_exact_values"])
        attempts=[];best={}
        for u in urls(kind,aid) if aid else []:
            f=fetch(u);style=date_match(f.get("text",""),iso)
            rec={"url":u,"status":f.get("status",""),"content_type":f.get("content_type",""),"text_len":len(f.get("text","")),"date_match_style":style}
            attempts.append(rec)
            if style:best=rec;break
            if not best:best=rec
            time.sleep(.25)
        out.append({
          "cohort_key":r["cohort_key"],"display_name":r["display_name"],"wikidata_qid":r["wikidata_qid"],
          "source_label":r["source_label"],"authority_pid":pid,"authority_id":aid,"candidate_dob":iso,
          "tested_url":best.get("url",""),"http_status":best.get("status",""),"content_type":best.get("content_type",""),
          "text_len":best.get("text_len",""),"exact_date_match":int(bool(best.get("date_match_style"))),
          "date_match_style":best.get("date_match_style",""),"attempts_json":json.dumps(attempts,ensure_ascii=False),
          "acceptance_status":"diagnostic_only_not_accepted"
        })
        print(r["source_label"],r["display_name"],aid,best.get("status"),best.get("date_match_style"))
    fields=list(out[0].keys());write_csv(OUT/"secondary_authority_diagnostic.csv",out,fields)
    summary={"dataset":"Royal Society current secondary authority diagnostic v1","sample_n":len(out),"by_source":{},"dob_values_accepted":0,"bazi_variables_computed":0}
    for label in SPECS:
        rr=[x for x in out if x["source_label"]==label]
        summary["by_source"][label]={
          "n":len(rr),"identifier_found":sum(bool(x["authority_id"]) for x in rr),
          "http_200":sum(str(x["http_status"])=="200" for x in rr),
          "exact_date_match":sum(x["exact_date_match"] for x in rr)
        }
    (OUT/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
