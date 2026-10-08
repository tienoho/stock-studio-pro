"""
Unit tests for SceneVoiceMatcher application service.
"""

import unittest
import tempfile
import shutil
from pathlib import Path

from src.application.services.scene_voice_matcher import SceneVoiceMatcher, SceneVoiceMatchItem
from src.infrastructure.media.ffmpeg_processor import FFmpegProcessor


class TestSceneVoiceMatcher(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())
        self.matcher = SceneVoiceMatcher()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_parse_srt(self):
        srt_file = self.test_dir / "sample.srt"
        srt_content = """1
00:00:01,000 --> 00:00:04,500
Đây là phân cảnh thứ nhất

2
00:00:05,200 --> 00:00:08,800
Đây là phân cảnh thứ hai
"""
        srt_file.write_text(srt_content, encoding="utf-8")
        parsed = self.matcher.parse_srt(srt_file)

        self.assertEqual(len(parsed), 2)
        self.assertAlmostEqual(parsed[0]["start"], 1.0, places=2)
        self.assertAlmostEqual(parsed[0]["end"], 4.5, places=2)
        self.assertAlmostEqual(parsed[0]["duration"], 3.5, places=2)
        self.assertIn("thứ nhất", parsed[0]["text"])

        self.assertAlmostEqual(parsed[1]["start"], 5.2, places=2)
        self.assertAlmostEqual(parsed[1]["end"], 8.8, places=2)
        self.assertAlmostEqual(parsed[1]["duration"], 3.6, places=2)

    def test_get_scene_folders_natural_sort(self):
        (self.test_dir / "Canh 10").mkdir()
        (self.test_dir / "Canh 2").mkdir()
        (self.test_dir / "Canh 1").mkdir()

        folders = self.matcher.get_scene_folders(self.test_dir)
        names = [f.name for f in folders]
        self.assertEqual(names, ["Canh 1", "Canh 2", "Canh 10"])

    def test_get_video_files(self):
        folder = self.test_dir / "scene_test"
        folder.mkdir()
        (folder / "vid1.mp4").write_text("dummy")
        (folder / "vid2.MOV").write_text("dummy")
        (folder / "image.jpg").write_text("dummy")
        (folder / "notes.txt").write_text("dummy")

        videos = self.matcher.get_video_files(folder)
        names = sorted([v.name.lower() for v in videos])
        self.assertEqual(names, ["vid1.mp4", "vid2.mov"])

    def test_get_media_files_includes_images(self):
        folder = self.test_dir / "media_test"
        folder.mkdir()
        (folder / "photo1.jpg").write_text("dummy")
        (folder / "clip1.mp4").write_text("dummy")
        (folder / "ignored.txt").write_text("dummy")

        media = self.matcher.get_media_files(folder)
        names = sorted([m.name.lower() for m in media])
        self.assertEqual(names, ["clip1.mp4", "photo1.jpg"])

    def test_parse_script_json(self):
        json_file = self.test_dir / "script.json"
        json_data = {
            "scenes": [
                {"id": 1, "title": "Bình minh", "dialogue": "Một ngày mới bắt đầu", "duration": 4.5},
                {"id": 2, "title": "Hành động", "dialogue": "Tàu điện lướt qua", "duration": 5.0}
            ]
        }
        import json
        json_file.write_text(json.dumps(json_data, ensure_ascii=False), encoding="utf-8")
        segments = self.matcher.parse_script_json(json_file)
        self.assertEqual(len(segments), 2)
        self.assertEqual(segments[0]["text"], "Một ngày mới bắt đầu")
        self.assertEqual(segments[0]["duration"], 4.5)

    def test_mux_audio_to_video_stream_mapping(self):
        """Verifies _mux_audio_to_video uses explicit mapping for video and audio streams."""
        from unittest.mock import MagicMock
        fake_ffmpeg = MagicMock()
        mock_res = MagicMock()
        mock_res.returncode = 0
        fake_ffmpeg._run_cmd.return_value = mock_res

        matcher = SceneVoiceMatcher(fake_ffmpeg)
        out_mock = self.test_dir / "out.mp4"
        out_mock.touch()
        # Mock file size > 1024
        with unittest.mock.patch.object(Path, "stat") as mock_stat:
            mock_stat.return_value.st_size = 2048
            matcher._mux_audio_to_video(Path("vid.mp4"), Path("voice.mp3"), out_mock)

        cmd = fake_ffmpeg._run_cmd.call_args[0][0]
        self.assertIn("-map", cmd)
        self.assertIn("0:v:0", cmd)
        self.assertIn("1:a:0", cmd)


if __name__ == "__main__":
    unittest.main()
