#!/usr/bin/env python3
"""Reusable original French Academy journal printed-page facsimile locator.

Given an original Tome/year and 1–4 printed pages, derive EXACT DjVu frame
from Wikisource Book pagelist links. Images may be on Commons OR locally
hosted by fr.wikisource.org; public imageinfo first Commons then local.
Store source SHA only in GitHub, small original previews as temporary artifacts.
Any original scan requires actual human visual interpretation separately;
nothing in this program marks historical persons as accepted full members.
"""
from __future__ import annotations
import argparse,hashlib,json,time,urllib.error
from pathlib import Path
from france_academy_1839_1927_original_scan_audit_v1 import (
    book_title,book_url,frames_from_book,preview_query)
from france_academy_1856_commons_original_preview_v1 import request,get_metadata

V="france-academy-generic-public-printed-page-original-scan-v1"
def sha(raw):return hashlib.sha256(raw).hexdigest()

def fixture():
    book=book_title(184,1927)
    assert "tome 184, 1927.djvu" in book
    assert "page1517" in preview_query(book,1517)
    assert "page1609" in preview_query(book,1609)
    assert "commons.wikimedia.org" in preview_query(book,1517)
    print("PASS: original scanned page locator, local Wikisource fallback and strict zero study-admissions policy")

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--fixture-check",action="store_true")
    p.add_argument("--volume",type=int,default=184)
    p.add_argument("--year",type=int,default=1927)
    p.add_argument("--pages",default="1517,1609",help="Comma separated 1..4 ORIGINAL printed page labels")
    p.add_argument("--delay",type=float,default=1.5)
    p.add_argument("--timeout",type=int,default=22)
    p.add_argument("--download",action="store_true")
    p.add_argument("--out",type=Path,default=Path("data/france_academy_fabry_1927_original_vote_decree_v1"))
    p.add_argument("--images",type=Path,default=Path("local_runs/france_academy_fabry_1927_original_scan_previews_v1"))
    a=p.parse_args()
    if a.fixture_check:return fixture()
    pages=[int(v) for v in a.pages.split(",") if v.strip()]
    if not 1<=len(pages)<=4 or len(set(pages))!=len(pages) or any(v<=0 for v in pages):
        raise ValueError("Only up to four distinct positive source printed pages per run")
    if not 1<=a.volume<=400 or not 1835<=a.year<=1965 or a.delay<1.2:
        raise ValueError("Unbounded volume/year or high frequency query")
    last=None
    def cool():
        nonlocal last
        if last is not None:time.sleep(max(0,a.delay-(time.monotonic()-last)))
        last=time.monotonic()
    cool()
    book=book_title(a.volume,a.year)
    raw,status,mime=request(book_url(a.volume,a.year),2000000,a.timeout,"text/html")
    if status!=200:raise ValueError("Original book index not HTTP200")
    source_hash=sha(raw)
    mappings=frames_from_book(raw,book,set(pages))
    out=[]
    for printed in pages:
        row={"year":a.year,"volume":a.volume,
           "printed_page_label":printed,"wikisource_book_source":book_url(a.volume,a.year),
           "wikisource_book_source_SHA256":source_hash,
           "page_link_source_candidates":mappings.get(printed,[]),
           "original_page_visually_reviewed":False,
           "decree_legal_signature_date_known":False,
           "person_accepted_as_member":False,
           "birth_date_accepted":False,"bazi_calculated":False}
        found=row["page_link_source_candidates"]
        if len(found)!=1:
            row["status"]="ORIGINAL_BOOK_PAGE_MAPPING_UNRESOLVED"
            out.append(row);continue
        frame=found[0]["frame"];row["djvu_frame"]=frame
        for host in ("commons.wikimedia.org","fr.wikisource.org"):
            cool()
            source_query=preview_query(book,frame).replace(
                 "https://commons.wikimedia.org","https://"+host)
            # Small thumbnail sufficient to assess election and government
            # approval text, and avoids 32MB+ original full DjVu archives.
            source_query=source_query.replace("iiurlwidth=1150","iiurlwidth=960")
            try:
                response,code,content_type=request(source_query,800000,a.timeout)
                if code!=200:raise ValueError("Original file imageinfo status not 200")
                row["imageinfo_metadata_SHA256"]=sha(response)
                row["imageinfo_last_host"]=host
                j=json.loads(response)
                k=((j.get("query") or {}).get("pages") or [{}])[0]
                row["imageinfo_file_is_missing"]=k.get("missing")
                info=get_metadata(response,frame)
                row.update({"original_DjVu_url":info["djvu_source_url"],
                            "DjVu_source_page_count":info["page_count"],
                            "scan_image_host":host,
                            "original_thumbnail_source_url":info["thumbnail_url"],
                            "status":"SCAN_THUMBNAIL_FOUND_NOT_VISUALLY_INSPECTED"})
                if a.download:
                    cool()
                    image,code,mime=request(info["thumbnail_url"],3000000,a.timeout,"image/jpeg,image/*")
                    if code!=200 or not image.startswith(b"\xff\xd8") or not mime.startswith("image/"):
                        raise ValueError("Original page thumbnail bytes are not JPEG")
                    a.images.mkdir(parents=True,exist_ok=True)
                    filename=f"original_tome{a.volume:03d}_{a.year}_print{printed}_frame{frame}.jpg"
                    (a.images/filename).write_bytes(image)
                    row.update({"transient_filename":filename,"image_SHA256":sha(image),
                        "image_bytes":len(image),"status":"ORIGINAL_SCAN_DOWNLOADED_FOR_HUMAN_REVIEW"})
                break
            except (urllib.error.HTTPError,urllib.error.URLError,TimeoutError,ValueError,IndexError) as e:
                row["last_attempt_error"]=type(e).__name__+":"+str(e)[:180]
                row["status"]="IMAGE_UNAVAILABLE_ON_"+host
        out.append(row)
    a.out.mkdir(parents=True,exist_ok=True)
    result={"version":V,"original_journal":"Académie des sciences, Comptes rendus",
        "year":a.year,"volume":a.volume,
        "records":out,"original_scan_preview_count":sum("image_SHA256" in x for x in out),
        "original_scan_visually_interpreted_in_script":0,
        "governmental_legal_dates_adjudicated":0,
        "accepted_regular_academy_members":0,"accepted_DOBs":0,"bazi_variables_computed":0}
    (a.out/"original_source_page_scan_metadata_v1.json").write_text(
         json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    print("ORIGINAL_SCAN_LOCATORS",json.dumps([{"page":x["printed_page_label"],
        "frame":x.get("djvu_frame"),"host":x.get("scan_image_host"),
        "status":x["status"],"bytes":x.get("image_bytes")} for x in out],ensure_ascii=False))

if __name__=="__main__":main()
