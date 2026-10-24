"""Fixed descriptive Shangguan associations; never select predictive models."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

STEMS = "甲乙丙丁戊己庚辛壬癸"
MAIN_QI = dict(zip("子丑寅卯辰巳午未申酉戌亥", "癸己甲乙戊丙丁己庚辛戊壬"))
ROLES = ("development", "primary_new")
FEATURES = ("month_main_shangguan", "five_position_shangguan_count")
REFERENCE_DATE = pd.Timestamp("2024-01-01")
REQUIRED = ("canonical_id", "exact_dob_frozen", "rating", "year_stem", "year_branch",
            "month_stem", "month_branch", "day_stem", "day_branch")


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def is_shangguan(day_stem, candidate_stem):
    if day_stem not in STEMS or candidate_stem not in STEMS or len(day_stem) != 1 or len(candidate_stem) != 1:
        raise ValueError("Unknown heavenly stem")
    day, other = STEMS.index(day_stem), STEMS.index(candidate_stem)
    return int((other // 2 - day // 2) % 5 == 1 and other % 2 != day % 2)


def derive_values(frame):
    """Validate all people, then derive the two fixed, unweighted definitions."""
    if not set(REQUIRED).issubset(frame.columns):
        raise ValueError("Missing required frozen person or rating fields")
    if frame.empty or frame[list(REQUIRED)].isna().any().any():
        raise ValueError("Empty frame or missing person data")
    out = frame[list(REQUIRED)].copy()
    out["canonical_id"] = out.canonical_id.astype(str).str.strip()
    if out.canonical_id.eq("").any() or out.canonical_id.duplicated().any():
        raise ValueError("Empty or duplicate canonical identity")
    out["rating"] = pd.to_numeric(out.rating, errors="raise")
    if not np.isfinite(out.rating).all() or (out.rating <= 0).any():
        raise ValueError("Invalid peak rating")
    dates = pd.to_datetime(out.exact_dob_frozen, format="%Y-%m-%d", errors="raise")
    out["age_at_2024_01_01"] = (REFERENCE_DATE - dates).dt.days / 365.2425
    if (out.age_at_2024_01_01 < 0).any():
        raise ValueError("Birth date follows rating cutoff")
    for name in ("year_stem", "month_stem", "day_stem"):
        if not out[name].isin(list(STEMS)).all():
            raise ValueError("Unknown heavenly stem")
    for name in ("year_branch", "month_branch", "day_branch"):
        if not out[name].isin(MAIN_QI).all():
            raise ValueError("Unknown earthly branch")
    indicators = []
    for row in out.itertuples(index=False):
        stems = (row.year_stem, MAIN_QI[row.year_branch], row.month_stem,
                 MAIN_QI[row.month_branch], MAIN_QI[row.day_branch])
        indicators.append([is_shangguan(row.day_stem, stem) for stem in stems])
    indicators = np.asarray(indicators, dtype=int)
    out[FEATURES[0]] = indicators[:, 3]
    out[FEATURES[1]] = indicators.sum(axis=1)
    return out


def correlation(x, y):
    x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    if len(x) < 2 or np.ptp(x) == 0 or np.ptp(y) == 0:
        return {"status": "unavailable_constant_or_too_small", "r": None, "ci95_low": None, "ci95_high": None}
    r = float(np.clip(np.corrcoef(x, y)[0, 1], -1, 1))
    lower = upper = None
    if len(x) > 3:
        if abs(r) == 1:
            lower = upper = r
        else:
            z = np.arctanh(r)
            delta = stats.norm.ppf(.975) / np.sqrt(len(x) - 3)
            lower, upper = [float(v) for v in np.tanh([z - delta, z + delta])]
    return {"status": "available", "r": r, "ci95_low": lower, "ci95_high": upper}


def ols_hc3(x, y, age=None):
    """Elo per unit of x with HC3 covariance; no predictive tuning or p-value."""
    x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    nuisance = np.ones((len(x), 1))
    if age is not None:
        centered = np.asarray(age, dtype=float) - np.mean(age)
        nuisance = np.column_stack((nuisance, centered, centered ** 2))
    design = np.column_stack((nuisance[:, 0], x, nuisance[:, 1:]))
    n, p = design.shape
    unavailable = {"status": "unavailable_rank_or_sample_size", "elo_per_unit": None,
                   "ci95_low": None, "ci95_high": None, "hc3_standard_error": None,
                   "partial_r": None, "n": n, "residual_df": n - p}
    if n <= p or np.linalg.matrix_rank(design) != p:
        return unavailable
    beta = np.linalg.lstsq(design, y, rcond=None)[0]
    inverse = np.linalg.inv(design.T @ design)
    residual = y - design @ beta
    leverage = np.einsum("ij,jk,ik->i", design, inverse, design)
    if np.any(1 - leverage <= 1e-10):
        return {**unavailable, "status": "unavailable_unit_leverage"}
    squared = (residual / (1 - leverage)) ** 2
    covariance = inverse @ (design.T @ (squared[:, None] * design)) @ inverse
    se = float(np.sqrt(max(0., covariance[1, 1])))
    delta = float(stats.t.ppf(.975, n - p) * se)
    partial = None
    if age is not None:
        rx = x - nuisance @ np.linalg.lstsq(nuisance, x, rcond=None)[0]
        ry = y - nuisance @ np.linalg.lstsq(nuisance, y, rcond=None)[0]
        if np.std(rx) > 1e-12 and np.std(ry) > 1e-12:
            partial = correlation(rx, ry)["r"]
    return {"status": "available", "elo_per_unit": float(beta[1]),
            "ci95_low": float(beta[1] - delta), "ci95_high": float(beta[1] + delta),
            "hc3_standard_error": se, "partial_r": partial, "n": n, "residual_df": n - p}


def analyze_cohort(frame, role):
    data = derive_values(frame)
    results = []
    for feature in FEATURES:
        x, y = data[feature].to_numpy(float), data.rating.to_numpy(float)
        groups = [{"level": int(level), "n": int(len(group)), "mean_peak_elo": float(group.rating.mean()),
                   "median_peak_elo": float(group.rating.median())}
                  for level, group in data.groupby(feature, sort=True)]
        spearman = None
        if feature == FEATURES[1] and np.ptp(x) > 0 and np.ptp(y) > 0:
            spearman = float(stats.spearmanr(x, y).statistic)
        results.append({"role": role, "feature": feature, "n": len(data), "groups": groups,
                        "pearson": correlation(x, y), "spearman_r": spearman,
                        "raw": ols_hc3(x, y),
                        "age_adjusted": ols_hc3(x, y, data.age_at_2024_01_01.to_numpy(float))})
    data.insert(0, "role", role)
    return results, data


def effect_rows(results):
    rows = []
    for result in results:
        for adjustment in ("raw", "age_adjusted"):
            rows.append({"role": result["role"], "feature": result["feature"], "adjustment": adjustment,
                         **result[adjustment], "pearson_r": result["pearson"]["r"],
                         "pearson_ci95_low": result["pearson"]["ci95_low"],
                         "pearson_ci95_high": result["pearson"]["ci95_high"],
                         "spearman_r": result["spearman_r"]})
    return rows


def format_number(value, digits=2):
    return "unavailable" if value is None else f"{value:.{digits}f}"


def render_report(summary):
    lines = ["# Shangguan and observed peak Elo", "",
             "Exploratory description fixed before inspecting these associations. Earlier snapshot results were seen. "
             "Cohorts are analyzed separately; this is not a new blind preregistration or a causal result.", "",
             "Peak means the highest audited published standard rating recorded through December 2023. "
             "Age is measured at the common 2024-01-01 boundary. No predictive model was trained.", "",
             "Primary: month-branch main qi is Shangguan (0/1). Secondary: Shangguan count in the five effective "
             "positions (year stem, year-branch main qi, month stem, month-branch main qi, day-branch main qi). "
             "No hidden-stem or position weights are tuned.", "",
             "| Cohort | Definition | N | Pearson r (95% interval) | Raw Elo/unit (95% HC3 interval) | Age-adjusted Elo/unit (95% HC3 interval) | Partial r |",
             "|---|---|---:|---|---|---|---|"]
    for item in summary["results"]:
        c, raw, adj = item["pearson"], item["raw"], item["age_adjusted"]
        f = format_number
        lines.append(f"| {item['role']} | {item['feature']} | {item['n']} | "
                     f"{f(c['r'],3)} [{f(c['ci95_low'],3)}, {f(c['ci95_high'],3)}] | "
                     f"{f(raw['elo_per_unit'])} [{f(raw['ci95_low'])}, {f(raw['ci95_high'])}] | "
                     f"{f(adj['elo_per_unit'])} [{f(adj['ci95_low'])}, {f(adj['ci95_high'])}] | {f(adj['partial_r'],3)} |")
    lines += ["", "## Group descriptions", "",
              "| Cohort | Definition | Level | N | Mean peak Elo | Median peak Elo |",
              "|---|---|---:|---:|---:|---:|"]
    for item in summary["results"]:
        for group in item["groups"]:
            lines.append(f"| {item['role']} | {item['feature']} | {group['level']} | {group['n']} | "
                         f"{group['mean_peak_elo']:.2f} | {group['median_peak_elo']:.2f} |")
    lines += ["", "Secondary count Spearman correlations: " + "; ".join(
        f"{item['role']} {format_number(item['spearman_r'],3)}" for item in summary["results"]
        if item["feature"] == FEATURES[1]) + ".", "",
        "The adjusted description includes centered age and age squared. All people are retained. "
        "Unavailable estimates are explicitly marked in summary.json and effects.csv.", "",
        "Intervals are descriptive and unadjusted for multiple estimates. A positive point estimate with an interval "
        "including zero is uncertain. Selection into elite chess, birth-calendar structure, omitted factors and unfinished "
        "careers limit interpretation; age adjustment does not resolve all of them. The two definitions are related. "
        "No confirmatory p-values, causal claims, age exclusions or model-selection decisions are made here.", "",
        "Input manifest SHA256: `" + summary["provenance"]["data_manifest_sha256"] + "`.", ""]
    return "\n".join(lines)


def run(root, output_dir):
    from peak_data import load_frame
    root, output_dir = Path(root).resolve(), Path(output_dir).resolve()
    results, people, identities = [], [], []
    for role in ROLES:
        role_results, data = analyze_cohort(load_frame(root, role), role)
        expected = {"development": 1000, "primary_new": 500}[role]
        if len(data) != expected:
            raise ValueError("Frozen cohort count differs")
        results.extend(role_results)
        people.append(data)
        identities.append(set(data.canonical_id))
    if identities[0] & identities[1]:
        raise ValueError("Person overlap between fixed cohorts")
    here = Path(__file__).resolve()
    summary = {"protocol_id": "chess-peak-shangguan-description-v1", "status": "complete",
               "exploratory": True, "new_blind_preregistration_claimed": False,
               "predictive_model_fitting_performed": False, "age_reference_date": "2024-01-01",
               "provenance": {"data_manifest_sha256": sha256(root / "studies/chess_peak_v1/data/data_manifest.json"),
                              "script_sha256": sha256(here), "plan_sha256": sha256(here.with_name("SHANGGUAN_PLAN.md"))},
               "results": results}
    output_dir.mkdir(parents=True, exist_ok=True)
    pd.concat(people, ignore_index=True).to_csv(output_dir / "per_person_shangguan.csv", index=False)
    pd.DataFrame(effect_rows(results)).to_csv(output_dir / "effects.csv", index=False)
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    (output_dir / "REPORT.md").write_text(render_report(summary), encoding="utf-8")
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.repo_root, args.output_dir)
    print(json.dumps({"status": result["status"], "cohort_feature_estimates": len(result["results"])}))


if __name__ == "__main__":
    main()
