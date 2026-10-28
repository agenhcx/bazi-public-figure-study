# Japan verification inputs v1

This packet supplies the original 40-row queue, four source inventories, four accepted adjudication tables, and a minimal factual source packet for the historical Tier-B replay. The CSV files are unchanged copies of the source artifacts; their SHA-256 values are listed in `inputs_manifest.json`.

The original queue SHA-256 is `bd81f0b4d994833fa5d0d5b04e2dcd036f0670b87aecdcfa08ce9df159acda11`.

## Provenance and availability

The source artifacts were supplied from the user's existing research files. All four raw snapshots were available during preparation and matched their inventories' pinned SHA-256 and byte counts. The two preserved HTML-to-visible-text transformations also reproduced the pinned text SHA-256 values with the existing fetch scripts' pure text-extraction functions and a CRLF final newline. Using LF changes the text hash.

The source packet records the original public URLs, artifact basenames, hashes, byte counts, locators, short section facts, and accepted broad sections. It contains no private file identifiers or absolute workspace paths.

Raw PDFs, full HTML pages, full visible-text captures, and rendered source pages are absent from this public packet. `exact_raw_source_in_packet` is false for every source. The packet alone does not establish a fresh raw-source replay. A replay must obtain the exact original snapshots privately or fetch only the four recorded source URLs into temporary storage and verify every pinned SHA-256 before adjudication. A changed live page must fail closed. Do not substitute a short quote for raw bytes or report its hash as the raw-source hash. Raw bytes and full-text derivatives must not be uploaded as workflow artifacts.

The original inventories retain relative Windows-style source paths such as `data\<source-dir>\raw_sources\<filename>`. Resolve either slash style into the temporary replay tree; do not rewrite these frozen CSVs.

The public packet was screened for birth dates, contact information, addresses, and family details. It contains names and public professional membership/election facts plus the pre-existing zero-valued collection/status flags. It adds no DOB collection, Bazi calculation, final roster row, or formal cohort freeze.

Hiratsuka is accepted as broad Section II, exact subsection 6. Yoshikawa, Nanbara, and Doi are accepted as broad Section I and remain excluded from the Section II science cohort. Exact subsections for these three are not inferred.
