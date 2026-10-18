#!/usr/bin/env python3
"""Bounded public Commons preview downloader for original 1856 Academy scans.

Recover printed-page->DjVu-frame mapping strictly from Wikisource Book pagelist.
Temporary JPEG preview files for HUMAN visual review; source metadata only
saved to repository. Never infer legal approval dates or accept new members.
"""
from __future__ import annotations
import argparse,hashlib,json,re,time,urllib.parse,urllib.request,urllib.error
from pathlib import Path
from bs4 import BeautifulSoup
from france_academy_1856_scan_locator_v1 import BOOK,book_url

VERSION="france-1856-commons-two-original-facsimiles-v1_1"
API="https://commons.wikimedia.org/w/api.php"
OUT=Path("data/france_academy_1856_commons_original_page_map_v1")
CACHE=Path("local_runs/france_1856_hermite_scan_preview_v1")
TARGET={85:"HERMITE_ACADEMY_NOMINATION",169:"HERMITE_IMPERIAL_CONFIRMATION"}
NEIGHBORS={83:"ORIGINAL_ADJACENT_PRINTED_83",84:"ORIGINAL_ADJACENT_PRINTED_84"}
UA="bazi-public-figure-study/1.0 (1856 public-domain archival verification)"
def request(url,maxlen,timeout,accept="application/json"):
    req=urllib.request.Request(url,headers={"Accept":accept,"User-Agent":UA})
    with urllib.request.urlopen(req,timeout=timeout) as r:
        data=r.read(maxlen+1)
        if len(data)>maxlen:raise ValueError("Oversized public source refused")
        return data,r.status,r.headers.get("Content-Type","")
def sha(raw):return hashlib.sha256(raw).hexdigest()
def original_pagelist(html,targets=TARGET):
    soup=BeautifulSoup(html,"html.parser"); out={}
    for a in soup.select("a.prp-index-pagelist-page[href]"):
        label=a.get_text(" ",strip=True)
        if not label.isdigit() or int(label) not in targets:continue
        parsed=urllib.parse.urlparse(urllib.parse.urljoin("https://fr.wikisource.org/",a["href"]))
        if parsed.path.endswith("/index.php"):
            title=urllib.parse.parse_qs(parsed.query).get("title",[""])[0]
        else:title=urllib.parse.unquote(parsed.path).split("/wiki/",1)[-1]
        if not title.startswith("Page:"+BOOK.replace(" ","_")+"/"):continue
        m=re.search(r"\.djvu/(\d+)$",title)
        if not m:continue
        out.setdefault(int(label),[]).append({
          "frame":int(m.group(1)),"pagelist_href":a["href"],
          "page_namespace_uncreated_redlink":"redlink=1" in parsed.query})
    return out
def metadata_query(frame):
    params={"action":"query","format":"json","formatversion":"2","prop":"imageinfo",
            "iiprop":"url|size|mime","iiurlwidth":"1050","iiurlparam":"page"+str(frame),
            "titles":"File:"+BOOK}
    return API+"?"+urllib.parse.urlencode(params)
def get_metadata(data,frame):
    j=json.loads(data)
    pages=(j.get("query") or {}).get("pages",[])
    if len(pages)!=1:raise ValueError("Unexpected Commons API envelope")
    imgs=pages[0].get("imageinfo",[])
    if len(imgs)!=1:raise ValueError("Commons source has no image info")
    im=imgs[0]
    if im.get("mime")!="image/vnd.djvu":raise ValueError("Not actual scanned DjVu")
    count=im.get("pagecount")
    if isinstance(count,int) and frame>count:
        raise ValueError("Requested frame outside document, would be clamped")
    u=im.get("thumburl","")
    if not u.startswith("https://") or not urllib.parse.urlparse(u).netloc.endswith("wikimedia.org"):
        raise ValueError("No trusted Wikimedia JPG preview URL")
    return {"frame":frame,"page_count":count,"thumbnail_url":u,"thumbnail_width":im.get("thumbwidth"),
            "thumbnail_height":im.get("thumbheight"),"djvu_source_url":im.get("url","")}
def fixture():
    b=('<div class="prp-index-pagelist">'
       '<a class="prp-index-pagelist-page new" href="/w/index.php?title=Page:Comptes_rendus_hebdomadaires_des_s%C3%A9ances_de_l%E2%80%99Acad%C3%A9mie_des_sciences,_tome_043,_1856.djvu/89&amp;action=edit&amp;redlink=1">85</a>'
       '<a class="prp-index-pagelist-page new" href="/w/index.php?title=Page:Comptes_rendus_hebdomadaires_des_s%C3%A9ances_de_l%E2%80%99Acad%C3%A9mie_des_sciences,_tome_043,_1856.djvu/173&amp;action=edit&amp;redlink=1">169</a></div>').encode()
    m=original_pagelist(b)
    assert len(m)==2 and m[85][0]["frame"]==89 and m[169][0]["frame"]==173,m
    fake={"query":{"pages":[{"imageinfo":[{"mime":"image/vnd.djvu","pagecount":1260,
      "thumburl":"https://upload.wikimedia.org/x.jpg","thumbwidth":1050,"thumbheight":1100}]}]}}
    assert get_metadata(json.dumps(fake).encode(),89)["page_count"]==1260
    try:get_metadata(json.dumps(fake).encode(),1261)
    except ValueError:pass
    else:raise AssertionError("No guard against preview page number clamping")
    print("PASS: explicit printed85->frame89 and printed169->frame173 from real-type pagelist redlinks")
def main():
    a=argparse.ArgumentParser()
    a.add_argument("--fixture-check",action="store_true")
    a.add_argument("--download",action="store_true")
    a.add_argument("--neighbors",action="store_true",help="Also retrieve printed p83,p84 to test nomination page85 index off-by-one")
    a.add_argument("--delay",type=float,default=1.5)
    a.add_argument("--timeout",type=int,default=20)
    a.add_argument("--out",type=Path,default=OUT)
    a.add_argument("--cache",type=Path,default=CACHE)
    args=a.parse_args()
    if args.fixture_check:return fixture()
    if args.delay<1.2:raise ValueError("Min delay 1.2 sec")
    book,code,mime=request(book_url(),1800000,args.timeout,"text/html")
    if code!=200:raise ValueError("Wikisource printed page mapping source not accessible")
    selected={**NEIGHBORS,**TARGET} if args.neighbors else TARGET
    maps=original_pagelist(book,selected); records=[];last=time.monotonic()
    for p,event in selected.items():
        candidates=maps.get(p,[])
        row={"printed_page":p,"event":event,"book_url":book_url(),
             "book_sha256":sha(book),"page_frame_links":candidates,
             "unique_page_frame_mapping":len(candidates)==1,
             "original_scan_visually_reviewed":False,"government_approval_legally_verified":False,
             "accepted_full_member":False,"accepted_birthdate":False,"bazi_variables_computed":False}
        if len(candidates)!=1:
            row["status"]="UNRESOLVED_OR_MULTIPLE_FRAMES";records.append(row);continue
        frame=candidates[0]["frame"]
        time.sleep(max(0,args.delay-(time.monotonic()-last)));last=time.monotonic()
        try:
            body,status,ctype=request(metadata_query(frame),500000,args.timeout)
            if status!=200:raise ValueError("Commons metadata status not 200")
            info=get_metadata(body,frame);row.update(info)
            row["source_imageinfo_sha256"]=sha(body)
            row["status"]="PUBLIC_IMAGE_LOCATED_NOT_VISUALLY_REVIEWED"
            if args.download:
                time.sleep(max(0,args.delay-(time.monotonic()-last)));last=time.monotonic()
                data,code,mime=request(info["thumbnail_url"],2300000,args.timeout,"image/jpeg,image/*")
                if code!=200 or not data.startswith(b"\xff\xd8") or not mime.startswith("image/"):
                    raise ValueError("Source is not a valid JPEG")
                args.cache.mkdir(parents=True,exist_ok=True)
                fname=f"tome043_print_{p}_djvu_frame_{frame}.jpg"
                (args.cache/fname).write_bytes(data)
                row.update({"source_preview_filename":fname,"source_preview_sha256":sha(data),
                  "preview_bytes":len(data),"preview_mime":mime,
                  "downloaded_preview_requires_human_review":True,
                  "status":"PREVIEW_SAVED_FOR_HUMAN_VISUAL_REVIEW"})
        except (urllib.error.HTTPError,urllib.error.URLError,TimeoutError,ValueError) as e:
            row["status"]="SOURCE_PREVIEW_ERROR_"+type(e).__name__
            row["error_code"]=getattr(e,"code",None)
        records.append(row)
    args.out.mkdir(parents=True,exist_ok=True)
    summary={"version":VERSION,"records":records,
        "book_printed_page_mapping_source_sha256":sha(book),
        "preview_files_downloaded":sum("source_preview_filename" in r for r in records),
        "source_images_visually_interpreted":0,"legal_government_approvals_adjudicated":0,
        "accepted_memberships":0,"accepted_DOB":0,"bazi_variables_computed":0}
    (args.out/"source_preview_metadata_v1.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("SOURCE_IMAGE_METADATA",json.dumps([{"printed":r["printed_page"],"frame":r.get("frame"),
        "status":r["status"],"bytes":r.get("preview_bytes")} for r in records],ensure_ascii=False))
if __name__=="__main__":main()
