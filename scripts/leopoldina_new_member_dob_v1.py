#!/usr/bin/env python3
from __future__ import annotations
import csv,html,os,re,time,unicodedata,urllib.request,urllib.parse
from pathlib import Path
from pypdf import PdfReader

YEAR=int(os.environ["ELECTION_YEAR"])
ROSTER=Path("data/leopoldina_roster_freeze_v1/leopoldina_science_core_roster_freeze_v1.csv")
OUT=Path("data/leopoldina_new_member_dob_shard_v1")
UA="Mozilla/5.0 (compatible; bazi-public-figure-study/1.0; reproducibility research)"
DIRECT_2009="https://levana.leopoldina.org/servlets/MCRFileNodeServlet/leopoldina_derivate_00308/2009_Leopoldina_Neugewaehlte_Mitglieder.pdf"
MONTH_MAP={
 "january":1,"jan":1,"januar":1,
 "february":2,"feb":2,"februar":2,
 "march":3,"mar":3,"märz":3,"maerz":3,
 "april":4,"apr":4,
 "may":5,"mai":5,
 "june":6,"jun":6,"juni":6,
 "july":7,"jul":7,"juli":7,
 "august":8,"aug":8,
 "september":9,"sep":9,"sept":9,
 "october":10,"oct":10,"oktober":10,"okt":10,
 "november":11,"nov":11,
 "december":12,"dec":12,"dezember":12,"dez":12,
}
MONTH_RE="|".join(sorted((re.escape(k) for k in MONTH_MAP),key=len,reverse=True))
NUM_RE=re.compile(r"\*\s*(\d{1,2})\s*\.\s*(\d{1,2})\s*\.\s*(\d{4})")
NAME_RE=re.compile(rf"\*\s*(\d{{1,2}})(?:st|nd|rd|th)?\s*\.?\s*({MONTH_RE})\s+(\d{{4}})",re.I)

def read_csv(p):
    with p.open("r",encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))

def norm(s):
    s=html.unescape(str(s or ""))
    s=unicodedata.normalize("NFKD",s)
    s="".join(c for c in s if not unicodedata.combining(c))
    s=s.lower()
    return re.sub(r"[^a-z0-9]+"," ",s).strip()

def fetch(url,accept="text/html,*/*",tries=5):
    err=""
    for i in range(tries):
        try:
            req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":accept})
            with urllib.request.urlopen(req,timeout=120) as r:
                return r.geturl(),r.read()
        except Exception as e:
            err=f"{type(e).__name__}: {e}";time.sleep(min(16,2**i))
    raise RuntimeError(f"Fetch failed {url}: {err}")

def discover_pdf(year):
    if year==2009:return DIRECT_2009,"direct_known_official"
    page=f"https://www.leopoldina.org/ergebnisse-und-termine/publikationen/detail/neugewaehlte-mitglieder-{year}"
    final,b=fetch(page)
    txt=b.decode("utf-8","replace")
    hrefs=[html.unescape(x) for x in re.findall(r'href=["\']([^"\']+\.pdf(?:\?[^"\']*)?)["\']',txt,re.I)]
    hrefs=[urllib.parse.urljoin(final,x) for x in hrefs]
    if not hrefs:raise RuntimeError(f"No PDF href discovered from {page}")
    preferred=[u for u in hrefs if re.search(r"neugewaehl|neugew[aä]hl|mitglieder",u,re.I)]
    return (preferred[0] if preferred else hrefs[0]),page

def dates(text):
    out=[]
    for m in NUM_RE.finditer(text):
        d,mo,y=map(int,m.groups())
        try:iso=f"{y:04d}-{mo:02d}-{d:02d}";__import__("datetime").date(y,mo,d)
        except Exception:continue
        out.append((iso,m.group(0)))
    for m in NAME_RE.finditer(text):
        d=int(m.group(1)); mo=MONTH_MAP[norm(m.group(2))]; y=int(m.group(3))
        try:iso=f"{y:04d}-{mo:02d}-{d:02d}";__import__("datetime").date(y,mo,d)
        except Exception:continue
        out.append((iso,m.group(0)))
    return out

def slug_tokens(slug):
    toks=[x for x in slug.lower().split("-") if x and not x.isdigit()]
    return [norm(x) for x in toks if len(norm(x))>1]

def page_is_target(text,slug):
    toks=slug_tokens(slug)
    if len(toks)<2:return False
    first,last=toks[0],toks[-1]
    # True profiles identify the member near the top of the page. Restricting
    # identity and metadata matching to the header region prevents citations
    # to other Leopoldina members later in somebody else's biography from
    # generating false multi-page DOB conflicts.
    head_raw=text[:1800]
    head=norm(head_raw)
    if not re.search(rf"\\b{re.escape(first)}\\b",head):return False
    if not re.search(rf"\\b{re.escape(last)}\\b",head):return False
    if not re.search(r"\b(section|sektion)\b",head):return False
    if not re.search(r"\b(matricula|matrikel|date of election|aufnahmedatum)\b",head):return False
    return "*" in head_raw

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    roster=[r for r in read_csv(ROSTER) if int(r["election_year"])==YEAR]
    pdf_url,locator=discover_pdf(YEAR)
    _,b=fetch(pdf_url,"application/pdf,*/*")
    if not b.startswith(b"%PDF"):raise RuntimeError(f"Not a PDF {pdf_url} bytes={len(b)}")
    pdf=OUT/f"new_members_{YEAR}.pdf";pdf.write_bytes(b)
    reader=PdfReader(str(pdf))
    pages=[p.extract_text() or "" for p in reader.pages]
    rows=[]
    for r in roster:
        matches=[]
        for i,text in enumerate(pages):
            if not page_is_target(text,r["member_slug"]):continue
            ds=dates(text[:1800])
            # Keep exact DOB-like starred dates only; old volumes use the star as birth marker.
            for iso,raw in ds:
                age=YEAR-int(iso[:4])
                if 20<=age<=100:
                    matches.append((iso,raw,i+1))
        unique=sorted({m[0] for m in matches})
        accepted=unique[0] if len(unique)==1 else ""
        support=[m for m in matches if m[0]==accepted] if accepted else matches
        rows.append({
          "member_slug":r["member_slug"],"display_name":r["display_name"],"class":r["class"],"section":r["section"],
          "election_year":YEAR,"candidate_dob":accepted,"candidate_count":len(unique),
          "raw_birth_marker":" | ".join(sorted({m[1] for m in support}))[:500],
          "pdf_page":" | ".join(str(x) for x in sorted({m[2] for m in support})),
          "pdf_url":pdf_url,"publication_locator":locator,
          "decision":"accept_official_new_member_profile_exact_dob" if accepted else ("conflict_review" if len(unique)>1 else "unresolved_no_exact_birth_marker"),
          "bazi_variables_computed":0
        })
    fields=list(rows[0].keys()) if rows else ["member_slug"]
    cp=OUT/f"dob_candidates_{YEAR}.csv"
    with cp.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
    accepted=[r for r in rows if r.get("decision")=="accept_official_new_member_profile_exact_dob"]
    conflicts=[r for r in rows if r.get("decision")=="conflict_review"]
    summary={
      "dataset":"Leopoldina official new-member exact-DOB shard v1","election_year":YEAR,
      "roster_targets":len(roster),"pdf_url":pdf_url,"pdf_pages":len(pages),"pdf_bytes":len(b),
      "accepted_exact_dob":len(accepted),"conflicts":len(conflicts),"unresolved":len(rows)-len(accepted)-len(conflicts),
      "acceptance_rule":"Exact day-month-year must appear with an asterisk birth marker on an official Leopoldina new-member profile page for the same frozen member; exactly one plausible date is required.",
      "bazi_variables_computed":0
    }
    (OUT/f"summary_{YEAR}.json").write_text(__import__("json").dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(__import__("json").dumps(summary,ensure_ascii=False,indent=2))
    if conflicts:raise RuntimeError(f"{YEAR}: {len(conflicts)} conflicting unique DOB candidates")

if __name__=="__main__":main()
