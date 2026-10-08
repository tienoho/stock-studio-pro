"""
Background worker for generating voice audio and subtitles.
"""

import os
import subprocess
from pathlib import Path
from typing import List, Optional
from PyQt6.QtCore import QThread, pyqtSignal

from ...application.services.edge_tts_service import EdgeTTSService


class VoiceGenerationWorker(QThread):
    """Background thread worker for generating voice audio and subtitles."""
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int, int)
    finished_signal = pyqtSignal(int, int)

    def __init__(
        self,
        files: List[Path],
        output_dir: Path,
        provider: str,
        voice_id: str,
        speed: float,
        generate_srt: bool = True,
        tool_root: Optional[Path] = None
    ):
        super().__init__()
        self.files = files
        self.output_dir = output_dir
        self.provider = provider
        self.voice_id = voice_id
        self.speed = speed
        self.generate_srt = generate_srt
        self.tool_root = tool_root
        self._is_stopped = False

    def stop(self):
        self._is_stopped = True

    def run(self):
        total = len(self.files)
        success = 0

        if "edge" in self.provider.lower():
            # Native Edge TTS
            service = EdgeTTSService(default_voice=self.voice_id)
            speed_pct = f"{int((self.speed - 1.0) * 100):+d}%"

            def on_log(msg):
                self.log_signal.emit(msg)

            def on_prog(cur, tot, text):
                self.progress_signal.emit(cur, tot)

            ok_count, total_count, _ = service.batch_synthesize_txt_files(
                txt_files=self.files,
                output_dir=self.output_dir,
                voice=self.voice_id,
                rate=speed_pct,
                generate_subtitles=self.generate_srt,
                progress_cb=on_prog,
                log_cb=on_log,
                stop_cb=lambda: self._is_stopped
            )
            success = ok_count
        else:
            # External Node.js provider fallback
            tool = (self.tool_root / "Voice TXT Tool") if self.tool_root else Path("Voice TXT Tool")
            server_script = tool / "server.mjs"
            if not server_script.exists():
                self.log_signal.emit(f"[LỖI] Không tìm thấy script ngoài tại: {server_script}")
                self.log_signal.emit("GỢI Ý: Chuyển sang chọn 'Edge TTS (Miễn phí / Khuyên dùng)' để tạo giọng trực tiếp không cần Node.js.")
                self.finished_signal.emit(0, total)
                return

            for idx, inp in enumerate(self.files, 1):
                if self._is_stopped:
                    self.log_signal.emit("[DỪNG] Đã hủy tiến trình tạo giọng.")
                    break
                self.log_signal.emit(f"[{idx}/{total}] Đang tạo giọng đọc: {inp.name} qua {self.provider}...")
                cmd = [
                    "node", "server.mjs", "--cli", str(inp), str(self.output_dir),
                    self.provider, str(self.speed)
                ]
                try:
                    proc = subprocess.Popen(
                        cmd, cwd=str(tool), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                        text=True, encoding="utf-8", errors="replace",
                        creationflags=(subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
                    )
                    for line in proc.stdout or []:
                        self.log_signal.emit(line.rstrip())
                    proc.wait()
                    if proc.returncode == 0:
                        success += 1
                except Exception as e:
                    self.log_signal.emit(f"[LỖI] {e}")

                self.progress_signal.emit(idx, total)

        self.finished_signal.emit(success, total)
