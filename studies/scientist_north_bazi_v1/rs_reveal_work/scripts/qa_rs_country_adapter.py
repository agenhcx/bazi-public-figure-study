#!/usr/bin/env python3
"""Pure synthetic checks for the UK adapter; no study data are read."""
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
ADAPTER = ROOT / "rs_reveal_work/scripts/analyze_rs_country.py"
ORIGINAL_COMMIT = "327cc1382828b2159a55db9c3a20231c1546345a"
ORIGINAL_PATH = "studies/scientist_north_bazi_v1/reveal_v1/scripts/analyze_country.py"


def main():
    original = subprocess.check_output(["git", "-C", str(ROOT / "academy_repo"), "show", ORIGINAL_COMMIT + ":" + ORIGINAL_PATH])
    assert hashlib.sha256(original).hexdigest() == "c24b25271c3ca8a3e3a870d2476f7d2c2596f457a1232ef5b1bd85f71c9e42fe"
    extract = lambda src: {n.name: ast.dump(n, include_attributes=False) for n in ast.parse(src).body if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
    before, after = extract(original.decode()), extract(ADAPTER.read_text())
    unchanged = ["load_pool", "observed_arrays", "CalendarModel", "mc_tests", "bootstrap_intervals", "descriptive", "run_case", "json_safe"]
    assert all(before[name] == after[name] for name in unchanged)
    spec = importlib.util.spec_from_file_location("rs_country_synthetic_module", ADAPTER)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    assert m.COUNTRIES.index("UK_Royal_Society") == 1 and m.BONFERRONI_FAMILY_SIZE == 36
    assert m.REPLICATES == 99999 and m.BOOTSTRAPS == 10000
    # Artificial independent fixtures: ten dates, one of each day stem.
    n = 10
    features = np.zeros((n, 6), dtype=np.int8)
    gods = np.zeros((n, 10), dtype=np.int8)
    gods[:, 0] = 5
    for i in range(0, n, 2):
        gods[i, 0], gods[i, 7], gods[i, 9] = 3, 1, 1
        features[i, 2] = 1
    features[:, 4] = np.arange(n) >= 8
    features[:, 5] = np.arange(n)
    pool = {"dates": np.asarray([f"2000-01-{i+1:02d}" for i in range(n)]),
            "year": np.full(n, 2000), "month": np.ones(n), "features": features,
            "GY_broad": features[:, 2].astype(bool), "SGY_broad": features[:, 3].astype(bool),
            "ten_god_counts": gods, "jie_boundary_plus_minus_one_civil_day": np.zeros(n, dtype=bool)}
    people = [{"person_id": f"toy_{i}", "analysis_DOB": str(pool["dates"][i])} for i in range(n)]
    rows = [m._pool_observation(person, i, pool, {"toy_0"}, {"toy_0", "toy_1"}) for i, person in enumerate(people)]
    assert rows[0]["Fields_parallel"] and not rows[1]["Fields_parallel"]
    assert rows[0]["included_expanded_without_LOC"] and not rows[2]["included_expanded_without_LOC"]
    assert rows[0]["assumptions_lock_commit"] == "6d02e0e4f22da59d171888d75a5163bb1ee410d8"
    observed, counted = m.observed_arrays(rows)
    assert np.array_equal(observed, features) and np.array_equal(counted, gods)
    model = m.CalendarModel(pool)
    expected, dm, expected_gods = model.expectations(rows)
    assert np.allclose(expected.mean(axis=0), features[:, :5].mean(axis=0))
    assert np.allclose(dm.sum(axis=0), np.ones(n))
    # Smoke test in a synthetic-only process; real-run constants remain pinned.
    m.REPLICATES = 9999
    first = m.mc_tests(rows, observed, dm, model, 1)
    second = m.mc_tests(rows, observed, dm, model, 1)
    assert first == second
    assert [x["seed"] for x in first] == list(range(2026111400, 2026111406))
    assert first[0]["p_nominal_plus_one"] == first[1]["p_nominal_plus_one"] == first[5]["p_nominal_plus_one"] == 1.
    assert all(x["p_Bonferroni_36_reference"] == min(1., 36 * x["p_nominal_plus_one"]) for x in first)
    intervals = m.bootstrap_intervals(observed, expected, 0, 1)
    assert intervals["seed"] == 202611150100 and intervals["replicates"] == 10000
    assert intervals["raw_mean_CI"].shape == (5, 2) and intervals["excess_mean_CI"].shape == (5, 2)
    desc = m.descriptive(rows, model)
    assert desc["n"] == 10 and len(desc["ten_gods_five_position_descriptive_only"]) == 10
    assert all(x["observed_people"] == 1 for x in desc["day_master_distribution"])
    result = {"schema": "RS_country_adapter_synthetic_QA_v1", "status": "PASS", "study_inputs_loaded": False,
              "original_statistical_functions_AST_identical": unchanged,
              "original_engine_sha256": hashlib.sha256(original).hexdigest(),
              "adapter_sha256": hashlib.sha256(ADAPTER.read_bytes()).hexdigest(),
              "UK_country_index": 1, "original_MC_replicates": 99999,
              "UK_MC_seeds": list(range(2026111400, 2026111406)),
              "synthetic_MC_replicates_only": 9999,
              "original_bootstrap_replicates": 10000, "bootstrap_UK_primary_seed": 202611150100,
              "carrier_conversion_and_fields_LOC_synthetic": True,
              "deterministic_tie_inclusive_MC": True, "Bonferroni36_preserved": True}
    out = ROOT / "rs_reveal_work/COUNTRY_SYNTHETIC_QA.json"
    assert not out.exists()
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
