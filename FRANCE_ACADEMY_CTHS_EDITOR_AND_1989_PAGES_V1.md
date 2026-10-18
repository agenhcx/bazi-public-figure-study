# France Academy historical roster: correction to frozen CTHS author-credit audit, original 1989 directory page leads

Checkpoint: 2026-10-18 UTC. Entirely **offline source analysis** of the 562 *previously archived* CTHS historical biographies; NOT a new scrape, NOT a completed French Academy roster, and NOT a source for accepting an exact birth date or ordinary/full membership into the research denominator. Birth-year study support stays **1835–1985**. BaZi variables remain uncomputed.

## Why the old zero was wrong

The old source-citation parser `scripts/france_academy_cths_original_citation_audit_v1.py` generated `cths_academy_editor_leads=0` because its regex recognized `redacteur` and `redacteurs` but **not the actual literal `Rédacteur(s) de la notice : ...`** text in CTHS biographies. Public example: Alexandre Favre, CTHS ID 112139, https://cths.fr/an/savant.php?id=112139 . This bug affected **only the editor-attribution metadata**, not the frozen 562-person identity, role-class candidate, DOB claims, source HTML SHA256 checks, prior 160 first-party elected names or global study freeze. Historical input has not been overwritten.

The new script `scripts/france_academy_cths_editor_credit_1989_page_audit_v1.py` reads the compressed, SHA-256-pinned 562 HTML sources entirely OFFLINE, correctly bounds `Rédacteur(s)` to `Fiche créée`, normalizes mixed CP1252/UTF-8, extracts editorial credits and printed 1989 directory page numbers from **only each biography's Sources biographiques field**, and writes compact audit CSVs. It does not publish long biography texts or the raw archive.

Frozen HTML bundle SHA256: `6258a366f69e120395450420fee8ae2587d586cb5db153937d1ef45267468811`.

## Actual 562-person editor-credit counts

| Explicit credit extracted from CTHS biography | Number | Correct interpretation |
|---|---:|---|
| Académie des sciences | **267** | The Paris French Academy itself is credited among the authors/editors |
| Institut de France (umbrella of five academies) | **142** | The parent institute is credited, NOT necessarily a signed original Paris Academy election document |
| Other named editors without either institutional literal | **130** | May be historians, scholars, or contributors; absence of the literal institution is not proof they did not consult Academy archival sources |
| No explicit editor line parsed | **23** | Source attribution unresolved |
| **Total** | **562** | A purposively selected historical set, NOT France's full historical cohort |

Thus **409/562** contain **either** `Académie des sciences` **or** `Institut de France` in an explicit biography author/editor credit. This is valuable provenance **within** the CTHS target collection, but is **not 409 certified full members**. All 562 were already collected because of secondary full-like/transitional membership descriptions in the 1835–1985 year priority frame. The Institut de France houses five separate academies: https://www.institutdefrance.fr/les-cinq-academies/ .

Original source-derived provisional membership role cross-tab:

| CTHS candidate membership role | Académie des sciences editor | Institut de France editor | Other editors | No editor | Total |
|---|---:|---:|---:|---:|---:|
| full-like only | 212 | 114 | 101 | 6 | 433 |
| correspondant → full-like | 55 | 26 | 27 | 17 | 125 |
| mixed full/foreign | 0 | 2 | 2 | 0 | 4 |
| **Total** | **267** | **142** | **130** | **23** | **562** |

**Methodological constraint**: CTHS may synthesize biographies from shared printed Academy indices. An editorial credit does not prove the actual DOB, the specific regular-member election, or independence from another authority source. Do not promote `editor_tier` alone into accepted study membership. The source role descriptions remain candidate statuses requiring original source/event-level checks.

## 1989 member-only book: concrete printed page references

BnF catalogues `Répertoire biographique des membres de l'Académie des sciences` (Gauthier-Villars, 1989); **foreign associates and correspondents explicitly excluded**. The volume itself has **not** been digitized and inspected in this investigation. The following precise printed-page leads were recovered from CTHS biographical `Sources biographiques` and are therefore **citations**, NOT firsthand verification of the books' page contents.

| CTHS ID | Person | 1989 printed pages (CTHS citation) | Credited author/editor institution |
|---|---|---|---|
| 2060 | Jean Wyart | 252–253 | Institut de France |
| 2067 | Jean Roche | 210–211 | Institut de France |
| 101487 | Georges Millot | 182–183 | Institut de France |
| 102781 | Lucien Malavard | 167–169 | Académie des sciences |
| 107885 | Jean Piveteau | 205–206 | Institut de France |
| 111463 | Pierre Lépine | 152–153 | Institut de France |
| 112041 | Jean Coulomb | **not stated in CTHS citation** | Académie des sciences |
| 112083 | Jean Dieudonné | 68 | Académie des sciences |
| 112087 | Charles Louis Dubost | 73–74 | Académie des sciences |
| 112139 | Alexandre Favre | 81–82 | Académie des sciences |
| 112282 | Pierre Grivet | 100–101 | Académie des sciences |
| 112594 | Alfred Jost | 119–120 | Académie des sciences |
| 112702 | René Lucas | 163–164 | Académie des sciences |
| 112705 | Paul Mandel | 173–175 | Académie des sciences |
| 112731 | Alexis Moyse | 187–188 | Académie des sciences |
| 112838 | Pierre Rouard | 213–214 | Académie des sciences |
| 112935 | Robert de Vernejoul | 243 | Académie des sciences |

Exactly **17** such member-only references, **16** with print page locations; **12** attributed Académie des sciences and **5** Institut de France. The 1993 mixed corresponding/member directory cannot be used as proof that an individual was in the 1989 *member-only* snapshot or as proof of a later ordinary election.

## Other source routes and honest access state

- Official Academy says its current site covers current members and members deceased in roughly the past 5 years, not its complete 1666–2025 membership: https://www.academie-sciences.fr/footer-les-membres-de-lacademie-des-sciences .
- The 2016 Leridon/Academy original electronic biographical dataset has **3,218 persons across multiple membership classes** in a separately discovered archive record. The actual original individual Excel/Word data was **not obtained**. Archive portal showed Anubis Access Denied; no bypass: https://archives.academie-sciences.fr/n/fichier-des-membres-de-l-academie-issu-de-l-index-biographique-par-henri-leridon/n:155 .
- The public BnF catalogue says the official 1994 `Index biographique ... supplément 1978–1993` is digitized, but prior bounded Gallica OCR/IIIF/OAI requests all returned HTTP403 from Github; no original page was read. The 1989 book's public cataloguing record also does not establish availability of a digitized text.
- The 160 selected 2010–2025 official elected records are a separate, noncontinuous later subset, not a full 1989–2025 roster.

## Auditable files

- Source-only script: `scripts/france_academy_cths_editor_credit_1989_page_audit_v1.py`
- SHA replay and editorial classification for all 562: `data/france_academy_cths_editor_origin_audit_v1/cths_562_editor_authority_evidence_v1.csv`
- Source-page locator shortlist: `data/france_academy_cths_editor_origin_audit_v1/cths_1989_member_only_17_print_page_locator_v1.csv`
- Invariants: `data/france_academy_cths_editor_origin_audit_v1/summary.json`
- CI run: https://github.com/agenhcx/bazi-public-figure-study/actions/runs/39114016135 .

The 562-source extract is reproducible and **does not contact** the CTHS site. No final cohort admissions, DOB acceptance, old freeze changes or astrological/unblinded outputs: `original_1989_book_pages_opened=0`, `official_full_member_study_accepted=0`, `study_exact_dob_accepted=0`, `bazi_variables_computed=0`.

## Next step

The best route for a *historically complete denominator* is still to obtain a **publicly and lawfully accessible original printed/digital Academy index or election register**. The 1989 directory covers only living/full members within its snapshot, even if each CTHS citation is legitimate; it is not the all-history census. If an original volume is only available in normal browser/library access, use the 16 precise printed-page locators as a manual sample and record original-page identifiers before any automated bulk expansion. For public born/died-era reconstruction, separately evaluate actual Academy-authored election/nomination accounts and preserve all correspondence-to-full and foreign-member transitions. Avoid treating 409 credited secondary biographies as 409 authenticated election entries.
