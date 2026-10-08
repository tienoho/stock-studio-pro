"""
Modal dialog notifying the user about new software releases and updates.
Provides 100% automated background streaming download, archive extraction,
and detached in-place executable replacement on Windows.
Styled in the modern Obsidian Dark & Electric Neon theme.
"""

from pathlib import Path
from typing import Optional
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QPlainTextEdit, QFrame, QCheckBox, QApplication, QProgressBar
)
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices

from ...application.services.update_checker import ReleaseInfo, UpdateCheckerService
from ..workers.update_worker import UpdateDownloadWorker
from ...core.constants import APP_NAME, APP_VERSION
from ...core.i18n import t
from ..styles.icons import get_svg_icon, get_svg_pixmap
from ..styles.tokens import load_stylesheet


class UpdateDialog(QDialog):
    """High-end modal dialog displaying available updates, changelog, and one-click auto-updater."""

    def __init__(self, release: ReleaseInfo, current_version: str = APP_VERSION, config_repo=None, parent=None):
        super().__init__(parent)
        self.release = release
        self.current_version = current_version
        self.config_repo = config_repo
        self._worker: Optional[UpdateDownloadWorker] = None
        self._staged_payload: Optional[Path] = None

        self.setWindowTitle(f"{APP_NAME} - {t('update.dialog_title', default='Bản Cập Nhật Mới')}")
        self.setMinimumSize(700, 560)
        self.resize(740, 600)
        self.setStyleSheet(load_stylesheet())

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 20)
        layout.setSpacing(14)

        # 1. Header Banner Card
        banner = QFrame()
        banner.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #161b22, stop:1 #0d1117);
                border: 1px solid #30363d;
                border-radius: 12px;
                padding: 12px;
            }
        """)
        banner_layout = QHBoxLayout(banner)
        banner_layout.setContentsMargins(16, 12, 16, 12)
        banner_layout.setSpacing(16)

        icon_lbl = QLabel()
        icon_lbl.setPixmap(get_svg_pixmap("zap", "#38ef7d", 32))
        banner_layout.addWidget(icon_lbl)

        info_box = QVBoxLayout()
        info_box.setSpacing(4)

        tag_badge_text = t("update.new_version_available", default="ĐÃ CÓ PHIÊN BẢN MỚI!")
        badge_lbl = QLabel(f"🚀  {tag_badge_text}")
        badge_lbl.setStyleSheet("color: #38ef7d; font-size: 11px; font-weight: 800; letter-spacing: 0.5px;")
        info_box.addWidget(badge_lbl)

        title_lbl = QLabel(self.release.title or f"{APP_NAME} {self.release.tag_name}")
        title_lbl.setStyleSheet("color: #f0f6fc; font-size: 18px; font-weight: 700;")
        info_box.addWidget(title_lbl)

        # Version progression pill
        ver_row = QHBoxLayout()
        ver_row.setSpacing(8)

        cur_pill = QLabel(f"Hiện tại: v{self.current_version}")
        cur_pill.setStyleSheet("""
            background: #21262d; color: #8b949e; font-size: 11px; font-weight: 600;
            border-radius: 10px; padding: 2px 10px;
        """)
        ver_row.addWidget(cur_pill)

        arrow_lbl = QLabel("➔")
        arrow_lbl.setStyleSheet("color: #58a6ff; font-weight: 700; font-size: 12px;")
        ver_row.addWidget(arrow_lbl)

        new_pill = QLabel(f"Mới nhất: {self.release.tag_name}")
        new_pill.setStyleSheet("""
            background: #1f3b2e; color: #38ef7d; font-size: 11px; font-weight: 700;
            border: 1px solid #238636; border-radius: 10px; padding: 2px 10px;
        """)
        ver_row.addWidget(new_pill)

        if self.release.published_at:
            date_lbl = QLabel(f"• Ngày phát hành: {self.release.published_at}")
            date_lbl.setStyleSheet("color: #8b949e; font-size: 11px;")
            ver_row.addWidget(date_lbl)

        if self.release.asset_size > 0:
            size_mb = self.release.asset_size / (1024 * 1024)
            size_lbl = QLabel(f"• Dung lượng: {size_mb:.1f} MB")
            size_lbl.setStyleSheet("color: #8b949e; font-size: 11px;")
            ver_row.addWidget(size_lbl)

        ver_row.addStretch()
        info_box.addLayout(ver_row)

        banner_layout.addLayout(info_box, 1)
        layout.addWidget(banner)

        # 2. Changelog / Release Notes Card
        notes_lbl = QLabel(t("update.changelog", default="Nhật ký thay đổi (What's New):"))
        notes_lbl.setStyleSheet("color: #c9d1d9; font-size: 12px; font-weight: 700;")
        layout.addWidget(notes_lbl)

        self.changelog_box = QPlainTextEdit()
        self.changelog_box.setReadOnly(True)
        self.changelog_box.setPlainText(self.release.body or "Bản cập nhật tối ưu hóa hiệu năng và vá lỗi.")
        self.changelog_box.setStyleSheet("""
            QPlainTextEdit {
                background-color: #090d16;
                color: #e6edf3;
                border: 1px solid #21262d;
                border-radius: 8px;
                padding: 12px;
                font-family: 'Consolas', 'Cascadia Code', monospace;
                font-size: 12px;
                line-height: 1.5;
            }
        """)
        layout.addWidget(self.changelog_box, 1)

        # 3. Download & Installation Progress Frame (Obsidian Dark Card)
        self.progress_frame = QFrame()
        self.progress_frame.setVisible(False)
        self.progress_frame.setStyleSheet("""
            QFrame {
                background-color: #0d1117;
                border: 1px solid #30363d;
                border-radius: 8px;
                padding: 8px 12px;
            }
        """)
        prog_layout = QVBoxLayout(self.progress_frame)
        prog_layout.setContentsMargins(10, 8, 10, 8)
        prog_layout.setSpacing(6)

        prog_header_row = QHBoxLayout()
        self.lbl_status = QLabel(t("update.downloading", default="Đang tải bản cập nhật..."))
        self.lbl_status.setStyleSheet("color: #58a6ff; font-size: 12px; font-weight: 600;")
        prog_header_row.addWidget(self.lbl_status)

        prog_header_row.addStretch()

        self.lbl_details = QLabel("0 MB / 0 MB (0%)")
        self.lbl_details.setStyleSheet("color: #8b949e; font-size: 11px; font-family: monospace;")
        prog_header_row.addWidget(self.lbl_details)

        prog_layout.addLayout(prog_header_row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #161b22;
                border: none;
                border-radius: 4px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1f6feb, stop:1 #38ef7d);
                border-radius: 4px;
            }
        """)
        prog_layout.addWidget(self.progress_bar)

        layout.addWidget(self.progress_frame)

        # 4. Bottom controls
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(12)

        self.chk_startup = QCheckBox(t("update.auto_check_startup", default="Tự động kiểm tra cập nhật khi khởi động"))
        self.chk_startup.setChecked(True)
        self.chk_startup.setStyleSheet("color: #8b949e; font-size: 11px;")
        if self.config_repo:
            cfg = self.config_repo.load_config()
            self.chk_startup.setChecked(bool(cfg.get("check_updates_startup", True)))
            self.chk_startup.toggled.connect(self._save_startup_pref)
        bottom_row.addWidget(self.chk_startup)

        bottom_row.addStretch()

        self.btn_later = QPushButton(t("update.remind_later", default="Để Sau"))
        self.btn_later.setFixedHeight(36)
        self.btn_later.setStyleSheet("""
            QPushButton {
                background: #21262d; color: #c9d1d9; border: 1px solid #30363d;
                border-radius: 6px; padding: 0 16px; font-weight: 600;
            }
            QPushButton:hover { background: #30363d; color: #ffffff; }
        """)
        self.btn_later.clicked.connect(self._on_later_or_cancel_clicked)
        bottom_row.addWidget(self.btn_later)

        self.btn_github = QPushButton(t("update.view_on_github", default="Xem Trên GitHub"))
        self.btn_github.setIcon(get_svg_icon("globe", "#ffffff", 14))
        self.btn_github.setFixedHeight(36)
        self.btn_github.setStyleSheet("""
            QPushButton {
                background: #161b22; color: #58a6ff; border: 1px solid #30363d;
                border-radius: 6px; padding: 0 16px; font-weight: 600;
            }
            QPushButton:hover { background: #21262d; border-color: #58a6ff; }
        """)
        self.btn_github.clicked.connect(self._open_github)
        bottom_row.addWidget(self.btn_github)

        self.btn_action = QPushButton(t("update.auto_download_install", default="⚡ Tự Động Cập Nhật Ngay"))
        self.btn_action.setObjectName("primaryBtn")
        self.btn_action.setIcon(get_svg_icon("arrow_down", "#ffffff", 14))
        self.btn_action.setFixedHeight(36)
        self.btn_action.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #238636, stop:1 #2ea043);
                color: #ffffff; font-weight: 700; border: none; border-radius: 6px;
                padding: 0 20px; font-size: 12px;
            }
            QPushButton:hover { background: #2ea043; }
            QPushButton:disabled { background: #21262d; color: #6e7681; }
        """)
        self.btn_action.clicked.connect(self._start_auto_download)
        bottom_row.addWidget(self.btn_action)

        layout.addLayout(bottom_row)

    def _save_startup_pref(self, checked: bool):
        if self.config_repo:
            cfg = self.config_repo.load_config()
            cfg["check_updates_startup"] = checked
            self.config_repo.save_config(cfg)

    def _open_github(self):
        url = self.release.html_url
        if url:
            QDesktopServices.openUrl(QUrl(url))

    def _on_later_or_cancel_clicked(self):
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self.lbl_status.setText("Đang hủy quá trình tải...")
            self.lbl_status.setStyleSheet("color: #f85149; font-size: 12px; font-weight: 600;")
            self.btn_later.setEnabled(False)
        else:
            self.close()

    def _start_auto_download(self):
        url = self.release.download_url
        # If download URL is not a direct zip, fallback to web browser
        if not url or not url.endswith(".zip"):
            self._open_github()
            self.accept()
            return

        self.progress_frame.setVisible(True)
        self.lbl_status.setText(t("update.downloading", default="Đang tải bản cập nhật..."))
        self.lbl_status.setStyleSheet("color: #58a6ff; font-size: 12px; font-weight: 600;")
        self.lbl_details.setText("0 MB / 0 MB (0%)")
        self.progress_bar.setValue(0)

        self.btn_action.setEnabled(False)
        self.btn_action.setText("Đang Tải Xuống...")
        self.btn_later.setText(t("update.cancel", default="Hủy Bỏ"))

        self._worker = UpdateDownloadWorker(
            download_url=url,
            total_size=self.release.asset_size,
            parent=self
        )
        self._worker.progress.connect(self._on_download_progress)
        self._worker.status.connect(self._on_download_status)
        self._worker.finished.connect(self._on_download_finished)
        self._worker.start()

    def _on_download_progress(self, downloaded: int, total: int, pct: float, speed: float):
        self.progress_bar.setValue(int(pct))
        dl_mb = downloaded / (1024 * 1024)
        tot_mb = total / (1024 * 1024) if total > 0 else dl_mb
        speed_str = f"{speed / (1024 * 1024):.1f} MB/s" if speed >= 1048576 else f"{speed / 1024:.0f} KB/s"
        self.lbl_details.setText(f"{dl_mb:.1f} MB / {tot_mb:.1f} MB ({pct:.1f}%) • {speed_str}")

    def _on_download_status(self, message: str):
        self.lbl_status.setText(message)

    def _on_download_finished(self, success: bool, message: str, staged_payload: Optional[Path]):
        self.btn_later.setEnabled(True)
        self.btn_later.setText(t("update.close", default="Đóng"))

        if success and staged_payload:
            self._staged_payload = staged_payload
            self.progress_bar.setValue(100)
            self.progress_bar.setStyleSheet("""
                QProgressBar {
                    background-color: #161b22;
                    border: none;
                    border-radius: 4px;
                }
                QProgressBar::chunk {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #238636, stop:1 #38ef7d);
                    border-radius: 4px;
                }
            """)

            if UpdateCheckerService.is_app_frozen():
                # Compiled executable mode: in-place replacement and automatic relaunch
                self.lbl_status.setText(t("update.ready_to_restart", default="✅ Đã tải xong! Khởi động lại ứng dụng để hoàn tất cập nhật."))
                self.lbl_status.setStyleSheet("color: #38ef7d; font-size: 12px; font-weight: 700;")

                self.btn_action.setText(t("update.restart_and_update", default="🚀 Khởi Động Lại Để Cập Nhật"))
                self.btn_action.setIcon(get_svg_icon("refresh", "#ffffff", 14))
                self.btn_action.setStyleSheet("""
                    QPushButton {
                        background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #238636, stop:1 #38ef7d);
                        color: #0d1117; font-weight: 800; border: none; border-radius: 6px;
                        padding: 0 20px; font-size: 12px;
                    }
                    QPushButton:hover { background: #38ef7d; }
                """)
                self.btn_action.setEnabled(True)
                self.btn_action.clicked.disconnect()
                self.btn_action.clicked.connect(self._apply_restart_and_update)
            else:
                # Running from source (developer mode): safeguard developer repository
                self.lbl_status.setText(t("update.dev_mode_ready", default="✅ Đã giải nén bản cập nhật thành công (Chế độ Nhà phát triển)."))
                self.lbl_status.setStyleSheet("color: #58a6ff; font-size: 12px; font-weight: 700;")

                self.btn_action.setText(t("update.open_staged_folder", default="📂 Mở Thư Mục Bản Dựng"))
                self.btn_action.setIcon(get_svg_icon("folder", "#ffffff", 14))
                self.btn_action.setStyleSheet("""
                    QPushButton {
                        background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #1f6feb, stop:1 #58a6ff);
                        color: #ffffff; font-weight: 700; border: none; border-radius: 6px;
                        padding: 0 20px; font-size: 12px;
                    }
                    QPushButton:hover { background: #58a6ff; }
                """)
                self.btn_action.setEnabled(True)
                self.btn_action.clicked.disconnect()
                self.btn_action.clicked.connect(self._open_staged_dir)
        else:
            self.lbl_status.setText(f"❌ {message}")
            self.lbl_status.setStyleSheet("color: #f85149; font-size: 12px; font-weight: 600;")
            self.btn_action.setText("⚡ Thử Lại")
            self.btn_action.setEnabled(True)

    def _apply_restart_and_update(self):
        if not self._staged_payload:
            return

        service = UpdateCheckerService()
        src_dir, target_dir, exe_name = service.resolve_update_target(self._staged_payload)
        bat_script = service.generate_updater_script(src_dir, target_dir, exe_name)
        service.launch_updater(bat_script, src_dir, target_dir, exe_name)

        # Cleanly quit current process
        self.accept()
        QApplication.instance().quit()

    def _open_staged_dir(self):
        if self._staged_payload and Path(self._staged_payload).exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._staged_payload)))
        self.accept()

    def closeEvent(self, event):
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait(600)
        super().closeEvent(event)

