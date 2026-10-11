#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import json
import re
import urllib.parse
from collections import Counter, defaultdict
from pathlib import Path

CANDIDATES = Path("data/leopoldina_dob_local_v1/candidate_unique_day_p569_v1.csv")
PERSON_CACHE = Path("data/leopoldina_p569_reference_local_v1/cache")
SOURCE_CATALOG = Path("data/leopoldina_p569_source_resolver_local_v1/stated_in_source_catalog_v1.csv")
V1_CONTENT = Path("data/leopoldina_p569_source_resolver_local_v1/content_source_candidate_records_v1.csv")
POLICY = Path("data/leopoldina_dob_source_policy_v1/trusted_source_registry_v1.csv")
OUT = Path("data/leopoldina_dob_source_discovery_v2")
YEAR_MIN = 1835
YEAR_MAX = 1985

def read_csv(path):
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

def write_csv(path, rows, fields):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

def sha256(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1<<20),b""):
            h.update(chunk)
    return h.hexdigest()

def valid_qid(v):
    return bool(re.fullmatch(r"Q\d+", str(v or "").strip()))

def entity_map(obj):
    entities=(obj or {}).get("entities",{})
    if isinstance(entities,list):
        return {str(x.get("id") or ""):x for x in entities if x.get("id")}
    return entities if isinstance(entities,dict) else {}

def load_person_cache():
    out={}
    files=sorted(PERSON_CACHE.glob("batch_*.json"))
    if not files:
        raise RuntimeError(f"No person cache files under {PERSON_CACHE}")
    for p in files:
        obj=json.loads(p.read_text(encoding="utf-8"))
        api=obj.get("api_response")
        if isinstance(api,dict):
            out.update(entity_map(api))
    if not out:
        raise RuntimeError("No person entities loaded from cache")
    return out, len(files)

def claim_strings(entity,pid):
    vals=[]
    for claim in (((entity or {}).get("claims") or {}).get(pid,[]) or []):
        dv=((claim or {}).get("mainsnak") or {}).get("datavalue")
        if not isinstance(dv,dict):
            continue
        v=dv.get("value")
        if isinstance(v,str) and v.strip():
            vals.append(v.strip())
    return sorted(set(vals))

def parse_formatter_items(raw):
    out=[]
    for item in str(raw or "").split("|"):
        if ":" not in item:
            continue
        pid,template=item.split(":",1)
        pid=pid.strip(); template=template.strip()
        if re.fullmatch(r"P\d+",pid) and "$1" in template:
            out.append((pid,template))
    return out

def formatter_url(template,value):
    encoded=urllib.parse.quote(str(value),safe="/:;,+@._~-")
    return template.replace("$1",encoded)

def source_hint(tier):
    return "institutional_or_archival_candidate" if tier=="A" else "content_source_candidate"

def main():
    for p in (CANDIDATES,SOURCE_CATALOG,V1_CONTENT,POLICY):
        if not p.exists():
            raise RuntimeError(f"Missing required input: {p}")

    candidates=read_csv(CANDIDATES)
    primary=[r for r in candidates if re.fullmatch(r"\d{4}-\d{2}-\d{2}",str(r.get("candidate_exact_dob") or "")) and YEAR_MIN <= int(r["candidate_exact_dob"][:4]) <= YEAR_MAX]
    if len(primary)!=2407:
        raise RuntimeError(f"Expected 2407 primary-window candidates, got {len(primary)}")

    catalog={r["source_qid"]:r for r in read_csv(SOURCE_CATALOG)}
    policy_rows=read_csv(POLICY)
    policy={}
    for r in policy_rows:
        q=r["source_qid"].strip()
        if not valid_qid(q):
            raise RuntimeError(f"Bad policy QID: {q}")
        if r["policy_tier"] not in {"A","B"}:
            raise RuntimeError(f"Unsupported tier for {q}: {r['policy_tier']}")
        allowed={x for x in r["allowed_properties"].split("|") if re.fullmatch(r"P\d+",x)}
        if not allowed:
            raise RuntimeError(f"No allowed_properties for {q}")
        if q not in catalog:
            raise RuntimeError(f"Policy source absent from source catalog: {q}")
        policy[q]={**r,"allowed_set":allowed}

    entities, cache_files=load_person_cache()
    by_qid={r["wikidata_qids"].strip():r for r in primary}
    missing=[q for q in by_qid if q not in entities]
    if missing:
        raise RuntimeError(f"Missing {len(missing)} primary candidate person entities from cache")

    fields=[
        "member_slug","display_name","wikidata_qid","candidate_exact_dob",
        "reference_hash","stated_in_qid","stated_in_label","stated_in_description",
        "source_policy_hint","source_main_property","source_record_id","source_record_url",
        "formatter_template","direct_reference_urls","reference_property_ids",
        "policy_tier","single_source_sufficient","independence_group","discovery_route",
        "content_verified","final_exact_dob","acceptance_status","bazi_variables_computed"
    ]

    rows=[]
    seen=set()

    # Route 1: retain existing P569-linked records, but only from the frozen trusted registry.
    for r in read_csv(V1_CONTENT):
        dob=str(r.get("candidate_exact_dob") or "")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}",dob):
            continue
        if not (YEAR_MIN <= int(dob[:4]) <= YEAR_MAX):
            continue
        sq=str(r.get("stated_in_qid") or "").strip()
        if sq not in policy:
            continue
        p=policy[sq]
        pid=str(r.get("source_main_property") or "").strip()
        if pid and pid not in p["allowed_set"]:
            continue
        rec={
            "member_slug":r.get("member_slug",""),"display_name":r.get("display_name",""),
            "wikidata_qid":r.get("wikidata_qid",""),"candidate_exact_dob":dob,
            "reference_hash":r.get("reference_hash",""),"stated_in_qid":sq,
            "stated_in_label":r.get("stated_in_label",""),"stated_in_description":r.get("stated_in_description",""),
            "source_policy_hint":source_hint(p["policy_tier"]),"source_main_property":pid,
            "source_record_id":r.get("source_record_id",""),"source_record_url":r.get("source_record_url",""),
            "formatter_template":r.get("formatter_template",""),"direct_reference_urls":r.get("direct_reference_urls",""),
            "reference_property_ids":r.get("reference_property_ids",""),
            "policy_tier":p["policy_tier"],"single_source_sufficient":p["single_source_sufficient"],
            "independence_group":p["independence_group"],"discovery_route":"existing_p569_reference",
            "content_verified":"","final_exact_dob":"","acceptance_status":"not_adjudicated","bazi_variables_computed":0,
        }
        k=(rec["member_slug"],sq,rec["source_main_property"],rec["source_record_id"],rec["source_record_url"],rec["direct_reference_urls"])
        if k not in seen:
            seen.add(k); rows.append(rec)

    # Route 2: locate trusted source records through pre-whitelisted external IDs on the exact person QID.
    for qid,r in sorted(by_qid.items(), key=lambda x:x[1]["member_slug"]):
        entity=entities[qid]
        for sq,p in policy.items():
            cat=catalog[sq]
            fmt_items=[x for x in parse_formatter_items(cat.get("formatter_templates","")) if x[0] in p["allowed_set"]]
            for pid in sorted(p["allowed_set"]):
                ids=claim_strings(entity,pid)
                if not ids:
                    continue
                fmts=[tpl for fp,tpl in fmt_items if fp==pid and "wikidata-externalid-url.toolforge.org" not in tpl]
                for rid in ids:
                    if not fmts:
                        # Preserve the discoverable ID even when the current source catalog lacks a direct formatter.
                        urls=[""]
                        templates=[""]
                    else:
                        urls=[formatter_url(t,rid) for t in fmts]
                        templates=fmts
                    for url,tpl in zip(urls,templates):
                        rec={
                            "member_slug":r["member_slug"],"display_name":r["display_name"],
                            "wikidata_qid":qid,"candidate_exact_dob":r["candidate_exact_dob"],
                            "reference_hash":"","stated_in_qid":sq,
                            "stated_in_label":cat.get("label",""),"stated_in_description":cat.get("description",""),
                            "source_policy_hint":source_hint(p["policy_tier"]),"source_main_property":pid,
                            "source_record_id":rid,"source_record_url":url,"formatter_template":tpl,
                            "direct_reference_urls":"","reference_property_ids":pid,
                            "policy_tier":p["policy_tier"],"single_source_sufficient":p["single_source_sufficient"],
                            "independence_group":p["independence_group"],"discovery_route":"person_external_id",
                            "content_verified":"","final_exact_dob":"","acceptance_status":"not_adjudicated","bazi_variables_computed":0,
                        }
                        k=(rec["member_slug"],sq,pid,rid,url,"")
                        if k not in seen:
                            seen.add(k); rows.append(rec)

    write_csv(OUT/"trusted_source_candidate_records_v2.csv",rows,fields)

    by_member=defaultdict(list)
    for x in rows:
        by_member[x["member_slug"]].append(x)
    coverage=[]
    for r in sorted(primary,key=lambda x:x["member_slug"]):
        rr=by_member.get(r["member_slug"],[])
        coverage.append({
            "member_slug":r["member_slug"],"display_name":r["display_name"],
            "wikidata_qid":r["wikidata_qids"],"candidate_exact_dob":r["candidate_exact_dob"],
            "trusted_source_record_rows":len(rr),
            "trusted_source_qid_count":len({x["stated_in_qid"] for x in rr}),
            "tier_a_source_qid_count":len({x["stated_in_qid"] for x in rr if x["policy_tier"]=="A"}),
            "tier_b_source_qid_count":len({x["stated_in_qid"] for x in rr if x["policy_tier"]=="B"}),
            "has_existing_p569_trusted_record":int(any(x["discovery_route"]=="existing_p569_reference" for x in rr)),
            "has_external_id_discovery":int(any(x["discovery_route"]=="person_external_id" for x in rr)),
            "needs_additional_source_discovery":int(not rr),
            "final_exact_dob":"","acceptance_status":"not_adjudicated","bazi_variables_computed":0,
        })
    cfields=list(coverage[0].keys())
    write_csv(OUT/"candidate_trusted_source_coverage_v2.csv",coverage,cfields)

    source_counts=Counter(x["stated_in_qid"] for x in rows)
    source_rows=[]
    for q,n in source_counts.most_common():
        p=policy[q]; cat=catalog[q]
        source_rows.append({
            "source_qid":q,"label":cat.get("label",""),"policy_tier":p["policy_tier"],
            "single_source_sufficient":p["single_source_sufficient"],"record_rows":n,
            "unique_candidates":len({x["member_slug"] for x in rows if x["stated_in_qid"]==q}),
        })
    write_csv(OUT/"source_yield_inventory_v2.csv",source_rows,["source_qid","label","policy_tier","single_source_sufficient","record_rows","unique_candidates"])

    summary={
        "dataset":"Leopoldina DOB trusted-source discovery v2",
        "year_min":YEAR_MIN,"year_max":YEAR_MAX,
        "primary_window_candidates":len(primary),
        "trusted_source_policy_rows":len(policy),
        "person_cache_files":cache_files,
        "person_entities_loaded":len(entities),
        "trusted_source_record_rows":len(rows),
        "candidates_with_any_trusted_source_record":sum(int(x["trusted_source_record_rows"])>0 for x in coverage),
        "candidates_with_tier_a_locator":sum(int(x["tier_a_source_qid_count"])>0 for x in coverage),
        "candidates_with_two_plus_tier_b_locators":sum(int(x["tier_b_source_qid_count"])>=2 for x in coverage),
        "candidates_with_no_trusted_source_record":sum(int(x["trusted_source_record_rows"])==0 for x in coverage),
        "route_counts":dict(sorted(Counter(x["discovery_route"] for x in rows).items())),
        "input_sha256":{
            "candidates":sha256(CANDIDATES),"source_catalog":sha256(SOURCE_CATALOG),
            "v1_content":sha256(V1_CONTENT),"policy":sha256(POLICY)
        },
        "final_exact_dob_written":0,"automatic_acceptance":0,"bazi_variables_computed":0,
        "rule":"Trusted sources are located through pre-whitelisted external-ID properties on exact person QIDs. Wikidata is a locator only; target source content must still be verified."
    }
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
