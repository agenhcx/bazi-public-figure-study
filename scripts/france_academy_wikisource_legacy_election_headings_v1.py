#!/usr/bin/env python3
"""Repair pre-1914 French Academy historical election-title recognition.

Source: public Wikisource table-of-contents TRANSCRIPT of Academy historical
Comptes rendus, not the opened physical pages. This overlays only a few
bounded volumes and never alters the 41-event frozen five-volume pilot.

1) Section heading "Élections" or "Nominations de membres et correspondants".
2) Earliest print uses "M. (Monsieur) [name] est élu" abbreviation.
3) Royal decrees, applications, replacements, awards and office votes are
   explicitly different categories from an Academy full-member election.
"""
from __future__ import annotations
import argparse,csv,hashlib,json,re,time,unicodedata,urllib.error
from collections import Counter,defaultdict
from pathlib import Path
from bs4 import BeautifulSoup
from france_academy_wikisource_index_preflight_v1 import build_urls,read_one
from france_academy_wikisource_election_rows_v1 import role_of,section_of,person_of,identity_key

VERSION="france-academy-legacy-heading-wikisource-source-only-v1"
VOLUMES=[(1,1835),(54,1862),(91,1880),(182,1926)]
CTHS="data/france_academy_cths_profile_dob_harvest_v1/cths_dob_claims_all_targets_candidate_only_v1.csv"
OUT=Path("data/france_academy_wikisource_legacy_heading_pilot_v1")
FIELDS=["volume","year","elected_name_candidate","election_role_candidate",
        "science_section_candidate","original_printed_volume_page",
        "source_table_url","source_html_sha256",
        "cths_562_exact_name_candidate_id","match_status",
        "source_evidence_tier","original_election_printed_page_opened",
        "official_membership_accepted","exact_dob_accepted","bazi_variables_computed"]
MEMBER={"FULL_SECTION_MEMBER","FULL_ACADEMICIAN_LIBRE","FULL_NONRESIDENT_MEMBER"}
CORR={"CORRESPONDENT","FOREIGN_ASSOCIATE"}
def fold(s):
    s=unicodedata.normalize("NFKD",str(s).casefold())
    return "".join(c for c in s if not unicodedata.combining(c))
def event_heading(s):
    x=fold(s)
    return bool(re.match(r"^(?:elections?(?: de membres)?|nominations? de membres et de correspondants(?: de l.academie)?)\b",x))
def name_from_line(line):
    raw=re.sub(r"\bM\.\s*\(\s*Monsieur\s*\)\s*","M. ",line,flags=re.I)
    raw=re.sub(r"\bM\.\s*\(\s*M\.\s*\)\s*","M. ",raw,flags=re.I)
    return person_of(raw)
def parse_html(raw,volume,year):
    soup=BeautifulSoup(raw,"html.parser")
    content=soup.select_one(".mw-parser-output") or soup
    events=[];headings=[]
    in_events=False
    for tr in content.find_all("tr"):
        cells=tr.find_all("td",recursive=False)
        if not cells:continue
        line=" ".join(cells[0].get_text(" ",strip=True).split())
        if not line:continue
        span=cells[0].find("span",class_=re.compile(r"sc",re.I))
        decorated=" ".join(span.get_text(" ",strip=True).split()) if span else ""
        # Detect explicit subject headings, including raw "Élections." and
        # 1880 variant "Nominations de membres et de correspondants ..."
        heading_text=decorated or (line.split(". —",1)[0] if "—" in line else "")
        if event_heading(heading_text):
            in_events=True;headings.append(heading_text[:120])
        elif decorated and not event_heading(decorated):
            in_events=False
        elif (line.startswith(("Candidatures.","Prix.","Décrets.","Décret.","Nécrologie.","Décès."))
              or (line.startswith("Nominations.") and not event_heading(line))):
            in_events=False
        if not in_events:continue
        if not re.search(r"\b(est|a été|sont)\s+élu",line,re.I):continue
        role=role_of(line)
        if not role:return_ = ""  # prevent unclassified entries from auto-promoting
        else:return_ = role
        if not return_:continue
        name=name_from_line(line)
        page=" ".join(cells[1].get_text(" ",strip=True).split()) if len(cells)>1 else ""
        if not re.fullmatch(r"\d{1,5}",page):page=""
        events.append({"volume":str(volume),"year":str(year),
          "elected_name_candidate":name,"election_role_candidate":role,
          "science_section_candidate":section_of(line),
          "original_printed_volume_page":page,
          "source_evidence_tier":"WIKISOURCE_INDEX_TRANSCRIPTION_NOT_ORIGINAL_EVENT_PAGE",
          "original_election_printed_page_opened":"0",
          "official_membership_accepted":"0","exact_dob_accepted":"0",
          "bazi_variables_computed":"0"})
    return events,headings

def write_csv(p,rows,fields):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore")
        w.writeheader();w.writerows(rows)

def fixture():
    snippets="""<table>
    <tr><td>Élections. — M. (Monsieur) Élie de Beaumont est élu membre de l'Académie des Sciences (section de minéralogie et de géologie), en remplacement de M. Lelièvre</td><td>515</td></tr>
    <tr><td><span class="sc">Nominations de membres et de correspondants de l'académie.</span> — M. Brioschi est élu Correspondant pour la Section de Géométrie, en remplacement de M. Borchardt.</td><td>903</td></tr>
    <tr><td>— M. Abria est élu Correspondant pour la Section de Physique.</td><td>960</td></tr>
    <tr><td><span class="sc">Décrets.</span> — Approuvant l'élection de M. Brioschi</td><td>981</td></tr>
    <tr><td>— M. Le Maire est élu membre de la Commission des prix</td><td>997</td></tr></table>"""
    e,h=parse_html(snippets.encode(),91,1880)
    assert len(e)==3,(e,h)
    assert e[0]["elected_name_candidate"]=="Élie de Beaumont",e
    assert e[0]["election_role_candidate"]=="FULL_SECTION_MEMBER",e
    assert e[1]["election_role_candidate"]=="CORRESPONDENT",e
    assert e[2]["original_printed_volume_page"]=="960",e
    assert len(h)==2
    assert all(x["official_membership_accepted"]=="0" for x in e)
    print("PASS: 1835 Élections, 1880 Nominations, Monsieur abbreviation, decrees and office votes separated")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--fixture-check",action="store_true")
    ap.add_argument("--out",type=Path,default=OUT)
    ap.add_argument("--limit",type=int,default=4)
    ap.add_argument("--delay",type=float,default=1.3)
    args=ap.parse_args()
    if args.fixture_check:return fixture()
    if not 1<=args.limit<=4 or args.delay<1.1:raise ValueError("Bounded up to 4 source volumes")
    with open(CTHS,encoding="utf-8-sig",newline="") as f:cths=list(csv.DictReader(f))
    if len(cths)!=562:raise RuntimeError("Unchanged CTHS historical source required")
    match=defaultdict(list)
    for r in cths:match[identity_key(r["name"])].append(r["cths_person_id"])
    rows=[];pervolume=[]
    for i,(v,y) in enumerate(VOLUMES[:args.limit]):
        url=build_urls(v,y)["wiki"]
        try:
            status,mime,raw=read_one(url,800000)
            events,heads=parse_html(raw,v,y)
            for ev in events:
                ids=match.get(identity_key(ev["elected_name_candidate"]),[])
                ev["source_table_url"]=url
                ev["source_html_sha256"]=hashlib.sha256(raw).hexdigest()
                ev["cths_562_exact_name_candidate_id"]=ids[0] if len(ids)==1 else ""
                ev["match_status"]="ONE_EXACT_CTHS_562_NAME_CANDIDATE" if len(ids)==1 else "NO_EXACT_MATCH" if not ids else "AMBIGUOUS_NAME"
                rows.append(ev)
            pervolume.append({"volume":v,"year":y,"status":status,"bytes":len(raw),
                "source_html_sha256":hashlib.sha256(raw).hexdigest(),"source_url":url,
                "recognized_election_headings":heads,
                "event_rows":len(events),"full_like_event_rows":sum(ev["election_role_candidate"] in MEMBER for ev in events),
                "corresponding_foreign_event_rows":sum(ev["election_role_candidate"] in CORR for ev in events),
                "unparsed_person_count":sum(not ev["elected_name_candidate"] for ev in events),
                "source_is_index_transcription_only":True})
        except (urllib.error.HTTPError,urllib.error.URLError,TimeoutError,ValueError) as exc:
            pervolume.append({"volume":v,"year":y,"status":"HTTP_"+str(exc.code) if isinstance(exc,urllib.error.HTTPError) else type(exc).__name__,
                              "error":str(exc)[:140],"event_rows":None,"unknown_not_zero":True})
        if i+1<args.limit:time.sleep(args.delay)
    out=args.out;out.mkdir(parents=True,exist_ok=True)
    write_csv(out/"historical_nominations_elections_candidates_v1.csv",rows,FIELDS)
    s={"version":VERSION,"source_volumes":[x["volume"] for x in pervolume],"source_checks":pervolume,
       "candidate_event_rows":len(rows),"full_like_event_candidates":sum(x["election_role_candidate"] in MEMBER for x in rows),
       "correspondent_foreign_candidates":sum(x["election_role_candidate"] in CORR for x in rows),
       "specific_frozen_1835_1880_names_not_study_accepted":True,
       "original_printed_event_pages_opened":0,"accepted_french_full_members":0,
       "accepted_study_birthdates":0,"bazi_variables_computed":0}
    (out/"summary.json").write_text(json.dumps(s,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    print("SUMMARY",json.dumps(s,ensure_ascii=False))
    print("PEOPLE",json.dumps([{"year":r["year"],"name":r["elected_name_candidate"],
                             "class":r["election_role_candidate"],"page":r["original_printed_volume_page"],
                             "cths_id":r["cths_562_exact_name_candidate_id"]} for r in rows],ensure_ascii=False))

if __name__=="__main__":main()
