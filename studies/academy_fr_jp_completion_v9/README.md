# France/Japan continuation v9 — 2026-10-29

This collection-only continuation starts from immutable v8 commit `928c3a5444bba55e421b400c2579e8ac5a29d0f9`. All earlier evidence, identity keys and source-calendar expressions remain unchanged. No analysis cohort is frozen and no BaZi variables are computed. Professor collection remains paused; Fields data remain parked.

| Current working ledger | France | Japan |
|---|---:|---:|
| Stable candidates | 877 | 482 |
| Day-level birth evidence | 744 | 368 |
| Strict ordinary membership | 394 | — |
| Identity, birth and membership all supported | 392 | — |

## Fixed selection and actual searches

All 60 selected French candidates and all five selected Japanese candidates received individual targeted searches. French selection came from 150 current membership gaps whose historical person-level query coverage was unknown; unknown does not mean never searched. The Japanese selection contains two calendar cases outside v7's fixed calendar queue and three date cases that v7 explicitly did not newly search.

France adds 13 strict ordinary memberships: 12 fixed candidates and Charles Camichel1936 from the same Academy-journal original, outside the fixed60. Camichel had no new individual query and is not counted as a61st targeted person. Nineteen new source decisions comprise13 strict approvals and six holds. Identity755 and DOB744 remain unchanged; all25 inherited chronology holds remain. The fixed60 now have explicit targeted coverage regardless of acceptance:12 strict,48 still membership gaps. Removing these60 from the prior unknown150 leaves90 historical-coverage-unknown identities; the source-only Camichel approval removes one further current membership gap, leaving89 current gaps with unknown historical query coverage. The exact IDs and limits are pinned in `source_audits/france_targeted_coverage_continuation.json`. The v8 group of21 searched-and-parked cases is retained separately, not relabelled unsearched.

France's source workers recorded104 literal queries, including one source-context query. The root role-typing review added two separate discovery queries, and the bulk-route scout added eight; neither activity inflates the fixed-person search denominator. The scout found no new source claims. Old Gallica403 routes were not retried. Source-only leads, including Escande whose DOB is not accepted, remain unapplied metadata.

The Chardonnet source supplies the literal1919-05-12 section-seat event but does not type an ordinary full-member role. Root and independent QA retained it as a hold under the existing Gravier precedent. No accepted ordinary-election date/year is manufactured from the event. Correspondent/foreign membership, as-of bounds, presidency, relative arithmetic and the notice author's title remain insufficient. Ordinary free/nonresident membership remains eligible only when explicitly typed.

Japan's five people received15 person queries plus three publisher-context queries. Only one new body claim was admitted; the three date cases produced no new claims. The actual Japan ledger contains528 distinct claims for433 people. The368 day statuses without known unresolved conflict comprise215 institution/university/organization supported,150 edited-reference-only and three other attributed-secondary-only. The other category separately retains the financial-filing reproduction, attributed HLA preview and this round's third-party reproduction of a university publication.

## Exact calendar routing and evidence tier

Terao Hisashi寺尾寿 gains the source-supplied date1855-11-04. 福井崇時's historical compilation explicitly pairs安政2年9月25日 with1855年11月4日 on actual PDFp36/printed499 footnote19 and supplies an astronomy career identity bridge. The complete PDF was captured from a third-party host; Chubu University's official issue index independently confirms the article/author, issue15/year2013 and university issuer. No official university download bytes or authenticated PDF link were captured. The exact tier `third_party_attributed_university_publication_reproduction_secondary` is therefore other-secondary, not institution-hosted or edited-reference evidence. Peer review and a literal Gregorian/new-calendar label are not claimed.

Root and independent QA verified the original hash, actual birth page and publisher attribution. The exact approval binds the new source/date, claims-file hash, independent-QA hash and worker-manifest hash. The later synthesized hold record was not the whole routing origin: an explicit pure calendar-routing overlay also exists in immutable v2. Root separately approved only Terao's exact original v2 file hash/record and sole historical noncomparable claim. No comparable-date conflict is adjudicated. After normal V4 replay, the local single-row `J.assemble` replay uses exactly the two claims and the existing NDL authority dictionary; only DOB status, selected ISO and hold note are copied back. All roster, section, election, NDL and provenance fields remain on the original row. No ancestor file or module global is modified.

All527 inherited claims remain unchanged in every field and all367 prior day expressions remain selected. The three earlier exact releases, Miyairi1865-06-08, Yamasaki1870-04-10 and Adachi1865-08-01, remain unchanged. Only Terao's routing is released:47 inherited holds become46. There are29 calendar holds,14 comparable-date conflicts, two caveats and one quality hold. Koto's new society article repeats an unconverted old-calendar expression and is not promoted.

Japan retains428 broad SectionII, seven exclusions and47 section-unresolved identities within the restored482-person working universe. The475 nonexcluded candidates contain107 cases without a day status. Terao's section remains unresolved, so the combined date/section queue stays120 and broad SectionII plus day remains355. This is not a frozen national denominator. No collector calendar conversion, default date components, source-majority adjudication or final cohort acceptance is performed.

## Review and offline reproduction

Each lane's final claim/decision files and worker manifest are bound by an external independent QA report in `source_audits`. Frozen worker summaries may still describe their own handoff QA as pending; the final external reports record completed review without rewriting reviewed worker files. Public deliverables contain metadata, hashes, locators and short excerpts. Raw PDF/HTML captures stay outside the deliverable.

```sh
python3 studies/academy_fr_jp_completion_v9/scripts/continue.py prepare --output-dir /tmp/academy-v9-prepared
python3 studies/academy_fr_jp_completion_v9/scripts/continue.py assemble --output-dir /tmp/academy-v9-replay
python3 -m unittest discover -s studies/academy_fr_jp_completion_v9/tests -v
python3 studies/academy_fr_jp_completion_v9/scripts/continue.py verify
```

Use fresh output directories. Preparation reconstructs nine inputs from reviewed source batches; assembly writes eight deterministic outputs. Verification checks every pinned file, all ancestor pins, preparation and output bytes. No live harvesting occurs in these commands. Neither country is declared complete and no lifetime source exhaustion is claimed.

A later continuation must preserve the exact attributed-reproduction classification and inherited v9 legacy-calendar replay when rebuilding from V4. Merely omitting the later Terao overlay is insufficient because V4 reloads the original v2 routing overlay. `V9.japan` consumes v9's own deltas relative to v8; `V9.previous_japan` returns the predecessor baseline. Baseline-empty-delta tests must preserve368 day statuses and the exact Terao result without suppressing a future genuine source conflict.
