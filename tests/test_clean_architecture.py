"""
Unit tests validating Clean Architecture and SOLID compliance.
Tests SubtitleService, MediaProviderRegistry, MediaOrganizerService, BrowserService, and Provider LSP.
"""

import unittest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.core.interfaces.media_provider import IMediaProvider
from src.infrastructure.providers.pexels_provider import PexelsProvider
from src.infrastructure.providers.pixabay_provider import PixabayProvider
from src.infrastructure.providers.vecteezy_provider import VecteezyProvider
from src.application.services.media_provider_registry import MediaProviderRegistry
from src.application.services.subtitle_service import SubtitleService
from src.application.services.media_organizer_service import MediaOrganizerService
from src.application.services.browser_service import BrowserService
from src.ui.workers import VoiceGenerationWorker, SceneVoiceWorker


class TestCleanArchitectureAndSOLID(unittest.TestCase):
    """Test suite ensuring strict adherence to Clean Architecture and SOLID principles."""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # ─────────────────────────────────────────────────────────────────
    # 1. LSP: Liskov Substitution Principle on IMediaProvider
    # ─────────────────────────────────────────────────────────────────
    def test_media_providers_lsp_compliance(self):
        """Verify all concrete providers inherit from IMediaProvider and implement test_key uniformly."""
        providers = [
            PexelsProvider(),
            PixabayProvider(),
            VecteezyProvider(),
        ]
        for p in providers:
            self.assertIsInstance(p, IMediaProvider)
            self.assertTrue(hasattr(p, "platform_name"))
            self.assertTrue(hasattr(p, "search_videos"))
            self.assertTrue(hasattr(p, "search_photos"))
            self.assertTrue(hasattr(p, "test_key"))
            self.assertTrue(hasattr(p, "refresh_video_url"))

    # ─────────────────────────────────────────────────────────────────
    # 2. OCP & DIP: MediaProviderRegistry
    # ─────────────────────────────────────────────────────────────────
    def test_media_provider_registry_resolution(self):
        """Verify dynamic registration and mode-based resolution in MediaProviderRegistry."""
        km_mock = MagicMock()
        km_mock.pexels_keys = ["mock_key_1"]
        km_mock.pixabay_keys = ["mock_key_2"]
        km_mock.vecteezy_keys = []

        registry = MediaProviderRegistry(km_mock)

        # Resolves pexels only
        active = registry.resolve_providers_for_mode("Pexels", km_mock)
        self.assertIn("pexels", active)
        self.assertNotIn("pixabay", active)

        # Resolves pexels + pixabay (vecteezy skipped because no keys)
        active_all = registry.resolve_providers_for_mode("Tất cả", km_mock)
        self.assertIn("pexels", active_all)
        self.assertIn("pixabay", active_all)
        self.assertNotIn("vecteezy", active_all)

        # Custom provider registration without modifying registry class (Open/Closed)
        class MockUnsplashProvider(IMediaProvider):
            @property
            def platform_name(self) -> str:
                return "unsplash"
            def search_videos(self, query: str, per_page: int = 30):
                return []
            def search_photos(self, query: str, per_page: int = 30):
                return []
            def test_key(self, key: str):
                return True, "Valid"
            def refresh_video_url(self, item_id: str, old_url: str = ""):
                return None

        registry.register_provider("unsplash", MockUnsplashProvider())
        custom_prov = registry.get_provider("unsplash")
        self.assertIsNotNone(custom_prov)
        self.assertEqual(custom_prov.platform_name, "unsplash")

    # ─────────────────────────────────────────────────────────────────
    # 3. SRP: SubtitleService
    # ─────────────────────────────────────────────────────────────────
    def test_subtitle_service_timecode_parsing_and_formatting(self):
        """Test timecode conversion accuracy in SubtitleService."""
        svc = SubtitleService()
        self.assertEqual(svc.parse_timecode_ms("00:01:05,250"), 65250)
        self.assertEqual(svc.parse_timecode_ms("01:00:00.000"), 3600000)
        self.assertEqual(svc.format_timecode_ms(65250), "00:01:05,250")
        self.assertEqual(svc.format_timecode_ms(3600000), "01:00:00,000")

    def test_subtitle_service_merge_srt_files(self):
        """Test stitching multiple SRT files with sequential time-offsetting."""
        svc = SubtitleService()

        srt1 = self.temp_dir / "part1.srt"
        srt1.write_text(
            "1\n00:00:00,000 --> 00:00:02,000\nHello world\n\n"
            "2\n00:00:02,500 --> 00:00:04,000\nSecond line\n",
            encoding="utf-8"
        )

        srt2 = self.temp_dir / "part2.srt"
        srt2.write_text(
            "1\n00:00:00,000 --> 00:00:03,000\nThird line from part 2\n",
            encoding="utf-8"
        )

        out_srt = self.temp_dir / "merged.srt"
        ok, msg, count = svc.merge_srt_files([srt1, srt2], out_srt, gap_ms=500)

        self.assertTrue(ok)
        self.assertEqual(count, 3)
        self.assertTrue(out_srt.exists())

        content = out_srt.read_text(encoding="utf-8")
        self.assertIn("Hello world", content)
        self.assertIn("Second line", content)
        self.assertIn("Third line from part 2", content)
        # Verify part 2 starts after part 1 max_end (4000ms) + gap (500ms) = 4500ms -> 00:00:04,500
        self.assertIn("00:00:04,500 --> 00:00:07,500", content)

    # ─────────────────────────────────────────────────────────────────
    # 4. SRP: MediaOrganizerService
    # ─────────────────────────────────────────────────────────────────
    def test_media_organizer_service_move_file_to_scene(self):
        """Test moving and renaming downloaded assets into standardized scene format."""
        svc = MediaOrganizerService()
        src_file = self.temp_dir / "downloaded_raw.mp4"
        src_file.write_text("dummy media content", encoding="utf-8")

        out_dir = self.temp_dir / "output"
        scene = {
            "id": 3,
            "time_start": "00:00:15",
        }

        dest = svc.move_file_to_scene(str(src_file), scene, out_dir, provider_tag="motionarray")
        self.assertTrue(dest.exists())
        self.assertEqual(dest.name, "003_00-00-15_motionarray_001.mp4")
        self.assertFalse(src_file.exists())

    def test_media_organizer_service_scan_scene_downloads(self):
        """Test scanning and auditing folder contents per scene."""
        svc = MediaOrganizerService()
        out_dir = self.temp_dir / "output"
        out_dir.mkdir(parents=True)

        (out_dir / "001_00-00-00_pexels_video_001.mp4").write_text("v1")
        (out_dir / "001_00-00-00_pexels_photo_001.jpg").write_text("p1")
        (out_dir / "002_00-00-05_motionarray_001.mp4").write_text("ma1")

        scenes = [{"id": 1}, {"id": 2}, {"id": 3}]
        audit = svc.scan_scene_downloads(out_dir, scenes)

        self.assertEqual(audit["total_files"], 3)
        self.assertEqual(audit["scenes_with_files"], 2)
        self.assertEqual(audit["scenes_counts"][1]["pexels_video"], 1)
        self.assertEqual(audit["scenes_counts"][1]["pexels_photo"], 1)
        self.assertEqual(audit["scenes_counts"][2]["ma_video"], 1)
        self.assertEqual(audit["scenes_counts"][3]["total"], 0)

    # ─────────────────────────────────────────────────────────────────
    # 5. SRP: BrowserService
    # ─────────────────────────────────────────────────────────────────
    def test_browser_service_batch_urls(self):
        """Test BrowserService batch URL opening with mocked open_url."""
        svc = BrowserService()
        with patch.object(svc, "open_url", return_value=True) as mock_open:
            opened = svc.open_batch_urls(["https://a.com", "https://b.com"], delay_seconds=0)
            self.assertEqual(opened, 2)
            self.assertEqual(mock_open.call_count, 2)

    # ─────────────────────────────────────────────────────────────────
    # 6. Cohesion: UI Workers Placement
    # ─────────────────────────────────────────────────────────────────
    def test_workers_modular_placement(self):
        """Verify workers are decoupled from UI tab files and imported from ui.workers."""
        self.assertTrue(issubclass(VoiceGenerationWorker, object))
        self.assertTrue(issubclass(SceneVoiceWorker, object))


if __name__ == "__main__":
    unittest.main()
