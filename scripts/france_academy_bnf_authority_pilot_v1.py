#!/usr/bin/env python3
"""Source-only BnF authority DOI/DOB/date audit for the 1989 France Academy leads.

Uses existing conservative CTHS-Wikidata identity crosswalk and official BnF
catalogue notices. Source claims only: NO automatic Academy membership or DOB
acceptance, NO BaZi variables, NO modifications to frozen source files.
Python 3.10+ standard library. Always begin with --fixture-check and --dry-run.
"""
from __future__ import annotations
import argparse
import csv
import datetime as dt
import hashlib
import html.parser
import json
import re
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path

VERSION = "france-academy-bnf-authority-source-only-v1"
REPO_CTHS = "data/france_academy_cths_profile_dob_harvest_v1/cths_dob_claims_all_targets_candidate_only_v1.csv"
REPO_PRIORITY = "data/france_academy_cths_historical_source_citation_audit_v1/institutional_directory_citation_review_queue_v1.csv"
REPO_CROSSWALK = "data/france_academy_cths_wikidata_crosswalk_v1/unique_strict_identity_candidates_v1.csv"
OUT = "local_runs/france_academy_bnf_authority_pilot_v1"
UA = "bazi-public-figure-study/1.0 (public BnF authority provenance audit)"
FIELDS = [
    "cths_person_id","cths_name","cths_dob_claim","wikidata_qid_candidate",
    "bnf_p268_candidate","bnf_catalogue_url","bnf_heading","bnf_date_of_birth_claim",
    "bnf_date_of_death_claim","dob_comparison","bnf_html_sha256",
    "bnf_source_cites_cths","bnf_source_cites_matchid","bnf_source_cites_lemonde",
    "bnf_source_cites_whoswho","identity_caution","fetch_status",
    "exact_dob_accepted","french_academy_full_member_accepted","bazi_variables_computed"
]
P268 = re.compile(r"^(?:cb)?([0-9]{8}[0-9a-z])$", re.I)
QID = re.compile(r"^Q[1-9][0-9]*$")
DATE = re.compile(r"^[12]\d{3}-\d\d-\d\d$")


def read_csv(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path, items, fields):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(items)


def hash_file(p):
    h = hashlib.sha256()
    with Path(p).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def safe_date(s):
    s = str(s or "").strip()
    if not DATE.fullmatch(s):
        return ""
    try:
        return dt.date.fromisoformat(s).isoformat()
    except ValueError:
        return ""


class TextOnly(html.parser.HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.skip = 0
        self.parts = []
    def handle_starttag(self, tag, attrs):
        if tag in ("script","style"): self.skip += 1
        elif tag in ("p","div","li","br","h1","h2","h3","td"): self.parts.append(" ")
    def handle_endtag(self, tag):
        if tag in ("script","style") and self.skip: self.skip -= 1
        elif tag in ("p","div","li","br","h1","h2","h3","td"): self.parts.append(" ")
    def handle_data(self, data):
        if not self.skip: self.parts.append(data)
    def text(self):
        return " ".join("".join(self.parts).split())


def decode_notice(raw):
    parser = TextOnly()
    parser.feed(raw.decode("utf-8", "replace"))
    text = parser.text()
    birth = re.search(r"(?:Naissance|Born)\s*:\s*([12]\d{3}-\d{2}-\d{2})", text, re.I)
    death = re.search(r"(?:Mort|D[eé]c[eè]s|Died)\s*:\s*([12]\d{3}-\d{2}-\d{2})", text, re.I)
    heading_match = re.search(r"(?:Notice de personne|Person notice)\s+(.*?)\s+(?:Pays|Country)\s*:", text, re.I)
    heading = heading_match.group(1).strip()[:160] if heading_match else text[:160]
    sources = re.search(r"Source\(s\)\s*:\s*(.*?)(?:Identifiant international|Identifiant de la notice|Notice n°|Cr[eé]ation\s*:)", text, re.I)
    bibliography = sources.group(1)[:1200] if sources else ""
    caution = re.search(r"(Ne pas confondre avec.{0,220}?)(?:Docteur|Source\(s\)|Pays\s*:|Identifiant international)", text, re.I)
    return {"heading":heading,"birth":safe_date(birth.group(1)) if birth else "",
            "death":safe_date(death.group(1)) if death else "",
            "citations":{k:int(v in bibliography.casefold()) for k,v in
                         (("cths","cths"),("matchid","match id"),
                          ("lemonde","le monde"),("whoswho","who's who"))},
            "identity_caution":caution.group(1).strip()[:200] if caution else "",
            "has_bibliography":bool(bibliography)}


def identity_targets(priority, crosswalk, cths, ids, limit):
    original = {r["cths_person_id"]:r for r in read_csv(cths)}
    identities = {r["cths_person_id"]:r for r in read_csv(crosswalk)}
    base = [r for r in read_csv(priority) if r.get("academy_member_only_1989") == "1"]
    # Prioritize already-identified cross-source discordance, then original
    # missing birth dates; never prioritize an astrological feature.
    base.sort(key=lambda r:(0 if r["cths_person_id"]=="2067" else
                            1 if not (original.get(r["cths_person_id"]) or {}).get("cths_exact_dob_claim_candidate_only") else 2,
                            int(r["cths_person_id"])))
    if ids:
        wanted = [v.strip() for v in ids.split(",") if v.strip()]
        if len(set(wanted)) != len(wanted): raise ValueError("duplicate --ids")
        byid = {r["cths_person_id"]:r for r in base}
        base = []
        for i in wanted:
            if i not in byid: raise ValueError("id not in fixed 1989 source-reference subset: " + i)
            base.append(byid[i])
    rows = []
    for r in base:
        pid = r["cths_person_id"]
        identity = identities.get(pid) or {}
        qid = identity.get("wd_qid_candidate","")
        cths_row = original.get(pid) or {}
        rows.append({"id":pid, "name":r["cths_name"],
                     "original_dob":cths_row.get("cths_exact_dob_claim_candidate_only",""),
                     "qid":qid if QID.fullmatch(qid) else "",
                     "cths_birthyear":r.get("cths_birth_year_candidate","")})
        if len(rows)>=limit: break
    return rows


def get(url, timeout):
    req = urllib.request.Request(url, headers={"User-Agent":UA,
                                                 "Accept":"application/json" if url.endswith(".json") else "text/html"})
    with urllib.request.urlopen(req, timeout=timeout) as rsp:
        body = rsp.read(3_000_001)
        if len(body)>3_000_000: raise ValueError("unexpectedly large authority payload")
        return body


def p268_ids(entity_bytes, qid):
    js=json.loads(entity_bytes)
    e=(js.get("entities") or {}).get(qid) or {}
    raw=(e.get("claims") or {}).get("P268", [])
    out=set()
    for claim in raw:
        x=(((claim.get("mainsnak") or {}).get("datavalue") or {}).get("value"))
        if isinstance(x,str):
            m=P268.fullmatch(x.strip())
            if m:out.add(m.group(1).lower())
    return sorted(out)


def pull_cached(url, cache_path, timeout, refresh):
    cp=Path(cache_path)
    if cp.exists() and not refresh:
        return cp.read_bytes(), "CACHE"
    raw=get(url,timeout)
    cp.parent.mkdir(parents=True,exist_ok=True)
    tmp=cp.with_suffix(cp.suffix+".part")
    tmp.write_bytes(raw)
    tmp.replace(cp)
    return raw,"HTTP_200"


def run(args):
    if not 1<=args.limit<=17: raise ValueError("--limit must be 1..17")
    if args.delay<1.1: raise ValueError("--delay must be >=1.1 seconds")
    selected=identity_targets(args.priority,args.crosswalk,args.cths,args.ids,args.limit)
    if args.dry_run:
        print(json.dumps({"source_only":True,"queries_planned":[{"id":x["id"],"name":x["name"],
                "candidate_qid":x["qid"],"original_dob":x["original_dob"]} for x in selected],
                "network_requests":0},ensure_ascii=False,indent=2))
        return
    inputs={k:hash_file(p) for k,p in (("priority",args.priority),("crosswalk",args.crosswalk),("cths",args.cths))}
    fingerprint=hashlib.sha256(json.dumps(inputs,sort_keys=True).encode()).hexdigest()[:24]
    cache=Path(args.out)/"_cache"/fingerprint
    rows=[]
    audits=[]
    last_network=[None]
    def throttled(url, path):
        if Path(path).exists() and not args.refresh:
            return pull_cached(url,path,args.timeout,False)
        if last_network[0] is not None:
            time.sleep(max(0,args.delay-(time.monotonic()-last_network[0])))
        last_network[0]=time.monotonic()
        return pull_cached(url,path,args.timeout,args.refresh)
    for t in selected:
        pid,qid=t["id"],t["qid"]
        if not qid:
            audits.append({"id":pid,"name":t["name"],"status":"NO_UNIQUE_WIKIDATA_ID_CANDIDATE"})
            continue
        url=f"https://www.wikidata.org/wiki/Special:EntityData/{qid}.json"
        try:
            wd_raw,wd_status=throttled(url,cache/(qid+".json"))
            ids=p268_ids(wd_raw,qid)
        except (urllib.error.HTTPError,urllib.error.URLError,TimeoutError,ValueError) as e:
            audits.append({"id":pid,"name":t["name"],"status":"WIKIDATA_ERROR",
                           "error":type(e).__name__+":"+str(getattr(e,"code",str(e)))[:120]})
            break
        if not ids:
            audits.append({"id":pid,"name":t["name"],"status":"NO_BNF_P268_CLAIM","wd_status":wd_status})
            continue
        for bnf in ids[:3]:
            source_url=f"https://catalogue.bnf.fr/ark:/12148/cb{bnf}"
            try:
                raw,fetch_status=throttled(source_url,cache/("bnf_"+bnf+".html"))
                notice=decode_notice(raw)
            except (urllib.error.HTTPError,urllib.error.URLError,TimeoutError,ValueError) as e:
                audits.append({"id":pid,"name":t["name"],"status":"BNF_FETCH_ERROR",
                              "url":source_url,"error":type(e).__name__+":"+str(getattr(e,"code",str(e)))[:120]})
                break
            dobc=notice["birth"]
            original=t["original_dob"]
            comparison=("NO_EXACT_BNF_DATE" if not dobc else
                        "CTHS_DOB_MISSING_BNF_DATE_LEAD" if not original else
                        "BNF_DATE_AGREES_CTHS_CLAIM" if dobc==original else
                        "BNF_DATE_CONFLICTS_CTHS_CLAIM")
            if dobc and t["cths_birthyear"] and dobc[:4]!=t["cths_birthyear"]:
                comparison="BNF_BIRTHYEAR_MISMATCH_QUARANTINE"
            rows.append({
                "cths_person_id":pid,"cths_name":t["name"],"cths_dob_claim":original,
                "wikidata_qid_candidate":qid,"bnf_p268_candidate":bnf,
                "bnf_catalogue_url":source_url,"bnf_heading":notice["heading"],
                "bnf_date_of_birth_claim":dobc,"bnf_date_of_death_claim":notice["death"],
                "dob_comparison":comparison,"bnf_html_sha256":hashlib.sha256(raw).hexdigest(),
                "bnf_source_cites_cths":str(notice["citations"]["cths"]),
                "bnf_source_cites_matchid":str(notice["citations"]["matchid"]),
                "bnf_source_cites_lemonde":str(notice["citations"]["lemonde"]),
                "bnf_source_cites_whoswho":str(notice["citations"]["whoswho"]),
                "identity_caution":notice["identity_caution"],"fetch_status":fetch_status,
                "exact_dob_accepted":"0","french_academy_full_member_accepted":"0",
                "bazi_variables_computed":"0"
            })
            audits.append({"id":pid,"name":t["name"],"status":"BNF_NOTICE_PARSED",
                           "url":source_url,"dob_found":bool(dobc),"date_comparison":comparison,
                           "bnf_source_cites_cths":notice["citations"]["cths"],
                           "bnf_source_cites_matchid":notice["citations"]["matchid"]})
        else:
            continue
        # Abort on first BnF access failure; do not multiply retries on an access restriction.
        if audits and audits[-1]["status"]=="BNF_FETCH_ERROR":
            break
    out=Path(args.out)
    write_csv(out/"bnf_authority_source_leads_v1.csv",rows,FIELDS)
    write_csv(out/"person_source_audit_v1.csv",audits,
              ["id","name","status","wd_status","url","dob_found","date_comparison",
               "bnf_source_cites_cths","bnf_source_cites_matchid","error"])
    summary={"version":VERSION,"input_sha256":inputs,"targets_selected":len(selected),
             "persons_with_bnf_source_claims":len({r["cths_person_id"] for r in rows}),
             "bnf_notice_claim_rows":len(rows),
             "source_outcome_counts":dict(Counter(r["status"] for r in audits)),
             "date_comparisons":dict(Counter(r["dob_comparison"] for r in rows)),
             "sources_may_not_be_independent":True,"is_complete_french_academy_roster":False,
             "final_exact_dob_accepted":0,"final_full_member_accepted":0,"bazi_variables_computed":0}
    (out/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("SUMMARY:",json.dumps({k:summary[k] for k in
           ("targets_selected","persons_with_bnf_source_claims","date_comparisons","source_outcome_counts")},
           ensure_ascii=False))
    return summary,rows


def fixture_check():
    page=b"""<html><title>BNF</title><body>Notice de personne Roche, Jean (1901-1992) forme internationale
         Pays : France Naissance : 1901-01-14, Sorgues Mort : 1992-05-24, Paris
         Ne pas confondre avec Jean Roche (1908-1979), egalement docteur en medecine de la faculte de Montpellier
         Docteur en medecine. Source(s) : Match ID ; Le Monde, 1961 ; CTHS ; Who's who in France
         Identifiant international de l'autorite : ISNI 0000</body></html>"""
    n=decode_notice(page)
    assert n["birth"]=="1901-01-14" and n["death"]=="1992-05-24"
    assert n["citations"]=={"cths":1,"matchid":1,"lemonde":1,"whoswho":1}
    assert "Ne pas confondre" in n["identity_caution"]
    fake={"entities":{"Q6075375":{"claims":{"P268":[
        {"mainsnak":{"datavalue":{"value":"12252855s"}}}]}}}}
    assert p268_ids(json.dumps(fake).encode(),"Q6075375")==["12252855s"]
    assert not safe_date("1901-02-00")
    print("PASS: BnF public metadata source-only parser, name collision note, source-dependency flags and QID P268 extraction")


def main():
    a=argparse.ArgumentParser()
    a.add_argument("--fixture-check",action="store_true")
    a.add_argument("--dry-run",action="store_true")
    a.add_argument("--ids",default="",help="Comma-separated CTHS IDs from the fixed 17 historical 1989 directory leads")
    a.add_argument("--limit",type=int,default=1)
    a.add_argument("--delay",type=float,default=1.3)
    a.add_argument("--timeout",type=float,default=20)
    a.add_argument("--refresh",action="store_true")
    a.add_argument("--priority",default=REPO_PRIORITY)
    a.add_argument("--crosswalk",default=REPO_CROSSWALK)
    a.add_argument("--cths",default=REPO_CTHS)
    a.add_argument("--out",default=OUT)
    args=a.parse_args()
    if args.fixture_check: fixture_check()
    else: run(args)


if __name__=="__main__":
    main()
