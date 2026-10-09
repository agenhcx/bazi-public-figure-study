#!/usr/bin/env python3
from __future__ import annotations
import argparse, csv, hashlib, html, json, re, time, urllib.request
from pathlib import Path
from urllib.parse import urlparse

BASE="https://royalsociety.org"
ENDPOINT=BASE+"/api/sitecore/FellowsDirectory/PostFellowsDirectoryDisplay"
UA="bazi-public-figure-study/1.0 (Royal Society current Fellow election-year enrichment; no DOB/BaZi)"

def post(payload,retries=6):
    body=json.dumps(payload).encode("utf-8")
    last=None
    for a in range(retries):
        try:
            req=urllib.request.Request(ENDPOINT,data=body,method="POST",headers={
                "User-Agent":UA,"Accept":"text/html,*/*",
                "Content-Type":"application/json;charset=UTF-8",
                "Referer":BASE+"/fellows-directory/"
            })
            with urllib.request.urlopen(req,timeout=120) as r:return r.read()
        except Exception as e:
            last=e
            if a+1<retries:time.sleep(min(30,2**a))
    raise RuntimeError(f"POST failed after {retries}: {payload}: {last}")

def max_page(text):
    vals=[int(x) for x in re.findall(r'data-name=["\']page["\'][^>]*data-value=["\'](\d+)["\']',text,re.I)]
    return max(vals) if vals else 1

def cards(text,year,page):
    pat=re.compile(
        r'''(?is)<article[^>]*class=["'][^"']*\bcard--person\b[^"']*["'][^>]*>.*?'''
        r'''<a[^>]*class=["'][^"']*\bcard__link\b[^"']*["'][^>]*href=["']([^"']+)["'][^>]*>.*?'''
        r'''<h4[^>]*class=["'][^"']*\bcard__title\b[^"']*["'][^>]*>(.*?)</h4>.*?</article>'''
    )
    out=[]
    for url,namehtml in pat.findall(text):
        name=re.sub(r"\s+"," ",html.unescape(re.sub(r"(?is)<[^>]+>"," ",namehtml))).strip()
        url=html.unescape(url)
        if url.startswith("/"):url=BASE+url
        idm=re.search(r"-(\d+)/?$",urlparse(url).path)
        out.append({
          "profile_numeric_id":idm.group(1) if idm else "",
          "display_name":name,"profile_url":url.rstrip("/")+"/",
          "election_year":year,"api_page":page
        })
    return out

def crawl_year(year):
    payload={"type":"Fellow","yearFrom":str(year),"yearTo":str(year),"page":1}
    raw=post(payload);text=raw.decode("utf-8",errors="replace")
    first=cards(text,year,1)
    if not first:
        return []
    pages=max_page(text)
    rows=list(first)
    for p in range(2,pages+1):
        raw=post({"type":"Fellow","yearFrom":str(year),"yearTo":str(year),"page":p})
        text=raw.decode("utf-8",errors="replace")
        part=cards(text,year,p)
        if not part:break
        rows.extend(part)
        time.sleep(0.05)
    ids=[r["profile_numeric_id"] for r in rows]
    if any(not x for x in ids) or len(ids)!=len(set(ids)):
        raise RuntimeError(f"{year}: missing/duplicate profile IDs")
    return rows

def sha256(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for c in iter(lambda:f.read(1<<20),b""):h.update(c)
    return h.hexdigest()

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--start-year",type=int,required=True);ap.add_argument("--end-year",type=int,required=True)
    a=ap.parse_args()
    out=Path(f"data/royal_society_current_election_year_v1/{a.start_year}_{a.end_year}")
    out.mkdir(parents=True,exist_ok=True)
    rows=[];counts=[]
    for y in range(a.start_year,a.end_year+1):
        rr=crawl_year(y);rows.extend(rr);counts.append({"year":y,"rows":len(rr)})
        print(f"{y}: {len(rr)}")
        time.sleep(0.08)
    p=out/"current_fellows_by_election_year.csv"
    with p.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=["profile_numeric_id","display_name","profile_url","election_year","api_page"]);w.writeheader();w.writerows(rows)
    q=out/"year_counts.csv"
    with q.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=["year","rows"]);w.writeheader();w.writerows(counts)
    m={"range":[a.start_year,a.end_year],"rows":len(rows),"unique_profile_ids":len({r["profile_numeric_id"] for r in rows}),
       "csv_sha256":sha256(p),"dob_lookup_performed":0,"bazi_variables_computed":0}
    (out/"manifest.json").write_text(json.dumps(m,indent=2),encoding="utf-8")
    print(json.dumps(m,indent=2))
if __name__=="__main__":main()
