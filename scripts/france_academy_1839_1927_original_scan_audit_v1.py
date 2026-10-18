#!/usr/bin/env python3
"""Bounded ORIGINAL 1839 and 1927 Academy election/approval scanned-page retrieval.

Source is the Commons-hosted DjVu FACSIMILE of the original French Académie
des sciences printed Comptes rendus. Wikisource index supplies PRINT page
labels, which must be mapped to DjVu frames using the actual Livre page list.
JPG images remain in a short-lived CI artifact for DIRECT VISUAL INSPECTION,
and are not copied into GitHub's data directory. Metadata and SHA only.
"""
from __future__ import annotations
import argparse,hashlib,json,re,time,urllib.parse,urllib.error
from pathlib import Path
from bs4 import BeautifulSoup
from france_academy_1856_commons_original_preview_v1 import request,get_metadata,API

VERSION="france-academy-1839-1927-original-three-page-facsimile-source-v1"
OUT=Path("data/france_academy_1839_1927_three_original_pages_v1")
IMAGE_OUT=Path("local_runs/france_academy_1839_1927_original_preview_v1")
ITEMS=[
 {"volume":8,"year":1839,"printed_page":873,"name":"Joseph Liouville",
  "stage":"ACADEMY_ELECTION_VOTE","member_role_candidate":"FULL_SECTION_MEMBER"},
 {"volume":8,"year":1839,"printed_page":919,"name":"Joseph Liouville",
  "stage":"ROYAL_APPROVAL_INDEX_LOCATOR","member_role_candidate":"FULL_SECTION_MEMBER"},
 {"volume":184,"year":1927,"printed_page":1516,"name":"Charles Fabry",
  "stage":"ACADEMY_ELECTION_VOTE","member_role_candidate":"FULL_SECTION_MEMBER"}]
BASE="https://fr.wikisource.org/wiki/"
def sha(x):return hashlib.sha256(x).hexdigest()
def book_title(volume,year):
    return f"Comptes rendus hebdomadaires des séances de l’Académie des sciences, tome {volume:03d}, {year}.djvu"
def book_url(volume,year):
    return BASE+urllib.parse.quote("Livre:"+book_title(volume,year).replace(" ","_"),safe=":/")
def frames_from_book(raw,book,selected):
    soup=BeautifulSoup(raw,"html.parser")
    found={}
    for a in soup.select("a.prp-index-pagelist-page[href]"):
        label=a.get_text(" ",strip=True)
        if not label.isdigit() or int(label) not in selected:continue
        url=urllib.parse.urlparse(urllib.parse.urljoin("https://fr.wikisource.org/",a["href"]))
        if url.path.endswith("/index.php"):
            title=urllib.parse.parse_qs(url.query).get("title",[""])[0]
        else:title=urllib.parse.unquote(url.path).split("/wiki/",1)[-1]
        if not title.startswith("Page:"+book.replace(" ","_")+"/"):continue
        m=re.search(r"\.djvu/(\d+)$",title)
        if not m:continue
        found.setdefault(int(label),[]).append({
          "frame":int(m.group(1)),"source_href":a["href"],
          "is_uncreated_Page_namespace_redlink":"redlink=1" in url.query})
    return found
def preview_query(book,frame):
    params={"action":"query","format":"json","formatversion":"2",
       "prop":"imageinfo","iiprop":"url|size|mime","iiurlparam":"page"+str(frame),
       "iiurlwidth":"1150","titles":"File:"+book}
    return API+"?"+urllib.parse.urlencode(params)
def check():
    x=book_title(8,1839)
    y=book_title(184,1927)
    assert "tome 008, 1839.djvu" in x and "tome 184, 1927.djvu" in y
    fixture=("<div class='prp-index-pagelist'>"
      "<a class='prp-index-pagelist-page new' href='/w/index.php?title=Page:Comptes_rendus_hebdomadaires_des_s%C3%A9ances_de_l%E2%80%99Acad%C3%A9mie_des_sciences,_tome_008,_1839.djvu/879&amp;action=edit&amp;redlink=1'>873</a>"
      "<a class='prp-index-pagelist-page new' href='/w/index.php?title=Page:Comptes_rendus_hebdomadaires_des_s%C3%A9ances_de_l%E2%80%99Acad%C3%A9mie_des_sciences,_tome_008,_1839.djvu/925&amp;action=edit&amp;redlink=1'>919</a>"
      "</div>").encode()
    mapping=frames_from_book(fixture,x,{873,919})
    assert mapping[873][0]["frame"]==879 and mapping[919][0]["frame"]==925
    assert len(ITEMS)==3 and ITEMS[0]["stage"]!=ITEMS[1]["stage"]
    print("PASS: indexed original printed page-to-DjVu frame, historical stage separation and bounded source targets")
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--fixture-check",action="store_true")
    p.add_argument("--download",action="store_true",help="Fetch up to 3 public-domain image previews for visual QA")
    p.add_argument("--delay",type=float,default=1.5)
    p.add_argument("--timeout",type=int,default=22)
    p.add_argument("--out",type=Path,default=OUT)
    p.add_argument("--images",type=Path,default=IMAGE_OUT)
    a=p.parse_args()
    if a.fixture_check:return check()
    if a.delay<1.2:raise ValueError("Source rate cap >=1.2 seconds")
    results=[]
    last_request=None
    group={}
    def cool():
        nonlocal last_request
        if last_request is not None:time.sleep(max(0,a.delay-(time.monotonic()-last_request)))
        last_request=time.monotonic()
    for item in ITEMS:
        v,y,printed=item["volume"],item["year"],item["printed_page"]
        base={"volume":v,"year":y,"original_printed_page_candidate":printed,
              "person_name_candidate":item["name"],"stage":item["stage"],
              "candidate_role":item["member_role_candidate"],
              "original_image_visually_reviewed":False,
              "original_legal_approval_decree_signed_date_known":False,
              "member_study_accepted":False,"DOB_study_accepted":False,
              "bazi_variables_computed":False}
        book=book_title(v,y)
        if v not in group:
            cool()
            try:
                raw,code,mime=request(book_url(v,y),2000000,a.timeout,"text/html")
                if code!=200:raise ValueError("Book HTTP status non200")
                wanted={x["printed_page"] for x in ITEMS if x["volume"]==v}
                group[v]={"url":book_url(v,y),"book_sha256":sha(raw),
                          "explicit_page_links":frames_from_book(raw,book,wanted)}
            except (urllib.error.HTTPError,urllib.error.URLError,TimeoutError,ValueError) as ex:
                group[v]={"fetch_error":type(ex).__name__,
                          "status_code":getattr(ex,"code",None),"explicit_page_links":{}}
        bookinfo=group[v]
        base["wikisource_book_index_url"]=book_url(v,y)
        base["book_html_sha256"]=bookinfo.get("book_sha256","")
        matches=bookinfo["explicit_page_links"].get(printed,[])
        base["source_page_mapping"]=matches
        if len(matches)!=1:
            base["status"]="UNRESOLVED_PRINT_PAGE_MAPPING_NOT_HISTORICAL_ABSENCE"
            results.append(base);continue
        frame=matches[0]["frame"]
        base["djvu_frame"]=frame
        cool()
        try:
            raw,code,mime=request(preview_query(book,frame),800000,a.timeout)
            if code!=200:raise ValueError("Commons non200 metadata")
            image=get_metadata(raw,frame)
            base["commons_imageinfo_sha256"]=sha(raw)
            base["commons_original_journal_djvu_url"]=image["djvu_source_url"]
            base["original_book_page_count"]=image["page_count"]
            base["public_thumbnail_URL"]=image["thumbnail_url"]
            base["status"]="IMAGE_URL_READY_FOR_VISUAL_REVIEW"
            if a.download:
                cool()
                jpg,code,ctype=request(image["thumbnail_url"],2900000,a.timeout,"image/jpeg,image/*")
                if code!=200 or not jpg.startswith(b"\xff\xd8") or not ctype.startswith("image/"):
                    raise ValueError("Original thumbnail MIME or JPEG bytes invalid")
                a.images.mkdir(parents=True,exist_ok=True)
                fname=f"tome{v:03d}_{y}_printed{printed}_frame{frame}.jpg"
                (a.images/fname).write_bytes(jpg)
                base.update({"local_image_filename":fname,"source_preview_sha256":sha(jpg),
                    "source_preview_bytes":len(jpg),"source_preview_mime":ctype,
                    "status":"ORIGINAL_PREVIEW_DOWNLOADED_AWAITING_DIRECT_VISUAL_REVIEW"})
        except (urllib.error.HTTPError,urllib.error.URLError,TimeoutError,ValueError) as ex:
            base["status"]="COMMONS_IMAGE_PREVIEW_ERROR_"+type(ex).__name__
            base["HTTP_error_code"]=getattr(ex,"code",None)
        results.append(base)
    summary={"version":VERSION,"provenance":"Original Commons DjVu images for original Academy 1839/1927 half-year journal volumes",
       "source_records":results,"source_person_event_pairs":len(results),
       "preview_images_fetched":sum(bool(x.get("local_image_filename")) for x in results),
       "original_scanned_pages_visually_interpreted_by_script":0,
       "historical_government_decree_original_signed_document_checked":0,
       "frozen_full_member_study_additions":0,"frozen_DOB_additions":0,
       "bazi_variables_computed":0}
    a.out.mkdir(parents=True,exist_ok=True)
    (a.out/"three_archival_original_scan_source_leads_v1.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    print("ORIGINAL_PAGE_FETCH",json.dumps([{"year":x["year"],"person":x["person_name_candidate"],
       "printed":x["original_printed_page_candidate"],"frame":x.get("djvu_frame"),
       "status":x["status"],"preview_bytes":x.get("source_preview_bytes")} for x in results],ensure_ascii=False))
if __name__=="__main__":main()
