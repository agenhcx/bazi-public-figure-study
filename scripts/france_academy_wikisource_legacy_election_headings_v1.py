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

VERSION="france-academy-legacy-heading-wikisource-source-only-v1_9"
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
    x=fold(s)
    # 98/128 omit the second "de"; 14 uses "ou de correspondants";
    # 74 explicitly inserts "d'associés étrangers" in the membership list.
    return bool(re.match(
        r"^(?:elections?(?: de membres)?|nominations? de membres(?: "
        r"(?:et|ou) (?:de )?correspondants|,\s*d.associes etrangers et de correspondants)"
        r"(?: de l.academie)?)\b",x))
def name_from_line(line):
    raw=re.sub(r"\bM\.\s*\(\s*Monsieur\s*\)\s*","M. ",line,flags=re.I)
    raw=re.sub(r"\bM\.\s*\(\s*M\.\s*\)\s*","M. ",raw,flags=re.I)
    return person_of(raw)
def nominated_name_from_line(line):
    """Retrieve ONLY the named appointee preceding est nommé/e, not a predecessor."""
    raw=re.sub(r"\bM\.\s*\(\s*Monsieur\s*\)\s*","M. ",line,flags=re.I)
    m=re.search(r"\bM\.\s+(.{2,140}?)\s+est\s+nomm[ée]e?\b",raw,re.I)
    if not m:
        # Tome 44: "Le P. Secchi est nommé Correspondant". The absent M.
        # honorific must not erase this explicitly named appointment.
        m=re.search(r"\bLe\s+P\.\s+(.{2,140}?)\s+est\s+nomm[ée]e?\b",raw,re.I)
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
    if re.search(r"\ba\s+la\s+place\s+(?:devenue\s+)?vacante\s+dans\s+la\s+section\b",tail):
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

def explicit_named_academy_event(line):
    """Bare Nominations needs a named person AND explicit Academy role.

    Tome 40 opens with an appointed section member, while Tome 131 opens
    with an elected correspondent. A generic commission membership or an
    unknown role must not open the member-event scope.
    """
    nominated=bool(re.search(r"\best\s+nomm[ée]e?\b",line,re.I))
    name=nominated_name_from_line(line) if nominated else name_from_line(line)
    role=nomination_role(line) if nominated else role_of(line)
    if not name:return False
    if role in CORR|{"FULL_ACADEMICIAN_LIBRE","FULL_NONRESIDENT_MEMBER"}:
        return True
    if role!="FULL_SECTION_MEMBER":return False
    action=re.search(r"\best\s+(?:nomm[ée]e?|[ée]lue?)\b",line,re.I)
    if not action:return False
    clause=re.split(r"\ben remplacement\b",fold(line[action.end():]),maxsplit=1)[0]
    return bool(re.search(r"\bmembre\s+de\s+(?:la\s+section|l.academie)\b",clause))

def split_correspondent_row(tr,line,page):
    """Recover the observed Tome 131 transclusion split, without guessing.

    The last row of a table ends in 'M. Zambacco est élu'. Its explicit
    correspondent/section predicate is unwrapped text between that table
    and the next, whose first row contains only the printed page number.
    Require all three adjacent source fragments; otherwise leave unchanged.
    """
    if page or not re.search(r"\best\s+[ée]lue?\s*$",line,re.I):return line,page
    if not name_from_line(line):return line,page
    table=tr.find_parent("table")
    if table is None or table.find_all("tr")[-1] is not tr:return line,page
    pieces=[];following=None
    for i,sibling in enumerate(table.next_siblings):
        if i>=8:return line,page
        tag=getattr(sibling,"name",None)
        if tag=="table":following=sibling;break
        if tag not in (None,"span"):return line,page
        pieces.append(sibling.get_text(" ",strip=True) if tag else str(sibling))
    continuation=" ".join(" ".join(pieces).split())
    if following is None or not re.fullmatch(
            r"Correspondant\s+pour\s+la\s+Section\s+(?:de\s+|d['’])[^.;\d]+\.?",
            continuation,re.I):return line,page
    first_row=following.find("tr")
    if first_row is None:return line,page
    cells=first_row.find_all("td",recursive=False)
    if len(cells)!=1:return line,page
    number=cells[0].get_text(" ",strip=True)
    if not re.fullmatch(r"\d{1,5}",number):return line,page
    return line+" "+continuation,number

def literal_wikitable_rows(soup):
    """Read the explicit unrendered membership table observed in Tome 74.

    Require a recognized small-cap membership heading outside an existing
    TR/tableItem and literal wikitable row/cell delimiters in its paragraph.
    Stop at the next subject and require an explicit numeric page cell;
    partial or unrelated prose must not become an inferred election row.
    """
    rows=[];seen=set()
    for sc in soup.find_all("span",class_=re.compile(r"sc",re.I)):
        heading=" ".join(sc.get_text(" ",strip=True).split())
        if not event_heading(heading):continue
        if sc.find_parent("tr") or sc.find_parent("div",class_="tableItem"):continue
        paragraph=sc.find_parent("p")
        if paragraph is None or id(paragraph) in seen:continue
        seen.add(id(paragraph))
        text=paragraph.get_text(" ",strip=True)
        if "|-" not in text:continue
        active=False
        for piece in re.split(r"\|\s*-\s*",text):
            piece=piece.strip()
            if not piece.startswith("|"):continue
            cells=piece[1:].strip().rsplit("|",1)
            line=" ".join(cells[0].split())
            prefix=line.split("—",1)[0].strip(" .")
            starts=event_heading(prefix)
            if starts:active=True
            elif not active:continue
            elif not line.startswith("—"):break
            page,refs=page_references(cells[1] if len(cells)==2 else "")
            if not page:
                if starts:rows.append((prefix,"",prefix,""))
                continue
            rows.append((line,page,prefix if starts else "",refs))
    return rows

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
        line,page=split_correspondent_row(tr,line,page)
        page,page_refs=page_references(page)
        sc=first.find("span",class_=re.compile(r"sc",re.I))
        heading=" ".join(sc.get_text(" ",strip=True).split()) if sc else ""
        table_rows.append((line,page,heading,page_refs))
    legacy_rows=[]
    for item in soup.select("div.tableItem"):
        # Tome 14 uses the same page container with ws-titre, not ws-titrex.
        # Prefer the established layout when both are present.
        div=item.select_one(".ws-titrex") or item.select_one(".ws-titre")
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

    for logical in (table_rows,legacy_rows,literal_wikitable_rows(soup)):
        in_events=False
        office_only=False
        for line,page,decorated,page_refs in logical:
            if not line:continue
            prefix=line.split("—",1)[0].strip(" .")
            head_candidate=prefix if event_heading(prefix) else decorated
            is_named_member_nomination=bool(
                fold(decorated).strip(" .")=="nominations" and
                explicit_named_academy_event(line))
            # Tome 37 p938 has a bare Nominations heading for an explicit
            # secretary election. It opens only an OFFICE scope: it must not
            # make bare nominations a generic source of new full members.
            is_named_office_election=bool(
                fold(decorated).strip(" .")=="nominations" and
                role_of(line)=="OFFICE_ELECTION_NOT_NEW_MEMBER" and
                name_from_line(line))
            if event_heading(head_candidate) or is_named_member_nomination or is_named_office_election:
                in_events=True
                office_only=is_named_office_election and not event_heading(head_candidate)
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
            if office_only and role!="OFFICE_ELECTION_NOT_NEW_MEMBER":continue
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

    # Source-derived regression: both readable TOCs formerly returned zero
    # people because their heading says "et correspondants", without "de".
    # Preserve the transcribed names, class distinctions and original pages.
    tome98="""<table>
       <tr><td><span class="sc">Nominations de membres et correspondants de l’académie.</span> — M. Haton de la Goupillière est élu Membre libre en remplacement de feu M. de la Gournerie</td><td>131</td></tr>
       <tr><td>— M. Darboux est élu Membre de la Section de Géométrie, en remplacement de M. Puiseux</td><td>552</td></tr>
       <tr><td>— M. de Jonquières est élu Membre libre, en remplacement de feu M. Breguet</td><td>713</td></tr>
       <tr><td>— M. Bouquet de la Grye est élu Membre de la Section de Géographie et Navigation, en remplacement de feu M. Yvon Villarceau</td><td>865</td></tr>
       <tr><td>— M. Cailletet est élu Membre libre, en remplacement de feu M. du Moncel</td><td>1311</td></tr>
       <tr><td>— M. Salmon est élu Correspondant, pour la Section de Géométrie, en remplacement de feu M. Spottiswoode</td><td>1516</td></tr>
       <tr><td><span class="sc">Observatoires.</span> — Nécessité de la création d’une succursale de l’Observatoire hors de Paris. Note de M. Mouchez</td><td>257</td></tr></table>"""
    recovered98,_=parse_html(tome98.encode("utf-8"),98,1884)
    assert [(r["elected_name_candidate"],r["election_role_candidate"],r["original_printed_volume_page"]) for r in recovered98]==[
        ("Haton de la Goupillière","FULL_ACADEMICIAN_LIBRE","131"),
        ("Darboux","FULL_SECTION_MEMBER","552"),
        ("de Jonquières","FULL_ACADEMICIAN_LIBRE","713"),
        ("Bouquet de la Grye","FULL_SECTION_MEMBER","865"),
        ("Cailletet","FULL_ACADEMICIAN_LIBRE","1311"),
        ("Salmon","CORRESPONDENT","1516")],recovered98
    tome128="""<table>
       <tr><td><span class="sc">Nominations de membres et correspondants de l’académie.</span> — M. Mendelejeff est élu Correspondant pour la Section de Chimie, en remplacement de M. Kékulé</td><td>215</td></tr>
       <tr><td>— M. Roux est élu Membre de la Section d’Économie rurale, en remplacement de feu M. Aimé Girard</td><td>268</td></tr>
       <tr><td>— M. Ray Lankester est élu Correspondant pour la Section d’Anatomie et Zoologie, en remplacement de M. Loven</td><td>543</td></tr>
       <tr><td>— M. Lortet est élu Correspondant pour la Section d’Anatomie et Zoologie, en remplacement de M. Steenstrup</td><td>543</td></tr>
       <tr><td>— M. Helmert est élu Correspondant pour la Section de Géographie et Navigation, en remplacement de Sir George-Henry Richards</td><td>582</td></tr>
       <tr><td>— Le R. P. Colin est élu Correspondant pour la Section de Géographie et Navigation, en remplacement de M. Manen</td><td>656</td></tr>
       <tr><td>— M. Prillieux est élu Membre de la Section de Botanique, en remplacement de M. Naudin</td><td>1146</td></tr>
       <tr><td><span class="sc">Observatoires.</span> — Note de M. Faye, accompagnant la présentation du Tome I des Annales de l’Observatoire de Nice</td><td>265</td></tr>
       <tr><td>— Le R. P. Autre est élu Membre de la commission locale</td><td>266</td></tr></table>"""
    recovered128,_=parse_html(tome128.encode("utf-8"),128,1899)
    assert [(r["elected_name_candidate"],r["election_role_candidate"],r["original_printed_volume_page"]) for r in recovered128]==[
        ("Mendelejeff","CORRESPONDENT","215"),
        ("Roux","FULL_SECTION_MEMBER","268"),
        ("Ray Lankester","CORRESPONDENT","543"),
        ("Lortet","CORRESPONDENT","543"),
        ("Helmert","CORRESPONDENT","582"),
        ("Colin","CORRESPONDENT","656"),
        ("Prillieux","FULL_SECTION_MEMBER","1146")],recovered128
    assert all(r[field]=="0" for r in recovered98+recovered128 for field in (
        "original_election_printed_page_opened","official_membership_accepted",
        "exact_dob_accepted","bazi_variables_computed"))
    assert not event_heading("Nominations"),"Bare nominations still require an explicit bounded rule"
    tome37="""<table>
       <tr><td><span class="sc">Nominations</span>. — M. <i>Élie de Beaumont</i> est élu à la place de Secrétaire perpétuel pour les Sciences mathématiques, place vacante par suite du décès de M. <i>Arago</i></td><td>938</td></tr>
       <tr><td>— M. Faux est élu Membre de la Section de Géométrie</td><td>939</td></tr>
       <tr><td><span class="sc">Organographie et Organogénie végétales</span>. — Carpographie anatomique ; Note de M. Lestiboudois</td><td>69</td></tr></table>"""
    # The synthetic next member line tests the deliberately restricted office
    # scope, rather than legitimizing every event under bare Nominations.
    recovered37,_=parse_html(tome37.encode("utf-8"),37,1853)
    assert len(recovered37)==1,recovered37
    assert (recovered37[0]["elected_name_candidate"],recovered37[0]["election_role_candidate"],recovered37[0]["original_printed_volume_page"])==(
        "Élie de Beaumont","OFFICE_ELECTION_NOT_NEW_MEMBER","938"),recovered37
    assert all(recovered37[0][field]=="0" for field in (
        "original_election_printed_page_opened","official_membership_accepted",
        "exact_dob_accepted","bazi_variables_computed"))

    # Actual Shard03 source wording: bare Nominations can also begin with
    # an explicitly appointed full section member. Subsequent external
    # candidate recommendations are not Academy membership elections.
    tome40="""<table>
       <tr><td><span class="sc">Nominations</span>. — M. Delaunay est nommé Membre de la Section d’Astronomie en remplacement de M. Mauvais</td><td>567</td></tr>
       <tr><td>— M. Daussy est nommé Membre de l’Académie, Section de Géographie et Navigation, en remplacement de feu M. Beautemps-Beaupré</td><td>829</td></tr>
       <tr><td><span class="sc">Nominations</span>. — M. Jules Cloquet est nommé Membre de la Section de Médecine et Chirurgie en remplacement de feu M. Lallemand</td><td>1233</td></tr>
       <tr><td>— M. Haussmann est nommé Correspondant de l’Académie, Section de Minéralogie et Géologie</td><td>410</td></tr>
       <tr><td>— M. Malaguti est nommé Correspondant de l’Académie pour la Section de Chimie</td><td>524</td></tr>
       <tr><td>— M. Bonnet est nommé Correspondant de l’Académie, Section de Médecine et de Chirurgie</td><td>933</td></tr>
       <tr><td>— M. Delezenne est nommé Correspondant de l’Académie pour la Section de Physique en remplacement de M. de Haldat</td><td>1213</td></tr>
       <tr><td>— L’Académie désigne, par la voie du scrutin, comme candidats pour la place vacante au Bureau des Longitudes, par suite de la mort de M. l’amiral Baudin, en première ligne M. Duperrey, en seconde ligne M. Jacquinot</td><td>285</td></tr>
       <tr><td>— L’Académie désigne par la voie du scrutin comme candidats pour la chaire d’Histoire naturelle (corps organisés) vacante au Collége de France par suite du décès de M. Duvernoy, en première ligne M. Flourens, en seconde ligne M. Valenciennes</td><td>1097</td></tr>
       <tr><td>— L’Académie désigne par la voie du scrutin comme candidats pour la chaire d’Anatomie comparée, vacante au Muséum d’Histoire, en première ligne M. Serres, en seconde ligne M. Gratiolet</td><td>1165</td></tr>
       <tr><td>— L’Académie désigne par la voie du scrutin comme candidats pour une place vacante au Bureau des Longitudes, en première ligne M. Yvon Villarceau, en seconde ligne M. Goujon</td><td>1213</td></tr></table>"""
    recovered40,_=parse_html(tome40.encode("utf-8"),40,1855)
    assert [(r["elected_name_candidate"],r["election_role_candidate"],r["original_printed_volume_page"]) for r in recovered40]==[
        ("Delaunay","FULL_SECTION_MEMBER","567"),
        ("Daussy","FULL_SECTION_MEMBER","829"),
        ("Jules Cloquet","FULL_SECTION_MEMBER","1233"),
        ("Haussmann","CORRESPONDENT","410"),
        ("Malaguti","CORRESPONDENT","524"),
        ("Bonnet","CORRESPONDENT","933"),
        ("Delezenne","CORRESPONDENT","1213")],recovered40

    # Exact source structure around the Tome 131 transclusion page break:
    # the role is outside either table, while the page occupies a single cell.
    tome131="""<table><tbody>
       <tr><td><span class="sc">Nominations</span>. — M. <i>Zambacco</i> est élu
       </td></tr></tbody></table> <span><span class="pagenum ws-pagenum" id="TdM" title="Page:Comptes rendus hebdomadaires des séances de l’Académie des sciences, tome 131, 1900.djvu/1341"></span></span>
       Correspondant pour la Section de Médecine et Chirurgie
       <table><tbody><tr><td>22</td></tr>
       <tr><td>— M. Czerny est élu Correspondant pour la Section de Médecine et Chirurgie.</td><td>96</td></tr>
       <tr><td>— M. Lipschitz est élu Correspondant pour la Section de Géométrie</td><td>169</td></tr>
       <tr><td>— M. Duhem est élu Correspondant pour la Section de Mécanique</td><td>325</td></tr>
       <tr><td>— M. Joseph Hooker est élu Associé étranger, en remplacement de M. Bunsen</td><td>825</td></tr>
       <tr><td>— M. Klein est élu Correspondant pour la Section de Minéralogie</td><td>825</td></tr>
       <tr><td>— M. Haller est élu Membre de la Section de Chimie, en remplacement de M. Ed. Grimaux</td><td>865</td></tr>
       <tr><td>— M. P. Painlevé est élu Membre de la Section de Géométrie, en remplacement de M. Darboux, nommé Secrétaire perpétuel</td><td>976</td></tr>
       <tr><td>— M. Dedekind est élu Correspondant pour la Section de Géométrie</td><td>1286</td></tr>
       <tr><td>— M. Strasburger est élu Correspondant pour la Section de Botanique</td><td>1286</td></tr>
       <tr><td><span class="sc">Observatoires</span>. — Sur l’observatoire du mont Etna ; par M. Janssen</td><td>317</td></tr></tbody></table>"""
    recovered131,_=parse_html(tome131.encode("utf-8"),131,1900)
    assert [(r["elected_name_candidate"],r["election_role_candidate"],r["original_printed_volume_page"]) for r in recovered131]==[
        ("Zambacco","CORRESPONDENT","22"),
        ("Czerny","CORRESPONDENT","96"),
        ("Lipschitz","CORRESPONDENT","169"),
        ("Duhem","CORRESPONDENT","325"),
        ("Joseph Hooker","FOREIGN_ASSOCIATE","825"),
        ("Klein","CORRESPONDENT","825"),
        ("Haller","FULL_SECTION_MEMBER","865"),
        ("P. Painlevé","FULL_SECTION_MEMBER","976"),
        ("Dedekind","CORRESPONDENT","1286"),
        ("Strasburger","CORRESPONDENT","1286")],recovered131
    # Do not invent the missing role or page when a source fragment is absent.
    assert not parse_html(tome131.replace(
        "Correspondant pour la Section de Médecine et Chirurgie\n", "\n",1).encode("utf-8"),131,1900)[0]
    assert not parse_html(tome131.replace(
        "<tr><td>22</td></tr>","<tr><td>unresolved</td></tr>",1).encode("utf-8"),131,1900)[0]
    assert not explicit_named_academy_event("M. Exemple est élu Membre de la Commission des prix")
    assert all(r[field]=="0" for r in recovered40+recovered131 for field in (
        "original_election_printed_page_opened","official_membership_accepted",
        "exact_dob_accepted","bazi_variables_computed"))

    fixture_shard04()
    print("PASS: historical fixtures; office scope; bare/literal nomination tables; bounded split rows; explicit clergy names; source-only gates")

def fixture_shard04():
    # Exact appointment wording from the Tome 14 div.tableItem source.
    actual14=[
        ("<span class='sc'>Nominations</span> <i>de membres ou de correspondants de l’Académie.</i> — M. Payen est nommé à la place devenue vacante dans la Section d’Économie rurale, par suite de la mort de M. Audouin", "59"),
        ("— M. Girardin est nommé correspondant de l’Académie, Section d’Économie rurale.", "156"),
        ("— M. Francœur est nommé à une place d’Académicien libre, en remplacement de M. Costaz", "578"),
        ("— M. d’Omalius-d’Halloy est nommé correspondant de l’Académie, pour la Section de Minéralogie et de Géologie.", "579"),
        ("— M. Œrstedt est nommé à une place d’associé étranger de l’Académie, vacante par suite de la mort de M. de Candolle", "568"),
        ("— M. Del Rio est nommé correspondant de l’Académie, pour la Section de Minéralogie et de Géologie.", "679"),
        ("— M. Burdin est nommé correspondant, pour la Section de Mécanique.", "680"),
        ("— M. Forbes est nommé correspondant de l’Académie, pour la Section de Physique.", "788"),
        ("— M. Wheatstone est nommé correspondant de l’Académie, pour la Section de Physique.", "862"),
        ("<span class='sc'>Nominations de candidats aux places pour lesquelles l’Académie est appelée à faire une présentation.</span> — M. Manzini est désigné par la voie du scrutin comme le candidat qui sera présenté par l’Académie", "400"),
        # Synthetic negative: this is outside the preceding membership scope.
        ("— M. Exemple est nommé Membre de la Section de Physique", "401")]
    tome14="".join("<div class='tableItem'><div class='ws-titpge'><div class='ws-titre'>"+
        line+"</div><div class='ws-noexport, ws-page'><span>"+page+
        "</span></div></div></div>" for line,page in actual14)
    recovered14,_=parse_html(tome14.encode("utf-8"),14,1842)
    assert [(r["elected_name_candidate"],r["election_role_candidate"],r["original_printed_volume_page"]) for r in recovered14]==[
        ("Payen","FULL_SECTION_MEMBER_CONTEXTUAL_NOMINATION","59"),
        ("Girardin","CORRESPONDENT","156"),
        ("Francœur","FULL_ACADEMICIAN_LIBRE","578"),
        ("d’Omalius-d’Halloy","CORRESPONDENT","579"),
        ("Œrstedt","FOREIGN_ASSOCIATE","568"),
        ("Del Rio","CORRESPONDENT","679"),
        ("Burdin","CORRESPONDENT","680"),
        ("Forbes","CORRESPONDENT","788"),
        ("Wheatstone","CORRESPONDENT","862")],recovered14
    assert not event_heading("Nominations de candidats aux places")

    # The source actually displays these literal wikitable markers in a P;
    # no original printed page or source text has been reconstructed by OCR.
    tome74="""<p>
| — M. E. Alix adresse une Note sur l’existence du nerf dépresseur chez l’hippopotame
| 557
|-
| <span class="sc">Nominations de membres, d’associés étrangers et de correspondants de l’académie</span>. — M. de Quatrefages est élu Vice-Président pour l’année 1872
| 13
|-
| — M. Hervé-Mangon est élu Membre de la Section d’Économie rurale, en remplacement de feu M. Payen | 30
|-
| — M. Agassiz est nommé Associé étranger, en remplacement de feu M. Murchison | 589
|-
| — M. Airy est nommé Associé étranger, en remplacement de feu Sir John Herschel | 589
|-
| — M. Rolland est nommé Membre de la Section de Mécanique, en remplacement de feu M. Piobert | 794
|-
| — M. l’abbé A. David est élu Correspondant, pour la Section de Géographie et Navigation, en remplacement de M. d’Abbadie, élu Membre de l’Académie
| 924
|-
| — M. Ledieu est élu Correspondant, pour la Section de Géographie et Navigation, en remplacement de M. le prince Demidoff | 924
|-
| — M. Tresca est nommé Membre de la Section de Mécanique, en remplacement de M. Combes | 1320
|-
| — M. Sédillot est élu Membre de la Section de Médecine et de Chirurgie, en remplacement de M. Stan. Laugier | 1550
|-
| <span class="sc">École polytechnique</span>. — M. Serret est nommé Membre du Conseil de perfectionnement de l’École Polytechnique, en remplacement de feu M. Combes | 269
|-
| — M. Exemple est nommé Membre de la Section de Physique | 270
|-</p>"""
    recovered74,_=parse_html(tome74.encode("utf-8"),74,1872)
    expected74=[
        ("de Quatrefages","OFFICE_ELECTION_NOT_NEW_MEMBER","13"),
        ("Hervé-Mangon","FULL_SECTION_MEMBER","30"),
        ("Agassiz","FOREIGN_ASSOCIATE","589"),
        ("Airy","FOREIGN_ASSOCIATE","589"),
        ("Rolland","FULL_SECTION_MEMBER","794"),
        ("l’abbé A. David","CORRESPONDENT","924"),
        ("Ledieu","CORRESPONDENT","924"),
        ("Tresca","FULL_SECTION_MEMBER","1320"),
        ("Sédillot","FULL_SECTION_MEMBER","1550")]
    assert [(r["elected_name_candidate"],r["election_role_candidate"],r["original_printed_volume_page"]) for r in recovered74]==expected74,recovered74
    partial,_=parse_html(tome74.replace("| 1550","| page unreadable").encode("utf-8"),74,1872)
    assert [(r["elected_name_candidate"],r["election_role_candidate"],r["original_printed_volume_page"]) for r in partial]==expected74[:-1],partial

    # Tome 44's explicit priest honorific and relative section wording.
    secchi="""<table><tr><td><span class="sc">Nominations de membres et de correspondants de l’académie</span>. — Le P. Secchi est nommé Correspondant, même Section, en remplacement de sir John Herschel, élu à une place d’Associé étranger</td><td>970</td></tr></table>"""
    recovered44,_=parse_html(secchi.encode("utf-8"),44,1857)
    assert len(recovered44)==1,recovered44
    assert (recovered44[0]["elected_name_candidate"],recovered44[0]["election_role_candidate"],recovered44[0]["original_printed_volume_page"],recovered44[0]["science_section_candidate"])==("Secchi","CORRESPONDENT","970",""),recovered44
    assert all(r[field]=="0" for r in recovered14+recovered74+recovered44 for field in (
        "original_election_printed_page_opened","official_membership_accepted",
        "exact_dob_accepted","bazi_variables_computed"))

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
