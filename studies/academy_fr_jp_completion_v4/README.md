# France and Japan academy continuation v4

This bounded continuation starts from the unchanged v3 commit `f5058c523402f1ed6df19df815400969a9c0a4de`. The selected Japanese queues contain 122 science candidates not yet individually processed or with only year/month evidence. Another worker takes 25 previously unsuccessful people through a different edited-reference route. The French queues contain 120 historical membership gaps outside the preceding 60-person batch. Neither country is complete or frozen for analysis. Professor collection stays paused.

| Evidence measure | v3 | v4 |
|---|---:|---:|
| Japan people with body birth information | 249 | 363 |
| Japan day status without a known unresolved conflict | 213 | 310 |
| Institution/university/organization day support | 169 | 195 |
| Edited-reference-only day support | 44 | 114 |
| Other attributed secondary-only day support | 0 | 1 |
| Nonexcluded Japan candidates without day status | 262 | 165 |
| Combined Japanese date/section queue | 273 | 177 |
| France strict ordinary membership | 267 | 290 |
| France identity, membership and DOB all accepted | 265 | 288 |

The Japanese universe remains 482 IDs: 428 broad Section II support, seven Section I exclusions and 47 unresolved sections. The 310 day rows include 298 with broad Section II support. The 475 nonexcluded candidates are not a frozen eligible national cohort. Source calendars, old-calendar expressions, source-supplied dual expressions and original precision remain explicit; no collector calendar conversion or default date filling occurs.

The additional secondary-only reproduction is a named public financial-filing reproduction. It is separated from the 114 edited dictionary cases and is not described as an issuer-original document. Complete attributed dictionary bodies are separate from institutional support and from name-only NDL authority candidates. An institutional year-only source does not promote a secondary day into institution-supported day evidence.

The already captured 2007 Academy award release was parsed across all nine award blocks and eleven recipients, yielding five existing roster IDs. The Sendai honorary-citizen source was likewise checked across the existing 482 IDs. Neither prize receipt nor honorary citizenship is used as Academy-membership proof. No new nonroster awardees/citizens are added. One redundant Sendai GET is recorded honestly; the remaining use reuses captured bytes.

Independent QA identified two errors before publication: Kon Yutaka's same-page dictionary disagreement was missing a second birth claim, and Sasaki Satohiko's printed August had been misread as June. The actual two-source disagreement is retained; the reader's June error is corrected rather than fabricated as a source conflict. Genuine new same-subject contradictions, unconverted dates and unverified competing leads remain distinct holds. Added old-calendar expressions for Honda and Shiga do not erase previously supported source-supplied modern dates.

France retains 877 candidate groups, 755 identity approvals and 744 DOB approvals. Forty reviewed membership decisions yield 23 additional strict approvals and 288 all-three groups; 589 groups still lack at least one dimension, not 589 missing birthdays. Role/cutoff evidence and exact election chronology remain separate. Source-dated role bounds are not election dates, nonresident ordinary members keep their subtype, and correspondent/foreign-associate events do not establish lifetime exclusion.

Two original A proposals were explicitly reconciled during integration: Tilho's existing PDF supplies an actual 1932 full-member election, while Urbain's year is refined to 1921-05-09. Louis de Broglie's newly read 1933 page does not silently override the inherited Academy PDF printing 1873 for the 1892-born subject. The impossible source event stays held. Cot's first-person 1946 membership statement is attached to Cot, not the eulogy's subject Tilho. Earlier source files and approvals remain intact.

`source_batches/` contains short transcriptions and approved metadata, not full copyrighted HTML/PDFs or private review images. `source_audits/` records independent review and integration limits. `inputs/` contains deterministic selections and overlays; `outputs/` contains current masters, claims, decisions and gaps. Replays check pinned decisions and bytes, not a new web recrawl or independent regeneration of human source interpretation.

From the repository root, with fresh output directories:

```bash
python3 -m unittest discover -s studies/academy_fr_jp_completion_v4/tests -v
python3 studies/academy_fr_jp_completion_v4/scripts/continue.py prepare --output-dir /tmp/academy-v4-inputs
python3 studies/academy_fr_jp_completion_v4/scripts/continue.py assemble --output-dir /tmp/academy-v4-outputs
diff -r studies/academy_fr_jp_completion_v4/outputs /tmp/academy-v4-outputs
python3 studies/academy_fr_jp_completion_v4/scripts/continue.py verify
```

The workflow also compares all four prepared inputs. All ancestor inventories remain unchanged. No BaZi or outcome analysis was performed.
