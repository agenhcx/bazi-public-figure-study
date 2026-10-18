#!/usr/bin/env python3
"""Audit the 2022 Leridon article ANNEX methodology without harvesting member DOBs.

One official HAL manuscript PDF request, exact source SHA256 pinned to the
previous verified source. Read ANNEX pages only. Write limited paragraph
snippets about member categories/fields and sample sizes for human audit.
No full PDF bytes/source prose are redistributed or committed.
"""
from __future__ import annotations
import datetime as dt, hashlib, json, re
from pathlib import Path
import fitz
import requests

URL="https://hal.science/hal-03763832v1/file/Leridon_Demographie-Academie-des-Sciences_version-AA_01-2022.pdf"
SHA="04ac1259f3488a0b88f9fbb4befd238df2f298821a65bf59e7dd7f1ec8f6b752"
OUT=Path("data/france_academy_leridon_historical_master_source_pilot_v1")
NEEDLES=[
 ("strict_2004","L’étude de 2002-2004"),
 ("2018_2020","L’étude de 2018-2020"),
 ("digital_file","fichier numérique complet"),
 ("member_types","Membres au sens strict"),
 ("birth_data","date de naissance"),
 ("dates_birth","dates de naissance"),
 ("data_collection","saisie"),
 ("new_2016_period","2016"),
 ("study_population_3218","3218"),
 ("members_1039","1039"),
]
def main():
    r=requests.get(URL,timeout=30,allow_redirects=False)
    r.raise_for_status()
    b=r.content
    actual=hashlib.sha256(b).hexdigest()
    if actual!=SHA:raise SystemExit("HAL manuscript source digest changed; review source version before continuing")
    doc=fitz.open(stream=b,filetype="pdf")
    assert len(doc)==41
    results=[]
    for pageno in range(34,41):
        s=" ".join(doc[pageno].get_text("text",sort=True).replace("\u00ad","").split())
        for field,needle in NEEDLES:
            pos=s.casefold().find(needle.casefold())
            if pos<0:continue
            # Human-readable excerpt for evidence-review, not a full copied page
            excerpt=s[max(0,pos-60):min(len(s),pos+260)]
            results.append({"page_zero_based":pageno,"term":field,"near_source_phrase":excerpt})
    summary={
      "version":"france-academy-leridon-2022-appendix-methodology-v1",
      "utc":dt.datetime.now(dt.timezone.utc).isoformat(),
      "source_url":URL,"source_sha256":actual,"source_pdf_pages":len(doc),
      "appendix_page_start_zero_based":34,
      "methodology_clues":results,
      "individually_named_3218_academy_people_retrieved":0,
      "full_individual_excel_file_obtained":False,
      "independent_birthdate_verifications":0,
      "member_election_adjudications":0,
      "bazi_variables_computed":0,
      "warning":"Author article offers descriptive method and aggregate data, not the original 3218-person Excel. The archived Academy full roster requires separate source access and legal rights check."
    }
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/"appendix_methodology_summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"pdf_pages":len(doc),"method_clues":len(results),
      "seen_labels":[{"page":x["page_zero_based"],"term":x["term"],"excerpt":x["near_source_phrase"][:190]} for x in results]},
      ensure_ascii=False,indent=2))
if __name__=="__main__":main()
