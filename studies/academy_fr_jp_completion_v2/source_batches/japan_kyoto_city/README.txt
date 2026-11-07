Kyoto City official honorary-citizen directory harvest, 2026-10-29.

The complete directory contains 58 person names. Exact normalized full-name
matching against the fixed 435 Japan science candidates yields 14 matches.
Four (Honjo, Yamanaka, Hayaishi, Mitsuda) are explicitly delegated to shard C.
The remaining ten each have an explicit full date in the municipal profile's
birth-date field. This batch is complete for those ten directory matches.

The useful precision gain is Koichi Tanaka: the earlier society profile gave
1959-08 only, while this municipal body explicitly gives Showa34 8月3日.
Other batch overlap must be deduplicated by member_key; do not count each
corroborating source as a new person. Sakurada's source explicitly says January1;
this is a source-supplied day, not precision padding. Older original spelling
櫻田/廣中 is linked using documented character variants, not fuzzy matching.

Five additional scientific profiles were inspected but do not match the fixed
435 roster: Kawamura Tamiji, Hattori Shunjiro, Imanishi Kinji, Okada Tokindo and
Sakaguchi Shimon. They are not added and no academy membership is inferred from
municipal honors. Akira Suzuki and Akira Yoshino are absent from the directory.

All claims preserve the Japanese era-date statement. Era YEAR transcription
does not change the printed month/day; no lunar/solar calendar conversion is
performed. Calendar names are not explicit, so calendar=not_stated is retained.

Web open/find retrieved municipal page bodies (not search snippets). Two direct
HTTP attempts to capture the directory returned one 403 and one timeout. Hence source_sha256 is null.
The separate evidence_capture_sha256 identifies the saved web-tool extraction,
not original HTML. Those full web-tool captures stay private and are not part of
the minimized publication. Exact web retrieval clock time was not recorded;
retrieved_utc remains null and retrieval date is preserved.

web_observations.json is the fixed minimized input; directory_names.json holds
all 58 observed directory names and directory_inventory.json their 14 candidate
matches and dispositions. assemble.py replays and validates claims offline;
use --roster PATH and --output-dir PATH for portability. collect.py is an optional
live HTTP collector/parser; direct directory access failed in this environment,
so the published results are replayed from the body observations instead.

No final cohort/membership adjudication, BaZi computation or analysis freeze.
