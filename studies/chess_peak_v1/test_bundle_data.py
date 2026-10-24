"""Synthetic transport and no-overwrite checks; never operate on study data."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import bundle_data as bundle


class BundleTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.data = self.root / bundle.DATA
        self.data.mkdir(parents=True)

    def tearDown(self):
        self.temporary.cleanup()

    def source(self, name, content):
        path = self.data / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    def write_manifest(self, manifest):
        (self.data / bundle.MANIFEST_NAME).write_text(json.dumps(manifest), encoding="utf-8")

    def test_roundtrip_multifile_safe_names_and_deterministic_repacking(self):
        contents = {"nested/history with spaces.json.gz": bytes(range(120)), "second.bin": b"abc" * 31,
            "direct.txt": b"small", "empty.txt": b""}
        for name, content in contents.items():
            self.source(name, content)
        manifest = bundle.pack_data(self.root, part_size=17)
        self.assertEqual(len(manifest["files"]), 4)
        self.assertEqual(bundle.pack_data(self.root, part_size=17), manifest)
        for record in manifest["files"]:
            path = self.root / record["path"]
            self.assertEqual(path.read_bytes(), contents[path.relative_to(self.data).as_posix()])
            if record["parts"]:
                self.assertEqual(record["parts"][0]["bytes"], 17)
                self.assertRegex(Path(record["parts"][0]["path"]).name, r"^[0-9a-f]{16}_[A-Za-z0-9_.-]+\.part001$")
                path.unlink()
        restored = bundle.restore_bundles(self.root)
        self.assertEqual(restored, manifest)
        for name, content in contents.items():
            self.assertEqual((self.data / name).read_bytes(), content)
        self.assertEqual(bundle.restore_bundles(self.root), manifest)

    def test_empty_inventory_and_zero_byte_direct_file(self):
        self.assertEqual(bundle.pack_data(self.root, 8)["files"], [])
        self.assertEqual(bundle.restore_bundles(self.root)["files"], [])
        empty = self.source("zero.bin", b"")
        record = bundle.pack_data(self.root, 8)["files"][0]
        self.assertEqual(record["parts"], [])
        self.assertEqual(record["bytes"], 0)
        self.assertEqual(record["sha256"], hashlib.sha256(b"").hexdigest())
        bundle.restore_bundles(self.root)
        self.assertEqual(empty.read_bytes(), b"")

    def test_corrupt_or_missing_part_stops_before_any_restore(self):
        first = self.source("first.bin", b"a" * 25)
        second = self.source("second.bin", b"b" * 25)
        manifest = bundle.pack_data(self.root, 8)
        first.unlink()
        second.unlink()
        part = self.root / manifest["files"][1]["parts"][0]["path"]
        original = part.read_bytes()
        part.write_bytes(b"c" * len(original))
        with self.assertRaisesRegex(ValueError, "SHA256"):
            bundle.restore_bundles(self.root)
        self.assertFalse(first.exists())
        self.assertFalse(second.exists())
        part.unlink()
        with self.assertRaisesRegex(ValueError, "absent"):
            bundle.restore_bundles(self.root)

    def test_resealed_part_still_requires_whole_file_hash(self):
        source = self.source("history.bin", b"a" * 20)
        manifest = bundle.pack_data(self.root, 8)
        source.unlink()
        record = manifest["files"][0]["parts"][0]
        part = self.root / record["path"]
        part.write_bytes(b"b" * record["bytes"])
        record["sha256"] = hashlib.sha256(part.read_bytes()).hexdigest()
        self.write_manifest(manifest)
        with self.assertRaisesRegex(ValueError, "whole-file"):
            bundle.restore_bundles(self.root)
        self.assertFalse(source.exists())

    def test_existing_correct_target_kept_and_wrong_target_never_overwritten(self):
        source = self.source("history.bin", b"a" * 25)
        bundle.pack_data(self.root, 8)
        before = source.stat().st_ino
        bundle.restore_bundles(self.root)
        self.assertEqual(source.stat().st_ino, before)
        source.write_bytes(b"b" * 25)
        with self.assertRaisesRegex(ValueError, "SHA256"):
            bundle.restore_bundles(self.root)
        self.assertEqual(source.read_bytes(), b"b" * 25)

    def test_concurrently_created_target_is_not_overwritten(self):
        source = self.source("history.bin", b"a" * 25)
        bundle.pack_data(self.root, 8)
        source.unlink()
        original_link = bundle.os.link
        def raced_link(temporary, target, **kwargs):
            Path(target).write_bytes(b"r" * 25)
            return original_link(temporary, target, **kwargs)
        with patch.object(bundle.os, "link", side_effect=raced_link):
            with self.assertRaisesRegex(ValueError, "SHA256"):
                bundle.restore_bundles(self.root)
        self.assertEqual(source.read_bytes(), b"r" * 25)
        self.assertEqual(list(self.data.glob(".bundle-restore-*")), [])

    def test_original_and_part_paths_cannot_escape_or_target_manifest(self):
        self.source("history.bin", b"a" * 25)
        original = bundle.pack_data(self.root, 8)
        invalid = ["/tmp/escape", "../escape", (bundle.DATA / ".." / "escape").as_posix(),
            "studies/chess_single_A_v2/data/escape", (bundle.DATA / "bundles" / "escape").as_posix(),
            (bundle.DATA / bundle.MANIFEST_NAME).as_posix(), (bundle.DATA / "." / "escape").as_posix() + "/../escape",
            bundle.DATA.as_posix() + "//escape", bundle.DATA.as_posix() + "/back\\slash"]
        for relative in invalid:
            with self.subTest(original_path=relative):
                changed = json.loads(json.dumps(original))
                changed["files"][0]["path"] = relative
                self.write_manifest(changed)
                with self.assertRaises(ValueError):
                    bundle.restore_bundles(self.root)
        changed = json.loads(json.dumps(original))
        changed["files"][0]["parts"][0]["path"] = (bundle.DATA / "outside.part001").as_posix()
        self.write_manifest(changed)
        with self.assertRaises(ValueError):
            bundle.restore_bundles(self.root)

    def test_missing_direct_source_manifest_or_data_directory_stop(self):
        with self.assertRaises(ValueError):
            bundle.restore_bundles(self.root)
        source = self.source("small.bin", b"small")
        bundle.pack_data(self.root, 8)
        source.unlink()
        with self.assertRaisesRegex(ValueError, "Direct-published"):
            bundle.restore_bundles(self.root)
        with tempfile.TemporaryDirectory() as empty:
            with self.assertRaisesRegex(ValueError, "directory is absent"):
                bundle.pack_data(empty)

    def test_overlapping_originals_and_existing_file_parents_fail_before_restore(self):
        first = self.source("a.bin", b"a" * 25)
        nested = self.source("nested/b.bin", b"b" * 25)
        manifest = bundle.pack_data(self.root, 8)
        manifest["files"][1]["path"] = (bundle.DATA / "a.bin/b.bin").as_posix()
        first.unlink()
        nested.unlink()
        self.write_manifest(manifest)
        with self.assertRaisesRegex(ValueError, "ancestors"):
            bundle.restore_bundles(self.root)
        self.assertFalse(first.exists())
        # Even without another manifest entry, a file cannot become a parent.
        manifest["files"] = manifest["files"][1:]
        first.write_bytes(b"existing parent file")
        self.write_manifest(manifest)
        with self.assertRaisesRegex(ValueError, "parent is not a directory"):
            bundle.restore_bundles(self.root)
        self.assertEqual(first.read_bytes(), b"existing parent file")

    def test_malformed_inventory_sizes_hashes_order_and_duplicate_sources_stop(self):
        self.source("history.bin", b"a" * 25)
        original = bundle.pack_data(self.root, 8)
        mutations = [lambda m: m.update(protocol_id="unknown"), lambda m: m.update(part_size=True),
            lambda m: m["files"][0].update(bytes=bundle.MAX_FILE_BYTES + 1),
            lambda m: m["files"][0].update(sha256="bad"), lambda m: m["files"][0].update(parts=[]),
            lambda m: m["files"][0]["parts"].reverse(), lambda m: m["files"][0]["parts"][0].update(bytes=7),
            lambda m: m["files"].append(m["files"][0]), lambda m: m["files"][0].update(unknown=True)]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                changed = json.loads(json.dumps(original))
                mutation(changed)
                self.write_manifest(changed)
                with self.assertRaises(ValueError):
                    bundle.restore_bundles(self.root)
        (self.data / bundle.MANIFEST_NAME).write_text('{"protocol_id":"one","protocol_id":"two"}')
        with self.assertRaisesRegex(ValueError, "duplicate JSON keys"):
            bundle.restore_bundles(self.root)

    def test_symlink_source_parent_or_part_is_rejected(self):
        outside = self.root / "outside.bin"
        outside.write_bytes(b"outside")
        link = self.data / "escape.bin"
        link.symlink_to(outside)
        with self.assertRaisesRegex(ValueError, "symlink"):
            bundle.pack_data(self.root, 8)
        link.unlink()
        source = self.source("nested/history.bin", b"a" * 25)
        manifest = bundle.pack_data(self.root, 8)
        source.unlink()
        source.parent.rmdir()
        source.parent.symlink_to(self.root, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlink"):
            bundle.restore_bundles(self.root)
        source.parent.unlink()
        source.parent.mkdir()
        part = self.root / manifest["files"][0]["parts"][0]["path"]
        part.unlink()
        part.symlink_to(outside)
        with self.assertRaisesRegex(ValueError, "symlink"):
            bundle.restore_bundles(self.root)

    def test_file_cap_and_invalid_part_sizes_stop_before_reading_large_source(self):
        source = self.source("oversize.bin", b"")
        with source.open("wb") as stream:
            stream.truncate(bundle.MAX_FILE_BYTES + 1)
        with self.assertRaisesRegex(ValueError, "50 MiB"):
            bundle.pack_data(self.root, 8)
        self.assertFalse((self.data / bundle.MANIFEST_NAME).exists())
        source.unlink()
        for part_size in (0, -1, True, 1.5, bundle.MAX_FILE_BYTES + 1):
            with self.subTest(part_size=part_size), self.assertRaises(ValueError):
                bundle.pack_data(self.root, part_size)

    def test_pack_refuses_corrupt_reused_parts_and_source_changes(self):
        source = self.source("history.bin", b"a" * 25)
        manifest = bundle.pack_data(self.root, 8)
        part = self.root / manifest["files"][0]["parts"][0]["path"]
        part.write_bytes(b"b" * 8)
        before = (self.data / bundle.MANIFEST_NAME).read_bytes()
        with self.assertRaisesRegex(ValueError, "SHA256"):
            bundle.pack_data(self.root, 8)
        self.assertEqual(part.read_bytes(), b"b" * 8)
        self.assertEqual((self.data / bundle.MANIFEST_NAME).read_bytes(), before)
        changing = self.source("changing.bin", b"x" * 25)
        original_hash = bundle._hash_file
        def changed_after_hash(path, expected_bytes=None):
            result = original_hash(path, expected_bytes)
            if path == changing:
                path.write_bytes(b"y" * 25)
            return result
        with patch.object(bundle, "_hash_file", side_effect=changed_after_hash):
            with self.assertRaisesRegex(ValueError, "changed between hashing and splitting"):
                bundle.pack_data(self.root, 8)
        self.assertEqual((self.data / bundle.MANIFEST_NAME).read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
