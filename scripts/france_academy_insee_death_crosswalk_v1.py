#!/usr/bin/env python3
"""Source-only, offline and conservative INSEE death-register crosswalk for French Academy CTHS leads.

Use local official INSEE decadal/annual CSV ZIPs; never collect data via network and
never promote a birthdate or Academy membership into the science cohort.
Python 3.10+, standard library only. Run --fixture-check before real data.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import io
import json
import re
import tempfile
import unicodedata
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

VERSION = "france-academy-insee-public-deaths-source-only-v1"
DEFAULT_CTHS = "data/france_academy_cths_profile_dob_harvest_v1/cths_dob_claims_all_targets_candidate_only_v1.csv"
DEFAULT_ROLES = "data/france_academy_cths_society_role_repair_v1_1/cths_academy_membership_candidates_corrected_v1_1.csv"
OUTPUT_COLUMNS = ["cths_person_id", "cths_name", "cths_birthyear", "cths_deathyear_candidate", "cths_exact_dob_candidate", "cths_membership_class_provisional", "insee_dob_claim", "insee_deathdate_claim", "insee_birthplace", "insee_name", "source_file", "source_zip_sha256", "source_member", "source_record_sha256", "record_match_rule", "dob_comparison", "person_match_status", "french_academy_full_member_accepted", "exact_dob_accepted", "bazi_variables_computed"]


def norm(s):
    s = (s or "").replace("œ", "oe").replace("Œ", "OE").replace("æ", "ae").replace("Æ", "AE")
    s = unicodedata.normalize("NFKD", s).casefold()
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", s).split())


def parse_cths_name(name):
    """Parse explicit NAME GivenName style, quarantine uncertain spelling/particles later."""
    tokens = (name or "").strip().split()
    given_pos = next((i for i, t in enumerate(tokens[1:], 1)
                      if len(t) > 1 and t[0].isupper() and any(c.islower() for c in t[1:])), None)
    if given_pos is None:
        return None
    surname, given = norm(" ".join(tokens[:given_pos])), norm(tokens[given_pos])
    return (surname, given) if surname and given else None


def surname_aliases(s):
    aliases = {s}
    parts = s.split()
    if len(parts) > 1 and parts[0] in {"de", "d", "du", "des", "le", "la"}:
        aliases.add(" ".join(parts[1:]))
    if len(parts) > 1 and parts[-1] in {"de", "d", "du", "des"}:
        aliases.add(" ".join(parts[:-1]))
    return aliases


def official_date(s):
    v = (s or "").strip()
    digits = re.sub(r"[-/ .]", "", v)
    if not re.fullmatch(r"\d{8}", digits) or digits[:4] == "0000":
        return "", digits
    try:
        parsed = dt.date(int(digits[:4]), int(digits[4:6]), int(digits[6:8]))
        return parsed.isoformat(), digits
    except ValueError:
        return "", digits


def sha_file(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_csv(path):
    with Path(path).open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path, rows, fields):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def load_targets(cths, roles):
    full_roles = {r["cths_person_id"]: r for r in load_csv(roles)}
    targets, keyed, invalid_names = {}, defaultdict(list), []
    for r in load_csv(cths):
        pid = r["cths_person_id"]
        role = full_roles.get(pid)
        if role is None:
            raise ValueError("Missing role record for CTHS id " + pid)
        if pid in targets:
            raise ValueError("Repeated CTHS id: " + pid)
        name = role["name_fixed"]
        parsed = parse_cths_name(name)
        if not parsed:
            invalid_names.append({"cths_person_id": pid, "name": name, "reason": "name_structure_unparsed"})
        lifespan = re.search(r"\((\d{4})\s*[-–]\s*(\d{4})\)", role.get("membership_note_fixed", ""))
        birthyear = (r.get("CTHS_roster_year_provisional") or role.get("birth_year_lifespan_candidate") or "").strip()
        deathyear = lifespan.group(2) if lifespan else ""
        dob = (r.get("cths_exact_dob_claim_candidate_only") or "").strip()
        t = {"id": pid, "name": name, "birthyear": birthyear, "deathyear": deathyear,
             "dob": dob, "class": r.get("CTHS_roster_membership_class_provisional", "")}
        targets[pid] = t
        if parsed and re.fullmatch(r"\d{4}", birthyear):
            for sur in surname_aliases(parsed[0]):
                keyed[(sur, parsed[1])].append(t)
    return targets, keyed, invalid_names


def canon_col(s):
    return norm(s).replace(" ", "")


def field(row, keys):
    for k in keys:
        if k in row and str(row[k]).strip():
            return str(row[k]).strip()
    return ""


def parse_csv_records(binary, encoding):
    wrapper = io.TextIOWrapper(binary, encoding=encoding, errors="replace", newline="")
    try:
        first = wrapper.readline()
        if not first:
            return
        # INSEE has also published older fixed-width txt resources; do not confuse them with CSV.
        is_fixed = len(first.rstrip("\r\n")) >= 167 and "*" in first[:80] and first[81:89].isdigit()
        if is_fixed:
            for line in [first]:  # first record, then stream the rest without buffering
                yield {"name": line[:80].strip(), "birth": line[81:89], "death": line[154:162],
                       "birthplace": line[94:154].strip(), "raw": line.rstrip("\r\n")}
            for line in wrapper:
                if len(line) < 167:
                    continue
                yield {"name": line[:80].strip(), "birth": line[81:89], "death": line[154:162],
                       "birthplace": line[94:154].strip(), "raw": line.rstrip("\r\n")}
            return
        # Robust but deliberately limited to formats documented by INSEE.
        delimiter = ";" if first.count(";") >= first.count(",") else ","
        rdr = csv.DictReader(__import__("itertools").chain([first], wrapper), delimiter=delimiter)
        columns = {canon_col(k): k for k in (rdr.fieldnames or []) if k}
        has_name = any(k in columns for k in ("nom", "nomprenom", "nomprenoms", "nomdefamille", "nomnaissance"))
        has_dob = any(k in columns for k in ("datenaissance", "datenaiss", "datedenaissance", "datenais"))
        has_death = any(k in columns for k in ("datedeces", "datedudeces", "datededeces"))
        if not (has_name and has_dob and has_death):
            raise ValueError("Unsupported INSEE CSV header: " + repr(list(columns)))
        for row in rdr:
            data = {canon_col(k): v for k, v in row.items() if k}
            name = field(data, ("nomprenom", "nomprenoms"))
            if not name:
                family = field(data, ("nomdefamille", "nomnaissance", "nom"))
                given = field(data, ("prenoms", "prenom", "prenomusuel"))
                name = family + "*" + given
            yield {"name": name,
                   "birth": field(data, ("datenaissance", "datenaiss", "datedenaissance", "datenais")),
                   "death": field(data, ("datedeces", "datedudeces", "datededeces")),
                   "birthplace": field(data, ("communecommunaissance", "communenaissance", "libellelieunaissance", "lieunaissance", "lieudenaissance", "paysnaissance")),
                   "raw": json.dumps(data, sort_keys=True, ensure_ascii=False)}
    finally:
        wrapper.detach()


def record_identifiers(name):
    if "*" not in name:
        return None
    surname, rest = name.split("*", 1)
    sr = norm(surname)
    given_tokens = norm(rest).split()
    return (sr, given_tokens[0]) if sr and given_tokens else None


def crosswalk_one(path, targets_by_name, outdir, target_source_fingerprint):
    path = Path(path)
    digest = sha_file(path)
    # Cache must include the CTHS roster and role-source hashes, not only the INSEE ZIP.
    cache_key = hashlib.sha256((VERSION + ":" + digest + ":" + target_source_fingerprint).encode()).hexdigest()
    cache = Path(outdir) / "_cache" / (cache_key + ".json")
    if cache.exists():
        saved = json.loads(cache.read_text(encoding="utf-8"))
        if saved.get("version") == VERSION and saved.get("source_sha256") == digest and saved.get("target_source_fingerprint") == target_source_fingerprint:
            print("REUSE: ", path.name, digest[:12])
            return saved
    counts = Counter()
    candidates = []
    with zipfile.ZipFile(path) as z:
        members = [i for i in z.infolist() if not i.is_dir() and i.filename.lower().endswith((".csv", ".txt"))
                   and i.file_size > 100 and "metadonn" not in i.filename.lower()]
        if not members:
            raise RuntimeError("ZIP contains no likely INSEE source csv/txt files: " + str(path))
        for m in members:
            with z.open(m) as raw:
                peek = raw.peek(8192) if hasattr(raw, "peek") else b""
                encoding = "utf-8-sig"
                try:
                    peek.decode("utf-8-sig")
                except UnicodeDecodeError:
                    encoding = "cp1252"
                print("READ: ", path.name, m.filename, "encoding=" + encoding)
                for record in parse_csv_records(raw, encoding):
                    counts["scanned_rows"] += 1
                    ids = record_identifiers(record["name"])
                    if not ids or ids not in targets_by_name:
                        continue
                    exact_dob, digits_birth = official_date(record["birth"])
                    exact_death, digits_death = official_date(record["death"])
                    byr = digits_birth[:4] if len(digits_birth) >= 4 else ""
                    dyr = digits_death[:4] if len(digits_death) >= 4 else ""
                    for t in targets_by_name[ids]:
                        if byr != t["birthyear"] or (t["deathyear"] and dyr != t["deathyear"]):
                            continue
                        counts["matched_candidate_rows"] += 1
                        candidates.append({"cths_person_id": t["id"], "cths_name": t["name"],
                                           "cths_birthyear": t["birthyear"], "cths_deathyear_candidate": t["deathyear"],
                                           "cths_exact_dob_candidate": t["dob"], "cths_membership_class_provisional": t["class"],
                                           "insee_dob_claim": exact_dob, "insee_deathdate_claim": exact_death,
                                           "insee_birthplace": record["birthplace"][:120], "insee_name": record["name"][:160],
                                           "source_file": path.name, "source_zip_sha256": digest,
                                           "source_member": m.filename, "source_record_sha256": hashlib.sha256(record["raw"].encode("utf-8")).hexdigest(),
                                           "record_match_rule": "surname_first_given_birthyear" + ("_deathyear" if t["deathyear"] else "_deathyear_missing")})
    if not counts["scanned_rows"]:
        raise RuntimeError("No INSEE rows scanned from " + str(path))
    data = {"version": VERSION, "source_file": str(path.resolve()), "source_sha256": digest,
            "target_source_fingerprint": target_source_fingerprint,
            "member_names": [m.filename for m in members], "counts": dict(counts), "candidate_rows": candidates}
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return data


def run(cths, roles, paths, outdir):
    target_input_hashes = {"cths_dob_candidates_sha256": sha_file(Path(cths)), "cths_role_roster_sha256": sha_file(Path(roles))}
    target_source_fingerprint = hashlib.sha256(json.dumps(target_input_hashes, sort_keys=True).encode()).hexdigest()
    targets, keys, unparsed = load_targets(cths, roles)
    src = [crosswalk_one(p, keys, outdir, target_source_fingerprint) for p in paths]
    rows = [r.copy() for s in src for r in s["candidate_rows"]]
    groups = defaultdict(list)
    for r in rows:
        groups[r["cths_person_id"]].append(r)
    # Duplicate identical source reissues do not magically add independent evidence.
    result = []
    for r in rows:
        group = groups[r["cths_person_id"]]
        signatures = {(g["insee_dob_claim"], g["insee_deathdate_claim"], norm(g["insee_name"])) for g in group}
        multi = len(signatures) > 1
        r["person_match_status"] = ("MULTIPLE_INSEE_IDENTITIES_MANUAL" if multi else
                                    "UNIQUE_INSEE_LEAD_MANUAL" if r["cths_deathyear_candidate"] else
                                    "NO_CTHS_DEATHYEAR_MANUAL")
        if not r["insee_dob_claim"]:
            r["dob_comparison"] = "INSEE_DATE_NOT_EXACT"
        elif not r["cths_exact_dob_candidate"]:
            r["dob_comparison"] = "CTHS_DOB_MISSING_NEW_INSEE_LEAD"
        elif r["cths_exact_dob_candidate"] == r["insee_dob_claim"]:
            r["dob_comparison"] = "DOB_AGREES_CTHS_CLAIM"
        else:
            r["dob_comparison"] = "DOB_CONFLICTS_WITH_CTHS_CLAIM"
        r.update(french_academy_full_member_accepted="0", exact_dob_accepted="0", bazi_variables_computed="0")
        result.append(r)
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    result.sort(key=lambda r: (int(r["cths_person_id"]), r["source_file"], r["insee_dob_claim"]))
    write_csv(out / "insee_cths_candidate_matches_v1.csv", result, OUTPUT_COLUMNS)
    counts = Counter(r["person_match_status"] for r in result)
    notes = {"version": VERSION, "candidate_only": True, "insee_french_national_register_is_not_complete": True,
             "target_input_hashes": target_input_hashes,
             "cths_target_persons": len(targets), "unparsed_target_name_count": len(unparsed),
             "candidate_persons": len(groups), "candidate_rows": len(result), "status_counts": dict(counts),
             "source_hashes": [{"filename": Path(s["source_file"]).name, "sha256": s["source_sha256"], "counts": s["counts"]} for s in src],
             "accepted_exact_dob": 0, "accepted_full_french_members": 0, "bazi_variables_computed": 0,
             "method": "normalised surname + first given + birthyear + known deathyear; birthplace and aliases require manual review; no fuzzy acceptance"}
    (out / "summary.json").write_text(json.dumps(notes, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_csv(out / "target_name_parse_failures_v1.csv", unparsed, ["cths_person_id", "name", "reason"])
    print("SUMMARY:", json.dumps({k: notes[k] for k in ("cths_target_persons", "candidate_persons", "candidate_rows", "status_counts")}, ensure_ascii=False))
    return notes, result


def fixture_check():
    with tempfile.TemporaryDirectory() as d:
        base = Path(d)
        targets = [
            {"cths_person_id": "112083", "name": "DIEUDONNÉ Jean", "CTHS_roster_year_provisional": "1906", "CTHS_roster_membership_class_provisional": "full_like_only_candidate", "cths_exact_dob_claim_candidate_only": ""},
            {"cths_person_id": "112087", "name": "DUBOST Charles", "CTHS_roster_year_provisional": "1914", "CTHS_roster_membership_class_provisional": "full_like_only_candidate", "cths_exact_dob_claim_candidate_only": ""},
            {"cths_person_id": "101487", "name": "MILLOT Georges", "CTHS_roster_year_provisional": "1917", "CTHS_roster_membership_class_provisional": "full_like_only_candidate", "cths_exact_dob_claim_candidate_only": "1917-05-24"}]
        roles = [
            {"cths_person_id": "112083", "name_fixed": "DIEUDONNÉ Jean", "membership_note_fixed": "(1906-1992) - membre 1968"},
            {"cths_person_id": "112087", "name_fixed": "DUBOST Charles", "membership_note_fixed": "(1914-1991) - membre 1975"},
            {"cths_person_id": "101487", "name_fixed": "MILLOT Georges", "membership_note_fixed": "(1917-1991) - membre 1977"}]
        c, p = base / "cths.csv", base / "roles.csv"
        write_csv(c, targets, list(targets[0]))
        write_csv(p, roles, list(roles[0]))
        z = base / "insee_fixture.zip"
        death_rows = [
            ["DIEUDONNE", "Jean", "19060701", "19921129", "Lille"],
            ["DUBOST", "Charles Louis", "19141001", "19910111", "Saint-Gaultier"],
            ["DUBOST", "Charles", "19050518", "19910115", "Moulins"],
            ["MILLOT", "Georges", "19170524", "19910910", "Troyes"],
            ["MILLOT", "Georges", "19170527", "19910910", "Troyes"]]
        stream = io.StringIO()
        writer = csv.writer(stream, delimiter=";")
        writer.writerow(["nom", "prenoms", "date_naissance", "date_deces", "lieu_naissance"])
        writer.writerows(death_rows)
        with zipfile.ZipFile(z, "w", compression=zipfile.ZIP_DEFLATED) as f:
            f.writestr("deces-fixture.csv", stream.getvalue())
        result, matches = run(c, p, [z], base / "out")
        assert result["cths_target_persons"] == 3 and len(matches) == 4
        di = [r for r in matches if r["cths_person_id"] == "112083"]
        du = [r for r in matches if r["cths_person_id"] == "112087"]
        mi = [r for r in matches if r["cths_person_id"] == "101487"]
        assert len(di) == len(du) == 1 and len(mi) == 2
        assert di[0]["insee_dob_claim"] == "1906-07-01"
        assert du[0]["insee_dob_claim"] == "1914-10-01"
        assert all(r["person_match_status"] == "MULTIPLE_INSEE_IDENTITIES_MANUAL" for r in mi)
        assert all(r["exact_dob_accepted"] == "0" for r in matches)
        assert all(r["bazi_variables_computed"] == "0" for r in matches)
        # Smoke check the alternative older fixed-width record layout described by INSEE.
        fixed = ("DUBOST*CHARLES LOUIS".ljust(80) + "1" + "19141001" + "36000" +
                 "SAINT GAULTIER".ljust(30) + "FRANCE".ljust(30) + "19910111" + "75101" + "001234567")
        assert len(fixed) == 176
        fixed_parsed = list(parse_csv_records(io.BytesIO((fixed + "\n").encode("ascii")), "utf-8-sig"))
        assert len(fixed_parsed) == 1 and fixed_parsed[0]["birth"] == "19141001"
        assert record_identifiers(fixed_parsed[0]["name"]) == ("dubost", "charles")
        assert parse_cths_name("VERNEJOUL Robert de") == ("vernejoul", "robert")
        assert official_date("19010200")[0] == ""
        print("PASS: synthetic INSEE CSV ZIP + fixed-width fixture; namesake, incomplete dates, ambiguity and no-acceptance QA")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cths", default=DEFAULT_CTHS)
    ap.add_argument("--roles", default=DEFAULT_ROLES)
    ap.add_argument("--insee-zip", action="append", default=[], help="Repeat to supply multiple locally downloaded official INSEE ZIPs")
    ap.add_argument("--out", default="local_runs/france_academy_insee_public_deaths_v1")
    ap.add_argument("--fixture-check", action="store_true")
    a = ap.parse_args()
    if a.fixture_check:
        fixture_check()
        return
    if not a.insee_zip:
        ap.error("At least one --insee-zip path is required for a real run (or use --fixture-check)")
    for p in a.insee_zip:
        if not Path(p).is_file():
            ap.error("Missing local official INSEE ZIP: " + p)
    run(a.cths, a.roles, a.insee_zip, a.out)


if __name__ == "__main__":
    main()