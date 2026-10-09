#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,datetime as dt,hashlib,html,json,re,time,urllib.request,urllib.error
from pathlib import Path

ROSTER=Path("data/royal_society_roster_freeze_v1/royal_society_fellows_roster_freeze_v1.csv")
MANIFEST=Path("data/royal_society_roster_freeze_v1/manifest.json")
UA="bazi-public-figure-study/1.0 (Royal Society official past-Fellow exact-DOB acquisition; no BaZi computation)"

MONTHS="January|February|March|April|May|June|July|August|September|October|November|December"
EXACT_RE=re.compile(rf"^\s*(0?[1-9]|[12]\d|3[01])\s+({MONTHS})\s+((?:16|17|18|19|20)\d{{2}})\s*[\.?]?\s*$",re.I)
YEAR_RE=re.compile(r"^\s*((?:16|17|18|19|20)\d{2})\s*[\.?]?\s*$")
CIRCA_RE=re.compile(r"^\s*(?:c\.?|ca\.?|circa)\s*((?:16|17|18|19|20)\d{2})\s*[\.?]?\s*$",re.I)

STOP_LABELS=[
 "Place of death","Date of death","DatesAndPlaces","Occupation","Research field","Activity",
 "Education","Career","Membership category","Memberships","RSActivity","Relationships","Source",
 "Honours","Nationality","Date of election","Age at election","Code","Archives associated with this Fellow"
]
STOP_ALT="|".join(re.escape(x) for x in STOP_LABELS)

def sha256(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for c in iter(lambda:f.read(1<<20),b""):h.update(c)
    return h.hexdigest()

def strip_html(raw):
    s=raw.decode("utf-8",errors="replace")
    s=re.sub(r"(?is)<script\b.*?</script>"," ",s)
    s=re.sub(r"(?is)<style\b.*?</style>"," ",s)
    s=re.sub(r"(?s)<[^>]+>"," ",s)
    s=html.unescape(s)
    return re.sub(r"\s+"," ",s).strip()

def fetch(url,retries=7):
    last=None
    for a in range(retries):
        try:
            req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"text/html,application/xhtml+xml"})
            with urllib.request.urlopen(req,timeout=120) as r:
                return r.read(),r.geturl(),r.status
        except urllib.error.HTTPError as e:
            last=e
            if e.code==403 and a+1<retries:
                time.sleep(min(90,5*(2**a)));continue
            if a+1<retries:
                time.sleep(min(45,2**a));continue
            raise
        except Exception as e:
            last=e
            if a+1<retries:time.sleep(min(45,2**a))
    raise RuntimeError(f"fetch failed after {retries}: {url}: {last}")

def extract_label(text,label):
    m=re.search(re.escape(label)+rf"\s+(.{{1,120}}?)(?=\s+(?:{STOP_ALT})\b|$)",text,re.I)
    return re.sub(r"\s+"," ",m.group(1)).strip() if m else ""

def extract_lifespan_birth_year(text):
    # Prefer the catalogue's top-level Dates field, e.g. "Dates 1861 - 1949".
    m=re.search(r"\bDates\s+(?:c\.?\s*)?((?:16|17|18|19|20)\d{2})\s*[-–]",text,re.I)
    return int(m.group(1)) if m else None

def classify(raw):
    x=str(raw or "").strip()
    if not x:return "missing","",None
    m=EXACT_RE.match(x)
    if m:
        d=int(m.group(1));mon=m.group(2).title();y=int(m.group(3))
        try:
            iso=dt.datetime.strptime(f"{d} {mon} {y}","%d %B %Y").date().isoformat()
            return "exact_day",iso,y
        except ValueError:
            return "invalid_exact_candidate","",y
    m=CIRCA_RE.match(x)
    if m:return "circa_year","",int(m.group(1))
    m=YEAR_RE.match(x)
    if m:return "year_only","",int(m.group(1))
    if re.search(r"\b(?:16|17|18|19|20)\d{2}\b",x):
        return "nonstandard_or_ambiguous","",None
    return "other","",None

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--chunk-index",type=int,required=True)
    ap.add_argument("--chunk-count",type=int,required=True)
    args=ap.parse_args()
    if not (0<=args.chunk_index<args.chunk_count):raise SystemExit("bad chunk args")

    man=json.loads(MANIFEST.read_text(encoding="utf-8"))
    if man["roster_csv_sha256"]!=sha256(ROSTER) or man["total"]!=8669:
        raise RuntimeError("Frozen roster hash/invariant mismatch")

    with ROSTER.open("r",encoding="utf-8-sig",newline="") as f:
        past=[r for r in csv.DictReader(f) if r["status_at_source"]=="past"]
    if len(past)!=7099:raise RuntimeError(f"Expected 7099 past Fellows, got {len(past)}")
    past=sorted(past,key=lambda r:r["cohort_key"])
    rows=[r for i,r in enumerate(past) if i%args.chunk_count==args.chunk_index]

    out=Path(f"data/royal_society_past_dob_official_v1/chunk_{args.chunk_index:02d}_of_{args.chunk_count:02d}")
    if out.exists() and any(out.iterdir()):raise RuntimeError(f"nonempty output {out}")
    out.mkdir(parents=True,exist_ok=True)

    result=[]
    for n,r in enumerate(rows,1):
        rec={
          "cohort_key":r["cohort_key"],"record_id":r["source_id"],"display_name":r["display_name"],
          "election_year":r["election_year"],"source_url":r["source_url"],
          "dob_raw":"","dob_precision":"","dob_exact_iso":"","dob_year_from_raw":"",
          "catalogue_lifespan_birth_year":"","birth_year_consistent":"","http_status":"","final_url":"","error":""
        }
        try:
            raw,final,status=fetch(r["source_url"])
            text=strip_html(raw)
            dob_raw=extract_label(text,"Date of birth")
            precision,iso,raw_year=classify(dob_raw)
            life_year=extract_lifespan_birth_year(text)
            consistent=""
            if raw_year is not None and life_year is not None:
                consistent=int(raw_year==life_year)
            rec.update({
              "dob_raw":dob_raw,"dob_precision":precision,"dob_exact_iso":iso,
              "dob_year_from_raw":raw_year if raw_year is not None else "",
              "catalogue_lifespan_birth_year":life_year if life_year is not None else "",
              "birth_year_consistent":consistent,"http_status":status,"final_url":final,
            })
        except Exception as e:
            rec["error"]=repr(e)
        result.append(rec)
        if n%100==0 or n==len(rows):
            exact=sum(x["dob_precision"]=="exact_day" and x["birth_year_consistent"]!=0 for x in result)
            err=sum(bool(x["error"]) for x in result)
            print(f"chunk {args.chunk_index}/{args.chunk_count}: {n}/{len(rows)} exact={exact} errors={err}")
        time.sleep(0.22)

    fields=list(result[0].keys())
    p=out/"past_fellows_official_dob.csv"
    with p.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(result)

    counts={}
    for r in result:counts[r["dob_precision"]]=counts.get(r["dob_precision"],0)+1
    inconsistent=[r for r in result if r["dob_exact_iso"] and r["birth_year_consistent"]==0]
    summary={
      "dataset":"Royal Society past Fellow official exact-DOB acquisition v1",
      "chunk_index":args.chunk_index,"chunk_count":args.chunk_count,
      "rows":len(result),"http_errors":sum(bool(r["error"]) for r in result),
      "precision_counts":counts,
      "exact_day_candidates":sum(r["dob_precision"]=="exact_day" for r in result),
      "exact_day_birth_year_inconsistent":len(inconsistent),
      "accepted_exact_dob":sum(r["dob_precision"]=="exact_day" and r["birth_year_consistent"]!=0 for r in result),
      "csv_sha256":sha256(p),"bazi_variables_computed":0,
      "acceptance_rule":"Exact day-month-year parsed specifically from the official Royal Society 'Date of birth' field. If a top-level lifespan birth year is present, it must agree; inconsistent exact candidates are not accepted."
    }
    (out/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    # Network errors should be retried in a later targeted pass, not silently accepted.
    if summary["http_errors"]:
        raise SystemExit(2)

if __name__=="__main__":
    main()
