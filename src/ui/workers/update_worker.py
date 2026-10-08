"""
Background worker thread for checking application updates without blocking the UI.
"""

import shutil
import tempfile
from pathlib import Path
from typing import Optional
from PyQt6.QtCore import QThread, pyqtSignal

from ...application.services.update_checker import UpdateCheckerService, ReleaseInfo
from ...core.constants import APP_VERSION, GITHUB_REPO_OWNER, GITHUB_REPO_NAME


class UpdateCheckWorker(QThread):
    """Asynchronous background worker to check for new releases."""

    update_available = pyqtSignal(object)  # Emits ReleaseInfo
    no_update = pyqtSignal(str)           # Emits status message
    error_occurred = pyqtSignal(str)      # Emits error message

    def __init__(
        self,
        current_version: str = APP_VERSION,
        owner: str = GITHUB_REPO_OWNER,
        repo: str = GITHUB_REPO_NAME,
        timeout: float = 6.0,
        parent=None
    ):
        super().__init__(parent)
        self.current_version = current_version
        self.owner = owner
        self.repo = repo
        self.timeout = timeout

    def run(self):
        service = UpdateCheckerService(owner=self.owner, repo=self.repo)
        has_update, release, msg = service.check_for_updates(
            current_version=self.current_version,
            timeout=self.timeout
        )

        if has_update and release:
            self.update_available.emit(release)
        elif release and not has_update:
            self.no_update.emit(msg)
        else:
            self.error_occurred.emit(msg)


class UpdateDownloadWorker(QThread):
    """
    Background worker thread for streaming download of the update archive,
    extracting into a staging folder, and preparing files for atomic in-place replacement.
    """

    progress = pyqtSignal(int, int, float, float)  # downloaded_bytes, total_bytes, percentage, speed_bps
    status = pyqtSignal(str)                       # Human-readable progress description
    finished = pyqtSignal(bool, str, object)       # success, message, staged_payload_dir (Path or None)

    def __init__(self, download_url: str, total_size: int = 0, parent=None):
        super().__init__(parent)
        self.download_url = download_url
        self.total_size = total_size
        self._is_cancelled = False

    def cancel(self):
        """Requests graceful cancellation of the ongoing download."""
        self._is_cancelled = True

    def _is_cancel_requested(self) -> bool:
        return self._is_cancelled

    def _on_progress(self, downloaded: int, total: int, speed: float):
        if total <= 0 and self.total_size > 0:
            total = self.total_size
        pct = (downloaded / total * 100.0) if total > 0 else 0.0
        pct = min(max(pct, 0.0), 100.0)
        self.progress.emit(downloaded, total, pct, speed)

    def run(self):
        service = UpdateCheckerService()
        temp_base = Path(tempfile.gettempdir()) / "autostock_update"
        temp_base.mkdir(parents=True, exist_ok=True)
        zip_dest = temp_base / "update_package.zip"
        staged_dir = temp_base / "staged"

        try:
            # Clean staged directory from prior runs
            if staged_dir.exists():
                shutil.rmtree(staged_dir, ignore_errors=True)

            self.status.emit("Đang kết nối đến máy chủ phát hành và tải xuống...")
            service.download_asset(
                download_url=self.download_url,
                dest_path=zip_dest,
                progress_cb=self._on_progress,
                cancel_fn=self._is_cancel_requested,
                estimated_total=self.total_size
            )

            if self._is_cancelled:
                self.finished.emit(False, "Người dùng đã hủy quá trình tải.", None)
                return

            self.status.emit("Đang kiểm tra tính toàn vẹn và giải nén gói cập nhật...")
            effective_payload = service.extract_archive(zip_dest, staged_dir)

            self.status.emit("Gói cập nhật đã sẵn sàng!")
            self.finished.emit(True, "Tải và giải nén thành công.", effective_payload)

        except InterruptedError:
            self.finished.emit(False, "Quá trình tải đã bị hủy.", None)
        except Exception as e:
            self.finished.emit(False, f"Lỗi tải cập nhật: {e}", None)

