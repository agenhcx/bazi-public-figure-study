#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import html
import io
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from pypdf import PdfReader

BASE = Path("data/nas_science_core_dob_crosswalk")
INPUT = BASE / "nas_science_core_dob_crosswalk_v16.csv"
UA = "bazi-public-figure-study/1.0 (NAS institutional-official DOB pilot; no BaZi computation)"

MONTHS = {m.lower(): i for i, m in enumerate(
    ["", "January", "February", "March", "April", "May", "June",
     "July", "August", "September", "October", "November", "December"]
)}
for k, v in list(MONTHS.items()):
    if len(k) >= 3:
        MONTHS[k[:3]] = v

GENERIC = {
    "university","college","school","institute","institution","center","centre","department",
    "laboratory","lab","national","medical","medicine","science","sciences","research","the",
    "of","for","and","inc","corporation","company","hospital","foundation","academy","state",
    "system","health","technology","technologies"
}

def read_csv(path):
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

def write_csv(path, rows, fields):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

def present(v):
    return str(v or "").strip() not in ("", "nan", "None")

def as_int(v, default=0):
    try:
        return int(float(str(v)))
    except Exception:
        return default

def norm(s):
    return " ".join(re.sub(r"[^a-z0-9]+", " ", str(s or "").lower()).split())

def useful_tokens(s):
    return {x for x in norm(s).split() if len(x) > 2 and x not in GENERIC}

def reliable_qid(r):
    q = (r.get("wikidata_qid") or "").strip()
    if re.fullmatch(r"Q\d+", q):
        return q, "wikidata_qid"
    q = (r.get("global_candidate_qid") or "").strip()
    if not re.fullmatch(r"Q\d+", q):
        return "", ""
    if as_int(r.get("global_exact_name_match_count")) != 1:
        return "", ""
    toks = len(norm(r.get("name", "")).split())
    if toks >= 3 or as_int(r.get("global_affiliation_match")) == 1:
        return q, "global_unique_identity"
    return "", ""

def get(url, accept="text/html,application/xhtml+xml,application/pdf;q=0.9,*/*;q=0.1", retries=2, timeout=15):
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": UA,
                "Accept": accept,
                "Accept-Language": "en-US,en;q=0.8",
            })
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return getattr(r, "status", 200), r.read(8_000_000), r.headers.get_content_type(), r.geturl(), ""
        except urllib.error.HTTPError as e:
            last = e
            if e.code in {401,403,404}:
                return e.code, b"", "", url, "HTTP " + str(e.code)
            if i + 1 >= retries or e.code not in {429,500,502,503,504}:
                break
            time.sleep(min(8, 2 ** i))
        except Exception as e:
            last = e
            if i + 1 >= retries:
                break
            time.sleep(min(8, 2 ** i))
    return getattr(last, "code", ""), b"", "", url, repr(last)

def json_get(url):
    st, data, ct, final, err = get(url, "application/json", retries=2, timeout=15)
    if not data:
        return st, None, final, err
    try:
        return st, json.loads(data.decode("utf-8")), final, err
    except Exception as e:
        return st, None, final, (err + "; " if err else "") + repr(e)

def entity(qid):
    st, obj, final, err = json_get(f"https://www.wikidata.org/wiki/Special:EntityData/{qid}.json")
    ent = ((obj or {}).get("entities") or {}).get(qid) if isinstance(obj, dict) else None
    return ent or {}, err

def dv(claim):
    try:
        return claim["mainsnak"]["datavalue"]["value"]
    except Exception:
        return None

def item_claims(ent, prop):
    out = []
    for c in (ent.get("claims") or {}).get(prop, []):
        v = dv(c)
        if isinstance(v, dict):
            x = v.get("id")
            if isinstance(x, str) and re.fullmatch(r"Q\d+", x):
                out.append(x)
    return sorted(set(out))

def url_claims(ent, prop="P856"):
    out = []
    for c in (ent.get("claims") or {}).get(prop, []):
        v = dv(c)
        if isinstance(v, str) and v.startswith(("http://", "https://")):
            out.append(v)
    return sorted(set(out))

def label(ent):
    labels = ent.get("labels") or {}
    for lang in ("en", "mul"):
        x = labels.get(lang)
        if isinstance(x, dict) and x.get("value"):
            return str(x["value"])
    return ""

def domain(url):
    try:
        h = urllib.parse.urlparse(url).netloc.lower().split(":")[0]
        return h[4:] if h.startswith("www.") else h
    except Exception:
        return ""

def same_domain(url, dom):
    h = domain(url)
    return bool(h and dom and (h == dom or h.endswith("." + dom)))

def affil_match_score(affil, candidate_label):
    a = useful_tokens(affil)
    b = useful_tokens(candidate_label)
    if not a or not b:
        return 0.0, 0
    ov = len(a & b)
    return ov / max(1, min(len(a), len(b))), ov

def institution_domains_for_row(r, person_ent_cache, inst_ent_cache, affil_search_cache):
    affil = (r.get("affiliation") or "").strip()
    candidates = []

    qid, basis = reliable_qid(r)
    if qid:
        pent = person_ent_cache.get(qid) or {}
        for iq in item_claims(pent, "P108") + item_claims(pent, "P1416"):
            ent = inst_ent_cache.get(iq) or {}
            lab = label(ent)
            score, ov = affil_match_score(affil, lab)
            for u in url_claims(ent):
                d = domain(u)
                if d and (score >= 0.5 or ov >= 2 or norm(affil) in norm(lab) or norm(lab) in norm(affil)):
                    candidates.append((d, u, lab, "person_qid_employer:" + basis, score, ov))

    for hit in affil_search_cache.get(affil, []):
        iq = hit.get("id", "")
        ent = inst_ent_cache.get(iq) or {}
        lab = label(ent) or hit.get("label", "")
        score, ov = affil_match_score(affil, lab)
        if not (score >= 0.5 or ov >= 2 or norm(affil) == norm(lab)):
            continue
        for u in url_claims(ent):
            d = domain(u)
            if d:
                candidates.append((d, u, lab, "affiliation_wikidata_search", score, ov))

    best = {}
    for x in candidates:
        d = x[0]
        if d not in best or (x[4], x[5]) > (best[d][4], best[d][5]):
            best[d] = x
    return sorted(best.values(), key=lambda x: (-x[4], -x[5], x[0]))[:1]

def wbsearch_affiliation(affil):
    if not affil:
        return []
    q = urllib.parse.urlencode({
        "action":"wbsearchentities", "search":affil, "language":"en",
        "format":"json", "limit":5, "type":"item"
    })
    st, obj, final, err = json_get("https://www.wikidata.org/w/api.php?" + q)
    if not isinstance(obj, dict):
        return []
    return [x for x in obj.get("search", []) if isinstance(x, dict) and re.fullmatch(r"Q\d+", str(x.get("id","")))]

def iso(y, m, d):
    try:
        return dt.date(int(y), int(m), int(d)).isoformat()
    except Exception:
        return ""

def parse_date_token(s, expected_year=None):
    s = html.unescape(str(s or "")).strip()
    patterns = [
        (r"\b([12]\d{3})[-/.](\d{1,2})[-/.](\d{1,2})\b", "ymd"),
        (r"\b(\d{1,2})[-/.](\d{1,2})[-/.]([12]\d{3})\b", "mdy"),
        (r"\b([A-Za-z]{3,9})\s+(\d{1,2})(?:st|nd|rd|th)?[,]?\s+([12]\d{3})\b", "mdytext"),
        (r"\b(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]{3,9})[,]?\s+([12]\d{3})\b", "dmytext"),
    ]
    for p, kind in patterns:
        m = re.search(p, s, re.I)
        if not m:
            continue
        if kind == "ymd":
            d = iso(m.group(1), m.group(2), m.group(3))
        elif kind == "mdy":
            d = iso(m.group(3), m.group(1), m.group(2))
        elif kind == "mdytext":
            mo = MONTHS.get(m.group(1).lower()[:3], 0)
            d = iso(m.group(3), mo, m.group(2)) if mo else ""
        else:
            mo = MONTHS.get(m.group(2).lower()[:3], 0)
            d = iso(m.group(3), mo, m.group(1)) if mo else ""
        if d and (not expected_year or d.startswith(str(expected_year) + "-")):
            return d
    return ""

def extract_explicit_dates(text, expected_year=None):
    plain = html.unescape(re.sub(r"\s+", " ", text or " "))
    vals, evidence = set(), []
    pats = [
        r"\bborn\b\s*[:=,-]?\s*",
        r"\bdate\s+of\s+birth\b\s*[:=,-]?\s*",
        r"\bbirth\s*date\b\s*[:=,-]?\s*",
        r"\bDOB\b\s*[:=,-]?\s*",
    ]
    for p in pats:
        for m in re.finditer(p, plain, re.I):
            window = plain[m.end():m.end()+120]
            d = parse_date_token(window, expected_year)
            if d:
                vals.add(d)
                evidence.append(plain[max(0, m.start()-60):m.end()+150].strip())
    return vals, evidence

def parse_html(data, expected_year, base_url):
    text = data.decode("utf-8", "ignore")
    vals, evidence = set(), []

    for m in re.finditer(r'(?is)<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', text):
        try:
            obj = json.loads(html.unescape(m.group(1)))
            stack = [obj]
            while stack:
                x = stack.pop()
                if isinstance(x, dict):
                    for k, v in x.items():
                        if str(k).lower() in {"birthdate","dateofbirth","birth_date","date_of_birth"}:
                            seq = v if isinstance(v, list) else [v]
                            for z in seq:
                                if isinstance(z, dict):
                                    z = z.get("@value") or z.get("value") or z.get("label") or ""
                                d = parse_date_token(z, expected_year)
                                if d:
                                    vals.add(d)
                                    evidence.append("jsonld:" + str(z))
                        if isinstance(v, (dict, list)):
                            stack.append(v)
                elif isinstance(x, list):
                    stack.extend(x)
        except Exception:
            pass

    nojs = re.sub(r"(?is)<script\b.*?</script>|<style\b.*?</style>", " ", text)
    plain = re.sub(r"(?s)<[^>]+>", " ", nojs)
    a, b = extract_explicit_dates(plain, expected_year)
    vals |= a
    evidence += b

    return sorted(vals), evidence

def parse_pdf(data, expected_year):
    vals, evidence = set(), []
    try:
        rd = PdfReader(io.BytesIO(data))
        text = " ".join((p.extract_text() or "") for p in rd.pages[:30])
        a, b = extract_explicit_dates(text, expected_year)
        vals |= a
        evidence += b
        return sorted(vals), evidence, ""
    except Exception as e:
        return [], [], repr(e)

def ddg_results(query):
    q = urllib.parse.urlencode({"q": query})
    st, data, ct, final, err = get("https://html.duckduckgo.com/html/?" + q, "text/html", retries=1, timeout=10)
    if not data:
        return [], "duckduckgo:" + err
    text = data.decode("utf-8", "ignore")
    out = []
    for href in re.findall(r'(?is)<a[^>]+class=["\'][^"\']*result__a[^"\']*["\'][^>]+href=["\']([^"\']+)["\']', text):
        u = html.unescape(href)
        if u.startswith("//"):
            u = "https:" + u
        try:
            p = urllib.parse.urlparse(u)
            if "duckduckgo.com" in p.netloc and "uddg=" in p.query:
                u = urllib.parse.parse_qs(p.query).get("uddg", [""])[0]
        except Exception:
            pass
        if u.startswith(("http://","https://")):
            out.append(u)
    return list(dict.fromkeys(out)), ""

def bing_results(query):
    q = urllib.parse.urlencode({"q": query})
    st, data, ct, final, err = get("https://www.bing.com/search?" + q, "text/html", retries=1, timeout=10)
    if not data:
        return [], "bing:" + err
    text = data.decode("utf-8", "ignore")
    out = re.findall(r'(?is)<li[^>]+class=["\'][^"\']*b_algo[^"\']*["\'][^>]*>.*?<h2[^>]*>\s*<a[^>]+href=["\']([^"\']+)["\']', text)
    out = [html.unescape(u) for u in out if u.startswith(("http://","https://"))]
    return list(dict.fromkeys(out)), ""

def search_official(name, dom):
    queries = [
        f'site:{dom} "{name}" ("date of birth" OR born OR DOB)',
        f'site:{dom} "{name}" (CV OR biography)',
    ]
    urls, errs = [], []
    for q in queries:
        got, err = ddg_results(q)
        if err:
            errs.append(err)
        if not got:
            got, err = bing_results(q)
            if err:
                errs.append(err)
        for u in got:
            if same_domain(u, dom) and u not in urls:
                urls.append(u)
        if len(urls) >= 3:
            break
    return urls[:3], " || ".join(errs)

def fetch_candidate_url(url, expected_year):
    st, data, ct, final, err = get(url, retries=1, timeout=12)
    if not data:
        return [], [], final or url, err
    if "pdf" in (ct or "").lower() or str(final).lower().endswith(".pdf"):
        ds, ev, perr = parse_pdf(data, expected_year)
        if perr:
            err = (err + "; " if err else "") + perr
    else:
        ds, ev = parse_html(data, expected_year, final)
    return ds, ev, final, err

def choose_sample(rows, n, salt):
    return sorted(rows, key=lambda r: hashlib.sha256((salt + r.get("profile_url","")).encode()).hexdigest())[:n]

def shard_rows(rows, shard, shards):
    return [r for i, r in enumerate(rows) if i % shards == shard]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--shards", type=int, default=1)
    ap.add_argument("--validation-n", type=int, default=80)
    ap.add_argument("--unresolved-n", type=int, default=160)
    args = ap.parse_args()

    rows = read_csv(INPUT)
    if len(rows) != 3051:
        raise RuntimeError(f"Expected 3051 rows, got {len(rows)}")

    living = [r for r in rows if r.get("deceased") != "Y"]
    known = [r for r in living if present(r.get("final_exact_dob"))]
    unresolved = [r for r in living if not present(r.get("final_exact_dob"))]

    validation = choose_sample(known, args.validation_n, "institutional-validation-v1:")
    probe = choose_sample(unresolved, args.unresolved_n, "institutional-unresolved-v1:")
    targets = [("validation", r) for r in validation] + [("unresolved", r) for r in probe]
    targets = sorted(targets, key=lambda x: hashlib.sha256((x[0] + ":" + x[1].get("profile_url","")).encode()).hexdigest())
    targets = shard_rows(targets, args.shard, args.shards)

    qids = sorted({reliable_qid(r)[0] for _, r in targets if reliable_qid(r)[0]})
    person_ent = {}
    with ThreadPoolExecutor(max_workers=10) as ex:
        fs = {ex.submit(entity, q): q for q in qids}
        for f in as_completed(fs):
            q = fs[f]
            try:
                person_ent[q] = f.result()[0]
            except Exception:
                person_ent[q] = {}

    affils = sorted({(r.get("affiliation") or "").strip() for _, r in targets if (r.get("affiliation") or "").strip()})
    affil_search = {}
    with ThreadPoolExecutor(max_workers=8) as ex:
        fs = {ex.submit(wbsearch_affiliation, a): a for a in affils}
        for f in as_completed(fs):
            a = fs[f]
            try:
                affil_search[a] = f.result()
            except Exception:
                affil_search[a] = []

    inst_qids = set()
    for ent in person_ent.values():
        inst_qids.update(item_claims(ent, "P108"))
        inst_qids.update(item_claims(ent, "P1416"))
    for hits in affil_search.values():
        for h in hits:
            if re.fullmatch(r"Q\d+", str(h.get("id",""))):
                inst_qids.add(h["id"])

    inst_ent = {}
    with ThreadPoolExecutor(max_workers=10) as ex:
        fs = {ex.submit(entity, q): q for q in sorted(inst_qids)}
        for f in as_completed(fs):
            q = fs[f]
            try:
                inst_ent[q] = f.result()[0]
            except Exception:
                inst_ent[q] = {}

    results = []
    for cohort, r in targets:
        known_exact = r.get("final_exact_dob", "") if cohort == "validation" else ""
        expected_year = known_exact[:4] if known_exact else None
        domains = institution_domains_for_row(r, person_ent, inst_ent, affil_search)
        all_dates, all_ev, used_urls, search_errs, fetch_errs = set(), [], [], [], []
        domain_meta = []
        for dom, root_url, inst_label, basis, score, ov in domains:
            domain_meta.append(f"{dom}|{inst_label}|{basis}|score={score:.3f}|ov={ov}")
            urls, serr = search_official(r.get("name",""), dom)
            if serr:
                search_errs.append(dom + ":" + serr)
            for u in urls:
                ds, ev, final, ferr = fetch_candidate_url(u, expected_year)
                if ferr:
                    fetch_errs.append(final + ":" + ferr)
                if ds:
                    all_dates.update(ds)
                    used_urls.append(final)
                    all_ev.extend([final + " :: " + x for x in ev[:5]])
        dates = sorted(all_dates)
        cand = dates[0] if len(dates) == 1 else ""
        conflict = int(len(dates) > 1)
        ey = as_int(r.get("election_year"), 0)
        age = ey - int(cand[:4]) if cand and ey else None
        age_ok = int(age is not None and 25 <= age <= 100) if cand else ""
        val_match = ""
        if cohort == "validation" and cand:
            val_match = int(cand == known_exact)

        results.append({
            "cohort": cohort,
            "profile_url": r.get("profile_url",""),
            "name": r.get("name",""),
            "election_year": r.get("election_year",""),
            "affiliation": r.get("affiliation",""),
            "known_exact_dob": known_exact,
            "institution_domains": " || ".join(domain_meta),
            "parsed_exact_dates": "|".join(dates),
            "candidate_dob": cand,
            "date_conflict": conflict,
            "age_at_election": age if age is not None else "",
            "age_plausible": age_ok,
            "validation_match": val_match,
            "candidate_for_manual_review": int(cohort == "unresolved" and bool(cand) and not conflict and age_ok == 1),
            "source_urls": "|".join(sorted(set(used_urls))),
            "evidence": " || ".join(all_ev[:12]),
            "search_errors": " || ".join(search_errs[:8]),
            "fetch_errors": " || ".join(fetch_errs[:8]),
        })

    fields = [
        "cohort","profile_url","name","election_year","affiliation","known_exact_dob",
        "institution_domains","parsed_exact_dates","candidate_dob","date_conflict","age_at_election",
        "age_plausible","validation_match","candidate_for_manual_review","source_urls","evidence",
        "search_errors","fetch_errors"
    ]
    out = BASE / f"nas_institutional_official_dob_pilot_v1_shard{args.shard}.csv"
    write_csv(out, results, fields)
    cands = [x for x in results if x["candidate_for_manual_review"] == 1]
    write_csv(BASE / f"nas_institutional_official_dob_candidates_v1_shard{args.shard}.csv", cands, fields)
    conflicts = [x for x in results if x["cohort"] == "validation" and x["candidate_dob"] and x["validation_match"] == 0]
    write_csv(BASE / f"nas_institutional_official_dob_validation_conflicts_v1_shard{args.shard}.csv", conflicts, fields)

    val_found = [x for x in results if x["cohort"] == "validation" and x["candidate_dob"]]
    summary = {
        "dataset": "NAS institutional-official exact-DOB pilot v1",
        "input": INPUT.name,
        "shard": args.shard,
        "shards": args.shards,
        "targets_in_shard": len(results),
        "validation_rows": sum(x["cohort"] == "validation" for x in results),
        "unresolved_rows": sum(x["cohort"] == "unresolved" for x in results),
        "rows_with_resolved_institution_domain": sum(bool(x["institution_domains"]) for x in results),
        "validation_rows_with_exact_date_recovered": len(val_found),
        "validation_exact_matches": sum(x["validation_match"] == 1 for x in val_found),
        "validation_exact_conflicts": len(conflicts),
        "validation_match_rate": (
            round(sum(x["validation_match"] == 1 for x in val_found) / len(val_found), 6)
            if val_found else None
        ),
        "unresolved_candidates_for_manual_review": len(cands),
        "candidate_names": [x["name"] for x in cands],
        "bazi_variables_computed": 0,
        "decision_note": (
            "Pilot only. Search engines are locators only; accepted evidence must come from the official "
            "institution domain derived from the NAS affiliation/Wikidata institution. Exact DOB extraction "
            "requires structured birthDate or explicit born/date-of-birth/DOB text. No v16 DOB is modified."
        )
    }
    (BASE / f"summary_nas_institutional_official_dob_pilot_v1_shard{args.shard}.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
