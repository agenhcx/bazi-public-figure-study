#!/usr/bin/env python3
from __future__ import annotations
import argparse, csv, html, json, re, time, urllib.parse, urllib.request, urllib.error
from pathlib import Path

PROV=Path("data/royal_society_current_p569_provenance_input")
IDA=Path("data/royal_society_current_locator_identity_audit_input")
OUTBASE=Path("data/royal_society_current_secondary_authority_validation_v1")
API="https://www.wikidata.org/w/api.php"
UA="bazi-public-figure-study/1.0 (Royal Society MacTutor EOAS DOB validation; no BaZi)"

SPECS={
 "MacTutor History of Mathematics archive":("P1563","mactutor"),
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
    for i in range(0,len(qids),10):
        part=qids[i:i+10]
        qs=urllib.parse.urlencode({"action":"wbgetentities","ids":"|".join(part),"props":"claims","format":"json","maxlag":5})
        last=None
        for a in range(10):
            try:
                req=urllib.request.Request(API+"?"+qs,headers={"User-Agent":UA,"Accept":"application/json"})
                with urllib.request.urlopen(req,timeout=60) as r:data=json.load(r)
                if data.get("error"):
                    last=RuntimeError(json.dumps(data["error"],ensure_ascii=False));time.sleep(min(60,3*(a+1)));continue
                out.update(data.get("entities",{}));last=None;break
            except urllib.error.HTTPError as e:
                last=e
                if e.code==429 and a<9:
                    try:wait=float(e.headers.get("Retry-After",""))
                    except:wait=5*(a+1)
                    time.sleep(max(5,min(60,wait)));continue
                if a<9:time.sleep(min(30,2**a));continue
                raise
            except Exception as e:
                last=e
                if a<9:time.sleep(min(30,2**a));continue
                raise
        if last is not None:raise RuntimeError(f"Wikidata batch failed: {part}: {last}")
        time.sleep(1)
    return out

def claim_string(ent,pid):
    for st in ent.get("claims",{}).get(pid,[]) or []:
        v=st.get("mainsnak",{}).get("datavalue",{}).get("value")
        if isinstance(v,str) and v:return v
    return ""

def source_url(kind,aid):
    if kind=="mactutor":return f"https://mathshistory.st-andrews.ac.uk/Biographies/{aid}/"
    if kind=="eoas":return f"https://www.eoas.info/biogs/{aid}.htm"
    return ""

def fetch(url,retries=3):
    last=""
    for a in range(retries):
        try:
            req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"text/html,text/plain,*/*;q=0.5"})
            with urllib.request.urlopen(req,timeout=35) as r:
                raw=r.read(2_000_000);ct=(r.headers.get("Content-Type") or "").lower()
                txt=html.unescape(raw.decode("utf-8",errors="replace"))
                txt=re.sub(r"(?is)<script\b.*?</script>"," ",txt);txt=re.sub(r"(?is)<style\b.*?</style>"," ",txt)
                txt=re.sub(r"(?s)<[^>]+>"," ",txt);txt=re.sub(r"\s+"," ",txt)
                return {"status":getattr(r,"status",200),"final_url":r.geturl(),"content_type":ct,"text":txt}
        except urllib.error.HTTPError as e:
            last=f"HTTP {e.code}"
            if e.code in (429,500,502,503,504) and a+1<retries:time.sleep(2+3*a);continue
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
    u=sorted(set(vals));return u[0] if len(u)==1 else ""

def date_match(text,iso):
    if not text or not iso:return ""
    y,m,d=map(int,iso.split("-"));mn=MONTHS[m-1]
    pats=[("iso",rf"(?<!\d){y:04d}-{m:02d}-{d:02d}(?!\d)"),
          ("named_dmy",rf"(?<!\w)0?{d}(?:st|nd|rd|th)?\s+{mn}\s*,?\s*{y}(?!\d)"),
          ("named_mdy",rf"(?<!\w){mn}\s+0?{d}(?:st|nd|rd|th)?\s*,?\s*{y}(?!\d)"),
          ("numeric_dmy",rf"(?<!\d)0?{d}[./-]0?{m}[./-]{y}(?!\d)")]
    for style,p in pats:
        if re.search(p,text,re.I):return style
    return ""

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--shard-index",type=int,required=True);ap.add_argument("--shard-count",type=int,required=True);a=ap.parse_args()
    pf=list(PROV.rglob("p569_stated_in_sources_v1.csv"));af=list(IDA.rglob("locator_identity_audit.csv"))
    if len(pf)!=1 or len(af)!=1:raise RuntimeError(f"input invariant provenance={pf} identity={af}")
    src=read_csv(pf[0]);ida={r["cohort_key"]:r for r in read_csv(af[0])}
    selected=[];seen=set()
    for r in src:
        if r["source_label"] not in SPECS:continue
        iso=candidate_date(r["p569_exact_values"])
        if not iso:continue
        k=(r["cohort_key"],r["source_label"])
        if k in seen:continue
        seen.add(k);selected.append(r)
    selected=sorted(selected,key=lambda r:(r["cohort_key"],r["source_label"]))
    rows=[r for i,r in enumerate(selected) if i%a.shard_count==a.shard_index]
    ents=wd_entities([r["wikidata_qid"] for r in rows])
    out=[]
    for i,r in enumerate(rows,1):
        pid,kind=SPECS[r["source_label"]];aid=claim_string(ents.get(r["wikidata_qid"],{}),pid);iso=candidate_date(r["p569_exact_values"])
        u=source_url(kind,aid) if aid else "";f=fetch(u) if u else {"status":"","final_url":"","content_type":"","text":"","error":"missing_identifier"}
        style=date_match(f.get("text",""),iso);flag=int((ida.get(r["cohort_key"],{}).get("identity_flag") or "0"))
        accepted=bool(aid and style and not flag)
        out.append({
          "cohort_key":r["cohort_key"],"display_name":r["display_name"],"wikidata_qid":r["wikidata_qid"],"candidate_dob":iso,
          "source_label":r["source_label"],"authority_pid":pid,"authority_id":aid,"validated_source_url":u,
          "http_status":f.get("status",""),"date_match_style":style,"identity_flag":flag,
          "accepted_secondary_authority":int(accepted),
          "acceptance_reason":"original source page contains same unique exact DOB and locator passed current-Fellow chronology audit" if accepted else ""
        })
        if i%10==0:print("validated",i,"/",len(rows))
    d=OUTBASE/f"shard_{a.shard_index:02d}_of_{a.shard_count:02d}";d.mkdir(parents=True,exist_ok=True)
    fields=list(out[0].keys()) if out else [];write_csv(d/"secondary_authority_validation.csv",out,fields)
    summary={"dataset":"Royal Society current MacTutor EOAS DOB validation v1","shard_index":a.shard_index,"shard_count":a.shard_count,
             "rows":len(out),"accepted_rows":sum(x["accepted_secondary_authority"] for x in out),
             "accepted_unique_people":len({x["cohort_key"] for x in out if x["accepted_secondary_authority"]}),
             "identity_flagged_rejected":sum(x["identity_flag"] for x in out),"by_source":{},"bazi_variables_computed":0}
    for label in SPECS:
        rr=[x for x in out if x["source_label"]==label];summary["by_source"][label]={"rows":len(rr),"accepted":sum(x["accepted_secondary_authority"] for x in rr)}
    (d/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
