#!/usr/bin/env python3
import urllib.request
from pathlib import Path
from pypdf import PdfReader
URL="https://www.leopoldina.org/fileadmin/Migrierte_Daten/Publikationen/Dokumente/Neugewaehlte_Mitglieder_2013_2.pdf"
req=urllib.request.Request(URL,headers={"User-Agent":"Mozilla/5.0","Accept":"application/pdf,*/*"})
with urllib.request.urlopen(req,timeout=120) as r:b=r.read()
Path("/tmp/x.pdf").write_bytes(b)
rd=PdfReader("/tmp/x.pdf")
for n in [37,65]:
    t=rd.pages[n-1].extract_text() or ""
    print("\n===== PAGE",n,"=====\n")
    print(t[:2500].replace("\x00"," "))
