Japan v4 DOB continuation B — 2026-10-29

Baseline: academy_fr_jp_completion_v3, commit prefix f5058. Existing482 roster only; no new IDs. Old products/shared repo unchanged. All final inclusion flags false and BaZi counts zero.

Integration files:
 claims.json — 9 institution/learned-society body claims (5 full days,4 birth years).
 secondary_dictionary_claims.json — 25 secondary reference rows covering22people: named Nichigai/Kodansha dictionaries plus one publisher-author year biography (Iritani, Shokabo). Publisher/book/professional identity bridge retained. Held/conflicting dates are evidence, not approved dates.
 bulk_academy2007_claims.json — 5 existing-roster matches after fully parsing9tables/11award recipients from the already captured2007page. ExistingcaptureSHA/time reused; no newGET. 11-row inventory in bulk_academy2007_inventory.json; nonmatches not added.
 holds.json / holds.csv — 6 people whose day must not be approved from this batch.
 processed.csv — all41 assigned people have an explicit disposition.
 summary.json / request_log.json / capture_log.json / delivery_manifest.json — counts, all39 exact queries, source-level routing and original-byte hashes.

Result:39 body-verified claim rows /36existing-roster people. Comparable, unheld day dates: institution10people (9 without prior selected day +1corroboration), secondary-only14people; total23people without baseline selected day. Parent must deduplicate other workers and retain membership/section holds. Among assigned41:7institution days,14secondary days,6date holds,5year-only,1month-only,8bounded no usable birth body.

2007 matching was complete across482, not only this queue. Five matches: Akira1953-01-27; Taira1946-05-30; Hori1927-08-22; Maruyama1933-10-17; Miyashita1949-12-08. Table's other6recipients have no ID in the fixed roster and remain inventory only. Award biographies do not themselves establish Academy membership. DOB and award dates are distinct.

Mandatory holds:
 Nakamura Seiji1869-09-24 and Miura Kinnosuke1864-03-21 are literal pre1873era dates; calendar_comparable=false. No collector conversion.
 Tawara Yoshizumi: Nichigai Ansei2/7/6 versus Kodansha Ansei2/7/4; both conflict and calendar hold.
 Kato Toyojiro: Nichigai1882-07-03 versus Kodansha1882-07-01; conflict hold.
 Kon Yutaka: Nichigai1878-10-01 versus Kodansha1878-02-07; conflict hold discovered in independent QA and both sources retained.
 Asahina Yasuhiko: captured dictionary body1881-04-16. A learned-society PDF search result reports04-12 but opening timed out. The latter is an UNVERIFIED conflict lead, not a body-verified claim; conservative caveat hold pending actual PDF inspection.

Known failures stopped: Tamura Saburo society obituary full-body403; no snippet DOB used. Asahina society PDF opening timeout; no false original hash. Best sources with only year/month were recorded at their actual precision. Wrong Wada entertainer and Shimizu corporate auditor were rejected. Existing exhausted NDL/Kyoto/SSOCJ/GSJ/JPS bulk routes were not restarted.

Verification: every claim has stable existingID/name, source URL, precision, short original statement, professional identity support, original-byte hash/time and calendar routing. Every captured hash checked against file bytes; all25secondary raw date statements/publisher labels located in actual captured HTML. Hiratsuka PDF index0/printed175 visually inspected (1903-08-28); Amemiya PDF index0 visually inspected (1889year only). HTML2007 parsed completely and matched across482. No padded components, majority voting or lunar/Gregorian conversion.

Private source bodies: private/ contains copyrighted full HTML/PDFs and rendered pages; do not publish. Source capture metadata may retain audit paths. Helper scripts records.py/build.py/capture.py/finish.py are scratch production helpers, not part of the public data manifest; capture.py would make new network requests if rerun.
