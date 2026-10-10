#!/usr/bin/env python3
from __future__ import annotations
import csv, hashlib, json
from collections import Counter, defaultdict
from pathlib import Path

ROSTER=Path("data/royal_society_roster_freeze_v1/royal_society_fellows_roster_freeze_v1.csv")
PAST_ACCEPTED=Path("data/royal_society_past_dob_closeout_v1/accepted_exact_dob_final_v1.csv")
CURRENT_CANDIDATES=Path("data/royal_society_current_dob_candidate_v1/current_exact_dob_candidate_pool_v1.csv")
RECOVERY=Path("data/royal_society_current_dob_candidate_v1/authority_recovery_whitelist_v1.csv")
OUT=Path("data/royal_society_dob_freeze_v1")
LIBRARY_AUTHORITY_DOMAINS={"catalogue.bnf.fr","d-nb.info","aleph.nkp.cz"}

def read_csv(p):
    with p.open("r",encoding="utf-8-sig",newline="") as f:
        return list(csv.DictReader(f))

def write_csv(p,rows,fields):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore")
        w.writeheader(); w.writerows(rows)

def sha256(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for c in iter(lambda:f.read(1<<20),b""): h.update(c)
    return h.hexdigest()

def era(y):
    s=str(y or "").strip()
    if not s.isdigit(): return "unknown"
    y=int(s)
    if y<1900:return "pre-1900"
    if y<1950:return "1900-1949"
    if y<1980:return "1950-1979"
    if y<2000:return "1980-1999"
    if y<2010:return "2000-2009"
    if y<2020:return "2010-2019"
    return "2020-2025"

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    roster=read_csv(ROSTER)
    past=read_csv(PAST_ACCEPTED)
    cand=read_csv(CURRENT_CANDIDATES)
    recovery=read_csv(RECOVERY)

    if len(roster)!=8669 or len({r["cohort_key"] for r in roster})!=8669:
        raise RuntimeError(f"Roster invariant failed: rows={len(roster)} unique={len({r['cohort_key'] for r in roster})}")
    current_roster=[r for r in roster if r["status_at_source"]=="current"]
    past_roster=[r for r in roster if r["status_at_source"]=="past"]
    if len(current_roster)!=1570 or len(past_roster)!=7099:
        raise RuntimeError(f"Roster status split failed current={len(current_roster)} past={len(past_roster)}")

    if len(past)!=4884 or len({r["cohort_key"] for r in past})!=4884:
        raise RuntimeError(f"Past accepted invariant failed rows={len(past)}")
    past_map={r["cohort_key"]:r for r in past}
    if not set(past_map).issubset({r["cohort_key"] for r in past_roster}):
        raise RuntimeError("Past accepted contains keys outside frozen past roster")
    if any(not str(r.get("dob_exact_iso") or "").strip() for r in past):
        raise RuntimeError("Past accepted contains blank exact DOB")

    if len(cand)!=125 or len({r["cohort_key"] for r in cand})!=125:
        raise RuntimeError(f"Current candidate invariant failed rows={len(cand)}")
    current_keys={r["cohort_key"] for r in current_roster}
    if not {r["cohort_key"] for r in cand}.issubset(current_keys):
        raise RuntimeError("Current candidates contain keys outside frozen current roster")

    authority=[r for r in cand if (r.get("reference_domain") or "").strip().lower() in LIBRARY_AUTHORITY_DOMAINS]
    nonlibrary=[r for r in cand if r not in authority]
    if len(authority)!=43 or len(nonlibrary)!=82:
        raise RuntimeError(f"Expected 43 authority-only and 82 non-library candidates, got {len(authority)} and {len(nonlibrary)}")

    if len(recovery)!=17 or len({r["cohort_key"] for r in recovery})!=17:
        raise RuntimeError(f"Expected 17 independent recovery rows, got {len(recovery)}")
    recovery_map={r["cohort_key"]:r for r in recovery}
    authority_map={r["cohort_key"]:r for r in authority}
    if not set(recovery_map).issubset(set(authority_map)):
        raise RuntimeError("Recovery whitelist contains non-authority candidate")
    for k,rr in recovery_map.items():
        a=authority_map[k]
        if rr["display_name"].strip()!=a["display_name"].strip() or rr["candidate_dob"].strip()!=a["candidate_dob"].strip():
            raise RuntimeError(f"Recovery identity/DOB mismatch for {k}")
        if rr["decision"]!="recover" or not rr["independent_source_url"].strip():
            raise RuntimeError(f"Invalid recovery evidence row {k}")
        dom=rr["independent_source_url"].split("/")[2].lower()
        if dom in LIBRARY_AUTHORITY_DOMAINS:
            raise RuntimeError(f"Recovery source is still a library authority for {k}")

    accepted_current=[]
    for r in nonlibrary:
        accepted_current.append({
          "cohort_key":r["cohort_key"],
          "display_name":r["display_name"],
          "exact_dob":r["candidate_dob"],
          "dob_status":"exact_current_independent_nonlibrary",
          "provenance_source_url":r["reference_url"],
          "provenance_source_class":r["source_class"],
          "provenance_note":r["acceptance_reason"],
          "locator_source_url":"",
          "locator_source_domain":""
        })
    for k,rr in recovery_map.items():
        a=authority_map[k]
        accepted_current.append({
          "cohort_key":k,
          "display_name":a["display_name"],
          "exact_dob":a["candidate_dob"],
          "dob_status":"exact_current_authority_locator_independently_recovered",
          "provenance_source_url":rr["independent_source_url"],
          "provenance_source_class":rr["independent_source_class"],
          "provenance_note":rr["evidence_note"],
          "locator_source_url":a["reference_url"],
          "locator_source_domain":a["reference_domain"]
        })
    accepted_current=sorted(accepted_current,key=lambda r:r["cohort_key"])
    if len(accepted_current)!=99 or len({r["cohort_key"] for r in accepted_current})!=99:
        raise RuntimeError(f"Expected 99 final current exact DOBs, got {len(accepted_current)}")

    authority_audit=[]
    for a in sorted(authority,key=lambda r:r["cohort_key"]):
        rr=recovery_map.get(a["cohort_key"])
        authority_audit.append({
          "cohort_key":a["cohort_key"],
          "display_name":a["display_name"],
          "candidate_dob":a["candidate_dob"],
          "library_locator_domain":a["reference_domain"],
          "library_locator_url":a["reference_url"],
          "decision":"recovered_independent_nonlibrary" if rr else "downgraded_unresolved",
          "independent_source_url":rr["independent_source_url"] if rr else "",
          "independent_source_class":rr["independent_source_class"] if rr else "",
          "evidence_note":rr["evidence_note"] if rr else "Library-authority date retained as locator evidence only; targeted non-library exact-DOB search did not identify an acceptance-grade independent source."
        })
    if sum(r["decision"].startswith("recovered") for r in authority_audit)!=17:
        raise RuntimeError("Authority recovery count invariant failed")

    cur_map={r["cohort_key"]:r for r in accepted_current}
    cross=[]
    for rr in roster:
        k=rr["cohort_key"]
        base={
          "cohort_key":k,
          "status_at_source":rr["status_at_source"],
          "display_name":rr["display_name"],
          "membership_category":rr["membership_category"],
          "election_year":rr["election_year"],
          "source_roster_url":rr["source_url"],
          "final_exact_dob":"",
          "dob_status":"unresolved_exact_dob",
          "provenance_source_url":"",
          "provenance_source_class":"",
          "provenance_note":"",
          "locator_source_url":"",
          "locator_source_domain":""
        }
        if k in past_map:
            p=past_map[k]
            base.update({
              "final_exact_dob":p["dob_exact_iso"],
              "dob_status":"exact_royal_society_official_catalogue",
              "provenance_source_url":p["source_url"],
              "provenance_source_class":"royal_society_official_catalogue",
              "provenance_note":p.get("dob_adjudication","accepted_explicit_date_of_birth_field"),
            })
        elif k in cur_map:
            c=cur_map[k]
            base.update({
              "final_exact_dob":c["exact_dob"],
              "dob_status":c["dob_status"],
              "provenance_source_url":c["provenance_source_url"],
              "provenance_source_class":c["provenance_source_class"],
              "provenance_note":c["provenance_note"],
              "locator_source_url":c["locator_source_url"],
              "locator_source_domain":c["locator_source_domain"],
            })
        cross.append(base)

    exact=[r for r in cross if r["final_exact_dob"]]
    if len(exact)!=4983:
        raise RuntimeError(f"Expected 4983 exact DOBs overall, got {len(exact)}")
    if sum(r["status_at_source"]=="past" and bool(r["final_exact_dob"]) for r in cross)!=4884:
        raise RuntimeError("Past exact count changed")
    if sum(r["status_at_source"]=="current" and bool(r["final_exact_dob"]) for r in cross)!=99:
        raise RuntimeError("Current exact count changed")

    cp=OUT/"royal_society_fellows_dob_crosswalk_v1.csv"
    cf=["cohort_key","status_at_source","display_name","membership_category","election_year","source_roster_url","final_exact_dob","dob_status","provenance_source_url","provenance_source_class","provenance_note","locator_source_url","locator_source_domain"]
    write_csv(cp,cross,cf)
    cap=OUT/"royal_society_current_exact_dob_final_v1.csv"
    write_csv(cap,accepted_current,["cohort_key","display_name","exact_dob","dob_status","provenance_source_url","provenance_source_class","provenance_note","locator_source_url","locator_source_domain"])
    aap=OUT/"royal_society_current_authority_reaudit_v1.csv"
    write_csv(aap,authority_audit,["cohort_key","display_name","candidate_dob","library_locator_domain","library_locator_url","decision","independent_source_url","independent_source_class","evidence_note"])

    status_rows=[]
    for status in ("past","current","all"):
        subset=cross if status=="all" else [r for r in cross if r["status_at_source"]==status]
        n=len(subset); e=sum(bool(r["final_exact_dob"]) for r in subset)
        status_rows.append({"stratum":status,"rows":n,"exact_dob":e,"unresolved":n-e,"exact_dob_coverage":round(e/n,6)})
    sp=OUT/"missingness_by_status_v1.csv"
    write_csv(sp,status_rows,["stratum","rows","exact_dob","unresolved","exact_dob_coverage"])

    groups=defaultdict(list)
    for r in cross:
        groups[(r["status_at_source"],era(r["election_year"]))].append(r)
    era_rows=[]
    order=["pre-1900","1900-1949","1950-1979","1980-1999","2000-2009","2010-2019","2020-2025","unknown"]
    for status in ("past","current"):
        for e in order:
            subset=groups.get((status,e),[])
            if not subset: continue
            n=len(subset); x=sum(bool(r["final_exact_dob"]) for r in subset)
            era_rows.append({"status_at_source":status,"election_era":e,"rows":n,"exact_dob":x,"unresolved":n-x,"exact_dob_coverage":round(x/n,6)})
    ep=OUT/"missingness_by_election_era_v1.csv"
    write_csv(ep,era_rows,["status_at_source","election_era","rows","exact_dob","unresolved","exact_dob_coverage"])

    source_counts=Counter(r["provenance_source_class"] for r in accepted_current)
    summary={
      "dataset":"Royal Society primary Fellow exact-DOB freeze v1",
      "roster_rows":8669,
      "past_rows":7099,
      "current_rows":1570,
      "past_exact_dob":4884,
      "past_exact_dob_coverage":round(4884/7099,6),
      "current_raw_candidate_pool":125,
      "current_nonlibrary_candidates_retained":82,
      "current_library_authority_candidates_reaudited":43,
      "current_library_authority_candidates_independently_recovered":17,
      "current_library_authority_candidates_downgraded_unresolved":26,
      "current_exact_dob_final":99,
      "current_exact_dob_coverage":round(99/1570,6),
      "overall_exact_dob_final":4983,
      "overall_exact_dob_coverage":round(4983/8669,6),
      "overall_unresolved":3686,
      "current_accepted_source_class_counts":dict(sorted(source_counts.items())),
      "acceptance_policy":"Royal Society official structured DOB fields are accepted for past Fellows. For current Fellows, Wikidata/library authority records are locator-only; exact DOB requires an independent non-library source visibly stating the same day-month-year. This aligns the final freeze with the NAS v17 provenance standard.",
      "superseded_collection_note":"Draft PRs #36-#38 remain collection history and are not the final acceptance policy because some intermediate outputs treated library authorities as directly eligible.",
      "bazi_variables_computed":0
    }
    summary["files"]={
      cp.name:sha256(cp),
      cap.name:sha256(cap),
      aap.name:sha256(aap),
      sp.name:sha256(sp),
      ep.name:sha256(ep)
    }
    sump=OUT/"summary_v1.json"
    sump.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    freeze={
      "dataset":"Royal Society primary Fellow exact-DOB collection freeze v1",
      "cohort_rows":8669,
      "exact_dob_rows":4983,
      "exact_dob_coverage":round(4983/8669,6),
      "unresolved_rows":3686,
      "past_exact_dob_rows":4884,
      "current_exact_dob_rows":99,
      "crosswalk_sha256":sha256(cp),
      "current_exact_csv_sha256":sha256(cap),
      "authority_reaudit_sha256":sha256(aap),
      "missingness_status_sha256":sha256(sp),
      "missingness_era_sha256":sha256(ep),
      "freeze_status":"final",
      "collection_stop_rule":"Freeze broad Royal Society DOB acquisition after this provenance-aligned pass. Reopen only for a newly identified high-authority correction with independently auditable provenance, versioned before hierarchy outcome analysis.",
      "bazi_variables_computed":0
    }
    (OUT/"freeze_candidate_v1.json").write_text(json.dumps(freeze,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    print(json.dumps(freeze,ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
