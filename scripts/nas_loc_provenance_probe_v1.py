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

IN = Path("data/nas_authority_dob_candidates_v1.csv")
OUT = Path("data/nas_loc_provenance_probe_v1.csv")
SUMMARY = Path("data/nas_loc_provenance_probe_summary_v1.json")
UA = "bazi-public-figure-study/1.0 (LOC provenance audit; no BaZi computation)"
NS = {"m":"http://www.loc.gov/MARC21/slim"}

MONTHS = {
    1:["january","jan"],2:["february","feb"],3:["march","mar"],4:["april","apr"],
    5:["may"],6:["june","jun"],7:["july","jul"],8:["august","aug"],
    9:["september","sep","sept"],10:["october","oct"],11:["november","nov"],12:["december","dec"]
}

def read_csv(p):
    with p.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

def write_csv(p, rows):
    fields = list(rows[0].keys()) if rows else []
    with p.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader(); w.writerows(rows)

def get(url, retries=5):
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent":UA,"Accept":"application/xml,text/xml;q=0.9,*/*;q=0.1"})
            with urllib.request.urlopen(req, timeout=90) as r:
                data = r.read()
                return getattr(r,"status",200), data, ""
        except urllib.error.HTTPError as e:
            last = e
            if e.code == 404:
                return 404, b"", "HTTP 404"
            if i+1 >= retries or e.code not in {429,500,502,503,504}:
                break
            try: delay=float(e.headers.get("Retry-After",""))
            except Exception: delay=min(20.0,2.0**i)
            time.sleep(max(1.0,delay))
        except Exception as e:
            last = e
            if i+1 >= retries: break
            time.sleep(min(20.0,2.0**i))
    return getattr(last,"code",""), b"", repr(last)

def subfields(field):
    return [(s.attrib.get("code",""), (s.text or "").strip()) for s in field.findall("m:subfield",NS)]

def joined(field):
    return " ".join(v for _,v in subfields(field) if v).strip()

def parse_marc(data):
    root = ET.fromstring(data)
    rec = root if root.tag.endswith("record") else root.find(".//m:record",NS)
    if rec is None:
        raise RuntimeError("No MARC record element")
    result = {
        "heading":"",
        "heading_dates":"",
        "field_046":"",
        "field_670":[],
        "field_678":[],
        "field_667":[],
    }
    for f in rec.findall("m:datafield",NS):
        tag=f.attrib.get("tag","")
        sf=subfields(f)
        if tag=="100":
            result["heading"]=joined(f)
            result["heading_dates"]="|".join(v for c,v in sf if c=="d")
        elif tag=="046":
            result["field_046"] += (" || " if result["field_046"] else "") + joined(f)
        elif tag=="670":
            result["field_670"].append(joined(f))
        elif tag=="678":
            result["field_678"].append(joined(f))
        elif tag=="667":
            result["field_667"].append(joined(f))
    return result

def candidate_variants(iso):
    d=dt.date.fromisoformat(iso)
    vars={iso, iso.replace("-","/"), iso.replace("-",".")}
    y,m,day=d.year,d.month,d.day
    vars |= {f"{m}/{day}/{y}",f"{m:02d}/{day:02d}/{y}",f"{day}/{m}/{y}",f"{day:02d}/{m:02d}/{y}"}
    for mon in MONTHS[m]:
        vars |= {
            f"{mon} {day} {y}", f"{mon} {day}, {y}", f"{mon}. {day}, {y}",
            f"{day} {mon} {y}", f"{day} {mon}. {y}"
        }
    return {re.sub(r"[^a-z0-9]+"," ",x.lower()).strip() for x in vars}

def text_mentions_date(text, iso):
    norm=re.sub(r"[^a-z0-9]+"," ",(text or "").lower()).strip()
    return any(v and v in norm for v in candidate_variants(iso))

def main():
    rows=read_csv(IN)
    out=[]
    for r in rows:
        loc=(r.get("loc_ids") or "").strip()
        iso=r["authority_candidate_dob"].strip()
        url=f"https://id.loc.gov/authorities/names/{urllib.parse.quote(loc)}.marcxml.xml"
        status,data,error=get(url)
        parsed={"heading":"","heading_dates":"","field_046":"","field_670":[],"field_678":[],"field_667":[]}
        if data:
            try: parsed=parse_marc(data)
            except Exception as e: error=(error+"; " if error else "")+repr(e)
        notes670=" || ".join(parsed["field_670"])
        notes678=" || ".join(parsed["field_678"])
        notes667=" || ".join(parsed["field_667"])
        candidate_in_670=int(text_mentions_date(notes670,iso))
        candidate_in_678=int(text_mentions_date(notes678,iso))
        candidate_in_046=int(text_mentions_date(parsed["field_046"],iso))
        candidate_in_heading=int(text_mentions_date(parsed["heading_dates"],iso))
        # Source-note clues useful for manual provenance assessment.
        lower=notes670.lower()
        source_clues=[]
        for clue in ["curriculum vitae","c.v.","cv ","email","personal communication","author","website",
                     "publisher","biography","faculty","university","born","birth"]:
            if clue in lower: source_clues.append(clue)
        out.append({
            **r,
            "loc_marc_url":url,
            "fetch_status":status,
            "fetch_error":error,
            "loc_heading":parsed["heading"],
            "loc_heading_dates":parsed["heading_dates"],
            "loc_046":parsed["field_046"],
            "candidate_date_mentioned_in_046":candidate_in_046,
            "candidate_date_mentioned_in_heading_dates":candidate_in_heading,
            "candidate_date_mentioned_in_670":candidate_in_670,
            "candidate_date_mentioned_in_678":candidate_in_678,
            "loc_670_source_notes":notes670,
            "loc_678_biographical_notes":notes678,
            "loc_667_notes":notes667,
            "provenance_source_clues":"|".join(source_clues),
        })
    write_csv(OUT,out)
    summary={
      "dataset":"NAS LOC candidate provenance probe v1",
      "candidate_rows":len(out),
      "fetch_successes":sum(str(x["fetch_status"])=="200" for x in out),
      "candidate_date_mentioned_in_046":sum(x["candidate_date_mentioned_in_046"] for x in out),
      "candidate_date_mentioned_in_heading_dates":sum(x["candidate_date_mentioned_in_heading_dates"] for x in out),
      "candidate_date_mentioned_in_670":sum(x["candidate_date_mentioned_in_670"] for x in out),
      "candidate_date_mentioned_in_678":sum(x["candidate_date_mentioned_in_678"] for x in out),
      "rows_with_670_source_notes":sum(bool(x["loc_670_source_notes"]) for x in out),
      "bazi_variables_computed":0,
      "decision_note":"Provenance diagnostic only. LOC MARC 670 source notes are exposed for manual review; no DOB is automatically accepted."
    }
    SUMMARY.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
