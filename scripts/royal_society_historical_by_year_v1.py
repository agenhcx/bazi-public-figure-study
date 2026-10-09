#!/usr/bin/env python3
from __future__ import annotations
import csv, datetime as dt, hashlib, html, json, re, time, urllib.parse, urllib.request
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse

BASE="https://catalogues.royalsociety.org"
OUT=Path("data/royal_society_historical_by_year_v1")
UA="bazi-public-figure-study/1.0 (Royal Society official past-Fellow roster by election year; no DOB/BaZi)"

def sha256(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for c in iter(lambda:f.read(1024*1024),b""): h.update(c)
    return h.hexdigest()

def get(url,retries=7):
    last=None
    for a in range(retries):
        try:
            req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"text/html,application/xhtml+xml"})
            with urllib.request.urlopen(req,timeout=150) as r:
                return r.read(),r.geturl(),r.status,dict(r.headers)
        except Exception as e:
            last=e
            if a+1<retries:
                # Longer cooldown for CalmView throttling.
                time.sleep(min(90,3*(2**a)))
    raise RuntimeError(f"GET failed after {retries}: {url}\n{last}")

class PageParser(HTMLParser):
    def __init__(self):
        super().__init__();self.links=[];self.in_table=False;self.table_id="";self.in_tr=False;self.in_cell=False;self.cell=[];self.current_row=[];self.rows=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=="a" and a.get("href"):
            self.links.append((a["href"],""))
        elif tag=="table":
            self.in_table=True;self.table_id=a.get("id","")
        elif self.in_table and self.table_id=="overviewlist" and tag=="tr":
            self.in_tr=True;self.current_row=[]
        elif self.in_tr and tag in ("td","th"):
            self.in_cell=True;self.cell=[]
        elif self.in_cell and tag=="br":
            self.cell.append(" ")
    def handle_data(self,data):
        if self.in_cell:self.cell.append(data)
        if self.links:
            h,t=self.links[-1];self.links[-1]=(h,t+data)
    def handle_endtag(self,tag):
        if self.in_cell and tag in ("td","th"):
            txt=re.sub(r"\s+"," ",html.unescape("".join(self.cell))).strip()
            self.current_row.append(txt);self.in_cell=False
        elif self.in_tr and tag=="tr":
            if self.current_row:self.rows.append(self.current_row)
            self.in_tr=False
        elif self.in_table and tag=="table":
            self.in_table=False;self.table_id=""

def result_range(text):
    m=re.search(r"\b(\d[\d,]*)\s+to\s+(\d[\d,]*)\s+of\s+(\d[\d,]*)\b",text,re.I)
    return tuple(int(x.replace(",","")) for x in m.groups()) if m else None

def year_url(year):
    filt=f"(((MembershipCategory='Fellow'))) And ((DateOfElection='{year}'))"
    return BASE+"/calmview/Overview.aspx?"+urllib.parse.urlencode({"src":"CalmView.Persons","r":filt})

def parse_rows(text,year,page_no,source_url):
    p=PageParser();p.feed(text)
    hrefs=[]
    for href,label in p.links:
        full=urljoin(source_url,html.unescape(href))
        if "Record.aspx" in full and "src=CalmView.Persons" in full:
            q=parse_qs(urlparse(full).query);rid=(q.get("id") or [""])[0]
            if rid:hrefs.append((rid,full))
    # CalmView repeats record links in some controls; preserve first URL per ID in page order.
    uniq=[];seen=set()
    for rid,full in hrefs:
        if rid not in seen:
            seen.add(rid);uniq.append((rid,full))
    data_rows=[r for r in p.rows if len(r)>=4 and str(r[0]).strip().lower()!="surname"]
    if len(data_rows)!=len(uniq):
        raise RuntimeError(f"year {year} page {page_no}: rows={len(data_rows)} unique_record_links={len(uniq)}")
    out=[]
    for (rid,full),vals in zip(uniq,data_rows):
        out.append({
          "record_id":rid,
          "display_name":vals[1],
          "lifespan_text":vals[2],
          "election_date_text":vals[3],
          "election_year_query":year,
          "record_url":full.split("&pos=",1)[0],
          "result_page":page_no,
        })
    return out,p

def find_next(p,current_url):
    for href,label in p.links:
        if re.sub(r"\s+"," ",label).strip().lower()=="next" and "Overview.aspx" in href:
            return urljoin(current_url,html.unescape(href))
    return ""

def crawl_year(year):
    raw,url,status,headers=get(year_url(year))
    text=raw.decode("utf-8",errors="replace")
    rr=result_range(text)
    if not rr:
        # Recent years may have zero deceased/past Fellows and return to a blank search state.
        if "No records" in text or "PersonSearch" in url or "personsearch" in url:
            return [],{"year":year,"official_total":0,"pages":0,"requests":1}
        raise RuntimeError(f"year {year}: no result range; final_url={url}")

    total=rr[2];rows=[];page_no=1;previous_end=0;requests=1
    rawdir=OUT/"raw_pages"/str(year);rawdir.mkdir(parents=True,exist_ok=True)
    while True:
        text=raw.decode("utf-8",errors="replace")
        rr=result_range(text)
        if not rr:raise RuntimeError(f"year {year} page {page_no}: missing result range")
        a,b,t=rr
        if t!=total:raise RuntimeError(f"year {year}: total changed {total}->{t}")
        if a!=previous_end+1:raise RuntimeError(f"year {year}: nonprogress {previous_end} -> {a}-{b}")
        previous_end=b
        pagefile=rawdir/f"page_{page_no:02d}.html";pagefile.write_bytes(raw)
        part,p=parse_rows(text,year,page_no,url)
        if len(part)!=(b-a+1):
            raise RuntimeError(f"year {year} page {page_no}: expected {b-a+1}, parsed {len(part)}")
        rows.extend(part)
        if b>=total:break
        nxt=find_next(p,url)
        if not nxt:raise RuntimeError(f"year {year}: no Next at {a}-{b}/{total}")
        raw,url,status,headers=get(nxt);requests+=1;page_no+=1
        time.sleep(0.45)

    ids=[r["record_id"] for r in rows]
    if len(rows)!=total or len(set(ids))!=total:
        raise RuntimeError(f"year {year}: total={total} rows={len(rows)} unique={len(set(ids))}")
    return rows,{"year":year,"official_total":total,"pages":page_no,"requests":requests}

def main():
    if OUT.exists() and any(OUT.iterdir()):
        raise RuntimeError(f"Output directory nonempty: {OUT}")
    OUT.mkdir(parents=True,exist_ok=True)
    allrows=[];yearstats=[]
    for year in range(1660,2026):
        try:
            rows,stat=crawl_year(year)
        except Exception as e:
            raise RuntimeError(f"Failed election year {year}: {e}") from e
        allrows.extend(rows);yearstats.append(stat)
        if year%10==0 or stat["official_total"]>=20 or year>=2020:
            print(f"{year}: total={stat['official_total']} pages={stat['pages']} cumulative={len(allrows)}")
        time.sleep(0.25)

    ids=[r["record_id"] for r in allrows]
    dup=[rid for rid,n in __import__("collections").Counter(ids).items() if n>1]
    if dup:
        raise RuntimeError(f"Duplicate record IDs across election-year queries: {len(dup)} e.g. {dup[:20]}")

    csvp=OUT/"royal_society_past_fellows_by_election_year_v1.csv"
    fields=["record_id","display_name","lifespan_text","election_date_text","election_year_query","record_url","result_page"]
    with csvp.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(allrows)

    statp=OUT/"year_counts.csv"
    with statp.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=["year","official_total","pages","requests"]);w.writeheader();w.writerows(yearstats)

    manifest={
      "dataset":"Royal Society official past-Fellow roster by election year v1",
      "created_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
      "years_queried":"1660-2025 inclusive",
      "membership_category":"Fellow",
      "rows":len(allrows),
      "unique_record_ids":len(set(ids)),
      "years_with_records":sum(s["official_total"]>0 for s in yearstats),
      "total_http_result_pages":sum(s["requests"] for s in yearstats),
      "csv_sha256":sha256(csvp),
      "year_counts_sha256":sha256(statp),
      "dob_lookup_performed":0,
      "bazi_variables_computed":0,
      "note":"Independent election-year queries are used to avoid long-session CalmView paging resets/throttling. This table is past/deceased Fellow roster acquisition only and is not yet the combined frozen UK cohort."
    }
    (OUT/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(manifest,ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
