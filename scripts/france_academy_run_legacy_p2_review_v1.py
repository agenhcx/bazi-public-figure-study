#!/usr/bin/env python3
"""Capture or seal the one bounded, frozen 16-volume P2 source revision.

Default is a read-only plan. --seal-existing creates the checkpoint and ledger
from an existing completed inventory without rerunning it or making requests.
--run uses the existing rate-limited, checkpointed inventory implementation;
add --offline to require its cached responses. Historical and first-capture
files are preserved. Successful parsing never accepts a study member or DOB.
"""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
import france_academy_comptes_rendus_211_volume_inventory_v1 as inventory
import france_academy_offline_source_toc_event_ledger_v1 as ledger
import france_academy_update_source_checkpoint_v2 as update

CACHE=Path("local_runs/france_academy_211_volume_inventory_source_cache_v1")
OUT=Path("local_runs/france_academy_legacy_p2_review_v1")


def validated_inputs(baseline_path):
    baseline=update.read_baseline(baseline_path,require_v2=True)
    return baseline,update.p2_revision_provenance(baseline,update.sha(baseline_path))


def invoke(function,arguments):
    before=sys.argv[:]
    try:
        sys.argv=arguments
        return function()
    finally:
        sys.argv=before


def preserve_pre_capture(output,provenance,create=False):
    """Never replace the initial capture evidence with a later cached replay."""
    path=output/"pre_capture_provenance_v1.json"
    if path.exists():
        old=update.load(path)
        update.require(old.get("baseline_sha256")==provenance["baseline_sha256"] and
                       old.get("review_queue_sha256")==provenance["review_queue_sha256"] and
                       old.get("frozen_volumes")==update.P2_VOLUMES,
                       "Existing P2 pre-capture provenance differs from frozen inputs")
        return
    if not create:return
    existing=[]
    for r in provenance["prior_source_records"]:
        path=CACHE/f"table_{r['volume']}_{r['year']}.html"
        for candidate in (path,path.with_suffix(path.suffix+".http.json")):
            if candidate.is_file():
                existing.append({"path":update.label(candidate),"sha256":update.sha(candidate)})
    report={"version":"france-academy-legacy-p2-pre-capture-provenance-v1",
            "frozen_volumes":list(update.P2_VOLUMES),**provenance,
            "selected_source_cache_files_existing_before_run":existing,
            "planned_review_volumes":16,"planned_new_volumes":0,
            "accepted_memberships":0,"accepted_exact_dobs":0,"bazi_variables_computed":0}
    inventory.write_json_atomic(output/"pre_capture_provenance_v1.json",report)


def seal_existing(output,baseline_path,cache_root=CACHE):
    """Seal an already captured inventory; this path never calls inventory.main."""
    output=Path(output);baseline_path=Path(baseline_path);cache_root=Path(cache_root)
    baseline,provenance=validated_inputs(baseline_path)
    preserve_pre_capture(output,provenance)
    record=update.load(output/"summary.json")
    update.require(record.get("run_complete") is True,"P2 inventory is incomplete; inspect source_run_progress_v1.json")
    update.require(record.get("table_of_contents_probed_volumes")==update.P2_VOLUMES and
                   record.get("table_probes_completed")==16 and record.get("category_volume_count")==211,
                   "P2 inventory does not contain the complete frozen selection")
    catalog=update.rows(output/update.FILES[0])
    update.require(set(update.unique(catalog,"P2 inventory"))==set(range(1,212)),"P2 inventory frame changed")
    selected=update.unique([r for r in catalog if r["table_sampled"]=="1"],"P2 selected sources")
    update.require(set(selected)==set(update.P2_VOLUMES),"P2 selected inventory differs from frozen sixteen volumes")
    report={"version":update.P2_REVISION_VERSION,"volumes":list(update.P2_VOLUMES),
            **provenance,"source_sha256_comparison":update.p2_source_comparison(provenance["prior_source_records"],selected),
            "table_http_counts":record["table_probe_http_status"],
            "recognized_election_headings":record["table_probe_election_heading_count"],
            "parsed_candidate_event_rows":record["sample_election_event_candidates"],
            "revision_reason":"FROZEN_P2_REVIEW;HISTORICAL_SOURCE_SHA_PRESERVED;CURRENT_SOURCE_SHA_COMPARED",
            "missing_or_unparsed_not_historical_zero":True,
            "original_event_pages_inspected":0,"accepted_memberships":0,
            "accepted_birthdates":0,"bazi_variables_computed":0}
    update.gates([catalog,record,report])
    update.validate_revision_selection(report,selected,{int(r["volume"]) for r in baseline},
                                       provenance["baseline_sha256"],baseline)
    inventory.write_json_atomic(output/"source_only_shard_checkpoint_v1.json",report)
    invoke(ledger.main,["p2-offline-ledger","--source-dir",str(output),"--out",str(output),
                        "--cache-root",str(cache_root)])
    update.verify_batch(output,cache_root)
    _,after=validated_inputs(baseline_path)
    update.require(after==provenance,"P2 baseline or frozen queue changed during sealing")
    return report


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline",type=Path,default=update.P2_BASELINE)
    parser.add_argument("--out",type=Path,default=OUT)
    mode=parser.add_mutually_exclusive_group()
    mode.add_argument("--run",action="store_true",help="Run the existing bounded source inventory")
    mode.add_argument("--seal-existing",action="store_true",help="Seal an existing completed inventory without rerunning it")
    parser.add_argument("--offline",action="store_true",help="For --run, prohibit source requests")
    parser.add_argument("--delay",type=float,default=1.5)
    parser.add_argument("--cache-root",type=Path,default=CACHE,help="Source cache for sealing; --run uses the standard inventory cache")
    args=parser.parse_args(argv)
    update.require(args.delay>=1.5,"P2 source delay must be at least 1.5 seconds")
    _,provenance=validated_inputs(args.baseline)
    if not args.run and not args.seal_existing:
        print(json.dumps({"version":update.P2_REVISION_VERSION,"volumes":update.P2_VOLUMES,
            **provenance,"required_table_requests_max":16,"required_requests_max":21,
            "planned_new_volumes":0,"live_network_requests":0,
            "accepted_memberships":0,"accepted_exact_dobs":0,"bazi_variables_computed":0},ensure_ascii=False))
        return
    if args.run:
        update.require(args.cache_root.resolve()==CACHE.resolve(),"--run uses the standard inventory cache; custom --cache-root is for --seal-existing")
        preserve_pre_capture(args.out,provenance,create=True)
        command=["p2-source-inventory","--sample-volumes",",".join(map(str,update.P2_VOLUMES)),
                 "--max-table-probes","16","--delay",str(args.delay),"--out",str(args.out)]
        if args.offline:command.append("--offline")
        invoke(inventory.main,command)
    report=seal_existing(args.out,args.baseline,args.cache_root)
    print("P2_REVISION",json.dumps(report,ensure_ascii=False))


if __name__=="__main__":main()
