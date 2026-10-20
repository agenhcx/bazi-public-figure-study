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

VERSION="france-academy-legacy-heading-wikisource-source-only-v1_13"
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
    # 98/128 omit the second "de"; 94 uses "des correspondants";
    # 83 uses "Nomination des membres";
    # 14 uses "ou de correspondants";
    # 74 explicitly inserts "d'associés étrangers" in the membership list.
    return bool(re.match(
        r"^(?:elections?(?: de membres)?|nominations? des? membres(?: "
        r"(?:et|ou) (?:des? )?correspondants|,\s*d.associes etrangers et de correspondants)"
        r"(?: de l.academie)?)\b",x))
def name_from_line(line):
    raw=re.sub(r"\bM\.\s*\(\s*Monsieur\s*\)\s*","M. ",line,flags=re.I)
    raw=re.sub(r"\bM\.\s*\(\s*M\.\s*\)\s*","M. ",raw,flags=re.I)
    result=person_of(raw)
    if result:return result
    # Tome 178 prints "Sur William Pope", not "Sir". Preserve its source
    # spelling as a candidate instead of silently correcting the honorific.
    body=raw.split("—",1)[-1].strip()
    match=re.match(r"(Sur\s+.{2,110}?)\s+est\s+élu\b",body,re.I)
    return " ".join(match.group(1).split()).strip(" ,;.-") if match else ""
def nominated_name_from_line(line):
    """Retrieve ONLY the named appointee preceding est nommé/e, not a predecessor."""
    raw=re.sub(r"\bM\.\s*\(\s*Monsieur\s*\)\s*","M. ",line,flags=re.I)
    m=re.search(r"\bM\.\s+(.{2,140}?)\s+est\s+nomm[ée]e?\b",raw,re.I)
    if not m:
        # Tome 44: "Le P. Secchi est nommé Correspondant". The absent M.
        # honorific must not erase this explicitly named appointment.
        m=re.search(r"\bLe\s+P\.\s+(.{2,140}?)\s+est\s+nomm[ée]e?\b",raw,re.I)
    if not m:
        # Tome 110 explicitly says Lord Rayleigh. Preserve that transcribed
        # honorific; do not expand or silently normalize this identity.
        m=re.search(r"\b(Lord\s+.{2,140}?)\s+est\s+nomm[ée]e?\b",raw,re.I)
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
    if "academicien libre" in tail or "membre libre" in tail:return "FULL_ACADEMICIAN_LIBRE"
    if "membre non resid" in tail:return "FULL_NONRESIDENT_MEMBER"
    if re.search(r"\bmembre(?:s)?\s+de\s+l.academie\b|\bmembre\b",tail):return "FULL_SECTION_MEMBER"
    # Tome 17 separates the vacant seat from its Section with a comma.
    if re.search(r"\ba\s+la\s+place\s+(?:devenue\s+)?vacante\s*,?\s+dans\s+la\s+section\b",tail):
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

def membership_reminder_heading(line,decorated):
    """Tome 49 announces future Academy appointments before naming Denis.

    Its bare Nominations heading alone is insufficient. Require the actual
    presidential reminder and all three explicitly enumerated Academy
    classes; subsequent rows must still name an explicit Academy appointee.
    """
    if fold(decorated).strip(" .")!="nominations":return False
    text=fold(line)
    return bool(re.search(r"\bm\. le president rappelle a l.academie\b",text) and
        re.search(r"\bpour completer le nombre de ses associes etrangers, de ses membres et de ses correspondants\b",text))

def uppercase_subject_heading(line):
    """Unstyled uppercase subjects end a membership column, as in Tome 50.

    The observed titles end in a full stop, either before the em dash or
    on their own row. A continuation beginning with an em dash is not a
    subject heading. Explicit event headings are handled before this rule.
    """
    prefix=line.split("—",1)[0].strip()
    return len(prefix)>=4 and prefix.endswith(".") and prefix.isupper()

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

def split_nomination_row(tr,line,page):
    """Join only the two complete nomination splits observed in Shard06.

    Tome 77 continues a named free-member appointment; Tome 109 continues
    a correspondent's replacement clause. Both put the explicit page in
    the next table's first, single-cell row. Missing or unrelated fragments
    leave the original partial record unchanged.
    """
    if page or not nominated_name_from_line(line):return line,page
    free_member=bool(re.search(r"\best\s+nomm[ée]e?\s+à\s+la\s+place\s+de\s*$",line,re.I))
    correspondent=bool(nomination_role(line)=="CORRESPONDENT" and re.search(r",\s*en\s*$",line,re.I))
    if not (free_member or correspondent):return line,page
    table=tr.find_parent("table")
    if table is None or table.find_all("tr")[-1] is not tr:return line,page
    pieces=[];following=None
    for i,sibling in enumerate(table.next_siblings):
        if i>=8:return line,page
        tag=getattr(sibling,"name",None)
        if tag=="table":following=sibling;break
        if tag not in (None,"span","i"):return line,page
        part=sibling.get_text(" ",strip=True) if tag else str(sibling)
        # The observed spans are empty page markers, not another subject.
        if tag=="span" and part:return line,page
        pieces.append(part)
    continuation=" ".join(" ".join(pieces).split())
    pattern=(r"Membre libre laissée vacante par le décès de M\.\s+[^;\d]+" if free_member
             else r"remplacement de feu M\.\s+[^;\d]+")
    if following is None or not re.fullmatch(pattern,continuation,re.I):return line,page
    first_row=following.find("tr")
    if first_row is None:return line,page
    cells=first_row.find_all("td",recursive=False)
    if len(cells)!=1:return line,page
    number=cells[0].get_text(" ",strip=True)
    if not re.fullmatch(r"\d{1,5}",number):return line,page
    return line+" "+continuation,number

def split_member_division_row(tr,line,page):
    """Complete Tome 178's named member/division/page transclusion split.

    The existing section extractor explicitly supports division des. Do
    not supply it unless both the adjacent division text and single-cell
    printed page are present at the actual end/start of their tables.
    """
    if page or not name_from_line(line) or not re.search(r"\best\s+élu\s+membre\s+de\s*$",line,re.I):return line,page
    table=tr.find_parent("table")
    if table is None or table.find_all("tr")[-1] is not tr:return line,page
    pieces=[];following=None
    for i,sibling in enumerate(table.next_siblings):
        if i>=8:return line,page
        tag=getattr(sibling,"name",None)
        if tag=="table":following=sibling;break
        if tag not in (None,"span"):return line,page
        part=sibling.get_text(" ",strip=True) if tag else str(sibling)
        if tag=="span" and part:return line,page
        pieces.append(part)
    continuation=" ".join(" ".join(pieces).split())
    if following is None or not re.fullmatch(r"la division des [^.;\d]+",continuation,re.I):return line,page
    first_row=following.find("tr")
    if first_row is None:return line,page
    cells=first_row.find_all("td",recursive=False)
    if len(cells)!=1:return line,page
    number=cells[0].get_text(" ",strip=True)
    if not re.fullmatch(r"\d{1,5}",number):return line,page
    return line+" "+continuation,number

def floating_table_item_row(item):
    """Read Tome 112's old tableDots/tablePage floating layout.

    Both unique structural slots must belong to this tableItem. The title
    is the sibling immediately before the dots wrapper, never the entire
    page or surrounding prose. An incomplete page can preserve a heading
    boundary but must not create a new event with an inferred locator.
    """
    dots=item.select(".tableDots");pages=item.select(".tablePage")
    if len(dots)!=1 or len(pages)!=1:return None
    dots,page_node=dots[0],pages[0]
    if any(node.find_parent("div",class_="tableItem") is not item for node in (dots,page_node)):return None
    if any("ws-noexport" not in node.parent.get("class",[]) for node in (dots,page_node)):return None
    title=dots.parent.find_previous_sibling("div")
    if title is None or title.parent is not dots.parent.parent:return None
    if title.find_parent("div",class_="tableItem") is not item or title.select_one(".tablePage, .tableDots"):return None
    line=" ".join(title.get_text(" ",strip=True).split())
    if not line:return None
    page,refs=page_references(page_node.get_text(" ",strip=True))
    sc=title.find("span",class_=re.compile("sc",re.I))
    heading=" ".join(sc.get_text(" ",strip=True).split()) if sc else ""
    if not page:
        prefix=line.split("—",1)[0].strip(" .")
        if event_heading(prefix):line=prefix
        elif heading:line=heading
        else:return None
        refs=""
    return line,page,heading,refs

def nominal_index_entry(line,scope,page):
    """Read explicit member-role noun phrases inside a membership heading.

    Tomes 48, 171 and 173 omit an appointment/election verb in these rows.
    Require the observed complete role/section/replacement construction,
    or the named free-member construction, plus a printed page. Preserve
    that omission in the action category; never manufacture 'est élu'.
    """
    if scope not in ("ELECTION","NOMINATION") or not page or "—" not in line:return None
    body=line.split("—",1)[1].strip()
    free=re.fullmatch(r"De\s+M\.\s+(.{2,110}?)\s+parmi\s+les\s+académiciens\s+libres\.?",body,re.I)
    if free and scope=="ELECTION":
        name=free.group(1);role="FULL_ACADEMICIAN_LIBRE";section=""
    else:
        match=re.fullmatch(
            r"M\.\s+(.{2,110}?),?\s+(correspondant|membre)\s+"
            r"(?:d[ée]\s+la|pour\s+la)\s+section\s+(?:de\s+|d['’])"
            r"([^,;]+),\s+en\s+remplacement\s+de\s+[^;]+",body,re.I)
        if not match:return None
        name=match.group(1)
        role="CORRESPONDENT" if fold(match.group(2))=="correspondant" else "FULL_SECTION_MEMBER"
        section=" ".join(match.group(3).split())[:90]
    name=" ".join(name.split()).strip(" ,;.-")
    if not name or " et " in fold(name) or re.search(
            r"\b(?:est|sont|ete|elu|nomme|candidat|candidats|adresse|demande|prie|propose|presente)\b",fold(name)):
        return None
    return name,role,section,"NOMINAL_"+scope+"_INDEX_ENTRY_TRANSCRIBED"

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
        name=x["transcribed_elected_person_name"]
        excerpt=x.get("transcribed_line_excerpt","")
        if not name and re.match(r"^—\s+Sur\s+",excerpt):
            # Repair this existing modern record in place. Adding a separate
            # legacy row would leave a duplicate anonymous event behind.
            name=name_from_line(excerpt)
        events.append({"volume":str(volume),"year":str(year),
             "elected_name_candidate":name,
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
        line,page=split_nomination_row(tr,line,page)
        line,page=split_member_division_row(tr,line,page)
        page,page_refs=page_references(page)
        sc=first.find("span",class_=re.compile(r"sc",re.I))
        heading=" ".join(sc.get_text(" ",strip=True).split()) if sc else ""
        table_rows.append((line,page,heading,page_refs))
    legacy_rows=[]
    for item in soup.select("div.tableItem"):
        # Tome 14 uses the same page container with ws-titre, not ws-titrex.
        # Prefer the established layout when both are present.
        div=item.select_one(".ws-titrex") or item.select_one(".ws-titre")
        if div is None:
            floating=floating_table_item_row(item)
            if floating:legacy_rows.append(floating)
            continue
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
                    # A completed adjacent continuation may also recover the
                    # explicit section/division omitted by the first parser.
                    if p1 and p2 and p1==p2 and not x.get("science_section_candidate") and candidate.get("science_section_candidate"):
                        x["science_section_candidate"]=candidate["science_section_candidate"]
                    return
        events.append(candidate)

    for logical in (table_rows,legacy_rows,literal_wikitable_rows(soup)):
        in_events=False
        office_only=False
        correspondent_only=False
        reminder_only=False
        nominal_scope=""
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
            # Tome 3's Nominations merely cross-refers to Correspondants.
            # The destination explicitly appoints Baily a correspondent of
            # the Academy. A bare Correspondants heading or correspondence
            # notice alone must not open a generic member-event scope.
            is_named_correspondent=bool(
                fold(decorated).strip(" .")=="correspondants" and
                explicit_named_academy_event(line) and
                nomination_role(line)=="CORRESPONDENT" and
                re.search(r"\bcorrespondant\s+de\s+l.academie\b",fold(line)))
            is_membership_reminder=membership_reminder_heading(line,decorated)
            if event_heading(head_candidate) or is_named_member_nomination or is_named_office_election or is_named_correspondent or is_membership_reminder:
                in_events=True
                office_only=is_named_office_election and not event_heading(head_candidate)
                correspondent_only=is_named_correspondent
                reminder_only=is_membership_reminder
                nominal_scope=""
                if re.match(r"^(?:elections?|nominations?) des? membres\b",fold(head_candidate)):
                    nominal_scope="ELECTION" if fold(head_candidate).startswith("election") else "NOMINATION"
                header=head_candidate if event_heading(head_candidate) else prefix
                if header not in headings:headings.append(header[:120])
            elif decorated or uppercase_subject_heading(line):
                in_events=False
            elif fold(prefix).startswith(("candidatures","prix","decrets","decret","necrologie","deces")):
                in_events=False
            if not in_events:continue
            if reminder_only and not explicit_named_academy_event(line):continue
            nominated=bool(re.search(r"\best\s+nomm[ée]e?\b",line,re.I))
            elected=bool(re.search(r"\b(est|a été|sont)\s+élu",line,re.I))
            nominal=nominal_index_entry(line,nominal_scope,page) if not (nominated or elected) else None
            if nominal:
                name,role,section,wording=nominal
            else:
                if not (nominated or elected):continue
                role=nomination_role(line) if nominated else role_of(line)
                name=nominated_name_from_line(line) if nominated else name_from_line(line)
                section=nomination_section(line) if nominated else section_of(line).strip(" )")
                wording="EST_NOMME_TRANSCRIBED" if nominated else "EST_ELU_TRANSCRIBED"
            if not role:continue
            if office_only and role!="OFFICE_ELECTION_NOT_NEW_MEMBER":continue
            if correspondent_only and role!="CORRESPONDENT":continue
            # Quarantine unparsed identities; do not infer people from heading.
            if not name:continue
            candidate={"volume":str(volume),"year":str(year),
                "elected_name_candidate":name,"election_role_candidate":role,
                "source_action_wording":wording,
                "science_section_candidate":section,
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
    fixture_legacy_p1()
    fixture_shard05()
    fixture_shard06()
    fixture_shard07()
    fixture_shard08()
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

def fixture_legacy_p1():
    # Actual Tome 3 cross-reference and its explicit appointment destination.
    # The nomination heading is not itself an event and the nearby commission
    # and library appointments are not Academy membership nominations.
    tome3="""<table>
       <tr><td>Le Président de la Commission centrale administrative transmet le résultat du scrutin qui a eu lieu dans les cinq Académies. — M. Roulin a réuni la majorité ; il est nommé sous-bibliothécaire</td><td>111</td></tr>
       <tr><td>— M. Magendie est nommé membre de la Commission chargée de surveiller des expériences relatives à un nouveau mode de traitement pour la Morve des chevaux</td><td>372</td></tr>
       <tr><td><span class="sc">Correspondants</span>. — M. <i>Baily</i> est nommé membre correspondant de l’Académie, pour la <i>Section d’Astronomie</i></td><td>611</td></tr>
       <tr><td><span class="sc">Courants électriques</span>. — A l’approche d’un orage les appareils destinés à faire connaître l’électricité des nuages offrent souvent de brusques et grands changements dans la direction des courants ; lettre de M. Peltier</td><td>145</td></tr>
       <tr><td><span class="sc">Nominations</span>. — Voyez aux mots <i>Commission, Correspondants, Chaire</i>.</td><td></td></tr></table>"""
    recovered3,_=parse_html(tome3.encode("utf-8"),3,1836)
    assert [(r["elected_name_candidate"],r["election_role_candidate"],r["original_printed_volume_page"],r["science_section_candidate"]) for r in recovered3]==[
        ("Baily","CORRESPONDENT","611","Astronomie")],recovered3
    # Synthetic negatives leave the subject/appointment incomplete or make
    # the appointee a commission member; neither must infer a correspondent.
    assert not parse_html(tome3.replace(
        "est nommé membre correspondant de l’Académie", "adresse une lettre à l’Académie").encode("utf-8"),3,1836)[0]
    assert not parse_html(tome3.replace(
        "est nommé membre correspondant de l’Académie", "est nommé membre de la Commission").encode("utf-8"),3,1836)[0]

    # All six Tome 94 membership rows. Only the source heading's "des"
    # differs from previously supported grammar. The distinct presidential
    # and commission columns remain outside this membership scope.
    tome94="""<table>
       <tr><td><span class="sc">Nominations de membres et des correspondants de l’académie</span>. — M. A. Gaudry est élu Membre de la section de Minéralogie, en remplacement de feu M. H. Sainte-Claire Deville</td><td>119</td></tr>
       <tr><td>— M. P. Bert est élu Membre de la Section de Médecine et Chirurgie, en remplacement de feu M. Bouillaud</td><td>925</td></tr>
       <tr><td>— M. de Freycinet est élu Membre libre, en remplacement de feu M. Bussy</td><td>1276</td></tr>
       <tr><td>— M. Demontzey est élu Correspondant pour la Section d’Économie rurale, en remplacement de feu M. Is. Pierre</td><td>1385</td></tr>
       <tr><td>— M. Schloesing est nommé Membre de la Section d’Économie rurale, en remplacement de feu M. Decaisne</td><td>1561</td></tr>
       <tr><td>— M. Lallemand est nommé Correspondant pour la Section de Physique, en remplacement de feu M. Billet</td><td>1698</td></tr>
       <tr><td><span class="sc">Présidents de l’académie</span>. — M. Blanchard est élu Vice-Président pour l’année 1882</td><td>13</td></tr>
       <tr><td><span class="sc">Commissions spéciales</span>. — MM. Decaisne et Edm. Becquerel sont nommés Membres de la Commission centrale administrative, pour l’année 1882</td><td>13</td></tr></table>"""
    recovered94,_=parse_html(tome94.encode("utf-8"),94,1882)
    assert [(r["elected_name_candidate"],r["election_role_candidate"],r["original_printed_volume_page"]) for r in recovered94]==[
        ("A. Gaudry","FULL_SECTION_MEMBER","119"),
        ("P. Bert","FULL_SECTION_MEMBER","925"),
        ("de Freycinet","FULL_ACADEMICIAN_LIBRE","1276"),
        ("Demontzey","CORRESPONDENT","1385"),
        ("Schloesing","FULL_SECTION_MEMBER","1561"),
        ("Lallemand","CORRESPONDENT","1698")],recovered94
    assert all(r[field]=="0" for r in recovered3+recovered94 for field in (
        "original_election_printed_page_opened","official_membership_accepted",
        "exact_dob_accepted","bazi_variables_computed"))

def fixture_shard05():
    # Actual Tome 17 wording and tableItem layout: the source names vacant
    # Academy Section seats, without explicitly saying member for the two
    # continuations. Keep the established CONTEXTUAL classification.
    actual17=[
        ("— M. <i>Binet</i> est nommé, en remplacement de M. <i>Poncelet</i> absent, membre de la Commission chargée de faire un Rapport sur la turbine de M. <i>Passot</i>.", "483"),
        ("<span class='sc'>Nomination</span> <i>de membres et de correspondants de l’Académie'. — M. </i>Binet<i> est nommé membre de l’Académie, Section de Géométrie, en remplacement de feu M. </i>Lacroix<i>.</i>", "71"),
        ("— M. <i>Mauvais</i> est nommé à la place devenue vacante, dans la Section d’Astronomie, par suite de la mort de M. <i>Bouvard</i>.", "1164"),
        ("— M. <i>Morin</i> est nommé à la place vacante, dans la Section de Mécanique, par suite du décès de M. <i>Coriolis</i>.", "1327")]
    tome17="".join("<div class='tableItem'><div class='ws-titpge'><div class='ws-titrex'>"+
        line+"</div><div class='ws-page'>"+page+"</div></div></div>" for line,page in actual17)
    recovered17,_=parse_html(tome17.encode("utf-8"),17,1843)
    assert [(r["elected_name_candidate"],r["election_role_candidate"],r["original_printed_volume_page"],r["science_section_candidate"]) for r in recovered17]==[
        ("Binet","FULL_SECTION_MEMBER","71","Géométrie"),
        ("Mauvais","FULL_SECTION_MEMBER_CONTEXTUAL_NOMINATION","1164","Astronomie"),
        ("Morin","FULL_SECTION_MEMBER_CONTEXTUAL_NOMINATION","1327","Mécanique")],recovered17
    assert nomination_role("M. Exemple est nommé à la place vacante, dans la Commission des prix")=="NOMINATION_UNKNOWN_MEMBER_CLASS_MANUAL"
    assert all(r[field]=="0" for r in recovered17 for field in (
        "original_election_printed_page_opened","official_membership_accepted",
        "exact_dob_accepted","bazi_variables_computed"))

def fixture_shard06():
    # Tome 48's six continuation rows explicitly print Correspondant and a
    # replacement, but do not repeat the nomination verb after Carus.
    tome48="""<table>
       <tr><td>NOMINATIONS <i>de Membres et de Correspondants de l’Académie :</i></td><td></td></tr>
       <tr><td>— M. <i>Owen</i> est élu Associé étranger de l’Académie, en remplacement de feu M. Robert Brown</td><td>832</td></tr>
       <tr><td>— M. <i>Carus</i> est nommé Correspondant de l’Académie pour la Section d’Anatomie et de Zoologie, en remplacement de feu M. Müller</td><td>329</td></tr>
       <tr><td>— M. <i>Ridolfi,</i> Correspondant de la Section d’Économie rurale, en remplacement de fen M. Jaubert de Passa</td><td>633</td></tr>
       <tr><td>— M. <i>Renault,</i> Correspondant de la Section d’Économie rurale, en remplacement de feu M. d’Hombres Firmas</td><td>687</td></tr>
       <tr><td>— M. <i>Hofmann,</i> Correspondant dé la Section de Chimie, en remplacement de feu M. Gerhardt</td><td>722</td></tr>
       <tr><td>— M. <i>Dujardin,</i> Correspondant de la Section d’Anatomie et de Zoologie, en remplacement de feu M. le prince Ch. Bonaparte</td><td>832</td></tr>
       <tr><td>— M. <i>Virchow,</i> Correspondant de la Section de Médecine et de Chirurgie, en remplacement de feu M. Marshal Hall</td><td>1017</td></tr>
       <tr><td>— M. <i>Lecoq,</i> Correspondant de la Section de Botanique, en remplacement de feu M. Bonpland</td><td>1047</td></tr>
       <tr><td><span class="sc">Ombres</span>. — Sur les ombres bleues du 27 mai 1859 ; Note de M. Babinet</td><td>1007</td></tr></table>"""
    recovered48,_=parse_html(tome48.encode("utf-8"),48,1859)
    expected48=[("Owen","FOREIGN_ASSOCIATE","832"),("Carus","CORRESPONDENT","329"),
        ("Ridolfi","CORRESPONDENT","633"),("Renault","CORRESPONDENT","687"),
        ("Hofmann","CORRESPONDENT","722"),("Dujardin","CORRESPONDENT","832"),
        ("Virchow","CORRESPONDENT","1017"),("Lecoq","CORRESPONDENT","1047")]
    assert [(r["elected_name_candidate"],r["election_role_candidate"],r["original_printed_volume_page"]) for r in recovered48]==expected48,recovered48
    assert all(r["source_action_wording"]=="NOMINAL_NOMINATION_INDEX_ENTRY_TRANSCRIBED" for r in recovered48[2:])
    missing_page,_=parse_html(tome48.replace("<td>633</td>","<td>unresolved</td>").encode("utf-8"),48,1859)
    assert [r["elected_name_candidate"] for r in missing_page]==[x[0] for x in expected48 if x[0]!="Ridolfi"]
    # Synthetic external-column variant: neither a role noun nor a page
    # licenses an event when the explicit membership heading is absent.
    assert not parse_html(tome48.replace(
        "NOMINATIONS <i>de Membres et de Correspondants de l’Académie :</i>",
        '<span class="sc">Commissions</span>').encode("utf-8"),48,1859)[0]

    tome171="""<table>
       <tr><td><span class="sc">Élections de membres et de correspondants</span>. — De M. <i>J.-L. Breton</i> parmi les académiciens libres</td><td>1045</td></tr>
       <tr><td><span class="sc">Électricité</span></td></tr></table>"""
    recovered171,_=parse_html(tome171.encode("utf-8"),171,1920)
    assert [(r["elected_name_candidate"],r["election_role_candidate"],r["original_printed_volume_page"],r["source_action_wording"]) for r in recovered171]==[
        ("J.-L. Breton","FULL_ACADEMICIAN_LIBRE","1045","NOMINAL_ELECTION_INDEX_ENTRY_TRANSCRIBED")],recovered171
    tome173="""<table>
       <tr><td><span class="sc">Élections de membres et de correspondants</span>. — M. <i>J. Andrade</i> est élu correspondant pour la section de mécanique en remplacement de M. <i>Vallier,</i> décédé</td><td>755</td></tr>
       <tr><td>— M. <i>Marcel Brillouin</i> membre de la section de physique générale, en remplacement de M. <i>G. Lippmann,</i> décédé.</td><td>962</td></tr>
       <tr><td>— M. <i>Félix Mesnil</i> membre de la section d’anatomie et zoologie, en remplacement de M. <i>Edmond Perrier,</i> décédé</td><td>1148</td></tr>
       <tr><td>— M. <i>P. Zeeman</i> correspondant pour la section de physique, en remplacement de M. <i>Righi,</i> décédé</td><td>1323</td></tr>
       <tr><td><span class="sc">Électricité</span></td></tr></table>"""
    recovered173,_=parse_html(tome173.encode("utf-8"),173,1921)
    assert [(r["elected_name_candidate"],r["election_role_candidate"],r["original_printed_volume_page"]) for r in recovered173]==[
        ("J. Andrade","CORRESPONDENT","755"),("Marcel Brillouin","FULL_SECTION_MEMBER","962"),
        ("Félix Mesnil","FULL_SECTION_MEMBER","1148"),("P. Zeeman","CORRESPONDENT","1323")],recovered173
    assert all(r["source_action_wording"]=="NOMINAL_ELECTION_INDEX_ENTRY_TRANSCRIBED" for r in recovered173[1:])
    # Synthetic candidates and external committee nouns must not become
    # named membership events, even when their lines contain role words.
    assert nominal_index_entry("— M. Exemple est candidat à une place de membre de la section de physique, en remplacement de M. Autre", "ELECTION", "12") is None
    assert nominal_index_entry("— M. Exemple membre de la Commission des prix, en remplacement de M. Autre", "ELECTION", "12") is None
    outside=tome173.replace("</table>",'<tr><td>— M. Exemple membre de la section de physique, en remplacement de M. Autre</td><td>12</td></tr></table>')
    assert len(parse_html(outside.encode("utf-8"),173,1921)[0])==4

    # Exact three-fragment transclusion layouts from Tomes 77 and 109.
    tome77="""<table><tbody>
       <tr><td><span class="sc">Nominations de membres et de correspondants de l’académie</span>. — M. Steenstrup est nommé Correspondant, pour la Section d’Anatomie et Zoologie, en remplacement de M. Agassiz, élu Associé étranger</td><td>33</td></tr>
       <tr><td>— M. <i>F. de Lesseps</i> est nommé à la place de</td></tr></tbody></table> <span><span class="pagenum ws-pagenum" id="TdM" title="Page:Comptes rendus hebdomadaires des séances de l’Académie des sciences, tome 077, 1873.djvu/1593"></span></span>
       Membre libre laissée vacante par le décès de M. de Verneuil
       <table><tbody><tr><td>190</td></tr></tbody></table>"""
    recovered77,_=parse_html(tome77.encode("utf-8"),77,1873)
    lesseps=next(r for r in recovered77 if r["elected_name_candidate"]=="F. de Lesseps")
    assert len(recovered77)==2 and (lesseps["election_role_candidate"],lesseps["original_printed_volume_page"],lesseps["source_action_wording"])==(
        "FULL_ACADEMICIAN_LIBRE","190","EST_NOMME_TRANSCRIBED"),recovered77
    for partial in (tome77.replace("<td>190</td>","<td>unresolved</td>"),
                    tome77.replace("Membre libre laissée vacante par le décès de M. de Verneuil","Commission administrative")):
        rows,_=parse_html(partial.encode("utf-8"),77,1873)
        row=next(r for r in rows if r["elected_name_candidate"]=="F. de Lesseps")
        assert row["election_role_candidate"]=="NOMINATION_UNKNOWN_MEMBER_CLASS_MANUAL" and not row["original_printed_volume_page"],row

    tome109="""<table><tbody>
       <tr><td><span class="sc">Nominations de membres et correspondants de l’académie</span>. — M. Arloing est nommé Correspondant, pour la Section d’Économie rurale, en remplacement de feu M. Martins</td><td>17</td></tr>
       <tr><td>— M. <i>Suess</i> est nommé Correspondant, pour la Section de Minéralogie, en</td></tr></tbody></table> <span><span class="pagenum ws-pagenum" id="TdM" title="Page:Comptes rendus hebdomadaires des séances de l’Académie des sciences, tome 109, 1889.djvu/1147"></span></span>
       remplacement de feu M. <i>de Dechen</i>.
       <table><tbody><tr><td>957</td></tr>
       <tr><td>— M. Pomel est nommé Correspondant, pour la Section de Minéralogie, en remplacement de feu M. Lory</td><td>957</td></tr></tbody></table>"""
    recovered109,_=parse_html(tome109.encode("utf-8"),109,1889)
    suess=next(r for r in recovered109 if r["elected_name_candidate"]=="Suess")
    assert len(recovered109)==3 and (suess["election_role_candidate"],suess["original_printed_volume_page"],suess["science_section_candidate"])==(
        "CORRESPONDENT","957","Minéralogie"),recovered109
    assert all(r[field]=="0" for r in recovered48+recovered171+recovered173+recovered77+recovered109 for field in (
        "original_election_printed_page_opened","official_membership_accepted",
        "exact_dob_accepted","bazi_variables_computed"))

def fixture_shard07():
    # Tome 49's bare heading first describes the membership work, then
    # explicitly appoints Denis. Preserve the printed locality in the name.
    tome49="""<table>
       <tr><td><span class="sc">Nominations</span>. — M. le Président rappelle à l’Académie qu’elle aura à s’occuper prochainement de plusieurs nominations pour compléter le nombre de ses Associés étrangers, de ses Membres et de ses Correspondants.</td><td>593</td></tr>
       <tr><td>— M. <i>Denis,</i> de Commercy, est nommé Correspondant de la Section de Médecine et Chirurgie en remplacement de feu M. <i>Bonnet.</i></td><td>935</td></tr>
       <tr><td><span class="sc">Optique</span>. — Essai d’un nouveau télescope parabolique en verre argenté ; Note de M. L. Foucault.</td><td>85</td></tr></table>"""
    recovered49,_=parse_html(tome49.encode("utf-8"),49,1859)
    assert [(r["elected_name_candidate"],r["election_role_candidate"],r["original_printed_volume_page"],r["science_section_candidate"]) for r in recovered49]==[
        ("Denis, de Commercy","CORRESPONDENT","935","Médecine et Chirurgie")],recovered49
    # Synthetic commission appointment within the reminder does not satisfy
    # the explicit Academy-role requirement; unrelated headings close it.
    commission='<tr><td>— M. Exemple est nommé membre de la Commission des prix</td><td>936</td></tr>'
    with_commission=tome49.replace('<tr><td><span class="sc">Optique</span>',commission+'<tr><td><span class="sc">Optique</span>')
    assert len(parse_html(with_commission.encode("utf-8"),49,1859)[0])==1
    assert not parse_html(tome49.replace(
        "Associés étrangers, de ses Membres et de ses Correspondants", "Commissaires").encode("utf-8"),49,1859)[0]

    # Actual Tome 50 boundary: headings are plain uppercase text, not sc
    # spans. The independent presidency row must not leak into nominations.
    tome50="""<table>
       <tr><td>NOMINATIONS <i>de Membres et de Correspondants de l’Académie.</i></td><td></td></tr>
       <tr><td>— M. <i>Nordmann</i> est élu Correspondant de l’Académie pour la Section de Zoologie et d’Anatomie comparée, en remplacement de M. Ehrenberg, devenu Associé étranger.</td><td>1134</td></tr>
       <tr><td>O</td></tr>
       <tr><td>OEIL. — Sur une propriété du cristallin de l’œil humain ; Note de M. <i>Breton</i> (de Champ).</td><td>498</td></tr>
       <tr><td>OLÉFIANT (GAZ). — Synthèse de l’éther iodhydrique au moyen du gaz oléfiant ; Note de M. <i>Berthelot</i></td><td>612</td></tr>
       <tr><td>PRÉSIDENCE DE L’ACADÉMIE. — M. <i>Milne Edwards</i> est élu Vice-Président pour l’année 1860 : M. <i>Chasles,</i> Vice-Président pour l’année 1859, passe aux fonctions de Président</td><td>13</td></tr></table>"""
    recovered50,_=parse_html(tome50.encode("utf-8"),50,1860)
    assert [(r["elected_name_candidate"],r["election_role_candidate"],r["original_printed_volume_page"]) for r in recovered50]==[
        ("Nordmann","CORRESPONDENT","1134")],recovered50
    assert uppercase_subject_heading("ÉLECTRICITÉ.")
    assert uppercase_subject_heading("PRÉSIDENCE DE L’ACADÉMIE. — M. Milne Edwards est élu Vice-Président")
    assert not uppercase_subject_heading("— M. Nordmann est élu Correspondant.")

    # Tome 110 actually includes Lord in this appointment entry. Retain
    # that spelling as the source-name candidate, without expanding it.
    tome110="""<table>
       <tr><td><span class="sc">Nominations de membres et de correspondants de l’académie</span>. — M. <i>Beltrami</i> est élu Correspondant, pour la Section de Mécanique, en remplacement de feu M. <i>Clausius</i></td><td>118</td></tr>
       <tr><td>— M. <i>Gilbert</i> est nommé Correspondant pour la Section de Mécanique, en remplacement de feu M. <i>Broch</i></td><td>218</td></tr>
       <tr><td>— Lord <i>Rayleigh</i> est nommé Correspondant, pour la Section de Physique, en remplacement de feu M. <i>Kirchhoff</i>.</td><td>508</td></tr>
       <tr><td>— M. <i>Louis Soret</i> est élu Correspondant pour la Section de Physique, en remplacement de feu M. <i>Joule</i></td><td>566</td></tr></table>"""
    recovered110,_=parse_html(tome110.encode("utf-8"),110,1890)
    assert [(r["elected_name_candidate"],r["original_printed_volume_page"]) for r in recovered110]==[
        ("Beltrami","118"),("Gilbert","218"),("Lord Rayleigh","508"),("Louis Soret","566")],recovered110
    rayleigh=recovered110[2]
    assert (rayleigh["election_role_candidate"],rayleigh["source_action_wording"],rayleigh["science_section_candidate"])==(
        "CORRESPONDENT","EST_NOMME_TRANSCRIBED","Physique"),rayleigh

    # Do not resolve Tome 22's unusual 'associé libre' by silently replacing
    # it with Tome 23's different approval wording. The original page needs
    # review; a royal confirmation is not another membership election.
    assert nomination_role("— M. Jacobi est nommé associé libre de l’Académie, en remplacement de M. Bessel.")=="NOMINATION_UNKNOWN_MEMBER_CLASS_MANUAL"
    approval="""<table><tr><td>ORDONNANCE ROYALE confirmant la nomination de M. Jacobi en qualité d’associé étranger de l’Académie des Sciences.</td><td>57</td></tr></table>"""
    assert not parse_html(approval.encode("utf-8"),23,1846)[0]
    assert all(r[field]=="0" for r in recovered49+recovered50+recovered110 for field in (
        "original_election_printed_page_opened","official_membership_accepted",
        "exact_dob_accepted","bazi_variables_computed"))

def fixture_shard08():
    tome83="""<table>
       <tr><td><span class="sc">Nomination des membres et correspondants de l’académie</span>. — M. <i>Favé</i> est élu à la place d’Académicien libre laissée vacante par le décès de M. <i>A.-P. Séguier</i></td><td>125</td></tr>
       <tr><td>— M. le général <i>Favé</i> adresse ses remercîments à l’Académie</td><td>312</td></tr>
       <tr><td><span class="sc">Observations météorologiques de montsouris</span></td><td>94</td></tr></table>"""
    recovered83,_=parse_html(tome83.encode("utf-8"),83,1876)
    assert [(r["elected_name_candidate"],r["election_role_candidate"],r["original_printed_volume_page"]) for r in recovered83]==[
        ("Favé","FULL_ACADEMICIAN_LIBRE","125")],recovered83

    # Actual Tome 112 title/page slot hierarchy. Decorative style values
    # are shortened; the tableItem/tableDots/tablePage relationships and
    # all seven membership lines are retained from the captured source.
    actual112=[
        ("<span class='sc'>Nominations de membres et de correspondants de l’académie</span>. — M. <i>Haller</i> est élu Correspondant pour la Section de Chimie, en remplacement de feu M. <i>Chancel</i>", "81"),
        ("— M. <i>Chambrelent</i> est élu Membre de la Section d’Économie rurale, en remplacement de feu M. <i>Peligot</i>", "148"),
        ("— M. <i>Geikie</i> est élu Correspondant pour la Section de Minéralogie, en remplacement de feu M. <i>Favre</i>", "470"),
        ("— M. <i>G. Sire</i> est élu Correspondant pour la Section de Mécanique, en remplacement de feu M. <i>Dausse</i>", "509"),
        ("— M. <i>de Serpa Pinto</i> est élu Correspondant pour la Section de Géographie et Navigation, en remplacement de feu M. <i>Pissis</i>", "846"),
        ("— M. le Prince <i>Albert de Monaco</i> est élu Correspondant pour la Section de Géographie et Navigation, en remplacement de M. <i>de Tchihatcheff</i>", "930"),
        ("— M. <i>Moissan</i> est élu Membre de la Section de Chimie, en remplacement de feu M. <i>Cahours</i>", "1298"),
        ("<span class='sc'>Olfaction</span>. — Olfactomètre fondé sur la diffusion à travers les membranes flexibles ; par M. Charles Henry", "344")]
    def floating_html(rows):
        return "".join("<div class='tableItem' style='position:relative'><div style='margin-right:0px'><div style='float:left;width:100%'><div style='position:relative;z-index:2'><span>"+
            line+"</span></div><div class='ws-noexport' style='position:relative;margin-left:1em'><div class='tableDots'></div></div></div><div class='ws-noexport' style='float:right'><div class='tablePage'><span>"+
            page+"</span></div></div><div style='clear:both'></div></div></div>" for line,page in rows)
    tome112=floating_html(actual112)
    recovered112,_=parse_html(tome112.encode("utf-8"),112,1891)
    expected112=[("Haller","CORRESPONDENT","81"),("Chambrelent","FULL_SECTION_MEMBER","148"),
        ("Geikie","CORRESPONDENT","470"),("G. Sire","CORRESPONDENT","509"),
        ("de Serpa Pinto","CORRESPONDENT","846"),("le Prince Albert de Monaco","CORRESPONDENT","930"),
        ("Moissan","FULL_SECTION_MEMBER","1298")]
    assert [(r["elected_name_candidate"],r["election_role_candidate"],r["original_printed_volume_page"]) for r in recovered112]==expected112,recovered112
    # Missing structural slots cannot be borrowed from surrounding prose.
    assert not parse_html(tome112.replace("class='tableDots'","class='unresolved'").encode("utf-8"),112,1891)[0]
    assert not parse_html(tome112.replace("class='tablePage'","class='unresolved'").encode("utf-8"),112,1891)[0]
    partial_rows=[(line,"unresolved" if page=="81" else page) for line,page in actual112]
    partial,_=parse_html(floating_html(partial_rows).encode("utf-8"),112,1891)
    assert [r["elected_name_candidate"] for r in partial]==[x[0] for x in expected112[1:]],partial
    outside=tome112+floating_html([("— M. Exemple est élu Membre de la Section de Chimie, en remplacement de M. Autre", "12")])
    assert len(parse_html(outside.encode("utf-8"),112,1891)[0])==7
    external=tome112.replace("Nominations de membres et de correspondants de l’académie", "Commissions spéciales")
    assert not parse_html(external.encode("utf-8"),112,1891)[0]

    # The modern extractor already emits these nine Tome 178 records. Fix
    # Pope's empty name from its own excerpt and Rabut's missing division
    # from the three adjacent source fragments, without adding a duplicate.
    tome178="""<table><tbody>
       <tr><td><span class="sc">Elections de membres et de correspondants</span>. — M. <i>Félix Lagrange</i> est élu correspondant pour la section de médecine et chirurgie</td><td>288</td></tr>
       <tr><td>— M. <i>Maurice de Broglie</i> est élu académicien libre</td><td>744</td></tr>
       <tr><td>— M. <i>Alexandre Desgrez</i> est élu académicien libre</td><td>911</td></tr>
       <tr><td>— M. <i>Serge Winogradsky</i> est élu associé étranger</td><td>1251</td></tr>
       <tr><td>— M. <i>Edmund Beecher Wilson</i> est élu correspondant pour la section d’anatomie et zoologie</td><td>1508</td></tr>
       <tr><td>— Sur <i>William Pope</i> est élu correspondant pour la section de chimie</td><td>1592</td></tr>
       <tr><td>— M. <i>Johannes Schmidt</i> est élu correspondant pour la section d’anatomie et zoologie</td><td>1674</td></tr>
       <tr><td>— M. <i>Charles Rabut</i> est élu membre de</td></tr></tbody></table> <span><span class="pagenum ws-pagenum" id="TdM" title="Page:Comptes rendus hebdomadaires des séances de l’Académie des sciences, tome 178, 1924.djvu/2304"></span></span>
       la division des applications de la science à l’industrie
       <table><tbody><tr><td>1871</td></tr>
       <tr><td>— M. <i>Giovanni Battista De Toni</i> est élu correspondant pour la section de botanique</td><td>2155</td></tr>
       <tr><td><span class="sc">Electricité</span></td></tr></tbody></table>"""
    recovered178,_=parse_html(tome178.encode("utf-8"),178,1924)
    assert len(recovered178)==9 and all(r["elected_name_candidate"] for r in recovered178),recovered178
    pope=next(r for r in recovered178 if r["original_printed_volume_page"]=="1592")
    assert (pope["elected_name_candidate"],pope["election_role_candidate"],pope["source_action_wording"],pope["science_section_candidate"])==(
        "Sur William Pope","CORRESPONDENT","EST_ELU_TRANSCRIBED","chimie"),pope
    rabut=next(r for r in recovered178 if r["elected_name_candidate"]=="Charles Rabut")
    assert (rabut["election_role_candidate"],rabut["original_printed_volume_page"],rabut["science_section_candidate"])==(
        "FULL_SECTION_MEMBER","1871","division des applications de la science à l’industrie"),rabut
    for incomplete in (tome178.replace("la division des applications de la science à l’industrie",""),
                       tome178.replace("<td>1871</td>","<td>unresolved</td>")):
        rows,_=parse_html(incomplete.encode("utf-8"),178,1924)
        row=next(r for r in rows if r["elected_name_candidate"]=="Charles Rabut")
        assert not row["science_section_candidate"],row
    assert all(r[field]=="0" for r in recovered83+recovered112+recovered178 for field in (
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
