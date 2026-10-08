#!/usr/bin/env python3
from __future__ import annotations

import csv
import datetime as dt
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

IN=Path("data/nas_pending_wikipedia_dob_candidates_v1.csv")
OUT=Path("data/nas_pending_authority_search_v1.csv")
SUMMARY=Path("data/nas_pending_authority_search_summary_v1.json")
UA="bazi-public-figure-study/1.0 (pending NAS authority search; no BaZi computation)"
NS={"m":"http://www.loc.gov/MARC21/slim"}

def read_csv(p):
    with p.open("r",encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
def write_csv(p,rows):
    fields=list(rows[0].keys()) if rows else []
    with p.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore"); w.writeheader(); w.writerows(rows)

def norm_name(s):
    s=re.sub(r"[^a-z0-9]+"," ",(s or "").lower())
    return " ".join(s.split())

def valid_date(s):
    s=str(s or "").strip()
    m=re.fullmatch(r"([12]\d{3})[-/.](\d{1,2})[-/.](\d{1,2})",s)
    if not m:return ""
    try:return dt.date(int(m.group(1)),int(m.group(2)),int(m.group(3))).isoformat()
    except:return ""

def get(url,accept="application/json",retries=5):
    last=None
    for i in range(retries):
        try:
            req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":accept})
            with urllib.request.urlopen(req,timeout=90) as r:
                return getattr(r,"status",200),r.read(),""
        except urllib.error.HTTPError as e:
            last=e
            if e.code==404:return 404,b"","HTTP 404"
            if i+1>=retries or e.code not in {429,500,502,503,504}:break
            try:delay=float(e.headers.get("Retry-After",""))
            except:delay=min(20.0,2.0**i)
            time.sleep(max(1.0,delay))
        except Exception as e:
            last=e
            if i+1>=retries:break
            time.sleep(min(20.0,2.0**i))
    return getattr(last,"code",""),b"",repr(last)

def json_get(url):
    st,data,err=get(url)
    if not data:return st,None,err
    try:return st,json.loads(data.decode("utf-8")),err
    except Exception as e:return st,None,(err+"; " if err else "")+repr(e)

def extract_loc_suggest(obj):
    pairs=[]
    def uri(v):
        return isinstance(v,str) and re.search(r"https?://id\.loc\.gov/authorities/names/n[o]?[0-9]+",v)
    # Common suggest2 response may be dict-based or OpenSearch list.
    if isinstance(obj,dict):
        # direct hits / results / records
        for key in ("hits","results","records","suggestions"):
            arr=obj.get(key)
            if isinstance(arr,list):
                for x in arr:
                    if isinstance(x,dict):
                        u=x.get("uri") or x.get("id") or x.get("@id") or x.get("url") or ""
                        label=x.get("label") or x.get("title") or x.get("name") or ""
                        if uri(u):pairs.append((str(label),str(u)))
        # recurse shallowly
        for v in obj.values():
            if isinstance(v,(dict,list)):
                pairs.extend(extract_loc_suggest(v))
    elif isinstance(obj,list):
        # OpenSearch style: [query,[labels],...,[uris]]
        labels=[]
        uris=[]
        for part in obj:
            if isinstance(part,list):
                if all(isinstance(x,str) for x in part):
                    if any(uri(x) for x in part): uris.extend(x for x in part if uri(x))
                    elif not labels: labels=part
            elif isinstance(part,(dict,list)):
                pairs.extend(extract_loc_suggest(part))
        for i,u in enumerate(uris):
            pairs.append((labels[i] if i<len(labels) else "",u))
    # unique
    seen=set(); out=[]
    for label,u in pairs:
        m=re.search(r"(https?://id\.loc\.gov/authorities/names/(n[o]?[0-9]+))",u)
        if not m:continue
        key=m.group(2)
        if key in seen:continue
        seen.add(key);out.append((label,m.group(1)))
    return out

def parse_loc_marc(data):
    root=ET.fromstring(data)
    rec=root if root.tag.endswith("record") else root.find(".//m:record",NS)
    if rec is None:return {}
    d={"heading":"","field_046":"","field_670":[]}
    for f in rec.findall("m:datafield",NS):
        tag=f.attrib.get("tag","")
        sf=[(s.attrib.get("code",""),(s.text or "").strip()) for s in f.findall("m:subfield",NS)]
        joined=" ".join(v for _,v in sf if v).strip()
        if tag=="100":d["heading"]=joined
        elif tag=="046":d["field_046"]+=((" || " if d["field_046"] else "")+joined)
        elif tag=="670":d["field_670"].append(joined)
    return d

def date_mentioned(text,iso):
    if not iso:return 0
    d=dt.date.fromisoformat(iso)
    months=["","january","february","march","april","may","june","july","august","september","october","november","december"]
    forms={
      iso,f"{d.month}/{d.day}/{d.year}",f"{d.month:02d}/{d.day:02d}/{d.year}",
      f"{months[d.month]} {d.day} {d.year}",f"{months[d.month]} {d.day}, {d.year}",
      f"{d.day} {months[d.month]} {d.year}"
    }
    n=re.sub(r"[^a-z0-9]+"," ",(text or "").lower()).strip()
    return int(any(re.sub(r"[^a-z0-9]+"," ",x.lower()).strip() in n for x in forms))

def gnd_dates(obj):
    vals=set()
    if not isinstance(obj,dict):return []
    raw=obj.get("dateOfBirth",[])
    if not isinstance(raw,list):raw=[raw]
    for x in raw:
        if isinstance(x,dict):
            for k in ("@value","value","label"):
                z=valid_date(x.get(k,""))
                if z:vals.add(z)
        else:
            z=valid_date(x)
            if z:vals.add(z)
    return sorted(vals)

def gnd_name(obj):
    if not isinstance(obj,dict):return ""
    p=obj.get("preferredName","")
    if isinstance(p,dict):return p.get("@value","") or p.get("label","") or ""
    return str(p or "")

def loc_search(name):
    q=urllib.parse.quote(name)
    urls=[
      f"https://id.loc.gov/authorities/names/suggest2/?q={q}&count=20",
      f"https://id.loc.gov/authorities/names/suggest/?q={q}&count=20"
    ]
    pairs=[]; errors=[]
    for url in urls:
        st,obj,err=json_get(url)
        if err:errors.append(f"{url}: {err}")
        if obj is not None:
            pairs.extend(extract_loc_suggest(obj))
        if pairs:break
    # rank exact normalized label first, otherwise keep top few
    nn=norm_name(name)
    pairs=sorted(pairs,key=lambda x:(norm_name(x[0])!=nn, len(norm_name(x[0])), x[0]))
    return pairs[:10]," || ".join(errors)

def gnd_search(name):
    q=urllib.parse.quote(name)
    url=f"https://lobid.org/gnd/search?q={q}&format=json&size=20"
    st,obj,err=json_get(url)
    hits=[]
    if isinstance(obj,dict):
        arr=obj.get("member") or obj.get("members") or []
        if isinstance(arr,list):
            for x in arr:
                if not isinstance(x,dict):continue
                gid=str(x.get("gndIdentifier") or "").strip()
                label=gnd_name(x)
                if gid:hits.append((label,gid,x))
    nn=norm_name(name)
    hits=sorted(hits,key=lambda x:(norm_name(x[0])!=nn,len(norm_name(x[0])),x[0]))
    return hits[:10],err

def main():
    rows=read_csv(IN); out=[]
    for r in rows:
        name=r["name"]; cand=r["wikipedia_candidate_dob"]
        loc_hits,loc_search_error=loc_search(name)
        gnd_hits,gnd_search_error=gnd_search(name)

        # Inspect only candidates with exact/similar names.
        for source,label,ident,meta in (
            [("LOC",lab,uri.rsplit("/",1)[-1],None) for lab,uri in loc_hits] +
            [("GND",lab,gid,obj) for lab,gid,obj in gnd_hits]
        ):
            if source=="LOC":
                url=f"https://id.loc.gov/authorities/names/{ident}.marcxml.xml"
                st,data,err=get(url,accept="application/xml,text/xml;q=0.9,*/*;q=0.1")
                parsed={}
                if data:
                    try:parsed=parse_loc_marc(data)
                    except Exception as e:err=(err+"; " if err else "")+repr(e)
                heading=parsed.get("heading","")
                notes=" || ".join(parsed.get("field_670",[]))
                exact_hit=max(date_mentioned(parsed.get("field_046",""),cand),date_mentioned(notes,cand))
                birth_dates=cand if exact_hit else ""
                out.append({
                  **r,"authority_source":"LOC","authority_id":ident,"search_label":label,
                  "name_similarity_exact":int(norm_name(name)==norm_name(label) or norm_name(name) in norm_name(heading)),
                  "record_url":url,"fetch_status":st,"record_heading":heading,
                  "exact_birth_dates":birth_dates,"candidate_date_explicitly_mentioned":exact_hit,
                  "source_notes":notes,"search_error":loc_search_error,"fetch_error":err
                })
            else:
                obj=meta or {}
                url=f"https://lobid.org/gnd/{urllib.parse.quote(ident)}.json"
                st,full,err=json_get(url)
                if isinstance(full,dict):obj=full
                dates=gnd_dates(obj)
                notes=json.dumps({k:obj.get(k) for k in ("biographicalOrHistoricalInformation","source","professionOrOccupation","placeOfBirth") if k in obj},ensure_ascii=False)
                out.append({
                  **r,"authority_source":"GND","authority_id":ident,"search_label":label,
                  "name_similarity_exact":int(norm_name(name)==norm_name(label)),
                  "record_url":url,"fetch_status":st,"record_heading":gnd_name(obj),
                  "exact_birth_dates":"|".join(dates),
                  "candidate_date_explicitly_mentioned":int(cand in dates),
                  "source_notes":notes,"search_error":gnd_search_error,"fetch_error":err
                })

    write_csv(OUT,out)
    summary={
      "dataset":"NAS five pending Wikipedia DOB candidates: direct authority-name search v1",
      "input_rows":len(rows),
      "output_authority_hits":len(out),
      "loc_hits":sum(x["authority_source"]=="LOC" for x in out),
      "gnd_hits":sum(x["authority_source"]=="GND" for x in out),
      "exact_name_hits":sum(int(x["name_similarity_exact"]) for x in out),
      "hits_explicitly_supporting_wikipedia_candidate_date":sum(int(x["candidate_date_explicitly_mentioned"]) for x in out),
      "candidate_names_with_any_explicit_support":sorted({x["name"] for x in out if int(x["candidate_date_explicitly_mentioned"])==1}),
      "bazi_variables_computed":0,
      "decision_note":"Diagnostic only. Name-search hits are not accepted automatically; any candidate requires identity/provenance review before supplementing v12."
    }
    SUMMARY.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=="__main__":main()
