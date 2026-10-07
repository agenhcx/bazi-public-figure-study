#!/usr/bin/env python3
from __future__ import annotations
import json, re, urllib.parse, urllib.request, datetime as dt
from pathlib import Path

OUT=Path("data/royal_society_current_api_probe_v1")
BASE="https://royalsociety.org"
URL=BASE+"/api/sitecore/FellowsDirectory/PostFellowsDirectoryDisplay"
UA="bazi-public-figure-study/1.0 (Royal Society current-directory API protocol probe; no DOB/BaZi)"

def post_json(payload):
    body=json.dumps(payload).encode("utf-8")
    req=urllib.request.Request(URL,data=body,method="POST",headers={
        "User-Agent":UA,"Accept":"text/html,*/*","Content-Type":"application/json;charset=UTF-8",
        "Referer":BASE+"/fellows-directory/"
    })
    with urllib.request.urlopen(req,timeout=120) as r:
        return r.read(),r.status,dict(r.headers),r.geturl()

def post_form(payload):
    body=urllib.parse.urlencode(payload).encode("utf-8")
    req=urllib.request.Request(URL,data=body,method="POST",headers={
        "User-Agent":UA,"Accept":"text/html,*/*","Content-Type":"application/x-www-form-urlencoded",
        "Referer":BASE+"/fellows-directory/"
    })
    with urllib.request.urlopen(req,timeout=120) as r:
        return r.read(),r.status,dict(r.headers),r.geturl()

def inspect(raw):
    text=raw.decode("utf-8",errors="replace")
    profile_links=sorted(set(re.findall(r'href=["\'](/people/[^"\']+/?)["\']',text,re.I)))
    pages=[int(x) for x in re.findall(r'data-name=["\']page["\'][^>]*data-value=["\'](\d+)["\']',text,re.I)]
    return {
        "bytes":len(raw),
        "profile_link_count":len(profile_links),
        "profile_link_sample":profile_links[:20],
        "page_values":sorted(set(pages)),
        "max_page_value":max(pages) if pages else None,
        "has_postdisplay_content":int("js-postDisplayContent" in text),
        "has_error_word":int(bool(re.search(r"\berror\b",text,re.I))),
        "text_prefix":re.sub(r"\s+"," ",re.sub(r"<[^>]+>"," ",text))[:500],
    }

def main():
    if OUT.exists() and any(OUT.iterdir()):
        raise RuntimeError(f"Output dir nonempty: {OUT}")
    OUT.mkdir(parents=True,exist_ok=True)
    payloads=[
        ("json_fellow_page1",post_json,{"type":"Fellow","page":1}),
        ("form_fellow_page1",post_form,{"type":"Fellow","page":1}),
        ("json_all_page1",post_json,{"page":1}),
    ]
    results=[]
    for name,fn,payload in payloads:
        try:
            raw,status,headers,url=fn(payload)
            p=OUT/f"{name}.html";p.write_bytes(raw)
            rec={"name":name,"payload":payload,"status":status,"content_type":headers.get("Content-Type",""),"final_url":url}
            rec.update(inspect(raw));results.append(rec)
        except Exception as e:
            results.append({"name":name,"payload":payload,"error":repr(e)})
    summary={
        "dataset":"Royal Society current-directory API encoding probe v1",
        "created_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
        "endpoint":URL,
        "results":results,
        "dob_lookup_performed":0,
        "bazi_variables_computed":0,
        "note":"Protocol diagnostic only; no roster freeze."
    }
    (OUT/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=="__main__":main()
