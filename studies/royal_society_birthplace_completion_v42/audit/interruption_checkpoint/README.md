# Royal Society V42 interruption checkpoint

This is a recovery checkpoint, not a complete V42 release. Six prospectively fixed records were reviewed and all six held. No birthplace, hemisphere, date, source grade, or other master value changed. The last complete release is V41 at commit 5556e7e981f29383187ea201beb1edb22ad04be0.

Source QA completed once: 171 checks passed, zero blockers. Replay preflight passed 112 checks; the root production main_v42 ran once with observed clean exit and all five output hashes were pinned. Independent final QA light preflight passed48 checks. Its full run reached56 structural checks and started two isolated CLI replays. The execution environment then became unavailable. Neither replay exit nor the final QA exit/report was observed. No complete V42 ZIP was created, and no normal V42 study is published by this checkpoint.

All4,983 complete master objects were observed unchanged fromV41. NativeDOB1835-1985 inclusive window remains2,644=2,305North+182South+157unknown(103blank,54stored-place unknown). All9 issue files remain byte-exact: activeDOB13,partialplace2,source-age4,and6otherfiles. No grade upgrade, new admission exception, source-exhaustion claim, analysis or final cohort freeze.

method_application_scope_v42.json is the original prospective scope text recovered from retained actual tool output. Its SHA256 was independently recomputed in the surviving orchestration runtime and exactly matches c5c7594d271b6923725acad91612b8f53b3528383d3bf50f0658ccfa0e639796. The two reconstructed_summary files are explicit attestations from retained tool results, not the original report bytes. checkpoint.json retains original file hashes, source references, verified production pins, the interrupted QA state and concrete resume steps. Missing original timestamps or bytes were not invented.

The environment failure cause is unknown. Check the existing QA session88045 first if the environment recovers. Only claim final verification after observing actual exits or completing a justified replacement run. Preserve this interruption record when a complete V42 release is later saved.
