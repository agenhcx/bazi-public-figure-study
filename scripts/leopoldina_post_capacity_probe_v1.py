#!/usr/bin/env python3
from __future__ import annotations
import json,re,urllib.request,urllib.parse,http.cookiejar
from pathlib import Path
from html import unescape

BASE="https://www.leopoldina.org/en/members/member-list/"
OUT=Path("data/leopoldina_post_capacity_probe_v1")
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/155.0 Safari/537.36"
JAR=http.cookiejar.CookieJar()
OPENER=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(JAR))
COMMON={"User-Agent":UA,"Accept":"text/html,application/xhtml+xml","Accept-Language":"en-US,en;q=0.9"}

def fetch_post(fields):
    data=urllib.parse.urlencode(fields,doseq=True).encode()
    h={**COMMON,"Referer":BASE,"Content-Type":"application/x-www-form-urlencoded"}
    try:
        with OPENER.open(urllib.request.Request(BASE,data=data,headers=h,method="POST"),timeout=60) as r:
            body=r.read().decode("utf-8","replace")
            return r.status,r.geturl(),body,""
    except Exception as e:
        return getattr(e,"code",None),BASE,"",f"{type(e).__name__}: {e}"

def inspect(name,fields):
    status,url,body,error=fetch_post(fields)
    links=sorted(set(unescape(x) for x in re.findall(r'data-document-url="([^"]*/en/members/member-list/detail/[^"]+)"',body,re.I)))
    m=re.search(r'Displaying results\s+(\d+)\s+to\s+(\d+)\s+of\s+(\d+)',body,re.I)
    classes={}
    for cm in re.finditer(r'data-facet-item-value="(Class [^"]+)"[^>]*>.*?<span[^>]*rounded-full[^>]*>(\d+)</span>',body,re.I|re.S):
        classes[unescape(cm.group(1))]=int(cm.group(2))
    return {"name":name,"fields":fields,"status":status,"final_url":url,"bytes":len(body.encode()),"detail_links":len(links),"display_range":list(m.groups()) if m else None,"class_facets":classes,"first_links":links[:3],"last_links":links[-3:],"error":error}

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    # establish cookies/session
    with OPENER.open(urllib.request.Request(BASE,headers=COMMON),timeout=60) as r:
        r.read()
    tests=[
      ("rpp_100",{"tx_solr[resultsPerPage]":"100"}),
      ("rpp_500",{"tx_solr[resultsPerPage]":"500"}),
      ("rpp_5000",{"tx_solr[resultsPerPage]":"5000"}),
      ("class1_rpp_2000",{"tx_solr[filter][0]":"class:Class I: Mathematics, Natural Sciences and Engineering","tx_solr[resultsPerPage]":"2000"}),
      ("class2_rpp_2000",{"tx_solr[filter][0]":"class:Class II: Life Sciences","tx_solr[resultsPerPage]":"2000"}),
      ("class3_rpp_2000",{"tx_solr[filter][0]":"class:Class III: Medicine","tx_solr[resultsPerPage]":"2000"}),
    ]
    report={"dataset":"Leopoldina POST capacity/filter probe v1","tests":[inspect(n,f) for n,f in tests],"bazi_variables_computed":0}
    (OUT/"probe.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=="__main__": main()
