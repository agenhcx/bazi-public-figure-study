#!/usr/bin/env python3
from __future__ import annotations
import csv,json,re,unicodedata
from collections import Counter,defaultdict
from pathlib import Path

ROSTER=Path("data/leopoldina_roster_freeze_v1/leopoldina_science_core_roster_freeze_v1.csv")
TXT=Path("data/leopoldina_2015_crosswalk_input_v1/2015_Leopoldina_Mitgliederverzeichnis_02.txt")
OUT=Path("data/leopoldina_2015_pdf_crosswalk_diagnostic_v1")
DATE=re.compile(r"^\*\s*([0-3]?\d)\.([01]?\d)\.((?:18|19|20)\d{2})\s*$")
YEAR=re.compile(r"^(16|17|18|19|20)\d{2}$")

def read_csv(p):
    with p.open("r",encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
def norm(s):
    s=unicodedata.normalize("NFKD",s or "")
    s="".join(c for c in s if not unicodedata.combining(c)).lower()
    s=re.sub(r"\b(?:prof|professor|dr|sir|dame|freiherr|frhr)\b"," ",s)
    return re.sub(r"[^a-z0-9]+","",s)
def invert_pdf_name(s):
    if "," not in s:return s
    a,b=s.split(",",1)
    return (b.strip()+" "+a.strip()).strip()
def plausible_name(s):
    if not s or len(s)>120 or "," not in s:return False
    if re.search(r"\b(?:name|sektion|section|anschrift|address|jahr|year)\b",s,re.I):return False
    return bool(re.search(r"[A-Za-zÄÖÜäöüß]",s))
def main():
    OUT.mkdir(parents=True,exist_ok=True)
    roster=read_csv(ROSTER)
    if len(roster)!=2888:raise RuntimeError(f"Expected 2888 frozen roster rows, got {len(roster)}")
    lines=[x.strip() for x in TXT.read_text(encoding="utf-8",errors="replace").splitlines()]
    raw=[]
    for i,line in enumerate(lines):
        m=DATE.fullmatch(line)
        if not m:continue
        name=""
        for j in range(i-1,max(-1,i-7),-1):
            if plausible_name(lines[j]):
                name=lines[j];break
        ey=""
        for j in range(i+1,min(len(lines),i+13)):
            if YEAR.fullmatch(lines[j]):
                y=int(lines[j])
                if 1652<=y<=2015:
                    ey=str(y);break
        dob=f"{m.group(3)}-{m.group(2).zfill(2)}-{m.group(1).zfill(2)}"
        raw.append({"pdf_line":i+1,"pdf_name":name,"pdf_name_inverted":invert_pdf_name(name),"dob":dob,"election_year":ey})
    if len(raw)!=1612:raise RuntimeError(f"Expected 1612 exact DOB lines from diagnostic, got {len(raw)}")
    index=defaultdict(list)
    for r in roster:
        index[(norm(r["display_name"]),r["election_year"])].append(r)
    out=[]
    for x in raw:
        key=(norm(x["pdf_name_inverted"]),x["election_year"])
        cand=index.get(key,[])
        status="unique_exact_name_year" if len(cand)==1 else ("ambiguous_exact_name_year" if len(cand)>1 else "unmatched")
        z={**x,"match_status":status,"candidate_count":len(cand),"cohort_key":cand[0]["cohort_key"] if len(cand)==1 else "","roster_name":cand[0]["display_name"] if len(cand)==1 else "","roster_class":cand[0]["class"] if len(cand)==1 else "","roster_section":cand[0]["section"] if len(cand)==1 else ""}
        out.append(z)
    counts=Counter(x["match_status"] for x in out)
    matched=[x for x in out if x["match_status"]=="unique_exact_name_year"]
    # guard against duplicate PDF dates mapping to same frozen member
    dupkeys=[k for k,v in Counter(x["cohort_key"] for x in matched).items() if v>1]
    fields=list(out[0].keys())
    with (OUT/"crosswalk_diagnostic_v1.csv").open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(out)
    summary={
      "dataset":"Leopoldina 2015 official directory exact-DOB crosswalk diagnostic v1",
      "pdf_exact_dob_records":len(raw),
      "parse_missing_name":sum(not x["pdf_name"] for x in raw),
      "parse_missing_election_year":sum(not x["election_year"] for x in raw),
      "match_status_counts":dict(counts),
      "unique_frozen_science_roster_matches":len(matched),
      "unique_matched_by_class":dict(Counter(x["roster_class"] for x in matched)),
      "duplicate_pdf_records_to_same_cohort_key":len(dupkeys),
      "duplicate_cohort_keys":dupkeys[:30],
      "unmatched_sample":[x for x in out if x["match_status"]=="unmatched"][:40],
      "acceptance_performed":0,
      "bazi_variables_computed":0
    }
    (OUT/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
