#!/usr/bin/env python3
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROSTER = Path("data/leopoldina_roster_freeze_v1/leopoldina_science_core_roster_freeze_v1.csv")
FREEZE = Path("data/leopoldina_roster_freeze_v1.json")
OUT = Path("data/leopoldina_p10299_authority_validation_v1")
QLEVER = "https://qlever.dev/api/wikidata"
UA = "bazi-public-figure-study/1.0 (Leopoldina P10299 authority validation; no BaZi computation)"
SAMPLE_PER_STATUS = 200
MAX_WORKERS = 8

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
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

def qlever_tsv(query, retries=6):
    body = urllib.parse.urlencode({"query": query, "action": "tsv_export"}).encode()
    last = None
    for attempt in range(retries):
        req = urllib.request.Request(QLEVER, data=body, method="POST", headers={
            "User-Agent": UA,
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "text/tab-separated-values",
        })
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                raw = r.read().decode("utf-8-sig")
            break
        except (urllib.error.HTTPError, urllib.error.URLError) as e:
            last = e
            code = getattr(e, "code", None)
            if attempt + 1 >= retries or (code is not None and code not in {429,500,502,503,504}):
                raise
            time.sleep(min(30, 2 ** attempt))
    else:
        raise RuntimeError(f"QLever failed: {last}")
    rr = list(csv.reader(raw.splitlines(), delimiter="\t"))
    if not rr:
        return []
    headers = [x.lstrip("?").strip() for x in rr[0]]
    out = []
    for row in rr[1:]:
        row += [""] * (len(headers) - len(row))
        item = {}
        for i,h in enumerate(headers):
            v=(row[i] or "").strip()
            if v.startswith("<") and v.endswith(">"):
                v=v[1:-1]
            elif v.startswith('"'):
                m=re.match(r'^"(.*)"(?:\^\^<[^>]+>|@[A-Za-z-]+)?$',v)
                if m:v=m.group(1)
            item[h]=v
        out.append(item)
    return out

def parse_qid(v):
    return (v or "").rsplit("/",1)[-1]

def parse_date(v):
    m=re.search(r"([12]\d{3})-(\d{2})-(\d{2})",v or "")
    if not m:return ""
    try:return dt.date(int(m.group(1)),int(m.group(2)),int(m.group(3))).isoformat()
    except ValueError:return ""

def as_int(v):
    try:return int(float(str(v)))
    except Exception:return None

def http_json(url, retries=5):
    last=None
    for attempt in range(retries):
        try:
            req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"application/json"})
            with urllib.request.urlopen(req,timeout=90) as r:
                obj=json.loads(r.read().decode("utf-8"))
                status=getattr(r,"status",200)
            return {"ok":1,"status":status,"obj":obj,"error":""}
        except urllib.error.HTTPError as e:
            last=e
            if e.code==404:
                return {"ok":0,"status":404,"obj":None,"error":"HTTP 404"}
            if attempt+1>=retries or e.code not in {429,500,502,503,504}:break
            time.sleep(min(20,2**attempt))
        except Exception as e:
            last=e
            if attempt+1>=retries:break
            time.sleep(min(20,2**attempt))
    return {"ok":0,"status":getattr(last,"code",""),"obj":None,"error":repr(last)}

def valid_exact_date(s):
    s=str(s or "").strip()
    m=re.fullmatch(r"([12]\d{3})-(\d{2})-(\d{2})",s)
    if not m:
        m=re.fullmatch(r"([12]\d{3})(\d{2})(\d{2})",s)
    if not m:return ""
    try:return dt.date(int(m.group(1)),int(m.group(2)),int(m.group(3))).isoformat()
    except ValueError:return ""

def parse_gnd_birth_dates(obj):
    vals=set()
    if not isinstance(obj,dict):return []
    raw=obj.get("dateOfBirth",[])
    if not isinstance(raw,list):raw=[raw]
    for x in raw:
        if isinstance(x,dict):
            for k in ("@value","value","label"):
                d=valid_exact_date(x.get(k,""))
                if d:vals.add(d)
        else:
            d=valid_exact_date(x)
            if d:vals.add(d)
    return sorted(vals)

def walk_birth_values(obj):
    vals=[]
    if isinstance(obj,dict):
        for k,v in obj.items():
            lk=str(k).lower()
            if "birthdate" in lk or lk.endswith("#birthdate"):
                vals.append(v)
            vals.extend(walk_birth_values(v))
    elif isinstance(obj,list):
        for x in obj:vals.extend(walk_birth_values(x))
    return vals

def scalar_strings(obj):
    out=[]
    if isinstance(obj,str):out.append(obj)
    elif isinstance(obj,dict):
        for k in ("@value","value"):
            if isinstance(obj.get(k),str):out.append(obj[k])
        for v in obj.values():
            if isinstance(v,(dict,list)):out.extend(scalar_strings(v))
    elif isinstance(obj,list):
        for x in obj:out.extend(scalar_strings(x))
    return out

def parse_loc_birth_dates(obj):
    vals=set()
    for raw in walk_birth_values(obj):
        for s in scalar_strings(raw):
            d=valid_exact_date(s)
            if d:vals.add(d)
    return sorted(vals)

def fetch_gnd(gid):
    url=f"https://lobid.org/gnd/{urllib.parse.quote(gid)}.json"
    r=http_json(url)
    return {"id":gid,"ok":r["ok"],"status":r["status"],"dates":parse_gnd_birth_dates(r["obj"]) if r["ok"] else [],"error":r["error"]}

def fetch_loc(lid):
    url=f"https://id.loc.gov/authorities/names/{urllib.parse.quote(lid)}.json"
    r=http_json(url)
    return {"id":lid,"ok":r["ok"],"status":r["status"],"dates":parse_loc_birth_dates(r["obj"]) if r["ok"] else [],"error":r["error"]}

def fetch_many(ids, fn):
    out={}
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futs={ex.submit(fn,x):x for x in sorted(set(ids))}
        for fut in as_completed(futs):
            x=futs[fut]
            try:out[x]=fut.result()
            except Exception as e:out[x]={"id":x,"ok":0,"status":"","dates":[],"error":repr(e)}
    return out

def deterministic_sample(rows, n):
    return sorted(rows,key=lambda r:hashlib.sha256(r["member_slug"].encode()).hexdigest())[:n]

def main():
    freeze=json.loads(FREEZE.read_text(encoding="utf-8"))
    roster=read_csv(ROSTER)
    if len(roster)!=2888:raise RuntimeError("Roster count mismatch")
    if freeze.get("checksums",{}).get("roster_csv_sha256")!=sha256(ROSTER):raise RuntimeError("Roster hash mismatch")
    roster_by_slug={r["member_slug"]:r for r in roster}

    query="""
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX p: <http://www.wikidata.org/prop/>
PREFIX psv: <http://www.wikidata.org/prop/statement/value/>
PREFIX wikibase: <http://wikiba.se/ontology#>
SELECT ?person ?memberId ?dob ?precision ?gnd ?loc WHERE {
  ?person wdt:P10299 ?memberId .
  OPTIONAL {
    ?person p:P569 ?dobStatement .
    ?dobStatement psv:P569 ?dobNode .
    ?dobNode wikibase:timeValue ?dob ;
             wikibase:timePrecision ?precision .
  }
  OPTIONAL { ?person wdt:P227 ?gnd . }
  OPTIONAL { ?person wdt:P244 ?loc . }
}
"""
    raw=qlever_tsv(query)
    by_slug={}
    for x in raw:
        slug=(x.get("memberId") or "").strip()
        if slug not in roster_by_slug:continue
        rec=by_slug.setdefault(slug,{"qids":set(),"dates":set(),"gnd":set(),"loc":set()})
        q=parse_qid(x.get("person",""))
        if q:rec["qids"].add(q)
        p=as_int(x.get("precision")); d=parse_date(x.get("dob",""))
        if d and p is not None:rec["dates"].add((d,p))
        if (x.get("gnd") or "").strip():rec["gnd"].add((x.get("gnd") or "").strip())
        if (x.get("loc") or "").strip():rec["loc"].add((x.get("loc") or "").strip())

    eligible=[]
    for slug,r in roster_by_slug.items():
        w=by_slug.get(slug)
        if not w or len(w["qids"])!=1:continue
        d=sorted({x for x,p in w["dates"] if p>=11})
        if len(d)!=1:continue
        if not w["gnd"] and not w["loc"]:continue
        eligible.append({
            "member_slug":slug,
            "display_name":r["display_name"],
            "deceased_marker":r["deceased_marker"],
            "election_year":r["election_year"],
            "qid":next(iter(w["qids"])),
            "wikidata_dob":d[0],
            "gnd_ids":"|".join(sorted(w["gnd"])),
            "loc_ids":"|".join(sorted(w["loc"])),
        })
    deceased=[r for r in eligible if r["deceased_marker"]=="1"]
    nondeceased=[r for r in eligible if r["deceased_marker"]!="1"]
    sample=deterministic_sample(deceased,min(SAMPLE_PER_STATUS,len(deceased)))+deterministic_sample(nondeceased,min(SAMPLE_PER_STATUS,len(nondeceased)))

    gnd_ids=set();loc_ids=set()
    for r in sample:
        gnd_ids.update(x for x in r["gnd_ids"].split("|") if x)
        loc_ids.update(x for x in r["loc_ids"].split("|") if x)
    gnd_fetch=fetch_many(gnd_ids,fetch_gnd)
    loc_fetch=fetch_many(loc_ids,fetch_loc)

    out=[]
    for r in sample:
        gd=sorted({d for gid in r["gnd_ids"].split("|") if gid for d in gnd_fetch.get(gid,{}).get("dates",[])})
        ld=sorted({d for lid in r["loc_ids"].split("|") if lid for d in loc_fetch.get(lid,{}).get("dates",[])})
        gu=gd[0] if len(gd)==1 else ""
        lu=ld[0] if len(ld)==1 else ""
        gcmp="match" if gu and gu==r["wikidata_dob"] else ("conflict" if gu else "")
        lcmp="match" if lu and lu==r["wikidata_dob"] else ("conflict" if lu else "")
        cross_conflict=int(bool(gu and lu and gu!=lu))
        authority=""
        if not cross_conflict:
            authority=gu or lu
        comparison="match" if authority and authority==r["wikidata_dob"] else ("conflict" if authority else "")
        out.append({
            **r,
            "gnd_exact_birth_dates":"|".join(gd),
            "loc_exact_birth_dates":"|".join(ld),
            "gnd_comparison":gcmp,
            "loc_comparison":lcmp,
            "gnd_loc_conflict":cross_conflict,
            "authority_candidate_dob":authority,
            "authority_vs_wikidata":comparison,
            "accepted_exact_dob":"",
            "bazi_variables_computed":0,
        })

    fields=list(out[0].keys())
    OUT.mkdir(parents=True,exist_ok=True)
    write_csv(OUT/"validation_rows.csv",out,fields)
    conflicts=[r for r in out if r["gnd_comparison"]=="conflict" or r["loc_comparison"]=="conflict" or r["gnd_loc_conflict"]==1]
    write_csv(OUT/"conflicts_for_review.csv",conflicts,fields)

    comparable=[r for r in out if r["authority_vs_wikidata"] in {"match","conflict"}]
    gcomp=[r for r in out if r["gnd_comparison"] in {"match","conflict"}]
    lcomp=[r for r in out if r["loc_comparison"] in {"match","conflict"}]
    summary={
      "dataset":"Leopoldina P10299 Wikidata P569 authority validation v1",
      "frozen_roster_rows":len(roster),
      "eligible_unique_day_p569_with_authority_id":len(eligible),
      "validation_sample_n":len(out),
      "sample_by_status":{"deceased_marker":sum(r["deceased_marker"]=="1" for r in out),"no_deceased_marker":sum(r["deceased_marker"]!="1" for r in out)},
      "gnd_ids_fetched":len(gnd_ids),
      "gnd_fetch_successes":sum(int(v.get("ok",0)) for v in gnd_fetch.values()),
      "loc_ids_fetched":len(loc_ids),
      "loc_fetch_successes":sum(int(v.get("ok",0)) for v in loc_fetch.values()),
      "gnd_comparable":len(gcomp),
      "gnd_matches":sum(r["gnd_comparison"]=="match" for r in gcomp),
      "gnd_conflicts":sum(r["gnd_comparison"]=="conflict" for r in gcomp),
      "gnd_match_rate":round(sum(r["gnd_comparison"]=="match" for r in gcomp)/len(gcomp),6) if gcomp else None,
      "loc_comparable":len(lcomp),
      "loc_matches":sum(r["loc_comparison"]=="match" for r in lcomp),
      "loc_conflicts":sum(r["loc_comparison"]=="conflict" for r in lcomp),
      "loc_match_rate":round(sum(r["loc_comparison"]=="match" for r in lcomp)/len(lcomp),6) if lcomp else None,
      "authority_comparable":len(comparable),
      "authority_matches":sum(r["authority_vs_wikidata"]=="match" for r in comparable),
      "authority_conflicts":sum(r["authority_vs_wikidata"]=="conflict" for r in comparable),
      "authority_match_rate":round(sum(r["authority_vs_wikidata"]=="match" for r in comparable)/len(comparable),6) if comparable else None,
      "gnd_loc_conflicts":sum(int(r["gnd_loc_conflict"]) for r in out),
      "rows_flagged_for_review":len(conflicts),
      "dob_values_accepted":0,
      "bazi_variables_computed":0,
      "validation_rule":"Deterministic 200 deceased-marker + 200 no-deceased-marker sample from unique day-precision P569 rows with P10299 identity and at least one P227/P244 authority ID. Direct GND/LOC records are compared to P569; no DOB is written.",
    }
    (OUT/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
