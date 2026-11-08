# France C v13: two annual-report source screen

Fixed scope is16 C candidates; Christophe Salomon is a separately labelled source-sharing observation owned by fixed B5. No repository ledger, raw date, identity, DOB, membership, alias, conflict, cohort, analysis or outreach field is changed by this handoff.

ExactlyoneGET to each root-authorized URL succeeded200, with no redirect, retry, search query or person query:

- https://www.academie-sciences.fr/pdf/documentation/RA1718/RA_2017_2018.pdf — actual56-page institutional report, SHA256 `ad9514aa78a93d64c594598c0fcea546ddee46eb6b5d76fe49d052495ba6fc62`,8134812bytes.
- https://www.academie-sciences.fr/pdf/documentation/RA_AS_2021_2022.pdf — actual37-page PDF containing spreads, SHA256 `0b535eb3e419f9b065fbbb3d7774db188617d07becb4df9c02b02a23babdef22`,3705082bytes.

Both complete extracted bodies were screened. Four relevant PDF pages were rendered and visually read: RA1718one-based49/50 and RA2122one-based25/36. The named roster/career rows contain no birthday field; the two incidental lecture/media mentions contain no birthday. Nine targets have no own-name entry in either report. Consequently `decisions.json`, `individual_case_proposals.json` and `birth_claim_proposals.json` are empty. The16 fixed candidates have32 document-name screens, not16 personal-biography reviews; there arezero personal-biography body reviews.

RA1718PDF49 describes18 new members elected during2017 and their reception on29May2018. PDF50 explicitly heads the list as members elected in2017, with subject-specific section/career rows for the five C2017targets and Salomon. It gives election year only. Neither05December2017 nor the2018reception date is manufactured as its election day. The separate `salomon_cross_batch_source.json` preserves this observation and C capture provenance for B; Salomon contributeszero to C selection/processing counts.

RA2122PDF36 actually lists16 foreign associates elected in2021, received14June2022, and18 ordinary members elected in2022. This differs from the discovery inventory's expected2019/2020regular-member reception route. The actual body is retained, and no2019/2020roster or birthday evidence is asserted from it. Cani and Chuine appear in outreach/lecture contexts, especially PDF25/printed48; these are not biographies or dated membership events.

Chédotal's prior profile header/body hold is not cleared; his own-name2017roster row supplies no birthdate. Bousquet-Mélou is absent and receives no newDOB-quality source. All aliases and prior conflicts remain held.

`requests.json` preserves timestamps recorded immediately before the requests. `source_manifest.json` states that timestamp meaning and separately records actual capture-file completion times. The first local script failed while importing an unavailable Python module before it could make any HTTP request; the standard-library fetch then made exactlythe two reportedGETs.

Raw PDFs, extracted full text and page renders are private working captures. Public handoff files contain bounded provenance, hashes and locators only. `HANDOFF.json` indexes the files. Source observations require root exact review before any downstream field change.
