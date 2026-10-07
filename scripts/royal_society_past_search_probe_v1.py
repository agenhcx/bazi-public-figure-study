#!/usr/bin/env python3
from __future__ import annotations
import csv, datetime as dt, hashlib, html, http.cookiejar, json, re, urllib.parse, urllib.request
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin

OUT=Path("data/royal_society_past_search_probe_v1")
URL="https://catalogues.royalsociety.org/calmview/personsearch.aspx?src=CalmView.Persons"
UA="bazi-public-figure-study/1.0 (Royal Society historical roster form probe; no DOB/BaZi)"
MEMBERSHIP="ctl00$main$DSCoverySearch1$ctl00$SearchText$MembershipCategory_default"
SEARCHBTN="ctl00$main$DSCoverySearch1$ctl01$Button1"

class FormParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.hidden={}; self.links=[]; self.forms=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=="input" and a.get("name"):
            if (a.get("type") or "").lower()=="hidden":
                self.hidden[a["name"]]=a.get("value","")
        elif tag=="a" and a.get("href"):
            self.links.append(a["href"])
        elif tag=="form":
            self.forms.append({"action":a.get("action",""),"method":a.get("method","get")})

def sha256(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for c in iter(lambda:f.read(1024*1024),b""):h.update(c)
    return h.hexdigest()

def opener():
    cj=http.cookiejar.CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

def get(op,url):
    req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"text/html,application/xhtml+xml"})
    with op.open(req,timeout=180) as r:return r.read(),r.geturl(),r.status,dict(r.headers)

def post(op,url,data):
    body=urllib.parse.urlencode(data).encode("utf-8")
    req=urllib.request.Request(url,data=body,method="POST",headers={
        "User-Agent":UA,
        "Accept":"text/html,application/xhtml+xml",
        "Content-Type":"application/x-www-form-urlencoded",
        "Referer":URL,
    })
    with op.open(req,timeout=180) as r:return r.read(),r.geturl(),r.status,dict(r.headers)

def parse(data):
    text=data.decode("utf-8",errors="replace")
    p=FormParser();p.feed(text)
    return text,p

def probe(category):
    op=opener()
    first,fu,fs,fh=get(op,URL)
    _,fp=parse(first)
    if "__VIEWSTATE" not in fp.hidden or "__EVENTVALIDATION" not in fp.hidden:
        raise RuntimeError("Missing ASP.NET state fields")
    payload=dict(fp.hidden)
    payload[MEMBERSHIP]=category
    payload[SEARCHBTN]="Search"
    # Preserve explicit defaults for fields represented by selects/textboxes.
    payload.setdefault("ctl00$main$DSCoverySearch1$ctl00$SearchText$Nationality_default","")
    payload.setdefault("ctl00$main$DSCoverySearch1$ctl00$SearchText$Gender_default","")
    result,ru,rs,rh=post(op,URL,payload)
    text,rp=parse(result)

    safe=re.sub(r"[^A-Za-z0-9]+","_",category).strip("_").lower()
    path=OUT/f"results_{safe}.html";path.write_bytes(result)
    links=[urljoin(ru,x) for x in rp.links]

    # CalmView record/result links are intentionally detected broadly here.
    recordish=sorted(set(x for x in links if re.search(r"(person|record|catalog|id=|action=)",x,re.I)))
    nums=[int(x) for x in re.findall(r"\b(?:Page\s*)?(\d+)\s*(?:of|/)\s*(\d+)\b",text,re.I) for x in x if x.isdigit()]
    markers={}
    for pat in [
        r"\b\d+\s+results?\b",
        r"\b\d+\s+records?\b",
        r"Page\s+\d+\s+of\s+\d+",
        r"Search results",
        r"Membership Category",
        r"Date of election",
    ]:
        markers[pat]=re.findall(pat,text,re.I)[:20]

    return {
        "category":category,
        "status":rs,
        "final_url":ru,
        "bytes":len(result),
        "sha256":sha256(path),
        "form_count":len(rp.forms),
        "hidden_input_count":len(rp.hidden),
        "link_count":len(links),
        "recordish_link_count":len(recordish),
        "recordish_link_sample":recordish[:50],
        "text_markers":markers,
        "contains_category_literal":int(category.lower() in text.lower()),
    }

def main():
    if OUT.exists() and any(OUT.iterdir()):
        raise RuntimeError(f"Output dir nonempty: {OUT}")
    OUT.mkdir(parents=True,exist_ok=True)
    results=[]
    for cat in ("Fellow","Foreign Member"):
        print("Probing",cat)
        results.append(probe(cat))
    summary={
        "dataset":"Royal Society historical CalmView membership-category probe v1",
        "created_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
        "source":URL,
        "results":results,
        "dob_fields_parsed":0,
        "bazi_variables_computed":0,
        "note":"Diagnostic only. Uses the official ASP.NET form state and submits only membership category. No DOB extraction and no roster freeze."
    }
    (OUT/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=="__main__":main()
