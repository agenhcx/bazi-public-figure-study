#!/usr/bin/env python3
from __future__ import annotations
import csv,json,re,time,unicodedata,urllib.parse,urllib.request
from collections import defaultdict,Counter
from pathlib import Path

INPUT=Path("data/leopoldina_dob_crosswalk_v1/leopoldina_dob_crosswalk_after_official_v1.csv")
OUT=Path("data/leopoldina_wikidata_identity_pilot_v1")
QLEVER="https://qlever.dev/api/wikidata"
LEOPOLDINA="Q543804"
UA="bazi-public-figure-study/1.0 (Leopoldina Wikidata identity locator; no BaZi computation)"
PROPS={"P214":"viaf_id","P227":"gnd_id","P244":"loc_id","P268":"bnf_id","P269":"idref_id","P213":"isni_id","P856":"official_homepage"}

def read_csv(p):
    with p.open("r",encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
def write_csv(p,rows,fields):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore");w.writeheader();w.writerows(rows)
def query(q,retries=5):
    body=urllib.parse.urlencode({"query":q,"action":"tsv_export"}).encode()
    last=None
    for i in range(retries):
        try:
            req=urllib.request.Request(QLEVER,data=body,method="POST",headers={"User-Agent":UA,"Content-Type":"application/x-www-form-urlencoded","Accept":"text/tab-separated-values"})
            with urllib.request.urlopen(req,timeout=240) as r:raw=r.read().decode("utf-8-sig")
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
        except Exception as e:
            last=e
            if i+1>=retries:raise
            time.sleep(min(20,2**i))
    raise RuntimeError(last)
def fold(s):
    s=unicodedata.normalize("NFKD",str(s or ""));s="".join(c for c in s if not unicodedata.combining(c)).lower()
    return " ".join(re.sub(r"[^a-z0-9]+"," ",s).split())
DROP={"prof","professor","dr","em","emeritus","sir","lord","frhr","freiherr"}
def name_key(s):
    xs=fold(s).split()
    # Remove academic/honorific tokens, but retain particles such as von/zur/de.
    xs=[x for x in xs if x not in DROP]
    return " ".join(xs)
def roster_keys(r):
    keys=set()
    d=name_key(re.sub(r"\([^)]*$","",r.get("display_name","")))
    if d:keys.add(d)
    slug=re.sub(r"-\d+$","",r.get("member_slug",""))
    sk=name_key(slug.replace("-"," "))
    if sk:keys.add(sk)
    # Initial-insensitive key helps labels omitting middle initials but is never sufficient if ambiguous.
    if d:
        toks=d.split()
        if len(toks)>=3:
            keys.add(" ".join([toks[0],toks[-1]]))
    return keys
def chunks(xs,n=120):
    for i in range(0,len(xs),n):yield xs[i:i+n]
def qid(uri):return uri.rsplit("/",1)[-1]
def precision_int(v):
    try:return int(float(str(v)))
    except:return None

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    roster=read_csv(INPUT)
    if len(roster)!=2888:raise RuntimeError(f"Expected 2888 roster rows, got {len(roster)}")
    # Membership-scoped candidate universe.
    members=query(f"""PREFIX wd:<http://www.wikidata.org/entity/>
PREFIX wdt:<http://www.wikidata.org/prop/direct/>
SELECT DISTINCT ?person WHERE {{ ?person wdt:P463 wd:{LEOPOLDINA} . }} ORDER BY ?person""")
    qids=sorted({qid(r["person"]) for r in members if r.get("person")})
    if len(qids)<100:raise RuntimeError(f"Implausibly small Wikidata Leopoldina P463 universe: {len(qids)}")
    labels=defaultdict(set)
    for batch in chunks(qids,250):
        values=" ".join("wd:"+q for q in batch)
        q=f"""PREFIX wd:<http://www.wikidata.org/entity/>
PREFIX rdfs:<http://www.w3.org/2000/01/rdf-schema#>
PREFIX skos:<http://www.w3.org/2004/02/skos/core#>
SELECT ?person ?label ?kind WHERE {{
 VALUES ?person {{ {values} }}
 {{ ?person rdfs:label ?label . BIND("label" AS ?kind) }}
 UNION
 {{ ?person skos:altLabel ?label . BIND("alt" AS ?kind) }}
 FILTER(LANG(?label) IN ("en","de"))
}}"""
        for x in query(q):
            qq=qid(x.get("person",""));lab=x.get("label","")
            if qq and lab:labels[qq].add(lab)
    key_to_qids=defaultdict(set)
    for q in qids:
        for lab in labels[q]:
            k=name_key(lab)
            if k:key_to_qids[k].add(q)
            toks=k.split()
            if len(toks)>=3:key_to_qids[" ".join([toks[0],toks[-1]])].add(q)

    mapped=[]
    unique_qids=set()
    for r in roster:
        keys=roster_keys(r);cand=set()
        for k in keys:cand|=key_to_qids.get(k,set())
        # Require at least one full-name key match when possible; first-last-only can only supplement.
        full=[k for k in keys if len(k.split())>=2 and k==name_key(re.sub(r"\([^)]*$","",r.get("display_name","")))]
        strong=set()
        for k in full:strong|=key_to_qids.get(k,set())
        if strong:cand=strong
        basis="unique_membership_scoped_exact_name" if len(cand)==1 else ("ambiguous_membership_scoped_name" if len(cand)>1 else "unmatched")
        qq=next(iter(cand)) if len(cand)==1 else ""
        if qq:unique_qids.add(qq)
        mapped.append({
          "member_slug":r["member_slug"],"display_name":r["display_name"],"class":r["class"],"section":r["section"],"election_year":r["election_year"],
          "final_exact_dob":r["final_exact_dob"],"wikidata_qid":qq,"qid_match_basis":basis,"qid_candidate_count":len(cand),
          "qid_candidates":"|".join(sorted(cand)),
          "matched_labels":"|".join(sorted(labels[qq])) if qq else "",
          "bazi_variables_computed":0
        })
    # Metadata only for unique identity matches.
    meta=defaultdict(lambda:defaultdict(set))
    uq=sorted(unique_qids)
    for batch in chunks(uq,100):
        values=" ".join("wd:"+q for q in batch)
        opts="\n".join(f"OPTIONAL {{ ?person wdt:{p} ?{name} . }}" for p,name in PROPS.items())
        sel=" ".join("?"+name for name in PROPS.values())
        q=f"""PREFIX wd:<http://www.wikidata.org/entity/>
PREFIX wdt:<http://www.wikidata.org/prop/direct/>
SELECT ?person {sel} WHERE {{
 VALUES ?person {{ {values} }}
 {opts}
}}"""
        for x in query(q):
            qq=qid(x.get("person",""))
            for name in PROPS.values():
                if x.get(name):meta[qq][name].add(x[name])
    birth=defaultdict(list)
    for batch in chunks(uq,120):
        values=" ".join("wd:"+q for q in batch)
        q=f"""PREFIX wd:<http://www.wikidata.org/entity/>
PREFIX p:<http://www.wikidata.org/prop/>
PREFIX psv:<http://www.wikidata.org/prop/statement/value/>
PREFIX wikibase:<http://wikiba.se/ontology#>
SELECT ?person ?dob ?precision WHERE {{
 VALUES ?person {{ {values} }}
 ?person p:P569 ?stmt .
 ?stmt psv:P569 ?value .
 ?value wikibase:timeValue ?dob ; wikibase:timePrecision ?precision .
}}"""
        for x in query(q):
            qq=qid(x.get("person",""));prec=precision_int(x.get("precision"))
            if qq and x.get("dob") and prec is not None:birth[qq].append((x["dob"],prec))
    for r in mapped:
        qq=r["wikidata_qid"]
        if not qq:continue
        for name in PROPS.values():r[name]="|".join(sorted(meta[qq][name]))
        exact=sorted({d for d,p in birth[qq] if p>=11})
        r["wikidata_exact_p569_values"]="|".join(exact)
        r["wikidata_exact_p569_count"]=len(exact)
        r["wikidata_p569_conflict"]=int(len(exact)>1)
        r["wikidata_max_birth_precision"]=max((p for _,p in birth[qq]),default="")
    for r in mapped:
        if not r.get("wikidata_qid"):
            for name in PROPS.values():r[name]=""
            r["wikidata_exact_p569_values"]="";r["wikidata_exact_p569_count"]=0;r["wikidata_p569_conflict"]=0;r["wikidata_max_birth_precision"]=""
    fields=list(mapped[0].keys())
    mp=OUT/"leopoldina_wikidata_identity_map_v1.csv";write_csv(mp,mapped,fields)
    unique=[r for r in mapped if r["wikidata_qid"]]
    unresolved=[r for r in unique if not r["final_exact_dob"]]
    summary={
      "dataset":"Leopoldina Wikidata membership-scoped identity locator pilot v1",
      "wikidata_membership_property":"P463=Q543804",
      "wikidata_candidate_persons":len(qids),
      "frozen_roster_rows":len(roster),
      "unique_qid_matches":len(unique),
      "ambiguous_name_rows":sum(r["qid_match_basis"]=="ambiguous_membership_scoped_name" for r in mapped),
      "unmatched_rows":sum(r["qid_match_basis"]=="unmatched" for r in mapped),
      "unique_qid_unresolved_dob_rows":len(unresolved),
      "unresolved_with_exact_p569_locator":sum(int(r["wikidata_exact_p569_count"])==1 for r in unresolved),
      "unresolved_with_p569_conflict":sum(int(r["wikidata_p569_conflict"])==1 for r in unresolved),
      "unresolved_with_official_homepage":sum(bool(r["official_homepage"]) for r in unresolved),
      "unresolved_with_viaf":sum(bool(r["viaf_id"]) for r in unresolved),
      "unresolved_with_gnd":sum(bool(r["gnd_id"]) for r in unresolved),
      "unresolved_with_loc":sum(bool(r["loc_id"]) for r in unresolved),
      "unresolved_with_bnf":sum(bool(r["bnf_id"]) for r in unresolved),
      "unresolved_with_idref":sum(bool(r["idref_id"]) for r in unresolved),
      "unresolved_with_isni":sum(bool(r["isni_id"]) for r in unresolved),
      "policy":"Identity/locator diagnostic only. Wikidata P569 and library authority values are not final DOB evidence. Use P569 references, official homepages/CVs, and independent non-library provenance for acceptance.",
      "bazi_variables_computed":0
    }
    (OUT/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
