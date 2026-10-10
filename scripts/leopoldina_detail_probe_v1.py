#!/usr/bin/env python3
from __future__ import annotations
import json,re,urllib.request,time
from pathlib import Path
from html import unescape

OUT=Path("data/leopoldina_detail_probe_v1")
URLS=[
 "https://www.leopoldina.org/en/members/member-list/detail/carl-bergemann",
 "https://www.leopoldina.org/en/members/member-list/detail/zvi-laron",
 "https://www.leopoldina.org/en/members/member-list/detail/meike-stiesch",
 "https://www.leopoldina.org/en/members/member-list/detail/anja-feldmann",
]
UA="Mozilla/5.0 (compatible; bazi-public-figure-study/1.0; reproducibility research)"

def fetch(url):
    req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"text/html,application/xhtml+xml"})
    with urllib.request.urlopen(req,timeout=60) as r:return r.read().decode("utf-8","replace")
def clean(s):return re.sub(r"\s+"," ",unescape(re.sub(r"<[^>]+>"," ",s))).strip()

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    rows=[]
    for i,url in enumerate(URLS):
        html=fetch(url)
        title=re.search(r"<h1[^>]*>(.*?)</h1>",html,re.I|re.S)
        text=clean(html)
        snippets={}
        for term in ["Section","Election year","Location","Honorary","Cognomen"]:
            j=text.find(term)
            snippets[term]=text[max(0,j-180):j+500] if j>=0 else ""
        raw_snippets={}
        for term in ["Section","Election year"]:
            m=re.search(term,html,re.I)
            raw_snippets[term]=html[max(0,m.start()-700):m.start()+1600] if m else ""
        rows.append({"url":url,"bytes":len(html.encode()),"h1":clean(title.group(1)) if title else "","dagger_present":int("✝" in text or "†" in text),"text_snippets":snippets,"raw_snippets":raw_snippets})
        (OUT/f"sample_{i}.html").write_text(html,encoding="utf-8")
        time.sleep(.2)
    report={"dataset":"Leopoldina member-detail HTML probe v1","rows":rows,"dob_lookup_performed":0,"bazi_variables_computed":0}
    (OUT/"probe.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=="__main__":main()
