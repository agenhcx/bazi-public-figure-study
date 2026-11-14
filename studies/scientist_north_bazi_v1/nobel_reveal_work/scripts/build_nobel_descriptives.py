#!/usr/bin/env python3
"""Gated, descriptive-only Nobel tables under the frozen scientist definitions.

No additional p values, trend tests, selected windows, or fitted birth hours.
Synthetic self-tests do not read study cohorts or frozen feature pools.
"""

import argparse
from collections import Counter
import datetime as dt
import gzip
import hashlib
import json
from pathlib import Path
import re
import zipfile

import numpy as np

V4_SHA = "53302ef5c4bbb946adcaceb70d7a7fd576c7f06d03c3e7080874654e1a2644f9"
CALENDAR_SHA = "d150883033464ebd3afafaf764738ed3b573d0d0fb4bd252a955e403a75fcc8b"
HIDDEN_SHA = "19e8bc8648fe8b69122161da260e1dae487816241c655bd96a1273783f1ef723"
GODS = ["比肩", "劫财", "食神", "伤官", "偏财", "正财", "七杀", "正官", "偏印", "正印"]
STEMS = list("甲乙丙丁戊己庚辛壬癸")
MODELS = ["M0_5", "M1_priority_5", "M1_share_5", "M1_any_5",
          "M2_main_7", "M3_priority_7", "M3_share_7", "M3_any_7"]
TRAITS = ["PI", "SG"]
DENOMINATORS = [5, 5, 5, 5, 7, 7, 7, 7]
BASIC_METRICS = ["PI_count", "SG_count", "GY_narrow", "SGY_narrow", "water_DM"]
DECADES = list(range(1830, 1990, 10))
COUNTRIES = ["NAS", "UK_Royal_Society", "DE_Leopoldina", "France", "Japan", "CAS"]


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"


def json_safe(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [json_safe(v) for v in value]
    return value


def verify_gate(args):
    """No feature or person file is opened until this complete lock check passes."""
    scope = json.loads(Path(args.scope).read_text())
    locked = json.loads(Path(args.locked_files).read_text())
    receipt = json.loads(Path(args.execution_receipt).read_text())
    verified = (receipt.get("remote_plan_and_code_verified_before_summary") is True or
                receipt.get("remote_Git_lock_verified_before_inference") is True)
    require(verified, "Remote plan/code verification flag missing")
    commit = receipt.get("commit", receipt.get("lock_commit_sha", ""))
    require(bool(re.fullmatch(r"[0-9a-f]{40}", commit)), "Remote lock commit SHA missing")
    require(receipt.get("scope_sha256") == sha(args.scope), "Scope digest mismatch")
    require(receipt.get("locked_file_manifest_sha256") == sha(args.locked_files), "Locked manifest digest mismatch")
    require(isinstance(locked, dict) and locked, "Nonempty path-to-SHA manifest required")
    own = Path(__file__).resolve()
    own_in_manifest = False
    for name, digest in locked.items():
        path = Path(name).resolve()
        require(sha(path) == digest, "Locked file changed: " + name)
        if path == own:
            own_in_manifest = True
    require(own_in_manifest, "This descriptor script must be pinned in the remote manifest")
    require(sha(args.v4_zip) == V4_SHA, "V4 ZIP pin mismatch")
    require(sha(args.calendar_npz) == CALENDAR_SHA, "Original calendar cache pin mismatch")
    require(sha(args.hidden_npz) == HIDDEN_SHA, "Original hidden cache pin mismatch")
    require(not Path(args.output).exists(), "Output already exists; refusing to overwrite")
    return scope, receipt, {"V4": V4_SHA, "calendar": CALENDAR_SHA, "hidden": HIDDEN_SHA,
                            "descriptor_code": sha(own), "scope": sha(args.scope),
                            "locked_files": sha(args.locked_files)}


def load_npz(path):
    with np.load(path, allow_pickle=False) as source:
        return {k: source[k] for k in source.files}


def validate_pools(calendar, hidden):
    require(calendar["ten_god_names"].tolist() == GODS, "Calendar TG order changed")
    require(calendar["dm_stems"].tolist() == STEMS, "Calendar DM order changed")
    n = len(calendar["dates"])
    expected_dates = []
    cursor = dt.date(1835, 1, 1)
    while cursor <= dt.date(1985, 12, 31):
        expected_dates.append(cursor.isoformat())
        cursor += dt.timedelta(days=1)
    require(calendar["dates"].tolist() == expected_dates, "Calendar date window/order incomplete")
    require(calendar["ten_god_counts"].shape == (n, 10), "Calendar TG dimensions invalid")
    require(np.all(calendar["ten_god_counts"].sum(axis=1) == 5), "Five-position TG sum invalid")
    require(hidden["models"].tolist() == MODELS and hidden["traits"].tolist() == TRAITS, "Hidden axes changed")
    require(hidden["position_denominators"].tolist() == DENOMINATORS, "Hidden model denominators changed")
    require(hidden["scales"].tolist() == [72, 12], "Hidden integer scales changed")
    require(hidden["metrics"].tolist() == ["count_scaled72", "presence_scaled12"], "Hidden metric order changed")
    for key in ["dates", "year", "month", "jie_boundary_day", "jie_boundary_plus_minus_one_civil_day",
                "year_pillar", "month_pillar", "day_pillar"]:
        require(np.array_equal(calendar[key], hidden[key]), "Hidden/calendar alignment changed: " + key)
    count = hidden["count_scaled72"]
    presence = hidden["presence_scaled12"]
    require(count.shape == presence.shape == (n, 8, 2), "Hidden feature shape invalid")
    require(np.array_equal(hidden["features"][..., 0], count), "Hidden count aliases differ")
    require(np.array_equal(hidden["features"][..., 1], presence), "Hidden presence aliases differ")
    require(np.all((count >= 0) & (count <= np.asarray(DENOMINATORS)[None, :, None] * 72)), "Hidden count bounds invalid")
    require(np.all((presence >= 0) & (presence <= 12)), "Hidden presence bounds invalid")
    require(np.array_equal(count[:, 0, 0], calendar["PI_count"].astype(np.int64) * 72), "M0 PI cache reproduction failed")
    require(np.array_equal(count[:, 0, 1], calendar["SG_count"].astype(np.int64) * 72), "M0 SG cache reproduction failed")
    require(np.array_equal(presence[:, :4], (count[:, :4] > 0).astype(np.int16) * 12), "Known-position presence is not its exact indicator")
    return {str(date): i for i, date in enumerate(calendar["dates"])}


def year_expectations(calendar, hidden):
    """Exhaustive within-birthyear calendar expectations, never a 10% shortcut."""
    out = {}
    for year in np.unique(calendar["year"]):
        keep = calendar["year"] == year
        tg = calendar["ten_god_counts"][keep].astype(np.int64)
        out[int(year)] = {
            "dates": int(keep.sum()),
            "TG_count": tg.mean(axis=0),
            "TG_presence": (tg > 0).mean(axis=0),
            "DM": np.bincount(calendar["DM_index"][keep], minlength=10) / int(keep.sum()),
            "basic": calendar["features"][keep, :5].mean(axis=0),
            "hidden_count_scaled72": hidden["count_scaled72"][keep].mean(axis=0),
            "hidden_presence_scaled12": hidden["presence_scaled12"][keep].mean(axis=0),
        }
    return out


def summarize_arrays(rows, indexes, calendar, hidden, expected):
    """One row/person; the five positions never become five observations."""
    n = len(rows)
    require(n > 0, "Cannot summarize empty Nobel source group")
    years = np.asarray([int(r["analysis_DOB"][:4]) for r in rows], dtype=np.int64)
    tg = calendar["ten_god_counts"][indexes].astype(np.int64)
    dm = calendar["DM_index"][indexes].astype(np.int64)
    tge = np.asarray([expected[int(y)]["TG_count"] for y in years])
    tgpe = np.asarray([expected[int(y)]["TG_presence"] for y in years])
    dme = np.asarray([expected[int(y)]["DM"] for y in years])
    hc = hidden["count_scaled72"][indexes].astype(np.int64)
    hp = hidden["presence_scaled12"][indexes].astype(np.int64)
    hce = np.asarray([expected[int(y)]["hidden_count_scaled72"] for y in years])
    hpe = np.asarray([expected[int(y)]["hidden_presence_scaled12"] for y in years])
    basic_observed = calendar["features"][indexes, :5].astype(np.int64)
    basic_expected = np.asarray([expected[int(y)]["basic"] for y in years])
    basic_metrics = {name: {"observed_mean": float(basic_observed[:, j].mean()),
                            "calendar_expected_mean": float(basic_expected[:, j].mean()),
                            "excess_mean": float((basic_observed[:, j] - basic_expected[:, j]).mean()),
                            "observed_sum": int(basic_observed[:, j].sum()),
                            "calendar_expected_sum": float(basic_expected[:, j].sum())}
                     for j, name in enumerate(BASIC_METRICS)}
    gods = []
    for j, label in enumerate(GODS):
        obs, exp = float(tg[:, j].mean()), float(tge[:, j].mean())
        po, pe = float((tg[:, j] > 0).mean()), float(tgpe[:, j].mean())
        gods.append({"label": label, "count_total": int(tg[:, j].sum()),
                     "calendar_expected_count_total": float(tge[:, j].sum()),
                     "mean_count_per_person": obs, "calendar_expected_mean_count": exp,
                     "excess_mean_count": obs - exp,
                     "position_share": obs / 5, "calendar_expected_position_share": exp / 5,
                     "excess_position_share_pp": (obs - exp) * 20,
                     "people_at_least_one": int(np.count_nonzero(tg[:, j] > 0)),
                     "person_presence_probability": po, "calendar_expected_person_presence_probability": pe,
                     "excess_person_presence_pp": (po - pe) * 100,
                     "inferential_p_value_added": False})
    daymasters = []
    counts = np.bincount(dm, minlength=10)
    dm_expected = dme.sum(axis=0)
    for j, label in enumerate(STEMS):
        daymasters.append({"label": label, "people": int(counts[j]), "share": float(counts[j] / n),
                           "calendar_expected_people": float(dm_expected[j]),
                           "calendar_expected_share": float(dm_expected[j] / n),
                           "excess_share_pp": float((counts[j] - dm_expected[j]) * 100 / n),
                           "inferential_p_value_added": False})
    hidden_rows = []
    for model_index, model in enumerate(MODELS):
        denom = DENOMINATORS[model_index]
        for trait_index, trait in enumerate(TRAITS):
            obs = float(hc[:, model_index, trait_index].mean() / 72)
            exp = float(hce[:, model_index, trait_index].mean() / 72)
            po = float(hp[:, model_index, trait_index].mean() / 12)
            pe = float(hpe[:, model_index, trait_index].mean() / 12)
            hidden_rows.append({"model": model, "trait": trait, "label": "偏印" if trait == "PI" else "伤官",
                                "position_denominator": denom,
                                "count_sum_scaled72": int(hc[:, model_index, trait_index].sum()),
                                "presence_sum_scaled12": int(hp[:, model_index, trait_index].sum()),
                                "mean_count_per_person": obs, "calendar_expected_mean_count": exp,
                                "excess_mean_count": obs - exp,
                                "position_share": obs / denom,
                                "calendar_expected_position_share": exp / denom,
                                "excess_position_share_pp": (obs - exp) * 100 / denom,
                                "person_presence_probability": po,
                                "calendar_expected_person_presence_probability": pe,
                                "excess_person_presence_pp": (po - pe) * 100,
                                "presence_interpretation": "known_five_position_indicator_mean" if model_index < 4 else "mean_of_12_uniform_hour_specific_presence_indicators",
                                "inference_role": "descriptive_only_post_academy_reveal_model_sensitivity",
                                "inferential_p_value_added": False})
    decades = []
    for decade in DECADES:
        keep = (years // 10) * 10 == decade
        size = int(keep.sum())
        tg_counts = tg[keep].sum(axis=0)
        dm_counts = np.bincount(dm[keep], minlength=10)
        decades.append({"decade": decade, "people": size,
                        "birth_window_partial": decade in (1830, 1980),
                        "small_bin_n_lt_20": size < 20,
                        "TG_count_totals": tg_counts.tolist(),
                        "TG_calendar_expected_count_totals": tge[keep].sum(axis=0).tolist(),
                        "TG_position_shares": (tg_counts / (size * 5)).tolist() if size else [None] * 10,
                        "TG_presence_people": (tg[keep] > 0).sum(axis=0).tolist(),
                        "TG_calendar_expected_presence_people": tgpe[keep].sum(axis=0).tolist(),
                        "DM_people": dm_counts.tolist(),
                        "DM_calendar_expected_people": dme[keep].sum(axis=0).tolist(),
                        "DM_shares": (dm_counts / size).tolist() if size else [None] * 10,
                        "inferential_p_value_added": False})
    require(sum(x["count_total"] for x in gods) == n * 5, "Observed TG sum lost positions")
    require(sum(x["people"] for x in daymasters) == n, "Observed DM sum lost people")
    require(sum(x["people"] for x in decades) == n, "Decade bins lost people")
    for trait_index, j in [(0, 8), (1, 3)]:
        h = hidden_rows[trait_index]
        g = gods[j]
        require(abs(h["mean_count_per_person"] - g["mean_count_per_person"]) < 1e-12, "M0 observed TG/hidden summary mismatch")
        require(abs(h["calendar_expected_mean_count"] - g["calendar_expected_mean_count"]) < 1e-12, "M0 expected TG/hidden summary mismatch")
        require(abs(h["person_presence_probability"] - g["person_presence_probability"]) < 1e-12, "M0 observed presence mismatch")
        require(abs(h["calendar_expected_person_presence_probability"] - g["calendar_expected_person_presence_probability"]) < 1e-12, "M0 expected presence mismatch")
    memberships = Counter(tag for row in rows for tag in row["qualified_academy_memberships"])
    return {"people": n, "five_position_denominator": n * 5,
            "birth_year_min": int(years.min()), "birth_year_max": int(years.max()),
            "calendar_year_counts": {str(y): int(c) for y, c in sorted(Counter(years.tolist()).items())},
            "person_ids_sha256": hashlib.sha256(("\n".join(sorted(r["person_id"] for r in rows)) + "\n").encode()).hexdigest(),
            "academy_membership_counts_nonexclusive": {c: memberships[c] for c in COUNTRIES},
            "basic_metrics": basic_metrics,
            "TenGod_M0": gods, "DayMaster10": daymasters, "hidden_PI_SG_models": hidden_rows,
            "decade_tables": decades, "inferential_p_values_added": False}


def load_rows(v4_zip, source):
    name = "scientist_north_data_freeze_v4/outputs/" + source + "/Nobel_full_roster_matched_people.jsonl.gz"
    with zipfile.ZipFile(v4_zip) as archive:
        rows = [json.loads(line) for line in gzip.decompress(archive.read(name)).splitlines() if line.strip()]
    require(len(rows) == {"strict": 621, "expanded": 627}[source], "Full official Nobel source population size changed")
    require(len({r["person_id"] for r in rows}) == len(rows), "Duplicate Nobel person ID")
    require(all(r["hemisphere"] == "north" for r in rows), "Non-north Nobel person")
    require(all("1835-01-01" <= r["analysis_DOB"] <= "1985-12-31" for r in rows), "Nobel DOB outside frozen window")
    return sorted(rows, key=lambda row: row["person_id"])


def synthetic_test():
    """Toy data independently exercises every denominator and presence formula."""
    tg = np.asarray([[1, 0, 1, 0, 0, 0, 0, 0, 2, 1],
                     [0, 1, 0, 1, 0, 1, 0, 0, 0, 2],
                     [0, 0, 0, 2, 1, 0, 0, 1, 1, 0]], dtype=np.int64)
    dm_toy = np.asarray([0, 8, 9])
    basic_toy = np.column_stack([tg[:, 8], tg[:, 3], np.zeros(3), np.zeros(3), dm_toy >= 8, dm_toy]).astype(np.int64)
    calendar = {"ten_god_counts": tg, "DM_index": dm_toy, "features": basic_toy}
    hc = np.zeros((3, 8, 2), dtype=np.int64)
    hc[:, 0, 0] = tg[:, 8] * 72
    hc[:, 0, 1] = tg[:, 3] * 72
    hc[:, 1:4, :] = hc[:, 0:1, :]
    # Uniform-hour counts and presences are fractional, deliberately unlike
    # indicator(mean count > 0), while still lying within model bounds.
    hc[:, 4:, :] = np.asarray([[[18, 36]], [[72, 90]], [[36, 18]]])
    hp = (hc > 0).astype(np.int64) * 12
    hp[:, 4:, :] = np.asarray([[[3, 4]], [[12, 9]], [[6, 2]]])
    hidden = {"count_scaled72": hc, "presence_scaled12": hp}
    rows = [{"analysis_DOB": f"1900-01-0{i+1}", "person_id": str(i), "qualified_academy_memberships": []} for i in range(3)]
    expected = {1900: {"TG_count": tg.mean(axis=0), "TG_presence": (tg > 0).mean(axis=0),
                       "DM": np.bincount(calendar["DM_index"], minlength=10) / 3,
                       "basic": basic_toy[:, :5].mean(axis=0),
                       "hidden_count_scaled72": hc.mean(axis=0),
                       "hidden_presence_scaled12": hp.mean(axis=0)}}
    out = summarize_arrays(rows, np.arange(3), calendar, hidden, expected)
    require(out["people"] == 3 and out["five_position_denominator"] == 15, "Toy denominators")
    require(out["TenGod_M0"][8]["count_total"] == 3, "Toy PI count")
    require(out["TenGod_M0"][8]["people_at_least_one"] == 2, "Toy PI presence")
    require(out["TenGod_M0"][3]["count_total"] == 3, "Toy SG count")
    require(out["TenGod_M0"][3]["people_at_least_one"] == 2, "Toy SG presence")
    require(out["TenGod_M0"][8]["position_share"] == 1 / 5, "Toy position share")
    require(out["basic_metrics"]["water_DM"]["observed_sum"] == 2, "Toy basic water count")
    require(abs(out["hidden_PI_SG_models"][8]["person_presence_probability"] - 7 / 12) < 1e-12, "Toy hourly probability")
    require(out["hidden_PI_SG_models"][8]["person_presence_probability"] != 1, "Hourly presence collapsed into indicator of mean")
    require(all(abs(r["excess_mean_count"]) < 1e-12 for r in out["TenGod_M0"]), "Toy expectation identity")
    require(len(out["decade_tables"]) == 16 and out["decade_tables"][7]["people"] == 3, "Toy 1900 bin")
    require(out["decade_tables"][0]["DM_shares"] == [None] * 10, "Empty-bin shares must be undefined")
    require(not out["inferential_p_values_added"], "Unexpected toy inference")
    return {"schema": "Nobel_descriptive_synthetic_QA_v1", "status": "PASS",
            "study_cohort_files_read": False, "synthetic_people": 3,
            "checked": ["person_vs_position_denominators", "TG10_sum5", "DM10_person_sum",
                        "full16_decades_including_empty", "PI_SG_M0_hidden_consistency",
                        "hour_presence_mean_not_indicator_of_mean", "exact_calendar_expectation_identity",
                        "no_additional_inference"]}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--self-test", action="store_true")
    p.add_argument("--self-test-output")
    p.add_argument("--scope")
    p.add_argument("--locked-files")
    p.add_argument("--execution-receipt")
    p.add_argument("--v4-zip")
    p.add_argument("--calendar-npz")
    p.add_argument("--hidden-npz")
    p.add_argument("--output")
    args = p.parse_args()
    if args.self_test:
        result = synthetic_test()
        if args.self_test_output:
            Path(args.self_test_output).parent.mkdir(parents=True, exist_ok=True)
            Path(args.self_test_output).write_text(canonical(result))
        print(canonical(result), end="")
        return
    for name in ["scope", "locked_files", "execution_receipt", "v4_zip", "calendar_npz", "hidden_npz", "output"]:
        require(bool(getattr(args, name)), "Required argument missing: " + name)
    scope, receipt, hashes = verify_gate(args)
    calendar, hidden = load_npz(args.calendar_npz), load_npz(args.hidden_npz)
    index = validate_pools(calendar, hidden)
    expected = year_expectations(calendar, hidden)
    populations = {source: load_rows(args.v4_zip, source) for source in ["strict", "expanded"]}
    require({r["person_id"] for r in populations["strict"]}.issubset({r["person_id"] for r in populations["expanded"]}), "Strict not subset of expanded")
    expanded_dates = {r["person_id"]: r["analysis_DOB"] for r in populations["expanded"]}
    require(all(expanded_dates[r["person_id"]] == r["analysis_DOB"] for r in populations["strict"]), "Shared-source DOB changed")
    groups = {}
    for source, rows in populations.items():
        indexes = np.asarray([index[r["analysis_DOB"]] for r in rows], dtype=np.int64)
        groups[source] = summarize_arrays(rows, indexes, calendar, hidden, expected)
    result = {"schema": "Nobel_descriptive_tables_v1", "population": "Nobel_full_roster_matched_people",
              "source_order": ["strict", "expanded"], "TenGod_order": GODS, "DayMaster_order": STEMS,
              "hidden_model_order": MODELS, "hidden_trait_order": TRAITS, "decade_bins": DECADES,
              "groups": groups, "source_and_code_sha256": hashes,
              "inference_role": "descriptive_only; original_global18_results_remain_separate",
              "hidden_model_inference_role": "post_academy_reveal_model_sensitivity; not_original_global18",
              "new_p_values_or_trend_tests_computed": False,
              "independent_replication_claim": False,
              "interpretation": {"count_unit": "one_person_with_five_known_positions; day_stem_reference_excluded",
                                 "calendar": "each_person_birthyear_uniform_all_valid_dates; exhaustive_expectations",
                                 "known_models": "year_stem,year_branch,month_stem,month_branch,day_branch",
                                 "hour_models": "known5_plus_hourstem_hourbranch; mean_over12_uniform_doublehours",
                                 "hour_probability": "mean_of_hour_specific_presence_indicators; no_actual_birthhour",
                                 "priority": "first_exposed_in_frozen_main_middle_residual_order; fallback_main",
                                 "share": "equal_share_among_exposed; fallback_main",
                                 "any": "branch_trait_present_if_any_exposed_matching_trait; fallback_main",
                                 "expanded": "source_sensitivity_contains_strict; not_independent_validation",
                                 "small_decade_bins": "descriptive_only; no_local_or_trend_p_values"},
              "execution_receipt": receipt, "scope": scope,
              "completed_utc": dt.datetime.now(dt.timezone.utc).isoformat()}
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(canonical(json_safe(result)))
    print(canonical({"status": "PASS", "output": args.output, "N": {k: v["people"] for k, v in groups.items()},
                     "new_p_values": 0}), end="")


if __name__ == "__main__":
    main()
