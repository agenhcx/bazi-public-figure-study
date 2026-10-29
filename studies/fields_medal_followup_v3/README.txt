Fields Medal follow-up v3: offline patch integration

Current main roster: 64 people, 63 day-source verified and 1 month-only
(Caucher Birkar, explicit July 1978, no day). There are no remaining
year-only, blocked or not-found main records. The main day-source count
advances from v2 59 to v3 63 (+4); the v1 57 and v2 59 snapshots remain
immutable checkpoints. The separate 2026 extension is unchanged: 4 people,
1 day-source, 2 month-only and 1 year-only.

This builder reads the v1 fixed 68-person roster and five shard inputs,
reconstructs v2 using its two saved patches, and applies only the four
new day claims and one new month claim saved alongside this README.
No full copy of prior records is made. Every original claim and source
remains in the output ledgers, including Birkar's original snippet lead.
Only his NEW observed HLF body supplies accepted month-level evidence.
All supplied calendars remain not_stated; source date components are not
calendar-converted. No day is supplied to a month-only or year-only claim.

Evidence was collected by the worker before this offline build. This round
used 0 new queries and 1 body each for Smirnov and Bhargava (previous exact
URL discoveries reused), and 1 query plus 1 body each for Birkar, Scholze
and Huh: totals 3 queries, 5 bodies, 0 CV attempts. Original v1 counters
stay unchanged; this round is separately audited with actor worker.
Exact request/source observation times are unknown and remain null.
The saved completion timestamp describes log finalization only.
collection_log.json retains full query text and short evidence fragments,
and removes transient tool references and local filesystem paths.

Rebuild offline into a NEW directory:
  python scripts/build.py --output-dir outputs_new
The default outputs directory must not already exist. No network code is
used. Run patch tests with:
  python -B -m unittest discover -s tests -v

Outputs include split main/extension roster CSVs, claim and source ledgers,
the missing/partial queue, summaries, checkpoint delta, worker round audit
and a SHA-256 input/output manifest. v1/v2 inputs are read-only and hashed.
MANIFEST.json hashes this package, excluding itself and bytecode.
BaZi records: 0. Analysis records: 0. Final analysis cohort freeze: false.
