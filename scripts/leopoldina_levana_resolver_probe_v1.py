#!/usr/bin/env python3
from __future__ import annotations
import json,re,html,urllib.request
from urllib.parse import urljoin
from pathlib import Path

OUT=Path("data/leopoldina_levana_resolver_probe_v1")
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/155.0 Safari/537.36"
RECORDS={
  2009:"https://levana.leopoldina.org/receive/leopoldina_mods_00308",
  2011:"https://levana.leopoldina.org/receive/leopoldina_mods_00992",
  2015:"https://levana.leopoldina.org/receive/leopoldina_mods_00454",
  2019:"https://levana.leopoldina.org/receive/leopoldina_mods_00323",
}
def fetch(url):
    try:
        req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"text/html,application/xhtml+xml,*/*","Accept-Language":"en-US,en;q=0.9"})
        with urllib.request.urlopen(req,timeout=40) as r:return r.status,r.geturl(),r.read().decode("utf-8","replace"),""
    except Exception as e:return getattr(e,"code",None),url,"",f"{type(e).__name__}: {e}"
def main():
    OUT.mkdir(parents=True,exist_ok=True)
    out=[]
    for year,url in RECORDS.items():
        st,final,body,err=fetch(url)
        candidates=[]
        for m in re.finditer(r'(?:href|src)=["\']([^"\']+)["\']',body,re.I):
            u=urljoin(final,html.unescape(m.group(1)))
            if any(k in u.lower() for k in [".pdf","mcrfilenodeservlet","derivate","download"]):
                candidates.append(u)
        # also capture raw embedded servlet strings
        candidates += [urljoin(final,html.unescape(x)) for x in re.findall(r'(https?://[^"\'<>\s]+MCRFileNodeServlet[^"\'<>\s]+)',body,re.I)]
        candidates=sorted(set(candidates))
        rec={"year":year,"record_url":url,"status":st,"final_url":final,"html_bytes":len(body.encode()),"error":err,"candidates":candidates}
        out.append(rec)
        print(json.dumps(rec,ensure_ascii=False,indent=2))
    (OUT/"probe.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
if __name__=="__main__":main()
