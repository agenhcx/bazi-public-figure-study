#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import numpy as np
import pandas as pd
from scipy.stats import mannwhitneyu, kruskal

GAN_ELEMENT = {
    "甲":"木","乙":"木","丙":"火","丁":"火","戊":"土",
    "己":"土","庚":"金","辛":"金","壬":"水","癸":"水"
}
STEMS = list("甲乙丙丁戊己庚辛壬癸")
ELEMENTS = ["木","火","土","金","水"]

def add_dm(df):
    x = df.copy()
    x["day_master"] = x["day_pillar"].astype(str).str[0]
    x["dm_element"] = x["day_master"].map(GAN_ELEMENT)
    return x

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ranking", required=True)
    ap.add_argument("--elo", default=None)
    ap.add_argument("--prefix", default="daymaster_performance")
    args = ap.parse_args()

    base = add_dm(pd.read_csv(args.ranking, encoding="utf-8-sig"))

    # Official career-best rank
    if "highest_rank" in base.columns:
        r = base.copy()
        r["highest_rank"] = pd.to_numeric(r["highest_rank"], errors="coerce")
        r = r[r["highest_rank"].notna()].copy()

        if len(r) >= 20:
            stem_rank = (
                r.groupby("day_master")["highest_rank"]
                 .agg(n="size", mean_rank="mean", median_rank="median")
                 .reindex(STEMS)
                 .reset_index()
            )
            elem_rank = (
                r.groupby("dm_element")["highest_rank"]
                 .agg(n="size", mean_rank="mean", median_rank="median")
                 .reindex(ELEMENTS)
                 .reset_index()
            )

            metal = r.loc[r["dm_element"]=="金","highest_rank"]
            nonmetal = r.loc[r["dm_element"]!="金","highest_rank"]
            earth = r.loc[r["dm_element"]=="土","highest_rank"]

            rank_tests = pd.DataFrame([
                {
                    "comparison":"金 vs 非金; H1 金更差(highest_rank更大)",
                    "u": mannwhitneyu(metal, nonmetal, alternative="greater").statistic,
                    "p_one_sided": mannwhitneyu(metal, nonmetal, alternative="greater").pvalue,
                    "p_two_sided": mannwhitneyu(metal, nonmetal, alternative="two-sided").pvalue,
                },
                {
                    "comparison":"金 vs 土; H1 金更差(highest_rank更大)",
                    "u": mannwhitneyu(metal, earth, alternative="greater").statistic,
                    "p_one_sided": mannwhitneyu(metal, earth, alternative="greater").pvalue,
                    "p_two_sided": mannwhitneyu(metal, earth, alternative="two-sided").pvalue,
                },
                {
                    "comparison":"五行global Kruskal",
                    "u": np.nan,
                    "p_one_sided": np.nan,
                    "p_two_sided": kruskal(*[
                        g["highest_rank"].to_numpy()
                        for _, g in r.groupby("dm_element")
                    ]).pvalue,
                },
            ])

            stem_rank.to_csv(f"{args.prefix}_official_rank_10stem.csv", index=False, encoding="utf-8-sig")
            elem_rank.to_csv(f"{args.prefix}_official_rank_5element.csv", index=False, encoding="utf-8-sig")
            rank_tests.to_csv(f"{args.prefix}_official_rank_tests.csv", index=False, encoding="utf-8-sig")

            print("\nOFFICIAL CAREER-BEST RANK (smaller = better)")
            print(stem_rank.to_string(index=False))
            print("\nBY ELEMENT")
            print(elem_rank.to_string(index=False))
            print("\nTESTS")
            print(rank_tests.to_string(index=False))
        else:
            print(f"\nWARNING: only {len(r)} rows have highest_rank; official-rank analysis skipped.")
    else:
        print("\nWARNING: ranking file has no highest_rank column.")

    # Cohort dynamic Elo
    if args.elo:
        elo = pd.read_csv(args.elo, encoding="utf-8-sig")
        keys = base[["qid","day_master","dm_element"]].drop_duplicates("qid")
        e = elo.merge(keys, on="qid", how="left")
        e["internal_matches"] = pd.to_numeric(e["internal_matches"], errors="coerce")
        e = e[(e["internal_matches"] >= 10) & e["peak_elo_gender_z"].notna()].copy()

        stem_elo = (
            e.groupby("day_master")
             .agg(
                 n=("peak_elo_gender_z","size"),
                 mean_gender_z=("peak_elo_gender_z","mean"),
                 median_gender_z=("peak_elo_gender_z","median"),
                 mean_gender_percentile=("peak_elo_gender_percentile","mean"),
                 median_gender_percentile=("peak_elo_gender_percentile","median"),
             )
             .reindex(STEMS)
             .reset_index()
        )
        elem_elo = (
            e.groupby("dm_element")
             .agg(
                 n=("peak_elo_gender_z","size"),
                 mean_gender_z=("peak_elo_gender_z","mean"),
                 median_gender_z=("peak_elo_gender_z","median"),
                 mean_gender_percentile=("peak_elo_gender_percentile","mean"),
                 median_gender_percentile=("peak_elo_gender_percentile","median"),
             )
             .reindex(ELEMENTS)
             .reset_index()
        )

        metal = e.loc[e["dm_element"]=="金","peak_elo_gender_z"]
        nonmetal = e.loc[e["dm_element"]!="金","peak_elo_gender_z"]
        earth = e.loc[e["dm_element"]=="土","peak_elo_gender_z"]

        elo_tests = pd.DataFrame([
            {
                "comparison":"金 vs 非金; H1 金更弱(z更低)",
                "p_one_sided":mannwhitneyu(metal, nonmetal, alternative="less").pvalue,
                "p_opposite_direction":mannwhitneyu(metal, nonmetal, alternative="greater").pvalue,
                "p_two_sided":mannwhitneyu(metal, nonmetal, alternative="two-sided").pvalue,
            },
            {
                "comparison":"金 vs 土; H1 金更弱(z更低)",
                "p_one_sided":mannwhitneyu(metal, earth, alternative="less").pvalue,
                "p_opposite_direction":mannwhitneyu(metal, earth, alternative="greater").pvalue,
                "p_two_sided":mannwhitneyu(metal, earth, alternative="two-sided").pvalue,
            },
            {
                "comparison":"五行global Kruskal",
                "p_one_sided":np.nan,
                "p_opposite_direction":np.nan,
                "p_two_sided":kruskal(*[
                    g["peak_elo_gender_z"].to_numpy()
                    for _, g in e.groupby("dm_element")
                ]).pvalue,
            },
        ])

        stem_elo.to_csv(f"{args.prefix}_elo_10stem.csv", index=False, encoding="utf-8-sig")
        elem_elo.to_csv(f"{args.prefix}_elo_5element.csv", index=False, encoding="utf-8-sig")
        elo_tests.to_csv(f"{args.prefix}_elo_tests.csv", index=False, encoding="utf-8-sig")

        print("\nDYNAMIC ELO (gender-standardized; higher = stronger)")
        print(stem_elo.to_string(index=False))
        print("\nBY ELEMENT")
        print(elem_elo.to_string(index=False))
        print("\nTESTS")
        print(elo_tests.to_string(index=False))

if __name__ == "__main__":
    main()
