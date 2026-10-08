"""
Background worker executing VideoCutService with Qt signals.
"""

from pathlib import Path
from PyQt6.QtCore import QThread, pyqtSignal
from ...application.services.video_cut_service import VideoCutService


class VideoCutMergeWorker(QThread):
    """Cut videos in scene folders, then create smooth random final videos."""

    progress = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, folder: str, segment_seconds: float = 1.0, final_count: int = 1, max_clips_per_final: int = 0):
        super().__init__()
        self.folder = Path(folder)
        self.segment_seconds = max(0.1, float(segment_seconds))
        self.final_count = max(1, int(final_count))
        self.max_clips_per_final = max(0, int(max_clips_per_final))
        self._stop = False
        self.service = VideoCutService()

    def stop(self):
        self._stop = True

    def run(self):
        try:
            if not self.folder.exists() or not self.folder.is_dir():
                self.finished_signal.emit(False, "Folder không tồn tại")
                return
            if not self.service.processor.ffmpeg_exists():
                self.finished_signal.emit(False, "Không thấy ffmpeg. Cài ffmpeg hoặc thêm ffmpeg vào PATH trước nhé")
                return

            folders = self.service.get_target_folders(self.folder)
            if not folders:
                self.finished_signal.emit(False, "Không tìm thấy video trong folder đã chọn hoặc các folder con")
                return

            canh_dir = self.folder / "Canh" if len(folders) > 1 else self.folder.parent / "Canh"
            canh_dir.mkdir(parents=True, exist_ok=True)
            self.progress.emit(f"Sẽ xử lý {len(folders)} folder cảnh: " + ", ".join(f.name for f in folders[:20]))
            self.progress.emit(f"Final cảnh sẽ lưu tại: {canh_dir}")

            total_final = 0
            for idx, fld in enumerate(folders, 1):
                if self._stop:
                    self.finished_signal.emit(False, "Đã dừng")
                    return
                total_final += self.service.process_folder(
                    folder=fld,
                    folder_index=idx,
                    folder_total=len(folders),
                    canh_dir=canh_dir,
                    segment_seconds=self.segment_seconds,
                    final_count=self.final_count,
                    max_clips_per_final=self.max_clips_per_final,
                    progress_cb=self.progress.emit,
                    should_stop=lambda: self._stop,
                )

            self.finished_signal.emit(True, f"Xong {len(folders)} folder cảnh, tạo {total_final} file final")
        except Exception as e:
            self.finished_signal.emit(False, str(e))
