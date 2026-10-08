"""
Media Organizer Service managing downloaded file placement, renaming, and directory scanning.
Decouples file system operations from the UI presentation layer.
"""

import os
import re
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple


class MediaOrganizerService:
    """Application service for moving, renaming, and auditing downloaded scene media files."""

    VIDEO_EXTENSIONS = ('.mp4', '.mov', '.webm', '.mkv', '.avi')
    PHOTO_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.webp', '.bmp')

    def move_file_to_scene(
        self,
        src_path: str,
        scene: Dict[str, Any],
        output_dir: Path,
        provider_tag: str = "motionarray"
    ) -> Path:
        """
        Moves and standardizes the filename of a downloaded asset to belong to a specific scene.
        Format: {scene_id:03d}_{timestamp_start}_{provider_tag}_{sequence:03d}.ext
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        scene_id = scene.get("id", 1)
        scene_id_str = str(scene_id).zfill(3) if isinstance(scene_id, int) or str(scene_id).isdigit() else str(scene_id)

        ts_start = scene.get("timestamp_start") or scene.get("time_start") or "00-00-00"
        ts_safe = str(ts_start).replace(":", "-").replace(",", "-").replace(".", "-")
        scene_prefix = f"{scene_id_str}_{ts_safe}"

        src = Path(src_path)
        ext = src.suffix.lower()

        existing = list(output_dir.glob(f"{scene_prefix}_{provider_tag}_*"))
        next_num = len(existing) + 1
        dest_path = output_dir / f"{scene_prefix}_{provider_tag}_{next_num:03d}{ext}"

        while dest_path.exists():
            next_num += 1
            dest_path = output_dir / f"{scene_prefix}_{provider_tag}_{next_num:03d}{ext}"

        shutil.move(str(src), str(dest_path))
        return dest_path

    def scan_scene_downloads(
        self,
        output_dir: Path,
        scenes: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Scans output folder and tallies downloaded video, photo, and provider-specific files per scene.
        Returns a dictionary mapping scene_id to file counts and overall totals.
        """
        scene_counts: Dict[Any, Dict[str, Any]] = {}
        for scene in scenes:
            sid = scene.get("id")
            if sid is None:
                continue
            scene_counts[sid] = {
                'pexels_video': 0,
                'pexels_photo': 0,
                'ma_video': 0,
                'other': 0,
                'scene': scene,
                'total': 0,
            }

        if not output_dir.exists():
            return {
                "scenes_counts": scene_counts,
                "scenes_with_files": 0,
                "total_files": 0,
                "total_scenes": len(scenes)
            }

        for f in output_dir.iterdir():
            if not f.is_file() or f.name.startswith("_"):
                continue
            m = re.match(r'^(\d{3})_', f.name)
            if not m:
                continue
            try:
                sid = int(m.group(1))
            except ValueError:
                continue

            if sid not in scene_counts:
                # Might be 0-based or 1-based indexing match
                continue

            name_lower = f.name.lower()
            if '_pexels_video_' in name_lower and name_lower.endswith(self.VIDEO_EXTENSIONS):
                scene_counts[sid]['pexels_video'] += 1
            elif '_pexels_photo_' in name_lower and name_lower.endswith(self.PHOTO_EXTENSIONS):
                scene_counts[sid]['pexels_photo'] += 1
            elif '_motionarray_' in name_lower:
                scene_counts[sid]['ma_video'] += 1
            elif name_lower.endswith(self.VIDEO_EXTENSIONS + self.PHOTO_EXTENSIONS):
                scene_counts[sid]['other'] += 1

        scenes_with_files = 0
        total_files = 0
        for sid, info in scene_counts.items():
            tot = info['pexels_video'] + info['pexels_photo'] + info['ma_video'] + info['other']
            info['total'] = tot
            if tot > 0:
                scenes_with_files += 1
                total_files += tot

        return {
            "scenes_counts": scene_counts,
            "scenes_with_files": scenes_with_files,
            "total_files": total_files,
            "total_scenes": len(scenes)
        }
