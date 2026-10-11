#!/usr/bin/env python3
from __future__ import annotations
import csv,html,os,re,time,unicodedata,urllib.request,urllib.parse
from pathlib import Path
from pypdf import PdfReader

YEAR=int(os.environ["ELECTION_YEAR"])
ROSTER=Path("data/leopoldina_roster_freeze_v1/leopoldina_science_core_roster_freeze_v1.csv")
OUT=Path("data/leopoldina_new_member_dob_shard_v1")
UA="Mozilla/5.0 (compatible; bazi-public-figure-study/1.0; reproducibility research)"
OFFICIAL_PDF_URLS={
  2009:"https://levana.leopoldina.org/servlets/MCRFileNodeServlet/leopoldina_derivate_00308/2009_Leopoldina_Neugewaehlte_Mitglieder.pdf",
  2010:"https://www.leopoldina.org/fileadmin/Migrierte_Daten/Publikationen/Dokumente/01-59_NAL_Mitglieder-2010_Gesamt.pdf",
  2011:"https://levana.leopoldina.org/servlets/MCRFileNodeServlet/leopoldina_derivate_00781/2011_Leopoldina_Neugewaehlte_Mitglieder.pdf",
  2012:"https://www.leopoldina.org/fileadmin/Migrierte_Daten/Publikationen/Dokumente/Neugewaehlte_Mitglieder_2012.pdf",
  2013:"https://www.leopoldina.org/fileadmin/Migrierte_Daten/Publikationen/Dokumente/Neugewaehlte_Mitglieder_2013_2.pdf",
  2014:"https://www.leopoldina.org/fileadmin/Migrierte_Daten/Publikationen/Dokumente/Neugewaehlte_Mitglieder_2014_01.pdf",
  2015:"",
  2016:"https://www.leopoldina.org/fileadmin/Migrierte_Daten/Publikationen/Dokumente/Neugew%C3%A4hlte_Mitglieder_2016.pdf",
  2017:"https://www.leopoldina.org/fileadmin/Migrierte_Daten/Publikationen/Dokumente/Neugewaehlte_Mitglieder_2017_01.pdf",
  2018:"https://www.leopoldina.org/fileadmin/Migrierte_Daten/Publikationen/Dokumente/Neugewaehlte_Mitglieder_2018_01.pdf",
  2019:"https://levana.leopoldina.org/servlets/MCRFileNodeServlet/leopoldina_derivate_00170/2019_Leopoldina_Neugewaehlte_Mitglieder.pdf",
}
PUBLICATION_LOCATORS={
  y:f"https://www.leopoldina.org/ergebnisse-und-termine/publikationen/detail/neugewaehlte-mitglieder-{y}"
  for y in range(2009,2020)
}
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
    if year not in OFFICIAL_PDF_URLS:
        raise RuntimeError(f"Year outside frozen official-volume pass: {year}")
    return OFFICIAL_PDF_URLS[year],PUBLICATION_LOCATORS[year]

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
    # In the old new-member volumes the profile identity appears before the
    # first starred birth marker. Require the exact first-name and surname
    # tokens in that pre-birth header. This rejects references to spouses,
    # collaborators, or similarly named members later on the same/adjacent
    # profile text (e.g. Mann/Wilmanns and the two Mosers).
    head_raw=text[:1800]
    star=head_raw.find("*")
    if star<0:return False
    identity=norm(head_raw[:star])
    head=norm(head_raw)
    if not re.search(rf"\b{re.escape(first)}\b",identity):return False
    if not re.search(rf"\b{re.escape(last)}\b",identity):return False
    if not re.search(r"\b(section|sektion)\b",head):return False
    if not re.search(r"\b(matricula|matrikel|date of election|aufnahmedatum)\b",head):return False
    return True

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    roster=[r for r in read_csv(ROSTER) if int(r["election_year"])==YEAR]
    pdf_url,locator=discover_pdf(YEAR)
    source_status="available"
    source_error=""
    b=b""
    pages=[]

    if not pdf_url:
        source_status="no_verified_current_pdf_locator"
    else:
        try:
            _,b=fetch(pdf_url,"application/pdf,*/*",tries=3)
            if not b.startswith(b"%PDF"):
                source_status="non_pdf_response"
                source_error=f"response_bytes={len(b)}"
            else:
                pdf=OUT/f"new_members_{YEAR}.pdf";pdf.write_bytes(b)
                reader=PdfReader(str(pdf))
                pages=[p.extract_text() or "" for p in reader.pages]
        except Exception as e:
            source_status="transport_unavailable"
            source_error=f"{type(e).__name__}: {e}"

    rows=[]
    for r in roster:
        matches=[]
        if source_status=="available":
            for i,text in enumerate(pages):
                if not page_is_target(text,r["member_slug"]):continue
                ds=dates(text[:1800])
                for iso,raw in ds:
                    age=YEAR-int(iso[:4])
                    if 20<=age<=100:
                        matches.append((iso,raw,i+1))
        unique=sorted({m[0] for m in matches})
        accepted=unique[0] if len(unique)==1 else ""
        support=[m for m in matches if m[0]==accepted] if accepted else matches
        if source_status!="available":
            decision=f"unresolved_source_{source_status}"
        elif accepted:
            decision="accept_official_new_member_profile_exact_dob"
        elif len(unique)>1:
            decision="conflict_review"
        else:
            decision="unresolved_no_exact_birth_marker"
        rows.append({
          "member_slug":r["member_slug"],"display_name":r["display_name"],"class":r["class"],"section":r["section"],
          "election_year":YEAR,"candidate_dob":accepted,"candidate_count":len(unique),
          "raw_birth_marker":" | ".join(sorted({m[1] for m in support}))[:500],
          "pdf_page":" | ".join(str(x) for x in sorted({m[2] for m in support})),
          "pdf_url":pdf_url,"publication_locator":locator,"source_status":source_status,"source_error":source_error,
          "decision":decision,"bazi_variables_computed":0
        })

    fields=list(rows[0].keys()) if rows else ["member_slug"]
    cp=OUT/f"dob_candidates_{YEAR}.csv"
    with cp.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
    accepted=[r for r in rows if r.get("decision")=="accept_official_new_member_profile_exact_dob"]
    conflicts=[r for r in rows if r.get("decision")=="conflict_review"]
    summary={
      "dataset":"Leopoldina official new-member exact-DOB shard v1","election_year":YEAR,
      "roster_targets":len(roster),"pdf_url":pdf_url,"source_status":source_status,"source_error":source_error,
      "pdf_pages":len(pages),"pdf_bytes":len(b),
      "accepted_exact_dob":len(accepted),"conflicts":len(conflicts),"unresolved":len(rows)-len(accepted)-len(conflicts),
      "acceptance_rule":"Exact day-month-year must appear with an asterisk birth marker on an official Leopoldina new-member profile page for the same frozen member; exactly one plausible date is required. Unavailable or non-PDF official source responses remain unresolved rather than failing over to a weaker source.",
      "bazi_variables_computed":0
    }
    (OUT/f"summary_{YEAR}.json").write_text(__import__("json").dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(__import__("json").dumps(summary,ensure_ascii=False,indent=2))
    if conflicts:raise RuntimeError(f"{YEAR}: {len(conflicts)} conflicting unique DOB candidates")

if __name__=="__main__":main()
