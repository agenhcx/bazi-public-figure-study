#!/usr/bin/env python3
from __future__ import annotations

import argparse, csv, datetime as dt, hashlib, html, http.cookiejar, json, re, time
import urllib.parse, urllib.request
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse

BASE="https://catalogues.royalsociety.org"
SEARCH=BASE+"/calmview/personsearch.aspx?src=CalmView.Persons"
UA="bazi-public-figure-study/1.0 (Royal Society past-Fellow roster by election year v2; no DOB/BaZi)"

MEMBERSHIP="ctl00$main$DSCoverySearch1$ctl00$SearchText$MembershipCategory_default"
ELECTION="ctl00$main$DSCoverySearch1$ctl00$SearchText$DateOfElection_default"
SEARCHBTN="ctl00$main$DSCoverySearch1$ctl01$Button1"
NEXT_TARGET="ctl00$main$TopPager$ctl22"

class Parser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hidden={}; self.links=[]; self.in_table=False; self.table_id=""
        self.in_tr=False; self.in_cell=False; self.cell=[]; self.current_row=[]; self.rows=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=="input" and a.get("name") and (a.get("type") or "").lower()=="hidden":
            self.hidden[a["name"]]=a.get("value","")
        elif tag=="a" and a.get("href"):
            self.links.append((a["href"],""))
        elif tag=="table":
            self.in_table=True; self.table_id=a.get("id","")
        elif self.in_table and self.table_id=="overviewlist" and tag=="tr":
            self.in_tr=True; self.current_row=[]
        elif self.in_tr and tag in ("td","th"):
            self.in_cell=True; self.cell=[]
        elif self.in_cell and tag=="br":
            self.cell.append(" ")
    def handle_data(self,data):
        if self.in_cell:self.cell.append(data)
        if self.links:
            h,t=self.links[-1]; self.links[-1]=(h,t+data)
    def handle_endtag(self,tag):
        if self.in_cell and tag in ("td","th"):
            self.current_row.append(re.sub(r"\s+"," ",html.unescape("".join(self.cell))).strip())
            self.in_cell=False
        elif self.in_tr and tag=="tr":
            if self.current_row:self.rows.append(self.current_row)
            self.in_tr=False
        elif self.in_table and tag=="table":
            self.in_table=False; self.table_id=""

def sha256(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for c in iter(lambda:f.read(1<<20),b""):h.update(c)
    return h.hexdigest()

def make_opener():
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

def request(op,url,data=None,referer=None,retries=6):
    last=None
    for a in range(retries):
        try:
            headers={"User-Agent":UA,"Accept":"text/html,application/xhtml+xml"}
            if referer:headers["Referer"]=referer
            if data is None:
                req=urllib.request.Request(url,headers=headers)
            else:
                body=urllib.parse.urlencode(data).encode("utf-8")
                headers["Content-Type"]="application/x-www-form-urlencoded"
                req=urllib.request.Request(url,data=body,method="POST",headers=headers)
            with op.open(req,timeout=150) as r:
                return r.read(),r.geturl()
        except Exception as e:
            last=e
            if a+1<retries:time.sleep(min(60,2**a))
    raise RuntimeError(f"HTTP failed: {url}: {last}")

def parse(raw):
    text=raw.decode("utf-8",errors="replace")
    p=Parser();p.feed(text)
    return text,p

def result_range(text):
    m=re.search(r"\b(\d[\d,]*)\s+to\s+(\d[\d,]*)\s+of\s+(\d[\d,]*)\b",text,re.I)
    return tuple(int(x.replace(",","")) for x in m.groups()) if m else None

def record_rows(text,year,page_no,source_url):
    _,p=parse(text.encode("utf-8"))
    hrefs=[]
    for href,label in p.links:
        full=urljoin(source_url,html.unescape(href))
        if "Record.aspx" in full and "src=CalmView.Persons" in full:
            rid=(parse_qs(urlparse(full).query).get("id") or [""])[0]
            if rid:hrefs.append((rid,full))
    uniq=[];seen=set()
    for rid,full in hrefs:
        if rid not in seen:
            seen.add(rid);uniq.append((rid,full))
    data_rows=[r for r in p.rows if len(r)>=4 and str(r[0]).strip().lower()!="surname"]
    if len(uniq)!=len(data_rows):
        raise RuntimeError(f"year {year} page {page_no}: ids={len(uniq)} rows={len(data_rows)}")
    out=[]
    for (rid,full),vals in zip(uniq,data_rows):
        out.append({
          "record_id":rid,"display_name":vals[1],"lifespan_text":vals[2],
          "election_date_text":vals[3],"election_year_query":year,
          "record_url":full.split("&pos=",1)[0],"result_page":page_no,
        })
    return out

def start_year(year):
    op=make_opener()
    raw,url=request(op,SEARCH)
    text,p=parse(raw)
    if "__VIEWSTATE" not in p.hidden or "__EVENTVALIDATION" not in p.hidden:
        raise RuntimeError("search page missing state")
    payload=dict(p.hidden)
    payload[MEMBERSHIP]="Fellow"; payload[ELECTION]=str(year); payload[SEARCHBTN]="Search"
    raw,url=request(op,SEARCH,payload,referer=url)
    return op,raw,url

def crawl_year(year):
    op,raw,url=start_year(year)
    text,p=parse(raw)
    rr=result_range(text)
    if not rr:
        # CalmView returns the search form when no rows match.
        return [],{"year":year,"official_total":0,"pages":0}
    total=rr[2]; rows=[]; page_no=1; previous_end=0
    while True:
        text,p=parse(raw); rr=result_range(text)
        if not rr:raise RuntimeError(f"year {year} page {page_no}: missing range")
        a,b,t=rr
        if t!=total:raise RuntimeError(f"year {year}: total changed {total}->{t}")
        if a!=previous_end+1:raise RuntimeError(f"year {year}: nonprogress {previous_end}->{a}-{b}")
        previous_end=b
        part=record_rows(text,year,page_no,url)
        if len(part)!=(b-a+1):raise RuntimeError(f"year {year} page {page_no}: expected {b-a+1}, got {len(part)}")
        rows.extend(part)
        if b>=total:break
        # Fresh session per year means ASP.NET postback depth stays tiny
        # (normally only 2-4 pages), avoiding the long-session 403 seen in the
        # 7,099-row all-Fellow crawl.
        state=dict(p.hidden)
        if "__VIEWSTATE" not in state or "__EVENTVALIDATION" not in state:
            raise RuntimeError(f"year {year} page {page_no}: missing paging state")
        state["__EVENTTARGET"]=NEXT_TARGET; state["__EVENTARGUMENT"]=""
        raw,url=request(op,url,state,referer=url)
        page_no+=1; time.sleep(0.12)

    ids=[r["record_id"] for r in rows]
    if len(rows)!=total or len(set(ids))!=total:
        raise RuntimeError(f"year {year}: total={total}, rows={len(rows)}, unique={len(set(ids))}")
    return rows,{"year":year,"official_total":total,"pages":page_no}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--start-year",type=int,required=True)
    ap.add_argument("--end-year",type=int,required=True)
    args=ap.parse_args()
    if not (1660<=args.start_year<=args.end_year<=2025):raise SystemExit("bad year range")

    out=Path(f"data/royal_society_historical_by_year_v2/{args.start_year}_{args.end_year}")
    if out.exists() and any(out.iterdir()):raise RuntimeError(f"nonempty output: {out}")
    out.mkdir(parents=True,exist_ok=True)

    rows=[];stats=[];failures=[]
    for year in range(args.start_year,args.end_year+1):
        try:
            rr,st=crawl_year(year);rows.extend(rr);stats.append(st)
        except Exception as e:
            failures.append({"year":year,"error":repr(e)})
            stats.append({"year":year,"official_total":"","pages":"","error":repr(e)})
        if year%10==0 or year==args.end_year:
            print(f"{year}: cumulative_rows={len(rows)} failures={len(failures)}")
        time.sleep(0.18)

    ids=[r["record_id"] for r in rows]
    dup=[k for k,v in Counter(ids).items() if v>1]
    csvp=out/"past_fellows.csv"
    fields=["record_id","display_name","lifespan_text","election_date_text","election_year_query","record_url","result_page"]
    with csvp.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
    statp=out/"year_counts.csv"
    fields2=["year","official_total","pages","error"]
    with statp.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields2,extrasaction="ignore");w.writeheader();w.writerows(stats)
    manifest={
      "dataset":"Royal Society official past-Fellow roster by election year v2",
      "range":[args.start_year,args.end_year],"rows":len(rows),"unique_record_ids":len(set(ids)),
      "duplicate_record_ids":len(dup),"failed_years":len(failures),"failures":failures,
      "csv_sha256":sha256(csvp),"year_counts_sha256":sha256(statp),
      "dob_lookup_performed":0,"bazi_variables_computed":0
    }
    (out/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(manifest,ensure_ascii=False,indent=2))
    if failures or dup:raise SystemExit(2)

if __name__=="__main__":
    main()
