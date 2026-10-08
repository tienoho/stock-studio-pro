"""
Unit tests validating data retrieval resilience across providers, parsers, and services.
"""

import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path

from src.core.models.api_key import APIKey
from src.core.models.scene import extract_scenes_from_json
from src.application.services.key_manager import KeyManager
from src.application.services.media_organizer_service import MediaOrganizerService
from src.infrastructure.providers.pexels_provider import PexelsProvider
from src.infrastructure.providers.pixabay_provider import PixabayProvider
from src.infrastructure.providers.vecteezy_provider import VecteezyProvider


class TestDataRetrievalResilience(unittest.TestCase):

    def test_pexels_best_video_handles_none_dimensions(self):
        """PexelsProvider._best_video must not raise TypeError when width or height is None."""
        provider = PexelsProvider()
        files = [
            {"width": None, "height": None, "file_type": "video/mp4", "link": "http://v1.mp4"},
            {"width": 1920, "height": 1080, "file_type": "video/mp4", "link": "http://v2.mp4"},
            {"width": 1280, "height": 720, "file_type": "video/mp4", "link": "http://v3.mp4"},
        ]
        best = provider._best_video(files)
        self.assertIsNotNone(best)
        self.assertEqual(best["link"], "http://v2.mp4")

    def test_pexels_marks_key_dead_on_401(self):
        """PexelsProvider marks key as dead and rotates on HTTP 401."""
        km = KeyManager(
            pexels_keys=[{"name": "P1", "key": "bad_key"}, {"name": "P2", "key": "good_key"}],
            pixabay_keys=[]
        )
        provider = PexelsProvider(km)
        with patch("requests.get") as mock_get:
            mock_resp_401 = MagicMock(status_code=401)
            mock_resp_200 = MagicMock(status_code=200)
            mock_resp_200.json.return_value = {"videos": []}
            mock_get.side_effect = [mock_resp_401, mock_resp_200]

            res = provider.search_videos("nature")
            self.assertEqual(res, [])
            self.assertTrue(km.pexels_keys[0].is_dead)

    def test_pixabay_query_truncation_and_key_invalidation(self):
        """PixabayProvider truncates queries > 100 chars and marks key dead on HTTP 400 bad key."""
        km = KeyManager(
            pexels_keys=[],
            pixabay_keys=[{"name": "Pix1", "key": "invalid_key"}, {"name": "Pix2", "key": "valid_key"}]
        )
        provider = PixabayProvider(km)
        long_query = "a" * 150

        with patch("requests.get") as mock_get:
            mock_resp_400 = MagicMock(status_code=400, text='[ERROR 400] Invalid or missing API key')
            mock_resp_200 = MagicMock(status_code=200)
            mock_resp_200.json.return_value = {"hits": []}
            mock_get.side_effect = [mock_resp_400, mock_resp_200]

            provider.search_photos(long_query)
            # The query sent in params should be truncated to 100
            called_params = mock_get.call_args_list[0][1]["params"]
            self.assertEqual(len(called_params["q"]), 100)
            # First key marked dead
            self.assertTrue(km.pixabay_keys[0].is_dead)

    def test_extract_scenes_from_json_supports_top_level_list(self):
        """extract_scenes_from_json should support direct JSON lists of scenes."""
        data = [
            {"id": 1, "dialogue": "Scene 1", "keywords": "nature, mountain, sky"},
            {"id": 2, "dialogue": "Scene 2", "tags": ["ocean", "waves"]},
        ]
        scenes = extract_scenes_from_json(data)
        self.assertEqual(len(scenes), 2)
        # Check fallback keywords parsed correctly
        self.assertEqual(scenes[0]["primary_keywords"], ["nature", "mountain", "sky"])
        self.assertEqual(scenes[1]["primary_keywords"], ["ocean", "waves"])

    def test_extract_scenes_from_json_assigns_missing_ids(self):
        """extract_scenes_from_json should assign sequential 1-based IDs if missing or empty."""
        data = {
            "scenes": [
                {"dialogue": "Intro", "primary_keywords": ["start"]},
                {"id": "", "dialogue": "Middle", "primary_keywords": ["middle"]},
            ]
        }
        scenes = extract_scenes_from_json(data)
        self.assertEqual(len(scenes), 2)
        self.assertEqual(scenes[0]["id"], 1)
        self.assertEqual(scenes[1]["id"], 2)

    def test_media_organizer_scan_matches_single_digit_and_str_keys(self, tmp_path=None):
        """scan_scene_downloads must count files like 1_00.mp4 and match string or int scene IDs."""
        import tempfile
        service = MediaOrganizerService()
        with tempfile.TemporaryDirectory() as tmp_dir:
            out = Path(tmp_dir)
            # Create files with single digit and 3-digit prefixes
            (out / "1_00.mp4").touch()
            (out / "1_01.mp4").touch()
            (out / "002_00-00-00_motionarray_001.mp4").touch()
            (out / "3_00_pexels_photo_001.jpg").touch()

            scenes = [
                {"id": "1", "time_start": "00:00"},
                {"id": 2, "time_start": "00:05"},
                {"id": "3", "time_start": "00:10"},
            ]

            audit = service.scan_scene_downloads(out, scenes)
            self.assertEqual(audit["total_files"], 4)
            self.assertEqual(audit["scenes_with_files"], 3)
            # Scene "1" has 2 files
            sc1_info = audit["scenes_counts"]["1"]
            self.assertEqual(sc1_info["other"], 2)


if __name__ == "__main__":
    unittest.main()
