#!/usr/bin/env python3
from __future__ import annotations
import csv,json,re,time,urllib.request,urllib.error
from html import unescape
from pathlib import Path
from urllib.parse import urljoin

BASE="https://www.leopoldina.org/en/members/member-list"
OUT=Path("data/leopoldina_roster_url_inventory_v1")
UA="Mozilla/5.0 (compatible; bazi-public-figure-study/1.0; reproducibility research)"

def fetch(url,tries=4):
    err=""
    for i in range(tries):
        try:
            req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"text/html,application/xhtml+xml"})
            with urllib.request.urlopen(req,timeout=40) as r:
                return r.status,r.geturl(),r.read().decode("utf-8","replace"),""
        except Exception as e:
            err=f"{type(e).__name__}: {e}"
            time.sleep(2**i)
    return None,url,"",err

def details(html,base):
    hrefs=[unescape(h) for h in re.findall(r'href=["\']([^"\']+)["\']',html,re.I)]
    urls=[urljoin(base,h).split("#")[0] for h in hrefs]
    return sorted(set(u for u in urls if re.search(r"/en/members/member-list/detail/[^/?#]+/?$",u)))

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    seen={}
    pages=[]
    stop_reason=""
    for page in range(1,401):
        url=BASE+"/" if page==1 else f"{BASE}?tx_solr%5Bpage%5D={page}"
        status,final_url,html,error=fetch(url)
        ds=details(html,final_url) if html else []
        new=[u for u in ds if u not in seen]
        pages.append({"page":page,"requested_url":url,"status":status or "","final_url":final_url,"detail_links":len(ds),"new_detail_links":len(new),"bytes":len(html.encode("utf-8")) if html else 0,"error":error})
        if error:
            stop_reason=f"fetch_error_page_{page}"
            break
        for u in new:
            seen[u]=page
        print(f"page={page} links={len(ds)} new={len(new)} cumulative={len(seen)}")
        if not ds:
            stop_reason=f"empty_page_{page}"
            break
        if not new:
            stop_reason=f"no_new_links_page_{page}"
            break
        if len(ds)<50:
            stop_reason=f"short_final_page_{page}"
            break
        time.sleep(0.25)
    else:
        stop_reason="max_page_guard"

    if len(seen)<1000:
        raise RuntimeError(f"Implausibly small Leopoldina URL inventory: {len(seen)}; stop={stop_reason}")

    rows=[{"member_slug":u.rstrip("/").split("/")[-1],"detail_url":u,"first_seen_page":seen[u]} for u in sorted(seen)]
    with (OUT/"member_urls_v1.csv").open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=["member_slug","detail_url","first_seen_page"]); w.writeheader(); w.writerows(rows)
    with (OUT/"page_audit_v1.csv").open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(pages[0])); w.writeheader(); w.writerows(pages)
    summary={
      "dataset":"Leopoldina official member URL inventory v1",
      "source":"Official Leopoldina English member directory, unfiltered pagination",
      "unique_member_detail_urls":len(rows),
      "pages_requested":len(pages),
      "last_page":pages[-1]["page"],
      "last_page_detail_links":pages[-1]["detail_links"],
      "stop_reason":stop_reason,
      "all_http_success":all(str(p["status"])=="200" for p in pages),
      "class_filter_not_used":"Direct class-filter query returned 403 in the discovery probe; cohort class will instead be assigned from each official member detail page section using the pre-frozen section-to-class map.",
      "dob_lookup_performed":0,
      "bazi_variables_computed":0
    }
    (OUT/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
