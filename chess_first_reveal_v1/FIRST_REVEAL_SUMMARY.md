# Chess BaZi First Reveal v1

Confirmatory and exploratory sections are deliberately separated.

## Confirmatory — Day Master distributions

- **1994_M** n=501: 木 100 (20.0%), 火 95 (19.0%), 土 99 (19.8%), 金 95 (19.0%), 水 112 (22.4%)
- **1994_F** n=201: 木 41 (20.4%), 火 38 (18.9%), 土 43 (21.4%), 金 46 (22.9%), 水 33 (16.4%)
- **2013_M** n=501: 木 110 (22.0%), 火 92 (18.4%), 土 91 (18.2%), 金 114 (22.8%), 水 94 (18.8%)
- **2013_F** n=200: 木 37 (18.5%), 火 40 (20.0%), 土 36 (18.0%), 金 54 (27.0%), 水 33 (16.5%)

## Confirmatory — Metal/Earth temporal gradient

```json
{
  "M": {
    "table_rows": [
      "1994",
      "2013"
    ],
    "table_cols": [
      "Metal_DM",
      "Earth_DM"
    ],
    "table": [
      [
        95,
        99
      ],
      [
        114,
        91
      ]
    ],
    "odds_ratio_1994_vs_2013": 0.765993265993266,
    "fisher_two_sided_p": 0.1936008256012009,
    "fisher_directional_p_metal_earlier_earth_later": 0.9233565560739149,
    "analysis_role": "confirmatory_frozen_prereg"
  },
  "F": {
    "table_rows": [
      "1994",
      "2013"
    ],
    "table_cols": [
      "Metal_DM",
      "Earth_DM"
    ],
    "table": [
      [
        46,
        43
      ],
      [
        54,
        36
      ]
    ],
    "odds_ratio_1994_vs_2013": 0.7131782945736435,
    "fisher_two_sided_p": 0.29370353119404435,
    "fisher_directional_p_metal_earlier_earth_later": 0.8981365824897924,
    "analysis_role": "confirmatory_frozen_prereg"
  },
  "sex_stratified_CMH": {
    "strata": [
      {
        "sex": "M",
        "table": [
          [
            95,
            99
          ],
          [
            114,
            91
          ]
        ]
      },
      {
        "sex": "F",
        "table": [
          [
            46,
            43
          ],
          [
            54,
            36
          ]
        ]
      }
    ],
    "mantel_haenszel_common_odds_ratio": 0.7493874445476117,
    "cmh_z_direction_metal_earlier": -1.722815771613798,
    "cmh_one_sided_p": 0.9575390771273193,
    "cmh_two_sided_p": 0.08492184574536124,
    "analysis_role": "confirmatory_frozen_prereg"
  }
}
```

## Confirmatory — five-element 1994 vs 2013

```json
{
  "M": {
    "elements": [
      "木",
      "火",
      "土",
      "金",
      "水"
    ],
    "table": [
      [
        100,
        95,
        99,
        95,
        112
      ],
      [
        110,
        92,
        91,
        114,
        94
      ]
    ],
    "chi2": 4.161249184952933,
    "df": 4,
    "p": 0.3846227765104446,
    "expected": [
      [
        105.0,
        93.5,
        95.0,
        104.5,
        103.0
      ],
      [
        105.0,
        93.5,
        95.0,
        104.5,
        103.0
      ]
    ],
    "analysis_role": "confirmatory_frozen_prereg"
  },
  "F": {
    "elements": [
      "木",
      "火",
      "土",
      "金",
      "水"
    ],
    "table": [
      [
        41,
        38,
        43,
        46,
        33
      ],
      [
        37,
        40,
        36,
        54,
        33
      ]
    ],
    "chi2": 1.5141790718591401,
    "df": 4,
    "p": 0.8241268897832562,
    "expected": [
      [
        39.09725685785536,
        39.09725685785536,
        39.598503740648376,
        50.12468827930174,
        33.082294264339154
      ],
      [
        38.90274314214464,
        38.90274314214464,
        39.401496259351624,
        49.87531172069826,
        32.917705735660846
      ]
    ],
    "analysis_role": "confirmatory_frozen_prereg"
  },
  "pooled": {
    "elements": [
      "木",
      "火",
      "土",
      "金",
      "水"
    ],
    "table": [
      [
        141,
        133,
        142,
        141,
        145
      ],
      [
        147,
        132,
        127,
        168,
        127
      ]
    ],
    "chi2": 4.514894118532494,
    "df": 4,
    "p": 0.34078507420479975,
    "expected": [
      [
        144.10263720598718,
        132.5944404846757,
        134.59586600142552,
        154.61012116892374,
        136.09693513898787
      ],
      [
        143.89736279401282,
        132.4055595153243,
        134.40413399857448,
        154.38987883107626,
        135.90306486101213
      ]
    ],
    "analysis_role": "confirmatory_frozen_prereg"
  }
}
```

## Confirmatory — 伤官 / 偏印 performance

```json
{
  "shangguan_count_6pos": {
    "1994_M": {
      "rho": 0.04430680379438236,
      "p": 0.3223064100878613,
      "n": 501
    },
    "1994_F": {
      "rho": 0.055523951878574125,
      "p": 0.4336960912015366,
      "n": 201
    },
    "2013_M": {
      "rho": -0.013607805611073515,
      "p": 0.7612519498616009,
      "n": 501
    },
    "2013_F": {
      "rho": 0.0936952173362843,
      "p": 0.18695194053588077,
      "n": 200
    },
    "pooled_standardized_elo": {
      "rho": 0.03203182555071061,
      "p": 0.2305112711687113,
      "n": 1403
    }
  },
  "pianyin_count_6pos": {
    "1994_M": {
      "rho": 0.014788066645493585,
      "p": 0.7412541487095003,
      "n": 501
    },
    "1994_F": {
      "rho": 0.035444019106752246,
      "p": 0.6174069825810031,
      "n": 201
    },
    "2013_M": {
      "rho": -0.049759328767635606,
      "p": 0.2662795477759665,
      "n": 501
    },
    "2013_F": {
      "rho": -0.08756893985559638,
      "p": 0.21756849406594675,
      "n": 200
    },
    "pooled_standardized_elo": {
      "rho": -0.02133026051838061,
      "p": 0.42467400969640146,
      "n": 1403
    }
  }
}
```

## Exploratory — Water / Metal+Water

**These analyses are not confirmatory.**

- **1994_M**: Water DM=22.4%; mean WaterCount=1.048; mean MetalWaterCount=2.182
- **1994_F**: Water DM=16.4%; mean WaterCount=0.910; mean MetalWaterCount=1.886
- **2013_M**: Water DM=18.8%; mean WaterCount=1.096; mean MetalWaterCount=2.182
- **2013_F**: Water DM=16.5%; mean WaterCount=1.145; mean MetalWaterCount=2.220

```json
{
  "analysis_role": "exploratory_pre_reveal_not_confirmatory",
  "water_intelligence_proxy_note": "Water-DM, WaterCount, and MetalWaterCount were fixed before first chess BaZi reveal in this analysis plan but were not part of the original confirmatory preregistration.",
  "by_cohort": {
    "1994_M": {
      "WaterDM_count": 112,
      "WaterDM_share": 0.22355289421157684,
      "WaterCount_mean": 1.0479041916167664,
      "MetalCount_mean": 1.1337325349301397,
      "MetalWaterCount_mean": 2.1816367265469063,
      "calendar_null": {
        "WaterDM": {
          "observed_sum": 112.0,
          "observed_mean_per_player": 0.22355289421157684,
          "null_mean_sum": 100.3472,
          "null_mean_per_player": 0.2002938123752495,
          "null_sd_sum": 9.078696861738553,
          "z": 1.28353222686725,
          "empirical_p_high": 0.10977804439112178,
          "empirical_p_low": 0.9088182363527294,
          "n_sims": 5000,
          "null": "uniform Gregorian date within same birth year"
        },
        "WaterCount": {
          "observed_sum": 525.0,
          "observed_mean_per_player": 1.0479041916167664,
          "null_mean_sum": 541.8184,
          "null_mean_per_player": 1.0814738522954093,
          "null_sd_sum": 17.84028801940493,
          "z": -0.9427202061820178,
          "empirical_p_high": 0.8336332733453309,
          "empirical_p_low": 0.1841631673665267,
          "n_sims": 5000,
          "null": "uniform Gregorian date within same birth year"
        },
        "MetalWaterCount": {
          "observed_sum": 1093.0,
          "observed_mean_per_player": 2.1816367265469063,
          "null_mean_sum": 1098.5308,
          "null_mean_per_player": 2.19267624750499,
          "null_sd_sum": 21.87325168299943,
          "z": -0.2528567805169411,
          "empirical_p_high": 0.6058788242351529,
          "empirical_p_low": 0.4123175364927015,
          "n_sims": 5000,
          "null": "uniform Gregorian date within same birth year"
        }
      }
    },
    "1994_F": {
      "WaterDM_count": 33,
      "WaterDM_share": 0.16417910447761194,
      "WaterCount_mean": 0.9104477611940298,
      "MetalCount_mean": 0.9751243781094527,
      "MetalWaterCount_mean": 1.8855721393034826,
      "calendar_null": {
        "WaterDM": {
          "observed_sum": 33.0,
          "observed_mean_per_player": 0.16417910447761194,
          "null_mean_sum": 40.3058,
          "null_mean_per_player": 0.20052636815920397,
          "null_sd_sum": 5.662817307663386,
          "z": -1.2901352106332644,
          "empirical_p_high": 0.9180163967206558,
          "empirical_p_low": 0.11137772445510898,
          "n_sims": 5000,
          "null": "uniform Gregorian date within same birth year"
        },
        "WaterCount": {
          "observed_sum": 183.0,
          "observed_mean_per_player": 0.9104477611940298,
          "null_mean_sum": 204.4298,
          "null_mean_per_player": 1.0170636815920397,
          "null_sd_sum": 10.983788084269289,
          "z": -1.951039098313562,
          "empirical_p_high": 0.9798040391921615,
          "empirical_p_low": 0.024795040991801638,
          "n_sims": 5000,
          "null": "uniform Gregorian date within same birth year"
        },
        "MetalWaterCount": {
          "observed_sum": 379.0,
          "observed_mean_per_player": 1.8855721393034826,
          "null_mean_sum": 412.424,
          "null_mean_per_player": 2.0518606965174127,
          "null_sd_sum": 13.71801227482154,
          "z": -2.4365045992375594,
          "empirical_p_high": 0.9932013597280543,
          "empirical_p_low": 0.007998400319936013,
          "n_sims": 5000,
          "null": "uniform Gregorian date within same birth year"
        }
      }
    },
    "2013_M": {
      "WaterDM_count": 94,
      "WaterDM_share": 0.18762475049900199,
      "WaterCount_mean": 1.095808383233533,
      "MetalCount_mean": 1.0858283433133733,
      "MetalWaterCount_mean": 2.1816367265469063,
      "calendar_null": {
        "WaterDM": {
          "observed_sum": 94.0,
          "observed_mean_per_player": 0.18762475049900199,
          "null_mean_sum": 100.4322,
          "null_mean_per_player": 0.2004634730538922,
          "null_sd_sum": 9.084046848262524,
          "z": -0.7080764891949297,
          "empirical_p_high": 0.7728454309138172,
          "empirical_p_low": 0.264747050589882,
          "n_sims": 5000,
          "null": "uniform Gregorian date within same birth year"
        },
        "WaterCount": {
          "observed_sum": 549.0,
          "observed_mean_per_player": 1.095808383233533,
          "null_mean_sum": 556.1272,
          "null_mean_per_player": 1.1100343313373253,
          "null_sd_sum": 17.397090328856205,
          "z": -0.40967770272355675,
          "empirical_p_high": 0.6602679464107178,
          "empirical_p_low": 0.3629274145170966,
          "n_sims": 5000,
          "null": "uniform Gregorian date within same birth year"
        },
        "MetalWaterCount": {
          "observed_sum": 1093.0,
          "observed_mean_per_player": 2.1816367265469063,
          "null_mean_sum": 1094.7726,
          "null_mean_per_player": 2.185174850299401,
          "null_sd_sum": 22.071418593822845,
          "z": -0.08031201041586475,
          "empirical_p_high": 0.5428914217156569,
          "empirical_p_low": 0.4771045790841832,
          "n_sims": 5000,
          "null": "uniform Gregorian date within same birth year"
        }
      }
    },
    "2013_F": {
      "WaterDM_count": 33,
      "WaterDM_share": 0.165,
      "WaterCount_mean": 1.145,
      "MetalCount_mean": 1.075,
      "MetalWaterCount_mean": 2.22,
      "calendar_null": {
        "WaterDM": {
          "observed_sum": 33.0,
          "observed_mean_per_player": 0.165,
          "null_mean_sum": 39.9538,
          "null_mean_per_player": 0.199769,
          "null_sd_sum": 5.68754210419909,
          "z": -1.2226371027418044,
          "empirical_p_high": 0.9064187162567486,
          "empirical_p_low": 0.130373925214957,
          "n_sims": 5000,
          "null": "uniform Gregorian date within same birth year"
        },
        "WaterCount": {
          "observed_sum": 229.0,
          "observed_mean_per_player": 1.145,
          "null_mean_sum": 221.387,
          "null_mean_per_player": 1.106935,
          "null_sd_sum": 11.139679056862365,
          "z": 0.6834128668464798,
          "empirical_p_high": 0.2623475304939012,
          "empirical_p_low": 0.7644471105778844,
          "n_sims": 5000,
          "null": "uniform Gregorian date within same birth year"
        },
        "MetalWaterCount": {
          "observed_sum": 444.0,
          "observed_mean_per_player": 2.22,
          "null_mean_sum": 428.7462,
          "null_mean_per_player": 2.143731,
          "null_sd_sum": 14.130481933180226,
          "z": 1.0794960902346924,
          "empirical_p_high": 0.14817036592681462,
          "empirical_p_low": 0.8692261547690462,
          "n_sims": 5000,
          "null": "uniform Gregorian date within same birth year"
        }
      }
    }
  }
}
```
