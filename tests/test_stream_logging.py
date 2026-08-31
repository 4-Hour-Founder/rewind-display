from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "surveillance"))

from core.Stream import Stream  # noqa: E402


class StreamLoggingTests(unittest.TestCase):
    def test_constructor_does_not_log_rtsp_credentials(self) -> None:
        stream_config = {
            "url": "rtsp://camera-user:camera-secret@camera.invalid:554/sub",
        }
        with self.assertLogs("l_default", level="DEBUG") as captured:
            Stream("Display Camera", stream_config, object(), ":0.0", 0, 0, 0)
        combined = "\n".join(captured.output)
        self.assertNotIn("camera-user", combined)
        self.assertNotIn("camera-secret", combined)
        self.assertIn("<hidden_username>", combined)


if __name__ == "__main__":
    unittest.main()
