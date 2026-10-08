"""
AutoStockMainWindow Thin Controller.
Coordinates tabs, application services, and settings persistence.
"""

import json
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QStatusBar,
    QMessageBox, QApplication, QDialog, QPushButton
)
from PyQt6.QtCore import Qt, QSize, QTimer

from ..core.constants import APP_NAME, APP_VERSION, CONFIG_FILE, STATE_FILE, CACHE_DIR
from ..core.i18n import I18nService, t
from ..core.models.scene import extract_scenes_from_json
from ..infrastructure.persistence.sqlite_config_repo import SqliteConfigRepository
from ..infrastructure.persistence.sqlite_state_repo import SqliteStateRepository
from ..infrastructure.media.thumbnail_cache import ThumbnailCache
from ..infrastructure.watcher.downloads_watcher import DownloadsWatcher
from .components.thumbnail_card import ThumbnailLoader
from .styles.tokens import load_stylesheet
from .styles.icons import get_svg_icon
from .tabs import DownloaderTab, CutMixTab, VoiceTab, SceneVoiceTab, AutoTab, WorkflowTab
from .dialogs import SettingsDialog, UpdateDialog
from .workers import UpdateCheckWorker
from ..application.services.update_checker import ReleaseInfo
from .components.toast_notification import ToastNotification


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

        self.main_tabs = QTabWidget()
        root_layout.addWidget(self.main_tabs, 1)

        # Tab corner container: Update Status & Language toggle buttons
        corner_widget = QWidget()
        corner_layout = QHBoxLayout(corner_widget)
        corner_layout.setContentsMargins(0, 0, 8, 0)
        corner_layout.setSpacing(6)

        self.btn_update = QPushButton()
        self.btn_update.setIcon(get_svg_icon("arrow_down", "#38ef7d", 13))
        self.btn_update.setIconSize(QSize(13, 13))
        self.btn_update.setText(f" v{APP_VERSION}")
        self.btn_update.setToolTip(t("update.check_btn"))
        self.btn_update.setFixedHeight(30)
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
        self.btn_update.clicked.connect(self._on_update_btn_clicked)
        corner_layout.addWidget(self.btn_update)

        self.btn_lang = QPushButton()
        self.btn_lang.setIcon(get_svg_icon("globe", "#58a6ff", 14))
        self.btn_lang.setIconSize(QSize(14, 14))
        curr_loc = self.i18n.get_locale().upper()
        self.btn_lang.setText(f" {curr_loc}")
        self.btn_lang.setToolTip(t("app.switch_lang"))
        self.btn_lang.setFixedHeight(30)
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
        self.btn_lang.clicked.connect(self._toggle_language)
        corner_layout.addWidget(self.btn_lang)

        self.main_tabs.setCornerWidget(corner_widget, Qt.Corner.TopRightCorner)

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
        if hasattr(self.downloader_tab, "api_key_widget"):
            self.downloader_tab.api_key_widget.keysChanged.connect(self._on_config_changed)

        # 2. Cut & Mix Tab
        self.cut_mix_tab = CutMixTab(parent=self)
        self.cut_mix_tab.finished.connect(self._on_cut_mix_finished)

        # 3. Voice TXT Studio Tab
        self.voice_tab = VoiceTab(config=self.config, save_config_fn=self.config_repo.save_config, parent=self)
        self.voice_tab.finished.connect(self._on_voice_finished)

        # 4. Scene Voice Match Tab
        self.scene_voice_tab = SceneVoiceTab(parent=self)
        self.scene_voice_tab.finished.connect(self._on_scene_voice_finished)

        # 5. Auto Mode Tab
        self.auto_tab = AutoTab(parent=self)
        self.auto_tab.runAutoRequested.connect(self._run_auto_mode)

        # 6. Workflow Node Tab
        self.workflow_tab = WorkflowTab(parent_window=self, parent=self)
        self.workflow_tab.runWorkflowRequested.connect(self._run_workflow)

        # Assemble Tabs with Vector SVG Icons and i18n
        self.main_tabs.addTab(self.downloader_tab, get_svg_icon("film", "#4ec9b0", 16), t("tabs.downloader"))
        self.main_tabs.addTab(self.cut_mix_tab, get_svg_icon("scissors", "#58a6ff", 16), t("tabs.cut_mix"))
        self.main_tabs.addTab(self.voice_tab, get_svg_icon("mic", "#bc8cff", 16), t("tabs.voice"))
        self.main_tabs.addTab(self.scene_voice_tab, get_svg_icon("activity", "#f0883e", 16), t("tabs.scene_voice"))
        self.main_tabs.addTab(self.auto_tab, get_svg_icon("zap", "#e3b341", 16), t("tabs.auto"))
        self.main_tabs.addTab(self.workflow_tab, get_svg_icon("workflow", "#58a6ff", 16), t("tabs.workflow"))

        # Status Bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage(t("app.status_ready"))

        # Setup Global Productivity Shortcuts
        self._setup_shortcuts()

    def _setup_shortcuts(self):
        from PyQt6.QtGui import QKeySequence, QShortcut
        for i in range(6):
            sc = QShortcut(QKeySequence(f"Ctrl+{i+1}"), self)
            sc.activated.connect(lambda idx=i: self.main_tabs.setCurrentIndex(idx))

        sc_save = QShortcut(QKeySequence("Ctrl+S"), self)
        sc_save.activated.connect(self._save_session_state)

        sc_f5 = QShortcut(QKeySequence("F5"), self)
        sc_f5.activated.connect(self._on_f5_pressed)

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
        self.main_tabs.setTabText(1, t("tabs.cut_mix"))
        self.main_tabs.setTabText(2, t("tabs.voice"))
        self.main_tabs.setTabText(3, t("tabs.scene_voice"))
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
        self.downloader_tab.load_scenes(scenes, json_data)
        if file_path:
            if hasattr(self, "scene_voice_tab") and hasattr(self.scene_voice_tab, "svc_json"):
                self.scene_voice_tab.svc_json.setText(file_path)
            if hasattr(self, "voice_tab") and hasattr(self.voice_tab, "json_script_input"):
                self.voice_tab.json_script_input.setText(file_path)
                self.voice_tab.json_parts_input.setText(file_path)
        self.status_bar.showMessage(t("downloader.loaded_json_status", count=len(scenes)), 4000)

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
            # Cross-tab folder synchronization
            if hasattr(self, "cut_mix_tab") and hasattr(self.cut_mix_tab, "cut_folder_input"):
                self.cut_mix_tab.cut_folder_input.setText(project_dir)
            if hasattr(self, "scene_voice_tab") and hasattr(self.scene_voice_tab, "svc_root"):
                self.scene_voice_tab.svc_root.setText(project_dir)

        if self._auto_mode_config.get("then_voice"):
            self._auto_mode_config["then_voice"] = False
            self.auto_tab.auto_log.appendPlainText("Tự động: Tải hoàn tất. Chuyển sang tạo giọng đọc...")
            self.main_tabs.setCurrentIndex(2)

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
                self.main_tabs.setCurrentIndex(1)
                self.cut_mix_tab.start_cut_merge()
                return

            if step == "Create voice":
                self._workflow_waiting_for = "Create voice"
                self.main_tabs.setCurrentIndex(2)
                mode = str(config.get("mode") or "TXT folder/file")
                if "JSON" in mode:
                    self.voice_tab._start_json_parts_voice_native()
                else:
                    self.voice_tab.start_native_voice()
                return

            if step == "Scene voice match":
                self._workflow_waiting_for = "Scene voice match"
                self.main_tabs.setCurrentIndex(3)
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
        # Propagate generated voices to Scene Voice tab
        if hasattr(self, "scene_voice_tab") and hasattr(self.voice_tab, "voice_output_dir"):
            v_dir = Path(self.voice_tab.voice_output_dir.text().strip() or "voices")
            if v_dir.exists():
                self.scene_voice_tab.svc_voice.setText(str(v_dir))
                master_audio = v_dir / "master_voice.mp3"
                if master_audio.exists():
                    self.scene_voice_tab.svc_full_voice.setText(str(master_audio))

        if self._workflow_waiting_for == "Create voice":
            self._workflow_waiting_for = None
            if self._workflow_index > 0 and self._workflow_index <= len(self._workflow_running_nodes):
                self._workflow_running_nodes[self._workflow_index - 1].set_status("success" if ok else "error")
            self.workflow_tab.workflow_log.appendPlainText(f"Tạo giọng đọc: {'thành công' if ok else 'lỗi'} -> {message}")
            if ok:
                self._workflow_continue()

    def _on_scene_voice_finished(self, ok: bool, message: str):
        if self._workflow_waiting_for == "Scene voice match":
            self._workflow_waiting_for = None
            if self._workflow_index > 0 and self._workflow_index <= len(self._workflow_running_nodes):
                self._workflow_running_nodes[self._workflow_index - 1].set_status("success" if ok else "error")
            self.workflow_tab.workflow_log.appendPlainText(f"Khớp Video & Voice: {'thành công' if ok else 'lỗi'} -> {message}")
            if ok:
                self._workflow_continue()

    # ═══════════════════════════════════════════════════════════════
    # DRAG & DROP SCRIPT IMPORT
    # ═══════════════════════════════════════════════════════════════

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
                    try:
                        with open(local_path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        scenes = extract_scenes_from_json(data)
                        if scenes:
                            self._on_json_loaded(data, scenes, local_path)
                            self.main_tabs.setCurrentIndex(0)
                            ToastNotification.show_toast(
                                self,
                                f"Đã nạp {len(scenes)} cảnh từ {Path(local_path).name}",
                                "success",
                                3000
                            )
                        else:
                            ToastNotification.show_toast(self, "File JSON không có danh sách cảnh hợp lệ", "warning", 3000)
                    except Exception as e:
                        ToastNotification.show_toast(self, f"Lỗi đọc kịch bản: {str(e)[:45]}", "error", 4000)
                    return
        super().dropEvent(event)

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
            if self.downloader_tab.search_worker and self.downloader_tab.search_worker.isRunning():
                self.downloader_tab.search_worker.stop()
            if self.downloader_tab.download_worker and self.downloader_tab.download_worker.isRunning():
                self.downloader_tab.download_worker.stop()
            if hasattr(self, "state_repo") and hasattr(self.state_repo, "db"):
                self.state_repo.db.close()
        except Exception:
            pass
        super().closeEvent(event)


# Alias for backwards compatibility
StockStudioMainWindow = AutoStockMainWindow

