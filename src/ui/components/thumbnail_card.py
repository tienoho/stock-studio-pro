"""
ThumbnailCard and asynchronous ThumbnailLoader components.
"""

import threading
from concurrent.futures import ThreadPoolExecutor
from PyQt6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox
from PyQt6.QtCore import Qt, pyqtSignal, QObject
from PyQt6.QtGui import QCursor, QPixmap

from ...core.constants import CARD_WIDTH, CARD_HEIGHT, THUMB_WIDTH, THUMB_HEIGHT
from ...core.i18n import t
from ...infrastructure.media.thumbnail_cache import add_duration_to_pixmap
from ..styles.theme_manager import ThemeManager
from .stat_box import Badge


class ThumbnailLoaderSignals(QObject):
    loaded = pyqtSignal(str, object)  # url, QPixmap
    failed = pyqtSignal(str)          # url


class ThumbnailLoader(QObject):
    """Background pool loader for thumbnail pixmaps."""

    def __init__(self, cache):
        super().__init__()
        self.cache = cache
        self.signals = ThumbnailLoaderSignals()
        self.executor = ThreadPoolExecutor(max_workers=2)
        self._pending = set()
        self._lock = threading.Lock()

    def load_async(self, url: str):
        with self._lock:
            if url in self._pending:
                return
            cached = self.cache.get_pixmap(url)
            if cached:
                self.signals.loaded.emit(url, cached)
                return
            self._pending.add(url)

        self.executor.submit(self._fetch_worker, url)

    def _fetch_worker(self, url: str):
        try:
            pixmap = self.cache.fetch_pixmap(url)
            with self._lock:
                self._pending.discard(url)
            if pixmap:
                self.signals.loaded.emit(url, pixmap)
            else:
                self.signals.failed.emit(url)
        except Exception:
            with self._lock:
                self._pending.discard(url)
            self.signals.failed.emit(url)

    def shutdown(self):
        self.executor.shutdown(wait=False)


class ThumbnailCard(QFrame):
    """Studio card component with media thumbnail, badges, and selection checkbox."""

    selectionChanged = pyqtSignal(dict, bool)
    clicked = pyqtSignal(dict)
    retryRequested = pyqtSignal(dict)

    def __init__(self, item: dict, is_selected: bool = False, parent=None):
        super().__init__(parent)
        self.item = item
        self.is_selected = is_selected
        self.thumb_loaded = False
        self.thumb_failed = False

        self.setFixedSize(CARD_WIDTH, CARD_HEIGHT)
        self.setObjectName("card")
        self._update_style()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Thumbnail label
        self.thumb_label = QLabel()
        self.thumb_label.setFixedSize(THUMB_WIDTH, THUMB_HEIGHT)
        self.thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumb_label.setText("Loading...")
        self.thumb_label.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.thumb_label.mousePressEvent = self._on_thumb_clicked
        layout.addWidget(self.thumb_label)

        # Badges row
        badges = QHBoxLayout()
        badges.setSpacing(4)
        badges.setContentsMargins(0, 0, 0, 0)

        source_colors = {
            "pexels": "#059669",
            "pixabay": "#0284c7",
            "wikimedia": "#0891b2",
            "openverse": "#ea580c",
            "coverr": "#e11d48",
            "motionarray": "#d97706",
            "vecteezy": "#7c3aed",
            "youtube": "#dc2626",
            "tiktok": "#0f172a",
        }
        source_color = source_colors.get(item.get("source", ""), "#0284c7")
        badges.addWidget(Badge(item.get("source", "").upper(), source_color))

        m_type = item.get("type", "video")
        type_color = "#dc2626" if m_type == "video" else "#7c3aed"
        type_text = "VIDEO" if m_type == "video" else "PHOTO"
        badges.addWidget(Badge(type_text, type_color))
        badges.addStretch()

        layout.addLayout(badges)

        # Checkbox
        self.checkbox = QCheckBox(t("downloader.select_media"))
        self.checkbox.setChecked(is_selected)
        self.checkbox.toggled.connect(self._on_check_changed)
        self.checkbox.setFixedHeight(28)
        layout.addWidget(self.checkbox)

        # Apply initial styling and listen to theme changes
        self._update_style()
        ThemeManager.get_instance().themeChanged.connect(self._update_style)

    def _on_thumb_clicked(self, event):
        if self.thumb_failed:
            self.retryRequested.emit(self.item)
        else:
            self.clicked.emit(self.item)

    def mouseDoubleClickEvent(self, event):
        """Double clicking card opens high-res preview."""
        self.clicked.emit(self.item)
        super().mouseDoubleClickEvent(event)

    def mousePressEvent(self, event):
        """Clicking card background toggles selection."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.checkbox.toggle()
        super().mousePressEvent(event)

    def _update_style(self, theme_name: str = ""):
        try:
            is_dark = ThemeManager.get_instance().is_dark()
        except (RuntimeError, Exception):
            return
        if self.is_selected:
            if is_dark:
                self.setStyleSheet("""
                    #card {
                        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #0f2c20, stop:1 #0a1c15);
                        border: 2px solid #10b981;
                        border-radius: 12px;
                    }
                    #card:hover {
                        border-color: #34d399;
                        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #133829, stop:1 #0c231a);
                    }
                """)
            else:
                self.setStyleSheet("""
                    #card {
                        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #ecfdf5, stop:1 #d1fae5);
                        border: 2px solid #10b981;
                        border-radius: 12px;
                    }
                    #card:hover {
                        border-color: #059669;
                        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #d1fae5, stop:1 #a7f3d0);
                    }
                """)
        else:
            if is_dark:
                self.setStyleSheet("""
                    #card {
                        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #121826, stop:1 #0c101a);
                        border: 1px solid #1f2b3f;
                        border-radius: 12px;
                    }
                    #card:hover {
                        border-color: #6366f1;
                        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #151d2d, stop:1 #0e131d);
                    }
                """)
            else:
                self.setStyleSheet("""
                    #card {
                        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #ffffff, stop:1 #f8fafc);
                        border: 1px solid #e2e8f0;
                        border-radius: 12px;
                    }
                    #card:hover {
                        border-color: #6366f1;
                        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #f8fafc, stop:1 #f1f5f9);
                    }
                """)

        if hasattr(self, 'thumb_label'):
            if is_dark:
                self.thumb_label.setStyleSheet("""
                    background-color: #0c0f17;
                    border-radius: 8px;
                    color: #64748b;
                    font-size: 11px;
                    font-weight: 600;
                """)
            else:
                self.thumb_label.setStyleSheet("""
                    background-color: #e2e8f0;
                    border-radius: 8px;
                    color: #64748b;
                    font-size: 11px;
                    font-weight: 600;
                """)

        if hasattr(self, 'checkbox'):
            if is_dark:
                self.checkbox.setStyleSheet("""
                    QCheckBox {
                        color: #e2e8f0;
                        font-size: 11px;
                        font-weight: 700;
                        padding: 4px 8px;
                        background-color: #1a2233;
                        border-radius: 6px;
                        spacing: 6px;
                    }
                    QCheckBox:hover { background-color: #222d42; color: #ffffff; }
                    QCheckBox::indicator {
                        width: 16px;
                        height: 16px;
                        border-radius: 4px;
                        border: 1.5px solid #3b4d6e;
                        background-color: #0c0f17;
                    }
                    QCheckBox::indicator:checked {
                        background-color: #10b981;
                        border-color: #34d399;
                    }
                    QCheckBox::indicator:hover {
                        border-color: #818cf8;
                    }
                """)
            else:
                self.checkbox.setStyleSheet("""
                    QCheckBox {
                        color: #1e293b;
                        font-size: 11px;
                        font-weight: 700;
                        padding: 4px 8px;
                        background-color: #f1f5f9;
                        border-radius: 6px;
                        spacing: 6px;
                    }
                    QCheckBox:hover { background-color: #e2e8f0; color: #0f172a; }
                    QCheckBox::indicator {
                        width: 16px;
                        height: 16px;
                        border-radius: 4px;
                        border: 1.5px solid #cbd5e1;
                        background-color: #ffffff;
                    }
                    QCheckBox::indicator:checked {
                        background-color: #10b981;
                        border-color: #059669;
                    }
                    QCheckBox::indicator:hover {
                        border-color: #6366f1;
                    }
                """)

    def _on_check_changed(self, checked: bool):
        self.is_selected = checked
        self._update_style()
        self.selectionChanged.emit(self.item, checked)

    def set_thumbnail(self, pixmap: QPixmap):
        if pixmap is None or pixmap.isNull():
            return

        scaled = pixmap.scaled(
            THUMB_WIDTH, THUMB_HEIGHT,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation
        )

        if scaled.width() > THUMB_WIDTH or scaled.height() > THUMB_HEIGHT:
            x_offset = (scaled.width() - THUMB_WIDTH) // 2
            y_offset = (scaled.height() - THUMB_HEIGHT) // 2
            scaled = scaled.copy(x_offset, y_offset, THUMB_WIDTH, THUMB_HEIGHT)

        if self.item.get("type") == "video" and self.item.get("duration"):
            scaled = add_duration_to_pixmap(scaled, self.item["duration"])

        self.thumb_label.setPixmap(scaled)
        self.thumb_loaded = True
        self.thumb_failed = False

    def set_failed_state(self):
        self.thumb_failed = True
        self.thumb_loaded = False
        self.thumb_label.clear()
        self.thumb_label.setText(t("downloader.load_fail"))
        self.thumb_label.setStyleSheet("""
            background-color: #261217;
            border: 1px dashed #ef4444;
            border-radius: 8px;
            color: #f87171;
            font-size: 10px;
            font-weight: 700;
        """)

    def reset_to_loading(self):
        self.thumb_failed = False
        self.thumb_loaded = False
        self.thumb_label.clear()
        self.thumb_label.setText("Loading...")
        self.thumb_label.setStyleSheet("""
            background-color: #0c0f17;
            border-radius: 8px;
            color: #64748b;
            font-size: 11px;
            font-weight: 600;
        """)

    def set_selected(self, selected: bool):
        if self.checkbox.isChecked() != selected:
            self.checkbox.setChecked(selected)
