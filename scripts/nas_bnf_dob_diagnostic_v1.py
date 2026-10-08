#!/usr/bin/env python3
from __future__ import annotations
import csv, hashlib, json, re, time, urllib.parse, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

BASE=Path("data/nas_science_core_dob_crosswalk")
INPUT=BASE/"nas_science_core_dob_crosswalk_v14.csv"
OUT=BASE/"nas_bnf_dob_diagnostic_v1.csv"
VAL=BASE/"nas_bnf_dob_validation_conflicts_v1.csv"
CAND=BASE/"nas_bnf_dob_candidates_v1.csv"
SUMMARY=BASE/"summary_bnf_dob_diagnostic_v1.json"
UA="bazi-public-figure-study/1.0 (BnF DOB diagnostic; no BaZi computation)"

GENERIC={"university","college","school","institute","institution","center","centre","department","laboratory","lab","national","medical","medicine","science","sciences","research","the","of","for","and","inc","corporation","company","hospital","foundation","academy","state","system","health","technology","technologies"}

def read_csv(p):
    with p.open("r",encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
def write_csv(p,rows,fields=None):
    if fields is None:fields=list(rows[0].keys()) if rows else []
    with p.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore");w.writeheader();w.writerows(rows)
def present(v):return str(v or "").strip() not in ("","nan","None")
def norm_name(s):
    s=re.sub(r"[^a-z0-9]+"," ",str(s or "").lower())
    return " ".join(s.split())
def as_int(v,d=0):
    try:return int(float(str(v)))
    except:return d
def reliable_qid(r):
    q=(r.get("wikidata_qid") or "").strip()
    if re.fullmatch(r"Q\d+",q):return q,"primary_match"
    q=(r.get("global_candidate_qid") or "").strip()
    if not re.fullmatch(r"Q\d+",q):return "",""
    if as_int(r.get("global_exact_name_match_count"))!=1:return "",""
    token_count=len(norm_name(r.get("name","")).split())
    aff=as_int(r.get("global_affiliation_match"))==1
    if token_count>=3 or aff:return q,"global_unique_identity"
    return "",""
def exact_date(s):
    m=re.search(r"([12]\d{3})-(\d{2})-(\d{2})",str(s or ""))
    if not m:return ""
    y,mo,d=m.groups()
    try:
        import datetime as dt
        return dt.date(int(y),int(mo),int(d)).isoformat()
    except:return ""
def get(url,accept="application/json",retries=5):
    last=None
    for i in range(retries):
        try:
            req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":accept})
            with urllib.request.urlopen(req,timeout=90) as r:return getattr(r,"status",200),r.read(),""
        except urllib.error.HTTPError as e:
            last=e
            if e.code==404:return 404,b"","HTTP 404"
            if i+1>=retries or e.code not in {429,500,502,503,504}:break
            try:delay=float(e.headers.get("Retry-After",""))
            except Exception:delay=min(20,2**i)
            time.sleep(max(2,delay))
        except Exception as e:
            last=e
            if i+1>=retries:break
            time.sleep(min(20,2**i))
    return getattr(last,"code",""),b"",repr(last)
def dv(snak):
    try:return snak["datavalue"]["value"]
    except:return None
def fetch_entity(qid):
    url=f"https://www.wikidata.org/wiki/Special:EntityData/{qid}.json"
    st,data,err=get(url,"application/json")
    if not data:return qid,{"ok":0,"p268":[],"error":err,"url":url}
    try:
        obj=json.loads(data.decode("utf-8"))
        ent=(obj.get("entities") or {}).get(qid) or {}
        claims=ent.get("claims") or {}
        vals=[]
        for c in claims.get("P268",[]):
            v=dv(c.get("mainsnak") or {})
            if isinstance(v,str) and v.strip():vals.append(v.strip())
        return qid,{"ok":1,"p268":sorted(set(vals)),"error":"","url":url}
    except Exception as e:return qid,{"ok":0,"p268":[],"error":repr(e),"url":url}
def parse_bnf_dates(text):
    vals=set()
    pats=[
      r'"birthDate"\s*:\s*"([^"]+)"',
      r'"dateOfBirth"\s*:\s*"([^"]+)"',
      r'itemprop=["\']birthdate["\'][^>]{0,300}?(?:content|datetime|value)=["\']([^"\']+)["\']',
      r'(?:birthDate|dateOfBirth)[^0-9]{0,120}([12]\d{3}-\d{2}-\d{2})',
      r'([12]\d{3}-\d{2}-\d{2})[^\n<]{0,100}(?:birthDate|dateOfBirth)',
    ]
    for p in pats:
        for x in re.findall(p,text,re.I|re.S):
            d=exact_date(x)
            if d:vals.add(d)
    return sorted(vals)
def fetch_bnf(p268):
    pid=p268.strip()
    if pid.lower().startswith("cb"):pid=pid[2:]
    urls=[
      f"https://data.bnf.fr/ark:/12148/cb{urllib.parse.quote(pid)}",
      f"https://data.bnf.fr/en/ark:/12148/cb{urllib.parse.quote(pid)}",
    ]
    errors=[]
    for url in urls:
        st,data,err=get(url,"text/html,application/xhtml+xml;q=0.9,*/*;q=0.8")
        if err:errors.append(f"{url}: {err}")
        if data:
            try:text=data.decode("utf-8","ignore")
            except:text=str(data)
            dates=parse_bnf_dates(text)
            if dates:return p268,{"ok":1,"dates":dates,"url":url,"error":" || ".join(errors)}
    return p268,{"ok":0,"dates":[],"url":urls[0],"error":" || ".join(errors)}

rows=read_csv(INPUT)
if len(rows)!=3051:raise RuntimeError(f"Expected 3051 rows, got {len(rows)}")
unresolved=[r for r in rows if not present(r.get("final_exact_dob"))]

# unresolved targets with conservative/reliable identity
targets=[]
for r in unresolved:
    q,b=reliable_qid(r)
    if q:targets.append((r,q,b))

# deterministic validation sample from already-known exact rows with reliable QID
known=[]
for r in rows:
    if not present(r.get("final_exact_dob")):continue
    q,b=reliable_qid(r)
    if q:known.append((r,q,b))
known=sorted(known,key=lambda x:hashlib.sha256(x[0]["profile_url"].encode()).hexdigest())[:250]

all_qids=sorted({q for _,q,_ in targets+known})
entities={}
with ThreadPoolExecutor(max_workers=10) as ex:
    fs={ex.submit(fetch_entity,q):q for q in all_qids}
    for f in as_completed(fs):
        q=fs[f]
        try:qq,res=f.result();entities[qq]=res
        except Exception as e:entities[q]={"ok":0,"p268":[],"error":repr(e),"url":""}

all_p268=sorted({p for q in all_qids for p in entities.get(q,{}).get("p268",[])})
bnf={}
with ThreadPoolExecutor(max_workers=6) as ex:
    fs={ex.submit(fetch_bnf,p):p for p in all_p268}
    for f in as_completed(fs):
        p=fs[f]
        try:pp,res=f.result();bnf[pp]=res
        except Exception as e:bnf[p]={"ok":0,"dates":[],"url":"","error":repr(e)}

def combined_dates(q):
    vals=set()
    for p in entities.get(q,{}).get("p268",[]):
        vals.update(bnf.get(p,{}).get("dates",[]))
    return sorted(vals)

valrows=[]; comparable=matches=conflicts=0
for r,q,b in known:
    dates=combined_dates(q)
    master=r.get("final_exact_dob","")
    if len(dates)==1:
        comparable+=1
        if dates[0]==master:matches+=1
        else:
            conflicts+=1
            valrows.append({
              "profile_url":r["profile_url"],"name":r["name"],"qid":q,
              "master_exact_dob":master,"bnf_exact_dob":dates[0],
              "p268_ids":"|".join(entities.get(q,{}).get("p268",[])),
              "bnf_urls":"|".join(bnf[p].get("url","") for p in entities.get(q,{}).get("p268",[]) if p in bnf)
            })

out=[];cands=[]
for r,q,b in targets:
    ps=entities.get(q,{}).get("p268",[])
    dates=combined_dates(q)
    conflict=int(len(dates)>1)
    cand=dates[0] if len(dates)==1 else ""
    try:age=int(r.get("election_year") or 0)-int(cand[:4]) if cand else None
    except:age=None
    ageok=int(age is not None and 25<=age<=100) if cand else ""
    row={
      "profile_url":r["profile_url"],"name":r["name"],"election_year":r.get("election_year",""),
      "affiliation":r.get("affiliation",""),"qid":q,"identity_basis":b,
      "p268_ids":"|".join(ps),"bnf_exact_dates":"|".join(dates),
      "bnf_exact_conflict":conflict,"bnf_candidate_dob":cand,
      "age_at_election":age if age is not None else "","age_plausible":ageok,
      "candidate_for_manual_review":int(bool(cand) and not conflict and ageok==1),
      "bnf_urls":"|".join(bnf[p].get("url","") for p in ps if p in bnf),
      "fetch_errors":" || ".join([entities.get(q,{}).get("error","")]+[bnf[p].get("error","") for p in ps if p in bnf]).strip(" |")
    }
    out.append(row)
    if int(row["candidate_for_manual_review"])==1:cands.append(row)

write_csv(OUT,out)
write_csv(VAL,valrows,["profile_url","name","qid","master_exact_dob","bnf_exact_dob","p268_ids","bnf_urls"])
write_csv(CAND,cands,list(out[0].keys()) if out else [])
summary={
 "dataset":"NAS BnF exact-DOB diagnostic v1",
 "input_v14_rows":len(rows),
 "unresolved_rows":len(unresolved),
 "unresolved_reliable_qid_targets":len(targets),
 "validation_sample_rows":len(known),
 "wikidata_entity_fetch_successes":sum(int(entities[q]["ok"]) for q in all_qids if q in entities),
 "unique_p268_ids":len(all_p268),
 "validation_rows_with_p268":sum(bool(entities.get(q,{}).get("p268")) for _,q,_ in known),
 "validation_comparable_exact_rows":comparable,
 "validation_exact_matches":matches,
 "validation_exact_conflicts":conflicts,
 "validation_match_rate":round(matches/comparable,6) if comparable else None,
 "unresolved_rows_with_p268":sum(bool(entities.get(q,{}).get("p268")) for _,q,_ in targets),
 "unresolved_rows_with_unique_bnf_exact_candidate":sum(bool(x["bnf_candidate_dob"]) and not int(x["bnf_exact_conflict"]) for x in out),
 "candidates_for_manual_review":len(cands),
 "bazi_variables_computed":0,
 "decision_note":"Diagnostic only. BnF dates are not auto-accepted. Validation on frozen known exact DOBs is reported first; unresolved candidates require identity/provenance review before any supplement."
}
SUMMARY.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(summary,ensure_ascii=False,indent=2))
