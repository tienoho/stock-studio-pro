"""
Downloads folder watcher to auto-detect new video files from MotionArray.
"""

from pathlib import Path
import threading
import time
from typing import Set
from PyQt6.QtCore import QObject, pyqtSignal


class DownloadsWatcherSignals(QObject):
    """Qt signals emitted when a new downloaded media file is ready."""
    fileDetected = pyqtSignal(str)


class DownloadsWatcher(QObject):
    """Watches the system Downloads directory for newly downloaded video files."""

    EXTENSIONS = {'.mp4', '.mov', '.webm', '.avi', '.mkv'}
    MIN_FILE_SIZE = 100 * 1024  # 100KB minimum size

    def __init__(self, downloads_dir: Path = None):
        super().__init__()
        self.signals = DownloadsWatcherSignals()
        self.downloads_dir = Path(downloads_dir) if downloads_dir else Path.home() / "Downloads"
        self._known_files: Set[str] = set()
        self._processed_files: Set[str] = set()
        self._running = False
        self._thread = None
        self._lock = threading.Lock()

    def start(self):
        if self._running:
            return
        if not self.downloads_dir.exists():
            return

        try:
            self._known_files = set(self._scan_folder())
        except Exception:
            return

        self._running = True
        self._thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)

    def _scan_folder(self):
        files = []
        try:
            for f in self.downloads_dir.iterdir():
                if not f.is_file():
                    continue
                if f.suffix.lower() not in self.EXTENSIONS:
                    continue
                if f.name.endswith('.crdownload') or f.name.endswith('.tmp'):
                    continue
                files.append(str(f))
        except Exception:
            pass
        return files

    def _is_file_ready(self, filepath: str) -> bool:
        """Ensure file has finished writing (size stable and not locked)."""
        p = Path(filepath)
        if not p.exists():
            return False
        try:
            size1 = p.stat().st_size
            if size1 < self.MIN_FILE_SIZE:
                return False
            time.sleep(1.0)
            size2 = p.stat().st_size
            return size1 == size2 and size2 > 0
        except Exception:
            return False

    def _watch_loop(self):
        while self._running:
            try:
                current_files = set(self._scan_folder())
                new_files = current_files - self._known_files

                for filepath in new_files:
                    if filepath in self._processed_files:
                        continue

                    if self._is_file_ready(filepath):
                        with self._lock:
                            self._processed_files.add(filepath)
                            self._known_files.add(filepath)
                        self.signals.fileDetected.emit(filepath)
            except Exception:
                pass

            for _ in range(20):
                if not self._running:
                    break
                time.sleep(0.1)
