"""
Tests for PartMerger service in src.application.services.part_merger.
"""

import json
import unittest
from src.core.exceptions import PartMergeError
from src.application.services.part_merger import PartMerger


class TestPartMerger(unittest.TestCase):
    def setUp(self):
        self.part1_dict = {
            "_part_metadata": {
                "part_number": 1,
                "total_parts": 2,
                "first_scene_id": 1,
                "last_scene_id": 2,
                "first_timestamp": "00:00:00,000",
                "last_timestamp": "00:00:10,000"
            },
            "video_topic": "Nature Documentary",
            "scenes": [
                {
                    "id": 1,
                    "time_start": "00:00:00,000",
                    "time_end": "00:00:05,000",
                    "dialogue_es": "En el bosque profundo",
                    "duration_seconds": 5.0
                },
                {
                    "id": 2,
                    "time_start": "00:00:05,000",
                    "time_end": "00:00:10,000",
                    "dialogue_es": "Los animales despiertan",
                    "duration_seconds": 5.0
                }
            ]
        }

        self.part2_dict = {
            "_part_metadata": {
                "part_number": 2,
                "total_parts": 2,
                "first_scene_id": 3,
                "last_scene_id": 4,
                "first_timestamp": "00:00:10,000",
                "last_timestamp": "00:00:20,000"
            },
            "video_topic": "Nature Documentary",
            "scenes": [
                {
                    "id": 3,
                    "time_start": "00:00:10,000",
                    "time_end": "00:00:15,000",
                    "dialogue_es": "El sol brilla arriba",
                    "duration_seconds": 5.0
                },
                {
                    "id": 4,
                    "time_start": "00:00:15,000",
                    "time_end": "00:00:20,000",
                    "dialogue_es": "Un nuevo día comienza",
                    "duration_seconds": 5.0
                }
            ]
        }

    def test_merge_from_texts_success(self):
        texts = [
            ("part1.md", f"```json\n{json.dumps(self.part1_dict)}\n```"),
            ("part2.md", f"```json\n{json.dumps(self.part2_dict)}\n```"),
        ]
        merged = PartMerger.merge_from_texts(texts)
        self.assertEqual(merged["total_scenes"], 4)
        self.assertEqual(merged["total_duration_seconds"], 20.0)
        self.assertEqual(merged["video_topic"], "Nature Documentary")
        self.assertEqual(len(merged["scenes"]), 4)

    def test_missing_metadata_raises_error(self):
        invalid_dict = {"scenes": [{"id": 1, "time_start": "00:00:00,000", "time_end": "00:00:05,000", "dialogue_es": "abc"}]}
        texts = [("part1.md", json.dumps(invalid_dict))]
        with self.assertRaises(PartMergeError):
            PartMerger.merge_from_texts(texts)

    def test_empty_parts_raises_error(self):
        texts = [("part1.md", "   "), ("part2.md", "")]
        with self.assertRaises(PartMergeError):
            PartMerger.merge_from_texts(texts)

    def test_discontinuous_scene_id_raises_error(self):
        # Part 2 begins with scene 5 instead of 3
        bad_part2 = dict(self.part2_dict)
        bad_part2["_part_metadata"] = dict(self.part2_dict["_part_metadata"])
        bad_part2["_part_metadata"]["first_scene_id"] = 5
        bad_part2["_part_metadata"]["last_scene_id"] = 6
        bad_part2["scenes"] = [
            {"id": 5, "time_start": "00:00:10,000", "time_end": "00:00:15,000", "dialogue_es": "x"},
            {"id": 6, "time_start": "00:00:15,000", "time_end": "00:00:20,000", "dialogue_es": "y"},
        ]
        texts = [
            ("part1.md", json.dumps(self.part1_dict)),
            ("part2.md", json.dumps(bad_part2)),
        ]
        with self.assertRaises(PartMergeError):
            PartMerger.merge_from_texts(texts)


if __name__ == "__main__":
    unittest.main()
