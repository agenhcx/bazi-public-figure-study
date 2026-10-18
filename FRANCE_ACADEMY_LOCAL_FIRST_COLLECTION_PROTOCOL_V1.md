# France Academy: local-first collection and compact handoff protocol v1

**Scope:** Evidence collection and DOB provenance, without any BaZi variable calculation.
**Starting checkpoint:** The original 562 CTHS biography pages, raw HTML SHA-256 bundle, and 529 parsable day-level CTHS birth-date *claims* already exist on main. Do not download them again from the source site.

## Local-first workflow

1. I implement/refine a deterministic script against a frozen input and verify on a small (10–30) pilot, optionally in GitHub Actions. Define the source and field acceptance policy before expanding to the full queue.
2. The user runs the bulk collection on their Windows machine. For *new network collection* (not the existing offline audit), require durable per-person checkpoints, local cache, explicit timeout/retry, rate limit, resumability, source SHA-256 and no silent status promotion. Do not start bulk collection until these tests pass.
3. Results remain in the local working folder. I analyze summary, exceptions, and source conflicts supplied by the user. Don't paste full logs, 500+ rows, or the raw HTML archive into chat.
4. If provenance and parsing are stable, checkpoint audit CSV / source references / hashes to GitHub with an appropriately scoped commit and a PR or tag. Retain prohibited sources out of accepted DOB rows and keep full-member status independently adjudicated.
5. Only after all primary institution/tier cohorts and the joint analysis specification are frozen, run the BaZi transformation. This protocol does not change those research rules.

## Immediately runnable offline integrity audit

This checks all 562 already-captured CTHS HTML source hashes, candidate DOB parse assertions and person IDs, without internet access or refetching the source site. Python standard library only, Python >=3.10.

From the existing clone root `C:\chenxi\bazi_project\1986wiki` in PowerShell, use **single-line** commands:

`git pull --ff-only`

`python .\scripts\france_academy_cths_local_audit_v1.py`

The output directory is `local_runs/france_academy_cths_source_audit_v1/` and is excluded from version control. It produces:

| Filename | Purpose | Share with assistant? |
|---|---|---|
| `summary.json` | Coverage, zero-network confirmation, raw HTML integrity and counts | Yes |
| `source_and_membership_review_queue.csv` | Only records with DOB parse gaps or mixed historical role | Yes |
| `dob_independent_source_verification_queue.csv` | All exact CTHS assertions that still need independent source verification | Not necessary by default; keep locally or commit if useful |
 
The audit script does not conduct independent DOB verification. Thus `verified_independent_DOB_count=0` remains correct at this stage; data presence is not evidence independence.

## What future collector scripts must provide before bulk run

- `--limit 20` for smoke tests; `--resume` to reuse fetched success records and retry only failures, `--offline` for deterministic parsing without network, and `--out` to keep source data under `local_runs/`.
- One per-person status, evidence source, date precision, source URL and capture hash; failed responses never become empty birthdates.
- Strict 1835–1985 year-range **priority** for France, yet maintain a complete institution roster separately. No shortcuts from Wikidata/CTHS day-precision date to accepted exact DOB.
- Politely spaced requests, explicit fixed concurrency and finite retry/backoff; do not bypass a provider's access limits.
- The assistant should focus on `summary.json`, `conflicts.csv`, `unresolved.csv` rather than the entire raw collection.

## Sanity checks

Expected from the prior completed source snapshot:

- `persons_checked=562`
- `CTHS_source_claims_parseable_exact=529`
- 32 incomplete/unparsed date assertions and one no birth metadata (may overlap with mixed-role review)
- `raw_source_integrity.complete=true`
- `verified_independent_DOB_count=0`
- `bazi_variables_computed=0`

Every content checksum is verified against the captured snapshot, not live web content.
