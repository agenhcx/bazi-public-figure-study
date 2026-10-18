#!/usr/bin/env python3
"""Local, network-free audit of the already captured French Academy CTHS evidence.

No requests, no re-crawling, no extra DOB acceptance or BaZi variables.
Prints only a compact summary and outputs small review CSVs; keeps all raw HTML
and the 529 source provenance candidates in the local repository.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import tarfile
from collections import Counter
from pathlib import Path

DEFAULT_DATA=Path("data/france_academy_cths_profile_dob_harvest_v1")
DEFAULT_QUEUE=Path("data/france_academy_cths_dob_collection_queue_v1/cths_provisional_member_source_fetch_queue_v1.csv")
DEFAULT_OUT=Path("local_runs/france_academy_cths_source_audit_v1")
VERSION="france-academy-local-offline-source-audit-v1"

def sha(path:Path)->str:
    digest=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""):
            digest.update(chunk)
    return digest.hexdigest()

def csv_read(path:Path)->list[dict[str,str]]:
    with path.open("r",encoding="utf-8-sig",newline="") as f:
        return list(csv.DictReader(f))

def csv_write(path:Path,rows:list[dict[str,str]],cols:list[str])->None:
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("w",encoding="utf-8-sig",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=cols,extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

def verify_archive(path:Path,expected_archive_sha:str,expected_source_shas:set[str])->dict:
    if not path.is_file():
        raise RuntimeError("Missing raw source archive: "+str(path))
    archive_hash=sha(path)
    if archive_hash!=expected_archive_sha:
        raise RuntimeError("Raw source archive SHA mismatch; source snapshot cannot be trusted")
    found=set()
    with tarfile.open(path,mode="r:gz") as tf:
        for member in tf:
            if not member.isfile():
                raise RuntimeError("Unexpected non-file archive entry: "+member.name)
            path_parts=Path(member.name).parts
            if len(path_parts)!=2 or path_parts[0]!="source_html" or not member.name.endswith(".html"):
                raise RuntimeError("Unexpected archive path (rejecting unsafe layout): "+member.name)
            expected_hash=Path(member.name).stem
            if expected_hash in found:
                raise RuntimeError("Duplicate source digest in archive: "+expected_hash)
            f=tf.extractfile(member)
            if f is None:
                raise RuntimeError("Unreadable archive member: "+member.name)
            digest=hashlib.sha256()
            for chunk in iter(lambda:f.read(1024*1024),b""):
                digest.update(chunk)
            if digest.hexdigest()!=expected_hash:
                raise RuntimeError("Archived HTML content digest mismatch: "+member.name)
            found.add(expected_hash)
    if found!=expected_source_shas:
        raise RuntimeError(
            "Archive/source-ledger mismatch: absent=%d, unexpected=%d" %
            (len(expected_source_shas-found),len(found-expected_source_shas)))
    return {"archive_sha256":archive_hash,"individual_source_pages_verified":len(found),"complete":True}

def main()->int:
    ap=argparse.ArgumentParser(description="Network-free French Academy CTHS source and DOB candidate audit")
    ap.add_argument("--data",type=Path,default=DEFAULT_DATA)
    ap.add_argument("--queue",type=Path,default=DEFAULT_QUEUE)
    ap.add_argument("--out",type=Path,default=DEFAULT_OUT)
    ap.add_argument("--skip-archive-verification",action="store_true",help="Fast metadata-only check; not a full integrity audit")
    args=ap.parse_args()

    summary=json.loads((args.data/"summary.json").read_text(encoding="utf-8"))
    records=csv_read(args.data/"cths_dob_claims_all_targets_candidate_only_v1.csv")
    queue=csv_read(args.queue)
    ids=[r["cths_person_id"] for r in records]
    queued=[r["cths_person_id"] for r in queue]
    if len(ids)!=len(set(ids)) or len(queued)!=len(set(queued)):
        raise RuntimeError("Duplicated person IDs")
    if set(ids)!=set(queued) or len(ids)!=summary["expected_target_people"]:
        raise RuntimeError("Queue and scraped source person IDs or count differ")

    by_id={r["cths_person_id"]:r for r in queue}
    source_shas=set()
    statuses=Counter()
    reasons=Counter()
    review_rows=[]
    provenance_rows=[]
    bad=[]
    for r in records:
        pid=r["cths_person_id"]
        status=r["cths_birth_parser_status"]
        statuses[status]+=1
        url=r["url"]
        original_sha=r["source_raw_html_sha256"]
        if r["source_snapshot_available"]=="1":
            if len(original_sha)!=64:
                bad.append(f"source sha unavailable for {pid}")
            source_shas.add(original_sha)
        else:
            bad.append(f"source snapshot missing for {pid}")
        if url!=by_id[pid]["cths_profile_url"]:
            bad.append(f"source URL mismatch for {pid}")
        if r.get("accepted_exact_dob")!="0" or r.get("CTHS_original_birthdate_provenance_independently_checked")!="0":
            bad.append(f"unexpected DOB acceptance/independent verification flag for {pid}")
        if by_id[pid].get("eligible_for_primary_roster")!="0":
            bad.append(f"unexpected primary eligibility flag for {pid}")
        provisional_year=int(r["CTHS_roster_year_provisional"])
        dob=r["cths_exact_dob_claim_candidate_only"]
        if status=="candidate_exact_day":
            try:
                parsed=dt.date.fromisoformat(dob)
            except ValueError:
                bad.append(f"invalid candidate exact DOB for {pid}")
            else:
                if parsed.year!=provisional_year:
                    bad.append(f"birth-year disagreement for {pid}")
        elif dob:
            bad.append(f"nonexact candidate has ISO DOB value for {pid}")
        if r["CTHS_roster_membership_class_provisional"]!=by_id[pid]["membership_type_provisional"]:
            bad.append(f"membership category mismatch for {pid}")

        why=[]
        if status!="candidate_exact_day":
            why.append("DOB_"+status)
        if by_id[pid]["membership_type_provisional"]=="full_and_foreign_mixed_manual":
            why.append("MIXED_HISTORICAL_MEMBERSHIP")
        if r["fetch_result"]!="HTTP_200":
            why.append("SOURCE_FETCH_"+r["fetch_result"])
        if why:
            reasons.update(why)
            review_rows.append({
                "cths_person_id":pid,
                "name":r["name"],
                "birth_year_provisional":str(provisional_year),
                "candidate_dob":dob,
                "review_reason":" | ".join(why),
                "CTHS_source_url":url,
                "CTHS_source_sha256":original_sha,
                "DOB_accepted":"0",
                "full_membership_accepted":"0",
            })
        if dob:
            provenance_rows.append({
                "cths_person_id":pid,
                "name":r["name"],
                "CTHS_dob_assertion_candidate":dob,
                "CTHS_source_url":url,
                "CTHS_source_sha256":original_sha,
                "independent_source_url":"",
                "independent_source_exact_dob_quote":"",
                "source_independence_verified":"0",
                "membership_officially_verified":"0",
                "date_accepted":"0",
            })
    if bad:
        raise RuntimeError("Source data invariant violations: "+"; ".join(bad[:12]))

    parsed_count=statuses["candidate_exact_day"]
    if parsed_count!=summary["candidate_exact_iso_count"]:
        raise RuntimeError("Parsed exact candidate counts do not match source freeze manifest")
    if len(records)!=summary["processed_people"]:
        raise RuntimeError("CTHS source manifest target total changed")

    archive_check={"skipped":True,"individual_source_pages_verified":0,"complete":False}
    if not args.skip_archive_verification:
        archive_check=verify_archive(
            args.data/summary["raw_html_archive"],
            summary["raw_html_bundle_sha256"],
            source_shas)

    args.out.mkdir(parents=True,exist_ok=True)
    csv_write(args.out/"source_and_membership_review_queue.csv",
              sorted(review_rows,key=lambda r:r["cths_person_id"]),
              ["cths_person_id","name","birth_year_provisional","candidate_dob","review_reason",
               "CTHS_source_url","CTHS_source_sha256","DOB_accepted","full_membership_accepted"])
    csv_write(args.out/"dob_independent_source_verification_queue.csv",
              sorted(provenance_rows,key=lambda r:r["cths_person_id"]),
              ["cths_person_id","name","CTHS_dob_assertion_candidate","CTHS_source_url",
               "CTHS_source_sha256","independent_source_url","independent_source_exact_dob_quote",
               "source_independence_verified","membership_officially_verified","date_accepted"])

    report={
        "script":VERSION,
        "audit_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
        "network_requests":0,
        "persons_checked":len(records),
        "CTHS_source_claims_parseable_exact":parsed_count,
        "CTHS_DOB_nonexact_or_missing":len(records)-parsed_count,
        "review_queue_unique_people":len(review_rows),
        "review_reason_counts":dict(sorted(reasons.items())),
        "independent_source_verification_queue":len(provenance_rows),
        "verified_independent_DOB_count":0,
        "verified_historical_full_membership_count":0,
        "bazi_variables_computed":0,
        "raw_source_integrity":archive_check,
        "warning":"Only audits existing source evidence. CTHS DOB claims are not independently verified.",
    }
    (args.out/"summary.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))
    print("Send only summary.json and source_and_membership_review_queue.csv if discussion is needed.")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
