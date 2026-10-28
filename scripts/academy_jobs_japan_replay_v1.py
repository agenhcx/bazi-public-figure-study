#!/usr/bin/env python3
"""Replay four existing Japan adjudicators using exact archived local inputs.

The default mode is offline. An explicit --rehydrate-approved-sources flag
allows one GET for each of four pinned source URLs into temporary storage.
Missing or altered source bytes fail the job; documentary closeout facts are
never substituted for a successful evidence replay.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import html
import importlib.util
import io
import json
import re
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import unicodedata
from pathlib import Path
from types import ModuleType
from typing import Any

import academy_jobs_japan_integration_v1 as shared

VERSION = "academy-jobs-japan-replay-v1"
QUEUE = "data/japan_academy_remaining40_direct_evidence_queue_v1/remaining40_direct_evidence_queue_v1.csv"
QUEUE_SHA256 = "bd81f0b4d994833fa5d0d5b04e2dcd036f0670b87aecdcfa08ce9df159acda11"
SOURCE_URLS = {
    "hiratsuka": "https://www.jstage.jst.go.jp/article/jjom/41/4/41_H11-175/_pdf/-char/ja",
    "yoshikawa": "https://www.tobunken.go.jp/materials/nenshi/ny/1982",
    "nanbara": "https://www.lib.u-tokyo.ac.jp/sites/default/files/2025-09/2025Nanbara_history.pdf",
    "doi": "https://www.tobunken.go.jp/materials/nenshi/5759.html",
}
RAW_EXTRA = {
    "hiratsuka": "raw_sources/hiratsuka_naohide_jjom_41_4_obituary.pdf",
    "yoshikawa": "raw_sources/tobunken_1982_nenshi.html",
}
APPROVED_HOSTS = frozenset(urllib.parse.urlsplit(url).hostname for url in SOURCE_URLS.values())
MAX_BYTES = 8 * 1024 * 1024
PACKET_SHA256 = "7d2bd0166f963f446041e92532279a5224ce829c93c91514ca8884bebbd935ff"
INVENTORY_SHA256 = {
    "hiratsuka": "c99e9461438ed91c223999ea43c506efab96c889cd687d18c3ddcfb871b14f0f",
    "yoshikawa": "1e7ccac1fdbc2e11ed8f04a59db90b6eb618a775ae89d68832e691ea29263418",
    "nanbara": "2fc9f8d70ca45e1d1daa8dd3f3dbaac5b1ba6d1d8444815add18dea5a6dc6354",
    "doi": "10731efeff14fbf35846bd3de3c628c4159650cdd315945a075cbfc42de39668",
}
ADJUDICATION_SHA256 = {
    "hiratsuka": "b89d070509dbdcab33e29837c188003ca98efdadb29b40e6ea98eb85208cd058",
    "yoshikawa": "a08d1d982ddd7a84b1f41ec4bf3916436212225248d3b01e0324716692a780b3",
    "nanbara": "4d30d55c2d088348f4748d5883daf90a60f2632a4a4db025e4245a80ad706f94",
    "doi": "2e70e043ae80ed5979bffe5f4c4d613b22c2ff4ef49b8ebad9f49dfb896ce7c3",
}


class SourceBlockedError(RuntimeError):
    def __init__(self, case: str, reason: str, attempts: list[dict[str, Any]]):
        super().__init__(f"blocked_source={case}: {reason}")
        self.blocked_source = case
        self.attempts = attempts


class NoRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # A redirect would be an additional GET. The approved budget is one
        # literal URL request per source, so fail closed rather than follow it.
        return None


def visible_text(body: bytes, case: str) -> bytes:
    text = body.decode("utf-8", errors="replace")
    text = re.sub(r"(?is)<script\b.*?</script>", " ", text)
    text = re.sub(r"(?is)<style\b.*?</style>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    if case == "yoshikawa":
        for old, new in (("&nbsp;", " "), ("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"), ("&#8211;", "–"), ("&#8212;", "—")):
            text = text.replace(old, new)
    else:
        text = html.unescape(text)
    # The archived visible-text snapshots were written on Windows. Preserve
    # their exact CRLF bytes so the original adjudicator SHA pins still apply.
    return (" ".join(text.split()) + "\r\n").encode("utf-8")


def raw_original(module: ModuleType, case: dict[str, str]) -> Path:
    if case["case"] in RAW_EXTRA:
        return module.DEFAULT_INVENTORY.parent / RAW_EXTRA[case["case"]]
    return module.DEFAULT_SOURCE if hasattr(module, "DEFAULT_SOURCE") else module.DEFAULT_HTML


def rehydrate_sources(repo: Path, raw_root: Path) -> list[dict[str, Any]]:
    attempts: list[dict[str, Any]] = []
    opener = urllib.request.build_opener(NoRedirects())
    for index, case in enumerate(shared.CASES):
        if index:
            time.sleep(1)
        name = case["case"]
        url = SOURCE_URLS[name]
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme != "https" or parsed.hostname not in APPROVED_HOSTS or parsed.username or parsed.password or parsed.port not in (None, 443):
            raise SourceBlockedError(name, "URL is outside the literal approved HTTPS manifest", attempts)
        module = load_adjudicator(repo, case)
        request = urllib.request.Request(url, headers={"User-Agent": "bazi-public-figure-study/1.0 (bounded archived evidence replay)"})
        attempt: dict[str, Any] = {"case": name, "url": url, "GET_attempts": 1, "timeout_seconds": 20}
        attempts.append(attempt)
        try:
            with opener.open(request, timeout=20) as response:
                attempt["http_status"] = response.status
                body = response.read(MAX_BYTES + 1)
            if len(body) > MAX_BYTES:
                raise ValueError(f"Source exceeds {MAX_BYTES} byte limit")
            expected = module.EXPECTED_HTML_SHA256 if hasattr(module, "EXPECTED_HTML_SHA256") else module.EXPECTED_SOURCE_SHA256
            if hashlib.sha256(body).hexdigest() != expected:
                raise ValueError("Source bytes changed from the frozen SHA256; no acceptance permitted")
            raw = raw_root / raw_original(module, case)
            raw.parent.mkdir(parents=True, exist_ok=True)
            raw.write_bytes(body)
            if hasattr(module, "DEFAULT_TEXT"):
                text = visible_text(body, name)
                if hashlib.sha256(text).hexdigest() != module.EXPECTED_TEXT_SHA256:
                    raise ValueError("Derived visible-text bytes differ from the original frozen snapshot")
                text_path = raw_root / module.DEFAULT_TEXT
                text_path.parent.mkdir(parents=True, exist_ok=True)
                text_path.write_bytes(text)
            attempt["status"] = "exact_archived_sha_verified"
        except urllib.error.HTTPError as error:
            attempt["http_status"] = error.code
            attempt["status"] = "blocked"
            reason = "HTTP 429: host requests stopped; no retry" if error.code == 429 else f"HTTP {error.code}; no redirect, fallback, or retry"
            raise SourceBlockedError(name, reason, attempts) from error
        except Exception as error:
            attempt["status"] = "blocked"
            raise SourceBlockedError(name, f"{type(error).__name__}: {error}", attempts) from error
    return attempts


def locate(input_root: Path, original: Path | str) -> Path:
    original = Path(original)
    # Both layouts preserve the original filenames and file bytes. The short
    # layout is convenient for Library ZIPs that contain only a dataset folder.
    candidates = [input_root / original]
    if original.parts and original.parts[0] == "data":
        candidates.append(input_root.joinpath(*original.parts[1:]))
    found = [path.resolve() for path in candidates if path.is_file()]
    if len(set(found)) != 1:
        raise FileNotFoundError(f"Expected exactly one local archived input for {original}; checked {candidates}")
    path = found[0]
    if not path.is_relative_to(input_root.resolve()):
        raise ValueError(f"Input symlink escapes the archive root: {original}")
    return path


def load_adjudicator(repo: Path, case: dict[str, str]) -> ModuleType:
    path = repo / "scripts" / case["script"]
    spec = importlib.util.spec_from_file_location("japan_replay_" + case["case"], path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load local adjudicator {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if module.TARGET_KEY != case["member_key"] or module.TARGET_NAME != case["name_jp"]:
        raise ValueError(f"Adjudicator identity mismatch: {case['case']}")
    return module


def expect_hash(path: Path, expected: str, hashes: dict[str, str]) -> None:
    actual = shared.sha256(path)
    if actual != expected:
        raise ValueError(f"Archived input SHA256 mismatch: {path}")
    hashes[str(path)] = actual


def prepare_case(repo: Path, input_root: Path, raw_root: Path, case: dict[str, str], hashes: dict[str, str]) -> tuple[ModuleType, dict[str, Path]]:
    module = load_adjudicator(repo, case)
    hashes[str(repo / "scripts" / case["script"])] = shared.sha256(repo / "scripts" / case["script"])
    files = {"inventory": locate(input_root, module.DEFAULT_INVENTORY)}
    rows = shared.read_csv(files["inventory"])
    if len(rows) != 1:
        raise ValueError(f"Expected one original inventory row: {case['case']}")
    row = rows[0]
    for field, expected in {"member_key": case["member_key"], "name_jp": case["name_jp"], "source_tier": "B", "source_url": SOURCE_URLS[case["case"]]}.items():
        if row.get(field) != expected:
            raise ValueError(f"Original inventory {field} mismatch: {case['case']}")
    if row.get("source_organization") != module.SOURCE_ORGANIZATION:
        raise ValueError(f"Original inventory institution mismatch: {case['case']}")
    expect_hash(files["inventory"], INVENTORY_SHA256[case["case"]], hashes)
    for argument, constant, expected_constant in (
        ("text", "DEFAULT_TEXT", "EXPECTED_TEXT_SHA256"),
        ("html", "DEFAULT_HTML", "EXPECTED_HTML_SHA256"),
        ("source", "DEFAULT_SOURCE", "EXPECTED_SOURCE_SHA256"),
    ):
        if hasattr(module, constant):
            files[argument] = locate(raw_root, getattr(module, constant))
            expect_hash(files[argument], getattr(module, expected_constant), hashes)
    if case["case"] in RAW_EXTRA:
        raw_original = module.DEFAULT_INVENTORY.parent / RAW_EXTRA[case["case"]]
        raw = locate(raw_root, raw_original)
        expect_hash(raw, module.EXPECTED_SOURCE_SHA256, hashes)
        files["raw_capture"] = raw
    raw = files.get("source") or files.get("html") or files.get("raw_capture")
    if raw is None:
        raise RuntimeError(f"No raw source captured: {case['case']}")
    if raw.suffix == ".pdf":
        body = raw.read_bytes()
        if not body.startswith(b"%PDF-") or b"%%EOF" not in body[-65536:]:
            raise ValueError(f"Actual PDF integrity check failed: {case['case']}")
        binary = shutil.which("pdftotext")
        if not binary:
            raise ValueError("pdftotext is required to verify preserved PDF section wording")
        # -raw preserves the obituary's source reading order rather than
        # interleaving its printed columns. NFKC also maps the PDF's Kangxi
        # radical character in 部⾧ to ordinary 長; source bytes stay unchanged.
        extracted = subprocess.run([binary, "-raw", "-enc", "UTF-8", str(raw), "-"], capture_output=True, text=True, check=True, timeout=20).stdout
        normalized = unicodedata.normalize("NFKC", "".join(extracted.split()))
        phrases = [module.EVIDENCE_MEMBER, module.EVIDENCE_SECTION]
        phrases.append(module.EVIDENCE_SUBSECTION if case["case"] == "hiratsuka" else module.EVIDENCE_PRESIDENT)
        if any(unicodedata.normalize("NFKC", "".join(phrase.split())) not in normalized for phrase in phrases):
            raise ValueError(f"Preserved PDF wording did not match the original adjudication: {case['case']}")
    return module, files


def run(repo: Path, input_root: Path, output: Path, raw_root: Path | None = None, rehydrate: bool = False) -> dict[str, Any]:
    if output.is_relative_to(input_root) or input_root.is_relative_to(output):
        raise ValueError("Replay output and input archive must not contain each other")
    queue = locate(input_root, QUEUE)
    before: dict[str, str] = {}
    expect_hash(queue, QUEUE_SHA256, before)
    packet_path = locate(input_root, "source_packet.json")
    expect_hash(packet_path, PACKET_SHA256, before)
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    sources = {source["key"]: source for source in packet["sources"]}
    if len(sources) != 4 or set(sources) != {case["case"] for case in shared.CASES}:
        raise ValueError("The exact-source packet must contain the four approved cases")
    queue_rows = shared.read_csv(queue)
    if len(queue_rows) != 40 or len({r["member_key"] for r in queue_rows}) != 40:
        raise ValueError("Original replay queue must contain exactly 40 unique people")
    by_key = {row["member_key"]: row for row in queue_rows}
    for case in shared.CASES:
        if by_key.get(case["member_key"], {}).get("name_jp") != case["name_jp"]:
            raise ValueError(f"Original queue exact identity mismatch: {case['case']}")
    # Validate canonical inventory identities before any explicitly authorized
    # rehydration GET. Inventory filenames and bytes are never regenerated.
    for case in shared.CASES:
        module = load_adjudicator(repo, case)
        inventory = locate(input_root, module.DEFAULT_INVENTORY)
        expect_hash(inventory, INVENTORY_SHA256[case["case"]], before)
        source = sources[case["case"]]
        expected_source_sha = module.EXPECTED_HTML_SHA256 if hasattr(module, "EXPECTED_HTML_SHA256") else module.EXPECTED_SOURCE_SHA256
        if source["source_url"] != SOURCE_URLS[case["case"]] or source["source_sha256"] != expected_source_sha:
            raise ValueError(f"The source packet differs from original evidence identity: {case['case']}")
        expected_adjudication = locate(input_root, source["adjudication_relative_path"])
        expect_hash(expected_adjudication, ADJUDICATION_SHA256[case["case"]], before)
        rows = shared.read_csv(inventory)
        if len(rows) != 1 or any(rows[0].get(key) != expected for key, expected in {"member_key": case["member_key"], "name_jp": case["name_jp"], "source_url": SOURCE_URLS[case["case"]], "source_tier": "B", "source_organization": module.SOURCE_ORGANIZATION}.items()):
            raise ValueError(f"Unapproved source inventory identity: {case['case']}")
    requests = rehydrate_sources(repo, raw_root) if rehydrate else []
    raw_root = raw_root or input_root
    # Validate all four complete bundles before accepting any case.
    prepared = [(case, *prepare_case(repo, input_root, raw_root, case, before)) for case in shared.CASES]
    results = []
    for case, module, files in prepared:
        case_output = output / case["case"]
        capture = io.StringIO()
        with contextlib.redirect_stdout(capture):
            if case["case"] == "hiratsuka":
                module.run(queue, files["inventory"], case_output)
            elif case["case"] == "yoshikawa":
                module.run(queue, files["inventory"], files["text"], case_output)
            elif case["case"] == "nanbara":
                module.run(queue, files["inventory"], files["source"], case_output)
            else:
                module.run(queue, files["inventory"], files["text"], files["html"], case_output)
        (case_output / "replay_stdout.txt").write_text(capture.getvalue(), encoding="utf-8")
        summary = json.loads((case_output / "summary.json").read_text(encoding="utf-8"))
        expected_adjudication = locate(input_root, sources[case["case"]]["adjudication_relative_path"])
        actual_adjudication = case_output / expected_adjudication.name
        if shared.read_csv(actual_adjudication) != shared.read_csv(expected_adjudication):
            raise ValueError(f"Replayed CSV differs from the archived prior adjudication: {case['case']}")
        for field, expected in {
            "input_remaining_rows": 40, "target_member_key": case["member_key"],
            "target_name_jp": case["name_jp"], "accepted_broad_section": case["section"],
            "accepted_exact_subsection": case["subsection"], "direct_section_evidence_accepted": 1,
            "final_roster_frozen": 0, "dob_collection_started": 0, "bazi_variables_computed": 0,
            "final_roster_rows_written": 0,
        }.items():
            if summary.get(field) != expected:
                raise ValueError(f"Replayed result differs for {case['case']}: {field}")
        results.append({
            "case": case["case"], "member_key": case["member_key"], "name_jp": case["name_jp"],
            "accepted_broad_section": case["section"], "accepted_exact_subsection": case["subsection"],
            "source_url": SOURCE_URLS[case["case"]], "original_adjudicator": case["script"],
            "raw_source_bytes_hash_verified": 1, "prior_adjudicator_replayed": 1,
            "new_manual_semantic_review_performed": 0, "final_roster_row_written": 0,
        })
    for name, digest in before.items():
        if shared.sha256(Path(name)) != digest:
            raise RuntimeError(f"Replay input changed during the job: {name}")
    shared.write_csv(output / "replayed_evidence_decisions_v1.csv", results)
    residual = [row for row in queue_rows if row["member_key"] not in {case["member_key"] for case in shared.CASES}]
    if len(residual) != 36:
        raise ValueError("Replay residual must contain 36 people")
    shared.write_csv(output / "remaining36_unresolved_v1.csv", residual)
    summary = {
        "dataset": VERSION, "status": "passed", "input_queue_rows": 40,
        "raw_source_cases_replayed": 4, "raw_source_bytes_hash_verified_cases": 4,
        "replayed_section_ii_subsection6_cases": 1, "replayed_section_i_exclusions": 3,
        "effective_unresolved_rows": 36, "new_manual_semantic_reviews": 0,
        "evidence_origin": "exact_archived_source_bytes_and_original_adjudicator_replay",
        "source_identity_url_checks_passed": 4, "source_routes_reopened": 0,
        "archived_adjudication_csv_comparisons_passed": 4,
        "external_requests": len(requests), "source_request_attempts": requests,
        "pdf_original_phrase_checks_passed": 2, "raw_source_files_in_output": 0,
        "full_roster_completeness_claimed": 0, "primary_eligibility_finalized": 0,
        "final_roster_rows_written": 0, "final_roster_frozen": 0,
        "dob_collection_started": 0, "bazi_variables_computed": 0,
        "frozen_inputs_modified": 0, "input_sha256": before,
        "limitations": ["Replays prior adjudications; this is not a new independent manual source review.", "No DOB claim or complete/final Japan cohort is produced.", "The section-search closeout remains closed."],
    }
    shared.write_json(output / "summary.json", summary)
    (output / "summary.md").write_text(
        "Japan archived evidence replay: **passed**.\n\n"
        "All **4** original adjudicators replayed against the exact archived 40-person queue and "
        "hash-verified raw source captures. Source URLs, institutions, and exact person keys/names matched. "
        "Results: Hiratsuka → Section II/subsection 6; Yoshikawa, Nanbara, Doi → Section I. "
        "Effective residual: **36**.\n\n"
        "This replays existing adjudications; new independent manual semantic reviews: 0. "
        "No DOB assertions, complete/final Japan cohort, or hierarchy eligibility freeze is produced.\n\n"
        f"Frozen inputs modified: 0. Source-search routes reopened: 0. External requests: {len(requests)} "
        "(only manifest-approved exact-source rehydration). Raw source files in artifacts: 0. BaZi variables computed: 0.\n",
        encoding="utf-8",
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--input-root", type=Path, default=Path("data/academy_jobs_japan_inputs_v1"))
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--private-raw-root", type=Path, help="Private archive root; raw files are never copied to output")
    mode.add_argument("--rehydrate-approved-sources", action="store_true", help="One GET per each of four literal approved URLs, no retries/redirects; exact SHA required")
    parser.add_argument("--output-dir", "--output", dest="output", type=Path, required=True)
    args = parser.parse_args()
    output = None
    try:
        repo = args.repo_root.resolve()
        input_root = (repo / args.input_root).resolve() if not args.input_root.is_absolute() else args.input_root.resolve()
        output = shared.prepare_output(repo, args.output)
        if args.rehydrate_approved_sources:
            # Raw bytes live outside local_runs, are never artifact outputs,
            # and are deleted on success and on every exception.
            with tempfile.TemporaryDirectory(prefix="japan-evidence-replay-") as temporary:
                result = run(repo, input_root, output, Path(temporary), True)
        else:
            raw_root = args.private_raw_root.resolve() if args.private_raw_root else None
            result = run(repo, input_root, output, raw_root)
        print(json.dumps({key: value for key, value in result.items() if key != "input_sha256"}, ensure_ascii=False, indent=2))
        return 0
    except Exception as error:
        shared.failure(output, VERSION, error)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
