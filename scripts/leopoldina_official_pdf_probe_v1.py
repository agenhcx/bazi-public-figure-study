#!/usr/bin/env python3
from __future__ import annotations
import csv,json,re,unicodedata,urllib.request
from pathlib import Path
from pypdf import PdfReader

ROSTER=Path("data/leopoldina_roster_freeze_v1/leopoldina_science_core_roster_freeze_v1.csv")
OUT=Path("data/leopoldina_official_pdf_probe_v1")
UA="Mozilla/5.0 (compatible; bazi-public-figure-study/1.0; reproducibility research)"
SOURCES=[
  {
    "label":"new_members_2014",
    "election_year":2014,
    "url":"https://www.leopoldina.org/fileadmin/Migrierte_Daten/Publikationen/Dokumente/Neugewaehlte_Mitglieder_2014_01.pdf",
    "page_start":0,"page_end":9999
  },
  {
    "label":"structure_2025_new_members_2024",
    "election_year":2024,
    "url":"https://www.leopoldina.org/fileadmin/Daten/Publikationen/Dokumente/2025_Leopoldina_Struktur_und_Mitglieder.pdf",
    "page_start":75,"page_end":315
  }
]
MONTHS=r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?|Januar|Februar|März|Maerz|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember)"
DATE_PATTERNS=[
 re.compile(rf"\*\s*\d{{1,2}}(?:st|nd|rd|th)?\s+{MONTHS}\s+\d{{4}}",re.I),
 re.compile(rf"\*\s*\d{{1,2}}[.]?\s+{MONTHS}\s+\d{{4}}",re.I),
 re.compile(r"\*\s*\d{1,2}[.]\d{1,2}[.]\d{4}",re.I),
 re.compile(r"\*\s*\d{4}[-/]\d{1,2}[-/]\d{1,2}",re.I),
]

def read_csv(p):
    with p.open("r",encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))

def norm(s):
    s=unicodedata.normalize("NFKD",s)
    s="".join(c for c in s if not unicodedata.combining(c))
    s=s.lower()
    return re.sub(r"[^a-z0-9]+"," ",s).strip()

def download(url,path):
    req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"application/pdf,*/*"})
    with urllib.request.urlopen(req,timeout=120) as r:
        b=r.read()
    if not b.startswith(b"%PDF"): raise RuntimeError(f"Not PDF: {url} bytes={len(b)}")
    path.write_bytes(b)
    return len(b)

def extract_pdf(path,start,end):
    reader=PdfReader(str(path))
    texts=[]
    for i,p in enumerate(reader.pages):
        if i<start or i>end: continue
        try:t=p.extract_text() or ""
        except Exception:t=""
        texts.append((i+1,t))
    return len(reader.pages),texts

def candidate_contexts(pages,slug):
    toks=[t for t in slug.split("-") if t and len(t)>1]
    if not toks:return []
    surname=toks[-1]
    given=toks[0]
    out=[]
    for page_no,text in pages:
        nt=norm(text)
        # loose surname search, then require first token somewhere in the same page
        if surname not in nt or given not in nt: continue
        for m in re.finditer(re.escape(surname),text,re.I):
            a=max(0,m.start()-500);b=min(len(text),m.end()+700)
            ctx=re.sub(r"\s+"," ",text[a:b]).strip()
            if given.lower() in norm(ctx):
                dates=[]
                for p in DATE_PATTERNS:
                    dates.extend(x.group(0) for x in p.finditer(ctx))
                out.append({"page":page_no,"context":ctx[:1100],"date_candidates":sorted(set(dates))})
                if len(out)>=4:return out
    return out

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    roster=read_csv(ROSTER)
    report={"dataset":"Leopoldina official PDF DOB structure probe v1","sources":[],"bazi_variables_computed":0}
    for src in SOURCES:
        pdf=OUT/(src["label"]+".pdf")
        size=download(src["url"],pdf)
        page_count,pages=extract_pdf(pdf,src["page_start"],src["page_end"])
        targets=[r for r in roster if int(r["election_year"])==src["election_year"]]
        rows=[]
        for r in targets:
            cs=candidate_contexts(pages,r["member_slug"])
            dates=sorted({d for c in cs for d in c["date_candidates"]})
            rows.append({
              "member_slug":r["member_slug"],"display_name":r["display_name"],"class":r["class"],"section":r["section"],
              "election_year":r["election_year"],"contexts_found":len(cs),"exact_date_candidates":dates,"contexts":cs
            })
        matched=sum(bool(r["contexts_found"]) for r in rows)
        dated=sum(len(r["exact_date_candidates"])==1 for r in rows)
        src_summary={
          "label":src["label"],"url":src["url"],"pdf_bytes":size,"pdf_pages":page_count,
          "pages_extracted":len(pages),"target_roster_rows":len(targets),"name_context_found":matched,
          "unique_exact_date_candidate_near_name":dated,"rows":rows
        }
        (OUT/(src["label"]+"_probe.json")).write_text(json.dumps(src_summary,ensure_ascii=False,indent=2),encoding="utf-8")
        report["sources"].append({k:v for k,v in src_summary.items() if k!="rows"})
        print(json.dumps(report["sources"][-1],ensure_ascii=False,indent=2))
    (OUT/"summary.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")

if __name__=="__main__":main()
