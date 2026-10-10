#!/usr/bin/env python3
from __future__ import annotations
import html,json,re,urllib.request,urllib.parse
from pathlib import Path

OUT=Path("data/leopoldina_levana_locator_probe_v1")
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/155.0 Safari/537.36"
RECORDS={
  2009:"https://levana.leopoldina.org/receive/leopoldina_mods_00308",
  2011:"https://levana.leopoldina.org/receive/leopoldina_mods_00992",
  2015:"https://levana.leopoldina.org/receive/leopoldina_mods_00454",
  2019:"https://levana.leopoldina.org/receive/leopoldina_mods_00323",
}
KNOWN_DIRECT_2009="https://levana.leopoldina.org/servlets/MCRFileNodeServlet/leopoldina_derivate_00308/2009_Leopoldina_Neugewaehlte_Mitglieder.pdf"

def fetch(url,accept="text/html,*/*"):
    req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":accept,"Accept-Language":"en-US,en;q=0.9"})
    try:
        with urllib.request.urlopen(req,timeout=60) as r:
            b=r.read()
            return {"status":r.status,"final_url":r.geturl(),"content_type":r.headers.get("Content-Type",""),"bytes":len(b),"body":b,"error":""}
    except Exception as e:
        return {"status":getattr(e,"code",None),"final_url":url,"content_type":"","bytes":0,"body":b"","error":f"{type(e).__name__}: {e}"}

def extract_links(body,base):
    text=body.decode("utf-8","replace")
    hrefs=[]
    for m in re.finditer(r'href=["\']([^"\']+)["\']',text,re.I):
        href=urllib.parse.urljoin(base,html.unescape(m.group(1)))
        if any(k.lower() in href.lower() for k in ["mcrfilenodeservlet",".pdf","download","derivate"]):
            hrefs.append(href)
    raw=sorted(set(re.findall(r'https?://[^\s"\'<>]+',text)))
    raw=[html.unescape(u) for u in raw if any(k in u.lower() for k in ["mcrfilenodeservlet",".pdf","derivate"])]
    return sorted(set(hrefs+raw)),text

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    report={"dataset":"Leopoldina Levana locator probe v1","records":{},"bazi_variables_computed":0}
    for y,u in RECORDS.items():
        x=fetch(u)
        links,text=extract_links(x["body"],x["final_url"]) if x["body"] else ([],"")
        rec={k:v for k,v in x.items() if k!="body"}
        rec["links"]=links
        rec["title"]=re.sub(r"\s+"," ",re.sub(r"<[^>]+>"," ",(re.search(r"<title[^>]*>(.*?)</title>",text,re.I|re.S).group(1) if re.search(r"<title[^>]*>(.*?)</title>",text,re.I|re.S) else ""))).strip()
        report["records"][str(y)]=rec
        (OUT/f"record_{y}.html").write_bytes(x["body"])
    x=fetch(KNOWN_DIRECT_2009,"application/pdf,*/*")
    links,text=extract_links(x["body"],x["final_url"]) if x["body"] else ([],"")
    report["known_direct_2009_response"]={k:v for k,v in x.items() if k!="body"}
    report["known_direct_2009_response"]["starts_pdf"]=int(x["body"].startswith(b"%PDF"))
    report["known_direct_2009_response"]["links"]=links
    report["known_direct_2009_response"]["body_prefix"]=text[:1200]
    (OUT/"known_direct_2009_response.bin").write_bytes(x["body"])
    (OUT/"probe.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=="__main__":main()
