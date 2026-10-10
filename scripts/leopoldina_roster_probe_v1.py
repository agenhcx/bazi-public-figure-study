#!/usr/bin/env python3
from __future__ import annotations
import json,re,time,urllib.request,urllib.error
from html import unescape
from pathlib import Path
from urllib.parse import urljoin,urlparse,parse_qs

OUT=Path("data/leopoldina_roster_probe_v1")
URLS=[
 "https://www.leopoldina.org/en/members/member-list/",
 "https://www.leopoldina.org/mitglieder/mitgliederverzeichnis/",
 "https://www.leopoldina.org/en/members/member-list?tx_solr%5Bfilter%5D%5B0%5D=class%3AClass+I%3A+Mathematics%2C+Natural+Sciences+and+Engineering",
 "https://www.leopoldina.org/en/members/member-list?tx_solr%5Bfilter%5D%5B0%5D=class%3AClass+I%3A+Mathematics%2C+Natural+Sciences+and+Engineering&tx_solr%5Bpage%5D=2",
]
UA="Mozilla/5.0 (compatible; bazi-public-figure-study/1.0; reproducibility research)"

def fetch(url):
    req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"text/html,application/xhtml+xml"})
    try:
        with urllib.request.urlopen(req,timeout=30) as r:
            b=r.read()
            return {"status":r.status,"final_url":r.geturl(),"bytes":len(b),"html":b.decode("utf-8","replace"),"error":""}
    except Exception as e:
        return {"status":None,"final_url":url,"bytes":0,"html":"","error":f"{type(e).__name__}: {e}"}

def clean(s):
    return re.sub(r"\s+"," ",unescape(re.sub(r"<[^>]+>"," ",s))).strip()

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    report={"dataset":"Leopoldina official member-directory discovery probe v1","bazi_variables_computed":0,"pages":[]}
    for idx,url in enumerate(URLS):
        x=fetch(url); html=x.pop("html")
        if idx==0 and html:
            (OUT/"member_list_landing_snapshot.html").write_text(html,encoding="utf-8")
        hrefs=[unescape(h) for h in re.findall(r'href=["\']([^"\']+)["\']',html,re.I)]
        hrefs=[urljoin(x["final_url"],h) for h in hrefs]
        detail=sorted(set(h for h in hrefs if re.search(r"/(?:en/members/member-list|mitglieder/mitgliederverzeichnis)/detail/",h)))
        member_links=sorted(set(h for h in hrefs if "member-list" in h or "mitgliederverzeichnis" in h))
        forms=[]
        for fm in re.finditer(r"<form\b([^>]*)>(.*?)</form>",html,re.I|re.S):
            attrs=fm.group(1); body=fm.group(2)
            action=re.search(r'action=["\']([^"\']*)["\']',attrs,re.I)
            method=re.search(r'method=["\']([^"\']*)["\']',attrs,re.I)
            inputs=[]
            for im in re.finditer(r"<(?:input|select)\b([^>]*)>",body,re.I|re.S):
                a=im.group(1)
                nm=re.search(r'name=["\']([^"\']+)["\']',a,re.I)
                tp=re.search(r'type=["\']([^"\']+)["\']',a,re.I)
                if nm: inputs.append({"name":nm.group(1),"type":tp.group(1) if tp else ""})
            forms.append({"action":urljoin(x["final_url"],action.group(1)) if action else x["final_url"],"method":method.group(1).upper() if method else "GET","inputs":inputs[:80]})
        page_like=[]
        for h in member_links:
            q=parse_qs(urlparse(h).query)
            if q: page_like.append({"url":h,"query":q})
        title_m=re.search(r"<title[^>]*>(.*?)</title>",html,re.I|re.S)
        report["pages"].append({
          **x,
          "requested_url":url,
          "title":clean(title_m.group(1)) if title_m else "",
          "detail_link_count":len(detail),
          "detail_links_sample":detail[:30],
          "member_directory_link_count":len(member_links),
          "member_directory_links_sample":member_links[:80],
          "query_links_sample":page_like[:80],
          "pagination_links":[h for h in member_links if "tx_solr%5Bpage%5D" in h or "tx_solr[page]" in h][:30],
          "forms":forms[:20]
        })
        time.sleep(1)
    (OUT/"probe.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
