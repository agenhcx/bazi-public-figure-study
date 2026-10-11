#!/usr/bin/env python3
from __future__ import annotations
import csv,html,os,re,time,unicodedata,urllib.request,urllib.parse
from datetime import date
from pathlib import Path
from pypdf import PdfReader

YEAR=int(os.environ["STRUCTURE_YEAR"])
ROSTER=Path("data/leopoldina_roster_freeze_v1/leopoldina_science_core_roster_freeze_v1.csv")
ACCEPTED=Path("data/leopoldina_official_static_dob_v1/accepted_exact_dob_static_volumes_v1.csv")
OUT=Path("data/leopoldina_structure_star_dob_shard_v1")
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/155.0 Safari/537.36"
MONTHS={"januar":1,"january":1,"jan":1,"februar":2,"february":2,"feb":2,"märz":3,"maerz":3,"march":3,"mar":3,"april":4,"apr":4,"mai":5,"may":5,"juni":6,"june":6,"jun":6,"juli":7,"july":7,"jul":7,"august":8,"aug":8,"september":9,"sept":9,"sep":9,"oktober":10,"october":10,"okt":10,"oct":10,"november":11,"nov":11,"dezember":12,"december":12,"dez":12,"dec":12}
MRE="|".join(sorted((re.escape(x) for x in MONTHS),key=len,reverse=True))
NUM_STAR=re.compile(r"[*✱]\s*(\d{1,2})[./](\d{1,2})[./](\d{4})")
WORD_STAR=re.compile(rf"[*✱]\s*(\d{{1,2}})(?:st|nd|rd|th)?\.?\s+({MRE})\s+(\d{{4}})",re.I)

def read_csv(p):
    with p.open("r",encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
def norm(s):
    s=html.unescape(str(s or ""));s=unicodedata.normalize("NFKD",s);s="".join(c for c in s if not unicodedata.combining(c));s=s.lower()
    return re.sub(r"[^a-z0-9]+"," ",s).strip()
def month(s):
    s=unicodedata.normalize("NFKD",s.lower());s="".join(c for c in s if not unicodedata.combining(c));return MONTHS[s]
def fetch(url,accept="text/html,*/*",tries=4):
    err=""
    for i in range(tries):
        try:
            req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":accept,"Accept-Language":"en-US,en;q=0.9"})
            with urllib.request.urlopen(req,timeout=120) as r:return r.geturl(),r.read()
        except Exception as e:err=f"{type(e).__name__}: {e}";time.sleep(min(15,2**i))
    raise RuntimeError(f"Fetch failed {url}: {err}")
def resolve_pdf(year):
    page=f"https://www.leopoldina.org/ergebnisse-und-termine/publikationen/detail/leopoldina-struktur-und-mitglieder-{year}"
    final,b=fetch(page)
    text=b.decode("utf-8","replace")
    links=[]
    for m in re.finditer(r'<a\b([^>]*)href=["\']([^"\']+)["\']([^>]*)>(.*?)</a>',text,re.I|re.S):
        u=urllib.parse.urljoin(final,html.unescape(m.group(2)))
        label=re.sub(r"\s+"," ",html.unescape(re.sub(r"<[^>]+>"," ",m.group(4)))).strip()
        if ".pdf" in u.lower() and re.search(r"publikation|publication|pdf",label,re.I):links.append((label,u))
    # Current detail pages should have exactly one explicit publication PDF; prefer label.
    pref=[u for label,u in links if re.search(r"zur publikation|download publication",label,re.I)]
    if pref:return pref[0],page
    if links:return links[0][1],page
    return "",page
def parse_star_dates(line):
    out=[]
    for m in NUM_STAR.finditer(line):
        try:d,mo,y=map(int,m.groups());iso=date(y,mo,d).isoformat()
        except Exception:continue
        out.append((iso,m.group(0)))
    for m in WORD_STAR.finditer(line):
        try:d=int(m.group(1));mo=month(m.group(2));y=int(m.group(3));iso=date(y,mo,d).isoformat()
        except Exception:continue
        out.append((iso,m.group(0)))
    return out
def tokens(slug):
    xs=[norm(x) for x in slug.split("-") if len(norm(x))>1]
    return xs[0],xs[-1] if len(xs)>=2 else ("","")
def main():
    OUT.mkdir(parents=True,exist_ok=True)
    accepted={r["member_slug"] for r in read_csv(ACCEPTED)}
    roster=[r for r in read_csv(ROSTER) if r["member_slug"] not in accepted]
    idx={}
    for r in roster:
        ts=[norm(x) for x in r["member_slug"].split("-") if len(norm(x))>1]
        if len(ts)<2:continue
        idx.setdefault(ts[-1],[]).append((ts[0],r))
    pdf_url,locator=resolve_pdf(YEAR)
    source_status="available";source_error="";rows=[]
    if not pdf_url:
        source_status="no_verified_pdf_locator"
    else:
        try:
            _,b=fetch(pdf_url,"application/pdf,*/*")
            if not b.startswith(b"%PDF"):raise RuntimeError(f"non-PDF response bytes={len(b)}")
            pdf=OUT/f"structure_{YEAR}.pdf";pdf.write_bytes(b)
            reader=PdfReader(str(pdf))
            for pno,p in enumerate(reader.pages,1):
                text=p.extract_text() or ""; lines=text.splitlines()
                for i,line in enumerate(lines):
                    ds=parse_star_dates(line)
                    if not ds:continue
                    window=" ".join(lines[max(0,i-2):min(len(lines),i+3)])
                    nw=norm(window)
                    matched=[]
                    for surname,cands in idx.items():
                        if surname not in nw:continue
                        for first,r in cands:
                            if first in nw:matched.append(r)
                    # Require one frozen member identity in the local line window.
                    uniq={r["member_slug"]:r for r in matched}
                    if len(uniq)!=1:continue
                    r=next(iter(uniq.values()))
                    for iso,raw in ds:
                        age=int(r["election_year"])-int(iso[:4])
                        if 18<=age<=110:
                            rows.append({"member_slug":r["member_slug"],"display_name":r["display_name"],"class":r["class"],"section":r["section"],"election_year":r["election_year"],"deceased_marker":r["deceased_marker"],"candidate_dob":iso,"raw_birth_marker":raw,"structure_year":YEAR,"pdf_page":pno,"context":window[:600],"pdf_url":pdf_url,"publication_locator":locator,"source_status":"available","bazi_variables_computed":0})
        except Exception as e:
            source_status="transport_unavailable";source_error=f"{type(e).__name__}: {e}"
    fields=["member_slug","display_name","class","section","election_year","deceased_marker","candidate_dob","raw_birth_marker","structure_year","pdf_page","context","pdf_url","publication_locator","source_status","bazi_variables_computed"]
    cp=OUT/f"candidates_{YEAR}.csv"
    with cp.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
    summary={"structure_year":YEAR,"pdf_url":pdf_url,"source_status":source_status,"source_error":source_error,"candidate_rows":len(rows),"candidate_members":len({r["member_slug"] for r in rows}),"bazi_variables_computed":0}
    (OUT/f"summary_{YEAR}.json").write_text(__import__("json").dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(__import__("json").dumps(summary,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
