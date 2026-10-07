#!/usr/bin/env python3
from __future__ import annotations
import csv, datetime as dt, hashlib, html, json, re, time, urllib.parse, urllib.request
from pathlib import Path

INPUT=Path("data/nas_science_core_dob_crosswalk/nas_science_core_dob_crosswalk_v6.csv")
OUT=Path("data/nas_science_core_dob_crosswalk")
QLEVER_ENDPOINT="https://qlever.dev/api/wikidata"
WIKIPEDIA_API="https://en.wikipedia.org/w/api.php"
USER_AGENT="bazi-public-figure-study/1.0 (NAS DOB source validation; no BaZi computation)"
VALIDATION_SAMPLE_N=300
TITLE_BATCH=40

def read_csv(p):
    with p.open("r",encoding="utf-8-sig",newline="") as f: return list(csv.DictReader(f))
def write_csv(p,rows,fields):
    with p.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore"); w.writeheader(); w.writerows(rows)
def present(v): return str(v or "").strip() not in ("","nan","None")
def as_int(v,default=0):
    try:return int(float(str(v)))
    except:return default

def http_json(url,retries=5):
    last=None
    for a in range(retries):
        try:
            req=urllib.request.Request(url,headers={"User-Agent":USER_AGENT,"Accept":"application/json"})
            with urllib.request.urlopen(req,timeout=120) as r: return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            last=e
            if a+1<retries: time.sleep(min(20,2**a))
    raise RuntimeError(f"HTTP failed: {url}\n{last}")

def qlever_tsv(query):
    body=urllib.parse.urlencode({"query":query,"action":"tsv_export"}).encode()
    req=urllib.request.Request(QLEVER_ENDPOINT,data=body,method="POST",headers={
        "User-Agent":USER_AGENT,"Content-Type":"application/x-www-form-urlencoded","Accept":"text/tab-separated-values"})
    with urllib.request.urlopen(req,timeout=300) as r: raw=r.read().decode("utf-8-sig")
    rr=list(csv.reader(raw.splitlines(),delimiter="\t"))
    if not rr:return []
    h=[x.lstrip("?") for x in rr[0]]; out=[]
    for row in rr[1:]:
        if not row:continue
        row+=[""]*(len(h)-len(row)); vals=[]
        for v in row[:len(h)]:
            v=v.strip()
            if v.startswith("<") and v.endswith(">"):v=v[1:-1]
            elif len(v)>=2 and v[0]=='"':
                e=v.rfind('"')
                if e>0:v=v[1:e]
            vals.append(v)
        out.append(dict(zip(h,vals)))
    return out

def reliable_qid(r):
    if present(r.get("wikidata_qid")):
        return r["wikidata_qid"].strip(),r.get("wikidata_match_method","") or "wikidata_crosswalk"
    if present(r.get("global_candidate_qid")) and as_int(r.get("global_affiliation_match"))==1:
        return r["global_candidate_qid"].strip(),"global_exact_name_plus_affiliation"
    return "",""

def qid_to_enwiki(qids):
    out={}; qids=sorted(set(q for q in qids if q))
    for i in range(0,len(qids),250):
        b=qids[i:i+250]; values=" ".join("wd:"+q for q in b)
        query=f"""PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX schema: <http://schema.org/>
SELECT ?person ?article WHERE {{
 VALUES ?person {{ {values} }}
 ?article schema:about ?person ;
          schema:isPartOf <https://en.wikipedia.org/> .
}}"""
        for r in qlever_tsv(query):
            p=r.get("person",""); a=r.get("article","")
            if p and a:
                out[p.rsplit("/",1)[-1]]=urllib.parse.unquote(a.rsplit("/wiki/",1)[-1]).replace("_"," ")
    return out

def fetch_wikitext_batch(titles):
    params={"action":"query","prop":"revisions","rvprop":"content","rvslots":"main","titles":"|".join(titles),
            "redirects":"1","format":"json","formatversion":"2"}
    obj=http_json(WIKIPEDIA_API+"?"+urllib.parse.urlencode(params)); out={}
    for p in obj.get("query",{}).get("pages",[]):
        title=p.get("title",""); revs=p.get("revisions") or []; content=""
        if revs: content=revs[0].get("slots",{}).get("main",{}).get("content","")
        if title: out[title]=content
    return out

def fetch_all_wikitext(titles):
    out={}; titles=sorted(set(titles))
    for i in range(0,len(titles),TITLE_BATCH):
        out.update(fetch_wikitext_batch(titles[i:i+TITLE_BATCH])); time.sleep(0.15)
    return out

MONTHS={m.lower():i+1 for i,m in enumerate(
    "January February March April May June July August September October November December".split())}
def valid_date(y,m,d):
    try:return dt.date(int(y),int(m),int(d)).isoformat()
    except:return ""

def parse_birth_date_field(wt):
    if not wt:return []
    vals=set()
    for m in re.finditer(r"(?im)^\s*\|\s*birth_date\s*=\s*(.*?)\s*$",wt):
        raw=html.unescape(m.group(1)).strip(); low=raw.lower().replace("_"," ")
        tm=re.search(r"\{\{\s*birth\s*date(?:\s*and\s*age)?\s*\|([^{}]+)\}\}",low,re.I)
        if tm:
            parts=[x.strip() for x in tm.group(1).split("|")]; nums=[]
            for x in [x for x in parts if "=" not in x]:
                if re.fullmatch(r"\d{1,4}",x): nums.append(int(x))
            if len(nums)>=3 and nums[0]>=1000:
                z=valid_date(nums[0],nums[1],nums[2])
                if z:vals.add(z)
        for z in re.findall(r"\b(\d{4}-\d{2}-\d{2})\b",raw):
            try: dt.date.fromisoformat(z); vals.add(z)
            except: pass
        mm=re.search(r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+(\d{4})\b",raw,re.I)
        if mm:
            z=valid_date(mm.group(3),MONTHS[mm.group(1).lower()],mm.group(2))
            if z:vals.add(z)
        dm=re.search(r"\b(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})\b",raw,re.I)
        if dm:
            z=valid_date(dm.group(3),MONTHS[dm.group(2).lower()],dm.group(1))
            if z:vals.add(z)
    return sorted(vals)

def election_age(y,d):
    try:return int(y)-dt.date.fromisoformat(d).year
    except:return None
def validation_hash(r):return hashlib.sha256(r["profile_url"].encode()).hexdigest()

def main():
    rows=read_csv(INPUT)
    if len(rows)!=3051:raise RuntimeError(f"Expected 3051 rows, got {len(rows)}")
    missing=[r for r in rows if not present(r.get("final_exact_dob"))]
    exact=[r for r in rows if present(r.get("final_exact_dob"))]
    missing_rel=[]
    for r in missing:
        q,b=reliable_qid(r)
        if q:missing_rel.append((r,q,b))
    validation=[]
    for r in exact:
        q,b=reliable_qid(r)
        if q:validation.append((r,q,b))
    validation.sort(key=lambda x:validation_hash(x[0])); sample=validation[:VALIDATION_SAMPLE_N]
    qids=sorted({q for _,q,_ in missing_rel+sample})
    titles=qid_to_enwiki(qids); wt=fetch_all_wikitext(titles.values())
    result=[]
    def add(r,q,b,purpose):
        title=titles.get(q,""); text=wt.get(title,"") if title else ""; dates=parse_birth_date_field(text)
        existing=r.get("final_exact_dob","").strip(); unique=dates[0] if len(dates)==1 else ""
        age=election_age(r.get("election_year",""),unique) if unique else None
        plausible=int(age is not None and 25<=age<=100); comp=""
        if purpose=="validation" and existing and unique:comp="match" if existing==unique else "conflict"
        result.append({"profile_url":r.get("profile_url",""),"name":r.get("name",""),"election_year":r.get("election_year",""),
          "primary_section":r.get("primary_section",""),"affiliation":r.get("affiliation",""),"purpose":purpose,"qid":q,
          "identity_basis":b,"enwiki_title":title,"wikitext_found":int(bool(text)),
          "wikipedia_birth_date_values":"|".join(dates),"wikipedia_birth_date_count":len(dates),
          "existing_final_exact_dob":existing,"validation_comparison":comp,
          "wikipedia_age_at_election":age if age is not None else "","wikipedia_age_plausible":plausible,
          "candidate_for_supplement":int(purpose=="missing" and len(dates)==1 and plausible==1)})
    for x in sample:add(*x,"validation")
    for x in missing_rel:add(*x,"missing")
    out=OUT/"nas_wikipedia_birthdate_diagnostic.csv"; write_csv(out,result,list(result[0].keys()))
    val=[r for r in result if r["purpose"]=="validation"]; miss=[r for r in result if r["purpose"]=="missing"]
    cmp=[r for r in val if r["validation_comparison"] in ("match","conflict")]
    summary={"source":"English Wikipedia birth_date infobox field via MediaWiki wikitext API",
      "qid_to_sitelink_source":"Wikidata via QLever schema:about/schema:isPartOf","qlever_endpoint":QLEVER_ENDPOINT,
      "wikipedia_api":WIKIPEDIA_API,"input_science_core_rows":len(rows),"input_final_exact_dob_rows":len(exact),
      "input_missing_exact_dob_rows":len(missing),"missing_rows_with_reliable_qid":len(missing_rel),
      "validation_eligible_rows_with_reliable_qid":len(validation),"validation_sample_n":len(sample),
      "unique_qids_queried":len(qids),"enwiki_sitelinks_found":sum(q in titles for q in qids),
      "unique_enwiki_pages_requested":len(set(titles.values())),"wikitext_pages_returned":sum(bool(x) for x in wt.values()),
      "validation_rows_with_unique_birth_date":sum(r["wikipedia_birth_date_count"]==1 for r in val),
      "validation_comparable_rows":len(cmp),"validation_exact_matches":sum(r["validation_comparison"]=="match" for r in val),
      "validation_exact_conflicts":sum(r["validation_comparison"]=="conflict" for r in val),
      "validation_match_rate":round(sum(r["validation_comparison"]=="match" for r in val)/len(cmp),6) if cmp else None,
      "missing_rows_with_unique_birth_date":sum(r["wikipedia_birth_date_count"]==1 for r in miss),
      "missing_rows_candidate_for_supplement":sum(r["candidate_for_supplement"] for r in miss),
      "bazi_variables_computed":0,
      "decision_note":"Diagnostic only. Do not write Wikipedia dates into the master until validation concordance is reviewed."}
    (OUT/"summary_wikipedia_birthdate_diagnostic.json").write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps(summary,indent=2,ensure_ascii=False))
if __name__=="__main__":main()
