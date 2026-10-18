# France Academy: 16 additional historical original-volume TOC probes, then frozen 172-volume local shard plan v1

Checkpoint 2026-10-18 UTC, **source-collection only**, no BaZi/outcome unblinding or official person admission. The 1835–1940 journal volume inventory is not a complete historical full-member roster.

## Cumulative source availability now checked

The historic *Comptes rendus hebdomadaires des séances de l’Académie des sciences* includes 211 half-year original journal volumes 1835–1940; an official Academy year-volume-archive crosswalk had already been established and verified on the previously frozen record. This checkpoint adds a **third, disjoint** set of table-of-contents (TOC) probes spread across all seven periods of the Academy's retrospective indexes.

| Source-audit sample | TOCs actually requested | Returned valid HTML/200 | HTTP404 at intended TOC subpage | Recognized election headings | Transcribed election-event candidates |
|---|---:|---:|---:|---:|---:|
| Frozen earlier discovery | 11 | 9 | 2 | 6 | 40 |
| Frozen separate holdout | 12 | 6 | 6 | 2 | 8 |
| **New third batch** | **16** | **11** | **5** | **6** | **38** |
| **Combined nonoverlapping observed totals** | **39** | **26** | **13** | **14** | **86** |

The 86 rows count parsed journal **index election occurrences**, including different historical member categories, not 86 distinct regular members, and not 86 born-1835–1985 eligible scientific achievers. We have **not** directly scanned each original election page; this batch relies on the historical Wikisource TOC transcriptions. The 13 observed 404s are specific TOC-URL responses, not proof the underlying original indexed books have vanished or that no person was elected. All 172 remaining volumes were kept explicitly **NOT_YET_PROBED**.

Third-batch individual TOCs:

| Original volume | Year | Status | Election index event candidates |
|---|---:|---|---:|
| 4 | 1837 | HTTP404 | not known |
| 24 | 1847 | HTTP404 | not known |
| 43 | 1856 | HTTP200 | 0 *parsed* (election heading present, structure requires manual audit) |
| 61 | 1865 | HTTP200 | 0 *parsed* |
| 72 | 1871 | HTTP200 | 0 *parsed* |
| 89 | 1879 | HTTP200 | 2 |
| 101 | 1885 | HTTP404 | not known |
| 117 | 1893 | HTTP200 | 0 *parsed* |
| 130 | 1900 | HTTP200 | 0 *parsed* |
| 144 | 1907 | HTTP200 | 0 *parsed* |
| 154 | 1912 | HTTP200 | 7 |
| 164 | 1917 | HTTP200 | 9 |
| 172 | 1921 | HTTP404 | not known |
| 186 | 1928 | HTTP200 | 6 |
| 194 | 1932 | HTTP200 | 14 |
| 206 | 1938 | HTTP404 | not known |

**Quality follow-up**: Volume 43/1856 has a recognized election heading but 0 parsed person rows, demonstrating that a zero parser result cannot be interpreted as a real no-election semester. Review early markup/role grammatical variants, then inspect a few original page images before scaling that era.

Successful bounded GitHub source run: https://github.com/agenhcx/bazi-public-figure-study/actions/runs/39122671285 .

## Frozen, era-stratified next-stage source plan

The 39 inspected volumes are excluded by volume number from the previously archived two 211-row inventories plus the third 16-volume result. The remaining **172** are all inventoried original publications whose intended Wikisource TOC endpoints have **not** yet been requested in these three sampling frames.

These 172 are deterministically assigned to **11 disjoint batches**, ten batches of 16 and one final batch of 12. The ordering cycles through seven Academy retrospective index periods (volumes 1–31, 32–61, 62–91, 92–121, 122–151, 152–181, and 182–211). This balances early and later period access issues. The plan was saved **before** performing any of its own network queries.

Fixed source-only plan: `data/france_academy_unprobed_16_volume_batch_v1/remaining_172_toc_shard_plan_v1.csv`, with per-volume year, public official original link, transcribed Wikisource TOC target, shard, sequence and `NOT_YET_PROBED` state. **Do not rewrite or remove a missing volume after seeing a source error**, because that would distort historical completeness and missingness audits.

## Locally reusable batch runner

`scripts/france_academy_run_remaining_172_toc_batch_v1.py` reuses the existing tested 211-volume source inventory reader, with fixed plan, SHA-bearing per-volume fetch responses, indexed event role counts and an existing local cache. Python >=3.10 with pinned compatible `beautifulsoup4`.

From the repository root on Windows, each command is a single PowerShell line:

1. `git pull --ff-only`
2. `python .\scripts\france_academy_run_remaining_172_toc_batch_v1.py --fixture-check`
3. `python .\scripts\france_academy_run_remaining_172_toc_batch_v1.py --shard 0` (dry-run preview, **no network**)
4. `python .\scripts\france_academy_run_remaining_172_toc_batch_v1.py --shard 0 --run` (actual bounded 16-volume query, >=1.5 seconds between requests, source response cache reused; output under `local_runs/france_academy_remaining_172_toc_batches_v1/shard_00/`).

Once an individual shard's summary is reviewed, choose `--shard 1` through `--shard 10`; **do not blindly launch all 11 if the early shard reveals missing source templates or parsing shortcomings**. `--offline --run` can reprocess existing cached responses without network if those sources are locally available.

The script deliberately has no default live mode; `--run` must be supplied explicitly, and a source-access 403/429 is reported as a restriction rather than a missing historical member. Each shard locally writes `summary.json`, `academy_original_wikisource_211_volume_inventory_v1.csv`, and `source_only_shard_checkpoint_v1.json` with zero research acceptance.

Python 3.10 and 3.13 offline fixture/dry-run CI: https://github.com/agenhcx/bazi-public-figure-study/actions/runs/39122965734 .

## Integrity and research design

- 211 original journal volumes ≠ complete 1666–2025 Academy member census.
- A TOC HTTP200 ≠ full-text original election page verified.
- A successful election-index event ≠ an original legal/effective full-member admission.
- Correspondant, foreign, nonresident, and historically defined member categories remain separately tagged, not silently merged.
- Approval and vote notices may be in distinct half-year volumes; this was separately audited in `FRANCE_ACADEMY_VOTE_DECREE_CROSS_VOLUME_SOURCE_AUDIT_V2.md`.
- Frozen CTHS 562 biographies, original full-member evidence and DOB dates, two unresolved French birthday conflicts, and entire Nobel/other-academies frozen rule set are untouched.
- **All** new roster membership admissions=0; accepted DOBs=0; BaZi variables computed=0. No automatic acceptance from a Wikisource transcript.

Suggested next technical work is to inspect *source grammar* for the early-year volume 43/1856 zero parser case, then run the next 16-volume batch from the frozen 172 source plan, assess structured missingness by era, and scale only after first-party election scan spot-checks.
