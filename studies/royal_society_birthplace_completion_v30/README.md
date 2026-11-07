# Royal Society geographic support v30

This batch reviews twelve fixed records from the69 existing-place records with unresolved geography in the native1835–1985 window. It adds one geography-only resolution: Arthur Alcock Rambaut, North, supported by a new S2 original birth-country observation. No birthplace text, birthplace source grade, DOB or prior evidence is replaced.

| Scope | North | South | Unknown | Total |
|---|---:|---:|---:|---:|
| All fixed UK records | 4,191 | 187 | 605 | 4,983 |
| Native DOB1835–1985, inclusive | 2,291 | 182 | 171 | 2,644 |

The window's171 unknown records comprise103 blank birthplaces and68 stored places with unresolved geography. Across all records these counts are525 and80. All103 blank-window complete objects are unchanged. The69-record geographic queue is an eligibility pool, not69 biographies read. Twelve individual geographic followups produced one adoption and eleven holds. Exactly4,982 complete objects remain identical to v29.

## Rambaut: geographic support without replacing birthplace

| Field | Before | After |
|---|---|---|
| Stored birthplace | Waterford | Waterford |
| Original birthplace source grade | S1 | S1 |
| Original birthplace URL, claim and evidence | Frozen | Unchanged |
| Hemisphere | Unknown | North |
| New geographic support | None | S2, explicit Waterford, Ireland in original ODNB public Extract |

The newly acquired attributed ODNB public Extract by literal P A Wayman states full Arthur Alcock Rambaut, lifespan1859–1923, exact21September1859 and a direct Waterford, Ireland born clause. Its original publication is2004-09-23 and displayed version2015-09-17. The access-limited remainder was not read. The existing Waterford label matches the new birth-country context; Ireland is wholly northern. The new grade is `geographic_support_only`, with no upgrade or downgrade of original S1 birthplace support or native DOB grades. No personal country, QID, coordinates or modern administrative normalization is assigned.

A separate newly acquired Dictionary of Irish Biography person entry by Patricia M.Byrne states the same full subject, exact date, lifespan and Waterford city, with birth metadata Co.Waterford. It supplies the distinctive personal career context: astronomer royal for Ireland and Andrews professor in1892, Radcliffe Observer at Oxford in1897. These are DIB observations; the ODNB public Extract itself provides the astronomer label and family context. DIB original publication/revision is October2009. This person entry is distinct from an earlier taxonomy-only route. No informational independence or civil-record verification is claimed. ODNB describes second of three sons while DIB describes third son; the family-ordinal contrast is retained without adjudication or a manufactured DOB/place conflict.

## Jardine: seventh qualified DOB-source conflict

A genuinely new original2013 Independent interview by Steve Connor has a biographical vital section naming Lisa Anne Jardine CBE and stating12April1944. The frozen native date is1944-04-14. Full name and distinctive UCL Renaissance-studies/HFEA2008 career bind the observation to the same subject. The date assertion is conservatively S3 as a new journalist biographical observation only; it is not an adopted geographic fact or a DOB/birthplace grade change. The dated2013 source does not confirm the later2015 endpoint.

Jardine is appended as the seventh qualified active DOB-source conflict. All six older conflict objects remain unchanged. Her entire master object, original Oxford birthplace, S1 birthplace grade, DOB, source evidence and geographic unknown status remain unchanged. No correct-date/native-error/parser-error verdict is made. Prior AnnualReport/Nature search projections remain unacquired discovery observations; this new body does not retrospectively qualify them. NIAS's year-only Oxford, UK entry and other dateless material cannot bypass the unresolved date hold. Tomes's provisional printed-day/glyph uncertainty remains separate and is not an eighth confirmed conflict.

| Other held record | Evidence or limit |
|---|---|
| Jerry Adams | Existing generic USA context remains unresolved; a new oral-history route failed without an acquired qualifying birth-region body. Frozen nameJerry Adams is not expanded from a QID. |
| Pierre Henry John Young | No genuinely new qualifying birth-region body; generic France and old mirror results are not automatically mapped. |
| Basil Kassanis | Existing Macedonian-born wording remains unqualified. Reused memoir cover/abstract gives no new geographic body; first observed download returned404 and stopped. |
| George Douglas Hutton Bell | No qualifying new birth-country/region body; Wales in education/national context is excluded. |
| Charles William Bunn | New memoir route unavailable; archive index names an appreciation without its body. Frozen IUCr work was not reopened. |
| Peter Michael Maitlis | New original-work routes unavailable; escape/emigration from Germany does not qualify the born clause. |
| Bernard Ephraim Julius Pagel | New original authored Observatory obituary still states bornBerlin only. NPG's generic PlaceGermany taxonomy lacks a birth relationship. |
| Sheldon Francis Dudley | New original-body route reached a challenge and stopped; no geographic adoption or repair of the older internal FRS-year contrast. |
| Graham Garland Ross | New authored CERN obituary gives GrahamRoss/bornAberdeen1944; Scottish nationality is separate, Garland/exact DOB are absent. No omitted-middle exception or country inference. |
| Derman Guy Christopherson | New original memoir route unavailable; old Plumstead/south-eastLondon text remains geographically unresolved. |

The remaining eight inherited issue/method sidecars are byte-identical to v29. The active DOB sidecar changes only by appending Jardine after its six old objects. Gotch's place conflict, Malet's approximate-year hold, Waterfield's integer-age arithmetic, Midwinter's endpoint, Coles's cross-source age contrast, Wager's middle-name admission and Shortt's qualified ordinal-age wording remain unchanged. No omitted-middle or endpoint exception is invoked in this batch.

Source work comprises24 worker queries,19 worker navigation attempts and three root first opens:22 navigation attempts, plus four worker cached finds. There were no root queries/finds, screenshots or raw GETs. Source A inspected prior individual holds before discovery, but inspected Kassanis's acceptedv20 identity-only carrier context late, after a nonproductive carrier reuse. That reuse adds no new qualified body coverage; its first observed download404 stopped. This limitation is disclosed, and no adopted fact depends on it. Rambaut's actual ODNB and DIB person URLs were new acquisitions. Other actual errors, prior intents and result-mapping limits remain in ledgers. Failed routes stopped without retries, variants or bypass. Unknown raw HTTP status/request times/byte hashes remain null; parsed text is not raw bytes. Quotations are nine words for Rambaut's ODNB clause and four for Jardine's date, within25 words per original work. No full source HTML/PDF/images or projection caches are distributed.

## Files and replay

The cumulative ZIP contains the complete current `outputs/birthplace_rows.jsonl.gz`, CSVs, changes, summary, geography fact, audits and frozen inputs. The remaining-window CSV has171 records. CSV keeps all110 old columns and appends six v30 geographic columns, for116. All original birthplace columns retain their values; only the selected record's current hemisphere changes in the old projection. `geography_followup_v30` stores the new geographic-support fact and previous/absent geographic-field snapshots for exact rollback. The legacyv20 geography helper and all old loaders remain unchanged; a separate v30 helper handles current geography.

```sh
python studies/royal_society_birthplace_completion_v30/scripts/replay.py
```

The command reconstructs exact v29 from the v10 carrier and frozenv11–v29 inputs, then applies v30 without web requests. Baseline commit: `8c801f03dd42fb497d437ede34d6caf0d3a41e4a`; baseline canonical JSONL SHA256: `e528b4afce6ded29ff6af749b4d46a8d7b9d0bce7d57d34ac8f1366421bbce73`. Current canonical SHA256: `4313e08b77eee084ed6ba828b1490a57deba8fab502a6fe09a4780db8ac14e8a`. The v29 first-pass closeout is retained as a historical `prior_v29_first_pass_queue_closeout.json` with its original hash, not relabelled as a current-master audit. Its103 blank records remain unchanged; no new first-birthplace followups are performed.

Native DOB/calendar/authority/cohort/eligibility/DOB grades, birthplace text/grades/URLs/claims/selected evidence/official status/hashes, country/QIDs/personal coordinates, all prior facts and untargeted complete objects remain frozen. Only six geographic fields and the new context may change. No other cohort, statistical deduplication, BaZi, outcomes or final cohort freeze is performed. Source QA and independent final QA are separate; final QA checks exact baseline reconstruction, geographic-only rollback, frozen birthplaces, sidecar append, CSV/counts and two isolated replays against five production pins. Gzip uses blank filename/zero mtime; the output master is packaged and reproducible, not duplicated as another Git blob. The manifest excludes itself and Python caches.
