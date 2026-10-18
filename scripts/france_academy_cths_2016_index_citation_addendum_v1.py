#!/usr/bin/env python3
"""Offline addendum to earlier 562 French Academy CTHS bibliography audit.

Identify citations to official *Index biographique de 1666 à 2016* omitted
by prior 1979/1989/1993/1994-only source categories. Keep primary manuscript
distinct from an actually inspected individual index entry; NO DOB acceptance.
"""
from __future__ import annotations

import csv, datetime as dt, hashlib, json, re, tarfile
from pathlib import Path
from france_academy_cths_original_citation_audit_v1 import extract_sections, read_csv, save_csv

ROOT=Path("data/france_academy_cths_profile_dob_harvest_v1")
BASE=Path("data/france_academy_cths_historical_source_citation_audit_v1")
OUT=Path("data/france_academy_leridon_historical_master_source_pilot_v1")
MATCHES=[
 ("index_biographique_1666_2016",
  re.compile(r"\bindex\s+biographique\b.{0,100}\b1666\s+a\s+2016\b|\bindex\s+biographique\b.{0,60}\b2016\b")),
 ("index_biographique_1666_1978",
  re.compile(r"\bindex\s+biographique\b.{0,100}\b1666\s+a\s+1978\b")),
]

def main():
    people=read_csv(ROOT/"cths_dob_claims_all_targets_candidate_only_v1.csv")
    prior=read_csv(BASE/"cths_562_cited_source_metadata_v1.csv")
    if len(people)!=562 or len(prior)!=562:raise RuntimeError("CTHS historical source corpus changed")
    original={r["cths_person_id"]:r for r in people}
    earlier={r["cths_person_id"]:r for r in prior}
    expected=json.loads((ROOT/"summary.json").read_text(encoding="utf-8"))
    a=ROOT/expected["raw_html_archive"]
    if hashlib.sha256(a.read_bytes()).hexdigest()!=expected["raw_html_bundle_sha256"]:
        raise RuntimeError("Pinned source archive hash drift")
    out=[]
    checked=0
    with tarfile.open(a,"r:gz") as tf:
        for x in tf:
            if not x.isfile():continue
            fp=tf.extractfile(x)
            if fp is None:raise RuntimeError("Malformed archive")
            raw=fp.read()
            h=hashlib.sha256(raw).hexdigest()
            if x.name!="source_html/"+h+".html":raise RuntimeError("Original source digest mismatch")
            owners=[p for p in people if p["source_raw_html_sha256"]==h]
            if len(owners)!=1:raise RuntimeError("Source/person mapping not unique")
            p=owners[0]; checked+=1
            bib=extract_sections(raw)["bibliography_text"]
            flags={k:int(bool(reg.search(bib))) for k,reg in MATCHES}
            if flags["index_biographique_1666_2016"]:
                old=earlier[p["cths_person_id"]]
                out.append({
                    "cths_person_id":p["cths_person_id"],
                    "name":p["name"],
                    "cths_year_provisional":p["CTHS_roster_year_provisional"],
                    "cths_dob_candidate_unverified":p["cths_exact_dob_claim_candidate_only"],
                    "member_class_CTHS_only":p["CTHS_roster_membership_class_provisional"],
                    "cths_profile_url":p["url"],
                    "source_html_sha256":h,
                    "index_1666_2016_explicitly_cited":1,
                    "prior_historical_source_directory_in_1979_1989_1993_1994_2008":old["any_cited_official_historical_member_directory"],
                    "original_2016_index_entry_directly_read":0,
                    "underlying_2016_index_DOB_verified":0,
                    "underlying_2016_member_class_verified":0,
                    "bazi_variables_computed":0
                })
    if checked!=562:raise RuntimeError("CTHS archived person count mismatch")
    out.sort(key=lambda x:(int(x["cths_year_provisional"]),int(x["cths_person_id"])))
    OUT.mkdir(parents=True,exist_ok=True)
    columns=list(out[0]) if out else ["cths_person_id","name","cths_profile_url",
                                   "index_1666_2016_explicitly_cited","original_2016_index_entry_directly_read",
                                   "underlying_2016_index_DOB_verified","underlying_2016_member_class_verified",
                                   "bazi_variables_computed"]
    save_csv(OUT/"cths_2016_index_bibliographic_leads_addendum_v1.csv",out,columns)
    counts={
       "version":"france-academy-CTHS-2016-biographic-index-source-citation-addendum-v1",
       "checked_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
       "offline_network_requests":0,
       "cths_sha_audited_people":checked,
       "mentions_official_2016_biographic_index":len(out),
       "2016_source_leads_new_not_in_old_130":sum(x["prior_historical_source_directory_in_1979_1989_1993_1994_2008"]=="0" for x in out),
       "2016_source_leads_already_in_old_130":sum(x["prior_historical_source_directory_in_1979_1989_1993_1994_2008"]=="1" for x in out),
       "original_2016_index_entries_directly_seen":0,
       "underlying_2016_DOBs_verified":0,
       "underlying_2016_membership_statuses_verified":0,
       "bazi_variables_computed":0,
       "warning":"Index references are bibliography citations, not proof that cited printed index contains the person/DOB. User-provided or accessible original index still required."
    }
    (OUT/"cths_2016_index_citation_summary_v1.json").write_text(json.dumps(counts,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(counts,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
