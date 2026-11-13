#!/usr/bin/env python3
"""Pure PI/SG hidden-stem encoders; no dates, astronomy or cohort inputs.

Output axes are model, trait (PI/SG), metric (count_scaled72/presence_scaled12).
The reference Day Stem is excluded as a target position and an exposure source.
Year/Month/Hour positions bearing the same character as it remain visible.
"""

import argparse
from fractions import Fraction
from functools import lru_cache
import json

import numpy as np


STEMS = "甲乙丙丁戊己庚辛壬癸"
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"
STEM_INDEX = {stem: i for i, stem in enumerate(STEMS)}
BRANCH_INDEX = {branch: i for i, branch in enumerate(BRANCHES)}
TEN_GODS = ("比肩", "劫财", "食神", "伤官", "偏财", "正财", "七杀", "正官", "偏印", "正印")
# Exact historical ordered table: main > middle > residual. In particular,
# preserve 巳=丙戊庚 rather than changing order to another convention.
HIDDEN_STEMS = {
    "子": ("癸",), "丑": ("己", "癸", "辛"), "寅": ("甲", "丙", "戊"),
    "卯": ("乙",), "辰": ("戊", "乙", "癸"), "巳": ("丙", "戊", "庚"),
    "午": ("丁", "己"), "未": ("己", "丁", "乙"), "申": ("庚", "壬", "戊"),
    "酉": ("辛",), "戌": ("戊", "辛", "丁"), "亥": ("壬", "甲"),
}
RULE_NAMES = ("main", "priority", "share", "any")
MODEL_NAMES = (
    "M0_5", "M1_priority_5", "M1_share_5", "M1_any_5",
    "M2_main_7", "M3_priority_7", "M3_share_7", "M3_any_7",
)
TRAIT_NAMES = ("PI", "SG")
TRAIT_TEN_GODS = ("偏印", "伤官")
METRIC_NAMES = ("count_scaled72", "presence_scaled12")
COUNT_SCALE = 72
PRESENCE_SCALE = 12
POSITION_DENOMINATORS = (5, 5, 5, 5, 7, 7, 7, 7)
MAX_COUNT_SCALED72 = tuple(COUNT_SCALE * positions for positions in POSITION_DENOMINATORS)


def ten_god(day_stem, other_stem):
    """The frozen ten-stem element/polarity relation, with string inputs."""
    day, other = STEM_INDEX[day_stem], STEM_INDEX[other_stem]
    delta = (other // 2 - day // 2) % 5
    same_polarity = day % 2 == other % 2
    pairs = (("比肩", "劫财"), ("食神", "伤官"), ("偏财", "正财"),
             ("七杀", "正官"), ("偏印", "正印"))
    return pairs[delta][0 if same_polarity else 1]


def hour_stem_index(day_stem_index, hour_branch_index):
    """Five-Rat rule using the actual reference Day Stem; branches 子...亥."""
    day_stem_index, hour_branch_index = int(day_stem_index), int(hour_branch_index)
    if not 0 <= day_stem_index < 10 or not 0 <= hour_branch_index < 12:
        raise ValueError("Stem/branch index outside its canonical domain")
    return (2 * (day_stem_index % 5) + hour_branch_index) % 10


def hour_stem(day_stem, hour_branch):
    return STEMS[hour_stem_index(STEM_INDEX[day_stem], BRANCH_INDEX[hour_branch])]


@lru_cache(maxsize=1)
def _trait_match():
    result = np.asarray([
        [[ten_god(day, other) == trait for trait in TRAIT_TEN_GODS] for other in STEMS]
        for day in STEMS
    ], dtype="int8")
    result.setflags(write=False)
    return result


@lru_cache(maxsize=1)
def _branch_table6():
    """Small pure lookup: rule, DM, visible-stem bitmask, branch, trait.

    Integer units of one sixth represent both 1/2 and 1/3 exposure shares.
    The table enumerates stem masks, not dates or study people.
    """
    table = np.empty((4, 10, 1024, 12, 2), dtype="int8")
    masks = np.arange(1024, dtype="uint16")
    matches = _trait_match()
    for day in range(10):
        for branch_index, branch in enumerate(BRANCHES):
            hidden = np.asarray([STEM_INDEX[stem] for stem in HIDDEN_STEMS[branch]], dtype="uint16")
            exposed = ((masks[:, None] >> hidden[None, :]) & 1).astype(bool)
            exposed_count = exposed.sum(axis=1)
            target = matches[day, hidden].astype("int16")
            main = 6 * target[0]
            table[0, day, :, branch_index] = main
            # argmax gives the first exposed hidden stem in canonical order;
            # all-False masks select index0, exactly the main-qi fallback.
            chosen = exposed.argmax(axis=1)
            table[1, day, :, branch_index] = 6 * target[chosen]
            numerator = exposed.astype("int16") @ target
            share = 6 * numerator // np.maximum(exposed_count[:, None], 1)
            share[exposed_count == 0] = main
            table[2, day, :, branch_index] = share
            any_score = (numerator > 0).astype("int16") * 6
            any_score[exposed_count == 0] = main
            table[3, day, :, branch_index] = any_score
    table.setflags(write=False)
    return table


def branch_contribution_scaled6(day_stem, branch, visible_stems, rule):
    """Return a copy of the PI/SG branch contribution in exact units of 1/6."""
    if rule not in RULE_NAMES:
        raise ValueError("Unknown exposure rule: " + str(rule))
    mask = 0
    for stem in visible_stems:
        mask |= 1 << STEM_INDEX[stem]
    return _branch_table6()[RULE_NAMES.index(rule), STEM_INDEX[day_stem], mask, BRANCH_INDEX[branch]].copy()


def _pillar_indices(values):
    if isinstance(values, str):
        raise TypeError("Batch pillar inputs must be sequences of complete pillars")
    values = list(values)
    stems, branches = [], []
    for value in values:
        if not isinstance(value, str) or len(value) != 2 or value[0] not in STEM_INDEX or value[1] not in BRANCH_INDEX:
            raise ValueError("Each pillar must contain one canonical stem and one branch")
        stems.append(STEM_INDEX[value[0]])
        branches.append(BRANCH_INDEX[value[1]])
    return np.asarray(stems, dtype="int8"), np.asarray(branches, dtype="int8")


def encode_many_pillars(year_pillars, month_pillars, day_pillars):
    """Return exact int16 array(n,8models,2traits,2metrics), with no astronomy.

    Decode count by /72; decode per-position share by /(72*5 or72*7).
    Decode person presence by /12. For hourly models, presence is the mean
    of the twelve per-hour indicators, never indicator(mean count >0).
    """
    ys, yb = _pillar_indices(year_pillars)
    ms, mb = _pillar_indices(month_pillars)
    dm, db = _pillar_indices(day_pillars)
    if not (len(ys) == len(ms) == len(dm)):
        raise ValueError("Year/month/day pillar vectors have different lengths")
    n = len(dm)
    output = np.zeros((n, 8, 2, 2), dtype="int16")
    if not n:
        return output
    matches, table = _trait_match(), _branch_table6()
    visible5 = (np.left_shift(np.uint16(1), ys.astype("uint16")) |
                np.left_shift(np.uint16(1), ms.astype("uint16")))
    # Exclude only the reference Day-Stem position. A Y/M/H stem with the
    # same character must remain a real exposure source.
    stem5_score6 = 6 * (matches[dm, ys].astype("int16") + matches[dm, ms].astype("int16"))
    for rule_index in range(4):
        score6 = stem5_score6.copy()
        for branch in (yb, mb, db):
            score6 += table[rule_index, dm, visible5, branch]
        output[:, rule_index, :, 0] = score6 * 12
        output[:, rule_index, :, 1] = (score6 > 0).astype("int16") * PRESENCE_SCALE

        hour_count_sum6 = np.zeros((n, 2), dtype="int16")
        hour_presence_sum = np.zeros((n, 2), dtype="int16")
        for hour_branch in range(12):
            hs = (2 * (dm % 5) + hour_branch) % 10
            visible7 = visible5 | np.left_shift(np.uint16(1), hs.astype("uint16"))
            hour_score6 = stem5_score6 + 6 * matches[dm, hs].astype("int16")
            for branch in (yb, mb, db):
                hour_score6 += table[rule_index, dm, visible7, branch]
            hour_score6 += table[rule_index, dm, visible7, hour_branch]
            hour_count_sum6 += hour_score6
            hour_presence_sum += hour_score6 > 0
        # Mean of12 scores in units1/6 has denominator72, so the sum of
        # score6 values is already the exact count_scaled72 integer.
        output[:, rule_index + 4, :, 0] = hour_count_sum6
        output[:, rule_index + 4, :, 1] = hour_presence_sum

    if np.any(output[..., 0] < 0) or np.any(output[..., 0] > np.asarray(MAX_COUNT_SCALED72)[None, :, None]):
        raise AssertionError("Count score outside its five/seven-position bound")
    if np.any(output[..., 1] < 0) or np.any(output[..., 1] > PRESENCE_SCALE):
        raise AssertionError("Person-presence score outside0..12")
    if not np.array_equal(output[..., 0] > 0, output[..., 1] > 0):
        raise AssertionError("Count/presence zero-support mismatch")
    return output


def encode_pillars(year_pillar, month_pillar, day_pillar):
    return encode_many_pillars([year_pillar], [month_pillar], [day_pillar])[0]


def _fraction_reference(year_pillar, month_pillar, day_pillar):
    """Independent scalar Fraction reference used only by symbolic fixtures."""
    ys, yb = year_pillar
    ms, mb = month_pillar
    dm, db = day_pillar

    def target(stem, trait):
        return Fraction(int(ten_god(dm, stem) == trait))

    def branch_score(branch, visible, trait, rule):
        hidden = HIDDEN_STEMS[branch]
        exposed = tuple(stem for stem in hidden if stem in visible)
        if rule == "main" or not exposed:
            return target(hidden[0], trait)
        if rule == "priority":
            return target(exposed[0], trait)
        if rule == "share":
            return sum((target(stem, trait) for stem in exposed), Fraction(0)) / len(exposed)
        return Fraction(any(target(stem, trait) > 0 for stem in exposed))

    result = np.zeros((8, 2, 2), dtype="int16")
    for rule_index, rule in enumerate(RULE_NAMES):
        for trait_index, trait in enumerate(TRAIT_TEN_GODS):
            stem5 = target(ys, trait) + target(ms, trait)
            known = stem5 + sum((branch_score(branch, {ys, ms}, trait, rule) for branch in (yb, mb, db)), Fraction(0))
            result[rule_index, trait_index] = (int(known * COUNT_SCALE), int(known > 0) * PRESENCE_SCALE)
            hour_scores = []
            for hour_branch in BRANCHES:
                hs = hour_stem(dm, hour_branch)
                visible = {ys, ms, hs}
                score = stem5 + target(hs, trait)
                score += sum((branch_score(branch, visible, trait, rule) for branch in (yb, mb, db, hour_branch)), Fraction(0))
                hour_scores.append(score)
            expected_count = sum(hour_scores, Fraction(0)) / 12
            scaled_count = expected_count * COUNT_SCALE
            if scaled_count.denominator != 1:
                raise AssertionError("LCM72 did not represent a reference score exactly")
            result[rule_index + 4, trait_index] = (int(scaled_count), sum(score > 0 for score in hour_scores))
    return result


def self_test():
    """Symbolic pillars/masks only: no DOB, calendar cache or cohort is read."""
    assert ten_god("甲", "壬") == "偏印" and ten_god("甲", "丁") == "伤官"
    for day in STEMS:
        assert sorted(ten_god(day, other) for other in STEMS) == sorted(TEN_GODS)
    assert branch_contribution_scaled6("甲", "未", {"己", "丁"}, "priority").tolist() == [0, 0]
    assert branch_contribution_scaled6("甲", "未", {"己", "丁"}, "share").tolist() == [0, 3]
    assert branch_contribution_scaled6("甲", "未", {"己", "丁"}, "any").tolist() == [0, 6]
    assert branch_contribution_scaled6("甲", "申", {"庚", "壬", "戊"}, "share").tolist() == [2, 0]
    for rule in ("priority", "share", "any"):
        assert branch_contribution_scaled6("甲", "亥", {"丁", "己"}, rule).tolist() == [6, 0]

    # YG=reference-DM character remains exposed; the reference-DM position
    # itself is not added when the same character is absent from Y/M.
    assert encode_pillars("甲子", "丁亥", "甲子")[1, 0, 0] == 0
    assert encode_pillars("乙丑", "丁亥", "甲子")[1, 0, 0] == 72
    separate_rules = encode_pillars("己未", "丁酉", "甲子")
    assert separate_rules[:4, 1, 0].tolist() == [72, 72, 108, 144]

    hourly = encode_pillars("甲子", "甲子", "甲子")
    assert hourly[4, :, 0].tolist() == [12, 12]
    assert hourly[4, :, 1].tolist() == [2, 2]
    assert hourly[5, 0].tolist() == [12, 1]
    # Both expected PI counts are1/6, but presence is2/12 versus1/12.
    assert hourly[4, 0, 0] == hourly[5, 0, 0] and hourly[4, 0, 1] != hourly[5, 0, 1]

    zi_starts = {"甲": "甲", "己": "甲", "乙": "丙", "庚": "丙", "丙": "戊", "辛": "戊",
                 "丁": "庚", "壬": "庚", "戊": "壬", "癸": "壬"}
    for day, start in zi_starts.items():
        assert hour_stem(day, "子") == start
    fixtures = [("甲子", "甲子", "甲子"), ("己未", "丁酉", "甲子"),
                ("甲子", "丁亥", "甲子"), ("乙丑", "丁亥", "甲子")]
    fixtures += [(STEMS[index] + BRANCHES[index % 12], "丁亥", STEMS[index] + "子") for index in range(10)]
    for pillars in fixtures:
        assert np.array_equal(encode_pillars(*pillars), _fraction_reference(*pillars)), pillars
    batch = encode_many_pillars(*zip(*fixtures))
    assert np.array_equal(batch, np.stack([_fraction_reference(*pillars) for pillars in fixtures]))
    return {"status": "PASS", "symbolic_fixture_rows": len(fixtures), "astronomy_calls": 0,
            "calendar_or_cohort_files_loaded": False, "count_scale": COUNT_SCALE,
            "presence_scale": PRESENCE_SCALE, "reference_day_stem_positional_exclusion_checked": True,
            "share_half_and_third_checked": True, "per_hour_presence_before_average_checked": True,
            "vectorized_vs_independent_Fraction_reference": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true", required=True)
    parser.parse_args()
    print(json.dumps(self_test(), ensure_ascii=False))


if __name__ == "__main__":
    main()
