Fields Medal: bounded birthday source collection, version 1

Result
------
The first pass processed every member of the fixed main roster: 64 medalists
awarded through 2025 (the latest award in this cohort is 2022). There are 57
people with explicit day/month/year components in an observed institutional
source body (89.0625%), 1 with a month, 3 with a year, 2 blocked, and 1 not found.
These are source-supported components, not independent cross-verification.

The four 2026 medalists are a separate extension: 1 day, 2 month, 1 year.
They never enter the main denominator. The roster is from the IMU's chronological
Fields Medal list. Grigori Perelman is retained with award_declined=true.
Andrew Wiles's 1998 special silver plaque is not a Fields Medal recipient row.

No Nobel birth-year restriction was inherited. In particular, Peter Scholze and
James Maynard (1987) remain in the main roster. No BaZi variables, hypothesis
tests, calendar conversion, or final analysis-cohort freeze were performed.
The Fields Medal award-age rule will require separate consideration in any
future study; it must not be treated as an unrestricted career-age sample.

What the evidence means
-----------------------
Only an explicit date in an actually observed source body counts. A search
snippet is retained as a lead but never counts as body support. Partial dates
stay partial; age, anniversary, graduation dates and default first-of-month
values were not used to fill missing components. Calendar labels are preserved.
The column source_date_components_iso is a transcription of source components,
not an assertion that a historical date has been adjudicated as Gregorian.

MacTutor (University of St Andrews) supplies body-supported dates for 50 of the
64 main roster people. It is an institutional historical compilation, not a
civil birth record. Of the 61 main people with any body-supported date, 60 have
claims from only one institution host under the documented grouping rule.
Do not interpret this as 57 independently corroborated dates. Queries sometimes
included candidate dates; this collection was not blinded validation.

Budgets and audit limits
-----------------------
The per-person cap was 2 targeted queries, 2 different body candidates and 1
direct CV attempt. The declared totals are 41 queries, 72 body candidates and
6 CV attempts for the main cohort; 7 queries, 4 bodies and 0 CVs for 2026.
The shared award-list/directory discovery is separate from targeted checks.
Institutional biographies and official award organizations were allowed.

The saved logs retain observed operation order and available query text.
Exact source retrieval times not exposed by the search tool remain null;
checked_at_utc denotes record completion, not HTTP retrieval time. Some 2026
queries were logged only as grouped patterns; their exact query strings cannot
be independently reconstructed from the saved logs. Budgets for those queries
are therefore declared, not completely operation-log-audited. No replacement
query or fabricated timestamp was introduced to close this documentation gap.

The protocol was documented after collection and is not a preregistered
statistical analysis. The fixed roster and instructions preceded shard work.
This is a finished bounded first pass. Missing and partial records are parked,
with no automatic rescue pass or expansion to other awards.

Remaining main records
----------------------
Alessio Figalli: month only (April 1984).
Manjul Bhargava, Peter Scholze, June Huh: year only.
Stanislav Smirnov, Caucher Birkar: blocked; snippets do not count.
Akshay Venkatesh: no accepted birth-date claim found within budget.
The machine-readable queue includes these seven plus the three partial 2026
records. Its ten rows are not ten missing main-cohort birthdays.

Files and reproduction
----------------------
fixed_roster.json: fixed membership and IMU source hash.
config.json: scope, source rules, budgets and analysis boundaries.
data/: five immutable collected record shards.
logs/: sanitized discovery/operation metadata, without raw source pages.
outputs/: main/extension rosters, claim and source ledgers, partial/missing
queue, deterministic summary and hashes. The DOB ledger preserves every claim.
audit.json: independent identity/data review and known audit limitations.
MANIFEST.json: SHA-256 for every study file except this manifest itself.

Run from repository root (the output directory must not already exist):
python3 -m unittest discover -s studies/fields_medal_collection_v1/tests -v
python3 studies/fields_medal_collection_v1/scripts/aggregate.py --roster studies/fields_medal_collection_v1/fixed_roster.json --inputs studies/fields_medal_collection_v1/data/shard1.json studies/fields_medal_collection_v1/data/shard2.json studies/fields_medal_collection_v1/data/shard3.json studies/fields_medal_collection_v1/data/shard4.json studies/fields_medal_collection_v1/data/extension2026.json --output-dir /tmp/fields-medal-replay-v1
diff -r studies/fields_medal_collection_v1/outputs /tmp/fields-medal-replay-v1

The GitHub workflow runs these offline checks and retains replay artifacts for
14 days. It does not request new birthday sources. Repository files remain the
durable evidence ledger after artifact expiry. Raw biography copies are not
redistributed. Original URLs and brief factual excerpts remain with each claim.
