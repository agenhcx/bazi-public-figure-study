#!/usr/bin/env python3
"""
Robust 1986 birth-date scan without SPARQL / WDQS.

Pipeline:
  1) Enumerate English Wikipedia Category:<YEAR> births
  2) Resolve article titles to Wikidata entities in batches via wbgetentities
  3) Read P569 (date of birth) claims
  4) Keep precise Gregorian day-level dates in the requested year
  5) Produce people.csv + daily_stats.csv + summary.txt + plot

This deliberately avoids query.wikidata.org, so it is not subject to the
public WDQS 60-second SPARQL query limit.

Install:
  pip install requests pandas matplotlib

Run:
  python birthdate_scan_v7.py --year 1986

If your connection is flaky:
  python birthdate_scan_v7.py --year 1986 --batch-size 20 --sleep 0.5
"""

import argparse
import calendar
import json
import math
import random
import time
import subprocess
from urllib.parse import urlencode
from datetime import date
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import requests

ENWIKI_API = "https://en.wikipedia.org/w/api.php"
WIKIDATA_API = "https://www.wikidata.org/w/api.php"

USER_AGENT = "BirthdateDistributionStudy/0.2 (personal research; local script)"
GREGORIAN_QID = "Q1985727"


def request_json(session, url, params, *, method="GET", max_attempts=6, timeout=(20, 90)):
    """
    Fetch JSON using Windows curl.exe rather than requests.

    This is useful on local proxy/VPN setups where curl works but
    Python requests/urllib3 fails during HTTPS CONNECT/TLS tunneling.
    """
    proxy = getattr(session, "_curl_proxy", None)
    connect_timeout = int(timeout[0]) if isinstance(timeout, tuple) else 20
    max_time = int(timeout[1]) if isinstance(timeout, tuple) else int(timeout)

    if method == "POST":
        body = urlencode(params)
        cmd = [
            "curl.exe",
            "--silent",
            "--show-error",
            "--fail-with-body",
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
            "--silent",
            "--show-error",
            "--fail-with-body",
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

    if proxy:
        cmd[1:1] = ["--proxy", proxy]

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

            try:
                data = json.loads(cp.stdout)
            except json.JSONDecodeError as e:
                raise RuntimeError(
                    f"Invalid JSON from API: {e}; "
                    f"response head={cp.stdout[:300]!r}"
                )

            if isinstance(data, dict) and "error" in data:
                code = data["error"].get("code", "unknown")
                info = data["error"].get("info", "")
                raise RuntimeError(f"API error {code}: {info}")

            return data

        except Exception as e:
            last_error = e
            if attempt == max_attempts:
                break
            wait = min(30, 2 ** min(attempt, 4) + random.random())
            print(f"    curl/API error: {e}")
            print(f"    retry {attempt}/{max_attempts} in {wait:.1f}s")
            time.sleep(wait)

    raise RuntimeError(
        f"curl request failed after {max_attempts} attempts: {last_error}"
    )


def new_session(proxy=None):
    class CurlSession:
        pass

    s = CurlSession()
    s._curl_proxy = proxy
    if proxy:
        print(f"Using curl.exe proxy: {proxy}")
    else:
        print("Using curl.exe without explicit proxy")
    return s


def connectivity_test(session):
    tests = [
        ("English Wikipedia", ENWIKI_API),
        ("Wikidata", WIKIDATA_API),
    ]
    for name, url in tests:
        params = {
            "action": "query",
            "format": "json",
            "meta": "siteinfo",
            "siprop": "general",
        }
        try:
            data = request_json(
                session, url, params,
                max_attempts=2,
                timeout=(10, 20),
            )
            print(f"Connectivity OK: {name}")
        except Exception as e:
            raise RuntimeError(
                f"Connectivity test failed for {name}: {e}\n"
                "If you are in a network where Wikimedia is not directly reachable, "
                "run with --proxy http://127.0.0.1:PORT"
            ) from e


def enumerate_birth_category(session, year, cache_path):
    """
    Enumerate all main-namespace pages directly in Category:<year> births.
    MediaWiki categorymembers supports continuation and up to 500 items/request.
    """
    if cache_path.exists():
        pages = json.loads(cache_path.read_text(encoding="utf-8"))
        print(f"[1/3] Loaded category cache: {len(pages):,} pages")
        return pages

    print(f"[1/3] Enumerating Category:{year} births ...")
    pages = []
    cont = None
    request_no = 0

    while True:
        params = {
            "action": "query",
            "format": "json",
            "formatversion": "2",
            "list": "categorymembers",
            "cmtitle": f"Category:{year} births",
            "cmnamespace": "0",
            "cmtype": "page",
            "cmlimit": "500",
            "cmprop": "ids|title",
        }
        if cont:
            params["cmcontinue"] = cont

        data = request_json(session, ENWIKI_API, params)
        batch = data.get("query", {}).get("categorymembers", [])
        pages.extend(batch)
        request_no += 1

        print(f"    category request {request_no}: +{len(batch):,}, total={len(pages):,}")

        nxt = data.get("continue", {}).get("cmcontinue")
        if not nxt:
            break
        cont = nxt
        time.sleep(0.8)

    cache_path.write_text(
        json.dumps(pages, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"    saved category cache: {cache_path}")
    return pages


def parse_birth_claims(entity, year):
    """
    Return sorted unique precise Gregorian YYYY-MM-DD values from non-deprecated
    P569 claims that fall in the requested Gregorian year.
    """
    out = set()

    for claim in entity.get("claims", {}).get("P569", []):
        if claim.get("rank") == "deprecated":
            continue

        snak = claim.get("mainsnak", {})
        if snak.get("snaktype") != "value":
            continue

        dv = snak.get("datavalue", {})
        if dv.get("type") != "time":
            continue

        value = dv.get("value", {})
        if value.get("precision") != 11:
            continue

        cal = value.get("calendarmodel", "")
        if not cal.endswith("/" + GREGORIAN_QID):
            continue

        t = value.get("time", "")
        # Wikibase time is commonly +1986-05-14T00:00:00Z
        if len(t) < 11:
            continue

        ymd = t.lstrip("+")[:10]
        try:
            parsed = date.fromisoformat(ymd)
        except ValueError:
            continue

        if parsed.year == year:
            out.add(parsed.isoformat())

    return sorted(out)


def resolve_batches(session, pages, year, cache_dir, batch_size=50, sleep_s=0.3):
    """
    Resolve English Wikipedia titles directly through wbgetentities.
    We request only claims + English labels, keeping each response small.

    Each batch is cached, so rerunning resumes automatically.
    """
    rows = []
    n_batches = math.ceil(len(pages) / batch_size)

    print(f"[2/3] Reading Wikidata P569 in {n_batches} batches ...")

    for bi in range(n_batches):
        batch = pages[bi * batch_size:(bi + 1) * batch_size]
        cache_path = cache_dir / f"batch_{bi:05d}.json"

        if cache_path.exists():
            entities = json.loads(cache_path.read_text(encoding="utf-8"))
            status = "cached"
        else:
            titles = [p["title"] for p in batch]
            params = {
                "action": "wbgetentities",
                "format": "json",
                "sites": "enwiki",
                "titles": "|".join(titles),
                "props": "claims|labels",
                "languages": "en",
                "languagefallback": "1",
                }

            # POST avoids very long URLs when 50 titles are passed.
            data = request_json(session, WIKIDATA_API, params, method="POST")
            entities = data.get("entities", {})
            cache_path.write_text(
                json.dumps(entities, ensure_ascii=False),
                encoding="utf-8",
            )
            status = "downloaded"
            time.sleep(sleep_s)

        kept = 0
        conflicts = 0

        for qid, entity in entities.items():
            if qid == "-1" or entity.get("missing") is not None:
                continue

            dobs = parse_birth_claims(entity, year)
            if not dobs:
                continue

            label = entity.get("labels", {}).get("en", {}).get("value", qid)
            conflict = len(dobs) > 1
            if conflict:
                conflicts += 1

            for dob in dobs:
                rows.append({
                    "qid": qid,
                    "name": label,
                    "dob": dob,
                    "dob_conflict": conflict,
                })
                kept += 1

        print(
            f"    [{bi+1:04d}/{n_batches:04d}] {status}: "
            f"entities={len(entities):3d}, precise-year DOB rows={kept:3d}, "
            f"conflicts={conflicts}"
        )

    return rows


def build_daily_stats(people, year):
    clean = people.loc[~people["dob_conflict"]].copy()
    clean["dob"] = pd.to_datetime(clean["dob"])
    clean["date_key"] = clean["dob"].dt.date

    grouped = clean.groupby("date_key").agg(
        n_people=("qid", "nunique")
    )

    stats = pd.DataFrame({
        "date": pd.date_range(f"{year}-01-01", f"{year}-12-31", freq="D")
    })
    stats["date_key"] = stats["date"].dt.date

    stats = stats.merge(
        grouped,
        left_on="date_key",
        right_index=True,
        how="left",
    ).drop(columns="date_key")

    stats["n_people"] = stats["n_people"].fillna(0).astype(int)

    mu = stats["n_people"].mean()
    sd = stats["n_people"].std(ddof=1)
    stats["count_z"] = (stats["n_people"] - mu) / sd if sd else 0.0
    stats["count_percentile"] = (
        stats["n_people"].rank(method="average", pct=True) * 100
    )

    return stats


def make_summary(people, stats, year):
    clean = people.loc[~people["dob_conflict"]]
    mu = stats["n_people"].mean()
    med = stats["n_people"].median()
    sd = stats["n_people"].std(ddof=1)

    lines = [
        f"Year: {year}",
        f"Scope: direct pages in enwiki Category:{year} births,",
        "       resolved to Wikidata P569, Gregorian precision=day",
        f"Unique precise-DOB people: {clean['qid'].nunique():,}",
        f"Conflicting precise-DOB QIDs excluded from daily stats: "
        f"{people.loc[people['dob_conflict'], 'qid'].nunique():,}",
        f"Mean people/day: {mu:.3f}",
        f"Median people/day: {med:.1f}",
        f"SD across days: {sd:.3f}",
        "",
        "Top 15 dates:",
    ]

    top = stats.sort_values(
        ["n_people", "date"], ascending=[False, True]
    ).head(15)
    for _, r in top.iterrows():
        lines.append(
            f"  {r['date'].date()}: n={int(r['n_people'])}, "
            f"z={r['count_z']:.3f}, percentile={r['count_percentile']:.1f}"
        )

    lines += ["", "Bottom 15 dates:"]
    bottom = stats.sort_values(
        ["n_people", "date"], ascending=[True, True]
    ).head(15)
    for _, r in bottom.iterrows():
        lines.append(
            f"  {r['date'].date()}: n={int(r['n_people'])}, "
            f"z={r['count_z']:.3f}, percentile={r['count_percentile']:.1f}"
        )

    target = stats.loc[stats["date"] == pd.Timestamp(f"{year}-05-14")]
    if not target.empty:
        r = target.iloc[0]
        lines += [
            "",
            f"{year}-05-14:",
            f"  n_people={int(r['n_people'])}",
            f"  z={r['count_z']:.3f}",
            f"  percentile={r['count_percentile']:.1f}",
        ]

    lines += ["", "All month-14 dates:"]
    for _, r in stats.loc[stats["date"].dt.day == 14].iterrows():
        lines.append(
            f"  {r['date'].date()}: n={int(r['n_people'])}, "
            f"z={r['count_z']:.3f}, percentile={r['count_percentile']:.1f}"
        )

    return "\n".join(lines)


def make_plot(stats, year, path):
    fig, ax = plt.subplots(figsize=(14, 5))
    ax.plot(stats["date"], stats["n_people"], linewidth=0.9)
    ax.axhline(stats["n_people"].mean(), linestyle="--", linewidth=1)

    target_date = pd.Timestamp(f"{year}-05-14")
    row = stats.loc[stats["date"] == target_date]
    if not row.empty:
        n = int(row.iloc[0]["n_people"])
        ax.scatter([target_date], [n], s=45, zorder=5)
        ax.annotate(
            f"May 14: {n}",
            (target_date, n),
            xytext=(8, 10),
            textcoords="offset points",
        )

    ax.set_title(
        f"{year}: enwiki Category:{year} births -> Wikidata precise P569"
    )
    ax.set_xlabel("Birth date")
    ax.set_ylabel("People")
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, default=1986)
    parser.add_argument("--outdir", default=None)
    parser.add_argument("--batch-size", type=int, default=50)
    parser.add_argument("--sleep", type=float, default=0.8)
    parser.add_argument(
        "--proxy",
        default=None,
        help="HTTP proxy, e.g. http://127.0.0.1:10808",
    )
    args = parser.parse_args()

    if not (1 <= args.batch_size <= 50):
        raise SystemExit("--batch-size must be between 1 and 50")

    year = args.year
    outdir = Path(args.outdir or f"birthdate_scan_{year}_v4")
    outdir.mkdir(parents=True, exist_ok=True)
    cache_dir = outdir / "wikidata_batches"
    cache_dir.mkdir(parents=True, exist_ok=True)

    session = new_session(args.proxy)
    connectivity_test(session)

    category_cache = outdir / f"{year}_category_members.json"
    pages = enumerate_birth_category(session, year, category_cache)

    rows = resolve_batches(
        session,
        pages,
        year,
        cache_dir,
        batch_size=args.batch_size,
        sleep_s=args.sleep,
    )

    if not rows:
        raise RuntimeError("No precise DOB rows found.")

    people = pd.DataFrame(rows).drop_duplicates(["qid", "dob"]).copy()
    people = people.sort_values(["dob", "name"])

    people_path = outdir / f"{year}_people.csv"
    people.to_csv(people_path, index=False, encoding="utf-8-sig")

    stats = build_daily_stats(people, year)
    stats_path = outdir / f"{year}_daily_stats.csv"
    stats.to_csv(stats_path, index=False, encoding="utf-8-sig")

    summary = make_summary(people, stats, year)
    summary_path = outdir / f"{year}_summary.txt"
    summary_path.write_text(summary, encoding="utf-8")

    plot_path = outdir / f"{year}_daily_counts.png"
    make_plot(stats, year, plot_path)

    print("[3/3] Finished.")
    print()
    print(summary)
    print()
    print("Saved:")
    print(f"  {people_path}")
    print(f"  {stats_path}")
    print(f"  {summary_path}")
    print(f"  {plot_path}")


if __name__ == "__main__":
    main()
