"""No-network regressions for bounded source fetching and interruption recovery."""
import contextlib
import csv
import io
import json
import os
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

import france_academy_comptes_rendus_211_volume_inventory_v1 as source


class SourceResumeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.previous=Path.cwd()
        os.chdir(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(os.chdir,self.previous)
        self.category=[{"volume":v,"year":source.expected_year(v),
            "wikisource_book_title":"Livre:Volume "+str(v)} for v in range(1,212)]
        self.html=b"<html><p>Fixture source without election text.</p></html>"

    def run_main(self,offline=False):
        args=["source","--sample-volumes","1,2","--max-table-probes","2","--out","out"]
        if offline:args.append("--offline")
        with patch.object(sys,"argv",args), patch.object(source,"get_category",return_value=(self.category,[{"sha256":"0"*64}])), patch.object(source.time,"sleep"), contextlib.redirect_stdout(io.StringIO()):
            source.main()

    def test_access_block_prevents_second_request_and_saves_partial(self):
        for code in (403,429):
            with self.subTest(status=code):
                calls=[]
                def fetch(url,timeout):
                    calls.append(url)
                    if url==source.OFFICIAL:return self.html,200,"text/html"
                    raise urllib.error.HTTPError(url,code,"blocked",None,None)
                with patch.object(source,"fetch",side_effect=fetch):
                    with self.assertRaises(urllib.error.HTTPError):self.run_main()
                table_calls=[url for url in calls if url!=source.OFFICIAL]
                self.assertEqual(len(table_calls),1)
                self.assertEqual(table_calls[0],source.build_urls(1,1835)["wiki"])
                summary=json.loads(Path("out/summary.json").read_text())
                self.assertFalse(summary["run_complete"])
                self.assertEqual(summary["table_probes_completed"],0)
                self.assertEqual(summary["run_status"],"STOPPED_HTTP_"+str(code))
                with Path("out/academy_original_wikisource_211_volume_inventory_v1.csv").open(encoding="utf-8-sig") as f:
                    rows=list(csv.DictReader(f))
                self.assertEqual(rows[0]["table_http_status"],"HTTP_"+str(code))
                self.assertEqual(rows[1]["table_http_status"],"NOT_CHECKED")

    def test_cached_success_survives_stop_and_offline_missing_is_incomplete(self):
        first_url=source.build_urls(1,1835)["wiki"]
        def fetch(url,timeout):
            if url in (source.OFFICIAL,first_url):return self.html,200,"text/html"
            raise urllib.error.HTTPError(url,403,"blocked",None,None)
        with patch.object(source,"fetch",side_effect=fetch):
            with self.assertRaises(urllib.error.HTTPError):self.run_main()
        with patch.object(source,"fetch",side_effect=AssertionError("offline network request")):
            with self.assertRaises(FileNotFoundError):self.run_main(offline=True)
        summary=json.loads(Path("out/summary.json").read_text())
        self.assertFalse(summary["run_complete"])
        self.assertEqual(summary["table_of_contents_probed_volumes"],[1])
        self.assertEqual(summary["table_probes_completed"],1)
        self.assertEqual(summary["incomplete_selected_volumes"],[2])
        self.assertEqual(summary["table_probe_http_status"],{"LOCAL_CACHE":1})

    def test_404_persists_and_offline_replays_without_request(self):
        calls=[]
        def fetch(url,timeout):
            calls.append(url)
            if url==source.OFFICIAL:return self.html,200,"text/html"
            raise urllib.error.HTTPError(url,404,"missing",None,None)
        with patch.object(source,"fetch",side_effect=fetch):self.run_main()
        self.assertEqual(len(calls),3)
        with patch.object(source,"fetch",side_effect=AssertionError("cached 404 made a request")):
            self.run_main(offline=True)
        summary=json.loads(Path("out/summary.json").read_text())
        self.assertTrue(summary["run_complete"])
        self.assertEqual(summary["table_probe_http_status"],{"HTTP_404":2})
        with Path("out/academy_original_wikisource_211_volume_inventory_v1.csv").open(encoding="utf-8-sig") as f:
            rows=list(csv.DictReader(f))
        self.assertEqual(rows[0]["transcribed_election_rows"],"")
        self.assertEqual(rows[0]["election_heading_detected"],"UNDETERMINED")


if __name__=="__main__":unittest.main()
