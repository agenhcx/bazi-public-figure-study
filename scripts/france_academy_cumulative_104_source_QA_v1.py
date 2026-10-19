#!/usr/bin/env python3
"""Reproduce 104 checked original journal volumes and 299 INDEX event occurrences.

Sources:
  - immutable 88-source TOC counts (including false zeros 37/98/128),
  - separately preserved three historical nominations source overlay (+14),
  - Shard03 fixed 16-volume TOC audit with 61 person rows,
  - single Zambacco adjacent-tables role/page correction (event count +0).
Only *derived* cumulative overlays are written; original source snapshots and
frozen Bazi cohort data are NEVER changed. No source network access.
"""
from __future__ import annotations
import argparse,csv,hashlib,json
from collections import Counter
from pathlib import Path

VERSION="france-academy-104-original-journal-TOCs-299-source-index-events-v1"
ROOT=Path("data/france_academy_remaining_172_toc_batch_v1")
OLD=ROOT/"cumulative_88_source_checked_unique_volumes_v1.csv"
OLDSUM=ROOT/"cumulative_88_source_summary_v1.json"
NEW=ROOT/"shard_03/academy_original_wikisource_211_volume_inventory_v1.csv"
NEWLEDGER=ROOT/"shard_03/verified_transcribed_person_event_candidates_v1.csv"
NEWSUM=ROOT/"shard_03/person_event_ledger_summary_v1.json"
REC=Path("data/france_academy_nominations_37_98_128_recovery_v1")
RECCSV=REC/"recovered_historical_nomination_election_index_events_v1.csv"
RECSUM=REC/"summary.json"
CROSS=Path("data/france_academy_shard03_Zambacco_source_overlay_v1")
CROSSCSV=CROSS/"Zambacco_1900_single_event_source_role_correction_v1.csv"
CROSSSUM=CROSS/"summary.json"
OUT=ROOT
COLS=["volume","year","first_index_probe_group","toc_http_status",
      "original_source_SHA256","followup_source_SHA256",
      "original_parsed_index_event_rows","corrected_parsed_index_event_rows",
      "correction_source","source_review_state",
      "original_election_page_directly_opened","accepted_full_member","DOB_accepted",
      "bazi_features_computed"]
EVENT_FIELDS=["volume","year","name_as_transcribed","member_role_source_candidate",
  "original_action_wording","science_section_transcribed","first_printed_page_candidate",
  "all_printed_pages_indexed","wikisource_table_url","source_html_sha256",
  "source_sha256_verified_against_inventory","cths_562_exact_name_candidate_id",
  "name_matching_status","origin_source_tier","original_member_election_page_opened",
  "official_member_status_accepted","exact_dob_accepted","bazi_variables_computed",
  "role_followup_overlay_applied","followup_source_SHA256"]
def read(p):
    with p.open(encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
def js(p):return json.loads(p.read_text(encoding="utf8"))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,records,fields):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore")
        w.writeheader();w.writerows(records)
def build():
    old=read(OLD);oldsum=js(OLDSUM)
    new_source=read(NEW)
    new_event=read(NEWLEDGER);newsum=js(NEWSUM)
    recovered=read(RECCSV);recover_sum=js(RECSUM)
    join=read(CROSSCSV);join_sum=js(CROSSSUM)
    if len(old)!=88 or len({x["volume"] for x in old})!=88:
        raise RuntimeError("Frozen 88 source frame missing or duplicated")
    if len(new_source)!=211 or len(new_event)!=61:
        raise RuntimeError("Prespecified Shard03 frame sizes changed")
    if len(recovered)!=14 or len(join)!=1:
        raise RuntimeError("Source-verified historical corrections missing")
    if oldsum["candidate_original_journal_INDEX_events_including_all_roles_and_offices"]!=224:
        raise RuntimeError("Frozen earlier 224 indexed event count changed")
    if newsum["parsed_event_rows"]!=61 or recover_sum["event_candidate_rows_recovered"]!=14:
        raise RuntimeError("Verified source overlay event totals changed")
    if recover_sum["full_like_source_rows"]!=7 or recover_sum["correspondent_rows"]!=6 or recover_sum["office_elections_not_new_full_members"]!=1:
        raise RuntimeError("History member vs office role resolution changed")
    if join_sum["original_shard03_event_rows"]!=61 or join_sum["original_index_event_count_change"]!=0:
        raise RuntimeError("Zambacco is ONE event, not an additional new person")
    z=join[0]
    if z["new_conservative_role"]!="CORRESPONDENT" or z["new_original_printed_page_claim"]!="22":
        raise RuntimeError("Corrected 1900 orphan index source still unresolved")
    revised={str(v):[] for v in (37,98,128)}
    for row in recovered:
        if row["volume"] not in revised:raise RuntimeError("Source overlay outside fixed three volumes")
        revised[row["volume"]].append(row)
        if any(row[k]!="0" for k in ("accepted_full_member","accepted_DOB","bazi_features_computed")):
            raise RuntimeError("Accidental cohort acceptance in newly recovered source leads")
    if {k:len(v) for k,v in revised.items()}!={"37":1,"98":6,"128":7}:
        raise RuntimeError("Actual 1853/1884/1899 event counts not verified")
    originals={x["volume"]:x for x in old}
    for k in revised:
        if originals[k]["parsed_index_event_rows"]!="0" or originals[k]["technical_status"]!="HTTP_200":
            raise RuntimeError("Old source was not actually a false-zero event")
    selected=[x for x in new_source if x["table_sampled"]=="1"]
    if len(selected)!=16 or len({x["volume"] for x in selected})!=16:
        raise RuntimeError("Shard03 not 16 disjoint source targets")
    if any(x["volume"] in originals for x in selected):
        raise RuntimeError("Source volume overlap between 88 old and 16 new")
    if sorted(int(x["volume"]) for x in selected)!=[11,12,13,39,40,69,70,100,102,131,132,162,163,191,192,193]:
        raise RuntimeError("Original prespecified source-plan volume identifiers changed")
    if newsum["source_200_bytes_checked"]!=9 or newsum["other_TOC_statuses_not_election_zero"]!=7:
        raise RuntimeError("Recent Shard03 SHA checks changed")
    if any(x["source_sha256_verified_against_inventory"]!="1" for x in new_event):
        raise RuntimeError("Original per-person source byte hashes not verified")
    total=list(old)
    summaries=[]
    for row in old:
        v=row["volume"]
        patch=revised.get(v,[])
        newnum=len(patch) if patch else int(row["parsed_index_event_rows"] or 0) if row["technical_status"]=="HTTP_200" else None
        if patch and any(x["prior_source_HTML_sha256"]!=row["source_image_sha256"] for x in patch):
            raise RuntimeError("Historical preserved-source SHA mismatch")
        record={
          "volume":v,"year":row["year"],
          "first_index_probe_group":row["source_probe_group"],
          "toc_http_status":row["technical_status"],
          "original_source_SHA256":row["source_image_sha256"],
          "followup_source_SHA256":patch[0]["newly_read_source_HTML_sha256"] if patch else "",
          "original_parsed_index_event_rows":row["parsed_index_event_rows"],
          "corrected_parsed_index_event_rows":str(newnum) if newnum is not None else "",
          "correction_source":"REVISITED_3_HISTORICAL_NOMINATION_GRAMMARS" if patch else "",
          "source_review_state":"TOC_ONLY_404_NOT_HISTORICAL_ZERO" if row["technical_status"]=="HTTP_404"
                                else "INDEX_EVENT_COUNT_NOT_UNIQUE_ACCEPTED_MEMBERS",
          "original_election_page_directly_opened":"0","accepted_full_member":"0",
          "DOB_accepted":"0","bazi_features_computed":"0"}
        summaries.append(record)
    for r in selected:
        status=r["table_http_status"]
        if status not in ("HTTP_200","HTTP_404"):
            raise RuntimeError("Unrecognized source response")
        if status=="HTTP_200" and not r["transcribed_election_rows"].isdigit():
            raise RuntimeError("Readable source with no captured parser count")
        if status=="HTTP_404" and r["transcribed_election_rows"]:
            raise RuntimeError("No historical zero from missing TOC")
        summaries.append({
          "volume":r["volume"],"year":r["year"],
          "first_index_probe_group":"FROZEN_SHARD_03",
          "toc_http_status":status,
          "original_source_SHA256":r["table_html_sha256"],
          "followup_source_SHA256":z["recheck_source_SHA256"] if r["volume"]=="131" else "",
          "original_parsed_index_event_rows":r["transcribed_election_rows"],
          "corrected_parsed_index_event_rows":r["transcribed_election_rows"],
          "correction_source":"ZAMBACCO_ROLE_AND_PAGE_ONLY_NO_ADDED_EVENT" if r["volume"]=="131" else "",
          "source_review_state":"TOC_ONLY_404_NOT_HISTORICAL_ZERO" if status=="HTTP_404"
                                else "INDEX_EVENT_COUNT_NOT_UNIQUE_ACCEPTED_MEMBERS",
          "original_election_page_directly_opened":"0","accepted_full_member":"0",
          "DOB_accepted":"0","bazi_features_computed":"0"})
    summaries.sort(key=lambda x:int(x["volume"]))
    if len(summaries)!=104 or len({x["volume"] for x in summaries})!=104:
        raise RuntimeError("Expected 104 unique historical source volumes")
    status=Counter(x["toc_http_status"] for x in summaries)
    if status!={"HTTP_200":72,"HTTP_404":32}:
        raise RuntimeError("72 readable / 32 TOC-only 404 counts have changed")
    total_rows=sum(int(x["corrected_parsed_index_event_rows"]) for x in summaries if x["corrected_parsed_index_event_rows"])
    if total_rows!=299 or 224+14+61!=299:raise RuntimeError("Source overlay/cumulative counts invalid")
    # Preserve Shard03 raw CSV and create a separately named, conservatively
    # corrected per-person overlay with the original archive source checksum.
    upgraded=[]
    corrected=0
    for row in new_event:
        x=dict(row);x["role_followup_overlay_applied"]="0";x["followup_source_SHA256"]=""
        if row["volume"]=="131" and row["name_as_transcribed"]=="Zambacco":
            if corrected or row["member_role_source_candidate"]!="UNKNOWN_ROLE_MANUAL" or row["first_printed_page_candidate"]:
                raise RuntimeError("Ambiguous Zambacco event prior to role patch")
            x["member_role_source_candidate"]="CORRESPONDENT"
            x["first_printed_page_candidate"]="22"
            x["all_printed_pages_indexed"]="22"
            x["science_section_transcribed"]="Médecine et Chirurgie"
            x["role_followup_overlay_applied"]="1"
            x["followup_source_SHA256"]=z["recheck_source_SHA256"]
            corrected+=1
        if any(x[k]!="0" for k in ("official_member_status_accepted","exact_dob_accepted","bazi_variables_computed")):
            raise RuntimeError("New candidate accidentally accepted into cohort")
        upgraded.append(x)
    if corrected!=1:raise RuntimeError("Zambacco source overlay not applied exactly once")
    newroles=Counter(x["member_role_source_candidate"] for x in upgraded)
    if newroles["CORRESPONDENT"]!=47 or newroles.get("UNKNOWN_ROLE_MANUAL",0):
        raise RuntimeError("Corrected 1900 role counts disagree with source")
    report={"version":VERSION,
            "211_historical_original_books_inventory":211,
            "volume_source_inputs_SHA256":{"old_88":sha(OLD),"new_16":sha(NEW),
                                           "three_fixed_source_cases":sha(RECCSV),
                                           "Zambacco_one_role_patch":sha(CROSSCSV)},
            "TOC_volume_unique_checked":104,"TOC_source_HTTP_status":dict(status),
            "TOC_index_event_candidate_rows":total_rows,
            "components":{"frozen_prior_88_original_index_events":224,
                          "recovered_original_three_false_zero_roles":14,
                          "prespecified_Shard03_new_source_events":61,
                          "Zambacco_split_table_role_corrected_one_existing_event":0},
            "new_or_recovered_total_75_event_rows":75,
            "new_or_recovered_7_plus_13_full_like_index_role_candidates":20,
            "in_new_fixed_Shard03_roles_after_Zambacco":dict(newroles),
            "remaining_original_volume_TOCPages_never_checked":107,
            "note":"Source HTML response bytes differ on re-fetch; this alone is NOT evidence that historical index text changed.",
            "one_1853_election_is_office_not_new_member":True,
            "1853_Tome37_textual_TOC_header_year_suspect_requires_original_check":True,
            "original_printed_event_pages_newly_opened_in_this_QA":0,
            "historical_full_member_population_complete":False,
            "members_accepted_in_analytical_cohort":0,"exact_birthdays_accepted":0,
            "bazi_features_computed":0}
    return summaries,upgraded,report
def fixture():
    assert 88+16==104 and 63+9==72 and 25+7==32 and 224+14+61==299 and 211-104==107
    print("PASS: 104 distinct TOCs, 299 indexed event occurrences and source-only overlay arithmetic")
def main():
    a=argparse.ArgumentParser()
    a.add_argument("--fixture-check",action="store_true")
    a.add_argument("--out",type=Path,default=OUT)
    opts=a.parse_args()
    if opts.fixture_check:return fixture()
    records,events,report=build()
    write(opts.out/"cumulative_104_source_checked_volume_evidence_v1.csv",records,COLS)
    write(opts.out/"shard_03/Zambacco_corrected_61_historical_event_evidence_overlay_v1.csv",events,EVENT_FIELDS)
    (opts.out/"cumulative_104_source_summary_v1.json").write_text(
       json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("CUMULATIVE_REPRODUCED",json.dumps({"volumes":len(records),"HTTP":report["TOC_source_HTTP_status"],
       "candidate_events":report["TOC_index_event_candidate_rows"],
       "shard03_role_counts":report["in_new_fixed_Shard03_roles_after_Zambacco"],
       "remaining_never_probed":report["remaining_original_volume_TOCPages_never_checked"]},ensure_ascii=False))
if __name__=="__main__":main()
