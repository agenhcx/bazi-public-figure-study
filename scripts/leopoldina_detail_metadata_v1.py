#!/usr/bin/env python3
from __future__ import annotations
import csv,html,os,re,time,urllib.request,http.cookiejar
from pathlib import Path

IN=Path("data/leopoldina_roster_url_inventory_v1/leopoldina_science_classes_member_urls_through_2025_v1.csv")
OUT=Path("data/leopoldina_detail_metadata_shard_v1")
SHARD_INDEX=int(os.environ["SHARD_INDEX"])
SHARD_COUNT=int(os.environ.get("SHARD_COUNT","16"))
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/155.0 Safari/537.36"
BASE="https://www.leopoldina.org/en/members/member-list/"
JAR=http.cookiejar.CookieJar()
OPENER=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(JAR))

def read_csv(p):
    with p.open("r",encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))

def clean(s):
    return re.sub(r"\s+"," ",html.unescape(re.sub(r"<[^>]+>"," ",s))).strip()

def fetch(url,tries=6):
    err=""
    for i in range(tries):
        try:
            h={"User-Agent":UA,"Accept":"text/html,application/xhtml+xml","Accept-Language":"en-US,en;q=0.9","Referer":BASE}
            with OPENER.open(urllib.request.Request(url,headers=h),timeout=60) as r:
                return r.status,r.geturl(),r.read().decode("utf-8","replace"),""
        except Exception as e:
            err=f"{type(e).__name__}: {e}"
            time.sleep(min(20,2**i))
    return None,url,"",err

def field(body,label):
    m=re.search(rf'<strong[^>]*>\s*{re.escape(label)}\s*</strong>\s*<span[^>]*>(.*?)</span>',body,re.I|re.S)
    return clean(m.group(1)) if m else ""

def heading(body):
    m=re.search(r"<h1\b[^>]*>(.*?)</h1>",body,re.I|re.S)
    return clean(m.group(1)) if m else ""

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    rows=read_csv(IN)
    if len(rows)!=2888: raise RuntimeError(f"Expected frozen URL inventory 2888, got {len(rows)}")
    mine=[r for i,r in enumerate(rows) if i%SHARD_COUNT==SHARD_INDEX]
    # establish site session
    fetch(BASE)
    out=[]
    for n,r in enumerate(mine,1):
        status,final_url,body,error=fetch(r["detail_url"])
        h1=heading(body) if body else ""
        sec=field(body,"Section") if body else ""
        loc=field(body,"Location") if body else ""
        ey=field(body,"Election year") if body else ""
        deceased=int(("✝" in h1) or ("†" in h1))
        display_name=re.sub(r"\s*[✝†].*$","",h1).strip()
        out.append({
          **r,
          "http_status":status or "",
          "final_url":final_url,
          "display_name":display_name,
          "h1_raw":h1,
          "deceased_marker":deceased,
          "section":sec,
          "location":loc,
          "detail_election_year":ey,
          "election_year_matches_inventory":int(str(ey).strip()==str(r["election_year"]).strip()) if ey else 0,
          "heading_contains_honorary":int(bool(re.search(r"\bhonorary\b",h1,re.I))),
          "error":error
        })
        if n%25==0: print(f"shard={SHARD_INDEX} {n}/{len(mine)}")
        time.sleep(.08)
    fields=list(out[0].keys())
    p=OUT/f"detail_metadata_s{SHARD_INDEX}.csv"
    with p.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(out)
    bad=[r for r in out if r["error"] or str(r["http_status"])!="200" or not r["display_name"] or not r["section"] or not r["detail_election_year"] or r["election_year_matches_inventory"]!=1]
    summary={"shard_index":SHARD_INDEX,"shard_count":SHARD_COUNT,"rows":len(out),"http_200":sum(str(r["http_status"])=="200" for r in out),"deceased_marker":sum(int(r["deceased_marker"]) for r in out),"field_complete_and_year_match":len(out)-len(bad),"bad_rows":len(bad),"bazi_variables_computed":0}
    (OUT/f"summary_s{SHARD_INDEX}.json").write_text(__import__("json").dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(__import__("json").dumps(summary,ensure_ascii=False,indent=2))
    if bad:
        raise RuntimeError(f"Shard {SHARD_INDEX} has {len(bad)} bad rows; first={bad[:3]}")

if __name__=="__main__":main()
