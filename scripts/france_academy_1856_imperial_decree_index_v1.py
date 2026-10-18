#!/usr/bin/env python3
"""1856 Académie des sciences nominal appointment vs imperial-decree index pilot.

Public Wikisource indexes of Academy-authored original Comptes rendus, Tomes
42-43. The index is a transcription, NOT the opened original appointment or
decree; suffix/initial aliases and same-name cases require human review.
No accepted Academy membership, DOB or BaZi output.
"""
from __future__ import annotations
import argparse,csv,hashlib,json,re,time,urllib.error
from collections import Counter
from pathlib import Path
from bs4 import BeautifulSoup
from france_academy_wikisource_index_preflight_v1 import build_urls,read_one
from france_academy_wikisource_legacy_election_headings_v1 import parse_html,fold
from france_academy_wikisource_election_rows_v1 import identity_key

VERSION="france-academy-1856-imperial-decree-source-only-v1"
OUT=Path("data/france_academy_1856_imperial_decree_index_v1")
YEARS=[(42,1856),(43,1856)]
COLS=["volume","year","appointment_name_original_index",
      "appointment_member_role_candidate","appointment_original_page",
      "decree_name_original_index","decree_original_page",
      "index_stage_link_status","person_identity_comparison",
      "index_source_url","source_html_sha256",
      "imperial_approval_original_document_opened","effective_member_date_adjudicated",
      "official_full_membership_accepted","study_exact_dob_accepted","bazi_variables_computed"]

def text(s):return " ".join((s or "").split())

def decree_nominees(raw):
    """Accept only nominated-academician imperial decree entries and continuations.

    A decree about gifts/awards is never a member appointment. A previous
    section heading alone does not establish approved nominees.
    """
    soup=BeautifulSoup(raw,"html.parser")
    out=[]
    in_imperial=False
    for tr in soup.find_all("tr"):
        cells=tr.find_all("td",recursive=False)
        if not cells:continue
        td=cells[0]
        line=text(td.get_text(" ",strip=True))
        if not line:continue
        ref=text(cells[1].get_text(" ",strip=True)) if len(cells)>1 else ""
        page=ref if re.fullmatch(r"\d{1,5}",ref) else ""
        decorated=td.find("span",class_=re.compile("sc",re.I))
        h=text(decorated.get_text(" ",strip=True)) if decorated else line.split("—",1)[0].strip(" .")
        if fold(h).startswith("decrets imperiaux"):
            in_imperial=True
        elif decorated and not fold(h).startswith("decrets imperiaux"):
            in_imperial=False
        elif not line.startswith(("—","-")) and not fold(line).startswith("decrets imperiaux"):
            in_imperial=False
        if not in_imperial:continue
        # The 1856 upper-half source opens with a collective decree header,
        # followed by three person entries. Its second half instead has a
        # singular inline decree confirming Hermite.
        m=(re.search(r"\bd[ée]cret\s+confirmant\s+la\s+nomination\s+de\s+M\.\s+(.+)",line,re.I)
           or re.search(r"(?:^|[—–]\s*)la\s+nomination\s+de\s+M\.\s+(.+)",line,re.I)
           or re.search(r"^[—–]\s*de\s+M\.\s+(.+)",line,re.I))
        if not m:continue
        claim=re.split(r"\s*(?:\(|\ben remplacement\b|\bà la place\b|\bdans la section\b)",m.group(1),maxsplit=1,flags=re.I)[0]
        name=text(claim).strip(" ,-.:;")
        if not name:continue
        out.append({"person":name,"page":page,"source_excerpt":line[:230]})
    return out

def rows_for(volume,year,raw):
    events,_=parse_html(raw,volume,year)
    decrees=decree_nominees(raw)
    url=build_urls(volume,year)["wiki"]
    sha=hashlib.sha256(raw).hexdigest()
    by_name={}
    for d in decrees:
        by_name.setdefault(identity_key(d["person"]),[]).append(d)
    linked=[]
    used=set()
    for e in events:
        name=e["elected_name_candidate"]
        matches=by_name.get(identity_key(name),[]) if name else []
        if len(matches)==1:
            d=matches[0]
            status="INDEX_APPOINTMENT_AND_IMPERIAL_DECREE_EXACT_NAME_CANDIDATE"
            used.add((d["person"],d["page"]))
        elif len(matches)>1:
            d=None
            status="MULTIPLE_DECREE_INDEX_NAMES_MANUAL"
        else:
            d=None
            status="NO_EXACT_DECREE_NAME_IN_VOLUME_UNKNOWN"
        linked.append({"volume":str(volume),"year":str(year),
           "appointment_name_original_index":name,
           "appointment_member_role_candidate":e["election_role_candidate"],
           "appointment_original_page":e["original_printed_volume_page"],
           "decree_name_original_index":d["person"] if d else "",
           "decree_original_page":d["page"] if d else "",
           "index_stage_link_status":status,
           "person_identity_comparison":"NORMALIZED_EXACT_STRING_LEAD_NOT_VERIFIED_IDENTITY",
           "index_source_url":url,"source_html_sha256":sha,
           "imperial_approval_original_document_opened":"0",
           "effective_member_date_adjudicated":"0",
           "official_full_membership_accepted":"0","study_exact_dob_accepted":"0",
           "bazi_variables_computed":"0"})
    unmatched=[{"volume":volume,"year":year,"decree_name":d["person"],
                "decree_page":d["page"],"original_index_excerpt":d["source_excerpt"],
                "source_url":url,"source_html_sha256":sha,
                "review_reason":"ABBREVIATED_NAME_OR_DIFFERENT_SOURCE_FORM_OR_OTHER_EVENT"}
                for d in decrees if (d["person"],d["page"]) not in used]
    return linked,unmatched,{"volume":volume,"year":year,
         "candidate_appointments":len(events),
         "imperial_decree_index_claims":len(decrees),
         "exact_name_stage_links":len(used),
         "unmatched_decree_name_forms":len(unmatched),
         "source_sha256":sha,"source_url":url,
         "opened_original_vote_or_decree_event_pages":0}

def output(path,rows,fields):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore")
        w.writeheader();w.writerows(rows)

def fixture():
    html="""<table>
    <tr><td><span class="sc">NOMINATIONS de Membres et de Correspondants de l’Académie.</span> — M. Hermite est nommé à la place vacante dans la Section de Géométrie par suite du décès de M. Binet</td><td>85</td></tr>
    <tr><td>— M. W. Hooker est nommé Correspondant de l’Académie, Section de Botanique</td><td>1143</td></tr>
    <tr><td><span class="sc">Décrets impériaux.</span> — Décret confirmant la nomination de M. Hermite à la place vacante dans la Section de Géométrie</td><td>169</td></tr>
    <tr><td>— Décret autorisant le legs Barbier</td><td>621</td></tr>
    <tr><td><span class="sc">Dextrine</span> — rapport</td><td>908</td></tr></table>""".encode("utf-8")
    x,u,s=rows_for(43,1856,html)
    assert len(x)==2 and not u,s
    assert len(decree_nominees(html))==1
    assert x[0]["appointment_name_original_index"]=="Hermite"
    assert x[0]["decree_original_page"]=="169"
    assert x[1]["index_stage_link_status"]=="NO_EXACT_DECREE_NAME_IN_VOLUME_UNKNOWN"
    assert s["opened_original_vote_or_decree_event_pages"]==0
    assert all(r["official_full_membership_accepted"]=="0" for r in x)
    print("PASS: 1856 emperor-decree confirmation index linked to Academy Hermite nomination, not to Hooker correspondent")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--fixture-check",action="store_true")
    ap.add_argument("--limit",type=int,default=2)
    ap.add_argument("--delay",type=float,default=1.5)
    ap.add_argument("--out",type=Path,default=OUT)
    a=ap.parse_args()
    if a.fixture_check:fixture();return
    if a.delay<1.2 or a.limit not in (1,2):raise ValueError("Max two 1856 volumes")
    out=[];unmatched=[];sources=[]
    for i,(volume,year) in enumerate(YEARS[:a.limit]):
        if i:time.sleep(a.delay)
        url=build_urls(volume,year)["wiki"]
        try:
            status,mime,raw=read_one(url,900000)
            if status!=200:raise ValueError("Unrecognized source status")
            rows,notlinked,info=rows_for(volume,year,raw)
            out.extend(rows);unmatched.extend(notlinked);sources.append(info)
        except (urllib.error.HTTPError,urllib.error.URLError,TimeoutError,ValueError) as e:
            sources.append({"volume":volume,"year":year,
                "fetch_error":type(e).__name__+":"+str(e)[:100],
                "source_unavailable_is_not_zero_members":True})
            break
    output(a.out/"imperial_1856_appointment_decree_chain_candidates_v1.csv",out,COLS)
    output(a.out/"manual_decree_alias_review_v1.csv",unmatched,
        ["volume","year","decree_name","decree_page","original_index_excerpt","source_url","source_html_sha256","review_reason"])
    summary={"version":VERSION,"journal_source_tier":"WIKISOURCE_INDEX_TRANSCRIPTION_ONLY",
       "sources":sources,"appointment_records":len(out),
       "decree_index_name_claims":sum(x.get("imperial_decree_index_claims",0) for x in sources),
       "exact_name_links":sum(r["index_stage_link_status"]=="INDEX_APPOINTMENT_AND_IMPERIAL_DECREE_EXACT_NAME_CANDIDATE" for r in out),
       "unmatched_decree_name_forms":len(unmatched),
       "approval_decree_original_pages_opened":0,"ratification_legal_date_adjudicated":0,
       "accepted_member_persons":0,"accepted_birthdates":0,"bazi_variables_computed":0}
    a.out.mkdir(parents=True,exist_ok=True)
    (a.out/"summary.json").write_text(json.dumps(summary,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print("SUMMARY",json.dumps(summary,ensure_ascii=False))
    print("MATCHES",[(r["appointment_name_original_index"],r["decree_name_original_index"],r["appointment_original_page"],r["decree_original_page"]) for r in out if r["decree_name_original_index"]])
if __name__=="__main__":main()
