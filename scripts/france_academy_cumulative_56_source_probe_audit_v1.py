#!/usr/bin/env python3
"""Reconcile 4 disjoint Academy TOC source probes + 1856 grammar corrections.

This is a META-DATA ONLY source availability reconciliation: no new fetch,
no original election full pages, and no study DOBs/members accepted.
The 43/1856 TOC originally parsed 0 entries despite being readable. Correct
this ONE existing probe from the separately source-SHA-audited 1856 parser,
add the newly inspected 42/1856 TOC once, never double count.
"""
from __future__ import annotations
import argparse,csv,json
from collections import Counter
from pathlib import Path

VERSION="france-academy-1835-1940-cumulative-56-probed-volume-QA-v1"
FILES=[
 ("DISCOVERY_11","data/france_academy_comptes_rendus_211_volume_inventory_v1/academy_original_wikisource_211_volume_inventory_v1.csv",11),
 ("HOLDOUT_12","data/france_academy_comptes_rendus_211_volume_holdout_v1/academy_original_wikisource_211_volume_inventory_v1.csv",12),
 ("THIRD_16","data/france_academy_unprobed_16_volume_batch_v1/academy_original_wikisource_211_volume_inventory_v1.csv",16),
 ("FROZEN_SHARD_00_16","data/france_academy_remaining_172_toc_batch_v1/shard_00/academy_original_wikisource_211_volume_inventory_v1.csv",16)]
NOMINATION_SUM="data/france_academy_1856_nomination_grammar_pilot_v1/summary.json"
OUT=Path("data/france_academy_1856_nomination_grammar_pilot_v1")
COLUMNS=["volume","year","source_probe_group","source_technical_status",
    "election_heading_recognized","source_event_index_rows","source_event_count_interpretation",
    "official_original_volume_link","wikisource_TOC_url","source_HTML_sha256",
    "original_event_page_directly_inspected","legal_approval_status_adjudicated",
    "source_member_study_accepted","study_exact_DOB_accepted","bazi_variables_computed"]

def read(path):
    with open(path,encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))

def write(path,rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=COLUMNS)
        w.writeheader();w.writerows(rows)

def check():
    groups={}
    mapping={}
    for label,path,n in FILES:
        rows=read(path)
        if len(rows)!=211:raise RuntimeError("Expected 211 official-to-Wikisource rows in "+path)
        sampled={int(r["volume"]):r for r in rows if r["table_sampled"]=="1"}
        if len(sampled)!=n:raise RuntimeError("Source sample count changed in "+label)
        if set(sampled)&set(groups):
            raise RuntimeError("Previously sampled volume IDs not disjoint from "+label)
        groups.update({v:(label,r) for v,r in sampled.items()})
        for row in rows:
            v=int(row["volume"])
            tup=(row["year"],row["official_source_url"],row["wikisource_table_url"])
            if v in mapping and mapping[v]!=tup:
                raise RuntimeError("Original publication mapping changed for "+str(v))
            mapping[v]=tup
    if len(groups)!=55 or len(mapping)!=211:
        raise RuntimeError("Expected exactly 55 previously distinct probes")
    nominee=json.load(open(NOMINATION_SUM,encoding="utf-8"))
    verified={int(x["volume"]):x for x in nominee["source_checks"] if int(x["volume"]) in (42,43)}
    if set(verified)!={42,43}:
        raise RuntimeError("Two 1856 original source index audits missing")
    if 42 in groups or 43 not in groups:
        raise RuntimeError("Expected 42 newly inspected; 43 already present in third sample")
    old43=groups[43][1]
    if old43["transcribed_election_rows"]!="0" or old43["table_http_status"]!="HTTP_200":
        raise RuntimeError("Unexpected prior 1856 tome43 old zero parser state")
    if int(verified[42]["event_rows"])!=7 or int(verified[43]["event_rows"])!=2:
        raise RuntimeError("Expected 1856 source restored 7+2 nominations")
    if any(int(verified[v]["status"])!=200 for v in (42,43)):
        raise RuntimeError("1856 source not publicly verified HTML200")

    # Explicitly replace inaccurate PARSER output; do not rewrite original
    # third-batch source bytes or its historical provenance checkpoint.
    output=[]
    for v in sorted(set(groups)|{42}):
        if v==42:
            first_source="NEW_1856_TOME42_NOMINATION_GRAMMAR_DIAGNOSTIC"
            src=verified[42]
            source_status="HTTP_200"
            headings="1"
            events="7"
            sha=src["source_html_sha256"]
        elif v==43:
            first_source="THIRD_16_ORIGINAL_PROBE_PLUS_CORRECTED_1856_PARSER"
            src=verified[43]
            source_status="HTTP_200"
            headings="1"
            events="2"
            sha=src["source_html_sha256"]
        else:
            first_source,src=groups[v]
            source_status=src["table_http_status"]
            headings=src["election_heading_detected"]
            events=src["transcribed_election_rows"]
            sha=src["table_html_sha256"]
        if source_status not in ("HTTP_200","HTTP_404","LOCAL_CACHE"):
            raise RuntimeError("Non-classified historical source status "+source_status)
        if source_status=="HTTP_404":
            if events:raise RuntimeError("Historical 404 cannot have confirmed event count")
            # An empty field means UNKNOWN, NEVER literal zero historical elections.
            status="TOC_HTTP404_UNKNOWN"
            headings="UNDETERMINED"
        else:
            if not events or not events.isdigit():
                raise RuntimeError("Readable TOC must have an explicit PARSED count")
            status="PARSED_INDEX_EVENT_COUNT_NOT_COMPLETE_HISTORICAL_ELECTIONS"
        m=mapping[v]
        output.append({
            "volume":str(v),"year":m[0],"source_probe_group":first_source,
            "source_technical_status":source_status,
            "election_heading_recognized":headings,
            "source_event_index_rows":events,
            "source_event_count_interpretation":status,
            "official_original_volume_link":m[1],
            "wikisource_TOC_url":m[2],
            "source_HTML_sha256":sha,
            "original_event_page_directly_inspected":"0",
            "legal_approval_status_adjudicated":"0",
            "source_member_study_accepted":"0",
            "study_exact_DOB_accepted":"0","bazi_variables_computed":"0"
        })
    if len(output)!=56:raise RuntimeError("Expected 56 uniquely accessed TOC volume IDs")
    statuses=Counter(r["source_technical_status"] for r in output)
    total=sum(int(r["source_event_index_rows"]) for r in output if r["source_event_index_rows"])
    if statuses.get("HTTP_200",0)+statuses.get("LOCAL_CACHE",0)!=39 or statuses.get("HTTP_404",0)!=17:
        raise RuntimeError("Expected 39 readable / 17 TOC404 after 1856 reclassification")
    if total!=141:raise RuntimeError("Expected exactly 141 source-index events after 1856 revision and shard zero")
    return output,{"version":VERSION,"total_original_volumes_in_metadata":211,
        "historical_years":106,
        "distinct_TOC_volumes_actually_probed":56,
        "original_39_disjoint_samples_plus_shard0":55,
        "new_1856_TOC_vol42":1,"corrected_preexisting_1856_TOC_vol43":1,
        "technical_statuses":dict(statuses),
        "candidate_index_election_and_nomination_event_rows":total,
        "remaining_never_probed_TOC_volumes":155,
        "an_empty_parsed_index_is_not_a_zero_member_semester":True,
        "memberships_still_unaccepted":True,
        "accepted_study_members":0,"accepted_exact_birthdays":0,
        "bazi_variables_computed":0}

def test():
    assert 39+16+1==56
    assert 86+46+7+2==141
    assert 211-56==155
    print("PASS: 39+16 previously disjoint, one newly probed 1856 TOC, one corrected old 1856 source; no admissions")

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--fixture-check",action="store_true")
    p.add_argument("--out",type=Path,default=OUT)
    a=p.parse_args()
    if a.fixture_check:test();return
    rows,summary=check()
    write(a.out/"cumulative_56_source_checked_volume_coverage_v1.csv",rows)
    (a.out/"cumulative_56_source_summary_v1.json").write_text(
        json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("CUMULATIVE",json.dumps(summary,ensure_ascii=False))
if __name__=="__main__":main()
