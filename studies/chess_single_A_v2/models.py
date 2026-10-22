"""The prespecified estimators for chess single-player analysis A.

Inputs are already deterministic raw-symbol or date matrices. Every learned
input transformation and target transformation belongs to the returned
estimator, so cloning/fitting it in a training fold keeps preprocessing local.
This module never loads study data or chooses a model from evaluation scores.
"""
from __future__ import annotations

from copy import deepcopy
from itertools import product
import warnings

import numpy as np
from sklearn.base import BaseEstimator, RegressorMixin
from sklearn.compose import TransformedTargetRegressor
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.exceptions import ConvergenceWarning
from sklearn.kernel_ridge import KernelRidge
from sklearn.linear_model import Ridge
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import PolynomialFeatures, StandardScaler
from sklearn.utils.validation import check_is_fitted, validate_data
from threadpoolctl import threadpool_limits


class MeanSeedMLPRegressor(RegressorMixin, BaseEstimator):
    """Average every configured initialization, without selecting a seed.

    Constructor parameters are retained unchanged for sklearn.clone. Fitted
    estimators are separate objects, making the complete ensemble portable in
    joblib artifacts rather than depending on an external prediction cache.
    """

    def __init__(self, mlp_params, random_states):
        self.mlp_params = mlp_params
        self.random_states = random_states

    def fit(self, X, y):
        X, y = validate_data(self, X, y, y_numeric=True)
        seeds = list(self.random_states)
        if not seeds or len(seeds) != len(set(seeds)):
            raise ValueError("MLP seeds must be nonempty and distinct")
        if "random_state" in self.mlp_params:
            raise ValueError("MLP random_state must come only from random_states")
        self.estimators_ = []
        for seed in seeds:
            model = MLPRegressor(random_state=seed, **self.mlp_params)
            model.fit(X, y)
            self.estimators_.append(model)
        return self

    def predict(self, X):
        check_is_fitted(self, "estimators_")
        X = validate_data(self, X, reset=False)
        predictions = np.stack([model.predict(X) for model in self.estimators_])
        if not np.isfinite(predictions).all():
            raise ValueError("Nonfinite MLP seed prediction")
        return predictions.mean(axis=0)


def candidate_configs(config):
    """Enumerate the finite search in written family/grid insertion order."""
    candidates = []
    seen_families = set()
    for family in config["families"]:
        name = family["name"]
        if name in seen_families:
            raise ValueError(f"Duplicate family: {name}")
        seen_families.add(name)
        grid = family["grid"]
        names = list(grid)
        values = [grid[key] for key in names]
        if any(not isinstance(items, list) or not items for items in values):
            raise ValueError(f"Every grid axis must be a nonempty list: {name}")
        for number, chosen in enumerate(product(*values)):
            candidates.append({
                "candidate_id": f"{name}_{number:03d}",
                "family": name,
                "params": {key: deepcopy(value) for key, value in zip(names, chosen)},
            })
    return candidates


def build_estimator(candidate, config):
    """Build one complete estimator, with all numerical settings from config."""
    name = candidate["family"]
    matches = [item for item in config["families"] if item["name"] == name]
    if len(matches) != 1:
        raise ValueError(f"Unknown or duplicated family: {name}")
    family = matches[0]
    params = deepcopy(candidate["params"])
    fixed = deepcopy(family["fixed"])
    if set(params) != set(family["grid"]):
        raise ValueError(f"Candidate parameters do not match configured grid: {name}")
    for key, value in params.items():
        if value not in family["grid"][key]:
            raise ValueError(f"Candidate value outside configured grid: {name}/{key}")
    if set(params) & set(fixed):
        raise ValueError(f"Candidate overrides a fixed parameter: {name}")

    steps = []
    if name == "pairwise_ridge":
        if fixed.pop("retain_main_effects") is not True:
            raise ValueError("The locked pairwise model must retain main effects")
        expansion = {key: fixed.pop(key) for key in
                     ("degree", "interaction_only", "include_bias")}
        steps.append(("interactions", PolynomialFeatures(**expansion)))
        estimator = Ridge(**fixed, **params)
    elif name == "ridge":
        estimator = Ridge(**fixed, **params)
    elif name == "rbf_kernel_ridge":
        estimator = KernelRidge(**fixed, **params)
    elif name == "shallow_gradient_boosting":
        estimator = GradientBoostingRegressor(**fixed, **params)
    elif name == "small_mlp":
        seeds = fixed.pop("random_states")
        fixed.pop("seed_policy")  # Human-readable protocol metadata, not a kwarg.
        if len(seeds) != 3 or len(set(seeds)) != 3:
            raise ValueError("The locked MLP averages all three distinct seeds")
        params["hidden_layer_sizes"] = tuple(params["hidden_layer_sizes"])
        estimator = MeanSeedMLPRegressor(
            mlp_params={**fixed, **params}, random_states=tuple(seeds))
    else:
        raise ValueError(f"Unsupported family: {name}")

    if name != "shallow_gradient_boosting":
        steps.append(("scale", StandardScaler()))
    steps.append(("regressor", estimator))
    return TransformedTargetRegressor(
        regressor=Pipeline(steps), transformer=StandardScaler())


def fit_with_diagnostics(estimator, X, y, *, threads=1):
    """Fit without rescuing failures; retain finite fits with their warnings.

    Numerical/fit/prediction exceptions propagate to the search procedure. It
    must invalidate that candidate for the whole inner search and must also
    reject nonfinite held-out predictions. This helper checks training output
    as an additional finite-fit safeguard, not a model-selection score.
    """
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        with threadpool_limits(limits=threads):
            estimator.fit(X, y)
            prediction = np.asarray(estimator.predict(X), dtype=float)
        if prediction.shape != np.asarray(y).shape or not np.isfinite(prediction).all():
            raise ValueError("Fitted estimator produced invalid training predictions")
    diagnostics = {
        "warnings": [{"category": item.category.__name__, "message": str(item.message)}
                     for item in captured],
        "convergence_warnings": sum(issubclass(item.category, ConvergenceWarning)
                                    for item in captured),
        "finite_training_predictions": True,
        "threads": threads,
    }
    return estimator, diagnostics
