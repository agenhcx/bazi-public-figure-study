#!/usr/bin/env python3
"""Local-first first-party French Academy election PDF source audit (2019-2023).

--fixture-check validates the 58-person, four-document hand-read reference OFFLINE.
--fetch --limit 2 --resume fetches a bounded number of allowlisted public PDFs and
writes each successful source atomically with SHA256 and metadata.
--offline --limit 4 replays saved snapshots WITHOUT network requests.

Original first-party election announcement is not the later president's decree.
Source DOB fields remain intentionally EMPTY. No BaZi or cohort unblinding.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import re
import sys
import time
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlparse

BASE=Path("data/france_academy_elections_2019_2023_pilot_v2")
SOURCES=BASE/"source_inventory_v2.csv"
GOLD=BASE/"golden_58_official_member_names_v2.csv"
DEFAULT_OUT=Path("local_runs/france_academy_elections_2019_2023_v2")
ORDER=("FR2019","FR2020","FR2022","FR2023")
EXPECTED={"FR2019":18,"FR2020":4,"FR2022":18,"FR2023":18}
EXPECTED_PAGES={"FR2019":3,"FR2020":2,"FR2022":3,"FR2023":3}
ALLOWED={"www.academie-sciences.fr","academie-sciences.fr"}
UA="bazi-public-figure-study/1.0 (noncommercial historical Academy elections study; github.com/agenhcx/bazi-public-figure-study)"
MAX_PDF_BYTES=15_000_000
VERSION="france-academy-election-2019-2023-pdf-source-pilot-v2"


def read_csv(path:Path)->list[dict]:
    with path.open(encoding="utf-8-sig",newline="") as f:
        return list(csv.DictReader(f))


def save_csv(path:Path,rows:list[dict],fields:list[str])->None:
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("w",encoding="utf-8-sig",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def sha(raw:bytes)->str:
    return hashlib.sha256(raw).hexdigest()


def normalize(s:str)->str:
    s=unicodedata.normalize("NFKD",(s or "").casefold())
    s="".join(x for x in s if not unicodedata.combining(x))
    s=s.replace("œ","oe").replace("æ","ae").replace("ø","o").replace("\u0002"," ")
    return " ".join(re.findall(r"[a-z0-9]+",s))


def sha_path(p:Path)->str:
    h=hashlib.sha256()
    with p.open("rb") as f:
        for block in iter(lambda:f.read(1024*1024),b""):
            h.update(block)
    return h.hexdigest()


def fixture(sources:list[dict],people:list[dict])->dict:
    if len(sources)!=5 or len(people)!=58:
        raise RuntimeError("Expected exactly 4 regular PDF sources + 2021 foreign negative control, 58 people")
    source_by_id={s["source_document_id"]:s for s in sources}
    if set(source_by_id)!=set(ORDER)|{"NEG2021FOREIGN"}:
        raise RuntimeError("Source inventory drift")
    if len(source_by_id)!=len(sources):
        raise RuntimeError("Duplicate source IDs")
    ctr=Counter()
    identity=set()
    for source in sources:
        docid=source["source_document_id"]
        if docid=="NEG2021FOREIGN":
            if source["source_member_class"]!="foreign_associates_only_EXCLUDE":
                raise RuntimeError("Negative control was promoted")
            continue
        if source["source_member_class"]!="regular_members_elected" or source["dob_field_capability"]!="NO_DOB_PRINTED":
            raise RuntimeError("Unexpected member type or DOB capability: "+docid)
        if int(source["expected_pdf_pages"])!=EXPECTED_PAGES[docid] or int(source["expected_persons"])!=EXPECTED[docid]:
            raise RuntimeError("Source expected page/person count changed: "+docid)
        url=source["first_party_source_url"]
        if urlparse(url).scheme!="https" or urlparse(url).hostname not in ALLOWED:
            raise RuntimeError("Source outside original Academy PDF host allowlist: "+url)
        if not urlparse(url).path.endswith(".pdf"):
            raise RuntimeError("Regular source must be a PDF")
    for r in people:
        docid=r["source_document_id"]
        if docid not in ORDER:
            raise RuntimeError("Foreign or unknown source in elected-member gold roster")
        src=source_by_id[docid]
        if r["election_year"]!=src["election_year"] or r["announcement_date"]!=src["announcement_date"]:
            raise RuntimeError("Publication/election year mismatch")
        if r["birth_year_from_this_source"] or r["exact_DOB_from_this_source"]:
            raise RuntimeError("The selected four notices did not give person DOBs; must stay blank")
        if r["DOB_precision_in_source"]!="absent_in_election_pdf":
            raise RuntimeError("Inferred day precision from no-DOB PDF")
        if (r["study_cohort_member_frozen"]!="0" or r["DOB_accepted"]!="0" or
            r["bazi_variables_computed"]!="0" or r["election_exact_day_independently_confirmed"]!="0"):
            raise RuntimeError("Premature study acceptance or exact election day")
        ix=int(r["pdf_page_zero_based"])
        if not 0<=ix<EXPECTED_PAGES[docid]:
            raise RuntimeError("PDF page out of bounds")
        key=(normalize(r["person_name_printed_visual_review"]),docid)
        if not key[0] or key in identity:
            raise RuntimeError("Empty/duplicate person name in original PDF gold")
        identity.add(key)
        ctr[docid]+=1
    if dict(ctr)!=EXPECTED:
        raise RuntimeError("Golden roster size mismatch: "+str(dict(ctr)))
    return {
        "golden_persons":len(people),
        "golden_by_document":dict(ctr),
        "first_party_source_documents":len(ORDER),
        "foreign_associate_control_excluded":True,
        "DOB_from_this_official_notice_all_absent":True,
        "first_party_election_announcement_year_only":True,
        "network_requests":0,
        "bazi_variables_computed":0,
    }


def get_pdf(session,url:str,timeout:float,delay:float,retries:int)->tuple[bytes,str,int]:
    import requests
    errors=[]
    for attempt in range(1,retries+1):
        try:
            time.sleep(delay)
            resp=session.get(url,timeout=timeout,allow_redirects=True)
            host=urlparse(resp.url).hostname
            if host not in ALLOWED:
                raise RuntimeError("Redirected outside approved official Academy domain")
            resp.raise_for_status()
            raw=resp.content
            if not (raw.startswith(b"%PDF-") and 1200<len(raw)<MAX_PDF_BYTES):
                raise RuntimeError("Unexpected download format/size")
            return raw,resp.url,attempt
        except (requests.RequestException,RuntimeError) as err:
            errors.append(f"{type(err).__name__}: {str(err)[:160]}")
            if attempt<retries:time.sleep(min(2**attempt,5))
    raise RuntimeError(" ; ".join(errors))


def read_pdf(raw:bytes)->tuple[list[str],dict]:
    try:import fitz
    except ImportError as exc:
        raise RuntimeError("PDF reading requires PyMuPDF; pip install requests pymupdf") from exc
    d=fitz.open(stream=raw,filetype="pdf")
    if d.needs_pass or len(d)>20 or len(d)<1:
        raise RuntimeError("Unexpected PDF page count/encryption")
    pages=[p.get_text("text",sort=True).replace("\u00ad","") for p in d]
    return pages,{"pages":len(pages),"text_characters":sum(len(x) for x in pages)}


def text_audit(d:dict,pages:list[str])->None:
    docid=d["source_document_id"]
    alltext=normalize(" ".join(pages))
    year=d["election_year"]
    # First-party source class is proved by title/body, not just filename.
    if "nouveaux membres" not in alltext or "academie des sciences" not in alltext:
        raise RuntimeError("Missing official *new regular member* title")
    if year not in alltext:
        raise RuntimeError("Official announcement source year not present")
    if "elus" not in alltext:
        raise RuntimeError("Official election word not found")
    # Some PDFs mention the future decree but not the finalized ratification:
    # preserve current status as first-party election announcement only.


def match_person(docid:str,person:dict,pages:list[str])->dict:
    page=int(person["pdf_page_zero_based"])
    content=normalize(pages[page])
    sought=normalize(person["person_name_printed_visual_review"])
    exact=bool(re.search(r"(?<![a-z0-9])"+re.escape(sought)+r"(?![a-z0-9])",content))
    return {
        "source_document_id":docid,
        "person":person["person_name_printed_visual_review"],
        "election_year":person["election_year"],
        "announcement_date":person["announcement_date"],
        "election_exact_day_verified":0,
        "science_section_in_source":person["science_section_in_source"],
        "source_page_zero_based":page,
        "match_status":"NAME_ON_SOURCE_PAGE" if exact else "PAGE_TEXT_MISMATCH_REVIEW",
        "name_matched":int(exact),
        "source_DOB_precision":"absent_in_election_pdf",
        "source_DOB_claim":"",
        "source_document_verified_as_election":1,
        "presidential_decree_independently_verified":0,
        "final_cohort_accepted":0,
        "bazi_variables_computed":0,
    }


def run(mode:str,sources:list[dict],people:list[dict],out:Path,limit:int,
        delay:float,timeout:float,retries:int,resume:bool)->dict:
    out.mkdir(parents=True,exist_ok=True)
    cache=out/"cache";cache.mkdir(exist_ok=True)
    session=None
    if mode=="fetch":
        try:import requests
        except ImportError as exc:raise RuntimeError("pip install requests pymupdf") from exc
        session=requests.Session()
        session.headers.update({"User-Agent":UA,"Accept-Language":"fr-FR,fr;q=0.9"})
    persons_by_doc=defaultdict(list)
    for p in people:persons_by_doc[p["source_document_id"]].append(p)
    source_rows=[]
    outrows=[]
    for source in sources:
        docid=source["source_document_id"]
        if docid=="NEG2021FOREIGN":
            source_rows.append({"document_id":docid,"fetch_status":"SKIPPED_FOREIGN_MEMBER_CONTROL",
                                "url":source["first_party_source_url"],"source_sha256":"",
                                "pdf_pages":"","persons_verified":0,"persons_unmatched":0,"error":""})
            continue
        if docid not in ORDER[:limit]:
            continue
        url=source["first_party_source_url"]
        filepath=cache/(docid+".pdf")
        metadata=cache/(docid+".json")
        try:
            if filepath.is_file() and (resume or mode=="offline"):
                if not metadata.exists():
                    raise RuntimeError("Cached PDF missing source provenance metadata")
                info=json.loads(metadata.read_text(encoding="utf-8"))
                raw=filepath.read_bytes()
                h=sha(raw)
                if info.get("source_url")!=url or info.get("sha256")!=h:
                    raise RuntimeError("Cached source URL or PDF hash mismatch; quarantined")
                status="CACHE_REPLAY_VERIFIED"
            elif mode=="offline":
                raise RuntimeError("No cached official PDF for offline replay: "+docid)
            else:
                raw,final_url,attempts=get_pdf(session,url,timeout,delay,retries)
                h=sha(raw)
                # Atomic: cache the pair only after a successful complete PDF
                # fetch. The cached URL/hash audit is checked on every replay.
                tmp=filepath.with_suffix(".pdf.tmp")
                tmp.write_bytes(raw)
                os.replace(tmp,filepath)
                info={
                    "document_id":docid,"source_url":url,"resolved_source_url":final_url,
                    "sha256":h,"retrieved_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
                    "attempts":attempts,
                }
                metatmp=metadata.with_suffix(".json.tmp")
                metatmp.write_text(json.dumps(info,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
                os.replace(metatmp,metadata)
                status="FETCHED_AND_CACHED"
            if not raw.startswith(b"%PDF-"):
                raise RuntimeError("Source cache is not PDF")
            pages,stat=read_pdf(raw)
            if stat["pages"]!=int(source["expected_pdf_pages"]):
                raise RuntimeError(f"PDF page-count mismatch; {stat['pages']} vs {source['expected_pdf_pages']}")
            text_audit(source,pages)
            results=[match_person(docid,p,pages) for p in persons_by_doc[docid]]
            for r in results:
                r["source_url"]=url
                r["source_sha256"]=h
            outrows.extend(results)
            ok=sum(x["name_matched"] for x in results)
            source_rows.append({
                "document_id":docid,"fetch_status":status,"url":url,"source_sha256":h,
                "pdf_pages":len(pages),"persons_verified":ok,
                "persons_unmatched":len(results)-ok,"error":""})
            print(f"{docid} {status} pages={len(pages)} names={ok}/{len(results)}",flush=True)
        except Exception as exc:
            source_rows.append({
                "document_id":docid,"fetch_status":"SOURCE_ERROR_REQUIRES_REVIEW",
                "url":url,"source_sha256":"","pdf_pages":"",
                "persons_verified":0,"persons_unmatched":len(persons_by_doc[docid]),
                "error":f"{type(exc).__name__}: {str(exc)[:350]}"})
            print(f"{docid} ERROR {type(exc).__name__} {str(exc)[:160]}",flush=True)
    save_csv(out/"source_fetch_audit_v2.csv",source_rows,
        ["document_id","fetch_status","url","source_sha256","pdf_pages",
         "persons_verified","persons_unmatched","error"])
    save_csv(out/"candidate_official_member_election_v2.csv",outrows,
        ["source_document_id","person","election_year","announcement_date",
         "election_exact_day_verified","science_section_in_source","source_page_zero_based",
         "match_status","name_matched","source_DOB_precision","source_DOB_claim",
         "source_document_verified_as_election","presidential_decree_independently_verified",
         "final_cohort_accepted","bazi_variables_computed","source_url","source_sha256"])
    unmatched=[x for x in outrows if not x["name_matched"]]
    save_csv(out/"unmatched_names_v2.csv",unmatched,
        ["source_document_id","person","source_page_zero_based","match_status","source_url","source_sha256"])
    errors=Counter(x["fetch_status"] for x in source_rows)
    report={
        "version":VERSION,"mode":mode,
        "timestamp_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
        "regular_pdf_documents_selected":limit,
        "regular_pdf_documents_verified":sum(x["fetch_status"] in ("FETCHED_AND_CACHED","CACHE_REPLAY_VERIFIED") for x in source_rows),
        "all_source_states":dict(errors),
        "person_name_records_checked":len(outrows),
        "person_names_verified_from_firstparty":sum(x["name_matched"] for x in outrows),
        "person_names_unmatched":len(unmatched),
        "source_PDF_birthdays_found":0,
        "first_party_elected_member_candidate_rows":sum(x["name_matched"] for x in outrows),
        "foreign_2021_associate_negative_control_excluded":True,
        "global_roster_finalized":False,
        "independent_DOB_accepted":0,
        "bazi_variables_computed":0,
        "warning":"Election notices establish names/sections and election year, not exact DOB or government-ratified full membership. No primary birth-year filtering yet.",
    }
    (out/"summary.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)
    return report


def main()->int:
    ap=argparse.ArgumentParser()
    mode=ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--fixture-check",action="store_true")
    mode.add_argument("--fetch",action="store_true")
    mode.add_argument("--offline",action="store_true")
    ap.add_argument("--limit",type=int,default=2,help="Number of regular Academy PDFs to audit (1-4)")
    ap.add_argument("--resume",action="store_true",help="Reuse successful cached PDF+hash; retry missing/error only")
    ap.add_argument("--out",type=Path,default=DEFAULT_OUT)
    ap.add_argument("--delay",type=float,default=1.3)
    ap.add_argument("--timeout",type=float,default=25)
    ap.add_argument("--retries",type=int,default=2)
    args=ap.parse_args()
    if not 1<=args.limit<=4 or args.delay<0.8 or args.timeout<4 or not 1<=args.retries<=3:
        raise RuntimeError("Invalid bounded pilot parameters")
    inventory=read_csv(SOURCES)
    people=read_csv(GOLD)
    fixture_report=fixture(inventory,people)
    if args.fixture_check:
        print(json.dumps({"script":VERSION,"mode":"fixture-check",**fixture_report},indent=2,ensure_ascii=False))
        return 0
    result=run("fetch" if args.fetch else "offline",inventory,people,args.out,
               args.limit,args.delay,args.timeout,args.retries,args.resume)
    if result["regular_pdf_documents_verified"]!=args.limit or result["person_names_unmatched"]:
        return 2
    return 0


if __name__=="__main__":
    sys.exit(main())
