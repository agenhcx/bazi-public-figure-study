#!/usr/bin/env python3
"""Capture CTHS Académie des sciences biography DOB *candidates* with provenance.

Mode collect: one deterministic shard from previously frozen 562-person queue.
Mode consolidate: merge exactly four shard artifacts, keep original HTML in a
compressed permanent snapshot and emit DOB precision/missingness audits.

This pipeline does not independently verify CTHS date origins, accept DOBs,
accept full-member status, or compute any BaZi variables.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import re
import tarfile
import time
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from ftfy import fix_text

VERSION="france-academy-cths-profile-dob-raw-harvest-v1"
QUEUEDIR=Path("data/france_academy_cths_dob_collection_queue_v1")
OUT=Path("data/france_academy_cths_profile_dob_harvest_v1")
SHARDS=4
UA="bazi-public-figure-study/1.0 academic noncommercial archival birth-date evidence study; github.com/agenhcx/bazi-public-figure-study"
MONTHS=dict(zip(
    ("janvier","fevrier","mars","avril","mai","juin","juillet","aout","septembre","octobre","novembre","decembre"),
    range(1,13)))
EXACT=re.compile(
    r"(?<!\d)(?P<day>0?[1-9]|[12]\d|3[01])\s+"
    r"(?P<month>janvier|fevrier|mars|avril|mai|juin|juillet|aout|septembre|octobre|novembre|decembre)"
    r"\s+(?P<year>1[6789]\d{2}|20[012]\d)\b",re.I)

def fold(s:str)->str:
    s=unicodedata.normalize("NFKD",fix_text(s).casefold())
    return "".join(c for c in s if not unicodedata.combining(c))

def digest(b:bytes)->str:return hashlib.sha256(b).hexdigest()

def read(path:Path)->list[dict]:
    with path.open("r",encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))

def write(path:Path,rows:list[dict],hdr:list[str])->None:
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=hdr,extrasaction="ignore");w.writeheader();w.writerows(rows)

def parse(raw:bytes,expected_birth_year:int)->dict:
    # CTHS biography pages tend to be largely UTF-8, sometimes mixed legacy
    # CP1252; decoding to CP1252 then ftfy per field is robust to both.
    soup=BeautifulSoup(raw.decode("cp1252",errors="replace"),"html.parser")
    text=fix_text(soup.get_text(" ",strip=True))
    candidates=re.findall(r"\bNaissance\s*:\s*(.{0,250})",text,flags=re.I)
    birth_context=""
    if candidates:
        birth_context=candidates[0]
        birth_context=re.split(
            r"\s*(?:Décès\s*:|Société(?:\(s\))?\s*:|Biographie\b|Sociétés\b|"
            r"\bBibliographie\b|Académie des sciences\s*:)",
            birth_context,maxsplit=1,flags=re.I)[0]
    birth_context=" ".join(birth_context.split())[:200]
    normalized=fold(birth_context)
    exact=EXACT.search(normalized)
    # Date must be the beginning of the dedicated "Naissance:" field;
    # a date buried in biography text must never masquerade as birth.
    if exact and exact.start()<=4:
        day=int(exact.group("day"));year=int(exact.group("year"))
        month=MONTHS[exact.group("month")]
        try:
            iso=dt.date(year,month,day).isoformat()
            quality="candidate_exact_day"
        except ValueError:
            iso="";quality="invalid_calendar_date"
        if year!=expected_birth_year:
            quality="candidate_birth_year_conflict"
    elif birth_context:
        iso="";quality="birth_metadata_nonexact_or_unparsed"
    else:
        iso="";quality="no_birth_metadata_detected"
    # Recovered context is just a CTHS assertion. Source bibliography may
    # be copied from Wikidata/Wikipedia or a primary record: not adjudicated.
    return {
        "cths_birth_raw":birth_context,
        "cths_exact_dob_claim_candidate_only":iso,
        "cths_birth_parser_status":quality,
        "year_agrees_with_roster":int(
            bool(exact and int(exact.group("year"))==expected_birth_year)),
        "CTHS_original_birthdate_provenance_independently_checked":0,
        "accepted_exact_dob":0,
    }

def get(session:requests.Session,url:str,delay:float,timeout:int)->bytes:
    last=None
    for attempt in range(1,3):
        try:
            time.sleep(delay)
            resp=session.get(url,timeout=timeout,allow_redirects=False)
            if resp.status_code not in (200,):
                raise ValueError(f"HTTP {resp.status_code}")
            raw=resp.content
            if not 1200<len(raw)<2_000_000 or b"<html" not in raw.lower():
                raise ValueError(f"unrecognized page length {len(raw)}")
            return raw
        except (requests.RequestException, ValueError) as exc:
            last=exc
            time.sleep(1)
    raise RuntimeError(f"{last}")

def collect(shard:int,delay:float,timeout:int)->None:
    p=QUEUEDIR/f"source_fetch_shard_{shard:02d}_of_{SHARDS:02d}.csv"
    targets=read(p)
    if not 100<=len(targets)<=180:
        raise RuntimeError(f"Unusual shard {shard} size {len(targets)}")
    dst=OUT/f"shard_{shard}"
    rawdst=dst/"source_html";rawdst.mkdir(parents=True,exist_ok=True)
    s=requests.Session();s.headers.update({"User-Agent":UA,"Accept-Language":"fr-FR,fr;q=0.9"})
    rows,errs=[],[]
    for idx,t in enumerate(targets,1):
        url=t["cths_profile_url"];pid=t["cths_person_id"]
        expected=int(t["birth_year_provisional"])
        try:
            raw=get(s,url,delay,timeout)
            hsh=digest(raw)
            (rawdst/(hsh+".html")).write_bytes(raw)
            value=parse(raw,expected)
            rows.append({
                "cths_person_id":pid,"name":t["cths_name"],"url":url,
                "CTHS_roster_year_provisional":expected,
                "CTHS_roster_membership_class_provisional":t["membership_type_provisional"],
                "source_raw_html_sha256":hsh,
                "source_snapshot_available":1,"fetch_result":"HTTP_200",
                **value,
            })
        except Exception as exc:
            rows.append({
                "cths_person_id":pid,"name":t["cths_name"],"url":url,
                "CTHS_roster_year_provisional":expected,
                "CTHS_roster_membership_class_provisional":t["membership_type_provisional"],
                "source_raw_html_sha256":"","source_snapshot_available":0,
                "fetch_result":"FETCH_OR_PARSE_ERROR",
                "cths_birth_raw":"","cths_exact_dob_claim_candidate_only":"",
                "cths_birth_parser_status":"FETCH_OR_PARSE_ERROR",
                "year_agrees_with_roster":0,
                "CTHS_original_birthdate_provenance_independently_checked":0,
                "accepted_exact_dob":0,
            })
            errs.append({"cths_person_id":pid,"url":url,"error":str(exc)[:400]})
        if idx%30==0 or idx==len(targets):
            print(f"CTHS shard={shard}: {idx}/{len(targets)} fetched={idx-len(errs)}, errors={len(errs)}",flush=True)
    hdr=list(rows[0])
    write(dst/"candidate_birthdays.csv",rows,hdr)
    write(dst/"fetch_errors.csv",errs,["cths_person_id","url","error"])
    audit={
        "version":VERSION,"shard":shard,"target_rows":len(targets),"result_rows":len(rows),
        "fetch_errors":len(errs),"parse_status_counts":dict(Counter(x["cths_birth_parser_status"] for x in rows)),
        "source_assertion_exact_dob_only":True,
        "birthdays_accepted":0,"bazi_variables_computed":0,
    }
    (dst/"summary.json").write_text(json.dumps(audit,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(audit,ensure_ascii=False,indent=2),flush=True)

def consolidate(artifact_dir:Path)->None:
    queue=read(QUEUEDIR/"cths_provisional_member_source_fetch_queue_v1.csv")
    expected_ids={r["cths_person_id"] for r in queue}
    merged=[];rootfiles=[]
    for i in range(SHARDS):
        src=artifact_dir/f"cths-birth-source-shard-{i}"
        if not src.is_dir():raise RuntimeError(f"Missing shard artifact folder {src}")
        audit=json.loads((src/"summary.json").read_text(encoding="utf-8"))
        rows=read(src/"candidate_birthdays.csv")
        if len(rows)!=audit["target_rows"] or audit["shard"]!=i:raise RuntimeError("Shard summary mismatch")
        merged.extend(rows)
        rootfiles+=list((src/"source_html").glob("*.html"))
    ids=[r["cths_person_id"] for r in merged]
    if len(ids)!=len(expected_ids) or len(set(ids))!=len(ids) or set(ids)!=expected_ids:
        raise RuntimeError(f"CTHS DOB source harvest coverage/identity failure: {len(ids)} vs {len(expected_ids)}")
    if not merged:raise RuntimeError("No collected people")
    # Evidence preservation: persist raw page snapshots in a deterministic
    # source-hash keyed compressed tarball rather than thousands of Git files.
    OUT.mkdir(parents=True,exist_ok=True)
    tarpath=OUT/"cths_profile_source_html_sha256_bundle_v1.tar.gz"
    with tarfile.open(tarpath,"w:gz") as archive:
        seen=set()
        for p in sorted(rootfiles,key=lambda p:p.name):
            if p.name in seen:continue
            if digest(p.read_bytes())!=p.stem:raise RuntimeError(f"Raw HTML checksum mismatch {p}")
            seen.add(p.name)
            archive.add(p,arcname="source_html/"+p.name,recursive=False)
    merged.sort(key=lambda r:r["cths_person_id"].zfill(12))
    fields=list(merged[0])
    write(OUT/"cths_dob_claims_all_targets_candidate_only_v1.csv",merged,fields)
    status=Counter(r["cths_birth_parser_status"] for r in merged)
    decade=defaultdict(Counter)
    for r in merged:
        year=int(r["CTHS_roster_year_provisional"])
        dec=f"{year//10*10}s"
        decade[dec][r["cths_birth_parser_status"]]+=1
        decade[dec]["target_rows"]+=1
    dcols=["birth_decade","target_rows"]+sorted(status)
    write(OUT/"birthdate_parse_coverage_by_birth_decade_v1.csv",
          [{"birth_decade":k,**v} for k,v in sorted(decade.items())],dcols)
    report={
        "version":VERSION,
        "created_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
        "expected_target_people":len(expected_ids),"processed_people":len(merged),
        "source_raw_page_files_count":len(seen),
        "raw_html_archive":tarpath.name,"raw_html_bundle_sha256":digest(tarpath.read_bytes()),
        "parse_quality_counts":dict(status),
        "candidate_exact_iso_count":sum(bool(x["cths_exact_dob_claim_candidate_only"]) for x in merged),
        "candidate_year_mismatch":status["candidate_birth_year_conflict"],
        "source_fetch_error_count":status["FETCH_OR_PARSE_ERROR"],
        "accepted_exact_dob_count":0,"accepted_full_membership_status_count":0,
        "no_independent_source_check":True,"bazi_variables_computed":0,
        "warning":"CTHS exact DOB claims and sources are candidates only; verify original provenance and confirm official full-member election status before adding to science hierarchy study.",
    }
    (OUT/"summary.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)

def main():
    ap=argparse.ArgumentParser()
    modes=ap.add_mutually_exclusive_group(required=True)
    modes.add_argument("--collect-shard",type=int)
    modes.add_argument("--consolidate-from",type=Path)
    ap.add_argument("--delay",type=float,default=1.25)
    ap.add_argument("--timeout",type=int,default=25)
    args=ap.parse_args()
    if args.collect_shard is not None:
        if not 0<=args.collect_shard<SHARDS:raise ValueError("Shard out of range")
        if args.delay<0.8:raise ValueError("Politeness delay too low")
        collect(args.collect_shard,args.delay,args.timeout)
    else:consolidate(args.consolidate_from)

if __name__=="__main__":main()
