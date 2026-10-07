#!/usr/bin/env python3
from __future__ import annotations

import base64
import csv
import datetime as dt
import io
import json
import re
import time
import unicodedata
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path

OUT = Path("data/nas_wikidata_dob_pilot")
OUT.mkdir(parents=True, exist_ok=True)

QLEVER_ENDPOINT = "https://qlever.dev/api/wikidata"
WIKIDATA_API = "https://www.wikidata.org/w/api.php"
GITHUB_API = "https://api.github.com"

# Fixed Git blobs from acepocalypse/ntl-academies-tracker.
# rich: membership type, deceased flag, election year, primary/secondary section.
# slim: same profile URLs; many deceased cards store "birth date - death date".
RICH_BLOB_SHA = "74f61f07c22c1ed68bb24b97be3085e727b5a873"
SLIM_BLOB_SHA = "7ceadb405b623f7a00d12d5ac99ff7d252e73515"
TRACKER_REPO = "acepocalypse/ntl-academies-tracker"

SCIENCE_CORE = {12,13,14,15,16,21,22,23,24,25,26,27,28,29,41,42,43,44}

USER_AGENT = "bazi-public-figure-study/1.0 (NAS DOB coverage pilot; no BaZi outcomes)"

QLEVER_QUERY = r"""
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?person ?nasid ?label WHERE {
  ?person wdt:P5380 ?nasid .
  OPTIONAL {
    ?person rdfs:label ?label .
    FILTER(LANG(?label) = "en")
  }
}
ORDER BY ?person ?nasid
"""

def http_get(url: str, headers: dict | None = None, timeout: int = 180) -> bytes:
    h = {"User-Agent": USER_AGENT, "Accept": "*/*"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()

def http_post_form(url: str, fields: dict, timeout: int = 300) -> bytes:
    body = urllib.parse.urlencode(fields).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "User-Agent": USER_AGENT,
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "text/tab-separated-values",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()

def clean_tsv_term(s: str) -> str:
    s = (s or "").strip()
    if s.startswith("<") and s.endswith(">"):
        return s[1:-1]
    # QLever often serializes language-tagged labels as "Label"@en.
    if s.startswith('"'):
        m = re.match(r'^"(.*)"(?:@[A-Za-z-]+|\^\^<[^>]+>)?$', s)
        if m:
            return m.group(1).replace(r'\"','"').replace(r"\\","\\")
    return s

def normalize_name(s: str, drop_middle_initials: bool = False) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.casefold()
    s = re.sub(r"\b(jr|sr|ii|iii|iv)\b", " ", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    toks = [t for t in s.split() if t]
    if drop_middle_initials and len(toks) >= 3:
        toks = [t for i,t in enumerate(toks) if not (0 < i < len(toks)-1 and len(t)==1)]
    return " ".join(toks)

def secnum(s: str):
    m = re.search(r"(?:Section\s*)?(\d+)", s or "", re.I)
    return int(m.group(1)) if m else None

def is_regular_membership(s: str) -> bool:
    s = s or ""
    if re.search(r"International|Resigned|Rescinded", s, re.I):
        return False
    return bool(re.search(r"Member|Emeritus", s, re.I))

def parse_csv_text(text: str):
    return list(csv.DictReader(io.StringIO(text)))

def fetch_git_blob(repo: str, sha: str) -> bytes:
    url = f"{GITHUB_API}/repos/{repo}/git/blobs/{sha}"
    obj = json.loads(http_get(url, headers={"Accept":"application/vnd.github+json"}))
    if obj.get("encoding") != "base64":
        raise RuntimeError(f"Unexpected Git blob encoding: {obj.get('encoding')}")
    return base64.b64decode(obj["content"])

def parse_nas_date_range(s: str):
    s = (s or "").strip()
    m = re.match(
        r"^([A-Z][a-z]+ \d{1,2}, \d{4})\s*-\s*([A-Z][a-z]+ \d{1,2}, \d{4})$",
        s
    )
    if not m:
        return None
    try:
        b = dt.datetime.strptime(m.group(1), "%B %d, %Y").date().isoformat()
        d = dt.datetime.strptime(m.group(2), "%B %d, %Y").date().isoformat()
        return b, d
    except ValueError:
        return None

def qlever_p5380_people():
    raw = http_post_form(QLEVER_ENDPOINT, {"query":QLEVER_QUERY, "action":"tsv_export"})
    (OUT/"qlever_p5380_raw.tsv").write_bytes(raw)
    rows = list(csv.reader(raw.decode("utf-8-sig").splitlines(), delimiter="\t"))
    if not rows:
        raise RuntimeError("QLever returned no rows.")
    headers = [x.lstrip("?") for x in rows[0]]
    idx = {h:i for i,h in enumerate(headers)}
    people = defaultdict(lambda: {"nasids":set(), "labels":set()})
    for r in rows[1:]:
        r = r + [""]*(len(headers)-len(r))
        person = clean_tsv_term(r[idx["person"]])
        if not person:
            continue
        qid = person.rsplit("/",1)[-1]
        people[qid]["nasids"].add(clean_tsv_term(r[idx["nasid"]]))
        label = clean_tsv_term(r[idx["label"]])
        if label:
            people[qid]["labels"].add(label)
    return people, max(0,len(rows)-1)

def chunks(seq, n):
    for i in range(0,len(seq),n):
        yield seq[i:i+n]

def wikidata_birth_claims(qids: list[str], people: dict):
    out = {}
    for batch_no, batch in enumerate(chunks(qids, 50), 1):
        params = {
            "action":"wbgetentities",
            "ids":"|".join(batch),
            "props":"claims|labels",
            "languages":"en",
            "format":"json",
            "formatversion":"2",
        }
        url = WIKIDATA_API + "?" + urllib.parse.urlencode(params)
        obj = json.loads(http_get(url, headers={"Accept":"application/json"}, timeout=180))
        entities = obj.get("entities", {})
        for qid in batch:
            e = entities.get(qid, {})
            labels = set(people[qid]["labels"])
            lab = e.get("labels",{}).get("en",{}).get("value")
            if lab:
                labels.add(lab)
            claims = [
                c for c in e.get("claims",{}).get("P569",[])
                if c.get("rank") != "deprecated"
                and c.get("mainsnak",{}).get("snaktype") == "value"
            ]
            # Respect Wikidata rank: if preferred P569 values exist, ignore normal-ranked alternatives.
            preferred = [c for c in claims if c.get("rank") == "preferred"]
            use = preferred if preferred else claims

            vals = []
            for c in use:
                dv = c.get("mainsnak",{}).get("datavalue",{}).get("value")
                if not isinstance(dv,dict):
                    continue
                vals.append({
                    "time":dv.get("time",""),
                    "precision":dv.get("precision"),
                    "rank":c.get("rank",""),
                })
            exact = sorted({
                wikidata_time_to_iso(v["time"])
                for v in vals
                if isinstance(v.get("precision"),int) and v["precision"] >= 11
                and wikidata_time_to_iso(v["time"])
            })
            precisions = sorted({v["precision"] for v in vals if isinstance(v.get("precision"),int)})
            out[qid] = {
                "qid":qid,
                "nasids":sorted(x for x in people[qid]["nasids"] if x),
                "labels":sorted(labels),
                "max_precision":max(precisions) if precisions else None,
                "exact_dates":exact,
                "exact_conflict":len(exact)>1,
                "has_p569":bool(vals),
            }
        if batch_no % 20 == 0:
            print(f"  Wikidata batches completed: {batch_no}")
        time.sleep(0.05)
    return out

def wikidata_time_to_iso(s: str):
    m = re.match(r"^\+?(\d{4})-(\d{2})-(\d{2})T", s or "")
    if not m:
        return None
    y,mn,d = map(int,m.groups())
    try:
        return dt.date(y,mn,d).isoformat()
    except ValueError:
        return None

def unique_index(items, key_fn):
    tmp = defaultdict(list)
    for x in items:
        k = key_fn(x)
        if k:
            tmp[k].append(x)
    return {k:v[0] for k,v in tmp.items() if len(v)==1}, {k:v for k,v in tmp.items() if len(v)>1}

def write_csv(path: Path, rows: list[dict], fields: list[str]):
    with path.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

print("Step 1: QLever P5380 -> Wikidata QIDs")
people, qlever_rows = qlever_p5380_people()
qids = sorted(people)
print(f"  Wikidata persons with P5380: {len(qids)}")

print("Step 2: Wikidata entity API -> P569 claims with precision")
wd = wikidata_birth_claims(qids, people)

wd_rows=[]
for qid in qids:
    d=wd[qid]
    wd_rows.append({
        "qid":qid,
        "nas_member_ids":"|".join(d["nasids"]),
        "english_labels":"|".join(d["labels"]),
        "has_non_deprecated_p569":int(d["has_p569"]),
        "max_birthdate_precision":d["max_precision"] if d["max_precision"] is not None else "",
        "exact_day_values":"|".join(d["exact_dates"]),
        "exact_day_value_count":len(d["exact_dates"]),
        "exact_day_conflict":int(d["exact_conflict"]),
    })
write_csv(
    OUT/"wikidata_nas_member_dob.csv",
    wd_rows,
    ["qid","nas_member_ids","english_labels","has_non_deprecated_p569",
     "max_birthdate_precision","exact_day_values","exact_day_value_count","exact_day_conflict"]
)

print("Step 3: Fetch fixed NAS tracker blobs")
rich_raw=fetch_git_blob(TRACKER_REPO,RICH_BLOB_SHA)
slim_raw=fetch_git_blob(TRACKER_REPO,SLIM_BLOB_SHA)
rich=parse_csv_text(rich_raw.decode("utf-8-sig"))
slim=parse_csv_text(slim_raw.decode("utf-8-sig"))
print(f"  rich rows={len(rich)}, slim rows={len(slim)}")

slim_by_url={r["profile_url"]:r for r in slim}
regular=[r for r in rich if is_regular_membership(r.get("membership_type",""))]
science=[r for r in regular if secnum(r.get("primary_section","")) in SCIENCE_CORE]

# Build conservative unique name indices for Wikidata.
wd_people=[]
for qid,d in wd.items():
    for label in d["labels"]:
        wd_people.append({"qid":qid,"label":label,"data":d})

wd_strict, wd_strict_amb = unique_index(
    wd_people, lambda x: normalize_name(x["label"],False)
)
wd_loose, wd_loose_amb = unique_index(
    wd_people, lambda x: normalize_name(x["label"],True)
)
rich_strict_counts=defaultdict(int)
rich_loose_counts=defaultdict(int)
for r in rich:
    rich_strict_counts[normalize_name(r.get("name",""),False)] += 1
    rich_loose_counts[normalize_name(r.get("name",""),True)] += 1

result=[]
for r in science:
    profile=r["profile_url"]
    name=r.get("name","")
    slim_r=slim_by_url.get(profile)
    nas_birth=""
    nas_death=""
    if slim_r:
        bd=parse_nas_date_range(slim_r.get("affiliation",""))
        if bd:
            nas_birth,nas_death=bd

    match=None
    rule=""
    sk=normalize_name(name,False)
    lk=normalize_name(name,True)
    if rich_strict_counts.get(sk)==1 and sk in wd_strict:
        match=wd_strict[sk]
        rule="unique_strict_name"
    elif rich_loose_counts.get(lk)==1 and lk in wd_loose:
        match=wd_loose[lk]
        rule="unique_name_drop_middle_initials"

    wd_qid=""
    wd_births=[]
    wd_conflict=0
    if match:
        wd_qid=match["qid"]
        wd_births=match["data"]["exact_dates"]
        wd_conflict=int(match["data"]["exact_conflict"])

    source_conflict=0
    resolved=""
    source=""
    if nas_birth and len(wd_births)==1:
        if nas_birth==wd_births[0]:
            resolved=nas_birth
            source="NAS_snapshot+Wikidata_agree"
        else:
            source_conflict=1
            source="NAS_snapshot_vs_Wikidata_conflict"
    elif nas_birth:
        resolved=nas_birth
        source="NAS_snapshot"
    elif len(wd_births)==1:
        resolved=wd_births[0]
        source="Wikidata"
    elif len(wd_births)>1:
        source="Wikidata_internal_conflict"

    result.append({
        "profile_url":profile,
        "name":name,
        "membership_type":r.get("membership_type",""),
        "deceased":r.get("deceased",""),
        "election_year":r.get("year",""),
        "primary_section":r.get("primary_section",""),
        "secondary_section":r.get("secondary_section",""),
        "nas_snapshot_exact_birth":nas_birth,
        "nas_snapshot_death":nas_death,
        "wikidata_qid":wd_qid,
        "wikidata_match_rule":rule,
        "wikidata_exact_birth_values":"|".join(wd_births),
        "wikidata_internal_conflict":wd_conflict,
        "nas_vs_wikidata_conflict":source_conflict,
        "resolved_exact_birth_pilot":resolved,
        "resolved_source_pilot":source,
    })

fields=list(result[0].keys())
write_csv(OUT/"nas_science_core_dob_pilot.csv",result,fields)

def stats(arr):
    n=len(arr)
    deceased=[x for x in arr if x["deceased"]=="Y"]
    living=[x for x in arr if x["deceased"]!="Y"]
    def c(xs,k): return sum(bool(x[k]) for x in xs)
    return {
        "n":n,
        "nas_snapshot_exact":c(arr,"nas_snapshot_exact_birth"),
        "wikidata_unique_name_match":c(arr,"wikidata_qid"),
        "wikidata_exact_single_value":sum(
            1 for x in arr
            if x["wikidata_exact_birth_values"] and "|" not in x["wikidata_exact_birth_values"]
        ),
        "source_conflicts":sum(int(x["nas_vs_wikidata_conflict"]) for x in arr),
        "resolved_exact_pilot":c(arr,"resolved_exact_birth_pilot"),
        "resolved_exact_rate":round(c(arr,"resolved_exact_birth_pilot")/n,6) if n else None,
        "deceased_n":len(deceased),
        "deceased_resolved_exact":c(deceased,"resolved_exact_birth_pilot"),
        "deceased_resolved_rate":round(c(deceased,"resolved_exact_birth_pilot")/len(deceased),6) if deceased else None,
        "living_n":len(living),
        "living_resolved_exact":c(living,"resolved_exact_birth_pilot"),
        "living_resolved_rate":round(c(living,"resolved_exact_birth_pilot")/len(living),6) if living else None,
    }

summary={
    "study":"Professor -> Academy -> Nobel/Fields academic-selection study",
    "stage":"NAS science-core exact DOB availability pilot",
    "created_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
    "tracker_rich_blob_sha":RICH_BLOB_SHA,
    "tracker_slim_blob_sha":SLIM_BLOB_SHA,
    "tracker_rich_rows":len(rich),
    "tracker_slim_rows":len(slim),
    "regular_membership_rows":len(regular),
    "science_core_rows":len(science),
    "wikidata_persons_with_P5380":len(qids),
    "wikidata_persons_with_non_deprecated_P569":sum(int(d["has_p569"]) for d in wd.values()),
    "wikidata_persons_with_exact_day":sum(int(len(d["exact_dates"])>0) for d in wd.values()),
    "wikidata_persons_with_exact_day_conflict":sum(int(d["exact_conflict"]) for d in wd.values()),
    "qlever_raw_rows":qlever_rows,
    "science_core_coverage":stats(result),
    "method_note":"Wikidata is linked to NAS rows only by conservative unique normalized-name matching in this pilot. Conflicts are not resolved automatically.",
    "blinding_note":"No BaZi variables or hypothesis outcomes are computed.",
}
(OUT/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(summary,ensure_ascii=False,indent=2))
