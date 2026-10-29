#!/usr/bin/env python3
"""Conservative local parser for the downloaded UC In Memoriam volumes.
No network. Outputs automatic, unverified candidates, never verified DOBs.
"""
import argparse, collections, datetime, hashlib, json, pathlib, re
from urllib.parse import urlsplit


def volume_year(value):
    if not re.fullmatch(r"\d{4}", value) or not 1800 <= int(value) <= 2100:
        raise argparse.ArgumentTypeError("--volume-year must be four digits from 1800 through 2100")
    return int(value)


def validate_source_url(value, year):
    """Check official provenance syntax, without network or content inference."""
    if not isinstance(value, str) or re.search(r"[\s\x00-\x1f\x7f]", value):
        raise ValueError("--source-url contains invalid characters")
    try:
        parsed = urlsplit(value)
        host = parsed.hostname or ""
        if parsed.scheme != "https" or not (host == "berkeley.edu" or host.endswith(".berkeley.edu")):
            raise ValueError("--source-url must be an official Berkeley HTTPS URL")
        if parsed.username is not None or parsed.password is not None:
            raise ValueError("--source-url must not contain credentials")
        if parsed.port not in (None, 443):
            raise ValueError("--source-url must use standard HTTPS")
        # Downloaded files may be locally renamed. Check an explicitly named
        # source-volume year, without requiring the local PDF basename to match.
        named_year = re.search(r"inmemoriam[-_ ]?(\d{4})\.pdf$", parsed.path, re.I)
        if named_year and int(named_year.group(1)) != year:
            raise ValueError("--source-url volume year disagrees with --volume-year")
    except ValueError as error:
        raise ValueError(str(error)) from error
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--text", type=pathlib.Path, required=True, help="UTF-8 pypdf extract with physical page markers")
    parser.add_argument("--pdf", type=pathlib.Path, required=True, help="Downloaded official source PDF")
    parser.add_argument("--output-dir", type=pathlib.Path, required=True, help="Fresh output directory; existing paths are refused")
    parser.add_argument("--source-url", required=True, help="Official Berkeley HTTPS source URL, without credentials")
    parser.add_argument("--volume-year", type=volume_year, required=True, help="Four-digit volume year, 1800 through 2100")
    args = parser.parse_args(argv)
    try:
        source_url = validate_source_url(args.source_url, args.volume_year)
    except ValueError as error:
        parser.error(str(error))
    INPUT, PDF, OUT = args.text, args.pdf, args.output_dir
    if not INPUT.is_file() or not PDF.is_file():
        parser.error("--text and --pdf must be existing files")
    if OUT.exists():
        parser.error("--output-dir must be fresh and must not exist")
    OUT.mkdir(parents=True, exist_ok=False)
    PRIVATE = OUT / "private"
    PRIVATE.mkdir()

    TEXT = INPUT.read_text()
    lines = TEXT.splitlines()
    page = 0
    pages = []
    for line in lines:
        m = re.match(r"=== PDF physical page (\d+) ===", line)
        if m:
            page = int(m.group(1))
        pages.append(page)
    year_header = re.compile(r"^\s*((?:18|19|20)\d{2})\s*[-–—]\s*((?:18|19|20)\d{2})\s*$")
    boundary = re.compile(r"^=== PDF physical page \d+ ===$|^—.*—$")
    headers = []
    for i, line in enumerate(lines):
        match = year_header.fullmatch(line)
        if not match:
            continue
        # Headers wrap onto a second line when campus name overflows.
        j = i - 1
        while j >= 0 and not lines[j].strip():
            j -= 1
        header_lines = [lines[j].strip()]
        start = j
        if ":" not in header_lines[0] and j > 0 and ":" in lines[j - 1]:
            header_lines.insert(0, lines[j - 1].strip())
            start = j - 1
        raw_header = " ".join(header_lines)
        if ":" not in raw_header or "," not in raw_header or boundary.match(raw_header):
            continue
        name, rest = raw_header.split(",", 1)
        department, campus = rest.rsplit(":", 1)
        # Credential is not part of discipline.
        department = re.sub(r"^\s*(?:M\.D\.|Ph\.D\.)\s*,\s*", "", department).strip()
        headers.append(dict(index=i, start=start, name=name.strip(), department=department,
                            campus=campus.strip(), birth_year=int(match[1]), death_year=int(match[2]),
                            header=raw_header, physical_page=pages[start]))

    month_names = "January February March April May June July August September October November December".split()
    month_map = {m.lower(): i + 1 for i, m in enumerate(month_names)}
    mon = "(?:" + "|".join(month_names) + ")"
    date_re = re.compile(r"\b(?:(?P<m1>" + mon + r")\s+(?P<d1>\d{1,2})(?:st|nd|rd|th)?\s*,?\s+(?P<y1>(?:18|19|20)\d{2})|(?P<d2>\d{1,2})(?:st|nd|rd|th)?\s+(?P<m2>" + mon + r")\s*,?\s+(?P<y2>(?:18|19|20)\d{2}))\b", re.I)
    kinship = re.compile(r"\b(?:father|mother|son|daughter|wife|husband|sister|brother|parents|grandfather|grandmother)\b", re.I)
    title_start = re.compile(r"^(?:Professor|Associate Professor|Assistant Professor|Research|Dean|Vice|Chancellor|Director|Chair|Provost|University Librarian|President|Librarian|Specialist|Senior|Astronomer|Distinguished|Instructor|Clinical|Visiting|Acting|The .{0,55} Professor)\b")
    records, private = [], []
    rejected_births = collections.Counter()
    for n, h in enumerate(headers):
        end = headers[n + 1]["start"] if n + 1 < len(headers) else len(lines)
        segment_lines = [(k, l) for k, l in enumerate(lines[h["index"] + 1:end], h["index"] + 1)
                         if l.strip() and not boundary.match(l.strip())]
        titles = []
        while segment_lines and len(titles) < 3 and title_start.match(segment_lines[0][1].strip()):
            titles.append(segment_lines.pop(0)[1].strip())
        prose = " ".join(l.strip() for _, l in segment_lines)
        # Track the source page for each reconstructed text character.
        char_pages = []
        for k, l in segment_lines:
            char_pages.extend([pages[k]] * (len(l.strip()) + 1))
        surname = h["name"].split()[-1].strip(".,")
        accepted = []
        for bm in re.finditer(r"\b(?:was\s+born|born)\b", prose, re.I):
            # Only a named subject in the same sentence/clause qualifies.
            prior = prose[max(0, bm.start() - 250):bm.start()]
            prefix = re.split(r"[.!?]\s+", prior)[-1]
            if not re.search(r"\b" + re.escape(surname) + r"\b", prefix):
                rejected_births["no_named_subject_in_birth_clause"] += 1
                continue
            if kinship.search(prefix):
                rejected_births["kinship_clause"] += 1
                continue
            tail = re.split(r"[.!?]", prose[bm.end():bm.end() + 220], maxsplit=1)[0]
            dm = date_re.search(tail)
            if not dm:
                rejected_births["no_full_date_in_same_birth_clause"] += 1
                continue
            y = int(dm["y1"] or dm["y2"])
            m = month_map[(dm["m1"] or dm["m2"]).lower()]
            d = int(dm["d1"] or dm["d2"])
            try:
                datetime.date(y, m, d)
            except ValueError:
                rejected_births["invalid_date"] += 1
                continue
            if y != h["birth_year"]:
                rejected_births["year_disagrees_with_header"] += 1
                continue
            accepted.append(dict(year=y, month=m, day=d, raw=dm[0],
                                 physical_page=char_pages[bm.start()] if bm.start() < len(char_pages) else None,
                                 rule_id="UC_NAMED_BIRTH_CLAUSE_FULL_DATE_MATCH_HEADER_YEAR_V1",
                                 clause_sha256=hashlib.sha256((prefix + " born " + tail).encode()).hexdigest()))
        dates = {(x["year"], x["month"], x["day"]) for x in accepted}
        candidate = accepted[0] if len(dates) == 1 else None
        rec = dict(candidate_id=f"uc-inmemoriam-{args.volume_year}-{n + 1:03d}", name=h["name"], discipline=h["department"],
                   campus=h["campus"], academic_title="; ".join(titles) or None,
                   birth_year=h["birth_year"], death_year=h["death_year"],
                   birth_month=candidate["month"] if candidate else None,
                   birth_day=candidate["day"] if candidate else None,
                   birth_date_raw=candidate["raw"] if candidate else None,
                   precision="day" if candidate else "year", calendar="not_stated", status="automatic_unverified",
                   source=dict(filename=PDF.name, url=source_url, volume_year=args.volume_year, physical_page=h["physical_page"],
                               birth_clause_physical_page=candidate["physical_page"] if candidate else None,
                               narrative_end_physical_page=pages[end - 1] if end else None),
                   rule_id=candidate["rule_id"] if candidate else "UC_YEAR_SPAN_NAMED_HEADING_V1",
                   review_note=("Named birth clause full date agrees with year header; automatic candidate only."
                                if candidate else ("Multiple distinct full dates matched; day/month left empty." if len(dates) > 1
                                                   else "Only year-span heading retained; no qualifying named full-date birth clause.")))
        records.append(rec)
        private.append(dict(candidate_id=rec["candidate_id"], header_raw=h["header"], prose=prose,
                            full_date_matches=accepted))
    source_hash = hashlib.sha256(PDF.read_bytes()).hexdigest()
    counts = dict(total_header_candidates=len(records), day_candidates=sum(r["precision"] == "day" for r in records),
                  year_candidates=sum(r["precision"] == "year" for r in records),
                  statuses=dict(collections.Counter(r["status"] for r in records)),
                  campuses=dict(collections.Counter(r["campus"] for r in records)),
                  candidates_with_title=sum(bool(r["academic_title"]) for r in records))
    payload = dict(schema_version=1, source_file=PDF.name, volume_year=args.volume_year, source_url=source_url, source_sha256=source_hash,
                   records=records)
    (OUT / "candidates.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    (PRIVATE / "segments.json").write_text(json.dumps(private, ensure_ascii=False, indent=2) + "\n")
    summary = dict(schema_version=1, parser_version=2, volume_year=args.volume_year, source_file=PDF.name, source_url=source_url, source_sha256=source_hash, source_physical_pages=len(set(pages) - {0}),
                   counts=counts, network_requests=0, individual_verifications=0,
                   unparsed_year_span_line_count=sum(bool(year_header.fullmatch(l)) for l in lines) - len(headers),
                   unparsed_year_span_note="Isolated year spans lacking the nearby comma/colon named-heading syntax are skipped without manual rescue.",
                   validation=dict(valid_unique_candidate_ids=len({r['candidate_id'] for r in records}) == len(records),
                                   all_records_have_physical_page_rule_precision_status=all(r['source']['physical_page'] and r['rule_id'] and r['precision'] and r['status'] == 'automatic_unverified' for r in records),
                                   year_only_month_day_null=all(r['birth_month'] is None and r['birth_day'] is None for r in records if r['precision'] == 'year'),
                                   prose_outside_public_candidates=True),
                   rejected_birth_clause_counts=dict(rejected_births),
                   constraints=["Every record is automatic_unverified.",
                                "Only named-heading year spans establish year-level candidates.",
                                "Full-date candidates require named subject in same birth clause, complete date, and agreement with heading year.",
                                "Pronoun-only, kinship, incomplete and year-mismatched clauses are skipped.",
                                "Other people mentioned in prose are not intentionally extracted; no manual rescue performed.",
                                "Entry boundaries, names, disciplines and titles are automatic and may need review."])
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(summary, ensure_ascii=False, indent=2))



if __name__ == "__main__":
    main()
