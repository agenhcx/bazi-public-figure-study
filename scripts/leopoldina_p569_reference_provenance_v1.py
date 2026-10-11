#!/usr/bin/env python3
from __future__ import annotations
import csv, hashlib, json, re, time, urllib.error, urllib.parse, urllib.request
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlparse

ROSTER=Path("data/leopoldina_roster_freeze_v1/leopoldina_science_core_roster_freeze_v1.csv")
FREEZE=Path("data/leopoldina_roster_freeze_v1.json")
OUT=Path("data/leopoldina_p569_reference_provenance_v1")
QLEVER="https://qlever.dev/api/wikidata"
UA="bazi-public-figure-study/1.0 (Leopoldina P569 reference provenance diagnostic; no BaZi computation)"

def read_csv(p):
    with p.open("r",encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
def write_csv(p,rows,fields):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore");w.writeheader();w.writerows(rows)
def sha256(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for c in iter(lambda:f.read(1<<20),b""):h.update(c)
    return h.hexdigest()
def qlever_tsv(q,retries=6):
    body=urllib.parse.urlencode({"query":q,"action":"tsv_export"}).encode();last=None
    for a in range(retries):
        req=urllib.request.Request(QLEVER,data=body,method="POST",headers={"User-Agent":UA,"Content-Type":"application/x-www-form-urlencoded","Accept":"text/tab-separated-values"})
        try:
            with urllib.request.urlopen(req,timeout=300) as r:raw=r.read().decode("utf-8-sig")
            break
        except (urllib.error.HTTPError,urllib.error.URLError) as e:
            last=e;code=getattr(e,"code",None)
            if a+1>=retries or (code is not None and code not in {429,500,502,503,504}):raise
            time.sleep(min(30,2**a))
    else:raise RuntimeError(last)
    rr=list(csv.reader(raw.splitlines(),delimiter="\t"))
    if not rr:return []
    hs=[x.lstrip("?").strip() for x in rr[0]];out=[]
    for row in rr[1:]:
        row += [""]*(len(hs)-len(row));d={}
        for i,h in enumerate(hs):
            v=(row[i] or "").strip()
            if v.startswith("<") and v.endswith(">"):v=v[1:-1]
            elif v.startswith('"'):
                m=re.match(r'^"(.*)"(?:\^\^<[^>]+>|@[A-Za-z-]+)?$',v)
                if m:v=m.group(1)
            d[h]=v
        out.append(d)
    return out
def parse_date(v):
    m=re.search(r"([12]\d{3})-(\d{2})-(\d{2})",v or "")
    return m.group(0) if m else ""
def as_int(v):
    try:return int(float(str(v)))
    except:return None
def domain(u):
    try:return urlparse(u).netloc.lower().removeprefix("www.")
    except:return ""

def main():
    freeze=json.loads(FREEZE.read_text(encoding="utf-8"))
    roster=read_csv(ROSTER)
    if len(roster)!=2888:raise RuntimeError("Roster count mismatch")
    if freeze.get("checksums",{}).get("roster_csv_sha256")!=sha256(ROSTER):raise RuntimeError("Roster hash mismatch")
    roster_slugs={r["member_slug"] for r in roster}
    q="""
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX p: <http://www.wikidata.org/prop/>
PREFIX psv: <http://www.wikidata.org/prop/statement/value/>
PREFIX pr: <http://www.wikidata.org/prop/reference/>
PREFIX prov: <http://www.w3.org/ns/prov#>
PREFIX wikibase: <http://wikiba.se/ontology#>
SELECT ?person ?memberId ?dob ?precision ?refUrl ?statedIn WHERE {
  ?person wdt:P10299 ?memberId ;
          p:P569 ?dobStatement .
  ?dobStatement psv:P569 ?dobNode .
  ?dobNode wikibase:timeValue ?dob ;
           wikibase:timePrecision ?precision .
  OPTIONAL {
    ?dobStatement prov:wasDerivedFrom ?ref .
    OPTIONAL { ?ref pr:P854 ?refUrl . }
    OPTIONAL { ?ref pr:P248 ?statedIn . }
  }
}
"""
    raw=qlever_tsv(q)
    by=defaultdict(lambda:{"dates":set(),"urls":set(),"stated":set(),"person":set()})
    for x in raw:
        slug=(x.get("memberId") or "").strip()
        if slug not in roster_slugs:continue
        prec=as_int(x.get("precision"));dob=parse_date(x.get("dob",""))
        if not dob or prec is None or prec<11:continue
        key=(slug,dob)
        b=by[key]
        b["dates"].add((dob,prec))
        if (x.get("person") or "").strip():b["person"].add((x.get("person") or "").rsplit("/",1)[-1])
        if (x.get("refUrl") or "").strip():b["urls"].add((x.get("refUrl") or "").strip())
        if (x.get("statedIn") or "").strip():b["stated"].add((x.get("statedIn") or "").rsplit("/",1)[-1])

    # Restrict to one unique day-precision DOB per official slug.
    dates_by_slug=defaultdict(set)
    for slug,dob in by:dates_by_slug[slug].add(dob)
    eligible={slug:next(iter(ds)) for slug,ds in dates_by_slug.items() if len(ds)==1}
    roster_by_slug={r["member_slug"]:r for r in roster}
    rows=[];domains=Counter()
    for slug,dob in sorted(eligible.items()):
        b=by[(slug,dob)];urls=sorted(b["urls"]);stated=sorted(b["stated"])
        ds=sorted({domain(u) for u in urls if domain(u)})
        for d in ds:domains[d]+=1
        leop=[u for u in urls if domain(u).endswith("leopoldina.org")]
        rows.append({
          "member_slug":slug,
          "display_name":roster_by_slug[slug]["display_name"],
          "deceased_marker":roster_by_slug[slug]["deceased_marker"],
          "election_year":roster_by_slug[slug]["election_year"],
          "wikidata_qids":"|".join(sorted(b["person"])),
          "day_precision_dob":dob,
          "reference_urls":"|".join(urls),
          "reference_domains":"|".join(ds),
          "stated_in_qids":"|".join(stated),
          "has_any_reference_url":int(bool(urls)),
          "has_leopoldina_reference_url":int(bool(leop)),
          "has_stated_in":int(bool(stated)),
          "no_url_or_stated_in":int(not urls and not stated),
          "accepted_exact_dob":"",
          "bazi_variables_computed":0,
        })
    OUT.mkdir(parents=True,exist_ok=True);fields=list(rows[0].keys())
    write_csv(OUT/"p569_reference_provenance.csv",rows,fields)
    (OUT/"reference_domain_counts.csv").write_text("domain,rows\n"+"\n".join(f"{d},{n}" for d,n in domains.most_common()),encoding="utf-8")

    def stats(rr):
        return {
          "rows":len(rr),
          "has_any_reference_url":sum(int(x["has_any_reference_url"]) for x in rr),
          "has_leopoldina_reference_url":sum(int(x["has_leopoldina_reference_url"]) for x in rr),
          "has_stated_in":sum(int(x["has_stated_in"]) for x in rr),
          "no_url_or_stated_in":sum(int(x["no_url_or_stated_in"]) for x in rr),
        }
    summary={
      "dataset":"Leopoldina P10299-linked P569 reference provenance diagnostic v1",
      "frozen_roster_rows":len(roster),
      "unique_day_precision_p569_rows":len(rows),
      "overall":stats(rows),
      "by_status":{
        "deceased_marker":stats([x for x in rows if x["deceased_marker"]=="1"]),
        "no_deceased_marker":stats([x for x in rows if x["deceased_marker"]!="1"]),
      },
      "top_reference_domains":domains.most_common(30),
      "dob_values_accepted":0,
      "bazi_variables_computed":0,
      "note":"Reference inventory only. A reference URL or stated-in item is not automatically deemed independent/high-authority; this scan measures how much provenance is available for deterministic follow-up.",
    }
    (OUT/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
