#!/usr/bin/env python3
"""Offline person-event ledger from *already fetched* Academy TOC HTML sources.

Read same-run SHA256-matched Wikisource HTML caches, matching the frozen
source inventory. No new requests, no scans or DOB use. Events are index
transcription candidates, never accepted Académie regular members.
Python 3.10+, beautifulsoup4.
"""
from __future__ import annotations
import argparse,csv,hashlib,json
from collections import Counter,defaultdict
from pathlib import Path
from france_academy_wikisource_legacy_election_headings_v1 import parse_html
from france_academy_wikisource_election_rows_v1 import identity_key

VERSION="france-academy-toc-source-index-person-events-v1"
SOURCE_ROOT=Path("data/france_academy_remaining_172_toc_batch_v1/shard_00")
CACHE_ROOT=Path("local_runs/france_academy_211_volume_inventory_source_cache_v1")
CTHS=Path("data/france_academy_cths_profile_dob_harvest_v1/cths_dob_claims_all_targets_candidate_only_v1.csv")
FIELDS=["volume","year","name_as_transcribed","member_role_source_candidate",
  "original_action_wording","science_section_transcribed","first_printed_page_candidate",
  "all_printed_pages_indexed","wikisource_table_url",
  "source_html_sha256","source_sha256_verified_against_inventory",
  "cths_562_exact_name_candidate_id","name_matching_status",
  "origin_source_tier","original_member_election_page_opened",
  "official_member_status_accepted","exact_dob_accepted","bazi_variables_computed"]

def csv_read(p):
    with Path(p).open(encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))

def write_csv(p,rows,cols):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=cols,extrasaction="ignore")
        w.writeheader();w.writerows(rows)

def build(source_dir,cache_root):
    summary=json.loads((source_dir/"summary.json").read_text(encoding="utf-8"))
    checkpoint=json.loads((source_dir/"source_only_shard_checkpoint_v1.json").read_text(encoding="utf-8"))
    catalog=csv_read(source_dir/"academy_original_wikisource_211_volume_inventory_v1.csv")
    if len(catalog)!=211:raise RuntimeError("Expected complete 211-volume inventory")
    selected=set(int(x) for x in checkpoint["volumes"])
    checked={int(r["volume"]):r for r in catalog if r["table_sampled"]=="1"}
    if not 1<=len(selected)<=16 or set(checked)!=selected:
        raise RuntimeError("Shard-zero selected volumes diverge from fixed source manifest")
    if summary["table_of_contents_probed_volumes"]!=sorted(selected):
        raise RuntimeError("Inventory summary and per-volume source rows differ")
    cths=csv_read(CTHS)
    if len(cths)!=562:raise RuntimeError("CTHS source roster changed")
    names=defaultdict(list)
    for r in cths:names[identity_key(r["name"])].append(r["cths_person_id"])
    events=[];audit=[]
    for v in sorted(checked):
        row=checked[v]
        year=int(row["year"])
        status=row["table_http_status"]
        cache=cache_root/("table_"+str(v)+"_"+str(year)+".html")
        if status not in ("HTTP_200","LOCAL_CACHE"):
            audit.append({"volume":v,"year":year,"status":status,
                          "record_count":"UNKNOWN_NOT_ZERO",
                          "source_lookups":0,"byte_verification":"NOT_AVAILABLE"})
            continue
        if not cache.is_file():
            raise RuntimeError("Original fetched source bytes not cached for HTTP200: "+str(cache))
        raw=cache.read_bytes()
        h=hashlib.sha256(raw).hexdigest()
        if h!=row["table_html_sha256"]:
            raise RuntimeError("Fetched TOC response SHA256 mismatch for "+str(v))
        people,heads=parse_html(raw,v,year)
        if len(people)!=int(row["transcribed_election_rows"]):
            raise RuntimeError("Event parser not replaying stored source result for "+str(v))
        for p in people:
            person=p.get("elected_name_candidate","")
            ids=names.get(identity_key(person),[]) if person else []
            events.append({
               "volume":str(v),"year":str(year),
               "name_as_transcribed":person,
               "member_role_source_candidate":p["election_role_candidate"],
               "original_action_wording":p["source_action_wording"],
               "science_section_transcribed":p["science_section_candidate"],
               "first_printed_page_candidate":p["original_printed_volume_page"],
               "all_printed_pages_indexed":p.get("source_printed_page_references",""),
               "wikisource_table_url":row["wikisource_table_url"],
               "source_html_sha256":h,
               "source_sha256_verified_against_inventory":"1",
               "cths_562_exact_name_candidate_id":ids[0] if len(ids)==1 else "",
               "name_matching_status":"ONE_EXACT_CTHS_562_TOKEN_IDENTITY_CANDIDATE" if len(ids)==1
                      else "NO_EXACT_CTHS_562_MATCH" if not ids else "MULTIPLE_CTHS_562_MATCHES_MANUAL",
               "origin_source_tier":"WIKISOURCE_ACADEMY_PRINTED_INDEX_TRANSCRIPTION_NOT_ORIGINAL_EVENT_SCAN",
               "original_member_election_page_opened":"0",
               "official_member_status_accepted":"0",
               "exact_dob_accepted":"0","bazi_variables_computed":"0"
            })
        audit.append({"volume":v,"year":year,"status":status,
             "record_count":len(people),"source_lookups":0,"byte_verification":"SHA256_MATCH"})
    events.sort(key=lambda r:(int(r["volume"]),int(r["first_printed_page_candidate"] or 0),
                              r["name_as_transcribed"]))
    return events,audit

def test():
    html=b'<table><tr><td><span class="sc">NOMINATIONS de Membres et de Correspondants de l\'Acad\xc3\xa9mie</span> \xe2\x80\x94 M. Hermite est nomm\xc3\xa9 \xc3\xa0 la place vacante dans la Section de G\xc3\xa9om\xc3\xa9trie</td><td>85</td></tr></table>'
    e,_=parse_html(html,43,1856)
    assert len(e)==1 and e[0]["source_action_wording"]=="EST_NOMME_TRANSCRIBED"
    assert e[0]["election_role_candidate"]=="FULL_SECTION_MEMBER_CONTEXTUAL_NOMINATION"
    assert e[0]["original_election_printed_page_opened"]=="0"
    print("PASS: offline source-identified event ledger extraction and no member acceptance")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--fixture-check",action="store_true")
    ap.add_argument("--source-dir",type=Path,default=SOURCE_ROOT)
    ap.add_argument("--cache-root",type=Path,default=CACHE_ROOT)
    ap.add_argument("--out",type=Path,default=SOURCE_ROOT)
    a=ap.parse_args()
    if a.fixture_check:test();return
    events,audit=build(a.source_dir,a.cache_root)
    write_csv(a.out/"verified_transcribed_person_event_candidates_v1.csv",events,FIELDS)
    full_like={"FULL_SECTION_MEMBER","FULL_NONRESIDENT_MEMBER","FULL_ACADEMICIAN_LIBRE",
               "FULL_SECTION_MEMBER_CONTEXTUAL_NOMINATION"}
    roles=Counter(r["member_role_source_candidate"] for r in events)
    metric={"version":VERSION,
        "source_sha256":hashlib.sha256((a.source_dir/"academy_original_wikisource_211_volume_inventory_v1.csv").read_bytes()).hexdigest(),
        "source_replays":audit,"selected_toc_volumes":len(audit),
        "source_200_bytes_checked":sum(x["byte_verification"]=="SHA256_MATCH" for x in audit),
        "other_TOC_statuses_not_election_zero":sum(x["byte_verification"]!="SHA256_MATCH" for x in audit),
        "parsed_event_rows":len(events),
        "event_classes":dict(roles),
        "full_like_index_event_candidates":sum(roles.get(k,0) for k in full_like),
        "cths_562_unique_exact_name_event_candidates":sum(
           r["name_matching_status"]=="ONE_EXACT_CTHS_562_TOKEN_IDENTITY_CANDIDATE" for r in events),
        "historical_cohort_complete":False,
        "original_event_pages_directly_inspected":0,
        "accepted_french_members":0,"accepted_DOBs":0,"bazi_variables_computed":0}
    a.out.mkdir(parents=True,exist_ok=True)
    (a.out/"person_event_ledger_summary_v1.json").write_text(json.dumps(metric,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print("LEDGER_SUMMARY",json.dumps({k:metric[k] for k in (
        "source_200_bytes_checked","parsed_event_rows",
        "event_classes","full_like_index_event_candidates",
        "cths_562_unique_exact_name_event_candidates")},ensure_ascii=False))
if __name__=="__main__":main()
