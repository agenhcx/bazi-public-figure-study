#!/usr/bin/env python3
from __future__ import annotations
import csv, datetime as dt, json, re, time, urllib.error, urllib.parse, urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

IN=Path("data/nas_global_qid_authority_candidates_v1.csv")
OUT=Path("data/nas_global_qid_authority_provenance_v1.csv")
SUMMARY=Path("data/nas_global_qid_authority_provenance_summary_v1.json")
UA="bazi-public-figure-study/1.0 (global-QID provenance audit; no BaZi computation)"
NS={"m":"http://www.loc.gov/MARC21/slim"}

MONTHS={1:["january","jan"],2:["february","feb"],3:["march","mar"],4:["april","apr"],5:["may"],6:["june","jun"],7:["july","jul"],8:["august","aug"],9:["september","sep","sept"],10:["october","oct"],11:["november","nov"],12:["december","dec"]}

def read_csv(p):
    with p.open("r",encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
def write_csv(p,rows):
    fields=list(rows[0].keys()) if rows else []
    with p.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore");w.writeheader();w.writerows(rows)
def get(url,accept,retries=5):
    last=None
    for i in range(retries):
        try:
            req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":accept})
            with urllib.request.urlopen(req,timeout=90) as r:return getattr(r,"status",200),r.read(),""
        except urllib.error.HTTPError as e:
            last=e
            if e.code==404:return 404,b"","HTTP 404"
            if i+1>=retries or e.code not in {429,500,502,503,504}:break
            try:delay=float(e.headers.get("Retry-After",""))
            except:delay=min(20,2**i)
            time.sleep(max(1,delay))
        except Exception as e:
            last=e
            if i+1>=retries:break
            time.sleep(min(20,2**i))
    return getattr(last,"code",""),b"",repr(last)
def candidate_forms(iso):
    d=dt.date.fromisoformat(iso);out={iso,iso.replace("-","/"),iso.replace("-",".")}
    out|={f"{d.month}/{d.day}/{d.year}",f"{d.month:02d}/{d.day:02d}/{d.year}",f"{d.day}/{d.month}/{d.year}",f"{d.day:02d}/{d.month:02d}/{d.year}"}
    for mon in MONTHS[d.month]:
        out|={f"{mon} {d.day} {d.year}",f"{mon} {d.day}, {d.year}",f"{mon}. {d.day}, {d.year}",f"{d.day} {mon} {d.year}",f"{d.day} {mon}. {d.year}"}
    return {re.sub(r"[^a-z0-9]+"," ",x.lower()).strip() for x in out}
def mentions(text,iso):
    n=re.sub(r"[^a-z0-9]+"," ",str(text or "").lower()).strip()
    return int(any(f and f in n for f in candidate_forms(iso)))
def parse_loc(data):
    root=ET.fromstring(data)
    rec=root if root.tag.endswith("record") else root.find(".//m:record",NS)
    if rec is None:return {"heading":"","f046":"","f670":[],"f678":[]}
    out={"heading":"","f046":"","f670":[],"f678":[]}
    for f in rec.findall("m:datafield",NS):
        tag=f.attrib.get("tag","")
        sf=[(s.attrib.get("code",""),(s.text or "").strip()) for s in f.findall("m:subfield",NS)]
        joined=" ".join(v for _,v in sf if v).strip()
        if tag=="100":out["heading"]=joined
        elif tag=="046":out["f046"]+=((" || " if out["f046"] else "")+joined)
        elif tag=="670":out["f670"].append(joined)
        elif tag=="678":out["f678"].append(joined)
    return out
def gnd_extract(obj):
    if not isinstance(obj,dict):return {"dob":[],"sources":"","bio":"","occupations":""}
    raw=obj.get("dateOfBirth",[])
    if not isinstance(raw,list):raw=[raw]
    dob=[]
    for x in raw:
        if isinstance(x,dict):
            for k in ("@value","value","label"):
                v=x.get(k)
                if v:dob.append(str(v))
        elif x:dob.append(str(x))
    src=obj.get("source",[])
    bio=obj.get("biographicalOrHistoricalInformation",[])
    occ=obj.get("professionOrOccupation",[])
    return {
      "dob":sorted(set(dob)),
      "sources":json.dumps(src,ensure_ascii=False),
      "bio":json.dumps(bio,ensure_ascii=False),
      "occupations":json.dumps(occ,ensure_ascii=False),
    }

rows=read_csv(IN);out=[]
for r in rows:
    iso=r["authority_candidate_dob"].strip()
    locid=(r.get("loc_ids") or "").strip()
    gndid=(r.get("gnd_ids") or "").strip()

    loc_url=f"https://id.loc.gov/authorities/names/{urllib.parse.quote(locid)}.marcxml.xml" if locid else ""
    loc_status="";loc_error="";loc={"heading":"","f046":"","f670":[],"f678":[]}
    if loc_url:
        loc_status,data,loc_error=get(loc_url,"application/xml,text/xml;q=0.9,*/*;q=0.1")
        if data:
            try:loc=parse_loc(data)
            except Exception as e:loc_error=(loc_error+"; " if loc_error else "")+repr(e)
    notes670=" || ".join(loc["f670"])
    notes678=" || ".join(loc["f678"])

    gnd_url=f"https://lobid.org/gnd/{urllib.parse.quote(gndid)}.json" if gndid else ""
    gnd_status="";gnd_error="";gnd={"dob":[],"sources":"","bio":"","occupations":""}
    if gnd_url:
        gnd_status,data,gnd_error=get(gnd_url,"application/json")
        if data:
            try:gnd=gnd_extract(json.loads(data.decode("utf-8")))
            except Exception as e:gnd_error=(gnd_error+"; " if gnd_error else "")+repr(e)

    loc_support=max(mentions(loc["f046"],iso),mentions(notes670,iso),mentions(notes678,iso))
    gnd_support=max(mentions("|".join(gnd["dob"]),iso),mentions(gnd["sources"],iso),mentions(gnd["bio"],iso))
    # Strong provenance means the exact date is explicitly present in a source-note/structured field,
    # but Jan-01 remains flagged for manual caution.
    jan1=int(iso[5:]=="01-01")
    out.append({
      **r,
      "loc_marc_url":loc_url,"loc_fetch_status":loc_status,"loc_fetch_error":loc_error,
      "loc_heading":loc["heading"],"loc_046":loc["f046"],
      "loc_670_source_notes":notes670,"loc_678_biographical_notes":notes678,
      "loc_explicitly_supports_candidate_date":loc_support,
      "gnd_url":gnd_url,"gnd_fetch_status":gnd_status,"gnd_fetch_error":gnd_error,
      "gnd_date_of_birth_values":"|".join(gnd["dob"]),
      "gnd_source_metadata":gnd["sources"],"gnd_biographical_metadata":gnd["bio"],
      "gnd_occupations":gnd["occupations"],
      "gnd_explicitly_supports_candidate_date":gnd_support,
      "candidate_is_jan1":jan1,
      "provenance_support_any":int(bool(loc_support or gnd_support)),
      "safe_for_manual_acceptance_review":int(bool((loc_support or gnd_support) and not jan1))
    })

write_csv(OUT,out)
summary={
 "dataset":"NAS global-QID authority provenance audit v1",
 "candidate_rows":len(out),
 "loc_records_fetched":sum(str(x["loc_fetch_status"])=="200" for x in out),
 "gnd_records_fetched":sum(str(x["gnd_fetch_status"])=="200" for x in out),
 "rows_loc_explicit_support":sum(int(x["loc_explicitly_supports_candidate_date"]) for x in out),
 "rows_gnd_explicit_support":sum(int(x["gnd_explicitly_supports_candidate_date"]) for x in out),
 "rows_any_explicit_support":sum(int(x["provenance_support_any"]) for x in out),
 "jan1_candidates_flagged":sum(int(x["candidate_is_jan1"]) for x in out),
 "rows_safe_for_manual_acceptance_review":sum(int(x["safe_for_manual_acceptance_review"]) for x in out),
 "supported_names":[x["name"] for x in out if int(x["provenance_support_any"])==1],
 "safe_review_names":[x["name"] for x in out if int(x["safe_for_manual_acceptance_review"])==1],
 "bazi_variables_computed":0,
 "decision_note":"Provenance diagnostic only. Exact dates are not written to v12. Jan-01 candidates remain blocked even if structurally present until source-note review excludes year-only normalization."
}
SUMMARY.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(summary,ensure_ascii=False,indent=2))
