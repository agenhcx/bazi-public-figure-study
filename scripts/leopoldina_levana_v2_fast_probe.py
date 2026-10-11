#!/usr/bin/env python3
import concurrent.futures,json,urllib.request
from pathlib import Path
IDS={2009:"leopoldina_mods_00308",2011:"leopoldina_mods_00992",2015:"leopoldina_mods_00454",2019:"leopoldina_mods_00323"}
UA="Mozilla/5.0 (compatible; bazi-public-figure-study/1.0)"
def one(item):
    y,obj=item
    u=f"https://levana.leopoldina.org/api/v2/objects/{obj}/derivates.json"
    try:
        req=urllib.request.Request(u,headers={"User-Agent":UA,"Accept":"application/json"})
        with urllib.request.urlopen(req,timeout=8) as r:
            b=r.read()
            return y,{"url":u,"status":r.status,"content_type":r.headers.get("Content-Type",""),"bytes":len(b),"body":b.decode("utf-8","replace")[:20000]}
    except Exception as e:
        return y,{"url":u,"status":getattr(e,"code",None),"error":f"{type(e).__name__}: {e}"}
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
    result=dict(ex.map(one,IDS.items()))
out=Path("data/leopoldina_levana_v2_fast_probe_v1");out.mkdir(parents=True,exist_ok=True)
(out/"probe.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(result,ensure_ascii=False,indent=2))
