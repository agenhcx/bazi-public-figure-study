#!/usr/bin/env python3
"""1900 Tome131: source-specific correction of a wrapped nomination index row.

Do not re-fetch all 16 prespecified Shard03 volumes. Fetch ONE public TOC
and replay new parser; immutable original Shard03 61-row ledger remains untouched.
Then emit one additive source-and-parser-correction overlay with old vs new
role and original printed page. Explicit 2-line context; no study admission.
"""
from __future__ import annotations
import argparse,csv,hashlib,json,time,re,urllib.error
from pathlib import Path
from bs4 import BeautifulSoup
from france_academy_wikisource_index_preflight_v1 import build_urls,read_one
from france_academy_wikisource_legacy_election_headings_v1 import parse_html

V="france-academy-1900-Zambacco-two-index-row-join-QA-v1"
ORIGINAL=Path("data/france_academy_remaining_172_toc_batch_v1/shard_03")
OUT=Path("data/france_academy_shard03_Zambacco_source_overlay_v1")
COLS=["volume","year","source_name_form","original_SHARD03_role","new_conservative_role",
      "original_SHARD03_printed_page","new_original_printed_page_claim",
      "new_section","first_source_row_excerpt","second_continuation_excerpt",
      "original_shard03_source_SHA256","recheck_source_SHA256",
      "original_source_HTML_bytes_same","source_index_page_url",
      "source_event_scan_opened","person_full_identity_resolved",
      "final_member_accepted","final_DOB_accepted","bazi_features"]

def readcsv(p):
    with p.open(encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
def source_two_rows(raw):
    soup=BeautifulSoup(raw,"html.parser")
    result=[]
    trs=soup.find_all("tr")
    for i,tr in enumerate(trs):
        td=tr.find_all("td",recursive=False)
        if not td:continue
        text=" ".join(td[0].get_text(" ",strip=True).split())
        if "Zambacco" in text and re.search(r"\best\s+[ée]lu\b",text,re.I):
            next_text=""
            for sibling in trs[i+1:i+2]:
                next_cells=sibling.find_all("td",recursive=False)
                if next_cells:next_text=" ".join(next_cells[0].get_text(" ",strip=True).split())
            result.append((text,next_text))
    return result
def fixture():
    html=("<table><tr><td><span class='sc'>Nominations.</span> — M. Zambacco est élu</td><td></td></tr>"
          "<tr><td>Correspondant pour la Section de Médecine et Chirurgie</td><td>22</td></tr></table>").encode("utf8")
    p,heads=parse_html(html,131,1900)
    assert len(p)==1 and p[0]["elected_name_candidate"]=="Zambacco",p
    assert p[0]["election_role_candidate"]=="CORRESPONDENT" and p[0]["original_printed_volume_page"]=="22",p
    assert len(source_two_rows(html))==1
    print("PASS: adjacent explicit member-role continuation joins only one source election")
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--fixture-check",action="store_true")
    ap.add_argument("--out",type=Path,default=OUT)
    a=ap.parse_args()
    if a.fixture_check:return fixture()
    old=readcsv(ORIGINAL/"verified_transcribed_person_event_candidates_v1.csv")
    original_candidates=[x for x in old if x["volume"]=="131" and x["name_as_transcribed"]=="Zambacco"]
    if len(old)!=61 or len(original_candidates)!=1:raise RuntimeError("Unchanged pre-fix 61 event ledger required")
    before=original_candidates[0]
    if before["member_role_source_candidate"]!="UNKNOWN_ROLE_MANUAL" or before["first_printed_page_candidate"]:
        raise RuntimeError("Original source omission already fixed or manifest changed")
    url=build_urls(131,1900)["wiki"]
    status,mime,raw=read_one(url,900000)
    if status!=200:raise RuntimeError("Official journal TOC transcription not accessible")
    sha=hashlib.sha256(raw).hexdigest()
    parsed,heads=parse_html(raw,131,1900)
    current=[x for x in parsed if x["elected_name_candidate"]=="Zambacco"]
    if len(current)!=1 or current[0]["election_role_candidate"]!="CORRESPONDENT" or current[0]["original_printed_volume_page"]!="22":
        soup=BeautifulSoup(raw,"html.parser")
        allrows=soup.find_all("tr")
        diagnostics=[]
        for i,tr in enumerate(allrows):
            if "Zambacco" not in tr.get_text(" ",strip=True):continue
            for adj in allrows[max(0,i-1):i+4]:
                td=adj.find_all("td",recursive=False)
                diagnostics.append({"cells":[x.get_text(" ",strip=True)[:350] for x in td],
                                    "html_excerpt":str(adj)[:1050]})
        print("ORIGINAL_ZAMBACCO_HTML_DOM",json.dumps(diagnostics,ensure_ascii=False),flush=True)
        rawhtml=raw.decode("utf-8","replace")
        pos=rawhtml.find("Zambacco</i> est élu")
        if pos<0:pos=rawhtml.find("Zambacco")
        print("ORIGINAL_ZAMBACCO_HTML_NEIGHBORS",rawhtml[max(0,pos-190):pos+690] if pos>=0 else "NO_HTML_TEXT",flush=True)
        raise RuntimeError("Did not confirm original second-row role and printed page in live 1900 text: "+repr(current))
    pair=source_two_rows(raw)
    if len(pair)!=1 or "Correspondant" not in pair[0][1]:
        raise RuntimeError("Original source row pair absent or split in a different way")
    row={"volume":"131","year":"1900","source_name_form":"Zambacco",
         "original_SHARD03_role":before["member_role_source_candidate"],
         "new_conservative_role":current[0]["election_role_candidate"],
         "original_SHARD03_printed_page":before["first_printed_page_candidate"],
         "new_original_printed_page_claim":"22",
         "new_section":current[0]["science_section_candidate"],
         "first_source_row_excerpt":pair[0][0][:220],
         "second_continuation_excerpt":pair[0][1][:220],
         "original_shard03_source_SHA256":before["source_html_sha256"],
         "recheck_source_SHA256":sha,
         "original_source_HTML_bytes_same":str(int(sha==before["source_html_sha256"])),
         "source_index_page_url":url,
         "source_event_scan_opened":"0","person_full_identity_resolved":"0",
         "final_member_accepted":"0","final_DOB_accepted":"0","bazi_features":"0"}
    a.out.mkdir(parents=True,exist_ok=True)
    with (a.out/"Zambacco_1900_single_event_source_role_correction_v1.csv").open("w",encoding="utf-8-sig",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=COLS);writer.writeheader();writer.writerow(row)
    summary={"version":V,"original_shard03_event_rows":61,
       "original_role_counts":{"UNKNOWN_ROLE_MANUAL":1,"CORRESPONDENT":46},
       "new_role_counts_for_61_shard03_events":{"UNKNOWN_ROLE_MANUAL":0,"CORRESPONDENT":47},
       "original_index_event_count_change":0,"original_1853_1884_1899_source_overlays_separate":True,
       "person_source":[row],"source_SHA256":sha,
       "firstparty_original_printed_page_directly_opened":0,
       "membership_accepted":0,"birthdate_accepted":0,"bazi_features":0}
    (a.out/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    print("ZAMBACCO_INDEX_CORRECTION",json.dumps({"person":row["source_name_form"],"role":row["new_conservative_role"],
           "page":row["new_original_printed_page_claim"],
           "original_source_bytes_same":row["original_source_HTML_bytes_same"]},ensure_ascii=False))
if __name__=="__main__":main()
