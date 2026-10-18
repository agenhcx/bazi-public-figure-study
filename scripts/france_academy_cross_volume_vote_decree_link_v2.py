#!/usr/bin/env python3
"""Two-half-year Academy election-to-approval index provenance crosswalk.

Important: Wixisource HISTORICAL TABLE TRANSCRIPT is not the underlying signed
decree, and approval date/effective member status are never inferred.
Elections and government approvals are different stages of the same person's
membership event, NOT independent new full memberships. Python 3.10+ BS4.
"""
from __future__ import annotations
import argparse,csv,hashlib,json,re,time,urllib.error
from collections import Counter,defaultdict
from pathlib import Path
from bs4 import BeautifulSoup
from france_academy_wikisource_index_preflight_v1 import build_urls,read_one
from france_academy_wikisource_legacy_election_headings_v1 import parse_html
from france_academy_wikisource_election_rows_v1 import identity_key
from france_academy_vote_decree_index_link_v1 import parse_decrees as old_parse_decrees

VERSION="france-academy-cross-volume-vote-decree-index-v2"
YEAR_PAIRS=[(1926,182,183),(1934,198,199)]
OUT=Path("data/france_academy_cross_volume_vote_decree_pilot_v2")
MEMBER_ROLES={"FULL_SECTION_MEMBER","FULL_ACADEMICIAN_LIBRE","FULL_NONRESIDENT_MEMBER"}
FIELDS=[
 "election_year","election_volume","person_elected","original_election_printed_page",
 "election_role_type","approval_year","approval_volume","approval_name",
 "original_approval_notice_printed_page","approval_line_kind",
 "event_chain_status","cross_volume_match","match_identity_basis",
 "election_index_source_url","election_index_source_sha256",
 "approval_index_source_url","approval_index_source_sha256",
 "approval_original_decree_date","approval_original_decree_document_opened",
 "original_election_printed_page_opened","study_member_acceptance",
 "study_exact_birthdate_acceptance","bazi_variables_computed"]

def clean(s):
    return " ".join(str(s or "").split())

def approvals_also_lowercase(raw):
    """Recover '— décrets. — Approuvant...' modern index style unrecognized
    by the original <span class=sc> Décrets parser, without falsely treating
    'Id. de' used in unrelated sections as approval.
    """
    soup=BeautifulSoup(raw,"html.parser")
    found=[]
    for tr in soup.find_all("tr"):
        cells=tr.find_all("td",recursive=False)
        if not cells:continue
        line=clean(cells[0].get_text(" ",strip=True))
        if not line:continue
        if not re.search(r"^(?:[—–]\s*)?décrets?\s*\.\s*[—–]\s*approuvant\s+l['’]élection\s+de\s+M\.",line,re.I):
            continue
        m=re.search(r"approuvant\s+l['’]élection\s+de\s+M\.\s+(.+)",line,re.I)
        if not m:continue
        suffix=m.group(1)
        suffix=re.split(r"\s+(?:dans|comme|parmi|en remplacement|à la section)\b",suffix,maxsplit=1,flags=re.I)[0]
        name=clean(suffix.split(",",1)[0]).strip(" -.,;")
        page=clean(cells[1].get_text(" ",strip=True)) if len(cells)>1 else ""
        if not re.fullmatch(r"\d{1,5}",page):page=""
        if not name:continue
        found.append({"name":name,"page":page,"kind":"EXPLICIT_LOWERCASE_INLINE_DECREE_HEADING",
                      "line_excerpt":line[:300]})
    return found

def parse_all_decrees(raw):
    original=old_parse_decrees(raw)
    supplemental=approvals_also_lowercase(raw)
    merged={}
    for row in original+supplemental:
        if not row["name"]:continue
        k=(identity_key(row["name"]),row["page"])
        if k not in merged:merged[k]=row
    return list(merged.values())

def choose_links(indexes):
    """Candidate events retained exactly once; attach at most one decree from
    the same volume or immediately following volume.  Exact name-token match
    never implies final identity acceptance without original pages.
    """
    approvals=defaultdict(list)
    elections=[]
    for x in indexes:
        for r in x["approval_events"]:
            if not r["name"]:continue
            approvals[identity_key(r["name"])].append((x,r))
        for r in x["election_events"]:
            elections.append((x,r))
    rows=[]
    approvals_used=set()
    for src,e in elections:
        name=e["elected_name_candidate"]
        key=identity_key(name) if name else ""
        applicable=[(x,d) for x,d in approvals.get(key,[])
                    if x["volume"] in (src["volume"],src["volume"]+1)]
        if not applicable:
            state="NO_MATCH_IN_THIS_OR_NEXT_VOLUME_NOT_NEGATIVE_EVIDENCE"
            sel=None
        elif len(applicable)>1:
            state="MULTIPLE_DECREE_INDEX_MATCHES_REQUIRES_HUMAN_REVIEW"
            sel=None
        else:
            sel=applicable[0]
            state=("LINKED_SAME_VOLUME_INDEX_ONLY" if sel[0]["volume"]==src["volume"]
                   else "LINKED_NEXT_VOLUME_INDEX_ONLY")
            approvals_used.add((sel[0]["volume"],identity_key(sel[1]["name"]),sel[1]["page"]))
        rows.append({
            "election_year":str(src["year"]),
            "election_volume":str(src["volume"]),
            "person_elected":name,
            "original_election_printed_page":e["original_printed_volume_page"],
            "election_role_type":e["election_role_candidate"],
            "approval_year":str(sel[0]["year"]) if sel else "",
            "approval_volume":str(sel[0]["volume"]) if sel else "",
            "approval_name":sel[1]["name"] if sel else "",
            "original_approval_notice_printed_page":sel[1]["page"] if sel else "",
            "approval_line_kind":sel[1]["kind"] if sel else "",
            "event_chain_status":state,
            "cross_volume_match":"1" if sel and sel[0]["volume"]!=src["volume"] else "0",
            "match_identity_basis":"EXACT_NORMALIZED_FULL_NAME_TOKENS_ONLY_NOT_FINAL_PERSON_ID",
            "election_index_source_url":src["url"],"election_index_source_sha256":src["sha256"],
            "approval_index_source_url":sel[0]["url"] if sel else "",
            "approval_index_source_sha256":sel[0]["sha256"] if sel else "",
            "approval_original_decree_date":"",
            "approval_original_decree_document_opened":"0",
            "original_election_printed_page_opened":"0",
            "study_member_acceptance":"0","study_exact_birthdate_acceptance":"0",
            "bazi_variables_computed":"0"})
    not_linked=[{"year":x["year"],"volume":x["volume"],"name":d["name"],"page":d["page"],"kind":d["kind"],
                 "source_url":x["url"],"source_sha256":x["sha256"]}
                for x in indexes for d in x["approval_events"] if d["name"] and
                (x["volume"],identity_key(d["name"]),d["page"]) not in approvals_used]
    return rows,not_linked

def identity_source(volume,year,events,decrees):
    return {"volume":volume,"year":year,
        "url":f"https://example.org/v/{volume}","sha256":"f"*64,
        "election_events":events,"approval_events":decrees}

def fixture():
    def vote(name,role,page):
        return {"elected_name_candidate":name,"election_role_candidate":role,
                "original_printed_volume_page":str(page)}
    def approval(name,page):
        return {"name":name,"page":str(page),"kind":"EXPLICIT_LOWERCASE_INLINE_DECREE_HEADING"}
    h=("<table><tr><td>— décrets. — Approuvant l’élection de M. Paul Langevin"
       " en remplacement de M. P. Villard</td><td>5</td></tr>"
       "<tr><td>— décrets. — Approuvant l’élection de M. Pierre Weiss parmi les membres"
       " non résidants</td><td>5</td></tr></table>").encode("utf-8")
    parsed=approvals_also_lowercase(h)
    assert [d["name"] for d in parsed]==["Paul Langevin","Pierre Weiss"],parsed
    assert [d["page"] for d in parsed]==["5","5"]
    a=identity_source(182,1926,[vote("Pierre Weiss","FULL_NONRESIDENT_MEMBER",1511)],[])
    b=identity_source(183,1926,[],[approval("Pierre Weiss",5)])
    c=identity_source(198,1934,[vote("Paul Langevin","FULL_SECTION_MEMBER",2220)],[])
    d=identity_source(199,1934,[],[approval("Paul Langevin",5)])
    rows,unlinked=choose_links([a,b,c,d])
    assert len(rows)==2 and not unlinked
    assert all(r["cross_volume_match"]=="1" and r["event_chain_status"]=="LINKED_NEXT_VOLUME_INDEX_ONLY" for r in rows)
    assert [(r["person_elected"],r["election_volume"],r["approval_volume"]) for r in rows]==[
        ("Pierre Weiss","182","183"),("Paul Langevin","198","199")]
    assert all(r["approval_original_decree_date"]=="" and r["study_member_acceptance"]=="0" for r in rows)
    print("PASS: two known true cross-volume links, inline lower-case headings, no extra admissions, no fictitious approval dates")

def write_csv(p,rows,cols):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=cols,extrasaction="ignore");w.writeheader();w.writerows(rows)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--fixture-check",action="store_true")
    p.add_argument("--pairs",type=int,default=2,help="Number of historical half-year pairs, 1 or 2")
    p.add_argument("--delay",type=float,default=1.3)
    p.add_argument("--out",type=Path,default=OUT)
    args=p.parse_args()
    if args.fixture_check:fixture();return
    if not 1<=args.pairs<=2 or args.delay<1.1:
        raise ValueError("At most two half-year pairs, >=1.1s interval")
    data=[];last=None
    audit=[]
    for year,a,b in YEAR_PAIRS[:args.pairs]:
        for volume in (a,b):
            if last is not None:time.sleep(max(0,args.delay-(time.monotonic()-last)))
            last=time.monotonic()
            url=build_urls(volume,year)["wiki"]
            try:
                status,mime,raw=read_one(url,900000)
                if status!=200:raise ValueError("Unexpected status "+str(status))
                source_hash=hashlib.sha256(raw).hexdigest()
                elected,heads=parse_html(raw,volume,year)
                approved=parse_all_decrees(raw)
                data.append({"year":year,"volume":volume,"url":url,"sha256":source_hash,
                             "election_events":elected,"approval_events":approved})
                audit.append({"year":year,"volume":volume,"status":200,"source_hash":source_hash,
                              "elections":len(elected),"approval_index_claims":len(approved),
                              "original_scan_pages_viewed":0})
            except (urllib.error.HTTPError,urllib.error.URLError,TimeoutError,ValueError) as exc:
                audit.append({"year":year,"volume":volume,"status":getattr(exc,"code","SOURCE_ERROR"),
                              "error":type(exc).__name__+":"+str(exc)[:160],
                              "failed_source_not_no_election_or_approval":True})
                break
    rows,unlinked=choose_links(data)
    write_csv(args.out/"cross_volume_vote_decree_event_chains_v2.csv",rows,FIELDS)
    write_csv(args.out/"unmatched_decree_index_manual_v2.csv",unlinked,
              ["year","volume","name","page","kind","source_url","source_sha256"])
    stats=dict(Counter(r["event_chain_status"] for r in rows))
    summary={"version":VERSION,
            "source_type":"French Wikisource transcription of Academy printed journal indexes; original decrees not opened",
            "source_audit":audit,"parsed_election_event_rows":len(rows),
            "source_index_vote_decree_match_counts":stats,
            "cross_volume_links":sum(r["cross_volume_match"]=="1" for r in rows),
            "all_approval_index_claims":sum(len(x["approval_events"]) for x in data),
            "unmatched_approval_index_claims":len(unlinked),
            "cross_volume_matching_window":"same_or_immediately_following_volume_only",
            "election_vs_government_approval_recorded_separately":True,
            "original_government_decree_documents_opened":0,
            "legal_approval_date_adjudicated":0,"full_study_members_accepted":0,
            "study_birthdays_accepted":0,"bazi_variables_computed":0}
    args.out.mkdir(parents=True,exist_ok=True)
    (args.out/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("SUMMARY",json.dumps(summary,ensure_ascii=False))
    print("CROSS_LINKS",json.dumps([{"name":r["person_elected"],
         "election_volume":r["election_volume"],"election_page":r["original_election_printed_page"],
         "approval_volume":r["approval_volume"],"approval_page":r["original_approval_notice_printed_page"],
         "status":r["event_chain_status"]} for r in rows if r["cross_volume_match"]=="1"],ensure_ascii=False))
if __name__=="__main__":main()
