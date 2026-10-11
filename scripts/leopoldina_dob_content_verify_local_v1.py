#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import html
import json
import os
import re
import ssl
import time
import tempfile
import unicodedata
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse, urljoin

IN = Path("data/leopoldina_p569_source_resolver_local_v1/content_source_candidate_records_v1.csv")
OUT = Path("data/leopoldina_dob_content_verify_local_v1")
CACHE = OUT / "cache"
UA = "bazi-public-figure-study/1.0 (Leopoldina DOB content verification; no BaZi computation)"
SLEEP_SECONDS = float(os.environ.get("LEOPOLDINA_CONTENT_SLEEP", "0.15"))
MAX_BYTES = int(os.environ.get("LEOPOLDINA_CONTENT_MAX_BYTES", str(5 * 1024 * 1024)))

# Explicit locator/aggregation systems: useful for identity/source discovery, not
# sufficient independent DOB evidence.
LOCATOR_ONLY_QIDS = {
    "Q36578",      # GND
    "Q19938912",   # BnF authorities
    "Q13550863",   # Czech authority DB
    "Q23833686",   # DNB catalog
    "Q112122720",  # WorldCat Entities
    "Q29861311",   # SNAC
    "Q1201876",    # Open Library
}

MONTH_WORDS = {
    1: ["january","jan","januar","janvier","gennaio","enero","januari","januar","siječnja","sijecnja","januarja"],
    2: ["february","feb","februar","février","fevrier","febbraio","febrero","februari","veljače","veljace","februarja"],
    3: ["march","mar","märz","maerz","mars","marzo","maart","ožujka","ozujka","marca"],
    4: ["april","apr","avril","aprile","abril","travanj","travnja"],
    5: ["may","mai","mai","maggio","mayo","mei","svibnja"],
    6: ["june","jun","juni","juin","giugno","junio","juni","lipnja"],
    7: ["july","jul","juli","juillet","luglio","julio","juli","srpnja"],
    8: ["august","aug","août","aout","agosto","augustus","kolovoza"],
    9: ["september","sep","sept","septembre","settembre","septiembre","rujna"],
    10: ["october","oct","oktober","okt","octobre","ottobre","octubre","oktober","listopada"],
    11: ["november","nov","novembre","noviembre","studenoga"],
    12: ["december","dec","dezember","dez","décembre","decembre","dicembre","diciembre","prosinac","prosinca"],
}

try:
    import certifi
except ImportError:
    certifi = None


class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag.lower() in {"script", "style", "noscript", "svg"}:
            self.skip += 1

    def handle_endtag(self, tag):
        if tag.lower() in {"script", "style", "noscript", "svg"} and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip and data:
            self.parts.append(data)


def read_csv(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows, fields):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def sha256_bytes(b: bytes):
    return hashlib.sha256(b).hexdigest()


def sha256_file(path: Path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def verified_contexts():
    out = []
    if certifi is not None:
        out.append(("certifi", ssl.create_default_context(cafile=certifi.where())))
    out.append(("system", ssl.create_default_context()))
    return out


def cache_key(url: str):
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


def fetch(url: str, retries=4):
    CACHE.mkdir(parents=True, exist_ok=True)
    key = cache_key(url)
    meta_path = CACHE / f"{key}.json"
    body_path = CACHE / f"{key}.body"
    if meta_path.exists() and body_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        # Successful responses are stable/reusable. Failed responses are deliberately
        # retried on later runs so transient blocks, redirects, TLS fixes, or VPN
        # changes do not become permanent false negatives.
        if not str(meta.get("error") or "").strip():
            return meta, body_path.read_bytes(), True

    last = None
    for attempt in range(retries):
        cert_errors = []
        for label, ctx in verified_contexts():
            current_url = url
            try:
                for redirect_index in range(7):
                    req = urllib.request.Request(
                        current_url,
                        headers={
                            "User-Agent": UA,
                            "Accept": "text/html,application/xhtml+xml,application/json,text/plain,application/xml,text/xml,application/pdf;q=0.8,*/*;q=0.5",
                            "Accept-Language": "en-US,en;q=0.9,de;q=0.8,fr;q=0.6",
                        },
                    )
                    try:
                        r = urllib.request.urlopen(req, timeout=90, context=ctx)
                    except urllib.error.HTTPError as e:
                        # A few scholarly sites return 307/308 in ways urllib does not
                        # automatically follow. Follow only an explicit Location header.
                        if e.code in {301, 302, 303, 307, 308} and e.headers.get("Location") and redirect_index < 6:
                            current_url = urljoin(current_url, e.headers["Location"])
                            continue
                        raise
                    with r:
                        body = r.read(MAX_BYTES + 1)
                        truncated = int(len(body) > MAX_BYTES)
                        if truncated:
                            body = body[:MAX_BYTES]
                        meta = {
                            "url": url,
                            "http_status": getattr(r, "status", 200),
                            "final_url": r.geturl(),
                            "content_type": str(r.headers.get("Content-Type") or ""),
                            "content_length_captured": len(body),
                            "truncated": truncated,
                            "error": "",
                            "tls_context": label,
                            "body_sha256": sha256_bytes(body),
                        }
                        body_path.write_bytes(body)
                        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
                        return meta, body, False
                raise RuntimeError(f"Too many redirects for {url}")
            except urllib.error.URLError as e:
                reason = getattr(e, "reason", None)
                if isinstance(reason, ssl.SSLCertVerificationError) or "CERTIFICATE_VERIFY_FAILED" in str(e):
                    cert_errors.append(f"{label}: {e}")
                    continue
                last = e
                break
            except Exception as e:
                last = e
                break
        if cert_errors and last is None:
            last = RuntimeError(" | ".join(cert_errors))
        if attempt + 1 < retries:
            time.sleep(min(12.0, 2.0 ** attempt))

    meta = {
        "url": url,
        "http_status": "",
        "final_url": url,
        "content_type": "",
        "content_length_captured": 0,
        "truncated": 0,
        "error": repr(last),
        "tls_context": "",
        "body_sha256": "",
    }
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    body_path.write_bytes(b"")
    return meta, b"", False


def fold(s: str):
    s = html.unescape(s or "")
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.casefold()
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def body_to_text(body: bytes, content_type: str):
    ctype = (content_type or "").lower()
    if not body:
        return "", "empty"
    if "pdf" in ctype or body.startswith(b"%PDF"):
        return "", "pdf_unparsed"
    enc = "utf-8"
    m = re.search(r"charset\s*=\s*([A-Za-z0-9._-]+)", ctype)
    if m:
        enc = m.group(1)
    try:
        raw = body.decode(enc, "replace")
    except Exception:
        raw = body.decode("utf-8", "replace")

    if "html" in ctype or "<html" in raw[:1000].lower() or "<body" in raw[:2000].lower():
        p = TextExtractor()
        try:
            p.feed(raw)
            text = " ".join(p.parts)
        except Exception:
            text = re.sub(r"(?s)<[^>]+>", " ", raw)
        return re.sub(r"\s+", " ", html.unescape(text)).strip(), "html_text"
    return re.sub(r"\s+", " ", html.unescape(raw)).strip(), "text"


def date_variants(iso: str):
    y, m, d = map(int, iso.split("-"))
    out = {
        iso,
        f"{y}/{m:02d}/{d:02d}",
        f"{y}.{m:02d}.{d:02d}",
        f"{d:02d}.{m:02d}.{y}",
        f"{d}.{m}.{y}",
        f"{d:02d}/{m:02d}/{y}",
        f"{d}/{m}/{y}",
        f"{d:02d}-{m:02d}-{y}",
        f"{d}-{m}-{y}",
    }
    for word in MONTH_WORDS[m]:
        out.add(f"{d} {word} {y}")
        out.add(f"{d}. {word} {y}")
        out.add(f"{word} {d} {y}")
        out.add(f"{word} {d}, {y}")
    return sorted({fold(x) for x in out if x}, key=len, reverse=True)


def find_date(text: str, iso: str):
    ft = fold(text)
    for v in date_variants(iso):
        idx = ft.find(v)
        if idx >= 0:
            a = max(0, idx - 220)
            b = min(len(ft), idx + len(v) + 260)
            return 1, v, ft[a:b]
    y = iso[:4]
    return 0, "", "" if y not in ft else "birth_year_present"


def domain(url):
    try:
        return urlparse(url).netloc.lower().removeprefix("www.")
    except Exception:
        return ""


def effective_class(row):
    policy_tier = (row.get("policy_tier") or "").strip()
    if policy_tier == "A":
        return "tier_a_candidate"
    if policy_tier == "B":
        return "tier_b_candidate"
    qid = (row.get("stated_in_qid") or "").strip()
    label = fold(row.get("stated_in_label") or "")
    hint = (row.get("source_policy_hint") or "").strip()
    if qid in LOCATOR_ONLY_QIDS:
        return "locator_only"
    if any(x in label for x in ("authority", "snac", "open library", "worldcat", "integrated authority")):
        return "locator_only"
    if hint == "institutional_or_archival_candidate":
        return "tier_a_candidate"
    if hint == "content_source_candidate":
        return "tier_b_candidate"
    return "unclassified"


def row_urls(row):
    out = []
    if (row.get("source_record_url") or "").strip():
        out.append((row["source_record_url"].strip(), "source_record_url"))
    for u in re.split(r"[|;]\s*", (row.get("direct_reference_urls") or "").strip()):
        if u.startswith("http://") or u.startswith("https://"):
            out.append((u, "direct_reference_url"))
    seen = set()
    dedup = []
    for u, kind in out:
        if u not in seen:
            seen.add(u)
            dedup.append((u, kind))
    return dedup



def attempt_key(row, url):
    payload = [
        str(row.get("member_slug") or ""),
        str(row.get("wikidata_qid") or ""),
        str(row.get("candidate_exact_dob") or ""),
        str(row.get("stated_in_qid") or ""),
        str(row.get("independence_group") or ""),
        str(url or ""),
    ]
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def load_progress(progress_path: Path):
    latest = {}
    if not progress_path.exists():
        return latest
    with progress_path.open("r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as e:
                raise RuntimeError(f"Corrupt progress JSONL at {progress_path}:{lineno}: {e}")
            key = str(row.get("_attempt_key") or "")
            if not re.fullmatch(r"[0-9a-f]{64}", key):
                raise RuntimeError(f"Invalid checkpoint attempt key at {progress_path}:{lineno}")
            latest[key] = row
    return latest


def append_progress(progress_path: Path, row):
    progress_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(row, ensure_ascii=False, separators=(",", ":"))
    with progress_path.open("a", encoding="utf-8") as f:
        f.write(payload + "\n")
        f.flush()
        os.fsync(f.fileno())


def ensure_progress_meta(meta_path: Path, meta):
    if meta_path.exists():
        old = json.loads(meta_path.read_text(encoding="utf-8"))
        for key in ("schema_version", "input_sha256", "year_min", "year_max"):
            if old.get(key) != meta.get(key):
                raise RuntimeError(
                    f"Checkpoint metadata mismatch for {key}: "
                    f"existing={old.get(key)!r}, current={meta.get(key)!r}. "
                    "Use a different --out directory or --reset-progress."
                )
        return
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = meta_path.with_suffix(meta_path.suffix + ".tmp")
    tmp.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(meta_path)


def reset_progress_files(out: Path):
    for name in ("verification_progress_v1.jsonl", "verification_progress_meta_v1.json"):
        p = out / name
        if p.exists():
            p.unlink()


def main():
    global OUT, CACHE
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default=str(IN))
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--cache-dir", default="", help="Optional shared cache directory; default is <out>/cache")
    ap.add_argument("--year-min", type=int, default=1835)
    ap.add_argument("--year-max", type=int, default=1985)
    ap.add_argument("--limit", type=int, default=0, help="Optional URL-attempt limit for a pilot; 0=all")
    ap.add_argument("--retry-failed", action="store_true", help="Re-run previously checkpointed fetch_failed attempts only; successful/no-match attempts remain skipped")
    ap.add_argument("--reset-progress", action="store_true", help="Delete only the output checkpoint journal/meta before starting; shared URL cache is preserved")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        sample = "Geboren am 15. April 1896 in Saratow."
        hit, variant, snippet = find_date(sample, "1896-04-15")
        assert hit == 1 and "1896" in snippet
        assert effective_class({"stated_in_qid":"Q29861311","stated_in_label":"SNAC","source_policy_hint":"content_source_candidate"}) == "locator_only"
        assert effective_class({"policy_tier":"A","stated_in_qid":"Q1050232"}) == "tier_a_candidate"
        assert effective_class({"policy_tier":"B","stated_in_qid":"Q1202222"}) == "tier_b_candidate"
        k1 = attempt_key({"member_slug":"x","wikidata_qid":"Q1","candidate_exact_dob":"1900-01-01","stated_in_qid":"Q2","independence_group":"g"},"https://example.org/a")
        k2 = attempt_key({"member_slug":"x","wikidata_qid":"Q1","candidate_exact_dob":"1900-01-01","stated_in_qid":"Q2","independence_group":"g"},"https://example.org/a")
        assert k1 == k2 and len(k1) == 64
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            pp = td / "progress.jsonl"
            mp = td / "meta.json"
            meta = {"schema_version":1,"input_sha256":"abc","year_min":1835,"year_max":1985}
            ensure_progress_meta(mp, meta)
            append_progress(pp, {"_attempt_key":k1,"verification_status":"exact_date_text_match"})
            loaded = load_progress(pp)
            assert loaded[k1]["verification_status"] == "exact_date_text_match"
            ensure_progress_meta(mp, dict(meta))
            try:
                ensure_progress_meta(mp, {**meta, "input_sha256":"different"})
            except RuntimeError:
                pass
            else:
                raise AssertionError("checkpoint metadata mismatch was not rejected")
        print("Leopoldina content verifier self-test OK")
        return

    src = Path(args.input)
    out = Path(args.out)
    OUT = out
    CACHE = Path(args.cache_dir) if args.cache_dir else out / "cache"
    if args.reset_progress:
        reset_progress_files(out)
    if not src.exists():
        raise RuntimeError(f"Missing {src}. Run source resolver first.")

    rows = read_csv(src)
    eligible = []
    for r in rows:
        dob = (r.get("candidate_exact_dob") or "").strip()
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", dob):
            continue
        y = int(dob[:4])
        if args.year_min <= y <= args.year_max:
            eligible.append(r)

    attempts = []
    for r in eligible:
        cls = effective_class(r)
        if cls == "locator_only":
            continue
        for u, kind in row_urls(r):
            attempts.append((r, u, kind, cls))

    # Stable order and exact URL dedupe within the same member/source.
    seen = set()
    dedup = []
    for r, u, kind, cls in attempts:
        k = (r.get("member_slug"), r.get("stated_in_qid"), u)
        if k not in seen:
            seen.add(k)
            dedup.append((r, u, kind, cls))
    attempts = dedup
    if args.limit:
        attempts = attempts[:args.limit]

    out.mkdir(parents=True, exist_ok=True)
    progress_path = out / "verification_progress_v1.jsonl"
    progress_meta_path = out / "verification_progress_meta_v1.json"
    progress_meta = {
        "schema_version": 1,
        "input": str(src),
        "input_sha256": sha256_file(src),
        "year_min": args.year_min,
        "year_max": args.year_max,
        "note": "Append-only per-URL checkpoint. Last row for an attempt key wins. Ctrl+C may repeat only the in-flight URL.",
    }
    ensure_progress_meta(progress_meta_path, progress_meta)
    progress_latest = load_progress(progress_path)

    attempt_keys = {}
    for r, u, kind, cls in attempts:
        k = attempt_key(r, u)
        if k in attempt_keys:
            raise RuntimeError(f"Duplicate attempt key after URL dedupe: {k}")
        attempt_keys[k] = (r, u, kind, cls)

    # Keep only checkpoint rows belonging to the current attempt universe.
    verification_by_key = {
        k: dict(v) for k, v in progress_latest.items() if k in attempt_keys
    }
    completed_before = len(verification_by_key)
    pending = []
    for k, tup in attempt_keys.items():
        old = verification_by_key.get(k)
        if old is None:
            pending.append((k, *tup))
        elif args.retry_failed and old.get("verification_status") == "fetch_failed":
            pending.append((k, *tup))

    print(
        f"resume: total_attempts={len(attempts)} checkpointed={completed_before} "
        f"pending={len(pending)} retry_failed={int(args.retry_failed)}"
    )

    try:
        for pending_index, (k, r, u, kind, cls) in enumerate(pending, 1):
            meta, body, cache_hit = fetch(u)
            text, parse_mode = body_to_text(body, meta.get("content_type",""))
            hit, matched, snippet = find_date(text, r["candidate_exact_dob"]) if text else (0, "", "")
            name_words = [fold(x) for x in re.findall(r"[A-Za-zÀ-ž'-]{4,}", r.get("display_name",""))]
            ft = fold(text)
            name_anchor_hit = int(any(w in ft for w in name_words[-3:])) if text and name_words else 0
            status = (
                "exact_date_text_match" if hit else
                "pdf_needs_separate_verification" if parse_mode == "pdf_unparsed" else
                "fetch_failed" if meta.get("error") else
                "no_exact_date_text_match"
            )
            rec = {
                "_attempt_key": k,
                "member_slug": r.get("member_slug",""),
                "display_name": r.get("display_name",""),
                "wikidata_qid": r.get("wikidata_qid",""),
                "candidate_exact_dob": r.get("candidate_exact_dob",""),
                "stated_in_qid": r.get("stated_in_qid",""),
                "stated_in_label": r.get("stated_in_label",""),
                "resolver_policy_hint": r.get("source_policy_hint",""),
                "policy_tier": r.get("policy_tier",""),
                "single_source_sufficient": r.get("single_source_sufficient",""),
                "independence_group": r.get("independence_group",""),
                "discovery_route": r.get("discovery_route",""),
                "effective_source_class": cls,
                "url_kind": kind,
                "url": u,
                "domain": domain(u),
                "http_status": meta.get("http_status",""),
                "final_url": meta.get("final_url",""),
                "content_type": meta.get("content_type",""),
                "captured_bytes": meta.get("content_length_captured",0),
                "body_sha256": meta.get("body_sha256",""),
                "cache_hit": int(cache_hit),
                "parse_mode": parse_mode,
                "name_anchor_hit": name_anchor_hit,
                "candidate_exact_date_text_match": hit,
                "matched_variant": matched,
                "evidence_snippet_folded": snippet,
                "verification_status": status,
                "fetch_error": meta.get("error",""),
                "content_verified_machine": int(hit),
                "final_exact_dob": "",
                "acceptance_status": "not_adjudicated",
                "bazi_variables_computed": 0,
            }
            append_progress(progress_path, rec)
            verification_by_key[k] = rec
            overall_done = len(verification_by_key)
            print(
                f"{overall_done}/{len(attempts)} (+{pending_index}/{len(pending)} this run) "
                f"{r.get('member_slug')} {domain(u)} {status} cache={int(cache_hit)}"
            )
            if not cache_hit and pending_index < len(pending):
                time.sleep(SLEEP_SECONDS)
    except KeyboardInterrupt:
        print(
            f"\nInterrupted safely. Checkpointed {len(verification_by_key)}/{len(attempts)} attempts. "
            "Re-run the same command to resume."
        )
        raise SystemExit(130)

    verification = []
    for k in attempt_keys:
        if k in verification_by_key:
            row = dict(verification_by_key[k])
            row.pop("_attempt_key", None)
            verification.append(row)

    if len(verification) != len(attempts):
        raise RuntimeError(
            f"Run ended without interruption but checkpoint coverage is incomplete: "
            f"{len(verification)}/{len(attempts)}"
        )

    vfields = [
        "member_slug","display_name","wikidata_qid","candidate_exact_dob",
        "stated_in_qid","stated_in_label","resolver_policy_hint","policy_tier",
        "single_source_sufficient","independence_group","discovery_route","effective_source_class",
        "url_kind","url","domain","http_status","final_url","content_type","captured_bytes",
        "body_sha256","cache_hit","parse_mode","name_anchor_hit",
        "candidate_exact_date_text_match","matched_variant","evidence_snippet_folded",
        "verification_status","fetch_error","content_verified_machine",
        "final_exact_dob","acceptance_status","bazi_variables_computed",
    ]
    write_csv(out / "verification_rows_v1.csv", verification, vfields)

    by_member = {}
    for r in eligible:
        qid = r.get("wikidata_qid","")
        slug = r.get("member_slug","")
        k = (slug, qid)
        if k not in by_member:
            by_member[k] = {
                "member_slug": slug,
                "display_name": r.get("display_name",""),
                "wikidata_qid": qid,
                "candidate_exact_dob": r.get("candidate_exact_dob",""),
            }
    vr_by_member = defaultdict(list)
    for x in verification:
        vr_by_member[(x["member_slug"],x["wikidata_qid"])].append(x)

    summary_rows = []
    for k, base in sorted(by_member.items()):
        vv = vr_by_member.get(k, [])
        pos = [x for x in vv if int(x["content_verified_machine"]) == 1]
        tier_a = sorted({x["stated_in_qid"] for x in pos if x["effective_source_class"] == "tier_a_candidate" and x["stated_in_qid"]})
        tier_b = sorted({x["stated_in_qid"] for x in pos if x["effective_source_class"] == "tier_b_candidate" and x["stated_in_qid"]})
        tier_a_groups = sorted({(x["independence_group"] or x["stated_in_qid"]) for x in pos if x["effective_source_class"] == "tier_a_candidate" and (x["independence_group"] or x["stated_in_qid"])})
        tier_b_groups = sorted({(x["independence_group"] or x["stated_in_qid"]) for x in pos if x["effective_source_class"] == "tier_b_candidate" and (x["independence_group"] or x["stated_in_qid"])})
        summary_rows.append({
            **base,
            "verification_url_attempts": len(vv),
            "http_success_rows": sum(str(x["http_status"]).startswith("2") for x in vv),
            "machine_exact_date_positive_rows": len(pos),
            "positive_tier_a_source_qids": "|".join(tier_a),
            "positive_tier_a_source_count": len(tier_a),
            "positive_tier_a_independence_groups": "|".join(tier_a_groups),
            "positive_tier_a_independence_group_count": len(tier_a_groups),
            "positive_tier_b_source_qids": "|".join(tier_b),
            "positive_tier_b_source_count": len(tier_b),
            "positive_tier_b_independence_groups": "|".join(tier_b_groups),
            "positive_tier_b_independence_group_count": len(tier_b_groups),
            "positive_domains": "|".join(sorted({x["domain"] for x in pos if x["domain"]})),
            "pdf_review_rows": sum(x["verification_status"] == "pdf_needs_separate_verification" for x in vv),
            "fetch_failed_rows": sum(x["verification_status"] == "fetch_failed" for x in vv),
            "machine_evidence_status": (
                "not_attempted" if not vv else
                "tier_a_positive" if tier_a_groups else
                "two_plus_tier_b_positive" if len(tier_b_groups) >= 2 else
                "one_tier_b_positive" if len(tier_b_groups) == 1 else
                "no_machine_positive"
            ),
            "final_exact_dob": "",
            "acceptance_status": "not_adjudicated",
            "bazi_variables_computed": 0,
        })

    sfields = list(summary_rows[0].keys()) if summary_rows else [
        "member_slug","display_name","wikidata_qid","candidate_exact_dob"
    ]
    write_csv(out / "candidate_content_verification_summary_v1.csv", summary_rows, sfields)
    write_csv(out / "machine_positive_rows_v1.csv", [x for x in verification if int(x["content_verified_machine"])], vfields)
    write_csv(out / "fetch_or_pdf_review_v1.csv", [x for x in verification if x["verification_status"] in {"fetch_failed","pdf_needs_separate_verification"}], vfields)

    status_counts = Counter(x["verification_status"] for x in verification)
    evidence_counts = Counter(x["machine_evidence_status"] for x in summary_rows)
    summary = {
        "dataset": "Leopoldina primary-window DOB source-content verification",
        "input": str(src),
        "input_sha256": sha256_file(src),
        "cache_directory": str(CACHE),
        "year_min": args.year_min,
        "year_max": args.year_max,
        "eligible_reference_rows": len(eligible),
        "eligible_unique_candidates": len(summary_rows),
        "url_attempts": len(verification),
        "checkpoint_total_attempts": len(attempts),
        "checkpoint_completed_attempts": len(verification),
        "checkpoint_progress_file": str(progress_path),
        "checkpoint_meta_file": str(progress_meta_path),
        "run_complete": int(len(verification) == len(attempts)),
        "verification_status_counts": dict(sorted(status_counts.items())),
        "candidate_machine_evidence_counts": dict(sorted(evidence_counts.items())),
        "candidates_attempted": sum(int(x["verification_url_attempts"]) > 0 for x in summary_rows),
        "candidates_unattempted": sum(int(x["verification_url_attempts"]) == 0 for x in summary_rows),
        "candidates_with_any_machine_positive": sum(int(x["machine_exact_date_positive_rows"]) > 0 for x in summary_rows),
        "candidates_with_tier_a_positive": sum(int(x["positive_tier_a_independence_group_count"]) > 0 for x in summary_rows),
        "candidates_with_two_plus_tier_b_positive": sum(int(x["positive_tier_b_independence_group_count"]) >= 2 for x in summary_rows),
        "final_exact_dob_written": 0,
        "automatic_acceptance": 0,
        "bazi_variables_computed": 0,
        "decision_rule": "Collection/verification only. Machine exact-date matches are evidence candidates, not final DOB acceptance. Locator-only sources are excluded. Final acceptance requires a separately frozen adjudication rule.",
    }
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
