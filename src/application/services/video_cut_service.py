"""
Video Cut & Mix application service orchestrating FFmpeg cuts per scene folder.
"""

from pathlib import Path
import random
from typing import List, Callable, Optional
from ...infrastructure.media.ffmpeg_processor import FFmpegProcessor


class VideoCutService:
    """Orchestrates cutting video chunks in scene folders and mixing final cuts."""

    def __init__(self, processor: Optional[FFmpegProcessor] = None):
        self.processor = processor or FFmpegProcessor()

    def get_video_files(self, folder: Path) -> List[Path]:
        files = []
        for f in folder.iterdir():
            if f.is_file() and f.suffix.lower() in self.processor.VIDEO_EXTENSIONS:
                if not f.stem.lower().startswith("final"):
                    files.append(f)
        return sorted(files, key=lambda x: x.name.lower())

    def get_target_folders(self, root_folder: Path) -> List[Path]:
        child_folders = [
            d for d in root_folder.iterdir()
            if d.is_dir() and not d.name.startswith("_") and d.name.lower() not in ("canh", "cảnh")
        ]
        scene_folders = [d for d in child_folders if self.get_video_files(d)]
        if scene_folders:
            def sort_key(p: Path):
                return (0, int(p.name)) if p.name.isdigit() else (1, p.name.lower())
            return sorted(scene_folders, key=sort_key)
        return [root_folder] if self.get_video_files(root_folder) else []

    def clear_old_clips(self, clips_dir: Path) -> None:
        clips_dir.mkdir(parents=True, exist_ok=True)
        for old in clips_dir.glob("*.mp4"):
            try:
                old.unlink()
            except Exception:
                pass

    def process_folder(
        self,
        folder: Path,
        folder_index: int,
        folder_total: int,
        canh_dir: Path,
        segment_seconds: float = 1.0,
        final_count: int = 1,
        max_clips_per_final: int = 0,
        progress_cb: Optional[Callable[[str], None]] = None,
        should_stop: Optional[Callable[[], bool]] = None,
    ) -> int:
        should_stop = should_stop or (lambda: False)
        log = progress_cb or (lambda msg: None)

        raw_videos = self.get_video_files(folder)
        vertical_videos = [v for v in raw_videos if self.processor.is_vertical_video(v)]
        videos = [v for v in raw_videos if v not in vertical_videos]

        if vertical_videos:
            log(f"  Bỏ {len(vertical_videos)} video dọc trong folder {folder.name}")
        if not videos:
            log(f"Bỏ qua {folder.name}: không có video ngang")
            return 0

        clips_dir = folder / "_clips"
        self.clear_old_clips(clips_dir)
        log(f"[{folder_index}/{folder_total}] Folder {folder.name}: {len(videos)} video, cắt mỗi {segment_seconds:g}s")

        clips = []
        part_no = 0
        for idx, video in enumerate(videos, 1):
            if should_stop():
                return 0

            duration = self.processor.clip_duration(video)
            if duration <= 0:
                log(f"  [BỎ QUA] {video.name}: không đọc được duration")
                continue

            log(f"  [{idx}/{len(videos)}] Cắt chính xác: {video.name} ({duration:.1f}s)")
            start_at = 0.0
            while start_at < duration:
                if should_stop():
                    return 0

                part_no += 1
                out_clip = clips_dir / f"{video.stem}_part_{part_no:04d}.mp4"
                ok, err = self.processor.cut_clip(video, start_at, segment_seconds, out_clip)
                if ok:
                    clips.append(out_clip)
                else:
                    log(f"  [CẢNH BÁO] Lỗi đoạn {start_at:.1f}s của {video.name}: {err[-200:]}")
                start_at += segment_seconds

        clips = [c for c in clips if c.exists() and c.stat().st_size > 1024]
        min_clip_sec = max(0.2, min(segment_seconds * 0.7, 3.0))
        kept_clips = [c for c in clips if self.processor.clip_duration(c) >= min_clip_sec]
        skipped_short = len(clips) - len(kept_clips)
        if skipped_short:
            log(f"  Bỏ {skipped_short} clip ngắn hơn {min_clip_sec:.1f}s")

        if not kept_clips:
            log(f"  [LỖI] Folder {folder.name}: không còn clip hợp lệ (>={min_clip_sec:.1f}s) để ghép")
            return 0

        log(f"  Đã tạo {len(kept_clips)} clip hợp lệ (>={min_clip_sec:.1f}s). Ghép random final...")
        made = 0
        for n in range(1, final_count + 1):
            if should_stop():
                return made

            picked = kept_clips[:]
            random.shuffle(picked)
            if max_clips_per_final > 0:
                picked = picked[:max_clips_per_final]

            expected_seconds = sum(self.processor.clip_duration(c) for c in picked)
            out_name = f"{folder_index}.mp4" if final_count == 1 else f"{folder_index}_{n}.mp4"
            out_path = canh_dir / out_name

            log(f"  Ghép {out_path.name} vào folder Canh từ {len(picked)} clip | ~{expected_seconds:.1f}s...")
            ok, err = self.processor.concat_clips(picked, out_path)
            if ok:
                made += 1
                log(f"  [THÀNH CÔNG] Đã lưu: {out_path}")
            else:
                log(f"  [CẢNH BÁO] final {n} lỗi: {err[-250:]}")

        return made
