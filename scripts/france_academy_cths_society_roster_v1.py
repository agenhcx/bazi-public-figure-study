#!/usr/bin/env python3
"""Source-captured CTHS Académie des sciences candidate roster (society id 506).

A secondary institutional *history* dataset. Membership notes distinguish full,
correspondant and associé étranger. This is a source-discovery/adjudication input,
NOT the final frozen full-member roster and NOT an exact-DOB acceptance layer.

No BaZi transformations, inference, or "assume any membership is full" fallback.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import re
import time
import unicodedata
from collections import Counter
from pathlib import Path
from urllib.parse import urljoin, urlparse, parse_qs

import requests
from bs4 import BeautifulSoup, NavigableString, Tag

VERSION = "france-academy-cths-society-roster-v1"
SOURCE = "https://cths.fr/an/societe.php?id=506&proso=y&soc_liees="
BASE = "https://cths.fr/an/"
AGENT = "bazi-public-figure-study/1.0 (noncommercial academic audit; GitHub agenhcx/bazi-public-figure-study)"
EXPECTED_LOWER, EXPECTED_UPPER = 1000, 3500
TIMEOUT = 32
SAMPLE_PER_CATEGORY = 5

def digest(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def ascii_fold(value: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", value.lower()) if unicodedata.category(c) != "Mn")

def tidy(text: str) -> str:
    return " ".join(text.split())

def source_get(session: requests.Session, url: str, *, timeout: float, delay: float) -> bytes:
    time.sleep(delay)
    resp = session.get(url, timeout=timeout)
    resp.raise_for_status()
    if len(resp.content) > 7_000_000:
        raise RuntimeError("Unexpectedly large CTHS page")
    if b"</html" not in resp.content.lower():
        raise RuntimeError("Unexpected/non-HTML document")
    return resp.content

def extract_savant_anchors(html: bytes) -> list[Tag]:
    soup = BeautifulSoup(html, "html.parser")
    result: list[Tag] = []
    for a in soup.find_all("a", href=True):
        target = urljoin(BASE, a["href"])
        u = urlparse(target)
        if u.hostname not in ("cths.fr", "www.cths.fr"):
            continue
        if not u.path.endswith("/savant.php"):
            continue
        if not parse_qs(u.query).get("id", [""])[0].isdigit():
            continue
        result.append(a)
    return result

def surrounding_phrase(anchor: Tag) -> str:
    # The society roster prints "[NAME] (lifespan) - status, elections" in
    # adjacent nodes. Stay within one entry; never ingest all subsequent rows.
    chunks = []
    for next_node in anchor.next_siblings:
        if isinstance(next_node, Tag):
            if next_node.name in {"br", "hr", "li", "tr"}:
                break
            if next_node.find("a", href=re.compile("savant\\.php")):
                break
            if next_node.name == "a" and "savant.php" in next_node.get("href", ""):
                break
            chunks.append(next_node.get_text(" ", strip=True))
        elif isinstance(next_node, NavigableString):
            chunks.append(str(next_node))
        if sum(map(len, chunks)) > 800:
            break
    phrase = tidy(" ".join(chunks)).strip(" -\t")
    if phrase:
        return phrase[:1000]
    # A direct parent can be an individual li or td; avoid accidental full-page.
    parent = anchor.parent
    if parent and parent.name in {"li", "p", "td", "div"}:
        content = tidy(parent.get_text(" ", strip=True))
        label = tidy(anchor.get_text(" ", strip=True))
        if 0 < len(content) < 550 and content.startswith(label):
            return content[len(label):].strip(" -\t")
    return ""

def identity_and_type(phrase: str) -> tuple[str, str]:
    x = ascii_fold(phrase)
    foreign = bool(re.search(
        r"\b(?:associe(?:e)?\s+etranger(?:e)?|membre(?:\s+associe)?\s+etranger(?:e)?|"
        r"correspondant(?:e)?\s+etranger(?:e)?|etranger(?:e)?\s+correspondant(?:e)?)\b", x))
    corr = bool(re.search(r"\bcorrespondant(?:e)?\b", x))
    # Exclude "membre associé étranger" even when extra whitespace intervenes.
    full = bool(re.search(
        r"\b(?:academicien(?:ne)?\s+libre|membre\s+libre|membre\s+non[- ]residant|"
        r"membre\s+residant|membre\s+titulaire|"
        r"membre\b(?!\s+(?:associe(?:e)?|correspondant(?:e)?|etranger(?:e)?)))", x))
    if foreign and full:
        return "mixed_full_and_foreign_manual", "Full and foreign-like words coexist; review sequence and role"
    if corr and full:
        return "correspondent_to_full_candidate", "Both full and corresponding membership in historical note"
    if full:
        return "full_label_candidate", "CTHS description appears to assert member/full status"
    if foreign and corr:
        return "foreign_and_correspondent_only_candidate", "No full label"
    if foreign:
        return "foreign_only_candidate", "No full label"
    if corr:
        return "correspondent_only_candidate", "No full label"
    return "unresolved_status", "No confidently classified membership term"

def parse_roster(html: bytes) -> tuple[list[dict],dict]:
    soup = BeautifulSoup(html,"html.parser")
    text = soup.get_text(" ",strip=True)
    advertised = re.findall(r"(\d{3,4})\s+fiches\s+prosopographiques",text,re.I)
    all_anchors = extract_savant_anchors(html)
    rows, seen = [],set()
    for a in all_anchors:
        href = urljoin(BASE,a.get("href",""))
        id_ = parse_qs(urlparse(href).query).get("id",[""])[0]
        if id_ in seen:
            continue
        seen.add(id_)
        name = tidy(a.get_text(" ",strip=True))
        phrase = surrounding_phrase(a)
        kind, reason = identity_and_type(phrase)
        yearpair = re.search(r"\(\s*(\d{4})\s*-\s*(\d{4}|\s*)\s*\)",phrase)
        rows.append({
            "cths_person_id": id_,
            "cths_profile_url": "https://cths.fr/an/savant.php?id="+id_,
            "name_raw": name,
            "membership_note_raw": phrase,
            "birth_year_lifespan_candidate": yearpair.group(1) if yearpair else "",
            "death_year_lifespan_candidate": yearpair.group(2).strip() if yearpair else "",
            "cths_status_candidate": kind,
            "status_reviewer_note": reason,
            "cths_full_member_accepted": 0,
            "cths_exact_dob_accepted": 0,
        })
    return rows,{"advertised_count_mentions":advertised,"savant_links_raw":len(all_anchors),"distinct_cths_person_ids":len(rows)}

def fetch_sample_profiles(session: requests.Session, rows:list[dict], raw:Path, timeout:float, delay:float, per_class:int) -> tuple[list[dict],list[dict]]:
    grouped = {}
    for r in rows:
        grouped.setdefault(r["cths_status_candidate"],[]).append(r)
    chosen = []
    for cls in sorted(grouped):
        # Spread across the alphabet to review the parser on varied structure.
        grp=grouped[cls]
        stride=max(1, len(grp)//max(1,per_class))
        chosen.extend(grp[::stride][:per_class])
    seen, profiles, errors=set(),[],[]
    for item in chosen:
        if item["cths_person_id"] in seen: continue
        seen.add(item["cths_person_id"])
        url=item["cths_profile_url"]
        try:
            body = source_get(session,url,timeout=timeout,delay=delay)
            hsh = digest(body)
            (raw / (hsh+".html")).write_bytes(body)
            soup=BeautifulSoup(body,"html.parser")
            plain=soup.get_text(" ",strip=True)
            # Keep the verbatim section near Société(s) and date fields for QA.
            birth=re.search(r"Naissance\s*:\s*(.{1,110}?)(?:\s*-\s*Décès\s*:|\s*Décès\s*:|\s+Soci[eé]t[eé]\(s\))",plain,re.I)
            assoc=re.search(r"Acad[eé]mie des sciences\s*:\s*(.{0,230})",plain,re.I)
            profiles.append({
                "cths_person_id":item["cths_person_id"],
                "name_raw":item["name_raw"],
                "cths_profile_url":url,
                "source_sha256":hsh,
                "roster_class_candidate":item["cths_status_candidate"],
                "profile_birth_text_candidate":tidy(birth.group(1)) if birth else "",
                "profile_academy_membership_snippet_candidate":tidy(assoc.group(1))[:230] if assoc else "",
                "verification_status":"PROFILE_FETCHED_NOT_ADJUDICATED",
            })
        except Exception as exc:
            errors.append({"url":url,"person_id":item["cths_person_id"],
                           "stage":"profile","error":str(exc)[:500]})
    return profiles,errors

def write_csv(path:Path, rows:list[dict],fields:list[str]):
    with path.open("w",newline="",encoding="utf-8-sig") as f:
        writer=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

def main() -> None:
    ap=argparse.ArgumentParser()
    ap.add_argument("--out",default="data/france_academy_cths_society_roster_v1")
    ap.add_argument("--min-count",type=int,default=EXPECTED_LOWER)
    ap.add_argument("--max-profiles-per-class",type=int,default=4)
    ap.add_argument("--delay",type=float,default=.5)
    ap.add_argument("--timeout",type=float,default=TIMEOUT)
    args=ap.parse_args()
    if args.delay<.3: raise ValueError("Polite delay >=.3 sec")
    output=Path(args.out);output.mkdir(parents=True,exist_ok=True)
    raw=output/"raw_html";raw.mkdir(exist_ok=True)
    ses=requests.Session();ses.headers.update({"User-Agent":AGENT,"Accept-Language":"fr-FR,fr;q=0.9"})
    try:
        page=source_get(ses,SOURCE,timeout=args.timeout,delay=args.delay)
        hsh=digest(page)
        (raw/(hsh+".html")).write_bytes(page)
        rows,metrics=parse_roster(page)
        if not args.min_count <= len(rows) <= EXPECTED_UPPER:
            raise RuntimeError(f"CTHS roster unexpected count {len(rows)} (expected >= {args.min_count})")
        # Parsing with 2,000 links but empty member-type notes is not a valid success.
        typed=sum(x["cths_status_candidate"]!="unresolved_status" for x in rows)
        if typed<100:
            raise RuntimeError(f"CTHS extracted only {typed} role-bearing rows, DOM parse needs review")
        roster_fields=list(rows[0].keys())
        write_csv(output/"cths_academy_society_membership_candidates_v1.csv",rows,roster_fields)
        profiles,errors=fetch_sample_profiles(
            ses,rows,raw,args.timeout,args.delay,args.max_profiles_per_class)
        write_csv(output/"cths_profile_smoke_evidence_v1.csv",profiles,[
            "cths_person_id","name_raw","cths_profile_url","source_sha256",
            "roster_class_candidate","profile_birth_text_candidate",
            "profile_academy_membership_snippet_candidate","verification_status"])
        write_csv(output/"source_errors_v1.csv",errors,["stage","url","person_id","error"])
        result={
            "version":VERSION,
            "source_url":SOURCE,
            "source_html_sha256":hsh,
            "run_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
            **metrics,
            "status_candidate_counts":dict(Counter(r["cths_status_candidate"] for r in rows)),
            "membership_note_nonempty":sum(bool(r["membership_note_raw"]) for r in rows),
            "profile_smoke_fetched":len(profiles),
            "profile_smoke_errors":len(errors),
            "official_full_members_accepted":0,
            "official_exact_dobs_accepted":0,
            "historical_roster_complete":False,
            "final_roster_frozen":False,
            "bazi_variables_computed":0,
            "source_provenance_warning":"CTHS secondary history includes correspondents and foreign associates. Individual raw note and official status must be adjudicated before primary cohort inclusion.",
        }
        (output/"summary.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)
    except Exception as exc:
        (output/"source_failure.json").write_text(json.dumps({"source":SOURCE,"stage":"fetch_or_parse","exception":str(exc),"run_at_utc":dt.datetime.now(dt.timezone.utc).isoformat()},indent=2),encoding="utf-8")
        raise

if __name__=="__main__":
    main()
