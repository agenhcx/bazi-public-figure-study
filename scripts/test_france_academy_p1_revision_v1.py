"""Offline integrity regressions for the frozen five-volume P1 revision."""
import copy
import unittest
from unittest.mock import patch

import france_academy_update_source_checkpoint_v2 as update


class P1RevisionTests(unittest.TestCase):
    def setUp(self):
        path=update.REPO/"data/france_academy_source_checkpoint_v3/cumulative_source_checked_unique_volumes_v2.csv"
        self.baseline_sha=update.sha(path)
        self.previous_ids={int(r["volume"]) for r in update.read_baseline(path)}
        self.selected=self.sources(update.P1_VOLUMES)
        self.checkpoint={"version":update.P1_REVISION_VERSION,"volumes":list(update.P1_VOLUMES),
            "baseline_sha256":self.baseline_sha,"review_queue":update.P1_REVIEW_QUEUE.as_posix(),
            "review_queue_sha256":update.P1_REVIEW_QUEUE_SHA}

    @staticmethod
    def sources(volumes):
        return {v:{"year":str(1835+v//2),"table_http_status":"LOCAL_CACHE",
            "wikisource_table_url":update.build_urls(v,1835+v//2)["wiki"]} for v in volumes}

    def validate(self,checkpoint=None,selected=None):
        return update.validate_revision_selection(
            self.checkpoint if checkpoint is None else checkpoint,
            self.selected if selected is None else selected,self.previous_ids,self.baseline_sha)

    def test_valid_p1_binds_frozen_queue_provenance(self):
        self.assertEqual(self.validate(),{update.P1_REVIEW_QUEUE.as_posix():update.P1_REVIEW_QUEUE_SHA})

    def test_rejects_incomplete_or_reordered_p1_scope(self):
        for volumes in (update.P1_VOLUMES[:-1],list(reversed(update.P1_VOLUMES))):
            with self.subTest(volumes=volumes):
                checkpoint=dict(self.checkpoint,volumes=volumes)
                with self.assertRaisesRegex(RuntimeError,"five frozen volumes in order"):
                    self.validate(checkpoint,self.sources(volumes))

    def test_rejects_wrong_revision_url_or_year(self):
        for field,value in (("wikisource_table_url",self.selected[35]["wikisource_table_url"]),("year","1837")):
            with self.subTest(field=field):
                selected=copy.deepcopy(self.selected)
                selected[3][field]=value
                with self.assertRaisesRegex(RuntimeError,"canonical volume: 3"):
                    self.validate(selected=selected)

    def test_rejects_wrong_input_baseline_sha(self):
        with self.assertRaisesRegex(RuntimeError,"baseline SHA differs"):
            self.validate(dict(self.checkpoint,baseline_sha256="0"*64))

    def test_rejects_wrong_queue_identity_or_changed_frozen_queue(self):
        for field,value in (("review_queue","data/other/queue.csv"),("review_queue_sha256","0"*64)):
            with self.subTest(field=field):
                with self.assertRaisesRegex(RuntimeError,"review queue"):
                    self.validate(dict(self.checkpoint,**{field:value}))
        with patch.object(update,"sha",return_value="0"*64):
            with self.assertRaisesRegex(RuntimeError,"Frozen P1 review queue bytes changed"):
                self.validate()

    def test_prior_three_volume_revision_keeps_its_scope_and_canonical_urls(self):
        checkpoint={"version":"france-academy-shard02-grammar-revision-v2","volumes":[37,98,128]}
        self.assertEqual(self.validate(checkpoint,self.sources([37,98,128])),{})
        with self.assertRaisesRegex(RuntimeError,"Shard02 grammar revision scope changed"):
            self.validate(checkpoint,self.sources([37,98]))


if __name__=="__main__":unittest.main()
