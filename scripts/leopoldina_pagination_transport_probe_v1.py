#!/usr/bin/env python3
from __future__ import annotations
import json,urllib.request,urllib.parse,http.cookiejar
from pathlib import Path

OUT=Path("data/leopoldina_pagination_transport_probe_v1")
BASE="https://www.leopoldina.org/en/members/member-list"
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/155.0 Safari/537.36"

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    jar=http.cookiejar.CookieJar()
    opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    common={"User-Agent":UA,"Accept":"text/html,application/xhtml+xml","Accept-Language":"en-US,en;q=0.9"}
    tests=[]
    # Establish browser-like session on landing page.
    landing=urllib.request.Request(BASE+"/",headers=common)
    try:
        with opener.open(landing,timeout=30) as r:
            body=r.read()
            tests.append({"name":"landing_session","status":r.status,"final_url":r.geturl(),"bytes":len(body),"error":""})
    except Exception as e:
        tests.append({"name":"landing_session","status":None,"final_url":"","bytes":0,"error":f"{type(e).__name__}: {e}"})

    candidates=[
      ("encoded_no_slash", BASE+"?tx_solr%5Bpage%5D=2", None),
      ("encoded_with_slash", BASE+"/?tx_solr%5Bpage%5D=2", None),
      ("literal_brackets", BASE+"?tx_solr[page]=2", None),
      ("encoded_referer", BASE+"?tx_solr%5Bpage%5D=2", BASE+"/"),
    ]
    for name,url,ref in candidates:
        h=dict(common)
        if ref: h["Referer"]=ref
        try:
            with opener.open(urllib.request.Request(url,headers=h),timeout=30) as r:
                body=r.read()
                tests.append({"name":name,"status":r.status,"final_url":r.geturl(),"bytes":len(body),"error":""})
        except Exception as e:
            tests.append({"name":name,"status":getattr(e,"code",None),"final_url":url,"bytes":0,"error":f"{type(e).__name__}: {e}"})

    post_data=urllib.parse.urlencode({"tx_solr[page]":"2","tx_solr[resultsPerPage]":"50"}).encode()
    for target in (BASE,BASE+"/"):
        h={**common,"Referer":BASE+"/","Content-Type":"application/x-www-form-urlencoded"}
        try:
            with opener.open(urllib.request.Request(target,data=post_data,headers=h,method="POST"),timeout=30) as r:
                body=r.read()
                tests.append({"name":"post_"+("slash" if target.endswith("/") else "noslash"),"status":r.status,"final_url":r.geturl(),"bytes":len(body),"error":""})
        except Exception as e:
            tests.append({"name":"post_"+("slash" if target.endswith("/") else "noslash"),"status":getattr(e,"code",None),"final_url":target,"bytes":0,"error":f"{type(e).__name__}: {e}"})
    report={"dataset":"Leopoldina pagination transport probe v1","tests":tests,"bazi_variables_computed":0}
    (OUT/"probe.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=="__main__": main()
