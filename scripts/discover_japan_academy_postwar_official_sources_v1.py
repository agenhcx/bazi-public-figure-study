#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,hashlib,json,re,time,urllib.parse,urllib.request,xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

SCRIPT_VERSION="japan-academy-postwar-official-source-discovery-v1"
SNAPSHOT_DATE="2026-10-15"
DEFAULT_INPUT=Path("data/japan_academy_imperial_section_adjudication_v1/unresolved_other_official_source_required_v1.csv")
DEFAULT_OUT=Path("data/japan_academy_postwar_official_source_discovery_v1")
SRU="https://ndlsearch.ndl.go.jp/api/sru"
NS={"sru":"http://www.loc.gov/zing/srw/"}
QUERIES=[
 ("q1_ichiran",'title="日本学士院一覧"'),
 ("q2_member_directory",'title="日本学士院会員名簿"'),
 ("q3_official_1979",'title="日本学士院" AND creator="日本学士院"'),
 ("q4_eighty_year_history",'title="日本学士院八十年史"'),
]
ANCHORS=[
 {"anchor_id":"japan_academy_official_publications","url":"https://www.japan-acad.go.jp/japanese/publishing/other.html","evidence":"Official page lists 日本学士院一覧 for 昭和23年～42年 (1948–1967) and 日本学士院 for 昭和54年 (1979)."},
 {"anchor_id":"ndl_research_navi","url":"https://ndlsearch.ndl.go.jp/rnavi/politics/public_officer/others","evidence":"NDL Research Navi identifies 日本学士院一覧 自昭和23年至昭和29年 as a roster source."},
 {"anchor_id":"cinii_member_directory","url":"https://ci.nii.ac.jp/ncid/BB06030912","evidence":"CiNii bibliographic record for 日本学士院会員名簿, published by 日本学士院 from 1952.5-, with multiple dated volumes."},
]
PID_PATTERNS=[
 re.compile(r"https?://dl\.ndl\.go\.jp/(?:pid/)?(?P<pid>\d+)",re.I),
 re.compile(r"R100000039-I(?P<pid>\d+)",re.I),
 re.compile(r"\bpid[:/=](?P<pid>\d+)\b",re.I),
]

def read_csv(p):
 with p.open("r",encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
def write_csv(p,rows):
 p.parent.mkdir(parents=True,exist_ok=True)
 fields=list(rows[0].keys()) if rows else []
 with p.open("w",encoding="utf-8-sig",newline="") as f:
  w=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore");w.writeheader();w.writerows(rows)
def write_json(p,obj):
 p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
def sha(b):return hashlib.sha256(b).hexdigest()
def sha_file(p):
 h=hashlib.sha256()
 with p.open("rb") as f:
  for c in iter(lambda:f.read(1<<20),b""):h.update(c)
 return h.hexdigest()
def lname(tag):return tag.rsplit("}",1)[-1] if "}" in tag else tag
def values(root):
 out={}
 for e in root.iter():
  k=lname(e.tag).lower();t=" ".join("".join(e.itertext()).split())
  if t:out.setdefault(k,[]).append(t)
  for a,v in e.attrib.items():
   if v:out.setdefault("@"+lname(a).lower(),[]).append(str(v))
 return out
def join(v,*keys):
 out=[]
 for k in keys:
  for x in v.get(k.lower(),[]):
   if x not in out:out.append(x)
 return " | ".join(out)
def pids(text):
 out=[]
 for pat in PID_PATTERNS:
  for m in pat.finditer(text or ""):
   x=m.group("pid")
   if x not in out:out.append(x)
 return out
def unpack(rd):
 if list(rd):return rd
 s=(rd.text or "").strip()
 return ET.fromstring(s) if s.startswith("<") else rd
def parse_sru(data,qid,q):
 root=ET.fromstring(data);n=root.find(".//sru:numberOfRecords",NS)
 total=int(n.text) if n is not None and (n.text or "").isdigit() else 0;rows=[]
 for rec in root.findall(".//sru:record",NS):
  rd=rec.find("sru:recordData",NS)
  if rd is None:continue
  v=values(unpack(rd));title=join(v,"title");creator=join(v,"creator");issued=join(v,"issued","date");ids=join(v,"identifier","description","@about","@resource")
  rows.append({"query_id":qid,"query":q,"title":title,"creator":creator,"issued_or_dates":issued,"identifiers_and_descriptions":ids,"pids":"|".join(pids(" | ".join([title,creator,issued,ids])))})
 return total,rows
def sru_url(q):
 return SRU+"?"+urllib.parse.urlencode({"operation":"searchRetrieve","version":"1.2","recordSchema":"dcndl","recordPacking":"xml","onlyBib":"true","maximumRecords":"200","query":q})
def fetch(url,cache,refresh=False):
 cache.mkdir(parents=True,exist_ok=True);k=sha(url.encode());bp=cache/(k+".body");mp=cache/(k+".json")
 if not refresh and bp.exists() and mp.exists():
  b=bp.read_bytes();m=json.loads(mp.read_text(encoding="utf-8"))
  if m.get("url")==url and m.get("sha256")==sha(b):return b,"cached_hash_verified"
 req=urllib.request.Request(url,headers={"User-Agent":"bazi-public-figure-study/1.0 (+research; noncommercial)"})
 with urllib.request.urlopen(req,timeout=45) as r:b=r.read()
 bp.write_bytes(b);mp.write_text(json.dumps({"url":url,"sha256":sha(b),"bytes":len(b)},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 return b,"fetched"
def classify(title,creator):
 if "日本学士院一覧" in title:return "official_postwar_ichiran"
 if "日本学士院会員名簿" in title:return "official_member_directory"
 if "日本学士院八十年史" in title:return "official_history_support"
 if re.sub(r"\s+","",title) in {"日本学士院","TheJapanAcademy1979"} and "日本学士院" in creator:return "official_general_publication"
 return "other_search_result"
def year(s):
 m=re.match(r"^\s*(\d{4})",s or "");return int(m.group(1)) if m else None
def partition(r):
 ey,ry=year(r.get("first_election_date","")),year(r.get("final_retirement_date",""))
 if ey is None:return "date_parse_review"
 if ry is None:ry=9999
 if ey<=1967 and ry>=1948:return "overlaps_1948_1967_ichiran_scope"
 if ey<=1984 and ry>=1968:return "post1967_pre1985_member_directory_scope"
 if ey>=1985:return "1985plus_official_web_or_later_directory_scope"
 if ry<1948:return "pre1948_gap_or_other_official_source"
 return "other_official_source_review"
def dedupe(rows):
 seen=set();out=[]
 for r in rows:
  k=(r["title"],r["creator"],r["issued_or_dates"],r["pids"])
  if k not in seen:seen.add(k);out.append(r)
 return out

def self_test():
 x='''<?xml version="1.0"?><searchRetrieveResponse xmlns="http://www.loc.gov/zing/srw/"><numberOfRecords>1</numberOfRecords><records><record><recordData><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/"><rdf:Description><dc:title>日本学士院一覧 昭和23-29年</dc:title><dc:creator>日本学士院</dc:creator><dcterms:description>https://dl.ndl.go.jp/pid/2934795</dcterms:description></rdf:Description></rdf:RDF></recordData></record></records></searchRetrieveResponse>'''.encode()
 n,r=parse_sru(x,"q",'title="日本学士院一覧"')
 assert n==1 and r[0]["pids"]=="2934795" and classify(r[0]["title"],r[0]["creator"])=="official_postwar_ichiran"
 assert partition({"first_election_date":"1950-01-01","final_retirement_date":"1970-01-01"})=="overlaps_1948_1967_ichiran_scope"
 print("SELF-TEST OK: SRU parsing, PID extraction, title classification, and member-era partition are consistent")

def run(inp,out,refresh=False,plan_only=False):
 if not inp.exists():raise FileNotFoundError(inp)
 members=read_csv(inp)
 if len(members)!=239:raise RuntimeError(f"Expected 239 unresolved members, found {len(members)}")
 out.mkdir(parents=True,exist_ok=True);parts=[]
 for r in members:
  parts.append({"member_key":r.get("member_key",""),"name_jp":r.get("name_jp",""),"name_en":r.get("name_en",""),"first_election_date":r.get("first_election_date",""),"final_retirement_date":r.get("final_retirement_date",""),"source_queue_status":r.get("source_queue_status",""),"postwar_source_partition":partition(r),"roster_acceptance_written":0,"dob_collection_started":0,"bazi_variables_computed":0})
 write_csv(out/"unresolved_member_postwar_source_partition_v1.csv",parts);write_json(out/"source_anchors_v1.json",ANCHORS)
 if plan_only:
  s={"dataset":SCRIPT_VERSION,"source_snapshot_date":SNAPSHOT_DATE,"input_unresolved_members":239,"member_partition_counts":dict(Counter(x["postwar_source_partition"] for x in parts)),"planned_sru_queries":len(QUERIES),"network_requested":0,"roster_rows_accepted":0,"final_roster_frozen":0,"dob_collection_started":0,"bazi_variables_computed":0}
  write_json(out/"summary.json",s);print(json.dumps(s,ensure_ascii=False,indent=2));return
 allr=[];qi=[];cache=out/"cache"/"sru"
 for qid,q in QUERIES:
  u=sru_url(q);b,state=fetch(u,cache,refresh);n,rows=parse_sru(b,qid,q);qi.append({"query_id":qid,"query":q,"url":u,"number_of_records_reported":n,"records_parsed":len(rows),"retrieval_state":state,"response_sha256":sha(b)});allr+=rows;time.sleep(.2)
 rows=dedupe(allr);en=[]
 for r in rows:en.append({**r,"source_class":classify(r["title"],r["creator"]),"digital_pid_count":len([x for x in r["pids"].split("|") if x]),"member_section_evidence_accepted":0})
 write_csv(out/"ndl_sru_query_inventory_v1.csv",qi);write_csv(out/"ndl_bibliographic_inventory_v1.csv",en);off=[r for r in en if r["source_class"]!="other_search_result"];write_csv(out/"official_postwar_publication_candidates_v1.csv",off)
 s={"dataset":SCRIPT_VERSION,"source_snapshot_date":SNAPSHOT_DATE,"input_unresolved_members":239,"member_partition_counts":dict(Counter(x["postwar_source_partition"] for x in parts)),"sru_queries":len(QUERIES),"sru_records_before_dedup":len(allr),"bibliographic_records_after_dedup":len(en),"source_class_counts":dict(Counter(x["source_class"] for x in en)),"official_publication_candidate_rows":len(off),"official_publication_candidates_with_digital_pid":sum(bool(x["pids"]) for x in off),"source_anchors":len(ANCHORS),"roster_rows_accepted":0,"final_roster_frozen":0,"dob_collection_started":0,"bazi_variables_computed":0,"input_sha256":{"unresolved_members":sha_file(inp)},"next_action":"Review publication candidates and digital availability; do not classify members yet."}
 write_json(out/"summary.json",s);print(json.dumps(s,ensure_ascii=False,indent=2))

def main():
 ap=argparse.ArgumentParser();ap.add_argument("--input",default=str(DEFAULT_INPUT));ap.add_argument("--out",default=str(DEFAULT_OUT));ap.add_argument("--refresh",action="store_true");ap.add_argument("--plan-only",action="store_true");ap.add_argument("--self-test",action="store_true");a=ap.parse_args()
 if a.self_test:self_test();return 0
 run(Path(a.input),Path(a.out),a.refresh,a.plan_only);return 0
if __name__=="__main__":raise SystemExit(main())
