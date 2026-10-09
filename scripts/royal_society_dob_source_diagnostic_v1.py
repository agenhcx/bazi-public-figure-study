#!/usr/bin/env python3
from __future__ import annotations

import csv, datetime as dt, hashlib, html, json, re, time, urllib.request
from pathlib import Path

ROSTER=Path("data/royal_society_roster_freeze_v1/royal_society_fellows_roster_freeze_v1.csv")
MANIFEST=Path("data/royal_society_roster_freeze_v1/manifest.json")
OUT=Path("data/royal_society_dob_source_diagnostic_v1")
UA="bazi-public-figure-study/1.0 (Royal Society official DOB source diagnostic; no BaZi computation)"

BIRTH_TERMS=re.compile(r"(?i)\b(date of birth|birth date|born|birth)\b")
DATE_PATTERNS=[
    re.compile(r"\b(?:0?[1-9]|[12]\d|3[01])\s+(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+(?:16|17|18|19|20)\d{2}\b",re.I),
    re.compile(r"\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+(?:0?[1-9]|[12]\d|3[01]),?\s+(?:16|17|18|19|20)\d{2}\b",re.I),
    re.compile(r"\b(?:16|17|18|19|20)\d{2}[-/](?:0?[1-9]|1[0-2])[-/](?:0?[1-9]|[12]\d|3[01])\b"),
]

def sha256(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1<<20),b""): h.update(chunk)
    return h.hexdigest()

def strip_html(raw: bytes) -> str:
    s=raw.decode("utf-8",errors="replace")
    s=re.sub(r"(?is)<script\b.*?</script>"," ",s)
    s=re.sub(r"(?is)<style\b.*?</style>"," ",s)
    s=re.sub(r"(?s)<[^>]+>"," ",s)
    s=html.unescape(s)
    return re.sub(r"\s+"," ",s).strip()

def fetch(url: str, retries=5):
    last=None
    for attempt in range(retries):
        try:
            req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"text/html,application/xhtml+xml"})
            with urllib.request.urlopen(req,timeout=90) as r:
                return r.read(),r.geturl(),r.status,dict(r.headers)
        except Exception as e:
            last=e
            if attempt+1<retries: time.sleep(min(20,2**attempt))
    raise RuntimeError(f"fetch failed after {retries}: {url}: {last}")

def evenly_spaced(rows, n):
    if len(rows)<=n:return list(rows)
    if n<=1:return [rows[0]]
    idx=[]
    for i in range(n):
        j=round(i*(len(rows)-1)/(n-1))
        if j not in idx: idx.append(j)
    return [rows[j] for j in idx]

def snippets(text: str, limit=6):
    out=[]
    for m in BIRTH_TERMS.finditer(text):
        a=max(0,m.start()-140); b=min(len(text),m.end()+220)
        sn=text[a:b]
        sn=re.sub(r"\s+"," ",sn).strip()
        if sn not in out: out.append(sn)
        if len(out)>=limit:break
    return out

def dates(text: str, limit=12):
    vals=[]
    for pat in DATE_PATTERNS:
        for m in pat.finditer(text):
            x=m.group(0)
            if x not in vals: vals.append(x)
            if len(vals)>=limit:return vals
    return vals

def diagnose(row):
    rec={
      "cohort_key":row["cohort_key"],
      "status_at_source":row["status_at_source"],
      "display_name":row["display_name"],
      "election_year":row["election_year"],
      "source_url":row["source_url"],
    }
    try:
        raw,final,status,headers=fetch(row["source_url"])
        text=strip_html(raw)
        rec.update({
          "http_status":status,
          "final_url":final,
          "bytes":len(raw),
          "content_type":headers.get("Content-Type",""),
          "birth_term_hits":len(BIRTH_TERMS.findall(text)),
          "candidate_date_strings":dates(text),
          "birth_snippets":snippets(text),
        })
    except Exception as e:
        rec["error"]=repr(e)
    return rec

def main():
    if not ROSTER.exists() or not MANIFEST.exists():
        raise RuntimeError("Frozen Royal Society roster artifact has not been materialized into data/royal_society_roster_freeze_v1")
    manifest=json.loads(MANIFEST.read_text(encoding="utf-8"))
    if manifest.get("total")!=8669 or manifest.get("roster_csv_sha256")!=sha256(ROSTER):
        raise RuntimeError("Frozen roster invariant/hash mismatch")

    with ROSTER.open("r",encoding="utf-8-sig",newline="") as f:
        rows=list(csv.DictReader(f))
    past=[r for r in rows if r["status_at_source"]=="past"]
    current=[r for r in rows if r["status_at_source"]=="current"]
    if len(past)!=7099 or len(current)!=1570:
        raise RuntimeError("Frozen status counts do not match expected 7099 past + 1570 current")

    sample=evenly_spaced(sorted(past,key=lambda r:r["cohort_key"]),24)+evenly_spaced(sorted(current,key=lambda r:r["cohort_key"]),24)
    OUT.mkdir(parents=True,exist_ok=True)
    records=[]
    for i,row in enumerate(sample,1):
        rec=diagnose(row); records.append(rec)
        print(f"{i}/{len(sample)} {row['status_at_source']} {row['display_name']}: status={rec.get('http_status')} birth_hits={rec.get('birth_term_hits',0)}")
        time.sleep(0.12)

    for rec in records:
        p=OUT/f"{rec['cohort_key']}.json"
        p.write_text(json.dumps(rec,ensure_ascii=False,indent=2),encoding="utf-8")

    by_status={}
    for st in ("past","current"):
        rr=[r for r in records if r["status_at_source"]==st]
        by_status[st]={
          "sample_n":len(rr),
          "http_200":sum(r.get("http_status")==200 for r in rr),
          "birth_term_positive":sum((r.get("birth_term_hits") or 0)>0 for r in rr),
          "candidate_date_positive":sum(bool(r.get("candidate_date_strings")) for r in rr),
          "errors":sum("error" in r for r in rr),
        }

    summary={
      "dataset":"Royal Society official DOB source diagnostic v1",
      "created_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
      "roster_total":len(rows),
      "frozen_roster_sha256":sha256(ROSTER),
      "sample_method":"24 evenly spaced past Fellows + 24 evenly spaced current Fellows by frozen cohort_key; deterministic diagnostic only",
      "sample_total":len(records),
      "by_status":by_status,
      "dob_values_accepted":0,
      "bazi_variables_computed":0,
      "purpose":"Assess whether official Royal Society record/profile pages expose exact birth-date information before designing bulk DOB acquisition."
    }
    (OUT/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
