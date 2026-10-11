#!/usr/bin/env python3
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

ROSTER = Path("data/leopoldina_roster_freeze_v1/leopoldina_science_core_roster_freeze_v1.csv")
FREEZE = Path("data/leopoldina_roster_freeze_v1.json")
OUT = Path("data/leopoldina_wikidata_memberid_dob_pilot_v1")
QLEVER = "https://qlever.dev/api/wikidata"
UA = "bazi-public-figure-study/1.0 (Leopoldina P10299 exact-DOB diagnostic; no BaZi computation)"

def read_csv(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

def write_csv(path: Path, rows, fields):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

def sha256(path: Path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

def qlever_tsv(query: str, retries=6):
    body = urllib.parse.urlencode({"query": query, "action": "tsv_export"}).encode()
    last = None
    for attempt in range(retries):
        req = urllib.request.Request(
            QLEVER,
            data=body,
            method="POST",
            headers={
                "User-Agent": UA,
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "text/tab-separated-values",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                raw = r.read().decode("utf-8-sig")
            break
        except (urllib.error.HTTPError, urllib.error.URLError) as e:
            last = e
            code = getattr(e, "code", None)
            if attempt + 1 >= retries or (code is not None and code not in {429, 500, 502, 503, 504}):
                raise
            time.sleep(min(30, 2 ** attempt))
    else:
        raise RuntimeError(f"QLever failed after retries: {last}")

    rr = list(csv.reader(raw.splitlines(), delimiter="\t"))
    if not rr:
        return []
    headers = [x.lstrip("?").strip() for x in rr[0]]
    out = []
    for row in rr[1:]:
        if not row:
            continue
        row += [""] * (len(headers) - len(row))
        item = {}
        for i, h in enumerate(headers):
            v = (row[i] or "").strip()
            if v.startswith("<") and v.endswith(">"):
                v = v[1:-1]
            elif len(v) >= 2 and v[0] == '"':
                # Strip outer lexical quotes, preserving the lexical value before datatype/lang suffix.
                m = re.match(r'^"(.*)"(?:\^\^<[^>]+>|@[A-Za-z-]+)?$', v)
                if m:
                    v = m.group(1)
            item[h] = v
        out.append(item)
    return out

def parse_qid(v):
    return (v or "").rsplit("/", 1)[-1]

def parse_date(v):
    m = re.search(r"([12]\d{3})-(\d{2})-(\d{2})", v or "")
    if not m:
        return ""
    try:
        return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat()
    except ValueError:
        return ""

def as_int(v):
    try:
        return int(float(str(v)))
    except Exception:
        return None

def era(year):
    y = int(year)
    if y <= 1900:
        return "<=1900"
    if y <= 1950:
        return "1901-1950"
    if y <= 2000:
        return "1951-2000"
    return "2001-2025"

def main():
    freeze = json.loads(FREEZE.read_text(encoding="utf-8"))
    roster = read_csv(ROSTER)
    if len(roster) != 2888:
        raise RuntimeError(f"Expected 2888 frozen roster rows, got {len(roster)}")
    if freeze.get("checksums", {}).get("roster_csv_sha256") != sha256(ROSTER):
        raise RuntimeError("Frozen Leopoldina roster hash mismatch")
    slugs = [r["member_slug"].strip() for r in roster]
    if len(set(slugs)) != len(slugs):
        raise RuntimeError("Frozen roster member_slug is not unique")

    query = """
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX p: <http://www.wikidata.org/prop/>
PREFIX psv: <http://www.wikidata.org/prop/statement/value/>
PREFIX wikibase: <http://wikiba.se/ontology#>
SELECT ?person ?memberId ?dob ?precision ?gnd ?loc WHERE {
  ?person wdt:P10299 ?memberId .
  OPTIONAL {
    ?person p:P569 ?dobStatement .
    ?dobStatement psv:P569 ?dobNode .
    ?dobNode wikibase:timeValue ?dob ;
             wikibase:timePrecision ?precision .
  }
  OPTIONAL { ?person wdt:P227 ?gnd . }
  OPTIONAL { ?person wdt:P244 ?loc . }
}
"""
    raw = qlever_tsv(query)
    by_slug = {}
    for x in raw:
        slug = (x.get("memberId") or "").strip()
        if not slug:
            continue
        qid = parse_qid(x.get("person", ""))
        rec = by_slug.setdefault(slug, {"qids": set(), "dates": set(), "gnd": set(), "loc": set(), "precisions": set()})
        if qid:
            rec["qids"].add(qid)
        prec = as_int(x.get("precision"))
        dob = parse_date(x.get("dob", ""))
        if dob and prec is not None:
            rec["dates"].add((dob, prec))
            rec["precisions"].add(prec)
        if (x.get("gnd") or "").strip():
            rec["gnd"].add((x.get("gnd") or "").strip())
        if (x.get("loc") or "").strip():
            rec["loc"].add((x.get("loc") or "").strip())

    rows = []
    for r in roster:
        slug = r["member_slug"].strip()
        w = by_slug.get(slug, {"qids": set(), "dates": set(), "gnd": set(), "loc": set(), "precisions": set()})
        qids = sorted(w["qids"])
        day_dates = sorted({d for d, p in w["dates"] if p >= 11})
        all_dates = sorted(f"{d}@p{p}" for d, p in w["dates"])
        unique_day = day_dates[0] if len(day_dates) == 1 and len(qids) == 1 else ""
        age = int(r["election_year"]) - int(unique_day[:4]) if unique_day else None
        age_ok = int(age is not None and 15 <= age <= 110) if unique_day else ""
        rows.append({
            "member_slug": slug,
            "display_name": r["display_name"],
            "detail_url": r["detail_url"],
            "deceased_marker": r["deceased_marker"],
            "class": r["class"],
            "section": r["section"],
            "election_year": r["election_year"],
            "election_era": era(r["election_year"]),
            "wikidata_qids": "|".join(qids),
            "qid_count": len(qids),
            "wikidata_date_values": "|".join(all_dates),
            "day_precision_dates": "|".join(day_dates),
            "day_precision_date_count": len(day_dates),
            "unique_day_precision_dob": unique_day,
            "age_at_election_if_unique": age if age is not None else "",
            "age_plausible_if_unique": age_ok,
            "gnd_ids": "|".join(sorted(w["gnd"])),
            "loc_ids": "|".join(sorted(w["loc"])),
            "accepted_exact_dob": "",
            "bazi_variables_computed": 0,
        })

    fields = list(rows[0].keys())
    OUT.mkdir(parents=True, exist_ok=True)
    write_csv(OUT / "roster_p10299_crosswalk.csv", rows, fields)
    conflicts = [x for x in rows if int(x["qid_count"]) > 1 or int(x["day_precision_date_count"]) > 1 or (x["unique_day_precision_dob"] and x["age_plausible_if_unique"] != 1)]
    write_csv(OUT / "review_queue.csv", conflicts, fields)

    def stats(rr):
        return {
            "rows": len(rr),
            "matched_unique_qid": sum(int(x["qid_count"]) == 1 for x in rr),
            "unmatched_p10299": sum(int(x["qid_count"]) == 0 for x in rr),
            "multiple_qids_same_slug": sum(int(x["qid_count"]) > 1 for x in rr),
            "unique_day_precision_dob": sum(bool(x["unique_day_precision_dob"]) for x in rr),
            "unique_day_precision_dob_age_plausible": sum(bool(x["unique_day_precision_dob"]) and x["age_plausible_if_unique"] == 1 for x in rr),
            "multiple_day_precision_dates": sum(int(x["day_precision_date_count"]) > 1 for x in rr),
            "has_gnd_id": sum(bool(x["gnd_ids"]) for x in rr),
            "has_loc_id": sum(bool(x["loc_ids"]) for x in rr),
        }

    summary = {
        "dataset": "Leopoldina Wikidata P10299 exact-DOB diagnostic v1",
        "frozen_roster_rows": len(roster),
        "frozen_roster_sha256": sha256(ROSTER),
        "wikidata_rows_returned": len(raw),
        "wikidata_distinct_member_ids": len(by_slug),
        "overall": stats(rows),
        "by_status": {
            "deceased_marker": stats([x for x in rows if x["deceased_marker"] == "1"]),
            "no_deceased_marker": stats([x for x in rows if x["deceased_marker"] != "1"]),
        },
        "by_election_era": {
            e: stats([x for x in rows if x["election_era"] == e])
            for e in ("<=1900", "1901-1950", "1951-2000", "2001-2025")
        },
        "review_queue_rows": len(conflicts),
        "dob_values_accepted": 0,
        "bazi_variables_computed": 0,
        "identity_rule": "Exact official member_slug == Wikidata P10299 Leopoldina member ID. No name matching or fuzzy matching.",
        "dob_rule": "Diagnostic candidate requires exactly one QID for the official slug and exactly one P569 value with Wikidata timePrecision >= 11 (day precision). No DOBs are written in this stage.",
    }
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
