"""No-network boundary regressions for frozen shards and verified prior sources."""
import contextlib
import copy
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import france_academy_run_remaining_172_toc_batch_v1 as runner
import france_academy_update_source_checkpoint_v2 as checkpoint

REPO=Path(__file__).resolve().parents[1]
FROZEN4=[41,71,103,133,165,195,14,42,73,104,134,166,196,15,44,74]
NEW4=[41,71,103,133,165,195,14,73,104,134,166,196,15,44,74]
PRIOR=REPO/"data/france_academy_source_checkpoint_v2/cumulative_source_checked_unique_volumes_v2.csv"


class BaselineResumeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.previous=Path.cwd()
        os.chdir(REPO)
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(os.chdir,self.previous)

    def dry_run(self,shard,baseline=None):
        argv=["runner","--shard",str(shard)]
        if baseline:argv.extend(["--baseline",str(baseline)])
        output=io.StringIO()
        with patch.object(sys,"argv",argv), contextlib.redirect_stdout(output), patch.object(
                runner,"run_inventory",side_effect=AssertionError("Dry run attempted source requests")):
            runner.main()
        return output.getvalue()

    def copy_baseline(self,subdir="baseline"):
        folder=Path(self.tmp.name)/subdir
        folder.mkdir()
        dest=folder/PRIOR.name
        shutil.copyfile(PRIOR,dest)
        shutil.copyfile(PRIOR.parent/"summary.json",folder/"summary.json")
        return dest

    def validate(self,report):
        prior={int(r["volume"]) for r in checkpoint.read_baseline(PRIOR)}
        return checkpoint.validate_shard_selection(report,report["volumes"],prior,PRIOR,FROZEN4)

    def test_overlap_42_is_reused_with_source_provenance_and_frozen_order(self):
        report=json.loads(self.dry_run(4,PRIOR))
        self.assertEqual(report["frozen_volumes"],FROZEN4)
        self.assertEqual(report["volumes"],NEW4)
        self.assertEqual(report["reused_prior_volumes"],[42])
        self.assertEqual(report["required_table_requests_max"],15)
        self.assertEqual(report["baseline_sha256"],checkpoint.sha(PRIOR))
        record=report["reused_prior_source_records"][0]
        self.assertEqual((record["volume"],record["year"],record["parsed_index_event_rows"]),(42,"1856","7"))
        self.assertEqual(record["source_html_sha256"],"2e6b32b56a5ff5ea28c4aef52ada56218d9dc10a5c5ecd5539e58d4d2af4d6f9")
        self.assertEqual(self.validate(report)["reused_prior_volumes"],[42])

    def test_missing_prior_record_is_rejected_before_source_requests(self):
        path=self.copy_baseline()
        records=[r for r in checkpoint.rows(path) if r["volume"]!="42"]
        path.write_bytes(checkpoint.csv_bytes(records,checkpoint.FIELDS))
        with self.assertRaisesRegex(RuntimeError,"Baseline CSV SHA"):
            self.dry_run(4,path)

    def test_malformed_or_unadjudicated_baseline_record_is_rejected(self):
        changes=[("year","1855"),("source_html_sha256",""),("accepted_member","1"),
                 ("technical_status","NOT_CHECKED")]
        for i,(key,value) in enumerate(changes):
            with self.subTest(field=key):
                path=self.copy_baseline("bad"+str(i))
                records=checkpoint.rows(path)
                next(r for r in records if r["volume"]=="42")[key]=value
                path.write_bytes(checkpoint.csv_bytes(records,checkpoint.FIELDS))
                with self.assertRaises(RuntimeError):self.dry_run(4,path)
        path=self.copy_baseline("missing-column")
        path.write_bytes(checkpoint.csv_bytes(
            [{k:v for k,v in r.items() if k!="year"} for r in checkpoint.rows(path)],
            [k for k in checkpoint.FIELDS if k!="year"]))
        with self.assertRaisesRegex(RuntimeError,"Incomplete v2 baseline columns"):
            self.dry_run(4,path)

    def test_missing_new_volume_cannot_be_hidden_as_partial_shard(self):
        report=json.loads(self.dry_run(4,PRIOR))
        report["volumes"].remove(41)
        with self.assertRaisesRegex(RuntimeError,"every frozen-minus-baseline"):
            self.validate(report)

    def test_unexpected_reuse_missing_provenance_and_wrong_baseline_are_rejected(self):
        original=json.loads(self.dry_run(4,PRIOR))
        cases=[]
        wrong=copy.deepcopy(original);wrong["reused_prior_volumes"].append(71);cases.append(wrong)
        wrong=copy.deepcopy(original);wrong.pop("reused_prior_source_records");cases.append(wrong)
        wrong=copy.deepcopy(original);wrong["baseline_sha256"]="0"*64;cases.append(wrong)
        wrong=copy.deepcopy(original);wrong["reused_prior_source_records"][0]["parsed_index_event_rows"]="0";cases.append(wrong)
        wrong=copy.deepcopy(original);wrong["frozen_volumes"].remove(42);cases.append(wrong)
        for i,report in enumerate(cases):
            with self.subTest(case=i), self.assertRaisesRegex(RuntimeError,"reuse provenance"):
                self.validate(report)

    def test_no_baseline_dry_run_retains_original_shard03_bytes(self):
        frozen3=[191,11,39,69,100,131,162,192,12,40,70,102,132,163,193,13]
        expected={"version":"france-academy-remaining-172-toc-shard-runner-v1","shard":3,"volumes":frozen3,
            "required_table_requests_max":16,"required_requests_max":21,"live_network_requests":0,
            "original_scanned_election_pages_inspected":0,"accepted_memberships":0,"bazi_variables_computed":0}
        self.assertEqual(self.dry_run(3),json.dumps(expected,ensure_ascii=False)+"\n")

    def test_no_overlap_checkpoint_serialization_matches_frozen_outputs(self):
        # Use frozen input ledgers to isolate the checkpoint serialization
        # contract from source parsing, which has its own runtime SHA checks.
        def existing_batch(folder,_cache):
            catalog=checkpoint.rows(folder/checkpoint.FILES[0])
            selected=checkpoint.unique([r for r in catalog if r["table_sampled"]=="1"],"Test inventory")
            return (selected,checkpoint.rows(folder/checkpoint.FILES[4]),
                    checkpoint.load(folder/checkpoint.FILES[2]),
                    {checkpoint.label(folder/name):checkpoint.sha(folder/name) for name in checkpoint.FILES})
        out=Path(self.tmp.name)/"replayed"
        golden=checkpoint.load(PRIOR.parent/"summary.json")
        argv=["checkpoint","--revision-dir","data/france_academy_shard02_grammar_review_v2","--out",str(out)]
        with patch.object(sys,"argv",argv), patch.object(checkpoint,"verify_batch",side_effect=existing_batch), patch.object(
                checkpoint,"PARSER_VERSION",golden["parser_version"]), contextlib.redirect_stdout(io.StringIO()):
            checkpoint.main()
        for name in ("cumulative_source_checked_unique_volumes_v2.csv","remaining_source_queue_v2.csv",
                     "added_or_reparsed_index_events_v2.csv","summary.json"):
            with self.subTest(file=name):self.assertEqual((out/name).read_bytes(),(PRIOR.parent/name).read_bytes())


if __name__=="__main__":unittest.main()
