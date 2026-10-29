Fields Medal follow-up v2: offline evidence integration

This version reuses the immutable fields_medal_collection_v1 fixed roster,
four main shards and separate 2026 extension. Only new_body_claims.json is
the follow-up evidence input. No full copy of the original records is stored.
The patch input is retained as supplied; its Pending integration annotation
describes capture time. The completed current state is in outputs/summary.json
and outputs/followup_delta.json.

The two supplied, previously observed HLF body claims are added for Alessio
Figalli (source components 1984-04-02) and Akshay Venkatesh (1981-11-21).
Figalli's original month claim and Venkatesh's original failed/no-date sources
remain in the ledgers. The new evidence was collected by root, not by this
offline builder. Each follow-up used one search and one body candidate;
exact retrieval times are unknown (null). Original v1 budget counters stay
unchanged, with this round documented separately in patch_audit.json.

Current main roster: 64 people, 59 day-source verified, 3 year-only,
2 blocked, 0 month-only, 0 not-found. The old count of 57 is superseded by 59
and retained in followup_delta.json as the v1 checkpoint (+2).
The 2026 extension remains separate and unchanged: 4 people, 1 day-source,
2 month-only, 1 year-only. No partial date is padded and no conflict is
resolved by selecting a preferred source. The date columns contain source
components; no calendar conversion or Gregorian acceptance is asserted.
BaZi records: 0. Analysis records: 0. Final analysis cohort freeze: false.

Rebuild from this directory into a NEW output directory:
  python scripts/build.py --output-dir outputs_new
The default output directory is outputs and must not already exist.
Run offline patch checks:
  python -m unittest discover -s tests -v

The build imports v1/scripts/aggregate.py and runs its strict fixed-roster,
identity, precision, URL, source-body and original per-record budget checks.
Only validated body claims count toward coverage. The two patch records
match exact fixed-roster names; supplied optional IDs must match those names.
Duplicate patches and unknown names are rejected. Outputs include split
roster and claim/source CSV ledgers, the missing/partial queue, summaries,
the round audit, baseline delta and a SHA-256 output/input manifest.
MANIFEST.json records this v2 package's files. Neither manifest self-hashes.
