"""
FFmpeg and ffprobe wrapper for cutting, scaling, and concatenating video.
Independent of Qt/GUI.
"""

import os
import subprocess
import random
from pathlib import Path
from typing import List, Tuple, Optional


class FFmpegProcessor:
    """Provides pure Python + FFmpeg CLI video processing."""

    VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}

    def __init__(self):
        self.creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0

    def _run_cmd(self, cmd: List[str]) -> subprocess.CompletedProcess:
        return subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=self.creationflags,
        )

    def ffmpeg_exists(self) -> bool:
        try:
            return self._run_cmd(["ffmpeg", "-version"]).returncode == 0
        except Exception:
            return False

    def video_size(self, video_path: Path) -> Tuple[int, int]:
        try:
            r = self._run_cmd([
                "ffprobe", "-v", "error", "-select_streams", "v:0",
                "-show_entries", "stream=width,height",
                "-of", "csv=s=x:p=0", str(video_path)
            ])
            if r.returncode == 0 and "x" in (r.stdout or ""):
                parts = r.stdout.strip().splitlines()[0].split("x")[:2]
                return int(parts[0]), int(parts[1])
        except Exception:
            pass
        return 0, 0

    def is_vertical_video(self, video_path: Path) -> bool:
        w, h = self.video_size(video_path)
        return w > 0 and h > 0 and h > w

    def clip_duration(self, clip_path: Path) -> float:
        try:
            r = self._run_cmd([
                "ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", str(clip_path)
            ])
            if r.returncode == 0:
                return max(0.0, float((r.stdout or "0").strip()))
        except Exception:
            pass
        return 0.0

    def cut_clip(self, video_path: Path, start_at: float, duration: float, out_clip: Path) -> Tuple[bool, str]:
        """Cut precise clip with scaling to 1920x1080 lanczos, 30fps."""
        cmd = [
            "ffmpeg", "-y",
            "-ss", f"{start_at:.3f}", "-t", f"{duration:.3f}",
            "-i", str(video_path),
            "-map", "0:v:0", "-an",
            "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease:flags=lanczos,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,fps=30,setsar=1,format=yuv420p,setpts=PTS-STARTPTS",
            "-r", "30",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
            "-profile:v", "high", "-level", "4.1", "-pix_fmt", "yuv420p",
            "-movflags", "+faststart", "-f", "mp4", str(out_clip)
        ]
        r = self._run_cmd(cmd)
        ok = (r.returncode == 0 and out_clip.exists() and out_clip.stat().st_size > 1024)
        return ok, r.stderr

    def concat_clips(self, clips: List[Path], out_path: Path) -> Tuple[bool, str]:
        """Concatenate clips using filter_complex or concat demuxer for large clip lists."""
        if not clips:
            return False, "Danh sách clips rỗng"

        # For large clip lists (> 20 clips), use concat demuxer file to prevent Windows command line length overflow
        if len(clips) > 20:
            return self._concat_via_demuxer(clips, out_path)

        cmd = ["ffmpeg", "-y"]
        for clip in clips:
            cmd.extend(["-i", str(clip)])

        filter_parts = []
        for i in range(len(clips)):
            filter_parts.append(
                f"[{i}:v:0]scale=1920:1080:force_original_aspect_ratio=decrease:flags=lanczos,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,fps=30,setsar=1,format=yuv420p,setpts=PTS-STARTPTS[v{i}]"
            )
        filter_parts.append("".join(f"[v{i}]" for i in range(len(clips))) + f"concat=n={len(clips)}:v=1:a=0[v]")

        cmd.extend([
            "-filter_complex", ";".join(filter_parts),
            "-map", "[v]", "-an", "-r", "30",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
            "-profile:v", "high", "-level", "4.1", "-pix_fmt", "yuv420p",
            "-video_track_timescale", "30000",
            "-movflags", "+faststart", "-f", "mp4", str(out_path)
        ])

        r = self._run_cmd(cmd)
        ok = (r.returncode == 0 and out_path.exists() and out_path.stat().st_size > 1024)
        if not ok and len(clips) > 1:
            # Fallback to concat demuxer on error
            return self._concat_via_demuxer(clips, out_path)
        return ok, r.stderr

    def _concat_via_demuxer(self, clips: List[Path], out_path: Path) -> Tuple[bool, str]:
        """Concatenate clips safely using a temporary file list."""
        list_file = out_path.parent / f"_concat_{out_path.stem}.txt"
        try:
            with open(list_file, "w", encoding="utf-8") as f:
                for c in clips:
                    escaped_path = str(c.resolve()).replace("\\", "/").replace("'", "'\\''")
                    f.write(f"file '{escaped_path}'\n")

            cmd = [
                "ffmpeg", "-y",
                "-f", "concat", "-safe", "0",
                "-i", str(list_file),
                "-an", "-r", "30",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
                "-profile:v", "high", "-level", "4.1", "-pix_fmt", "yuv420p",
                "-video_track_timescale", "30000",
                "-movflags", "+faststart", "-f", "mp4", str(out_path)
            ]
            r = self._run_cmd(cmd)
            ok = (r.returncode == 0 and out_path.exists() and out_path.stat().st_size > 1024)
            return ok, r.stderr
        finally:
            try:
                list_file.unlink(missing_ok=True)
            except Exception:
                pass

