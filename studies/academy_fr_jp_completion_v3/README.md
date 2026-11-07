# France and Japan academy continuation v3

This round continues the v2 country gaps without changing its source bytes, decisions or analysis gates. The baseline is commit `a7297e662502ce821c9289dc7d5226b82208b92d`; the required v2 file hashes are pinned in `inputs/baseline_provenance.json`. Professor collection remains paused. Neither country is declared complete or frozen for analysis.

## France: ordinary-membership evidence

The selected queues contain 28 modern membership-only gaps and 60 historical CTHS membership-only gaps. The bounded historical search produced actual positive sources for 20 cases; an unsuccessful filename probe or absence from a source is not evidence of nonmembership. Together, 48 reviewed decisions yield 21 strict ordinary-membership approvals: nine modern and twelve historical. Academy originals and relevant pages were visually checked; an independent reviewer checked all twelve historical positives.

| Dimension | v2 baseline | v3 current |
|---|---:|---:|
| Candidate groups | 877 | 877 |
| Accepted identity | 755 | 755 |
| Accepted exact DOB | 744 | 744 |
| Strict ordinary membership | 246 | 267 |
| All three dimensions | 244 | 265 |
| Groups with at least one remaining gap | 633 | 612 |

Of these groups, 290 have ordinary-role support and 288 have a stable election cutoff. Identity, DOB, role and cutoff together have support for 285 groups, but this does not replace the stricter 265-row table. A source proving membership by a dated document is kept as an upper bound, not a fabricated election year. Precise election chronology conflicts remain visible. Five newly identified conflicts bring that flag to 24 rows.

Ordinary nonresident members are retained as an explicit full-member subtype. Correspondent and foreign-associate observations do not prove lifetime exclusion and do not erase an earlier supported full role. Institut de France's own typed Academy subject files are identified as parent-institution first-party records; they are not counted as independent corroboration of Academy records. Conflicting first-party dates are not resolved by source majority.

Laveran and Roubaud's printed dates were checked against OCR errors. Moureu's incompatible original statements and Fage's conflicting chronology remain held. Fage's earlier role is bound to the original dated speech and its internal successor statement, rather than inferred only from a later printed author heading. Gaston Delépine was rejected as a wrong-person source for Marcel Delépine. No inherited DOB, identity, source-calendar or external Santy/Abragam disposition was relaxed by this membership-only pass.

## Japan: body-source DOB evidence

Three fixed 60-person science queues were searched in parallel. The 47 section gaps and seven prior identity-assignment holds were handled separately. The seven identity holds now have career/date/institution bridges and their preserved dates can be recomputed. No new direct section evidence was obtained: the restored universe is still 482 IDs, with 428 broad Section II support, seven Section I exclusions and 47 unresolved sections.

| Source-date status | v2 | v3 |
|---|---:|---:|
| People with body birth information | 157 | 249 |
| Day components without a known unresolved conflict | 120 | 213 |
| Institution, university or organization day support | 120 | 169 |
| Edited-reference-only day support | 0 | 44 |
| Nonexcluded candidates without the day status | 355 | 262 |
| Combined DOB and section action queue | 364 | 273 |

The source tiers are deliberately separate. Complete attributed entries from edited commercial biographical dictionaries supply a secondary layer; they are not institution records, Wikipedia dates, name-only authority matches or independent votes. An institution's year-only statement does not convert a secondary full date into institution-supported day evidence. Among the 213 day rows, 202 also have broad Section II support and 212 have source birth years in 1835–1985. All final-cohort acceptance flags remain false.

The source batches include the genetics society's historical presidents table, the organic-synthesis society's honorary-member birth table, a physics-society chronology, university and professional biographies, and a bounded set of edited-reference subjects. Their birthday fields were distinguished from award, appointment, death and publication dates. Dates supplied literally as January 1 were not collector defaults. Source-supplied calendar pairs, unconverted old-calendar expressions and original precision remain explicit.

Independent QA verified the 21 matches in the three main tables, reference transcription and difficult engineering PDFs. Toriyama's same-page month/day discrepancy is retained as two claims. Three new dictionary/institution conflicts from shard A remain held. Root follow-up read the previously snippet-only Yamashita reference: it really gives May 21, competing with the professional museum's May 2. Both bodies are now retained, with no selected date. There are eight DOB-source conflicts and 17 calendar holds in the current status ledger.

The prior claim that all 38 discovered NDL portrait links had been consumed was too broad. Three people had no body birth claim in v2: Takamatsu, Sano and Kozai. Their already-discovered pages were read this round. Three other unused portrait URLs belonged to people whose birth dates already came from other sources. The correction is recorded without editing historical v2 files. The year-only NDL Authorities route was not recrawled.

## Files and replay

`source_batches/` contains only approved short transcriptions and metadata. Full copyrighted HTML, PDFs, dictionary entries and private review images are excluded. The original failed/error responses are not represented as valid source captures. Some worker records retain web-body observations with no original-byte hash; the independent QA identifies the limits of its own raw-byte review.

`inputs/` contains deterministic concatenated claims and reviewed overlays. `outputs/` contains both current masters, claims, decisions and explicit gaps. Preparation, assembly and verification make no source requests. The source facts were reviewed by humans; an offline replay verifies the pinned decisions, not fresh factual agreement with changing websites.

From the repository root, use fresh output directories:

```bash
python3 -m unittest discover -s studies/academy_fr_jp_completion_v3/tests -v
python3 studies/academy_fr_jp_completion_v3/scripts/prepare_inputs.py --output-dir /tmp/academy-v3-inputs
python3 studies/academy_fr_jp_completion_v3/scripts/assemble.py --output-dir /tmp/academy-v3-output
diff -r studies/academy_fr_jp_completion_v3/outputs /tmp/academy-v3-output
python3 studies/academy_fr_jp_completion_v3/scripts/verify_study.py
```

The workflow compares all four prepared input files as well. Existing v1/v2 tests and replays remain in place. Country counts describe these restored candidate sets and evidence definitions; they are not national missing-birthday denominators. No BaZi or outcome analysis was performed.
