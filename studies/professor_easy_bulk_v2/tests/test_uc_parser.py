"""Offline synthetic checks for the cross-volume conservative UC parser."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "parse_uc_memorial.py"


def load_parser():
    spec = importlib.util.spec_from_file_location("uc_memorial_v2", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    exec(compile(SCRIPT.read_bytes(), str(SCRIPT), "exec"), module.__dict__)
    return module


class UCParserTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="uc-parser-tests-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.pdf = self.root / "actual_local_download.pdf"
        self.pdf.write_bytes(b"synthetic PDF bytes for source hash; not parsed")
        self.module = load_parser()

    def run_parser(self, prose, volume="2000", url=None, output="out"):
        text = self.root / (output + ".txt")
        text.write_text("=== PDF physical page 7 ===\nJane Smith, Mathematics: Berkeley\n1910–1990\nProfessor of Mathematics\n" + prose + "\n", encoding="utf-8")
        out = self.root / output
        args = ["--text", str(text), "--pdf", str(self.pdf), "--output-dir", str(out),
                "--source-url", url or f"https://digicoll.lib.berkeley.edu/nanna/record/1/files/inmemoriam{volume}.pdf",
                "--volume-year", volume]
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.module.main(args)
        return json.loads((out / "candidates.json").read_text(encoding="utf-8"))

    def test_volume_ids_and_actual_source_metadata(self):
        prose = "Jane Smith was born on May 2, 1910."
        first = self.run_parser(prose, volume="2000", output="first")
        second = self.run_parser(prose, volume="2001", output="second")
        a, b = first["records"][0], second["records"][0]
        self.assertNotEqual(a["candidate_id"], b["candidate_id"])
        self.assertIn("2000", a["candidate_id"])
        self.assertIn("2001", b["candidate_id"])
        self.assertEqual(a["source"]["filename"], self.pdf.name)
        self.assertEqual(a["source"]["volume_year"], 2000)
        self.assertIn("inmemoriam2000.pdf", a["source"]["url"])
        self.assertEqual(first["source_file"], self.pdf.name)
        self.assertEqual(a["calendar"], "not_stated")
        self.assertEqual(a["status"], "automatic_unverified")
        self.assertEqual((a["birth_month"], a["birth_day"]), (5, 2))

    def test_other_person_and_pronoun_births_do_not_fill_subject_date(self):
        cases = ["Jane Smith's father was born on May 2, 1890.",
                 "Jane Smith was a professor. She was born on May 2, 1910.",
                 "Jane Smith was born on May 2, 1890."]
        for i, prose in enumerate(cases):
            with self.subTest(prose=prose):
                record = self.run_parser(prose, output=f"other{i}")["records"][0]
                self.assertEqual(record["birth_year"], 1910)
                self.assertEqual(record["precision"], "year")
                self.assertIsNone(record["birth_month"])
                self.assertIsNone(record["birth_day"])

    def test_year_or_incomplete_month_never_gets_a_default_day(self):
        for i, prose in enumerate(["Jane Smith was born in 1910.", "Jane Smith was born in May 1910."]):
            with self.subTest(prose=prose):
                record = self.run_parser(prose, output=f"partial{i}")["records"][0]
                self.assertEqual(record["precision"], "year")
                self.assertIsNone(record["birth_month"])
                self.assertIsNone(record["birth_day"])
                self.assertIsNone(record["birth_date_raw"])

    def test_untrusted_or_mismatched_source_and_invalid_volume_rejected(self):
        cases = [
            ("2000", "http://digicoll.lib.berkeley.edu/inmemoriam2000.pdf"),
            ("2000", "https://berkeley.edu.example.org/inmemoriam2000.pdf"),
            ("2000", "https://name:secret@digicoll.lib.berkeley.edu/inmemoriam2000.pdf"),
            ("2000", "https://digicoll.lib.berkeley.edu/inmemoriam2001.pdf"),
            ("1799", "https://digicoll.lib.berkeley.edu/inmemoriam1799.pdf"),
            ("2101", "https://digicoll.lib.berkeley.edu/inmemoriam2101.pdf"),
            ("02000", "https://digicoll.lib.berkeley.edu/inmemoriam2000.pdf"),
        ]
        for i, (volume, url) in enumerate(cases):
            with self.subTest(volume=volume, url=url):
                with self.assertRaises(SystemExit):
                    self.run_parser("Jane Smith was born on May 2, 1910.", volume=volume, url=url, output=f"bad{i}")
                self.assertFalse((self.root / f"bad{i}").exists())


if __name__ == "__main__":
    unittest.main()
