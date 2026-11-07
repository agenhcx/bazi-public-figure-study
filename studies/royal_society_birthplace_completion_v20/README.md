# Royal Society birthplace completion v20

This batch adds four first stored birthplaces to the fixed 4,983 UK Royal Society records: two new birthplace-support S2 observations and two S3 observations. One birthplace also resolves North; three retain unknown geography. A separately declared, one-record authority-graph geography pilot yields no adoption. These birthplace grades do not change original DOB-source grades or the existing DOB-based S2 versus S2+S3 comparison groups.

| Scope | North | South | Unknown | Total |
|---|---:|---:|---:|---:|
| All fixed UK records | 4,172 | 186 | 625 | 4,983 |
| Native DOB 1835–1985, inclusive | 2,272 | 181 | 191 | 2,644 |

The native DOB window now has 137 unknown records with blank birthplace and 54 with a stored birthplace but unknown geography. Across the full cohort these numbers are 559 and 66. The 141-record initial blank-place pool is a queue, not a claim that 141 biographies were inspected. This batch reviewed eight fixed blank-place subjects and one existing-place geography subject: four birthplace adoptions, zero geography-only adoptions and five holds. Exactly 4,979 complete record objects remain identical to v19.

| Record | New raw birthplace | Birthplace support | Geography | Evidence limit |
|---|---|---|---|---|
| NA4166, William Reginald Stephen Garton | Chelsea | S2 | Unknown | Signed original scientific memoir carried on ResearchGate; exact DOB and full identity verified. No original PDF bytes acquired. |
| NA4036, John Edwin Midwinter | Newbury, Berkshire | S2 | North | Signed expert obituary; matching full name/exact DOB and UCL career context. Native authority endyear2011 versus source death2021 remains unresolved. |
| NA2044, Dennis John Crisp | London | S3 | Unknown | Original BIOGRAPHIES entry uses an inspected conventional birth-date/place then death-date/place bracket. No literal born label or legend observed. |
| NA1998, Basil Kassanis | Macedonian born | S3 | Unknown | Literal institutional catalogue birth-region wording; catalogue DOB precision is year only. Separate annotated Macedonia interpretation assigns no modern country or hemisphere. |

The initial compatible-lifespan gate would hold Midwinter. After observing that case and before adoption, the parent explicitly adopted a bounded death-endpoint-only admission amendment. It requires original full native name, exact unchanged native DOB, multiple distinctive career anchors, additional original institutional identity context, no competing identity/birthdate conflict and no death-date selection effect. The original authority label, DOB, identity and eligibility stay frozen; no deathyear correction is made. The Guardian and UCL publications share Bayvel attribution and are not counted as independent birth/date confirmation. Conservative S2 for a signed edited obituary by a named professional colleague is an explicitly reviewed source-genre judgment, not a host-based S1 or peer-review claim. See `audit/method_qa.json` and `audit/parent_adjudication.json` for the actual post-observation timing and gates.

Crisp's source relationship is an explicitly disclosed structured-format interpretation after inspecting the original section and neighboring layouts. S3 does not excuse an ambiguous subject/birth-place relation. Kassanis retains literal wording in `raw_birthplace`; nationality, associated collection place and photographer address do not supply birth geography.

The separate Adam/NA4918 pilot preserves the prior Cambridge birthplace and every evidence field. Lobid documentation/access was denied; the person record and a separately authorized first inspection of the original DNB base record were tool-inaccessible. No semantic person body, placeOfBirth edge or typed place record was obtained. No retry, endpoint variants or geocoder inference was used.

Argyris and Laver remain active DOB-source conflict holds in `audit/active_source_DOB_conflicts.json`. Argyris has an original born-year1913 versus native1916 discrepancy; Laver has a source profile-header birthyear1925 versus native1929 discrepancy. Neither is covered by a death-endpoint exception or bypassed through dateless sources. Midwinter's unresolved death-endpoint discrepancy is recorded separately.

Source work comprised 14 discovery queries, 18 worker navigation attempts and 8 root parsed-source/context opens, plus one parsed find and one unsuccessful cached screenshot attempt. There were no raw HTTP/PDF GETs. Two group-A adaptive queries had intent logged after their requests; that deviation is retained rather than presented as preregistration. Planned original-source opens had prior intent. Tool-reported errors remain separate from unknown raw status, time and byte hashes. Failed routes were stopped. Garton is an original work on an external carrier; Crisp is a compiled biographical bibliography; Kassanis is uncredited institutional catalogue metadata. Hosting alone does not establish source quality.

## Files and replay

`outputs/birthplace_rows.jsonl.gz` is the complete current master in the ZIP; `outputs/birthplaces.csv` is a readable projection. `outputs/remaining_unknown_window.csv` has the 191 remaining window records. `outputs/changes.json` and `outputs/summary.json` provide exact deltas and counts. Versioned facts include previous values and previously absent fields for reversible updates. The old 45 CSV columns retain their meanings; six v20 birthplace columns and five separate v20 geography-support columns are appended.

Run from the repository root with a single command:

```sh
python studies/royal_society_birthplace_completion_v20/scripts/replay.py
```

Replay uses the included v10 carrier plus frozen v11–v19 facts/scopes to reconstruct exact v19 before applying v20. It performs no web collection. Baseline v19 commit is `25b6b8f40d148d2e6c61235675446bbbfbdb4928`; baseline canonical JSONL SHA256 is `5c8d93078101a69b32c9652c6bcbc99ce926c2dd4bd50547e235071ae377c043`. Gzip uses blank filename and zero mtime. The compressed output master is packaged for download and reproduced by the script; it is not duplicated as a new Git blob. `MANIFEST.sha256` covers every distributed file except itself, and excludes Python caches.

Audit files distinguish worker observations, original strict holds, the parent's final adjudication, method review, source QA and independent replay QA. Short source excerpts contain at most 25 distinct English words per original work across the package. No full original HTML/PDF, images, graph dumps or source-projection caches are distributed. Source QA reviews worker/root observations and does not claim another independent original acquisition.

Native DOB/calendar, authority identity, fixed cohort/eligibility, country/QIDs/personal coordinates, original DOB grades, prior selected evidence, hashes, official-field status and all prior versioned facts stay unchanged. Only the four declared current birthplace/geography updates and their versioned rollback facts differ. No other cohort, cross-cohort statistical deduplication, BaZi, outcomes or final cohort freeze is performed.
