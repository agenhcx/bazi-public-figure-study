#!/usr/bin/env python3
"""France Académie des sciences PDF election-notice discovery/verification.

Local-first candidate metadata pipeline:
  --fixture-check validates the 66-row hand-read official PDF golden reference.
  --fetch --limit 2 --resume attempts ONLY two whitelisted official/mirrored PDFs,
     keeping successful raw downloads in a stable local cache with SHA-256.
  --offline replays existing cached PDFs without new HTTP connections.

Never infer missing DOB days, promote foreign associates or use ceremony/approval
year as election year. This script produces candidate source metadata, not a
globally frozen research roster and no BaZi variables.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import re
import sys
import time
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlparse

BASE=Path("data/france_academy_official_election_pdf_pilot_v1")
INVENTORY=BASE/"source_document_inventory_v1.csv"
GOLD=BASE/"official_election_name_DOB_transcription_v1.csv"
OUT=Path("local_runs/france_academy_official_pdf_pilot_v1")
EXPECTED_COUNTS={"FR2011":21,"FR2013":17,"FR2014":10,"FR2017":18}
ORDER=list(EXPECTED_COUNTS)
USER_AGENT="bazi-public-figure-study/1.0 (noncommercial French Academy official election archive study; https://github.com/agenhcx/bazi-public-figure-study)"
WHITELIST_DOMAINS={"www.academie-sciences.fr","academie-sciences.fr",
                   "verimag.univ-grenoble-alpes.fr"}
MONTHS={m:i for i,m in enumerate(
    "janvier fevrier mars avril mai juin juillet aout septembre octobre novembre decembre".split(),1)}
MONTH_RE="|".join(MONTHS)
BIRTH_REG=r"(?P<raw>n[ée]e?\s+(?:le\s+)?(?P<day>1(?:er|e)?|[2-9]|[12]\d|3[01])\s+(?P<month>"+MONTH_RE+r")\s*(?P<year>1[89]\d{2}|20\d{2}))"
YEAR_REG=r"n[ée]e?\s+en\s+(?P<year>1[89]\d{2}|20\d{2})"

def read_csv(path:Path)->list[dict[str,str]]:
    with path.open("r",encoding="utf-8-sig",newline="") as f:
        return list(csv.DictReader(f))

def write_csv(path:Path,rows:list[dict],cols:list[str])->None:
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=cols,extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

def sha(raw:bytes)->str:
    return hashlib.sha256(raw).hexdigest()

def normalize(s:str)->str:
    s=unicodedata.normalize("NFKD",(s or "").casefold())
    s="".join(ch for ch in s if not unicodedata.combining(ch))
    return " ".join(re.findall(r"[a-z0-9]+",s))

def fold_text(s:str)->str:
    s=unicodedata.normalize("NFKD",s.casefold())
    return "".join(ch for ch in s if not unicodedata.combining(ch))

def count_assertions(gold:list[dict],sources:list[dict])->dict:
    counts=Counter(x["source_document_id"] for x in gold)
    if dict(counts)!=EXPECTED_COUNTS:
        raise RuntimeError(f"Golden per-document counts changed: {dict(counts)}")
    if len(gold)!=66:raise RuntimeError("Expected 66 hand-transcribed official electees")
    if len({(r["election_date_from_first_party"],normalize(r["person_name_transcribed"])) for r in gold})!=66:
        raise RuntimeError("Duplicated election year/name in golden fixture")
    if {r["document_id"] for r in sources}!=set(ORDER)|{"NEG2022AE"}:
        raise RuntimeError("Inventoried document types have changed without version bump")
    src={r["document_id"]:r for r in sources}
    for row in gold:
        d=src[row["source_document_id"]]
        if d["document_role_gate"]!="full_member_election":
            raise RuntimeError("Foreign associate document in ordinary member candidate data")
        precise=row["birth_precision"]
        dob=row["birth_as_stated_candidate"]
        if precise.startswith("day_precision"):
            if len(dob)!=10:
                raise RuntimeError("Invalid day-precision DOB representation")
            dt.date.fromisoformat(dob)
        elif precise=="year_only":
            if not re.fullmatch(r"\d{4}",dob):
                raise RuntimeError("Only birth-year may appear in year-only source")
        elif precise=="absent_in_source":
            if dob:
                raise RuntimeError("Invented DOB on source with absent DOB")
        else:
            raise RuntimeError("Unapproved date precision: "+precise)
        if row["exact_DOB_entered_frozen_analysis"]!="0" or row["bazi_variables_computed"]!="0":
            raise RuntimeError("Analysis-unblinding invariant violated")
        if row["first_party_full_member_election_candidate"]!="1" or row["government_approval_independently_adjudicated"]!="0":
            raise RuntimeError("Manual transcription must not accept government-ratified status")
        if not row["election_date_from_first_party"].startswith(("2010-","2011-","2013-","2014-","2017-")):
            raise RuntimeError("Unexpected election date")
    expected={
        "FR2011":Counter({"day_precision_explicit":20,"day_precision_ordinal_1e_needs_review":1}),
        "FR2013":Counter({"absent_in_source":17}),
        "FR2014":Counter({"year_only":10}),
        "FR2017":Counter({"absent_in_source":18}),
    }
    actual={name:Counter(r["birth_precision"] for r in gold if r["source_document_id"]==name)
            for name in ORDER}
    if actual!=expected:
        raise RuntimeError(f"Precision distributions changed: {actual}")
    return {
        "fixture_people":len(gold),
        "fixture_counts":dict(counts),
        "fixture_precision_distribution":{k:dict(v) for k,v in actual.items()},
        "foreign_associate_negative_control":"excluded_from_primary",
    }

def read_pdf_text(raw:bytes)->tuple[list[str],dict]:
    try: import fitz
    except ImportError as exc:
        raise RuntimeError("PDF replay requires PyMuPDF. Install with python -m pip install pymupdf requests") from exc
    doc=fitz.open(stream=raw,filetype="pdf")
    if doc.needs_pass:raise RuntimeError("Unexpected encrypted source PDF")
    if len(doc)<1 or len(doc)>90:raise RuntimeError("Unexpected source PDF page count")
    pages=[]
    for page in doc:
        txt=page.get_text("text",sort=True)
        pages.append(txt.replace("\u00ad","").replace("\u00a0"," ").replace("\ufffd",""))
    return pages,{"pages":len(doc),"pdf_text_total_chars":sum(len(x) for x in pages)}

def extract_candidate(pages:list[str],r:dict)->dict:
    docid=r["source_document_id"]
    page=int(r["source_page_zero_index"])
    if not 0<=page<len(pages):
        return {"verification":"SOURCE_PAGE_OUT_OF_RANGE","page_index":page,"pdf_birth_raw":"",
                "pdf_birth_candidate":"","pdf_text_name_present":0}
    txt=pages[page]
    name=r["person_name_transcribed"]
    compact=" ".join(txt.replace("\u00ad","").split())
    search_text=fold_text(compact)
    # Fold accents on both names, because some official typeset PDFs remove
    # accents (Benoît / Benoit) but still require full name token matches.
    name_pattern=re.escape(fold_text(name)).replace(r"\ ",r"\s+")
    name_m=re.search(r"(?<!\w)"+name_pattern+r"(?!\w)",search_text,re.I)
    if not name_m:
        return {"verification":"NAME_NOT_FOUND_ON_EXPECTED_PAGE","page_index":page,"pdf_birth_raw":"",
                "pdf_birth_candidate":"","pdf_text_name_present":0}
    if docid in {"FR2013","FR2017"}:
        # These official sources are a name/discipline roster, not DOB evidence.
        return {"verification":"OFFICIAL_NAME_ONLY_CONFIRMED","page_index":page,"pdf_birth_raw":"",
                "pdf_birth_candidate":"","pdf_text_name_present":1}
    # Only scan <=80 characters immediately after the matched person's name.
    # This excludes a past/future president or unrelated biography DOB.
    span=search_text[name_m.end():name_m.end()+110]
    if docid=="FR2014":
        m=re.match(r"\s*,\s*"+YEAR_REG,span,re.I)
        if not m:
            return {"verification":"YEAR_ONLY_TEXT_NOT_FOUND","page_index":page,"pdf_birth_raw":"",
                    "pdf_birth_candidate":"","pdf_text_name_present":1}
        claim=m.group("year")
        return {"verification":"YEAR_ONLY_SOURCE_MATCH" if claim==r["birth_as_stated_candidate"]
                else "YEAR_ONLY_SOURCE_CONFLICT",
                "page_index":page,"pdf_birth_raw":m.group(0).strip(),
                "pdf_birth_candidate":claim,"pdf_text_name_present":1}
    if docid=="FR2011":
        m=re.match(r"\s*,\s*"+BIRTH_REG,normalize_months_for_regex(span),re.I)
        if not m:
            return {"verification":"EXACT_DATE_TEXT_NOT_FOUND","page_index":page,"pdf_birth_raw":"",
                    "pdf_birth_candidate":"","pdf_text_name_present":1}
        raw_date=m.group("raw")
        day_text=m.group("day")
        day=1 if re.fullmatch(r"1\s*(?:er|e|ᵉ)?",day_text) else int(day_text)
        month=MONTHS.get(normalize(m.group("month")))
        year=int(m.group("year"))
        try:
            claim=dt.date(year,month,day).isoformat() if month else ""
        except ValueError:
            claim=""
        quality="PDF_ORDINAL_1e_REQUIRES_REVIEW" if re.match(r"1e$",day_text) else "PDF_EXACT_DATE_CONFIRMED"
        if claim!=r["birth_as_stated_candidate"]:
            quality="PDF_EXACT_DATE_CONFLICT"
        return {"verification":quality,"page_index":page,"pdf_birth_raw":raw_date,
                "pdf_birth_candidate":claim,"pdf_text_name_present":1}
    raise RuntimeError("Unexpected document ID from approved source inventory")

def normalize_months_for_regex(s:str)->str:
    # Keep original French field labels for review; no machine translation or
    # guessed calendar-day defaults. Most original French accents don't affect
    # the 12 month spellings except février, août, décembre.
    for accented,unaccented in [("février","fevrier"),("août","aout"),("décembre","decembre")]:
        s=s.replace(accented,unaccented).replace(accented.title(),unaccented.title())
    return s

def request_pdf(session,url:str,timeout:float,delay:float,retries:int)->tuple[bytes,str]:
    import requests
    last=""
    for attempt in range(1,retries+1):
        try:
            time.sleep(delay)
            response=session.get(url,timeout=timeout,allow_redirects=True)
            final_host=urlparse(response.url).hostname
            if final_host not in WHITELIST_DOMAINS:
                raise RuntimeError("Redirect to unapproved domain: "+str(final_host))
            response.raise_for_status()
            data=response.content
            if not (data.startswith(b"%PDF-") and 1000<len(data)<15_000_000):
                raise RuntimeError(f"Not an expected PDF or over size limit: bytes={len(data)}")
            return data,response.url
        except (requests.RequestException,RuntimeError) as exc:
            last=f"{type(exc).__name__}: {str(exc)[:250]}"
            if attempt<retries:time.sleep(min(2**attempt,5))
    raise RuntimeError(last)

def audit(out:Path,records:list[dict],sources:list[dict],mode:str,limit:int,
          delay:float,timeout:float,retries:int,resume:bool)->dict:
    if mode=="fetch":
        try:import requests
        except ImportError as exc:raise RuntimeError("Install requests and PyMuPDF for PDF fetching") from exc
        session=requests.Session()
        session.headers.update({"User-Agent":USER_AGENT,"Accept-Language":"fr-FR,fr;q=0.9"})
    else:session=None
    out.mkdir(parents=True,exist_ok=True)
    cache=out/"cache";cache.mkdir(exist_ok=True)
    source_rows=[]
    extracted=[]
    rowmap=defaultdict(list)
    for r in records:rowmap[r["source_document_id"]].append(r)
    for d in sources:
        docid=d["document_id"]
        if docid=="NEG2022AE":
            source_rows.append({"document_id":docid,"status":"EXCLUDED_FOREIGN_ASSOCIATE_NEGATIVE_CONTROL",
                                "document_role_gate":d["document_role_gate"],"url":d["source_url"],
                                "source_sha256":"","source_pages":"","names_matched":0,
                                "source_DOB_claims_matched":0,"error":""})
            continue
        if docid not in ORDER[:limit]:continue
        uri=d["source_url"]
        if urlparse(uri).hostname not in WHITELIST_DOMAINS:
            raise RuntimeError("Unapproved source host in manifest")
        p=cache/(docid+".pdf")
        meta=cache/(docid+".json")
        try:
            if p.is_file() and (mode=="offline" or resume):
                raw=p.read_bytes();actualsha=sha(raw)
                if not meta.exists():
                    raise RuntimeError("Cached PDF lacks immutable metadata/URL audit")
                if not raw.startswith(b"%PDF-"):
                    raise RuntimeError("Cached file not a PDF")
                if meta.exists():
                    prior=json.loads(meta.read_text(encoding="utf-8"))
                    if prior["source_sha256"]!=actualsha or prior["source_url"]!=uri:
                        raise RuntimeError("Existing cached PDF or URL hash drift")
                fetched_url=uri
                source_status="REUSED_VERIFIED_LOCAL_CACHE"
            elif mode=="offline":
                raise RuntimeError("Offline mode has no saved PDF: "+str(p))
            elif mode=="fetch":
                raw,fetched_url=request_pdf(session,uri,timeout,delay,retries)
                p.write_bytes(raw)
                actualsha=sha(raw)
                meta.write_text(json.dumps({"document_id":docid,"source_url":uri,
                            "final_url":fetched_url,"source_sha256":actualsha,
                            "cached_utc":dt.datetime.now(dt.timezone.utc).isoformat()},
                            ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
                source_status="FETCHED_AND_CACHED"
            else:raise RuntimeError("Unsupported mode")
            pages,pinfo=read_pdf_text(raw)
            if pinfo["pages"]!=int(d["expected_pdf_pages"]):
                raise RuntimeError("PDF page count changed or incorrect historical source")
            full_text=normalize(" ".join(pages))
            if docid=="FR2011" and ("douze nouveaux membres" not in full_text or "30 novembre 2010" not in full_text):
                raise RuntimeError("2011 PDF identity header missing")
            if docid=="FR2013" and "academiciens elus en 2013" not in full_text:
                raise RuntimeError("2013 booklet identity header missing")
            if docid=="FR2014" and ("dix nouveaux membres" not in full_text or "18 novembre 2014" not in full_text):
                raise RuntimeError("2014 election document identity header missing")
            if docid=="FR2017" and ("dix huit nouveaux membres" not in full_text or "5 decembre 2017" not in full_text):
                raise RuntimeError("2017 election document identity header missing")
            successes=0; date_successes=0
            for person in rowmap[docid]:
                rec=extract_candidate(pages,person)
                accepted=rec["verification"] in {"OFFICIAL_NAME_ONLY_CONFIRMED","YEAR_ONLY_SOURCE_MATCH",
                           "PDF_EXACT_DATE_CONFIRMED","PDF_ORDINAL_1e_REQUIRES_REVIEW"}
                successes+=int(accepted)
                date_successes+=int(rec["verification"] in {"PDF_EXACT_DATE_CONFIRMED","PDF_ORDINAL_1e_REQUIRES_REVIEW"})
                extracted.append({
                    "document_id":docid,"person_name":person["person_name_transcribed"],
                    "election_date_from_source":person["election_date_from_first_party"],
                    "birth_claim_gold_candidate":person["birth_as_stated_candidate"],
                    "birth_precision_gold":person["birth_precision"],
                    "pdf_raw_birth_field":rec["pdf_birth_raw"],
                    "pdf_parsed_DOB_or_year_candidate":rec["pdf_birth_candidate"],
                    "validation_status":rec["verification"],
                    "source_pdf_url":uri,
                    "source_pdf_sha256":actualsha,
                    "source_page_zero_index":rec["page_index"],
                    "official_election_identity_source_verified":int(accepted),
                    "independent_exact_DOB_sources_verified":0,
                    "final_study_DOB_accepted":0,
                    "bazi_variables_computed":0,
                })
            source_rows.append({
                "document_id":docid,"status":source_status,"document_role_gate":d["document_role_gate"],
                "url":uri,"source_sha256":actualsha,"source_pages":pinfo["pages"],
                "names_matched":successes,"source_DOB_claims_matched":date_successes,"error":""})
        except Exception as exc:
            source_rows.append({"document_id":docid,"status":"SOURCE_UNAVAILABLE_OR_UNEXPECTED",
                "document_role_gate":d["document_role_gate"],"url":uri,"source_sha256":"",
                "source_pages":"","names_matched":0,"source_DOB_claims_matched":0,
                "error":f"{type(exc).__name__}: {str(exc)[:310]}"})
    status=Counter(row["validation_status"] for row in extracted)
    write_csv(out/"source_fetch_audit_v1.csv",source_rows,
              ["document_id","status","document_role_gate","url","source_sha256",
               "source_pages","names_matched","source_DOB_claims_matched","error"])
    write_csv(out/"candidate_person_evidence_v1.csv",extracted,
              ["document_id","person_name","election_date_from_source","birth_claim_gold_candidate",
               "birth_precision_gold","pdf_raw_birth_field","pdf_parsed_DOB_or_year_candidate",
               "validation_status","source_pdf_url","source_pdf_sha256","source_page_zero_index",
               "official_election_identity_source_verified","independent_exact_DOB_sources_verified",
               "final_study_DOB_accepted","bazi_variables_computed"])
    report={
        "version":"france-academy-official-election-pdf-source-pilot-v1",
        "mode":mode,
        "generated_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
        "http_attempts_upper_bound":limit*retries if mode=="fetch" else 0,
        "selected_full_election_documents":len([x for x in source_rows if x["document_id"]!="NEG2022AE"]),
        "downloaded_or_reused_documents":sum(x["status"] in {"FETCHED_AND_CACHED","REUSED_VERIFIED_LOCAL_CACHE"} for x in source_rows),
        "blocked_or_unexpected_documents":sum(x["status"]=="SOURCE_UNAVAILABLE_OR_UNEXPECTED" for x in source_rows),
        "person_source_assertions_replayed":len(extracted),
        "per_person_parse_status":dict(status),
        "name_and_role_source_matched":sum(int(x["official_election_identity_source_verified"]) for x in extracted),
        "source_exact_DOB_claims_parsed":sum(x["validation_status"] in {"PDF_EXACT_DATE_CONFIRMED","PDF_ORDINAL_1e_REQUIRES_REVIEW"} for x in extracted),
        "foreign_associate_negative_control_excluded":True,
        "independent_exact_DOB_provenance_accepted":0,
        "cohort_roster_finalized":False,
        "bazi_variables_computed":0,
        "WARNING":"Small official-source replay only. Names/dates not automatically promoted to study. Blocked sources must be retried from legitimate local access and never counted as zero names.",
    }
    (out/"summary.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)
    return report

def main()->int:
    ap=argparse.ArgumentParser()
    group=ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--fixture-check",action="store_true",help="No HTTP, validates 66-name first-party transcription")
    group.add_argument("--fetch",action="store_true",help="Download bounded whitelisted source PDFs")
    group.add_argument("--offline",action="store_true",help="Replay cached PDF source hashes and metadata without HTTP")
    ap.add_argument("--limit",type=int,default=2,help="Maximum regular-member PDF documents, 1-4")
    ap.add_argument("--resume",action="store_true",help="Reparse cached success pages rather than redownload")
    ap.add_argument("--delay",type=float,default=1.5)
    ap.add_argument("--timeout",type=float,default=25)
    ap.add_argument("--retries",type=int,default=2)
    ap.add_argument("--out",type=Path,default=OUT)
    args=ap.parse_args()
    if not 1<=args.limit<=4:raise ValueError("--limit must be 1 to 4 for pilot")
    if args.delay<0.7 or args.timeout<3 or not 1<=args.retries<=3:
        raise ValueError("Unsafe request cadence or timeout/retry configuration")
    sources=read_csv(INVENTORY)
    gold=read_csv(GOLD)
    fixtures=count_assertions(gold,sources)
    if args.fixture_check:
        report={"version":"france-academy-official-election-pdf-source-pilot-v1",
                "mode":"fixture-check","network_requests":0,
                **fixtures,
                "final_study_DOB_accepted":0,
                "bazi_variables_computed":0}
        print(json.dumps(report,indent=2,ensure_ascii=False))
        return 0
    mode="fetch" if args.fetch else "offline"
    report=audit(args.out,gold,sources,mode,args.limit,args.delay,args.timeout,args.retries,args.resume)
    if report["downloaded_or_reused_documents"]==0:
        raise SystemExit("No source PDFs accessible; run from legitimate Windows/local access, do not infer absence of Academy electees")
    return 0

if __name__=="__main__":
    sys.exit(main())
