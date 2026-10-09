#!/usr/bin/env python3
from __future__ import annotations
import csv, hashlib, html, json, re
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse

IN=Path("data/royal_society_consolidation_inputs_v1")
OUT=Path("data/royal_society_roster_consolidated_v1")

def sha256(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for c in iter(lambda:f.read(1<<20),b""):h.update(c)
    return h.hexdigest()

def find_one(name):
    xs=list(IN.rglob(name))
    if len(xs)!=1:raise RuntimeError(f"Expected exactly one {name}, found {len(xs)}: {xs}")
    return xs[0]

def read_csv(p):
    with p.open("r",encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))

class PageParser(HTMLParser):
    def __init__(self):
        super().__init__();self.links=[];self.in_table=False;self.table_id="";self.in_tr=False;self.in_cell=False;self.cell=[];self.current_row=[];self.rows=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=="a" and a.get("href"):self.links.append((a["href"],""))
        elif tag=="table":self.in_table=True;self.table_id=a.get("id","")
        elif self.in_table and self.table_id=="overviewlist" and tag=="tr":self.in_tr=True;self.current_row=[]
        elif self.in_tr and tag in ("td","th"):self.in_cell=True;self.cell=[]
        elif self.in_cell and tag=="br":self.cell.append(" ")
    def handle_data(self,data):
        if self.in_cell:self.cell.append(data)
        if self.links:
            h,t=self.links[-1];self.links[-1]=(h,t+data)
    def handle_endtag(self,tag):
        if self.in_cell and tag in ("td","th"):
            self.current_row.append(re.sub(r"\s+"," ",html.unescape("".join(self.cell))).strip());self.in_cell=False
        elif self.in_tr and tag=="tr":
            if self.current_row:self.rows.append(self.current_row)
            self.in_tr=False
        elif self.in_table and tag=="table":self.in_table=False;self.table_id=""

def parse_blank_html(p):
    text=p.read_text(encoding="utf-8",errors="replace")
    q=PageParser();q.feed(text)
    ids=[]
    for href,label in q.links:
        full=urljoin("https://catalogues.royalsociety.org/calmview/",html.unescape(href))
        if "Record.aspx" in full and "src=CalmView.Persons" in full:
            rid=(parse_qs(urlparse(full).query).get("id") or [""])[0]
            if rid:ids.append((rid,full))
    uniq=[];seen=set()
    for rid,full in ids:
        if rid not in seen:seen.add(rid);uniq.append((rid,full))
    rows=[r for r in q.rows if len(r)>=4 and str(r[0]).strip().lower()!="surname"]
    if len(uniq)!=3 or len(rows)!=3:
        raise RuntimeError(f"blank-election rows expected 3: ids={len(uniq)} table_rows={len(rows)}")
    out=[]
    for (rid,full),v in zip(uniq,rows):
        out.append({"record_id":rid,"display_name":v[1],"lifespan_text":v[2],"election_date_text":v[3],"election_year_query":"","record_url":full.split("&pos=",1)[0],"result_page":"1"})
    return out

def norm_name(s):
    s=html.unescape(str(s or "")).lower()
    s=re.sub(r"\b(?:sir|dame|lord|lady|professor|prof|dr)\b"," ",s)
    return re.sub(r"[^a-z0-9]+","",s)

def write_csv(path,rows,fields):
    with path.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore");w.writeheader();w.writerows(rows)

def main():
    if OUT.exists() and any(OUT.iterdir()):raise RuntimeError(f"Output dir nonempty: {OUT}")
    OUT.mkdir(parents=True,exist_ok=True)

    current=read_csv(find_one("fellow_current_roster.csv"))
    if len(current)!=1570 or len({r["profile_url"] for r in current})!=1570:
        raise RuntimeError(f"Current roster invariant failed: rows={len(current)} unique_urls={len({r['profile_url'] for r in current})}")

    base=[]
    for p in sorted(IN.rglob("past_fellows.csv")):
        # Include 4 broad ranges plus 3 one-year retries; distinguish by parent path.
        base.extend(read_csv(p))

    # Because failed broad-range years yielded no rows, the one-year retries can
    # simply be concatenated. Assert no duplicates instead of silently dropping.
    ids=[r["record_id"] for r in base]
    dup=[k for k,v in Counter(ids).items() if v>1]
    if dup:raise RuntimeError(f"Duplicate historical record IDs before blank-date append: {dup[:20]}")
    if len(base)!=7096:
        raise RuntimeError(f"Expected 7096 year-known past Fellows after retries, found {len(base)}")

    blank=parse_blank_html(find_one("blank_eq.html"))
    historical=base+blank
    hids=[r["record_id"] for r in historical]
    if len(historical)!=7099 or len(set(hids))!=7099:
        raise RuntimeError(f"Historical total invariant failed: rows={len(historical)} unique={len(set(hids))}")

    hist_by_name={}
    for r in historical:hist_by_name.setdefault(norm_name(r["display_name"]),[]).append(r)
    overlaps=[]
    for r in current:
        n=norm_name(r["display_name"])
        if n and n in hist_by_name:
            for h in hist_by_name[n]:
                overlaps.append({
                  "normalized_name":n,
                  "current_name":r["display_name"],"current_profile_url":r["profile_url"],
                  "historical_name":h["display_name"],"historical_record_id":h["record_id"],
                  "historical_lifespan":h["lifespan_text"],"historical_election_date":h["election_date_text"]
                })

    hist_fields=["record_id","display_name","lifespan_text","election_date_text","election_year_query","record_url","result_page"]
    write_csv(OUT/"royal_society_past_fellows_v1.csv",historical,hist_fields)
    write_csv(OUT/"royal_society_current_fellows_v1.csv",current,list(current[0].keys()))
    overlap_fields=["normalized_name","current_name","current_profile_url","historical_name","historical_record_id","historical_lifespan","historical_election_date"]
    write_csv(OUT/"current_past_name_overlap_review_v1.csv",overlaps,overlap_fields)

    combined=[]
    for r in historical:
        combined.append({"source_status":"past","source_id":r["record_id"],"display_name":r["display_name"],"election_date_text":r["election_date_text"],"lifespan_text":r["lifespan_text"],"source_url":r["record_url"]})
    for r in current:
        combined.append({"source_status":"current","source_id":r["profile_numeric_id"],"display_name":r["display_name"],"election_date_text":"","lifespan_text":"","source_url":r["profile_url"]})
    write_csv(OUT/"royal_society_fellow_roster_candidate_v1.csv",combined,["source_status","source_id","display_name","election_date_text","lifespan_text","source_url"])

    summary={
      "dataset":"Royal Society Fellow roster consolidation candidate v1",
      "current_fellows":len(current),
      "past_fellows":len(historical),
      "past_with_election_year":7096,
      "past_blank_election_date":3,
      "combined_source_rows":len(combined),
      "current_past_exact_normalized_name_overlap_pairs":len(overlaps),
      "historical_ids_unique":len(set(hids)),
      "current_profile_urls_unique":len({r["profile_url"] for r in current}),
      "historical_csv_sha256":sha256(OUT/"royal_society_past_fellows_v1.csv"),
      "current_csv_sha256":sha256(OUT/"royal_society_current_fellows_v1.csv"),
      "combined_csv_sha256":sha256(OUT/"royal_society_fellow_roster_candidate_v1.csv"),
      "dob_lookup_performed":0,
      "bazi_variables_computed":0,
      "freeze_ready": int(len(overlaps)==0),
      "note":"If normalized-name overlaps are nonzero, review them before freezing. Current profiles still require election-year metadata enrichment before final cohort closeout."
    }
    (OUT/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=="__main__":main()
