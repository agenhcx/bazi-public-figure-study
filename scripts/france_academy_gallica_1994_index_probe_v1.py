#!/usr/bin/env python3
"""Bounded official Gallica API pilot for the 1994 French Academy index supplement.

Document: *Index biographique de l'Académie des sciences, supplément 1978–1993*,
BnF catalogue ark:/12148/cb35792869s, digitization ark:/12148/bd6t5922329w.
NO mass OCR, no DOI inference, no acceptance of Academy membership or DOB.

--fixture-check  validates endpoint/source metadata offline
--probe          at most 4 polite requests to Gallica documented endpoints
--offline        inspects any previously cached successful responses without HTTP

If access is forbidden, record status and stop. Do not evade source controls.
"""
from __future__ import annotations
import argparse
import datetime as dt
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

VERSION="france-academy-1994-gallica-digital-index-access-pilot-v1"
ARK="bd6t5922329w"
CATALOGUE="https://catalogue.bnf.fr/ark:/12148/cb35792869s"
BOOK_URL="https://gallica.bnf.fr/ark:/12148/"+ARK
OUT=Path("local_runs/france_academy_gallica_1994_index_probe_v1")
UA="bazi-public-figure-study/1.0 (academic, noncommercial; GitHub agenhcx/bazi-public-figure-study)"
ENDPOINTS=[
    {"id":"oai_metadata","url":"https://gallica.bnf.fr/services/OAIRecord?ark="+ARK,
     "ext":"xml","expect":["application/xml","text/xml","xml"]},
    {"id":"iiif_manifest","url":"https://gallica.bnf.fr/iiif/ark:/12148/"+ARK+"/manifest.json",
     "ext":"json","expect":["json"]},
    {"id":"ocr_full_text","url":BOOK_URL+".texteBrut",
     "ext":"txt","expect":["text","plain","utf-8"]},
    {"id":"ocr_page_2","url":BOOK_URL+"/f2.texteBrut",
     "ext":"txt","expect":["text","plain","utf-8"]},
]
ALLOWED={"gallica.bnf.fr"}


def digest(data:bytes)->str:return hashlib.sha256(data).hexdigest()


def fixtures()->dict:
    assert ARK=="bd6t5922329w"
    assert urlparse(CATALOGUE).hostname=="catalogue.bnf.fr"
    assert len(ENDPOINTS)==4
    ids=set()
    for x in ENDPOINTS:
        if x["id"] in ids:raise RuntimeError("Duplicated endpoint ID")
        ids.add(x["id"])
        parsed=urlparse(x["url"])
        if parsed.scheme!="https" or parsed.hostname not in ALLOWED:
            raise RuntimeError("Unexpected endpoint host/scheme")
        if ARK not in x["url"]:
            raise RuntimeError("Wrong digitized source ID")
    return {"source_title":"Index biographique de l'Académie des sciences, supplément 1978–1993",
            "source_publication_year":1994,
            "catalogue_ark":"cb35792869s",
            "digitization_ark":ARK,
            "catalogue_url":CATALOGUE,
            "book_url":BOOK_URL,
            "source_estimated_printed_pages":133,
            "source_rights_note":"BnF catalogue says LIBRE DE DROITS; no redistribution of service output attempted",
            "endpoint_count":len(ENDPOINTS)}


def safe_snapshot(data:bytes,content_type:str,kind:str)->tuple[bool,str,dict]:
    if len(data)>15_000_000:
        return False,"RESPONSE_TOO_LARGE",{}
    begin=data[:900].lstrip().lower()
    content_type=(content_type or "").lower()
    if any(k in begin for k in [b"captcha",b"anubis",b"access denied",b"forbidden",b"<html"]):
        return False,"HTML_CHALLENGE_OR_NOT_EXPECTED",{}
    if kind=="iiif_manifest":
        try: obj=json.loads(data)
        except (ValueError,UnicodeDecodeError):
            return False,"INVALID_JSON",{}
        if not isinstance(obj,dict) or not any(k in obj for k in ("sequences","items","@context")):
            return False,"UNEXPECTED_MANIFEST_SCHEMA",{}
        sequences=obj.get("sequences",[])
        items=obj.get("items",[])
        canvases=sequences[0].get("canvases",[]) if sequences else items
        # No person index scanning in access check.
        return True,"IIIF_MANIFEST_VALID",{"canvases":len(canvases),"manifest_label":str(obj.get("label",""))[:180]}
    if kind=="oai_metadata":
        if b"<" not in data[:70] or not any(k in data[:2000].lower() for k in [b"<results",b"<?xml",b"<record",b"<notice"]):
            return False,"UNEXPECTED_OAI_METADATA",{}
        return True,"OAI_METADATA_XML",{}
    if len(data)<5 or (content_type and "pdf" in content_type):
        return False,"UNEXPECTED_OCR_BODY",{}
    # textBrut can emit XML with source text; the raw response is retained
    # only in local gitignored cache for provenance, not parsed as exact DOB.
    return True,"OCR_TEXT_RESPONSE_CANDIDATE",{"characters":len(data)}


def run(limit:int,offline:bool,out:Path,delay:float,timeout:float)->dict:
    import requests
    out.mkdir(parents=True,exist_ok=True)
    cache=out/"cache";cache.mkdir(parents=True,exist_ok=True)
    session=None
    if not offline:
        session=requests.Session()
        session.headers.update({"User-Agent":UA,"Accept-Language":"fr-FR,fr;q=0.8,en;q=0.3"})
    rows=[]
    for i,x in enumerate(ENDPOINTS[:limit]):
        filename=cache/(x["id"]+"."+x["ext"])
        metadata=cache/(x["id"]+".meta.json")
        attempt=0;state="";status=None;safe={};source_sha="";ct=""
        try:
            if filename.exists() and metadata.exists():
                raw=filename.read_bytes()
                entry=json.loads(metadata.read_text(encoding="utf-8"))
                if entry.get("url")!=x["url"] or entry.get("sha256")!=digest(raw):
                    raise RuntimeError("Local snapshot URL/hash does not match")
                ct=entry.get("content_type","")
                status=entry.get("original_status",200)
                state="REUSED_LOCAL_CACHE"
            elif offline:
                raise RuntimeError("No cached response for offline inspection")
            else:
                attempt=1
                if i:time.sleep(delay)
                # Never auto-follow a redirect to an uncontrolled location.
                response=session.get(x["url"],timeout=timeout,allow_redirects=False)
                status=response.status_code
                ct=response.headers.get("content-type","")
                raw=response.content
                if status in (301,302,303,307,308):
                    state="REDIRECT_NOT_FOLLOWED"
                elif status in (401,403,407,429):
                    state="BLOCKED_OR_RATE_LIMITED"
                elif status!=200:
                    state="HTTP_UNAVAILABLE"
                else:
                    valid,kind,safe=safe_snapshot(raw,ct,x["id"])
                    if valid:
                        state=kind
                        source_sha=digest(raw)
                        # Save successful source bytes and sidecar atomically,
                        # never check into GitHub as full text/image data.
                        tmp=filename.with_name(filename.name+".part")
                        tmp.write_bytes(raw)
                        os.replace(tmp,filename)
                        meta={"url":x["url"],"sha256":source_sha,"content_type":ct,
                              "original_status":status,
                              "captured_utc":dt.datetime.now(dt.timezone.utc).isoformat()}
                        tmpmeta=metadata.with_name(metadata.name+".part")
                        tmpmeta.write_text(json.dumps(meta,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
                        os.replace(tmpmeta,metadata)
                    else:state=kind
            if state=="REUSED_LOCAL_CACHE":
                valid,kind,safe=safe_snapshot(raw,ct,x["id"])
                if not valid:state=kind
                else:source_sha=digest(raw)
        except Exception as exc:
            state="SOURCE_ERROR_"+type(exc).__name__
            safe={"error_detail":str(exc)[:180]}
        rows.append({"endpoint_id":x["id"],"url":x["url"],"http_status":status,
                     "state":state,"sha256":source_sha,"request_attempts":attempt,
                     "metadata":safe})
        print(f"{x['id']}: {state}, HTTP {status}",flush=True)
    result={
        "version":VERSION,
        "audit_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
        "mode":"offline" if offline else "probe",
        "number_of_endpoints_selected":limit,
        "number_of_source_requests":sum(x["request_attempts"] for x in rows),
        "usable_api_responses":sum(bool(x["sha256"]) for x in rows),
        "api_endpoint_status":[{"id":x["endpoint_id"],"state":x["state"],"http_status":x["http_status"],
                                "sha256":x["sha256"],"metadata":x["metadata"]} for x in rows],
        "digitized_1994_index_data_not_yet_parsed_for_members":True,
        "accepted_exact_dob":0,"accepted_full_member":0,"bazi_variables_computed":0,
        "warning":"A digitized-catalogue pointer and successful API response alone do NOT certify any person-level birthdate or Academy member class. HTTP403 must not be bypassed.",
    }
    (out/"summary.json").write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return result


def main()->int:
    ap=argparse.ArgumentParser()
    modes=ap.add_mutually_exclusive_group(required=True)
    modes.add_argument("--fixture-check",action="store_true")
    modes.add_argument("--probe",action="store_true")
    modes.add_argument("--offline",action="store_true")
    ap.add_argument("--limit",type=int,default=3)
    ap.add_argument("--timeout",type=float,default=22.0)
    ap.add_argument("--delay",type=float,default=1.3)
    ap.add_argument("--out",type=Path,default=OUT)
    args=ap.parse_args()
    if args.limit not in range(1,5) or not (0.9<=args.delay<=30) or not (5<=args.timeout<=60):
        raise RuntimeError("Must use at most four politely spaced bounded requests")
    info=fixtures()
    if args.fixture_check:
        print(json.dumps({"mode":"fixture-check","network_requests":0,**info},ensure_ascii=False,indent=2))
        return 0
    # Requests is intentionally installed only for small Gallica probe/standalone.
    result=run(args.limit,args.offline,args.out,args.delay,args.timeout)
    if result["usable_api_responses"]==0:
        print("All selected endpoints blocked/unavailable: review local summary; do not retry aggressively.")
    return 0


if __name__=="__main__":
    sys.exit(main())
