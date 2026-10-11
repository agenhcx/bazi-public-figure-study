#!/usr/bin/env python3
from __future__ import annotations
import csv,hashlib,json
from collections import Counter
from datetime import date
from pathlib import Path

SRC=Path("data/leopoldina_official_static_checkpoint_input/accepted_exact_dob_2009_2019_v1.csv")
ROSTER=Path("data/leopoldina_roster_freeze_v1/leopoldina_science_core_roster_freeze_v1.csv")
OUT=Path("data/leopoldina_official_static_dob_v1")
EXPECTED_YEARS={2010:37,2012:33,2013:40,2014:35,2016:34,2017:31,2018:38}
SOURCE_STATES=[
 {"election_year":2009,"status":"official_archive_pow_blocked","locator":"https://levana.leopoldina.org/servlets/MCRFileNodeServlet/leopoldina_derivate_00308/2009_Leopoldina_Neugewaehlte_Mitglieder.pdf","note":"Official Levana PDF locator is known, but current GitHub Actions requests are redirected to a proof-of-work challenge; no rows accepted from this source state."},
 {"election_year":2011,"status":"official_archive_pow_blocked","locator":"https://levana.leopoldina.org/servlets/MCRFileNodeServlet/leopoldina_derivate_00781/2011_Leopoldina_Neugewaehlte_Mitglieder.pdf","note":"Official Levana PDF locator is known, but current GitHub Actions requests are redirected to a proof-of-work challenge; no rows accepted from this source state."},
 {"election_year":2015,"status":"no_verified_current_pdf_locator","locator":"https://levana.leopoldina.org/receive/leopoldina_mods_00454","note":"Official publication page currently points its PDF button to an unrelated document; the correct open-access record is known but not an auditable current direct PDF source in this pass."},
 {"election_year":2019,"status":"official_archive_pow_blocked","locator":"https://levana.leopoldina.org/servlets/MCRFileNodeServlet/leopoldina_derivate_00170/2019_Leopoldina_Neugewaehlte_Mitglieder.pdf","note":"Official Levana PDF locator is known, but current GitHub Actions requests are redirected to a proof-of-work challenge; no rows accepted from this source state."}
]

def read_csv(p):
    with p.open("r",encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
def write_csv(p,rows,fields):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore");w.writeheader();w.writerows(rows)
def sha256(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for c in iter(lambda:f.read(1<<20),b""):h.update(c)
    return h.hexdigest()

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    rows=read_csv(SRC); roster=read_csv(ROSTER); rmap={r["member_slug"]:r for r in roster}
    if len(rows)!=248:raise RuntimeError(f"Expected 248 accepted official-static rows, got {len(rows)}")
    if len({r["member_slug"] for r in rows})!=248:raise RuntimeError("Duplicate accepted member_slug")
    yc=Counter(int(r["election_year"]) for r in rows)
    if dict(sorted(yc.items()))!=EXPECTED_YEARS:raise RuntimeError(f"Unexpected accepted year counts: {dict(sorted(yc.items()))}")
    for r in rows:
        if r["decision"]!="accept_official_new_member_profile_exact_dob" or r.get("source_status")!="available":
            raise RuntimeError(f"Non-accepted/non-available row in frozen accepted artifact: {r['member_slug']}")
        if r["member_slug"] not in rmap:raise RuntimeError(f"Accepted row outside frozen roster: {r['member_slug']}")
        rr=rmap[r["member_slug"]]
        if rr["election_year"]!=r["election_year"]:raise RuntimeError(f"Election-year mismatch: {r['member_slug']}")
        try:date.fromisoformat(r["candidate_dob"])
        except Exception:raise RuntimeError(f"Invalid ISO DOB: {r['member_slug']} {r['candidate_dob']}")
    rows=sorted(rows,key=lambda r:(int(r["election_year"]),r["member_slug"]))
    ap=OUT/"accepted_exact_dob_static_volumes_v1.csv"
    write_csv(ap,rows,list(rows[0].keys()))
    sp=OUT/"blocked_or_unverified_official_years_v1.csv"
    write_csv(sp,SOURCE_STATES,["election_year","status","locator","note"])
    summary={
      "dataset":"Leopoldina official static new-member-volume exact-DOB checkpoint v1",
      "accepted_exact_dob":248,
      "accepted_by_election_year":dict(sorted(yc.items())),
      "accepted_years":sorted(EXPECTED_YEARS),
      "blocked_or_unverified_years":[2009,2011,2015,2019],
      "acceptance_rule":"Exact DOB is accepted only from a successfully retrieved official Leopoldina new-member PDF, on the frozen member's profile page, with the starred birth marker and unique plausible day-month-year. Rows are restricted to the immutable Leopoldina science-core roster.",
      "accepted_csv_sha256":sha256(ap),
      "source_state_csv_sha256":sha256(sp),
      "source_artifact":{"workflow_run_id":38097235061,"artifact_id":11686950396,"artifact_name":"leopoldina-new-member-dob-official-v1","artifact_zip_sha256":"a6ea29d60a2c6ba25c52e6b6a43934df15ad5674201a8c421cdb9af60b59f43d"},
      "bazi_variables_computed":0
    }
    (OUT/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=="__main__":main()
