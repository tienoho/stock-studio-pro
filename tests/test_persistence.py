"""
Tests for persistence repositories in src.infrastructure.persistence.
Covers JSON, Pickle, and Production SQLite repositories.
"""

import json
import pickle
import tempfile
import unittest
from pathlib import Path

from src.infrastructure.persistence.json_config_repo import JsonConfigRepository, obfuscate, deobfuscate
from src.infrastructure.persistence.pickle_state_repo import PickleStateRepository
from src.infrastructure.persistence.sqlite_db import SqliteDatabase
from src.infrastructure.persistence.sqlite_config_repo import SqliteConfigRepository
from src.infrastructure.persistence.sqlite_state_repo import SqliteStateRepository
from src.infrastructure.persistence.sqlite_workflow_repo import SqliteWorkflowRepository
from src.infrastructure.persistence.sqlite_downloads_repo import SqliteDownloadsRepository


class TestPersistence(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_file = Path(self.temp_dir.name) / "config.json"
        self.state_file = Path(self.temp_dir.name) / "state.pkl"
        self.db_file = Path(self.temp_dir.name) / "test_studio.db"
        self.db = None

    def tearDown(self):
        if self.db:
            try:
                self.db.close()
            except Exception:
                pass
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_obfuscation(self):
        secret = "secret_api_key_456"
        encoded = obfuscate(secret)
        self.assertNotEqual(secret, encoded)
        decoded = deobfuscate(encoded)
        self.assertEqual(secret, decoded)

    def test_json_config_repo_save_and_load(self):
        repo = JsonConfigRepository(self.config_file)
        config = {
            "pexels_keys": [{"name": "Key 1", "key": "my_pexels_key"}],
            "output_dir": "D:\\Test\\Output"
        }
        repo.save(config)

        # Check raw file contains obfuscated key
        raw_text = self.config_file.read_text(encoding="utf-8")
        self.assertNotIn("my_pexels_key", raw_text)

        # Load back via repo should decode it
        loaded = repo.load()
        self.assertEqual(loaded["output_dir"], "D:\\Test\\Output")
        self.assertEqual(loaded["pexels_keys"][0]["key"], "my_pexels_key")

    def test_pickle_state_repo_save_and_load(self):
        repo = PickleStateRepository(self.state_file)
        state = {
            "current_scene_id": 42,
            "scenes": [{"id": 42, "title": "Test"}]
        }
        repo.save(state)
        self.assertTrue(self.state_file.exists())

        loaded = repo.load()
        self.assertEqual(loaded["current_scene_id"], 42)
        self.assertEqual(len(loaded["scenes"]), 1)

        repo.reset()
        self.assertFalse(self.state_file.exists())
        self.assertIsNone(repo.load())

    # ═══════════════════════════════════════════════════════════════
    # SQLITE TESTS
    # ═══════════════════════════════════════════════════════════════

    def test_sqlite_db_init(self):
        self.db = SqliteDatabase(self.db_file)
        conn = self.db.get_connection()
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = {row["name"] for row in cur.fetchall()}
        self.assertIn("app_config", tables)
        self.assertIn("api_keys", tables)
        self.assertIn("scenes", tables)
        self.assertIn("media_items", tables)
        self.assertIn("workflow_presets", tables)

    def test_sqlite_config_repo_crud_and_obfuscation(self):
        self.db = SqliteDatabase(self.db_file)
        repo = SqliteConfigRepository(db=self.db)

        # Direct add API key
        key_id = repo.add_api_key("pexels", "Pexels Primary", "pex_secret_key_999", is_active=True)
        self.assertGreater(key_id, 0)

        # Check raw SQLite table stores obfuscated key
        conn = self.db.get_connection()
        cur = conn.cursor()
        cur.execute("SELECT key FROM api_keys WHERE id = ?;", (key_id,))
        raw_in_db = cur.fetchone()["key"]
        self.assertNotEqual(raw_in_db, "pex_secret_key_999")

        # Get keys list for UI
        keys = repo.get_api_keys("pexels")
        self.assertEqual(len(keys), 1)
        self.assertEqual(keys[0]["name"], "Pexels Primary")
        self.assertEqual(keys[0]["key"], "pex_secret_key_999")
        self.assertTrue(keys[0]["is_active"])

        # Toggle key
        repo.toggle_api_key(key_id, False)
        keys_after_toggle = repo.get_api_keys("pexels")
        self.assertFalse(keys_after_toggle[0]["is_active"])

        # Inactive key should not appear in load_config() active list
        cfg = repo.load_config()
        self.assertEqual(len(cfg["pexels_keys"]), 0)

        # Toggle back to active
        repo.toggle_api_key(key_id, True)
        cfg = repo.load_config()
        self.assertEqual(len(cfg["pexels_keys"]), 1)
        self.assertEqual(cfg["pexels_keys"][0]["key"], "pex_secret_key_999")

        # Delete key
        repo.delete_api_key(key_id)
        self.assertEqual(len(repo.get_api_keys("pexels")), 0)

    def test_sqlite_config_repo_save_and_sync(self):
        self.db = SqliteDatabase(self.db_file)
        repo = SqliteConfigRepository(db=self.db)

        config_data = {
            "output_dir": "D:\\MyOutputDir",
            "search_prefs": {"photos": True, "videos": False, "source": "Chỉ Pexels"},
            "pixabay_keys": [{"name": "Pix 1", "key": "pix_abc_123"}],
        }
        repo.save_config(config_data)

        loaded = repo.load_config()
        self.assertEqual(loaded["output_dir"], "D:\\MyOutputDir")
        self.assertEqual(loaded["search_prefs"]["source"], "Chỉ Pexels")
        self.assertEqual(len(loaded["pixabay_keys"]), 1)
        self.assertEqual(loaded["pixabay_keys"][0]["key"], "pix_abc_123")

    def test_sqlite_config_auto_migration(self):
        # Create legacy JSON file
        legacy_json = Path(self.temp_dir.name) / "legacy_config.json"
        legacy_data = {
            "output_dir": "D:\\LegacyOutput",
            "pexels_keys": [{"name": "Old Pexels", "key": obfuscate("old_pex_key")}],
            "pixabay_keys": [{"name": "Old Pixabay", "key": obfuscate("old_pix_key")}],
        }
        legacy_json.write_text(json.dumps(legacy_data), encoding="utf-8")

        self.db = SqliteDatabase(self.db_file)
        repo = SqliteConfigRepository(db=self.db, legacy_json_path=legacy_json)
        loaded = repo.load_config()

        self.assertEqual(loaded["output_dir"], "D:\\LegacyOutput")
        self.assertEqual(len(loaded["pexels_keys"]), 1)
        self.assertEqual(loaded["pexels_keys"][0]["key"], "old_pex_key")
        self.assertEqual(len(loaded["pixabay_keys"]), 1)
        self.assertEqual(loaded["pixabay_keys"][0]["key"], "old_pix_key")

    def test_sqlite_state_repo_save_load_reset(self):
        self.db = SqliteDatabase(self.db_file)
        repo = SqliteStateRepository(db=self.db)

        state_data = {
            "current_scene_id": 101,
            "json_data": {"title": "Production Test"},
            "scenes": [
                {
                    "id": 101,
                    "time_start": "00:00",
                    "time_end": "00:05",
                    "duration_seconds": 5.0,
                    "description_vi": "Cảnh hoàng hôn tuyệt đẹp",
                    "dialogue_es": "Hermoso atardecer",
                    "primary_keywords": ["sunset", "sky"],
                    "secondary_keywords": ["clouds"],
                    "mood": "calm",
                    "shot_type": "wide",
                }
            ],
            "scene_items": {
                101: [
                    {
                        "id": "item_999",
                        "source": "pexels",
                        "type": "video",
                        "download_url": "https://example.com/video.mp4",
                        "thumb_url": "https://example.com/thumb.jpg",
                        "width": 1920,
                        "height": 1080,
                        "duration": 15,
                        "author": "John Doe",
                        "author_url": "https://example.com/author",
                        "page_url": "https://example.com/page",
                        "search_query": "sunset",
                    }
                ]
            },
            "selected_items": {
                101: {
                    "pexels_video_item_999": {
                        "id": "item_999",
                        "source": "pexels",
                        "type": "video"
                    }
                }
            }
        }

        repo.save_state(state_data)

        loaded = repo.load_state()
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["current_scene_id"], 101)
        self.assertEqual(loaded["json_data"]["title"], "Production Test")
        self.assertEqual(len(loaded["scenes"]), 1)
        self.assertEqual(loaded["scenes"][0]["description_vi"], "Cảnh hoàng hôn tuyệt đẹp")
        self.assertEqual(loaded["scenes"][0]["primary_keywords"], ["sunset", "sky"])

        # Check media items and selection
        items = loaded["scene_items"].get(101, [])
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["id"], "item_999")
        self.assertEqual(items[0]["author"], "John Doe")

        selected = loaded["selected_items"].get(101, {})
        self.assertIn("pexels_video_item_999", selected)

        # Test reset
        repo.reset()
        self.assertIsNone(repo.load_state())

    def test_sqlite_state_auto_migration(self):
        # Create legacy pickle file
        legacy_pkl = Path(self.temp_dir.name) / "legacy_state.pkl"
        legacy_data = {
            "current_scene_id": 7,
            "scenes": [{"id": 7, "description_vi": "Legacy Scene"}],
            "scene_items": {7: []},
            "selected_items": {7: {}},
        }
        with open(legacy_pkl, "wb") as f:
            pickle.dump(legacy_data, f)

        self.db = SqliteDatabase(self.db_file)
        repo = SqliteStateRepository(db=self.db, legacy_pickle_path=legacy_pkl)
        loaded = repo.load_state()

    def test_sqlite_cross_scene_media_isolation(self):
        self.db = SqliteDatabase(self.db_file)
        repo = SqliteStateRepository(db=self.db)

        # Identical media item found in two separate scenes
        common_item = {
            "id": "shared_vid_123",
            "source": "pexels",
            "type": "video",
            "download_url": "https://example.com/v.mp4"
        }
        state = {
            "current_scene_id": 1,
            "scenes": [
                {"id": 1, "description_vi": "Scene 1"},
                {"id": 2, "description_vi": "Scene 2"}
            ],
            "scene_items": {
                1: [common_item],
                2: [common_item]
            },
            "selected_items": {
                1: {"pexels_video_shared_vid_123": common_item},
                2: {}  # Not selected in scene 2
            }
        }
        repo.save_state(state)
        loaded = repo.load_state()

        self.assertEqual(len(loaded["scene_items"][1]), 1)
        self.assertEqual(len(loaded["scene_items"][2]), 1)
        self.assertIn("pexels_video_shared_vid_123", loaded["selected_items"][1])
        self.assertNotIn("pexels_video_shared_vid_123", loaded["selected_items"][2])

    def test_sqlite_key_usage_tracking(self):
        self.db = SqliteDatabase(self.db_file)
        repo = SqliteConfigRepository(db=self.db)

        key_id = repo.add_api_key("pexels", "Tracked Key", "tracked_secret_123")
        keys = repo.get_api_keys("pexels")
        self.assertIsNone(keys[0]["last_used"])

        # Record activity
        repo.record_key_usage("pexels", "tracked_secret_123")
        keys_after = repo.get_api_keys("pexels")
        self.assertIsNotNone(keys_after[0]["last_used"])

    def test_sqlite_arbitrary_config_settings(self):
        self.db = SqliteDatabase(self.db_file)
        repo = SqliteConfigRepository(db=self.db)

        config = {
            "output_dir": "D:\\TestOut",
            "voice_speed": 1.25,
            "auto_pipeline_options": {"retry_count": 3, "notify": True}
        }
        repo.save(config)
        loaded = repo.load()

        self.assertEqual(loaded["output_dir"], "D:\\TestOut")
        self.assertEqual(loaded["voice_speed"], 1.25)
        self.assertEqual(loaded["auto_pipeline_options"]["retry_count"], 3)

    def test_sqlite_live_backup_and_stats(self):
        self.db = SqliteDatabase(self.db_file)
        repo = SqliteConfigRepository(db=self.db)
        repo.add_api_key("pexels", "Backup Test Key", "sec_123")

        backup_file = Path(self.temp_dir.name) / "live_backup.db"
        ok = self.db.backup_database(backup_file)
        self.assertTrue(ok)
        self.assertTrue(backup_file.exists())

        # Verify backup contains the key
        backup_db = SqliteDatabase(backup_file)
        try:
            backup_repo = SqliteConfigRepository(db=backup_db)
            keys = backup_repo.get_api_keys("pexels")
            self.assertEqual(len(keys), 1)
            self.assertEqual(keys[0]["name"], "Backup Test Key")
        finally:
            backup_db.close()

        # Verify stats
        stats = self.db.get_database_stats()
        self.assertIn("table_counts", stats)
        self.assertGreaterEqual(stats["table_counts"]["api_keys"], 1)

    def test_sqlite_workflow_presets_repo(self):
        self.db = SqliteDatabase(self.db_file)
        wf_repo = SqliteWorkflowRepository(db=self.db)

        preset_data = {
            "nodes": [
                {"type": "Load JSON", "x": 100, "y": 150},
                {"type": "Search stock", "x": 300, "y": 150}
            ]
        }
        ok = wf_repo.save_preset("Full Pipeline Pro", preset_data)
        self.assertTrue(ok)

        names = wf_repo.list_presets()
        self.assertIn("Full Pipeline Pro", names)

        loaded = wf_repo.get_preset("Full Pipeline Pro")
        self.assertIsNotNone(loaded)
        self.assertEqual(len(loaded["nodes"]), 2)

        deleted = wf_repo.delete_preset("Full Pipeline Pro")
        self.assertTrue(deleted)
        self.assertNotIn("Full Pipeline Pro", wf_repo.list_presets())

    def test_sqlite_downloads_history_repo(self):
        self.db = SqliteDatabase(self.db_file)
        dl_repo = SqliteDownloadsRepository(db=self.db)

        item_key = "pexels_video_555"
        self.assertFalse(dl_repo.is_downloaded(item_key))

        ok = dl_repo.record_download(
            item_key=item_key,
            scene_id="1",
            source="pexels",
            media_type="video",
            item_id="555",
            filepath="D:\\Output\\scene1_01.mp4",
            filesize=1048576,
            status="completed"
        )
        self.assertTrue(ok)
        self.assertTrue(dl_repo.is_downloaded(item_key))

        info = dl_repo.get_download_info(item_key)
        self.assertIsNotNone(info)
        self.assertEqual(info["filepath"], "D:\\Output\\scene1_01.mp4")
        self.assertEqual(info["filesize"], 1048576)

        history = dl_repo.get_history(limit=10)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["item_key"], item_key)

        dl_repo.clear_history()
        self.assertFalse(dl_repo.is_downloaded(item_key))


if __name__ == "__main__":
    unittest.main()
