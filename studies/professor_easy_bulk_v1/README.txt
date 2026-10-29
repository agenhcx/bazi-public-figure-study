Professor/faculty easy batch collection, version 1

The user chose existing public batch sources, with no person-by-person birthday
search or verification. Ranks are unrestricted. Sources without a convenient
whole-file route are parked; absent or partial dates are not rescued.

Completed extraction: Rostock physics and chemistry
-------------------------------------------------
Two already downloaded official CSV exports contain 90 and 117 subject rows.
Deduplication by exact catalogue PURL gives 205 candidates, with two shared
physics/chemistry PURLs. The duplicate facts agree; no name-based fuzzy merge
or individual profile request was used.

Printed source dates: 156 full dates, 27 years only, 22 missing. Of the 156
full dates, 149 fall in the scientist project's 1835-1985 birth-year window.
All 205 source records remain in the delivered candidate table; the separate
149-row view is a date/window filter, not an accepted analysis control cohort.
Six records have an honorary-title indicator and three lack a role value.
Role/period/faculty text is preserved; no individual role adjudication is done.
Academy/Nobel overlap, geographic eligibility and historical calendar acceptance
are not resolved. No BaZi variables or hypothesis tests were computed.

The parser transcribes explicit dd.mm.yyyy and year strings, rejects impossible
numeric dates, keeps missing dates empty and fails on conflicting duplicate
PURLs. Source dates are not asserted as calendar-converted Gregorian DOBs.

US and UK routes
----------------
One official UC In Memoriam annual volume (2001) was downloaded in one request:
117 physical PDF pages, all with extractable text. It concerns deceased faculty
and administrators and is not a current or national professor census. Narrative
birth details do not have a uniform full-DOB header. Source checks record the
actual download, format and limits; any automatic text candidates are separately
labelled and must not be confused with individually verified facts.
One local batch parse produced 75 named-heading candidates: 13 with a complete
date in a named birth clause agreeing with the heading year, and 62 with year
only. All are automatic_unverified. Two isolated year-span lines failed the
heading rule and were skipped. Only four candidates have discipline text
containing physics or chemistry (including biochemistry), and only one of those
four has a day candidate. The 13 dates are not 13 eligible physics/chemistry
controls. This is a parsing demonstration; the rest receive no manual rescue.

Cambridge ACAD is a mixed historical alumni/member database. A bounded check
did not establish a convenient whole-file export with names, explicit birthdays
and professor roles. It is parked, without opening individual person records.
Utrecht's access challenge and Kiel's individual RDF route were not pursued in
this batch. This is not a continuation of the QS US/UK/China person-level pilot.

Delivery and reproducibility
---------------------------
The repository contains extraction code, synthetic validation tests, source
URLs, pinned download hashes and aggregate counts. Minimized derived factual
tables are delivered privately as a ZIP, not as a public raw-source dump.
Original CSV/PDF/text files are not redistributed in the deliverable. An open
redistribution licence for the Rostock exports was not established by this work.
This statement does not infer that public factual extraction needs permission.

The source_checks records include direct CSV URLs discovered in the official
UI. Given the two downloaded files, run these single-line commands from root:
python3 -m unittest discover -s studies/professor_easy_bulk_v1/tests -v
python3 studies/professor_easy_bulk_v1/scripts/build_rostock.py --physics PATH_TO_PHYSICS_CSV --chemistry PATH_TO_CHEMISTRY_CSV --output-dir NEW_OUTPUT_DIRECTORY
python3 studies/professor_easy_bulk_v1/scripts/parse_uc_memorial.py --text PATH_TO_EXTRACTED_TEXT --pdf PATH_TO_PDF --output-dir NEW_UC_OUTPUT_DIRECTORY

The build checks source bytes against the saved hashes and refuses an existing
output directory. If source bytes change, a new versioned snapshot is needed.
The shared GitHub workflow tests the parser offline; private source files are
not uploaded to GitHub and a fresh upstream download is not part of CI.
