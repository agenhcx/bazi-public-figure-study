#!/usr/bin/env python3
from __future__ import annotations
import datetime as dt, hashlib, html, json, re, urllib.request
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin

OUT=Path("data/royal_society_roster_diagnostic_v1")
CURRENT="https://royalsociety.org/fellows-directory/"
PAST="https://catalogues.royalsociety.org/calmview/personsearch.aspx?src=CalmView.Persons"
UA="bazi-public-figure-study/1.0 (Royal Society roster acquisition diagnostic; no DOB/BaZi)"

def fetch(url):
    req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"text/html,application/xhtml+xml"})
    with urllib.request.urlopen(req,timeout=120) as r:
        return r.read(),dict(r.headers),r.geturl(),r.status
def sha256(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for c in iter(lambda:f.read(1024*1024),b""):h.update(c)
    return h.hexdigest()

class Probe(HTMLParser):
    def __init__(self):
        super().__init__(); self.forms=[]; self.cur=None; self.links=[]; self.scripts=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=="form":
            self.cur={"action":a.get("action",""),"method":a.get("method","get"),"inputs":[]}
            self.forms.append(self.cur)
        elif tag in ("input","select","textarea","button") and self.cur is not None:
            self.cur["inputs"].append({"tag":tag,"name":a.get("name",""),"type":a.get("type",""),"value":a.get("value",""),"id":a.get("id","")})
        elif tag=="a" and a.get("href"):
            self.links.append(a["href"])
        elif tag=="script":
            self.scripts.append({"src":a.get("src",""),"type":a.get("type",""),"id":a.get("id","")})
    def handle_endtag(self,tag):
        if tag=="form":self.cur=None

def probe(name,url):
    data,headers,final_url,status=fetch(url)
    p=OUT/f"{name}.html"; p.write_bytes(data)
    text=data.decode("utf-8",errors="replace")
    parser=Probe(); parser.feed(text)
    links=[urljoin(final_url,x) for x in parser.links]
    profileish=[x for x in links if any(k in x.lower() for k in ("fellow","person","profile","people"))]
    apish=sorted(set(re.findall(r'https?://[^"\'<>\s]+|/[A-Za-z0-9_./?=&%-]*(?:api|search|graphql)[A-Za-z0-9_./?=&%-]*',text,re.I)))
    nextdata=re.findall(r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>',text,re.I|re.S)
    result={
      "requested_url":url,"final_url":final_url,"status":status,"bytes":len(data),
      "content_type":headers.get("Content-Type",""),"sha256":sha256(p),
      "form_count":len(parser.forms),"forms":parser.forms[:20],
      "link_count":len(links),"profileish_link_count":len(profileish),"profileish_link_sample":profileish[:30],
      "script_count":len(parser.scripts),"script_sample":parser.scripts[:30],
      "apiish_text_matches":apish[:100],
      "has_next_data":int(bool(nextdata)),
      "next_data_chars":len(nextdata[0]) if nextdata else 0,
      "common_markers":{
        "fellow_word_count":len(re.findall(r"\bfellow\b",text,re.I)),
        "foreign_member_count":len(re.findall(r"foreign member",text,re.I)),
        "membership_category_count":len(re.findall(r"membership category",text,re.I)),
        "date_of_election_count":len(re.findall(r"date of election",text,re.I)),
      }
    }
    return result

def main():
    if OUT.exists() and any(OUT.iterdir()): raise RuntimeError(f"Output dir nonempty: {OUT}")
    OUT.mkdir(parents=True,exist_ok=True)
    results={}
    for name,url in (("current_directory",CURRENT),("past_fellows_search",PAST)):
        try: results[name]=probe(name,url)
        except Exception as e: results[name]={"requested_url":url,"error":repr(e)}
    summary={
      "dataset":"Royal Society official roster acquisition diagnostic v1",
      "created_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
      "current_directory":CURRENT,"past_fellows_search":PAST,
      "results":results,
      "dob_lookup_performed":0,"bazi_variables_computed":0,
      "note":"Diagnostic only. No roster is frozen and no DOB/BaZi fields are collected."
    }
    (OUT/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
