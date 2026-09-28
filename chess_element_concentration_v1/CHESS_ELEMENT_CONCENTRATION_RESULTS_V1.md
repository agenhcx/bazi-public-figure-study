# Chess Elemental-Concentration Results V1

Status: post-reveal exploratory; plan frozen before first concentration calculation.

## Frozen primary performance test
- 2023 NEW_TARGET pooled: distinct-elements vs Elo-z rho=0.11495, directional p=0.998820, two-sided p=0.002440

## Frozen primary selection test
- 2023 NEW_TARGET pooled: observed mean distinct elements=3.66762, null=3.69193, z=-0.9134, directional p=0.188341

## Eight-stratum direction consistency
- Performance rho<0: 2/8
- Selection observed<null: 3/8

## Distinct-elements performance by stratum
- 1994_M: rho=0.05232, p_dir=0.876722
- 1994_F: rho=0.03294, p_dir=0.675866
- 2013_M: rho=-0.03611, p_dir=0.210656
- 2013_F: rho=0.09323, p_dir=0.905842
- 2023_M_FULL: rho=-0.05115, p_dir=0.125437
- 2023_F_FULL: rho=0.05490, p_dir=0.781064
- 2023_M_NEW_TARGET: rho=0.12491, p_dir=0.997360
- 2023_F_NEW_TARGET: rho=0.08584, p_dir=0.887022

## Distinct-elements selection by stratum
- 1994_M: obs=3.66267, null=3.66021, z=0.0790, p_dir=0.544273
- 1994_F: obs=3.66169, null=3.64371, z=0.3613, p_dir=0.656117
- 2013_M: obs=3.56886, null=3.59829, z=-0.9339, p_dir=0.182541
- 2013_F: obs=3.70000, null=3.60965, z=1.8000, p_dir=0.968252
- 2023_M_FULL: obs=3.65269, null=3.65105, z=0.0520, p_dir=0.535073
- 2023_F_FULL: obs=3.69802, null=3.65592, z=0.8475, p_dir=0.816609
- 2023_M_NEW_TARGET: obs=3.65868, null=3.69187, z=-1.0618, p_dir=0.152892
- 2023_F_NEW_TARGET: obs=3.69000, null=3.69289, z=-0.0584, p_dir=0.501675