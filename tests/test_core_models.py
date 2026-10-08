"""
Tests for domain models in src.core.models.
"""

import unittest
from src.core.models.media import MediaItem, MediaType, MediaSource
from src.core.models.scene import Scene, srt_time_to_seconds, format_duration, extract_scenes_from_json
from src.core.models.api_key import APIKey
from src.core.models.workflow import WorkflowNodeData, WorkflowEdgeData, WorkflowPreset


class TestMediaModel(unittest.TestCase):
    def test_media_item_creation(self):
        item = MediaItem(
            id="123",
            source=MediaSource.PEXELS.value,
            type=MediaType.VIDEO.value,
            download_url="https://example.com/video.mp4",
            thumbnail_url="https://example.com/thumb.jpg",
            title="Ocean Waves",
            duration=15.0,
            width=1920,
            height=1080
        )
        self.assertEqual(item.id, "123")
        self.assertEqual(item.source, "pexels")
        self.assertEqual(item.type, "video")
        self.assertEqual(item.key, "pexels_video_123")

        # Test dictionary conversion
        d = item.to_dict()
        self.assertEqual(d["id"], "123")
        self.assertEqual(d["source"], "pexels")
        self.assertEqual(d["type"], "video")

        # Test from_dict
        restored = MediaItem.from_dict(d)
        self.assertEqual(restored.id, item.id)
        self.assertEqual(restored.source, item.source)


class TestSceneModel(unittest.TestCase):
    def test_srt_time_to_seconds(self):
        self.assertEqual(srt_time_to_seconds("00:00:05,000"), 5.0)
        self.assertEqual(srt_time_to_seconds("00:01:30,500"), 90.5)
        self.assertEqual(srt_time_to_seconds("01:00:00,000"), 3600.0)
        self.assertEqual(srt_time_to_seconds("invalid"), 0.0)

    def test_format_duration(self):
        self.assertEqual(format_duration(5), "0:05")
        self.assertEqual(format_duration(90), "1:30")
        self.assertEqual(format_duration(3605), "60:05")
        self.assertEqual(format_duration("14.5"), "0:14")
        self.assertEqual(format_duration("90"), "1:30")
        self.assertEqual(format_duration(0), "?")
        self.assertEqual(format_duration("0"), "?")
        self.assertEqual(format_duration(None), "?")
        self.assertEqual(format_duration("invalid"), "?")
        self.assertEqual(format_duration(-10), "?")

    def test_extract_scenes_from_json(self):
        raw_data = {
            "scenes": [
                {
                    "id": 1,
                    "time_start": "00:00:00,000",
                    "time_end": "00:00:05,000",
                    "primary_keywords": ["wave", "ocean"]
                },
                {
                    "id": 2,
                    "time_start": "00:00:05,000",
                    "time_end": "00:00:10,000",
                    "primary_keywords": ["beach", "sand"]
                }
            ]
        }
        scenes = extract_scenes_from_json(raw_data)
        self.assertEqual(len(scenes), 2)
        self.assertEqual(scenes[0]["id"], 1)
        self.assertEqual(scenes[1]["id"], 2)


class TestAPIKeyModel(unittest.TestCase):
    def test_api_key_limits(self):
        key = APIKey(name="Test Key", key="secret_123", platform="pexels")
        self.assertTrue(key.can_use())
        key.record_request()
        self.assertEqual(key.total_requests, 1)
        self.assertTrue(key.can_use())

        # Test dictionary export
        d = key.to_dict()
        self.assertEqual(d["name"], "Test Key")
        self.assertEqual(d["key"], "secret_123")


class TestWorkflowModels(unittest.TestCase):
    def test_workflow_node_and_edge(self):
        node = WorkflowNodeData(id=1, title="Search stock", x=100.0, y=150.0, config={"source": "Pexels"})
        edge = WorkflowEdgeData(source_id=1, target_id=2)
        preset = WorkflowPreset(nodes=[node], edges=[edge])

        self.assertEqual(len(preset.nodes), 1)
        self.assertEqual(preset.nodes[0].title, "Search stock")
        self.assertEqual(preset.edges[0].source_id, 1)


if __name__ == "__main__":
    unittest.main()
