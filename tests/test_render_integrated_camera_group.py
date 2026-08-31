from __future__ import annotations

import importlib.util
import io
import stat
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
RENDERER_PATH = REPO_ROOT / "deploy" / "render_integrated_camera_group.py"
VALIDATOR_PATH = REPO_ROOT / "deploy" / "validate_monitor_config.py"

renderer_spec = importlib.util.spec_from_file_location(
    "render_integrated_camera_group", RENDERER_PATH
)
renderer = importlib.util.module_from_spec(renderer_spec)
assert renderer_spec.loader is not None
renderer_spec.loader.exec_module(renderer)

validator_spec = importlib.util.spec_from_file_location(
    "validate_monitor_config_for_renderer", VALIDATOR_PATH
)
validator = importlib.util.module_from_spec(validator_spec)
assert validator_spec.loader is not None
validator_spec.loader.exec_module(validator)


class IntegratedCameraGroupRendererTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = {
            "camera_groups": {
                "display": {"cameras": ["front", "register", "aisle", "parking"]}
            },
            "go2rtc": {
                "streams": {
                    "front_sub": [
                        "rtsp://user:pass@10.0.0.1:554/sub#media=video"
                    ],
                    "register_sub": ["rtsp://user:pass@10.0.0.2:554/sub"],
                    "aisle_sub": ["rtsp://user:pass@10.0.0.3:554/sub"],
                    "parking_sub": ["rtsp://user:pass@10.0.0.4:554/sub"],
                }
            },
        }

    def test_rendered_group_is_valid_and_strips_go2rtc_fragment(self) -> None:
        rendered, cameras = renderer.render_group(self.config, "display")
        loaded = yaml.safe_load(rendered)
        validator.validate_integrated_four_camera(loaded)
        self.assertEqual(cameras, ["front", "register", "aisle", "parking"])
        self.assertNotIn("#media=video", rendered)

    def test_output_is_mode_0600(self) -> None:
        rendered, _ = renderer.render_group(self.config, "display")
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "monitor1.yml"
            renderer.write_protected(output, rendered, force=False)
            mode = stat.S_IMODE(output.stat().st_mode)
            self.assertEqual(mode, 0o600)

    def test_selected_camera_can_use_loopback_restream(self) -> None:
        rendered, _ = renderer.render_group(
            self.config, "display", restream_cameras={"parking"}
        )
        loaded = yaml.safe_load(rendered)
        validator.validate_integrated_four_camera(loaded)
        streams = loaded["essentials"]["screens"][0]["streams"]
        self.assertEqual(
            streams[3]["url"],
            "http://127.0.0.1:1984/api/stream.mp4?src=parking_sub",
        )
        self.assertNotIn(
            "--rtsp-transport=tcp", streams[3]["freeform_advanced_mpv_options"]
        )
        self.assertIn("--vo=gpu", streams[3]["freeform_advanced_mpv_options"])
        self.assertIn(
            "--gpu-context=x11egl", streams[3]["freeform_advanced_mpv_options"]
        )

    def test_restream_camera_must_belong_to_group(self) -> None:
        with redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                renderer.render_group(
                    self.config, "display", restream_cameras={"unknown"}
                )

    def test_non_rtsp_source_is_rejected(self) -> None:
        self.config["go2rtc"]["streams"]["front_sub"] = [
            "ffmpeg:http://camera.invalid/sub"
        ]
        with redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                renderer.render_group(self.config, "display")

    def test_group_must_have_exactly_four_cameras(self) -> None:
        self.config["camera_groups"]["display"]["cameras"].pop()
        with redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                renderer.render_group(self.config, "display")


if __name__ == "__main__":
    unittest.main()
