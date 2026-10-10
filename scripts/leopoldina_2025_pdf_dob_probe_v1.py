#!/usr/bin/env python3
from __future__ import annotations
import json,re,subprocess
from pathlib import Path

PDF=Path("data/leopoldina_2025_pdf_dob_probe_v1/2025_Leopoldina_Struktur_und_Mitglieder.pdf")
TXT=Path("data/leopoldina_2025_pdf_dob_probe_v1/2025_Leopoldina_Struktur_und_Mitglieder.txt")
OUT=Path("data/leopoldina_2025_pdf_dob_probe_v1")
SAMPLES=["Zvi Laron","Meike Stiesch","Anja Feldmann","Bettina Rockenbach","Volker ter Meulen"]

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    subprocess.run(["pdftotext","-layout",str(PDF),str(TXT)],check=True)
    text=TXT.read_text(encoding="utf-8",errors="replace")
    lines=text.splitlines()
    # Historical Leopoldina directories used an asterisk before exact birth dates.
    pats=[
      re.compile(r"\*\s*([0-3]?\d)[.\-/]\s*([01]?\d)[.\-/]\s*((?:18|19|20)\d{2})"),
      re.compile(r"\*\s*([0-3]?\d)\s+([A-Za-zÄÖÜäöü]+)\s+((?:18|19|20)\d{2})"),
    ]
    matches=[]
    for i,line in enumerate(lines):
        if any(p.search(line) for p in pats):
            matches.append({"line":i+1,"text":line.strip()})
    headings=[line.strip() for line in lines if "birth date" in line.lower() or "geburtsdatum" in line.lower()]
    samples={}
    for name in SAMPLES:
        idx=[i for i,l in enumerate(lines) if name.lower() in l.lower()]
        samples[name]=[" | ".join(x.strip() for x in lines[max(0,i-2):min(len(lines),i+5)] if x.strip()) for i in idx[:3]]
    report={
      "dataset":"Leopoldina 2025 official member-directory PDF DOB diagnostic v1",
      "pdf_pages_hint":504,
      "text_chars":len(text),
      "birthdate_heading_lines":headings[:20],
      "exact_birthdate_pattern_line_count":len(matches),
      "exact_birthdate_pattern_samples":matches[:30],
      "named_samples":samples,
      "bazi_variables_computed":0
    }
    (OUT/"probe.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=="__main__":main()
