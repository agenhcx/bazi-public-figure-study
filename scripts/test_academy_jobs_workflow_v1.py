#!/usr/bin/env python3
"""Exercise the workflow's PDF dependency preflight without apt or network."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest


WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/academy_uk_japan_followup_v1.yml"
STEP_NAME = "Ensure PDF wording verifier and Japanese CMap are available"
CMAP = "/usr/share/poppler/cMap/Adobe-Japan1/90ms-RKSJ-H"
CID_TO_UNICODE = "/usr/share/poppler/cidToUnicode/Adobe-Japan1"


def preflight_script() -> str:
    # Extract this one literal run block without adding a YAML dependency.
    lines = WORKFLOW.read_text(encoding="utf-8").splitlines()
    start = lines.index(f"      - name: {STEP_NAME}")
    if lines[start + 1] != "        run: |":
        raise AssertionError("Dependency preflight must remain a literal shell step")
    body = []
    for line in lines[start + 2:]:
        if line and not line.startswith("          "):
            break
        body.append(line)
    return textwrap.dedent("\n".join(body)) + "\n"


class WorkflowPDFDependencyTests(unittest.TestCase):
    def run_preflight(self, *, executable: bool, cmap: bool, cid: bool = True,
                      install_cmap: bool = True, install_cid: bool = True):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binary_dir = root / "bin"
            binary_dir.mkdir()
            cmap_path = root / "poppler" / "90ms-RKSJ-H"
            cmap_path.parent.mkdir()
            if cmap:
                cmap_path.write_text("test CMap", encoding="utf-8")
            cid_path = root / "poppler" / "Adobe-Japan1"
            if cid:
                cid_path.write_text("test CID-to-Unicode", encoding="utf-8")
            fake_pdf = binary_dir / "pdftotext"
            pdf_script = '#!/bin/sh\nprintf "%s\\n" "pdftotext version checked" >> "$PREFLIGHT_TEST_LOG"\n'
            if executable:
                fake_pdf.write_text(pdf_script, encoding="utf-8")
                fake_pdf.chmod(0o755)
            sudo = binary_dir / "sudo"
            sudo.write_text(f"#!{sys.executable}\n" + textwrap.dedent('''\
                import json, os, pathlib, sys
                args = sys.argv[1:]
                with open(os.environ["PREFLIGHT_TEST_LOG"], "a", encoding="utf-8") as stream:
                    stream.write(json.dumps(args) + "\\n")
                if args[:2] == ["apt-get", "install"]:
                    if "poppler-utils" not in args or "poppler-data" not in args:
                        sys.exit(23)
                    binary = pathlib.Path(os.environ["PREFLIGHT_FAKE_PDF"])
                    binary.write_text(os.environ["PREFLIGHT_PDF_SCRIPT"], encoding="utf-8")
                    binary.chmod(0o755)
                    if os.environ["PREFLIGHT_INSTALL_CMAP"] == "1":
                        pathlib.Path(os.environ["POPPLER_JAPANESE_CMAP"]).write_text("test CMap", encoding="utf-8")
                    if os.environ["PREFLIGHT_INSTALL_CID"] == "1":
                        pathlib.Path(os.environ["POPPLER_JAPANESE_CID_TO_UNICODE"]).write_text("test CID-to-Unicode", encoding="utf-8")
            '''), encoding="utf-8")
            sudo.chmod(0o755)
            log = root / "commands.log"
            env = dict(os.environ, PATH=str(binary_dir), POPPLER_JAPANESE_CMAP=str(cmap_path),
                       POPPLER_JAPANESE_CID_TO_UNICODE=str(cid_path),
                       PREFLIGHT_TEST_LOG=str(log), PREFLIGHT_FAKE_PDF=str(fake_pdf),
                       PREFLIGHT_PDF_SCRIPT=pdf_script, PREFLIGHT_INSTALL_CMAP="1" if install_cmap else "0",
                       PREFLIGHT_INSTALL_CID="1" if install_cid else "0")
            result = subprocess.run(["/bin/bash", "-e", "-c", preflight_script()], env=env,
                                    capture_output=True, text=True, timeout=10)
            commands = log.read_text(encoding="utf-8").splitlines() if log.exists() else []
            return result, commands

    def test_preflight_precedes_source_rehydration_and_pins_real_cmap_path(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn(f"      POPPLER_JAPANESE_CMAP: {CMAP}", workflow)
        self.assertIn(f"      POPPLER_JAPANESE_CID_TO_UNICODE: {CID_TO_UNICODE}", workflow)
        self.assertLess(workflow.index(f"      - name: {STEP_NAME}"),
                        workflow.index("--rehydrate-approved-sources"))

    def test_complete_environment_skips_install(self):
        result, commands = self.run_preflight(executable=True, cmap=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(commands, ["pdftotext version checked"])

    def test_missing_cmap_installs_both_packages(self):
        result, commands = self.run_preflight(executable=True, cmap=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(commands[0]), ["apt-get", "update"])
        self.assertEqual(json.loads(commands[1]), ["apt-get", "install", "--yes",
                                                  "--no-install-recommends", "poppler-utils", "poppler-data"])
        self.assertEqual(commands[2], "pdftotext version checked")

    def test_missing_executable_installs_both_packages(self):
        result, commands = self.run_preflight(executable=False, cmap=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("poppler-data", json.loads(commands[1]))
        self.assertEqual(commands[2], "pdftotext version checked")

    def test_missing_cid_to_unicode_installs_both_packages(self):
        result, commands = self.run_preflight(executable=True, cmap=True, cid=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("poppler-data", json.loads(commands[1]))
        self.assertEqual(commands[2], "pdftotext version checked")

    def test_still_missing_cmap_fails_before_replay(self):
        result, commands = self.run_preflight(executable=True, cmap=False, install_cmap=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(len(commands), 2)
        self.assertNotIn("pdftotext version checked", commands)

    def test_still_missing_cid_to_unicode_fails_before_replay(self):
        result, commands = self.run_preflight(executable=True, cmap=True, cid=False, install_cid=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(len(commands), 2)
        self.assertNotIn("pdftotext version checked", commands)


if __name__ == "__main__":
    unittest.main()
