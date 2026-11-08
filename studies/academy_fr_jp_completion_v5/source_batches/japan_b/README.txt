Japan v5 B — final bounded evidence batch

Fixed30-person v5 queue; baseline v4 dataset. No roster eligibility or analysis changed. Old outputs/shared repo unchanged. All final_cohort_accepted=false and BaZi counts0.

Import claims.json (5 institution/learned-society rows) and secondary_dictionary_claims.json (17secondary rows). The latter includes16named-publisher dictionary entries and1publisher-author year biography; every publisher/book is explicit. holds.json has Yoshikawa Suketeru's pre1873era date hold. processed.csv covers all30people; requests.json records22successful new original-byte captures and hashes. Prior-route audit and38exact queries are included.24unique new bodies inspected (including index and unproductive society memorial); bounded30/45limits not exhausted.

Result:22claims/22existing-roster people.19new comparable day dates:4institution/learned-society (Kida1943-12-10,Inagami1931-02-20,Nakanishi1942-01-07,Seki1915-05-21) and15secondary-only.2new birth-year claims (Okada1936,Suda1935).1calendar hold (Yoshikawa Keio4/8/9); no old-calendar conversion.8remaining people parked with explicit route/result notes.

Body checks: all17secondary raw date statements and publisher labels located in captured actual HTML; other same-page birth statements scanned for conflicts. Nishimura's anatomy/embryology entry1912-05-17 is explicitly separated from1892-02-16metallurgist namesake; no cross-person dates merged. Suzuki Keisuke1954-06-24 is the organic chemist, not corporate executive. All identities use professional career, not name alone.

PDF visual checks: Seki foundation news No71,index4/printed4 CV explicitly 大正4年5月21日ご出生,Osaka chemistry/thermal-society career. Nakanishi autobiography index2 BORN1942-01-07 and index3 first-person birth sentence; visible profile matches Kyoto neuroscience/Osaka Bioscience. Successful local visual image is nakanishi_p2_view.jpg (PNG decoder rejected initial rendering). Inagami Springer publisher body preview fully supplies DOB/career paragraphs; remainder subscription-only, not represented as complete article.

Source_SHA256 is original captured byte hash, never extracted-text hash; all22were checked against files. Private full HTML/PDF/JPEGs must not be published. MANIFEST.json lists public delivery files only; helper scripts records.py/build.py/capture.py/finish.py are production helpers, not public deliverables. capture.py may issue requests if rerun, so no rerun needed.

Japan A independently QAs this batch; B cross-QAs Japan C in a separate report. Integrator should deduplicate other workers and apply all retained holds.
