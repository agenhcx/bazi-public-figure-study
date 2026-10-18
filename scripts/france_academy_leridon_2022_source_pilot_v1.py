#!/usr/bin/env python3
"""Probe the two legitimate open manuscript hosts for Henri Leridon's 2022
Academy historical-demography paper and its 1666-2016 prosopographical annex.

Bounded 1 HTTP request per distinct host. No CAPTCHA/anti-bot bypass.
Save only a source fingerprint, page count and short methodology excerpts.
Source is a descriptive scholarly paper, *not* the original individual-level
master roster; no DOB or membership status is accepted.
"""
from __future__ import annotations
import argparse, datetime as dt, hashlib, json, re, time
from pathlib import Path
from urllib.parse import urlparse
import requests

OUT=Path("data/france_academy_leridon_historical_master_source_pilot_v1")
ART={
 "title":"Démographie de l'Académie des sciences (Institut de France) de 1666 à 2017, et perspectives",
 "author":"Henri Leridon",
 "journal":"Archives Internationales d'Histoire des Sciences",
 "year":2022,
 "doi":"10.1484/J.ARIHS.5.129761",
 "paper_is_same_as_member_file":False,
 "member_file_annex_period":"1666-2016",
 "archive_homepage":"https://archives.academie-sciences.fr/",
 "archive_entry_discovered_unverified":"https://archives.academie-sciences.fr/n/fichier-des-membres-de-l-academie-issu-de-l-index-biographique-par-henri-leridon/n:155",
}
HOSTS={
 "ined_archined":"https://archined.ined.fr/download/publication/AYLe1nW7eogrXWkVh1EU/c5471953cdf142a46ed91c363bd115531661789184620.pdf",
 "hal_open_archive":"https://hal.science/hal-03763832v1/file/Leridon_Demographie-Academie-des-Sciences_version-AA_01-2022.pdf",
}
MARKERS=[
 "ANNEXE", "numérisation des notices", "2018-2020", "2002-2004",
 "fichier numérique complet", "les personnes ayant appartenu", "1039",
 "3160", "3230", "Membres au sens strict",
]
def metadata_for_text(doc):
    pages=[]
    for i in range(len(doc)):
        page=doc[i].get_text("text",sort=True)
        s=" ".join(page.replace("\u00ad","").split())
        l=s.lower()
        hits=[]
        for marker in MARKERS:
            pos=l.find(marker.lower())
            if pos>=0: hits.append({"term":marker,"nearby":s[max(0,pos-85):min(len(s),pos+190)]})
        if hits:
            pages.append({"pdf_page_zero_based":i,"marker_contexts":hits[:7]})
    return pages

def probe()->dict:
    import fitz
    sources=[]
    for j,(name,url) in enumerate(HOSTS.items()):
        if j:time.sleep(1.3)
        result={"source_host_id":name,"source_url":url,"status":"NOT_ATTEMPTED",
                "http_code":None,"pdf_sha256":"","pdf_page_count":0,
                "pdf_pages_with_methods_markers":[],"error":""}
        try:
            r=requests.get(url,timeout=24,allow_redirects=False,
                headers={"User-Agent":"bazi-public-figure-study/1.0 noncommercial academic-source reproducibility audit"})
            result["http_code"]=r.status_code
            if r.status_code!=200:
                result["status"]="HTTP_BLOCKED_OR_UNAVAILABLE"
            elif not r.content.startswith(b"%PDF-") or len(r.content)>12_000_000:
                result["status"]="UNEXPECTED_NON_PDF_RESPONSE"
            else:
                p=fitz.open(stream=r.content,filetype="pdf")
                if p.needs_pass or len(p)<20 or len(p)>100:
                    result["status"]="UNEXPECTED_PAGE_COUNT_OR_ENCRYPTION"
                else:
                    result["status"]="OPEN_MANUSCRIPT_RETRIEVED"
                    result["pdf_sha256"]=hashlib.sha256(r.content).hexdigest()
                    result["pdf_page_count"]=len(p)
                    result["pdf_pages_with_methods_markers"]=metadata_for_text(p)
            print(name,result["status"],result["http_code"],flush=True)
        except Exception as e:
            result["status"]="NETWORK_OR_PARSER_ERROR"
            result["error"]=type(e).__name__+": "+str(e)[:180]
            print(name,result["status"],flush=True)
        sources.append(result)
    return {
       "version":"france-academy-leridon-2022-master-archive-source-pilot-v1",
       "checked_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
       "paper_metadata":ART,
       "probed_exactly_two_hosts":True,
       "number_of_http_requests":len(HOSTS),
       "source_statuses":sources,
       "pdfs_retrieved":sum(x["status"]=="OPEN_MANUSCRIPT_RETRIEVED" for x in sources),
       "individual_level_academy_roster_retrieved":False,
       "historical_member_category_adjudications":0,
       "accepted_person_DOBs":0,
       "bazi_variables_computed":0,
       "note":"Annex methodology extraction is NOT retrieval of underlying Academy member Excel/file; 2004 strict-only and later all-status datasets have different denominators."
    }
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--fixture-check",action="store_true")
    ap.add_argument("--probe",action="store_true")
    args=ap.parse_args()
    if args.fixture_check:
        assert ART["doi"] and ART["member_file_annex_period"]=="1666-2016"
        for name,url in HOSTS.items():
            p=urlparse(url)
            assert p.hostname in {"archined.ined.fr","hal.science"} and p.scheme=="https" and p.path.endswith(".pdf")
        print(json.dumps({"source_identity":ART,"network_requests":0,"hosts":list(HOSTS)},ensure_ascii=False,indent=2))
        return
    if not args.probe:raise SystemExit("Specify --probe or --fixture-check")
    data=probe()
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/"summary.json").write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"retrieved":data["pdfs_retrieved"],
       "hosts":[{"source":x["source_host_id"],"status":x["status"],"http":x["http_code"],"pages":x["pdf_page_count"]} for x in data["source_statuses"]]},
       ensure_ascii=False,indent=2))
if __name__=="__main__":main()
