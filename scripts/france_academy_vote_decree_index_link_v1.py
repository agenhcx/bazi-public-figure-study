#!/usr/bin/env python3
"""Link 1920s/1930s Academy election-index entries with decree-approval-index entries.

Evidence: public French Wikisource TRANSCRIPTION of the original Academy
Comptes rendus tables. Index locators only, no decree itself verified, no
implicit approval from an Academy election and no effectivity-date inference.
Python 3.10+ / beautifulsoup4. Bounded pilot, request throttling, no BaZi.
"""
from __future__ import annotations
import argparse,csv,hashlib,json,re,time,unicodedata,urllib.error
from collections import Counter
from pathlib import Path
from bs4 import BeautifulSoup
from france_academy_wikisource_index_preflight_v1 import build_urls,read_one
from france_academy_wikisource_election_rows_v1 import extract_from_html,identity_key
from france_academy_wikisource_legacy_election_headings_v1 import fold

VERSION="france-academy-vote-decree-index-link-v1"
TARGETS=[(182,1926),(198,1934),(179,1924)]
ROOT=Path("data/france_academy_vote_decree_index_link_pilot_v1")
FULL={"FULL_SECTION_MEMBER","FULL_ACADEMICIAN_LIBRE","FULL_NONRESIDENT_MEMBER"}
FIELDS=[
 "year","volume","person_name_elected","election_role_type","original_election_page_candidate",
 "approval_name_transcribed","original_decree_notice_page_candidate","approval_index_line_kind",
 "event_link_status","election_index_transcription_excerpt","decree_index_transcription_excerpt",
 "index_source_url","index_source_sha256","event_stage_1_vote_evidenced_by_index",
 "event_stage_2_government_decree_evidenced_by_index","event_stage_3_decree_original_page_opened",
 "event_stage_4_final_membership_acceptance","original_event_pages_opened",
 "study_exact_dob_accepted","bazi_variables_computed"]

def clean(s):
    return " ".join((s or "").split())

def headings(text):
    v=fold(text)
    return v.startswith("decrets") or v.startswith("decret") or v.startswith("approbations")

def parse_decrees(raw):
    soup=BeautifulSoup(raw,"html.parser")
    rows=[]
    section=None
    previous_is_approval=False
    for tr in soup.find_all("tr"):
        cells=tr.find_all("td",recursive=False)
        if not cells:continue
        first=cells[0]
        line=clean(first.get_text(" ",strip=True))
        if not line:continue
        span=first.find("span",class_=re.compile("sc"))
        if span:
            section="DECREE" if headings(span.get_text(" ",strip=True)) else "OTHER"
            previous_is_approval=False
        if section!="DECREE":continue
        page=clean(cells[1].get_text(" ",strip=True)) if len(cells)>1 else ""
        if not re.fullmatch(r"\d{1,5}",page):page=""
        # "Approuvant l'élection de M. X ..." starts approval context.
        explicit=re.search(r"\bapprouvant\s+l['’]élection\s+de\s+M\.\s+(.+)$",line,re.I)
        # For "— Id. de M. X" the immediately preceding parsed decree
        # must also be an election approval, never a free-standing Id.
        idcont=re.search(r"(?:^|[—–]\s*)Id\.\s+de\s+M\.\s+(.+)$",line,re.I)
        if explicit:
            mode="EXPLICIT_APPRouvant_ELECTION"
            remainder=explicit.group(1)
            previous_is_approval=True
        elif idcont and previous_is_approval:
            mode="ANAPHORIC_ID_PREVIOUS_APPROVAL"
            remainder=idcont.group(1)
        else:
            previous_is_approval=False
            continue
        # Ignore a predecessor name after "en remplacement de", and preserve
        # only named person immediately after "M." and before section/status.
        remainder=re.split(r"\s+en\s+remplacement\s+de\s+",remainder,maxsplit=1,flags=re.I)[0]
        remainder=re.split(r"\s+(?:dans\s+la\s+section|dans\s+la\s+division|comme\s+membre)\b",remainder,maxsplit=1,flags=re.I)[0]
        name=clean(remainder.split(",",1)[0]).strip(" .;:-")
        if not name or len(name)>110 or name.lower().startswith("m."):
            rows.append({"name":"","page":page,"kind":"UNPARSED_APPROVAL_NAME_MANUAL",
                         "line_excerpt":line[:300]})
        else:
            rows.append({"name":name,"page":page,"kind":mode,
                         "line_excerpt":line[:300]})
    return rows

def link_elections(elections,decrees,volume,year,url,digest):
    approvals={}
    for d in decrees:
        if not d["name"]:continue
        key=identity_key(d["name"])
        approvals.setdefault(key,[]).append(d)
    rows=[]
    matched_indexes=set()
    for e in elections:
        name=e["transcribed_elected_person_name"]
        key=identity_key(name) if name else ""
        candidates=approvals.get(key,[])
        if not candidates:
            state="ELECTION_NO_MATCHED_DECREE_IN_THIS_INDEX_NOT_NEGATIVE_EVIDENCE"
            selected=None
        elif len(candidates)>1:
            state="MULTIPLE_DECREE_INDEX_CLAIMS_MANUAL"
            selected=None
        else:
            state="ELECTION_PLUS_DECREE_INDEX_LINK_CANDIDATE"
            selected=candidates[0]
            matched_indexes.add(key)
        rows.append({
            "year":str(year),"volume":str(volume),"person_name_elected":name,
            "election_role_type":e["transcribed_election_type"],
            "original_election_page_candidate":e["printed_election_page"],
            "approval_name_transcribed":selected["name"] if selected else "",
            "original_decree_notice_page_candidate":selected["page"] if selected else "",
            "approval_index_line_kind":selected["kind"] if selected else "",
            "event_link_status":state,
            "election_index_transcription_excerpt":e["transcribed_line_excerpt"][:300],
            "decree_index_transcription_excerpt":selected["line_excerpt"] if selected else "",
            "index_source_url":url,"index_source_sha256":digest,
            "event_stage_1_vote_evidenced_by_index":"1",
            "event_stage_2_government_decree_evidenced_by_index":"1" if selected else "0",
            "event_stage_3_decree_original_page_opened":"0",
            "event_stage_4_final_membership_acceptance":"0",
            "original_event_pages_opened":"0","study_exact_dob_accepted":"0",
            "bazi_variables_computed":"0"})
    unmatched=[d for d in decrees if not d["name"] or identity_key(d["name"]) not in matched_indexes]
    return rows,unmatched

def write_csv(p,rows,fields):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open("w",newline="",encoding="utf-8-sig") as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore")
        w.writeheader();w.writerows(rows)

def fixture():
    html=b"""<table>
    <tr><td><span class="sc">D\xc3\xa9crets</span>. \xe2\x80\x94 Approuvant l\xe2\x80\x99\xc3\xa9lection de M. Camille Matignon dans la section de chimie, en remplacement de M. Haller.</td><td>421</td></tr>
    <tr><td>\xe2\x80\x94 Id. de M. Georges Perrier dans la section de g\xc3\xa9ographie et navigation</td><td>549</td></tr>
    <tr><td>\xe2\x80\x94 Id. de M. Jean Charcot, dans la division des acad\xc3\xa9miciens libres</td><td>817</td></tr>
    <tr><td>\xe2\x80\x94 Id. de M. Victor Grignard comme membre non r\xc3\xa9sidant</td><td>1497</td></tr>
    <tr><td><span class="sc">Prix</span>. \xe2\x80\x94 M. Faux est \xc3\xa9lu</td><td>1588</td></tr></table>"""
    # Decode bytes into actual unicode before feeding html parser: emulate UTF-8 source.
    html=html.decode("utf-8").encode("utf-8")
    d=parse_decrees(html)
    assert len(d)==4,d
    assert [i["page"] for i in d]==["421","549","817","1497"],d
    assert [i["name"] for i in d]==["Camille Matignon","Georges Perrier","Jean Charcot","Victor Grignard"],d
    el=[{"transcribed_elected_person_name":x,"transcribed_election_type":"FULL_SECTION_MEMBER",
         "printed_election_page":str(i*100),"transcribed_line_excerpt":"est élu"} for i,x in enumerate(
         ["Camille Matignon","Georges Perrier","Jean Charcot","Victor Grignard","Pierre Weiss"],1)]
    linked,unlinked=link_elections(el,d,182,1926,"https://example.org","f"*64)
    assert len(linked)==5 and not unlinked
    assert sum(x["event_link_status"]=="ELECTION_PLUS_DECREE_INDEX_LINK_CANDIDATE" for x in linked)==4
    assert linked[-1]["event_stage_2_government_decree_evidenced_by_index"]=="0"
    assert all(x["event_stage_4_final_membership_acceptance"]=="0" for x in linked)
    # Approval event is separate from an Academy election; never add a new member.
    print("PASS: four decree approval index links, 'Id.' context, unrelated topics excluded, no final admissions")

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--fixture-check",action="store_true")
    p.add_argument("--limit",type=int,default=3,help="At most 3 named historical volumes")
    p.add_argument("--delay",type=float,default=1.5)
    p.add_argument("--out",type=Path,default=ROOT)
    args=p.parse_args()
    if args.fixture_check:fixture();return
    if not 1<=args.limit<=3 or args.delay<1.2:
        raise ValueError("Pilot max3; >=1.2s request separation")
    rows=[];audits=[];unmatched=[]
    for i,(volume,year) in enumerate(TARGETS[:args.limit]):
        if i:time.sleep(args.delay)
        url=build_urls(volume,year)["wiki"]
        try:
            http,mime,raw=read_one(url,900000)
            if http!=200:raise ValueError("Unexpected source response "+str(http))
            digest=hashlib.sha256(raw).hexdigest()
            elections,_=extract_from_html(raw,year,volume)
            decrees=parse_decrees(raw)
            linked,missing=link_elections(elections,decrees,volume,year,url,digest)
            rows.extend(linked)
            unmatched.extend([{"volume":volume,"year":year,**x} for x in missing])
            audits.append({"volume":volume,"year":year,"http":http,"mime":mime,"source_sha256":digest,
                 "source_url":url,"election_events":len(elections),"decree_approval_claims":len(decrees),
                 "linked_decree_election_events":sum(x["event_link_status"]=="ELECTION_PLUS_DECREE_INDEX_LINK_CANDIDATE" for x in linked),
                 "index_role_distribution":dict(Counter(x["transcribed_election_type"] for x in elections)),
                 "original_printed_event_pages_opened":0})
        except (urllib.error.HTTPError,urllib.error.URLError,TimeoutError,ValueError) as exc:
            audits.append({"volume":volume,"year":year,
                 "http":getattr(exc,"code","SOURCE_ERROR"),"error":type(exc).__name__+":"+str(exc)[:140],
                 "source_unavailable_does_not_imply_zero_events":True})
            break
    write_csv(args.out/"vote_decree_link_candidates_v1.csv",rows,FIELDS)
    write_csv(args.out/"decree_unmatched_manual_v1.csv",unmatched,
              ["volume","year","name","page","kind","line_excerpt"])
    stats=Counter(x["event_link_status"] for x in rows)
    overview={"version":VERSION,"source_tier":"WIKISOURCE_TRANSCRIPTION_OF_ACADEMY_INDEX_NOT_OPENED_ORIGINAL_EVENT_PAGE",
         "source_audit":audits,"elections_parsed":len(rows),"decrees_with_no_election_link":len(unmatched),
         "status_counts":dict(stats),"links_on_full_member_class_elections":sum(
           x["event_link_status"]=="ELECTION_PLUS_DECREE_INDEX_LINK_CANDIDATE" and x["election_role_type"] in FULL
           for x in rows),
         "original_vote_event_pages_opened":0,"original_decree_approval_pages_opened":0,
         "government_approval_legally_adjudicated":0,
         "final_full_members_accepted":0,"final_exact_birthdates_accepted":0,"bazi_variables_computed":0}
    args.out.mkdir(parents=True,exist_ok=True)
    (args.out/"summary.json").write_text(json.dumps(overview,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    print("SUMMARY",json.dumps(overview,ensure_ascii=False))
    print("LINKED",json.dumps([{"year":x["year"],"person":x["person_name_elected"],
      "role":x["election_role_type"],"election_page":x["original_election_page_candidate"],
      "approval_page":x["original_decree_notice_page_candidate"],
      "status":x["event_link_status"]} for x in rows],ensure_ascii=False))
if __name__=="__main__":main()
