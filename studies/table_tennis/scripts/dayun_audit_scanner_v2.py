#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
dayun_audit_scanner.py

Purpose
-------
A reproducible/auditable 大运 calculator for the table-tennis project.

It deliberately does NOT ask an LLM to hand-calculate 大运.
It uses the deterministic lunar-python library and prints enough
intermediate information for manual checking:

    - exact BaZi pillars
    - day master
    - year-stem yin/yang
    - expected 顺/逆 direction from sex + year-stem polarity
    - library 顺/逆 direction
    - previous/next 节
    - 起运 interval
    - exact 起运 solar date/time
    - first several 大运
    - each 大运 stem's 十神 relative to the day master
    - each 大运 branch's 本气天干 + 本气十神
    - 大运 active at chronological ages 8 / 12 / 15 / 18
    - 24-hour birth-time sensitivity for date-only DOBs

The code also flags dates close to a 节, because foreign athletes lack
birth place/timezone in the current dataset.

Install
-------
pip install lunar-python pandas

Examples
--------

A single known-time audit:
    python dayun_audit_scanner.py \
        --person 1997-01-22 男 \
        --hour 12 --minute 0

Compare traditional 起运 calculation sects:
    python dayun_audit_scanner.py \
        --person 1997-01-22 男 \
        --hour 12 \
        --compare-yun-sects

24-hour sensitivity for an unknown birth time:
    python dayun_audit_scanner.py \
        --sensitivity 1997-01-22 男

Batch scan a CSV:
    python dayun_audit_scanner.py \
        --input tabletennis_reference_enriched.csv \
        --output dayun_hour_sensitivity.csv

Small batch smoke test:
    python dayun_audit_scanner.py \
        --input tabletennis_reference_enriched.csv \
        --output dayun_hour_sensitivity.csv \
        --limit 10

Conventions
-----------
gender:
    男 / male / m / 1  -> 1
    女 / female / f / 0 -> 0

yun sect:
    1 = lunar-python traditional rule:
        3 days = 1 year,
        1 day = 4 months,
        1 时辰 = 10 days
    2 = minute-based linear conversion

Default:
    yun_sect = 1
    zi_sect = 2

Important
---------
lunar-python has no birthplace/timezone parameter in this workflow.
For ordinary dates this usually does not change the 大运 sequence.
For dates close to a 节, exact birthplace/timezone can matter.
Those cases are FLAGGED rather than silently treated as certain.

The 24-hour scan uses HH:30 for H=00..23. The resulting fractions are
"sensitivity-grid fractions", NOT a claim that real birth times are
uniformly distributed by clock hour.
"""

import argparse
import calendar
from collections import Counter
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

try:
    from lunar_python import Solar
    from lunar_python.util import LunarUtil
except Exception as e:
    raise SystemExit(
        "Cannot import lunar-python.\n"
        "Install with:\n"
        "  pip install lunar-python pandas\n"
        f"Original error: {e}"
    )


YANG_GAN = set("甲丙戊庚壬")
YIN_GAN = set("乙丁己辛癸")

# 地支本气（主气）天干。只统计本气，不把余气/中气一起混入。
BRANCH_MAIN_GAN = {
    "子": "癸",
    "丑": "己",
    "寅": "甲",
    "卯": "乙",
    "辰": "戊",
    "巳": "丙",
    "午": "丁",
    "未": "己",
    "申": "庚",
    "酉": "辛",
    "戌": "戊",
    "亥": "壬",
}


def parse_gender(x):
    s = str(x).strip().lower()

    if s in {
        "男",
        "male",
        "m",
        "1",
    }:
        return 1

    if s in {
        "女",
        "female",
        "f",
        "0",
    }:
        return 0

    raise ValueError(
        f"Unrecognized gender: {x!r}"
    )


def gender_text(g):
    return "男" if g == 1 else "女"


def dt_to_solar(dt):
    return Solar.fromYmdHms(
        dt.year,
        dt.month,
        dt.day,
        dt.hour,
        dt.minute,
        dt.second,
    )


def solar_to_dt(s):
    return datetime.strptime(
        s.toYmdHms(),
        "%Y-%m-%d %H:%M:%S",
    )


def add_years(dt, years):
    """
    Add calendar years. Feb 29 -> Feb 28 if target year is not leap.
    """
    y = dt.year + years

    try:
        return dt.replace(
            year=y
        )
    except ValueError:
        return dt.replace(
            year=y,
            month=2,
            day=28,
        )


def expected_forward(
    year_gan,
    gender,
):
    """
    Traditional rule:
      阳男阴女顺
      阴男阳女逆
    """
    if year_gan in YANG_GAN:
        yang = True
    elif year_gan in YIN_GAN:
        yang = False
    else:
        raise ValueError(
            f"Invalid year gan: {year_gan}"
        )

    male = gender == 1

    return (
        (yang and male)
        or ((not yang) and (not male))
    )


def ten_god(
    day_gan,
    target_gan,
):
    key = (
        str(day_gan)
        + str(target_gan)
    )

    return LunarUtil.SHI_SHEN.get(
        key,
        ""
    )


def branch_main_gan(
    zhi,
):
    """Return 地支本气对应天干."""
    return BRANCH_MAIN_GAN.get(
        str(zhi),
        "",
    )


def branch_main_ten_god(
    day_gan,
    zhi,
):
    """Return 十神 of the branch's 本气 relative to day master."""
    gan = branch_main_gan(
        zhi
    )

    if not gan:
        return ""

    return ten_god(
        day_gan,
        gan,
    )


def make_chart(
    dt,
    gender,
    yun_sect=1,
    zi_sect=2,
):
    solar = dt_to_solar(dt)
    lunar = solar.getLunar()

    ec = lunar.getEightChar()

    # 子时换日流派 setting inside EightChar.
    ec.setSect(
        int(zi_sect)
    )

    yun = ec.getYun(
        int(gender),
        int(yun_sect),
    )

    year_gan = ec.getYearGan()

    expected = expected_forward(
        year_gan,
        gender,
    )

    library_forward = bool(
        yun.isForward()
    )

    if expected != library_forward:
        raise RuntimeError(
            "Direction self-check FAILED: "
            f"expected_forward={expected}, "
            f"library_forward={library_forward}, "
            f"year_gan={year_gan}, "
            f"gender={gender_text(gender)}"
        )

    return {
        "solar": solar,
        "lunar": lunar,
        "ec": ec,
        "yun": yun,
        "year_gan": year_gan,
        "day_gan": ec.getDayGan(),
        "expected_forward": expected,
        "library_forward": library_forward,
    }


def start_interval_text(
    yun,
):
    return (
        f"{yun.getStartYear()}年 "
        f"{yun.getStartMonth()}月 "
        f"{yun.getStartDay()}日 "
        f"{yun.getStartHour()}时"
    )


def active_dayun_at_age(
    birth_dt,
    chart,
    age,
    dayun_count=10,
):
    """
    Determine the 大运 active at exact chronological age N,
    using exact first 起运 solar datetime + 10-year boundaries.
    This avoids relying only on nominal/虚岁 age labels.
    """
    target = add_years(
        birth_dt,
        int(age),
    )

    first_start = solar_to_dt(
        chart[
            "yun"
        ].getStartSolar()
    )

    if target < first_start:
        return {
            "age": int(age),
            "target_dt": target,
            "dayun_index": 0,
            "dayun_ganzhi": "",
            "dayun_gan": "",
            "dayun_tengod": "",
            "dayun_zhi": "",
            "dayun_branch_main_gan": "",
            "dayun_branch_main_tengod": "",
            "status": "未起运",
        }

    da_yun = chart[
        "yun"
    ].getDaYun(
        dayun_count + 1
    )

    for i in range(
        1,
        len(da_yun),
    ):
        start = add_years(
            first_start,
            (i - 1) * 10,
        )

        end = add_years(
            first_start,
            i * 10,
        )

        if (
            target >= start
            and target < end
        ):
            gz = da_yun[
                i
            ].getGanZhi()

            gan = (
                gz[0]
                if gz
                else ""
            )

            zhi = (
                gz[1]
                if gz
                and len(gz) >= 2
                else ""
            )

            main_gan = (
                branch_main_gan(
                    zhi
                )
                if zhi
                else ""
            )

            return {
                "age": int(age),
                "target_dt": target,
                "dayun_index": i,
                "dayun_ganzhi": gz,
                "dayun_gan": gan,
                "dayun_tengod": (
                    ten_god(
                        chart[
                            "day_gan"
                        ],
                        gan,
                    )
                    if gan
                    else ""
                ),
                "dayun_zhi": zhi,
                "dayun_branch_main_gan": main_gan,
                "dayun_branch_main_tengod": (
                    ten_god(
                        chart[
                            "day_gan"
                        ],
                        main_gan,
                    )
                    if main_gan
                    else ""
                ),
                "status": "大运",
            }

    return {
        "age": int(age),
        "target_dt": target,
        "dayun_index": np.nan,
        "dayun_ganzhi": "",
        "dayun_gan": "",
        "dayun_tengod": "",
        "dayun_zhi": "",
        "dayun_branch_main_gan": "",
        "dayun_branch_main_tengod": "",
        "status": "超出计算范围",
    }


def nearest_jie_info(
    dt,
    gender,
    yun_sect=1,
    zi_sect=2,
):
    chart = make_chart(
        dt,
        gender,
        yun_sect=yun_sect,
        zi_sect=zi_sect,
    )

    lunar = chart[
        "lunar"
    ]

    prev_jie = lunar.getPrevJie()
    next_jie = lunar.getNextJie()

    current = dt

    prev_dt = solar_to_dt(
        prev_jie.getSolar()
    )
    next_dt = solar_to_dt(
        next_jie.getSolar()
    )

    prev_hours = abs(
        (
            current
            - prev_dt
        ).total_seconds()
    ) / 3600.0

    next_hours = abs(
        (
            next_dt
            - current
        ).total_seconds()
    ) / 3600.0

    if prev_hours <= next_hours:
        return {
            "nearest_jie_side": "prev",
            "nearest_jie_solar": (
                prev_jie
                .getSolar()
                .toYmdHms()
            ),
            "hours_to_nearest_jie": (
                prev_hours
            ),
        }

    return {
        "nearest_jie_side": "next",
        "nearest_jie_solar": (
            next_jie
            .getSolar()
            .toYmdHms()
        ),
        "hours_to_nearest_jie": (
            next_hours
        ),
    }


def date_boundary_flag(
    dob,
    gender,
    yun_sect=1,
    zi_sect=2,
    threshold_hours=36.0,
):
    """
    Evaluate DOB at noon and flag if close to a 节.

    We intentionally use a generous threshold because the current
    athlete dataset generally lacks birthplace/timezone.
    """
    base = datetime.strptime(
        dob,
        "%Y-%m-%d",
    ).replace(
        hour=12,
        minute=0,
        second=0,
    )

    info = nearest_jie_info(
        base,
        gender,
        yun_sect=yun_sect,
        zi_sect=zi_sect,
    )

    # Also see if year/month pillars change across noon on the
    # previous/current/next civil day.
    pillars = []

    for offset in [
        -1,
        0,
        1,
    ]:
        x = make_chart(
            base
            + timedelta(
                days=offset
            ),
            gender,
            yun_sect=yun_sect,
            zi_sect=zi_sect,
        )

        pillars.append(
            (
                x["ec"].getYear(),
                x["ec"].getMonth(),
            )
        )

    pillar_changes_3day = (
        len(
            set(pillars)
        )
        > 1
    )

    flagged = (
        info[
            "hours_to_nearest_jie"
        ]
        <= threshold_hours
        or pillar_changes_3day
    )

    return {
        **info,
        "pillar_changes_within_plusminus_1day": (
            int(
                pillar_changes_3day
            )
        ),
        "boundary_sensitive": int(
            flagged
        ),
    }


def print_single(
    dob,
    gender_raw,
    hour=12,
    minute=0,
    yun_sect=1,
    zi_sect=2,
    ages=(8, 12, 15, 18),
    dayun_count=6,
):
    gender = parse_gender(
        gender_raw
    )

    dt = datetime.strptime(
        dob,
        "%Y-%m-%d",
    ).replace(
        hour=int(hour),
        minute=int(minute),
        second=0,
    )

    chart = make_chart(
        dt,
        gender,
        yun_sect=yun_sect,
        zi_sect=zi_sect,
    )

    ec = chart[
        "ec"
    ]

    yun = chart[
        "yun"
    ]

    print()
    print("=" * 100)
    print(
        f"DOB={dt:%Y-%m-%d %H:%M}, "
        f"gender={gender_text(gender)}, "
        f"yun_sect={yun_sect}, "
        f"zi_sect={zi_sect}"
    )
    print("=" * 100)

    print(
        f"BaZi: {ec.toString()}"
    )

    print(
        f"Year pillar={ec.getYear()}, "
        f"Month pillar={ec.getMonth()}, "
        f"Day pillar={ec.getDay()}, "
        f"Time pillar={ec.getTime()}"
    )

    print(
        f"Day master={ec.getDayGan()}"
    )

    print(
        f"Direction expected="
        f"{'顺' if chart['expected_forward'] else '逆'}; "
        f"library="
        f"{'顺' if chart['library_forward'] else '逆'}"
    )

    print(
        f"起运 interval: "
        f"{start_interval_text(yun)}"
    )

    print(
        f"起运 solar: "
        f"{yun.getStartSolar().toYmdHms()}"
    )

    b = date_boundary_flag(
        dob,
        gender,
        yun_sect=yun_sect,
        zi_sect=zi_sect,
    )

    print(
        f"Nearest Jie: "
        f"{b['nearest_jie_solar']}, "
        f"distance={b['hours_to_nearest_jie']:.2f} h, "
        f"boundary_sensitive={bool(b['boundary_sensitive'])}"
    )

    print()
    print("大运:")
    print(
        f"{'idx':>3s} "
        f"{'GanZhi':>8s} "
        f"{'StemTG':>6s} "
        f"{'MainQi':>6s} "
        f"{'BranchTG':>8s} "
        f"{'libStartAge':>11s} "
        f"{'libEndAge':>9s} "
        f"{'startYear':>9s} "
        f"{'endYear':>7s}"
    )

    da_yun = yun.getDaYun(
        dayun_count + 1
    )

    for i in range(
        1,
        len(da_yun),
    ):
        dy = da_yun[i]
        gz = dy.getGanZhi()
        gan = (
            gz[0]
            if gz
            else ""
        )
        tg = (
            ten_god(
                chart[
                    "day_gan"
                ],
                gan,
            )
            if gan
            else ""
        )

        zhi = (
            gz[1]
            if gz
            and len(gz) >= 2
            else ""
        )

        main_gan = (
            branch_main_gan(
                zhi
            )
            if zhi
            else ""
        )

        branch_tg = (
            ten_god(
                chart[
                    "day_gan"
                ],
                main_gan,
            )
            if main_gan
            else ""
        )

        print(
            f"{i:3d} "
            f"{gz:>8s} "
            f"{tg:>6s} "
            f"{main_gan:>6s} "
            f"{branch_tg:>8s} "
            f"{dy.getStartAge():11d} "
            f"{dy.getEndAge():9d} "
            f"{dy.getStartYear():9d} "
            f"{dy.getEndYear():7d}"
        )

    print()
    print("Exact chronological ages:")
    for age in ages:
        a = active_dayun_at_age(
            dt,
            chart,
            age,
            dayun_count=dayun_count,
        )

        print(
            f"age {age:>2d}: "
            f"{a['status']} "
            f"{a['dayun_ganzhi']} "
            f"干={a['dayun_tengod']} "
            f"支本气={a['dayun_branch_main_gan']}"
            f"/{a['dayun_branch_main_tengod']} "
            f"(target={a['target_dt']:%Y-%m-%d %H:%M})"
        )


def sensitivity_one_date(
    dob,
    gender_raw,
    yun_sect=1,
    zi_sect=2,
    ages=(8, 12, 15, 18),
    dayun_count=6,
):
    gender = parse_gender(
        gender_raw
    )

    rows = []

    base_date = datetime.strptime(
        dob,
        "%Y-%m-%d",
    )

    for hour in range(24):
        dt = base_date.replace(
            hour=hour,
            minute=30,
            second=0,
        )

        chart = make_chart(
            dt,
            gender,
            yun_sect=yun_sect,
            zi_sect=zi_sect,
        )

        ec = chart[
            "ec"
        ]

        yun = chart[
            "yun"
        ]

        r = {
            "dob": dob,
            "gender": gender_text(
                gender
            ),
            "assumed_time": (
                f"{hour:02d}:30"
            ),
            "year_pillar": ec.getYear(),
            "month_pillar": ec.getMonth(),
            "day_pillar": ec.getDay(),
            "day_gan": ec.getDayGan(),
            "direction": (
                "顺"
                if yun.isForward()
                else "逆"
            ),
            "start_years": yun.getStartYear(),
            "start_months": yun.getStartMonth(),
            "start_days": yun.getStartDay(),
            "start_hours": yun.getStartHour(),
            "start_solar": (
                yun.getStartSolar()
                .toYmdHms()
            ),
        }

        for age in ages:
            a = active_dayun_at_age(
                dt,
                chart,
                age,
                dayun_count=dayun_count,
            )

            r[
                f"age{age}_ganzhi"
            ] = a[
                "dayun_ganzhi"
            ]

            r[
                f"age{age}_tengod"
            ] = a[
                "dayun_tengod"
            ]

            r[
                f"age{age}_branch"
            ] = a[
                "dayun_zhi"
            ]

            r[
                f"age{age}_branch_main_gan"
            ] = a[
                "dayun_branch_main_gan"
            ]

            r[
                f"age{age}_branch_main_tengod"
            ] = a[
                "dayun_branch_main_tengod"
            ]

        rows.append(r)

    out = pd.DataFrame(
        rows
    )

    b = date_boundary_flag(
        dob,
        gender,
        yun_sect=yun_sect,
        zi_sect=zi_sect,
    )

    return out, b


def summarize_sensitivity(
    sens,
    boundary_info,
    ages=(8, 12, 15, 18),
):
    row = {
        "dob": sens.iloc[0][
            "dob"
        ],
        "gender": sens.iloc[0][
            "gender"
        ],
        "hour_variants": len(sens),
        "unique_year_pillars": (
            sens[
                "year_pillar"
            ].nunique()
        ),
        "unique_month_pillars": (
            sens[
                "month_pillar"
            ].nunique()
        ),
        "unique_day_pillars": (
            sens[
                "day_pillar"
            ].nunique()
        ),
        "unique_directions": (
            sens[
                "direction"
            ].nunique()
        ),
        "unique_start_solar": (
            sens[
                "start_solar"
            ].nunique()
        ),
        **boundary_info,
    }

    for age in ages:
        tgcol = (
            f"age{age}_tengod"
        )
        gzcol = (
            f"age{age}_ganzhi"
        )

        tgc = Counter(
            sens[
                tgcol
            ].fillna(
                ""
            )
        )

        gzc = Counter(
            sens[
                gzcol
            ].fillna(
                ""
            )
        )

        row[
            f"age{age}_unique_tengod"
        ] = len(tgc)

        row[
            f"age{age}_unique_ganzhi"
        ] = len(gzc)

        row[
            f"age{age}_tengod_counts"
        ] = ";".join(
            f"{k or 'NONE'}:{v}"
            for k, v in sorted(
                tgc.items()
            )
        )

        row[
            f"age{age}_ganzhi_counts"
        ] = ";".join(
            f"{k or 'NONE'}:{v}"
            for k, v in sorted(
                gzc.items()
            )
        )

        row[
            f"age{age}_foodgod_grid_fraction"
        ] = (
            sens[
                tgcol
            ]
            .eq(
                "食神"
            )
            .mean()
        )

        row[
            f"age{age}_sevenkill_grid_fraction"
        ] = (
            sens[
                tgcol
            ]
            .eq(
                "七杀"
            )
            .mean()
        )

        row[
            f"age{age}_foodgod_or_sevenkill_grid_fraction"
        ] = (
            sens[
                tgcol
            ]
            .isin(
                [
                    "食神",
                    "七杀",
                ]
            )
            .mean()
        )

        # 地支本气十神，单独统计，不和天干混为一列。
        btgcol = (
            f"age{age}_branch_main_tengod"
        )

        bmgcol = (
            f"age{age}_branch_main_gan"
        )

        btgc = Counter(
            sens[
                btgcol
            ].fillna(
                ""
            )
        )

        bmgc = Counter(
            sens[
                bmgcol
            ].fillna(
                ""
            )
        )

        row[
            f"age{age}_branch_main_unique_tengod"
        ] = len(btgc)

        row[
            f"age{age}_branch_main_tengod_counts"
        ] = ";".join(
            f"{k or 'NONE'}:{v}"
            for k, v in sorted(
                btgc.items()
            )
        )

        row[
            f"age{age}_branch_main_gan_counts"
        ] = ";".join(
            f"{k or 'NONE'}:{v}"
            for k, v in sorted(
                bmgc.items()
            )
        )

        row[
            f"age{age}_branch_main_foodgod_grid_fraction"
        ] = (
            sens[
                btgcol
            ]
            .eq(
                "食神"
            )
            .mean()
        )

        row[
            f"age{age}_branch_main_sevenkill_grid_fraction"
        ] = (
            sens[
                btgcol
            ]
            .eq(
                "七杀"
            )
            .mean()
        )

        row[
            f"age{age}_branch_main_foodgod_or_sevenkill_grid_fraction"
        ] = (
            sens[
                btgcol
            ]
            .isin(
                [
                    "食神",
                    "七杀",
                ]
            )
            .mean()
        )

        # Either 大运天干 OR 地支本气 hits 食神/七杀.
        stem_hit = sens[
            tgcol
        ].isin(
            [
                "食神",
                "七杀",
            ]
        )

        branch_hit = sens[
            btgcol
        ].isin(
            [
                "食神",
                "七杀",
            ]
        )

        row[
            f"age{age}_stem_or_branch_main_foodgod_or_sevenkill_grid_fraction"
        ] = (
            stem_hit
            | branch_hit
        ).mean()

        row[
            f"age{age}_stem_and_branch_main_foodgod_or_sevenkill_grid_fraction"
        ] = (
            stem_hit
            & branch_hit
        ).mean()

    return row


def compare_yun_sects(
    dob,
    gender_raw,
    hour,
    minute,
    zi_sect=2,
    ages=(8, 12, 15, 18),
):
    for ys in [
        1,
        2,
    ]:
        print_single(
            dob,
            gender_raw,
            hour=hour,
            minute=minute,
            yun_sect=ys,
            zi_sect=zi_sect,
            ages=ages,
        )


def batch_scan(
    input_path,
    output_path,
    limit=None,
    yun_sect=1,
    zi_sect=2,
    ages=(8, 12, 15, 18),
):
    df = pd.read_csv(
        input_path,
        encoding="utf-8-sig",
    )

    for col in [
        "name",
        "dob",
        "gender",
    ]:
        if col not in df.columns:
            raise SystemExit(
                f"Input missing column: {col}"
            )

    work = df.copy()

    if limit is not None:
        work = work.head(
            int(limit)
        )

    rows = []

    for pos, (
        idx,
        r,
    ) in enumerate(
        work.iterrows(),
        1,
    ):
        name = str(
            r["name"]
        )

        dob = str(
            r["dob"]
        )

        gender = r[
            "gender"
        ]

        print(
            f"[{pos:3d}/{len(work):3d}] "
            f"{name} {dob} {gender}"
        )

        try:
            sens, b = (
                sensitivity_one_date(
                    dob,
                    gender,
                    yun_sect=yun_sect,
                    zi_sect=zi_sect,
                    ages=ages,
                )
            )

            s = summarize_sensitivity(
                sens,
                b,
                ages=ages,
            )

            s["name"] = name
            s["qid"] = (
                r["qid"]
                if "qid" in r.index
                else ""
            )

            # Noon chart cross-check against the existing BaZi CSV.
            noon = make_chart(
                datetime.strptime(
                    dob,
                    "%Y-%m-%d",
                ).replace(
                    hour=12,
                    minute=0,
                ),
                parse_gender(
                    gender
                ),
                yun_sect=yun_sect,
                zi_sect=zi_sect,
            )

            s[
                "computed_noon_year_pillar"
            ] = noon[
                "ec"
            ].getYear()

            s[
                "computed_noon_month_pillar"
            ] = noon[
                "ec"
            ].getMonth()

            s[
                "computed_noon_day_pillar"
            ] = noon[
                "ec"
            ].getDay()

            for col, comp in [
                (
                    "year_pillar",
                    "computed_noon_year_pillar",
                ),
                (
                    "month_pillar",
                    "computed_noon_month_pillar",
                ),
                (
                    "day_pillar",
                    "computed_noon_day_pillar",
                ),
            ]:
                if col in r.index:
                    s[
                        f"{col}_matches_existing"
                    ] = int(
                        str(
                            r[col]
                        )
                        == str(
                            s[
                                comp
                            ]
                        )
                    )

            s["error"] = ""

            rows.append(s)

        except Exception as e:
            rows.append({
                "name": name,
                "dob": dob,
                "gender": gender,
                "error": (
                    f"{type(e).__name__}: {e}"
                ),
            })

            print(
                f"    FAILED: {e}"
            )

        pd.DataFrame(
            rows
        ).to_csv(
            output_path,
            index=False,
            encoding="utf-8-sig",
        )

    out = pd.DataFrame(
        rows
    )

    print()
    print(
        f"Saved: {output_path}"
    )

    if "boundary_sensitive" in out.columns:
        print(
            f"boundary_sensitive: "
            f"{int(pd.to_numeric(out['boundary_sensitive'], errors='coerce').fillna(0).sum())}"
            f"/{len(out)}"
        )

    for age in ages:
        col = (
            f"age{age}_unique_tengod"
        )

        if col in out.columns:
            stable = (
                pd.to_numeric(
                    out[col],
                    errors="coerce",
                )
                == 1
            )

            print(
                f"age {age}: stable Tengod across 24-hour grid = "
                f"{int(stable.sum())}/{stable.notna().sum()}"
            )


def main():
    ap = argparse.ArgumentParser()

    mode = ap.add_mutually_exclusive_group(
        required=True
    )

    mode.add_argument(
        "--person",
        nargs=2,
        metavar=(
            "YYYY-MM-DD",
            "GENDER",
        ),
    )

    mode.add_argument(
        "--sensitivity",
        nargs=2,
        metavar=(
            "YYYY-MM-DD",
            "GENDER",
        ),
    )

    mode.add_argument(
        "--input",
    )

    ap.add_argument(
        "--output",
        default="dayun_hour_sensitivity.csv",
    )

    ap.add_argument(
        "--hour",
        type=int,
        default=12,
    )

    ap.add_argument(
        "--minute",
        type=int,
        default=0,
    )

    ap.add_argument(
        "--yun-sect",
        type=int,
        choices=[
            1,
            2,
        ],
        default=1,
    )

    ap.add_argument(
        "--zi-sect",
        type=int,
        choices=[
            1,
            2,
        ],
        default=2,
    )

    ap.add_argument(
        "--ages",
        nargs="+",
        type=int,
        default=[
            8,
            12,
            15,
            18,
        ],
    )

    ap.add_argument(
        "--dayun-count",
        type=int,
        default=6,
    )

    ap.add_argument(
        "--compare-yun-sects",
        action="store_true",
    )

    ap.add_argument(
        "--limit",
        type=int,
        default=None,
    )

    args = ap.parse_args()

    if args.person:
        dob, gender = (
            args.person
        )

        if args.compare_yun_sects:
            compare_yun_sects(
                dob,
                gender,
                args.hour,
                args.minute,
                zi_sect=args.zi_sect,
                ages=args.ages,
            )
        else:
            print_single(
                dob,
                gender,
                hour=args.hour,
                minute=args.minute,
                yun_sect=args.yun_sect,
                zi_sect=args.zi_sect,
                ages=args.ages,
                dayun_count=args.dayun_count,
            )

        return

    if args.sensitivity:
        dob, gender = (
            args.sensitivity
        )

        sens, b = (
            sensitivity_one_date(
                dob,
                gender,
                yun_sect=args.yun_sect,
                zi_sect=args.zi_sect,
                ages=args.ages,
                dayun_count=args.dayun_count,
            )
        )

        print(
            sens.to_string(
                index=False
            )
        )

        print()
        print("SUMMARY:")
        summary = summarize_sensitivity(
            sens,
            b,
            ages=args.ages,
        )

        for k, v in summary.items():
            print(
                f"{k}: {v}"
            )

        sens.to_csv(
            "dayun_single_date_hour_grid.csv",
            index=False,
            encoding="utf-8-sig",
        )

        print()
        print(
            "Saved: dayun_single_date_hour_grid.csv"
        )

        return

    batch_scan(
        args.input,
        args.output,
        limit=args.limit,
        yun_sect=args.yun_sect,
        zi_sect=args.zi_sect,
        ages=args.ages,
    )


if __name__ == "__main__":
    main()
