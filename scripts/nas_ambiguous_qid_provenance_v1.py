#!/usr/bin/env python3
from __future__ import annotations
import csv, json, re, time, urllib.parse, urllib.request, urllib.error
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

IN=Path("data/nas_ambiguous_qid_affiliation_candidates_v1.csv")
OUT=Path("data/nas_ambiguous_qid_provenance_v1.csv")
SUMMARY=Path("data/nas_ambiguous_qid_provenance_summary_v1.json")
QLEVER="https://qlever.dev/api/wikidata"
UA="bazi-public-figure-study/1.0 (ambiguous-QID provenance audit; no BaZi computation)"
NS={"m":"http://www.loc.gov/MARC21/slim"}

def read_csv(p):
    with p.open("r",encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
def write_csv(p,rows):
    fields=list(rows[0].keys()) if rows else []
    with p.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore");w.writeheader();w.writerows(rows)
def run_sparql(q,retries=6):
    body=urllib.parse.urlencode({"query":q,"action":"tsv_export"}).encode()
    last=None
    for i in range(retries):
        req=urllib.request.Request(QLEVER,data=body,method="POST",headers={"User-Agent":UA,"Content-Type":"application/x-www-form-urlencoded","Accept":"text/tab-separated-values"})
        try:
            with urllib.request.urlopen(req,timeout=300) as r:raw=r.read().decode("utf-8-sig")
            break
        except urllib.error.HTTPError as e:
            last=e
            if i+1>=retries or e.code not in {429,500,502,503,504}:raise
            try:delay=float(e.headers.get("Retry-After",""))
            except Exception:delay=min(45,3*(2**i))
            time.sleep(max(3,delay))
        except Exception as e:
            last=e
            if i+1>=retries:raise
            time.sleep(min(30,3*(2**i)))
    rr=list(csv.reader(raw.splitlines(),delimiter="\t"))
    if not rr:return []
    h=[x.lstrip("?").strip() for x in rr[0]];out=[]
    for row in rr[1:]:
        row+=[""]*(len(h)-len(row));d={}
        for j,k in enumerate(h):
            v=(row[j] or "").strip()
            if v.startswith("<") and v.endswith(">"):v=v[1:-1]
            elif len(v)>=2 and v[0]=='"':
                e=v.rfind('"')
                if e>0:v=v[1:e]
            v=re.sub(r"@[A-Za-z][A-Za-z0-9-]*$","",v)
            d[k]=v
        out.append(d)
    return out
def get(url,accept,retries=4):
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
            except Exception:delay=min(15,2**i)
            time.sleep(max(2,delay))
        except Exception as e:
            last=e
            if i+1>=retries:break
            time.sleep(min(15,2**i))
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
    forms=[iso,f"{int(m)}/{int(d)}/{y}",f"{m}/{d}/{y}",f"{int(d)}/{int(m)}/{y}",f"{d}/{m}/{y}"]
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

rows=read_csv(IN)
qids=[r["resolved_qid"] for r in rows]
vals=" ".join("wd:"+q for q in qids)

# QLever call 1/2: P569 statement references for all 14 candidates.
refq=f"""PREFIX wd:<http://www.wikidata.org/entity/>
PREFIX p:<http://www.wikidata.org/prop/>
PREFIX ps:<http://www.wikidata.org/prop/statement/>
PREFIX prov:<http://www.w3.org/ns/prov#>
PREFIX pr:<http://www.wikidata.org/prop/reference/>
PREFIX rdfs:<http://www.w3.org/2000/01/rdf-schema#>
SELECT ?person ?dob ?statedIn ?statedInLabel ?refUrl WHERE {{
 VALUES ?person {{ {vals} }}
 ?person p:P569 ?stmt .
 ?stmt ps:P569 ?dob .
 OPTIONAL {{
   ?stmt prov:wasDerivedFrom ?ref .
   OPTIONAL {{ ?ref pr:P248 ?statedIn . OPTIONAL {{ ?statedIn rdfs:label ?statedInLabel . FILTER(LANG(?statedInLabel)="en") }} }}
   OPTIONAL {{ ?ref pr:P854 ?refUrl . }}
 }}
}}"""
refs=defaultdict(list)
for x in run_sparql(refq):
    qid=x.get("person","").rsplit("/",1)[-1]
    d=exact_date(x.get("dob",""))
    if qid and d:
        refs[(qid,d)].append({
            "statedIn":x.get("statedIn","").rsplit("/",1)[-1] if x.get("statedIn") else "",
            "statedInLabel":x.get("statedInLabel",""),
            "refUrl":x.get("refUrl","")
        })

# QLever call 2/2: authority IDs for all 14 candidates in one batch.
idq=f"""PREFIX wd:<http://www.wikidata.org/entity/>
PREFIX wdt:<http://www.wikidata.org/prop/direct/>
SELECT ?person ?gnd ?loc WHERE {{
 VALUES ?person {{ {vals} }}
 OPTIONAL {{ ?person wdt:P227 ?gnd . }}
 OPTIONAL {{ ?person wdt:P244 ?loc . }}
}}"""
auth=defaultdict(lambda:{"gnd":set(),"loc":set()})
for x in run_sparql(idq):
    qid=x.get("person","").rsplit("/",1)[-1]
    if not qid:continue
    if x.get("gnd"):auth[qid]["gnd"].add(x["gnd"])
    if x.get("loc"):auth[qid]["loc"].add(x["loc"])

out=[]
for r in rows:
    iso=r["authority_candidate_dob"];qid=r["resolved_qid"]
    gnds=sorted(auth[qid]["gnd"]);locs=sorted(auth[qid]["loc"])
    loc_notes="";loc046="";loc_error=""
    for locid in locs:
        st,data,err=get(f"https://id.loc.gov/authorities/names/{urllib.parse.quote(locid)}.marcxml.xml","application/xml,text/xml;q=0.9,*/*;q=0.1")
        if err:loc_error+=((" || " if loc_error else "")+err)
        if data:
            p=parse_loc(data);loc046+=((" || " if loc046 else "")+p["f046"]);loc_notes+=((" || " if loc_notes else "")+" || ".join(p["f670"]))
    loc_support=max(mentions(loc046,iso),mentions(loc_notes,iso))

    gnd_dobs=[];gnd_source="";gnd_bio="";gnd_error=""
    for gid in gnds:
        st,data,err=get(f"https://lobid.org/gnd/{urllib.parse.quote(gid)}.json","application/json")
        if err:gnd_error+=((" || " if gnd_error else "")+err)
        if data:
            g=gnd_extract(json.loads(data.decode("utf-8")));gnd_dobs+=g["dob"]
            gnd_source+=((" || " if gnd_source else "")+g["source"])
            gnd_bio+=((" || " if gnd_bio else "")+g["bio"])
    gnd_support=max(mentions("|".join(gnd_dobs),iso),mentions(gnd_source,iso),mentions(gnd_bio,iso))

    wr=refs.get((qid,iso),[])
    stated_labels=sorted({x["statedInLabel"] for x in wr if x["statedInLabel"]})
    ref_urls=sorted({x["refUrl"] for x in wr if x["refUrl"]})
    external_ref=int(bool(stated_labels or ref_urls))
    out.append({
      **r,
      "loc_ids":"|".join(locs),"gnd_ids":"|".join(gnds),
      "loc_046":loc046,"loc_670_source_notes":loc_notes,"loc_explicit_date_support":loc_support,"loc_fetch_error":loc_error,
      "gnd_date_values":"|".join(sorted(set(gnd_dobs))),"gnd_source_metadata":gnd_source,"gnd_bio_metadata":gnd_bio,
      "gnd_explicit_date_support":gnd_support,"gnd_fetch_error":gnd_error,
      "wikidata_reference_row_count":len(wr),
      "wikidata_stated_in_labels":"|".join(stated_labels),
      "wikidata_reference_urls":"|".join(ref_urls),
      "wikidata_has_external_reference":external_ref,
      "provenance_tier":"authority_explicit" if (loc_support or gnd_support) else ("wikidata_referenced" if external_ref else "wikidata_unreferenced")
    })

write_csv(OUT,out)
summary={
 "dataset":"NAS ambiguous-QID exact-DOB provenance audit v1",
 "candidate_rows":len(out),
 "qlever_calls":2,
 "rows_with_loc_explicit_support":sum(int(x["loc_explicit_date_support"]) for x in out),
 "rows_with_gnd_explicit_support":sum(int(x["gnd_explicit_date_support"]) for x in out),
 "rows_with_wikidata_external_reference":sum(int(x["wikidata_has_external_reference"]) for x in out),
 "authority_explicit_rows":sum(x["provenance_tier"]=="authority_explicit" for x in out),
 "wikidata_referenced_rows":sum(x["provenance_tier"]=="wikidata_referenced" for x in out),
 "wikidata_unreferenced_rows":sum(x["provenance_tier"]=="wikidata_unreferenced" for x in out),
 "bazi_variables_computed":0,
 "decision_note":"Diagnostic only. QLever requests are batched to reduce rate-limit risk. Authority-explicit means LOC/GND exposes the candidate exact date. Wikidata-referenced means P569 has P248/P854 evidence requiring source-quality review. No DOB writes are made."
}
SUMMARY.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(summary,ensure_ascii=False,indent=2))
