#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

SCRIPT_VERSION = "japan-academy-manifest-member-range-review-v1"
DEFAULT_INPUT = Path("data/japan_academy_official_roster_sources_v1")
DEFAULT_OUT = Path("data/japan_academy_manifest_member_range_review_v1")

FORMER_RE = re.compile(r"(?:前(?:帝國|帝国)?學士院|前(?:帝國|帝国)?学士院|前會員|前会員).*(?:會員|会員|客員)?")
PREDECESSOR_RE = re.compile(r"元東京(?:學士會院|学士会院).*(?:會員|会員|客員)")
NONROSTER_RE = re.compile(
    r"待遇|議員|议员|互選|互选|投票|規則|规则|事業擔當|事業担当|"
    r"委員|委员|囑託|嘱託|職員|职员"
)
SECTION2_RE = re.compile(r"(?:^|[　\s])第(?:二|2)\s*部(?:[/\s]|$)")
ACTIVE_MEMBER_RE = re.compile(
    r"^(?:第[一二三四五六七八九十百〇零0-9]+[　\s]+)?"
    r"(?:會員|会員)(?:及客員|及客员)?(?:[/\s]|$)"
)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fields is None:
        fields = list(rows[0].keys()) if rows else []
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def label_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        return " | ".join(x for x in (label_text(v) for v in value) if x)
    if isinstance(value, dict):
        if "@value" in value:
            return str(value.get("@value") or "").strip()
        parts = []
        for key in sorted(value):
            t = label_text(value[key])
            if t:
                parts.append(t)
        return " | ".join(parts)
    return str(value).strip()


def primary_title(value: str) -> str:
    return str(value or "").split(" | ", 1)[0].strip()


def canvas_index_from_id(canvas_id: str) -> int | None:
    m = re.search(r"/canvas/(\d+)(?:$|[/?#])", canvas_id)
    if m:
        return int(m.group(1))
    return None


def classify_range(label: str) -> str:
    s = " ".join(str(label or "").split())
    if PREDECESSOR_RE.search(s):
        return "predecessor_archive_roster"
    if FORMER_RE.search(s):
        return "former_member_archive_roster"
    if NONROSTER_RE.search(s):
        return "nonroster_member_keyword_false_positive"
    if SECTION2_RE.search(s) or re.match(r"^第(?:二|2)部(?:/|$)", s):
        return "explicit_section2_member_roster"
    if ACTIVE_MEMBER_RE.search(s):
        return "active_member_roster"
    if "名簿" in s:
        return "generic_directory_review"
    if re.search(r"會員|会員|第二部|第2部", s):
        return "other_member_keyword_review"
    return "not_member_range"


def extract_canvases(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if isinstance(manifest.get("sequences"), list):
        seqs = manifest.get("sequences") or []
        canvases = (seqs[0].get("canvases") or []) if seqs else []
        for ordinal, c in enumerate(canvases, 1):
            cid = str(c.get("@id") or c.get("id") or "")
            idx = canvas_index_from_id(cid) or ordinal
            image_url = ""
            images = c.get("images") or []
            if images and isinstance(images[0], dict):
                resource = images[0].get("resource") or {}
                image_url = str(resource.get("@id") or resource.get("id") or "")
                if not image_url:
                    service = resource.get("service") or {}
                    sid = str(service.get("@id") or service.get("id") or "")
                    if sid:
                        image_url = sid.rstrip("/") + "/full/full/0/default.jpg"
            out.append({
                "canvas_index": idx,
                "canvas_id": cid,
                "canvas_label": label_text(c.get("label")),
                "image_url": image_url,
            })
    elif isinstance(manifest.get("items"), list):
        for ordinal, c in enumerate(manifest.get("items") or [], 1):
            cid = str(c.get("id") or c.get("@id") or "")
            idx = canvas_index_from_id(cid) or ordinal
            image_url = ""
            pages = c.get("items") or []
            if pages and isinstance(pages[0], dict):
                annos = pages[0].get("items") or []
                if annos and isinstance(annos[0], dict):
                    body = annos[0].get("body") or {}
                    image_url = str(body.get("id") or body.get("@id") or "")
                    if not image_url:
                        services = body.get("service") or []
                        if isinstance(services, dict):
                            services = [services]
                        if services:
                            sid = str(services[0].get("id") or services[0].get("@id") or "")
                            if sid:
                                image_url = sid.rstrip("/") + "/full/max/0/default.jpg"
            out.append({
                "canvas_index": idx,
                "canvas_id": cid,
                "canvas_label": label_text(c.get("label")),
                "image_url": image_url,
            })
    return out


def load_cached_manifest(input_dir: Path, manifest_url: str) -> dict[str, Any]:
    key = hashlib.sha256(manifest_url.encode("utf-8")).hexdigest()
    meta_path = input_dir / "cache" / "responses" / f"{key}.json"
    body_path = input_dir / "cache" / "responses" / f"{key}.body"
    if not meta_path.exists() or not body_path.exists():
        raise FileNotFoundError(f"Cached manifest pair missing for {manifest_url}")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    body = body_path.read_bytes()
    if meta.get("url") != manifest_url:
        raise RuntimeError(f"Cached URL mismatch for {manifest_url}")
    if meta.get("sha256") != hashlib.sha256(body).hexdigest():
        raise RuntimeError(f"Cached SHA mismatch for {manifest_url}")
    return json.loads(body.decode("utf-8-sig"))


def review(input_dir: Path, out: Path) -> dict[str, Any]:
    out.mkdir(parents=True, exist_ok=True)
    manifest_rows = read_csv(input_dir / "manifest_inventory_v1.csv")
    range_rows = read_csv(input_dir / "manifest_range_inventory_v1.csv")
    bib_rows = read_csv(input_dir / "official_roster_bibliography_v1.csv")

    bib_by_pid = {r.get("pid", ""): r for r in bib_rows if r.get("pid")}
    manifest_by_pid = {r.get("pid", ""): r for r in manifest_rows if r.get("pid")}

    starts_by_pid: dict[str, list[int]] = defaultdict(list)
    enriched: list[dict[str, Any]] = []
    for r in range_rows:
        refs = [x for x in str(r.get("canvas_refs") or "").split("|") if x]
        indices = [x for x in (canvas_index_from_id(ref) for ref in refs) if x is not None]
        start = min(indices) if indices else None
        if start is not None:
            starts_by_pid[r.get("pid", "")].append(start)
        enriched.append({
            **r,
            "range_classification": classify_range(r.get("range_label", "")),
            "start_canvas_index": start if start is not None else "",
            "end_canvas_index": "",
            "selection_status": "",
        })

    for r in enriched:
        pid = r.get("pid", "")
        start_raw = r.get("start_canvas_index")
        if start_raw == "":
            continue
        start = int(start_raw)
        greater = sorted({x for x in starts_by_pid[pid] if x > start})
        manifest_row = manifest_by_pid.get(pid, {})
        canvas_count = int(manifest_row.get("canvas_count") or 0)
        end = greater[0] - 1 if greater else canvas_count
        r["end_canvas_index"] = end

    by_pid: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in enriched:
        by_pid[r.get("pid", "")].append(r)

    selected_spans: list[dict[str, Any]] = []
    for pid, rr in sorted(by_pid.items()):
        explicit = [
            r for r in rr
            if r["range_classification"] == "explicit_section2_member_roster"
            and r["start_canvas_index"] != ""
        ]
        active = [
            r for r in rr
            if r["range_classification"] == "active_member_roster"
            and r["start_canvas_index"] != ""
        ]
        chosen = explicit if explicit else active
        basis = "explicit_section2_preferred" if explicit else ("active_member_roster_fallback" if active else "")
        for r in chosen:
            r["selection_status"] = "selected_minimal_roster_span"
            selected_spans.append({
                "pid": pid,
                "series": r.get("series", ""),
                "bibliographic_title": primary_title(r.get("bibliographic_title", "")),
                "manifest_url": r.get("manifest_url", ""),
                "range_id": r.get("range_id", ""),
                "parent_range_id": r.get("parent_range_id", ""),
                "range_label": r.get("range_label", ""),
                "range_classification": r.get("range_classification", ""),
                "selection_basis": basis,
                "start_canvas_index": r.get("start_canvas_index", ""),
                "end_canvas_index": r.get("end_canvas_index", ""),
                "page_count": (
                    int(r["end_canvas_index"]) - int(r["start_canvas_index"]) + 1
                    if r.get("start_canvas_index") != "" and r.get("end_canvas_index") != ""
                    else ""
                ),
                "manual_scope_note": (
                    "If the span is a combined member-and-guest list, later transcription must "
                    "exclude guest/honorary rows and retain only official Section II members."
                ),
            })

    page_queue: list[dict[str, Any]] = []
    seen_pages: set[tuple[str, int]] = set()
    manifest_cache: dict[str, dict[str, Any]] = {}
    for span in selected_spans:
        pid = span["pid"]
        url = span["manifest_url"]
        if pid not in manifest_cache:
            manifest_cache[pid] = load_cached_manifest(input_dir, url)
        canvases = {int(c["canvas_index"]): c for c in extract_canvases(manifest_cache[pid])}
        for idx in range(int(span["start_canvas_index"]), int(span["end_canvas_index"]) + 1):
            c = canvases.get(idx)
            if c is None:
                raise RuntimeError(f"Canvas {idx} missing from manifest PID {pid}")
            page_key = (pid, idx)
            if page_key in seen_pages:
                continue
            seen_pages.add(page_key)
            page_queue.append({
                "pid": pid,
                "series": span["series"],
                "bibliographic_title": span["bibliographic_title"],
                "range_label": span["range_label"],
                "range_classification": span["range_classification"],
                "selection_basis": span["selection_basis"],
                "canvas_index": idx,
                "canvas_id": c["canvas_id"],
                "canvas_label": c["canvas_label"],
                "image_url": c["image_url"],
                "downloaded": 0,
                "ocr_performed": 0,
                "member_names_extracted": 0,
                "roster_rows_accepted": 0,
            })

    error_review: list[dict[str, Any]] = []
    for r in manifest_rows:
        if r.get("state") == "fetched":
            continue
        b = bib_by_pid.get(r.get("pid", ""), {})
        desc = b.get("descriptions", "")
        error = r.get("error", "")
        if "404" in error and ("テキストデータ" in desc or "プレーンテキスト" in desc):
            cls = "text_only_ndl_record_no_iiif_manifest"
            retry = 0
        elif "404" in error:
            cls = "iiif_manifest_not_found_review"
            retry = 0
        else:
            cls = "transient_or_unclassified_manifest_error"
            retry = 1
        error_review.append({
            **r,
            "bibliographic_descriptions": desc,
            "manifest_error_class": cls,
            "retry_recommended": retry,
        })

    write_csv(out / "range_classification_v1.csv", enriched)
    write_csv(out / "selected_member_list_spans_v1.csv", selected_spans)
    write_csv(out / "minimal_member_page_queue_v1.csv", page_queue)
    write_csv(out / "manifest_error_review_v1.csv", error_review)

    summary = {
        "dataset": SCRIPT_VERSION,
        "input_dir": str(input_dir),
        "manifest_rows": len(manifest_rows),
        "fetched_manifests": sum(r.get("state") == "fetched" for r in manifest_rows),
        "manifest_errors": sum(r.get("state") != "fetched" for r in manifest_rows),
        "range_rows_total": len(enriched),
        "range_classification_counts": dict(sorted(Counter(r["range_classification"] for r in enriched).items())),
        "selected_member_list_spans": len(selected_spans),
        "selected_span_basis_counts": dict(sorted(Counter(r["selection_basis"] for r in selected_spans).items())),
        "minimal_member_pages": len(page_queue),
        "unique_page_pids": len({r["pid"] for r in page_queue}),
        "manifest_error_class_counts": dict(sorted(Counter(r["manifest_error_class"] for r in error_review).items())),
        "images_downloaded": 0,
        "ocr_performed": 0,
        "member_names_extracted": 0,
        "roster_rows_accepted": 0,
        "final_roster_frozen": 0,
        "dob_collection_started": 0,
        "bazi_variables_computed": 0,
        "next_action": (
            "Review the selected spans and minimal page queue. Only after approval may a separate "
            "collector download the queued official roster images."
        ),
        "input_sha256": {
            "manifest_inventory": sha256_file(input_dir / "manifest_inventory_v1.csv"),
            "manifest_ranges": sha256_file(input_dir / "manifest_range_inventory_v1.csv"),
            "bibliography": sha256_file(input_dir / "official_roster_bibliography_v1.csv"),
        },
    }
    write_json(out / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


def self_test() -> None:
    labels = {
        "第五　会員/16p": "active_member_roster",
        "第二部/8p": "explicit_section2_member_roster",
        "第三十九　帝國學士院前會員及客員/141p": "former_member_archive_roster",
        "第四十一　元東京學士會院會員及客員/148p": "predecessor_archive_roster",
        "第八　貴族院帝國學士院會員議員互選規則/50p": "nonroster_member_keyword_false_positive",
        "第四十三　委員、事業擔當會員、囑託員/170p": "nonroster_member_keyword_false_positive",
    }
    for label, expected in labels.items():
        got = classify_range(label)
        assert got == expected, (label, got, expected)
    assert canvas_index_from_id("https://x/canvas/82") == 82
    manifest = {
        "sequences": [{"canvases": [{
            "@id": "https://x/canvas/1",
            "label": "1",
            "images": [{"resource": {"@id": "https://x/image.jpg"}}],
        }]}]
    }
    rows = extract_canvases(manifest)
    assert rows[0]["canvas_index"] == 1 and rows[0]["image_url"] == "https://x/image.jpg"
    print("SELF-TEST OK: range classification, canvas indexing, and image-URL extraction are consistent")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default=str(DEFAULT_INPUT))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        self_test()
        return 0
    review(Path(args.input), Path(args.out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
