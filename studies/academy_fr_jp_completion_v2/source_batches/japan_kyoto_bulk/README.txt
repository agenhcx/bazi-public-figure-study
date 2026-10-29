Japan Academy target intersection with Kyoto University personnel archive,2026-10-29

This work targets the existing academy candidates only. It does not resume professor cohort collection. The public university archive covers presidents, professors and associate professors employed before1949-05-30.1025 index rows were temporarily acquired to match the435 restored science candidates plus40 disjoint old qualification cases; unrelated professors are not published.

Actual result:
-53 exact-name match pairs. Two wrong Nishimura Hideo pairings were rejected by profession and death evidence: metallurgy isKyoto000706, medicine/anatomy is000707.
-51 remaining candidate source records, including47 restored435 targets and4 old40 targets.
-49 source-complete year/month/day expressions,1 month-only expression(Tamaru),1 missing DOB(medical Nishimura).
-The49 complete expressions comprise37 dates under the database's western-calendar policy and12 lunar month/day expressions with westernized year numbering. They must not be reported as49 Gregorian DOBs.
-In435:45 source-day expressions=33 western+12 lunar,1 month-only,1 missing. Inlegacy40:4 western day expressions, with no qualification promotion.
-41 have exact compact name and archive death date matching the academy's final retirement date. Ten require additional professional/chronological identity crosscheck. Retirement and death are different events; differing values are not automatically identity rejection or DOB conflict.
-All identity/final-cohort acceptance flags remain false. No BaZi, analysis freeze or academy role acceptance is performed by these scripts.

Calendar trap:
The official database legend explicitly says that for lunar dates throughMeiji5(1872), ONLY the year is rewritten in western-year numbering. Accordingly,1855/1/29 or1862/6/2 is not a Gregorian birthday merely because it has a four-digit year. The source expressions are retained, and gregorian_dob is blank for all12 lunar values. Calendar conversion was never performed. For1873+ entries, western_calendar_from_database_policy records interpretation of the stated database-wide policy, not a separate calendar label printed in each biography.
Policy:https://kensaku.kua1.archives.kyoto-u.ac.jp/rireki/files/pdf/legend.pdf

Quality cases:
-Tamaru Takuro:Kyoto000583 literally says1882/10; NDL authority says1872; the Morioka municipal biography explicitly says1872(Meiji5)9/29. The municipal day claim has unstated calendar and is stored separately. Keep conflicting published dates; do not silently repair Kyoto or infer a Gregorian equivalent.
-Katagiri Hideo:NDL exact-name authority00846688 is1963-born, cites a business-management book, and must be rejected as an association to the1897-born academy/Kyoto biochemist. The original name-only NDL layer is unchanged; authority_association_overlay.csv records the reject.
-Ito Hayazo:NDL1865 versus Kyoto's1864 lunar expression remains a provisional-association year difference for review. It is not automatically converted into a conflict between accepted same-person Gregorian DOBs.
-Three1/1 values are literally in the archive DOB field; the collector did not pad missing month/day. No global proof of their independence from other biographies is claimed.

Files safe to publish are listed in MANIFEST.json. private/ contains temporary full index and source bodies and is excluded. candidate_index_matches.json contains target matches only, not all1025 professors. Source facts, short identity context and capture hashes are published instead of full copyrighted bodies.

Acquisition:
The interface exposes page sizes10/20/50/100/200. The first blank-condition POST ignored the posted200 limit and returned20. GET pagination with the exposed limit200 parameter returned the complete6 pages200+200+200+200+200+25. One overlapping detail fetch was retained as two request events, never as two independent sources. Canonical retrieval_log.json preserves63 HTTP200 request events(61 unique URLs), including one targeted NDL crosscheck request and the municipal/legend sources. One earlier duplicate-detail body was overwritten by a later response at the same URL; this is explicitly marked in the log, with the retained body hash. All51 current detail captures and their exported claim hashes validate. Search-engine/documentation calls are not included in those origin-capture counts.

Rerun:
collect_kyoto.py locates the repository's frozen435 and40 inputs, queries the public index, intersects exact compact Japanese names and fetches matched details with bounded concurrency3. Cached bodies are reused. assemble_kyoto.py creates the guarded factual claims, rejects the two known wrong Nishimura pairings, preserves precision and calendar distinctions. Full source bodies are not shipped here; a fresh replay needs new public requests or the retained private captures. Network refresh can return changed source bytes and requires re-auditing. The municipality/association supplements and the canonical historical retrieval log are this round's review evidence, not acceptance rules embedded in the collector.
