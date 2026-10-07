#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import json
import re
import unicodedata
import urllib.request
from collections import defaultdict
from pathlib import Path

OUT = Path("data/nas_science_core_dob_crosswalk")
OUT.mkdir(parents=True, exist_ok=True)

RICH_URL = "https://raw.githubusercontent.com/acepocalypse/ntl-academies-tracker/e0c6fc599d49f14b13926fe5478f956976512be9/snapshots/2023/20250909_134202.csv"
CARD_URL = "https://raw.githubusercontent.com/acepocalypse/ntl-academies-tracker/c38d5a827c63ce0f2017293ec58e56c34a4fd34b/snapshots/2023/20251015_135859.csv"
RICH_BLOB_SHA = "74f61f07c22c1ed68bb24b97be3085e727b5a873"
CARD_BLOB_SHA = "31ccca97537eab0fd4ba1df59874597f7a5c589a"
WIKIDATA_CSV = Path("data/nas_wikidata_dob_pilot/nas_wikidata_dob_collapsed.csv")

SCIENCE_CORE = {12,13,14,15,16,21,22,23,24,25,26,27,28,29,41,42,43,44}
DATE_RANGE_RE = re.compile(
    r"^\s*([A-Za-z]+)\s+(\d{1,2}),\s+(\d{4})\s*-\s*"
    r"([A-Za-z]+)\s+(\d{1,2}),\s+(\d{4})\s*$"
)
MONTHS = {
    "january":1,"february":2,"march":3,"april":4,"may":5,"june":6,
    "july":7,"august":8,"september":9,"october":10,"november":11,"december":12,
}

def download(url: str, path: Path) -> None:
    req = urllib.request.Request(url, headers={"User-Agent":"bazi-public-figure-study/1.0"})
    with urllib.request.urlopen(req, timeout=180) as r:
        path.write_bytes(r.read())

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024), b""):
            h.update(chunk)
    return h.hexdigest()

def read_csv(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

def write_csv(path: Path, rows, fields):
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w=csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader(); w.writerows(rows)

def secnum(s: str):
    m=re.search(r"(?:Section\s*)?(\d+)", s or "", re.I)
    return int(m.group(1)) if m else None

def is_regular(s: str) -> bool:
    s=s or ""
    if re.search(r"International|Resigned|Rescinded", s, re.I):
        return False
    return bool(re.search(r"Member|Emeritus", s, re.I))

def norm_name(s: str) -> str:
    s=unicodedata.normalize("NFKD", s or "")
    s="".join(c for c in s if not unicodedata.combining(c))
    s=s.casefold().replace("&"," and ")
    s=re.sub(r"[^a-z0-9]+"," ",s)
    return re.sub(r"\s+"," ",s).strip()

def relaxed_name(s: str) -> str:
    t=norm_name(s).split()
    if not t:
        return ""
    suffix={"jr","sr","ii","iii","iv"}
    while t and t[-1] in suffix:
        t.pop()
    if len(t)>=3:
        t=[x for i,x in enumerate(t) if not (0<i<len(t)-1 and len(x)==1)]
    return " ".join(t)

def card_birth_date(s: str):
    m=DATE_RANGE_RE.match((s or "").strip())
    if not m:
        return ""
    mon=MONTHS.get(m.group(1).casefold())
    if not mon:
        return ""
    return f"{int(m.group(3)):04d}-{mon:02d}-{int(m.group(2)):02d}"

def wd_date(s: str):
    m=re.search(r"([12]\d{3})-(\d{2})-(\d{2})", s or "")
    return "-".join(m.groups()) if m else ""

def unique_index(rows, keyfn, valuefn):
    tmp=defaultdict(set)
    for r in rows:
        k=keyfn(r)
        if k:
            tmp[k].add(valuefn(r))
    return {k:next(iter(v)) for k,v in tmp.items() if len(v)==1}, {k:v for k,v in tmp.items() if len(v)>1}

rich_path=OUT/"nas_tracker_rich_source.csv"
card_path=OUT/"nas_tracker_card_source.csv"
download(RICH_URL, rich_path)
download(CARD_URL, card_path)

rich=read_csv(rich_path)
card=read_csv(card_path)
wd=read_csv(WIKIDATA_CSV)

cohort=[
    r for r in rich
    if is_regular(r.get("membership_type","")) and secnum(r.get("primary_section","")) in SCIENCE_CORE
]
card_by_url={r.get("profile_url",""):r for r in card if r.get("profile_url")}

# Wikidata label rows are one row per QID after collapsing.
wd_by_qid={r["qid"]:r for r in wd if r.get("qid")}
label_rows=[]
for r in wd:
    labels=[x for x in (r.get("english_labels") or "").split("|") if x]
    for label in labels:
        label_rows.append({"label":label,"qid":r["qid"]})

wd_strict, wd_strict_amb = unique_index(label_rows, lambda r:norm_name(r["label"]), lambda r:r["qid"])
wd_relaxed, wd_relaxed_amb = unique_index(label_rows, lambda r:relaxed_name(r["label"]), lambda r:r["qid"])
nas_strict_counts=defaultdict(int)
nas_relaxed_counts=defaultdict(int)
for r in cohort:
    nas_strict_counts[norm_name(r["name"])]+=1
    nas_relaxed_counts[relaxed_name(r["name"])]+=1

out=[]
review=[]
for r in cohort:
    url=r["profile_url"]
    name=r["name"]
    deceased=(r.get("deceased")=="Y")
    c=card_by_url.get(url,{})
    card_dob=card_birth_date(c.get("affiliation",""))

    qid=""
    method=""
    sk=norm_name(name)
    rk=relaxed_name(name)
    if nas_strict_counts[sk]==1 and sk in wd_strict:
        qid=wd_strict[sk]; method="strict_unique_name"
    elif nas_relaxed_counts[rk]==1 and rk in wd_relaxed:
        qid=wd_relaxed[rk]; method="relaxed_unique_name"

    wr=wd_by_qid.get(qid,{}) if qid else {}
    exact_values=[wd_date(x) for x in (wr.get("exact_day_values") or "").split("|") if wd_date(x)]
    exact_values=sorted(set(exact_values))
    wd_conflict=int(wr.get("exact_day_conflict") or 0)==1 or len(exact_values)>1
    wd_dob=exact_values[0] if len(exact_values)==1 and not wd_conflict else ""

    source_conflict=bool(card_dob and wd_dob and card_dob!=wd_dob)
    if source_conflict:
        final_dob=""
        status="source_conflict_review"
    elif card_dob:
        final_dob=card_dob
        status="exact_nas_card_plus_wikidata_agree" if wd_dob else "exact_nas_card"
    elif wd_dob:
        final_dob=wd_dob
        status="exact_wikidata"
    elif wd_conflict:
        final_dob=""
        status="wikidata_exact_conflict_review"
    elif not qid:
        final_dob=""
        status="no_conservative_wikidata_match"
    else:
        final_dob=""
        status="matched_wikidata_no_unique_exact_day"

    row={
        "profile_url":url,
        "name":name,
        "election_year":r.get("year",""),
        "membership_type":r.get("membership_type",""),
        "deceased":r.get("deceased",""),
        "primary_section":r.get("primary_section",""),
        "secondary_section":r.get("secondary_section",""),
        "nas_card_exact_dob":card_dob,
        "wikidata_qid":qid,
        "wikidata_match_method":method,
        "wikidata_max_birthdate_precision":wr.get("max_birthdate_precision",""),
        "wikidata_exact_values":"|".join(exact_values),
        "wikidata_exact_conflict":int(wd_conflict),
        "source_conflict":int(source_conflict),
        "final_exact_dob":final_dob,
        "dob_status":status,
    }
    out.append(row)
    if not final_dob or source_conflict or wd_conflict:
        review.append(row)

fields=list(out[0].keys())
write_csv(OUT/"nas_science_core_dob_crosswalk.csv", out, fields)
write_csv(OUT/"nas_science_core_dob_review.csv", review, fields)

living=[x for x in out if x["deceased"]!="Y"]
dead=[x for x in out if x["deceased"]=="Y"]
summary={
    "cohort_definition":"regular NAS Member/Emeritus; primary section in 12-16,21-29,41-44; election years through 2025",
    "science_core_rows":len(out),
    "deceased_rows":len(dead),
    "living_rows":len(living),
    "nas_card_exact_dob":sum(bool(x["nas_card_exact_dob"]) for x in out),
    "wikidata_conservative_name_matches":sum(bool(x["wikidata_qid"]) for x in out),
    "wikidata_strict_unique_matches":sum(x["wikidata_match_method"]=="strict_unique_name" for x in out),
    "wikidata_relaxed_unique_matches":sum(x["wikidata_match_method"]=="relaxed_unique_name" for x in out),
    "wikidata_unique_exact_dob_after_match":sum(bool(x["wikidata_exact_values"]) and not int(x["wikidata_exact_conflict"]) for x in out),
    "source_conflicts":sum(int(x["source_conflict"]) for x in out),
    "wikidata_exact_conflict_rows":sum(int(x["wikidata_exact_conflict"]) for x in out),
    "final_exact_dob_rows":sum(bool(x["final_exact_dob"]) for x in out),
    "final_exact_dob_coverage":round(sum(bool(x["final_exact_dob"]) for x in out)/len(out),6),
    "deceased_final_exact_dob_rows":sum(bool(x["final_exact_dob"]) for x in dead),
    "deceased_final_exact_dob_coverage":round(sum(bool(x["final_exact_dob"]) for x in dead)/len(dead),6),
    "living_final_exact_dob_rows":sum(bool(x["final_exact_dob"]) for x in living),
    "living_final_exact_dob_coverage":round(sum(bool(x["final_exact_dob"]) for x in living)/len(living),6),
    "review_rows":len(review),
    "bazi_variables_computed":0,
    "sources":{
        "rich_tracker":{"url":RICH_URL,"git_blob_sha":RICH_BLOB_SHA,"sha256":sha256(rich_path)},
        "card_tracker":{"url":CARD_URL,"git_blob_sha":CARD_BLOB_SHA,"sha256":sha256(card_path)},
        "wikidata_collapsed":{"path":str(WIKIDATA_CSV),"sha256":sha256(WIKIDATA_CSV)},
    },
    "note":"No BaZi variables are computed. Name matching is conservative and only unique strict/relaxed keys are auto-accepted."
}
(OUT/"summary.json").write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding="utf-8")
print(json.dumps(summary,indent=2,ensure_ascii=False))
