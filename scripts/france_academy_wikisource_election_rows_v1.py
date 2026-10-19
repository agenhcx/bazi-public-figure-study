#!/usr/bin/env python3
"""Bounded Wikisource transcription evidence of Académie des sciences elections.

The historical Comptes rendus is Academy-authored, but Wikisource index HTML
is a *transcription*, not the inspected original printed event page.
Membership-class candidates require original-page verification before accepted.
No DOB/Academy study acceptance or BaZi calculation.
"""
from __future__ import annotations
import argparse,csv,hashlib,json,re,time,unicodedata
from collections import Counter,defaultdict
from pathlib import Path
from bs4 import BeautifulSoup
from france_academy_wikisource_index_preflight_v1 import read_one,build_urls,TRIAL

VERSION="france-academy-wikisource-original-journal-index-election-source-v1_4"
CTHS="data/france_academy_cths_profile_dob_harvest_v1/cths_dob_claims_all_targets_candidate_only_v1.csv"
OUT="local_runs/france_academy_wikisource_election_index_v1"
FIELDS=["original_journal_issuer","transcription_site","year","original_volume","printed_election_page","page_reconstructed_from_continuation_row",
        "transcription_url","source_html_sha256","transcribed_elected_person_name",
        "transcribed_election_type","transcribed_science_section","event_evidence_class",
        "cths_562_exact_name_candidate_id","cths_562_name_match_status",
        "transcribed_line_excerpt","original_book_event_page_opened",
        "frozen_french_academy_full_membership_accepted","frozen_study_dob_accepted",
        "bazi_variables_computed"]
FULL={"FULL_SECTION_MEMBER","FULL_NONRESIDENT_MEMBER","FULL_ACADEMICIAN_LIBRE"}
OTHER={"CORRESPONDENT","FOREIGN_ASSOCIATE","OFFICE_ELECTION_NOT_NEW_MEMBER","UNKNOWN_ROLE_MANUAL"}
def norm(s):
    s=unicodedata.normalize("NFKD",str(s).casefold())
    s="".join(c for c in s if not unicodedata.combining(c))
    return " ".join(re.findall("[a-z0-9]+",s.replace("œ","oe").replace("æ","ae")))
def identity_key(name):
    return " ".join(sorted(norm(name).split()))
def data_csv(p):
    with Path(p).open(encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
def write_csv(p,items,cols):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=cols,extrasaction="ignore")
        w.writeheader();w.writerows(items)
def role_of(line):
    # Classify ONLY the predicate following "est élu"; a section heading
    # mentioning "membres et correspondants" must NOT turn the full election
    # into a corresponding election. Replacement names must also be ignored.
    full=norm(line)
    m=re.search(r"\b(est|a ete|sont)\s+elue?s?\b",full)
    if not m:return ""
    clause=re.split(r"\ben remplacement\b|\bdecede\b",full[m.end():],maxsplit=1)[0]
    if re.search(r"\bcorrespondant\b",clause):return "CORRESPONDENT"
    if "associe etranger" in clause:return "FOREIGN_ASSOCIATE"
    # Tome 98 uses "Membre libre" for Haton de la Goupillière,
    # de Jonquières and Cailletet: preserve that class before generic membre.
    if "academicien libre" in clause or "membre libre" in clause:return "FULL_ACADEMICIAN_LIBRE"
    if "membre non residant" in clause or "membre non resident" in clause:
        return "FULL_NONRESIDENT_MEMBER"
    if re.search(r"\b(secretaire perpetuel|president|vice president|directeur)\b",clause):
        return "OFFICE_ELECTION_NOT_NEW_MEMBER"
    if re.search(r"\bmembre\b",clause):return "FULL_SECTION_MEMBER"
    # 1839 index: elected "pour la place vacante dans la section".
    # Role is CONTEXTUAL, not an approved original full-membership class.
    if "place vacante" in clause and "section" in clause:
        return "FULL_SECTION_MEMBER_CONTEXTUAL_ELECTION"
    return "UNKNOWN_ROLE_MANUAL"
def person_of(line):
    # One named person elected; other people after "en remplacement de" are not elected.
    m=re.search(r"\bM(?:\.|\s)\s*(.{2,125}?)\s+est\s+[ée]lu(?:e)?\b",line,re.I)
    if not m:
        # Historical volumes also explicitly elect foreign associates as
        # "Sir Ernest Rutherford est élu Associé étranger" (Tome 185, p1424).
        # Tome 128 p656 also explicitly elects "Le R. P. Colin".
        # Do NOT drop a named appointee because the M. honorific is absent.
        m=re.search(r"\b(?:Sir|Lady|Lord|Mme|Mlle|Le\s+R\.\s*P\.)\s+(.{2,125}?)\s+est\s+[ée]lu(?:e)?\b",line,re.I)
    if not m:return ""
    name=re.sub(r"\s+"," ",m.group(1)).strip(" ;,-.")
    if not name or len(name)>110 or " et " in name.lower():return ""
    return name
def section_of(line):
    # Use the elected person's subject section, not a replacement person's role.
    # Preserve original French labels, but do not guess a section when absent.
    elected=re.split(r"\ben remplacement\b",line,maxsplit=1,flags=re.I)[0]
    m=re.search(r"\bsection\s+(?:de\s+|d['’])(.+?)(?:[,;.]|$)",elected,re.I)
    if m:
        section=re.sub(r"\s+"," ",m.group(1)).strip(" -")
        return section[:100]
    m=re.search(r"\bdivision\s+des\s+(.+?)(?:[,;.]|$)",elected,re.I)
    if m:return "division des "+m.group(1).strip()[:95]
    return ""
def extract_from_html(raw,year,vol):
    soup=BeautifulSoup(raw,"html.parser")
    actual=[]
    heads=[]
    current=""
    for tr in soup.find_all("tr"):
        cells=tr.find_all("td",recursive=False)
        if not cells:continue
        first=cells[0]
        line=" ".join(first.get_text(" ",strip=True).split())
        if not line:continue
        headings=first.find_all("span",class_=re.compile("sc"))
        # Exact small-cap subject heading, distinct from ordinary cross references.
        heading=norm(" ".join(headings[0].get_text(" ",strip=True).split())) if headings else ""
        if heading:
            heads.append(heading[:90])
            if heading.startswith("election") and ("membre" in heading or "correspondant" in heading or heading=="elections"):
                current="ELECTIONS"
            else:current="OTHER"
        if current!="ELECTIONS":continue
        # Split across adjacent index rows: e.g. 1926 Fredericq
        # ends in "en remplacement de" and next line lists Bergonié, page 551.
        if actual and not actual[-1]["printed_election_page"] and not headings:
            trailing_page=" ".join(cells[1].get_text(" ",strip=True).split()) if len(cells)>1 else ""
            if not trailing_page and re.fullmatch(r"\d{1,5}",line):
                trailing_page=line
            if (re.fullmatch(r"\d{1,5}",trailing_page) and
                not re.search(r"\b(est|a été|sont)\s+élu",line,re.I) and
                (line.startswith(("M.","MM.","Mme","Mlle")) or re.fullmatch(r"\d{1,5}",line))):
                actual[-1]["printed_election_page"]=trailing_page
                actual[-1]["page_reconstructed_from_continuation_row"]="1"
                continue
        if not re.search(r"\b(est|a été|sont)\s+élu",line,re.I):continue
        category=role_of(line)
        if not category:continue
        page = " ".join(cells[1].get_text(" ",strip=True).split()) if len(cells)>1 else ""
        if not re.fullmatch(r"\d{1,5}",page):page=""
        elected=person_of(line)
        actual.append({"year":str(year),"original_volume":str(vol),
                       "printed_election_page":page,
                       "page_reconstructed_from_continuation_row":"0",
                       "transcribed_elected_person_name":elected,
                       "transcribed_election_type":category,
                       "transcribed_science_section":section_of(line),
                       "transcribed_line_excerpt":line[:340],
                       "event_evidence_class": "ORIGINAL_JOURNAL_INDEX_WIKISOURCE_TRANSCRIPTION_ONLY",
                       "original_book_event_page_opened":"0",
                       "frozen_french_academy_full_membership_accepted":"0",
                       "frozen_study_dob_accepted":"0",
                       "bazi_variables_computed":"0"})
    return actual,heads
def smoke():
    rows="""<table><tr><td><span class="sc">Élections de membres et de correspondants.</span> — M. Camille Matignon est élu membre de la section de chimie en remplacement de M. Haller</td><td>303</td></tr>
<tr><td>— M. Léon Fredericq est élu correspondant pour la section de médecine et chirurgie</td><td>551</td></tr>
<tr><td>— M. Victor Grignard est élu membre non résidant</td><td>1366</td></tr>
<tr><td>— M. Emile Picard est élu secrétaire perpétuel</td><td>1400</td></tr>
<tr><td><span class="sc">Décrets.</span> — Approuvant l'élection de Matignon</td><td>421</td></tr>
<tr><td>— M. Faux est élu membre de la section de chimie</td><td>600</td></tr></table>"""
    found,h=extract_from_html(rows.encode(),1926,182)
    assert len(found)==4,(found,h)
    assert [x["transcribed_election_type"] for x in found]==[
         "FULL_SECTION_MEMBER","CORRESPONDENT","FULL_NONRESIDENT_MEMBER","OFFICE_ELECTION_NOT_NEW_MEMBER"]
    assert [x["printed_election_page"] for x in found]==["303","551","1366","1400"]
    assert found[0]["transcribed_elected_person_name"]=="Camille Matignon"
    assert person_of("— Sir Ernest Rutherford est élu Associé étranger en remplacement de Walcott")=="Ernest Rutherford"
    assert person_of("— M Owen est élu correspondant pour la section d’Anatomie")=="Owen"
    assert person_of("— Le R. P. Colin est élu Correspondant pour la Section de Géographie et Navigation, en remplacement de M. Manen")=="Colin"
    assert role_of("— M. Haton de la Goupillière est élu Membre libre en remplacement de feu M. de la Gournerie")=="FULL_ACADEMICIAN_LIBRE"
    assert role_of("— M. Boussingault est élu pour la place vacante dans la section d’Économie rurale")=="FULL_SECTION_MEMBER_CONTEXTUAL_ELECTION"
    assert found[0]["transcribed_science_section"]=="chimie"
    assert found[1]["transcribed_elected_person_name"]=="Léon Fredericq"
    assert norm("ÉMILE Picard")=="emile picard"
    assert found[0]["frozen_french_academy_full_membership_accepted"]=="0"
    print("PASS: academic roles split; table-section scope; decrees and elections not conflated")
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--fixture-check",action="store_true")
    ap.add_argument("--out",default=OUT)
    ap.add_argument("--limit",type=int,default=5)
    ap.add_argument("--delay",type=float,default=1.5)
    args=ap.parse_args()
    if args.fixture_check:smoke();return
    if not 1<=args.limit<=5 or args.delay<1.1:raise ValueError("Pilot limit 1-5 and delay >=1.1 s")
    cths=data_csv(CTHS)
    if len(cths)!=562:raise RuntimeError("FROZEN CTHS input changed")
    bykey=defaultdict(list)
    for r in cths:bykey[identity_key(r["name"])].append(r)
    source_audit=[]
    rows=[]
    for index,(vol,year) in enumerate(TRIAL[:args.limit]):
        url=build_urls(vol,year)["wiki"]
        code,mime,raw=read_one(url,800000)
        digest=hashlib.sha256(raw).hexdigest()
        found,heads=extract_from_html(raw,year,vol)
        for event in found:
            k=identity_key(event["transcribed_elected_person_name"])
            matches=bykey.get(k,[]) if event["transcribed_elected_person_name"] else []
            event.update({"original_journal_issuer":"Académie des sciences (Comptes rendus)",
                 "transcription_site":"French Wikisource",
                 "transcription_url":url,"source_html_sha256":digest,
                 "cths_562_exact_name_candidate_id":matches[0]["cths_person_id"] if len(matches)==1 else "",
                 "cths_562_name_match_status":"ONE_UNIQUE_EXACT_TOKEN_CTHS_562_CANDIDATE" if len(matches)==1 else
                       "NO_EXACT_CTHS_562_MATCH" if not matches else "MULTIPLE_EXACT_CTHS_562_MATCHES"})
            rows.append(event)
        stat=Counter(x["transcribed_election_type"] for x in found)
        audit={"year":year,"volume":vol,"response_code":code,"content_type":mime,
               "bytes":len(raw),"html_sha256":digest,"transcription_url":url,
               "headings_present":len(heads),"elections_section_headings":[h for h in heads if h.startswith("election")][:12],
               "election_rows":len(found),"event_types":dict(stat),
               "printed_pages_missing":sum(not x["printed_election_page"] for x in found),
               "printed_pages_recovered_from_continuation":sum(x["page_reconstructed_from_continuation_row"]=="1" for x in found),
               "rows_unparsed_person":sum(not x["transcribed_elected_person_name"] for x in found),
               "source_is_wikisource_transcription":True,"original_event_pages_opened":0}
        source_audit.append(audit)
        print("VOLUME",json.dumps(audit,ensure_ascii=False))
        if index+1<args.limit:time.sleep(args.delay)
    out=Path(args.out)
    out.mkdir(parents=True,exist_ok=True)
    rows.sort(key=lambda x:(int(x["year"]),int(x["original_volume"]),
                            int(x["printed_election_page"] or 0),x["transcribed_elected_person_name"]))
    write_csv(out/"academy_transcribed_election_events_pilot_v1.csv",rows,FIELDS)
    types=Counter(x["transcribed_election_type"] for x in rows)
    summary={"version":VERSION,"source": "Academy-authored historical Comptes rendus; Wikisource index transcriptions",
             "pilot_volumes":args.limit,"source_audit":source_audit,
             "all_transcribed_election_rows":len(rows),
             "full_member_category_source_candidates":sum(types[k] for k in FULL),
             "correspondent_or_foreign_source_candidates":types["CORRESPONDENT"]+types["FOREIGN_ASSOCIATE"],
             "other_election_rows_manual":sum(types[k] for k in OTHER if k not in ("CORRESPONDENT","FOREIGN_ASSOCIATE")),
             "role_counts":dict(types),
             "exact_name_only_matched_cths_562_events":sum(x["cths_562_name_match_status"]=="ONE_UNIQUE_EXACT_TOKEN_CTHS_562_CANDIDATE" for x in rows),
             "frozen_cths_562_unchanged":True,
             "original_journal_event_pages_opened":0,"cohort_frozen":False,
             "accepted_french_academy_full_members":0,"accepted_exact_dobs":0,"bazi_variables_computed":0}
    (out/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    print("TOTAL",json.dumps({k:summary[k] for k in ("all_transcribed_election_rows",
         "full_member_category_source_candidates","correspondent_or_foreign_source_candidates",
         "other_election_rows_manual","role_counts","exact_name_only_matched_cths_562_events")},
         ensure_ascii=False))
    print("SAMPLE_FULL",json.dumps([
         {k:r[k] for k in ("year","transcribed_elected_person_name","transcribed_election_type","printed_election_page","cths_562_exact_name_candidate_id")}
         for r in rows if r["transcribed_election_type"] in FULL][:24],ensure_ascii=False))
if __name__=="__main__":main()
