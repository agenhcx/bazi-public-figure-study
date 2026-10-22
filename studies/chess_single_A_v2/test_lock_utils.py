import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("lock_utils", HERE / "lock_utils.py")
u = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(u)


class LockTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.study = self.root / u.STUDY
        for name in u.CORE_FILES:
            self.write(str(u.STUDY / name), "synthetic fixture\n")
        self.write(str(u.STUDY / "config.json"), json.dumps({"fit_allowed": True}))
        self.write(str(u.STUDY / "requirements-model.txt"), "numpy==2.3.5\n")
        self.write(str(u.STUDY / "data/data_manifest.json"), json.dumps({"roles": {
            "development": {"path": str(u.STUDY / "data/derived.csv"),
                            "source": {"path": str(u.STUDY / "data/source.csv")}}}}))
        self.write(str(u.STUDY / "data/derived.csv"), "canonical_id,rating\n1,2500\n")
        self.write(str(u.STUDY / "data/source.csv"), "fide_id,rating\n1,2500\n")
        self.write(".github/workflows/chess_single_a_models_v2.yml", "synthetic workflow\n")
        self.lock = u.create_analysis_lock(self.root, source_data_commit="a" * 40,
                                           input_preparation_commit="b" * 40)

    def write(self, relative, value):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value, encoding="utf-8")

    def test_binds_code_config_derived_and_source_inputs(self):
        result = u.verify_analysis_lock(self.root, check_environment=False)
        self.assertTrue(result["prior_outcome_access_disclosed"])
        for name in ("data/derived.csv", "data/source.csv", "models.py", "config.json"):
            self.assertIn(str(u.STUDY / name), result["files"])

    def test_changed_model_input_is_blocked_before_training(self):
        self.write(str(u.STUDY / "data/derived.csv"), "canonical_id,rating\n1,2800\n")
        with self.assertRaisesRegex(ValueError, "fingerprint mismatch"):
            u.verify_analysis_lock(self.root, check_environment=False)

    def test_changed_estimator_code_is_blocked(self):
        self.write(str(u.STUDY / "models.py"), "changed estimator\n")
        with self.assertRaisesRegex(ValueError, "fingerprint mismatch"):
            u.verify_analysis_lock(self.root, check_environment=False)

    def test_missing_required_binding_is_blocked(self):
        self.lock["files"].pop(str(u.STUDY / "train_models.py"))
        self.write(str(u.LOCK_FILE), json.dumps(self.lock))
        with self.assertRaisesRegex(ValueError, "omits required"):
            u.verify_analysis_lock(self.root, check_environment=False)

    def test_disabled_fit_and_path_escape_are_rejected(self):
        self.write(str(u.STUDY / "config.json"), json.dumps({"fit_allowed": False}))
        with self.assertRaisesRegex(ValueError, "explicitly allow"):
            u.create_analysis_lock(self.root, source_data_commit="a", input_preparation_commit="b")
        with self.assertRaisesRegex(ValueError, "relative"):
            u._relative_file(self.root, "/tmp/escape")

    def test_environment_and_threads_are_checked(self):
        env = {name: "1" for name in u.THREAD_ENV}
        env["PYTHONHASHSEED"] = "0"
        actual = {"python": "3.11.17", "numpy": "2.3.5"}
        with patch.object(u, "environment_versions", return_value=actual), patch.dict(os.environ, env):
            u.verify_analysis_lock(self.root)
            with patch.dict(os.environ, {"OPENBLAS_NUM_THREADS": "2"}):
                with self.assertRaisesRegex(ValueError, "Thread limit"):
                    u.verify_analysis_lock(self.root)
        with patch.object(u, "environment_versions", return_value={"python": "3.12.14"}):
            with self.assertRaisesRegex(ValueError, "Environment mismatch"):
                u.verify_analysis_lock(self.root)


if __name__ == "__main__":
    unittest.main()
