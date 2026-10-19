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

VERSION="france-academy-legacy-heading-wikisource-source-only-v1_7"
VOLUMES=[(1,1835),(42,1856),(43,1856),(91,1880),(182,1926)]
CTHS="data/france_academy_cths_profile_dob_harvest_v1/cths_dob_claims_all_targets_candidate_only_v1.csv"
OUT=Path("data/france_academy_wikisource_legacy_heading_pilot_v1")
FIELDS=["volume","year","elected_name_candidate","election_role_candidate","source_action_wording",
        "science_section_candidate","original_printed_volume_page","source_printed_page_references",
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
    x=" ".join(fold(s).strip(" .:—-").split())
    # Heading classification is EXACT, so "Nominations de candidats"
    # cannot start a false election section.
    # 1884/1899 omit "de" before correspondants, 1853 has just "Nominations".
    pat=r"^(?:elections?|nominations?)(?: de membres(?: et (?:de )?correspondants(?: de l.academie)?)?)?$"
    return bool(re.fullmatch(pat,x))
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

def page_references(s):
    """Keep multi-page original TOC locators as ONE event, e.g. 510 et 618."""
    original=" ".join(str(s or "").split())
    if not re.fullmatch(r"\d{1,5}(?:\s*(?:,|;|et)\s*\d{1,5})*",original,re.I):
        return ("",original[:90])
    nums=re.findall(r"\d{1,5}",original)
    return (nums[0],"|".join(nums))

def parse_html(raw,volume,year):
    """Parse TR and div.tableItem representations independently and deduplicate.

    Some Wikisource historical pages (e.g. Tome 42/1856) contain BOTH:
    choosing div.tableItem if one exists drops the actual election records
    stored in the <tr> table. Preserve the tested modern index parser's
    reconstructed page numbers as the first source of election records.
    """
    soup=BeautifulSoup(raw,"html.parser")
    events=[];headings=[]
    old,modern_headings=extract_from_html(raw,year,volume)
    for x in old:
        events.append({"volume":str(volume),"year":str(year),
             "elected_name_candidate":x["transcribed_elected_person_name"],
             "election_role_candidate":x["transcribed_election_type"],
             "source_action_wording":"EST_ELU_TRANSCRIBED",
             "science_section_candidate":x["transcribed_science_section"],
             "original_printed_volume_page":x["printed_election_page"],
             "source_printed_page_references":x["printed_election_page"],
             "source_evidence_tier":"WIKISOURCE_INDEX_TRANSCRIPTION_NOT_ORIGINAL_EVENT_PAGE",
             "original_election_printed_page_opened":"0",
             "official_membership_accepted":"0","exact_dob_accepted":"0",
             "bazi_variables_computed":"0"})
    headings.extend(h for h in modern_headings if h.startswith(("election","nomination")))

    # List two distinct possible containers, neither supersedes the other.
    table_rows=[]
    for tr in soup.find_all("tr"):
        cells=tr.find_all("td",recursive=False)
        if not cells:continue
        first=cells[0]
        line=" ".join(first.get_text(" ",strip=True).split())
        page=" ".join(cells[1].get_text(" ",strip=True).split()) if len(cells)>1 else ""
        page,page_refs=page_references(page)
        sc=first.find("span",class_=re.compile(r"sc",re.I))
        heading=" ".join(sc.get_text(" ",strip=True).split()) if sc else ""
        table_rows.append((line,page,heading,page_refs))
    legacy_rows=[]
    for item in soup.select("div.tableItem"):
        div=item.select_one(".ws-titrex")
        if div is None:continue
        line=" ".join(div.get_text(" ",strip=True).split())
        page_container=item.select_one(".ws-titpge")
        full=" ".join(page_container.get_text(" ",strip=True).split()) if page_container else ""
        match=re.search(r"\b(\d{1,5})\s*$",full)
        page=match.group(1) if match else ""
        page_refs=page
        sc=div.find("span",class_=re.compile("sc",re.I))
        heading=" ".join(sc.get_text(" ",strip=True).split()) if sc else ""
        legacy_rows.append((line,page,heading,page_refs))

    def add_unique(candidate):
        # Duplicate markup or a modern indexed row plus our fallback may
        # repeat the exact SAME person and role. Keep the record with
        # its recovered page; if two nonempty DIFFERENT pages occur,
        # retain both as separate manual-review events.
        for x in events:
            if (fold(x["elected_name_candidate"])==fold(candidate["elected_name_candidate"]) and
                x["election_role_candidate"]==candidate["election_role_candidate"] and
                x["source_action_wording"]==candidate["source_action_wording"]):
                p1=x["original_printed_volume_page"]
                p2=candidate["original_printed_volume_page"]
                if not p1 or not p2 or p1==p2:
                    if not p1 and p2:x["original_printed_volume_page"]=p2
                    if not x.get("source_printed_page_references") and candidate.get("source_printed_page_references"):
                        x["source_printed_page_references"]=candidate["source_printed_page_references"]
                    return
        events.append(candidate)

    for logical in (table_rows,legacy_rows):
        in_events=False
        for line,page,decorated,page_refs in logical:
            if not line:continue
            prefix=line.split("—",1)[0].strip(" .")
            head_candidate=prefix if event_heading(prefix) else decorated
            is_named_correspondent_nomination=bool(
                fold(decorated).strip(" .")=="nominations" and
                re.search(r"\best\s+nomm[ée]e?\b",line,re.I) and
                re.search(r"\bcorrespondant\b",line,re.I))
            if event_heading(head_candidate) or is_named_correspondent_nomination:
                in_events=True
                header=head_candidate if event_heading(head_candidate) else prefix
                if header not in headings:headings.append(header[:120])
            elif decorated:
                in_events=False
            elif fold(prefix).startswith(("candidatures","prix","decrets","decret","necrologie","deces")):
                in_events=False
            if not in_events:continue
            nominated=bool(re.search(r"\best\s+nomm[ée]e?\b",line,re.I))
            elected=bool(re.search(r"\b(est|a été|sont)\s+élu",line,re.I))
            if not (nominated or elected):continue
            role=nomination_role(line) if nominated else role_of(line)
            if not role:continue
            name=nominated_name_from_line(line) if nominated else name_from_line(line)
            # Quarantine unparsed identities; do not infer people from heading.
            if not name:continue
            candidate={"volume":str(volume),"year":str(year),
                "elected_name_candidate":name,"election_role_candidate":role,
                "source_action_wording":"EST_NOMME_TRANSCRIBED" if nominated else "EST_ELU_TRANSCRIBED",
                "science_section_candidate":(nomination_section(line) if nominated else section_of(line).strip(" )")),
                "original_printed_volume_page":page,
                "source_printed_page_references":page_refs,
                "source_evidence_tier":"WIKISOURCE_INDEX_TRANSCRIPTION_NOT_ORIGINAL_EVENT_PAGE",
                "original_election_printed_page_opened":"0",
                "official_membership_accepted":"0","exact_dob_accepted":"0",
                "bazi_variables_computed":"0"}
            add_unique(candidate)
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
    assert len(h)>=2 and any('nomination' in fold(x) for x in h),(e,h)
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
    mixed=('<div class="tableItem"><div class="ws-titrex">Unrelated botanical index</div></div>'+nomination_html)
    mixed_results,_=parse_html(mixed.encode("utf-8"),43,1856)
    assert len(mixed_results)==len(nominated),(mixed_results,nominated)
    assert [x["elected_name_candidate"] for x in mixed_results]==["Hermite","W. Hooker","Guyon"]
    assert all(x["original_election_printed_page_opened"]=="0" for x in mixed_results)
    assert page_references("510 et 618")==("510","510|618")
    assert page_references("725 et 798")==("725","725|798")
    assert page_references("509")==("509","509")
    headings_variant="""<table>
      <tr><td><span class="sc">Nominations de membres et correspondants de l’académie.</span> — M. Haton de la Goupillière est élu Membre libre en remplacement de feu M. de la Gournerie</td><td>131</td></tr>
      <tr><td>— M. Darboux est élu Membre de la Section de Géométrie, en remplacement de M. Puiseux</td><td>552</td></tr>
      <tr><td>— M. Salmon est élu Correspondant, pour la Section de Géométrie, en remplacement de M. Spottiswoode</td><td>1516</td></tr>
      <tr><td><span class="sc">Astrologie.</span> — M. Faussaire est élu membre du Jury des prix</td><td>1517</td></tr>
      </table>"""
    variant,_=parse_html(headings_variant.encode("utf-8"),98,1884)
    assert [(r["elected_name_candidate"],r["election_role_candidate"]) for r in variant]==[
        ("Haton de la Goupillière","FULL_ACADEMICIAN_LIBRE"),
        ("Darboux","FULL_SECTION_MEMBER"),("Salmon","CORRESPONDENT")],variant
    office_html="""<table><tr><td><span class="sc">Nominations.</span> — M. Élie de Beaumont est élu à la place de Secrétaire perpétuel pour les Sciences mathématiques</td><td>938</td></tr></table>"""
    office,_=parse_html(office_html.encode("utf-8"),37,1853)
    assert len(office)==1 and office[0]["election_role_candidate"]=="OFFICE_ELECTION_NOT_NEW_MEMBER",office
    assert event_heading("Nominations de membres et correspondants de l’académie.")
    assert not event_heading("Nominations de candidats aux concours")


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
