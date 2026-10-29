Historical professor catalogue expansion — bounded feasibility metadata
Study: professor_catalogue_expansion_v1
Evidence checked: 2026-10-29 UTC

Files
- findings.json: structured source assessments, access observations, schema checks,
  bounded sample metadata, and HTTP response hashes/byte counts.
- source_matrix.csv: one row per catalogue with counts labelled by their actual unit.

Main result
Utrecht has a downloaded public URL inventory and three purposeful physics/chemistry
HTML examples with day-level birthdays. Its sitemap has 3,206 distinct URL entries,
not 3,206 unique or eligible science professors. The second advertised sitemap
returned HTTP 404 while carrying valid XML with 1,206 entries; the first carried
2,000 entries with HTTP 200. The sitemap exposes loc and lastmod, not birthdays.
REST returned 401. Later English information/Kramers page checks encountered an
Anubis challenge; no challenge was solved or bypassed.

Kiel has a public person list spanning 179 observed pages, one individual RDF sample
retrieved with HTTP 200, and an HTML birthday example confirmed in the session.
No whole catalogue batch was downloaded. Local descendant parsing confirms the explicit nested birth path
g:birth / owl:Thing / g:date with an xsd:date birthday. This is one structured
birth sample outside physics/chemistry, not a batch or a coverage estimate.

Leiden is an official paginated catalogue, but live downloads and an API sample
failed. Groningen's directory returned 503. Hamburg's official about content was
read, while its main site returned 503; no birthday schema was verified.

Limits
No actual bulk biographical birthday dataset was established for any of these five
sources. Enumeration is a separate claim from birthday data. Purposeful examples
are not hit rates. Historical launch/report counts are not current totals.
This package is metadata only: no response bodies, full roster, portraits, private
contact details, family information, or formal professor processing queue.
Packaging used existing session evidence only and made no network requests.
