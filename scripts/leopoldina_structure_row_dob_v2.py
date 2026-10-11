#!/usr/bin/env python3
from __future__ import annotations
import csv,html,os,re,time,unicodedata,urllib.request,urllib.parse
from datetime import date
from pathlib import Path
from pypdf import PdfReader

YEAR=int(os.environ["STRUCTURE_YEAR"])
ROSTER=Path("data/leopoldina_roster_freeze_v1/leopoldina_science_core_roster_freeze_v1.csv")
ACCEPTED=Path("data/leopoldina_official_static_dob_v1/accepted_exact_dob_static_volumes_v1.csv")
OUT=Path("data/leopoldina_structure_row_dob_shard_v2")
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/155.0 Safari/537.36"
MONTHS={"januar":1,"january":1,"jan":1,"februar":2,"february":2,"feb":2,"märz":3,"maerz":3,"march":3,"mar":3,"april":4,"apr":4,"mai":5,"may":5,"juni":6,"june":6,"jun":6,"juli":7,"july":7,"jul":7,"august":8,"aug":8,"september":9,"sept":9,"sep":9,"oktober":10,"october":10,"okt":10,"oct":10,"november":11,"nov":11,"dezember":12,"december":12,"dez":12,"dec":12}
MRE="|".join(sorted((re.escape(x) for x in MONTHS),key=len,reverse=True))
NUM_STAR=re.compile(r"[*✱]\s*(\d{1,2})[./](\d{1,2})[./](\d{4})")
WORD_STAR=re.compile(rf"[*✱]\s*(\d{{1,2}})(?:st|nd|rd|th)?\.?\s+({MRE})\s+(\d{{4}})",re.I)

def read_csv(p):
    with p.open("r",encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
def fold(s):
    out=[]
    for ch in html.unescape(str(s or "")):
        for c in unicodedata.normalize("NFKD",ch):
            if unicodedata.combining(c):continue
            if c.isalnum():out.append(c.lower())
            elif out and out[-1]!=" ":out.append(" ")
    return re.sub(r"\s+"," ","".join(out)).strip()
def fold_map(s):
    out=[];mp=[];last_space=False
    for i,ch in enumerate(s):
        emitted=False
        for c in unicodedata.normalize("NFKD",ch):
            if unicodedata.combining(c):continue
            if c.isalnum():
                out.append(c.lower());mp.append(i);last_space=False;emitted=True
            else:
                if out and not last_space:out.append(" ");mp.append(i);last_space=True
        if not emitted and ch.isspace() and out and not last_space:
            out.append(" ");mp.append(i);last_space=True
    return "".join(out),mp
def month(s):
    s=fold(s);return MONTHS[s]
def parse_first_star(s):
    hits=[]
    for m in NUM_STAR.finditer(s):
        try:d,mo,y=map(int,m.groups());iso=date(y,mo,d).isoformat()
        except Exception:continue
        hits.append((m.start(),iso,m.group(0)))
    for m in WORD_STAR.finditer(s):
        try:d=int(m.group(1));mo=month(m.group(2));y=int(m.group(3));iso=date(y,mo,d).isoformat()
        except Exception:continue
        hits.append((m.start(),iso,m.group(0)))
    return min(hits,key=lambda x:x[0]) if hits else None
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
    final,b=fetch(page);text=b.decode("utf-8","replace");links=[]
    for m in re.finditer(r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',text,re.I|re.S):
        u=urllib.parse.urljoin(final,html.unescape(m.group(1)));label=re.sub(r"\s+"," ",html.unescape(re.sub(r"<[^>]+>"," ",m.group(2)))).strip()
        if ".pdf" in u.lower() and re.search(r"zur publikation|download publication",label,re.I):links.append(u)
    return (links[0] if links else ""),page
def slug_tokens(slug):
    xs=[fold(x) for x in slug.split("-") if len(fold(x))>1]
    return (xs[0],xs[-1]) if len(xs)>=2 else ("","")
def find_name_end(raw,first,last):
    f,mp=fold_map(raw)
    pats=[
      re.compile(rf"\b{re.escape(last)}\b.{{0,100}}\b{re.escape(first)}\b"),
      re.compile(rf"\b{re.escape(first)}\b.{{0,100}}\b{re.escape(last)}\b"),
    ]
    matches=[]
    for p in pats:
        for m in p.finditer(f):
            if m.end()-1 < len(mp):matches.append(mp[m.end()-1]+1)
    return min(matches) if matches else None

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    accepted={r["member_slug"] for r in read_csv(ACCEPTED)}
    roster=[r for r in read_csv(ROSTER) if r["member_slug"] not in accepted]
    pdf_url,locator=resolve_pdf(YEAR);rows=[];source_status="available";source_error=""
    if not pdf_url:source_status="no_verified_pdf_locator"
    else:
        try:
            _,b=fetch(pdf_url,"application/pdf,*/*")
            if not b.startswith(b"%PDF"):raise RuntimeError(f"non-PDF response bytes={len(b)}")
            pdf=OUT/f"structure_{YEAR}.pdf";pdf.write_bytes(b);reader=PdfReader(str(pdf))
            for pno,p in enumerate(reader.pages,1):
                raw=p.extract_text() or ""
                if "*" not in raw and "✱" not in raw:continue
                for r in roster:
                    first,last=slug_tokens(r["member_slug"])
                    if not first or last not in fold(raw):continue
                    end=find_name_end(raw,first,last)
                    if end is None:continue
                    after=raw[end:end+320]
                    hit=parse_first_star(after)
                    if not hit:continue
                    pos,iso,marker=hit
                    age=int(r["election_year"])-int(iso[:4])
                    if not 18<=age<=110:continue
                    context=raw[max(0,end-120):min(len(raw),end+pos+len(marker)+120)]
                    rows.append({"member_slug":r["member_slug"],"display_name":r["display_name"],"class":r["class"],"section":r["section"],"election_year":r["election_year"],"deceased_marker":r["deceased_marker"],"candidate_dob":iso,"raw_birth_marker":marker,"structure_year":YEAR,"pdf_page":pno,"context":re.sub(r"\s+"," ",context).strip()[:700],"pdf_url":pdf_url,"publication_locator":locator,"source_status":"available","rule":"first_starred_exact_date_after_member_name_within_320_chars","bazi_variables_computed":0})
        except Exception as e:source_status="transport_unavailable";source_error=f"{type(e).__name__}: {e}"
    # Dedupe identical evidence hits.
    uniq={}
    for r in rows:uniq[(r["member_slug"],r["candidate_dob"],r["structure_year"],r["pdf_page"])]=r
    rows=sorted(uniq.values(),key=lambda r:(r["member_slug"],r["candidate_dob"],int(r["pdf_page"])))
    fields=["member_slug","display_name","class","section","election_year","deceased_marker","candidate_dob","raw_birth_marker","structure_year","pdf_page","context","pdf_url","publication_locator","source_status","rule","bazi_variables_computed"]
    cp=OUT/f"candidates_{YEAR}.csv"
    with cp.open("w",encoding="utf-8-sig",newline="") as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
    summary={"structure_year":YEAR,"pdf_url":pdf_url,"source_status":source_status,"source_error":source_error,"candidate_rows":len(rows),"candidate_members":len({r["member_slug"] for r in rows}),"bazi_variables_computed":0}
    (OUT/f"summary_{YEAR}.json").write_text(__import__("json").dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8");print(__import__("json").dumps(summary,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
