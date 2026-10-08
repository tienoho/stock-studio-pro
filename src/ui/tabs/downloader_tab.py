"""
DownloaderTab component implementing the primary 4-column studio view:
Setup Sidebar | Scenes Timeline | Media Grid & Controls | MotionArray & Monitor.
"""

import os
import re
import json
import time
import random
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional

from PyQt6.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QPushButton, QComboBox, QCheckBox, QLineEdit, QTextEdit, QScrollArea,
    QSpinBox, QMessageBox, QDialog, QApplication, QSplitter, QStackedWidget
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QCursor, QShortcut, QKeySequence

from ...core.constants import (
    APP_VERSION, DEFAULT_OUTPUT_DIR, GRID_ROWS, GRID_COLS, ITEMS_PER_PAGE,
    STAT_COLOR_BLUE, STAT_COLOR_PURPLE, STAT_COLOR_RED, STAT_COLOR_GREEN
)
from ...core.i18n import t
from ...core.models.scene import extract_scenes_from_json
from ..styles.icons import get_svg_icon, get_svg_pixmap
from ..styles.theme_manager import ThemeManager
from ..styles.ui_enhancer import enhance_widget_interactions, format_tooltip
from ...application.services.key_manager import KeyManager
from ..components.api_key_manager_widget import ApiKeyManagerWidget
from ..components.stat_box import StatBox
from ..components.scene_list_item import SceneListItem
from ..components.thumbnail_card import ThumbnailCard
from ..components.status_panel import StatusPanel
from ..components.preview_modal import PreviewModal
from ..components.toast_notification import ToastNotification
from ..dialogs.assign_scene_dialog import AssignSceneDialog
from ..workers.search_worker import SearchWorker
from ..workers.download_worker import DownloadWorker
from ...infrastructure.persistence.sqlite_downloads_repo import SqliteDownloadsRepository


class DownloaderTab(QWidget):
    """Primary 4-column studio tab for searching, previewing, and downloading stock media."""

    open_settings_requested = pyqtSignal()
    status_message = pyqtSignal(str, int)
    search_finished = pyqtSignal()
    download_finished = pyqtSignal(int, int, str, dict)
    nextStepRequested = pyqtSignal()
    json_loaded = pyqtSignal(dict, list, str)
    selection_changed = pyqtSignal(int)

    def __init__(
        self,
        config: dict,
        config_repo=None,
        state_repo=None,
        thumbnail_cache=None,
        thumb_loader=None,
        downloads_watcher=None,
        downloads_repo=None,
        parent=None
    ):
        super().__init__(parent)
        self.config = config
        self.config_repo = config_repo
        self.state_repo = state_repo
        self.thumbnail_cache = thumbnail_cache
        self.thumb_loader = thumb_loader
        self.downloads_watcher = downloads_watcher
        self.downloads_repo = downloads_repo or SqliteDownloadsRepository()

        # State
        self.scenes: List[Dict[str, Any]] = []
        self.json_data: Optional[Dict[str, Any]] = None
        self.scene_items: Dict[Any, List[Dict[str, Any]]] = {}
        self.selected_items: Dict[Any, Dict[str, Dict[str, Any]]] = {}
        self.current_scene_id: Optional[Any] = None
        self.current_page = 0
        self.current_filter = "all"
        self._current_ma_scene_id = None
        self._watcher_started = False
        self._auto_download_confirmless = False

        # Active UI references
        self.scene_list_widgets: List[SceneListItem] = []
        self.thumb_cards: List[ThumbnailCard] = []
        self.url_to_cards: Dict[str, List[ThumbnailCard]] = {}
        self.dm_scene_rows: Dict[Any, QFrame] = {}
        self.ma_keyword_checks: List[QCheckBox] = []

        # Workers
        self.search_worker: Optional[SearchWorker] = None
        self.download_worker: Optional[DownloadWorker] = None

        # Build UI layout
        self._build_ui()

        # Connect thumb loader signals if provided
        if self.thumb_loader:
            self.thumb_loader.signals.loaded.connect(self._on_thumbnail_loaded)
            self.thumb_loader.signals.failed.connect(self._on_thumbnail_failed)

        # Connect downloads watcher if provided
        if self.downloads_watcher:
            self.downloads_watcher.signals.fileDetected.connect(self._on_download_detected)

        # Connect theme changes to refresh dynamic styling
        ThemeManager.get_instance().themeChanged.connect(self._on_theme_changed)

    # ═══════════════════════════════════════════════════════════════
    # UI CONSTRUCTION (4 COLUMNS)
    # ═══════════════════════════════════════════════════════════════

    def _build_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Responsive 3-Column Splitter (Unified Studio Sidebar | Media Grid | Keywords & Monitor)
        self.splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self.splitter.setObjectName("studioSplitter")

        # Column 1: Unified Studio Sidebar (Scenes & Setup tabs)
        self.left_sidebar = self._build_unified_left_sidebar()
        self.setup_sidebar = self.left_sidebar
        self.scenes_sidebar = self.left_sidebar
        self.splitter.addWidget(self.left_sidebar)

        # Column 2: Main area (grid, stretches)
        self.main_area = self._build_main_area()
        self.splitter.addWidget(self.main_area)

        # Column 3: MotionArray & Keywords sidebar (right side)
        self.ma_sidebar = self._build_motionarray_sidebar()
        self.splitter.addWidget(self.ma_sidebar)

        self.splitter.setCollapsible(0, True)
        self.splitter.setCollapsible(1, False)
        self.splitter.setCollapsible(2, True)

        screen = QApplication.primaryScreen()
        screen_w = screen.availableGeometry().width() if screen else 1920
        c1 = 330 if screen_w >= 1400 else 300
        c3 = 290 if screen_w >= 1400 else 260
        c2 = max(550, screen_w - (c1 + c3))
        self.splitter.setSizes([c1, c2, c3])
        self.splitter.splitterMoved.connect(self._on_splitter_moved)

        main_layout.addWidget(self.splitter, 1)

        # Enable Drag & Drop
        self.setAcceptDrops(True)

        # Setup keyboard navigation shortcuts
        self._setup_shortcuts()

        # Enhance hand cursor on all buttons and controls
        enhance_widget_interactions(self)

    def _setup_shortcuts(self):
        # Quick scene navigation (Alt+Left/Right, PgUp/PgDown)
        QShortcut(QKeySequence("Alt+Left"), self, self.select_prev_scene)
        QShortcut(QKeySequence("Alt+Right"), self, self.select_next_scene)
        QShortcut(QKeySequence(Qt.Key.Key_PageUp), self, self.select_prev_scene)
        QShortcut(QKeySequence(Qt.Key.Key_PageDown), self, self.select_next_scene)

        # Quick sidebar toggling (Alt+1, Alt+3)
        QShortcut(QKeySequence("Alt+1"), self, self._toggle_setup_sidebar)
        QShortcut(QKeySequence("Alt+3"), self, self._toggle_ma_sidebar)

        # Scene search focus (Ctrl+F)
        QShortcut(QKeySequence("Ctrl+F"), self, self._focus_search)

        # Quick numerical filter switcher (1: All, 2: Photos, 3: Videos, 4: Selected)
        QShortcut(QKeySequence(Qt.Key.Key_1), self, lambda: self._quick_filter_key("all"))
        QShortcut(QKeySequence(Qt.Key.Key_2), self, lambda: self._quick_filter_key("photos"))
        QShortcut(QKeySequence(Qt.Key.Key_3), self, lambda: self._quick_filter_key("videos"))
        QShortcut(QKeySequence(Qt.Key.Key_4), self, lambda: self._quick_filter_key("selected"))

        # Batch actions (Ctrl+A: Select All in Scene, Ctrl+D: Clear Scene)
        QShortcut(QKeySequence("Ctrl+A"), self, self._select_all_scene)
        QShortcut(QKeySequence("Ctrl+D"), self, self._clear_scene_selection)

        # Quick Random pick & Retry thumbnails
        QShortcut(QKeySequence("Ctrl+R"), self, self._select_random_scene)
        QShortcut(QKeySequence("Ctrl+Shift+R"), self, self._retry_failed_thumbnails)

        # Download shortcut (Ctrl+Return)
        QShortcut(QKeySequence("Ctrl+Return"), self, self.start_download)

        # Open output directory shortcut (Ctrl+Shift+O)
        QShortcut(QKeySequence("Ctrl+Shift+O"), self, self._open_output_folder_in_explorer)

    def _open_output_folder_in_explorer(self):
        output_dir = Path(self.config.get("output_dir") or str(DEFAULT_OUTPUT_DIR))
        output_dir.mkdir(parents=True, exist_ok=True)
        try:
            if os.name == "nt":
                os.startfile(str(output_dir))
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(output_dir)])
            else:
                subprocess.Popen(["xdg-open", str(output_dir)])
            ToastNotification.show_toast(self, f"Đang mở thư mục xuất: {output_dir.name}", "info", 2000)
        except Exception as e:
            ToastNotification.show_toast(self, f"Không thể mở thư mục: {e}", "warning", 2500)

    def _focus_search(self):
        self.scene_search_input.setFocus()
        self.scene_search_input.selectAll()

    def _quick_filter_key(self, filter_type: str):
        fw = QApplication.focusWidget()
        if isinstance(fw, (QLineEdit, QTextEdit)):
            return
        self._set_filter(filter_type)

    def _toggle_setup_sidebar(self):
        sizes = self.splitter.sizes()
        if sizes[0] > 0:
            self._saved_setup_width = sizes[0]
            sizes[1] += sizes[0]
            sizes[0] = 0
            self.splitter.setSizes(sizes)
            self.btn_toggle_setup.setIcon(get_svg_icon("chevron-right", "#818cf8", 12))
            self.btn_toggle_setup.setToolTip("Mở rộng Bảng Điều Khiển (Alt+1)")
            if hasattr(self, "btn_reopen_left"):
                self.btn_reopen_left.setVisible(True)
            ToastNotification.show_toast(self, "Đã thu gọn Bảng Điều Khiển (Alt+1)", "info", 1800)
        else:
            restore_w = getattr(self, "_saved_setup_width", 330) or 330
            sizes[0] = restore_w
            sizes[1] = max(400, sizes[1] - restore_w)
            self.splitter.setSizes(sizes)
            self.btn_toggle_setup.setIcon(get_svg_icon("chevron-left", "#818cf8", 12))
            self.btn_toggle_setup.setToolTip("Thu gọn Bảng Điều Khiển (Alt+1)")
            if hasattr(self, "btn_reopen_left"):
                self.btn_reopen_left.setVisible(False)
            ToastNotification.show_toast(self, "Đã mở lại Bảng Điều Khiển (Alt+1)", "info", 1800)

    def _toggle_ma_sidebar(self):
        sizes = self.splitter.sizes()
        if sizes[2] > 0:
            self._saved_ma_width = sizes[2]
            sizes[1] += sizes[2]
            sizes[2] = 0
            self.splitter.setSizes(sizes)
            self.btn_toggle_ma.setIcon(get_svg_icon("chevron-left", "#fbbf24", 12))
            self.btn_toggle_ma.setToolTip("Mở rộng Từ Khóa & Tải (Alt+3)")
            if hasattr(self, "btn_reopen_right"):
                self.btn_reopen_right.setVisible(True)
            ToastNotification.show_toast(self, "Đã thu gọn Từ Khóa & Tải (Alt+3)", "info", 1800)
        else:
            restore_w = getattr(self, "_saved_ma_width", 290) or 290
            sizes[2] = restore_w
            sizes[1] = max(400, sizes[1] - restore_w)
            self.splitter.setSizes(sizes)
            self.btn_toggle_ma.setIcon(get_svg_icon("chevron-right", "#fbbf24", 12))
            self.btn_toggle_ma.setToolTip("Thu gọn Từ Khóa & Tải (Alt+3)")
            if hasattr(self, "btn_reopen_right"):
                self.btn_reopen_right.setVisible(False)
            ToastNotification.show_toast(self, "Đã mở lại Từ Khóa & Tải (Alt+3)", "info", 1800)

    def _on_splitter_moved(self, pos, index):
        sizes = self.splitter.sizes()
        if hasattr(self, "btn_reopen_left"):
            self.btn_reopen_left.setVisible(sizes[0] == 0)
        if hasattr(self, "btn_reopen_right"):
            self.btn_reopen_right.setVisible(len(sizes) > 2 and sizes[2] == 0)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.toLocalFile().lower().endswith(".json"):
                    event.acceptProposedAction()
                    return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.toLocalFile().lower().endswith(".json"):
                    event.acceptProposedAction()
                    return
        super().dragMoveEvent(event)

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                local_path = url.toLocalFile()
                if local_path.lower().endswith(".json"):
                    event.acceptProposedAction()
                    self._load_json_from_file(local_path)
                    return
        super().dropEvent(event)

    def _load_json_from_file(self, file_path: str):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            scenes = extract_scenes_from_json(data)
            if not scenes:
                ToastNotification.show_toast(self, "File JSON không chứa scenes hợp lệ", "warning", 3000)
                return
            self.load_scenes(scenes, data, file_path)
            file_name = Path(file_path).name
            ToastNotification.show_toast(self, f"Đã nạp {len(scenes)} scenes từ {file_name}", "success", 3000)
        except Exception as e:
            ToastNotification.show_toast(self, f"Lỗi đọc JSON: {str(e)[:45]}", "error", 4000)

    def _section_header(self, text: str, icon_name: Optional[str] = None) -> QWidget:
        container = QWidget()
        h = QHBoxLayout(container)
        h.setContentsMargins(0, 4, 0, 0)
        h.setSpacing(6)
        if icon_name:
            icon_lbl = QLabel()
            icon_lbl.setPixmap(get_svg_pixmap(icon_name, "#818cf8", 12))
            h.addWidget(icon_lbl)
        header = QLabel(text)
        header.setStyleSheet("color: #818cf8; font-size: 10px; font-weight: 800; letter-spacing: 1px;")
        h.addWidget(header)
        h.addStretch()
        return container

    def _build_setup_sidebar(self) -> QWidget:
        return getattr(self, "left_sidebar", None) or self._build_unified_left_sidebar()

    def _build_scenes_sidebar(self) -> QFrame:
        return getattr(self, "left_sidebar", None) or self._build_unified_left_sidebar()

    def _build_unified_left_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setObjectName("studioSidebar")
        sidebar.setMinimumWidth(280)
        sidebar.setMaximumWidth(450)
        sidebar.setStyleSheet("""
            QFrame#studioSidebar {
                background-color: #0c1018;
                border: none;
                border-right: 1px solid #1a2233;
            }
        """)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # ── 1. Top Header Row ──
        header_h = QHBoxLayout()
        header_h.setSpacing(6)
        brand_icon = QLabel()
        brand_icon.setPixmap(get_svg_pixmap("sliders", "#818cf8", 14))
        header_h.addWidget(brand_icon)

        self.brand_title = QLabel("BẢNG ĐIỀU KHIỂN")
        self.brand_title.setStyleSheet("color: #ffffff; font-size: 12px; font-weight: 800; letter-spacing: 0.6px;")
        header_h.addWidget(self.brand_title)

        self.version_badge = QLabel(f"v{APP_VERSION} PRO")
        self.version_badge.setStyleSheet("color: #818cf8; font-size: 10px; font-weight: 800; background: rgba(99, 102, 241, 0.15); padding: 1px 6px; border-radius: 4px; border: 1px solid rgba(99, 102, 241, 0.3);")
        header_h.addWidget(self.version_badge)

        header_h.addStretch()

        self.btn_toggle_setup = QPushButton()
        self.btn_toggle_setup.setIcon(get_svg_icon("chevron-left", "#818cf8", 12))
        self.btn_toggle_setup.setToolTip("Thu gọn Sidebar (Alt+1)")
        self.btn_toggle_setup.setFixedSize(24, 24)
        self.btn_toggle_setup.setStyleSheet("background: rgba(255, 255, 255, 0.06); border: 1px solid #1e293b; border-radius: 6px;")
        self.btn_toggle_setup.clicked.connect(self._toggle_setup_sidebar)
        header_h.addWidget(self.btn_toggle_setup)
        layout.addLayout(header_h)

        # ── 2. Primary Hero Search & Quick Action Buttons ──
        self.search_btn = QPushButton(t("downloader.search_all"))
        self.search_btn.setIcon(get_svg_icon("search", "#ffffff", 15))
        self.search_btn.setObjectName("primaryBtn")
        self.search_btn.setFixedHeight(36)
        self.search_btn.setStyleSheet("QPushButton#primaryBtn { font-size: 12px; font-weight: 800; letter-spacing: 0.5px; }")
        self.search_btn.clicked.connect(self.start_search)
        layout.addWidget(self.search_btn)

        quick_grid = QGridLayout()
        quick_grid.setContentsMargins(0, 0, 0, 0)
        quick_grid.setSpacing(4)

        self.stop_btn = QPushButton(t("common.stop"))
        self.stop_btn.setIcon(get_svg_icon("stop", "#ffffff", 12))
        self.stop_btn.setObjectName("dangerBtn")
        self.stop_btn.setFixedHeight(28)
        self.stop_btn.clicked.connect(self.stop_action)
        self.stop_btn.setEnabled(False)
        quick_grid.addWidget(self.stop_btn, 0, 0)

        self.btn_reset = QPushButton(t("common.reset"))
        self.btn_reset.setIcon(get_svg_icon("trash", "#cbd5e1", 12))
        self.btn_reset.setFixedHeight(28)
        self.btn_reset.clicked.connect(self.reset_all)
        quick_grid.addWidget(self.btn_reset, 0, 1)

        self.btn_open_folder = QPushButton("Thư Mục")
        self.btn_open_folder.setIcon(get_svg_icon("folder", "#ffffff", 12))
        self.btn_open_folder.setToolTip("Mở thư mục xuất (Ctrl+Shift+O)")
        self.btn_open_folder.setFixedHeight(28)
        self.btn_open_folder.clicked.connect(self._open_output_folder_in_explorer)
        quick_grid.addWidget(self.btn_open_folder, 1, 0)

        self.btn_settings = QPushButton(t("downloader.settings_btn"))
        self.btn_settings.setIcon(get_svg_icon("settings", "#e2e8f0", 12))
        self.btn_settings.setToolTip("Cấu hình & Tùy chọn")
        self.btn_settings.setFixedHeight(28)
        self.btn_settings.clicked.connect(self.open_settings_requested.emit)
        quick_grid.addWidget(self.btn_settings, 1, 1)

        layout.addLayout(quick_grid)

        self.json_status_label = QLabel(t("downloader.no_json_status"))
        self.json_status_label.setStyleSheet("""
            color: #94a3b8;
            font-size: 10px;
            font-weight: 600;
            padding: 3px 6px;
            background: #090d14;
            border-radius: 6px;
            border: 1px solid #1e293b;
        """)
        self.json_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.json_status_label.setWordWrap(True)
        layout.addWidget(self.json_status_label)

        # ── 3. Segmented Navigation Tabs (The Sidebar Menu) ──
        tab_nav_row = QHBoxLayout()
        tab_nav_row.setSpacing(4)

        self.btn_tab_scenes = QPushButton("🎬 DANH SÁCH CẢNH")
        self.btn_tab_scenes.setFixedHeight(28)
        self.btn_tab_scenes.setCheckable(True)
        self.btn_tab_scenes.setChecked(True)
        self.btn_tab_scenes.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self.btn_tab_setup = QPushButton("⚙️ API & BỘ LỌC")
        self.btn_tab_setup.setFixedHeight(28)
        self.btn_tab_setup.setCheckable(True)
        self.btn_tab_setup.setChecked(False)
        self.btn_tab_setup.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        tab_style = """
            QPushButton {
                background: #111724;
                color: #94a3b8;
                border: 1px solid #1e293b;
                border-radius: 6px;
                font-size: 10px;
                font-weight: 700;
            }
            QPushButton:hover {
                background: #172133;
                color: #ffffff;
            }
            QPushButton:checked {
                background: #1e293b;
                color: #38bdf8;
                border: 1px solid #38bdf8;
            }
        """
        self.btn_tab_scenes.setStyleSheet(tab_style)
        self.btn_tab_setup.setStyleSheet(tab_style)

        tab_nav_row.addWidget(self.btn_tab_scenes)
        tab_nav_row.addWidget(self.btn_tab_setup)
        layout.addLayout(tab_nav_row)

        # ── 4. Stacked Container ──
        self.sidebar_stack = QStackedWidget()

        # PAGE 0: SCENES TIMELINE
        page_scenes = QWidget()
        scenes_page_layout = QVBoxLayout(page_scenes)
        scenes_page_layout.setContentsMargins(0, 2, 0, 0)
        scenes_page_layout.setSpacing(6)

        # Scene sub-header with nav & counter
        sub_h = QHBoxLayout()
        sub_h.setSpacing(4)
        self.timeline_header = QLabel("Cảnh Timeline")
        self.timeline_header.setStyleSheet("color: #cbd5e1; font-size: 11px; font-weight: 700;")
        sub_h.addWidget(self.timeline_header)

        self.scenes_count_label = QLabel("0 cảnh")
        self.scenes_count_label.setStyleSheet("color: #818cf8; font-size: 10px; font-weight: 800; background: rgba(99, 102, 241, 0.15); padding: 1px 5px; border-radius: 4px;")
        sub_h.addWidget(self.scenes_count_label)
        sub_h.addStretch()

        self.btn_prev_scene = QPushButton()
        self.btn_prev_scene.setIcon(get_svg_icon("chevron-left", "#818cf8", 12))
        self.btn_prev_scene.setToolTip("Cảnh trước (Alt+Left)")
        self.btn_prev_scene.setFixedSize(22, 22)
        self.btn_prev_scene.setStyleSheet("background: rgba(255, 255, 255, 0.05); border: 1px solid #1e293b; border-radius: 4px;")
        self.btn_prev_scene.clicked.connect(self.select_prev_scene)
        sub_h.addWidget(self.btn_prev_scene)

        self.btn_next_scene = QPushButton()
        self.btn_next_scene.setIcon(get_svg_icon("chevron-right", "#818cf8", 12))
        self.btn_next_scene.setToolTip("Cảnh sau (Alt+Right)")
        self.btn_next_scene.setFixedSize(22, 22)
        self.btn_next_scene.setStyleSheet("background: rgba(255, 255, 255, 0.05); border: 1px solid #1e293b; border-radius: 4px;")
        self.btn_next_scene.clicked.connect(self.select_next_scene)
        sub_h.addWidget(self.btn_next_scene)
        scenes_page_layout.addLayout(sub_h)

        # Search scene box
        self.scene_search_input = QLineEdit()
        self.scene_search_input.setFixedHeight(30)
        self.scene_search_input.setPlaceholderText("🔍 Tìm cảnh... (Ctrl+F)")
        self.scene_search_input.textChanged.connect(self._filter_scenes)
        scenes_page_layout.addWidget(self.scene_search_input)

        # Filter buttons
        filter_seg_row = QHBoxLayout()
        filter_seg_row.setSpacing(4)
        self.scene_timeline_filter = "all"
        self.btn_tl_all = QPushButton("Tất Cả")
        self.btn_tl_missing = QPushButton("Thiếu Media")
        self.btn_tl_picked = QPushButton("Đã Chọn")
        for f_btn, f_mode in [(self.btn_tl_all, "all"), (self.btn_tl_missing, "missing"), (self.btn_tl_picked, "picked")]:
            f_btn.setFixedHeight(22)
            f_btn.setCheckable(True)
            f_btn.setChecked(f_mode == "all")
            f_btn.setStyleSheet("""
                QPushButton {
                    background: #111724;
                    color: #94a3b8;
                    border: 1px solid #1e293b;
                    border-radius: 4px;
                    font-size: 10px;
                    font-weight: 700;
                    padding: 0 4px;
                }
                QPushButton:checked {
                    background: #1e293b;
                    color: #38bdf8;
                    border-color: #38bdf8;
                }
            """)
            f_btn.clicked.connect(lambda checked, m=f_mode: self._set_timeline_filter(m))
            filter_seg_row.addWidget(f_btn)
        scenes_page_layout.addLayout(filter_seg_row)

        # Scenes Scroll Area
        self.scenes_scroll = QScrollArea()
        self.scenes_scroll.setWidgetResizable(True)
        self.scenes_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scenes_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scenes_scroll.setStyleSheet("QScrollArea { background-color: #090d14; border: 1px solid #1e293b; border-radius: 8px; }")
        self.scenes_container = QWidget()
        self.scenes_layout = QVBoxLayout(self.scenes_container)
        self.scenes_layout.setContentsMargins(4, 4, 4, 4)
        self.scenes_layout.setSpacing(4)
        self.scenes_layout.addStretch()
        self.scenes_scroll.setWidget(self.scenes_container)
        scenes_page_layout.addWidget(self.scenes_scroll, 1)

        # Scene info drawer
        info_h = QHBoxLayout()
        info_h.setSpacing(4)
        info_icon = QLabel()
        info_icon.setPixmap(get_svg_pixmap("file-text", "#94a3b8", 12))
        info_h.addWidget(info_icon)
        self.info_header = QLabel("CHI TIẾT CẢNH ĐANG CHỌN")
        self.info_header.setStyleSheet("color: #94a3b8; font-size: 10px; font-weight: 800; letter-spacing: 0.6px;")
        info_h.addWidget(self.info_header)
        info_h.addStretch()
        scenes_page_layout.addLayout(info_h)

        self.scene_info_panel = QTextEdit()
        self.scene_info_panel.setReadOnly(True)
        self.scene_info_panel.setFixedHeight(95)
        self.scene_info_panel.setStyleSheet("""
            QTextEdit {
                background-color: #090d14;
                color: #cbd5e1;
                border: 1px solid #1e293b;
                border-radius: 8px;
                padding: 6px;
                font-size: 11px;
                line-height: 1.3;
            }
        """)
        self.scene_info_panel.setPlainText("Chọn cảnh trong danh sách để xem chi tiết.")
        scenes_page_layout.addWidget(self.scene_info_panel)

        self.sidebar_stack.addWidget(page_scenes)

        # PAGE 1: SETUP & API KEYS
        page_setup = QScrollArea()
        page_setup.setWidgetResizable(True)
        page_setup.setFrameShape(QFrame.Shape.NoFrame)
        page_setup.setStyleSheet("background: transparent; border: none;")
        setup_container = QWidget()
        setup_page_layout = QVBoxLayout(setup_container)
        setup_page_layout.setContentsMargins(0, 4, 0, 0)
        setup_page_layout.setSpacing(10)

        # API Key Manager Widget
        self.api_key_widget = ApiKeyManagerWidget(self.config_repo, parent=self)
        self.api_key_widget.keysChanged.connect(self._on_api_keys_changed)
        setup_page_layout.addWidget(self.api_key_widget)

        # Search Options
        setup_page_layout.addWidget(self._section_header(t("downloader.search_options"), "settings"))
        search_prefs = self.config.get("search_prefs", {
            "photos": True,
            "videos": True,
            "source": "Pexels + Pixabay",
        })

        source_row = QHBoxLayout()
        self.source_lbl = QLabel(t("downloader.source_label"))
        self.source_lbl.setStyleSheet("color: #cbd5e1; font-weight: 600; font-size: 11px;")
        source_row.addWidget(self.source_lbl)

        self.search_source_combo = QComboBox()
        self.search_source_combo.addItems([
            "Pexels + Pixabay",
            "Pexels + Pixabay + Vecteezy",
            "Chỉ Pexels",
            "Chỉ Pixabay",
            "Chỉ Vecteezy"
        ])
        idx = self.search_source_combo.findText(search_prefs.get("source", "Pexels + Pixabay"))
        if idx >= 0:
            self.search_source_combo.setCurrentIndex(idx)
        self.search_source_combo.currentTextChanged.connect(self._save_search_prefs)
        source_row.addWidget(self.search_source_combo, 1)
        setup_page_layout.addLayout(source_row)

        chk_row = QHBoxLayout()
        self.search_photos_check = QCheckBox(t("downloader.find_photos"))
        self.search_photos_check.setChecked(search_prefs.get("photos", True))
        self.search_photos_check.toggled.connect(self._save_search_prefs)
        chk_row.addWidget(self.search_photos_check)

        self.search_videos_check = QCheckBox(t("downloader.find_videos"))
        self.search_videos_check.setChecked(search_prefs.get("videos", True))
        self.search_videos_check.toggled.connect(self._save_search_prefs)
        chk_row.addWidget(self.search_videos_check)
        setup_page_layout.addLayout(chk_row)

        # Status Panel
        setup_page_layout.addWidget(self._section_header("TRẠNG THÁI TIẾN TRÌNH", "activity"))
        self.status_panel = StatusPanel()
        setup_page_layout.addWidget(self.status_panel)

        setup_page_layout.addStretch()
        page_setup.setWidget(setup_container)
        self.sidebar_stack.addWidget(page_setup)

        layout.addWidget(self.sidebar_stack, 1)

        # Tab Switching Connectors
        def _switch_to_scenes():
            self.btn_tab_scenes.setChecked(True)
            self.btn_tab_setup.setChecked(False)
            self.sidebar_stack.setCurrentIndex(0)

        def _switch_to_setup():
            self.btn_tab_scenes.setChecked(False)
            self.btn_tab_setup.setChecked(True)
            self.sidebar_stack.setCurrentIndex(1)

        self.btn_tab_scenes.clicked.connect(_switch_to_scenes)
        self.btn_tab_setup.clicked.connect(_switch_to_setup)

        return sidebar

    def _on_api_keys_changed(self):
        """Slot triggered when API keys are added, deleted, or toggled in SQLite."""
        if self.config_repo:
            self.config = self.config_repo.load_config()
        self.status_message.emit(t("status.keys_updated"), 3000)

    def _build_main_area(self) -> QFrame:
        area = QFrame()
        area.setObjectName("mainArea")

        layout = QVBoxLayout(area)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Stats bar
        stats_h = QHBoxLayout()
        stats_h.setSpacing(12)

        self.stat_scene = StatBox("-", "CẢNH HIỆN TẠI", STAT_COLOR_BLUE)
        stats_h.addWidget(self.stat_scene)
        self.stat_total = StatBox(0, "TỔNG MEDIA CẢNH", STAT_COLOR_PURPLE)
        stats_h.addWidget(self.stat_total)
        self.stat_selected_scene = StatBox(0, "ĐÃ CHỌN TRONG CẢNH", STAT_COLOR_RED)
        stats_h.addWidget(self.stat_selected_scene)
        self.stat_selected_total = StatBox(0, "TỔNG ĐÃ CHỌN", STAT_COLOR_GREEN)
        stats_h.addWidget(self.stat_selected_total)

        layout.addLayout(stats_h)

        # Filter + Action bar
        action_h = QHBoxLayout()
        action_h.setSpacing(6)

        # Reopen Left button (visible when left sidebar collapsed)
        self.btn_reopen_left = QPushButton("⮞ Bảng Điều Khiển")
        self.btn_reopen_left.setIcon(get_svg_icon("sliders", "#818cf8", 12))
        self.btn_reopen_left.setFixedHeight(32)
        self.btn_reopen_left.setVisible(False)
        self.btn_reopen_left.setToolTip("Mở lại Bảng Điều Khiển (Alt+1)")
        self.btn_reopen_left.setStyleSheet("""
            QPushButton {
                background: #1e293b;
                color: #818cf8;
                border: 1px solid #818cf8;
                border-radius: 6px;
                font-weight: 700;
                font-size: 11px;
                padding: 0 8px;
            }
            QPushButton:hover {
                background: #27354a;
                color: #ffffff;
            }
        """)
        self.btn_reopen_left.clicked.connect(self._toggle_setup_sidebar)
        action_h.addWidget(self.btn_reopen_left)

        self.filter_buttons = {}
        filter_meta = [
            ("all", t("downloader.filter_all"), None, "1"),
            ("photos", t("downloader.filter_photos"), "image", "2"),
            ("videos", t("downloader.filter_videos"), "video", "3"),
            ("selected", t("downloader.filter_selected"), "check", "4")
        ]
        for fkey, label, icon_name, sc_key in filter_meta:
            btn = QPushButton(label)
            if icon_name:
                btn.setIcon(get_svg_icon(icon_name, "#ffffff", 12))
            btn.setFixedHeight(30)
            btn.setObjectName("filterActive" if fkey == "all" else "filterInactive")
            btn.setStyleSheet("""
                QPushButton {
                    padding: 0 8px;
                    font-size: 11px;
                    font-weight: 700;
                }
            """)
            btn.setToolTip(format_tooltip(f"Lọc {label.lower()}", sc_key))
            btn.clicked.connect(lambda checked, k=fkey: self._set_filter(k))
            action_h.addWidget(btn)
            self.filter_buttons[fkey] = btn

        action_h.addStretch()

        self.random_count_spin = QSpinBox()
        self.random_count_spin.setRange(1, 999)
        self.random_count_spin.setValue(1)
        self.random_count_spin.setFixedHeight(30)
        self.random_count_spin.setMinimumWidth(50)
        self.random_count_spin.setToolTip(format_tooltip("Số media muốn chọn ngẫu nhiên", "1-999"))
        lbl_qty = QLabel("SL:")
        lbl_qty.setStyleSheet("font-weight: 700; font-size: 11px; color: #94a3b8;")
        action_h.addWidget(lbl_qty)
        action_h.addWidget(self.random_count_spin)

        self.btn_random_select = QPushButton("Ngẫu nhiên")
        self.btn_random_select.setIcon(get_svg_icon("shuffle", "#ffffff", 12))
        self.btn_random_select.setObjectName("purpleBtn")
        self.btn_random_select.setFixedHeight(30)
        self.btn_random_select.setStyleSheet("QPushButton#purpleBtn { padding: 0 8px; font-size: 11px; font-weight: 700; }")
        self.btn_random_select.setToolTip(format_tooltip("Chọn ngẫu nhiên media trong cảnh", "Ctrl+R"))
        self.btn_random_select.clicked.connect(self._select_random_scene)
        action_h.addWidget(self.btn_random_select)

        btn_retry = QPushButton("Làm mới")
        btn_retry.setIcon(get_svg_icon("refresh", "#fbbf24", 12))
        btn_retry.setObjectName("warningBtn")
        btn_retry.setFixedHeight(30)
        btn_retry.setStyleSheet("QPushButton#warningBtn { padding: 0 8px; font-size: 11px; font-weight: 700; }")
        btn_retry.setToolTip(format_tooltip("Tải lại ảnh thu nhỏ bị lỗi", "Ctrl+Shift+R"))
        btn_retry.clicked.connect(self._retry_failed_thumbnails)
        action_h.addWidget(btn_retry)

        btn_select_all = QPushButton("Chọn hết")
        btn_select_all.setIcon(get_svg_icon("check", "#ffffff", 12))
        btn_select_all.setObjectName("secondaryBtn")
        btn_select_all.setFixedHeight(30)
        btn_select_all.setStyleSheet("QPushButton#secondaryBtn { padding: 0 8px; font-size: 11px; font-weight: 700; }")
        btn_select_all.setToolTip(format_tooltip("Chọn tất cả media trong cảnh này", "Ctrl+A"))
        btn_select_all.clicked.connect(self._select_all_scene)
        action_h.addWidget(btn_select_all)

        self.btn_clear = QPushButton(t("downloader.clear_all_picks"))
        self.btn_clear.setIcon(get_svg_icon("x", "#ffffff", 12))
        self.btn_clear.setObjectName("dangerBtn")
        self.btn_clear.setFixedHeight(30)
        self.btn_clear.setStyleSheet("QPushButton#dangerBtn { padding: 0 8px; font-size: 11px; font-weight: 700; }")
        self.btn_clear.setToolTip(format_tooltip("Bỏ chọn toàn bộ trong cảnh này", "Ctrl+D"))
        self.btn_clear.clicked.connect(self._clear_scene_selection)
        action_h.addWidget(self.btn_clear)

        self.btn_download = QPushButton(t("downloader.download_selected"))
        self.btn_download.setIcon(get_svg_icon("download", "#ffffff", 12))
        self.btn_download.setObjectName("successBtn")
        self.btn_download.setFixedHeight(30)
        self.btn_download.setStyleSheet("QPushButton#successBtn { padding: 0 10px; font-size: 11px; font-weight: 800; letter-spacing: 0.2px; }")
        self.btn_download.setToolTip(format_tooltip(t("downloader.download_selected"), "Ctrl+Enter"))
        self.btn_download.clicked.connect(self.start_download)
        action_h.addWidget(self.btn_download)

        self.btn_next_step = QPushButton("Tiếp tục ➔")
        self.btn_next_step.setIcon(get_svg_icon("mic", "#ffffff", 12))
        self.btn_next_step.setObjectName("accentBtn")
        self.btn_next_step.setFixedHeight(30)
        self.btn_next_step.setStyleSheet("""
            QPushButton#accentBtn {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6366f1, stop:1 #8b5cf6);
                color: #ffffff;
                font-size: 11px;
                font-weight: 800;
                padding: 0 10px;
                border-radius: 6px;
                border: 1px solid rgba(255,255,255,0.18);
            }
            QPushButton#accentBtn:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4f46e5, stop:1 #7c3aed);
            }
        """)
        self.btn_next_step.setToolTip(format_tooltip("Chuyển sang Bước 2: Tạo giọng đọc AI & Phụ đề SRT", "Ctrl+2"))
        self.btn_next_step.clicked.connect(lambda: self.nextStepRequested.emit())
        action_h.addWidget(self.btn_next_step)

        # Reopen Right button (visible when ma sidebar collapsed)
        self.btn_reopen_right = QPushButton("Từ Khóa & Tải ⮜")
        self.btn_reopen_right.setIcon(get_svg_icon("film", "#fbbf24", 12))
        self.btn_reopen_right.setFixedHeight(32)
        self.btn_reopen_right.setVisible(False)
        self.btn_reopen_right.setToolTip("Mở lại Từ Khóa & Giám Sát Tải (Alt+3)")
        self.btn_reopen_right.setStyleSheet("""
            QPushButton {
                background: #1e293b;
                color: #fbbf24;
                border: 1px solid rgba(245, 158, 11, 0.4);
                border-radius: 6px;
                font-weight: 700;
                font-size: 11px;
                padding: 0 8px;
            }
            QPushButton:hover {
                background: #27354a;
                color: #ffffff;
            }
        """)
        self.btn_reopen_right.clicked.connect(self._toggle_ma_sidebar)
        action_h.addWidget(self.btn_reopen_right)

        layout.addLayout(action_h)

        # Grid container
        self.grid_scroll = QScrollArea()
        self.grid_scroll.setWidgetResizable(True)
        self.grid_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.grid_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.grid_scroll.setStyleSheet("""
            QScrollArea {
                background-color: transparent;
                border: none;
            }
            QScrollBar:vertical {
                background-color: #161b22;
                width: 10px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background-color: #30363d;
                border-radius: 5px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #484f58;
            }
        """)

        self.grid_container = QWidget()
        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_layout.setSpacing(10)
        self.grid_layout.setContentsMargins(0, 0, 0, 0)
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        self.grid_scroll.setWidget(self.grid_container)
        layout.addWidget(self.grid_scroll, 1)

        # Placeholder
        self.placeholder_label = QLabel("Chọn cảnh ở danh sách bên trái\nhoặc bấm 'TÌM TẤT CẢ' để bắt đầu")
        self.placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.placeholder_label.setStyleSheet("color: #484f58; font-size: 14px; padding: 100px;")
        self.grid_layout.addWidget(self.placeholder_label, 0, 0, GRID_ROWS, GRID_COLS)

        # Pagination bar
        pag_h = QHBoxLayout()

        self.prev_btn = QPushButton("Trang trước")
        self.prev_btn.setIcon(get_svg_icon("chevron-left", "#ffffff", 12))
        self.prev_btn.setEnabled(False)
        self.prev_btn.clicked.connect(self._prev_page)
        pag_h.addWidget(self.prev_btn)

        self.page_label = QLabel("Trang 0/0")
        self.page_label.setStyleSheet("color: #e6edf3; font-size: 13px; font-weight: 600;")
        self.page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pag_h.addWidget(self.page_label, 1)

        self.next_btn = QPushButton("Trang sau")
        self.next_btn.setIcon(get_svg_icon("chevron-right", "#ffffff", 12))
        self.next_btn.setEnabled(False)
        self.next_btn.clicked.connect(self._next_page)
        pag_h.addWidget(self.next_btn)

        layout.addLayout(pag_h)

        return area

    def _build_motionarray_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setObjectName("maSidebar")

        sidebar.setMinimumWidth(260)
        sidebar.setMaximumWidth(400)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # MotionArray Card
        ma_frame = QFrame()
        ma_frame.setStyleSheet("""
            QFrame {
                background-color: #131926;
                border: 1px solid rgba(245, 158, 11, 0.4);
                border-radius: 10px;
            }
        """)
        ma_layout = QVBoxLayout(ma_frame)
        ma_layout.setContentsMargins(10, 10, 10, 10)
        ma_layout.setSpacing(6)

        ma_header_h = QHBoxLayout()
        ma_header_h.setSpacing(6)

        ma_icon = QLabel()
        ma_icon.setPixmap(get_svg_pixmap("film", "#fbbf24", 13))
        ma_header_h.addWidget(ma_icon)

        ma_header = QLabel("TỪ KHÓA TÌM KIẾM")
        ma_header.setStyleSheet("color: #fbbf24; font-size: 11px; font-weight: 800; letter-spacing: 0.5px; background: transparent; border: none;")
        ma_header_h.addWidget(ma_header)
        ma_header_h.addStretch()

        self.btn_toggle_ma = QPushButton()
        self.btn_toggle_ma.setIcon(get_svg_icon("chevron-right", "#fbbf24", 12))
        self.btn_toggle_ma.setToolTip("Thu gọn (Alt+3)")
        self.btn_toggle_ma.setFixedSize(22, 22)
        self.btn_toggle_ma.setStyleSheet("background: rgba(245, 158, 11, 0.1); border: 1px solid rgba(245, 158, 11, 0.3); border-radius: 4px;")
        self.btn_toggle_ma.clicked.connect(self._toggle_ma_sidebar)
        ma_header_h.addWidget(self.btn_toggle_ma)
        ma_layout.addLayout(ma_header_h)

        kw_btn_row = QHBoxLayout()
        kw_btn_row.setSpacing(4)

        btn_select_all_kw = QPushButton("Tất cả")
        btn_select_all_kw.setIcon(get_svg_icon("check", "#fbbf24", 11))
        btn_select_all_kw.setStyleSheet("""
            QPushButton {
                background-color: rgba(245, 158, 11, 0.15);
                color: #fbbf24;
                border: 1px solid rgba(245, 158, 11, 0.3);
                border-radius: 4px;
                padding: 2px 6px;
                font-size: 10px;
                font-weight: 700;
            }
            QPushButton:hover { background-color: rgba(245, 158, 11, 0.3); }
        """)
        btn_select_all_kw.setFixedHeight(22)
        btn_select_all_kw.clicked.connect(self._ma_select_all_keywords)
        kw_btn_row.addWidget(btn_select_all_kw)

        btn_select_none_kw = QPushButton("Bỏ chọn")
        btn_select_none_kw.setIcon(get_svg_icon("x", "#94a3b8", 11))
        btn_select_none_kw.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #94a3b8;
                border: 1px solid #334155;
                border-radius: 4px;
                padding: 2px 6px;
                font-size: 10px;
                font-weight: 700;
            }
            QPushButton:hover { background-color: #334155; color: #ffffff; }
        """)
        btn_select_none_kw.setFixedHeight(22)
        btn_select_none_kw.clicked.connect(self._ma_select_no_keywords)
        kw_btn_row.addWidget(btn_select_none_kw)

        btn_copy_kw = QPushButton("Sao chép")
        btn_copy_kw.setIcon(get_svg_icon("copy", "#38bdf8", 11))
        btn_copy_kw.setToolTip("Sao chép danh sách từ khóa đang chọn vào clipboard")
        btn_copy_kw.setStyleSheet("""
            QPushButton {
                background-color: rgba(56, 189, 248, 0.15);
                color: #38bdf8;
                border: 1px solid rgba(56, 189, 248, 0.3);
                border-radius: 4px;
                padding: 2px 6px;
                font-size: 10px;
                font-weight: 700;
            }
            QPushButton:hover { background-color: rgba(56, 189, 248, 0.3); color: #ffffff; }
        """)
        btn_copy_kw.setFixedHeight(22)
        btn_copy_kw.clicked.connect(self._ma_copy_all_keywords)
        kw_btn_row.addWidget(btn_copy_kw)
        ma_layout.addLayout(kw_btn_row)

        ma_instr = QLabel("Chọn từ khóa để tìm trên web:")
        ma_instr.setStyleSheet("color: #94a3b8; font-size: 10px; font-weight: 600; background: transparent; border: none;")
        ma_layout.addWidget(ma_instr)

        # Keywords list
        self.ma_keywords_scroll = QScrollArea()
        self.ma_keywords_scroll.setWidgetResizable(True)
        self.ma_keywords_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.ma_keywords_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.ma_keywords_scroll.setStyleSheet("""
            QScrollArea {
                background-color: #0c0f17;
                border: 1px solid #1e293b;
                border-radius: 6px;
            }
        """)

        self.ma_keywords_container = QWidget()
        self.ma_keywords_layout = QVBoxLayout(self.ma_keywords_container)
        self.ma_keywords_layout.setContentsMargins(6, 6, 6, 6)
        self.ma_keywords_layout.setSpacing(4)

        self.ma_keywords_placeholder = QLabel("Chọn cảnh để xem từ khóa")
        self.ma_keywords_placeholder.setStyleSheet("color: #64748b; font-size: 11px; padding: 25px 8px; background: transparent;")
        self.ma_keywords_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ma_keywords_placeholder.setWordWrap(True)
        self.ma_keywords_layout.addWidget(self.ma_keywords_placeholder)
        self.ma_keywords_layout.addStretch()

        self.ma_keywords_scroll.setWidget(self.ma_keywords_container)
        ma_layout.addWidget(self.ma_keywords_scroll, 1)

        # Status
        self.ma_status_label = QLabel("Chưa chọn cảnh")
        self.ma_status_label.setStyleSheet("""
            color: #94a3b8;
            font-size: 10px;
            padding: 3px 6px;
            background-color: #0c0f17;
            border-radius: 4px;
            border: 1px solid #1e293b;
        """)
        self.ma_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ma_status_label.setFixedHeight(24)
        ma_layout.addWidget(self.ma_status_label)

        # Button mở tab MotionArray
        self.btn_motionarray = QPushButton("Tìm MotionArray")
        self.btn_motionarray.setIcon(get_svg_icon("search", "#ffffff", 14))
        self.btn_motionarray.setEnabled(False)
        self.btn_motionarray.setToolTip("Mở tìm kiếm MotionArray với các từ khóa đã tick")
        self.btn_motionarray.clicked.connect(self._open_motionarray_search)
        self.btn_motionarray.setFixedHeight(36)
        self.btn_motionarray.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #d97706, stop:1 #f59e0b);
                color: #ffffff;
                font-weight: 800;
                font-size: 11px;
                padding: 6px;
                border-radius: 6px;
                border: none;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #b45309, stop:1 #d97706);
            }
            QPushButton:disabled {
                background-color: #1e293b;
                color: #64748b;
                border: 1px solid #334155;
            }
        """)
        ma_layout.addWidget(self.btn_motionarray)

        self.ma_watcher_label = QLabel("")
        self.ma_watcher_label.setStyleSheet("color: #64748b; font-size: 9px; background: transparent; border: none;")
        self.ma_watcher_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ma_watcher_label.setWordWrap(True)
        self.ma_watcher_label.setMaximumHeight(18)
        ma_layout.addWidget(self.ma_watcher_label)

        layout.addWidget(ma_frame, 2)

        # Download Monitor Card
        dm_frame = QFrame()
        dm_frame.setStyleSheet("""
            QFrame {
                background-color: #131926;
                border: 1px solid rgba(16, 185, 129, 0.4);
                border-radius: 10px;
            }
        """)
        dm_layout = QVBoxLayout(dm_frame)
        dm_layout.setContentsMargins(10, 10, 10, 10)
        dm_layout.setSpacing(6)

        dm_header_h = QHBoxLayout()
        dm_header_h.setSpacing(6)
        dm_icon = QLabel()
        dm_icon.setPixmap(get_svg_pixmap("download", "#34d399", 14))
        dm_header_h.addWidget(dm_icon)
        self.dm_header = QLabel(t("downloader.download_progress"))
        self.dm_header.setStyleSheet("color: #34d399; font-size: 12px; font-weight: 800; letter-spacing: 0.5px; background: transparent; border: none;")
        dm_header_h.addWidget(self.dm_header)
        dm_header_h.addStretch()

        btn_dm_refresh = QPushButton()
        btn_dm_refresh.setIcon(get_svg_icon("refresh", "#34d399", 14))
        btn_dm_refresh.setToolTip(t("downloader.scan_output_tooltip"))
        btn_dm_refresh.setFixedSize(26, 22)
        btn_dm_refresh.setStyleSheet("""
            QPushButton {
                background-color: rgba(16, 185, 129, 0.15);
                color: #34d399;
                border: 1px solid rgba(16, 185, 129, 0.3);
                border-radius: 4px;
            }
            QPushButton:hover { background-color: rgba(16, 185, 129, 0.3); }
        """)
        btn_dm_refresh.clicked.connect(self.refresh_download_monitor)
        dm_header_h.addWidget(btn_dm_refresh)
        dm_layout.addLayout(dm_header_h)

        self.dm_summary_label = QLabel("0 scenes có file • 0 files tổng")
        self.dm_summary_label.setStyleSheet("""
            color: #cbd5e1;
            font-size: 10px;
            font-weight: 600;
            padding: 4px 6px;
            background-color: #0c0f17;
            border-radius: 4px;
            border: 1px solid #1e293b;
        """)
        self.dm_summary_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.dm_summary_label.setWordWrap(True)
        dm_layout.addWidget(self.dm_summary_label)

        self.dm_scroll = QScrollArea()
        self.dm_scroll.setWidgetResizable(True)
        self.dm_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.dm_scroll.setStyleSheet("""
            QScrollArea {
                background-color: #0c0f17;
                border: 1px solid #1e293b;
                border-radius: 6px;
            }
        """)

        self.dm_container = QWidget()
        self.dm_container_layout = QVBoxLayout(self.dm_container)
        self.dm_container_layout.setContentsMargins(4, 4, 4, 4)
        self.dm_container_layout.setSpacing(3)

        self.dm_placeholder = QLabel("Chưa có scenes\n(Load JSON trước)")
        self.dm_placeholder.setStyleSheet("color: #64748b; font-size: 11px; padding: 25px 8px; background: transparent;")
        self.dm_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.dm_placeholder.setWordWrap(True)
        self.dm_container_layout.addWidget(self.dm_placeholder)
        self.dm_container_layout.addStretch()

        self.dm_scroll.setWidget(self.dm_container)
        dm_layout.addWidget(self.dm_scroll, 1)

        # Timer for monitor refresh
        self.dm_refresh_timer = QTimer(self)
        self.dm_refresh_timer.timeout.connect(self.refresh_download_monitor)
        self.dm_refresh_timer.start(3000)

        layout.addWidget(dm_frame, 3)
        return sidebar

    # ═══════════════════════════════════════════════════════════════
    # DATA BINDING & STATE
    # ═══════════════════════════════════════════════════════════════

    def load_scenes(self, scenes: list, json_data: dict = None, file_path: str = ""):
        """Loads scene data into the timeline and resets UI state."""
        self.scenes = scenes or []
        self.json_data = json_data
        if file_path:
            self.file_path = file_path
        self.scene_items = {s.get("id"): [] for s in self.scenes}
        self.selected_items = {s.get("id"): {} for s in self.scenes}
        self.current_scene_id = None
        self.current_page = 0

        # Update JSON status pill
        if self.scenes:
            self.json_status_label.setText(t("downloader.loaded_json_status", count=len(self.scenes)))
            self.json_status_label.setStyleSheet("""
                color: #34d399;
                font-size: 10px;
                font-weight: 700;
                padding: 4px 8px;
                background: rgba(16, 185, 129, 0.1);
                border-radius: 6px;
                border: 1px solid rgba(16, 185, 129, 0.3);
            """)
        else:
            self.json_status_label.setText(t("downloader.no_json_status"))
            self.json_status_label.setStyleSheet("""
                color: #94a3b8;
                font-size: 10px;
                font-weight: 600;
                padding: 4px 8px;
                background: #0c0f17;
                border-radius: 6px;
                border: 1px solid #1e293b;
            """)

        self._populate_scene_list()
        self._clear_grid()
        self._show_empty_placeholder()
        self.refresh_download_monitor()
        self._save_state()

        if self.scenes:
            self._on_scene_clicked(self.scenes[0])
            self.json_loaded.emit(self.json_data or {}, self.scenes, getattr(self, "file_path", ""))

    def restore_state(self, state: dict):
        """Restores scenes and downloaded items from saved state."""
        if not state:
            return
        self.scenes = state.get("scenes", [])
        self.json_data = state.get("json_data")
        self.scene_items = state.get("scene_items", {})
        self.selected_items = state.get("selected_items", {})
        self.current_scene_id = state.get("current_scene_id")

        if self.scenes:
            self.json_status_label.setText(t("downloader.loaded_json_status", count=len(self.scenes)))
            self.json_status_label.setStyleSheet("""
                color: #34d399;
                font-size: 10px;
                font-weight: 700;
                padding: 4px 8px;
                background: rgba(16, 185, 129, 0.1);
                border-radius: 6px;
                border: 1px solid rgba(16, 185, 129, 0.3);
            """)
            self._populate_scene_list()
            active_scene = next(
                (s for s in self.scenes if s.get("id") == self.current_scene_id),
                self.scenes[0]
            )
            self._on_scene_clicked(active_scene)
            self.refresh_download_monitor()

    def _save_state(self):
        if self.state_repo:
            try:
                self.state_repo.save_state({
                    "scenes": self.scenes,
                    "json_data": self.json_data,
                    "scene_items": self.scene_items,
                    "selected_items": self.selected_items,
                    "current_scene_id": self.current_scene_id,
                })
            except Exception:
                pass

    def _save_search_prefs(self):
        self.config["search_prefs"] = {
            "photos": self.search_photos_check.isChecked(),
            "videos": self.search_videos_check.isChecked(),
            "source": self.search_source_combo.currentText(),
        }
        if self.config_repo:
            try:
                self.config_repo.save_config(self.config)
            except Exception:
                pass

    def _set_timeline_filter(self, mode: str):
        self.scene_timeline_filter = mode
        if hasattr(self, "btn_tl_all"):
            self.btn_tl_all.setChecked(mode == "all")
        if hasattr(self, "btn_tl_missing"):
            self.btn_tl_missing.setChecked(mode == "missing")
        if hasattr(self, "btn_tl_picked"):
            self.btn_tl_picked.setChecked(mode == "picked")
        self._populate_scene_list()

    def _populate_scene_list(self):
        for widget in self.scene_list_widgets:
            widget.setParent(None)
            widget.deleteLater()
        self.scene_list_widgets = []

        search_text = self.scene_search_input.text().lower()
        tl_filter = getattr(self, "scene_timeline_filter", "all")
        filtered = []
        for scene in self.scenes:
            sid = scene.get("id")
            selected_count = len(self.selected_items.get(sid, {}))
            if tl_filter == "missing" and selected_count > 0:
                continue
            if tl_filter == "picked" and selected_count == 0:
                continue
            if search_text:
                dialogue = scene.get("dialogue_es", "") or scene.get("dialogue", "")
                kw = " ".join(scene.get("primary_keywords", []))
                if (search_text not in dialogue.lower() and
                    search_text not in kw.lower() and
                    search_text not in str(scene.get("id", ""))):
                    continue
            filtered.append(scene)

        total_picked = sum(1 for s in self.scenes if len(self.selected_items.get(s.get("id"), {})) > 0)
        self.scenes_count_label.setText(f"{len(filtered)}/{len(self.scenes)} cảnh (Đạt: {total_picked})")

        stretch_idx = self.scenes_layout.count() - 1
        for scene in filtered:
            is_active = (self.current_scene_id == scene.get("id"))
            item = SceneListItem(scene, is_active=is_active)
            item.clicked.connect(self._on_scene_clicked)

            scene_id = scene.get("id")
            items_count = len(self.scene_items.get(scene_id, []))
            selected_count = len(self.selected_items.get(scene_id, {}))
            item.update_stats(items_count, selected_count)

            self.scenes_layout.insertWidget(stretch_idx, item)
            self.scene_list_widgets.append(item)
            stretch_idx += 1

    def _filter_scenes(self):
        self._populate_scene_list()

    def _on_scene_clicked(self, scene: dict):
        scene_id = scene.get("id")
        self.current_scene_id = scene_id
        self.current_page = 0
        self.current_filter = "all"

        for widget in self.scene_list_widgets:
            widget.set_active(str(widget.scene.get("id")) == str(scene_id))

        for fkey, btn in self.filter_buttons.items():
            btn.setObjectName("filterActive" if fkey == "all" else "filterInactive")

        self.stat_scene.set_value(f"#{scene_id}")
        self._update_scene_info_panel(scene)
        self._populate_ma_keywords(scene)
        self._render_grid()
        self._update_stats()
        self._save_state()

    def select_next_scene(self):
        """Advances active scene to the next one, updating timeline and grid."""
        if not self.scenes:
            return
        idx = 0
        if self.current_scene_id is not None:
            for i, sc in enumerate(self.scenes):
                if sc.get("id") == self.current_scene_id:
                    idx = (i + 1) % len(self.scenes)
                    break
        self._on_scene_clicked(self.scenes[idx])
        self._scroll_timeline_to_active()

    def select_prev_scene(self):
        """Reverts active scene to the previous one, updating timeline and grid."""
        if not self.scenes:
            return
        idx = 0
        if self.current_scene_id is not None:
            for i, sc in enumerate(self.scenes):
                if sc.get("id") == self.current_scene_id:
                    idx = (i - 1 + len(self.scenes)) % len(self.scenes)
                    break
        self._on_scene_clicked(self.scenes[idx])
        self._scroll_timeline_to_active()

    def _scroll_timeline_to_active(self):
        """Scrolls the scene list scroll area to ensure the active scene card is in view."""
        for item in self.scene_list_widgets:
            if item.scene.get("id") == self.current_scene_id:
                self.scenes_scroll.ensureWidgetVisible(item)
                break

    def _on_theme_changed(self, theme_name: str):
        """Refreshes scene card styles and info panel when theme toggles."""
        if self.current_scene_id is not None:
            sc = next((s for s in self.scenes if str(s.get("id")) == str(self.current_scene_id)), None)
            if sc:
                self._update_scene_info_panel(sc)
        for widget in self.scene_list_widgets:
            widget._update_style()

    def _update_scene_info_panel(self, scene: dict):
        time_start = scene.get("time_start", "?")
        time_end = scene.get("time_end", "?")
        duration = scene.get("duration_seconds", 0)
        desc_vi = scene.get("description_vi", "") or scene.get("mo_ta", "")
        dialogue = scene.get("dialogue_es", "") or scene.get("dialogue_vi", "") or scene.get("dialogue", "")
        context = scene.get("context_summary_en", "") or scene.get("context_summary", "")
        primary = scene.get("primary_keywords", []) or []
        mood = scene.get("mood", "")
        shot = scene.get("shot_type", "")

        is_dark = ThemeManager.get_instance().is_dark()
        text_primary = "#cbd5e1" if is_dark else "#1e293b"
        text_muted = "#94a3b8" if is_dark else "#64748b"
        quote_bg = "#111724" if is_dark else "#f8fafc"
        quote_border = "#6366f1"
        quote_title = "#f8fafc" if is_dark else "#334155"
        quote_text = "#f1f5f9" if is_dark else "#0f172a"
        time_color = "#38bdf8" if is_dark else "#0284c7"
        badge_bg = "rgba(99, 102, 241, 0.25)" if is_dark else "rgba(99, 102, 241, 0.12)"
        badge_border = "rgba(99, 102, 241, 0.4)" if is_dark else "rgba(99, 102, 241, 0.3)"
        chip_bg = "#182234" if is_dark else "#f1f5f9"
        chip_border = "#243048" if is_dark else "#cbd5e1"
        chip_color = "#a78bfa" if is_dark else "#4f46e5"
        mood_color = "#fbbf24" if is_dark else "#d97706"
        shot_color = "#38bdf8" if is_dark else "#0284c7"

        html = f"""
        <div style="font-family: 'Segoe UI', sans-serif; font-size: 11px; line-height: 1.5; color: {text_primary};">
            <div style="margin-bottom: 8px;">
                <span style="background: {badge_bg}; color: #818cf8; font-weight: 800; font-size: 10px; padding: 2px 6px; border-radius: 4px; border: 1px solid {badge_border};">SCENE #{scene.get('id')}</span>
                <span style="color: {time_color}; font-weight: 700; margin-left: 6px;">⏱ {time_start} → {time_end} ({duration}s)</span>
            </div>
        """
        if dialogue:
            html += f"""
            <div style="background: {quote_bg}; border-left: 3px solid {quote_border}; border-radius: 4px; padding: 6px 8px; margin: 6px 0; border-top: 1px solid {'#1e293b' if is_dark else '#e2e8f0'}; border-right: 1px solid {'#1e293b' if is_dark else '#e2e8f0'}; border-bottom: 1px solid {'#1e293b' if is_dark else '#e2e8f0'};">
                <b style="color: {quote_title}; font-size: 10px; text-transform: uppercase;">Lời thoại:</b><br/>
                <span style="color: {quote_text}; font-style: italic;">{dialogue}</span>
            </div>
            """
        if desc_vi:
            html += f"""
            <div style="margin: 6px 0;">
                <b style="color: {text_muted}; font-size: 10px; text-transform: uppercase;">Mô tả cảnh:</b><br/>
                <span style="color: {text_primary};">{desc_vi}</span>
            </div>
            """
        if context:
            html += f"""
            <div style="margin: 6px 0;">
                <b style="color: {text_muted}; font-size: 10px; text-transform: uppercase;">Bối cảnh:</b><br/>
                <span style="color: {text_primary};">{context}</span>
            </div>
            """
        if primary:
            chips = "".join([f"<span style='background: {chip_bg}; color: {chip_color}; border: 1px solid {chip_border}; border-radius: 4px; padding: 1px 5px; margin-right: 4px; font-weight: 600; font-size: 10px;'>{k}</span>" for k in primary[:5]])
            html += f"""
            <div style="margin-top: 8px;">
                <b style="color: {'#818cf8' if is_dark else '#4f46e5'}; font-size: 10px; text-transform: uppercase;">Từ khóa chính:</b><br/>
                <div style="margin-top: 3px;">{chips}</div>
            </div>
            """
        extras = []
        if mood: extras.append(f"Cảm xúc: <b style='color:{mood_color};'>{mood}</b>")
        if shot: extras.append(f"Góc quay: <b style='color:{shot_color};'>{shot}</b>")
        if extras:
            html += f"<div style='margin-top: 6px; font-size: 10px; color: {text_muted};'>{' • '.join(extras)}</div>"

        html += "</div>"
        self.scene_info_panel.setHtml(html)

    # ═══════════════════════════════════════════════════════════════
    # MOTIONARRAY & KEYWORDS
    # ═══════════════════════════════════════════════════════════════

    def _populate_ma_keywords(self, scene: dict):
        for cb in self.ma_keyword_checks:
            cb.setParent(None)
            cb.deleteLater()
        self.ma_keyword_checks = []

        if hasattr(self, 'ma_keywords_placeholder') and self.ma_keywords_placeholder:
            try:
                self.ma_keywords_placeholder.setParent(None)
                self.ma_keywords_placeholder.deleteLater()
            except Exception:
                pass
            self.ma_keywords_placeholder = None

        scene_id = scene.get("id")
        primary = scene.get("primary_keywords") or []
        secondary = scene.get("secondary_keywords") or []

        seen = set()
        all_keywords = []
        for kw in (primary + secondary):
            if not kw:
                continue
            k = kw.strip()
            if k.lower() in seen:
                continue
            seen.add(k.lower())
            all_keywords.append((k, kw in primary))

        if not all_keywords:
            self.ma_status_label.setText(f"Scene #{scene_id} chưa có keyword")
            self.btn_motionarray.setEnabled(False)
            self.ma_keywords_placeholder = QLabel(f"Scene #{scene_id} không có keyword")
            self.ma_keywords_placeholder.setStyleSheet("color: #6e7681; font-size: 11px; padding: 20px; background: transparent;")
            self.ma_keywords_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.ma_keywords_layout.insertWidget(0, self.ma_keywords_placeholder)
            return

        for idx, (kw, is_primary) in enumerate(all_keywords):
            label_prefix = "[PRI]" if is_primary else "•"
            cb = QCheckBox(f"{label_prefix} {kw}")
            cb.setChecked(True)
            cb.setProperty("keyword", kw)
            cb.setProperty("is_primary", is_primary)
            cb.toggled.connect(self._ma_update_button_text)
            cb.setMinimumHeight(28)

            color = "#f39c12" if is_primary else "#c9d1d9"
            weight = "700" if is_primary else "500"
            bg_unchecked = "#1f1612" if is_primary else "#161b22"

            cb.setStyleSheet(f"""
                QCheckBox {{
                    color: {color};
                    font-size: 12px;
                    font-weight: {weight};
                    padding: 6px 8px;
                    background-color: {bg_unchecked};
                    border-radius: 4px;
                    spacing: 8px;
                    border: 1px solid transparent;
                }}
                QCheckBox:hover {{
                    background-color: #21262d;
                    border: 1px solid #f39c12;
                }}
            """)
            self.ma_keywords_layout.insertWidget(idx, cb)
            self.ma_keyword_checks.append(cb)

        self.btn_motionarray.setEnabled(True)
        self._ma_update_button_text()

    def _ma_update_button_text(self):
        checked = sum(1 for cb in self.ma_keyword_checks if cb.isChecked())
        total = len(self.ma_keyword_checks)
        if checked == 0:
            self.btn_motionarray.setText("(Chưa chọn keyword)")
            self.btn_motionarray.setIcon(get_svg_icon("search", "#94a3b8", 14))
            self.btn_motionarray.setEnabled(False)
        else:
            self.btn_motionarray.setText(f"Mở {checked} tab MotionArray")
            self.btn_motionarray.setIcon(get_svg_icon("search", "#ffffff", 14))
            self.btn_motionarray.setEnabled(True)

        self.ma_status_label.setText(f"Đã chọn {checked}/{total} keywords")

    def _ma_select_all_keywords(self):
        for cb in self.ma_keyword_checks:
            cb.setChecked(True)

    def _ma_select_no_keywords(self):
        for cb in self.ma_keyword_checks:
            cb.setChecked(False)

    def _ma_copy_all_keywords(self):
        selected_keywords = [
            cb.property("keyword") for cb in self.ma_keyword_checks if cb.isChecked() and cb.property("keyword")
        ]
        if not selected_keywords:
            selected_keywords = [
                cb.property("keyword") for cb in self.ma_keyword_checks if cb.property("keyword")
            ]
        if selected_keywords:
            kw_str = ", ".join(selected_keywords)
            QApplication.clipboard().setText(kw_str)
            ToastNotification.show_toast(self, f"Đã chép {len(selected_keywords)} từ khóa vào bộ nhớ tạm!", "success", 2000)
        else:
            ToastNotification.show_toast(self, "Không có từ khóa nào để sao chép", "warning", 2000)

    def _find_coccoc_path(self) -> Optional[str]:
        possible_paths = [
            os.path.expandvars(r"%LOCALAPPDATA%\CocCoc\Browser\Application\browser.exe"),
            os.path.expandvars(r"%PROGRAMFILES%\CocCoc\Browser\Application\browser.exe"),
            os.path.expandvars(r"%PROGRAMFILES(X86)%\CocCoc\Browser\Application\browser.exe"),
            r"C:\Users\%USERNAME%\AppData\Local\CocCoc\Browser\Application\browser.exe",
        ]
        for p in possible_paths:
            expanded = os.path.expandvars(p)
            if os.path.exists(expanded):
                return expanded
        return None

    def _open_motionarray_search(self):
        if not self.current_scene_id:
            QMessageBox.information(self, "Chưa chọn cảnh", "Vui lòng chọn một cảnh trước khi tìm kiếm.")
            return

        selected_keywords = [
            cb.property("keyword") for cb in self.ma_keyword_checks if cb.isChecked() and cb.property("keyword")
        ]
        if not selected_keywords:
            QMessageBox.information(self, "Chưa chọn từ khóa", "Vui lòng chọn ít nhất một từ khóa để tìm kiếm.")
            return

        self._current_ma_scene_id = self.current_scene_id

        if not self._watcher_started and self.downloads_watcher:
            self.downloads_watcher.start()
            self._watcher_started = True
            self.ma_watcher_label.setText(f"Đang theo dõi: {self.downloads_watcher.downloads_dir}")
            self.ma_watcher_label.setStyleSheet("color: #2ecc71; font-size: 9px; padding: 2px;")

        if len(selected_keywords) > 5:
            reply = QMessageBox.question(
                self, "Xác nhận mở nhiều tab",
                f"Cảnh #{self.current_scene_id}: sẽ mở {len(selected_keywords)} tab trình duyệt. Bạn có muốn tiếp tục?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        coccoc_path = self._find_coccoc_path()
        from urllib.parse import quote_plus
        opened = 0
        for kw in selected_keywords:
            try:
                encoded = quote_plus(kw)
                url = f"https://motionarray.com/browse/stock-video/?q={encoded}"
                if coccoc_path:
                    subprocess.Popen([coccoc_path, url])
                else:
                    import webbrowser
                    webbrowser.open(url, new=2)
                opened += 1
                time.sleep(0.3)
            except Exception as e:
                print(f"[MotionArray] Error opening tab '{kw}': {e}")

        browser_name = "Cốc Cốc" if coccoc_path else "browser mặc định"
        if opened > 0:
            self.ma_status_label.setText(f"Đã mở {opened} tab {browser_name}")
            self.status_message.emit(f"MotionArray: mở {opened} tab ({browser_name}) cho scene #{self.current_scene_id}", 4000)
            self.status_panel.add_log(f"MotionArray: mở {opened} tab cho scene #{self.current_scene_id}", "info")

    def _on_download_detected(self, filepath: str):
        if not self.scenes:
            return

        filename = os.path.basename(filepath)
        dialog = AssignSceneDialog(
            filename=filename,
            scenes=self.scenes,
            suggested_scene_id=self._current_ma_scene_id,
            parent=self
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        if dialog.action == "skip":
            self.status_message.emit(f"Bỏ qua file: {filename}", 3000)
        elif dialog.action == "delete":
            try:
                os.remove(filepath)
                self.status_message.emit(f"Đã xóa: {filename}", 3000)
            except Exception as e:
                QMessageBox.warning(self, "Lỗi xóa file", str(e))
        elif dialog.action == "assign":
            self._move_file_to_scene(filepath, dialog.selected_scene_id)

    def _move_file_to_scene(self, src_path: str, scene_id: Any):
        try:
            scene = next((s for s in self.scenes if s.get("id") == scene_id), None)
            if not scene:
                return

            output_dir = self.config.get("output_dir") or str(DEFAULT_OUTPUT_DIR)
            output_base = Path(output_dir)
            output_base.mkdir(parents=True, exist_ok=True)

            scene_id_str = str(scene_id).zfill(3) if isinstance(scene_id, int) else str(scene_id)
            ts_start = scene.get("timestamp_start") or scene.get("time_start") or "00-00-00"
            ts_safe = ts_start.replace(":", "-").replace(",", "-").replace(".", "-")
            scene_prefix = f"{scene_id_str}_{ts_safe}"

            existing = list(output_base.glob(f"{scene_prefix}_motionarray_*"))
            next_num = len(existing) + 1
            src = Path(src_path)
            dest_path = output_base / f"{scene_prefix}_motionarray_{next_num:03d}{src.suffix.lower()}"

            while dest_path.exists():
                next_num += 1
                dest_path = output_base / f"{scene_prefix}_motionarray_{next_num:03d}{src.suffix.lower()}"

            import shutil
            shutil.move(str(src), str(dest_path))

            self.status_message.emit(f"Đã sắp xếp: {dest_path.name} → cảnh #{scene_id}", 4000)
            self.refresh_download_monitor()
        except Exception as e:
            QMessageBox.critical(self, "Lỗi di chuyển file", f"Không thể di chuyển file:\n{e}")

    # ═══════════════════════════════════════════════════════════════
    # DOWNLOAD MONITOR
    # ═══════════════════════════════════════════════════════════════

    def refresh_download_monitor(self):
        if not hasattr(self, 'dm_container_layout') or not self.scenes:
            return

        output_dir = Path(self.config.get("output_dir") or str(DEFAULT_OUTPUT_DIR))
        if not output_dir.exists():
            self._dm_clear_rows()
            self.dm_summary_label.setText("0 scenes • 0 files")
            return

        if hasattr(self, 'dm_placeholder') and self.dm_placeholder is not None:
            try:
                self.dm_placeholder.setParent(None)
                self.dm_placeholder.deleteLater()
                self.dm_placeholder = None
            except Exception:
                pass

        scene_counts = {}
        for scene in self.scenes:
            sid = scene.get("id")
            if sid is None:
                continue
            scene_counts[sid] = {
                'pexels_video': 0, 'pexels_photo': 0, 'ma_video': 0, 'other': 0,
                'folder': output_dir, 'scene': scene
            }

        for f in output_dir.iterdir():
            if not f.is_file() or f.name.startswith("_"):
                continue
            m = re.match(r'^(\d{3})_', f.name)
            if not m:
                continue
            try:
                sid = int(m.group(1))
            except ValueError:
                continue
            if sid not in scene_counts:
                continue

            name_lower = f.name.lower()
            if '_pexels_video_' in name_lower and name_lower.endswith(('.mp4', '.mov')):
                scene_counts[sid]['pexels_video'] += 1
            elif '_pexels_photo_' in name_lower and name_lower.endswith(('.jpg', '.jpeg', '.png', '.webp')):
                scene_counts[sid]['pexels_photo'] += 1
            elif '_motionarray_' in name_lower:
                scene_counts[sid]['ma_video'] += 1
            elif name_lower.endswith(('.mp4', '.mov', '.jpg', '.jpeg', '.png', '.webp')):
                scene_counts[sid]['other'] += 1

        scenes_with_files = 0
        total_files = 0
        for sid, info in scene_counts.items():
            n_pv = info['pexels_video']
            n_pp = info['pexels_photo']
            n_ma = info['ma_video']
            n_other = info['other']
            tot = n_pv + n_pp + n_ma + n_other
            self._dm_update_scene_row(sid, info['scene'], n_pv, n_pp, n_ma, n_other, info['folder'])
            if tot > 0:
                scenes_with_files += 1
                total_files += tot

        total_scenes = len(self.scenes)
        color = "#4ec9b0" if (scenes_with_files == total_scenes and total_scenes > 0) else ("#f39c12" if scenes_with_files > 0 else "#7d8590")
        self.dm_summary_label.setText(f"{scenes_with_files}/{total_scenes} scenes • {total_files} files")
        self.dm_summary_label.setStyleSheet(f"color: {color}; font-size: 10px; font-weight: 600; padding: 4px 6px; background-color: #0d1117; border-radius: 3px;")

    def _dm_clear_rows(self):
        for row in list(self.dm_scene_rows.values()):
            try:
                row.setParent(None)
                row.deleteLater()
            except Exception:
                pass
        self.dm_scene_rows = {}

    def _dm_update_scene_row(self, scene_id, scene, n_pv, n_pp, n_ma, n_other, folder_path):
        total = n_pv + n_pp + n_ma + n_other
        time_start = scene.get("time_start", "?")

        if total == 0:
            status_icon_name, status_color, status_bg = "x", "#7d8590", "#161b22"
            detail_text = "chưa có file"
        elif total < 3:
            status_icon_name, status_color, status_bg = "alert-triangle", "#f39c12", "#1f1612"
            parts = [f"{n_pv}V"] if n_pv else []
            if n_pp: parts.append(f"{n_pp}P")
            if n_ma: parts.append(f"{n_ma}MA")
            if n_other: parts.append(f"{n_other}?")
            detail_text = f"{total} files ({', '.join(parts)})"
        else:
            status_icon_name, status_color, status_bg = "check", "#4ec9b0", "#0f1f15"
            parts = [f"{n_pv}V"] if n_pv else []
            if n_pp: parts.append(f"{n_pp}P")
            if n_ma: parts.append(f"{n_ma}MA")
            if n_other: parts.append(f"{n_other}?")
            detail_text = f"{total} files ({', '.join(parts)})"

        if scene_id not in self.dm_scene_rows:
            row = QFrame()
            row.setStyleSheet(f"QFrame {{ background-color: {status_bg}; border: 1px solid #21262d; border-radius: 4px; }} QFrame:hover {{ border: 1px solid {status_color}; }}")
            row.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            r_lay = QHBoxLayout(row)
            r_lay.setContentsMargins(6, 4, 6, 4)
            r_lay.setSpacing(4)

            icon_lbl = QLabel()
            icon_lbl.setObjectName("statusIcon")
            icon_lbl.setPixmap(get_svg_pixmap(status_icon_name, status_color, 12))
            icon_lbl.setFixedWidth(20)
            r_lay.addWidget(icon_lbl)

            info_lbl = QLabel(f"<b>#{scene_id}</b>  {time_start}")
            info_lbl.setStyleSheet("color: #c9d1d9; font-size: 10px; background: transparent; border: none;")
            r_lay.addWidget(info_lbl)

            r_lay.addStretch()

            count_lbl = QLabel(detail_text)
            count_lbl.setObjectName("countLbl")
            count_lbl.setStyleSheet(f"color: {status_color}; font-size: 10px; font-weight: 600; background: transparent; border: none;")
            r_lay.addWidget(count_lbl)

            def on_dm_row_click(event, sc=scene, p=folder_path):
                if event.button() == Qt.MouseButton.LeftButton:
                    self._on_scene_clicked(sc)
                    self._scroll_timeline_to_active()
                elif event.button() == Qt.MouseButton.RightButton:
                    if p.exists():
                        os.startfile(str(p)) if os.name == 'nt' else subprocess.Popen(["xdg-open", str(p)])
            row.mousePressEvent = on_dm_row_click
            row.setToolTip(f"Bấm chuột trái: chuyển tới Scene #{scene_id}\nBấm chuột phải: mở thư mục lưu")

            insert_idx = 0
            for i in range(self.dm_container_layout.count()):
                w = self.dm_container_layout.itemAt(i).widget()
                if w and w.property("scene_id") is not None and w.property("scene_id") > scene_id:
                    break
                insert_idx = i + 1

            row.setProperty("scene_id", scene_id)
            self.dm_container_layout.insertWidget(insert_idx, row)
            self.dm_scene_rows[scene_id] = row
        else:
            row = self.dm_scene_rows[scene_id]
            row.setStyleSheet(f"QFrame {{ background-color: {status_bg}; border: 1px solid #21262d; border-radius: 4px; }} QFrame:hover {{ border: 1px solid {status_color}; }}")
            icon_lbl = row.findChild(QLabel, "statusIcon")
            if icon_lbl:
                icon_lbl.setPixmap(get_svg_pixmap(status_icon_name, status_color, 12))
            count_lbl = row.findChild(QLabel, "countLbl")
            if count_lbl:
                count_lbl.setText(detail_text)
                count_lbl.setStyleSheet(f"color: {status_color}; font-size: 10px; font-weight: 600; background: transparent; border: none;")

    # ═══════════════════════════════════════════════════════════════
    # GRID & THUMBNAIL RENDERING
    # ═══════════════════════════════════════════════════════════════

    def _set_filter(self, filter_key: str):
        self.current_filter = filter_key
        for fkey, btn in self.filter_buttons.items():
            btn.setObjectName("filterActive" if fkey == filter_key else "filterInactive")
            btn.setStyleSheet("")
        self.current_page = 0
        self._render_grid()

    def _get_current_items(self) -> list:
        if self.current_scene_id is None:
            return []
        return self.scene_items.get(self.current_scene_id, [])

    def _apply_filter(self, items: list) -> list:
        if self.current_filter == "photos":
            return [i for i in items if i.get("type") == "photo"]
        elif self.current_filter == "videos":
            return [i for i in items if i.get("type") == "video"]
        elif self.current_filter == "selected":
            sel_dict = self.selected_items.get(self.current_scene_id, {})
            return [i for i in items if self._get_item_key(i) in sel_dict]
        return items

    def _update_filter_counts(self):
        """Updates count badges on filter tab buttons."""
        all_items = self._get_current_items()
        total_count = len(all_items)
        photos_count = sum(1 for i in all_items if i.get("type") == "photo")
        videos_count = sum(1 for i in all_items if i.get("type") == "video")
        sel_count = len(self.selected_items.get(self.current_scene_id, {}))

        if "all" in self.filter_buttons:
            self.filter_buttons["all"].setText(f"{t('downloader.filter_all')} ({total_count})")
        if "photos" in self.filter_buttons:
            self.filter_buttons["photos"].setText(f"{t('downloader.filter_photos')} ({photos_count})")
        if "videos" in self.filter_buttons:
            self.filter_buttons["videos"].setText(f"{t('downloader.filter_videos')} ({videos_count})")
        if "selected" in self.filter_buttons:
            self.filter_buttons["selected"].setText(f"{t('downloader.filter_selected')} ({sel_count})")

    def _clear_grid(self):
        for card in self.thumb_cards:
            card.setParent(None)
            card.deleteLater()
        self.thumb_cards = []
        self.url_to_cards = {}
        if hasattr(self, 'placeholder_label') and self.placeholder_label:
            try:
                self.placeholder_label.setParent(None)
            except Exception:
                pass

    def _show_empty_placeholder(self):
        self._clear_grid()
        box = QFrame()
        box.setObjectName("dragDropOverlay")
        box_layout = QVBoxLayout(box)
        box_layout.setContentsMargins(40, 60, 40, 60)
        box_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        box_layout.setSpacing(12)

        icon_lbl = QLabel()
        icon_lbl.setPixmap(get_svg_pixmap("film", "#6366f1", 44))
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        box_layout.addWidget(icon_lbl)

        txt_lbl = QLabel(t("downloader.empty_select_scene"))
        txt_lbl.setStyleSheet("color: #f1f5f9; font-size: 15px; font-weight: 700; background: transparent; border: none;")
        txt_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        box_layout.addWidget(txt_lbl)

        hint_lbl = QLabel("Mẹo: Kéo thả file kịch bản (.json) vào đây • Dùng Alt+Left/Right để chuyển cảnh")
        hint_lbl.setStyleSheet("color: #94a3b8; font-size: 11px; background: transparent; border: none;")
        hint_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        box_layout.addWidget(hint_lbl)

        self.placeholder_label = box
        self.grid_layout.addWidget(self.placeholder_label, 0, 0, GRID_ROWS, GRID_COLS)
        self._update_pagination()
        self._update_filter_counts()

    def _render_grid(self):
        self._clear_grid()
        self._update_filter_counts()

        if self.current_scene_id is None:
            self._show_empty_placeholder()
            return

        all_items = self._get_current_items()
        filtered = self._apply_filter(all_items)

        if not filtered:
            box = QFrame()
            box.setStyleSheet("background-color: #0c0f17; border: 1px dashed #2d3748; border-radius: 12px;")
            box_layout = QVBoxLayout(box)
            box_layout.setContentsMargins(30, 50, 30, 50)
            box_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            box_layout.setSpacing(10)

            icon_lbl = QLabel()
            icon_lbl.setPixmap(get_svg_pixmap("search", "#64748b", 36))
            icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            box_layout.addWidget(icon_lbl)

            lbl = QLabel(f"Cảnh #{self.current_scene_id} chưa có media phù hợp với bộ lọc\nBấm 'TÌM TẤT CẢ' hoặc đổi bộ lọc để xem media")
            lbl.setStyleSheet("color: #94a3b8; font-size: 12px; font-weight: 600; line-height: 1.5; background: transparent; border: none;")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            box_layout.addWidget(lbl)

            self.placeholder_label = box
            self.grid_layout.addWidget(self.placeholder_label, 0, 0, GRID_ROWS, GRID_COLS)
            self._update_pagination(total=0)
            return

        start = self.current_page * ITEMS_PER_PAGE
        page_items = filtered[start:start + ITEMS_PER_PAGE]
        selected_in_scene = self.selected_items.get(self.current_scene_id, {})

        for idx, item in enumerate(page_items):
            row = idx // GRID_COLS
            col = idx % GRID_COLS
            item_key = self._get_item_key(item)
            is_selected = item_key in selected_in_scene

            card = ThumbnailCard(item, is_selected=is_selected)
            card.selectionChanged.connect(self._on_item_select)
            card.clicked.connect(self._show_preview_modal)
            card.retryRequested.connect(self._on_card_retry)

            self.grid_layout.addWidget(card, row, col)
            self.thumb_cards.append(card)

            thumb_url = item.get("thumb_url")
            if thumb_url and self.thumbnail_cache and self.thumb_loader:
                pixmap = self.thumbnail_cache.get_pixmap(thumb_url)
                if pixmap:
                    card.set_thumbnail(pixmap)
                else:
                    self.url_to_cards.setdefault(thumb_url, []).append(card)
                    self.thumb_loader.load_async(thumb_url)

        self._update_pagination(total=len(filtered))

    def _on_card_retry(self, item: dict):
        for card in self.thumb_cards:
            try:
                if card.item.get("id") == item.get("id") and card.thumb_failed:
                    card.reset_to_loading()
                    url = item.get("thumb_url")
                    if url and self.thumb_loader:
                        self.url_to_cards.setdefault(url, []).append(card)
                        self.thumb_loader.load_async(url)
                    break
            except RuntimeError:
                pass

    def _on_thumbnail_loaded(self, url: str, pixmap):
        cards = self.url_to_cards.get(url, [])
        for card in cards:
            try:
                card.set_thumbnail(pixmap)
            except RuntimeError:
                pass
        if url in self.url_to_cards:
            del self.url_to_cards[url]

    def _on_thumbnail_failed(self, url: str):
        cards = self.url_to_cards.get(url, [])
        for card in cards:
            try:
                card.set_failed_state()
            except RuntimeError:
                pass
        if url in self.url_to_cards:
            del self.url_to_cards[url]

    def _retry_failed_thumbnails(self):
        retry_count = 0
        for card in self.thumb_cards:
            try:
                if card.thumb_failed and self.thumb_loader:
                    card.reset_to_loading()
                    url = card.item.get("thumb_url")
                    if url:
                        self.thumb_loader.load_async(url)
                        self.url_to_cards.setdefault(url, []).append(card)
                        retry_count += 1
            except RuntimeError:
                pass
        if retry_count > 0:
            self.status_message.emit(f"⟳ Đang retry {retry_count} thumbnails...", 3000)

    def _update_pagination(self, total: Optional[int] = None):
        if total is None:
            filtered = self._apply_filter(self._get_current_items())
            total = len(filtered)
        total_pages = max(1, (total + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)
        current = self.current_page + 1
        self.page_label.setText(f"Trang {current}/{total_pages} ({total} items)")
        self.prev_btn.setEnabled(self.current_page > 0)
        self.next_btn.setEnabled(self.current_page < total_pages - 1)

    def _prev_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self._render_grid()

    def _next_page(self):
        filtered = self._apply_filter(self._get_current_items())
        total_pages = (len(filtered) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
        if self.current_page < total_pages - 1:
            self.current_page += 1
            self._render_grid()

    def _get_item_key(self, item: dict) -> str:
        return f"{item.get('source')}_{item.get('type')}_{item.get('id')}"

    def _on_item_select(self, item: dict, is_selected: bool):
        if self.current_scene_id is None:
            return
        sid = self.current_scene_id
        if sid not in self.selected_items:
            self.selected_items[sid] = {}
        key = self._get_item_key(item)
        if is_selected:
            self.selected_items[sid][key] = item
        else:
            self.selected_items[sid].pop(key, None)

        self._update_stats()
        self._update_scene_list_item(sid)
        self._save_state()

    def _update_scene_list_item(self, scene_id: Any):
        for widget in self.scene_list_widgets:
            if str(widget.scene.get("id")) == str(scene_id):
                widget.update_stats(
                    len(self.scene_items.get(scene_id, []) or self.scene_items.get(widget.scene.get("id"), [])),
                    len(self.selected_items.get(scene_id, {}) or self.selected_items.get(widget.scene.get("id"), {}))
                )
                break

    def _update_stats(self):
        if self.current_scene_id is None:
            self.stat_total.set_value(0)
            self.stat_selected_scene.set_value(0)
        else:
            self.stat_total.set_value(len(self.scene_items.get(self.current_scene_id, [])))
            self.stat_selected_scene.set_value(len(self.selected_items.get(self.current_scene_id, {})))
        total_selected = sum(len(s) for s in self.selected_items.values())
        self.stat_selected_total.set_value(total_selected)
        self.selection_changed.emit(total_selected)

        # Dynamic CTA visual count feedback
        if hasattr(self, "btn_download"):
            if total_selected > 0:
                self.btn_download.setText(f"TẢI MEDIA ĐÃ CHỌN ({total_selected})")
            else:
                self.btn_download.setText(t("downloader.download_selected"))

    def _select_all_scene(self):
        if self.current_scene_id is None:
            return
        sid = self.current_scene_id
        items = self._apply_filter(self._get_current_items())
        if sid not in self.selected_items:
            self.selected_items[sid] = {}
        for item in items:
            self.selected_items[sid][self._get_item_key(item)] = item
        self._render_grid()
        self._update_stats()
        self._update_scene_list_item(sid)
        self._save_state()
        ToastNotification.show_toast(self, f"Đã chọn {len(items)} media cho Cảnh #{sid}", "success", 2000)

    def _select_random_scene(self):
        if self.current_scene_id is None:
            QMessageBox.information(self, "Chưa chọn cảnh", "Vui lòng chọn một cảnh trước khi chọn ngẫu nhiên.")
            return
        sid = self.current_scene_id
        items = self._apply_filter(self._get_current_items())
        if not items:
            QMessageBox.information(self, "Không có media", "Bộ lọc hiện tại chưa có media phù hợp để chọn.")
            return

        count = min(self.random_count_spin.value(), len(items))
        picked = random.sample(items, count)
        self.selected_items[sid] = {self._get_item_key(item): item for item in picked}

        self.status_message.emit(t("downloader.random_selected", count=count, total=len(items), sid=sid), 4000)
        self._render_grid()
        self._update_stats()
        self._update_scene_list_item(sid)
        self._save_state()
        ToastNotification.show_toast(self, f"Đã chọn ngẫu nhiên {count} media cho Cảnh #{sid}", "success", 2000)

    def auto_random_all_scenes(self, count: int = 1):
        """Randomly selects N items for every scene."""
        for scene in self.scenes:
            sid = scene.get("id")
            items = self.scene_items.get(sid, [])
            if not items:
                continue
            k = min(count, len(items))
            picked = random.sample(items, k)
            self.selected_items[sid] = {self._get_item_key(item): item for item in picked}
            self._update_scene_list_item(sid)

        self._render_grid()
        self._update_stats()
        self._save_state()

    def _clear_scene_selection(self):
        if self.current_scene_id is None:
            return
        sid = self.current_scene_id
        if sid in self.selected_items:
            self.selected_items[sid] = {}
        self._render_grid()
        self._update_stats()
        self._update_scene_list_item(sid)
        self._save_state()
        ToastNotification.show_toast(self, f"Đã bỏ chọn tất cả media của Cảnh #{sid}", "info", 2000)

    def _show_preview_modal(self, item: dict):
        modal = PreviewModal(item, self.thumbnail_cache, parent=self)
        modal.exec()

    # ═══════════════════════════════════════════════════════════════
    # SEARCH WORKER EXECUTION
    # ═══════════════════════════════════════════════════════════════

    def start_search(self):
        if not self.scenes:
            QMessageBox.warning(self, "Chưa có kịch bản", "Vui lòng nạp kịch bản trước khi tìm kiếm")
            return
        if not self.search_photos_check.isChecked() and not self.search_videos_check.isChecked():
            QMessageBox.warning(self, "Chưa chọn loại", "Vui lòng chọn ít nhất Ảnh hoặc Video")
            return

        source_mode = self.search_source_combo.currentText()
        source_lower = source_mode.lower()
        needs_pexels = "pexels" in source_lower or "+" in source_lower
        needs_pixabay = "pixabay" in source_lower or "+" in source_lower
        needs_vecteezy = "vecteezy" in source_lower or "+" in source_lower

        has_source_key = (
            (needs_pexels and self.config.get("pexels_keys")) or
            (needs_pixabay and self.config.get("pixabay_keys")) or
            (needs_vecteezy and self.config.get("vecteezy_keys"))
        )
        if not has_source_key:
            QMessageBox.warning(self, "Thiếu API Key", f"Thêm API key cho nguồn: {source_mode}")
            return

        if not self.search_photos_check.isChecked() and not self.search_videos_check.isChecked():
            QMessageBox.warning(self, "Chưa chọn loại media", "Vui lòng chọn ít nhất một định dạng: Ảnh hoặc Video.")
            return

        if any(self.scene_items.values()):
            reply = QMessageBox.question(
                self, "Đã có data", "Đã có data từ trước. Search lại sẽ ghi đè?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        self.scene_items = {s.get("id"): [] for s in self.scenes}
        self._completed_search_scenes = set()
        self._render_grid()
        self._update_stats()
        self._populate_scene_list()

        km = KeyManager(
            self.config.get("pexels_keys", []),
            self.config.get("pixabay_keys", []),
            [],
            self.config.get("vecteezy_keys", []),
            config_repo=self.config_repo
        )

        self.search_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.stop_btn.setText(t("downloader.stop_search"))
        self.stop_btn.setIcon(get_svg_icon("stop", "#ffffff", 14))

        self.status_panel.set_searching("Đang khởi tạo...")
        self.status_panel.add_log(f"Bắt đầu search {len(self.scenes)} scenes", "info")
        self.status_panel.update_counters(0, len(self.scenes), 0, 0)

        self.search_worker = SearchWorker(
            self.scenes, km,
            self.search_photos_check.isChecked(),
            self.search_videos_check.isChecked(),
            source_mode
        )
        self.search_worker.sceneCompleted.connect(self._on_scene_results)
        self.search_worker.progress.connect(self._on_search_progress)
        self.search_worker.finished_signal.connect(self._on_search_finished)
        self.search_worker.start()

    def _on_scene_results(self, scene_id: Any, items: list):
        self.scene_items[scene_id] = items
        if not hasattr(self, "_completed_search_scenes"):
            self._completed_search_scenes = set()
        self._completed_search_scenes.add(str(scene_id))
        self._update_scene_list_item(scene_id)

        if items:
            self.status_panel.add_log(f"Scene #{scene_id}: tìm thấy {len(items)} items", "success")
        else:
            self.status_panel.add_log(f"Scene #{scene_id}: 0 items", "warning")

        done = len(self._completed_search_scenes)
        total = len(self.scenes)
        total_items = sum(len(it) for it in self.scene_items.values())
        total_selected = sum(len(it) for it in self.selected_items.values())
        self.status_panel.update_counters(done, total, total_items, total_selected)
        self.status_panel.set_progress(done, total)

        if self.current_scene_id is None and items:
            scene = next((s for s in self.scenes if s.get("id") == scene_id), None)
            if scene:
                self._on_scene_clicked(scene)
        elif self.current_scene_id == scene_id:
            self._render_grid()
            self._update_stats()

    def _on_search_progress(self, message: str):
        self.status_message.emit(message, 0)
        self.status_panel.progress_label.setText(message)

    def _on_search_finished(self):
        self.search_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setText(t("common.stop"))
        self.stop_btn.setIcon(get_svg_icon("stop", "#ffffff", 14))
        self._save_state()

        total_items = sum(len(it) for it in self.scene_items.values())
        self.status_message.emit(f"Search xong: {total_items} items", 4000)
        self.status_panel.set_idle(f"Search xong: {total_items} items")
        self.status_panel.add_log(f"Search hoàn tất: {total_items} items", "success")
        self.search_finished.emit()

    # ═══════════════════════════════════════════════════════════════
    # DOWNLOAD WORKER EXECUTION
    # ═══════════════════════════════════════════════════════════════

    def start_download(self, confirmless: bool = False):
        total_selected = sum(len(s) for s in self.selected_items.values())
        if total_selected == 0:
            QMessageBox.information(self, "Chưa chọn media", "Vui lòng chọn ít nhất một file media để tải.")
            return

        output_dir = self.config.get("output_dir", "")
        if not output_dir:
            QMessageBox.warning(self, "Chưa chọn thư mục", "Vui lòng chọn thư mục lưu trong Cài đặt.")
            return

        if not confirmless and not self._auto_download_confirmless:
            reply = QMessageBox.question(
                self, "Xác nhận tải",
                f"Tải {total_selected} file về thư mục:\n\n{output_dir}",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        self._auto_download_confirmless = False

        Path(output_dir).mkdir(parents=True, exist_ok=True)

        km = KeyManager(
            self.config.get("pexels_keys", []),
            self.config.get("pixabay_keys", []),
            [],
            self.config.get("vecteezy_keys", []),
            config_repo=self.config_repo
        )

        self.search_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.stop_btn.setText(t("downloader.stop_download"))
        self.stop_btn.setIcon(get_svg_icon("stop", "#ffffff", 14))
        self.status_panel.set_downloading("Khởi tạo download...")

        self.download_worker = DownloadWorker(
            self.scenes,
            self.selected_items,
            output_dir,
            self.json_data,
            key_manager=km,
            downloads_repo=self.downloads_repo
        )
        self.download_worker.progress.connect(self._on_download_progress)
        self.download_worker.statsUpdate.connect(self._on_download_stats)
        self.download_worker.cooldownStart.connect(self._on_cooldown_start)
        self.download_worker.cooldownTick.connect(self._on_cooldown_tick)
        self.download_worker.cooldownEnd.connect(self._on_cooldown_end)
        self.download_worker.finished_signal.connect(self._on_download_finished)
        self.download_worker.start()

    def _on_download_progress(self, message: str, current: int, total: int):
        self.status_panel.set_progress(current, total, message)
        self.status_message.emit(f"Download: {current}/{total} • {message}", 0)

    def _on_download_stats(self, stats: dict):
        self.status_panel.set_stats(
            delay=stats.get("delay"),
            fail_rate=stats.get("fail_rate"),
            blocks=stats.get("blocks"),
            via_refresh=stats.get("via_refresh")
        )

    def _on_cooldown_start(self, seconds: int):
        self.status_panel.set_cooldown(seconds)
        QMessageBox.warning(
            self, "Tạm Dừng Tải",
            f"Máy chủ giới hạn lượt tải (lỗi 403).\n\nHệ thống sẽ tạm dừng {seconds // 60} phút rồi tự động tiếp tục."
        )

    def _on_cooldown_tick(self, remaining: int):
        self.status_panel.set_cooldown(remaining)

    def _on_cooldown_end(self):
        self.status_panel.end_cooldown()

    def _on_download_finished(self, success: int, fail: int, project_dir: str, error_breakdown: dict):
        self.search_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setText(t("common.stop"))
        self.stop_btn.setIcon(get_svg_icon("stop", "#ffffff", 14))

        if project_dir:
            self.status_panel.set_done(success, fail)
        else:
            self.status_panel.set_stopped()

        self.refresh_download_monitor()

        if project_dir:
            total = success + fail
            pct = (success / total * 100) if total > 0 else 0
            msg = f"Tải xong: {success}/{total} ({pct:.1f}%)\nLỗi: {fail}\n\nFolder: {project_dir}"
            ToastNotification.show_toast(
                self,
                f"Hoàn tất tải: {success}/{total} ({pct:.1f}%)" if total > 0 else "Hoàn tất tải",
                "success" if fail == 0 else "warning",
                3500
            )
            QMessageBox.information(self, "Hoàn tất", msg)
            if os.name == 'nt':
                try:
                    os.startfile(project_dir)
                except Exception:
                    pass

        if project_dir and success > 0 and hasattr(self, "btn_next_step"):
            self.btn_next_step.setStyleSheet("""
                QPushButton#accentBtn {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #10b981, stop:1 #059669);
                    color: #ffffff;
                    font-size: 11px;
                    font-weight: 800;
                    padding: 0 14px;
                    border-radius: 6px;
                    border: 1px solid rgba(255,255,255,0.3);
                }
                QPushButton#accentBtn:hover {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #059669, stop:1 #047857);
                }
            """)
            self.btn_next_step.setText("TIẾP TỤC: TẠO GIỌNG ĐỌC AI ➔")

        self.download_finished.emit(success, fail, project_dir, error_breakdown)

    def stop_action(self):
        if self.search_worker and self.search_worker.isRunning():
            self.search_worker.stop()
            self.status_message.emit("Đang dừng tìm kiếm...", 3000)
        if self.download_worker and self.download_worker.isRunning():
            self.download_worker.stop()
            self.status_message.emit("Đang dừng tải xuống...", 3000)
        self.stop_btn.setEnabled(False)

    def reset_all(self):
        reply = QMessageBox.question(
            self, "Đặt lại",
            "Xóa danh sách cảnh và kết quả tìm kiếm hiện tại?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.load_scenes([], None)
            self.status_panel.set_idle("Đã đặt lại")

    def retranslate_ui(self):
        """Updates all text elements upon language switch."""
        self.brand_title.setText(t("downloader.brand_title"))
        self.version_badge.setText(f"v{APP_VERSION} {t('app.version_badge')}")
        self.btn_settings.setText(t("downloader.settings_btn"))
        if not self.scenes:
            self.json_status_label.setText(t("downloader.no_json_status"))
        else:
            self.json_status_label.setText(t("downloader.loaded_json_status", count=len(self.scenes)))

        self.source_lbl.setText(t("downloader.source_label"))
        self.search_photos_check.setText(t("downloader.find_photos"))
        self.search_videos_check.setText(t("downloader.find_videos"))
        self.search_btn.setText(t("downloader.search_all"))
        self.stop_btn.setText(t("common.stop"))
        self.btn_reset.setText(t("common.reset"))

        self.timeline_header.setText(t("downloader.timeline"))
        self.scene_search_input.setPlaceholderText(t("downloader.search_scenes_placeholder"))
        self.info_header.setText(t("downloader.scene_info_header"))

        if "all" in self.filter_buttons:
            self.filter_buttons["all"].setText(t("downloader.filter_all"))
        if "photos" in self.filter_buttons:
            self.filter_buttons["photos"].setText(t("downloader.filter_photos"))
        if "videos" in self.filter_buttons:
            self.filter_buttons["videos"].setText(t("downloader.filter_videos"))

        self.btn_random_select.setText(t("downloader.random_all"))
        self.btn_clear.setText(t("downloader.clear_all_picks"))
        self.btn_download.setText(t("downloader.download_selected"))

        if hasattr(self, "dm_header"):
            self.dm_header.setText(t("downloader.download_progress"))

        if hasattr(self, "api_key_widget") and hasattr(self.api_key_widget, "retranslate_ui"):
            self.api_key_widget.retranslate_ui()
