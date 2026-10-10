#!/usr/bin/env python3
from __future__ import annotations
import csv,json,os,re,time,urllib.request,urllib.parse,http.cookiejar
from pathlib import Path
from html import unescape

BASE="https://www.leopoldina.org/en/members/member-list/"
OUT=Path("data/leopoldina_physics_inventory_shard_v1")
SHARD_INDEX=int(os.environ["SHARD_INDEX"]); SHARD_COUNT=int(os.environ.get("SHARD_COUNT","4"))
UA="Mozilla/5.0 (compatible; bazi-public-figure-study/1.0; reproducibility research)"
JAR=http.cookiejar.CookieJar(); OPENER=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(JAR))
COMMON={"User-Agent":UA,"Accept":"text/html,application/xhtml+xml","Accept-Language":"en-US,en;q=0.9"}

def get(url,tries=5):
    err=""
    for i in range(tries):
        try:
            with OPENER.open(urllib.request.Request(url,headers=COMMON),timeout=60) as r:return r.read().decode("utf-8","replace")
        except Exception as e:err=f"{type(e).__name__}: {e}";time.sleep(min(16,2**i))
    raise RuntimeError(err)
def post(year,tries=5):
    fields=[("tx_solr[filter][0]","section:Physics"),("tx_solr[filter][1]",f"electionYear:{year}")]
    data=urllib.parse.urlencode(fields).encode()
    h={**COMMON,"Referer":BASE,"Content-Type":"application/x-www-form-urlencoded"}
    err=""
    for i in range(tries):
        try:
            with OPENER.open(urllib.request.Request(BASE,data=data,headers=h,method="POST"),timeout=60) as r:return r.read().decode("utf-8","replace")
        except Exception as e:err=f"{type(e).__name__}: {e}";time.sleep(min(16,2**i))
    raise RuntimeError(err)
def facet_counts(html):
    out={}
    for m in re.finditer(r'data-facet-item-value="([^"]*)"[^>]*>(.*?)</li>',html,re.I|re.S):
        v=unescape(m.group(1)); body=m.group(2)
        cm=re.search(r'<span[^>]*rounded-full[^>]*>(\d+)</span>',body,re.I|re.S)
        if cm:out[v]=int(cm.group(1))
    return out
def parse(body):
    links=sorted(set(unescape(x) for x in re.findall(r'data-document-url="([^"]*/en/members/member-list/detail/[^"]+)"',body,re.I)))
    m=re.search(r'Displaying results\s+(\d+)\s+to\s+(\d+)\s+of\s+(\d+)',body,re.I)
    if m:return int(m.group(3)),links
    if re.search(r'No results found',body,re.I):return 0,links
    raise RuntimeError("Could not parse Physics bucket result total")
def main():
    OUT.mkdir(parents=True,exist_ok=True)
    landing=get(BASE); facets=facet_counts(landing)
    if facets.get("Physics")!=383:raise RuntimeError(f"Expected current Physics facet 383, got {facets.get('Physics')}")
    years=sorted(int(v) for v in facets if re.fullmatch(r"\d{4}",v))
    assigned=years[SHARD_INDEX::SHARD_COUNT]
    buckets=[];members=[]
    for n,y in enumerate(assigned,1):
        total,links=parse(post(y))
        if total>50 or len(links)!=total:raise RuntimeError(f"Physics {y} incomplete: total={total} links={len(links)}")
        buckets.append({"year":y,"official_total":total,"returned":len(links),"primary_window":int(y<=2025)})
        for u in links:
            full=urllib.parse.urljoin(BASE,u)
            members.append({"election_year":y,"primary_window":int(y<=2025),"member_slug":full.rstrip("/").split("/")[-1],"detail_url":full})
        if n%25==0:print(f"shard={SHARD_INDEX} {n}/{len(assigned)} members={len(members)}")
        time.sleep(.08)
    for name,rows,fields in [
      (f"buckets_s{SHARD_INDEX}.csv",buckets,["year","official_total","returned","primary_window"]),
      (f"members_s{SHARD_INDEX}.csv",members,["election_year","primary_window","member_slug","detail_url"])
    ]:
        with (OUT/name).open("w",encoding="utf-8-sig",newline="") as f:
            w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
    summary={"dataset":"Leopoldina Physics section URL inventory shard v1","shard_index":SHARD_INDEX,"years":len(assigned),"member_rows":len(members),"bazi_variables_computed":0}
    (OUT/f"summary_s{SHARD_INDEX}.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print(json.dumps(summary,indent=2))
if __name__=="__main__":main()
