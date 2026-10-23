"""Frozen B1 encodings and Ridge estimators; no data reads or research fits.

The three structural parameters change pooled input strengths, not the sign or
magnitude of their eventual effect on Elo.  Raw symbols remain in B1 so the
Ridge readout can also use distinctions absent from the pooled representation.
"""
from __future__ import annotations

import calendar
from datetime import date
from itertools import product
import math
from numbers import Real
import re

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.compose import TransformedTargetRegressor
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


STEMS = tuple("甲乙丙丁戊己庚辛壬癸")
BRANCHES = tuple("子丑寅卯辰巳午未申酉戌亥")
PHASES = ("wood", "fire", "earth", "metal", "water")
RAW_COLUMNS = ("year_stem", "year_branch", "month_stem", "month_branch",
               "day_stem", "day_branch")
DATE_COLUMNS = ("exact_dob_frozen", "snapshot")
STEM_PHASE = {stem: index // 2 for index, stem in enumerate(STEMS)}

# Ordered roles: main, middle, residual. A two-stem branch's second stem is
# explicitly middle; missing roles are omitted before normalization. This is
# an operational convention frozen for B1, including 巳 = 丙, 戊, 庚.
HIDDEN_STEMS = {
    "子": ("癸",), "丑": ("己", "癸", "辛"), "寅": ("甲", "丙", "戊"),
    "卯": ("乙",), "辰": ("戊", "乙", "癸"), "巳": ("丙", "戊", "庚"),
    "午": ("丁", "己"), "未": ("己", "丁", "乙"), "申": ("庚", "壬", "戊"),
    "酉": ("辛",), "戌": ("戊", "辛", "丁"), "亥": ("壬", "甲"),
}
DATE_FEATURE_NAMES = ("age", "age_squared", "age_cubed", "birth_season_sin1",
                      "birth_season_cos1", "birth_season_sin2", "birth_season_cos2")


def _finite_number(value, name: str) -> float:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite real number")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be a finite real number")
    return result


def _validate_structure(middle, residual_ratio, month) -> tuple[float, float, float]:
    middle = _finite_number(middle, "middle")
    residual_ratio = _finite_number(residual_ratio, "residual_ratio")
    month = _finite_number(month, "month")
    if not 0 < middle < 1:
        raise ValueError("middle must satisfy 0 < middle < 1")
    if not 0 < residual_ratio < 1:
        raise ValueError("residual_ratio must satisfy 0 < residual_ratio < 1")
    if not 0 < middle * residual_ratio < middle:
        raise ValueError("Weights must satisfy 1 > middle > middle*residual_ratio > 0")
    if month < 1:
        raise ValueError("month must be at least 1")
    return middle, residual_ratio, month


def _require_frame(frame: pd.DataFrame, columns: tuple[str, ...]) -> None:
    if not isinstance(frame, pd.DataFrame):
        raise TypeError("Feature input must be a pandas DataFrame")
    if not frame.columns.is_unique:
        raise ValueError("Feature input must have unique column names")
    for column in columns:
        if column not in frame:
            raise ValueError(f"Missing feature column {column}")


def _symbol_indices(frame: pd.DataFrame) -> list[np.ndarray]:
    _require_frame(frame, RAW_COLUMNS)
    indices = []
    for position, column in enumerate(RAW_COLUMNS):
        lookup = {symbol: i for i, symbol in enumerate(STEMS if position % 2 == 0 else BRANCHES)}
        values = frame[column].tolist()
        if any(not isinstance(value, str) or value not in lookup for value in values):
            raise ValueError(f"Unknown or missing symbol in {column}")
        indices.append(np.asarray([lookup[value] for value in values], dtype=np.int64))
    return indices


def _raw_matrix(indices: list[np.ndarray], n_rows: int) -> np.ndarray:
    matrix = np.zeros((n_rows, 66), dtype=np.float64)
    rows = np.arange(n_rows)
    offset = 0
    for position, values in enumerate(indices):
        matrix[rows, offset + values] = 1.0
        offset += 10 if position % 2 == 0 else 12
    return matrix


def branch_phase_mixtures(middle: float, residual_ratio: float) -> np.ndarray:
    """Return branch-by-phase fractions after normalizing active hidden roles."""
    middle, residual_ratio, _ = _validate_structure(middle, residual_ratio, 1)
    role_weights = np.asarray((1.0, middle, middle * residual_ratio))
    result = np.zeros((12, 5), dtype=np.float64)
    for branch_index, branch in enumerate(BRANCHES):
        stems = HIDDEN_STEMS[branch]
        weights = role_weights[:len(stems)]
        for stem, weight in zip(stems, weights / weights.sum()):
            result[branch_index, STEM_PHASE[stem]] += weight
    return result


def _date_matrix(frame: pd.DataFrame) -> np.ndarray:
    """Mirror A1's seven Gregorian controls exactly, without any disk reads."""
    _require_frame(frame, DATE_COLUMNS)
    rows = []
    for dob_value, snapshot_value in frame.loc[:, DATE_COLUMNS].itertuples(index=False, name=None):
        dob_text, snapshot_text = str(dob_value), str(snapshot_value)
        dob = date.fromisoformat(dob_text)
        if dob.isoformat() != dob_text:
            raise ValueError("DOB must be canonical YYYY-MM-DD")
        if not re.fullmatch(r"[0-9]{4}-[0-9]{2}", snapshot_text):
            raise ValueError(f"Invalid snapshot month: {snapshot_text!r}")
        snapshot = date.fromisoformat(snapshot_text + "-01")
        if snapshot.strftime("%Y-%m") != snapshot_text:
            raise ValueError("Noncanonical snapshot month")
        if dob > snapshot:
            raise ValueError("DOB after snapshot")
        age = (snapshot - dob).days / 365.2425
        phase = 2 * math.pi * (dob.timetuple().tm_yday - 1) / (366 if calendar.isleap(dob.year) else 365)
        rows.append((age, age * age, age * age * age, math.sin(phase), math.cos(phase),
                     math.sin(2 * phase), math.cos(2 * phase)))
    return np.asarray(rows, dtype=np.float64).reshape(len(frame), 7)


class B1FeatureTransformer(TransformerMixin, BaseEstimator):
    """Stateless raw66, B1 raw66+20, or exact A1 date7 feature encoding.

    Main/middle/residual weights are 1, m, m*q. Each branch has unit total
    strength before the month branch alone is multiplied by ``month``.
    Pooling the three stems and branches precedes division by 5+month and
    StandardScaler. Day-centered offsets follow wood/fire/earth/metal/water:
    same, produces, controls, controlled-by, produced-by. Generation/control
    products use absolute phase fractions, not day-centered fractions.
    """

    def __init__(self, middle=.5, residual_ratio=.5, month=1, representation="b1"):
        self.middle = middle
        self.residual_ratio = residual_ratio
        self.month = month
        self.representation = representation

    def _validate_configuration(self) -> tuple[float, float, float]:
        if self.representation not in ("b1", "raw", "date"):
            raise ValueError("representation must be one of b1, raw, date")
        return _validate_structure(self.middle, self.residual_ratio, self.month)

    def fit(self, X: pd.DataFrame, y=None):
        # y is intentionally unused: neither the fixed vocabulary nor pooling
        # statistics are learned from labels (or from the other frame columns).
        self.transform(X)
        columns = DATE_COLUMNS if self.representation == "date" else RAW_COLUMNS
        self.n_features_in_ = len(columns)
        self.feature_names_in_ = np.asarray(columns, dtype=object)
        return self

    def transform(self, X: pd.DataFrame) -> np.ndarray:
        middle, residual_ratio, month = self._validate_configuration()
        if self.representation == "date":
            return _date_matrix(X)
        indices = _symbol_indices(X)
        raw = _raw_matrix(indices, len(X))
        if self.representation == "raw":
            return raw

        identity = np.eye(5, dtype=np.float64)
        # Visible stems are always unweighted, including the month stem.
        totals = sum(identity[indices[position] // 2] for position in (0, 2, 4))
        mixtures = branch_phase_mixtures(middle, residual_ratio)
        totals += mixtures[indices[1]] + month * mixtures[indices[3]] + mixtures[indices[5]]
        fractions = totals / (5.0 + month)
        day_phase = indices[4] // 2
        centered_indices = (day_phase[:, None] + np.arange(5)) % 5
        centered = fractions[np.arange(len(X))[:, None], centered_indices]
        generation = fractions * np.roll(fractions, -1, axis=1)
        control = fractions * np.roll(fractions, -2, axis=1)
        return np.column_stack((raw, fractions, centered, generation, control))

    def get_feature_names_out(self, input_features=None) -> np.ndarray:
        self._validate_configuration()
        if self.representation == "date":
            return np.asarray(DATE_FEATURE_NAMES, dtype=object)
        names = [f"{column}={symbol}" for position, column in enumerate(RAW_COLUMNS)
                 for symbol in (STEMS if position % 2 == 0 else BRANCHES)]
        if self.representation == "b1":
            names += [f"phase_fraction_{phase}" for phase in PHASES]
            names += [f"day_centered_offset_{offset}" for offset in range(5)]
            names += [f"generation_{phase}_to_{PHASES[(i + 1) % 5]}" for i, phase in enumerate(PHASES)]
            names += [f"control_{phase}_to_{PHASES[(i + 2) % 5]}" for i, phase in enumerate(PHASES)]
        return np.asarray(names, dtype=object)


def candidates(config: dict) -> list[dict]:
    """Enumerate B1 then raw/date Ridge candidates in the frozen axis order."""
    grid = config["grid"]
    axes = {name: list(grid[name]) for name in ("middle", "residual_ratio", "month", "alpha")}
    for name, values in axes.items():
        if not values:
            raise ValueError(f"Empty candidate axis {name}")
        if len(values) != len(set(values)):
            raise ValueError(f"Duplicate values on candidate axis {name}")
    alphas = [_finite_number(value, "alpha") for value in axes["alpha"]]
    if any(alpha <= 0 for alpha in alphas):
        raise ValueError("alpha must be positive")
    output = []
    for index, (middle, residual_ratio, month, alpha) in enumerate(product(
            axes["middle"], axes["residual_ratio"], axes["month"], alphas)):
        middle, residual_ratio, month = _validate_structure(middle, residual_ratio, month)
        output.append(dict(candidate_id=f"b1_{index:03d}", representation="b1",
                           middle=middle, residual_ratio=residual_ratio, month=month, alpha=alpha))
    for representation in ("raw", "date"):
        for index, alpha in enumerate(alphas):
            output.append(dict(candidate_id=f"{representation}_{index:03d}",
                               representation=representation, alpha=alpha))
    return output


def build_estimator(candidate: dict) -> TransformedTargetRegressor:
    """Construct the same scaled Ridge readout for all three representations."""
    representation = candidate["representation"]
    parameters = {name: candidate[name] for name in ("middle", "residual_ratio", "month")} if representation == "b1" else {}
    features = B1FeatureTransformer(representation=representation, **parameters)
    features._validate_configuration()
    alpha = _finite_number(candidate["alpha"], "alpha")
    if alpha <= 0:
        raise ValueError("alpha must be positive")
    regressor = Pipeline([
        ("features", features),
        ("scale", StandardScaler()),
        ("regressor", Ridge(alpha=alpha, solver="lsqr", tol=1e-6, max_iter=10000)),
    ])
    return TransformedTargetRegressor(regressor=regressor, transformer=StandardScaler())
