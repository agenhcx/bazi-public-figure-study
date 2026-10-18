#!/usr/bin/env python3
"""Supplement direct 1839 Liouville vote result and 1927 Fabry original image.

Uses only two targeted Commons original DjVu pages; earlier Liouville
p873/p919 originals already collected separately and retained by source SHA.
Detailed sanitized metadata for unavailable Fabry preview; never assume
Wikisource index page is identical to original printed page.
No study member DOB acceptance or BaZi variables.
"""
from __future__ import annotations
import argparse,hashlib,json,time,urllib.error
from pathlib import Path
from france_academy_1839_1927_original_scan_audit_v1 import book_title,book_url,frames_from_book,preview_query
from france_academy_1856_commons_original_preview_v1 import request,get_metadata

V="france-academy-1839-1927-supplement-original-facsimile-v1"
TARGETS=[{"vol":8,"year":1839,"print":874,"person":"Joseph Liouville",
          "stage":"ACADEMY_ELECTION_VOTE_RESULT_CONTINUATION"},
         {"vol":184,"year":1927,"print":1516,"person":"Charles Fabry",
          "stage":"ACADEMY_FULL_SECTION_ELECTION"}]
OUT=Path("data/france_academy_1839_1927_original_supplement_v1")
IMG=Path("local_runs/france_academy_1839_1927_original_supplement_v1")
def hashit(a):return hashlib.sha256(a).hexdigest()
def thumbnail_error_diagnostic(body,frame):
    """Return bounded source-level reason; do not expose full URL query tokens."""
    d={}
    try:
        j=json.loads(body)
        pages=((j.get("query") or {}).get("pages") or [])
        if pages:
            p=pages[0]; info=(p.get("imageinfo") or [{}])[0]
            d={"title":str(p.get("title",""))[:160],
                "file_missing":p.get("missing"),
                "mime":info.get("mime"),
                "pagecount":info.get("pagecount"),
                "thumb_present":bool(info.get("thumburl")),
                "thumb_error":str(info.get("thumberror",""))[:240],
                "original_present":bool(info.get("url")),
                "requested_frame":frame}
        if "error" in j:d["api_error"]=str(j.get("error"))[:260]
    except (ValueError,IndexError,TypeError):
        d["reason"]="unparsed_commons_API_JSON"
    return d
def fixture():
    assert TARGETS[0]["print"]==874 and TARGETS[1]["print"]==1516
    sample=json.dumps({"query":{"pages":[{"title":"File:example.djvu","imageinfo":[
      {"mime":"image/vnd.djvu","pagecount":1200,"thumberror":"thumbnail failed"}]}]}}).encode()
    o=thumbnail_error_diagnostic(sample,874)
    assert o["thumb_error"]=="thumbnail failed" and not o["thumb_present"]
    print("PASS: separate 1839 vote-result page, 1927 full-member original; diagnostic only; zero cohort additions")
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--fixture-check",action="store_true")
    ap.add_argument("--download",action="store_true")
    ap.add_argument("--delay",type=float,default=1.5)
    ap.add_argument("--timeout",type=int,default=22)
    ap.add_argument("--out",type=Path,default=OUT)
    ap.add_argument("--images",type=Path,default=IMG)
    a=ap.parse_args()
    if a.fixture_check:return fixture()
    if a.delay<1.2:raise ValueError("Rate interval must be at least 1.2 seconds")
    rows=[];last=None
    def wait():
        nonlocal last
        if last is not None:time.sleep(max(0,a.delay-(time.monotonic()-last)))
        last=time.monotonic()
    for t in TARGETS:
        vol,year,p=t["vol"],t["year"],t["print"]
        row={"volume":vol,"year":year,"printed_page":p,
             "person":t["person"],"event_stage":t["stage"],
             "original_image_visually_reviewed":False,
             "original_signed_government_decree_verified":False,
             "final_accepted_regular_member":False,
             "final_accepted_DOB":False,"bazi_calculated":False}
        book=book_title(vol,year)
        wait()
        try:
            raw,status,mime=request(book_url(vol,year),1900000,a.timeout,"text/html")
            if status!=200:raise ValueError("Book index not HTTP200")
            row["index_source_sha256"]=hashit(raw)
            matches=frames_from_book(raw,book,{p}).get(p,[])
            row["DjVu_mapping_source_entries"]=matches
            if len(matches)!=1:
                row["status"]="PAGE_MAPPING_UNRESOLVED"
                rows.append(row);continue
            frame=matches[0]["frame"]
            row["frame"]=frame
            # Up to 2 bounded Commons metadata requests, first full and then
            # reduced-width if preview failed; no unbounded retry loops.
            for width in (850,480):
                wait()
                url=preview_query(book,frame).replace("iiurlwidth=1150","iiurlwidth="+str(width))
                body,http,ctype=request(url,850000,a.timeout)
                if http!=200:raise ValueError("Non-200 Commons imageinfo")
                row["commons_last_metadata_sha256"]=hashit(body)
                row["commons_last_metadata_diagnostic"]=thumbnail_error_diagnostic(body,frame)
                try:
                    info=get_metadata(body,frame)
                except (ValueError,IndexError,TypeError) as e:
                    row["commons_last_parse_error"]=type(e).__name__+":"+str(e)[:200]
                    row["status"]="COMMONS_THUMBNAIL_NOT_AVAILABLE_NEED_ALT_SOURCE"
                    continue
                row.update({"Commons_original_source":info["djvu_source_url"],
                            "original_public_thumbnail_url":info["thumbnail_url"],
                            "DJVU_book_pagecount":info["page_count"],
                            "thumbnail_requested_width":width,
                            "status":"PUBLIC_ORIGINAL_IMAGE_LOCATED_PENDING_VISUAL_CHECK"})
                if a.download:
                    wait()
                    data,http,ctype=request(info["thumbnail_url"],3000000,a.timeout,"image/jpeg,image/*")
                    if http!=200 or not data.startswith(b"\xff\xd8") or not ctype.startswith("image/"):
                        raise ValueError("Original preview is not JPEG image")
                    a.images.mkdir(parents=True,exist_ok=True)
                    name=f"tome{vol:03d}_{year}_print{p}_djvu{frame}.jpg"
                    (a.images/name).write_bytes(data)
                    row.update({"transient_filename":name,"image_sha256":hashit(data),
                        "image_bytes":len(data),
                        "status":"IMAGE_DOWNLOADED_REQUIRES_HUMAN_VISUAL_INTERPRETATION"})
                break
        except (urllib.error.HTTPError,urllib.error.URLError,TimeoutError,ValueError) as e:
            row.update({"status":"SOURCE_ERROR_"+type(e).__name__,
                        "error_code":getattr(e,"code",None),
                        "error_summary":str(e)[:170]})
        rows.append(row)
    a.out.mkdir(parents=True,exist_ok=True)
    d={"version":V,"source_records":rows,
       "original_image_download_count":sum("image_sha256" in r for r in rows),
       "original_pages_visually_interpreted_by_script":0,
       "signed_royal_or_imperial_decrees_verified":0,
       "new_final_full_members":0,"new_final_birth_dates":0,"bazi_feature_count":0}
    (a.out/"Liouville_vote_and_Fabry_original_page_supplement_v1.json").write_text(
        json.dumps(d,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    print("SUPPLEMENT_SOURCE_STATUS",json.dumps([
      {"person":r["person"],"printed":r["printed_page"],"frame":r.get("frame"),
       "status":r["status"],"diagnostic":r.get("commons_last_metadata_diagnostic"),
       "preview_bytes":r.get("image_bytes")} for r in rows],ensure_ascii=False))
if __name__=="__main__":main()
