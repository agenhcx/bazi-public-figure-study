#!/usr/bin/env python3
from __future__ import annotations
import datetime as dt, json, re, urllib.parse, urllib.request
from pathlib import Path

BASE="https://catalogues.royalsociety.org/calmview/Overview.aspx"
OUT=Path("data/royal_society_missing_election_date_probe_v1")
UA="bazi-public-figure-study/1.0 (Royal Society missing-election-date probe; no DOB/BaZi)"

FILTERS={
  "blank_eq":"(((MembershipCategory='Fellow'))) And ((DateOfElection=''))",
  "null_is":"(((MembershipCategory='Fellow'))) And ((DateOfElection Is Null))",
  "not_1660_2025":"(((MembershipCategory='Fellow'))) And Not ((DateOfElection>='1660') And (DateOfElection<='2025'))",
}

def result_range(text):
    m=re.search(r"\b(\d[\d,]*)\s+to\s+(\d[\d,]*)\s+of\s+(\d[\d,]*)\b",text,re.I)
    return tuple(int(x.replace(",","")) for x in m.groups()) if m else None

def fetch(label,filt):
    url=BASE+"?"+urllib.parse.urlencode({"src":"CalmView.Persons","r":filt})
    req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"text/html,application/xhtml+xml"})
    try:
        with urllib.request.urlopen(req,timeout=120) as r:
            raw=r.read(); final=r.geturl(); status=r.status
        text=raw.decode("utf-8",errors="replace")
        (OUT/f"{label}.html").write_bytes(raw)
        ids=sorted(set(re.findall(r"Record\.aspx\?[^\"']*src=CalmView\.Persons[^\"']*id=([^&\"']+)",text,re.I)))
        return {"label":label,"status":status,"final_url":final,"result_range":result_range(text),"unique_ids_first_page":ids[:50],"unique_id_count_first_page":len(ids)}
    except Exception as e:
        return {"label":label,"url":url,"error":repr(e)}

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    rows=[fetch(k,v) for k,v in FILTERS.items()]
    out={"dataset":"Royal Society missing election-date diagnostic v1","created_utc":dt.datetime.now(dt.timezone.utc).isoformat(),"results":rows,"dob_lookup_performed":0,"bazi_variables_computed":0}
    (OUT/"summary.json").write_text(json.dumps(out,indent=2),encoding="utf-8")
    print(json.dumps(out,indent=2))
if __name__=="__main__":main()
