# France Académie des sciences: historical election-index public-source pilot v1_1

**Research checkpoint:** 2026-10-18 UTC. Source-collection only, before cohort freeze and any BaZi analyses. The pilot targets original Academy-authored *Comptes rendus hebdomadaires des séances de l’Académie des sciences*, as transcribed in **French Wikisource Table des matières**. The sampled *index transcription* is a stronger historical election **lead** than a general biography's membership label, but is NOT the directly inspected original election announcement page.

## Historical source route and scope

- French Wikisource currently indexes a collection of original scanned *Comptes rendus* volumes, with a category listing 211 historical volumes from approximately 1835 to 1940. **This does not guarantee all corresponding index pages are transcribed or all journals are digitized**, and these 211 entries are volume images, not 211 guaranteed clean election-record datasets.
- Pilot fetches the public **rendered HTML Table des matières** rather than the Wikisource action=raw or revisions API, neither of which returned usable body content for these index pages. Source URLs, actual HTTP code, complete response SHA256 and approximate bytes appear in the source audit; original raw source HTML was not committed.
- The five pilot **half-year journal volumes** were intentionally selected for parser development, NOT sampling of five entire calendar years, NOT continuous temporal coverage:
  - Tome 168 (1919)
  - Tome 179 (1924)
  - Tome 182 (1926)
  - Tome 192 (1931)
  - Tome 198 (1934).
- Original DjVu scanned volumes are also linked from Wikisource (e.g., Tome 182/1926). Their original printed election-event pages have **not yet** been opened and verified by this pilot; these distinctions are encoded as `original_book_event_page_opened=0`.

## Audited source-only results

GitHub Actions successful parser and public-source run:
https://github.com/agenhcx/bazi-public-figure-study/actions/runs/39116133728 .

| Source volume | Year | Index election-event rows | Observed role groups |
|---|---:|---:|---|
| Tome 168 | 1919 | 13 | 7 section members, 2 nonresident, 1 foreign associate, 3 correspondents |
| Tome 179 | 1924 | 3 | 1 section member, 1 académicien libre, 1 correspondent |
| Tome 182 | 1926 | 8 | 2 section members, 2 nonresident, 1 académicien libre, 3 correspondents |
| Tome 192 | 1931 | 11 | 3 section members, 1 académicien libre, 7 correspondents |
| Tome 198 | 1934 | 6 | 6 section members |
| **Total** | — | **41** | **19 section members, 4 nonresident, 3 académiciens libres, 14 correspondents, 1 foreign associate** |

- **26** *full-like-role election-event candidates* across `FULL_SECTION_MEMBER`, `FULL_NONRESIDENT_MEMBER`, and `FULL_ACADEMICIAN_LIBRE`. These count election-event entries, NOT independently verified historical persons or net additions to the study denominator.
- **15** corresponding/foreign associate events kept out of the preliminary main member-like count (14 correspondant, 1 foreign).
- **25 of 41** event names strictly match a unique person by normalized-name token set in the already-frozen **562 CTHS priority biographies**. This is an identity *candidate*, not confirmation of every event's membership or date. The other 16 are not automatically nonmembers; the 562 CTHS set is deliberately limited and incomplete.
- All 41 event entries have a journal printed page candidate; one (1926 Léon Fredericq, p. 551) required reconstruction from the adjacent continuation line in the index layout. The parser explicitly flags the reconstructed page.
- The source's visible election heading can name "membres et correspondants" together. The parser deliberately classifies **the predicate after `est élu`** rather than this mixed heading, and does not mistake a predecessor mentioned after `en remplacement de` for a newly elected person. The separate government approval/`Décrets` section is not counted as a distinct person election.

Some exact transcribed historical event leads (original printed page has NOT been inspected):
- **Henri Andoyer**, `FULL_SECTION_MEMBER`, Tome 168/1919 p.1305, CTHS candidate ID 111763.
- **Georges Claude**, `FULL_SECTION_MEMBER`, Tome 179/1924 p.1237, CTHS ID 103005.
- **Paul Séjourné**, `FULL_ACADEMICIAN_LIBRE`, Tome 179/1924 p.1298, CTHS ID 112866.
- **Camille Matignon**, `FULL_SECTION_MEMBER`, Tome 182/1926 p.303, CTHS ID 100857.
- **Léon Fredericq**, `CORRESPONDENT`, Tome 182/1926 p.551; same-name 562-set crosswalk absent.
- **Victor Grignard**, `FULL_NONRESIDENT_MEMBER`, Tome 182/1926 p.1366, CTHS ID 111459.

## Artifact and reproducibility contract

- `scripts/france_academy_wikisource_index_preflight_v1.py`: diagnostic of API/raw versus rendered HTML and URL construction.
- `scripts/france_academy_wikisource_election_rows_v1.py`: source-limited reproducible extractor, Python >=3.10 + beautifulsoup4; `--fixture-check`, `--limit 1..5`, `--out` support.
- `data/france_academy_wikisource_election_pilot_v1/summary.json`: per-volume HTTP response status, SHA256, source URLs, journal volume, election-role counts, missing/continued page counts and freeze-protection flags.
- `data/france_academy_wikisource_election_pilot_v1/academy_transcribed_election_events_pilot_v1.csv`: name and original source line excerpt, transcribed election type, scientific section where explicitly stated, volume/year, printed page, identity-candidate crosswalk, source SHA256, source tier and zero acceptance flags.
- Workflow `.github/workflows/france_wikisource_elections_preflight_v1.yml` recorded the five-volume network pilot, preserved the compact result artifact and committed **candidate metadata only** onto the experiment branch. It does not write into the frozen CTHS source snapshots or the accepted cohort.

All original source biographies, historical member statuses and prior two DOB conflicts remain unchanged. These outputs **do not contain DOBs or birth-date inferences**. The full-member primary cohort, election dates, science hierarchy comparison and all preregistration parameters remain frozen in intent, **not yet ready for unblinding**.

## Statistical and historical caveats

1. **Volume != year:** selected volumes cover portions of a year (usually six months). A missing name or missing event in one selected volume is NOT absence of an election in the year.
2. **Transcription != scanned original event page:** historical journal is an original Academy publication, but this extraction reads a Wikisource-encoded table of contents. Only a separately opened original printed journal page and confirmed election class/date could qualify as first-party direct event verification.
3. **Election != later promotion:** the person may have been a correspondent before election, or nonresident before a later role transition; do not treat all appearances as independent unique people. Preserve every event by person/time/type and reconcile transitions before determining final full membership.
4. **Name match != identity acceptance:** accents, abbreviations and same-name scientists can cause errors. Exact normalized token-match is deliberately conservative, but still provisional.
5. **No complete denominator:** this small public pilot does not settle the historical 1666–2016 Leridon index, 1940–2025 source gaps, modern election-year uncertainty or class-definition differences by historical period.
6. **No feature lookups:** `original_journal_event_pages_opened=0`, `accepted_french_academy_full_members=0`, `accepted_exact_dobs=0`, `bazi_variables_computed=0`. These are hard audit invariants, not missing values imputed to zero.

## Next collection method

A useful next step is to **separately verify a few original printed event pages** via the lawful public DjVu scanned volumes, compare transcribed names, class, original election action/date and printed page numbering, and freeze parser acceptance rules before expanding to carefully inventoried volumes. Expansion should use an actual source-availability inventory, checkpoint SHA256 provenance, respect website rate limits, keep original scan content out of the repository when redistribution is unclear, and eventually use local Windows for bulk source retrieval. Later historical periods beyond available Wikisource transcriptions will still require other original Academy / government election records. **No archive-permission requests were sent and no access restrictions bypassed.**
