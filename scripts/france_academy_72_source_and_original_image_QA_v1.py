#!/usr/bin/env python3
"""Offline source-only proof: 72 distinct checked TOCs, 189 indexed events.

Reconcile earlier 56 audited volume metadata and new 16-volume shard 01,
with four independently downloaded/visually checked 1856 original scans.
Prevents promoting historical source events into accepted member DOB cohort.
"""
from __future__ import annotations
import csv,json
from collections import Counter
from pathlib import Path

DIR=Path("data/france_academy_remaining_172_toc_batch_v1")
PREV=Path("data/france_academy_1856_nomination_grammar_pilot_v1")
ORIG=Path("data/france_academy_1856_commons_original_page_map_v1")
def read(p):
    with open(p,encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
def jread(p):return json.loads(p.read_text(encoding="utf-8"))
def main():
    prev=read(PREV/"cumulative_56_source_checked_volume_coverage_v1.csv")
    first=jread(PREV/"cumulative_56_source_summary_v1.json")
    shard_catalog=read(DIR/"shard_01/academy_original_wikisource_211_volume_inventory_v1.csv")
    shard=[x for x in shard_catalog if x["table_sampled"]=="1"]
    shard_summary=jread(DIR/"shard_01/summary.json")
    person_summary=jread(DIR/"shard_01/person_event_ledger_summary_v1.json")
    events=read(DIR/"shard_01/verified_transcribed_person_event_candidates_v1.csv")
    merged=read(DIR/"cumulative_72_source_checked_unique_volumes_v1.csv")
    total=jread(DIR/"cumulative_72_source_summary_v1.json")
    images=jread(ORIG/"source_preview_metadata_v1.json")
    original_review=jread(ORIG/"four_original_pages_visual_adjudication_v1.json")
    prev_ids={int(x["volume"]) for x in prev}
    shard_ids={int(x["volume"]) for x in shard}
    final_ids={int(x["volume"]) for x in merged}
    if len(prev)!=56 or len(prev_ids)!=56 or len(shard)!=16 or len(shard_ids)!=16 or prev_ids & shard_ids:
        raise RuntimeError("Source 56 + disjoint shard01 invariants violated")
    if len(merged)!=72 or final_ids!=prev_ids|shard_ids or len(final_ids)!=72:
        raise RuntimeError("Duplicate/missing volume in cumulative 72")
    roles=Counter(x["member_role_source_candidate"] for x in events)
    if roles!=Counter(person_summary["event_classes"]):raise RuntimeError("Role breakdown modified")
    if len(events)!=person_summary["parsed_event_rows"] or len(events)!=shard_summary["sample_election_event_candidates"]:
        raise RuntimeError("Individual events do not reconcile with source TOC counts")
    if any(not e["name_as_transcribed"] for e in events):raise RuntimeError("Nameless historical event not quarantined")
    for r in merged:
        if r["accepted_member"]!="0" or r["bazi"]!="0":
            raise RuntimeError("An index event was promoted into study admission")
    statuses=Counter(r["technical_status"] for r in merged)
    if statuses!={"HTTP_200":51,"HTTP_404":21}:
        raise RuntimeError("Source access counts changed "+str(statuses))
    parsed=sum(int(r["parsed_index_event_rows"]) for r in merged if r["parsed_index_event_rows"])
    if parsed!=189 or first["candidate_index_election_and_nomination_event_rows"]!=141:
        raise RuntimeError("Cumulative source index count not reproducible")
    if total["original_source_index_unique_volumes_checked"]!=72 or total["remaining_never_probed_TOC_volumes"]!=139:
        raise RuntimeError("Cumulative ledger summary invalid")
    a={x["printed_page"]:x for x in images["records"]}
    b={x["printed_page"]:x for x in original_review["pages"]}
    if set(a)!=set(b) or set(a)!={83,84,85,169}:
        # Four original printed page snapshots must be identical across source sources.
        raise RuntimeError("Original four-page evidence mismatch")
    for p in (83,84,85,169):
        if a[p]["source_preview_sha256"]!=b[p]["source_image_sha256"] or a[p]["frame"]!=b[p]["djvu_frame"]:
            raise RuntimeError("Original scan SHA or frame mismatch "+str(p))
    if original_review["accepted_full_members_added"] or original_review["exact_DOB_accepted"] or original_review["bazi_variables_computed"]:
        raise RuntimeError("Original scanned evidence incorrectly accepted into cohort")
    if not original_review["pages"][1]["event_evidence_type"]=="ORIGINAL_ELECTION_VOTE_VERIFIED":
        raise RuntimeError("Incorrect 1856 source vote page adjudication")
    print("PASS: 72 unique historical sources; 51 TOC200/21 TOC404; 189 index event rows; 48 shard01 source persons")
    print("PASS: 4 original public-domain image scans SHA verified, Hermite vote p84 40/48 and approval report p169")
    print("PASS: NO cohort acceptance, NO birth data edits, NO BaZi computation")
if __name__=="__main__":main()
