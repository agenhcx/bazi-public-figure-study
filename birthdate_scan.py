#!/usr/bin/env python3
"""
Download all day-precision birth dates in a given Gregorian year from Wikidata
for people who have an English Wikipedia article, then summarize by day.

Default: 1986.

Outputs:
  <outdir>/<year>_people.csv
  <outdir>/<year>_daily_stats.csv
  <outdir>/<year>_summary.txt
  <outdir>/<year>_daily_counts.png

Install:
  pip install requests pandas matplotlib

Run:
  python birthdate_scan.py --year 1986

Optional:
  python birthdate_scan.py --year 1986 --outdir results_1986
"""

import argparse
import calendar
import json
import math
import time
from datetime import date
from pathlib import Path
from urllib.parse import unquote, urlparse

import matplotlib.pyplot as plt
import pandas as pd
import requests

ENDPOINT = "https://query.wikidata.org/sparql"

# Wikimedia asks automated clients to identify themselves.
# You can replace the contact text with an email or project URL if desired.
USER_AGENT = "BirthdateDistributionStudy/0.1 (personal research; contact: local-user)"

RETRYABLE = {429, 500, 502, 503, 504}


def iso_dt(d: date) -> str:
    return f"{d.isoformat()}T00:00:00Z"


def next_month_start(year: int, month: int) -> date:
    if month == 12:
        return date(year + 1, 1, 1)
    return date(year, month + 1, 1)


def make_query(start: date, end: date) -> str:
    """
    Inclusion rule:
      - human (Q5)
      - best-rank date of birth (P569)
      - date precision = day (11)
      - Gregorian calendar
      - at least one English Wikipedia article
    Also collect Wikidata sitelink count as a rough fame proxy.
    """
    return f"""
PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX p: <http://www.wikidata.org/prop/>
PREFIX psv: <http://www.wikidata.org/prop/statement/value/>
PREFIX wikibase: <http://wikiba.se/ontology#>
PREFIX schema: <http://schema.org/>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

SELECT DISTINCT ?person ?dob ?sitelinks ?article WHERE {{
  ?person wdt:P31 wd:Q5 ;
          wdt:P569 ?dob ;
          p:P569 ?birthStatement ;
          wikibase:sitelinks ?sitelinks .

  ?birthStatement psv:P569 ?birthValue .
  ?birthValue wikibase:timeValue ?dob ;
              wikibase:timePrecision 11 ;
              wikibase:timeCalendarModel wd:Q1985727 .

  FILTER(
    ?dob >= "{iso_dt(start)}"^^xsd:dateTime &&
    ?dob <  "{iso_dt(end)}"^^xsd:dateTime
  )

  ?article schema:about ?person ;
           schema:isPartOf <https://en.wikipedia.org/> .
}}
ORDER BY ?dob ?person
"""


def request_interval(session, start, end, depth=0):
    """
    Query one interval. If WDQS times out repeatedly, split the interval in half.
    """
    query = make_query(start, end)
    last_error = None

    for attempt in range(6):
        try:
            r = session.get(
                ENDPOINT,
                params={"query": query, "format": "json"},
                timeout=75,
            )

            if r.status_code == 200:
                return r.json()["results"]["bindings"]

            if r.status_code in RETRYABLE:
                retry_after = r.headers.get("Retry-After")
                if retry_after and retry_after.isdigit():
                    sleep_s = int(retry_after)
                else:
                    sleep_s = min(60, 2 ** attempt + 2)
                print(f"  HTTP {r.status_code}; retrying in {sleep_s}s")
                time.sleep(sleep_s)
                last_error = RuntimeError(f"HTTP {r.status_code}: {r.text[:300]}")
                continue

            r.raise_for_status()

        except (requests.Timeout, requests.ConnectionError) as e:
            last_error = e
            sleep_s = min(60, 2 ** attempt + 2)
            print(f"  network/timeout error; retrying in {sleep_s}s: {e}")
            time.sleep(sleep_s)

    # Automatic fallback: split an interval if it is more than one day.
    days = (end - start).days
    if days > 1 and depth < 8:
        mid = start.fromordinal(start.toordinal() + days // 2)
        print(f"  splitting {start}..{end} -> {start}..{mid} + {mid}..{end}")
        left = request_interval(session, start, mid, depth + 1)
        time.sleep(1.0)
        right = request_interval(session, mid, end, depth + 1)
        return left + right

    raise RuntimeError(
        f"Query failed for {start}..{end} after retries. Last error: {last_error}"
    )


def article_title(url: str) -> str:
    path = urlparse(url).path
    marker = "/wiki/"
    if marker in path:
        return unquote(path.split(marker, 1)[1]).replace("_", " ")
    return unquote(path.rsplit("/", 1)[-1]).replace("_", " ")


def qid_from_uri(uri: str) -> str:
    return uri.rsplit("/", 1)[-1]


def rows_from_bindings(bindings):
    rows = []
    for b in bindings:
        dob = b["dob"]["value"][:10]
        article = b["article"]["value"]
        rows.append({
            "qid": qid_from_uri(b["person"]["value"]),
            "name": article_title(article),
            "dob": dob,
            "sitelinks": int(b["sitelinks"]["value"]),
            "enwiki_url": article,
        })
    return rows


def build_daily_stats(people: pd.DataFrame, year: int) -> pd.DataFrame:
    people = people.copy()
    people["dob"] = pd.to_datetime(people["dob"])
    people["date"] = people["dob"].dt.date

    grouped = people.groupby("date").agg(
        n_people=("qid", "nunique"),
        sum_sitelinks=("sitelinks", "sum"),
        mean_sitelinks=("sitelinks", "mean"),
        median_sitelinks=("sitelinks", "median"),
        max_sitelinks=("sitelinks", "max"),
    )

    full = pd.DataFrame({
        "date": pd.date_range(f"{year}-01-01", f"{year}-12-31", freq="D")
    })
    full["date_key"] = full["date"].dt.date

    stats = full.merge(
        grouped,
        left_on="date_key",
        right_index=True,
        how="left",
    ).drop(columns="date_key")

    stats["n_people"] = stats["n_people"].fillna(0).astype(int)
    stats["sum_sitelinks"] = stats["sum_sitelinks"].fillna(0).astype(int)

    # Descriptive z-score using the observed 365-day distribution.
    mu = stats["n_people"].mean()
    sigma = stats["n_people"].std(ddof=1)
    stats["count_z"] = (stats["n_people"] - mu) / sigma

    # Empirical percentile: fraction of days with count <= this day's count.
    vals = stats["n_people"]
    stats["count_percentile"] = vals.rank(method="average", pct=True) * 100

    return stats


def summary_text(stats: pd.DataFrame, people: pd.DataFrame, year: int) -> str:
    s = []
    mu = stats["n_people"].mean()
    med = stats["n_people"].median()
    sd = stats["n_people"].std(ddof=1)

    s.append(f"Year: {year}")
    s.append("Scope: humans with day-precision Gregorian DOB + English Wikipedia article")
    s.append(f"Unique people: {people['qid'].nunique():,}")
    s.append(f"Mean people/day: {mu:.3f}")
    s.append(f"Median people/day: {med:.1f}")
    s.append(f"SD across days: {sd:.3f}")
    s.append("")

    top = stats.nlargest(10, ["n_people", "sum_sitelinks"])
    bottom = stats.nsmallest(10, ["n_people", "sum_sitelinks"])

    s.append("Top 10 dates by number of people:")
    for _, r in top.iterrows():
        s.append(
            f"  {r['date'].date()}: n={int(r['n_people'])}, "
            f"z={r['count_z']:.3f}, percentile={r['count_percentile']:.1f}, "
            f"sum_sitelinks={int(r['sum_sitelinks'])}"
        )
    s.append("")

    s.append("Bottom 10 dates by number of people:")
    for _, r in bottom.iterrows():
        s.append(
            f"  {r['date'].date()}: n={int(r['n_people'])}, "
            f"z={r['count_z']:.3f}, percentile={r['count_percentile']:.1f}, "
            f"sum_sitelinks={int(r['sum_sitelinks'])}"
        )
    s.append("")

    target = stats[stats["date"] == pd.Timestamp(f"{year}-05-14")]
    if not target.empty:
        r = target.iloc[0]
        s.append(f"{year}-05-14:")
        s.append(f"  n_people={int(r['n_people'])}")
        s.append(f"  count_z={r['count_z']:.3f}")
        s.append(f"  count_percentile={r['count_percentile']:.1f}")
        s.append(f"  sum_sitelinks={int(r['sum_sitelinks'])}")
        s.append(f"  mean_sitelinks={r['mean_sitelinks']:.3f}")
        s.append(f"  median_sitelinks={r['median_sitelinks']:.3f}")
        s.append(f"  max_sitelinks={int(r['max_sitelinks'])}")

    s.append("")
    s.append("All month-14 dates:")
    d14 = stats[stats["date"].dt.day == 14]
    for _, r in d14.iterrows():
        s.append(
            f"  {r['date'].date()}: n={int(r['n_people'])}, "
            f"z={r['count_z']:.3f}, percentile={r['count_percentile']:.1f}"
        )

    return "\n".join(s)


def make_plot(stats: pd.DataFrame, year: int, outpath: Path):
    fig, ax = plt.subplots(figsize=(14, 5))
    ax.plot(stats["date"], stats["n_people"], linewidth=0.9)
    ax.axhline(stats["n_people"].mean(), linestyle="--", linewidth=1.0)

    target_date = pd.Timestamp(f"{year}-05-14")
    row = stats.loc[stats["date"] == target_date]
    if not row.empty:
        ax.scatter(
            [target_date],
            [int(row.iloc[0]["n_people"])],
            s=45,
            zorder=5,
        )
        ax.annotate(
            f"May 14: {int(row.iloc[0]['n_people'])}",
            (target_date, int(row.iloc[0]["n_people"])),
            xytext=(8, 10),
            textcoords="offset points",
        )

    ax.set_title(
        f"{year}: English-Wikipedia people by exact birth date\n"
        "Wikidata day-precision DOB; dashed line = annual daily mean"
    )
    ax.set_xlabel("Birth date")
    ax.set_ylabel("Number of people")
    fig.tight_layout()
    fig.savefig(outpath, dpi=180)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, default=1986)
    parser.add_argument("--outdir", default=None)
    parser.add_argument(
        "--sleep",
        type=float,
        default=1.0,
        help="Pause between successful monthly queries (seconds).",
    )
    args = parser.parse_args()

    year = args.year
    outdir = Path(args.outdir or f"birthdate_scan_{year}")
    outdir.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    session.headers.update({
        "User-Agent": USER_AGENT,
        "Accept": "application/sparql-results+json",
    })

    all_rows = []
    for month in range(1, 13):
        start = date(year, month, 1)
        end = next_month_start(year, month)
        print(f"[{month:02d}/12] Querying {start} to {end} ...")
        bindings = request_interval(session, start, end)
        rows = rows_from_bindings(bindings)
        print(f"  got {len(rows):,} rows")
        all_rows.extend(rows)
        time.sleep(args.sleep)

    people = pd.DataFrame(all_rows)
    if people.empty:
        raise RuntimeError("No data returned.")

    # Drop exact duplicate rows.
    people = people.drop_duplicates(subset=["qid", "dob", "enwiki_url"]).copy()

    # Flag entities that have multiple best-rank day-level DOB values.
    dob_n = people.groupby("qid")["dob"].nunique()
    conflict_qids = set(dob_n[dob_n > 1].index)
    people["dob_conflict"] = people["qid"].isin(conflict_qids)

    if conflict_qids:
        print(
            f"WARNING: {len(conflict_qids)} QIDs have multiple precise best-rank DOBs. "
            "They are kept in people.csv but excluded from daily statistics."
        )

    people_path = outdir / f"{year}_people.csv"
    people.sort_values(["dob", "name"]).to_csv(
        people_path, index=False, encoding="utf-8-sig"
    )

    clean = people.loc[~people["dob_conflict"]].copy()
    stats = build_daily_stats(clean, year)

    stats_path = outdir / f"{year}_daily_stats.csv"
    stats.to_csv(stats_path, index=False, encoding="utf-8-sig")

    summary = summary_text(stats, clean, year)
    summary_path = outdir / f"{year}_summary.txt"
    summary_path.write_text(summary, encoding="utf-8")

    plot_path = outdir / f"{year}_daily_counts.png"
    make_plot(stats, year, plot_path)

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
