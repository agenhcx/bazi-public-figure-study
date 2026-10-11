#!/usr/bin/env python3
from __future__ import annotations
import csv,html,os,re,time,unicodedata,urllib.request,http.cookiejar
from datetime import date
from pathlib import Path

ROSTER=Path("data/leopoldina_roster_freeze_v1/leopoldina_science_core_roster_freeze_v1.csv")
ACCEPTED=Path("data/leopoldina_official_static_dob_v1/accepted_exact_dob_static_volumes_v1.csv")
OUT=Path("data/leopoldina_detail_birthphrase_shard_v1")
SHARD_INDEX=int(os.environ["SHARD_INDEX"]); SHARD_COUNT=int(os.environ.get("SHARD_COUNT","16"))
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/155.0 Safari/537.36"
BASE="https://www.leopoldina.org/en/members/member-list/"
JAR=http.cookiejar.CookieJar(); OPENER=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(JAR))

MONTHS={
 "januar":1,"january":1,"jan":1,"februar":2,"february":2,"feb":2,
 "märz":3,"maerz":3,"march":3,"mar":3,"april":4,"apr":4,"mai":5,"may":5,
 "juni":6,"june":6,"jun":6,"juli":7,"july":7,"jul":7,"august":8,"aug":8,
 "september":9,"sept":9,"sep":9,"oktober":10,"october":10,"okt":10,"oct":10,
 "november":11,"nov":11,"dezember":12,"december":12,"dez":12,"dec":12
}
MRE="|".join(sorted((re.escape(x) for x in MONTHS),key=len,reverse=True))
WORD_DATE=re.compile(rf"(\d{{1,2}})(?:st|nd|rd|th)?\.?\s+({MRE})\s+(\d{{4}})",re.I)
NUM_DATE=re.compile(r"(?<!\d)(\d{1,2})[./-](\d{1,2})[./-](\d{4})(?!\d)")
BIRTH_WORD=re.compile(r"\b(?:geboren(?:e|er|es|en)?|geburtsdatum|born|birth date|date of birth)\b",re.I)
STAR_DATE=re.compile(r"[*✱]\s*(?:am\s+)?",re.I)

def read_csv(p):
    with p.open("r",encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
def visible_text(body):
    body=re.sub(r"<script\b.*?</script>|<style\b.*?</style>"," ",body,flags=re.I|re.S)
    return re.sub(r"\s+"," ",html.unescape(re.sub(r"<[^>]+>"," ",body))).strip()
def norm_month(s):
    s=unicodedata.normalize("NFKD",s.lower()); s="".join(c for c in s if not unicodedata.combining(c))
    return MONTHS[s]
def parse_dates(text):
    out=[]
    for m in WORD_DATE.finditer(text):
        try:d=int(m.group(1)); mo=norm_month(m.group(2)); y=int(m.group(3)); iso=date(y,mo,d).isoformat()
        except Exception:continue
        out.append((m.start(),m.end(),iso,m.group(0),"word"))
    for m in NUM_DATE.finditer(text):
        try:d,mo,y=map(int,m.groups()); iso=date(y,mo,d).isoformat()
        except Exception:continue
        out.append((m.start(),m.end(),iso,m.group(0),"numeric"))
    return sorted(out)
def fetch(url,tries=5):
    err=""
    for i in range(tries):
        try:
            h={"User-Agent":UA,"Accept":"text/html,application/xhtml+xml","Accept-Language":"en-US,en;q=0.9","Referer":BASE}
            with OPENER.open(urllib.request.Request(url,headers=h),timeout=45) as r:return r.status,r.read().decode("utf-8","replace"),""
        except Exception as e:err=f"{type(e).__name__}: {e}";time.sleep(min(12,2**i))
    return None,"",err
def classify(text,a,b):
    lo=max(0,a-140); hi=min(len(text),b+140); ctx=text[lo:hi]
    before=text[max(0,a-60):a]
    if BIRTH_WORD.search(ctx):return "explicit_birth_word",ctx
    if STAR_DATE.search(before):return "explicit_star_birth_marker",ctx
    return "",ctx

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    roster=read_csv(ROSTER); accepted={r["member_slug"] for r in read_csv(ACCEPTED)}
    targets=[r for r in roster if r["member_slug"] not in accepted]
    mine=[r for i,r in enumerate(targets) if i%SHARD_COUNT==SHARD_INDEX]
    rows=[]; errors=[]
    # establish session
    fetch(BASE)
    for n,r in enumerate(mine,1):
        st,body,err=fetch(r["detail_url"])
        if st!=200 or err:
            errors.append({"member_slug":r["member_slug"],"display_name":r["display_name"],"detail_url":r["detail_url"],"http_status":st or "","error":err})
            continue
        txt=visible_text(body)
        hits=[]
        for a,b,iso,raw,fmt in parse_dates(txt):
            age=int(r["election_year"])-int(iso[:4])
            if age<18 or age>110:continue
            cls,ctx=classify(txt,a,b)
            if cls:
                hits.append((iso,raw,fmt,cls,ctx))
        # dedupe exact iso+class; preserve shortest useful context
        seen=set()
        for iso,raw,fmt,cls,ctx in hits:
            k=(iso,cls)
            if k in seen:continue
            seen.add(k)
            rows.append({
              "member_slug":r["member_slug"],"display_name":r["display_name"],"class":r["class"],"section":r["section"],
              "election_year":r["election_year"],"deceased_marker":r["deceased_marker"],
              "candidate_dob":iso,"pattern_class":cls,"date_format":fmt,"raw_date":raw,
              "context":ctx[:500],"detail_url":r["detail_url"],"http_status":st,"bazi_variables_computed":0
            })
        if n%25==0:print(f"shard={SHARD_INDEX} {n}/{len(mine)} candidates={len(rows)} errors={len(errors)}")
        time.sleep(.05)
    fields=["member_slug","display_name","class","section","election_year","deceased_marker","candidate_dob","pattern_class","date_format","raw_date","context","detail_url","http_status","bazi_variables_computed"]
    cp=OUT/f"candidates_s{SHARD_INDEX}.csv"
    with cp.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
    ep=OUT/f"errors_s{SHARD_INDEX}.csv"
    with ep.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=["member_slug","display_name","detail_url","http_status","error"]);w.writeheader();w.writerows(errors)
    summary={"shard_index":SHARD_INDEX,"targets":len(mine),"candidate_rows":len(rows),"candidate_members":len({r["member_slug"] for r in rows}),"http_errors":len(errors),"bazi_variables_computed":0}
    (OUT/f"summary_s{SHARD_INDEX}.json").write_text(__import__("json").dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(__import__("json").dumps(summary,ensure_ascii=False,indent=2))

if __name__=="__main__":main()
