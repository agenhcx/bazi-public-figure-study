Japan DOB continuation B — 2026-10-29

Baseline: a7297e662502ce821c9289dc7d5226b82208b92d (PR113), 482 existing roster IDs, v2 unchanged.

Canonical claims files for v3 integration:
  claims.json: 10 directly verified institution/learned-society claims.
  bulk_claims.json: 6 existing-roster matches from SSOCJ2017 table; 22-row inventory in bulk_table_inventory.json.
  bulk_jps_claims.json: 7 existing-roster matches from all97pages of JPS chronology; 102 obituary-row inventory in bulk_jps_inventory.json.
  secondary_dictionary_claims.json: 15 published named-dictionary full-body claims, explicitly SECONDARY. These are not institution-supported or first-hand evidence.

Counts: 38 claim rows, 37 unique existing-roster people. Institution/learned-society group:23rows/22people, 17 lacking selected day at baseline (includes Nozaki awaiting independent identity-hold release) and5 existing-day corroborations. Secondary-only:15people. Total32people without baseline selected day. These are worker evidence counts; parent must deduplicate other workers and apply identity/calendar/section holds.

Assigned60 disposition:15 institution/learned-society day,15 secondary-only day,14 searched with no usable full-day body,16 not individually processed. processed.csv states the distinction. All482 were matched against the two bulk sources; this does not mean all482 individually searched. No new scientists or roster IDs were added.

Source distinctions:
  SSOCJ table explicitly separates society appointment date from DOB. Appointment is not Academy election. Nozaki DOB is1922-01-01; independent holds worker handles same-person bridge.
  JPS chronology is an official society compiled historical chronology, not a contemporary civil record. Only named obituary birth statements were used; death dates remain separate.
  Published dictionary publishers/titles are named in every secondary row. Kotobank is the hosting platform. Multiple entries on one page do not become independent source claims. Suehiro's day comes from Kodansha; adjacent Nichigai entry gives only month.
  All new dates here are post1872. Era year arithmetic is transcription, not lunar/Gregorian conversion. No components padded; no Wiki or snippet dates used.
  Hiraga DOB combines the year heading and its birth row; source_location identifies both.

Verification: source bytes captured once per listed source, hashes checked against private capture files. All38 canonical records validated for existing ID/name, real date, required fields and zero final inclusion/BaZi. All15 dictionary raw date statements and publisher labels were located in captured full HTML. PDF birth pages visually inspected; Shibusawa PDF is image-only and DOB verified visually on index1, Hiwatashi on index2/printed3. Other PDF page locators are recorded in claims.

Private material (do not publish): private/ contains copyrighted full HTML/PDF bodies and page renderings, including a personal CV containing contact details. Keep only the short birth statements and relevant professional identity summaries in public claim JSON. jps_chronology_matches_draft.json is an intermediate draft and should not be integrated.

Raw capture metadata logs contain scratch capture_path values for audit; source_sha256 is original downloaded bytes, never a hash of extracted web text. No error page was counted as a captured source.

All final_cohort_accepted=false; bazi_variables_computed=0. No shared repository data modified by this worker.
