"""
Background worker thread for checking application updates without blocking the UI.
"""

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
