# Installation

Extract this ZIP into the repository root. It adds:

- `LEOPOLDINA_COVERAGE_MISSINGNESS_FREEZE_PLAN_V1.md`
- `scripts/freeze_leopoldina_coverage_missingness_v1.py`
- `.github/workflows/leopoldina_coverage_missingness_freeze_v1.yml`

It does not overwrite the repository `README.md`; this package README is stored
inside the ZIP only for installation guidance.

Run:

```powershell
python .\scripts\freeze_leopoldina_coverage_missingness_v1.py --self-test
python .\scripts\freeze_leopoldina_coverage_missingness_v1.py
```

Expected headline counts include 2,888 roster rows, 2,407 candidate rows, 724
accepted candidate rows, 1,681 unresolved candidate rows, 2 excluded invalid
candidate rows, 54 official-only accepted rows, and 778 combined accepted exact
DOB rows. No BaZi variable is computed.
