"""Offline P2 scope/provenance and real-parser revision-only integrity regressions."""
import contextlib,copy,io,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
import france_academy_run_legacy_p2_review_v1 as runner
import france_academy_update_source_checkpoint_v2 as update


BASELINE=update.REPO/update.P2_BASELINE


class P2RevisionMetadataTests(unittest.TestCase):
    def setUp(self):
        self.baseline=update.read_baseline(BASELINE,require_v2=True)
        self.provenance=update.p2_revision_provenance(self.baseline,update.sha(BASELINE))
        self.selected={v:{"year":str(1835+v//2),"table_http_status":"LOCAL_CACHE",
            "wikisource_table_url":update.build_urls(v,1835+v//2)["wiki"],
            "table_html_sha256":"f"*64,"original_printed_election_pages_directly_inspected":"0"}
            for v in update.P2_VOLUMES}
        self.checkpoint={"version":update.P2_REVISION_VERSION,"volumes":list(update.P2_VOLUMES),
            **copy.deepcopy(self.provenance),"source_sha256_comparison":update.p2_source_comparison(
                self.provenance["prior_source_records"],self.selected),
            "original_event_pages_inspected":0,"accepted_memberships":0,
            "accepted_birthdates":0,"bazi_variables_computed":0}

    def validate(self,checkpoint=None,selected=None,baseline=None,baseline_sha=None):
        return update.validate_revision_selection(
            self.checkpoint if checkpoint is None else checkpoint,
            self.selected if selected is None else selected,set(range(1,212)),
            update.P2_BASELINE_SHA if baseline_sha is None else baseline_sha,
            self.baseline if baseline is None else baseline)

    def test_valid_p2_binds_historical_source_records_and_both_hashes(self):
        self.assertEqual(self.validate(),{update.P2_REVIEW_QUEUE.as_posix():update.P2_REVIEW_QUEUE_SHA})
        self.assertEqual(len(self.checkpoint["prior_source_records"]),16)
        self.assertTrue(all(not r["source_bytes_identical"] for r in self.checkpoint["source_sha256_comparison"]))

    def test_rejects_missing_reordered_and_substituted_scope(self):
        for volumes in (update.P2_VOLUMES[:-1],list(reversed(update.P2_VOLUMES)),[53]+update.P2_VOLUMES[1:]):
            with self.subTest(volumes=volumes):
                cp=dict(self.checkpoint,volumes=volumes)
                with self.assertRaisesRegex(RuntimeError,"sixteen frozen volumes"):
                    self.validate(cp)

    def test_version_renaming_cannot_bypass_frozen_scope(self):
        for version in ("unrestricted-p2",update.P1_REVISION_VERSION,"france-academy-shard02-grammar-revision-v2"):
            with self.subTest(version=version):
                with self.assertRaises(RuntimeError):self.validate(dict(self.checkpoint,version=version))
        with self.assertRaisesRegex(RuntimeError,"not a new shard"):
            self.validate(dict(self.checkpoint,shard=0))

    def test_rejects_wrong_baseline_or_queue_identity(self):
        for field,value in (("baseline_sha256","0"*64),("review_queue","data/other.csv"),("review_queue_sha256","0"*64)):
            with self.subTest(field=field):
                with self.assertRaisesRegex(RuntimeError,"provenance differs"):
                    self.validate(dict(self.checkpoint,**{field:value}))
        with self.assertRaisesRegex(RuntimeError,"frozen v9 baseline SHA"):
            self.validate(baseline_sha="0"*64)

    def test_rejects_modified_history_and_frozen_queue_bytes(self):
        for field,value in (("source_html_sha256","0"*64),("parsed_index_event_rows","1"),("technical_status","HTTP_404")):
            cp=copy.deepcopy(self.checkpoint);cp["prior_source_records"][0][field]=value
            with self.subTest(field=field),self.assertRaisesRegex(RuntimeError,"provenance differs"):
                self.validate(cp)
        baseline=copy.deepcopy(self.baseline)
        next(r for r in baseline if r["volume"]=="54")["source_html_sha256"]="0"*64
        with self.assertRaisesRegex(RuntimeError,"historical source differs"):
            self.validate(baseline=baseline)
        original_sha=update.sha
        def changed_queue(path):
            return "0"*64 if Path(path).resolve()==(update.REPO/update.P2_REVIEW_QUEUE).resolve() else original_sha(path)
        with patch.object(update,"sha",side_effect=changed_queue),self.assertRaisesRegex(RuntimeError,"Frozen P2 review queue bytes changed"):
            self.validate()

    def test_rejects_wrong_source_url_year_and_failed_replacement(self):
        for field,value in (("wikisource_table_url",self.selected[55]["wikisource_table_url"]),("year","1900"),("table_http_status","HTTP_404")):
            selected=copy.deepcopy(self.selected);selected[54][field]=value
            with self.subTest(field=field),self.assertRaises(RuntimeError):self.validate(selected=selected)

    def test_rejects_fabricated_source_sha_comparison(self):
        for field,value in (("baseline_source_html_sha256","0"*64),("current_source_html_sha256","0"*64),("source_bytes_identical",True)):
            cp=copy.deepcopy(self.checkpoint);cp["source_sha256_comparison"][0][field]=value
            with self.subTest(field=field),self.assertRaisesRegex(RuntimeError,"source SHA comparison differs"):
                self.validate(cp)

    def test_rejects_nonzero_or_missing_p2_gates(self):
        for field in ("original_event_pages_inspected","accepted_memberships","accepted_birthdates","bazi_variables_computed"):
            with self.subTest(field=field),self.assertRaisesRegex(RuntimeError,"checkpoint gates absent"):
                self.validate(dict(self.checkpoint,**{field:1}))
        selected=copy.deepcopy(self.selected);selected[54]["original_printed_election_pages_directly_inspected"]="1"
        with self.assertRaisesRegex(RuntimeError,"not index-only"):self.validate(selected=selected)


class P2RunnerTests(unittest.TestCase):
    def test_default_plan_never_requests_or_creates_outputs(self):
        with tempfile.TemporaryDirectory() as d,patch.object(runner.inventory,"main") as capture,contextlib.redirect_stdout(io.StringIO()) as stream:
            output=Path(d)/"absent"
            runner.main(["--out",str(output)])
            report=json.loads(stream.getvalue())
            self.assertEqual(report["volumes"],update.P2_VOLUMES)
            self.assertEqual(report["planned_new_volumes"],0)
            self.assertEqual(report["live_network_requests"],0)
            self.assertFalse(output.exists());capture.assert_not_called()

    def test_blocked_or_missing_offline_capture_never_seals(self):
        for error in (HTTPError("https://example.invalid",403,"blocked",None,None),FileNotFoundError("offline missing")):
            with self.subTest(error=type(error).__name__),tempfile.TemporaryDirectory() as d:
                output=Path(d)/"partial";observed=[]
                def fail_capture():
                    observed.extend(sys.argv)
                    raise error
                with patch.object(runner.inventory,"main",side_effect=fail_capture),patch.object(runner,"seal_existing") as seal:
                    with self.assertRaises(type(error)):
                        runner.main(["--run","--offline","--out",str(output)])
                    seal.assert_not_called()
                self.assertIn("--offline",observed)
                self.assertEqual(observed[observed.index("--sample-volumes")+1],",".join(map(str,update.P2_VOLUMES)))
                self.assertEqual(observed[observed.index("--max-table-probes")+1],"16")
                self.assertFalse((output/"source_only_shard_checkpoint_v1.json").exists())

    def test_incomplete_existing_inventory_cannot_be_sealed(self):
        with tempfile.TemporaryDirectory() as d,patch.object(runner.ledger,"main") as ledger:
            output=Path(d);runner.inventory.write_json_atomic(output/"summary.json",{"run_complete":False})
            with self.assertRaisesRegex(RuntimeError,"inventory is incomplete"):
                runner.seal_existing(output,BASELINE)
            ledger.assert_not_called()
            self.assertFalse((output/"source_only_shard_checkpoint_v1.json").exists())


class P2PureRevisionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.source=self.root/"source";self.cache=self.root/"cache"
        self.source.mkdir();self.cache.mkdir();self.output=self.root/"v10"
        html=("<table><tr><td><span class='sc'>NOMINATIONS de Membres et de Correspondants de l'Académie</span> "
              "— M. Hermite est nommé à la place vacante dans la Section de Géométrie</td><td>85</td></tr></table>"
              +"<p>"+"Source context. "*50+"</p>").encode()
        catalog=[]
        for v in range(1,212):
            row=dict.fromkeys(runner.inventory.COLS,"")
            row.update(volume=v,year=1835+v//2,wikisource_table_url=update.build_urls(v,1835+v//2)["wiki"],
                       table_sampled="0",table_http_status="NOT_CHECKED",original_printed_election_pages_directly_inspected="0",
                       study_membership_accepted="0",study_DOB_accepted="0",bazi_variables_computed="0")
            if v in update.P2_VOLUMES:
                (self.cache/f"table_{v}_{row['year']}.html").write_bytes(html)
                runner.inventory.probe_table(row,self.cache,True,1,1.5,[None])
                self.assertEqual(row["transcribed_election_rows"],"1")
            catalog.append(row)
        runner.inventory.write_csv(self.source/update.FILES[0],catalog,runner.inventory.COLS)
        runner.inventory.write_json_atomic(self.source/"summary.json",{
            "run_complete":True,"table_probes_completed":16,"category_volume_count":211,
            "table_of_contents_probed_volumes":list(update.P2_VOLUMES),
            "table_probe_http_status":{"LOCAL_CACHE":16},"table_probe_election_heading_count":16,
            "sample_election_event_candidates":16,"accepted_full_memberships":0,
            "accepted_exact_dobs":0,"bazi_variables_computed":0})

    def seal(self):
        with contextlib.redirect_stdout(io.StringIO()):runner.seal_existing(self.source,BASELINE,self.cache)

    def run_update(self,*extra):
        argv=["update","--baseline",str(BASELINE),"--revision-dir",str(self.source),
              "--cache-root",str(self.cache),"--out",str(self.output),*extra]
        with patch.object(sys,"argv",argv),contextlib.redirect_stdout(io.StringIO()):update.main()

    def test_sealing_preserves_capture_inventory_provenance_and_first_files(self):
        provenance={"baseline_sha256":update.P2_BASELINE_SHA,"review_queue_sha256":update.P2_REVIEW_QUEUE_SHA,
                    "frozen_volumes":update.P2_VOLUMES,"root_capture_note":"preserve exactly"}
        runner.inventory.write_json_atomic(self.source/"pre_capture_provenance_v1.json",provenance)
        for name in ("first_capture_person_events_v1.csv","first_capture_source_review_v1.json","source_run_progress_v1.json"):
            (self.source/name).write_bytes(b"frozen original bytes\n")
        preserved={p.name:p.read_bytes() for p in self.source.iterdir()}
        with patch.object(runner.inventory,"main") as capture:self.seal();capture.assert_not_called()
        self.assertTrue(all((self.source/name).read_bytes()==data for name,data in preserved.items()))
        selected,events,cp,_=update.verify_batch(self.source,self.cache)
        self.assertEqual(len(selected),16);self.assertEqual(len(events),16)
        self.assertEqual(cp["version"],update.P2_REVISION_VERSION)
        self.assertNotIn("shard",cp)

    def test_revision_only_uses_real_verify_and_preserves_other_195_rows(self):
        self.seal();self.run_update("--revision-only")
        old={int(r["volume"]):r for r in update.rows(BASELINE)}
        new={int(r["volume"]):r for r in update.rows(self.output/"cumulative_source_checked_unique_volumes_v2.csv")}
        self.assertEqual(set(new),set(range(1,212)))
        for v in old:
            if v not in update.P2_VOLUMES:self.assertEqual(new[v],old[v])
            else:
                self.assertEqual(new[v]["baseline_source_html_sha256"],old[v]["source_html_sha256"])
                self.assertEqual(new[v]["baseline_parsed_index_event_rows"],"0")
                self.assertEqual(new[v]["parsed_index_event_rows"],"1")
                self.assertNotEqual(new[v]["source_html_sha256"],old[v]["source_html_sha256"])
                self.assertEqual(new[v]["source_probe_group"],old[v]["source_probe_group"])
        summary=update.load(self.output/"summary.json")
        self.assertEqual(summary["candidate_original_journal_INDEX_events_including_all_roles_and_offices"],754)
        self.assertEqual(summary["grammar_revision_net_added_index_events"],16)
        self.assertEqual(summary["source_revision_net_added_index_events"],16)
        self.assertEqual(summary["revision_delta_semantics"],"CURRENT_SOURCE_REPLACEMENT_EVENT_DELTA_NOT_ISOLATED_GRAMMAR_EFFECT")
        self.assertEqual(summary["revision_source_sha256_comparison_counts"],{"same":0,"different":16})
        self.assertEqual(summary["new_frozen_shard_volumes"],0);self.assertIsNone(summary["new_frozen_shard"])
        self.assertEqual(summary["new_shard_index_event_rows"],0)
        self.assertEqual(summary["reparsed_prior_volumes"],update.P2_VOLUMES)
        self.assertFalse(update.rows(self.output/"remaining_source_queue_v2.csv"))
        self.assertEqual({r["update_kind"] for r in update.rows(self.output/"added_or_reparsed_index_events_v2.csv")},{"REPARSED_PRIOR_SOURCE"})
        saved={p.name:p.read_bytes() for p in self.output.iterdir()}
        self.run_update("--revision-only")
        self.assertEqual(saved,{p.name:p.read_bytes() for p in self.output.iterdir()})

    def test_real_verify_rejects_modified_current_source_bytes(self):
        self.seal();path=self.cache/"table_54_1862.html";path.write_bytes(path.read_bytes()+b"changed")
        with self.assertRaisesRegex(RuntimeError,"SHA256 mismatch"):self.run_update("--revision-only")
        self.assertFalse(self.output.exists())

    def test_real_verify_rejects_modified_event_field(self):
        self.seal();path=self.source/"verified_transcribed_person_event_candidates_v1.csv"
        records=update.rows(path);records[0]["name_as_transcribed"]="invented replacement"
        runner.inventory.write_csv(path,records,runner.ledger.FIELDS)
        with self.assertRaisesRegex(RuntimeError,"Reparsed events differ"):self.run_update("--revision-only")
        self.assertFalse(self.output.exists())

    def test_explicit_pure_mode_rejects_new_shard_and_wrong_revision_version(self):
        self.seal()
        with patch.object(update,"verify_batch") as verify,self.assertRaisesRegex(RuntimeError,"forbids --shard-dir"):
            self.run_update("--revision-only","--shard-dir","unused")
        verify.assert_not_called()
        with self.assertRaisesRegex(RuntimeError,"Frozen P2 requires --revision-only"):
            self.run_update()
        path=self.source/"source_only_shard_checkpoint_v1.json";cp=update.load(path);cp["version"]=update.P1_REVISION_VERSION
        runner.inventory.write_json_atomic(path,cp)
        with self.assertRaisesRegex(RuntimeError,"cannot substitute another revision"):
            self.run_update("--revision-only")
        self.assertFalse(self.output.exists())


if __name__=="__main__":unittest.main()
