#!/usr/bin/env python3
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import html
import json
import re
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from html.parser import HTMLParser
from pathlib import Path
from collections import defaultdict

BASE = Path("data/nas_science_core_dob_crosswalk")
INPUT = BASE / "nas_science_core_dob_crosswalk_v8.csv"
WIKIDATA = Path("data/nas_wikidata_dob_pilot/nas_wikidata_dob_collapsed.csv")
OUT_DIAG = BASE / "nas_current_profile_dob_diagnostic_v1.csv"
OUT_CROSSWALK = BASE / "nas_science_core_dob_crosswalk_v9.csv"
OUT_LOG = BASE / "nas_current_profile_dob_supplement_log_v1.csv"
OUT_SUMMARY = BASE / "summary_v9.json"

VALIDATION_N = 80
MAX_WORKERS = 5
USER_AGENT = "bazi-public-figure-study/1.0 (NAS official-profile DOB refresh; no BaZi computation)"

MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
}
MONTH_RE = (
    r"(January|February|March|April|May|June|July|August|"
    r"September|October|November|December)"
)
DATE_RE = re.compile(
    rf"\b{MONTH_RE}\s+(\d{{1,2}}),\s+(\d{{4}})\b",
    re.I,
)

_thread_local = threading.local()


class VisibleText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag.lower() in {"script", "style", "noscript"}:
            self.skip += 1

    def handle_endtag(self, tag):
        if tag.lower() in {"script", "style", "noscript"} and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if self.skip:
            return
        s = re.sub(r"\s+", " ", html.unescape(data or "")).strip()
        if s:
            self.parts.append(s)


def read_csv(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows, fields=None):
    if fields is None:
        fields = list(rows[0].keys()) if rows else []
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


def reliable_qid(row):
    q = str(row.get("wikidata_qid") or "").strip()
    if q:
        return q
    q = str(row.get("global_candidate_qid") or "").strip()
    return q if q and as_int(row.get("global_match_accepted")) == 1 else ""


def year_values(s):
    return set(re.findall(r"(?<!\d)([12]\d{3})-\d{2}-\d{2}", str(s or "")))


def known_birth_year(row, wd_by_qid):
    qid = reliable_qid(row)
    if not qid:
        return "", 0
    wr = wd_by_qid.get(qid, {})
    vals = set()
    for col in (
        "exact_day_values",
        "month_precision_values",
        "year_precision_values",
        "direct_p569_values",
    ):
        vals |= year_values(wr.get(col, ""))
    if len(vals) == 1:
        return next(iter(vals)), 0
    if len(vals) > 1:
        return "", 1
    return "", 0


def iso_date(month_name, day, year):
    try:
        return dt.date(int(year), MONTHS[month_name.lower()], int(day)).isoformat()
    except Exception:
        return ""


def extract_birth_death(html_text):
    parser = VisibleText()
    parser.feed(html_text)
    parts = parser.parts

    candidates = []
    for i, part in enumerate(parts):
        label = re.sub(r"\s+", " ", part).strip().casefold()
        if "birth / deceased date" not in label and "birth/deceased date" not in label:
            continue
        window = " ".join(parts[i + 1:i + 12])
        dates = DATE_RE.findall(window)
        exacts = []
        for mon, day, year in dates[:2]:
            z = iso_date(mon, day, year)
            if z:
                exacts.append(z)
        if exacts:
            candidates.append((exacts[0], exacts[1] if len(exacts) > 1 else "", window[:500]))

    unique_birth = sorted({x[0] for x in candidates if x[0]})
    if len(unique_birth) != 1:
        return "", "", len(unique_birth), ""
    birth = unique_birth[0]
    deaths = sorted({x[1] for x in candidates if x[0] == birth and x[1]})
    death = deaths[0] if len(deaths) == 1 else ""
    evidence = next((x[2] for x in candidates if x[0] == birth), "")
    return birth, death, len(unique_birth), evidence


def fetch_profile(url, retries=6):
    last = ""
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept": "text/html,application/xhtml+xml",
                    "Accept-Language": "en-US,en;q=0.8",
                },
            )
            with urllib.request.urlopen(req, timeout=90) as resp:
                raw = resp.read()
                final_url = resp.geturl()
                status = getattr(resp, "status", 200)
            text = raw.decode("utf-8", errors="replace")
            birth, death, count, evidence = extract_birth_death(text)
            return {
                "fetch_ok": 1,
                "http_status": status,
                "final_url": final_url,
                "current_nas_birth_dob": birth,
                "current_nas_death_dod": death,
                "parsed_birth_candidate_count": count,
                "evidence_text": evidence,
                "error": "",
            }
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code}: {e.reason}"
            if e.code not in {429, 500, 502, 503, 504} or attempt + 1 >= retries:
                break
            retry_after = (e.headers.get("Retry-After") or "").strip()
            try:
                delay = float(retry_after)
            except Exception:
                delay = min(30.0, 2.0 ** attempt)
            time.sleep(max(1.0, min(60.0, delay)))
        except Exception as e:
            last = repr(e)
            if attempt + 1 >= retries:
                break
            time.sleep(min(20.0, 2.0 ** attempt))
    return {
        "fetch_ok": 0,
        "http_status": "",
        "final_url": "",
        "current_nas_birth_dob": "",
        "current_nas_death_dod": "",
        "parsed_birth_candidate_count": 0,
        "evidence_text": "",
        "error": last,
    }


def validation_hash(row):
    return hashlib.sha256(row["profile_url"].encode("utf-8")).hexdigest()


def main():
    rows = read_csv(INPUT)
    wdrows = read_csv(WIKIDATA)
    if len(rows) != 3051:
        raise RuntimeError(f"Expected 3051 science-core rows, got {len(rows)}")
    wd_by_qid = {r["qid"]: r for r in wdrows if r.get("qid")}

    missing = [r for r in rows if not present(r.get("final_exact_dob"))]

    # Parser validation uses rows whose DOB came directly from an older NAS card.
    validation_pool = [
        r for r in rows
        if present(r.get("final_exact_dob"))
        and present(r.get("nas_card_exact_dob"))
        and r.get("final_exact_dob") == r.get("nas_card_exact_dob")
    ]
    validation_pool.sort(key=validation_hash)
    validation = validation_pool[:VALIDATION_N]

    target = []
    for r in validation:
        target.append((r, "validation"))
    for r in missing:
        target.append((r, "missing"))

    fetched = {}
    urls = sorted({r["profile_url"] for r, _ in target})
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futs = {ex.submit(fetch_profile, url): url for url in urls}
        for fut in as_completed(futs):
            url = futs[fut]
            try:
                fetched[url] = fut.result()
            except Exception as e:
                fetched[url] = {
                    "fetch_ok": 0, "http_status": "", "final_url": "",
                    "current_nas_birth_dob": "", "current_nas_death_dod": "",
                    "parsed_birth_candidate_count": 0, "evidence_text": "",
                    "error": repr(e),
                }

    diag = []
    by_url = {r["profile_url"]: r for r in rows}
    for r, purpose in target:
        f = fetched.get(r["profile_url"], {})
        birth = f.get("current_nas_birth_dob", "")
        existing = (r.get("final_exact_dob") or "").strip()
        ky, ky_conflict = known_birth_year(r, wd_by_qid)
        year_agree = ""
        if birth and ky:
            year_agree = int(birth[:4] == ky)
        try:
            age = int(r.get("election_year") or 0) - int(birth[:4]) if birth else None
        except Exception:
            age = None
        age_ok = int(age is not None and 25 <= age <= 100) if birth else ""

        comparison = ""
        if purpose == "validation" and birth:
            comparison = "match" if birth == existing else "conflict"

        current_year_ok = (
            bool(birth)
            and not ky_conflict
            and (not ky or birth[:4] == ky)
        )
        candidate = int(
            purpose == "missing"
            and current_year_ok
            and age_ok == 1
            and as_int(f.get("parsed_birth_candidate_count")) == 1
        )

        diag.append({
            "profile_url": r.get("profile_url", ""),
            "name": r.get("name", ""),
            "purpose": purpose,
            "election_year": r.get("election_year", ""),
            "deceased_snapshot": r.get("deceased", ""),
            "primary_section": r.get("primary_section", ""),
            "existing_final_exact_dob": existing,
            "known_birth_year": ky,
            "known_birth_year_conflict": ky_conflict,
            "fetch_ok": f.get("fetch_ok", 0),
            "http_status": f.get("http_status", ""),
            "final_url": f.get("final_url", ""),
            "current_nas_birth_dob": birth,
            "current_nas_death_dod": f.get("current_nas_death_dod", ""),
            "parsed_birth_candidate_count": f.get("parsed_birth_candidate_count", 0),
            "current_nas_vs_known_year_agree": year_agree,
            "age_at_election": age if age is not None else "",
            "age_plausible": age_ok,
            "validation_comparison": comparison,
            "candidate_for_supplement": candidate,
            "evidence_text": f.get("evidence_text", ""),
            "fetch_error": f.get("error", ""),
        })

    write_csv(OUT_DIAG, diag)

    val = [x for x in diag if x["purpose"] == "validation"]
    val_comp = [x for x in val if x["validation_comparison"] in {"match", "conflict"}]
    val_matches = sum(x["validation_comparison"] == "match" for x in val)
    val_conflicts = [x for x in val if x["validation_comparison"] == "conflict"]
    candidates = [x for x in diag if x["candidate_for_supplement"] == 1]

    # Safety gate: only auto-apply if the official-page parser validates cleanly
    # on at least 30 comparable old NAS-card records and >= 98% exact agreement.
    validation_rate = val_matches / len(val_comp) if val_comp else 0.0
    auto_apply_enabled = len(val_comp) >= 30 and validation_rate >= 0.98

    log = []
    if auto_apply_enabled:
        for x in candidates:
            r = by_url[x["profile_url"]]
            if present(r.get("final_exact_dob")):
                raise RuntimeError(f"Current NAS supplement would overwrite resolved DOB: {r['name']}")
            r["final_exact_dob"] = x["current_nas_birth_dob"]
            r["dob_status"] = "exact_current_nas_official_profile"
            r["current_nas_profile_final_url"] = x["final_url"]
            r["current_nas_profile_death_dod"] = x["current_nas_death_dod"]
            r["current_nas_profile_evidence_text"] = x["evidence_text"]
            log.append({
                "profile_url": x["profile_url"],
                "name": x["name"],
                "new_final_exact_dob": x["current_nas_birth_dob"],
                "current_nas_death_dod": x["current_nas_death_dod"],
                "final_url": x["final_url"],
                "known_birth_year": x["known_birth_year"],
                "evidence_text": x["evidence_text"],
            })

    for r in rows:
        for k in (
            "current_nas_profile_final_url",
            "current_nas_profile_death_dod",
            "current_nas_profile_evidence_text",
        ):
            r.setdefault(k, "")

    write_csv(OUT_CROSSWALK, rows)
    write_csv(OUT_LOG, log)

    exact = sum(present(r.get("final_exact_dob")) for r in rows)
    living = [r for r in rows if r.get("deceased") != "Y"]
    dead = [r for r in rows if r.get("deceased") == "Y"]
    unresolved = [r for r in rows if not present(r.get("final_exact_dob"))]

    summary = {
        "dataset": "NAS science-core exact-DOB crosswalk v9 current official profile refresh",
        "parent": INPUT.name,
        "science_core_rows": len(rows),
        "target_missing_rows": len(missing),
        "validation_sample_n": len(validation),
        "unique_profile_urls_fetched": len(urls),
        "fetch_successes": sum(as_int(x.get("fetch_ok")) for x in diag),
        "validation_comparable_rows": len(val_comp),
        "validation_exact_matches": val_matches,
        "validation_exact_conflicts": len(val_conflicts),
        "validation_match_rate": round(validation_rate, 6) if val_comp else None,
        "auto_apply_enabled": int(auto_apply_enabled),
        "missing_rows_with_current_nas_exact_birth": sum(
            x["purpose"] == "missing" and present(x["current_nas_birth_dob"]) for x in diag
        ),
        "missing_rows_candidate_for_supplement": len(candidates),
        "current_nas_rows_applied": len(log),
        "final_exact_dob_rows": exact,
        "final_exact_dob_coverage": round(exact / len(rows), 6),
        "remaining_without_exact_dob": len(unresolved),
        "living_rows_snapshot_classification": len(living),
        "living_exact_dob_rows": sum(present(r.get("final_exact_dob")) for r in living),
        "living_exact_dob_coverage": round(
            sum(present(r.get("final_exact_dob")) for r in living) / len(living), 6
        ),
        "deceased_rows_snapshot_classification": len(dead),
        "deceased_exact_dob_rows": sum(present(r.get("final_exact_dob")) for r in dead),
        "deceased_exact_dob_coverage": round(
            sum(present(r.get("final_exact_dob")) for r in dead) / len(dead), 6
        ),
        "validation_conflict_names": [x["name"] for x in val_conflicts],
        "bazi_variables_computed": 0,
        "policy_note": (
            "Cohort and historical deceased/living classification remain frozen. Current NAS "
            "official profile pages are used only to enrich exact DOB. Auto-apply requires a "
            "clean parser validation gate and no conflict with a unique pre-existing birth year."
        ),
    }
    OUT_SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
