#!/usr/bin/env python3
from __future__ import annotations
import json,re
from pathlib import Path
from pypdf import PdfReader

PDF=Path("data/leopoldina_2015_pdf_dob_probe_v1/2015_Leopoldina_Mitgliederverzeichnis_02.pdf")
TXT=Path("data/leopoldina_2015_pdf_dob_probe_v1/2015_Leopoldina_Mitgliederverzeichnis_02.txt")
OUT=PDF.parent
SAMPLES=["Zvi Laron","Anja Feldmann","Volker ter Meulen","Carl Bergemann","Robert Wilhelm Bunsen"]

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    reader=PdfReader(str(PDF))
    pages=[p.extract_text() or "" for p in reader.pages]
    text="\n\f\n".join(pages); TXT.write_text(text,encoding="utf-8")
    lines=text.splitlines()
    pat=re.compile(r"\*\s*([0-3]?\d)\s*[.]\s*([01]?\d)\s*[.]\s*((?:18|19|20)\d{2})")
    matches=[{"line":i+1,"date":"-".join([m.group(3),m.group(2).zfill(2),m.group(1).zfill(2)]),"text":line.strip()} for i,line in enumerate(lines) for m in [pat.search(line)] if m]
    headings=[l.strip() for l in lines if "birth date" in l.lower() or "geburtsdatum" in l.lower()]
    samples={}
    for name in SAMPLES:
        idx=[i for i,l in enumerate(lines) if name.lower() in l.lower()]
        samples[name]=[" | ".join(x.strip() for x in lines[max(0,i-2):min(len(lines),i+7)] if x.strip()) for i in idx[:3]]
    report={"dataset":"Leopoldina 2015 official member-directory PDF DOB diagnostic v1","pages":len(reader.pages),"text_chars":len(text),"birthdate_heading_lines":headings[:20],"exact_birthdate_pattern_count":len(matches),"exact_birthdate_samples":matches[:30],"named_samples":samples,"bazi_variables_computed":0}
    (OUT/"probe.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=="__main__":main()
