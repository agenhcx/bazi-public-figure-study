#!/usr/bin/env python3
from __future__ import annotations
import json,re,urllib.request,urllib.parse,http.cookiejar,time
from pathlib import Path
from html import unescape

BASE="https://www.leopoldina.org/en/members/member-list/"
OUT=Path("data/leopoldina_class_year_probe_v1")
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/155.0 Safari/537.36"
CLASSES=[
 "Class I: Mathematics, Natural Sciences and Engineering",
 "Class II: Life Sciences",
 "Class III: Medicine",
]
YEARS=[1932,2009,2025]
JAR=http.cookiejar.CookieJar()
OPENER=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(JAR))
COMMON={"User-Agent":UA,"Accept":"text/html,application/xhtml+xml","Accept-Language":"en-US,en;q=0.9"}

def post(filters):
    fields=[]
    for i,v in enumerate(filters): fields.append((f"tx_solr[filter][{i}]",v))
    data=urllib.parse.urlencode(fields).encode()
    h={**COMMON,"Referer":BASE,"Content-Type":"application/x-www-form-urlencoded"}
    with OPENER.open(urllib.request.Request(BASE,data=data,headers=h,method="POST"),timeout=60) as r:
        return r.read().decode("utf-8","replace")

def inspect(cls,year):
    body=post([f"class:{cls}",f"electionYear:{year}"])
    links=sorted(set(unescape(x) for x in re.findall(r'data-document-url="([^"]*/en/members/member-list/detail/[^"]+)"',body,re.I)))
    m=re.search(r'Displaying results\s+(\d+)\s+to\s+(\d+)\s+of\s+(\d+)',body,re.I)
    total=int(m.group(3)) if m else 0
    return {"class":cls,"year":year,"total":total,"returned":len(links),"overflow":int(total>50),"first_links":links[:3],"last_links":links[-3:]}

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    with OPENER.open(urllib.request.Request(BASE,headers=COMMON),timeout=60) as r:r.read()
    rows=[]
    for year in YEARS:
        for cls in CLASSES:
            x=inspect(cls,year); rows.append(x); print(json.dumps(x,ensure_ascii=False)); time.sleep(.2)
    report={"dataset":"Leopoldina class-year bucket probe v1","rows":rows,"max_total":max(x["total"] for x in rows),"overflow_buckets":sum(x["overflow"] for x in rows),"bazi_variables_computed":0}
    (OUT/"probe.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=="__main__": main()
