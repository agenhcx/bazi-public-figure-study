#!/usr/bin/env python3
from __future__ import annotations
import csv, json, re, time, urllib.parse, urllib.request, urllib.error
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

BASE=Path("data/nas_science_core_dob_crosswalk")
INPUT=BASE/"nas_science_core_dob_crosswalk_v13.csv"
OUT=BASE/"nas_ambiguous_qid_affiliation_v1.csv"
CAND=BASE/"nas_ambiguous_qid_affiliation_candidates_v1.csv"
SUMMARY=BASE/"summary_ambiguous_qid_affiliation_v1.json"
QLEVER="https://qlever.dev/api/wikidata"
UA="bazi-public-figure-study/1.0 (ambiguous exact-name QID affiliation diagnostic; no BaZi computation)"
GENERIC={
"university","college","school","institute","institution","center","centre","department","laboratory","lab",
"national","medical","medicine","science","sciences","research","the","of","for","and","inc","corporation",
"company","hospital","foundation","academy","state","system","health","technology","technologies"
}

def read_csv(p):
    with p.open("r",encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
def write_csv(p,rows,fields=None):
    if fields is None:fields=list(rows[0].keys()) if rows else []
    with p.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore");w.writeheader();w.writerows(rows)
def present(v):return str(v or "").strip() not in ("","nan","None")
def norm(s):
    s=re.sub(r"[^a-z0-9]+"," ",str(s or "").lower())
    return " ".join(s.split())
def tokens(s):
    return {x for x in norm(s).split() if len(x)>2 and x not in GENERIC}
def sparql_literal(s):return json.dumps(s,ensure_ascii=False)+"@en"
def chunks(xs,n=80):
    for i in range(0,len(xs),n):yield xs[i:i+n]
def run_sparql(q,retries=6):
    body=urllib.parse.urlencode({"query":q,"action":"tsv_export"}).encode()
    last=None
    for i in range(retries):
        req=urllib.request.Request(QLEVER,data=body,method="POST",headers={"User-Agent":UA,"Content-Type":"application/x-www-form-urlencoded","Accept":"text/tab-separated-values"})
        try:
            with urllib.request.urlopen(req,timeout=300) as r:raw=r.read().decode("utf-8-sig")
            break
        except Exception as e:
            last=e
            if i+1>=retries:raise
            time.sleep(min(30,2**i))
    rr=list(csv.reader(raw.splitlines(),delimiter="\t"))
    if not rr:return []
    h=[x.lstrip("?").strip() for x in rr[0]];out=[]
    for row in rr[1:]:
        row+=[""]*(len(h)-len(row));d={}
        for j,k in enumerate(h):
            v=(row[j] or "").strip()
            if v.startswith("<") and v.endswith(">"):v=v[1:-1]
            elif len(v)>=2 and v[0]=='"':
                e=v.rfind('"')
                if e>0:v=v[1:e]
            v=re.sub(r"@[A-Za-z][A-Za-z0-9-]*$","",v)
            d[k]=v
        out.append(d)
    return out
def exact_date(s):
    m=re.search(r"([12]\d{3})-(\d{2})-(\d{2})",str(s or ""))
    return "-".join(m.groups()) if m else ""

rows=read_csv(INPUT)
if len(rows)!=3051:raise RuntimeError(f"Expected 3051 rows, got {len(rows)}")
unresolved=[r for r in rows if not present(r.get("final_exact_dob"))]
names=sorted({r["name"] for r in unresolved})

# exact official NAS name -> all human QIDs
hits=defaultdict(set)
for batch in chunks(names):
    vals=" ".join(sparql_literal(x) for x in batch)
    q=f"""PREFIX rdfs:<http://www.w3.org/2000/01/rdf-schema#>
PREFIX skos:<http://www.w3.org/2004/02/skos/core#>
PREFIX wdt:<http://www.wikidata.org/prop/direct/>
PREFIX wd:<http://www.wikidata.org/entity/>
SELECT DISTINCT ?query_name ?person WHERE {{
 VALUES ?query_name {{ {vals} }}
 {{ ?person rdfs:label ?query_name . }} UNION {{ ?person skos:altLabel ?query_name . }}
 ?person wdt:P31 wd:Q5 .
}}"""
    for x in run_sparql(q):
        if x.get("query_name") and x.get("person"):
            hits[x["query_name"]].add(x["person"].rsplit("/",1)[-1])

amb_names=[n for n,v in hits.items() if len(v)>1]
qid_set=sorted({q for n in amb_names for q in hits[n]})

# fetch employer/affiliation labels + P569 precision + P227/P244 for all ambiguous candidates
det=defaultdict(lambda:{"employers":set(),"dob":set(),"gnd":set(),"loc":set()})
for batch in chunks(qid_set,100):
    vals=" ".join("wd:"+q for q in batch if re.fullmatch(r"Q\d+",q))
    q=f"""PREFIX wd:<http://www.wikidata.org/entity/>
PREFIX wdt:<http://www.wikidata.org/prop/direct/>
PREFIX p:<http://www.wikidata.org/prop/>
PREFIX psv:<http://www.wikidata.org/prop/statement/value/>
PREFIX wikibase:<http://wikiba.se/ontology#>
PREFIX rdfs:<http://www.w3.org/2000/01/rdf-schema#>
SELECT DISTINCT ?person ?orgLabel ?dob ?precision ?gnd ?loc WHERE {{
 VALUES ?person {{ {vals} }}
 OPTIONAL {{
   {{ ?person wdt:P108 ?org . }} UNION {{ ?person wdt:P1416 ?org . }}
   ?org rdfs:label ?orgLabel . FILTER(LANG(?orgLabel)="en")
 }}
 OPTIONAL {{ ?person p:P569 ?st . ?st psv:P569 ?dv . ?dv wikibase:timeValue ?dob ; wikibase:timePrecision ?precision . }}
 OPTIONAL {{ ?person wdt:P227 ?gnd . }}
 OPTIONAL {{ ?person wdt:P244 ?loc . }}
}}"""
    for x in run_sparql(q):
        qq=x.get("person","").rsplit("/",1)[-1]
        if not qq:continue
        if x.get("orgLabel"):det[qq]["employers"].add(x["orgLabel"])
        if x.get("dob") and x.get("precision")=="11":
            d=exact_date(x["dob"])
            if d:det[qq]["dob"].add(d)
        if x.get("gnd"):det[qq]["gnd"].add(x["gnd"])
        if x.get("loc"):det[qq]["loc"].add(x["loc"])

def http_json(url,retries=4):
    last=None
    for i in range(retries):
        try:
            req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"application/json"})
            with urllib.request.urlopen(req,timeout=90) as r:return 1,json.loads(r.read().decode()),""
        except Exception as e:
            last=e
            if i+1>=retries:break
            time.sleep(min(10,2**i))
    return 0,None,repr(last)
def gnd_dates(obj):
    vals=set()
    if not isinstance(obj,dict):return []
    raw=obj.get("dateOfBirth",[])
    if not isinstance(raw,list):raw=[raw]
    for x in raw:
        if isinstance(x,dict):
            for k in ("@value","value","label"):
                d=exact_date(x.get(k,""))
                if d:vals.add(d)
        else:
            d=exact_date(x)
            if d:vals.add(d)
    return sorted(vals)
def walk(obj):
    vals=[]
    if isinstance(obj,dict):
        for k,v in obj.items():
            if "birthdate" in str(k).lower():vals.append(v)
            vals.extend(walk(v))
    elif isinstance(obj,list):
        for x in obj:vals.extend(walk(x))
    return vals
def strings(obj):
    out=[]
    if isinstance(obj,str):out.append(obj)
    elif isinstance(obj,dict):
        for v in obj.values():out.extend(strings(v))
    elif isinstance(obj,list):
        for x in obj:out.extend(strings(x))
    return out
def loc_dates(obj):
    vals=set()
    for x in walk(obj):
        for s in strings(x):
            d=exact_date(s)
            if d:vals.add(d)
    return sorted(vals)
def fetch(kind,ident):
    if kind=="gnd":
        ok,obj,err=http_json(f"https://lobid.org/gnd/{urllib.parse.quote(ident)}.json")
        return gnd_dates(obj) if ok else [],ok,err
    ok,obj,err=http_json(f"https://id.loc.gov/authorities/names/{urllib.parse.quote(ident)}.json")
    return loc_dates(obj) if ok else [],ok,err

# resolve identity only when exactly one ambiguous QID has meaningful affiliation overlap
selected=[]
allrows=[]
for r in unresolved:
    name=r["name"]
    qs=sorted(hits.get(name,set()))
    if len(qs)<=1:continue
    at=tokens(r.get("affiliation",""))
    scores=[]
    for q in qs:
        overlaps=set()
        for e in det[q]["employers"]:
            overlaps |= at.intersection(tokens(e))
        scores.append((q,overlaps))
    positive=[(q,o) for q,o in scores if o]
    chosen=positive[0][0] if len(positive)==1 else ""
    for q,o in scores:
        allrows.append({
          "profile_url":r["profile_url"],"name":name,"election_year":r.get("election_year",""),
          "affiliation":r.get("affiliation",""),"candidate_qid":q,"exact_name_human_qid_count":len(qs),
          "candidate_employers":"|".join(sorted(det[q]["employers"])),
          "affiliation_overlap_tokens":"|".join(sorted(o)),
          "is_unique_affiliation_resolved_qid":int(bool(chosen and q==chosen)),
          "wikidata_exact_dates":"|".join(sorted(det[q]["dob"])),
          "gnd_ids":"|".join(sorted(det[q]["gnd"])),"loc_ids":"|".join(sorted(det[q]["loc"]))
        })
    if chosen:selected.append((r,chosen))

# query authority dates only for affiliation-resolved identities
ids=set()
for r,q in selected:
    ids|={("gnd",x) for x in det[q]["gnd"]}
    ids|={("loc",x) for x in det[q]["loc"]}
fetched={}
with ThreadPoolExecutor(max_workers=6) as ex:
    fs={ex.submit(fetch,k,i):(k,i) for k,i in ids}
    for f in as_completed(fs):
        k=fs[f]
        try:fetched[k]=f.result()
        except Exception as e:fetched[k]=([],0,repr(e))

candidates=[]
for r,q in selected:
    wd=sorted(det[q]["dob"])
    g=set();l=set()
    for x in det[q]["gnd"]:g.update(fetched.get(("gnd",x),([],0,""))[0])
    for x in det[q]["loc"]:l.update(fetched.get(("loc",x),([],0,""))[0])
    g=sorted(g);l=sorted(l)
    vals=set(wd+g+l)
    cand=next(iter(vals)) if len(vals)==1 else ""
    conflict=int(len(vals)>1)
    basis=[]
    if wd:basis.append("wikidata_exact")
    if g:basis.append("gnd")
    if l:basis.append("loc")
    try:age=int(r.get("election_year") or 0)-int(cand[:4]) if cand else None
    except:age=None
    ageok=int(age is not None and 25<=age<=100) if cand else ""
    candidates.append({
      "profile_url":r["profile_url"],"name":r["name"],"election_year":r.get("election_year",""),
      "affiliation":r.get("affiliation",""),"resolved_qid":q,
      "employers":"|".join(sorted(det[q]["employers"])),
      "wikidata_exact_dates":"|".join(wd),"gnd_exact_dates":"|".join(g),"loc_exact_dates":"|".join(l),
      "authority_candidate_dob":cand,"candidate_basis":"+".join(basis),
      "source_conflict":conflict,"age_at_election":age if age is not None else "",
      "age_plausible":ageok,"candidate_for_manual_provenance_review":int(bool(cand) and not conflict and ageok==1)
    })

write_csv(OUT,allrows)
review=[x for x in candidates if int(x["candidate_for_manual_provenance_review"])==1]
write_csv(CAND,review,list(candidates[0].keys()) if candidates else [])
summary={
 "dataset":"NAS ambiguous exact-name QID affiliation disambiguation diagnostic v1",
 "input_v13_rows":len(rows),
 "unresolved_rows":len(unresolved),
 "unresolved_names_with_multiple_exact_name_human_qids":len({r["name"] for r in unresolved if len(hits.get(r["name"],set()))>1}),
 "ambiguous_candidate_qid_rows":len(allrows),
 "rows_resolved_to_unique_qid_by_affiliation":len(selected),
 "resolved_rows_with_any_exact_dob_candidate":sum(bool(x["authority_candidate_dob"]) for x in candidates),
 "resolved_rows_with_source_conflict":sum(int(x["source_conflict"]) for x in candidates),
 "candidates_for_manual_provenance_review":len(review),
 "bazi_variables_computed":0,
 "decision_note":"Diagnostic only. Identity resolution requires multiple exact-name human QIDs but exactly one candidate sharing at least one meaningful employer/affiliation token with the NAS row. DOBs are not written automatically."
}
SUMMARY.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(summary,ensure_ascii=False,indent=2))
