#!/usr/bin/env python3
"""Run one bounded, pre-frozen 16-volume public Academy journal TOC shard.

The 172-volume plan was determined *before* any of its own URLs were probed,
by excluding 11+12+16 prior inspected volumes from 211 volumes. Results stay
candidate-only: HTTP404 != no election, and parsed election != full member.
"""
from __future__ import annotations
import argparse,csv,json,sys
from collections import defaultdict
from pathlib import Path
from france_academy_comptes_rendus_211_volume_inventory_v1 import main as run_inventory

PLAN=Path("data/france_academy_unprobed_16_volume_batch_v1/remaining_172_toc_shard_plan_v1.csv")
ROOT=Path("local_runs/france_academy_remaining_172_toc_batches_v1")
V="france-academy-remaining-172-toc-shard-runner-v1"

def select():
    with PLAN.open(encoding="utf-8-sig",newline="") as f:rows=list(csv.DictReader(f))
    if len(rows)!=172:raise RuntimeError("Frozen source plan changed: expected 172 records")
    groups=defaultdict(list);ids=[]
    for r in rows:
        shard=int(r["shard"]);v=int(r["volume"]);pos=int(r["sequence"])
        if not 0<=shard<=10 or not 1<=v<=211:raise RuntimeError("Bad manifest shard/volume")
        if any(r.get(k)!="0" for k in ("full_study_members_accepted","study_exact_dob_accepted","bazi_variables_computed")):
            raise RuntimeError("Unexpected research admission flag in fixed source plan")
        if r["source_status"]!="NOT_YET_PROBED":raise RuntimeError("Manifest is not fixed pre-query plan")
        ids.append(v);groups[shard].append((pos,v,r["year"]))
    if len(set(ids))!=172 or set(groups)!=set(range(11)):
        raise RuntimeError("Missing shard or duplicated source volume")
    result={}
    for i in sorted(groups):
        items=sorted(groups[i])
        if [a[0] for a in items]!=list(range(len(items))):
            raise RuntimeError("Noncontiguous shard sequence")
        if len(items)!=(12 if i==10 else 16):
            raise RuntimeError("Shard sizes changed")
        result[i]=[x[1] for x in items]
    return result

def test():
    groups=select()
    assert len(groups)==11
    assert sum(len(g) for g in groups.values())==172
    assert 1 not in set(x for g in groups.values() for x in g)
    assert len(groups[0])==16 and len(groups[10])==12
    print("PASS: immutable 172/11 source-plan records, sequential unique volume keys, zero study admissions")

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--fixture-check",action="store_true")
    p.add_argument("--shard",type=int,default=0,help="integer 0..10")
    p.add_argument("--run",action="store_true",help="Opt into live source requests; otherwise dry-run")
    p.add_argument("--offline",action="store_true",help="Only reuse cached HTML responses")
    p.add_argument("--delay",type=float,default=1.5)
    p.add_argument("--out-root",type=Path,default=ROOT)
    args=p.parse_args()
    if args.fixture_check:test();return
    groups=select()
    if args.shard not in groups or args.delay<1.5:raise ValueError("Shard must be 0..10, rate >=1.5 seconds")
    selected=groups[args.shard]
    if not args.run:
        print(json.dumps({"version":V,"shard":args.shard,"volumes":selected,
            "required_table_requests_max":len(selected),
            "required_requests_max":len(selected)+5,"live_network_requests":0,
            "original_scanned_election_pages_inspected":0,
            "accepted_memberships":0,"bazi_variables_computed":0},ensure_ascii=False))
        return
    output=args.out_root/f"shard_{args.shard:02d}"
    before=sys.argv[:]
    try:
        sys.argv=["source-inventory","--sample-volumes",",".join(map(str,selected)),
            "--max-table-probes",str(len(selected)),"--delay",str(args.delay),
            "--out",str(output)]
        if args.offline:sys.argv.append("--offline")
        run_inventory()
    finally:
        sys.argv=before
    record=json.loads((output/"summary.json").read_text(encoding="utf-8"))
    if not record.get("run_complete",False):
        raise RuntimeError("Source shard incomplete; inspect source_run_progress_v1.json")
    if record["table_of_contents_probed_volumes"]!=sorted(selected):
        raise RuntimeError("Output sampled volume set is not the selected frozen shard")
    if record["category_volume_count"]!=211 or record["table_probes_completed"]!=len(selected):
        raise RuntimeError("Source input completeness check failed")
    if record["accepted_full_memberships"] or record["accepted_exact_dobs"] or record["bazi_variables_computed"]:
        raise RuntimeError("Accidental study acceptance detected")
    if record["table_probe_http_status"].get("HTTP_429") or record["table_probe_http_status"].get("HTTP_403"):
        raise RuntimeError("Source rate-limit/access block: do not automatically retry")
    report={"version":V,"shard":args.shard,"volumes":selected,
            "table_http_counts":record["table_probe_http_status"],
            "recognized_election_headings":record["table_probe_election_heading_count"],
            "parsed_candidate_event_rows":record["sample_election_event_candidates"],
            "missing_or_unparsed_not_historical_zero":True,
            "original_event_pages_inspected":0,"accepted_memberships":0,
            "accepted_birthdates":0,"bazi_variables_computed":0}
    (output/"source_only_shard_checkpoint_v1.json").write_text(
        json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    # Re-read cached HTML with exact SHA256 verification, no additional requests.
    # Preserve per-person source event evidence alongside volume-level counts.
    from france_academy_offline_source_toc_event_ledger_v1 import main as person_ledger_main
    saved_argv=sys.argv[:]
    try:
        sys.argv=["person-event-ledger","--source-dir",str(output),"--out",str(output)]
        person_ledger_main()
    finally:
        sys.argv=saved_argv
    event_summary=json.loads((output/"person_event_ledger_summary_v1.json").read_text(encoding="utf-8"))
    if event_summary["parsed_event_rows"]!=record["sample_election_event_candidates"]:
        raise RuntimeError("Person event ledger count differs from source volume summary")
    print("SHARD",json.dumps(report,ensure_ascii=False))
if __name__=="__main__":main()
