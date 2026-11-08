# Royal Society birthplace completion V46

This data overlay records one positive original-source recovery: the National Portrait Gallery person biography explicitly describes Peter John Morris as Australian-born. The accepted birthplace is Australia, source grade S3, South. The source states birth year 1934, not the native day/month; all original DOB evidence and identity fields remain unchanged. See METHOD_SCHEMA.md and the pinned source-stage QA/adjudication for the admission decision.

Run from a repository checkout:

```sh
python -B studies/royal_society_birthplace_completion_v46/scripts/replay.py
```

The script requires the exact pinned V44 master. A data ZIP can carry it as `inputs/baseline_v44_birthplace_rows.jsonl.gz`; a repository checkout can use the existing sibling V44 master. If both are absent, first regenerate V44 with `python -B studies/royal_society_birthplace_completion_v44/scripts/replay.py`. The overlay stops on a missing or changed baseline and never imports the historical pipeline. `--baseline PATH` and `--output-dir PATH` support explicit carriers and isolated output directories. Both baseline gzip and canonical master hashes are verified.

`inputs/accepted_birthplaces.json` and `inputs/accepted_geography.json` are exact root-final facts from `studies/royal_society_original_source_followup_v46`. `audit/source_stage_pointer.json` must pin these inputs, the frozen `audit/source_scope.json`, independent `audit/source_qa.json`, and root `audit/source_adjudication.json`. Nine issue inventories, inherited V29/V35 plans, and five complete native objects are retained as bounded current provenance. No cumulative empty replay wrappers or copied historical source audit are needed.

The actual replay writes five outputs. Its 201-column CSV preserves all 200 V44 columns and appends one positive context column. It verifies exact rollback, 4,982 unchanged complete rows, native fields and all historical contexts. Two sequential isolated overlay runs exited successfully and produced identical hashes for all five outputs. Their receipts/logs are retained in `audit/`. Source acquisition and data reproduction are distinct checks; the final independent full-data report is `audit/independent_data_qa.json`.

The fixed Royal Society master remains 4,983 membership records. Within native DOB 1835–1985 inclusive, there are 2,644 records: 2,305 North, 183 South and 156 unknown. The unresolved records comprise 102 blank birthplaces and 54 stored-place geography holds. This is a one-record data change, with 4,982 complete objects unchanged; no deduplicated-person count, new analysis eligibility or statistical outcome is inferred.

The downloadable archive contains both this data folder and its sibling original-source stage. From the extracted archive root, run `python -B royal_society_birthplace_completion_v46/scripts/replay.py`; the included pinned baseline carrier supports reproduction without rebuilding earlier versions. Binary baseline/output gzip files are packaged deliverables; Git stores the replay, reviewed facts and text outputs, with the existing V44 regeneration command as its baseline prerequisite.
