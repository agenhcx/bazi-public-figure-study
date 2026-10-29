Professor easy batch collection v2: incremental UC 2000 volume

Actual new data
---------------
One exact officially hosted whole-volume PDF link was downloaded successfully
in one request. The 2000 UC In Memoriam file has 123 physical PDF pages, each
with extractable text. The catalogue's historical extent of 296 printed pages
is a separate metadata value and is not claimed as the downloaded page count.
The canonical 2000/1999 catalogue landing pages returned 403 to the web renderer;
the already publicly indexed 2000 PDF itself returned HTTP 200. No authentication
or access challenge was bypassed. No individual professor profile was requested.

The same conservative extraction rules as v1 produced 76 named-heading
candidates, 18 with complete birth-date components and 58 with year only.
All remain automatic_unverified. Two isolated year-span lines without the
required named heading syntax were skipped without manual rescue.

Ten discipline values contain physics or chemistry, including biophysics and
biochemistry; three of these ten have day candidates. This literal screen is
not a manually adjudicated pure-physics/chemistry control cohort. All 76
candidate birth years are within 1835-1985. Original titles and missing values
are retained. Rank is unrestricted, but administrators and memorial selection
still prevent interpreting the volume as an unrestricted professor census.

There are zero exact normalized-name plus birth-year matches against the 75
candidates from the previously parsed 2001 volume. Normalization is NFKC,
strip and casefold only. No fuzzy or individual identity resolution was used;
zero exact matches does not prove that every record represents a new person.
The new delivery is incremental; v1's Rostock and UC2001 rows are not recopied.

Rules and limits
----------------
The DOB extraction loop is unchanged from v1: a full birth date must follow a
birth expression whose clause names the heading subject's surname; its year
must agree with the heading birth year. Pronoun-only clauses, other people,
kinship clauses, incomplete dates and conflicts are not rescued. The source
calendar is not stated. No calendar conversion, missing-day padding, BaZi
features or hypothesis testing was performed. Higher-tier overlap, birthplace
hemisphere and final control eligibility have not been adjudicated.

The reusable parser now requires --source-url and --volume-year, validates
their agreement, and includes the volume year in candidate IDs. There are
four synthetic tests for provenance, cross-volume IDs, other-person/pronoun
births and partial dates. Code imports cause no file writes or source requests.

Other easy routes checked this round
-----------------------------------
Kiel: no verified public whole-file download found in three searches and three
official page reads; no individual RDF requests or hidden endpoint probing.
Marburg: official landing page showed navigation/search but no direct batch.
Mainz: an official whole-name directory link was found, but its one ordinary
download attempt returned 503. No retry, API guessing or person-page crawl.
These sources are parked. The checks do not prove that batch data never exist.

Files and reproduction
----------------------
summary.json contains actual counts, literal subject screen and exact overlap
check. source_checks contains source URLs, hashes and bounded route outcomes.
private_delivery_checksums.json records hashes of the privately delivered
factual tables; no raw professor tables, PDF, full text or prose appear here.
MANIFEST.json hashes this study except itself. Original downloaded sources
stay unredistributed. The user receives a separate minimized incremental ZIP.

Single-line commands, from repository root:
python3 -m unittest discover -s studies/professor_easy_bulk_v2/tests -v
python3 studies/professor_easy_bulk_v2/scripts/parse_uc_memorial.py --text PATH_TO_PAGE_MARKED_TEXT --pdf PATH_TO_ORIGINAL_PDF --source-url OFFICIAL_SOURCE_URL --volume-year 2000 --output-dir NEW_OUTPUT_DIRECTORY

Generate text with pypdf extract_text for every page, separated by literal
markers of the form === PDF physical page 1 ===. The output directory must be
fresh. Private narrative segments emitted by the parser are audit intermediates,
not part of the data package or GitHub artifacts. CI uses synthetic text only;
actual source hashes and invariants were checked locally without individual
birth-date verification.
