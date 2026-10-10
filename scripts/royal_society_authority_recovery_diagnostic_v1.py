#!/usr/bin/env python3
from __future__ import annotations
import csv, html, json, re, time, urllib.error, urllib.request
from pathlib import Path

OUT=Path("data/royal_society_authority_recovery_diagnostic_v1")
UA="bazi-public-figure-study/1.0 (Royal Society authority recovery diagnostic)"

TARGETS=[
 {"cohort_key":"RS_CURRENT_11560","name":"Joanna Haigh","dob":"1954-05-07","sources":[
   ("IdRef","https://www.idref.fr/094258686.xml"),
   ("IdRef RDF","https://www.idref.fr/094258686.rdf")]},
 {"cohort_key":"RS_CURRENT_11029","name":"Andrew Balmford","dob":"1963-03-08","sources":[
   ("NLI","https://www.nli.org.il/en/authorities/987007423999305171"),
   ("NLI VIAF representation","https://viaf.org/processed/J9U%7C987007423999305171")]},
 {"cohort_key":"RS_CURRENT_11816","name":"Eddy Liew","dob":"1943-05-22","sources":[
   ("NLI","https://www.nli.org.il/en/authorities/987007447200205171"),
   ("NLI VIAF representation","https://viaf.org/processed/J9U%7C987007447200205171")]},
 {"cohort_key":"RS_CURRENT_25097","name":"Anthony Finkelstein","dob":"1959-07-28","sources":[
   ("LoC MADS RDF","https://id.loc.gov/authorities/names/n90626662.madsrdf.rdf"),
   ("LoC JSON","https://id.loc.gov/authorities/names/n90626662.json"),
   ("IdRef","https://www.idref.fr/083761683.xml")]},
 {"cohort_key":"RS_CURRENT_11192","name":"John Cardy","dob":"1947-03-19","sources":[
   ("IdRef","https://www.idref.fr/086106937.xml"),
   ("NLP","https://dbn.bn.org.pl/descriptor-details/9810558022405606"),
   ("NLP VIAF representation","https://viaf.org/processed/PLWABN%7C9810558022405606")]},
 {"cohort_key":"RS_CURRENT_11351","name":"Philip Donoghue","dob":"1971-04-05","sources":[
   ("IdRef","https://www.idref.fr/079878083.xml"),
   ("NLP","https://dbn.bn.org.pl/descriptor-details/9810621097405606"),
   ("NLP VIAF representation","https://viaf.org/processed/PLWABN%7C9810621097405606")]},
]

MONTHS=["January","February","March","April","May","June","July","August","September","October","November","December"]

def fetch(url):
    last=""
    for a in range(3):
        try:
            req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"application/xml,text/xml,application/rdf+xml,application/json,text/html,text/plain,*/*;q=0.5"})
            with urllib.request.urlopen(req,timeout=30) as r:
                raw=r.read(3_000_000)
                ct=(r.headers.get("Content-Type") or "").lower()
                txt=html.unescape(raw.decode("utf-8",errors="replace"))
                return {"status":getattr(r,"status",200),"final_url":r.geturl(),"content_type":ct,"text":txt}
        except urllib.error.HTTPError as e:
            last=f"HTTP {e.code}"
            if e.code in (429,500,502,503,504) and a<2:
                time.sleep(2+3*a);continue
            return {"status":e.code,"final_url":url,"content_type":"","text":"","error":last}
        except Exception as e:
            last=f"{type(e).__name__}: {e}"
            if a<2: time.sleep(2+3*a);continue
            return {"status":"","final_url":url,"content_type":"","text":"","error":last}
    return {"status":"","final_url":url,"content_type":"","text":"","error":last}

def match(text,iso):
    if not text:return ""
    y,m,d=map(int,iso.split("-")); mn=MONTHS[m-1]
    variants=[
      ("iso",rf"(?<!\d){y:04d}[-/.]0?{m}[-/.]0?{d}(?!\d)"),
      ("dmy",rf"(?<!\w)0?{d}(?:st|nd|rd|th)?\s+{mn}\s*,?\s*{y}(?!\d)"),
      ("mdy",rf"(?<!\w){mn}\s+0?{d}(?:st|nd|rd|th)?\s*,?\s*{y}(?!\d)"),
      ("numeric_dmy",rf"(?<!\d)0?{d}[-/.]0?{m}[-/.]{y}(?!\d)"),
      ("compact",rf"(?<!\d){y:04d}0?{m:02d}0?{d:02d}(?!\d)")
    ]
    for style,p in variants:
        if re.search(p,text,re.I): return style
    return ""

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    rows=[]
    for t in TARGETS:
        found=False
        for label,url in t["sources"]:
            f=fetch(url); style=match(f.get("text",""),t["dob"])
            row={
              "cohort_key":t["cohort_key"],"display_name":t["name"],"candidate_dob":t["dob"],
              "source_label":label,"source_url":url,"http_status":f.get("status",""),
              "content_type":f.get("content_type",""),"text_len":len(f.get("text","")),
              "exact_date_match":int(bool(style)),"date_match_style":style,
              "snippet":""
            }
            if style:
                txt=re.sub(r"\s+"," ",f["text"])
                pos=txt.lower().find(str(t["dob"].split("-")[0]).lower())
                row["snippet"]=txt[max(0,pos-180):pos+300] if pos>=0 else txt[:480]
                found=True
            rows.append(row)
            print(t["name"],label,f.get("status"),style,len(f.get("text","")))
            if found: break
            time.sleep(.3)
    fields=list(rows[0].keys())
    with (OUT/"authority_recovery_diagnostic.csv").open("w",encoding="utf-8-sig",newline="") as fh:
        w=csv.DictWriter(fh,fieldnames=fields);w.writeheader();w.writerows(rows)
    matched={}
    for r in rows:
        if r["exact_date_match"] and r["cohort_key"] not in matched: matched[r["cohort_key"]]=r
    summary={
      "dataset":"Royal Society current authority recovery diagnostic v1",
      "targets":len(TARGETS),"matched_people":len(matched),
      "matches":[{"cohort_key":k,"display_name":v["display_name"],"candidate_dob":v["candidate_dob"],"source_label":v["source_label"],"source_url":v["source_url"]} for k,v in matched.items()],
      "dob_values_accepted":0,"bazi_variables_computed":0,
      "note":"Diagnostic only. Third-party VIAF representations are locator/fallback evidence, not automatically accepted as original-source validation."
    }
    (OUT/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
