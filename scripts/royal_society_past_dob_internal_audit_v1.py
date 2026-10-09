#!/usr/bin/env python3
from __future__ import annotations
import argparse, csv, datetime as dt, html, json, re, time, urllib.request
from pathlib import Path

IN=Path("data/royal_society_past_dob_audit_inputs_v1")
BASEOUT=Path("data/royal_society_past_dob_internal_audit_v1")
UA="bazi-public-figure-study/1.0 (Royal Society DOB internal-consistency audit; no BaZi)"
MONTHS={m:i for i,m in enumerate(["January","February","March","April","May","June","July","August","September","October","November","December"],1)}

def read_csv(p):
    with p.open("r",encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))

def strip_html(raw):
    s=raw.decode("utf-8",errors="replace")
    s=re.sub(r"(?is)<script\b.*?</script>"," ",s)
    s=re.sub(r"(?is)<style\b.*?</style>"," ",s)
    s=re.sub(r"(?s)<[^>]+>"," ",s)
    s=html.unescape(s)
    return re.sub(r"\s+"," ",s).strip()

def fetch(url,retries=4):
    last=None
    for a in range(retries):
        try:
            req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"text/html,application/xhtml+xml"})
            with urllib.request.urlopen(req,timeout=45) as r:return r.read(),r.geturl(),r.status
        except Exception as e:
            last=e
            if a+1<retries:time.sleep(min(12,2**a))
    raise RuntimeError(repr(last))

STOP=["Place of birth","Place of death","Date of death","Dates","Nationality","Occupation","Research field","Activity","Education","Career","Membership category","Memberships","Date of election","Age at election","RSActivity","Relationships","Source","Code","Archives associated with this Fellow"]
STOP_ALT="|".join(re.escape(x) for x in STOP)

def field(text,label):
    m=re.search(re.escape(label)+rf"\s+(.{{1,180}}?)(?=\s+(?:{STOP_ALT})\b|$)",text,re.I)
    return re.sub(r"\s+"," ",m.group(1)).strip() if m else ""

def parse_exact(s):
    m=re.fullmatch(r"\s*(\d{1,2})\s+([A-Za-z]+)\s+((?:16|17|18|19|20)\d{2})\s*",str(s or ""))
    if not m:return None
    mon=MONTHS.get(m.group(2).title())
    if not mon:return None
    try:return dt.date(int(m.group(3)),mon,int(m.group(1)))
    except:return None

def parse_election(s):
    for fmt in ("%d/%m/%Y","%d %B %Y","%d %b %Y"):
        try:return dt.datetime.strptime(str(s).strip(),fmt).date()
        except:pass
    return None

def age_on(b,e):
    return e.year-b.year-((e.month,e.day)<(b.month,b.day))

def audit_one(kind,src):
    rec={"audit_kind":kind,"cohort_key":src["cohort_key"],"record_id":src["record_id"],"display_name":src["display_name"],"source_url":src["source_url"]}
    try:
        raw,final,status=fetch(src["source_url"]); text=strip_html(raw)
        dob=field(text,"Date of birth"); election=field(text,"Date of election"); age=field(text,"Age at election")
        dates=field(text,"Dates"); auth=field(text,"Authorised form of name")
        b=parse_exact(dob); e=parse_election(election); calc=age_on(b,e) if b and e else None
        ma=re.search(r"\b(\d{1,3})\b",age); page_age=int(ma.group(1)) if ma else None
        rec.update({
          "http_status":status,"final_url":final,"authorised_name":auth,"dates_field":dates,
          "date_of_birth":dob,"date_of_election":election,"age_at_election_field":age,
          "calculated_age_from_exact_dob":"" if calc is None else calc,
          "page_age_numeric":"" if page_age is None else page_age,
          "age_supports_exact_dob":"" if calc is None or page_age is None else int(calc==page_age),
          "retry_exact_iso":"" if not b else b.isoformat(),"error":""
        })
    except Exception as ex:
        rec["error"]=repr(ex)
    return rec

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--shard-index",type=int,required=True)
    ap.add_argument("--shard-count",type=int,required=True)
    a=ap.parse_args()
    if not (0<=a.shard_index<a.shard_count):raise SystemExit("bad shard args")

    conflicts=read_csv(next(IN.rglob("exact_dob_birthyear_conflict_review_v1.csv")))
    errors=read_csv(next(IN.rglob("http_error_retry_queue_v1.csv")))
    if len(conflicts)!=17 or len(errors)!=4:
        raise RuntimeError(f"Expected 17 conflicts + 4 errors, got {len(conflicts)} + {len(errors)}")

    all_items=[("conflict",x) for x in conflicts]+[("http_retry",x) for x in errors]
    items=[item for i,item in enumerate(all_items) if i%a.shard_count==a.shard_index]
    out=BASEOUT/f"shard_{a.shard_index:02d}_of_{a.shard_count:02d}"
    out.mkdir(parents=True,exist_ok=True)
    rows=[]
    for i,(kind,src) in enumerate(items,1):
        r=audit_one(kind,src);rows.append(r)
        print(f"shard {a.shard_index}: {i}/{len(items)} {kind} {src['display_name']} status={r.get('http_status')} exact={bool(r.get('retry_exact_iso'))} age_support={r.get('age_supports_exact_dob')} err={bool(r.get('error'))}")
        time.sleep(0.12)

    fields=sorted({k for r in rows for k in r})
    p=out/"internal_audit.csv"
    with p.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
    c=[r for r in rows if r["audit_kind"]=="conflict"];q=[r for r in rows if r["audit_kind"]=="http_retry"]
    summary={
      "dataset":"Royal Society DOB internal-consistency + HTTP retry audit v1",
      "shard_index":a.shard_index,"shard_count":a.shard_count,"rows":len(rows),
      "conflict_rows":len(c),
      "conflict_age_check_available":sum(r.get("age_supports_exact_dob","")!="" for r in c),
      "conflict_age_supports_exact":sum(r.get("age_supports_exact_dob")==1 for r in c),
      "conflict_age_contradicts_exact":sum(r.get("age_supports_exact_dob")==0 for r in c),
      "http_retry_rows":len(q),"http_retry_success":sum(r.get("http_status")==200 for r in q),
      "http_retry_exact_dob":sum(bool(r.get("retry_exact_iso")) for r in q),
      "remaining_http_errors":sum(bool(r.get("error")) for r in q),
      "bazi_variables_computed":0
    }
    (out/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
