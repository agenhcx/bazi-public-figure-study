#!/usr/bin/env python3
"""
Fetch Wikidata P106 (occupation) for people in 1986_people.csv,
resolve occupation labels, group them into broad career categories,
and summarize both the whole year and 1986-05-14.

Designed for the same Windows setup used by birthdate_scan_v7.py:
curl.exe + optional local HTTP proxy.

Dependencies:
    pip install pandas

Example:
    python occupation_scan_1986.py --input 1986_people.csv --year 1986 \
        --proxy http://127.0.0.1:10808

Outputs under occupation_scan_1986/:
    1986_people_with_occupations.csv
    1986_raw_occupation_counts.csv
    1986_broad_category_counts.csv
    1986_daily_category_stats.csv
    1986_occupation_summary.txt
    cache/...

Important:
- Broad categories are heuristic, based on English Wikidata occupation labels.
- They are OVERLAPPING: actor+singer counts in both Film/TV and Music.
- Raw P106 labels are also exported so the category rules can be audited/refined.
"""

import argparse
import csv
import json
import math
import random
import re
import subprocess
import time
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlencode

import pandas as pd

WIKIDATA_API = "https://www.wikidata.org/w/api.php"
USER_AGENT = "BirthdateOccupationStudy/0.1 (personal research; local script)"


# -------------------------
# Robust curl JSON fetcher
# -------------------------

class CurlSession:
    def __init__(self, proxy=None):
        self.proxy = proxy


def curl_json(session, url, params, *, method="POST",
              max_attempts=8, connect_timeout=20, max_time=90):
    if method == "POST":
        body = urlencode(params)
        cmd = [
            "curl.exe",
            "--silent", "--show-error", "--fail-with-body",
            "--connect-timeout", str(connect_timeout),
            "--max-time", str(max_time),
            "--retry", "2",
            "--retry-all-errors",
            "--retry-delay", "1",
            "-H", f"User-Agent: {USER_AGENT}",
            "-H", "Accept: application/json",
            "-H", "Accept-Encoding: identity",
            "-H", "Content-Type: application/x-www-form-urlencoded",
            "--data-binary", body,
            url,
        ]
    else:
        full_url = url + "?" + urlencode(params)
        cmd = [
            "curl.exe",
            "--silent", "--show-error", "--fail-with-body",
            "--connect-timeout", str(connect_timeout),
            "--max-time", str(max_time),
            "--retry", "2",
            "--retry-all-errors",
            "--retry-delay", "1",
            "-H", f"User-Agent: {USER_AGENT}",
            "-H", "Accept: application/json",
            "-H", "Accept-Encoding: identity",
            full_url,
        ]

    if session.proxy:
        cmd[1:1] = ["--proxy", session.proxy]

    last_error = None

    for attempt in range(1, max_attempts + 1):
        try:
            cp = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=max_time + 15,
            )
            if cp.returncode != 0:
                raise RuntimeError(
                    f"curl exit {cp.returncode}: "
                    f"{(cp.stderr or cp.stdout)[:500].strip()}"
                )

            text = cp.stdout.strip()

            # Wikimedia rate-limit messages can occasionally be prepended
            # before an otherwise-valid JSON object. Recover the JSON tail.
            if not text.startswith("{"):
                pos = text.find("{")
                if pos >= 0:
                    text = text[pos:]

            data = json.loads(text)

            if isinstance(data, dict) and "error" in data:
                code = data["error"].get("code", "unknown")
                info = data["error"].get("info", "")
                raise RuntimeError(f"API error {code}: {info}")

            return data

        except Exception as e:
            last_error = e
            if attempt == max_attempts:
                break
            wait = min(45, 2 ** min(attempt, 5) + random.random())
            print(f"    curl/API error: {e}")
            print(f"    retry {attempt}/{max_attempts} in {wait:.1f}s")
            time.sleep(wait)

    raise RuntimeError(
        f"curl request failed after {max_attempts} attempts: {last_error}"
    )


def connectivity_test(session):
    data = curl_json(
        session,
        WIKIDATA_API,
        {
            "action": "query",
            "format": "json",
            "meta": "siteinfo",
            "siprop": "general",
        },
        method="GET",
        max_attempts=3,
        max_time=30,
    )
    if "query" not in data:
        raise RuntimeError("Unexpected Wikidata connectivity response.")
    print("Connectivity OK: Wikidata")


# -------------------------
# Wikidata P106 collection
# -------------------------

def chunked(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i+n]


def fetch_p106_claims(session, qids, cache_dir, batch_size=50, sleep_s=0.8):
    """
    Returns:
        qid -> sorted unique P106 occupation QIDs
    """
    out = {}
    batches = list(chunked(qids, batch_size))
    print(f"[1/4] Fetching P106 claims in {len(batches)} batches ...")

    for bi, batch in enumerate(batches):
        cache_path = cache_dir / f"claims_{bi:05d}.json"

        if cache_path.exists():
            entities = json.loads(cache_path.read_text(encoding="utf-8"))
            status = "cached"
        else:
            data = curl_json(
                session,
                WIKIDATA_API,
                {
                    "action": "wbgetentities",
                    "format": "json",
                    "ids": "|".join(batch),
                    "props": "claims",
                },
                method="POST",
            )
            entities = data.get("entities", {})
            cache_path.write_text(
                json.dumps(entities, ensure_ascii=False),
                encoding="utf-8",
            )
            status = "downloaded"
            time.sleep(sleep_s)

        n_with = 0
        for qid in batch:
            entity = entities.get(qid, {})
            occs = set()

            for claim in entity.get("claims", {}).get("P106", []):
                if claim.get("rank") == "deprecated":
                    continue
                snak = claim.get("mainsnak", {})
                if snak.get("snaktype") != "value":
                    continue
                dv = snak.get("datavalue", {})
                if dv.get("type") != "wikibase-entityid":
                    continue
                value = dv.get("value", {})
                occ_qid = value.get("id")
                if occ_qid:
                    occs.add(occ_qid)

            out[qid] = sorted(occs)
            if occs:
                n_with += 1

        print(
            f"    [{bi+1:04d}/{len(batches):04d}] {status}: "
            f"people={len(batch):2d}, with P106={n_with:2d}"
        )

    return out


def fetch_labels(session, occ_qids, cache_dir, batch_size=50, sleep_s=0.8):
    """
    Returns:
        occupation_qid -> English/fallback label
    """
    labels = {}
    occ_qids = sorted(set(occ_qids))
    batches = list(chunked(occ_qids, batch_size))
    print(f"[2/4] Resolving {len(occ_qids):,} occupation QIDs in {len(batches)} batches ...")

    for bi, batch in enumerate(batches):
        cache_path = cache_dir / f"labels_{bi:05d}.json"

        if cache_path.exists():
            entities = json.loads(cache_path.read_text(encoding="utf-8"))
            status = "cached"
        else:
            data = curl_json(
                session,
                WIKIDATA_API,
                {
                    "action": "wbgetentities",
                    "format": "json",
                    "ids": "|".join(batch),
                    "props": "labels",
                    "languages": "en",
                    "languagefallback": "1",
                },
                method="POST",
            )
            entities = data.get("entities", {})
            cache_path.write_text(
                json.dumps(entities, ensure_ascii=False),
                encoding="utf-8",
            )
            status = "downloaded"
            time.sleep(sleep_s)

        for qid in batch:
            entity = entities.get(qid, {})
            label = entity.get("labels", {}).get("en", {}).get("value")
            labels[qid] = label or qid

        print(
            f"    [{bi+1:03d}/{len(batches):03d}] {status}: "
            f"occupations={len(batch):2d}"
        )

    return labels


# -------------------------
# Broad occupation taxonomy
# -------------------------

# All categories are non-exclusive / overlapping.
# Match against lower-case English P106 labels.

CATEGORY_PATTERNS = {
    "Sports athlete/player": [
        r"\bathlete\b",
        r"\bsportsperson\b",
        r"\bfootball player\b",
        r"\bfootballer\b",
        r"\bsoccer player\b",
        r"\bbasketball player\b",
        r"\bbaseball player\b",
        r"\bice hockey player\b",
        r"\bfield hockey player\b",
        r"\bhockey player\b",
        r"\brugby .*player\b",
        r"\bcricketer\b",
        r"\btennis player\b",
        r"\bbadminton player\b",
        r"\btable tennis player\b",
        r"\bvolleyball player\b",
        r"\bhandball player\b",
        r"\bwater polo player\b",
        r"\blacrosse player\b",
        r"\bgolfer\b",
        r"\bboxer\b",
        r"\bkickboxer\b",
        r"\bmixed martial artist\b",
        r"\bmartial artist\b",
        r"\bwrestler\b",
        r"\bjudoka\b",
        r"\bkarateka\b",
        r"\btaekwondo athlete\b",
        r"\bfencer\b",
        r"\bswimmer\b",
        r"\bdiver\b",
        r"\brower\b",
        r"\bcanoeist\b",
        r"\bkayaker\b",
        r"\bcyclist\b",
        r"\bracing driver\b",
        r"\brally driver\b",
        r"\bmotorcycle racer\b",
        r"\bskier\b",
        r"\bsnowboarder\b",
        r"\bskater\b",
        r"\bgymnast\b",
        r"\bweightlifter\b",
        r"\bpowerlifter\b",
        r"\bbodybuilder\b",
        r"\btriathlete\b",
        r"\bmarathon runner\b",
        r"\bsprinter\b",
        r"\bmiddle-distance runner\b",
        r"\blong-distance runner\b",
        r"\bhurdler\b",
        r"\bhigh jumper\b",
        r"\blong jumper\b",
        r"\btriple jumper\b",
        r"\bpole vaulter\b",
        r"\bshot putter\b",
        r"\bdiscus thrower\b",
        r"\bjavelin thrower\b",
        r"\bdecathlete\b",
        r"\bheptathlete\b",
        r"\barcher\b",
        r"\bshooter\b",
        r"\bequestrian\b",
        r"\bjockey\b",
        r"\bsurfer\b",
        r"\bsailor\b",
        r"\bbiathlete\b",
        r"\bbobsledder\b",
        r"\bluger\b",
        r"\bskeleton racer\b",
    ],

    "Music": [
        r"\bsinger\b",
        r"\bvocalist\b",
        r"\bmusician\b",
        r"\bsinger-songwriter\b",
        r"\bsongwriter\b",
        r"\bcomposer\b",
        r"\brapper\b",
        r"\bdisc jockey\b",
        r"\bdj\b",
        r"\brecord producer\b",
        r"\bmusic producer\b",
        r"\bguitarist\b",
        r"\bbassist\b",
        r"\bdrummer\b",
        r"\bpianist\b",
        r"\bkeyboardist\b",
        r"\bviolinist\b",
        r"\bviolist\b",
        r"\bcellist\b",
        r"\bdouble bassist\b",
        r"\bsaxophonist\b",
        r"\btrumpeter\b",
        r"\btrombonist\b",
        r"\bclarinetist\b",
        r"\bflutist\b",
        r"\boboist\b",
        r"\bpercussionist\b",
        r"\borganist\b",
        r"\bharpist\b",
        r"\bconductor\b",
        r"\bmusic director\b",
        r"\bmusic arranger\b",
    ],

    "Film/TV/Acting": [
        r"\bactor\b",
        r"\bactress\b",
        r"\bfilm actor\b",
        r"\btelevision actor\b",
        r"\bvoice actor\b",
        r"\bstage actor\b",
        r"\bfilm director\b",
        r"\btelevision director\b",
        r"\bscreenwriter\b",
        r"\bfilm producer\b",
        r"\btelevision producer\b",
        r"\bcinematographer\b",
        r"\bcomedian\b",
        r"\btelevision presenter\b",
        r"\btelevision personality\b",
        r"\bmedia personality\b",
        r"\bmodel\b",
    ],

    "Business/Entrepreneurship": [
        r"\bentrepreneur\b",
        r"\bbusinessperson\b",
        r"\bbusiness executive\b",
        r"\bchief executive officer\b",
        r"\bchief operating officer\b",
        r"\bbanker\b",
        r"\binvestor\b",
        r"\bventure capitalist\b",
        r"\bfinancier\b",
        r"\bindustrialist\b",
        r"\bcompany founder\b",
        r"\bbusiness magnate\b",
    ],

    "Politics/Government": [
        r"\bpolitician\b",
        r"\bdiplomat\b",
        r"\bmayor\b",
        r"\blegislator\b",
        r"\bmember of parliament\b",
        r"\bmember of .*assembly\b",
        r"\bgovernment minister\b",
        r"\bminister of\b",
        r"\bpublic servant\b",
        r"\bcivil servant\b",
        r"\bpolitical activist\b",
    ],

    "Science/Academia/Engineering": [
        r"\bscientist\b",
        r"\bresearcher\b",
        r"\bacademic\b",
        r"\bprofessor\b",
        r"\bmathematician\b",
        r"\bphysicist\b",
        r"\bchemist\b",
        r"\bbiologist\b",
        r"\beconomist\b",
        r"\bcomputer scientist\b",
        r"\bengineer\b",
        r"\bastronomer\b",
        r"\bgeologist\b",
        r"\bpsychologist\b",
        r"\bsociologist\b",
        r"\barchaeologist\b",
        r"\bhistorian\b",
    ],

    "Writing/Journalism": [
        r"\bwriter\b",
        r"\bauthor\b",
        r"\bnovelist\b",
        r"\bpoet\b",
        r"\bplaywright\b",
        r"\bjournalist\b",
        r"\bcolumnist\b",
        r"\breporter\b",
        r"\beditor\b",
        r"\bblogger\b",
    ],

    "Visual arts/Design": [
        r"\bartist\b",
        r"\bpainter\b",
        r"\bsculptor\b",
        r"\billustrator\b",
        r"\bphotographer\b",
        r"\bgraphic designer\b",
        r"\bfashion designer\b",
        r"\bdesigner\b",
        r"\barchitect\b",
    ],

    "Games/Esports": [
        r"\bchess player\b",
        r"\bpoker player\b",
        r"\bgo player\b",
        r"\besports player\b",
        r"\be-sports player\b",
        r"\bprofessional gamer\b",
        r"\bvideo game player\b",
    ],

    "Law": [
        r"\blawyer\b",
        r"\battorney\b",
        r"\bjudge\b",
        r"\bjurist\b",
        r"\bprosecutor\b",
        r"\bbarrister\b",
        r"\bsolicitor\b",
    ],

    "Medicine/Health": [
        r"\bphysician\b",
        r"\bmedical doctor\b",
        r"\bsurgeon\b",
        r"\bnurse\b",
        r"\bdentist\b",
        r"\bpharmacist\b",
        r"\bpsychiatrist\b",
        r"\btherapist\b",
    ],

    "Religion": [
        r"\bpriest\b",
        r"\bpastor\b",
        r"\bbishop\b",
        r"\bcleric\b",
        r"\btheologian\b",
        r"\brabbi\b",
        r"\bimam\b",
        r"\bmonk\b",
        r"\bnun\b",
    ],
}

COMPILED = {
    cat: [re.compile(pat, re.I) for pat in pats]
    for cat, pats in CATEGORY_PATTERNS.items()
}


def classify_labels(labels):
    cats = set()
    for label in labels:
        txt = label.lower()

        # Avoid treating games as sports because some labels contain "player".
        is_game = any(rx.search(txt) for rx in COMPILED["Games/Esports"])
        if is_game:
            cats.add("Games/Esports")

        for cat, patterns in COMPILED.items():
            if cat == "Games/Esports":
                continue
            if cat == "Sports athlete/player" and is_game:
                continue
            if any(rx.search(txt) for rx in patterns):
                cats.add(cat)

    return sorted(cats)


# -------------------------
# Statistics
# -------------------------

def hypergeom_upper_tail(k, n, K, N):
    """
    P[X >= k] where X ~ Hypergeom(N population, K successes, n draws)
    using exact integer combinations.
    """
    max_x = min(n, K)
    min_x = max(0, n - (N - K))
    if k <= min_x:
        return 1.0
    if k > max_x:
        return 0.0

    denom = math.comb(N, n)
    num = 0
    for x in range(k, max_x + 1):
        if 0 <= n - x <= N - K:
            num += math.comb(K, x) * math.comb(N - K, n - x)
    return num / denom


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="1986_people.csv")
    ap.add_argument("--year", type=int, default=1986)
    ap.add_argument("--proxy", default=None)
    ap.add_argument("--outdir", default=None)
    ap.add_argument("--batch-size", type=int, default=50)
    ap.add_argument("--sleep", type=float, default=0.8)
    ap.add_argument("--include-conflicts", action="store_true",
                    help="Include rows marked dob_conflict=True (default excludes them).")
    args = ap.parse_args()

    inpath = Path(args.input)
    if not inpath.exists():
        raise SystemExit(f"Input not found: {inpath}")

    outdir = Path(args.outdir or f"occupation_scan_{args.year}")
    outdir.mkdir(parents=True, exist_ok=True)
    cache_dir = outdir / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(inpath, dtype={"qid": str, "name": str, "dob": str})

    needed = {"qid", "name", "dob", "dob_conflict"}
    missing = needed - set(df.columns)
    if missing:
        raise SystemExit(f"Missing required columns: {sorted(missing)}")

    # Robust bool parsing
    df["dob_conflict"] = (
        df["dob_conflict"]
        .astype(str)
        .str.lower()
        .map({"true": True, "false": False})
        .fillna(False)
    )

    if not args.include_conflicts:
        df = df.loc[~df["dob_conflict"]].copy()

    # One person per QID for occupation analysis.
    # If duplicate rows remain, keep first.
    people = df.drop_duplicates("qid").copy()
    people["dob"] = pd.to_datetime(people["dob"], errors="coerce")
    people = people.loc[people["dob"].dt.year == args.year].copy()

    print(f"Input people used: {len(people):,}")
    print(f"Proxy: {args.proxy or '(none)'}")

    session = CurlSession(args.proxy)
    connectivity_test(session)

    qids = people["qid"].tolist()

    p106 = fetch_p106_claims(
        session, qids, cache_dir,
        batch_size=args.batch_size,
        sleep_s=args.sleep,
    )

    all_occ_qids = sorted({
        occ
        for occs in p106.values()
        for occ in occs
    })

    labels = fetch_labels(
        session, all_occ_qids, cache_dir,
        batch_size=args.batch_size,
        sleep_s=args.sleep,
    )

    print("[3/4] Building occupation/category table ...")

    people["occupation_qids"] = people["qid"].map(
        lambda q: "; ".join(p106.get(q, []))
    )
    people["occupation_labels"] = people["qid"].map(
        lambda q: "; ".join(
            sorted(labels.get(oq, oq) for oq in p106.get(q, []))
        )
    )
    people["broad_categories"] = people["qid"].map(
        lambda q: "; ".join(
            classify_labels(
                [labels.get(oq, oq) for oq in p106.get(q, [])]
            )
        )
    )
    people["has_p106"] = people["qid"].map(
        lambda q: bool(p106.get(q))
    )

    people_out = outdir / f"{args.year}_people_with_occupations.csv"
    people.to_csv(people_out, index=False, encoding="utf-8-sig")

    # Raw P106 label frequency: person-level deduplicated.
    raw_counter = Counter()
    for qid in people["qid"]:
        labs = {labels.get(oq, oq) for oq in p106.get(qid, [])}
        raw_counter.update(labs)

    raw_df = pd.DataFrame(
        raw_counter.most_common(),
        columns=["occupation_label", "n_people"],
    )
    raw_df["pct_all_people"] = raw_df["n_people"] / len(people) * 100
    raw_out = outdir / f"{args.year}_raw_occupation_counts.csv"
    raw_df.to_csv(raw_out, index=False, encoding="utf-8-sig")

    # Broad overlapping categories.
    category_people = defaultdict(set)
    for _, row in people.iterrows():
        cats = [x for x in str(row["broad_categories"]).split("; ") if x]
        for cat in cats:
            category_people[cat].add(row["qid"])

    cat_rows = []
    for cat, qset in category_people.items():
        cat_rows.append({
            "category": cat,
            "n_people": len(qset),
            "pct_all_people": len(qset) / len(people) * 100,
        })

    cat_df = pd.DataFrame(cat_rows).sort_values(
        ["n_people", "category"], ascending=[False, True]
    )
    cat_out = outdir / f"{args.year}_broad_category_counts.csv"
    cat_df.to_csv(cat_out, index=False, encoding="utf-8-sig")

    # Daily category statistics.
    all_categories = sorted(CATEGORY_PATTERNS)
    daily_rows = []
    for dob, g in people.groupby(people["dob"].dt.date):
        qset = set(g["qid"])
        rec = {
            "date": dob.isoformat(),
            "n_people": len(qset),
        }
        for cat in all_categories:
            ncat = len(qset & category_people.get(cat, set()))
            rec[f"{cat}__n"] = ncat
            rec[f"{cat}__pct"] = 100 * ncat / len(qset) if qset else 0.0
        daily_rows.append(rec)

    daily_df = pd.DataFrame(daily_rows).sort_values("date")
    daily_out = outdir / f"{args.year}_daily_category_stats.csv"
    daily_df.to_csv(daily_out, index=False, encoding="utf-8-sig")

    print("[4/4] Writing summary ...")

    with_p106 = int(people["has_p106"].sum())
    target_date = pd.Timestamp(f"{args.year}-05-14").date()
    target = people.loc[people["dob"].dt.date == target_date].copy()

    music_set = category_people.get("Music", set())
    target_music = target.loc[target["qid"].isin(music_set)].copy()

    N = len(people)
    K = len(music_set)
    n = len(target)
    k = len(target_music)
    p_one = hypergeom_upper_tail(k, n, K, N) if N and n else float("nan")

    # Empirical rank of daily music fraction (days with n_people > 0).
    music_pct_col = "Music__pct"
    target_daily = daily_df.loc[daily_df["date"] == target_date.isoformat()]
    if not target_daily.empty:
        target_pct = float(target_daily.iloc[0][music_pct_col])
        pct_rank = (
            (daily_df[music_pct_col] <= target_pct).mean() * 100
        )
    else:
        target_pct = float("nan")
        pct_rank = float("nan")

    summary_lines = [
        f"Year: {args.year}",
        f"People analyzed: {N:,}",
        f"People with >=1 P106 occupation: {with_p106:,} ({100*with_p106/N:.2f}%)",
        f"Unique raw occupation labels: {len(raw_counter):,}",
        "",
        "Top raw Wikidata P106 occupations (person counts; overlapping):",
    ]

    for _, r in raw_df.head(30).iterrows():
        summary_lines.append(
            f"  {r['occupation_label']}: "
            f"{int(r['n_people']):,} ({r['pct_all_people']:.2f}%)"
        )

    summary_lines += [
        "",
        "Broad categories (heuristic; overlapping):",
    ]

    for _, r in cat_df.iterrows():
        summary_lines.append(
            f"  {r['category']}: "
            f"{int(r['n_people']):,} ({r['pct_all_people']:.2f}%)"
        )

    summary_lines += [
        "",
        f"{args.year}-05-14:",
        f"  all analyzed people: {n}",
        f"  Music category people: {k}",
        f"  Music fraction: {100*k/n:.2f}%" if n else "  Music fraction: n/a",
        f"  Whole-year Music people: {K}/{N} ({100*K/N:.2f}%)",
        f"  One-sided Fisher/hypergeometric P[X >= {k}]: {p_one:.6g}",
        f"  Empirical percentile of daily Music fraction: {pct_rank:.1f}",
        "",
        "Music-category people on May 14:",
    ]

    for _, r in target_music.sort_values("name").iterrows():
        summary_lines.append(
            f"  {r['name']} ({r['qid']}): {r['occupation_labels']}"
        )

    summary_lines += [
        "",
        "Notes:",
        "  * Broad categories overlap; e.g. an actor+singer counts in both Film/TV and Music.",
        "  * Category mapping is label-based and heuristic. Audit raw_occupation_counts.csv",
        "    and people_with_occupations.csv before treating category counts as publication-grade.",
        "  * Business/Entrepreneurship is intentionally narrow; ordinary executives/managers",
        "    are not automatically classified as entrepreneurs unless P106 says so.",
        "  * People missing P106 remain in the denominator but are reported via coverage above.",
    ]

    summary = "\n".join(summary_lines)
    summary_out = outdir / f"{args.year}_occupation_summary.txt"
    summary_out.write_text(summary, encoding="utf-8")

    print()
    print(summary)
    print()
    print("Saved:")
    for p in [people_out, raw_out, cat_out, daily_out, summary_out]:
        print(f"  {p}")


if __name__ == "__main__":
    main()
