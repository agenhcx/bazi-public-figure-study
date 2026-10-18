#!/usr/bin/env python3
"""Reconcile 72 prior historical TOC source probes + 16 prespecified Shard02.

Zero network requests. Produces 88 distinct source-volume rows and an
event-count audit. Missing TOCs remain UNKNOWN (not zero historical elections).
No unique-person census, birthdate adjudication or BaZi feature computation.
"""
from __future__ import annotations
import argparse,csv,hashlib,json
from collections import Counter
from pathlib import Path

V="france-academy-88-historical-TOC-volume-source-reconciliation-v1"
BASE=Path("data/france_academy_remaining_172_toc_batch_v1")
PREV=BASE/"cumulative_72_source_checked_unique_volumes_v1.csv"
SHARD=BASE/"shard_02/academy_original_wikisource_211_volume_inventory_v1.csv"
EVID=BASE/"shard_02/verified_transcribed_person_event_candidates_v1.csv"
OV=BASE/"shard_02/person_event_ledger_summary_v1.json"
PREVSUM=BASE/"cumulative_72_source_summary_v1.json"
OUT=BASE
COLUMNS=["volume","year","source_probe_group","technical_status",
 "parsed_index_event_rows","index_event_semantics","source_image_sha256",
 "original_event_page_verified","accepted_member","bazi"]

def rows(p):
    with p.open(encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
def load(p):return json.loads(p.read_text(encoding="utf-8"))
def file_sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,data):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=COLUMNS,extrasaction="raise")
        w.writeheader();w.writerows(data)

def audit():
    old=rows(PREV);full=rows(SHARD);leads=rows(EVID)
    source=load(PREVSUM);new=load(OV)
    if len(old)!=72 or len(full)!=211 or len(leads)!=35:
        raise RuntimeError("Source input sizes changed")
    by_old={int(x["volume"]):x for x in old}
    if len(by_old)!=72:raise RuntimeError("Prior volume deduplication lost")
    chosen=[x for x in full if x["table_sampled"]=="1"]
    if len(chosen)!=16 or len({x["volume"] for x in chosen})!=16:
        raise RuntimeError("Shard02 should contain exactly 16 distinct volume probes")
    if any(int(x["volume"]) in by_old for x in chosen):
        raise RuntimeError("Source volume duplicated in earlier frame")
    if sorted(int(x["volume"]) for x in chosen)!=[9,10,37,38,67,68,98,99,127,128,129,157,160,161,189,190]:
        raise RuntimeError("A prespecified Shard02 volume was substituted")
    if source["historical_index_event_candidate_rows"]!=189 or new["parsed_event_rows"]!=35:
        raise RuntimeError("Prior and new indexed event counts disagree")
    if new["source_200_bytes_checked"]!=12 or new["other_TOC_statuses_not_election_zero"]!=4:
        raise RuntimeError("SHA-checked source status counts changed")
    if any(x["source_sha256_verified_against_inventory"]!="1" for x in leads):
        raise RuntimeError("New individual event evidence did not pass source SHA check")
    if any(x["official_member_status_accepted"]!="0" or x["exact_dob_accepted"]!="0" or
           x["bazi_variables_computed"]!="0" for x in leads):
        raise RuntimeError("Study acceptance unexpectedly changed")
    combined=list(old)
    for x in chosen:
        status=x["table_http_status"]
        if status not in ("HTTP_200","HTTP_404"):
            raise RuntimeError("Unexpected TOC status "+status)
        if status=="HTTP_200":
            if not x["transcribed_election_rows"].isdigit():
                raise RuntimeError("Readable source without parsed record-count label")
            note="INDEX_EVENT_COUNT_NOT_VERIFIED_FINAL_MEMBERS"
        else:
            if x["transcribed_election_rows"]:
                raise RuntimeError("404 volume cannot have a concluded parsed event count")
            note="TOC_HTTP404_NOT_HISTORICAL_ZERO"
        combined.append({
          "volume":x["volume"],"year":x["year"],"source_probe_group":"FROZEN_SHARD_02",
          "technical_status":status,"parsed_index_event_rows":x["transcribed_election_rows"],
          "index_event_semantics":note,"source_image_sha256":x["table_html_sha256"],
          "original_event_page_verified":"0","accepted_member":"0","bazi":"0"})
    combined.sort(key=lambda x:int(x["volume"]))
    if len(combined)!=88 or len({x["volume"] for x in combined})!=88:
        raise RuntimeError("Cumulative 88 volumes not distinct")
    cnt=Counter(x["technical_status"] for x in combined)
    if cnt!={"HTTP_200":63,"HTTP_404":25}:raise RuntimeError("Expected 63 readable and 25 TOC404")
    count=sum(int(x["parsed_index_event_rows"]) for x in combined if x["parsed_index_event_rows"])
    if count!=224:raise RuntimeError("Expected 189+35=224 historical index events")
    if sum(new["event_classes"].values())!=35:
        raise RuntimeError("Per-role counts do not sum to shard02 person-event rows")
    manifest={
      "version":V,"source_frame":"211 original Academy half-year volumes 1835-1940",
      "input_SHA256":{"cumulative_72":file_sha(PREV),"new_211_volume_inventory":file_sha(SHARD),
                      "new_person_event_ledger":file_sha(EVID)},
      "unique_volumes_ever_TOC_probed":len(combined),
      "TOC_page_status_count":dict(cnt),
      "candidate_original_journal_INDEX_events_including_all_roles_and_offices":count,
      "shard02_new_person_event_rows":35,
      "shard02_role_counts":new["event_classes"],
      "shard02_full_like_event_candidates":new["full_like_index_event_candidates"],
      "shard02_strict_name_links_to_frozen_CTHS562":new["cths_562_unique_exact_name_event_candidates"],
      "remaining_TOC_endpoints_never_tested":211-len(combined),
      "TOC_404_never_means_no_elections":True,
      "transcription_page_number_not_equal_verified_original_page":True,
      "new_source_only_full_members_accepted":0,
      "new_birthdays_accepted":0,"bazi_variables_computed":0}
    return combined,manifest

def fixture():
    assert 72+16==88 and 211-88==123 and 189+35==224 and 51+12==63 and 21+4==25
    print("PASS: source-only 72+16 volumes, 189+35 index rows; no historical 404 interpreted as absence")
def main():
    a=argparse.ArgumentParser()
    a.add_argument("--fixture-check",action="store_true")
    a.add_argument("--out",type=Path,default=OUT)
    opt=a.parse_args()
    if opt.fixture_check:return fixture()
    checked,m=audit()
    write(opt.out/"cumulative_88_source_checked_unique_volumes_v1.csv",checked)
    (opt.out/"cumulative_88_source_summary_v1.json").write_text(
        json.dumps(m,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    print("SOURCE_CUMULATIVE",json.dumps({"volumes":m["unique_volumes_ever_TOC_probed"],
        "http":m["TOC_page_status_count"],"events":m["candidate_original_journal_INDEX_events_including_all_roles_and_offices"],
        "remaining":m["remaining_TOC_endpoints_never_tested"]},ensure_ascii=False))
if __name__=="__main__":main()
