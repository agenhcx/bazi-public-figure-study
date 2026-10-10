#!/usr/bin/env python3
from __future__ import annotations
import argparse, csv, html, json, re, time, urllib.error, urllib.parse, urllib.request
from pathlib import Path

DIRECT=Path("data/direct_validation_inputs")
IDA=Path("data/current_locator_identity_audit_input")
OUTBASE=Path("data/royal_society_whoswho_authority_crossvalidation_v1")
API="https://www.wikidata.org/w/api.php"
UA="bazi-public-figure-study/1.0 (Royal Society Who's Who authority cross-validation; no BaZi)"

SPECS=[
 ("GND","P227"),
 ("BnF","P268"),
 ("Czech National Authority","P691"),
]
MONTHS=["January","February","March","April","May","June","July","August","September","October","November","December"]

def read_csv(p):
    with p.open("r",encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
def write_csv(p,rows,fields):
    with p.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore");w.writeheader();w.writerows(rows)

def wd_entities(qids):
    out={};qids=list(dict.fromkeys(qids));batch=20
    for i in range(0,len(qids),batch):
        part=qids[i:i+batch]
        qs=urllib.parse.urlencode({"action":"wbgetentities","ids":"|".join(part),"props":"claims","format":"json","maxlag":5})
        last=None
        for a in range(10):
            try:
                req=urllib.request.Request(API+"?"+qs,headers={"User-Agent":UA,"Accept":"application/json"})
                with urllib.request.urlopen(req,timeout=60) as r:data=json.load(r)
                if data.get("error"):
                    last=RuntimeError(json.dumps(data["error"],ensure_ascii=False))
                    time.sleep(min(60,3*(a+1)));continue
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
        print("wikidata batch",i//batch+1)
        time.sleep(1.0)
    return out

def claim_string(ent,pid):
    for st in ent.get("claims",{}).get(pid,[]) or []:
        v=st.get("mainsnak",{}).get("datavalue",{}).get("value")
        if isinstance(v,str) and v:return v
    return ""

def source_urls(label,aid):
    if label=="GND":
        return [f"https://d-nb.info/gnd/{aid}/about/lds",f"https://explore.gnd.network/gnd/{aid}"]
    if label=="BnF":
        return [f"https://catalogue.bnf.fr/ark:/12148/cb{aid}",f"https://data.bnf.fr/ark:/12148/cb{aid}"]
    if label=="Czech National Authority":
        q=urllib.parse.quote(f"ica={aid}")
        return [f"https://aleph.nkp.cz/F/?ccl_term={q}&func=find-c&local_base=aut"]
    return []

def fetch(url,retries=3):
    last=""
    for a in range(retries):
        try:
            req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"text/html,application/rdf+xml,application/xml,application/json,text/plain,*/*;q=0.5"})
            with urllib.request.urlopen(req,timeout=35) as r:
                raw=r.read(2_500_000);ct=(r.headers.get("Content-Type") or "").lower()
                txt=html.unescape(raw.decode("utf-8",errors="replace"))
                txt=re.sub(r"(?is)<script\b.*?</script>"," ",txt)
                txt=re.sub(r"(?is)<style\b.*?</style>"," ",txt)
                txt=re.sub(r"(?s)<[^>]+>"," ",txt)
                txt=re.sub(r"\s+"," ",txt)
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

def date_match(text,iso):
    if not text or not iso:return ""
    y,m,d=map(int,iso.split("-"));mn=MONTHS[m-1]
    pats=[
      ("iso",rf"(?<!\d){y:04d}-0?{m}-0?{d}(?!\d)"),
      ("named_dmy",rf"(?<!\w)0?{d}(?:st|nd|rd|th)?\s+{mn}\s*,?\s*{y}(?!\d)"),
      ("named_mdy",rf"(?<!\w){mn}\s+0?{d}(?:st|nd|rd|th)?\s*,?\s*{y}(?!\d)"),
      ("numeric_dmy",rf"(?<!\d)0?{d}[./-]0?{m}[./-]{y}(?!\d)"),
      ("numeric_ymd",rf"(?<!\d){y}[./-]0?{m}[./-]0?{d}(?!\d)"),
      ("compact_ymd",rf"(?<!\d){y:04d}{m:02d}{d:02d}(?!\d)")
    ]
    for style,p in pats:
        if re.search(p,text,re.I):return style
    return ""

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--shard-index",type=int,required=True);ap.add_argument("--shard-count",type=int,required=True);a=ap.parse_args()
    dfiles=list(DIRECT.rglob("direct_reference_validation.csv"))
    if len(dfiles)!=4:raise RuntimeError(f"expected 4 direct shards, got {dfiles}")
    rows=[]
    for p in dfiles:rows.extend(read_csv(p))
    # One row per person whose original direct reference was Who's Who and failed acceptance.
    wh=[]
    seen=set()
    for r in sorted(rows,key=lambda x:x["cohort_key"]):
        if (r.get("reference_domain") or "")!="ukwhoswho.com":continue
        if str(r.get("accepted_direct_reference") or "0")=="1":continue
        if r["cohort_key"] in seen:continue
        seen.add(r["cohort_key"]);wh.append(r)
    if len(wh)!=29:raise RuntimeError(f"expected 29 Who's Who blocked people, got {len(wh)}")

    afiles=list(IDA.rglob("locator_identity_audit.csv"))
    if len(afiles)!=1:raise RuntimeError(f"expected identity audit input, got {afiles}")
    ida={r["cohort_key"]:r for r in read_csv(afiles[0])}

    shard=[r for i,r in enumerate(wh) if i%a.shard_count==a.shard_index]
    ents=wd_entities([r["wikidata_qid"] for r in shard])
    out=[]
    for idx,r in enumerate(shard,1):
        iso=(r.get("candidate_dob") or "").strip()
        ent=ents.get(r["wikidata_qid"],{})
        identity_flag=int((ida.get(r["cohort_key"],{}).get("identity_flag") or "0"))
        attempts=[]
        accepted=None
        for label,pid in SPECS:
            aid=claim_string(ent,pid)
            if not aid:continue
            for u in source_urls(label,aid):
                f=fetch(u);style=date_match(f.get("text",""),iso)
                rec={"source_label":label,"authority_pid":pid,"authority_id":aid,"source_url":u,
                     "http_status":f.get("status",""),"content_type":f.get("content_type",""),
                     "text_len":len(f.get("text","")),"date_match_style":style}
                attempts.append(rec)
                if style and not identity_flag:
                    accepted=rec;break
                time.sleep(.2)
            if accepted:break
        best=accepted or (attempts[0] if attempts else {})
        out.append({
          "cohort_key":r["cohort_key"],"display_name":r["display_name"],"wikidata_qid":r["wikidata_qid"],
          "candidate_dob":iso,"identity_flag":identity_flag,
          "validated_source_label":best.get("source_label",""),"authority_pid":best.get("authority_pid",""),
          "authority_id":best.get("authority_id",""),"validated_source_url":best.get("source_url",""),
          "http_status":best.get("http_status",""),"date_match_style":best.get("date_match_style",""),
          "accepted_authority_crossvalidation":int(bool(accepted)),
          "acceptance_reason":"independent authority record directly contains same exact DOB and current-Fellow identity audit passed" if accepted else "",
          "attempts_json":json.dumps(attempts,ensure_ascii=False)
        })
        if idx%5==0:print("validated",idx,"/",len(shard))

    d=OUTBASE/f"shard_{a.shard_index:02d}_of_{a.shard_count:02d}";d.mkdir(parents=True,exist_ok=True)
    fields=list(out[0].keys()) if out else [];write_csv(d/"whoswho_authority_crossvalidation.csv",out,fields)
    summary={
      "dataset":"Royal Society current Who's Who authority cross-validation v1",
      "shard_index":a.shard_index,"shard_count":a.shard_count,"rows":len(out),
      "accepted_rows":sum(x["accepted_authority_crossvalidation"] for x in out),
      "accepted_unique_people":len({x["cohort_key"] for x in out if x["accepted_authority_crossvalidation"]}),
      "identity_flagged":sum(x["identity_flag"] for x in out),
      "accepted_by_source":{},
      "bazi_variables_computed":0
    }
    for label,_ in SPECS:
        summary["accepted_by_source"][label]=sum(x["accepted_authority_crossvalidation"] and x["validated_source_label"]==label for x in out)
    (d/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
