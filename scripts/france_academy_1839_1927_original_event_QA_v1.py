#!/usr/bin/env python3
"""Offline reproducible source-hash crosswalk for two inspected original journals.

Checks six publicly viewed 1839 Liouville and 1927 Fabry page images against
the raw source-acquisition manifests, historical election/approval separation,
and zero analytic cohort admission. The visual transcription is an authored
human observation, not a machine-generated conclusion.
"""
from __future__ import annotations
import csv,json
from pathlib import Path

ROOT=Path("data")
SRC=[
 ROOT/"france_academy_1839_1927_three_original_pages_v1/three_archival_original_scan_source_leads_v1.json",
 ROOT/"france_academy_1839_1927_original_supplement_v1/Liouville_vote_and_Fabry_original_page_supplement_v1.json",
 ROOT/"france_academy_fabry_1927_original_vote_decree_v1/original_source_page_scan_metadata_v1.json"]
QA=ROOT/"france_academy_1839_1927_original_event_QA_v1/six_firstparty_journal_scans_event_stage_review_v1.json"
CUM=ROOT/"france_academy_remaining_172_toc_batch_v1/cumulative_88_source_summary_v1.json"
def load(path):return json.loads(path.read_text(encoding="utf8"))
def main():
    a,b,c=[load(p) for p in SRC]
    q=load(QA);cum=load(CUM)
    hashes={}
    for r in a["source_records"]:
        if r.get("source_preview_sha256"):
            hashes[(r["volume"],r["original_printed_page_candidate"])]=(r["djvu_frame"],r["source_preview_sha256"])
    for r in b["source_records"]:
        if r.get("image_sha256"):
            hashes[(r["volume"],r["printed_page"])]=(r["frame"],r["image_sha256"])
    for r in c["records"]:
        if r.get("image_SHA256"):
            hashes[(c["volume"],r["printed_page_label"])]=(r["djvu_frame"],r["image_SHA256"])
    expected={(8,873),(8,874),(8,919),(184,1516),(184,1517),(184,1609)}
    if set(hashes)!=expected:raise RuntimeError("Missing or repeated first-party scan source pages")
    r=q["original_book_6_page_review"]
    if len(r)!=6 or {(x["volume"],x["printed_page"]) for x in r}!=expected:
        raise RuntimeError("Original six human-review page list differs from source capture")
    for p in r:
        v=(p["volume"],p["printed_page"])
        if not p["original_facsimile_directly_visually_reviewed"]:
            raise RuntimeError("Original source page review still pending "+str(v))
        if (p["djvu_frame"],p["image_SHA256"])!=hashes[v]:
            raise RuntimeError("Image SHA or frame disagrees with recorded public original "+str(v))
    assert q["Liouville_1839"]["vote_count"]=={
        "participating":51,"Liouville":29,"Pontecoulant":18,"Francoeur":2,"blank":2}
    assert q["Fabry_1927"]["vote_count"]=={
        "participating":54,"Fabry":51,"Abraham":1,"Langevin":1,"Sagnac":1}
    assert q["Fabry_1927"]["election_meeting_date"]=="1927-06-20"
    assert q["Fabry_1927"]["decree_date_quoted_in_original_journal"]=="1927-06-23"
    assert q["Fabry_1927"]["decree_read_and_seated_at_meeting_date"]=="1927-06-27"
    assert q["Liouville_1839"]["date_of_royal_decree_signed_verified"] is False
    assert q["Fabry_1927"]["separate_original_signed_presidential_decree_document_inspected"] is False
    assert q["Liouville_1839"]["within_1835_1985_research_birth_range"] is False
    assert q["Fabry_1927"]["within_1835_1985_research_birth_range"] is True
    fence=q["study_restrictions"]
    assert fence["new_cohort_members_accepted"]==fence["new_birthday_admissions"]==fence["bazi_variables_computed"]==0
    assert cum["unique_volumes_ever_TOC_probed"]==88
    assert cum["TOC_page_status_count"]=={"HTTP_200":63,"HTTP_404":25}
    assert cum["candidate_original_journal_INDEX_events_including_all_roles_and_offices"]==224
    assert cum["remaining_TOC_endpoints_never_tested"]==123
    print("PASS: six original scanned image SHA256/frame matches and two distinct first-party Academy event chains")
    print("PASS: Liouville 1839 29/51 vote royal confirmation, Fabry 1927 51/54 and dated approval decree")
    print("PASS: 88 historical TOC sources (63 readable/25 TOC404), 224 index event occurrences; NO study DOB/member/BaZi admission")
if __name__=="__main__":main()
