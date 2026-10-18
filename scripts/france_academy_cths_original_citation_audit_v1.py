#!/usr/bin/env python3
"""Offline classify ORIGINAL citations for existing 562 French Academy CTHS sources.

Audits SHA256 for every previously captured CTHS biography from the on-disk
tar.gz source bundle; inspects CTHS fieldset 'Sources biographiques' and a
strict identity crosswalk against the 160 FIRST-PARTY selected election names.

It creates only compact source-citation *metadata* (not full copied source
text) and evidence queues. Does NOT download anything, accept birthdates,
create a complete Academy roster or compute BaZi outcomes.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import re
import tarfile
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

from bs4 import BeautifulSoup
from ftfy import fix_text

SOURCE_ROOT=Path("data/france_academy_cths_profile_dob_harvest_v1")
FROZEN_CTHS=SOURCE_ROOT/"cths_dob_claims_all_targets_candidate_only_v1.csv"
ARCHIVE=SOURCE_ROOT/"cths_profile_source_html_sha256_bundle_v1.tar.gz"
ARCHIVE_MANIFEST=SOURCE_ROOT/"summary.json"
FIRST_PARTY=Path("data/france_academy_firstparty_elected_union_v1/firstparty_member_election_candidate_union_v1.csv")
OUT=Path("data/france_academy_cths_historical_source_citation_audit_v1")
VERSION="france-academy-cths-562-bibliographic-source-citation-offline-v1"
MIN_YEAR,MAX_YEAR=1835,1985

# The presence of a cited work in the CTHS bibliography is a *lead* only.
# It does NOT show the cited publication states or validates the person's
# date of birth, membership class or election date.
ACADEMY_INDEX_RULES=[
 ("academy_bio_1979",r"\bindex\s+biographique.{0,120}\bacademie\s+des\s+sciences\b.{0,140}\b1979\b|\bindex\s+biographique.{0,120}\b1978\b"),
 ("academy_member_only_1989",r"\brepertoire\s+biographique.{0,150}\bacademie\s+des\s+sciences\b.{0,100}\b1989\b|\brepertoire\s+biographique.{0,100}\bmembres\b.{0,100}\b1989\b"),
 ("academy_bio_supplement_1994",r"\bindex\s+biographique.{0,150}\b1978.{0,25}1993\b|\bindex\s+biographique.{0,100}\bsupplement\b.{0,100}\b1994\b"),
 ("academy_member_corr_1993",r"\brepertoire\s+biographique.{0,150}\bacademie\s+des\s+sciences\b.{0,100}\b1993\b|\brepertoire\s+biographique.{0,100}\bmembres\b.{0,100}\b1993\b"),
 ("academy_member_corr_2008",r"\brepertoire\s+biographique.{0,150}\bacademie\s+des\s+sciences\b.{0,100}\b2008\b|\brepertoire\s+biographique.{0,100}\bmembres\b.{0,100}\b2008\b"),
]
BROAD_CATEGORIES=[
 ("official_academy_biography",r"(?:\bnotice\s+(?:de|par|sur)\b.{0,100}\bacademie\s+des\s+sciences\b|\bcomptes?\s+rendus?\b.{0,50}\bacademie\s+des\s+sciences\b|\bcras\b)"),
 ("civil_birth_records",r"(?:\bacte\s+de\s+naissance\b|\bregistre\s+(?:de\s+)?naissances\b|\betat\s+civil\b)"),
 ("archives_nationales",r"\barchives\s+nationales\b|\blegion\s+d\s+honneur\b"),
 ("other_academies",r"\bacademie\s+(?:de\s+medecine|des\s+technologies|des\s+inscriptions|des\s+beaux\s+arts)\b"),
 ("institutional_CV",r"\bnotice\s+sur\s+les\s+titres\b|\btitres\s+et\s+travaux\b|\bcurriculum\s+vitae\b"),
 ("mass_media",r"\b(?:le\s+monde|le\s+figaro|liberation|les\s+echos|presse)\b"),
 ("wikipedia_or_wikidata",r"\bwikipedia\b|\bwikidata\b"),
 ("biographical_dictionaries",r"\bdictionnaire\s+de\s+biographie\b|\bdictionnaire\s+biographique\b|\bdbf\b"),
]


def read_csv(p:Path)->list[dict]:
    with p.open("r",encoding="utf-8-sig",newline="") as f:
        return list(csv.DictReader(f))


def save_csv(p:Path,items:list[dict],cols:list[str])->None:
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=cols,extrasaction="ignore")
        w.writeheader()
        w.writerows(items)


def sha_file(p:Path)->str:
    h=hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""):h.update(b)
    return h.hexdigest()


def fold(s:str)->str:
    s=unicodedata.normalize("NFKD",fix_text(s).casefold())
    return "".join(c for c in s if not unicodedata.combining(c))


def identity_key(s:str)->str:
    t=fold(s).replace("œ","oe").replace("æ","ae").replace("ø","o")
    return " ".join(sorted(re.findall(r"[a-z0-9]+",t)))


def extract_sections(raw:bytes)->dict:
    # CTHS profile HTML has a declared UTF-8 header but sometimes mixed
    # Windows-1252 bytes in the actual page body. Avoid silent charset guessing.
    text=fix_text(raw.decode("cp1252",errors="replace"))
    soup=BeautifulSoup(text,"html.parser")
    sources=soup.find(id="proso_sources_biographiques")
    if sources is None:
        sources=soup.find(id="fieldset_sources_biographiques")
    source_text=fix_text(sources.get_text(" ",strip=True)) if sources is not None else ""
    # Only short source METADATA is persisted, not the full copyrighted prose.
    full_text=fix_text(soup.get_text(" ",strip=True))
    # Data provenance/authorship is not necessarily source independence:
    # an Academy editor can still copy data from Wikipedia or authority files.
    editor=re.search(r"redacteur(?:s)?\s*(?:de\s+la\s+notice)?\s*:\s*(.{0,200})",fold(full_text))
    editor_academy=bool(editor and re.search(r"\bacademie\s+des\s+sciences\b",editor.group(1)))
    return {
        "bibliography_source_found":int(sources is not None),
        "bibliography_text":fold(source_text),
        "bibliography_raw_sha256":hashlib.sha256(source_text.encode("utf-8")).hexdigest(),
        "bibliography_editor_academy_mentioned":int(editor_academy),
    }


def main()->None:
    ap=argparse.ArgumentParser()
    ap.add_argument("--out",type=Path,default=OUT)
    args=ap.parse_args()

    expected=json.loads(ARCHIVE_MANIFEST.read_text(encoding="utf-8"))
    people=read_csv(FROZEN_CTHS)
    first=read_csv(FIRST_PARTY)
    if len(people)!=562 or len(first)!=160:
        raise RuntimeError(f"Frozen corpus drift: CTHS {len(people)} / first-party {len(first)}")
    person_ids={p["cths_person_id"] for p in people}
    if len(person_ids)!=562:raise RuntimeError("Duplicate CTHS IDs")
    source_shas={p["source_raw_html_sha256"] for p in people}
    if len(source_shas)!=562:raise RuntimeError("Unexpected duplicate CTHS source HTML hashes")
    if sha_file(ARCHIVE)!=expected["raw_html_bundle_sha256"]:
        raise RuntimeError("Input 562-source archive checksum differs from previous frozen manifest")

    indexes=defaultdict(list)
    for r in first:indexes[identity_key(r["name"])].append(r)
    if len(indexes)!=160:raise RuntimeError("First-party name key collisions require independent audit")

    per_source={}
    archived=set()
    with tarfile.open(ARCHIVE,"r:gz") as f:
        for entry in f:
            if not entry.isfile():raise RuntimeError("Non-file in immutable archive")
            parts=Path(entry.name).parts
            if len(parts)!=2 or parts[0]!="source_html" or not parts[-1].endswith(".html"):
                raise RuntimeError("Unexpected archived source layout")
            digest=Path(parts[-1]).stem
            if digest in archived:raise RuntimeError("Duplicate SHA256 archive member")
            rawfp=f.extractfile(entry)
            if rawfp is None:raise RuntimeError("Archive extraction failed")
            raw=rawfp.read()
            if hashlib.sha256(raw).hexdigest()!=digest:
                raise RuntimeError("Original HTML changed: "+entry.name)
            per_source[digest]=extract_sections(raw)
            archived.add(digest)
    if source_shas!=archived:
        raise RuntimeError("Archive-to-person identity mapping missing sources")

    out=[]
    matches=[]
    unmatched=[]
    buckets=Counter()
    official_index_hits=Counter()
    general_hits=Counter()
    notfound=0
    for p in people:
        pid=p["cths_person_id"]
        source=per_source[p["source_raw_html_sha256"]]
        text=source["bibliography_text"]
        source_flags={name:int(bool(re.search(pattern,text))) for name,pattern in ACADEMY_INDEX_RULES}
        other_flags={name:int(bool(re.search(pattern,text))) for name,pattern in BROAD_CATEGORIES}
        identity=identity_key(p["name"])
        elected=indexes.get(identity,[])
        if len(elected)>1:raise RuntimeError("Ambiguous official same-name match without year adjudication")
        verified=bool(elected)
        cthsyear=int(p["CTHS_roster_year_provisional"])
        birthyear_elected=(int(elected[0]["birth_year_in_selected_source_candidate"])
                           if verified and elected[0]["birth_year_in_selected_source_candidate"] else None)
        birthyear_disagree=bool(birthyear_elected is not None and birthyear_elected!=cthsyear)
        if birthyear_disagree:
            verified=False
        claim=p["cths_exact_dob_claim_candidate_only"]
        item={
            "cths_person_id":pid,
            "cths_name":p["name"],
            "cths_birth_year_candidate":cthsyear,
            "cths_date_claim_candidate_only":claim,
            "cths_membership_class_provisional":p["CTHS_roster_membership_class_provisional"],
            "cths_source_url":p["url"],
            "cths_html_sha256":p["source_raw_html_sha256"],
            "cths_bibliography_section_present":source["bibliography_source_found"],
            "cths_bibliography_sha256":source["bibliography_raw_sha256"],
            "cths_bibliography_editor_academy_claim":source["bibliography_editor_academy_mentioned"],
            **source_flags,
            **other_flags,
            "any_cited_official_historical_member_directory":int(any(source_flags.values())),
            "strict_160_firstparty_name_match":int(verified),
            "strict_160_name_match_without_birthyear_check":int(bool(elected)),
            "firstparty_name_match_birthyear_conflict":int(birthyear_disagree),
            "firstparty_source_doc":elected[0]["source_document_id"] if elected else "",
            "firstparty_election_year":elected[0]["election_year"] if elected else "",
            "original_archive_source_verified":1,
            "official_full_member_accepted_by_this_pass":0,
            "exact_DOB_accepted_by_this_pass":0,
        }
        out.append(item)
        for k,v in source_flags.items():official_index_hits[k]+=v
        for k,v in other_flags.items():general_hits[k]+=v
        if not source["bibliography_source_found"]:notfound+=1
        if verified:matches.append(item)
        if birthyear_disagree:unmatched.append(item)
        buckets[p["CTHS_roster_year_provisional"][:3]+"0s"]+=1

    OUT_PARENT=args.out
    OUT_PARENT.mkdir(parents=True,exist_ok=True)
    cols=list(out[0])
    save_csv(OUT_PARENT/"cths_562_cited_source_metadata_v1.csv",out,cols)
    save_csv(OUT_PARENT/"firstparty_election_identity_intersection_v1.csv",matches,cols)
    save_csv(OUT_PARENT/"firstparty_name_year_conflicts_v1.csv",unmatched,cols)
    highpriority=[r for r in out if r["any_cited_official_historical_member_directory"]
                  or r["cths_bibliography_editor_academy_claim"]]
    save_csv(OUT_PARENT/"institutional_directory_citation_review_queue_v1.csv",highpriority,cols)
    summary={
        "version":VERSION,
        "audit_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
        "offline_network_requests":0,
        "raw_cths_archived_biographies_verified":len(archived),
        "CTHS_people":len(people),
        "source_bibliography_section_missing":notfound,
        "cited_Academy_historical_directory_counts":dict(official_index_hits),
        "cited_other_source_category_counts":dict(general_hits),
        "cths_academy_editor_leads":sum(x["cths_bibliography_editor_academy_claim"] for x in out),
        "any_cited_Academy_historical_directory":sum(x["any_cited_official_historical_member_directory"] for x in out),
        "high_priority_directory_citation_review_people":len(highpriority),
        "firstparty_160_strict_name_match_to_CTHS_562":len(matches),
        "name_match_year_conflicts_quarantined":len(unmatched),
        "firstparty_source_160_not_all_memberships_confirmed":True,
        "source_directory_citation_not_independent_DOB_confirmation":True,
        "accepted_exact_DOB_count":0,
        "accepted_official_membership_count":0,
        "bazi_variables_computed":0,
        "warning":"CTHS bibliography mentions are just leads. Merely naming the 1979/1989/1993/1994/2008 Academy indices does NOT show a specific DOB/election-year field was checked in the original publication.",
    }
    (OUT_PARENT/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2),flush=True)


if __name__=="__main__":main()
