#!/usr/bin/env python3
from __future__ import annotations
import csv,json,os,re,time,urllib.request,urllib.parse,http.cookiejar
from pathlib import Path
from html import unescape

BASE="https://www.leopoldina.org/en/members/member-list/"
OUT=Path("data/leopoldina_class_year_inventory_shard_v1")
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/155.0 Safari/537.36"
CLASSES=[
 "Class I: Mathematics, Natural Sciences and Engineering",
 "Class II: Life Sciences",
 "Class III: Medicine",
]
CLASS_INDEX=int(os.environ["CLASS_INDEX"])
SHARD_INDEX=int(os.environ["SHARD_INDEX"])
SHARD_COUNT=int(os.environ.get("SHARD_COUNT","4"))
CLS=CLASSES[CLASS_INDEX]
JAR=http.cookiejar.CookieJar()
OPENER=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(JAR))
COMMON={"User-Agent":UA,"Accept":"text/html,application/xhtml+xml","Accept-Language":"en-US,en;q=0.9"}

def get(url,tries=5):
    err=""
    for i in range(tries):
        try:
            with OPENER.open(urllib.request.Request(url,headers=COMMON),timeout=60) as r:
                return r.read().decode("utf-8","replace")
        except Exception as e:
            err=f"{type(e).__name__}: {e}"; time.sleep(min(16,2**i))
    raise RuntimeError(err)

def post(filters,tries=5):
    fields=[(f"tx_solr[filter][{i}]",v) for i,v in enumerate(filters)]
    data=urllib.parse.urlencode(fields).encode()
    h={**COMMON,"Referer":BASE,"Content-Type":"application/x-www-form-urlencoded"}
    err=""
    for i in range(tries):
        try:
            with OPENER.open(urllib.request.Request(BASE,data=data,headers=h,method="POST"),timeout=60) as r:
                return r.read().decode("utf-8","replace")
        except Exception as e:
            err=f"{type(e).__name__}: {e}"; time.sleep(min(16,2**i))
    raise RuntimeError(err)

def facet_counts(html):
    out={}
    for m in re.finditer(r'data-facet-item-value="([^"]*)"[^>]*>(.*?)</li>',html,re.I|re.S):
        v=unescape(m.group(1)); body=m.group(2)
        cm=re.search(r'<span[^>]*rounded-full[^>]*>(\d+)</span>',body,re.I|re.S)
        if cm: out[v]=int(cm.group(1))
    return out

def parse_bucket(body):
    links=sorted(set(unescape(x) for x in re.findall(r'data-document-url="([^"]*/en/members/member-list/detail/[^"]+)"',body,re.I)))
    m=re.search(r'Displaying results\s+(\d+)\s+to\s+(\d+)\s+of\s+(\d+)',body,re.I)
    if m:
        return int(m.group(3)),links
    if re.search(r'No results found',body,re.I):
        return 0,links
    raise RuntimeError("Could not parse result total or no-results state")

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    landing=get(BASE)
    facets=facet_counts(landing)
    years=sorted(int(v) for v in facets if re.fullmatch(r"\d{4}",v))
    if not years or min(years)>1700 or 2025 not in years:
        raise RuntimeError(f"Implausible election-year facets: {years[:5]} ... {years[-5:]}")
    class_total=facets.get(CLS)
    if not class_total:
        raise RuntimeError(f"Missing class facet for {CLS}")
    assigned=years[SHARD_INDEX::SHARD_COUNT]
    buckets=[]; members=[]
    for n,year in enumerate(assigned,1):
        body=post([f"class:{CLS}",f"electionYear:{year}"])
        total,links=parse_bucket(body)
        if total>50:
            raise RuntimeError(f"Overflow bucket {CLS} {year}: total={total}")
        if len(links)!=total:
            raise RuntimeError(f"Incomplete bucket {CLS} {year}: total={total} links={len(links)}")
        buckets.append({"class_index":CLASS_INDEX,"class":CLS,"year":year,"official_total":total,"returned":len(links),"primary_window":int(year<=2025)})
        for u in links:
            full=urllib.parse.urljoin(BASE,u)
            members.append({"class_index":CLASS_INDEX,"class":CLS,"election_year":year,"primary_window":int(year<=2025),"member_slug":full.rstrip("/").split("/")[-1],"detail_url":full})
        if n%20==0: print(f"class={CLASS_INDEX} shard={SHARD_INDEX} buckets={n}/{len(assigned)} members={len(members)}")
        time.sleep(.08)
    bp=OUT/f"buckets_c{CLASS_INDEX}_s{SHARD_INDEX}.csv"
    mp=OUT/f"members_c{CLASS_INDEX}_s{SHARD_INDEX}.csv"
    with bp.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=["class_index","class","year","official_total","returned","primary_window"]);w.writeheader();w.writerows(buckets)
    with mp.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=["class_index","class","election_year","primary_window","member_slug","detail_url"]);w.writeheader();w.writerows(members)
    summary={"dataset":"Leopoldina class-year URL inventory shard v1","class_index":CLASS_INDEX,"class":CLS,"class_facet_total":class_total,"shard_index":SHARD_INDEX,"shard_count":SHARD_COUNT,"election_years_total":len(years),"assigned_years":len(assigned),"bucket_member_total":sum(int(x["official_total"]) for x in buckets),"member_rows":len(members),"overflow_buckets":0,"bazi_variables_computed":0}
    (OUT/f"summary_c{CLASS_INDEX}_s{SHARD_INDEX}.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=="__main__":main()
