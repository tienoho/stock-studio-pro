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

    def test_concat_audio_empty(self):
        ok, msg = self.processor.concat_audio([], Path("dummy.mp3"))
        self.assertFalse(ok)
        self.assertIn("rỗng", msg.lower())

    def test_concat_clips_empty(self):
        ok, msg = self.processor.concat_clips([], Path("dummy.mp4"))
        self.assertFalse(ok)
        self.assertIn("rỗng", msg.lower())

    def test_ffmpeg_exists_method(self):
        res = self.processor.ffmpeg_exists()
        self.assertIsInstance(res, bool)


if __name__ == "__main__":
    unittest.main()

