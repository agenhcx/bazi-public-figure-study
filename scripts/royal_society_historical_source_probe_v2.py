#!/usr/bin/env python3
from __future__ import annotations
import datetime as dt, hashlib, json, re, urllib.parse, urllib.request
from pathlib import Path

OUT=Path("data/royal_society_historical_source_probe_v2")
WHAT="https://catalogues.royalsociety.org/calmview/what.aspx"
UA="bazi-public-figure-study/1.0 (Royal Society historical source probe; no DOB/BaZi)"

CANDIDATES=[
 "https://royalsociety.org/-/media/Royal_Society_Content/about-us/fellowship/Fellows1660-2019.pdf",
 "https://royalsociety.org/uploadedFiles/Royal_Society_Content/about-us/fellowship/Fellows1660-2019.pdf",
 "http://royalsociety.org/uploadedFiles/Royal_Society_Content/about-us/fellowship/Fellows1660-2019.pdf",
]

def fetch(url,accept="*/*"):
    req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":accept})
    with urllib.request.urlopen(req,timeout=120) as r:
        return r.read(),dict(r.headers),r.geturl(),r.status

def sha256_bytes(b):
    h=hashlib.sha256();h.update(b);return h.hexdigest()

def main():
    if OUT.exists() and any(OUT.iterdir()):
        raise RuntimeError(f"Output dir nonempty: {OUT}")
    OUT.mkdir(parents=True,exist_ok=True)
    summary={
      "dataset":"Royal Society historical official-source probe v2",
      "created_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
      "what_url":WHAT,
      "candidate_results":[],
      "dob_lookup_performed":0,
      "bazi_variables_computed":0,
    }
    discovered=[]
    try:
        raw,h,u,s=fetch(WHAT,"text/html,application/xhtml+xml")
        text=raw.decode("utf-8",errors="replace")
        (OUT/"what.html").write_bytes(raw)
        for href in re.findall(r'''href=["']([^"']+)["']''',text,re.I):
            full=urllib.parse.urljoin(u,href)
            if "2019" in full or "fellows1660" in full.lower() or (".pdf" in full.lower() and "fellow" in full.lower()):
                discovered.append(full)
        summary["what_status"]=s
        summary["what_final_url"]=u
        summary["what_bytes"]=len(raw)
        summary["discovered_links"]=sorted(set(discovered))
    except Exception as e:
        summary["what_error"]=repr(e)

    urls=[]
    seen=set()
    for x in discovered+CANDIDATES:
        if x not in seen:
            seen.add(x);urls.append(x)

    for i,url in enumerate(urls,1):
        rec={"url":url}
        try:
            raw,h,u,s=fetch(url,"application/pdf,*/*;q=0.8")
            rec.update({
              "status":s,"final_url":u,"bytes":len(raw),
              "content_type":h.get("Content-Type",""),
              "starts_pdf":int(raw.startswith(b"%PDF")),
              "sha256":sha256_bytes(raw),
            })
            if raw.startswith(b"%PDF"):
                p=OUT/f"historical_listing_{i:02d}.pdf"
                p.write_bytes(raw)
                rec["saved_file"]=p.name
        except Exception as e:
            rec["error"]=repr(e)
        summary["candidate_results"].append(rec)

    (OUT/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
