#!/usr/bin/env python3
from __future__ import annotations
import csv, datetime as dt, hashlib, html, json, math, re, time
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

BASE="https://royalsociety.org"
ENDPOINT=BASE+"/api/sitecore/FellowsDirectory/PostFellowsDirectoryDisplay"
OUT=Path("data/royal_society_current_roster_v1")
UA="bazi-public-figure-study/1.0 (Royal Society official current roster acquisition; no DOB/BaZi)"

def sha256(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for c in iter(lambda:f.read(1024*1024),b""): h.update(c)
    return h.hexdigest()

def post(payload,retries=5):
    body=json.dumps(payload).encode("utf-8")
    last=None
    for a in range(retries):
        try:
            req=urllib.request.Request(ENDPOINT,data=body,method="POST",headers={
                "User-Agent":UA,"Accept":"text/html,*/*",
                "Content-Type":"application/json;charset=UTF-8",
                "Referer":BASE+"/fellows-directory/"
            })
            with urllib.request.urlopen(req,timeout=120) as r:
                return r.read()
        except Exception as e:
            last=e
            if a+1<retries: time.sleep(min(20,2**a))
    raise RuntimeError(f"POST failed after {retries}: {payload}\n{last}")

def max_page(text):
    vals=[int(x) for x in re.findall(r'data-name=["\']page["\'][^>]*data-value=["\'](\d+)["\']',text,re.I)]
    return max(vals) if vals else None

def parse_cards(text,category,page):
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
        m=re.search(r"/people/([^/?#]+)/?",url)
        slug=m.group(1) if m else ""
        idm=re.search(r"-(\d+)/?$",urlparse(url).path)
        numeric_id=idm.group(1) if idm else ""
        out.append({
            "profile_url":url.rstrip("/")+"/",
            "profile_slug":slug,
            "profile_numeric_id":numeric_id,
            "display_name":name,
            "membership_category_query":category,
            "api_page":page,
        })
    return out

def crawl(category):
    safe=re.sub(r"[^A-Za-z0-9]+","_",category).strip("_").lower()
    rawdir=OUT/"raw_api"/safe
    rawdir.mkdir(parents=True,exist_ok=True)

    raw=post({"type":category,"yearFrom":"1962","yearTo":"2025","page":1})
    text=raw.decode("utf-8",errors="replace")
    pages=max_page(text)
    if not pages: raise RuntimeError(f"{category}: could not determine page count")
    initial_pages=pages
    print(f"[{category}] initial_pages={pages}")

    rows=[]; pagehash=[]
    expected_full_page=None
    page=1
    while page<=pages:
        if page>1:
            raw=post({"type":category,"yearFrom":"1962","yearTo":"2025","page":page})
            text=raw.decode("utf-8",errors="replace")
        observed_max=max_page(text)
        if observed_max:
            if observed_max>pages:
                if observed_max>initial_pages+5:
                    raise RuntimeError(f"{category}: implausible page-count growth {initial_pages}->{observed_max}")
                print(f"  page-count extension at page {page}: {pages}->{observed_max}")
                pages=observed_max
        part=parse_cards(text,category,page)
        if not part:
            raise RuntimeError(f"{category}: no person cards on page {page}")
        if page==1: expected_full_page=len(part)
        if page<pages and len(part)>expected_full_page:
            raise RuntimeError(f"{category}: page {page} has {len(part)} cards, exceeds full-page size {expected_full_page}")
        rows.extend(part)
        p=rawdir/f"page_{page:04d}.html";p.write_bytes(raw)
        pagehash.append({"page":page,"cards":len(part),"observed_max_page":observed_max,"sha256":sha256(p),"bytes":p.stat().st_size})
        if page==1 or page==pages or page%25==0:
            print(f"  page {page}/{pages}: cards={len(part)}, cumulative={len(rows)}")
        page+=1
        time.sleep(0.05)

    urls=[r["profile_url"] for r in rows]
    if len(set(urls))!=len(rows):
        raise RuntimeError(f"{category}: duplicate profile URLs: rows={len(rows)}, unique={len(set(urls))}")
    ids=[r["profile_numeric_id"] for r in rows if r["profile_numeric_id"]]
    if len(ids)!=len(rows) or len(set(ids))!=len(rows):
        raise RuntimeError(f"{category}: numeric profile ID missing/duplicate")

    csvp=OUT/f"{safe}_current_roster.csv"
    fields=["profile_url","profile_slug","profile_numeric_id","display_name","membership_category_query","api_page"]
    with csvp.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
    return {
        "category":category,"initial_pages":initial_pages,"pages":pages,"page_size":expected_full_page,
        "rows":len(rows),"unique_profile_urls":len(set(urls)),"unique_profile_ids":len(set(ids)),
        "csv_file":csvp.name,"csv_sha256":sha256(csvp),"csv_bytes":csvp.stat().st_size,
        "raw_pages":pagehash,
    }

def main():
    if OUT.exists() and any(OUT.iterdir()):
        raise RuntimeError(f"Output directory nonempty: {OUT}")
    OUT.mkdir(parents=True,exist_ok=True)
    res=[crawl("Fellow"),crawl("Foreign Member")]
    manifest={
        "study":"Professor -> Academy -> Nobel/Fields academic-selection study",
        "dataset":"Royal Society official current Fellows Directory roster v1",
        "created_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
        "source_endpoint":ENDPOINT,
        "request_protocol":"POST JSON; fields type, yearFrom=1962, yearTo=2025, and page, matching a validated official PostDisplay request",
        "election_year_cutoff":2025,
        "categories":["Fellow","Foreign Member"],
        "primary_academy_rule":"Fellow only; Foreign Member retained separately",
        "identity_key":"Royal Society people profile numeric ID/profile URL",
        "dob_lookup_performed":0,"bazi_variables_computed":0,
        "results":res,
    }
    (OUT/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    with (OUT/"summary.csv").open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=["category","initial_pages","pages","page_size","rows","unique_profile_urls","unique_profile_ids"])
        w.writeheader();w.writerows([{k:r[k] for k in w.fieldnames} for r in res])
    print(json.dumps({r["category"]:{k:r[k] for k in ("pages","page_size","rows","unique_profile_urls")} for r in res},indent=2))

if __name__=="__main__":
    main()
