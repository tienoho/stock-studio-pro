"""
Regression tests verifying fixes for identified bugs across domain, services, and persistence layers.
"""

import unittest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

from src.infrastructure.media.ffmpeg_processor import FFmpegProcessor
from src.application.services.video_cut_service import VideoCutService
from src.infrastructure.providers.vecteezy_provider import VecteezyProvider
from src.infrastructure.persistence.sqlite_db import SqliteDatabase
from src.infrastructure.persistence.sqlite_config_repo import SqliteConfigRepository
from src.infrastructure.persistence.sqlite_state_repo import SqliteStateRepository
from src.application.services.smart_downloader import SmartDownloader


class TestBugFixes(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_fixes.db"
        self.db = SqliteDatabase(self.db_path)

    def tearDown(self):
        self.db.close()
        self.temp_dir.cleanup()

    def test_ffmpeg_processor_empty_concat_clips_guard(self):
        """Verifies concat_clips gracefully returns False on empty clips list without error."""
        processor = FFmpegProcessor()
        ok, msg = processor.concat_clips([], Path(self.temp_dir.name) / "out.mp4")
        self.assertFalse(ok)
        self.assertIn("rỗng", msg)

    def test_video_cut_service_folder_filtering(self):
        """Verifies get_target_folders ignores 'Canh' and 'Cảnh' directories case-insensitively."""
        root = Path(self.temp_dir.name) / "video_root"
        root.mkdir()
        canh_dir = root / "Canh"
        canh_dir.mkdir()
        (canh_dir / "vid.mp4").touch()
        canh_accent_dir = root / "Cảnh"
        canh_accent_dir.mkdir()
        (canh_accent_dir / "vid.mp4").touch()
        scene1 = root / "1"
        scene1.mkdir()
        (scene1 / "scene_vid.mp4").touch()

        service = VideoCutService()
        folders = service.get_target_folders(root)
        self.assertEqual(len(folders), 1)
        self.assertEqual(folders[0].name, "1")

    def test_vecteezy_provider_null_key_download_url(self):
        """Verifies VecteezyProvider._download_url handles None key without AttributeError."""
        provider = VecteezyProvider()
        # With key=None, it should not raise AttributeError on key.record_request()
        url = provider._download_url("12345", "video", None)
        self.assertEqual(url, "")

    def test_sqlite_config_repo_preserves_inactive_keys_on_save(self):
        """
        Verifies that deactivating an API key and subsequently saving general
        configuration settings does NOT permanently delete the inactive key.
        """
        repo = SqliteConfigRepository(db=self.db)
        key_id = repo.add_api_key("pexels", "Pexels Sec", "my_secret_key_123", is_active=True)

        # Deactivate key
        repo.toggle_api_key(key_id, False)
        keys_before = repo.get_api_keys("pexels")
        self.assertEqual(len(keys_before), 1)
        self.assertFalse(keys_before[0]["is_active"])

        # General config save (e.g. changing output directory or auto-save)
        repo.save_config({"output_dir": "D:\\NewDir"})

        # Inactive key must still exist in SQLite database!
        keys_after = repo.get_api_keys("pexels")
        self.assertEqual(len(keys_after), 1)
        self.assertEqual(keys_after[0]["name"], "Pexels Sec")
        self.assertFalse(keys_after[0]["is_active"])

    def test_sqlite_state_repo_handles_duplicate_or_empty_scene_ids(self):
        """Verifies SqliteStateRepository.save safely handles empty or duplicate scene IDs."""
        repo = SqliteStateRepository(db=self.db)
        state = {
            "scenes": [
                {"id": "", "dialogue": "Scene without id"},
                {"id": "duplicate_id", "dialogue": "Scene A"},
                {"id": "duplicate_id", "dialogue": "Scene B"},
                {"id": 4, "dialogue": "Scene 4"},
            ],
            "scene_items": {},
            "selected_items": {},
            "current_scene_id": "duplicate_id"
        }
        # Should not raise sqlite3.IntegrityError
        repo.save(state)

        loaded = repo.load()
        self.assertIsNotNone(loaded)
        self.assertEqual(len(loaded["scenes"]), 4)
        loaded_ids = [s["id"] for s in loaded["scenes"]]
        self.assertEqual(len(set(loaded_ids)), 4)  # All 4 unique

    def test_smart_downloader_refresh_url_without_query(self):
        """Verifies SmartDownloader attempts video URL refresh even if query is empty."""
        mock_provider = MagicMock()
        mock_provider.refresh_video_url.return_value = "https://example.com/fresh.mp4"

        downloader = SmartDownloader(providers={"pexels": mock_provider})
        downloader._try_download = MagicMock(side_effect=[
            (False, "403 Forbidden", "forbidden"),  # 1st attempt
            (True, "", "success"),                  # 2nd attempt with fresh url
        ])

        item = {
            "id": 999,
            "source": "pexels",
            "type": "video",
            "download_url": "https://example.com/expired.mp4",
            "search_query": ""  # Query is intentionally empty
        }

        success, err, err_type = downloader.download(item, Path(self.temp_dir.name) / "test.mp4")
        self.assertTrue(success)
        self.assertEqual(err_type, "success_after_refresh")
        mock_provider.refresh_video_url.assert_called_once_with("999", "https://example.com/expired.mp4")

    def test_workflow_node_config_dialog_scene_voice_match(self):
        """Verifies WorkflowNodeConfigDialog does not raise TypeError with float bounds for QSpinBox."""
        from PyQt6.QtWidgets import QApplication
        from src.ui.workflow.canvas import WorkflowNodeItem, WorkflowNodeConfigDialog
        app = QApplication.instance()
        if app is None:
            app = QApplication(["test", "-platform", "offscreen"])

        node = WorkflowNodeItem("1", "Scene voice match")
        dialog = WorkflowNodeConfigDialog(node)
        self.assertIsNotNone(dialog)
        title, config = dialog.values()
        self.assertEqual(title, "Scene voice match")
        dialog.close()

    def test_key_manager_filters_inactive_keys(self):
        """Verifies KeyManager does not include deactivated API keys in rotation."""
        from src.application.services.key_manager import KeyManager
        pexels_keys = [
            {"key": "active_key_1", "is_active": 1, "name": "Key 1"},
            {"key": "inactive_key_2", "is_active": 0, "name": "Key 2"},
            {"key": "inactive_key_3", "is_active": False, "name": "Key 3"},
            {"key": "active_key_4", "is_active": True, "name": "Key 4"},
        ]
        km = KeyManager(pexels_keys=pexels_keys, pixabay_keys=[])
        self.assertEqual(len(km.pexels_keys), 2)
        keys_in_pool = [k.key for k in km.pexels_keys]
        self.assertIn("active_key_1", keys_in_pool)
        self.assertIn("active_key_4", keys_in_pool)
        self.assertNotIn("inactive_key_2", keys_in_pool)
        self.assertNotIn("inactive_key_3", keys_in_pool)

    def test_srt_time_to_seconds_broad_formats(self):
        """Verifies srt_time_to_seconds supports dot separators, variable precision, and MM:SS."""
        from src.core.models.scene import srt_time_to_seconds
        self.assertEqual(srt_time_to_seconds("00:01:30.500"), 90.5)
        self.assertEqual(srt_time_to_seconds("1:05:00,250"), 3900.25)
        self.assertEqual(srt_time_to_seconds("05:30.5"), 330.5)
        self.assertEqual(srt_time_to_seconds("00:02:15"), 135.0)

    def test_download_worker_sanitizes_windows_filenames(self):
        """Verifies DownloadWorker correctly strips illegal Windows characters from scene_id."""
        import re
        illegal_scene_ids = ["Scene 01: Intro", "1/2", '3"Special', "4*Star", "5<Test>"]
        for sid in illegal_scene_ids:
            clean_sid = re.sub(r'[\\/*?:"<>|]', '_', str(sid).strip())
            scene_name = clean_sid.lstrip("0") or "0"
            self.assertFalse(any(c in scene_name for c in '\\/*?:"<>|'))


if __name__ == "__main__":
    unittest.main()

