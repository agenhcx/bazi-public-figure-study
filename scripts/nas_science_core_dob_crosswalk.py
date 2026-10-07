#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import json
import re
import unicodedata
import urllib.parse
import urllib.request
import urllib.error
import time
from collections import defaultdict
from pathlib import Path

OUT = Path("data/nas_science_core_dob_crosswalk")
OUT.mkdir(parents=True, exist_ok=True)

RICH_URL = "https://raw.githubusercontent.com/acepocalypse/ntl-academies-tracker/e0c6fc599d49f14b13926fe5478f956976512be9/snapshots/2023/20250909_134202.csv"
CARD_URL = "https://raw.githubusercontent.com/acepocalypse/ntl-academies-tracker/c38d5a827c63ce0f2017293ec58e56c34a4fd34b/snapshots/2023/20251015_135859.csv"
RICH_BLOB_SHA = "74f61f07c22c1ed68bb24b97be3085e727b5a873"
CARD_BLOB_SHA = "31ccca97537eab0fd4ba1df59874597f7a5c589a"
WIKIDATA_CSV = Path("data/nas_wikidata_dob_pilot/nas_wikidata_dob_collapsed.csv")
QLEVER = "https://qlever.dev/api/wikidata"

SCIENCE_CORE = {12,13,14,15,16,21,22,23,24,25,26,27,28,29,41,42,43,44}
DATE_RANGE_RE = re.compile(
    r"^\s*([A-Za-z]+)\s+(\d{1,2}),\s+(\d{4})\s*-\s*"
    r"([A-Za-z]+)\s+(\d{1,2}),\s+(\d{4})\s*$"
)
MONTHS = {
    "january":1,"february":2,"march":3,"april":4,"may":5,"june":6,
    "july":7,"august":8,"september":9,"october":10,"november":11,"december":12,
}
GENERIC_AFFILIATION_TOKENS = {
    "university","college","school","institute","institution","center","centre",
    "department","laboratory","lab","national","medical","medicine","science",
    "sciences","research","the","of","for","and","inc","corporation","company",
}

def download(url: str, path: Path) -> None:
    req=urllib.request.Request(url,headers={"User-Agent":"bazi-public-figure-study/1.0"})
    with urllib.request.urlopen(req,timeout=180) as r:
        path.write_bytes(r.read())

def sha256(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""):
            h.update(chunk)
    return h.hexdigest()

def read_csv(path: Path):
    with path.open("r",encoding="utf-8-sig",newline="") as f:
        return list(csv.DictReader(f))

def write_csv(path: Path,rows,fields):
    with path.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore")
        w.writeheader(); w.writerows(rows)

def secnum(s: str):
    m=re.search(r"(?:Section\s*)?(\d+)",s or "",re.I)
    return int(m.group(1)) if m else None

def is_regular(s: str) -> bool:
    s=s or ""
    if re.search(r"International|Resigned|Rescinded",s,re.I):
        return False
    return bool(re.search(r"Member|Emeritus",s,re.I))

def norm_name(s: str) -> str:
    s=unicodedata.normalize("NFKD",s or "")
    s="".join(c for c in s if not unicodedata.combining(c))
    s=s.casefold().replace("&"," and ")
    s=re.sub(r"[^a-z0-9]+"," ",s)
    return re.sub(r"\s+"," ",s).strip()

def relaxed_name(s: str) -> str:
    t=norm_name(s).split()
    if not t: return ""
    suffix={"jr","sr","ii","iii","iv"}
    while t and t[-1] in suffix: t.pop()
    if len(t)>=3:
        t=[x for i,x in enumerate(t) if not (0<i<len(t)-1 and len(x)==1)]
    return " ".join(t)

def card_birth_date(s: str) -> str:
    m=DATE_RANGE_RE.match((s or "").strip())
    if not m: return ""
    mon=MONTHS.get(m.group(1).casefold())
    if not mon: return ""
    return f"{int(m.group(3)):04d}-{mon:02d}-{int(m.group(2)):02d}"

def wd_date(s: str) -> str:
    m=re.search(r"([12]\d{3})-(\d{2})-(\d{2})",s or "")
    return "-".join(m.groups()) if m else ""

def unique_index(rows,keyfn,valuefn):
    tmp=defaultdict(set)
    for r in rows:
        k=keyfn(r)
        if k: tmp[k].add(valuefn(r))
    return (
        {k:next(iter(v)) for k,v in tmp.items() if len(v)==1},
        {k:v for k,v in tmp.items() if len(v)>1},
    )

def run_sparql(query: str, retries: int = 5):
    body=urllib.parse.urlencode({"query":query,"action":"tsv_export"}).encode("utf-8")
    last=None
    for attempt in range(retries):
        req=urllib.request.Request(
            QLEVER,data=body,method="POST",
            headers={
                "User-Agent":"bazi-public-figure-study/1.0 NAS global-name DOB supplement",
                "Content-Type":"application/x-www-form-urlencoded",
                "Accept":"text/tab-separated-values",
            },
        )
        try:
            with urllib.request.urlopen(req,timeout=300) as resp:
                raw=resp.read()
            break
        except urllib.error.HTTPError as e:
            last=e
            if e.code not in {429,500,502,503,504} or attempt+1>=retries:
                raise
        except urllib.error.URLError as e:
            last=e
            if attempt+1>=retries:
                raise
        time.sleep(min(30, 2**attempt))
    else:
        raise RuntimeError(f"QLever request failed after {retries} attempts: {last}")
    rows=list(csv.reader(raw.decode("utf-8-sig").splitlines(),delimiter="\t"))
    if not rows: return []
    headers=[x.lstrip("?").strip() for x in rows[0]]
    out=[]
    for r in rows[1:]:
        if not r: continue
        r=r+[""]*(len(headers)-len(r))
        item={}
        for i,h in enumerate(headers):
            s=(r[i] or "").strip()
            if s.startswith("<") and s.endswith(">"): s=s[1:-1]
            elif len(s)>=2 and s[0]=='"' and '"' in s[1:]:
                end=s.rfind('"'); s=s[1:end]
            s=re.sub(r"@[A-Za-z][A-Za-z0-9-]*$","",s)
            item[h]=s
        out.append(item)
    return out

def sparql_literal(s: str) -> str:
    return json.dumps(s,ensure_ascii=False)+"@en"

def chunks(seq,n=80):
    for i in range(0,len(seq),n):
        yield seq[i:i+n]

def global_exact_name_lookup(names):
    # Exact official NAS name only. This is a supplement, not fuzzy matching.
    found=defaultdict(set)
    for batch in chunks(sorted(set(names))):
        vals=" ".join(sparql_literal(x) for x in batch)
        query=f"""
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX wd: <http://www.wikidata.org/entity/>
SELECT DISTINCT ?query_name ?person WHERE {{
  VALUES ?query_name {{ {vals} }}
  {{
    ?person rdfs:label ?query_name .
  }} UNION {{
    ?person skos:altLabel ?query_name .
  }}
  ?person wdt:P31 wd:Q5 .
}}
"""
        for r in run_sparql(query):
            name=r.get("query_name",""); person=r.get("person","")
            if name and person: found[name].add(person.rsplit("/",1)[-1])
    return found

def global_person_details(qids):
    details=defaultdict(lambda:{"dob_values":[],"employers":[]})
    for batch in chunks(sorted(set(qids)),120):
        vals=" ".join("wd:"+q for q in batch if re.fullmatch(r"Q\d+",q))
        if not vals: continue
        dobq=f"""
PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX p: <http://www.wikidata.org/prop/>
PREFIX psv: <http://www.wikidata.org/prop/statement/value/>
PREFIX wikibase: <http://wikiba.se/ontology#>
SELECT DISTINCT ?person ?dob ?precision WHERE {{
  VALUES ?person {{ {vals} }}
  ?person p:P569 ?stmt .
  ?stmt psv:P569 ?value .
  ?value wikibase:timeValue ?dob ;
         wikibase:timePrecision ?precision .
}}
"""
        for r in run_sparql(dobq):
            q=r.get("person","").rsplit("/",1)[-1]
            try: prec=int(r.get("precision",""))
            except Exception: continue
            if prec>=11 and r.get("dob"):
                d=wd_date(r["dob"])
                if d: details[q]["dob_values"].append(d)

        empq=f"""
PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT DISTINCT ?person ?orgLabel WHERE {{
  VALUES ?person {{ {vals} }}
  {{
    ?person wdt:P108 ?org .
  }} UNION {{
    ?person wdt:P1416 ?org .
  }}
  ?org rdfs:label ?orgLabel .
  FILTER(LANG(?orgLabel)="en")
}}
"""
        for r in run_sparql(empq):
            q=r.get("person","").rsplit("/",1)[-1]
            if r.get("orgLabel"): details[q]["employers"].append(r["orgLabel"])
    return details

def affiliation_tokens(s: str):
    return {
        x for x in norm_name(s).split()
        if len(x)>2 and x not in GENERIC_AFFILIATION_TOKENS
    }

def affiliation_matches(a: str, employers) -> bool:
    at=affiliation_tokens(a)
    if not at: return False
    for e in employers:
        et=affiliation_tokens(e)
        if et and at.intersection(et):
            return True
    return False

def age_at_election(dob: str,election_year: str):
    try: return int(election_year)-int(dob[:4])
    except Exception: return None

rich_path=OUT/"nas_tracker_rich_source.csv"
card_path=OUT/"nas_tracker_card_source.csv"
download(RICH_URL,rich_path)
download(CARD_URL,card_path)
rich=read_csv(rich_path)
card=read_csv(card_path)
wd=read_csv(WIKIDATA_CSV)

cohort=[
    r for r in rich
    if is_regular(r.get("membership_type",""))
    and secnum(r.get("primary_section","")) in SCIENCE_CORE
]
card_by_url={r.get("profile_url",""):r for r in card if r.get("profile_url")}

wd_by_qid={r["qid"]:r for r in wd if r.get("qid")}
label_rows=[]
for r in wd:
    for label in [x for x in (r.get("english_labels") or "").split("|") if x]:
        label_rows.append({"label":label,"qid":r["qid"]})

wd_strict,_=unique_index(label_rows,lambda r:norm_name(r["label"]),lambda r:r["qid"])
wd_relaxed,_=unique_index(label_rows,lambda r:relaxed_name(r["label"]),lambda r:r["qid"])
nas_strict_counts=defaultdict(int); nas_relaxed_counts=defaultdict(int)
for r in cohort:
    nas_strict_counts[norm_name(r["name"])]+=1
    nas_relaxed_counts[relaxed_name(r["name"])]+=1

# First-pass candidate-universe matches.
pre_match={}
unmatched_names=[]
for r in cohort:
    name=r["name"]; sk=norm_name(name); rk=relaxed_name(name)
    qid=""; method=""
    if nas_strict_counts[sk]==1 and sk in wd_strict:
        qid=wd_strict[sk]; method="strict_unique_name"
    elif nas_relaxed_counts[rk]==1 and rk in wd_relaxed:
        qid=wd_relaxed[rk]; method="relaxed_unique_name"
    pre_match[r["profile_url"]]=(qid,method)
    if not qid: unmatched_names.append(name)

# Global exact-label/alias supplement only for rows missed by the NAS-candidate universe.
global_name_hits=global_exact_name_lookup(unmatched_names)
unique_global={
    name:next(iter(qids))
    for name,qids in global_name_hits.items() if len(qids)==1
}
global_details=global_person_details(unique_global.values())

out=[]; review=[]
for r in cohort:
    url=r["profile_url"]; name=r["name"]
    c=card_by_url.get(url,{})
    card_dob=card_birth_date(c.get("affiliation",""))

    qid,method=pre_match[url]
    global_name_match_count=len(global_name_hits.get(name,set()))
    global_affiliation_match=0
    global_candidate_qid=""
    global_accepted=0
    if not qid and name in unique_global:
        gqid=unique_global[name]
        global_candidate_qid=gqid
        det=global_details.get(gqid,{})
        gdobs=sorted(set(det.get("dob_values",[])))
        token_count=len(norm_name(name).split())
        global_affiliation_match=int(affiliation_matches(r.get("affiliation",""),det.get("employers",[])))
        # Conservative auto-accept:
        # exact official NAS name -> one human Wikidata item; require either a
        # specific 3+ token name or an affiliation corroboration.
        if len(gdobs)==1 and (token_count>=3 or global_affiliation_match):
            qid=gqid; method="global_exact_name_unique"; global_accepted=1

    if method=="global_exact_name_unique":
        det=global_details.get(qid,{})
        exact_values=sorted(set(det.get("dob_values",[])))
        wr={}
        wd_conflict=len(exact_values)>1
    else:
        wr=wd_by_qid.get(qid,{}) if qid else {}
        exact_values=sorted(set(
            wd_date(x) for x in (wr.get("exact_day_values") or "").split("|")
            if wd_date(x)
        ))
        wd_conflict=(int(wr.get("exact_day_conflict") or 0)==1 or len(exact_values)>1)

    wd_dob=exact_values[0] if len(exact_values)==1 and not wd_conflict else ""
    age=age_at_election(wd_dob,r.get("year","")) if wd_dob else None
    age_plausible=(age is None or (25<=age<=100))
    source_conflict=bool(card_dob and wd_dob and card_dob!=wd_dob)

    # Source priority: NAS card is primary for deceased profiles. A Wikidata
    # discrepancy remains a QA flag but does not erase an official-card DOB.
    if card_dob:
        final_dob=card_dob
        if source_conflict:
            status="exact_nas_card_wikidata_conflict"
        elif wd_dob:
            status="exact_nas_card_plus_wikidata_agree"
        else:
            status="exact_nas_card"
    elif wd_dob and age_plausible:
        final_dob=wd_dob
        status="exact_wikidata_global_name" if method=="global_exact_name_unique" else "exact_wikidata"
    elif wd_dob and not age_plausible:
        final_dob=""
        status="wikidata_implausible_election_age_review"
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
        "affiliation":r.get("affiliation",""),
        "election_year":r.get("year",""),
        "membership_type":r.get("membership_type",""),
        "deceased":r.get("deceased",""),
        "primary_section":r.get("primary_section",""),
        "secondary_section":r.get("secondary_section",""),
        "nas_card_exact_dob":card_dob,
        "wikidata_qid":qid,
        "wikidata_match_method":method,
        "wikidata_max_birthdate_precision":wr.get("max_birthdate_precision","") if wr else "",
        "wikidata_exact_values":"|".join(exact_values),
        "wikidata_exact_conflict":int(wd_conflict),
        "wikidata_age_at_election":age if age is not None else "",
        "wikidata_age_plausible":int(age_plausible) if wd_dob else "",
        "source_conflict":int(source_conflict),
        "global_exact_name_match_count":global_name_match_count,
        "global_candidate_qid":global_candidate_qid,
        "global_affiliation_match":global_affiliation_match,
        "global_match_accepted":global_accepted,
        "final_exact_dob":final_dob,
        "dob_status":status,
    }
    out.append(row)
    if not final_dob or source_conflict or wd_conflict or not age_plausible:
        review.append(row)

fields=list(out[0].keys())
write_csv(OUT/"nas_science_core_dob_crosswalk.csv",out,fields)
write_csv(OUT/"nas_science_core_dob_review.csv",review,fields)

# Save supplement diagnostics separately.
global_rows=[]
for name,qids in sorted(global_name_hits.items()):
    for q in sorted(qids):
        det=global_details.get(q,{})
        global_rows.append({
            "nas_name":name,
            "qid":q,
            "match_count_for_name":len(qids),
            "exact_dob_values":"|".join(sorted(set(det.get("dob_values",[])))),
            "employers":"|".join(sorted(set(det.get("employers",[])))),
            "unique_name_candidate":int(len(qids)==1),
        })
write_csv(
    OUT/"nas_global_exact_name_supplement.csv",
    global_rows,
    ["nas_name","qid","match_count_for_name","exact_dob_values","employers","unique_name_candidate"],
)

living=[x for x in out if x["deceased"]!="Y"]
dead=[x for x in out if x["deceased"]=="Y"]
summary={
    "cohort_definition":"regular NAS Member/Emeritus; primary section in 12-16,21-29,41-44; election years through 2025",
    "science_core_rows":len(out),
    "deceased_rows":len(dead),
    "living_rows":len(living),
    "nas_card_exact_dob":sum(bool(x["nas_card_exact_dob"]) for x in out),
    "wikidata_candidate_universe_matches":sum(x["wikidata_match_method"] in {"strict_unique_name","relaxed_unique_name"} for x in out),
    "wikidata_strict_unique_matches":sum(x["wikidata_match_method"]=="strict_unique_name" for x in out),
    "wikidata_relaxed_unique_matches":sum(x["wikidata_match_method"]=="relaxed_unique_name" for x in out),
    "global_exact_name_queries":len(set(unmatched_names)),
    "global_names_with_any_human_match":sum(bool(v) for v in global_name_hits.values()),
    "global_names_with_unique_human_match":len(unique_global),
    "global_matches_accepted":sum(int(x["global_match_accepted"]) for x in out),
    "source_conflicts_flagged_but_card_retained":sum(int(x["source_conflict"]) for x in out),
    "wikidata_exact_conflict_rows":sum(int(x["wikidata_exact_conflict"]) for x in out),
    "implausible_election_age_rows":sum(x["dob_status"]=="wikidata_implausible_election_age_review" for x in out),
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
        "qlever_global_exact_name_endpoint":QLEVER,
    },
    "note":"No BaZi variables are computed. NAS card DOB is primary for deceased. Global Wikidata supplement uses exact official NAS names only, not fuzzy matching."
}
(OUT/"summary.json").write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding="utf-8")
print(json.dumps(summary,indent=2,ensure_ascii=False))
