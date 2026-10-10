#!/usr/bin/env python3
import json,urllib.request
from pathlib import Path
OUT=Path("data/leopoldina_levana_rest_probe_v1");OUT.mkdir(parents=True,exist_ok=True)
IDS={2009:"leopoldina_mods_00308",2011:"leopoldina_mods_00992",2015:"leopoldina_mods_00454",2019:"leopoldina_mods_00323"}
UA="Mozilla/5.0 (compatible; bazi-public-figure-study/1.0)"
report={}
for y,obj in IDS.items():
    urls=[
      f"https://levana.leopoldina.org/api/v2/objects/{obj}/derivates.json",
      f"https://levana.leopoldina.org/api/v1/objects/{obj}/derivates?format=json",
      f"https://levana.leopoldina.org/api/v1/objects/{obj}?style=derivatedetails"
    ]
    rr=[]
    for u in urls:
        try:
            req=urllib.request.Request(u,headers={"User-Agent":UA,"Accept":"application/json,application/xml,text/xml,*/*"})
            with urllib.request.urlopen(req,timeout=25) as r:
                b=r.read()
                rr.append({"url":u,"status":r.status,"content_type":r.headers.get("Content-Type",""),"bytes":len(b),"body_prefix":b.decode("utf-8","replace")[:8000]})
        except Exception as e:
            rr.append({"url":u,"status":getattr(e,"code",None),"error":f"{type(e).__name__}: {e}"})
    report[str(y)]=rr
Path(OUT/"probe.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(report,ensure_ascii=False,indent=2))
