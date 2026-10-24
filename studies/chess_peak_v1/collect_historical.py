"""Audited extraction of official-list transcriptions through April 2003.

IDs in early lists were reused. A number alone never identifies a historical
person: canonical archive groups must also agree with name or exact DOB.
"""
from __future__ import annotations

import argparse
import csv
from collections import defaultdict
import hashlib
import io
import json
from pathlib import Path
import re
import unicodedata
import zipfile

ARCHIVES = {
    "pre2002": {"url": "https://www.olimpbase.org/Elo/data/elo1967-2001.zip",
        "sha256": "a93c69d1e3218769935aba92db50877a2e9c26cc62d377c1b663f37a786fe89b"},
    "2002_2009": {"url": "https://www.olimpbase.org/Elo/data/elo2002-2009.zip",
        "sha256": "41131d4b573f033ccf8f2df927f820046cfbee305051b83145c2955220d89003"},
}
FIRST, LAST = "1971-07", "2003-04"

# Explicit spelling/short-surname correspondence, never an Elo-based match.
NAME_ALIASES = {
    "Quesada Perez, Yuniesky": ["Quezada, Yuniesky"],
    "Delgado Ramirez, Neuris": ["Delgado, Neuris"],
    "Vazquez Igarza, Renier": ["Vazquez, Renier"],
    "Gonzalez Vidal, Yuri": ["Gonzalez, Yuri"],
    "Hernandez Carmenate, Holden": ["Hernandez, Holden"],
    "Gonzalez Zamora, Juan Carlos": ["Gonzalez, Zamora Juan Carlo"],
    "Hernandez Guerrero, Gilberto": ["Hernandez, Gilberto"],
    "Almeida Quintana, Omar": ["Almeida, Omar"],
    "Perez Mitjans, Orelvis": ["Perez, Orelvis"],
    "Abreu Delgado, Aryam": ["Abreu, Aryam"],
    "Collins, Sam E": ["Collins, Sam"],
    "Martinez Duany, Lelys Stanley": ["Martinez, Lelys"],
    "Rohl Montes, Juan Armando": ["Rohl, Juan"],
    "Ibrayev, Nurlan": ["Ibraev, Nurlan"],
    "Kulashko, Alexei": ["Kulashko, Aleksei"],
}


def normalized_name(value):
    text = unicodedata.normalize("NFKD", str(value)).casefold()
    return "".join(ch for ch in text if ch.isalnum() and not unicodedata.combining(ch))


ALIASES = {normalized_name(k): {normalized_name(k), *(normalized_name(v) for v in values)}
    for k, values in NAME_ALIASES.items()}


def canonical_id(value):
    value = str(value).strip()
    if not value or not value.isdigit() or int(value) <= 0:
        raise ValueError("Invalid FIDE identifier")
    return str(int(value))


def period(value):
    value = str(value).strip()
    if not re.fullmatch(r"\d{6}", value) or not 1 <= int(value[4:]) <= 12:
        raise ValueError("Invalid archive period")
    return value[:4] + "-" + value[4:]


def date_value(value):
    value = str(value).strip().replace(".", "-")
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) and not value.endswith("-00") and value[5:7] != "00":
        return value
    return None


def read_archive(path, key, *, verify_hash=True):
    """Yield normalized source rows, retaining their exact archival location."""
    path = Path(path)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if verify_hash and digest != ARCHIVES[key]["sha256"]:
        raise ValueError(f"Historical archive fingerprint differs: {key}")
    with zipfile.ZipFile(path) as archive:
        names = ["all.csv"] if key == "pre2002" else ["2002.txt", "2003.txt"]
        for member in names:
            if member not in archive.namelist():
                raise ValueError(f"Historical member absent: {member}")
            with archive.open(member) as binary:
                stream = io.TextIOWrapper(binary, encoding="latin-1", newline="")
                for line, fields in enumerate(csv.reader(stream, delimiter=";"), 1):
                    if not fields or not any(fields):
                        continue
                    if key == "pre2002":
                        if len(fields) < 9:
                            raise ValueError(f"Truncated historical row {member}:{line}")
                        group, name, raw_month, fid, dob, rating = fields[1], fields[2], fields[3], fields[4], fields[5], fields[8]
                    else:
                        if len(fields) < 7:
                            raise ValueError(f"Truncated historical row {member}:{line}")
                        name, raw_month, fid, dob, rating = fields[0], fields[1], fields[2], fields[3], fields[6]
                        group = name
                    # Pre-official compilations include unknown-month tokens
                    # such as 196900; they are outside the declared endpoint.
                    if key == "pre2002" and raw_month.strip() < "197107":
                        continue
                    month = period(raw_month)
                    if key == "2002_2009" and month > LAST:
                        continue
                    if not rating.strip():
                        continue
                    elo = int(rating)
                    if elo <= 0:
                        continue
                    yield {"period": month, "rating": elo, "canonical_source_name": group,
                        "source_name": name, "historical_fide_id": canonical_id(fid) if fid.strip() else None,
                        "source_dob": date_value(dob), "source_dob_raw": dob,
                        "source_archive": path.name, "source_archive_key": key,
                        "source_archive_sha256": digest, "source_url": ARCHIVES[key]["url"],
                        "source_member": member, "source_line": line,
                        "source_row": fields}


def match_group(person, group, *, modern_name_bridges=()):
    """Return explicit evidence for a candidate canonical group, or no match."""
    fid = canonical_id(person["canonical_id"])
    name = normalized_name(person["name"])
    allowed = ALIASES.get(name, {name})
    group_names = group["names"]
    exact_name = bool(allowed & group_names)
    exact_dob = person["exact_dob_frozen"] in group["dobs"]
    direct_id = fid in group["ids"]
    bridge = bool(set(modern_name_bridges) & group_names)
    if direct_id and (exact_name or exact_dob):
        return "historical_group_id_and_name" if exact_name else "historical_group_id_and_exact_dob"
    if bridge and exact_name:
        return "modern_id_name_to_canonical_historical_group"
    return None


def extract_history(archives, people, *, verify_hash=True):
    """Extract selected people without changing frozen identities or DOBs."""
    people = list(people)
    ids = [canonical_id(p["canonical_id"]) for p in people]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate frozen person identifiers")
    if set(archives) != set(ARCHIVES):
        raise ValueError("Both historical archives are required")
    groups, id_groups, name_groups = {}, defaultdict(set), defaultdict(set)
    all_periods, source_rows_n = set(), defaultdict(int)
    # The canonical name column is the archive's own historical-person grouping.
    for row in read_archive(archives["pre2002"], "pre2002", verify_hash=verify_hash):
        source_rows_n["pre2002"] += 1
        key = row["canonical_source_name"]
        group = groups.setdefault(key, {"ids": set(), "names": set(), "dobs": set(), "periods": set(), "id_periods": defaultdict(set)})
        group["periods"].add(row["period"])
        group["names"].update(normalized_name(row[k]) for k in ("canonical_source_name", "source_name"))
        if row["historical_fide_id"]:
            group["ids"].add(row["historical_fide_id"])
            group["id_periods"][row["historical_fide_id"]].add(row["period"])
        if row["source_dob"]:
            group["dobs"].add(row["source_dob"])
        if FIRST <= row["period"] <= LAST:
            all_periods.add(row["period"])
    for key, group in groups.items():
        for fid in group["ids"]:
            id_groups[fid].add(key)
        for name in group["names"]:
            name_groups[name].add(key)
    modern = defaultdict(list)
    for row in read_archive(archives["2002_2009"], "2002_2009", verify_hash=verify_hash):
        source_rows_n["2002_2009"] += 1
        if FIRST <= row["period"] <= LAST:
            all_periods.add(row["period"])
        if row["historical_fide_id"] in ids:
            modern[row["historical_fide_id"]].append(row)
    assignments = {}
    for person in people:
        fid, frozen_dob = canonical_id(person["canonical_id"]), person["exact_dob_frozen"]
        name = normalized_name(person["name"])
        allowed = ALIASES.get(name, {name})
        modern_ok = [r for r in modern[fid] if normalized_name(r["source_name"]) in allowed or r["source_dob"] == frozen_dob]
        bridges = {normalized_name(r["source_name"]) for r in modern_ok}
        candidates = set(id_groups.get(fid, ()))
        for key_name in allowed | bridges:
            candidates.update(name_groups.get(key_name, ()))
        accepted = [(key, match_group(person, groups[key], modern_name_bridges=bridges)) for key in sorted(candidates)]
        assignments[fid] = [(key, method) for key, method in accepted if method]
    selected_groups = {key for values in assignments.values() for key, _ in values}
    historical_selected = defaultdict(list)
    for row in read_archive(archives["pre2002"], "pre2002", verify_hash=verify_hash):
        if row["canonical_source_name"] in selected_groups and FIRST <= row["period"] <= LAST:
            historical_selected[row["canonical_source_name"]].append(row)
    records, fatal, matches, rejected, discrepancies, no_rows = [], [], [], [], [], []
    used_groups = {}
    for person in people:
        fid, frozen_dob = canonical_id(person["canonical_id"]), person["exact_dob_frozen"]
        name = normalized_name(person["name"])
        allowed = ALIASES.get(name, {name})
        modern_ok = [r for r in modern[fid] if normalized_name(r["source_name"]) in allowed or r["source_dob"] == frozen_dob]
        modern_bad = [r for r in modern[fid] if r not in modern_ok]
        # Bad rows stay explicitly rejected rather than being joined by number.
        for row in modern_bad:
            rejected.append({"canonical_id": fid, "source_member": row["source_member"],
                "source_line": row["source_line"], "source_name": row["source_name"],
                "reason": "modern_id_without_name_or_exact_dob_agreement"})
        accepted = assignments[fid]
        if len(accepted) > 1:
            # The archive splits spelling changes into distinct groups. Shared
            # exact DOB and non-overlapping periods can resolve that split;
            # simultaneous competing groups remain ambiguous.
            disjoint = all(not (groups[a]["periods"] & groups[b]["periods"])
                for i, (a, _) in enumerate(accepted) for b, _ in accepted[i+1:])
            if not disjoint or not all(frozen_dob in groups[key]["dobs"] for key, _ in accepted):
                fatal.append({"canonical_id": fid, "reason": "ambiguous_historical_canonical_groups", "groups": [x[0] for x in accepted]})
                continue
        selected = list(modern_ok)
        method = "modern_id_and_name_or_exact_dob"
        for key, method in accepted:
            if key in used_groups and used_groups[key] != fid:
                fatal.append({"canonical_id": fid, "reason": "historical_group_assigned_twice", "group": key})
                continue
            used_groups[key] = fid
            active = groups[key]["id_periods"].get(fid, set())
            overlapping_other_ids = {other for other, months in groups[key]["id_periods"].items()
                if other != fid and active and months & active}
            for row in historical_selected[key]:
                if row["historical_fide_id"] in overlapping_other_ids:
                    rejected.append({"canonical_id": fid, "reason": "other_id_overlaps_current_id_in_canonical_group",
                        "source_group": key, "excluded_source_row": row})
                else:
                    selected.append({**row, "match_method": method})
            matches.append({"canonical_id": fid, "frozen_name": person["name"], "canonical_source_name": key,
                "match_method": method, "historical_ids": sorted(groups[key]["ids"]),
                "source_dobs": sorted(groups[key]["dobs"]), "frozen_dob_unchanged": frozen_dob,
                "explicit_name_alias_used": name in ALIASES,
                "spelling_split_groups_merged": len(accepted)>1,
                "excluded_overlapping_other_ids": sorted(overlapping_other_ids)})
        for key in sorted(set(id_groups.get(fid, ())) - {x[0] for x in accepted}):
            rejected.append({"canonical_id": fid, "source_group": key,
                "reason": "historical_id_reused_without_identity_agreement"})
        seen_months = {}
        for row in selected:
            if row["period"] < FIRST or row["period"] > LAST:
                continue
            seen_months[row["period"]] = row["rating"]
            flags = []
            source_year = re.match(r"^(\d{4})", row["source_dob_raw"])
            source_year = source_year.group(1) if source_year else None
            if ((row["source_dob"] and row["source_dob"] != frozen_dob)
                    or (source_year is not None and source_year != frozen_dob[:4])):
                flags.append("source_dob_differs_from_frozen_dob")
                discrepancies.append({"canonical_id": fid, "frozen_name": person["name"],
                    "frozen_dob": frozen_dob, "source_dob": row["source_dob"],
                    "source_dob_raw": row["source_dob_raw"], "source_dob_year": source_year,
                    "source_member": row["source_member"], "source_line": row["source_line"]})
            if row["period"] < frozen_dob[:7]:
                fatal.append({"canonical_id": fid, "reason": "rating_before_frozen_birth_month", "period": row["period"]})
            records.append({**row, "canonical_id": fid, "source": "olimpbase_transcription",
                "match_method": row.get("match_method", "modern_id_and_name_or_exact_dob"),
                "identity_flags": flags})
        if not seen_months:
            no_rows.append({"canonical_id": fid, "name": person["name"], "exact_dob_frozen": frozen_dob})
    coverage = {"first_official_period": FIRST, "last_selected_period": LAST,
        "published_periods": sorted(all_periods), "period_count": len(all_periods)}
    if verify_hash and len(all_periods) != 64:
        fatal.append({"reason": "unexpected_historical_period_inventory", "n": len(all_periods)})
    by_month = defaultdict(list)
    for row in records:
        by_month[row["canonical_id"], row["period"]].append(row)
    conflicts = [{"canonical_id": cid, "period": month,
        "candidate_ratings": sorted({row["rating"] for row in rows}),
        "source_locations": [{key: row[key] for key in ("source_archive", "source_member", "source_line")} for row in rows]}
        for (cid, month), rows in sorted(by_month.items()) if len({row["rating"] for row in rows}) > 1]
    return {"status": "complete" if not fatal else "requires_identity_resolution",
        "protocol_id": "chess-peak-historical-transcription-v1", "records": sorted(records, key=lambda r: (r["canonical_id"], r["period"], r["source_member"], r["source_line"])),
        "archives": {k: {**ARCHIVES[k], "file": Path(archives[k]).name,
            "actual_sha256": hashlib.sha256(Path(archives[k]).read_bytes()).hexdigest()} for k in ARCHIVES},
        "coverage": coverage, "audit": {"fatal_issues": fatal,
            "unresolved_period_conflicts": conflicts,
            "period_conflict_policy": "All source candidates retained. Dataset assembly must establish that the peak is uniquely identifiable from other uncontested periods, or stop; never choose the higher or lower source row.",
            "selected_people_n": len(people), "people_with_history_n": len({r["canonical_id"] for r in records}),
            "records_n": len(records), "source_rows_scanned": dict(source_rows_n),
            "canonical_group_matches": matches, "rejected_identity_candidates": rejected,
            "identity_discrepancies": discrepancies, "people_without_selected_history": no_rows,
            "source_dob_policy": "Frozen DOB never changes; stable ID plus exact normalized name may anchor archive rows despite source-DOB discrepancies; no rating-dependent identity resolution.",
            "unofficial_pre1971_lists_excluded": True, "model_fitting_performed": False}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pre2002", type=Path, required=True)
    parser.add_argument("--2002-2009", dest="later", type=Path, required=True)
    parser.add_argument("--persons", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with args.persons.open(encoding="utf-8-sig", newline="") as stream:
        people = list(csv.DictReader(stream))
    result = extract_history({"pre2002": args.pre2002, "2002_2009": args.later}, people)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"status": result["status"], "people": result["audit"]["people_with_history_n"], "records": len(result["records"]), "fatal_issues": result["audit"]["fatal_issues"]}))


if __name__ == "__main__":
    main()
