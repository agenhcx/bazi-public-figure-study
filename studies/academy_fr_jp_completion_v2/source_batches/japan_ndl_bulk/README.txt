Japan academy candidate NDL authority batch, 2026-10-29

Scope: all 435 rows of the recovered Japanese science candidate input. Candidates are not a frozen national science cohort. This batch supplements the separate five-person source-supported seed; it never overwrites that seed.

Actual body retrieval: 10 SPARQL1.1 requests to the National Diet Library's documented public endpoint, all HTTP200, each below the documented 1000-result cap. Literal foaf:name values matched to candidate Japanese names after whitespace removal only. No fuzzy, Latin-name, old/new-glyph or alias mapping was silently applied.

Results: 397 candidates have one or more exact-name authority matches: 330 have one authority URI and 67 have multiple URIs. 38 have no exact-name match. 574 authority rows include 531 explicit four-digit birth-year values and 43 missing birth values. There are zero day or month DOB values from this route. At candidate level, 389 have at least one provisional birthyear match, including 322 unique-name matches.

Identity limitation: uniqueness within this endpoint is not proof of identity. All matches, birthyear claims and authority assignments remain provisional; identity_accepted and final_cohort_accepted are false. Multiple same-name authorities remain in claims.csv for review (for example, TANAKA Yutaka has 25), not reduced to the first search hit. Do not count these 397 as newly verified birthdays. No date components, calendar equivalence or DOBs were inferred. calendar=not_stated. No BaZi, analysis freeze, role acceptance or membership acceptance was performed.

Files:
- collect_ndl.py: rerunnable public API batch collector; uses standard Python library.
- claims.csv: all returned authority/name/date rows with public authority URL, body capture SHA256 and retrieval timestamp.
- candidate_matches.csv: all 435 candidates, exact-name match status, candidate URI count and URI list.
- summary.json: distinct-candidate and authority-row counts, including precision.
- request_log.json: actual 10 batch URLs, statuses, timestamps and hashes.
- transport_pilots.json: earlier bounded endpoint feasibility requests, kept separate from the 10 successful production requests.
- private/: reproducibility captures only; excluded from the deliverable manifest and not intended for redistribution. This includes the separate Nishina schema inspection, which confirmed only year in the structured date-of-birth field.

Example (from checkout/workspace root):
python3 academy_completion_workers/japan_bulk/collect_ndl.py --input academy_completion_checkout/studies/academy_reopen_fr_jp_v1/inputs/japan_science_candidates.csv

Cached batch files replay without network. Delete/relocate private/batch_*.json to intentionally refresh remote data. A replay retains capture-file modification timestamps and marks cache_replay=true. No role or date acceptance is automatic.

NDL official documentation:
https://id.ndl.go.jp/information/sparql/
https://id.ndl.go.jp/information/sparql-11/

Blocked Wikimedia routes were not retried or bypassed. This authority route yielded useful stable IDs and years, but is exhausted as a source of full birthday precision for this batch. Further full-DOB completion needs a genuinely different source family.

Extension: independent legacy40 qualification queue
collect_remaining40.py writes claims40.csv, candidate_matches40.csv, summary40.json and request_log40.json, leaving the original 435 outputs untouched. The 40 member IDs are disjoint from the 435 input. Its inherited qualification overlay is one broad Section II (Hiratsuka), three Section I exclusions (Yoshikawa, Nanbara, Doi), and 36 unresolved; this DOB pass makes no new qualification decisions. One successful production request yielded 54 authority rows:47 year-only and7 missing, zero day dates.38 candidates had exact-name authority candidates (31 unique-name,7 ambiguous),2 none.37 candidates had at least one provisional year match, of which30 unique-name. These are not science cohort birthdates.
