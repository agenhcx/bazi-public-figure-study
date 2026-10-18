#!/usr/bin/env python3
"""1856 Tome 43 Hermite election/decree: resolve printed page to DjVu page.

Only inspect public facsimile INDEX/HTML/thumbnail *metadata*. Unlike a human
looking at original scans, requesting Page HTML is not an actual original scan
read. In absence of a viewable original image, original_image_visually_checked=0.
No final elected-member admission, legal date adjudication or BaZi.
"""
from __future__ import annotations
import argparse,hashlib,json,re,time
import urllib.parse,urllib.request,urllib.error
from pathlib import Path
from bs4 import BeautifulSoup

VERSION="france-academy-1856-hermite-facsimile-location-probe-v1_1"
BOOK="Comptes rendus hebdomadaires des séances de l’Académie des sciences, tome 043, 1856.djvu"
ROOT="https://fr.wikisource.org/wiki/"
TARGETS=[
    {"original_printed_page":85,"kind":"HERMITE_ACADEMY_NOMINATION"},
    {"original_printed_page":169,"kind":"HERMITE_IMPERIAL_DECREE_CONFIRMATION"},
]
OUT=Path("data/france_academy_1856_original_image_page_locator_v1")
UA="bazi-public-figure-study/1.0 (bounded public archival facsimile URL locator)"
def book_url():
    return ROOT+urllib.parse.quote("Livre:"+BOOK.replace(" ","_"),safe=":/")
def wiki_url(title):
    return ROOT+urllib.parse.quote(title.replace(" ","_"),safe=":/")
def source(url,timeout):
    request=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"text/html"})
    with urllib.request.urlopen(request,timeout=timeout) as r:
        data=r.read(1_900_001)
        if len(data)>1_900_000:raise RuntimeError("Oversized individual page, abort")
        return r.status,data,r.geturl(),r.headers.get("Content-Type","")
def map_index_html(raw):
    """Extract explicit <a> link labels in the book's proofread pagelist.

    A printed-page number is not generally the same as DjVu frame number.
    Do not invent the frame from a historical-year-specific offset.
    """
    soup=BeautifulSoup(raw,"html.parser")
    pairs={}
    for a in soup.find_all("a",href=True):
        label=" ".join(a.get_text(" ",strip=True).split())
        if label not in {"85","169"}:continue
        href=urllib.parse.urljoin(ROOT,a["href"])
        unquoted=urllib.parse.unquote(href)
        m=re.search(r"/wiki/Page:(.*\.djvu)/(\d+)(?:[#?].*)?$",unquoted,re.I)
        if not m:continue
        if "tome_043" not in m.group(1).replace(",","_"):continue
        pairs.setdefault(int(label),set()).add((int(m.group(2)),href))
    return {k:[{"djvu_frame_number":page,"public_page_url":url} for page,url in sorted(v)]
            for k,v in pairs.items()}
def page_link_diagnostics(raw):
    soup=BeautifulSoup(raw,"html.parser")
    answer={}
    for target in ("85","169"):
        matches=[]
        for elem in soup.find_all(["a","span","b"]):
            if elem.get_text(" ",strip=True)!=target:continue
            if elem.find(["a","span","b"]) is not None:continue
            matches.append({"tag":elem.name,
                "href":str(elem.get("href",""))[:200],
                "title":str(elem.get("title",""))[:160],
                "class":" ".join(elem.get("class",[]))[:130],
                "parent_tag":elem.parent.name if elem.parent else "",
                "parent_html":str(elem.parent)[:260] if elem.parent else ""})
            if len(matches)>=6:break
        answer[target]=matches
    return answer

def scan_page_metadata(raw):
    soup=BeautifulSoup(raw,"html.parser")
    page_title=(soup.title.get_text(" ",strip=True) if soup.title else "")[:190]
    content=soup.select_one(".prp-page-content") or soup.select_one(".mw-parser-output")
    human_text=" ".join(content.get_text(" ",strip=True).split()) if content else ""
    img=soup.select_one(".prp-page-image img") or soup.select_one("img.mw-file-element")
    img_url=urllib.parse.urljoin(ROOT,img.get("src","")) if img and img.get("src") else ""
    return {"page_title":page_title,
       "page_has_transcribed_hermite_word":bool(re.search("hermite",human_text,re.I)),
       "page_has_transcribed_decree_word":bool(re.search("décret|decret",human_text,re.I)),
       "page_html_content_excerpt":human_text[:260],
       "public_facsimile_image_url_if_any":img_url,
       "actual_facsimile_image_opened_or_visually_inspected":False}
def fake():
    b=b'<html><a href="/wiki/Page:Comptes_rendus_hebdomadaires_des_s\xc3\xa9ances_de_l\xe2\x80\x99Acad\xc3\xa9mie_des_sciences,_tome_043,_1856.djvu/94">85</a><a href="/wiki/Page:Comptes_rendus_hebdomadaires_des_s\xc3\xa9ances_de_l\xe2\x80\x99Acad\xc3\xa9mie_des_sciences,_tome_043,_1856.djvu/178">169</a><a href="/wiki/Page:Another_volume.djvu/85">85</a></html>'
    m=map_index_html(b)
    assert m[85][0]["djvu_frame_number"]==94 and m[169][0]["djvu_frame_number"]==178
    assert len(m[85])==1
    q=scan_page_metadata(b'<html><title>Page</title><div class="prp-page-content">Hermite D\xc3\xa9cret</div></html>')
    assert q["page_has_transcribed_hermite_word"] and q["page_has_transcribed_decree_word"]
    assert not q["actual_facsimile_image_opened_or_visually_inspected"]
    print("PASS: actual Wikisource book pagelist linked to frame index; no guessed print-number offset")
def main():
    a=argparse.ArgumentParser()
    a.add_argument("--fixture-check",action="store_true")
    a.add_argument("--timeout",type=float,default=15)
    a.add_argument("--delay",type=float,default=1.3)
    a.add_argument("--out",type=Path,default=OUT)
    args=a.parse_args()
    if args.fixture_check:return fake()
    if args.delay<1.1:raise ValueError("Public rate limit min 1.1s")
    url=book_url()
    audits=[]
    book_hash=""
    try:
        status,raw,final,mime=source(url,args.timeout)
        if status!=200:raise ValueError("Book page HTTP not 200")
        book_hash=hashlib.sha256(raw).hexdigest()
        mapping=map_index_html(raw)
        link_diagnostics=page_link_diagnostics(raw)
        for i,t in enumerate(TARGETS):
            found=mapping.get(t["original_printed_page"],[])
            record={**t,"public_book_index":url,"book_html_sha256":book_hash,
                 "explicit_pagelist_mapping_candidates":found,
                 "book_page_label_HTML_diagnostics":link_diagnostics.get(str(t["original_printed_page"]),[]),
                 "pagelist_mapping_unique":len(found)==1,
                 "source_index_not_a_direct_page_image":True,
                 "original_event_scan_visually_verified":False,
                 "government_approval_original_document_verified":False,
                 "government_approval_date_adjudicated":False,
                 "study_full_member_accepted":False,"exact_DOB_accepted":False,
                 "bazi_variables_computed":False}
            if len(found)!=1:
                record["fetch_status"]="PAGE_MAPPING_UNRESOLVED_NOT_A_NEGATIVE_ELECTION"
                audits.append(record);continue
            if i:time.sleep(args.delay)
            page_url=found[0]["public_page_url"]
            try:
                pstatus,praw,purl,pmime=source(page_url,args.timeout)
                record.update({"fetch_status":"HTTP_"+str(pstatus),"actual_page_html_sha256":hashlib.sha256(praw).hexdigest(),
                               "page_final_url":purl,**scan_page_metadata(praw)})
            except (urllib.error.HTTPError,urllib.error.URLError,TimeoutError,ValueError) as e:
                record["fetch_status"]=("HTTP_"+str(e.code) if isinstance(e,urllib.error.HTTPError)
                                        else type(e).__name__)
                record["page_fetch_failure_is_not_missing_original_page"]=True
            audits.append(record)
    except (urllib.error.HTTPError,urllib.error.URLError,TimeoutError,ValueError) as e:
        audits=[{"fetch_status":("HTTP_"+str(e.code) if isinstance(e,urllib.error.HTTPError) else type(e).__name__),
                 "book_url":url,"book_source_could_not_be_accessed":True,
                 "printed_pages_not_equated_to_scan_frames":True}]
    result={"version":VERSION,"method":"Public Book index to Page namespace mapping with optional page HTML probe",
            "book_url":url,"book_html_sha256":book_hash,"records":audits,
            "original_scanned_pages_directly_visually_inspected":0,
            "legal_approval_documents_inspected":0,
            "accepted_french_full_memberships":0,"accepted_birthdays":0,"bazi_variables_computed":0}
    args.out.mkdir(parents=True,exist_ok=True)
    (args.out/"1856_hermite_nomination_and_imperial_decree_scan_locator_v1.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("FACSIMILE_LOCATORS",json.dumps({"records":[{"printed":r.get("original_printed_page"),
         "index_mapping":r.get("explicit_pagelist_mapping_candidates"),
         "status":r.get("fetch_status"),
         "text_has_hermite":r.get("page_has_transcribed_hermite_word"),
         "image_url_available":bool(r.get("public_facsimile_image_url_if_any"))} for r in audits]},ensure_ascii=False))
if __name__=="__main__":main()
