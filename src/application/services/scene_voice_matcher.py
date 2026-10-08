"""
Native Scene Voice Matching application service.
Cuts and scales video footage or images to match voiceover audio or SRT subtitle timings using FFmpeg.
Pure Python - does not rely on external scripts.
"""

import os
import re
import json
import random
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Callable

from ...infrastructure.media.ffmpeg_processor import FFmpegProcessor
from ...core.models.scene import srt_time_to_seconds, extract_scenes_from_json


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
    def parse_script_json(json_path: Path) -> List[Dict[str, Any]]:
        """Extracts scenes and dialogue text from JSON screenplay."""
        if not json_path or not json_path.exists():
            return []
        try:
            raw = json_path.read_text(encoding="utf-8", errors="ignore")
            data = json.loads(raw)
            scenes = extract_scenes_from_json(data)
            segments = []
            for s in scenes:
                if isinstance(s, dict):
                    text = s.get("dialogue") or s.get("dialogue_es") or s.get("description") or s.get("title") or s.get("text") or ""
                    try:
                        raw_dur = float(s.get("duration") or s.get("duration_seconds") or 0.0)
                    except (ValueError, TypeError):
                        raw_dur = 0.0
                    sid = s.get("id") or s.get("scene_id") or ""
                else:
                    text = getattr(s, "dialogue", "") or getattr(s, "description", "") or getattr(s, "title", "")
                    raw_dur = float(getattr(s, "duration_seconds", 0.0) or getattr(s, "duration", 0.0))
                    sid = getattr(s, "id", "")

                dur = raw_dur if raw_dur > 0.5 else 4.0
                segments.append({
                    "start": 0.0,
                    "end": dur,
                    "duration": dur,
                    "text": text,
                    "scene_id": sid
                })
            return segments
        except Exception:
            return []

    @staticmethod
    def get_scene_folders(root_dir: Path) -> List[Path]:
        """Finds scene folders within root_dir, sorted naturally."""
        if not root_dir.exists():
            return []
        dirs = [d for d in root_dir.iterdir() if d.is_dir()]
        def sort_key(d: Path):
            nums = re.findall(r"\d+", d.name)
            return int(nums[0]) if nums else 9999
        return sorted(dirs, key=sort_key)

    @classmethod
    def get_media_files(cls, folder: Path) -> List[Path]:
        """Gets all video and high-resolution image files in a folder."""
        if not folder.exists():
            return []
        valid_exts = FFmpegProcessor.VIDEO_EXTENSIONS | FFmpegProcessor.IMAGE_EXTENSIONS
        return [f for f in folder.glob("*") if f.is_file() and f.suffix.lower() in valid_exts]

    @classmethod
    def get_video_files(cls, folder: Path) -> List[Path]:
        """Gets only video files in a folder."""
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
        script_json: Optional[Path] = None,
        full_voice_audio: Optional[Path] = None,
        random_cuts: bool = False,
        concat_final: bool = True,
        chunk_seconds: float = 0.0,
        progress_cb: Optional[Callable[[int, int, str], None]] = None,
        log_cb: Optional[Callable[[str], None]] = None,
    ) -> Tuple[bool, str, List[Path]]:
        """
        Executes the matching pipeline:
        1. Reads timing from SRT, audio clips, or script JSON
        2. Assigns video/image footage from each scene folder
        3. Cuts and scales each clip to 1920x1080 30fps (looping if shorter)
        4. Concatenates into final video and muxes audio if requested
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
            direct_media = self.get_media_files(root_video_dir)
            if direct_media:
                scene_dirs = [root_video_dir]
            else:
                return False, f"Không tìm thấy thư mục cảnh hoặc media trong: {root_video_dir}", []

        # Parse timings: Priority 1 = SRT, Priority 2 = Voice audio files, Priority 3 = Script JSON
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
                dur = dur if dur > 0.5 else (chunk_seconds if chunk_seconds > 0 else 4.0)
                segments.append({
                    "start": 0.0,
                    "end": dur,
                    "duration": dur,
                    "text": af.stem,
                    "audio_file": af
                })

        if not segments and script_json and script_json.exists():
            log(f"Trích xuất phân đoạn từ kịch bản: {script_json.name}")
            segments = self.parse_script_json(script_json)

        # Fallback if nothing found: chunk_seconds
        if not segments:
            default_dur = chunk_seconds if chunk_seconds > 0.5 else 4.0
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
            dur = seg.get("duration", 4.0)
            text_desc = seg.get("text", "")
            audio_clip = seg.get("audio_file")

            scene_idx = (idx - 1) % len(scene_dirs)
            target_scene_dir = scene_dirs[scene_idx]
            media_list = self.get_media_files(target_scene_dir)

            if not media_list:
                all_media = []
                for sd in scene_dirs:
                    all_media.extend(self.get_media_files(sd))
                media_list = all_media

            if not media_list:
                log(f"[Cảnh {idx:02d}] Bỏ qua: Không có media trong {target_scene_dir.name}")
                continue

            # Prioritize video over image if available
            videos = [m for m in media_list if m.suffix.lower() in FFmpegProcessor.VIDEO_EXTENSIONS]
            chosen_media = (random.choice(videos) if random_cuts else videos[0]) if videos else (random.choice(media_list) if random_cuts else media_list[0])

            out_clip = clips_dir / f"clip_{idx:03d}_{target_scene_dir.name}.mp4"
            is_image = chosen_media.suffix.lower() in FFmpegProcessor.IMAGE_EXTENSIONS

            if is_image:
                log(f"[{idx:02d}/{total:02d}] Tạo video từ ảnh {chosen_media.name} (thời lượng: {dur:.2f}s)")
                ok, err = self.ffmpeg.image_to_clip(chosen_media, dur, out_clip)
            else:
                vid_dur = self.ffmpeg.clip_duration(chosen_media)
                start_at = 0.0
                if random_cuts and vid_dur > dur + 1.0:
                    max_start = max(0.0, vid_dur - dur)
                    start_at = random.uniform(0.0, max_start)
                log(f"[{idx:02d}/{total:02d}] Cắt {dur:.2f}s từ {chosen_media.name} (bắt đầu: {start_at:.2f}s, tự lặp nếu thiếu)")
                ok, err = self.ffmpeg.cut_clip(chosen_media, start_at, dur, out_clip, loop_if_short=True)

            if ok:
                # If segment has individual audio file and we want audio attached
                if audio_clip and Path(audio_clip).exists():
                    clip_with_audio = clips_dir / f"clip_{idx:03d}_voiced.mp4"
                    ok_a, _ = self._mux_audio_to_video(out_clip, Path(audio_clip), clip_with_audio)
                    if ok_a:
                        out_clip = clip_with_audio

                generated_clips.append(out_clip)
            else:
                log(f"[Lỗi xử lý cảnh {idx:02d}]: {err[:120] if err else 'Không xác định'}")

            if progress_cb:
                progress_cb(idx, total, f"Đã cắt {idx}/{total} clip")

        if not generated_clips:
            return False, "Không tạo được clip video nào", []

        log(f"Đã tạo thành công {len(generated_clips)} clip video chuẩn 1920x1080 30fps")

        final_video_path = output_dir / "final_scene_voice_matched.mp4"
        if concat_final:
            log(f"Đang ghép toàn bộ {len(generated_clips)} clip thành video master hoàn chỉnh...")
            ok_concat, concat_err = self.ffmpeg.concat_clips(generated_clips, final_video_path)
            if not ok_concat:
                log(f"Lỗi ghép nối video: {concat_err}")
                return False, f"Lỗi ghép nối: {concat_err}", generated_clips

            log(f"Video ghép nối hoàn tất: {final_video_path.name} ({final_video_path.stat().st_size // 1024} KB)")

            # Determine audio to mux over the master video
            audio_to_mux: Optional[Path] = None
            if full_voice_audio and Path(full_voice_audio).exists():
                audio_to_mux = Path(full_voice_audio)
            else:
                # If segment-level audio files exist, combine them into master audio
                seg_audios = [Path(seg["audio_file"]) for seg in segments if seg.get("audio_file") and Path(seg["audio_file"]).exists()]
                if seg_audios and len(seg_audios) == len(generated_clips):
                    master_voice_path = output_dir / "master_voice_combined.mp3"
                    log(f"Đang tự động ghép nối {len(seg_audios)} file âm thanh thành master voice...")
                    ok_a_concat, _ = self.ffmpeg.concat_audio(seg_audios, master_voice_path)
                    if ok_a_concat and master_voice_path.exists():
                        audio_to_mux = master_voice_path
                        log(f"Master voice hoàn tất: {master_voice_path.name}")

            if audio_to_mux and audio_to_mux.exists():
                muxed_path = output_dir / "final_scene_voice_with_master_audio.mp4"
                log(f"Đang hòa âm giọng đọc {audio_to_mux.name} vào video...")
                ok_mux, mux_err = self._mux_audio_to_video(final_video_path, audio_to_mux, muxed_path)
                if ok_mux:
                    final_video_path = muxed_path
                    log(f"Hòa âm hoàn tất: {muxed_path.name}")
                else:
                    log(f"Không thể hòa âm voice: {mux_err}")

            # Export synchronized SRT subtitle if available
            if voice_srt_path and Path(voice_srt_path).exists():
                try:
                    import shutil
                    dest_srt = output_dir / "final_scene_voice_matched.srt"
                    shutil.copy2(voice_srt_path, dest_srt)
                    log(f"Đã xuất phụ đề SRT đồng bộ: {dest_srt.name}")
                except Exception:
                    pass

        return True, f"Thành công: Đã xử lý {len(generated_clips)} clips. File xuất: {final_video_path.name}", generated_clips

    def _mux_audio_to_video(self, video_path: Path, audio_path: Path, out_path: Path) -> Tuple[bool, str]:
        """Muxes an audio track over video, matching duration and replacing any existing audio."""
        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-i", str(audio_path),
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k",
            "-shortest",
            "-movflags", "+faststart",
            str(out_path)
        ]
        r = self.ffmpeg._run_cmd(cmd)
        ok = r.returncode == 0 and out_path.exists() and out_path.stat().st_size > 1024
        return ok, r.stderr
