#!/usr/bin/env python3
"""Inventory Académie des sciences Comptes rendus historical volumes, 1835-1940.

Compare 211 Wikisource Livre: volume entries against the original Academy's
journal website year/volume source links. Probe a bounded, stratified selection
of *transcribed* Table des matières pages. No original scan event-page claims,
no inferred zero-election years, no BaZi or accepted membership changes.

Python 3.10+, BeautifulSoup4 (pinned in CI).
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

from bs4 import BeautifulSoup
from france_academy_wikisource_election_rows_v1 import extract_from_html
from france_academy_wikisource_index_preflight_v1 import build_urls

VERSION = "france-academy-211-comptes-rendus-volume-inventory-v1"
CAT = "Catégorie:Index - Comptes rendus hebdomadaires des séances de l’Académie des sciences"
API = "https://fr.wikisource.org/w/api.php"
OFFICIAL = "https://comptes-rendus.academie-sciences.fr/page/consulter-les-anciens-numeros-1835-1996_fr/"
OUT = Path("data/france_academy_comptes_rendus_211_volume_inventory_v1")
UA = "bazi-public-figure-study/1.0 (historical primary-source inventory; github.com/agenhcx/bazi-public-figure-study)"
TITLE = re.compile(r"\btome\s+0*(\d{1,3})\s*,\s*(18\d{2}|19\d{2})\.djvu\s*$",re.I)
SAMPLE = [1,20,54,91,121,136,158,168,182,198,211]
COLS = ["volume","year","expected_season","wikisource_book_title","wikisource_book_url",
        "wikisource_table_url","official_source_url","official_source_host",
        "official_link_mapping_status","category_evidence_sha256",
        "table_sampled","table_http_status","table_html_sha256",
        "table_body_readable","election_heading_detected","transcribed_election_rows",
        "full_like_event_rows_in_sample","correspondent_foreign_event_rows_in_sample",
        "original_printed_election_pages_directly_inspected",
        "study_membership_accepted","study_DOB_accepted","bazi_variables_computed"]
FULL = {"FULL_SECTION_MEMBER","FULL_NONRESIDENT_MEMBER","FULL_ACADEMICIAN_LIBRE"}
OTHER = {"CORRESPONDENT","FOREIGN_ASSOCIATE"}


def sha(b):return hashlib.sha256(b).hexdigest()


def fetch(url,timeout):
    req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"application/json,text/html;q=0.9"})
    with urllib.request.urlopen(req,timeout=timeout) as rsp:
        b=rsp.read(3_500_001)
        if len(b)>3_500_000:raise ValueError("Unexpected giant single webpage")
        return b,int(rsp.status),rsp.headers.get("Content-Type","")


def get_cached(url,path,offline,timeout,delay,last_request):
    path=Path(path)
    if path.is_file():
        return path.read_bytes(),"LOCAL_CACHE"
    if offline:
        raise FileNotFoundError("Offline cache missing (do not silently imply absence): "+str(path))
    if last_request[0] is not None:
        time.sleep(max(0,delay-(time.monotonic()-last_request[0])))
    last_request[0]=time.monotonic()
    body,code,_=fetch(url,timeout)
    if code!=200:raise ValueError("HTTP "+str(code))
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(path.suffix+".part")
    temp.write_bytes(body)
    temp.replace(path)
    return body,"HTTP_200"


def expected_year(v):
    if v==1:return 1835
    return 1836+(v-2)//2


def expected_volumes(year):
    if year==1835:return [1]
    base=2+2*(year-1836)
    return [base,base+1]


def parse_category_json(raw):
    obj=json.loads(raw)
    rows=[]
    for item in (obj.get("query") or {}).get("categorymembers",[]):
        title=item.get("title","")
        match=TITLE.search(title)
        if not match:continue
        n,y=int(match.group(1)),int(match.group(2))
        rows.append({"volume":n,"year":y,"wikisource_book_title":title})
    return rows,obj.get("continue")


def get_category(cache,offline,timeout,delay,last_request):
    # Always follow MediaWiki continuation. Category count is an inventory,
    # not evidence of complete table transcriptions or elected persons.
    rows=[]
    snapshots=[]
    cont={}
    for page in range(1,5):
        params={"action":"query","format":"json","formatversion":"2",
                "list":"categorymembers","cmtitle":CAT,"cmnamespace":"104","cmlimit":"500"}
        params.update(cont)
        url=API+"?"+urllib.parse.urlencode(params)
        key="category_page_"+str(page)+".json"
        raw,status=get_cached(url,cache/key,offline,timeout,delay,last_request)
        records,more=parse_category_json(raw)
        rows.extend(records)
        snapshots.append({"page":page,"url":url,"cache":status,"sha256":sha(raw),
                          "parsed_volume_titles":len(records)})
        if not more:break
        cont=more
    else:raise RuntimeError("Category pagination exceeded safe cap; manual review")
    return rows,snapshots


def parse_official(raw):
    soup=BeautifulSoup(raw,"html.parser")
    result={}
    coverage={}
    for li in soup.find_all("li"):
        txt=" ".join(li.get_text(" ",strip=True).split())
        m=re.match(r"^(\d{4})\s*:",txt)
        if not m:continue
        year=int(m.group(1))
        if not 1835<=year<=1940:continue
        vols=expected_volumes(year)
        links=[]
        for a in li.find_all("a",href=True):
            href=urllib.parse.urljoin(OFFICIAL,a["href"])
            host=urllib.parse.urlparse(href).netloc.lower()
            if ("gallica.bnf.fr" in host or
                "biodiversitylibrary.org" in host or
                "archive.org" in host):
                links.append((href,host))
        if year in coverage:continue
        coverage[year]={"expected_volumes":vols,"original_archive_links_in_annual_row":len(links)}
        if len(links)==len(vols):
            for i,v in enumerate(vols):
                result[v]={"url":links[i][0],"host":links[i][1],"status":"OFFICIAL_ANNUAL_ROW_LINK_ORDER"}
        elif len(vols)==2 and len(links)==1:
            # Specifically in 1939 the official row links tomes 208 and 209 jointly.
            # Do not assume same item unless explicitly named as both volumes.
            if year==1939 and "CCVIII" in txt.upper() and "CCIX" in txt.upper():
                for v in vols:
                    result[v]={"url":links[0][0],"host":links[0][1],
                               "status":"OFFICIAL_1939_JOINT_LINK_TWO_VOLUMES"}
            else:
                for v in vols:
                    result[v]={"url":"","host":"","status":"AMBIGUOUS_ONE_LINK_FOR_TWO_VOLUMES"}
        else:
            for v in vols:
                result[v]={"url":"","host":"","status":"OFFICIAL_ANNUAL_LINK_COUNT_UNRESOLVED"}
    return result,coverage


def check_inventory(rows):
    vols=[r["volume"] for r in rows]
    if len(vols)!=211 or len(set(vols))!=211 or set(vols)!=set(range(1,212)):
        raise RuntimeError("Expected exact volume set 1..211 from Wikisource; got "
                           +repr({"records":len(vols),"unique":len(set(vols)),
                                  "missing":sorted(set(range(1,212))-set(vols)),
                                  "unexpected":sorted(set(vols)-set(range(1,212)))}))
    for r in rows:
        if r["year"]!=expected_year(r["volume"]):
            raise RuntimeError(f"Volume/year mismatch {r!r}")


def create_inventory(category,official):
    inventory=[]
    for item in sorted(category,key=lambda r:r["volume"]):
        v,y=item["volume"],item["year"]
        origin=official.get(v,{"url":"","host":"","status":"NO_OFFICIAL_VOLUME_ENTRY"})
        book=item["wikisource_book_title"]
        book_url="https://fr.wikisource.org/wiki/"+urllib.parse.quote(book.replace(" ","_"),safe=":/")
        ses="FIRST_ONLY" if v==1 else "FIRST_HALF" if v%2==0 else "SECOND_HALF"
        inventory.append({"volume":v,"year":y,"expected_season":ses,
                          "wikisource_book_title":book,"wikisource_book_url":book_url,
                          "wikisource_table_url":build_urls(v,y)["wiki"],
                          "official_source_url":origin["url"],
                          "official_source_host":origin["host"],
                          "official_link_mapping_status":origin["status"],
                          "category_evidence_sha256":"",
                          "table_sampled":"0","table_http_status":"NOT_CHECKED",
                          "table_html_sha256":"","table_body_readable":"NOT_CHECKED",
                          "election_heading_detected":"NOT_CHECKED",
                          "transcribed_election_rows":"",
                          "full_like_event_rows_in_sample":"",
                          "correspondent_foreign_event_rows_in_sample":"",
                          "original_printed_election_pages_directly_inspected":"0",
                          "study_membership_accepted":"0","study_DOB_accepted":"0",
                          "bazi_variables_computed":"0"})
    return inventory


def write_csv(path,rows,cols):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("w",newline="",encoding="utf-8-sig") as f:
        w=csv.DictWriter(f,fieldnames=cols,extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def probe_table(row,cache,offline,timeout,delay,last_request):
    v,y=row["volume"],row["year"]
    path=cache/("table_"+str(v)+"_"+str(y)+".html")
    row["table_sampled"]="1"
    try:
        raw,state=get_cached(row["wikisource_table_url"],path,offline,timeout,delay,last_request)
        events,heads=extract_from_html(raw,y,v)
        soup=BeautifulSoup(raw,"html.parser")
        text=" ".join(soup.get_text(" ",strip=True).split())
        relevant=[h for h in heads if h.startswith("election")]
        row.update({"table_http_status":state,"table_html_sha256":sha(raw),
                    "table_body_readable":"1" if len(text)>=500 else "0",
                    "election_heading_detected":"1" if relevant else "0",
                    "transcribed_election_rows":str(len(events)),
                    "full_like_event_rows_in_sample":str(sum(e["transcribed_election_type"] in FULL for e in events)),
                    "correspondent_foreign_event_rows_in_sample":str(sum(e["transcribed_election_type"] in OTHER for e in events))})
    except (urllib.error.HTTPError,urllib.error.URLError,TimeoutError,ValueError,FileNotFoundError) as exc:
        row.update({"table_http_status":"HTTP_"+str(exc.code) if isinstance(exc,urllib.error.HTTPError)
                    else type(exc).__name__,"table_body_readable":"UNDETERMINED",
                    "election_heading_detected":"UNDETERMINED",
                    "transcribed_election_rows":"","full_like_event_rows_in_sample":"",
                    "correspondent_foreign_event_rows_in_sample":""})


def synthetic():
    items=[{"volume":1,"year":1835},{"volume":54,"year":1862},{"volume":211,"year":1940}]
    assert all(i["year"]==expected_year(i["volume"]) for i in items)
    response=json.dumps({"query":{"categorymembers":[
       {"title":"Livre:Comptes rendus hebdomadaires des séances de l’Académie des sciences, tome 001, 1835.djvu"},
       {"title":"Livre:Comptes rendus hebdomadaires des séances de l’Académie des sciences, tome 054, 1862.djvu"}]}}).encode()
    parsed,more=parse_category_json(response)
    assert len(parsed)==2 and parsed[1]["volume"]==54 and more is None
    original=("<ul><li>1835 : <a href='https://gallica.bnf.fr/ark:/12148/bpt6k1'>t. I</a></li>"
              "<li>1939 : <a href='https://gallica.bnf.fr/ark:/12148/bpt6k2'>t. CCVIII - t. CCIX</a></li>"
              "<li>1940 : <a href='https://gallica.bnf.fr/a'>t. CCX</a> - "
              "<a href='https://gallica.bnf.fr/b'>t. CCXI</a></li></ul>").encode()
    o,years=parse_official(original)
    assert o[1]["status"]=="OFFICIAL_ANNUAL_ROW_LINK_ORDER"
    assert o[208]["status"]=="OFFICIAL_1939_JOINT_LINK_TWO_VOLUMES"
    assert o[211]["url"]=="https://gallica.bnf.fr/b"
    assert years[1940]["original_archive_links_in_annual_row"]==2
    print("PASS: 211 expected volumes, category metadata, official volume mapping, 1939 shared link and no study inclusion")


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--fixture-check",action="store_true")
    p.add_argument("--offline",action="store_true",help="Require previously cached source responses")
    p.add_argument("--dry-run",action="store_true")
    p.add_argument("--sample-volumes",default=",".join(map(str,SAMPLE)),
                   help="Comma-separated selection (max 16), or empty string to skip all table probes")
    p.add_argument("--max-table-probes",type=int,default=11)
    p.add_argument("--out",type=Path,default=OUT)
    p.add_argument("--timeout",type=int,default=24)
    p.add_argument("--delay",type=float,default=1.2)
    args=p.parse_args()
    if args.fixture_check:return synthetic()
    samples=sorted(set(int(v) for v in args.sample_volumes.split(",") if v.strip()))
    if any(not 1<=v<=211 for v in samples):raise ValueError("Only 1..211 volumes permitted")
    if len(samples)>16 or args.max_table_probes>16 or args.delay<1.1:
        raise ValueError("Bounded 16-sample test, >=1.1 sec delay")
    samples=samples[:args.max_table_probes]
    if args.dry_run:
        print(json.dumps({"source":OFFICIAL,"category":CAT,"expected_volumes":211,
              "sample_volumes":samples,"source_read_only":True,
              "original_election_pages_verified":0,"network_requests":0},ensure_ascii=False))
        return
    cache=Path("local_runs/france_academy_211_volume_inventory_source_cache_v1")
    last_request=[None]
    category,cat_pages=get_category(cache,args.offline,args.timeout,args.delay,last_request)
    check_inventory(category)
    original_raw,_=get_cached(OFFICIAL,cache/"official_journal_archive.html",args.offline,
                              args.timeout,args.delay,last_request)
    official,coverage=parse_official(original_raw)
    inventory=create_inventory(category,official)
    category_digest=hashlib.sha256("".join(p["sha256"] for p in cat_pages).encode()).hexdigest()
    for r in inventory:r["category_evidence_sha256"]=category_digest
    for v in samples:
        row=inventory[v-1]
        probe_table(row,cache,args.offline,args.timeout,args.delay,last_request)
        print("TABLE",row["volume"],row["year"],row["table_http_status"],
              row["election_heading_detected"],row["transcribed_election_rows"],flush=True)
    assert len(inventory)==211 and all(r["study_membership_accepted"]=="0" and
        r["study_DOB_accepted"]=="0" and r["bazi_variables_computed"]=="0" and
        r["original_printed_election_pages_directly_inspected"]=="0" for r in inventory)
    args.out.mkdir(parents=True,exist_ok=True)
    write_csv(args.out/"academy_original_wikisource_211_volume_inventory_v1.csv",inventory,COLS)
    link_status=Counter(r["official_link_mapping_status"] for r in inventory)
    probes=[r for r in inventory if r["table_sampled"]=="1"]
    summary={
       "version":VERSION,
       "historic_period": [1835,1940],
       "official_site":OFFICIAL,
       "official_site_sha256":sha(original_raw),
       "official_years_with_annual_rows":len(coverage),
       "official_archive_link_status":dict(link_status),
       "wikisource_category":CAT,
       "category_source_pages":cat_pages,
       "category_volume_count":len(inventory),
       "volume_range_1_to_211_complete":True,
       "expected_year_count":106,
       "table_of_contents_probed_volumes":[x["volume"] for x in probes],
       "table_probes_completed":len(probes),
       "table_probe_http_status":dict(Counter(x["table_http_status"] for x in probes)),
       "table_probe_readable_count":sum(x["table_body_readable"]=="1" for x in probes),
       "table_probe_election_heading_count":sum(x["election_heading_detected"]=="1" for x in probes),
       "sample_election_event_candidates":sum(int(x["transcribed_election_rows"] or 0) for x in probes),
       "unprobed_volumes_not_claimed_readable":211-len(probes),
       "source_tier":"ORIGINAL_ACADEMY_JOURNAL_OFFICIAL_VOLUME_LINKS_PLUS_WIKISOURCE_BOOK_ENTRIES;SAMPLE_TABLES_ONLY",
       "no_original_book_election_pages_scanned":True,
       "no_full_member_roster_completeness_claim":True,
       "accepted_full_memberships":0,"accepted_exact_dobs":0,"bazi_variables_computed":0
    }
    (args.out/"summary.json").write_text(json.dumps(summary,indent=2,ensure_ascii=False)+"\n",encoding="utf8")
    print("SUMMARY",json.dumps(summary,ensure_ascii=False))


if __name__=="__main__":main()
