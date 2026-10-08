"""
Native Scene Voice Matching application service.
Cuts and scales video footage to match voiceover audio or SRT subtitle timings using FFmpeg.
Pure Python - does not rely on external scripts.
"""

import os
import re
import random
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Callable

from ...infrastructure.media.ffmpeg_processor import FFmpegProcessor
from ...core.models.scene import srt_time_to_seconds


class SceneVoiceMatchItem:
    """Represents a single segment to cut and match."""
    def __init__(self, index: int, text: str, duration: float, scene_dir: Path, audio_file: Optional[Path] = None):
        self.index = index
        self.text = text
        self.duration = duration
        self.scene_dir = scene_dir
        self.audio_file = audio_file


class SceneVoiceMatcher:
    """Coordinates cutting video clips according to subtitle / voice timings."""

    def __init__(self, ffmpeg_processor: Optional[FFmpegProcessor] = None):
        self.ffmpeg = ffmpeg_processor or FFmpegProcessor()

    @staticmethod
    def parse_srt(srt_path: Path) -> List[Dict[str, Any]]:
        """Parses an SRT file into a list of subtitle segments with timing in seconds."""
        if not srt_path.exists():
            return []
        raw = srt_path.read_text(encoding="utf-8", errors="ignore").replace("\r\n", "\n").replace("\r", "\n")
        blocks = []
        for block in re.split(r"\n{2,}", raw.strip()):
            lines = [l.strip() for l in block.split("\n") if l.strip()]
            if lines and lines[0].isdigit():
                lines = lines[1:]
            if not lines or "-->" not in lines[0]:
                continue
            parts = lines[0].split("-->")
            start_s = srt_time_to_seconds(parts[0].strip().split()[0])
            end_s = srt_time_to_seconds(parts[1].strip().split()[0])
            dur = max(0.5, end_s - start_s)
            content = " ".join(lines[1:]).strip()
            blocks.append({
                "start": start_s,
                "end": end_s,
                "duration": dur,
                "text": content
            })
        return blocks

    @staticmethod
    def get_scene_folders(root_dir: Path) -> List[Path]:
        """Finds scene folders within root_dir, sorted naturally."""
        if not root_dir.exists():
            return []
        # Look for subdirectories like Canh 1, Cảnh 01, Scene 1, or numeric folders
        dirs = [d for d in root_dir.iterdir() if d.is_dir()]
        def sort_key(d: Path):
            nums = re.findall(r"\d+", d.name)
            return int(nums[0]) if nums else 9999
        return sorted(dirs, key=sort_key)

    @staticmethod
    def get_video_files(folder: Path) -> List[Path]:
        """Gets all valid video files in a folder."""
        if not folder.exists():
            return []
        exts = FFmpegProcessor.VIDEO_EXTENSIONS
        return [f for f in folder.glob("*") if f.is_file() and f.suffix.lower() in exts]

    def match_and_cut(
        self,
        root_video_dir: Path,
        output_dir: Path,
        voice_srt_path: Optional[Path] = None,
        voice_audio_dir: Optional[Path] = None,
        full_voice_audio: Optional[Path] = None,
        random_cuts: bool = False,
        concat_final: bool = True,
        chunk_seconds: float = 0.0,
        progress_cb: Optional[Callable[[int, int, str], None]] = None,
        log_cb: Optional[Callable[[str], None]] = None,
    ) -> Tuple[bool, str, List[Path]]:
        """
        Executes the matching pipeline:
        1. Reads timing from SRT or audio clips
        2. Assigns video footage from each scene folder
        3. Cuts and scales each clip to 1920x1080 30fps
        4. Concatenates into final video if requested
        """
        def log(msg: str):
            if log_cb:
                log_cb(msg)

        if not self.ffmpeg.ffmpeg_exists():
            return False, "FFmpeg không tìm thấy trong hệ thống PATH", []

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        clips_dir = output_dir / "matched_clips"
        clips_dir.mkdir(parents=True, exist_ok=True)

        scene_dirs = self.get_scene_folders(root_video_dir)
        if not scene_dirs:
            # Fallback: check if root_video_dir itself contains videos directly
            direct_videos = self.get_video_files(root_video_dir)
            if direct_videos:
                scene_dirs = [root_video_dir]
            else:
                return False, f"Không tìm thấy thư mục cảnh hoặc video trong: {root_video_dir}", []

        # Parse timings
        segments: List[Dict[str, Any]] = []
        if voice_srt_path and voice_srt_path.exists():
            log(f"Đọc dữ liệu phụ đề từ: {voice_srt_path.name}")
            segments = self.parse_srt(voice_srt_path)

        if not segments and voice_audio_dir and voice_audio_dir.exists():
            audio_files = sorted(
                [f for f in voice_audio_dir.iterdir() if f.is_file() and f.suffix.lower() in {".mp3", ".wav", ".aac", ".m4a"}],
                key=lambda x: [int(c) if c.isdigit() else c for c in re.split(r"(\d+)", x.name)]
            )
            log(f"Quét được {len(audio_files)} file voice âm thanh")
            for i, af in enumerate(audio_files):
                dur = self.ffmpeg.clip_duration(af)
                dur = dur if dur > 0.5 else (chunk_seconds if chunk_seconds > 0 else 5.0)
                segments.append({
                    "start": 0.0,
                    "end": dur,
                    "duration": dur,
                    "text": af.stem,
                    "audio_file": af
                })

        # Fallback if no SRT and no audio: cut based on chunk_seconds
        if not segments:
            default_dur = chunk_seconds if chunk_seconds > 0.5 else 5.0
            for i, sdir in enumerate(scene_dirs, 1):
                segments.append({
                    "start": 0.0,
                    "end": default_dur,
                    "duration": default_dur,
                    "text": f"Cảnh {i}"
                })

        log(f"Bắt đầu cắt ghép {len(segments)} phân đoạn cảnh...")
        generated_clips: List[Path] = []
        total = len(segments)

        for idx, seg in enumerate(segments, 1):
            dur = seg.get("duration", 5.0)
            text_desc = seg.get("text", "")
            # Determine which scene folder to pull video from
            scene_idx = (idx - 1) % len(scene_dirs)
            target_scene_dir = scene_dirs[scene_idx]
            videos = self.get_video_files(target_scene_dir)

            if not videos:
                # Try sibling scene directories if current has no videos
                all_vids = []
                for sd in scene_dirs:
                    all_vids.extend(self.get_video_files(sd))
                videos = all_vids

            if not videos:
                log(f"[Cảnh {idx:02d}] Bỏ qua: Không có video nguồn trong {target_scene_dir.name}")
                continue

            chosen_vid = random.choice(videos) if random_cuts else videos[0]
            vid_dur = self.ffmpeg.clip_duration(chosen_vid)

            # Determine start offset
            start_at = 0.0
            if random_cuts and vid_dur > dur + 1.0:
                max_start = max(0.0, vid_dur - dur)
                start_at = random.uniform(0.0, max_start)

            out_clip = clips_dir / f"clip_{idx:03d}_{target_scene_dir.name}.mp4"
            log(f"[{idx:02d}/{total:02d}] Cắt {dur:.2f}s từ {chosen_vid.name} (bắt đầu: {start_at:.2f}s)")

            ok, err = self.ffmpeg.cut_clip(chosen_vid, start_at, dur, out_clip)
            if ok:
                generated_clips.append(out_clip)
            else:
                log(f"[Lỗi cắt cảnh {idx:02d}]: {err[:120] if err else 'Không xác định'}")

            if progress_cb:
                progress_cb(idx, total, f"Đã cắt {idx}/{total} clip")

        if not generated_clips:
            return False, "Không tạo được clip video nào", []

        log(f"Đã cắt thành công {len(generated_clips)} clip video chuẩn 1920x1080 30fps")

        final_video_path = output_dir / "final_scene_voice_matched.mp4"
        if concat_final:
            log(f"Đang tiến hành ghép toàn bộ {len(generated_clips)} clip thành video hoàn chỉnh...")
            ok_concat, concat_err = self.ffmpeg.concat_clips(generated_clips, final_video_path)
            if not ok_concat:
                log(f"Lỗi ghép nối video: {concat_err}")
                return False, f"Lỗi ghép nối: {concat_err}", generated_clips

            log(f"Video ghép nối hoàn tất: {final_video_path.name} ({final_video_path.stat().st_size // 1024} KB)")

            # If master full voice audio track is provided, mux it into final video
            if full_voice_audio and Path(full_voice_audio).exists():
                muxed_path = output_dir / "final_scene_voice_with_master_audio.mp4"
                log(f"Đang hòa âm file voice {Path(full_voice_audio).name} vào video...")
                ok_mux, mux_err = self._mux_audio_to_video(final_video_path, Path(full_voice_audio), muxed_path)
                if ok_mux:
                    final_video_path = muxed_path
                    log(f"Hòa âm hoàn tất: {muxed_path.name}")
                else:
                    log(f"Không thể hòa âm voice: {mux_err}")

        return True, f"Thành công: Đã xử lý {len(generated_clips)} clips. File xuất: {final_video_path.name}", generated_clips

    def _mux_audio_to_video(self, video_path: Path, audio_path: Path, out_path: Path) -> Tuple[bool, str]:
        """Muxes an audio track over video, matching duration and replacing silent audio."""
        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-i", str(audio_path),
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k",
            "-shortest",
            "-movflags", "+faststart",
            str(out_path)
        ]
        r = self.ffmpeg._run_cmd(cmd)
        ok = r.returncode == 0 and out_path.exists() and out_path.stat().st_size > 1024
        return ok, r.stderr
