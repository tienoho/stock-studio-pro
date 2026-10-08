"""
AutoStockMainWindow Thin Controller.
Coordinates tabs, application services, and settings persistence.
"""

import json
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QStatusBar,
    QMessageBox, QApplication, QDialog, QPushButton, QFrame, QLabel
)
from PyQt6.QtCore import Qt, QSize, QTimer
from PyQt6.QtGui import QCursor

from ..core.constants import APP_NAME, APP_VERSION, CONFIG_FILE, STATE_FILE, CACHE_DIR
from ..core.i18n import I18nService, t
from ..core.models.scene import extract_scenes_from_json
from ..infrastructure.persistence.sqlite_config_repo import SqliteConfigRepository
from ..infrastructure.persistence.sqlite_state_repo import SqliteStateRepository
from ..infrastructure.media.thumbnail_cache import ThumbnailCache
from ..infrastructure.watcher.downloads_watcher import DownloadsWatcher
from .components.thumbnail_card import ThumbnailLoader
from .styles.tokens import load_stylesheet
from .styles.theme_manager import ThemeManager
from .styles.icons import get_svg_icon
from .tabs import DownloaderTab, CutMixTab, VoiceTab, SceneVoiceTab, AutoTab, WorkflowTab
from .dialogs import SettingsDialog, UpdateDialog
from .workers import UpdateCheckWorker
from ..application.services.update_checker import ReleaseInfo
from .components.toast_notification import ToastNotification
from .styles.ui_enhancer import enhance_widget_interactions, format_tooltip, set_hand_cursor


class AutoStockMainWindow(QMainWindow):
    """Main application window coordinating all studio tabs and services."""

    def __init__(self):
        super().__init__()

        # Infrastructure / Production SQLite Repositories (with auto-migration from legacy JSON/Pickle)
        self.config_repo = SqliteConfigRepository()
        self.state_repo = SqliteStateRepository()
        self.config = self.config_repo.load_config()

        # Enterprise i18n Service
        saved_locale = self.config.get("locale", "vi")
        self.i18n = I18nService.get_instance(default_locale=saved_locale)
        self.i18n.set_locale(saved_locale)
        self.i18n.languageChanged.connect(self._on_language_changed)

        # Enterprise Theme Manager (Dark / Light Mode)
        saved_theme = self.config.get("theme", "dark")
        self.theme_manager = ThemeManager.get_instance(default_theme=saved_theme)
        self.theme_manager.set_theme(saved_theme)
        self.theme_manager.themeChanged.connect(self._on_theme_changed)

        self._update_window_title()

        # Responsive window sizing
        screen = QApplication.primaryScreen()
        screen_w = screen.availableGeometry().width() if screen else 1920
        screen_h = screen.availableGeometry().height() if screen else 1080

        self.setMinimumSize(1200, 700)
        window_w = min(1700, int(screen_w * 0.92))
        window_h = min(950, int(screen_h * 0.92))
        x = (screen_w - window_w) // 2 + (screen.geometry().x() if screen else 0)
        y = (screen_h - window_h) // 2 + (screen.geometry().y() if screen else 0)
        self.setGeometry(x, y, window_w, window_h)

        if screen_w < 1500 or screen_h < 850:
            self.showMaximized()

        self.setAcceptDrops(True)

        # Cache & background services
        self.thumbnail_cache = ThumbnailCache(CACHE_DIR)
        self.thumb_loader = ThumbnailLoader(self.thumbnail_cache)
        self.downloads_watcher = DownloadsWatcher()

        # Workflow / Auto execution state
        self._auto_after_search = False
        self._auto_mode_config = {}
        self._workflow_running_nodes = []
        self._workflow_index = 0
        self._workflow_waiting_for = None

        # Build UI layout & stylesheet
        self.setStyleSheet(load_stylesheet())
        self._build_ui()

        # Restore previous state
        state = self.state_repo.load_state()
        if state:
            self.downloader_tab.restore_state(state)

        # Silent background update check after 2.5s (smooth startup)
        if self.config.get("check_updates_startup", True):
            QTimer.singleShot(2500, self._check_updates_silent)

    def _update_window_title(self):
        badge = t("app.version_badge")
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION} [{badge}]")

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # Macro Workflow Stepper Bar
        self.workflow_stepper = QFrame()
        self.workflow_stepper.setObjectName("workflowStepper")
        self.workflow_stepper.setFixedHeight(40)
        self.workflow_stepper.setStyleSheet("""
            QFrame#workflowStepper {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0f1523, stop:0.5 #141c2e, stop:1 #0f1523);
                border-bottom: 1px solid #1f2b3f;
            }
        """)
        stepper_layout = QHBoxLayout(self.workflow_stepper)
        stepper_layout.setContentsMargins(16, 4, 16, 4)
        stepper_layout.setSpacing(6)

        step_brand = QLabel("QUY TRÌNH")
        step_brand.setStyleSheet("color: #818cf8; font-size: 10px; font-weight: 900; letter-spacing: 1px; padding-right: 4px;")
        stepper_layout.addWidget(step_brand)

        self.step_buttons = []
        steps_info = [
            ("1. KHO MEDIA", "film", "#4ec9b0", 0),
            ("2. GIỌNG ĐỌC AI", "mic", "#bc8cff", 1),
            ("3. GHÉP THÀNH PHẨM", "activity", "#f0883e", 2),
            ("4. CẮT & GHÉP LẺ", "scissors", "#58a6ff", 3),
            ("5. AUTO 1-CHẠM", "zap", "#e3b341", 4),
            ("6. WORKFLOW PRO", "workflow", "#58a6ff", 5),
        ]
        for name, icon, color, idx in steps_info:
            btn = QPushButton(name)
            btn.setIcon(get_svg_icon(icon, color, 12))
            btn.setCheckable(True)
            btn.setChecked(idx == 0)
            btn.setFixedHeight(28)
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn.setToolTip(format_tooltip(f"Chuyển sang bước {name}", f"Ctrl+{idx+1}"))
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: #94a3b8;
                    border: 1px solid transparent;
                    border-radius: 6px;
                    font-size: 10px;
                    font-weight: 700;
                    padding: 0 8px;
                }}
                QPushButton:hover {{
                    background: #172133;
                    color: #ffffff;
                }}
                QPushButton:checked {{
                    background: #1e293b;
                    color: {color};
                    border: 1px solid {color};
                }}
            """)
            btn.clicked.connect(lambda checked, i=idx: self.main_tabs.setCurrentIndex(i))
            stepper_layout.addWidget(btn)
            self.step_buttons.append(btn)

            if idx < 5:
                sep = QLabel("➔")
                sep.setStyleSheet("color: #334155; font-size: 10px; font-weight: 800;")
                stepper_layout.addWidget(sep)

        stepper_layout.addStretch()

        self.btn_quick_load = QPushButton("Nạp Kịch Bản")
        self.btn_quick_load.setIcon(get_svg_icon("file-text", "#38bdf8", 12))
        self.btn_quick_load.setToolTip(format_tooltip("Nạp kịch bản Claude AI JSON", "Ctrl+O"))
        self.btn_quick_load.setFixedHeight(26)
        self.btn_quick_load.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_quick_load.clicked.connect(self._prompt_load_json)
        stepper_layout.addWidget(self.btn_quick_load)

        self.btn_quick_out = QPushButton("Thư Mục Xuất")
        self.btn_quick_out.setIcon(get_svg_icon("folder", "#34d399", 12))
        self.btn_quick_out.setToolTip(format_tooltip("Mở thư mục xuất sản phẩm", "Ctrl+Shift+O"))
        self.btn_quick_out.setFixedHeight(26)
        self.btn_quick_out.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_quick_out.clicked.connect(self._open_output_folder)
        stepper_layout.addWidget(self.btn_quick_out)

        sep_tools = QLabel("│")
        sep_tools.setStyleSheet("color: #27354a; font-size: 11px;")
        stepper_layout.addWidget(sep_tools)

        self.btn_update = QPushButton()
        self.btn_update.setIcon(get_svg_icon("arrow_down", "#38ef7d", 12))
        self.btn_update.setIconSize(QSize(12, 12))
        self.btn_update.setText(f" v{APP_VERSION}")
        self.btn_update.setToolTip(format_tooltip(t("update.check_btn"), "F12"))
        self.btn_update.setFixedHeight(26)
        self.btn_update.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_update.clicked.connect(self._on_update_btn_clicked)
        stepper_layout.addWidget(self.btn_update)

        self.btn_theme = QPushButton()
        self.btn_theme.setFixedHeight(26)
        self.btn_theme.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_theme.clicked.connect(self._toggle_theme)
        stepper_layout.addWidget(self.btn_theme)

        self.btn_lang = QPushButton()
        self.btn_lang.setIcon(get_svg_icon("globe", "#58a6ff", 12))
        self.btn_lang.setIconSize(QSize(12, 12))
        curr_loc = self.i18n.get_locale().upper()
        self.btn_lang.setText(f" {curr_loc}")
        self.btn_lang.setToolTip(format_tooltip(t("app.switch_lang"), "Ctrl+L"))
        self.btn_lang.setFixedHeight(26)
        self.btn_lang.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_lang.clicked.connect(self._toggle_language)
        stepper_layout.addWidget(self.btn_lang)

        root_layout.addWidget(self.workflow_stepper)

        # Project Status Dashboard (Breadcrumb Bar)
        self.project_state = {
            "script_name": None,
            "script_path": None,
            "total_scenes": 0,
            "selected_media_count": 0,
            "downloaded_media_count": 0,
            "project_dir": None,
            "voice_status": "Chưa tạo",
            "video_status": "Chưa ghép",
        }
        self.project_dashboard = QFrame()
        self.project_dashboard.setObjectName("projectDashboard")
        self.project_dashboard.setFixedHeight(32)
        dash_layout = QHBoxLayout(self.project_dashboard)
        dash_layout.setContentsMargins(16, 2, 16, 2)
        dash_layout.setSpacing(10)

        self.dash_script_lbl = QLabel("📁 Kịch bản: Chưa nạp")
        self.dash_script_lbl.setStyleSheet("color: #64748b; font-size: 11px;")
        dash_layout.addWidget(self.dash_script_lbl)

        sep1 = QLabel("│")
        sep1.setStyleSheet("color: #27354a; font-size: 10px;")
        dash_layout.addWidget(sep1)

        self.dash_scenes_lbl = QLabel("🎬 Cảnh: 0")
        self.dash_scenes_lbl.setStyleSheet("color: #64748b; font-size: 11px;")
        dash_layout.addWidget(self.dash_scenes_lbl)

        sep2 = QLabel("│")
        sep2.setStyleSheet("color: #27354a; font-size: 10px;")
        dash_layout.addWidget(sep2)

        self.dash_media_lbl = QLabel("📦 Media: 0 clips")
        self.dash_media_lbl.setStyleSheet("color: #64748b; font-size: 11px;")
        dash_layout.addWidget(self.dash_media_lbl)

        sep3 = QLabel("│")
        sep3.setStyleSheet("color: #27354a; font-size: 10px;")
        dash_layout.addWidget(sep3)

        self.dash_voice_lbl = QLabel("🎙️ Voice: Chưa tạo")
        self.dash_voice_lbl.setStyleSheet("color: #64748b; font-size: 11px;")
        dash_layout.addWidget(self.dash_voice_lbl)

        sep4 = QLabel("│")
        sep4.setStyleSheet("color: #27354a; font-size: 10px;")
        dash_layout.addWidget(sep4)

        self.dash_video_lbl = QLabel("🎞️ Video: Chưa ghép")
        self.dash_video_lbl.setStyleSheet("color: #64748b; font-size: 11px;")
        dash_layout.addWidget(self.dash_video_lbl)

        dash_layout.addStretch()

        self.dash_action_btn = QPushButton("Nạp kịch bản mới ➔")
        self.dash_action_btn.setIcon(get_svg_icon("arrow_right", "#818cf8", 11))
        self.dash_action_btn.setFixedHeight(22)
        self.dash_action_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.dash_action_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #818cf8;
                font-size: 10px;
                font-weight: 700;
                border: 1px solid #2d3748;
                border-radius: 4px;
                padding: 0 8px;
            }
            QPushButton:hover {
                background: #1e293b;
                color: #ffffff;
                border-color: #818cf8;
            }
        """)
        self.dash_action_btn.clicked.connect(self._on_dash_action_clicked)
        dash_layout.addWidget(self.dash_action_btn)

        root_layout.addWidget(self.project_dashboard)

        self.main_tabs = QTabWidget()
        self.main_tabs.tabBar().setVisible(False)
        self.main_tabs.currentChanged.connect(self._on_tab_changed)
        root_layout.addWidget(self.main_tabs, 1)

        # 1. Downloader Tab
        self.downloader_tab = DownloaderTab(
            config=self.config,
            config_repo=self.config_repo,
            state_repo=self.state_repo,
            thumbnail_cache=self.thumbnail_cache,
            thumb_loader=self.thumb_loader,
            downloads_watcher=self.downloads_watcher,
            parent=self
        )
        self.downloader_tab.open_settings_requested.connect(self._open_settings_dialog)
        self.downloader_tab.status_message.connect(self._on_status_message)
        self.downloader_tab.search_finished.connect(self._on_search_finished)
        self.downloader_tab.download_finished.connect(self._on_download_finished)
        self.downloader_tab.nextStepRequested.connect(self._on_downloader_next_step)
        self.downloader_tab.json_loaded.connect(self._on_json_loaded)
        self.downloader_tab.selection_changed.connect(self._on_downloader_selection_changed)
        if hasattr(self.downloader_tab, "api_key_widget"):
            self.downloader_tab.api_key_widget.keysChanged.connect(self._on_config_changed)

        # 2. Voice Tab (Step 2)
        self.voice_tab = VoiceTab(config=self.config, save_config_fn=self.config_repo.save_config, parent=self)
        self.voice_tab.finished.connect(self._on_voice_finished)
        self.voice_tab.nextStepRequested.connect(self._on_voice_next_step)

        # 3. Scene Voice Match Tab (Step 3)
        self.scene_voice_tab = SceneVoiceTab(parent=self)
        self.scene_voice_tab.finished.connect(self._on_scene_voice_finished)

        # 4. Cut & Mix Tab (Pro tool)
        self.cut_mix_tab = CutMixTab(parent=self)
        self.cut_mix_tab.finished.connect(self._on_cut_mix_finished)

        # 5. Auto Mode Tab
        self.auto_tab = AutoTab(parent=self)
        self.auto_tab.runAutoRequested.connect(self._run_auto_mode)

        # 6. Workflow Node Tab
        self.workflow_tab = WorkflowTab(parent_window=self, parent=self)
        self.workflow_tab.runWorkflowRequested.connect(self._run_workflow)

        # Assemble Tabs with Vector SVG Icons and i18n
        self.main_tabs.addTab(self.downloader_tab, get_svg_icon("film", "#4ec9b0", 16), t("tabs.downloader"))
        self.main_tabs.addTab(self.voice_tab, get_svg_icon("mic", "#bc8cff", 16), t("tabs.voice"))
        self.main_tabs.addTab(self.scene_voice_tab, get_svg_icon("activity", "#f0883e", 16), t("tabs.scene_voice"))
        self.main_tabs.addTab(self.cut_mix_tab, get_svg_icon("scissors", "#58a6ff", 16), t("tabs.cut_mix"))
        self.main_tabs.addTab(self.auto_tab, get_svg_icon("zap", "#e3b341", 16), t("tabs.auto"))
        self.main_tabs.addTab(self.workflow_tab, get_svg_icon("workflow", "#58a6ff", 16), t("tabs.workflow"))

        # Status Bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage(t("app.status_ready"))

        # Setup Global Productivity Shortcuts
        self._setup_shortcuts()
        self._apply_stepper_theme()
        self._update_theme_btn()

        # Enhance hand cursor on all interactive elements
        enhance_widget_interactions(self)

    def _setup_shortcuts(self):
        from PyQt6.QtGui import QKeySequence, QShortcut
        for i in range(6):
            sc = QShortcut(QKeySequence(f"Ctrl+{i+1}"), self)
            sc.activated.connect(lambda idx=i: self.main_tabs.setCurrentIndex(idx))

        sc_save = QShortcut(QKeySequence("Ctrl+S"), self)
        sc_save.activated.connect(self._save_session_state)

        sc_open = QShortcut(QKeySequence("Ctrl+O"), self)
        sc_open.activated.connect(self._prompt_load_json)

        sc_out = QShortcut(QKeySequence("Ctrl+Shift+O"), self)
        sc_out.activated.connect(self._open_output_folder)

        sc_f5 = QShortcut(QKeySequence("F5"), self)
        sc_f5.activated.connect(self._on_f5_pressed)

        sc_theme = QShortcut(QKeySequence("Ctrl+T"), self)
        sc_theme.activated.connect(self._toggle_theme)

        sc_lang = QShortcut(QKeySequence("Ctrl+L"), self)
        sc_lang.activated.connect(self._toggle_language)

        sc_update = QShortcut(QKeySequence("F12"), self)
        sc_update.activated.connect(self._on_update_btn_clicked)

    def _on_tab_changed(self, index: int):
        if hasattr(self, "step_buttons"):
            for i, btn in enumerate(self.step_buttons):
                btn.setChecked(i == index)

    def _prompt_load_json(self):
        from .dialogs import JsonInputDialog
        dialog = JsonInputDialog(parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.result_data:
            scenes = extract_scenes_from_json(dialog.result_data)
            if scenes:
                source_file = getattr(dialog, "source_file_path", None)
                self._on_json_loaded(dialog.result_data, scenes, source_file)
                self.main_tabs.setCurrentIndex(0)
                ToastNotification.show_toast(self, f"Đã nạp {len(scenes)} phân đoạn cảnh thành công!", "success", 3000)

    def _open_output_folder(self):
        self.downloader_tab._open_output_folder_in_explorer()

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
                    self._load_json_path(local_path)
                    return
        super().dropEvent(event)

    def _load_json_path(self, path_str: str):
        try:
            with open(path_str, "r", encoding="utf-8") as f:
                data = json.load(f)
            scenes = extract_scenes_from_json(data)
            if scenes:
                self._on_json_loaded(data, scenes, path_str)
                self.main_tabs.setCurrentIndex(0)
                ToastNotification.show_toast(self, f"Đã nạp {len(scenes)} scenes từ: {Path(path_str).name}", "success", 3000)
            else:
                ToastNotification.show_toast(self, "File JSON không chứa phân đoạn scene hợp lệ", "warning", 3000)
        except Exception as e:
            ToastNotification.show_toast(self, f"Lỗi đọc JSON: {e}", "error", 3000)

    def _save_session_state(self):
        try:
            self.downloader_tab._save_state()
            ToastNotification.show_toast(self, "Đã lưu phiên làm việc vào SQLite", "success", 2000)
        except Exception as e:
            ToastNotification.show_toast(self, f"Lỗi lưu: {e}", "error", 2000)

    def _on_f5_pressed(self):
        current_idx = self.main_tabs.currentIndex()
        if current_idx == 0:
            self.downloader_tab.start_search()
        elif current_idx == 5:
            self._run_workflow()

    def _toggle_theme(self):
        """Toggles between Dark and Light mode and persists to SQLite."""
        new_theme = self.theme_manager.toggle_theme()
        self.config["theme"] = new_theme
        if self.config_repo:
            try:
                self.config_repo.save_config(self.config)
            except Exception:
                pass
        mode_text = "Giao diện Sáng (Crystal Light)" if new_theme == "light" else "Giao diện Tối (Obsidian Dark)"
        ToastNotification.show_toast(self, f"Đã chuyển sang {mode_text}", "info", 1800)

    def _on_theme_changed(self, theme_name: str):
        """Reactively updates application stylesheet and UI controls on theme change."""
        self.setStyleSheet(self.theme_manager.get_stylesheet(theme_name))
        self._update_theme_btn()
        self._apply_stepper_theme()

    def _update_theme_btn(self):
        """Updates the theme toggle button appearance and icon."""
        if not hasattr(self, "btn_theme"):
            return
        is_dark = self.theme_manager.is_dark()
        icon_name = "moon" if is_dark else "sun"
        icon_color = "#fbbf24" if is_dark else "#f59e0b"
        self.btn_theme.setIcon(get_svg_icon(icon_name, icon_color, 14))
        self.btn_theme.setIconSize(QSize(14, 14))
        self.btn_theme.setText(" Tối" if is_dark else " Sáng")
        tt_desc = "Chuyển sang giao diện Sáng (Light Mode)" if is_dark else "Chuyển sang giao diện Tối (Dark Mode)"
        self.btn_theme.setToolTip(format_tooltip(tt_desc, "Ctrl+T"))
        if is_dark:
            self.btn_theme.setStyleSheet("""
                QPushButton {
                    background: #111724;
                    color: #fbbf24;
                    border: 1px solid #1f2b3f;
                    border-radius: 8px;
                    padding: 0 10px;
                    font-size: 11px;
                    font-weight: 800;
                }
                QPushButton:hover {
                    background: #172133;
                    border-color: #fbbf24;
                    color: #ffffff;
                }
            """)
        else:
            self.btn_theme.setStyleSheet("""
                QPushButton {
                    background: #ffffff;
                    color: #d97706;
                    border: 1px solid #cbd5e1;
                    border-radius: 8px;
                    padding: 0 10px;
                    font-size: 11px;
                    font-weight: 800;
                }
                QPushButton:hover {
                    background: #fef3c7;
                    border-color: #f59e0b;
                    color: #b45309;
                }
            """)

    def _apply_stepper_theme(self):
        """Theme-aware styling for workflow stepper and top action buttons."""
        if not hasattr(self, "workflow_stepper"):
            return
        is_dark = self.theme_manager.is_dark()
        stepper_bg = "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0f1523, stop:0.5 #141c2e, stop:1 #0f1523)" if is_dark else "#ffffff"
        stepper_border = "#1f2b3f" if is_dark else "#e2e8f0"
        self.workflow_stepper.setStyleSheet(f"""
            QFrame#workflowStepper {{
                background: {stepper_bg};
                border-bottom: 1px solid {stepper_border};
            }}
        """)

        btn_hover_bg = "#172133" if is_dark else "#f1f5f9"
        btn_hover_fg = "#ffffff" if is_dark else "#0f172a"
        btn_checked_bg = "#1e293b" if is_dark else "#e0e7ff"
        text_color = "#94a3b8" if is_dark else "#64748b"

        steps_colors = ["#4ec9b0", "#bc8cff", "#f0883e", "#58a6ff", "#e3b341", "#58a6ff"]
        if hasattr(self, "step_buttons"):
            for idx, btn in enumerate(self.step_buttons):
                color = steps_colors[idx]
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: transparent;
                        color: {text_color};
                        border: 1px solid transparent;
                        border-radius: 6px;
                        font-size: 10px;
                        font-weight: 700;
                        padding: 0 8px;
                    }}
                    QPushButton:hover {{
                        background: {btn_hover_bg};
                        color: {btn_hover_fg};
                    }}
                    QPushButton:checked {{
                        background: {btn_checked_bg};
                        color: {color};
                        border: 1px solid {color};
                    }}
                """)

        if hasattr(self, "project_dashboard"):
            dash_bg = "#090e18" if is_dark else "#f8fafc"
            dash_border = "#1a2333" if is_dark else "#e2e8f0"
            self.project_dashboard.setStyleSheet(f"""
                QFrame#projectDashboard {{
                    background: {dash_bg};
                    border-bottom: 1px solid {dash_border};
                }}
            """)
            self._update_project_dashboard()

        quick_bg = "#121a29" if is_dark else "#ffffff"
        quick_border = "#1f2b3f" if is_dark else "#cbd5e1"
        quick_hover_bg = "#1a2438" if is_dark else "#f1f5f9"

        if hasattr(self, "btn_quick_load"):
            self.btn_quick_load.setStyleSheet(f"""
                QPushButton {{
                    background: {quick_bg};
                    color: #0284c7;
                    border: 1px solid {quick_border};
                    border-radius: 6px;
                    font-size: 10px;
                    font-weight: 700;
                    padding: 0 8px;
                }}
                QPushButton:hover {{
                    background: {quick_hover_bg};
                    border-color: #0284c7;
                    color: #ffffff;
                }}
            """)

        if hasattr(self, "btn_quick_out"):
            self.btn_quick_out.setStyleSheet(f"""
                QPushButton {{
                    background: {quick_bg};
                    color: #059669;
                    border: 1px solid {quick_border};
                    border-radius: 6px;
                    font-size: 10px;
                    font-weight: 700;
                    padding: 0 8px;
                }}
                QPushButton:hover {{
                    background: {quick_hover_bg};
                    border-color: #059669;
                    color: #ffffff;
                }}
            """)

        if hasattr(self, "btn_update"):
            if is_dark:
                self.btn_update.setStyleSheet("""
                    QPushButton {
                        background: #111724;
                        color: #94a3b8;
                        border: 1px solid #1f2b3f;
                        border-radius: 8px;
                        padding: 0 10px;
                        font-size: 11px;
                        font-weight: 700;
                    }
                    QPushButton:hover {
                        background: #172133;
                        border-color: #38ef7d;
                        color: #38ef7d;
                    }
                """)
            else:
                self.btn_update.setStyleSheet("""
                    QPushButton {
                        background: #ffffff;
                        color: #059669;
                        border: 1px solid #cbd5e1;
                        border-radius: 8px;
                        padding: 0 10px;
                        font-size: 11px;
                        font-weight: 700;
                    }
                    QPushButton:hover {
                        background: #ecfdf5;
                        border-color: #10b981;
                    }
                """)

        if hasattr(self, "btn_lang"):
            if is_dark:
                self.btn_lang.setStyleSheet("""
                    QPushButton {
                        background: #111724;
                        color: #58a6ff;
                        border: 1px solid #1f2b3f;
                        border-radius: 8px;
                        padding: 0 10px;
                        font-size: 11px;
                        font-weight: 800;
                    }
                    QPushButton:hover {
                        background: #172133;
                        border-color: #58a6ff;
                        color: #ffffff;
                    }
                """)
            else:
                self.btn_lang.setStyleSheet("""
                    QPushButton {
                        background: #ffffff;
                        color: #4f46e5;
                        border: 1px solid #cbd5e1;
                        border-radius: 8px;
                        padding: 0 10px;
                        font-size: 11px;
                        font-weight: 800;
                    }
                    QPushButton:hover {
                        background: #eef2ff;
                        border-color: #6366f1;
                    }
                """)

    def _toggle_language(self):
        """Switches between VI and EN, persisting to SQLite."""
        curr = self.i18n.get_locale()
        new_loc = "en" if curr == "vi" else "vi"
        self.config["locale"] = new_loc
        self.config_repo.save_config(self.config)
        self.i18n.set_locale(new_loc)

    def _on_language_changed(self, locale: str):
        """Reactively updates all UI text when language changes."""
        self._update_window_title()
        self.btn_lang.setText(f" {locale.upper()}")
        self.btn_lang.setToolTip(t("app.switch_lang"))

        # Update tab titles
        self.main_tabs.setTabText(0, t("tabs.downloader"))
        self.main_tabs.setTabText(1, t("tabs.voice"))
        self.main_tabs.setTabText(2, t("tabs.scene_voice"))
        self.main_tabs.setTabText(3, t("tabs.cut_mix"))
        self.main_tabs.setTabText(4, t("tabs.auto"))
        self.main_tabs.setTabText(5, t("tabs.workflow"))

        # Notify child tabs
        for tab in [self.downloader_tab, self.cut_mix_tab, self.voice_tab, self.scene_voice_tab, self.auto_tab, self.workflow_tab]:
            if hasattr(tab, "retranslate_ui"):
                tab.retranslate_ui()

        if hasattr(self, "btn_update"):
            self.btn_update.setToolTip(t("update.check_btn"))

        self.status_bar.showMessage(t("app.status_ready"), 3000)

    def _on_status_message(self, message: str, timeout: int = 0):
        self.status_bar.showMessage(message, timeout)

    # ═══════════════════════════════════════════════════════════════
    # AUTO-UPDATE & VERSION MANAGEMENT
    # ═══════════════════════════════════════════════════════════════

    def _on_update_btn_clicked(self):
        if hasattr(self, "_latest_release") and self._latest_release:
            dialog = UpdateDialog(self._latest_release, current_version=APP_VERSION, config_repo=self.config_repo, parent=self)
            dialog.exec()
        else:
            self._check_updates_manual()

    def _check_updates_silent(self):
        self._update_worker = UpdateCheckWorker(current_version=APP_VERSION, parent=self)
        self._update_worker.update_available.connect(lambda rel: self._on_update_available(rel, show_dialog=False))
        self._update_worker.start()

    def _check_updates_manual(self):
        self.status_bar.showMessage(t("update.checking"), 3000)
        self._manual_worker = UpdateCheckWorker(current_version=APP_VERSION, parent=self)
        self._manual_worker.update_available.connect(lambda rel: self._on_update_available(rel, show_dialog=True))
        self._manual_worker.no_update.connect(
            lambda msg: ToastNotification.show_toast(self, msg, "info", 3000)
        )
        self._manual_worker.error_occurred.connect(
            lambda err: ToastNotification.show_toast(self, err, "warning", 3500)
        )
        self._manual_worker.start()

    def _on_update_available(self, release: ReleaseInfo, show_dialog: bool = False):
        self._latest_release = release
        self.btn_update.setText(f" 🚀 {release.tag_name}")
        self.btn_update.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0f2c20, stop:1 #133829);
                color: #38ef7d;
                border: 1px solid #10b981;
                border-radius: 8px;
                padding: 0 10px;
                font-size: 11px;
                font-weight: 800;
            }
            QPushButton:hover {
                background: #10b981;
                color: #081a13;
            }
        """)
        self.btn_update.setToolTip(f"Bản mới {release.tag_name} đã sẵn sàng! Bấm để cập nhật.")
        ToastNotification.show_toast(
            self,
            f"🚀 Bản cập nhật mới {release.tag_name} đã sẵn sàng!",
            "success",
            4000
        )
        if show_dialog:
            dialog = UpdateDialog(release, current_version=APP_VERSION, config_repo=self.config_repo, parent=self)
            dialog.exec()

    # ═══════════════════════════════════════════════════════════════
    # SETTINGS & JSON IMPORT
    # ═══════════════════════════════════════════════════════════════

    def _open_settings_dialog(self):
        dialog = SettingsDialog(
            config=self.config,
            save_config_fn=self.config_repo.save_config,
            parent=self
        )
        dialog.jsonLoaded.connect(self._on_json_loaded)
        dialog.configChanged.connect(self._on_config_changed)
        dialog.exec()

    def _on_config_changed(self):
        self.config = self.config_repo.load_config()
        self.downloader_tab.config = self.config
        if hasattr(self.downloader_tab, "api_key_widget"):
            self.downloader_tab.api_key_widget.refresh_keys_display()

    def _on_json_loaded(self, json_data: dict, scenes: list, file_path: Optional[str] = None):
        if getattr(self.downloader_tab, "scenes", None) != scenes:
            self.downloader_tab.load_scenes(scenes, json_data, file_path or "")
        self.project_state["script_path"] = file_path
        self.project_state["script_name"] = Path(file_path).name if file_path else "Kịch bản tùy biến"
        self.project_state["total_scenes"] = len(scenes)
        self.project_state["voice_status"] = "Chưa tạo"
        self.project_state["video_status"] = "Chưa ghép"
        self._update_project_dashboard()
        if file_path:
            if hasattr(self, "scene_voice_tab") and hasattr(self.scene_voice_tab, "svc_json"):
                self.scene_voice_tab.svc_json.setText(file_path)
            if hasattr(self, "voice_tab") and hasattr(self.voice_tab, "json_script_input"):
                self.voice_tab.json_script_input.setText(file_path)
                self.voice_tab.json_parts_input.setText(file_path)
        self.status_bar.showMessage(t("downloader.loaded_json_status", count=len(scenes)), 4000)

    def _update_project_dashboard(self):
        if not hasattr(self, "project_dashboard"):
            return
        is_dark = ThemeManager.get_instance().is_dark()
        muted_color = "#64748b" if is_dark else "#94a3b8"

        # 1. Script name
        script_name = self.project_state.get("script_name")
        if script_name:
            self.dash_script_lbl.setText(f"📁 Dự án: {script_name}")
            self.dash_script_lbl.setStyleSheet("color: #38bdf8; font-weight: 700; font-size: 11px;")
        else:
            self.dash_script_lbl.setText("📁 Kịch bản: Chưa nạp")
            self.dash_script_lbl.setStyleSheet(f"color: {muted_color}; font-size: 11px;")

        # 2. Scenes
        total_scenes = self.project_state.get("total_scenes", 0)
        if total_scenes > 0:
            self.dash_scenes_lbl.setText(f"🎬 Cảnh: {total_scenes}/{total_scenes}")
            self.dash_scenes_lbl.setStyleSheet("color: #818cf8; font-weight: 700; font-size: 11px;")
        else:
            self.dash_scenes_lbl.setText("🎬 Cảnh: 0")
            self.dash_scenes_lbl.setStyleSheet(f"color: {muted_color}; font-size: 11px;")

        # 3. Media
        dl_count = self.project_state.get("downloaded_media_count", 0)
        sel_count = self.project_state.get("selected_media_count", 0)
        if dl_count > 0:
            self.dash_media_lbl.setText(f"📦 Media: {dl_count} clips (Đã tải)")
            self.dash_media_lbl.setStyleSheet("color: #34d399; font-weight: 700; font-size: 11px;")
        elif sel_count > 0:
            self.dash_media_lbl.setText(f"📦 Media: {sel_count} clips (Đã chọn)")
            self.dash_media_lbl.setStyleSheet("color: #fbbf24; font-weight: 700; font-size: 11px;")
        else:
            self.dash_media_lbl.setText("📦 Media: 0 clips")
            self.dash_media_lbl.setStyleSheet(f"color: {muted_color}; font-size: 11px;")

        # 4. Voice
        v_status = self.project_state.get("voice_status", "Chưa tạo")
        if v_status == "Đã tạo":
            self.dash_voice_lbl.setText("🎙️ Voice: Đã tạo")
            self.dash_voice_lbl.setStyleSheet("color: #c084fc; font-weight: 700; font-size: 11px;")
        else:
            self.dash_voice_lbl.setText("🎙️ Voice: Chưa tạo")
            self.dash_voice_lbl.setStyleSheet(f"color: {muted_color}; font-size: 11px;")

        # 5. Video
        vid_status = self.project_state.get("video_status", "Chưa ghép")
        if vid_status == "Đã hoàn tất":
            self.dash_video_lbl.setText("🎞️ Video: Sẵn sàng")
            self.dash_video_lbl.setStyleSheet("color: #10b981; font-weight: 800; font-size: 11px;")
        else:
            self.dash_video_lbl.setText("🎞️ Video: Chưa ghép")
            self.dash_video_lbl.setStyleSheet(f"color: {muted_color}; font-size: 11px;")

        # Context action button label
        if not self.project_state.get("script_name"):
            self.dash_action_btn.setText("Nạp kịch bản mới ➔")
        elif self.project_state.get("downloaded_media_count", 0) == 0:
            self.dash_action_btn.setText("Bước 1: Tải Media ➔")
        elif self.project_state.get("voice_status") != "Đã tạo":
            self.dash_action_btn.setText("Bước 2: Tạo Giọng Đọc ➔")
        elif self.project_state.get("video_status") != "Đã hoàn tất":
            self.dash_action_btn.setText("Bước 3: Ghép Video ➔")
        else:
            self.dash_action_btn.setText("Mở Thư Mục Xuất ➔")

    def _on_downloader_selection_changed(self, count: int):
        self.project_state["selected_media_count"] = count
        self._update_project_dashboard()

    def _on_downloader_next_step(self):
        """Advances workflow from Step 1 (Media Downloader) to Step 2 (Voice Studio)."""
        self.main_tabs.setCurrentIndex(1)
        script_path = self.project_state.get("script_path")
        if script_path:
            if hasattr(self.voice_tab, "json_script_input"):
                self.voice_tab.json_script_input.setText(str(script_path))
            if hasattr(self.voice_tab, "json_parts_input"):
                self.voice_tab.json_parts_input.setText(str(script_path))
            if hasattr(self.voice_tab, "voice_tabs"):
                self.voice_tab.voice_tabs.setCurrentIndex(2)
        ToastNotification.show_toast(self, "Đã chuyển sang Bước 2: Tạo giọng đọc AI", "info", 2500)

    def _on_voice_next_step(self):
        """Advances workflow from Step 2 (Voice Studio) to Step 3 (Scene Voice Matcher)."""
        self.main_tabs.setCurrentIndex(2)
        v_dir = Path(self.voice_tab.voice_output_dir.text().strip() or "voices")
        master_audio = v_dir / "master_voice.mp3"
        master_srt = v_dir / "kich_ban_hoan_chinh.srt"
        if not master_srt.exists():
            srts = list(v_dir.glob("*.srt"))
            if srts:
                master_srt = srts[0]

        if hasattr(self.scene_voice_tab, "svc_full_voice") and master_audio.exists():
            self.scene_voice_tab.svc_full_voice.setText(str(master_audio))
        if hasattr(self.scene_voice_tab, "svc_voice"):
            if master_srt.exists():
                self.scene_voice_tab.svc_voice.setText(str(master_srt))
            elif v_dir.exists():
                self.scene_voice_tab.svc_voice.setText(str(v_dir))

        proj_dir = self.project_state.get("project_dir")
        if proj_dir and hasattr(self.scene_voice_tab, "svc_root"):
            if not self.scene_voice_tab.svc_root.text().strip():
                self.scene_voice_tab.svc_root.setText(str(proj_dir))

        if hasattr(self.scene_voice_tab, "svc_out") and not self.scene_voice_tab.svc_out.text().strip():
            if proj_dir:
                self.scene_voice_tab.svc_out.setText(str(Path(proj_dir) / "final_output"))
            else:
                self.scene_voice_tab.svc_out.setText(str(v_dir.parent / "final_output"))

        ToastNotification.show_toast(self, "Đã kế thừa toàn bộ dữ liệu sang Bước 3: Sẵn sàng ghép thành phẩm!", "success", 3000)

    def _on_dash_action_clicked(self):
        if not self.project_state.get("script_name"):
            self._prompt_load_json()
        elif self.project_state.get("downloaded_media_count", 0) == 0:
            self.main_tabs.setCurrentIndex(0)
            ToastNotification.show_toast(self, "Bước 1: Hãy chọn và tải media cho các cảnh", "info", 2500)
        elif self.project_state.get("voice_status") != "Đã tạo":
            self._on_downloader_next_step()
        elif self.project_state.get("video_status") != "Đã hoàn tất":
            self._on_voice_next_step()
        else:
            self._open_output_folder()

    # ═══════════════════════════════════════════════════════════════
    # AUTO MODE PIPELINE
    # ═══════════════════════════════════════════════════════════════

    def _run_auto_mode(self, mode: str, count: int, then_voice: bool):
        if not self.downloader_tab.scenes:
            QMessageBox.warning(self, "Chưa có kịch bản", "Vui lòng nạp kịch bản vào hệ thống trước khi chạy Tự động.")
            return

        self._auto_after_search = True
        self._auto_mode_config = {"mode": mode, "count": count, "then_voice": then_voice}

        # Apply media type filters
        lower = mode.lower()
        self.downloader_tab.search_videos_check.setChecked("video" in lower)
        self.downloader_tab.search_photos_check.setChecked("ảnh" in lower or "+" in lower)

        self.auto_tab.auto_log.appendPlainText("Tự động: Bắt đầu tìm kiếm media...")
        self.downloader_tab.start_search()

    def _on_search_finished(self):
        if self._auto_after_search:
            self._auto_after_search = False
            count = self._auto_mode_config.get("count", 1)
            self.downloader_tab.auto_random_all_scenes(count)
            self.auto_tab.auto_log.appendPlainText(f"Tự động: Đã chọn ngẫu nhiên {count} media/cảnh. Bắt đầu tải...")
            self.downloader_tab.start_download(confirmless=True)
            return

        if self._workflow_waiting_for == "Search stock":
            self._workflow_waiting_for = None
            self.workflow_tab.workflow_log.appendPlainText("Tìm kiếm media: Hoàn tất, tiếp tục bước sau...")
            self._workflow_continue()

    def _on_download_finished(self, success: int, fail: int, project_dir: str, error_breakdown: dict):
        if project_dir:
            self.project_state["project_dir"] = project_dir
            self.project_state["downloaded_media_count"] = success
            self._update_project_dashboard()
            # Cross-tab folder synchronization
            if hasattr(self, "cut_mix_tab") and hasattr(self.cut_mix_tab, "cut_folder_input"):
                self.cut_mix_tab.cut_folder_input.setText(project_dir)
            if hasattr(self, "scene_voice_tab") and hasattr(self.scene_voice_tab, "svc_root"):
                self.scene_voice_tab.svc_root.setText(project_dir)

        if self._auto_mode_config.get("then_voice"):
            self._auto_mode_config["then_voice"] = False
            self.auto_tab.auto_log.appendPlainText("Tự động: Tải hoàn tất. Chuyển sang tạo giọng đọc...")
            self.main_tabs.setCurrentIndex(1)

        if self._workflow_waiting_for == "Download selected":
            self._workflow_waiting_for = None
            self.workflow_tab.workflow_log.appendPlainText("Tải đã chọn: Hoàn tất, tiếp tục bước sau...")
            self._workflow_continue()

    # ═══════════════════════════════════════════════════════════════
    # WORKFLOW NODE CANVAS RUNNER
    # ═══════════════════════════════════════════════════════════════

    def _run_workflow(self):
        nodes = self.workflow_tab.workflow_canvas.workflow_nodes()
        if not nodes:
            QMessageBox.information(self, "Quy trình trống", "Vui lòng thêm ít nhất một bước trước khi chạy.")
            return

        for n in nodes:
            n.set_status("idle")

        self._workflow_running_nodes = nodes
        self._workflow_index = 0
        steps = [node.title for node in nodes]
        self.workflow_tab.workflow_log.appendPlainText(f"BẮT ĐẦU: {' -> '.join(steps)}")
        self._workflow_continue()

    def _workflow_continue(self):
        nodes = self._workflow_running_nodes
        while self._workflow_index < len(nodes):
            # Mark previous node as success if applicable
            if self._workflow_index > 0:
                nodes[self._workflow_index - 1].set_status("success")

            node = nodes[self._workflow_index]
            self._workflow_index += 1
            step = node.title
            config = getattr(node, "config", {}) or {}

            node.set_status("running")
            self.workflow_tab.workflow_log.appendPlainText(f"Bước: {step}")

            if step == "Load JSON":
                if config.get("json"):
                    try:
                        raw = Path(str(config.get("json"))).read_text(encoding="utf-8")
                        data = json.loads(raw)
                        scenes = extract_scenes_from_json(data)
                        self._on_json_loaded(data, scenes, str(config.get("json")))
                        node.set_status("success")
                        continue
                    except Exception as e:
                        node.set_status("error")
                        QMessageBox.warning(self, "Lỗi đọc kịch bản", str(e))
                self.main_tabs.setCurrentIndex(0)
                self.downloader_tab._open_json_input_dialog()
                if self.downloader_tab.scenes:
                    node.set_status("success")
                    continue
                else:
                    node.set_status("error")
                    self.workflow_tab.workflow_log.appendPlainText("Quy trình dừng: Chưa nạp kịch bản.")
                    return

            if step == "Search stock":
                self._workflow_waiting_for = "Search stock"
                self.main_tabs.setCurrentIndex(0)
                self.downloader_tab.start_search()
                return

            if step == "Random select":
                count = int(config.get("count") or 1)
                self.downloader_tab.auto_random_all_scenes(count)
                node.set_status("success")
                continue

            if step == "Download selected":
                self._workflow_waiting_for = "Download selected"
                self.main_tabs.setCurrentIndex(0)
                self.downloader_tab.start_download(confirmless=True)
                return

            if step == "Cut/Mix video":
                self._workflow_waiting_for = "Cut/Mix video"
                self.main_tabs.setCurrentIndex(3)
                self.cut_mix_tab.start_cut_merge()
                return

            if step == "Create voice":
                self._workflow_waiting_for = "Create voice"
                self.main_tabs.setCurrentIndex(1)
                mode = str(config.get("mode") or "TXT folder/file")
                if "JSON" in mode:
                    self.voice_tab._start_json_parts_voice_native()
                else:
                    self.voice_tab.start_native_voice()
                return

            if step == "Scene voice match":
                self._workflow_waiting_for = "Scene voice match"
                self.main_tabs.setCurrentIndex(2)
                self.scene_voice_tab.start_scene_voice()
                return

        if nodes:
            nodes[-1].set_status("success")
        self.workflow_tab.workflow_log.appendPlainText("Quy trình: Đã hoàn tất toàn bộ các bước!")
        self._workflow_waiting_for = None

    def _on_cut_mix_finished(self, ok: bool, message: str):
        if self._workflow_waiting_for == "Cut/Mix video":
            self._workflow_waiting_for = None
            if self._workflow_index > 0 and self._workflow_index <= len(self._workflow_running_nodes):
                self._workflow_running_nodes[self._workflow_index - 1].set_status("success" if ok else "error")
            self.workflow_tab.workflow_log.appendPlainText(f"Cắt & Ghép video: {'thành công' if ok else 'lỗi'} -> {message}")
            if ok:
                self._workflow_continue()

    def _on_voice_finished(self, ok: bool, message: str):
        self.project_state["voice_status"] = "Đã tạo" if ok else "Lỗi"
        self._update_project_dashboard()
        # Propagate generated voices to Scene Voice tab
        if hasattr(self, "scene_voice_tab") and hasattr(self.voice_tab, "voice_output_dir"):
            v_dir = Path(self.voice_tab.voice_output_dir.text().strip() or "voices")
            if v_dir.exists():
                master_srt = v_dir / "kich_ban_hoan_chinh.srt"
                if not master_srt.exists():
                    srts = list(v_dir.glob("*.srt"))
                    if srts:
                        master_srt = srts[0]
                if master_srt.exists():
                    self.scene_voice_tab.svc_voice.setText(str(master_srt))
                else:
                    self.scene_voice_tab.svc_voice.setText(str(v_dir))

                master_audio = v_dir / "master_voice.mp3"
                if master_audio.exists():
                    self.scene_voice_tab.svc_full_voice.setText(str(master_audio))

                if not self.scene_voice_tab.svc_out.text().strip():
                    proj_dir = self.project_state.get("project_dir")
                    if proj_dir:
                        self.scene_voice_tab.svc_out.setText(str(Path(proj_dir) / "final_output"))
                    else:
                        self.scene_voice_tab.svc_out.setText(str(v_dir.parent / "final_output"))

        if self._workflow_waiting_for == "Create voice":
            self._workflow_waiting_for = None
            if self._workflow_index > 0 and self._workflow_index <= len(self._workflow_running_nodes):
                self._workflow_running_nodes[self._workflow_index - 1].set_status("success" if ok else "error")
            self.workflow_tab.workflow_log.appendPlainText(f"Tạo giọng đọc: {'thành công' if ok else 'lỗi'} -> {message}")
            if ok:
                self._workflow_continue()

    def _on_scene_voice_finished(self, ok: bool, message: str):
        self.project_state["video_status"] = "Đã hoàn tất" if ok else "Lỗi"
        self._update_project_dashboard()
        if self._workflow_waiting_for == "Scene voice match":
            self._workflow_waiting_for = None
            if self._workflow_index > 0 and self._workflow_index <= len(self._workflow_running_nodes):
                self._workflow_running_nodes[self._workflow_index - 1].set_status("success" if ok else "error")
            self.workflow_tab.workflow_log.appendPlainText(f"Khớp Video & Voice: {'thành công' if ok else 'lỗi'} -> {message}")
            if ok:
                self._workflow_continue()

    # ═══════════════════════════════════════════════════════════════
    # CLEANUP & CLOSING
    # ═══════════════════════════════════════════════════════════════

    def closeEvent(self, event):
        try:
            self.downloader_tab._save_state()
            if self.downloads_watcher:
                self.downloads_watcher.stop()
            if self.thumb_loader:
                self.thumb_loader.shutdown()

            # Downloader workers
            if hasattr(self.downloader_tab, "search_worker") and self.downloader_tab.search_worker and self.downloader_tab.search_worker.isRunning():
                self.downloader_tab.search_worker.stop()
                self.downloader_tab.search_worker.wait(1000)
            if hasattr(self.downloader_tab, "download_worker") and self.downloader_tab.download_worker and self.downloader_tab.download_worker.isRunning():
                self.downloader_tab.download_worker.stop()
                self.downloader_tab.download_worker.wait(1000)

            # Voice worker
            if hasattr(self, "voice_tab") and hasattr(self.voice_tab, "stop_voice"):
                self.voice_tab.stop_voice()
                if self.voice_tab.worker and self.voice_tab.worker.isRunning():
                    self.voice_tab.worker.wait(1000)

            # Scene Voice worker
            if hasattr(self, "scene_voice_tab") and hasattr(self.scene_voice_tab, "stop_scene_voice"):
                self.scene_voice_tab.stop_scene_voice()
                if self.scene_voice_tab.scene_voice_worker and self.scene_voice_tab.scene_voice_worker.isRunning():
                    self.scene_voice_tab.scene_voice_worker.wait(1000)

            # Cut & Mix worker
            if hasattr(self, "cut_mix_tab") and hasattr(self.cut_mix_tab, "worker"):
                if self.cut_mix_tab.worker and self.cut_mix_tab.worker.isRunning():
                    self.cut_mix_tab.worker.stop()
                    self.cut_mix_tab.worker.wait(1000)

            if hasattr(self, "state_repo") and hasattr(self.state_repo, "db"):
                self.state_repo.db.close()
        except Exception:
            pass
        super().closeEvent(event)


# Alias for backwards compatibility
StockStudioMainWindow = AutoStockMainWindow

