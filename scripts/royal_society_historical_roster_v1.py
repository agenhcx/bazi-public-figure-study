#!/usr/bin/env python3
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import html
import http.cookiejar
import json
import math
import re
import time
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse, parse_qs

BASE="https://catalogues.royalsociety.org"
SEARCH=BASE+"/calmview/personsearch.aspx?src=CalmView.Persons"
OUT=Path("data/royal_society_historical_roster_v1")
UA="bazi-public-figure-study/1.0 (Royal Society official historical roster acquisition; no DOB/BaZi)"

MEMBERSHIP="ctl00$main$DSCoverySearch1$ctl00$SearchText$MembershipCategory_default"
SEARCHBTN="ctl00$main$DSCoverySearch1$ctl01$Button1"
TOP_PAGESIZE="ctl00$main$TopPager$ctl15"
TOP_REFRESH="ctl00$main$TopPager$ctl17"

class PageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hidden={}
        self.links=[]
        self.in_table=False
        self.in_tr=False
        self.in_cell=False
        self.current_row=[]
        self.rows=[]
        self.cell=[]
        self.table_id=""
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=="input" and a.get("name") and (a.get("type") or "").lower()=="hidden":
            self.hidden[a["name"]]=a.get("value","")
        elif tag=="a" and a.get("href"):
            self.links.append((a.get("href",""),""))
        elif tag=="table":
            self.in_table=True
            self.table_id=a.get("id","")
        elif self.in_table and self.table_id=="overviewlist" and tag=="tr":
            self.in_tr=True; self.current_row=[]
        elif self.in_tr and tag in ("td","th"):
            self.in_cell=True; self.cell=[]
        elif self.in_cell and tag=="br":
            self.cell.append(" ")
    def handle_data(self,data):
        if self.in_cell:self.cell.append(data)
        if self.links:
            href,text=self.links[-1]
            if href and text is not None:
                self.links[-1]=(href,text+data)
    def handle_endtag(self,tag):
        if self.in_cell and tag in ("td","th"):
            txt=re.sub(r"\s+"," ",html.unescape("".join(self.cell))).strip()
            self.current_row.append(txt); self.in_cell=False
        elif self.in_tr and tag=="tr":
            if self.current_row:self.rows.append(self.current_row)
            self.in_tr=False
        elif self.in_table and tag=="table":
            self.in_table=False; self.table_id=""

def sha256(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for c in iter(lambda:f.read(1024*1024),b""):h.update(c)
    return h.hexdigest()

def make_opener():
    cj=http.cookiejar.CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

def request(op,url,data=None,referer=None,retries=5):
    last=None
    for attempt in range(retries):
        try:
            headers={"User-Agent":UA,"Accept":"text/html,application/xhtml+xml"}
            if referer:headers["Referer"]=referer
            if data is not None:
                body=urllib.parse.urlencode(data).encode("utf-8")
                headers["Content-Type"]="application/x-www-form-urlencoded"
                req=urllib.request.Request(url,data=body,method="POST",headers=headers)
            else:
                req=urllib.request.Request(url,headers=headers)
            with op.open(req,timeout=180) as r:
                raw=r.read()
                return raw,r.geturl(),r.status,dict(r.headers)
        except Exception as e:
            last=e
            if attempt+1<retries:time.sleep(min(20,2**attempt))
    raise RuntimeError(f"HTTP failed after {retries} attempts: {url}\n{last}")

def parse_page(raw):
    text=raw.decode("utf-8",errors="replace")
    p=PageParser();p.feed(text)
    return text,p

def result_range(text):
    m=re.search(r"\b(\d[\d,]*)\s+to\s+(\d[\d,]*)\s+of\s+(\d[\d,]*)\b",text,re.I)
    if not m:return None
    return tuple(int(x.replace(",","")) for x in m.groups())

def record_rows(text,category,source_url,page_no):
    # BeautifulSoup is deliberately avoided; use the record URLs and table rows from stdlib parsing.
    p=PageParser();p.feed(text)
    # overview table row layout: [View record, display_name, lifespan, elected]
    hrefs=[]
    for href,label in p.links:
        if "Record.aspx" in href and "src=CalmView.Persons" in href:
            full=urljoin(source_url,html.unescape(href))
            q=parse_qs(urlparse(full).query)
            rid=(q.get("id") or [""])[0]
            if rid:
                hrefs.append((rid,full))
    out=[]
    data_rows=[r for r in p.rows if r and not (r[0].lower()=="surname" if r else False)]
    if len(hrefs)!=len(data_rows):
        # Some rows may contain non-person links; fall back by explicit row regex.
        out=[]
        pat=re.compile(
            r'''(?is)<tr[^>]*class=["'][^"']*\brecord\b[^"']*["'][^>]*>.*?'''
            r'''href=["']([^"']*Record\.aspx\?[^"']*src=CalmView\.Persons[^"']*)["'][^>]*>.*?</a>'''
            r'''(.*?)</tr>'''
        )
        for href,body in pat.findall(text):
            cells=re.findall(r"(?is)<td[^>]*>(.*?)</td>",body)
            vals=[]
            for cell in cells:
                cell=re.sub(r"(?is)<[^>]+>"," ",cell)
                vals.append(re.sub(r"\s+"," ",html.unescape(cell)).strip())
            full=urljoin(source_url,html.unescape(href))
            q=parse_qs(urlparse(full).query)
            rid=(q.get("id") or [""])[0]
            if rid and len(vals)>=4:
                out.append({
                    "record_id":rid,
                    "display_name":vals[1],
                    "lifespan_text":vals[2],
                    "election_date_text":vals[3],
                    "membership_category_query":category,
                    "record_url":full.split("&pos=",1)[0],
                    "result_page":page_no,
                })
        return out
    for (rid,full),vals in zip(hrefs,data_rows):
        if len(vals)<4:continue
        out.append({
            "record_id":rid,
            "display_name":vals[1],
            "lifespan_text":vals[2],
            "election_date_text":vals[3],
            "membership_category_query":category,
            "record_url":full.split("&pos=",1)[0],
            "result_page":page_no,
        })
    return out

def hidden_fields(raw):
    _,p=parse_page(raw)
    return p.hidden

def find_next(text,current_url):
    p=PageParser();p.feed(text)
    for href,label in p.links:
        if re.sub(r"\s+"," ",label).strip().lower()=="next" and "Overview.aspx" in href:
            return urljoin(current_url,html.unescape(href))
    return ""

def start_search(category):
    op=make_opener()
    raw,url,status,headers=request(op,SEARCH)
    hidden=hidden_fields(raw)
    if "__VIEWSTATE" not in hidden or "__EVENTVALIDATION" not in hidden:
        raise RuntimeError("Search page missing ASP.NET state fields")
    payload=dict(hidden)
    payload[MEMBERSHIP]=category
    payload[SEARCHBTN]="Search"
    res,rurl,rstatus,rheaders=request(op,SEARCH,payload,referer=url)
    rr=result_range(res.decode("utf-8",errors="replace"))
    if not rr:raise RuntimeError(f"Could not parse result count for {category}")
    return op,res,rurl,rr

def try_set_page_size_100(op,raw,url):
    hidden=hidden_fields(raw)
    if "__VIEWSTATE" not in hidden:return raw,url,False
    payload=dict(hidden)
    payload[TOP_PAGESIZE]="100"
    payload[TOP_REFRESH]="Refresh"
    try:
        res,rurl,status,headers=request(op,url,payload,referer=url)
        rr=result_range(res.decode("utf-8",errors="replace"))
        if rr and rr[0]==1 and (rr[1]-rr[0]+1)>=50:
            return res,rurl,True
    except Exception:
        pass
    return raw,url,False

def crawl_category(category):
    safe=re.sub(r"[^A-Za-z0-9]+","_",category).strip("_").lower()
    raw_dir=OUT/"raw_pages"/safe
    raw_dir.mkdir(parents=True,exist_ok=True)

    op,raw,url,rr=start_search(category)
    total=rr[2]
    raw,url,page100=try_set_page_size_100(op,raw,url)
    rr=result_range(raw.decode("utf-8",errors="replace"))
    page_size=(rr[1]-rr[0]+1) if rr else 20
    print(f"[{category}] total={total}, page_size={page_size}, page100={page100}")

    rows=[]
    page_hashes=[]
    page_no=1
    seen_urls=set()

    while True:
        text=raw.decode("utf-8",errors="replace")
        rr=result_range(text)
        if not rr:raise RuntimeError(f"{category}: missing result range on page {page_no}")
        a,b,t=rr
        if t!=total:raise RuntimeError(f"{category}: total changed {total}->{t}")

        p=raw_dir/f"page_{page_no:04d}.html"
        p.write_bytes(raw)
        page_hashes.append({
            "page":page_no,"range_start":a,"range_end":b,
            "sha256":sha256(p),"bytes":p.stat().st_size,"source_url":url
        })

        part=record_rows(text,category,url,page_no)
        print(f"  page {page_no}: {a}-{b}, parsed={len(part)}")
        if len(part)!=(b-a+1):
            raise RuntimeError(f"{category}: expected {b-a+1} rows on page {page_no}, parsed {len(part)}")
        rows.extend(part)

        if b>=total:break
        next_url=find_next(text,url)
        if not next_url:raise RuntimeError(f"{category}: no Next link on page {page_no}")
        if next_url in seen_urls:raise RuntimeError(f"{category}: repeated Next URL on page {page_no}")
        seen_urls.add(next_url)
        raw,url,status,headers=request(op,next_url,referer=url)
        page_no+=1
        time.sleep(0.08)

    ids=[r["record_id"] for r in rows]
    if len(rows)!=total:
        raise RuntimeError(f"{category}: official total {total}, extracted rows {len(rows)}")
    if len(set(ids))!=total:
        raise RuntimeError(f"{category}: expected {total} unique IDs, got {len(set(ids))}")

    csv_path=OUT/f"{safe}_roster.csv"
    fields=["record_id","display_name","lifespan_text","election_date_text",
            "membership_category_query","record_url","result_page"]
    with csv_path.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)

    return {
        "category":category,
        "official_total":total,
        "extracted_rows":len(rows),
        "unique_record_ids":len(set(ids)),
        "page_size":page_size,
        "pages_fetched":len(page_hashes),
        "rows_with_election_date":sum(bool(r["election_date_text"]) for r in rows),
        "rows_with_lifespan_text":sum(bool(r["lifespan_text"]) for r in rows),
        "csv_file":csv_path.name,
        "csv_sha256":sha256(csv_path),
        "csv_bytes":csv_path.stat().st_size,
        "raw_pages":page_hashes,
    }

def main():
    if OUT.exists() and any(OUT.iterdir()):
        raise RuntimeError(f"Output directory already exists and is not empty: {OUT}")
    OUT.mkdir(parents=True,exist_ok=True)
    summaries=[]
    for cat in ("Fellow","Foreign Member"):
        summaries.append(crawl_category(cat))
    manifest={
        "study":"Professor -> Academy -> Nobel/Fields academic-selection study",
        "dataset":"Royal Society official historical person-roster snapshot v1",
        "created_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
        "source":SEARCH,
        "source_system":"Royal Society CalmView Persons",
        "membership_categories_acquired":["Fellow","Foreign Member"],
        "primary_academy_cohort_rule":"Fellow only; Foreign Member retained separately and excluded from primary UK S=1 cohort",
        "identity_key":"CalmView Persons record_id (NA...)",
        "dob_lookup_performed":0,
        "bazi_variables_computed":0,
        "categories":summaries,
        "freeze_note":"Do not freeze unless official_total == extracted_rows == unique_record_ids for each category.",
    }
    (OUT/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    summary_rows=[]
    for s in summaries:
        for k in ("official_total","extracted_rows","unique_record_ids","page_size","pages_fetched",
                  "rows_with_election_date","rows_with_lifespan_text"):
            summary_rows.append({"category":s["category"],"metric":k,"value":s[k]})
    with (OUT/"summary.csv").open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=["category","metric","value"]);w.writeheader();w.writerows(summary_rows)
    print(json.dumps({
        s["category"]:{
            "official_total":s["official_total"],
            "extracted_rows":s["extracted_rows"],
            "unique_record_ids":s["unique_record_ids"],
            "page_size":s["page_size"],
            "pages_fetched":s["pages_fetched"]
        } for s in summaries
    },indent=2))

if __name__=="__main__":
    main()
