from __future__ import annotations

import copy
import importlib.util
import io
import unittest
from contextlib import redirect_stderr
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = REPO_ROOT / "deploy" / "validate_monitor_config.py"
TEMPLATE_PATH = REPO_ROOT / "examples" / "retail-rewind-six-camera.yml"

spec = importlib.util.spec_from_file_location("validate_monitor_config", VALIDATOR_PATH)
validator = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(validator)


class SixCameraConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = yaml.safe_load(TEMPLATE_PATH.read_text(encoding="utf-8"))

    def test_reference_template_is_valid(self) -> None:
        validator.validate_six_camera(copy.deepcopy(self.config))

    def test_embedded_credentials_are_rejected(self) -> None:
        self.config["essentials"]["screens"][0]["streams"][0]["url"] = (
            "rtsp://user:password@NVR_HOST:8554/STREAM_SLOT_1"
        )
        with redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                validator.validate_six_camera(self.config)

    def test_wrong_column_count_is_rejected(self) -> None:
        self.config["essentials"]["screens"][0]["nr_of_columns"] = 2
        with redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                validator.validate_six_camera(self.config)

    def test_wrong_stream_count_is_rejected(self) -> None:
        self.config["essentials"]["screens"][0]["streams"].pop()
        with redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                validator.validate_six_camera(self.config)

    def test_invalid_port_is_rejected_without_a_traceback(self) -> None:
        self.config["essentials"]["screens"][0]["streams"][0]["url"] = (
            "rtsp://NVR_HOST:not-a-port/STREAM_SLOT_1"
        )
        with redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                validator.validate_six_camera(self.config)


if __name__ == "__main__":
    unittest.main()
