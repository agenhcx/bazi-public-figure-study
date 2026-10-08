#!/usr/bin/env python3
from __future__ import annotations
import csv, json, re, time, urllib.parse, urllib.request, urllib.error
import xml.etree.ElementTree as ET
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

IN=Path("data/nas_ambiguous_qid_affiliation_candidates_v1.csv")
OUT=Path("data/nas_ambiguous_qid_provenance_v1.csv")
SUMMARY=Path("data/nas_ambiguous_qid_provenance_summary_v1.json")
UA="bazi-public-figure-study/1.0 (ambiguous-QID provenance audit; no BaZi computation)"
NS={"m":"http://www.loc.gov/MARC21/slim"}

def read_csv(p):
    with p.open("r",encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
def write_csv(p,rows):
    fields=list(rows[0].keys()) if rows else []
    with p.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore");w.writeheader();w.writerows(rows)
def get(url,accept="application/json",retries=5):
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
            except Exception:delay=min(20,2**i)
            time.sleep(max(2,delay))
        except Exception as e:
            last=e
            if i+1>=retries:break
            time.sleep(min(20,2**i))
    return getattr(last,"code",""),b"",repr(last)
def parse_loc(data):
    root=ET.fromstring(data)
    rec=root if root.tag.endswith("record") else root.find(".//m:record",NS)
    out={"heading":"","f046":"","f670":[],"f678":[]}
    if rec is None:return out
    for f in rec.findall("m:datafield",NS):
        tag=f.attrib.get("tag","")
        sf=[(s.attrib.get("code",""),(s.text or "").strip()) for s in f.findall("m:subfield",NS)]
        joined=" ".join(v for _,v in sf if v).strip()
        if tag=="100":out["heading"]=joined
        elif tag=="046":out["f046"]+=((" || " if out["f046"] else "")+joined)
        elif tag=="670":out["f670"].append(joined)
        elif tag=="678":out["f678"].append(joined)
    return out
def exact_date(s):
    m=re.search(r"([12]\d{3})-(\d{2})-(\d{2})",str(s or ""))
    return "-".join(m.groups()) if m else ""
def mentions(text,iso):
    y,m,d=iso.split("-")
    month_names=["","january","february","march","april","may","june","july","august","september","october","november","december"]
    forms=[iso,f"{int(m)}/{int(d)}/{y}",f"{m}/{d}/{y}",f"{int(d)}/{int(m)}/{y}",f"{d}/{m}/{y}",
           f"{month_names[int(m)]} {int(d)} {y}",f"{month_names[int(m)]} {int(d)}, {y}",f"{int(d)} {month_names[int(m)]} {y}"]
    n=re.sub(r"[^a-z0-9]+"," ",str(text or "").lower()).strip()
    return int(any(re.sub(r"[^a-z0-9]+"," ",x.lower()).strip() in n for x in forms))
def gnd_extract(obj):
    if not isinstance(obj,dict):return {"dob":[],"source":"","bio":""}
    raw=obj.get("dateOfBirth",[])
    if not isinstance(raw,list):raw=[raw]
    vals=[]
    for x in raw:
        if isinstance(x,dict):
            for k in ("@value","value","label"):
                if x.get(k):vals.append(str(x[k]))
        elif x:vals.append(str(x))
    return {"dob":sorted(set(vals)),"source":json.dumps(obj.get("source",[]),ensure_ascii=False),"bio":json.dumps(obj.get("biographicalOrHistoricalInformation",[]),ensure_ascii=False)}

def datavalue_value(snak):
    try:return snak["datavalue"]["value"]
    except Exception:return None

def parse_wikidata_entity(qid):
    url=f"https://www.wikidata.org/wiki/Special:EntityData/{urllib.parse.quote(qid)}.json"
    st,data,err=get(url,"application/json")
    if not data:return {"ok":0,"error":err,"gnd":[],"loc":[],"p569":[],"url":url}
    obj=json.loads(data.decode("utf-8"))
    ent=(obj.get("entities") or {}).get(qid) or {}
    claims=ent.get("claims") or {}
    def ids(prop):
        vals=[]
        for c in claims.get(prop,[]):
            v=datavalue_value(c.get("mainsnak") or {})
            if isinstance(v,str):vals.append(v)
        return sorted(set(vals))
    p569=[]
    for c in claims.get("P569",[]):
        ms=c.get("mainsnak") or {}
        v=datavalue_value(ms)
        if not isinstance(v,dict):continue
        d=exact_date(v.get("time",""))
        precision=v.get("precision")
        refs=[]
        for ref in c.get("references") or []:
            snaks=ref.get("snaks") or {}
            stated=[]
            urls=[]
            for s in snaks.get("P248",[]):
                vv=datavalue_value(s)
                if isinstance(vv,dict) and vv.get("id"):stated.append(vv["id"])
            for s in snaks.get("P854",[]):
                vv=datavalue_value(s)
                if isinstance(vv,str):urls.append(vv)
            refs.append({"statedIn":sorted(set(stated)),"refUrls":sorted(set(urls))})
        p569.append({"date":d,"precision":precision,"references":refs})
    return {"ok":1,"error":"","gnd":ids("P227"),"loc":ids("P244"),"p569":p569,"url":url}

rows=read_csv(IN)
# Fetch the 14 Wikidata entities directly; no QLever dependency.
entity={}
with ThreadPoolExecutor(max_workers=5) as ex:
    fut={ex.submit(parse_wikidata_entity,r["resolved_qid"]):r["resolved_qid"] for r in rows}
    for f in as_completed(fut):
        q=fut[f]
        try:entity[q]=f.result()
        except Exception as e:entity[q]={"ok":0,"error":repr(e),"gnd":[],"loc":[],"p569":[],"url":""}

out=[]
for r in rows:
    iso=r["authority_candidate_dob"];qid=r["resolved_qid"]
    e=entity.get(qid,{"ok":0,"error":"missing entity result","gnd":[],"loc":[],"p569":[],"url":""})
    gnds=e.get("gnd",[]);locs=e.get("loc",[])

    loc_notes="";loc046="";loc_error=""
    for locid in locs:
        st,data,err=get(f"https://id.loc.gov/authorities/names/{urllib.parse.quote(locid)}.marcxml.xml","application/xml,text/xml;q=0.9,*/*;q=0.1")
        if err:loc_error+=((" || " if loc_error else "")+err)
        if data:
            p=parse_loc(data)
            loc046+=((" || " if loc046 else "")+p["f046"])
            loc_notes+=((" || " if loc_notes else "")+" || ".join(p["f670"]))
    loc_support=max(mentions(loc046,iso),mentions(loc_notes,iso))

    gnd_dobs=[];gnd_source="";gnd_bio="";gnd_error=""
    for gid in gnds:
        st,data,err=get(f"https://lobid.org/gnd/{urllib.parse.quote(gid)}.json","application/json")
        if err:gnd_error+=((" || " if gnd_error else "")+err)
        if data:
            g=gnd_extract(json.loads(data.decode("utf-8")))
            gnd_dobs+=g["dob"]
            gnd_source+=((" || " if gnd_source else "")+g["source"])
            gnd_bio+=((" || " if gnd_bio else "")+g["bio"])
    gnd_support=max(mentions("|".join(gnd_dobs),iso),mentions(gnd_source,iso),mentions(gnd_bio,iso))

    matching_claims=[x for x in e.get("p569",[]) if x.get("date")==iso and x.get("precision")==11]
    stated_in=sorted({qid2 for x in matching_claims for ref in x.get("references",[]) for qid2 in ref.get("statedIn",[])})
    ref_urls=sorted({u for x in matching_claims for ref in x.get("references",[]) for u in ref.get("refUrls",[])})
    ref_count=sum(len(x.get("references",[])) for x in matching_claims)
    external_ref=int(bool(stated_in or ref_urls))
    out.append({
      **r,
      "wikidata_entity_url":e.get("url",""),"wikidata_entity_fetch_ok":e.get("ok",0),"wikidata_entity_error":e.get("error",""),
      "loc_ids":"|".join(locs),"gnd_ids":"|".join(gnds),
      "loc_046":loc046,"loc_670_source_notes":loc_notes,"loc_explicit_date_support":loc_support,"loc_fetch_error":loc_error,
      "gnd_date_values":"|".join(sorted(set(gnd_dobs))),"gnd_source_metadata":gnd_source,"gnd_bio_metadata":gnd_bio,
      "gnd_explicit_date_support":gnd_support,"gnd_fetch_error":gnd_error,
      "wikidata_reference_row_count":ref_count,
      "wikidata_stated_in_qids":"|".join(stated_in),
      "wikidata_reference_urls":"|".join(ref_urls),
      "wikidata_has_external_reference":external_ref,
      "provenance_tier":"authority_explicit" if (loc_support or gnd_support) else ("wikidata_referenced" if external_ref else "wikidata_unreferenced")
    })

write_csv(OUT,out)
summary={
 "dataset":"NAS ambiguous-QID exact-DOB provenance audit v1",
 "candidate_rows":len(out),
 "wikidata_entity_fetch_successes":sum(int(x["wikidata_entity_fetch_ok"]) for x in out),
 "qlever_calls":0,
 "rows_with_loc_explicit_support":sum(int(x["loc_explicit_date_support"]) for x in out),
 "rows_with_gnd_explicit_support":sum(int(x["gnd_explicit_date_support"]) for x in out),
 "rows_with_wikidata_external_reference":sum(int(x["wikidata_has_external_reference"]) for x in out),
 "authority_explicit_rows":sum(x["provenance_tier"]=="authority_explicit" for x in out),
 "wikidata_referenced_rows":sum(x["provenance_tier"]=="wikidata_referenced" for x in out),
 "wikidata_unreferenced_rows":sum(x["provenance_tier"]=="wikidata_unreferenced" for x in out),
 "bazi_variables_computed":0,
 "decision_note":"Diagnostic only. Wikidata entity JSON is used directly to avoid QLever rate-limit/server instability. Authority-explicit means LOC/GND exposes the candidate exact date; Wikidata-referenced means matching precision-11 P569 has P248/P854 references requiring source-quality review. No DOB writes are made."
}
SUMMARY.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(summary,ensure_ascii=False,indent=2))
