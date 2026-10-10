#!/usr/bin/env python3
from __future__ import annotations
import csv,json,os,re,time,urllib.request
from pathlib import Path
from html import unescape

IN=Path("data/leopoldina_detail_input_v1/leopoldina_science_classes_member_urls_through_2025_v1.csv")
OUT=Path("data/leopoldina_detail_shard_v1")
SHARD_INDEX=int(os.environ["SHARD_INDEX"])
SHARD_COUNT=int(os.environ.get("SHARD_COUNT","12"))
UA="Mozilla/5.0 (compatible; bazi-public-figure-study/1.0; reproducibility research)"

def read_csv(p):
    with p.open("r",encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
def clean(s):
    return re.sub(r"\s+"," ",unescape(re.sub(r"<[^>]+>"," ",s or ""))).strip()
def field(html,label):
    m=re.search(r'<strong[^>]*>\s*'+re.escape(label)+r'\s*</strong>\s*<span[^>]*>(.*?)</span>',html,re.I|re.S)
    return clean(m.group(1)) if m else ""
def fetch(url,tries=5):
    err=""
    for i in range(tries):
        try:
            req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"text/html,application/xhtml+xml","Accept-Language":"en-US,en;q=0.9"})
            with urllib.request.urlopen(req,timeout=60) as r:
                return r.status,r.geturl(),r.read().decode("utf-8","replace"),""
        except Exception as e:
            err=f"{type(e).__name__}: {e}"; time.sleep(min(16,2**i))
    return "",url,"",err
def main():
    OUT.mkdir(parents=True,exist_ok=True)
    rows=read_csv(IN)
    if len(rows)!=2888 or len({r["detail_url"] for r in rows})!=2888:
        raise RuntimeError(f"Input invariant failed rows={len(rows)} unique={len({r['detail_url'] for r in rows})}")
    assigned=[r for i,r in enumerate(rows) if i%SHARD_COUNT==SHARD_INDEX]
    out=[]
    for n,r in enumerate(assigned,1):
        status,final_url,html,error=fetch(r["detail_url"])
        h1m=re.search(r"<h1[^>]*>(.*?)</h1>",html,re.I|re.S) if html else None
        h1=clean(h1m.group(1)) if h1m else ""
        deceased=int(bool(re.search(r"[✝†]",h1)))
        display_name=re.sub(r"\s*\([^)]*[✝†][^)]*\)\s*$","",h1).strip()
        section=field(html,"Section") if html else ""
        location=field(html,"Location") if html else ""
        election=field(html,"Election year") if html else ""
        ok=int(str(status)=="200" and bool(display_name) and bool(section) and election==str(r["election_year"]))
        out.append({
          **r,
          "http_status":status,
          "final_url":final_url,
          "display_name":display_name,
          "deceased":deceased,
          "section":section,
          "location":location,
          "detail_election_year":election,
          "election_year_matches_inventory":int(election==str(r["election_year"])),
          "parse_ok":ok,
          "error":error
        })
        if n%25==0:print(f"shard={SHARD_INDEX} {n}/{len(assigned)} ok={sum(x['parse_ok'] for x in out)}")
        time.sleep(.08)
    p=OUT/f"detail_shard_{SHARD_INDEX}.csv"
    fields=list(out[0].keys())
    with p.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(out)
    bad=[x for x in out if not x["parse_ok"]]
    summary={"dataset":"Leopoldina official detail-page roster shard v1","shard_index":SHARD_INDEX,"shard_count":SHARD_COUNT,"input_rows":len(assigned),"parsed_ok":len(out)-len(bad),"failed":len(bad),"failed_urls":[x["detail_url"] for x in bad[:30]],"dob_lookup_performed":0,"bazi_variables_computed":0}
    (OUT/f"summary_{SHARD_INDEX}.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    if bad: raise RuntimeError(f"Shard {SHARD_INDEX} has {len(bad)} failed detail rows")
if __name__=="__main__":main()
