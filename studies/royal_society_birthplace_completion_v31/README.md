# Royal Society geographic support v31

This batch reviews twelve fixed records from the68 stored-place records with unresolved geography in the native1835–1985 window. Two new S3 geographic-support observations resolve North: John Maynard Smith and Alister Clavering Hardy. No birthplace text, birthplace grade, DOB or prior evidence is replaced.

| Scope | North | South | Unknown | Total |
|---|---:|---:|---:|---:|
| All fixed UK records | 4,193 | 187 | 603 | 4,983 |
| Native DOB1835–1985, inclusive | 2,293 | 182 | 169 | 2,644 |

The window's169 unknown records comprise103 blank birthplaces and66 stored places without resolved geography. Across all records those counts are525 and78. All103 blank-window complete objects are unchanged. The68-record geographic pool is an eligibility queue, not68 biographies read. Twelve individual followups produced two adoptions and ten holds;4,981 complete objects remain identical to v30.

| Subject | Frozen birthplace / original grade | New actual birth-country context | New geographic support |
|---|---|---|---|
| John Maynard Smith, NA5065 | London / S1 | Born in London, England in1920; Kyoto Prize biographical timeline | S3 / North |
| Alister Clavering Hardy, NA7080 | Nottingham / S2 | Born10February1896 in Nottingham, England; Gifford Lectures biography | S3 / North |

Both original bodies were acquired by worker and root. The uncredited institutional prize/speaker profiles receive conservative S3 geographic support, without host-only S1, verified expert byline, civil-record or informational-independence claims. England is directly birth-linked. No country is inferred from familiar cities, nationality, work, schools, family, publisher or footer, and no personal country/QID/coordinates are assigned.

Maynard Smith's actual full heading and lifespan1920–2004 match native personal components and temporal context. The timeline states birthyear1920 only; it does not newly confirm native January6. Evolutionarily stable strategy, UCL and Sussex roles supply distinctive source-observed professional context. The awardyear2001 is not assigned as web-biography publication date. An old Balzan work had actual compatible full native name/exact DOB but London-only birth context; an unrelated unopened secondary date projection was not a qualified original conflict and is not used as new proof. The new Kyoto country qualifier is ordinary geographic refinement, without clearing a date hold.

Hardy's full Alister Clavering name and exact1896-02-10 agree with native data. Continuous plankton recorder, Discovery expedition and Regius/Linacre zoology roles supply distinctive context. The profile states no death date confirming native1985, and lecture/book dates are not assigned as web publication dates. No author or grade is transferred from its unacquired ODNB link. Original Nottingham/S2 source evidence remains unchanged.

## Nonadopted source-class observation

The worker actually acquired a Kiddle Harry Smith1921 microbiologist entry with compatible full name, exact DOB/lifespan/career and a Northampton, England birth assertion. Its footer explicitly describes Wikipedia-based content rewritten for children. That observation and the worker's weak S3 proposal remain in the audit; the root did not independently reopen the page.

Under the current original-work boundary the derivative encyclopedia carrier is held, with no silent source-class expansion. Its country statement is not called incorrect, and no existing Wikipedia-based birthplace claim is retrospectively downgraded. Earlier CFDFlow was a bylined professional profile with encyclopedia outlinks and possible dependence; Prabook was a compiled profile with unverified underlying provenance. Neither established a pure Wikipedia rewrite. The dated `source_class_adjudication.json` records this current decision, keeps the original worker report unchanged and adds a current Harry Smith hold. His complete master object and Northampton/S1 evidence remain unchanged.

| Other held subject | Actual evidence or limit |
|---|---|
| Michael Augustine Raftery | New authored memoir abstract says Irish-born and full name, but acquired heading/body lacks actual DOB/lifespan. Search/URL-slug dates and unrelated1936 text are not date proof; publisher first attempt403 stopped. |
| Leonard George Goodwin | New full signed memoir states WoodGreen, northLondon. This is city/subarea context, without an acquired birth-country qualifier; authors' UK addresses are excluded. |
| Roger Philip Ekins | No new qualifying birth-country body; the old failed publisher route remains closed. |
| Anthony George Cullis | New attributed ODNB Extract gives exact DOB and48HallowRoad, Worcester. Worcestershire/England elsewhere qualify later Malvern work, not birth. |
| Bland James Finlay | New Danish yearbook gives actual full name/exact16March1952, but Dorset, UK is a work address. A distinct personal-remembrance route was unavailable. |
| William Reginald Stephen Garton | New archive PDF first attempt403 stopped. |
| Claude Gordon Douglas | New compiled biography gives full name/exact native DOB and Leicester only. An unopened secondary date projection is not a qualified conflict. |
| Sir Derek Harry Roberts | New institutional profile gives short name/career but lacks Harry, DOB and an explicit born-country clause. |
| Arthur Roderick Collar | Two genuinely different new original work routes failed and stopped; old failed catalogue/PDF routes were not retried. |

Known earlier Ewins Bristol-versus-Blackpool and Barber Letchworth-versus-Hatfield place holds were excluded before selection. Their existence is preserved even though the separate Gotch sidecar is not an exhaustive list of old individual place holds; a new country-only source cannot bypass them.

All nine inherited issue/method sidecars are byte-identical to v30, including seven active DOB conflicts. Tomes remains separately provisional; all older place/approximate-year/integer-age/endpoint/cross-source-age/middle-name/ordinal-wording cases remain unchanged. No new qualified DOB/place conflict or omitted-middle/endpoint exception is added.

Source work comprises24 worker queries,16 worker navigation attempts and two root first opens:18 navigation attempts, plus five worker cached finds. No root query/find, screenshot or raw GET was used. Full targeted accepted contexts and individual holds were read before queries; a missing Garton display chunk was reread before querying. One Goodwin cached-find selective display omitted terminal match-status detail; no exact status was reconstructed and no match/absence claim or retry depends on it. The inspected first body's observed birth context retains its separate role. Other actual errors, prospective intents and result-mapping limits are retained, including one query with no identifiable distinct result references. Failed routes stopped without retries, variants or bypass. Unknown raw status/request times/byte hashes remain null. New adopted excerpts are four and nine words, within25 words per original work; no full source HTML/PDF/images or projection caches are distributed.

## Files and replay

The cumulative ZIP contains the complete current `outputs/birthplace_rows.jsonl.gz`, CSVs, changes, summary, geography facts, audits and frozen inputs. The remaining-window CSV has169 records. All116 old CSV columns retain positions/meaning; six v31 geographic columns are appended, for122. Only the selected records' current hemisphere cells change in the old projection. `geography_followup_v31` retains previous and absent geographic-field snapshots for exact rollback. Legacyv20 and v30 geography helpers/constants/scopes and all old loaders remain unchanged; a separate v31 helper handles current geography.

```sh
python studies/royal_society_birthplace_completion_v31/scripts/replay.py
```

This command reconstructs exact v30 from the v10 carrier and frozenv11–v30 inputs, then applies v31 without web requests. Baseline commit: `d8a19a4ea5f8e84480f313c54c8e9cedb3e5ff17`; baseline canonical JSONL SHA256: `4313e08b77eee084ed6ba828b1490a57deba8fab502a6fe09a4780db8ac14e8a`. Current canonical SHA256: `c9c6b0d913c4ec0a8ff9a5d458ad8707da398ded149b86cd3c2794ee8f1d1932`. The v29 first-pass closeout remains a historical prior file with its original v29 hash; its103 blank records are unchanged and no new first-birthplace work is performed.

All native DOB/calendar/authority/cohort/eligibility/DOB grades, birthplace text/grades/URLs/claims/selected evidence/official status/hashes, country/QIDs/personal coordinates, prior facts and untargeted complete objects remain frozen. Only six geographic fields and current context may change. No other cohort, statistical deduplication, BaZi, outcomes or final cohort freeze is performed. Source QA and independent final QA are separate; final QA checks reconstruction, geographic-only rollback, frozen birthplaces/sidecars, source-class roles, CSV/counts and two isolated replays against five production pins. Gzip uses blank filename/zero mtime; its output master is packaged and reproducible, not duplicated as another Git blob. The manifest excludes itself and Python caches.
