#!/usr/bin/env python3
from __future__ import annotations
import datetime as dt, html, http.cookiejar, json, re, urllib.parse, urllib.request
from html.parser import HTMLParser
from pathlib import Path

OUT=Path("data/royal_society_election_year_probe_v1")
URL="https://catalogues.royalsociety.org/calmview/personsearch.aspx?src=CalmView.Persons"
UA="bazi-public-figure-study/1.0 (Royal Society election-year roster probe; no DOB/BaZi)"
MEMBERSHIP="ctl00$main$DSCoverySearch1$ctl00$SearchText$MembershipCategory_default"
ELECTION="ctl00$main$DSCoverySearch1$ctl00$SearchText$DateOfElection_default"
SEARCHBTN="ctl00$main$DSCoverySearch1$ctl01$Button1"

class P(HTMLParser):
    def __init__(self):
        super().__init__(); self.hidden={}
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=="input" and a.get("name") and (a.get("type") or "").lower()=="hidden":
            self.hidden[a["name"]]=a.get("value","")

def opener():
    cj=http.cookiejar.CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

def req(op,url,data=None):
    headers={"User-Agent":UA,"Accept":"text/html,application/xhtml+xml"}
    if data is None:
        r=urllib.request.Request(url,headers=headers)
    else:
        body=urllib.parse.urlencode(data).encode()
        headers["Content-Type"]="application/x-www-form-urlencoded"
        headers["Referer"]=URL
        r=urllib.request.Request(url,data=body,method="POST",headers=headers)
    with op.open(r,timeout=120) as x:return x.read(),x.geturl()

def result_range(text):
    m=re.search(r"\b(\d[\d,]*)\s+to\s+(\d[\d,]*)\s+of\s+(\d[\d,]*)\b",text,re.I)
    return tuple(int(x.replace(",","")) for x in m.groups()) if m else None

def probe(year):
    op=opener(); raw,u=req(op,URL)
    p=P();p.feed(raw.decode("utf-8",errors="replace"))
    payload=dict(p.hidden)
    payload[MEMBERSHIP]="Fellow";payload[ELECTION]=str(year);payload[SEARCHBTN]="Search"
    res,ru=req(op,URL,payload)
    text=res.decode("utf-8",errors="replace")
    rr=result_range(text)
    links=re.findall(r'Record\.aspx\?[^"\']*src=CalmView\.Persons[^"\']*',text,re.I)
    return {"year":year,"result_range":rr,"record_links_first_page":len(set(links)),"final_url":ru,"bytes":len(res)}

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    years=[1660,1700,1800,1850,1900,1901,1950,2000,2020,2025]
    rows=[]
    for y in years:
        try:r=probe(y)
        except Exception as e:r={"year":y,"error":repr(e)}
        print(r);rows.append(r)
    summary={"dataset":"Royal Society Fellow election-year search probe v1","created_utc":dt.datetime.now(dt.timezone.utc).isoformat(),"results":rows,"dob_lookup_performed":0,"bazi_variables_computed":0}
    (OUT/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print(json.dumps(summary,indent=2))
if __name__=="__main__":main()
