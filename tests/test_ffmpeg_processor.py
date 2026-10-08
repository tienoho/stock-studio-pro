"""
Tests for FFmpegProcessor in src.infrastructure.media.ffmpeg_processor.
"""

import unittest
from pathlib import Path
from src.infrastructure.media.ffmpeg_processor import FFmpegProcessor


class TestFFmpegProcessor(unittest.TestCase):
    def setUp(self):
        self.processor = FFmpegProcessor()

    def test_video_extensions(self):
        valid = [Path("a.mp4"), Path("b.mov"), Path("c.mkv"), Path("d.webm")]
        for p in valid:
            self.assertIn(p.suffix.lower(), FFmpegProcessor.VIDEO_EXTENSIONS)

        invalid = [Path("thumb.jpg"), Path("script.json"), Path("audio.mp3")]
        for p in invalid:
            self.assertNotIn(p.suffix.lower(), FFmpegProcessor.VIDEO_EXTENSIONS)

    def test_ffmpeg_exists_method(self):
        # Result depends on whether ffmpeg is installed in system PATH
        res = self.processor.ffmpeg_exists()
        self.assertIsInstance(res, bool)


if __name__ == "__main__":
    unittest.main()
