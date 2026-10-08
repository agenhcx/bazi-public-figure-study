#!/usr/bin/env python3
from __future__ import annotations
import csv, hashlib, html, json, re, time, urllib.parse, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

BASE=Path("data/nas_science_core_dob_crosswalk")
INPUT=BASE/"nas_science_core_dob_crosswalk_v14.csv"
OUT=BASE/"nas_p569_reference_url_dob_v1.csv"
VAL=BASE/"nas_p569_reference_url_validation_conflicts_v1.csv"
CAND=BASE/"nas_p569_reference_url_candidates_v1.csv"
SUMMARY=BASE/"summary_p569_reference_url_dob_v1.json"
UA="bazi-public-figure-study/1.0 (P569 reference URL DOB diagnostic; no BaZi computation)"

def read_csv(p):
    with p.open("r",encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
def write_csv(p,rows,fields=None):
    fields=fields or (list(rows[0].keys()) if rows else [])
    with p.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore");w.writeheader();w.writerows(rows)
def present(v):return str(v or "").strip() not in ("","nan","None")
def as_int(v,d=0):
    try:return int(float(str(v)))
    except:return d
def norm_name(s):return " ".join(re.sub(r"[^a-z0-9]+"," ",str(s or "").lower()).split())
def reliable_qid(r):
    q=(r.get("wikidata_qid") or "").strip()
    if re.fullmatch(r"Q\d+",q):return q,"wikidata_qid"
    q=(r.get("global_candidate_qid") or "").strip()
    if not re.fullmatch(r"Q\d+",q):return "",""
    if as_int(r.get("global_exact_name_match_count"))!=1:return "",""
    toks=len(norm_name(r.get("name","")).split())
    if toks>=3 or as_int(r.get("global_affiliation_match"))==1:return q,"global_unique_identity"
    return "",""
def get(url,accept="text/html,application/json;q=0.9,*/*;q=0.1",retries=4):
    last=None
    for i in range(retries):
        try:
            req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":accept})
            with urllib.request.urlopen(req,timeout=75) as r:return getattr(r,"status",200),r.read(),r.headers.get_content_type(),""
        except urllib.error.HTTPError as e:
            last=e
            if e.code in {401,403,404}:return e.code,b"","","HTTP "+str(e.code)
            if i+1>=retries or e.code not in {429,500,502,503,504}:break
            try:delay=float(e.headers.get("Retry-After",""))
            except Exception:delay=min(12,2**i)
            time.sleep(max(2,delay))
        except Exception as e:
            last=e
            if i+1>=retries:break
            time.sleep(min(12,2**i))
    return getattr(last,"code",""),b"","",repr(last)
def dv(snak):
    try:return snak["datavalue"]["value"]
    except:return None
def exact_from_time(v):
    if not isinstance(v,dict):return "",""
    t=str(v.get("time",""));precision=v.get("precision")
    m=re.search(r"([12]\d{3})-(\d{2})-(\d{2})",t)
    if not m:return "",""
    return "-".join(m.groups()),precision
def entity(qid):
    url=f"https://www.wikidata.org/wiki/Special:EntityData/{qid}.json"
    st,data,ct,err=get(url,"application/json")
    if not data:return qid,{"ok":0,"claims":[],"error":err}
    try:
        obj=json.loads(data.decode("utf-8"))
        ent=(obj.get("entities") or {}).get(qid) or {}
        claims=[]
        for c in (ent.get("claims") or {}).get("P569",[]):
            d,p=exact_from_time(dv(c.get("mainsnak") or {}))
            refs=[]
            for ref in c.get("references") or []:
                sn=ref.get("snaks") or {}
                urls=[]
                stated=[]
                for s in sn.get("P854",[]):
                    v=dv(s)
                    if isinstance(v,str) and v.startswith(("http://","https://")):urls.append(v)
                for s in sn.get("P248",[]):
                    v=dv(s)
                    if isinstance(v,dict) and v.get("id"):stated.append(v["id"])
                refs.append({"urls":sorted(set(urls)),"statedIn":sorted(set(stated))})
            claims.append({"date":d,"precision":p,"references":refs})
        return qid,{"ok":1,"claims":claims,"error":""}
    except Exception as e:return qid,{"ok":0,"claims":[],"error":repr(e)}

MONTHS={m.lower():i for i,m in enumerate(["","January","February","March","April","May","June","July","August","September","October","November","December"])}
for k,v in list(MONTHS.items()):
    if len(k)>=3:MONTHS[k[:3]]=v

def iso(y,m,d):
    try:
        import datetime as dt
        return dt.date(int(y),int(m),int(d)).isoformat()
    except:return ""
def parse_date_token(s,expected_year=None):
    s=html.unescape(str(s or "")).strip()
    m=re.search(r"\b([12]\d{3})[-/.](\d{1,2})[-/.](\d{1,2})\b",s)
    if m:
        d=iso(*m.groups())
        if d and (not expected_year or d.startswith(str(expected_year)+"-")):return d
    m=re.search(r"\b(\d{1,2})[-/.](\d{1,2})[-/.]([12]\d{3})\b",s)
    if m:
        mo,dd,y=m.groups();d=iso(y,mo,dd)
        if d and (not expected_year or d.startswith(str(expected_year)+"-")):return d
    m=re.search(r"\b([A-Za-z]{3,9})\s+(\d{1,2})(?:st|nd|rd|th)?[,]?\s+([12]\d{3})\b",s,re.I)
    if m and m.group(1).lower()[:3] in MONTHS:
        d=iso(m.group(3),MONTHS[m.group(1).lower()[:3]],m.group(2))
        if d and (not expected_year or d.startswith(str(expected_year)+"-")):return d
    m=re.search(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]{3,9})[,]?\s+([12]\d{3})\b",s,re.I)
    if m and m.group(2).lower()[:3] in MONTHS:
        d=iso(m.group(3),MONTHS[m.group(2).lower()[:3]],m.group(1))
        if d and (not expected_year or d.startswith(str(expected_year)+"-")):return d
    return ""

def recursive_birth_values(obj):
    vals=[]
    if isinstance(obj,dict):
        for k,v in obj.items():
            kl=str(k).lower()
            if any(x in kl for x in ("birthdate","dateofbirth","birth_date","date_of_birth")):
                vals.append(v)
            vals.extend(recursive_birth_values(v))
    elif isinstance(obj,list):
        for x in obj:vals.extend(recursive_birth_values(x))
    return vals

def page_candidates(data,ctype,expected_year):
    vals=set();evidence=[]
    text=data.decode("utf-8","ignore")
    # Structured JSON / JSON-LD first.
    if "json" in str(ctype).lower() or text.lstrip().startswith(("{","[")):
        try:
            obj=json.loads(text)
            for v in recursive_birth_values(obj):
                stack=v if isinstance(v,list) else [v]
                for x in stack:
                    if isinstance(x,dict):
                        for kk in ("@value","value","label"):
                            d=parse_date_token(x.get(kk),expected_year)
                            if d:vals.add(d);evidence.append(f"structured:{kk}={x.get(kk)}")
                    else:
                        d=parse_date_token(x,expected_year)
                        if d:vals.add(d);evidence.append(f"structured={x}")
        except:pass
    # HTML structured attributes.
    for m in re.finditer(r'(?is)(?:itemprop|property)=["\'](?:birthDate|dateOfBirth)["\'][^>]{0,300}',text):
        frag=m.group(0)
        for a in re.findall(r'(?:content|datetime|value)=["\']([^"\']+)["\']',frag,re.I):
            d=parse_date_token(a,expected_year)
            if d:vals.add(d);evidence.append("html-structured:"+a)
    # Explicit birth-marker windows only; strip tags for robustness.
    plain=re.sub(r"(?is)<script\b.*?</script>|<style\b.*?</style>"," ",text)
    plain=re.sub(r"(?s)<[^>]+>"," ",plain)
    plain=html.unescape(re.sub(r"\s+"," ",plain))
    for m in re.finditer(r"(?i)(?:\bborn\b|\bbirth\s*date\b|\bdate\s*of\s*birth\b)\s*[:=-]?\s*",plain):
        w=plain[m.end():m.end()+90]
        d=parse_date_token(w,expected_year)
        if d:
            vals.add(d);evidence.append(plain[max(0,m.start()-40):m.end()+120].strip())
    return sorted(vals),evidence

def source_domain(url):
    try:return urllib.parse.urlparse(url).netloc.lower()
    except:return ""
def weak_domain(d):
    return int(any(x in d for x in ("wikipedia.org","wikidata.org","dbpedia.org","fandom.com","peoplepill.com","birthdaydbs.com","famousbirthdays.com")))

rows=read_csv(INPUT)
if len(rows)!=3051:raise RuntimeError(f"Expected 3051 rows, got {len(rows)}")
known=[];unres=[]
for r in rows:
    q,b=reliable_qid(r)
    if not q:continue
    (known if present(r.get("final_exact_dob")) else unres).append((r,q,b))
known=sorted(known,key=lambda x:hashlib.sha256(x[0]["profile_url"].encode()).hexdigest())[:300]

allq=sorted({q for _,q,_ in known+unres})
ents={}
with ThreadPoolExecutor(max_workers=10) as ex:
    fs={ex.submit(entity,q):q for q in allq}
    for f in as_completed(fs):
        q=fs[f]
        try:qq,res=f.result();ents[qq]=res
        except Exception as e:ents[q]={"ok":0,"claims":[],"error":repr(e)}

def consensus_year(q):
    ys=set()
    for c in ents.get(q,{}).get("claims",[]):
        if c.get("date"):ys.add(c["date"][:4])
    return next(iter(ys)) if len(ys)==1 else ""

def urls_for(q,year=None):
    out=set()
    for c in ents.get(q,{}).get("claims",[]):
        if year and c.get("date") and c["date"][:4]!=str(year):continue
        for ref in c.get("references",[]):
            out.update(ref.get("urls",[]))
    return sorted(out)

known_targets=[];unres_targets=[]
for r,q,b in known:
    y=(r.get("final_exact_dob") or "")[:4]
    us=urls_for(q,y)
    if us:known_targets.append((r,q,b,y,us))
for r,q,b in unres:
    y=consensus_year(q)
    if not y:continue
    us=urls_for(q,y)
    if us:unres_targets.append((r,q,b,y,us))

allurls=sorted({u for _,_,_,_,us in known_targets+unres_targets for u in us})
pages={}
with ThreadPoolExecutor(max_workers=8) as ex:
    fs={ex.submit(get,u):u for u in allurls}
    for f in as_completed(fs):
        u=fs[f]
        try:st,data,ct,err=f.result();pages[u]={"status":st,"data":data,"ctype":ct,"error":err}
        except Exception as e:pages[u]={"status":"","data":b"","ctype":"","error":repr(e)}

def extract_for(urls,year):
    vals=set();ev=[];goodurls=[]
    for u in urls:
        p=pages.get(u,{})
        if not p.get("data"):continue
        ds,e=page_candidates(p["data"],p.get("ctype",""),year)
        if ds:
            vals.update(ds);ev.extend([f"{u} :: {x}" for x in e[:4]]);goodurls.append(u)
    return sorted(vals),ev,goodurls

valrows=[];comp=match=conf=0
for r,q,b,y,us in known_targets:
    ds,ev,gus=extract_for(us,y)
    if len(ds)==1:
        comp+=1
        if ds[0]==r.get("final_exact_dob"):match+=1
        else:
            conf+=1
            valrows.append({
              "profile_url":r["profile_url"],"name":r["name"],"qid":q,
              "master_exact_dob":r.get("final_exact_dob",""),"reference_candidate_dob":ds[0],
              "reference_urls":"|".join(gus),"evidence":" || ".join(ev)
            })

out=[];cands=[]
for r,q,b,y,us in unres_targets:
    ds,ev,gus=extract_for(us,y)
    conflict=int(len(ds)>1)
    cand=ds[0] if len(ds)==1 else ""
    ey=as_int(r.get("election_year"))
    age=ey-int(cand[:4]) if cand and ey else None
    ageok=int(age is not None and 25<=age<=100) if cand else ""
    domains=sorted({source_domain(u) for u in gus if source_domain(u)})
    weak=int(bool(domains) and all(weak_domain(d) for d in domains))
    row={
      "profile_url":r["profile_url"],"name":r["name"],"election_year":r.get("election_year",""),
      "affiliation":r.get("affiliation",""),"qid":q,"identity_basis":b,"consensus_birth_year":y,
      "p569_reference_urls":"|".join(us),"parsed_exact_dates":"|".join(ds),"candidate_dob":cand,
      "reference_date_conflict":conflict,"age_at_election":age if age is not None else "",
      "age_plausible":ageok,"candidate_source_domains":"|".join(domains),"all_candidate_domains_weak":weak,
      "candidate_for_manual_review":int(bool(cand) and not conflict and ageok==1 and not weak),
      "evidence":" || ".join(ev),
      "fetch_errors":" || ".join(f"{u}:{pages.get(u,{}).get('error','')}" for u in us if pages.get(u,{}).get("error"))
    }
    out.append(row)
    if int(row["candidate_for_manual_review"])==1:cands.append(row)

write_csv(OUT,out)
write_csv(VAL,valrows,["profile_url","name","qid","master_exact_dob","reference_candidate_dob","reference_urls","evidence"])
write_csv(CAND,cands,list(out[0].keys()) if out else [])
summary={
 "dataset":"NAS Wikidata P569 reference-URL exact-DOB diagnostic v1",
 "input_v14_rows":len(rows),
 "unresolved_reliable_qid_rows":len(unres),
 "validation_sample_rows":len(known),
 "wikidata_entity_fetch_successes":sum(int(ents.get(q,{}).get("ok",0)) for q in allq),
 "validation_rows_with_p569_reference_url":len(known_targets),
 "unresolved_rows_with_consensus_birth_year_and_reference_url":len(unres_targets),
 "unique_reference_urls_fetched":len(allurls),
 "reference_urls_with_http_content":sum(bool(pages[u].get("data")) for u in allurls),
 "validation_comparable_exact_rows":comp,
 "validation_exact_matches":match,
 "validation_exact_conflicts":conf,
 "validation_match_rate":round(match/comp,6) if comp else None,
 "unresolved_rows_with_unique_reference_exact_candidate":sum(bool(x["candidate_dob"]) and not int(x["reference_date_conflict"]) for x in out),
 "candidates_for_manual_review":len(cands),
 "bazi_variables_computed":0,
 "decision_note":"Diagnostic only. Exact dates are parsed only from structured birth-date fields or explicit born/birth-date text windows on URLs cited directly by Wikidata P569 references. No DOB is auto-written."
}
SUMMARY.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(summary,ensure_ascii=False,indent=2))
