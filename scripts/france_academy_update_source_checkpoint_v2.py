#!/usr/bin/env python3
"""Advance an immutable, source-only Academy TOC checkpoint without network I/O.

Uses the existing offline ledger/parser (beautifulsoup4); orchestration uses
only the standard library. Old checkpoints are inputs, never overwritten.
Pass this script's cumulative CSV as --baseline for the next frozen shard,
choose a fresh --out directory, and omit --revision-dir unless revising sources.
"""
from __future__ import annotations
import argparse,csv,hashlib,io,json,os
from collections import Counter
from pathlib import Path
from france_academy_offline_source_toc_event_ledger_v1 import build, FIELDS as EVENT_FIELDS
from france_academy_wikisource_legacy_election_headings_v1 import VERSION as PARSER_VERSION
from france_academy_wikisource_index_preflight_v1 import build_urls

VERSION="france-academy-source-checkpoint-v2"
REPO=Path(__file__).resolve().parents[1]
BASE=Path("data/france_academy_remaining_172_toc_batch_v1")
BASELINE=BASE/"cumulative_88_source_checked_unique_volumes_v1.csv"
PLAN=Path("data/france_academy_unprobed_16_volume_batch_v1/remaining_172_toc_shard_plan_v1.csv")
PLAN_SHA="0a1cba241de6c3e0a572a5af41deca11aa554441c6f12aaa990c7a97b6fe5203"
P1_REVISION_VERSION="france-academy-legacy-p1-revision-v1"
P1_VOLUMES=[3,35,94,124,125]
P1_REVIEW_QUEUE=Path("data/france_academy_source_review_queue_v1/legacy_zero_event_review_queue_v1.csv")
P1_REVIEW_QUEUE_SHA="6481b2b28df751b37ee1845dc6db643ea0c5133a3c83244caf7d3bc1b4872ecc"
P2_REVISION_VERSION="france-academy-legacy-p2-revision-v1"
P2_VOLUMES=[54,55,61,65,72,93,117,120,121,130,136,144,159,160,161,183]
P2_BASELINE=Path("data/france_academy_source_checkpoint_v9/cumulative_source_checked_unique_volumes_v2.csv")
P2_BASELINE_SHA="529d6d9e6460e639124428097a1bc45066191c10c56cdf0953495d11b9f0a94d"
P2_REVIEW_QUEUE=Path("data/france_academy_source_review_queue_v2/pending_p2_source_review_queue_v2.csv")
P2_REVIEW_QUEUE_SHA="6bb32085c70271c4884d9d693ab2aebeae3d5eaf7a84f0dab01f65cbd867f300"
FILES=["academy_original_wikisource_211_volume_inventory_v1.csv","summary.json",
       "source_only_shard_checkpoint_v1.json","person_event_ledger_summary_v1.json",
       "verified_transcribed_person_event_candidates_v1.csv"]
FIELDS=["volume","year","source_probe_group","technical_status","parsed_index_event_rows",
        "index_event_semantics","source_html_sha256","baseline_parsed_index_event_rows",
        "baseline_source_html_sha256","revision_reason","original_event_page_verified",
        "accepted_member","accepted_exact_dob","bazi"]

def require(condition,message):
    if not condition:raise RuntimeError(message)
def rows(path):
    with path.open(encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
def load(path):return json.loads(path.read_text(encoding="utf-8"))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def label(path):return Path(os.path.relpath(path.resolve(),REPO)).as_posix()
def status(value):return "HTTP_200" if value=="LOCAL_CACHE" else value
def counts(items):return sum(int(r["parsed_index_event_rows"]) for r in items if r["parsed_index_event_rows"])
def roles(items):return dict(Counter(r["member_role_source_candidate"] for r in items))
def gates(value):
    if isinstance(value,list):
        for child in value:gates(child)
    elif isinstance(value,dict):
        for key,child in value.items():
            if "accepted" in key.lower() or "bazi" in key.lower():
                require(child in (0,"0",False),"Nonzero/missing source-only gate: "+key)
            if isinstance(child,(dict,list)):gates(child)
def unique(items,label):
    found={int(r["volume"]):r for r in items}
    require(len(found)==len(items) and set(found)<=set(range(1,212)),label+": duplicate/invalid volume")
    return found
def csv_bytes(items,fields):
    stream=io.StringIO(newline="")
    writer=csv.DictWriter(stream,fieldnames=fields,extrasaction="raise")
    writer.writeheader();writer.writerows(items)
    return stream.getvalue().encode("utf-8-sig")

def read_baseline(path,require_v2=False):
    original=rows(path);unique(original,"Baseline");gates(original)
    legacy=path.name==BASELINE.name and not require_v2
    if not legacy:
        require(original and set(FIELDS)<=set(original[0]),"Incomplete v2 baseline columns")
    result=[]
    for old in original:
        r={k:old.get(k,"") for k in FIELDS}
        r["source_html_sha256"]=old.get("source_html_sha256") or old.get("source_image_sha256","")
        r["technical_status"]=status(old["technical_status"])
        require(old.get("accepted_member")==old.get("bazi")=="0","Baseline gates absent")
        r["accepted_exact_dob"]=old.get("accepted_exact_dob","0")
        n=r["parsed_index_event_rows"]
        require(n.isdigit() if r["technical_status"]=="HTTP_200" else n=="",
                "Baseline failed/unknown source must not carry a zero count: "+r["volume"])
        require(r["original_event_page_verified"]=="0","Baseline is not index-only")
        if not legacy:
            require(r["year"].isdigit() and int(r["year"])==1835+int(r["volume"])//2,"Malformed baseline year")
            require(r["technical_status"] not in ("","NOT_CHECKED","NOT_YET_PROBED","HTTP_403","HTTP_429"),"Unfinished/blocked baseline source")
            require(len(r["technical_status"])==8 and r["technical_status"].startswith("HTTP_") and r["technical_status"][5:].isdigit(),"Malformed baseline status")
            digest=r["source_html_sha256"]
            if r["technical_status"]=="HTTP_200" or digest:
                require(len(digest)==64 and all(c in "0123456789abcdef" for c in digest),"Missing/malformed baseline source SHA")
        result.append(r)
    if legacy:
        require(len(result)==88 and counts(result)==224,"Frozen 88-volume/224-event baseline changed")
    else:
        manifest=load(path.parent/"summary.json");gates(manifest)
        require(manifest.get("version")==VERSION,"Expected a v2 baseline summary")
        require(manifest.get("output_SHA256",{}).get("cumulative_source_checked_unique_volumes_v2.csv")==sha(path),"Baseline CSV SHA differs from its summary")
        require(manifest.get("unique_volumes_ever_TOC_probed")==len(result),"Baseline is missing or adding volume records")
        require(manifest.get("candidate_original_journal_INDEX_events_including_all_roles_and_offices")==counts(result),"Baseline event total differs from summary")
        require(manifest.get("TOC_page_status_count")==dict(Counter(r["technical_status"] for r in result)),"Baseline source statuses differ from summary")
        require(manifest.get("remaining_TOC_endpoints_never_tested")==211-len(result),"Baseline remaining count differs from frame")
        require(all(manifest.get(k)==0 for k in ("accepted_memberships","accepted_exact_dobs","bazi_variables_computed")),"Baseline summary gates absent")
    return result

RESUME_FIELDS=("frozen_volumes","reused_prior_volumes","baseline_sha256","reused_prior_source_records")

def baseline_resume(frozen,path):
    """Derive new requests and explicit prior-source provenance, in frozen order."""
    require(sha(PLAN)==PLAN_SHA,"Frozen 172-volume plan bytes changed")
    prior=unique(read_baseline(path,require_v2=True),"Resume baseline")
    reused=[v for v in frozen if v in prior]
    records=[dict(volume=v,**{k:prior[v][k] for k in (
        "year","technical_status","parsed_index_event_rows","source_html_sha256")}) for v in reused]
    return [v for v in frozen if v not in prior],{
        "frozen_volumes":list(frozen),"reused_prior_volumes":reused,
        "baseline_sha256":sha(path),"reused_prior_source_records":records}

def validate_shard_selection(checkpoint,selected,previous_ids,baseline_path,frozen):
    """Recompute the complete frozen-minus-baseline set; omission is not reuse."""
    expected=[v for v in frozen if v not in previous_ids]
    reused=[v for v in frozen if v in previous_ids]
    provenance={}
    if reused or any(k in checkpoint for k in RESUME_FIELDS):
        new,provenance=baseline_resume(frozen,baseline_path)
        require(new==expected,"Baseline changed while selecting new volumes")
        require(all(checkpoint.get(k)==provenance[k] for k in RESUME_FIELDS),"Missing/mismatched baseline reuse provenance")
    require(expected and checkpoint["volumes"]==expected,"New shard must include every frozen-minus-baseline volume in order")
    require(len(selected)==len(expected) and set(selected)==set(expected),"Inventory differs from the complete new-volume selection")
    return provenance

def p2_revision_provenance(baseline,baseline_sha):
    """Bind the one frozen P2 review to v9 and its immutable historical sources."""
    require(baseline_sha==P2_BASELINE_SHA,"P2 requires the frozen v9 baseline SHA")
    prior=unique(baseline,"P2 baseline")
    require(set(prior)==set(range(1,212)) and counts(baseline)==738,"P2 baseline must contain 211 volumes / 738 events")
    queue_path=REPO/P2_REVIEW_QUEUE
    require(sha(queue_path)==P2_REVIEW_QUEUE_SHA,"Frozen P2 review queue bytes changed")
    queue=rows(queue_path);gates(queue)
    require([int(r["volume"]) for r in queue]==P2_VOLUMES,"P2 review queue order changed")
    records=[]
    for item in queue:
        v=int(item["volume"]);old=prior[v]
        require(item["review_status"]=="UNRESOLVED_NOT_CONFIRMED_OMISSION" and
                item["year"]==old["year"]==str(1835+v//2) and
                item["technical_http_status"]==old["technical_status"]=="HTTP_200" and
                item["parsed_index_event_rows"]==old["parsed_index_event_rows"]=="0" and
                item["baseline_source_html_sha256"]==old["source_html_sha256"],
                "P2 historical source differs from frozen baseline/queue: "+str(v))
        require(item["zero_elections_inferred"]==item["original_event_page_verified"]=="0",
                "P2 queue must remain source-only and unresolved")
        records.append(dict(volume=v,**{k:old[k] for k in (
            "year","technical_status","parsed_index_event_rows","source_html_sha256")}))
    return {"baseline_sha256":baseline_sha,"review_queue":P2_REVIEW_QUEUE.as_posix(),
            "review_queue_sha256":P2_REVIEW_QUEUE_SHA,"prior_source_records":records}

def p2_source_comparison(prior_source_records,selected):
    """Compare recorded historical hashes with current bytes; do not claim old bytes exist."""
    return [{"volume":r["volume"],"baseline_source_html_sha256":r["source_html_sha256"],
             "current_source_html_sha256":selected[r["volume"]]["table_html_sha256"],
             "source_bytes_identical":r["source_html_sha256"]==selected[r["volume"]]["table_html_sha256"]}
            for r in prior_source_records]

def validate_revision_selection(checkpoint,selected,previous_ids,baseline_sha,baseline=None):
    """Bind revised source identities and recognized frozen revision scopes to inputs."""
    require(set(selected)<=previous_ids,"Revision attempted to add an unprobed volume")
    require(all(status(r["table_http_status"])=="HTTP_200" for r in selected.values()),"A failed fetch cannot replace prior evidence")
    for v,r in selected.items():
        year=1835+v//2
        require(r.get("year")==str(year) and r.get("wikisource_table_url")==build_urls(v,year)["wiki"],
                "Revision source URL/year differs from canonical volume: "+str(v))
    version=checkpoint.get("version")
    require(version in ("france-academy-shard02-grammar-revision-v2",P1_REVISION_VERSION,P2_REVISION_VERSION),
            "Unrecognized source revision version")
    if version=="france-academy-shard02-grammar-revision-v2":
        require(set(selected)=={37,98,128},"Shard02 grammar revision scope changed")
    if version==P1_REVISION_VERSION:
        require(checkpoint.get("volumes")==P1_VOLUMES and set(selected)==set(P1_VOLUMES),
                "P1 revision must contain the five frozen volumes in order")
        require(checkpoint.get("baseline_sha256")==baseline_sha,"P1 revision baseline SHA differs from input baseline")
        require(checkpoint.get("review_queue")==P1_REVIEW_QUEUE.as_posix(),"P1 revision review queue path changed")
        queue=REPO/P1_REVIEW_QUEUE
        require(sha(queue)==P1_REVIEW_QUEUE_SHA,"Frozen P1 review queue bytes changed")
        require(checkpoint.get("review_queue_sha256")==P1_REVIEW_QUEUE_SHA,"P1 revision review queue SHA differs from frozen queue")
        return {label(queue):P1_REVIEW_QUEUE_SHA}
    if version==P2_REVISION_VERSION:
        require(checkpoint.get("volumes")==P2_VOLUMES and set(selected)==set(P2_VOLUMES),
                "P2 revision must contain the sixteen frozen volumes in order")
        require("shard" not in checkpoint,"P2 is a prior-source revision, not a new shard")
        require(baseline is not None,"P2 requires the actual validated baseline records")
        provenance=p2_revision_provenance(baseline,baseline_sha)
        require(all(checkpoint.get(k)==v for k,v in provenance.items()),"P2 baseline/queue/historical source provenance differs")
        comparison=p2_source_comparison(provenance["prior_source_records"],selected)
        require(checkpoint.get("source_sha256_comparison")==comparison,"P2 old/current source SHA comparison differs")
        require(all(checkpoint.get(k)==0 for k in (
            "original_event_pages_inspected","accepted_memberships","accepted_birthdates","bazi_variables_computed")),
            "P2 checkpoint gates absent")
        require(all(r.get("original_printed_election_pages_directly_inspected")=="0" for r in selected.values()),
                "P2 inventory is not index-only")
        return {P2_REVIEW_QUEUE.as_posix():P2_REVIEW_QUEUE_SHA}
    return {}

def verify_batch(folder,cache_root):
    catalog=rows(folder/FILES[0]);summary=load(folder/FILES[1]);checkpoint=load(folder/FILES[2])
    ledger=load(folder/FILES[3]);stored=rows(folder/FILES[4])
    for obj in (catalog,summary,checkpoint,ledger,stored):gates(obj)
    all_volumes=unique(catalog,"Inventory")
    require(set(all_volumes)==set(range(1,212)),"Incomplete 211-volume inventory")
    selected=unique([r for r in catalog if r["table_sampled"]=="1"],"Selected sources")
    ids=[int(v) for v in checkpoint["volumes"]]
    require(len(ids)==len(set(ids)) and set(ids)==set(selected),"Checkpoint selection differs from inventory")
    require(summary.get("run_complete") is True and summary["table_probes_completed"]==len(ids),"Incomplete run")
    require(summary["category_volume_count"]==211 and summary["table_of_contents_probed_volumes"]==sorted(ids),"Run frame changed")
    require(ledger["source_sha256"]==sha(folder/FILES[0]),"Ledger inventory SHA mismatch")
    regenerated,audit=build(folder,cache_root)  # SHA-checked source bytes and current parser, no HTTP.
    signature=lambda records:Counter(tuple(r.get(k,"") for k in EVENT_FIELDS) for r in records)
    require(signature(regenerated)==signature(stored),"Reparsed events differ from stored person ledger")
    require(audit==ledger["source_replays"],"Per-volume replay audit differs from stored ledger")
    require(ledger["parsed_event_rows"]==summary["sample_election_event_candidates"]==len(stored),"Event totals disagree")
    require(ledger["event_classes"]==roles(stored),"Role totals disagree")
    require(ledger["source_200_bytes_checked"]==sum(status(r["status"])=="HTTP_200" for r in audit),"Readable-source count disagrees")
    require(ledger["selected_toc_volumes"]==len(ids),"Ledger selection size differs")
    http=Counter(status(r["table_http_status"]) for r in selected.values())
    declared=Counter()
    for key,n in summary["table_probe_http_status"].items():declared[status(key)]+=n
    require(http==declared and ledger["other_TOC_statuses_not_election_zero"]==len(ids)-http["HTTP_200"],"Source status totals disagree")
    if "parsed_candidate_event_rows" in checkpoint:
        require(checkpoint["parsed_candidate_event_rows"]==len(stored),"Checkpoint event count disagrees")
    for v,r in selected.items():
        require(int(r["year"])==1835+v//2,"Inventory year does not match volume")
        require(all(r.get(k)=="0" for k in ("study_membership_accepted","study_DOB_accepted","bazi_variables_computed")),"Inventory gates absent")
        s=status(r["table_http_status"])
        if s!="HTTP_200":
            require(s not in ("NOT_CHECKED","NOT_YET_PROBED","") and r["transcribed_election_rows"]=="",
                    "Failed source incorrectly recorded as historical zero: "+str(v))
    return selected,stored,checkpoint,{label(folder/name):sha(folder/name) for name in FILES}

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--baseline",type=Path,default=BASELINE)
    ap.add_argument("--revision-dir",type=Path,default=None)
    ap.add_argument("--shard-dir",type=Path,default=None)
    ap.add_argument("--revision-only",action="store_true",help="Apply the frozen P2 revision without a new shard")
    ap.add_argument("--cache-root",type=Path,default=Path("local_runs/france_academy_211_volume_inventory_source_cache_v1"))
    ap.add_argument("--out",type=Path,default=Path("data/france_academy_source_checkpoint_v2"))
    args=ap.parse_args()
    require(not args.revision_only or (args.revision_dir is not None and args.shard_dir is None),
            "--revision-only requires --revision-dir and forbids --shard-dir")
    require(sha(PLAN)==PLAN_SHA,"Frozen 172-volume plan bytes changed")
    plan=rows(PLAN);gates(plan);plan_by=unique(plan,"Plan")
    require(len(plan)==172,"Expected 172 frozen plan rows")
    baseline=read_baseline(args.baseline);combined=unique(baseline,"Baseline")
    old_total=counts(baseline);previous_ids=set(combined)
    input_hashes={label(args.baseline):sha(args.baseline),label(PLAN):sha(PLAN)}
    revised_events=[];new_events=[];revised_ids=[];replacement_old_total=0;resume_provenance={}
    groups=[];shard=None;new_shard_volume_count=0
    if args.revision_dir:groups.append(("REPARSED_PRIOR_SOURCE",args.revision_dir))
    if not args.revision_only:groups.append(("NEW_FROZEN_SHARD",args.shard_dir or BASE/"shard_03"))
    for kind,folder in groups:
        selected,events,checkpoint,hashes=verify_batch(folder,args.cache_root)
        input_hashes.update(hashes)
        if kind=="REPARSED_PRIOR_SOURCE":
            require((checkpoint.get("version")==P2_REVISION_VERSION)==args.revision_only,
                    "Frozen P2 requires --revision-only; this mode cannot substitute another revision")
            input_hashes.update(validate_revision_selection(checkpoint,selected,previous_ids,
                input_hashes[label(args.baseline)],baseline))
            revised_ids=sorted(selected);revised_events=events
            replacement_old_total=counts([combined[v] for v in revised_ids])
        else:
            shard=int(checkpoint["shard"])
            frozen=[int(r["volume"]) for r in sorted(plan,key=lambda r:int(r["sequence"])) if int(r["shard"])==shard]
            resume_provenance=validate_shard_selection(checkpoint,selected,previous_ids,args.baseline,frozen)
            if resume_provenance:
                require(resume_provenance["baseline_sha256"]==input_hashes[label(args.baseline)],"Baseline changed during verification")
            require(all(r["year"]==plan_by[v]["year"] and r["wikisource_table_url"]==plan_by[v]["wikisource_table_url"] for v,r in selected.items()),"Source URLs/year differ from frozen plan")
            new_events=events
            new_shard_volume_count=len(selected)
        for v,source in selected.items():
            old=combined.get(v);s=status(source["table_http_status"])
            combined[v]={"volume":str(v),"year":source["year"],
                "source_probe_group":old["source_probe_group"] if old else f"FROZEN_SHARD_{shard:02d}",
                "technical_status":s,"parsed_index_event_rows":source["transcribed_election_rows"],
                "index_event_semantics":"INDEX_EVENTS_ALL_ROLES_INCLUDING_OFFICES_NOT_FINAL_MEMBERS" if s=="HTTP_200" else "FAILED_TOC_UNKNOWN_NOT_HISTORICAL_ZERO",
                "source_html_sha256":source["table_html_sha256"],
                "baseline_parsed_index_event_rows":old["parsed_index_event_rows"] if old else "",
                "baseline_source_html_sha256":old["source_html_sha256"] if old else "",
                "revision_reason":checkpoint.get("revision_reason",checkpoint["version"]+";REPLAYED_CURRENT_SOURCE_BYTES") if old else "",
                "original_event_page_verified":"0","accepted_member":"0","accepted_exact_dob":"0","bazi":"0"}
    cumulative=[combined[v] for v in sorted(combined)]
    remaining=[r for r in plan if int(r["volume"]) not in combined]
    require(len(remaining)==211-len(cumulative),"Remaining plan does not cover all unprobed volumes")
    delta=len(revised_events)-replacement_old_total;total=counts(cumulative)
    require(total==old_total+delta+len(new_events),"Cumulative event arithmetic failed")
    added=[dict(r,update_kind=kind) for kind,items in (("REPARSED_PRIOR_SOURCE",revised_events),("NEW_FROZEN_SHARD",new_events)) for r in items]
    payloads={"cumulative_source_checked_unique_volumes_v2.csv":csv_bytes(cumulative,FIELDS),
              "remaining_source_queue_v2.csv":csv_bytes(remaining,list(plan[0])),
              "added_or_reparsed_index_events_v2.csv":csv_bytes(added,EVENT_FIELDS+["update_kind"])}
    summary={"version":VERSION,"parser_version":PARSER_VERSION,"input_SHA256":input_hashes,
        "previous_unique_volumes":len(baseline),"previous_index_event_rows":old_total,
        "reparsed_prior_volumes":revised_ids,"revision_previous_event_rows":replacement_old_total,
        "revision_reparsed_event_rows":len(revised_events),"grammar_revision_net_added_index_events":delta,
        "revision_role_counts":roles(revised_events),"new_frozen_shard":shard,
        "new_frozen_shard_volumes":new_shard_volume_count,"new_shard_index_event_rows":len(new_events),
        "new_shard_role_counts":roles(new_events),"unique_volumes_ever_TOC_probed":len(cumulative),
        "TOC_page_status_count":dict(Counter(r["technical_status"] for r in cumulative)),
        "candidate_original_journal_INDEX_events_including_all_roles_and_offices":total,
        "remaining_TOC_endpoints_never_tested":len(remaining),"failed_source_event_count":"UNKNOWN_NOT_ZERO",
        "counts_are_source_events_not_unique_people":True,"original_scan_evidence_not_inferred_from_TOC":True,
        "accepted_memberships":0,"accepted_exact_dobs":0,"bazi_variables_computed":0,"network_requests":0,
        "output_SHA256":{name:hashlib.sha256(data).hexdigest() for name,data in payloads.items()}}
    if resume_provenance.get("reused_prior_volumes"):
        summary["frozen_shard_resume"]=resume_provenance
    if args.revision_only:
        require(set(combined)==previous_ids,"A revision-only checkpoint cannot add or remove volumes")
        summary["revision_only"]=True
        summary["source_revision_net_added_index_events"]=delta
        summary["revision_delta_semantics"]="CURRENT_SOURCE_REPLACEMENT_EVENT_DELTA_NOT_ISOLATED_GRAMMAR_EFFECT"
        comparison=checkpoint["source_sha256_comparison"]
        same=sum(r["source_bytes_identical"] for r in comparison)
        summary["revision_source_sha256_comparison_counts"]={"same":same,"different":len(comparison)-same}
    payloads["summary.json"]=(json.dumps(summary,ensure_ascii=False,indent=2)+"\n").encode("utf-8")
    for name,data in payloads.items():
        path=args.out/name
        require(path.resolve()!=args.baseline.resolve(),"Choose a fresh --out; baseline is immutable")
        require(not path.exists() or path.read_bytes()==data,"Refusing to overwrite different checkpoint: "+str(path))
    args.out.mkdir(parents=True,exist_ok=True)
    for name,data in payloads.items():
        path=args.out/name
        if not path.exists():path.write_bytes(data)
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=="__main__":main()
