#!/usr/bin/env python3
from __future__ import annotations
import json,re,html,urllib.request
from urllib.parse import urljoin
from pathlib import Path

OUT=Path("data/leopoldina_publication_locator_audit_v1")
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/155.0 Safari/537.36"

def fetch(url):
    try:
        req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"text/html,application/xhtml+xml","Accept-Language":"en-US,en;q=0.9"})
        with urllib.request.urlopen(req,timeout=25) as r:return r.status,r.geturl(),r.read().decode("utf-8","replace"),""
    except Exception as e:return getattr(e,"code",None),url,"",f"{type(e).__name__}: {e}"

def anchors(text,base):
    out=[]
    for m in re.finditer(r'<a\b([^>]*)href=["\']([^"\']+)["\']([^>]*)>(.*?)</a>',text,re.I|re.S):
        href=urljoin(base,html.unescape(m.group(2)))
        label=re.sub(r"\s+"," ",html.unescape(re.sub(r"<[^>]+>"," ",m.group(4)))).strip()
        attrs=re.sub(r"\s+"," ",m.group(1)+" "+m.group(3)).strip()
        if ".pdf" in href.lower() or re.search(r"publikation|publication|download|open access|mitglieder",label,re.I):
            out.append({"href":href,"label":label,"attrs":attrs[:400]})
    return out

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    report=[]
    for y in range(2010,2020):
        pages=[
          f"https://www.leopoldina.org/ergebnisse-und-termine/publikationen/detail/neugewaehlte-mitglieder-{y}",
          f"https://www.leopoldina.org/en/publications-and-dates/publications/detail/neugewaehlte-mitglieder-{y}",
        ]
        rec={"year":y,"pages":[]}
        for u in pages:
            st,final,body,err=fetch(u)
            rec["pages"].append({"url":u,"status":st,"final_url":final,"error":err,"anchors":anchors(body,final) if body else []})
        report.append(rec)
    (OUT/"audit.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    for r in report:
        print("\nYEAR",r["year"])
        for p in r["pages"]:
            print(p["status"],p["url"],p["error"])
            for a in p["anchors"]: print(" ",a["label"][:80],"->",a["href"])

if __name__=="__main__":main()
