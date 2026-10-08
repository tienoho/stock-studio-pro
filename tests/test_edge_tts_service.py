"""
Unit tests for EdgeTTSService.
"""

import unittest
from pathlib import Path
import tempfile
import shutil

from src.application.services.edge_tts_service import EdgeTTSService, AVAILABLE_VOICES


class TestEdgeTTSService(unittest.TestCase):
    def setUp(self):
        self.service = EdgeTTSService()
        self.test_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_available_voices_list(self):
        voices = self.service.get_available_voices()
        self.assertGreaterEqual(len(voices), 4)

        voice_ids = [v["id"] for v in voices]
        self.assertIn("vi-VN-HoaiMyNeural", voice_ids)
        self.assertIn("vi-VN-NamMinhNeural", voice_ids)
        self.assertIn("en-US-JennyNeural", voice_ids)

    def test_synthesize_empty_text_returns_error(self):
        out_file = self.test_dir / "test.mp3"
        ok, msg = self.service.synthesize("", out_file)
        self.assertFalse(ok)
        self.assertIn("rỗng", msg)


if __name__ == "__main__":
    unittest.main()
