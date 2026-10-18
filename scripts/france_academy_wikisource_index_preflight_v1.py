#!/usr/bin/env python3
"""Public historical Académie des sciences election-register transcription probe.

The source is Wikisource's transcription of the Academy's published original
Comptes rendus index. Keep it distinct from original-page verification.
No BaZi variables, no cohort admissions, no DOB changes.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

UA="bazi-public-figure-study/1.0 (academic archival election-source pilot; github.com/agenhcx/bazi-public-figure-study)"
BASE="Comptes rendus de l’Académie des sciences/Tome {volume}, {year}/Table des matières"
TRIAL=[(168,1919),(179,1924),(182,1926),(192,1931),(198,1934)]
ROOT="local_runs/france_wikisource_election_index_source_pilot_v1"
def build_urls(volume,year):
    title=BASE.format(volume=volume,year=year)
    return {
       "wiki": "https://fr.wikisource.org/wiki/"+urllib.parse.quote(title.replace(" ","_"),safe="/"),
       "api": "https://fr.wikisource.org/w/api.php?"+urllib.parse.urlencode({
          "action":"query","format":"json","formatversion":"2",
          "prop":"revisions","rvprop":"content","rvslots":"main","titles":title}),
       "raw": "https://fr.wikisource.org/w/index.php?"+urllib.parse.urlencode({
          "title":title,"action":"raw"})
    }
def read_one(url,limit=2500000):
    req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"application/json,text/plain,text/html;q=0.9"})
    with urllib.request.urlopen(req,timeout=22) as r:
        data=r.read(limit+1)
        if len(data)>limit: raise ValueError("Oversize Wikisource response")
        return r.status,r.headers.get("Content-Type",""),data
def content_from_api(raw):
    o=json.loads(raw.decode("utf8"))
    pages=((o.get("query") or {}).get("pages") or [])
    if len(pages)!=1:return ""
    revisions=pages[0].get("revisions") or []
    if not revisions:return ""
    slot=(revisions[0].get("slots") or {}).get("main") or {}
    return slot.get("content") or slot.get("*") or ""
def content_probe(text):
    # Raw transcription has section header and names; these snippets are not parsed
    # as full member-event records until structural reliability has been assessed.
    words=" ".join(str(text).split())
    m=re.search(r"Élections? de membres et de correspondants|Élections? de membres|Élections?\.|Élection de membres", words,re.I)
    return {"election_heading_found":bool(m),
            "first_heading_context":words[m.start():m.start()+1250] if m else "",
            "char_count":len(text),"raw_beginning":words[:400]}
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--fixture-check",action="store_true")
    ap.add_argument("--out",default=ROOT)
    ap.add_argument("--limit",type=int,default=5)
    args=ap.parse_args()
    if args.fixture_check:
        title=BASE.format(volume=182,year=1926)
        u=build_urls(182,1926)
        assert "wikisource.org" in u["wiki"]
        data=json.dumps({"query":{"pages":[{"revisions":[{"slots":{"main":{"content":"Élections de membres et de correspondants. — M. Camille Matignon est élu membre."}}}]}]}}).encode()
        assert "Matignon" in content_from_api(data)
        assert content_probe(content_from_api(data))["election_heading_found"]
        print("PASS: title, API envelope, election-heading classification, no source acceptance")
        return
    args.limit=max(1,min(5,args.limit))
    out=Path(args.out)
    out.mkdir(parents=True,exist_ok=True)
    checks=[]
    for volume,year in TRIAL[:args.limit]:
        urls=build_urls(volume,year)
        statuses=[]
        for method in ("api","raw","wiki"):
            try:
                code,ctype,data=read_one(urls[method])
                text=content_from_api(data) if method=="api" else data.decode("utf8",errors="replace")
                info=content_probe(text)
                statuses.append({"method":method,"status":code,"mime":ctype,"bytes":len(data),
                                 "sha256":hashlib.sha256(data).hexdigest(),**info,
                                 "url":urls[method]})
                if method=="api" and info["election_heading_found"]:
                    break
                if method=="raw" and info["election_heading_found"]:
                    break
            except (ValueError,urllib.error.HTTPError,urllib.error.URLError,TimeoutError) as e:
                statuses.append({"method":method,"status":getattr(e,"code","NETWORK_ERROR"),
                                 "error":type(e).__name__+":"+str(getattr(e,"reason",str(e)))[:160]})
        checks.append({"volume":volume,"year":year,"checks":statuses,
                       "original_printed_book_page_opened":0,"study_full_membership_accepted":0,
                       "study_exact_dob_accepted":0,"bazi_variables_computed":0})
        # 1.5 seconds between volumes; no access-control bypass
        if year!=TRIAL[min(args.limit-1,len(checks)-1)][1]: time.sleep(1.5)
    (out/"summary.json").write_text(json.dumps({"version":"france-wikisource-index-preflight-v1",
          "tested_volumes":len(checks),"source_results":checks,
          "complete_historical_roster":False,"accepted_full_members":0,"accepted_exact_dobs":0,
          "bazi_variables_computed":0},ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    for x in checks:
        print("SOURCE",x["volume"],x["year"],json.dumps([
           {k:s.get(k) for k in ("method","status","mime","bytes","sha256","election_heading_found","first_heading_context","error")}
           for s in x["checks"]],ensure_ascii=False))
    print("All sources provisional Wikisource transcriptions, NOT verified original volume scans.")

if __name__=="__main__":main()
