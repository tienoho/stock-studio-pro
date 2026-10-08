"""
PartMerger service for validating and merging multi-part Claude script files.
"""

import re
import json
from pathlib import Path
from datetime import datetime
from typing import List, Tuple, Dict, Any, Optional
from ...core.exceptions import PartMergeError


class PartMerger:
    """Merges multiple part*.md or raw text JSON parts from Claude AI into a unified JSON."""

    JSON_PATTERN = re.compile(r'```json\s*(\{.*?\})\s*```', re.DOTALL)
    PART_FILE_PATTERN = re.compile(r'part(\d+)\.md$', re.IGNORECASE)

    @staticmethod
    def scan_folder(folder_path: str) -> List[Tuple[int, Path]]:
        folder = Path(folder_path)
        if not folder.exists() or not folder.is_dir():
            raise PartMergeError(f"Folder không tồn tại: {folder_path}")

        files = []
        for f in folder.iterdir():
            if not f.is_file():
                continue
            match = PartMerger.PART_FILE_PATTERN.search(f.name)
            if match:
                part_num = int(match.group(1))
                files.append((part_num, f))

        if not files:
            raise PartMergeError(
                f"Không tìm thấy file part*.md trong folder:\n{folder_path}\n\n"
                f"Đảm bảo files có tên: part1.md, part2.md, part3.md..."
            )

        files.sort(key=lambda x: x[0])
        part_nums = [p[0] for p in files]
        expected = list(range(1, max(part_nums) + 1))
        if part_nums != expected:
            missing = set(expected) - set(part_nums)
            raise PartMergeError(
                f"Part numbers không liên tiếp.\n"
                f"Tìm thấy: {part_nums}\n"
                f"Thiếu: {sorted(missing)}\n\n"
                f"Đảm bảo có đầy đủ part1.md, part2.md, ..."
            )

        return files

    @staticmethod
    def parse_part_file(filepath: Path) -> Dict[str, Any]:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            raise PartMergeError(f"Không đọc được file {filepath.name}: {e}")

        match = PartMerger.JSON_PATTERN.search(content)
        if not match:
            raise PartMergeError(
                f"File {filepath.name} không chứa JSON code block ```json ... ```"
            )

        json_text = match.group(1)
        try:
            return json.loads(json_text)
        except json.JSONDecodeError as e:
            raise PartMergeError(
                f"File {filepath.name} có JSON syntax error: {e.msg} (line {e.lineno})"
            )

    @staticmethod
    def validate_part(data: Dict[str, Any], filepath_or_label: Any, expected_part_number: Optional[int] = None) -> bool:
        name = getattr(filepath_or_label, "name", str(filepath_or_label))
        if "_part_metadata" not in data:
            raise PartMergeError(f"File {name} thiếu '_part_metadata'.")

        meta = data["_part_metadata"]
        required_meta = [
            "part_number", "total_parts", "first_scene_id",
            "last_scene_id", "first_timestamp", "last_timestamp"
        ]
        for field in required_meta:
            if field not in meta:
                raise PartMergeError(f"File {name} thiếu metadata: {field}")

        if expected_part_number is not None and meta["part_number"] != expected_part_number:
            raise PartMergeError(
                f"File {name} có part_number={meta['part_number']} nhưng gợi ý part{expected_part_number}."
            )

        scenes = data.get("scenes")
        if not isinstance(scenes, list) or len(scenes) == 0:
            raise PartMergeError(f"File {name}: 'scenes' phải là danh sách không rỗng.")

        first_id = scenes[0].get("id")
        last_id = scenes[-1].get("id")
        if first_id != meta["first_scene_id"]:
            raise PartMergeError(
                f"File {name}: scene đầu có id={first_id}, nhưng metadata báo first_scene_id={meta['first_scene_id']}"
            )
        if last_id != meta["last_scene_id"]:
            raise PartMergeError(
                f"File {name}: scene cuối có id={last_id}, nhưng metadata báo last_scene_id={meta['last_scene_id']}"
            )

        prev_end = None
        for scene in scenes:
            for req in ["id", "time_start", "time_end", "dialogue_es"]:
                if req not in scene:
                    raise PartMergeError(f"File {name}: scene #{scene.get('id', '?')} thiếu field '{req}'")

            if prev_end is not None and scene["time_start"] < prev_end:
                raise PartMergeError(
                    f"File {name}: scene #{scene['id']} timestamp đi ngược ({scene['time_start']} < {prev_end})"
                )
            prev_end = scene["time_end"]

        return True

    @staticmethod
    def validate_cross_parts(parts_data: List[Tuple[Dict[str, Any], Any]]) -> bool:
        total_parts_expected = None
        prev_last_scene_id = 0
        prev_last_timestamp = "00:00:00,000"

        for data, filepath in parts_data:
            meta = data["_part_metadata"]
            name = getattr(filepath, "name", str(filepath))

            if total_parts_expected is None:
                total_parts_expected = meta["total_parts"]
            elif meta["total_parts"] != total_parts_expected:
                raise PartMergeError(
                    f"Inconsistent total_parts: Part {meta['part_number']} ({name}) báo {meta['total_parts']} != {total_parts_expected}"
                )

            first_id = meta["first_scene_id"]
            expected_first = prev_last_scene_id + 1
            if first_id != expected_first:
                raise PartMergeError(
                    f"Scene IDs không liên tiếp! Part trước kết thúc scene #{prev_last_scene_id}, part {meta['part_number']} bắt đầu #{first_id}"
                )

            first_time = meta["first_timestamp"]
            if first_time < prev_last_timestamp:
                raise PartMergeError(
                    f"Timestamps không liên tiếp! Part trước kết thúc: {prev_last_timestamp}, part này bắt đầu: {first_time}"
                )

            prev_last_scene_id = meta["last_scene_id"]
            prev_last_timestamp = meta["last_timestamp"]

        if len(parts_data) != total_parts_expected:
            raise PartMergeError(
                f"Thiếu parts! Metadata báo total={total_parts_expected}, nhưng chỉ có {len(parts_data)}."
            )

        return True

    @staticmethod
    def merge(folder_path: str) -> Dict[str, Any]:
        files = PartMerger.scan_folder(folder_path)
        parts_data = []
        for part_num, filepath in files:
            data = PartMerger.parse_part_file(filepath)
            parts_data.append((data, filepath))

        for i, (data, filepath) in enumerate(parts_data):
            PartMerger.validate_part(data, filepath, expected_part_number=i + 1)

        PartMerger.validate_cross_parts(parts_data)
        return PartMerger._build_merged(parts_data, [f[1].name for f in files])

    @staticmethod
    def parse_part_text(text: str, part_label: str = "Part") -> Dict[str, Any]:
        text = text.strip()
        if not text:
            raise PartMergeError(f"{part_label}: nội dung trống")

        match = PartMerger.JSON_PATTERN.search(text)
        if match:
            json_text = match.group(1)
        else:
            first_brace = text.find('{')
            last_brace = text.rfind('}')
            if first_brace == -1 or last_brace == -1 or first_brace >= last_brace:
                raise PartMergeError(f"{part_label}: không tìm thấy JSON code block")
            json_text = text[first_brace:last_brace + 1]

        try:
            return json.loads(json_text)
        except json.JSONDecodeError as e:
            raise PartMergeError(f"{part_label}: JSON syntax error: {e.msg} (line {e.lineno})")

    @staticmethod
    def merge_from_texts(part_texts: List[Tuple[str, str]]) -> Dict[str, Any]:
        valid_inputs = [(label, text) for label, text in part_texts if text.strip()]
        if not valid_inputs:
            raise PartMergeError("Tất cả parts đều trống. Vui lòng dán ít nhất 1 part.")

        parts_data = []
        for label, text in valid_inputs:
            data = PartMerger.parse_part_text(text, label)
            fake_path = type('FakePath', (), {'name': label})()
            parts_data.append((data, fake_path))

        try:
            parts_data.sort(key=lambda pd: pd[0].get("_part_metadata", {}).get("part_number", 0))
        except Exception:
            pass

        for data, fake_path in parts_data:
            PartMerger.validate_part(data, fake_path, expected_part_number=None)

        PartMerger.validate_cross_parts(parts_data)
        labels = [fp.name for _, fp in parts_data]
        return PartMerger._build_merged(parts_data, labels)

    @staticmethod
    def _build_merged(parts_data: List[Tuple[Dict[str, Any], Any]], source_labels: List[str]) -> Dict[str, Any]:
        first_data = parts_data[0][0]
        all_scenes = []
        for data, _ in parts_data:
            all_scenes.extend(data["scenes"])

        for scene in all_scenes:
            scene.pop("_part_metadata", None)

        total_duration = sum(scene.get("duration_seconds", 0) for scene in all_scenes)

        return {
            "video_topic": first_data.get("video_topic", "Unknown"),
            "language_source": first_data.get("language_source", "es"),
            "language_metadata": first_data.get("language_metadata", "en+vi"),
            "total_scenes": len(all_scenes),
            "total_duration_seconds": round(total_duration, 2),
            "_merge_info": {
                "merged_at": datetime.now().isoformat(),
                "parts_count": len(parts_data),
                "source_files": source_labels
            },
            "scenes": all_scenes
        }
