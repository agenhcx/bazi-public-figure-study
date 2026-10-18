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
from france_academy_wikisource_election_rows_v1 import role_of,section_of,person_of,identity_key,extract_from_html

VERSION="france-academy-legacy-heading-wikisource-source-only-v1_4"
VOLUMES=[(1,1835),(42,1856),(43,1856),(91,1880),(182,1926)]
CTHS="data/france_academy_cths_profile_dob_harvest_v1/cths_dob_claims_all_targets_candidate_only_v1.csv"
OUT=Path("data/france_academy_wikisource_legacy_heading_pilot_v1")
FIELDS=["volume","year","elected_name_candidate","election_role_candidate","source_action_wording",
        "science_section_candidate","original_printed_volume_page",
        "source_table_url","source_html_sha256",
        "cths_562_exact_name_candidate_id","match_status",
        "source_evidence_tier","original_election_printed_page_opened",
        "official_membership_accepted","exact_dob_accepted","bazi_variables_computed"]
MEMBER={"FULL_SECTION_MEMBER","FULL_ACADEMICIAN_LIBRE","FULL_NONRESIDENT_MEMBER","FULL_SECTION_MEMBER_CONTEXTUAL_NOMINATION"}
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
def nominated_name_from_line(line):
    """Retrieve ONLY the named appointee preceding est nommé/e, not a predecessor."""
    raw=re.sub(r"\bM\.\s*\(\s*Monsieur\s*\)\s*","M. ",line,flags=re.I)
    m=re.search(r"\bM\.\s+(.{2,140}?)\s+est\s+nomm[ée]e?\b",raw,re.I)
    if not m:return ""
    result=" ".join(m.group(1).split()).strip(" ,;.-")
    return result if len(result)<=110 and " et " not in result.casefold() else ""

def nomination_role(line):
    """Explicit appointment predicate after est nommé, NEVER from heading alone.

    Bare 'à la place vacante dans la Section de Géométrie' is a
    CONTEXTUAL member nomination, not an independently verified full member.
    """
    m=re.search(r"\best\s+nomm[ée]e?\b",line,re.I)
    if not m:return ""
    tail=fold(re.split(r"\ben remplacement de\b|\bpar suite du deces de\b",line[m.end():],maxsplit=1,flags=re.I)[0])
    if re.search(r"\bcorrespondant(?:e)?\b",tail):return "CORRESPONDENT"
    if "associe etranger" in tail:return "FOREIGN_ASSOCIATE"
    if "academicien libre" in tail:return "FULL_ACADEMICIAN_LIBRE"
    if "membre non resid" in tail:return "FULL_NONRESIDENT_MEMBER"
    if re.search(r"\bmembre(?:s)?\s+de\s+l.academie\b|\bmembre\b",tail):return "FULL_SECTION_MEMBER"
    if re.search(r"\ba\s+la\s+place\s+vacante\s+dans\s+la\s+section\b",tail):
        return "FULL_SECTION_MEMBER_CONTEXTUAL_NOMINATION"
    return "NOMINATION_UNKNOWN_MEMBER_CLASS_MANUAL"

def nomination_section(line):
    m=re.search(r"\bsection\s+(?:de\s+|d['’])(.+?)(?:\s+par\s+suite\b|\s+en\s+remplacement\b|[,.;]|$)",line,re.I)
    return " ".join(m.group(1).split())[:90] if m else ""

def parse_html(raw,volume,year):
    """Parse either legacy div.tableItem or modern table tr without double counting."""
    soup=BeautifulSoup(raw,"html.parser")
    content=soup.select_one(".mw-parser-output") or soup
    events=[];headings=[]
    old,modern_headings=extract_from_html(raw,year,volume)
    if old:
        # Reuse the already regression-tested 20th-century parser, including
        # reconstructed pages that were split across adjacent index lines.
        for x in old:
            events.append({"volume":str(volume),"year":str(year),
                  "elected_name_candidate":x["transcribed_elected_person_name"],
                  "election_role_candidate":x["transcribed_election_type"],
                  "source_action_wording":"EST_ELU_TRANSCRIBED",
                  "science_section_candidate":x["transcribed_science_section"],
                  "original_printed_volume_page":x["printed_election_page"],
                  "source_evidence_tier":"WIKISOURCE_INDEX_TRANSCRIPTION_NOT_ORIGINAL_EVENT_PAGE",
                  "original_election_printed_page_opened":"0",
                  "official_membership_accepted":"0","exact_dob_accepted":"0",
                  "bazi_variables_computed":"0"})
        return events,[h for h in modern_headings if h.startswith(("election","nomination"))]
    if soup.select("div.tableItem"):
        logical=[]
        for item in soup.select("div.tableItem"):
            div=item.select_one(".ws-titrex")
            if div is None:continue
            line=" ".join(div.get_text(" ",strip=True).split())
            # A legacy tableItem's "ws-titpge" contains title plus final page,
            # not necessarily a single td separate from title.
            pg=item.select_one(".ws-titpge")
            full=" ".join(pg.get_text(" ",strip=True).split()) if pg else ""
            match=re.search(r"\b(\d{1,5})\s*$",full)
            page=match.group(1) if match else ""
            sc=div.find("span",class_=re.compile("sc",re.I))
            header=" ".join(sc.get_text(" ",strip=True).split()) if sc else ""
            logical.append((line,page,header))
    else:
        logical=[]
        for tr in content.find_all("tr"):
            cells=tr.find_all("td",recursive=False)
            if not cells:continue
            line=" ".join(cells[0].get_text(" ",strip=True).split())
            page=" ".join(cells[1].get_text(" ",strip=True).split()) if len(cells)>1 else ""
            if not re.fullmatch(r"\d{1,5}",page):page=""
            span=cells[0].find("span",class_=re.compile("sc",re.I))
            header=" ".join(span.get_text(" ",strip=True).split()) if span else ""
            logical.append((line,page,header))
    in_events=False
    for line,page,decorated in logical:
        if not line:continue
        # The heading is typically a decorated smallcaps span, but the
        # earliest years may show raw "Élections. — ..." in ws-titrex.
        head_candidate=decorated or (line.split(".",1)[0] if "—" in line else "")
        if event_heading(head_candidate):
            in_events=True
            headings.append(head_candidate[:120])
        elif decorated and not event_heading(decorated):
            in_events=False
        elif line.startswith(("Candidatures.","Prix.","Décrets.","Décret.","Nécrologie.","Décès.")):
            in_events=False
        if not in_events:continue
        nominated=bool(re.search(r"\best\s+nomm[ée]e?\b",line,re.I))
        elected=bool(re.search(r"\b(est|a été|sont)\s+élu",line,re.I))
        if not (nominated or elected):continue
        role=nomination_role(line) if nominated else role_of(line)
        if not role:continue
        name=nominated_name_from_line(line) if nominated else name_from_line(line)
        events.append({"volume":str(volume),"year":str(year),
          "elected_name_candidate":name,"election_role_candidate":role,
          "source_action_wording":"EST_NOMME_TRANSCRIBED" if nominated else "EST_ELU_TRANSCRIBED",
          "science_section_candidate":(nomination_section(line) if nominated else section_of(line).strip(" )")),
          "original_printed_volume_page":page if re.fullmatch(r"\d{1,5}",page) else "",
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
    early="""<div class="mw-parser-output">
       <div class="tableItem"><div class="ws-titpge"><div class="ws-titrex">
       <span class="sc">Élections</span>. — M. Élie de Beaumont est élu membre de l’Académie des Sciences
       (section de minéralogie et de géologie), en remplacement de M. Lelièvre.
       </div> 515 </div></div>
       <div class="tableItem"><div class="ws-titpge"><div class="ws-titrex">
       <span class="sc">Électricité</span>. — Sur le courant.
       </div> 16 </div></div></div>"""
    legacy,h2=parse_html(early.encode(),1,1835)
    assert len(legacy)==1,(legacy,h2)
    assert legacy[0]["elected_name_candidate"]=="Élie de Beaumont",legacy
    assert legacy[0]["original_printed_volume_page"]=="515",legacy
    assert legacy[0]["election_role_candidate"]=="FULL_SECTION_MEMBER",legacy
    outside=early.replace('<div class="mw-parser-output">','<main class="content">').replace('</div></div></div>','</div></div></main>')
    assert len(parse_html(outside.encode(),1,1835)[0])==1
    nomination_html="""<table>
       <tr><td><span class="sc">NOMINATIONS de Membres et de Correspondants de l’Académie.</span> — M. Hermite est nommé à la place vacante dans la Section de Géométrie par suite du décès de M. Binet</td><td>85</td></tr>
       <tr><td>— M. W. Hooker est nommé Correspondant de l’Académie, Section de Botanique, en remplacement de M. Wallich</td><td>1143</td></tr>
       <tr><td><span class="sc">Sections de l’académie.</span> — M. Serret est candidat à la place vacante</td><td>61</td></tr>
       <tr><td><span class="sc">Nominations</span>. — M. Guyon est nommé Correspondant pour la Section de Médecine</td><td>378</td></tr>
       <tr><td><span class="sc">Décrets impériaux.</span> — Décret confirmant la nomination de M. Hermite</td><td>169</td></tr></table>"""
    nominated,nomheads=parse_html(nomination_html.encode("utf-8"),43,1856)
    assert len(nominated)==3,(nominated,nomheads)
    assert [x["elected_name_candidate"] for x in nominated]==["Hermite","W. Hooker","Guyon"]
    assert [x["election_role_candidate"] for x in nominated]==[
        "FULL_SECTION_MEMBER_CONTEXTUAL_NOMINATION","CORRESPONDENT","CORRESPONDENT"]
    assert nominated[0]["original_printed_volume_page"]=="85"
    assert nominated[0]["source_action_wording"]=="EST_NOMME_TRANSCRIBED"
    assert nominated[0]["science_section_candidate"]=="Géométrie"
    assert all(x["official_membership_accepted"]=="0" for x in nominated)
    print("PASS: 1835 election, 1856 est nommé in nominations, 1880/1926 elections; candidatures/decrees excluded")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--fixture-check",action="store_true")
    ap.add_argument("--out",type=Path,default=OUT)
    ap.add_argument("--limit",type=int,default=4)
    ap.add_argument("--delay",type=float,default=1.3)
    args=ap.parse_args()
    if args.fixture_check:return fixture()
    if not 1<=args.limit<=5 or args.delay<1.1:raise ValueError("Bounded up to 5 source volumes")
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
