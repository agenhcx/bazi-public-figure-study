#!/usr/bin/env python3
from __future__ import annotations
import csv, hashlib, html, io, json, re, time, urllib.parse, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from pypdf import PdfReader

BASE=Path("data/nas_science_core_dob_crosswalk")
INPUT=BASE/"nas_science_core_dob_crosswalk_v14.csv"
OUT=BASE/"nas_p856_official_cv_dob_v1.csv"
VAL=BASE/"nas_p856_official_cv_validation_conflicts_v1.csv"
CAND=BASE/"nas_p856_official_cv_candidates_v1.csv"
SUMMARY=BASE/"summary_p856_official_cv_dob_v1.json"
UA="bazi-public-figure-study/1.0 (P856 official homepage/CV DOB diagnostic; no BaZi computation)"

MONTHS={m.lower():i for i,m in enumerate(["","January","February","March","April","May","June","July","August","September","October","November","December"])}
for k,v in list(MONTHS.items()):
    if len(k)>=3: MONTHS[k[:3]]=v

def read_csv(p):
    with p.open("r",encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
def write_csv(p,rows,fields=None):
    fields=fields or (list(rows[0].keys()) if rows else [])
    with p.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore");w.writeheader();w.writerows(rows)
def present(v): return str(v or "").strip() not in ("","nan","None")
def as_int(v,d=0):
    try:return int(float(str(v)))
    except:return d
def norm_name(s): return " ".join(re.sub(r"[^a-z0-9]+"," ",str(s or "").lower()).split())
def reliable_qid(r):
    q=(r.get("wikidata_qid") or "").strip()
    if re.fullmatch(r"Q\d+",q):return q,"wikidata_qid"
    q=(r.get("global_candidate_qid") or "").strip()
    if not re.fullmatch(r"Q\d+",q):return "",""
    if as_int(r.get("global_exact_name_match_count"))!=1:return "",""
    toks=len(norm_name(r.get("name","")).split())
    if toks>=3 or as_int(r.get("global_affiliation_match"))==1:return q,"global_unique_identity"
    return "",""

def get(url,accept="text/html,application/xhtml+xml,application/pdf;q=0.9,*/*;q=0.1",retries=3):
    last=None
    for i in range(retries):
        try:
            req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":accept})
            with urllib.request.urlopen(req,timeout=60) as r:
                return getattr(r,"status",200),r.read(8_000_000),r.headers.get_content_type(),r.geturl(),""
        except urllib.error.HTTPError as e:
            last=e
            if e.code in {401,403,404}: return e.code,b"","",url,"HTTP "+str(e.code)
            if i+1>=retries or e.code not in {429,500,502,503,504}:break
            time.sleep(min(10,2**i))
        except Exception as e:
            last=e
            if i+1>=retries:break
            time.sleep(min(10,2**i))
    return getattr(last,"code",""),b"","",url,repr(last)

def dv(snak):
    try:return snak["datavalue"]["value"]
    except:return None

def entity(qid):
    url=f"https://www.wikidata.org/wiki/Special:EntityData/{qid}.json"
    st,data,ct,final,err=get(url,"application/json")
    if not data:return qid,{"ok":0,"p856":[],"error":err}
    try:
        obj=json.loads(data.decode("utf-8"))
        ent=(obj.get("entities") or {}).get(qid) or {}
        vals=[]
        for c in (ent.get("claims") or {}).get("P856",[]):
            v=dv(c.get("mainsnak") or {})
            if isinstance(v,str) and v.startswith(("http://","https://")): vals.append(v)
        return qid,{"ok":1,"p856":sorted(set(vals)),"error":""}
    except Exception as e:return qid,{"ok":0,"p856":[],"error":repr(e)}

def iso(y,m,d):
    try:
        import datetime as dt
        return dt.date(int(y),int(m),int(d)).isoformat()
    except:return ""

def parse_date_token(s,expected_year=None):
    s=html.unescape(str(s or "")).strip()
    pats=[
      (r"\b([12]\d{3})[-/.](\d{1,2})[-/.](\d{1,2})\b","ymd"),
      (r"\b(\d{1,2})[-/.](\d{1,2})[-/.]([12]\d{3})\b","mdy"),
      (r"\b([A-Za-z]{3,9})\s+(\d{1,2})(?:st|nd|rd|th)?[,]?\s+([12]\d{3})\b","mdytext"),
      (r"\b(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]{3,9})[,]?\s+([12]\d{3})\b","dmytext"),
    ]
    for p,t in pats:
        m=re.search(p,s,re.I)
        if not m:continue
        if t=="ymd": d=iso(m.group(1),m.group(2),m.group(3))
        elif t=="mdy": d=iso(m.group(3),m.group(1),m.group(2))
        elif t=="mdytext":
            mo=MONTHS.get(m.group(1).lower()[:3],0); d=iso(m.group(3),mo,m.group(2)) if mo else ""
        else:
            mo=MONTHS.get(m.group(2).lower()[:3],0); d=iso(m.group(3),mo,m.group(1)) if mo else ""
        if d and (not expected_year or d.startswith(str(expected_year)+"-")): return d
    return ""

def structured_birth_values(obj):
    vals=[]
    if isinstance(obj,dict):
        for k,v in obj.items():
            kl=str(k).lower()
            if any(x in kl for x in ("birthdate","dateofbirth","birth_date","date_of_birth")): vals.append(v)
            vals.extend(structured_birth_values(v))
    elif isinstance(obj,list):
        for x in obj:vals.extend(structured_birth_values(x))
    return vals

def extract_text_dates(text,expected_year):
    vals=set();evidence=[]
    plain=html.unescape(re.sub(r"\s+"," ",text))
    for m in re.finditer(r"(?i)(?:\bborn\b|\bbirth\s*date\b|\bdate\s*of\s*birth\b)\s*[:=-]?\s*",plain):
        w=plain[m.end():m.end()+100]
        d=parse_date_token(w,expected_year)
        if d:
            vals.add(d);evidence.append(plain[max(0,m.start()-50):m.end()+140].strip())
    return vals,evidence

def parse_html(data,expected_year,base_url):
    text=data.decode("utf-8","ignore")
    vals=set();evidence=[]
    # JSON-LD and JSON fragments
    for m in re.finditer(r'(?is)<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',text):
        try:
            obj=json.loads(html.unescape(m.group(1)))
            for v in structured_birth_values(obj):
                for x in (v if isinstance(v,list) else [v]):
                    if isinstance(x,dict):
                        for kk in ("@value","value","label"):
                            d=parse_date_token(x.get(kk),expected_year)
                            if d:vals.add(d);evidence.append(f"jsonld:{kk}={x.get(kk)}")
                    else:
                        d=parse_date_token(x,expected_year)
                        if d:vals.add(d);evidence.append(f"jsonld={x}")
        except: pass
    for m in re.finditer(r'(?is)(?:itemprop|property)=["\'](?:birthDate|dateOfBirth)["\'][^>]{0,300}',text):
        frag=m.group(0)
        for a in re.findall(r'(?:content|datetime|value)=["\']([^"\']+)["\']',frag,re.I):
            d=parse_date_token(a,expected_year)
            if d:vals.add(d);evidence.append("html-structured:"+a)
    nojs=re.sub(r"(?is)<script\b.*?</script>|<style\b.*?</style>"," ",text)
    plain=re.sub(r"(?s)<[^>]+>"," ",nojs)
    a,b=extract_text_dates(plain,expected_year); vals|=a;evidence+=b
    links=[]
    for m in re.finditer(r'(?is)<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',text):
        href=html.unescape(m.group(1)); anchor=re.sub(r"(?s)<[^>]+>"," ",m.group(2))
        joined=(href+" "+anchor).lower()
        if re.search(r"\b(cv|curriculum|vitae|biograph|bio|profile)\b",joined):
            try:
                u=urllib.parse.urljoin(base_url,href)
                if u.startswith(("http://","https://")):links.append(u)
            except:pass
    return sorted(vals),evidence,links

def parse_pdf(data,expected_year):
    vals=set();evidence=[]
    try:
        rd=PdfReader(io.BytesIO(data))
        text=" ".join((p.extract_text() or "") for p in rd.pages[:25])
        a,b=extract_text_dates(text,expected_year);vals|=a;evidence+=b
    except Exception as e:
        return [],[],repr(e)
    return sorted(vals),evidence,""

def host(u):
    try:return urllib.parse.urlparse(u).netloc.lower().split(":")[0]
    except:return ""
def same_site(a,b):
    ha,hb=host(a),host(b)
    return bool(ha and hb and (ha==hb or ha.endswith("."+hb) or hb.endswith("."+ha)))

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
        except Exception as e:ents[q]={"ok":0,"p856":[],"error":repr(e)}

targets=[]
for cohort,data in (("validation",known),("unresolved",unres)):
    for r,q,b in data:
        us=ents.get(q,{}).get("p856",[])
        if not us:continue
        y=(r.get("final_exact_dob") or "")[:4] if cohort=="validation" else ""
        targets.append((cohort,r,q,b,y,us))

root_urls=sorted({u for *_,us in targets for u in us})
pages={}
with ThreadPoolExecutor(max_workers=8) as ex:
    fs={ex.submit(get,u):u for u in root_urls}
    for f in as_completed(fs):
        u=fs[f]
        try:st,data,ct,final,err=f.result();pages[u]={"status":st,"data":data,"ctype":ct,"final":final,"error":err}
        except Exception as e:pages[u]={"status":"","data":b"","ctype":"","final":u,"error":repr(e)}

# Discover likely CV/bio links from root homepages.
link_targets=set()
root_parsed={}
for cohort,r,q,b,y,us in targets:
    expected=y or None
    for u in us:
        p=pages.get(u,{})
        if not p.get("data"):continue
        ct=p.get("ctype","")
        if "pdf" in ct or str(p.get("final","")).lower().endswith(".pdf"):
            ds,ev,err=parse_pdf(p["data"],expected)
            root_parsed[(u,expected)]={"dates":ds,"evidence":ev,"links":[],"error":err}
        else:
            ds,ev,links=parse_html(p["data"],expected,p.get("final") or u)
            links=[x for x in links if same_site(p.get("final") or u,x)][:4]
            root_parsed[(u,expected)]={"dates":ds,"evidence":ev,"links":links,"error":""}
            link_targets.update(links)

linked_pages={}
with ThreadPoolExecutor(max_workers=8) as ex:
    fs={ex.submit(get,u):u for u in sorted(link_targets)}
    for f in as_completed(fs):
        u=fs[f]
        try:st,data,ct,final,err=f.result();linked_pages[u]={"status":st,"data":data,"ctype":ct,"final":final,"error":err}
        except Exception as e:linked_pages[u]={"status":"","data":b"","ctype":"","final":u,"error":repr(e)}

def extract_for(r,us,known_exact=""):
    expected=(known_exact[:4] if known_exact else None)
    vals=set();ev=[];used=[];errs=[]
    for u in us:
        p=pages.get(u,{})
        if not p.get("data"):
            if p.get("error"):errs.append(f"{u}:{p['error']}")
            continue
        rp=root_parsed.get((u,expected))
        if rp is None:
            ct=p.get("ctype","")
            if "pdf" in ct or str(p.get("final","")).lower().endswith(".pdf"):
                ds,e,er=parse_pdf(p["data"],expected);links=[]
            else:
                ds,e,links=parse_html(p["data"],expected,p.get("final") or u);er=""
                links=[x for x in links if same_site(p.get("final") or u,x)][:4]
            rp={"dates":ds,"evidence":e,"links":links,"error":er}
        if rp["dates"]:
            vals.update(rp["dates"]);ev.extend([f"{u} :: {x}" for x in rp["evidence"][:5]]);used.append(u)
        if rp.get("error"):errs.append(f"{u}:{rp['error']}")
        for lu in rp.get("links",[])[:4]:
            lp=linked_pages.get(lu,{})
            if not lp.get("data"):
                if lp.get("error"):errs.append(f"{lu}:{lp['error']}")
                continue
            ct=lp.get("ctype","")
            if "pdf" in ct or str(lp.get("final","")).lower().endswith(".pdf"):
                ds,e,er=parse_pdf(lp["data"],expected)
                if er:errs.append(f"{lu}:{er}")
            else:
                ds,e,_=parse_html(lp["data"],expected,lp.get("final") or lu)
            if ds:
                vals.update(ds);ev.extend([f"{lu} :: {x}" for x in e[:5]]);used.append(lu)
    return sorted(vals),ev,sorted(set(used)),errs

valrows=[];comp=match=conf=0
for r,q,b in known:
    us=ents.get(q,{}).get("p856",[])
    if not us:continue
    ds,ev,used,errs=extract_for(r,us,r.get("final_exact_dob",""))
    if len(ds)==1:
        comp+=1
        if ds[0]==r.get("final_exact_dob"):match+=1
        else:
            conf+=1
            valrows.append({
              "profile_url":r["profile_url"],"name":r["name"],"qid":q,
              "master_exact_dob":r.get("final_exact_dob",""),"official_site_candidate_dob":ds[0],
              "source_urls":"|".join(used),"evidence":" || ".join(ev)
            })

out=[];cands=[]
for r,q,b in unres:
    us=ents.get(q,{}).get("p856",[])
    if not us:continue
    ds,ev,used,errs=extract_for(r,us,"")
    conflict=int(len(ds)>1);cand=ds[0] if len(ds)==1 else ""
    ey=as_int(r.get("election_year"));age=ey-int(cand[:4]) if cand and ey else None
    ageok=int(age is not None and 25<=age<=100) if cand else ""
    row={
      "profile_url":r["profile_url"],"name":r["name"],"election_year":r.get("election_year",""),
      "affiliation":r.get("affiliation",""),"qid":q,"identity_basis":b,
      "p856_urls":"|".join(us),"parsed_exact_dates":"|".join(ds),"candidate_dob":cand,
      "date_conflict":conflict,"age_at_election":age if age is not None else "","age_plausible":ageok,
      "candidate_for_manual_review":int(bool(cand) and not conflict and ageok==1),
      "source_urls":"|".join(used),"evidence":" || ".join(ev),"fetch_errors":" || ".join(errs)
    }
    out.append(row)
    if int(row["candidate_for_manual_review"])==1:cands.append(row)

write_csv(OUT,out)
write_csv(VAL,valrows,["profile_url","name","qid","master_exact_dob","official_site_candidate_dob","source_urls","evidence"])
write_csv(CAND,cands,list(out[0].keys()) if out else [])
summary={
 "dataset":"NAS Wikidata P856 official homepage/CV exact-DOB diagnostic v1",
 "input_v14_rows":len(rows),
 "unresolved_reliable_qid_rows":len(unres),
 "validation_sample_rows":len(known),
 "wikidata_entity_fetch_successes":sum(int(ents.get(q,{}).get("ok",0)) for q in allq),
 "validation_rows_with_p856":sum(bool(ents.get(q,{}).get("p856")) for _,q,_ in known),
 "unresolved_rows_with_p856":sum(bool(ents.get(q,{}).get("p856")) for _,q,_ in unres),
 "unique_root_p856_urls":len(root_urls),
 "root_urls_with_http_content":sum(bool(pages[u].get("data")) for u in root_urls),
 "discovered_same_site_cv_bio_links":len(link_targets),
 "linked_cv_bio_urls_with_http_content":sum(bool(linked_pages[u].get("data")) for u in linked_pages),
 "validation_comparable_exact_rows":comp,
 "validation_exact_matches":match,
 "validation_exact_conflicts":conf,
 "validation_match_rate":round(match/comp,6) if comp else None,
 "unresolved_rows_with_unique_official_exact_candidate":sum(bool(x["candidate_dob"]) and not int(x["date_conflict"]) for x in out),
 "candidates_for_manual_review":len(cands),
 "bazi_variables_computed":0,
 "decision_note":"Diagnostic only. P856 official homepages and same-site CV/bio/profile links are parsed only for structured birth-date fields or explicit born/birth-date text. No DOB is auto-written."
}
SUMMARY.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(summary,ensure_ascii=False,indent=2))
