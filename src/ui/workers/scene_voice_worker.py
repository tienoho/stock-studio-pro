"""
Background worker for executing SceneVoiceMatcher safely off the UI thread.
"""

from pathlib import Path
from typing import Optional
from PyQt6.QtCore import QThread, pyqtSignal

from ...application.services.scene_voice_matcher import SceneVoiceMatcher


class SceneVoiceWorker(QThread):
    """Background worker for executing SceneVoiceMatcher safely off the UI thread."""
    progress = pyqtSignal(str)
    progress_val = pyqtSignal(int, int)
    finished_signal = pyqtSignal(bool, str)

    def __init__(
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
    ):
        super().__init__()
        self.root_video_dir = root_video_dir
        self.output_dir = output_dir
        self.voice_srt_path = voice_srt_path
        self.voice_audio_dir = voice_audio_dir
        self.script_json = script_json
        self.full_voice_audio = full_voice_audio
        self.random_cuts = random_cuts
        self.concat_final = concat_final
        self.chunk_seconds = chunk_seconds
        self._is_stopped = False

    def stop(self):
        self._is_stopped = True

    def run(self):
        matcher = SceneVoiceMatcher()

        def on_prog(cur, total, text):
            self.progress_val.emit(cur, total)
            self.progress.emit(f"Tiến độ: [{cur}/{total}] {text}")

        def on_log(msg):
            self.progress.emit(msg)

        ok, msg, clips = matcher.match_and_cut(
            root_video_dir=self.root_video_dir,
            output_dir=self.output_dir,
            voice_srt_path=self.voice_srt_path,
            voice_audio_dir=self.voice_audio_dir,
            script_json=self.script_json,
            full_voice_audio=self.full_voice_audio,
            random_cuts=self.random_cuts,
            concat_final=self.concat_final,
            chunk_seconds=self.chunk_seconds,
            progress_cb=on_prog,
            log_cb=on_log,
            stop_cb=lambda: self._is_stopped,
        )
        self.finished_signal.emit(ok, msg)
