France and Japan academy collection reopened, version 1

The user explicitly paused professor collection and resumed academy completion.
This checkpoint restores Japanese source rosters, starts a traceable birthday
ledger and advances selected French evidence cases. It does not compute BaZi,
unblind outcomes, merge global analysis cohorts or freeze final eligibility.

Japan: recover the denominator before claiming missingness
---------------------------------------------------------
Three previously saved upstream packages were actually restored and their CSV
schemas inspected. No complete DOB table was found in those packages. They
contain 69 current Section II rows, 745 deceased rows across all sections, and
435 science-candidate rows. These are historical discovery snapshots, not a
certified current national census or a frozen birth-year-filtered cohort.

The previously parked 239-person subset lies entirely within the 745 deceased
rows. All 199 broad-Section-II-by-degree rows occur in the 435 science-candidate
table. The 36 unresolved cases concern section/eligibility, not 36 missing
birthdays. Earlier election and retirement dates must not be reused as DOBs.
The original discovery summary reports 137 explicit official-science rows;
the separate review hotfix reports 139. Preserve that source-version difference
instead of replacing individual row classifications with either headline count.

The first five fixed broad-Section-II candidates received a birthday check.
Four have explicit institutional body date claims; one remains not found within
budget. The other candidate rows remain not_processed, not failed searches.
No full Japan DOB missingness rate is asserted. Counts in the generated queue
describe this tracked candidate table and this seed round only.

Shiga's source explicitly provides an old-calendar birth expression and its
own current-solar-calendar footnote date. Both survive in the claim record;
the collector performed no calendar conversion. Komai's source supplies a
Meiji-era date, with transparent civil-era-year transcription noted. Do not
drop these annotations or treat alternate calendar expressions as competing
Gregorian births. Original partial/unknown components stay unfilled.

France: a role correction and three blocked original records
-----------------------------------------------------------
The 562-person CTHS source pool has 557 straightforward day-level text claims
after the existing first-day ordinal repair. Those claims are not a complete
verified full-member cohort. The 211-volume/811-event historical index work
is a source-event inventory, not 811 unique people or DOBs.

Paul Santy: the Academy's own 23 February 1970 obituary was read as a PDF image.
Its header explicitly calls him Correspondant for Medicine and Surgery. This
supplies first-party support for the previously pending correspondent exclusion
from the primary full-member candidate layer. His conflicting April16/April18
birth claims remain recorded; the exclusion does not pretend to resolve DOB.

Abragam: CEA IRAMIS was reobserved, explicitly giving 15 December1914 and French
Academy membership since1973, separately from foreign academy memberships.
This is employer corroboration, not a new-person DOB or the Academy's own
ordinary-member election record. The remaining classification question stays
pending; do not count it as a second fully resolved membership case.

Roche, Escande and Fontannes: the next identified sources were original civil
birth registers at Sorgues/Vaucluse, Toulouse and Lyon. This round obtained no
person's original birth act. Access/service failures are retained separately
from no-record-found. Existing date alternatives stay unresolved. Repeated
blocked archive requests are not the next default task.

Files and continuation
----------------------
inputs/japan_science_candidates.csv preserves the restored factual roster.
inputs/japan_dob_seed.json records actual body claims and calendar annotations.
inputs/france_case_updates.json supplies the new case-level source evidence.
source_audits/ records the restoration hashes, source scope and request failures;
original ZIP source caches and complete biographies are not redistributed.
outputs/ gives the Japanese candidate master, claim ledger, visible gap queue
and counts. Scripts/tests run offline and refuse an existing output directory.

Professor sources stay parked. France/Japan are active collection tasks again;
old closeout records are retained as historical checkpoints. The next Japanese
batch can continue on stable member IDs from the restored candidate table,
keeping DOB acquisition separate from unresolved section and election evidence.
