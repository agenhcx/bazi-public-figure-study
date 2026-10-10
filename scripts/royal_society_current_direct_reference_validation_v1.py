# workflow trigger: direct-reference validation v1
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import html
import json
import re
import time
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

IN = Path("data/royal_society_current_p569_provenance_input")
OUTBASE = Path("data/royal_society_current_direct_reference_validation_v1")
UA = "bazi-public-figure-study/1.0 (Royal Society current DOB direct-reference validation; no BaZi)"

MONTHS = {
    1: ["January","Jan","janvier","janv","Januar"],
    2: ["February","Feb","février","fevrier","févr","fevr","Februar"],
    3: ["March","Mar","mars","März","Marz"],
    4: ["April","Apr","avril"],
    5: ["May","mai","Mai"],
    6: ["June","Jun","juin","Juni"],
    7: ["July","Jul","juillet","Juli"],
    8: ["August","Aug","août","aout"],
    9: ["September","Sep","Sept","septembre"],
    10: ["October","Oct","octobre","Oktober"],
    11: ["November","Nov","novembre"],
    12: ["December","Dec","décembre","decembre","Dezember"],
}

HIGH_EXACT = {
    "ukwhoswho.com",
    "catalogue.bnf.fr",
    "data.bnf.fr",
    "gnd.network",
    "dnb.de",
    "loc.gov",
    "id.loc.gov",
    "authorities.loc.gov",
    "nobelprize.org",
    "leopoldina.org",
    "prixduquebec.gouv.qc.ca",
    "genome.gov",
    "nserc-crsng.gc.ca",
    "esf.org",
    "mpg.de",
    "mta.hu",
    "czlonkowie.pan.pl",
    "roe.ac.uk",
    "ucl.ac.uk",
    "statslab.cam.ac.uk",
    "physics.mcgill.ca",
    "web.math.ku.dk",
    "math.unibas.ch",
    "ssbprize.gov.in",
}
LOW_EXACT = {
    "britannica.com",
    "prabook.com",
    "thepeerage.com",
    "books.google.co.uk",
    "books.google.com",
    "sylviavetta.co.uk",
}


def read_csv(p):
    with p.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(p, rows, fields):
    with p.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def host(url):
    try:
        d = (urlparse(url).hostname or "").lower()
    except Exception:
        return ""
    return d[4:] if d.startswith("www.") else d


def source_class(domain):
    d = domain.lower()
    if d in LOW_EXACT:
        return "secondary_locator_only", 0
    if d in HIGH_EXACT:
        return "frozen_hierarchy_eligible", 1
    if d.endswith(".ac.uk") or ".ac." in d or d.endswith(".edu") or ".edu." in d:
        return "institutional_academic_eligible", 1
    if d.endswith(".gov") or ".gov." in d or d.endswith(".gov.uk") or ".gov.uk" in d:
        return "government_eligible", 1
    if d.endswith(".gc.ca") or d.endswith(".gouv.qc.ca"):
        return "government_eligible", 1
    return "unclassified_locator_only", 0


def parse_dates(s):
    out = []
    for t in (s or "").split(";"):
        t = t.strip()
        m = re.match(r"^[+-](\d{4})-(\d\d)-(\d\d)T", t)
        if not m:
            continue
        y, mo, d = map(int, m.groups())
        try:
            out.append(date(y, mo, d))
        except Exception:
            pass
    return sorted(set(out))


def fetch(url, retries=2):
    last = ""
    for a in range(retries):
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": UA,
                    "Accept": "text/html,application/xhtml+xml,application/json,text/plain,*/*;q=0.5",
                },
            )
            with urllib.request.urlopen(req, timeout=25) as r:
                ctype = (r.headers.get("Content-Type") or "").lower()
                status = getattr(r, "status", 200)
                final = r.geturl()
                raw = r.read(2_000_000)
                if "pdf" in ctype or raw[:4] == b"%PDF":
                    return {"status": status, "final_url": final, "content_type": ctype, "text": "", "fetch_status": "pdf_not_parsed"}
                charset = "utf-8"
                m = re.search(r"charset=([^;\s]+)", ctype)
                if m:
                    charset = m.group(1).strip('"\'')
                try:
                    text = raw.decode(charset, errors="replace")
                except Exception:
                    text = raw.decode("utf-8", errors="replace")
                text = html.unescape(text)
                text = re.sub(r"(?is)<script\b.*?</script>", " ", text)
                text = re.sub(r"(?is)<style\b.*?</style>", " ", text)
                text = re.sub(r"(?s)<[^>]+>", " ", text)
                text = re.sub(r"\s+", " ", text)
                return {"status": status, "final_url": final, "content_type": ctype, "text": text, "fetch_status": "ok"}
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code}"
            if e.code in (429, 500, 502, 503, 504) and a + 1 < retries:
                time.sleep(2 + a * 3)
                continue
            return {"status": e.code, "final_url": url, "content_type": "", "text": "", "fetch_status": last}
        except Exception as e:
            last = f"{type(e).__name__}: {e}"
            if a + 1 < retries:
                time.sleep(2 + a * 3)
                continue
            return {"status": "", "final_url": url, "content_type": "", "text": "", "fetch_status": last}
    return {"status": "", "final_url": url, "content_type": "", "text": "", "fetch_status": last or "unknown_error"}


def date_match(text, dt):
    if not text:
        return ""
    y, m, d = dt.year, dt.month, dt.day
    iso = rf"(?<!\d){y:04d}-{m:02d}-{d:02d}(?!\d)"
    if re.search(iso, text, flags=re.I):
        return "iso"

    month_terms = "|".join(re.escape(x) + r"\.?" for x in MONTHS[m])
    day = rf"0?{d}(?:st|nd|rd|th)?"
    p1 = rf"(?<!\w){day}\s+(?:{month_terms})\s*,?\s*{y}(?!\d)"
    p2 = rf"(?<!\w)(?:{month_terms})\s+{day}\s*,?\s*{y}(?!\d)"
    if re.search(p1, text, flags=re.I) or re.search(p2, text, flags=re.I):
        return "named_month"

    numeric = [
        rf"(?<!\d)0?{d}[./-]0?{m}[./-]{y}(?!\d)",
        rf"(?<!\d){y}[./]0?{m}[./]0?{d}(?!\d)",
    ]
    if any(re.search(p, text) for p in numeric):
        return "numeric_ambiguous"
    return ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shard-index", type=int, required=True)
    ap.add_argument("--shard-count", type=int, required=True)
    a = ap.parse_args()

    files = list(IN.rglob("p569_reference_urls_v1.csv"))
    if len(files) != 1:
        raise RuntimeError(f"Expected one provenance URL CSV, found {len(files)}")
    rows = read_csv(files[0])
    if len(rows) != 102:
        raise RuntimeError(f"Expected 102 URL instances, got {len(rows)}")

    rows = sorted(rows, key=lambda r: (r["cohort_key"], r["reference_url"]))
    shard = [r for i, r in enumerate(rows) if i % a.shard_count == a.shard_index]

    out = []
    for i, r in enumerate(shard, 1):
        d = host(r["reference_url"])
        cls, eligible = source_class(d)
        dates = parse_dates(r["p569_exact_values"])
        f = fetch(r["reference_url"])
        matches = [(dt.isoformat(), date_match(f["text"], dt)) for dt in dates]
        positive = [(ds, mt) for ds, mt in matches if mt]
        unique_candidate = len(dates) == 1
        strong_match = bool(positive and positive[0][1] in ("iso", "named_month"))
        accepted = bool(unique_candidate and eligible and strong_match)
        out.append({
            **r,
            "source_class": cls,
            "eligible_under_frozen_hierarchy": eligible,
            "candidate_date_count": len(dates),
            "http_status": f["status"],
            "final_url": f["final_url"],
            "content_type": f["content_type"],
            "fetch_status": f["fetch_status"],
            "date_match_style": positive[0][1] if positive else "",
            "confirmed_candidate_date": positive[0][0] if positive else "",
            "accepted_direct_reference": int(accepted),
            "acceptance_reason": (
                "eligible source + unique P569 candidate + exact date present in source page"
                if accepted else ""
            ),
        })
        if i % 10 == 0:
            print("validated", i, "/", len(shard))

    outdir = OUTBASE / f"shard_{a.shard_index:02d}_of_{a.shard_count:02d}"
    outdir.mkdir(parents=True, exist_ok=True)
    fields = list(out[0].keys()) if out else []
    write_csv(outdir / "direct_reference_validation.csv", out, fields)

    people = {}
    for r in out:
        k = r["cohort_key"]
        p = people.setdefault(k, {"accepted": 0, "matched": 0, "eligible": 0})
        p["accepted"] = max(p["accepted"], int(r["accepted_direct_reference"]))
        p["matched"] = max(p["matched"], int(bool(r["confirmed_candidate_date"])))
        p["eligible"] = max(p["eligible"], int(r["eligible_under_frozen_hierarchy"]))

    summary = {
        "dataset": "Royal Society current direct P569-reference validation v1",
        "shard_index": a.shard_index,
        "shard_count": a.shard_count,
        "url_instances": len(out),
        "unique_people": len(people),
        "eligible_url_instances": sum(int(r["eligible_under_frozen_hierarchy"]) for r in out),
        "fetched_ok": sum(r["fetch_status"] == "ok" for r in out),
        "date_match_any_style": sum(bool(r["confirmed_candidate_date"]) for r in out),
        "date_match_strong_style": sum(r["date_match_style"] in ("iso", "named_month") for r in out),
        "accepted_url_instances": sum(int(r["accepted_direct_reference"]) for r in out),
        "accepted_unique_people": sum(p["accepted"] for p in people.values()),
        "dob_values_accepted": sum(p["accepted"] for p in people.values()),
        "bazi_variables_computed": 0,
        "note": "Bare Wikidata P569 is never accepted. Acceptance requires an eligible frozen-hierarchy source and an exact date visibly matching the unique candidate.",
    }
    (outdir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
