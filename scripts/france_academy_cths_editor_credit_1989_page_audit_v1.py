#!/usr/bin/env python3
"""Re-audit editorial attribution and directory page leads in 562 archived CTHS pages.

An offline, SHA-audited correction to the earlier CTHS bibliography script's
incorrect detection of literal 'Rédacteur(s) de la notice'. Source-only evidence:
an Academy-credited notice does not prove original Academy membership election
or BIRTH evidence independence. NO cohort admission, DOB changes or BaZi.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import re
import tarfile
from collections import Counter
from pathlib import Path

from bs4 import BeautifulSoup
from ftfy import fix_text
from france_academy_cths_original_citation_audit_v1 import fold

V = "france-academy-cths-562-editor-origin-source-only-v1_1"
DATA = Path("data/france_academy_cths_profile_dob_harvest_v1")
SOURCES = DATA / "cths_dob_claims_all_targets_candidate_only_v1.csv"
MANIFEST = DATA / "summary.json"
ARCHIVE = DATA / "cths_profile_source_html_sha256_bundle_v1.tar.gz"
CITATION = Path("data/france_academy_cths_historical_source_citation_audit_v1/institutional_directory_citation_review_queue_v1.csv")
OUT = Path("data/france_academy_cths_editor_origin_audit_v1")
AUTH = re.compile(r"\bredacteur(?:\s*\(\s*s\s*\)|s)?\s*(?:de\s+la\s+notice)?\s*:\s*(.{0,240}?)\s+fiche\s+creee\b", re.I)
AUTH_FALLBACK = re.compile(r"\bredacteur(?:\s*\(\s*s\s*\)|s)?\s*(?:de\s+la\s+notice)?\s*:\s*(.{0,120})", re.I)
ACADEMY = re.compile(r"\bacademie\s+des\s+sciences\b")
R1989 = re.compile(r"repertoire\s+biographique.{0,155}\bacademie\s+des\s+sciences.{0,150}\b1989\b", re.I)
PAGE = re.compile(r"\b1989\s*[,;]?\s*p(?:ages?)?\.?\s*(\d{1,3})(?:\s*[-–]\s*(\d{1,3}))?", re.I)
COLS = ["cths_person_id","cths_name","cths_birthyear","cths_membership_class_provisional",
        "cths_editor_credit_category","institutional_editor_credit_tier","cths_editor_credit_short",
        "credit_field_parse_status","cths_1989_directory_cited","cths_1989_print_page_range_candidate",
        "original_1989_directory_entry_opened","cths_profile_url","cths_html_sha256",
        "academy_full_membership_accepted","exact_dob_accepted","bazi_variables_computed"]


def load(path):
    with Path(path).open(encoding="utf-8-sig",newline="") as f:
        return list(csv.DictReader(f))


def output(path, rows, cols):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=cols,extrasaction="ignore")
        w.writeheader();w.writerows(rows)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def digest_file(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda:f.read(1024*1024),b""):h.update(block)
    return h.hexdigest()


def extract(raw):
    soup=BeautifulSoup(fix_text(raw.decode("cp1252",errors="replace")),"html.parser")
    txt=fold(soup.get_text(" ",strip=True))
    found=AUTH.search(txt)
    if found:
        credit=" ".join(found.group(1).split())[:120]
        parser_status="FIELD_BOUNDED_TO_FICHE_CREEE"
    else:
        fallback=AUTH_FALLBACK.search(txt)
        credit=" ".join(fallback.group(1).split())[:120] if fallback else ""
        parser_status="FIELD_UNBOUNDED_MANUAL" if fallback else "FIELD_NOT_FOUND"
    if not credit:
        category="NO_EXPLICIT_EDITOR_CREDIT"
    elif ACADEMY.search(credit) and parser_status=="FIELD_BOUNDED_TO_FICHE_CREEE":
        category="ACADEMY_CREDITED_NOTICE_CANDIDATE"
    elif parser_status!="FIELD_BOUNDED_TO_FICHE_CREEE":
        category="EDITOR_FIELD_MANUAL_REVIEW"
    else:
        category="OTHER_CREDITED_NOTICE"
    bibli=soup.find(id="proso_sources_biographiques") or soup.find(id="fieldset_sources_biographiques")
    bibli_text=fold(bibli.get_text(" ",strip=True)) if bibli is not None else ""
    cited=bool(R1989.search(bibli_text))
    page=""
    if cited:
        m=PAGE.search(bibli_text)
        if m:
            p1=int(m.group(1));p2=int(m.group(2) or p1)
            if 1<=p1<=999 and p1<=p2<=999:
                page=str(p1)+("-"+str(p2) if p2!=p1 else "")
    institutional_tier=("ACADEMY_EXPLICIT" if category=="ACADEMY_CREDITED_NOTICE_CANDIDATE" else
                        "INSTITUT_UMBRELLA_EXPLICIT" if parser_status=="FIELD_BOUNDED_TO_FICHE_CREEE" and "institut de france" in credit else
                        "OTHER_NAMED_EDITOR" if category=="OTHER_CREDITED_NOTICE" else "NONE_OR_UNCERTAIN")
    return {"category":category,"institutional_tier":institutional_tier,"credit":credit,"status":parser_status,
            "cited1989":int(cited),"page1989":page}


def synthetic():
    def sample(s):
        return "<html><div id='proso_sources_biographiques'>"+s+"</div>"+(
            "Rédacteur(s) de la notice : Académie des sciences, Bruno Delmas "
            "Fiche créée le 12/11/2012 - Dernière mise à jour le 02/10/2023")+"</html>"
    first=sample("Répertoire biographique des membres de l'Académie des Sciences, Paris, 1989, p. 81-82")
    found=extract(first.encode("utf-8"))
    assert found["category"]=="ACADEMY_CREDITED_NOTICE_CANDIDATE"
    assert found["credit"]=="academie des sciences, bruno delmas"
    assert found["status"]=="FIELD_BOUNDED_TO_FICHE_CREEE"
    assert found["page1989"]=="81-82" and found["cited1989"]==1
    second=extract(sample("Répertoire biographique des membres et membres correspondants de l'Académie des Sciences, 1993").replace("Académie des sciences, Bruno Delmas","Autre historien").encode("utf-8"))
    assert second["category"]=="OTHER_CREDITED_NOTICE" and second["cited1989"]==0
    umbrella=extract(sample("Répertoire biographique des membres de l\'Académie des Sciences, Paris, 1989, p. 81-82").replace("Académie des sciences, Bruno Delmas","Institut de France, Bruno Delmas").encode("utf-8"))
    assert umbrella["institutional_tier"]=="INSTITUT_UMBRELLA_EXPLICIT"
    third=extract(b"<html><body>Biography no explicit editor. Fiche creee le 2012</body></html>")
    assert third["category"]=="NO_EXPLICIT_EDITOR_CREDIT"
    print("PASS: literal Rédacteur(s), editor-field boundary, 1989 source page, no false membership acceptance")


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--fixture-check",action="store_true")
    ap.add_argument("--out",type=Path,default=OUT)
    ap.add_argument("--limit",type=int,default=0,help="0 means all 562; otherwise first N sorted IDs")
    args=ap.parse_args()
    if args.fixture_check:
        synthetic();return
    expected=json.loads(MANIFEST.read_text(encoding="utf-8"))
    originals=load(SOURCES)
    leads=load(CITATION)
    if len(originals)!=562 or len(leads)!=130:raise RuntimeError("Frozen CTHS source counts changed")
    if digest_file(ARCHIVE)!=expected["raw_html_bundle_sha256"]:
        raise RuntimeError("Archive SHA256 does not match frozen original")
    shas={x["source_raw_html_sha256"] for x in originals}
    if len(shas)!=562 or any(len(x)!=64 for x in shas):
        raise RuntimeError("Source person SHA256 audit failed")
    seen={}
    with tarfile.open(ARCHIVE,"r:gz") as archive:
        for entry in archive:
            if not entry.isfile() or len(Path(entry.name).parts)!=2 or Path(entry.name).parts[0]!="source_html":
                raise RuntimeError("Invalid source archive member")
            source_sha=Path(entry.name).stem
            if source_sha in seen:raise RuntimeError("Duplicate source file")
            fp=archive.extractfile(entry)
            if fp is None:raise RuntimeError("Missing archived HTML")
            raw=fp.read()
            if digest(raw)!=source_sha:raise RuntimeError("Original CTHS HTML digest changed")
            seen[source_sha]=extract(raw)
    if set(seen)!=shas:raise RuntimeError("Source snapshot person mapping incomplete")
    by_lead={x["cths_person_id"]:x for x in leads}
    subset1989={x["cths_person_id"] for x in leads if x.get("academy_member_only_1989")=="1"}
    if len(subset1989)!=17:raise RuntimeError("1989 priority subset changed")
    rows=[]
    for person in sorted(originals,key=lambda r:int(r["cths_person_id"])):
        pid=person["cths_person_id"]
        s=seen[person["source_raw_html_sha256"]]
        lead=by_lead.get(pid)
        if pid in subset1989 and not s["cited1989"]:
            raise RuntimeError("Original 1989 bibliographic positive not replayable for CTHS "+pid)
        rows.append({
            "cths_person_id":pid,"cths_name":person["name"],
            "cths_birthyear":person["CTHS_roster_year_provisional"],
            "cths_membership_class_provisional":person["CTHS_roster_membership_class_provisional"],
            "cths_editor_credit_category":s["category"],
            "institutional_editor_credit_tier":s["institutional_tier"],
            "cths_editor_credit_short":s["credit"],
            "credit_field_parse_status":s["status"],
            "cths_1989_directory_cited":int(pid in subset1989),
            "cths_1989_print_page_range_candidate":s["page1989"] if pid in subset1989 else "",
            "original_1989_directory_entry_opened":"0",
            "cths_profile_url":person["url"],
            "cths_html_sha256":person["source_raw_html_sha256"],
            "academy_full_membership_accepted":"0","exact_dob_accepted":"0","bazi_variables_computed":"0"
        })
    if args.limit and 1<=args.limit<=562:
        rows=rows[:args.limit]
    out=args.out
    output(out/"cths_562_editor_authority_evidence_v1.csv",rows,COLS)
    pick=[x for x in rows if x["cths_person_id"] in subset1989]
    output(out/"cths_1989_member_only_17_print_page_locator_v1.csv",pick,COLS)
    counts=Counter(x["cths_editor_credit_category"] for x in rows)
    base1989=Counter(x["cths_editor_credit_category"] for x in pick)
    tiers=Counter(x["institutional_editor_credit_tier"] for x in rows)
    tiers1989=Counter(x["institutional_editor_credit_tier"] for x in pick)
    credited=sum(tiers[k] for k in ("ACADEMY_EXPLICIT","INSTITUT_UMBRELLA_EXPLICIT"))
    pages=sum(bool(x["cths_1989_print_page_range_candidate"]) for x in pick)
    if any(x["academy_full_membership_accepted"]!="0" or x["exact_dob_accepted"]!="0" or x["bazi_variables_computed"]!="0" for x in rows):
        raise RuntimeError("Study admission changed during editor metadata audit")
    summary={
        "version":V,"offline_network_requests":0,
        "cths_source_562_reverified":len(seen),
        "selected_rows":len(rows),"priority_1989_people_in_output":len(pick),
        "academy_editor_credit_counts":dict(counts),
        "1989_priority_editor_credit_counts":dict(base1989),
        "institutional_editor_tier_counts":dict(tiers),
        "1989_priority_institutional_editor_tier_counts":dict(tiers1989),
        "academy_or_institut_editor_credited":credited,
        "1989_priority_people_with_candidate_original_book_page":pages,
        "old_v1_editor_credit_zero_was_parser_false_negative_candidate":True,
        "source_archive_sha256":digest_file(ARCHIVE),
        "source_independence": "Academy-editor credit is institution-attributed CTHS secondary presentation; not inspected original election minutes",
        "original_1989_book_pages_opened":0,
        "official_full_member_study_accepted":0,"study_exact_dob_accepted":0,"bazi_variables_computed":0
    }
    out.mkdir(parents=True,exist_ok=True)
    (out/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("SUMMARY",json.dumps(summary,ensure_ascii=False))
    print("1989_ORIGINAL_PAGE_LEADS",json.dumps([
        {"id":x["cths_person_id"],"name":x["cths_name"],
         "academy_editor":x["cths_editor_credit_category"],"institutional_tier":x["institutional_editor_credit_tier"],"printed_page":x["cths_1989_print_page_range_candidate"]}
        for x in pick],ensure_ascii=False))


if __name__=="__main__":
    main()
