#!/usr/bin/env python3
from __future__ import annotations
import json,re,time,urllib.request,http.cookiejar
from html import unescape
from pathlib import Path

OUT=Path("data/leopoldina_detail_structure_probe_v1")
URLS=[
 "https://www.leopoldina.org/en/members/member-list/detail/carl-bergemann",
 "https://www.leopoldina.org/en/members/member-list/detail/meike-stiesch",
 "https://www.leopoldina.org/en/members/member-list/detail/thomas-misgeld",
 "https://www.leopoldina.org/en/members/member-list/detail/martine-jager"
]
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/155.0 Safari/537.36"
JAR=http.cookiejar.CookieJar()
OPENER=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(JAR))

def fetch(url):
    h={"User-Agent":UA,"Accept":"text/html,application/xhtml+xml","Accept-Language":"en-US,en;q=0.9","Referer":"https://www.leopoldina.org/en/members/member-list/"}
    try:
        with OPENER.open(urllib.request.Request(url,headers=h),timeout=60) as r:
            b=r.read().decode("utf-8","replace")
            return {"status":r.status,"final_url":r.geturl(),"html":b,"error":""}
    except Exception as e:
        return {"status":getattr(e,"code",None),"final_url":url,"html":"","error":f"{type(e).__name__}: {e}"}

def clean(s):
    return re.sub(r"\s+"," ",unescape(re.sub(r"<[^>]+>"," ",s))).strip()

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    # establish session
    fetch("https://www.leopoldina.org/en/members/member-list/")
    rows=[]
    for i,url in enumerate(URLS):
        x=fetch(url); html=x.pop("html")
        if html:
            (OUT/f"sample_{i}.html").write_text(html,encoding="utf-8")
        title=re.search(r"<title[^>]*>(.*?)</title>",html,re.I|re.S)
        text=clean(html)
        snippets=[]
        for pat in ["Born","Date of birth","Elected","Election","Section","Class","deceased","Died","Member since"]:
            m=re.search(rf".{{0,180}}\b{re.escape(pat)}\b.{{0,280}}",text,re.I)
            if m: snippets.append({"pattern":pat,"snippet":m.group(0)})
        labels=[]
        for m in re.finditer(r"<(?:dt|th|strong|h[2-6])[^>]*>(.*?)</(?:dt|th|strong|h[2-6])>",html,re.I|re.S):
            v=clean(m.group(1))
            if v and len(v)<120: labels.append(v)
        rows.append({**x,"requested_url":url,"title":clean(title.group(1)) if title else "","html_bytes":len(html.encode()),"labels":labels[:80],"snippets":snippets})
        time.sleep(.4)
    report={"dataset":"Leopoldina member detail structure probe v1","rows":rows,"bazi_variables_computed":0}
    (OUT/"probe.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=="__main__":main()
