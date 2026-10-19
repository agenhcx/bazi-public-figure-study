#!/usr/bin/env python3
"""Audit three historical French Academy TOCs erroneously parsed as zero events.

Revisit exactly volumes 37/1853, 98/1884, 128/1899 after grammar correction.
Source = French Wikisource transcription of original Académie des sciences
Comptes rendus index; DO NOT promote to original-page verified membership.
Preserve historical "office" vs member, libre vs section, correspondent and
partial name identity uncertainty. Python 3.10+ and BeautifulSoup4.
"""
from __future__ import annotations
import argparse,csv,hashlib,json,re,time,urllib.error
from collections import Counter
from pathlib import Path
from bs4 import BeautifulSoup
from france_academy_wikisource_legacy_election_headings_v1 import parse_html,fold
from france_academy_wikisource_index_preflight_v1 import read_one,build_urls
VERSION="france-academy-three-TOC-false-zeros-evidence-overlay-v1"
PAIRS=[(37,1853),(98,1884),(128,1899)]
BASE=Path("data/france_academy_remaining_172_toc_batch_v1/shard_02")
ORIGINAL_QUEUE=BASE/"shard02_source_parser_false_zero_review_queue_v1.csv"
OUT=Path("data/france_academy_nominations_37_98_128_recovery_v1")
FULL={"FULL_SECTION_MEMBER","FULL_NONRESIDENT_MEMBER","FULL_ACADEMICIAN_LIBRE",
      "FULL_SECTION_MEMBER_CONTEXTUAL_ELECTION","FULL_SECTION_MEMBER_CONTEXTUAL_NOMINATION"}
FIELDS=["volume","year","name_source_form","role_source_candidate","source_action_wording",
        "original_printed_page_claim","all_printed_page_claims","science_section_source_label",
        "index_context_short","name_fullness_review","original_index_source_url",
        "prior_source_HTML_sha256","newly_read_source_HTML_sha256","source_changed_since_shard02",
        "evidence_class","original_printed_election_page_directly_viewed",
        "accepted_full_member","accepted_DOB","bazi_features_computed"]
def file_rows(p):
    with p.open(encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
def save(path,rows,columns):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("w",encoding="utf-8-sig",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=columns,extrasaction="ignore")
        writer.writeheader();writer.writerows(rows)
def source_context(raw,name):
    soup=BeautifulSoup(raw,"html.parser")
    target=fold(name)
    for tr in soup.find_all("tr"):
        cells=tr.find_all("td",recursive=False)
        if not cells:continue
        line=" ".join(cells[0].get_text(" ",strip=True).split())
        if not re.search(r"\best\s+(?:élu|nommé)\b",line,re.I):continue
        if target in fold(line):
            return line[:320]
    return ""
def source_fullness(name):
    if name.startswith(("Le R. P. ","M. ","Cl. ","Ch. ","R. ")):
        return "ABBREVIATED_HISTORIC_SOURCE_NAME_IDENTITY_MANUAL"
    return "SOURCE_NAME_ONLY_IDENTITY_NOT_YET_CONFIRMED"
def fixture():
    from france_academy_wikisource_legacy_election_headings_v1 import event_heading
    from france_academy_wikisource_election_rows_v1 import role_of,person_of
    assert event_heading("Nominations de membres et correspondants de l’académie.")
    assert event_heading("Nominations.")
    assert not event_heading("Nominations de candidats au concours")
    assert role_of("— M. Haton est élu Membre libre")=="FULL_ACADEMICIAN_LIBRE"
    assert role_of("— M. Darboux est élu Membre de la Section de Géométrie")=="FULL_SECTION_MEMBER"
    assert role_of("— M. Élie de Beaumont est élu à la place de Secrétaire perpétuel")=="OFFICE_ELECTION_NOT_NEW_MEMBER"
    assert person_of("— Le R. P. Colin est élu Correspondant pour la Section de Géographie")=="Le R. P. Colin"
    assert len(PAIRS)==3 and all(y in (1853,1884,1899) for _,y in PAIRS)
    print("PASS: 1853 office, 1884 membre libre, 1899 correspondent and historical no-de title variant")
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--fixture-check",action="store_true")
    p.add_argument("--limit",type=int,default=3)
    p.add_argument("--delay",type=float,default=1.5)
    p.add_argument("--timeout",type=int,default=20)
    p.add_argument("--out",type=Path,default=OUT)
    a=p.parse_args()
    if a.fixture_check:return fixture()
    if not 1<=a.limit<=3 or a.delay<1.1:raise ValueError("Only 3 bounded historical TOCs")
    prior=file_rows(ORIGINAL_QUEUE)
    baseline={int(x["volume"]):x for x in prior if int(x["volume"]) in (37,98,128)}
    if len(baseline)!=3 or any(x["number_of_index_events_parsed"]!="0" for x in baseline.values()):
        raise RuntimeError("Prior original zero-parser cases changed")
    records=[];audits=[]
    for index,(v,y) in enumerate(PAIRS[:a.limit]):
        if index:time.sleep(a.delay)
        url=build_urls(v,y)["wiki"]
        try:
            status,mime,raw=read_one(url,900000)
            if status!=200:raise ValueError("TOC source not HTTP200")
            h=hashlib.sha256(raw).hexdigest()
            old=baseline[v]["TOC_SHA256"]
            events,heads=parse_html(raw,v,y)
            if not heads:
                raise RuntimeError("Corrected election/nomination heading not recognized in source")
            for e in events:
                name=e["elected_name_candidate"]
                if not name:raise RuntimeError("Not safe to publish a historical event without named identity")
                records.append({
                    "volume":str(v),"year":str(y),"name_source_form":name,
                    "role_source_candidate":e["election_role_candidate"],
                    "source_action_wording":e["source_action_wording"],
                    "original_printed_page_claim":e["original_printed_volume_page"],
                    "all_printed_page_claims":e.get("source_printed_page_references",""),
                    "science_section_source_label":e["science_section_candidate"],
                    "index_context_short":source_context(raw,name),
                    "name_fullness_review":source_fullness(name),
                    "original_index_source_url":url,
                    "prior_source_HTML_sha256":old,
                    "newly_read_source_HTML_sha256":h,
                    "source_changed_since_shard02":"1" if h!=old else "0",
                    "evidence_class":"WIKISOURCE_ORIGINAL_ACADEMY_INDEX_TRANSCRIPTION_NOT_INSPECTED_EVENT_PAGE",
                    "original_printed_election_page_directly_viewed":"0",
                    "accepted_full_member":"0","accepted_DOB":"0",
                    "bazi_features_computed":"0"})
            audits.append({"volume":v,"year":y,"source_status":status,"source_SHA256":h,
                "prior_shard02_SHA256":old,"source_changed":h!=old,
                "source_URL":url,"recognized_headings":heads,
                "parsed_event_candidates":len(events),
                "event_role_counts":dict(Counter(e["election_role_candidate"] for e in events)),
                "source_transcript_header_year_may_be_mislabeled":v==37,
                "original_election_event_pages_directly_opened":0})
        except (urllib.error.HTTPError,urllib.error.URLError,TimeoutError,ValueError) as ex:
            audits.append({"volume":v,"year":y,"source_status":getattr(ex,"code",type(ex).__name__),
                           "source_unavailable_not_zero_elections":True,
                           "error_type":type(ex).__name__,"error_preview":str(ex)[:130]})
            break
    records.sort(key=lambda x:(int(x["volume"]),int(x["original_printed_page_claim"] or 0),x["name_source_form"]))
    a.out.mkdir(parents=True,exist_ok=True)
    save(a.out/"recovered_historical_nomination_election_index_events_v1.csv",records,FIELDS)
    cnt=Counter(x["role_source_candidate"] for x in records)
    s={"version":VERSION,
       "scope":"exactly 3 historical journal TOC pages, formerly incorrectly parsed as no events",
       "original_frozen_shard02_source_rows_not_overwritten":True,
       "sources":audits,"source_html_read_success_count":sum(x.get("source_status")==200 for x in audits),
       "event_candidate_rows_recovered":len(records),
       "role_counts":dict(cnt),"full_like_source_rows":sum(cnt[k] for k in FULL),
       "correspondent_rows":cnt["CORRESPONDENT"],
       "office_elections_not_new_full_members":cnt["OFFICE_ELECTION_NOT_NEW_MEMBER"],
       "record_is_office_only_in_1853":True,
       "original_event_pages_opened":0,
       "study_member_acceptance":0,"study_dob_acceptance":0,"bazi_features":0}
    (a.out/"summary.json").write_text(json.dumps(s,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("RECOVERED",json.dumps({"records":len(records),"roles":dict(cnt),
       "per_source":[{"vol":x["volume"],"events":x.get("parsed_event_candidates"),"status":x["source_status"]} for x in audits]},ensure_ascii=False))
if __name__=="__main__":main()
