#!/usr/bin/env python3
from __future__ import annotations
import datetime as dt, hashlib, json, re, urllib.request
from pathlib import Path

OUT=Path("data/royal_society_postdisplay_probe_v1")
BASE="https://royalsociety.org"
DIRECTORY=BASE+"/fellows-directory/"
MAINJS=BASE+"/assets/js/main.js"
UA="bazi-public-figure-study/1.0 (Royal Society official roster protocol probe; no DOB/BaZi)"

def fetch(url, accept="*/*"):
    req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":accept})
    with urllib.request.urlopen(req,timeout=180) as r:
        return r.read(),dict(r.headers),r.geturl(),r.status

def sha256(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for c in iter(lambda:f.read(1024*1024),b""):h.update(c)
    return h.hexdigest()

def contexts(text, patterns, radius=1200, max_per=8):
    out=[]
    for pat in patterns:
        hits=list(re.finditer(pat,text,re.I))
        for m in hits[:max_per]:
            out.append({
                "pattern":pat,
                "start":m.start(),
                "context":text[max(0,m.start()-radius):min(len(text),m.end()+radius)]
            })
    return out

def main():
    if OUT.exists() and any(OUT.iterdir()):
        raise RuntimeError(f"Output dir nonempty: {OUT}")
    OUT.mkdir(parents=True,exist_ok=True)

    d,h,u,s=fetch(DIRECTORY,"text/html,application/xhtml+xml")
    dp=OUT/"fellows_directory.html"; dp.write_bytes(d)
    j,jh,ju,js=fetch(MAINJS,"application/javascript,text/javascript,*/*")
    jp=OUT/"main.js"; jp.write_bytes(j)
    text=j.decode("utf-8",errors="replace")

    patterns=[
        r"PostDisplay",
        r"postDisplay",
        r"data-url",
        r"FormData",
        r"URLSearchParams",
        r"fetch\s*\(",
        r"XMLHttpRequest",
        r"application/json",
        r"application/x-www-form-urlencoded",
        r"page",
    ]
    ctx=contexts(text,patterns)

    endpoint="/api/sitecore/FellowsDirectory/PostFellowsDirectoryDisplay"
    endpoint_hits=[m.start() for m in re.finditer(re.escape(endpoint),text,re.I)]

    summary={
        "dataset":"Royal Society PostDisplay frontend protocol diagnostic v1",
        "created_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
        "directory":{"url":u,"status":s,"bytes":len(d),"sha256":sha256(dp)},
        "main_js":{"url":ju,"status":js,"bytes":len(j),"content_type":jh.get("Content-Type",""),"sha256":sha256(jp)},
        "endpoint_literal_hits_in_js":endpoint_hits,
        "context_count":len(ctx),
        "contexts":ctx,
        "dob_lookup_performed":0,
        "bazi_variables_computed":0,
        "note":"Diagnostic only. No roster is frozen. This captures the official frontend request-construction code before implementing the directory crawler."
    }
    (OUT/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({
        "main_js_status":js,
        "main_js_bytes":len(j),
        "endpoint_literal_hits_in_js":len(endpoint_hits),
        "context_count":len(ctx),
        "output":str(OUT)
    },indent=2))

if __name__=="__main__":
    main()
