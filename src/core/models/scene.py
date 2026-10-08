"""
Scene models representing storyboard and script scenes.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import re


@dataclass
class Scene:
    """Represents a script scene."""
    id: str
    time_start: str = ""
    time_end: str = ""
    duration_seconds: float = 0.0
    dialogue: str = ""
    primary_keywords: List[str] = field(default_factory=list)
    secondary_keywords: List[str] = field(default_factory=list)
    extra_data: Dict[str, Any] = field(default_factory=dict)

    @property
    def all_keywords(self) -> List[str]:
        return [k for k in self.primary_keywords + self.secondary_keywords if k]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict matching existing expectations."""
        return {
            "id": self.id,
            "time_start": self.time_start,
            "time_end": self.time_end,
            "duration_seconds": self.duration_seconds,
            "dialogue_es": self.dialogue,
            "primary_keywords": self.primary_keywords,
            "secondary_keywords": self.secondary_keywords,
            **self.extra_data,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Scene":
        scene_id = str(data.get("id") or data.get("segment_id") or "")
        time_start = str(data.get("time_start", ""))
        time_end = str(data.get("time_end", ""))
        duration = float(data.get("duration_seconds") or 0.0)
        dialogue = str(data.get("dialogue_es") or data.get("dialogue") or data.get("text") or "")
        primary_kws = [str(k) for k in data.get("primary_keywords", []) if k]
        secondary_kws = [str(k) for k in data.get("secondary_keywords", []) if k]

        extra = {k: v for k, v in data.items() if k not in {
            "id", "segment_id", "time_start", "time_end", "duration_seconds",
            "dialogue_es", "dialogue", "text", "primary_keywords", "secondary_keywords"
        }}

        return cls(
            id=scene_id,
            time_start=time_start,
            time_end=time_end,
            duration_seconds=duration,
            dialogue=dialogue,
            primary_keywords=primary_kws,
            secondary_keywords=secondary_kws,
            extra_data=extra,
        )


def srt_time_to_seconds(value: str) -> float:
    """Parse timestamp (HH:MM:SS,mmm or HH:MM:SS.mmm or MM:SS,mmm) to seconds."""
    val = str(value).strip().replace(',', '.')
    m = re.match(r"^(\d+):(\d{2}):(\d{2})(?:\.(\d+))?$", val)
    if m:
        h, mi, sec = int(m.group(1)), int(m.group(2)), int(m.group(3))
        ms_str = m.group(4) or "0"
        ms_val = float(f"0.{ms_str}") if ms_str else 0.0
        return h * 3600 + mi * 60 + sec + ms_val
    m2 = re.match(r"^(\d+):(\d{2})(?:\.(\d+))?$", val)
    if m2:
        mi, sec = int(m2.group(1)), int(m2.group(2))
        ms_str = m2.group(3) or "0"
        ms_val = float(f"0.{ms_str}") if ms_str else 0.0
        return mi * 60 + sec + ms_val
    return 0.0



def format_duration(seconds: float) -> str:
    """Format seconds into M:SS."""
    if not seconds:
        return "?"
    m = int(seconds) // 60
    s = int(seconds) % 60
    return f"{m}:{s:02d}"


def extract_scenes_from_json(data: Any) -> List[Dict[str, Any]]:
    """Extract list of scene dictionaries from structured or partial JSON."""
    scenes = []
    if not isinstance(data, dict):
        return scenes

    try:
        if "scenes" in data and isinstance(data["scenes"], list):
            scenes.extend(data["scenes"])
        if "part_a_scenes" in data and isinstance(data["part_a_scenes"], list):
            scenes.extend(data["part_a_scenes"])
        if "part_b_segments" in data and isinstance(data["part_b_segments"], list):
            for seg in data["part_b_segments"]:
                if not isinstance(seg, dict):
                    continue
                seg_id = seg.get("id") or seg.get("segment_id") or len(scenes) + 1
                keywords = seg.get("keywords") or []
                scenes.append({
                    "id": f"seg_{seg_id}",
                    "time_start": seg.get("time_start", ""),
                    "time_end": seg.get("time_end", ""),
                    "duration_seconds": seg.get("duration_seconds", 0),
                    "dialogue_es": seg.get("dialogue_es_excerpt", ""),
                    "primary_keywords": keywords[:5],
                    "secondary_keywords": keywords[5:],
                    "_is_segment": True,
                    "_segment_topic": seg.get("segment_topic", ""),
                })
    except Exception as e:
        print(f"[extract_scenes] Error: {type(e).__name__}: {e}")

    return scenes
