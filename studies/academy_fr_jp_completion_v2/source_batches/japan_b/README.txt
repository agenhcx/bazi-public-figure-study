Japan institutional DOB shard B, original candidate indices 145 through 289 inclusive.

Scope: public birth information in body text of institutions, scientific societies,
award organizers, national-library exhibitions/authority records, and official
government biographies. All data are source claims. No final cohort, scientific
subsection, birth-window eligibility or overlap adjudication was performed.

claims.json contains the body-supported candidate records and short birth
statements, source URLs, source tiers and identity anchors. processed.csv enumerates
all 145 assigned candidates, including not_processed rows and the prior seed
Mishima skipped row. Do not interpret unprocessed rows as searched-and-missing.

Dates are transcribed at the precision actually printed. There are no padded
01-01 or month-end dates and no age-to-year subtraction. Japanese era YEAR
transcription is labelled separately from calendar conversion. The NDL exhibition
itself supplies paired historical era-date and Western-year date expressions for
Furuichi, Ito and Shimose; both are preserved and no collector conversion is made.
The calendar name itself is not explicit, so calendar=not_stated is retained.

Known limitations: award laureates are overrepresented in this easy-source batch;
several are Nobel laureates and must still pass the study's higher-tier overlap
rule. Institutional DOB provenance is not civil-registry verification. KEK's
Kobayashi/Maskawa CV contains stale displayed ages, which are not used to infer or
change the separately printed dates. No source statement is silently corrected.

No date was accepted from search-result snippets or Wikipedia/Wikidata in this
shard. The separate bulk worker may supply such a secondary layer. Nobel main
Facts pages and its public API returned 403; this route was stopped. Other failed
routes and no-date findings remain in the processed queue and lookup log.

build_records.py is an offline assembler for this manually curated evidence set.
It requires the original roster at the pinned checkout path sibling. The optional
capture_sources.py attempts a single raw HTTP capture per distinct verified source
URL and logs success/failure. Raw full bodies, PDF files and rendered pages stay in
private/ and must not be redistributed with the minimized project deliverable.

The optional capture was executed once per 27 distinct source URLs: 24 returned
HTTP200 and three failed. Exact retrieval times and SHA256 hashes are in
source_capture_log.json and joined into claims.json for successful captures.
The initially downloaded NIAD Hanafusa lecture (page 21) and Meijo Iijima CV
(page 1) also have private bytes. Public web retrieval verified source statements
before the raw-capture pass; no claim depends on raw capture success. retrieved_utc
is null where only the retrieval date was recorded. Do not invent a timestamp.
The original long NIAD PDF has a machine-extraction omission
in the web tool; the actually downloaded PDF and pdftotext output include the
Hanafusa birth line on physical page 21. A local page render was created but image
viewing tool failed to process it, so Hanafusa is text-body-verified, not claimed
as visually verified. Other PDF first pages were requested as screenshots.

BaZi variables computed: zero. Analysis/cohort freeze: false.
