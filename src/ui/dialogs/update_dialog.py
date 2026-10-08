"""
Modal dialog notifying the user about new software releases and updates.
Styled in the modern Obsidian Dark & Electric Neon theme.
"""

from pathlib import Path
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QPlainTextEdit, QFrame, QCheckBox, QApplication
)
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices

from ...application.services.update_checker import ReleaseInfo
from ...core.constants import APP_NAME, APP_VERSION
from ...core.i18n import t
from ..styles.icons import get_svg_icon, get_svg_pixmap
from ..styles.tokens import load_stylesheet


class UpdateDialog(QDialog):
    """High-end modal dialog displaying available updates and changelog."""

    def __init__(self, release: ReleaseInfo, current_version: str = APP_VERSION, config_repo=None, parent=None):
        super().__init__(parent)
        self.release = release
        self.current_version = current_version
        self.config_repo = config_repo

        self.setWindowTitle(f"{APP_NAME} - {t('update.dialog_title', default='Bản Cập Nhật Mới')}")
        self.setMinimumSize(680, 520)
        self.resize(720, 560)
        self.setStyleSheet(load_stylesheet())

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 20)
        layout.setSpacing(16)

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

        # 3. Bottom controls
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

        btn_later = QPushButton(t("update.remind_later", default="Để Sau"))
        btn_later.setFixedHeight(36)
        btn_later.setStyleSheet("""
            QPushButton {
                background: #21262d; color: #c9d1d9; border: 1px solid #30363d;
                border-radius: 6px; padding: 0 16px; font-weight: 600;
            }
            QPushButton:hover { background: #30363d; color: #ffffff; }
        """)
        btn_later.clicked.connect(self.close)
        bottom_row.addWidget(btn_later)

        btn_github = QPushButton(t("update.view_on_github", default="Xem Trên GitHub"))
        btn_github.setIcon(get_svg_icon("globe", "#ffffff", 14))
        btn_github.setFixedHeight(36)
        btn_github.setStyleSheet("""
            QPushButton {
                background: #161b22; color: #58a6ff; border: 1px solid #30363d;
                border-radius: 6px; padding: 0 16px; font-weight: 600;
            }
            QPushButton:hover { background: #21262d; border-color: #58a6ff; }
        """)
        btn_github.clicked.connect(self._open_github)
        bottom_row.addWidget(btn_github)

        self.btn_download = QPushButton(t("update.download_now", default="⚡ Tải & Cập Nhật (.ZIP)"))
        self.btn_download.setObjectName("primaryBtn")
        self.btn_download.setIcon(get_svg_icon("arrow_down", "#ffffff", 14))
        self.btn_download.setFixedHeight(36)
        self.btn_download.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #238636, stop:1 #2ea043);
                color: #ffffff; font-weight: 700; border: none; border-radius: 6px;
                padding: 0 20px; font-size: 12px;
            }
            QPushButton:hover { background: #2ea043; }
        """)
        self.btn_download.clicked.connect(self._download_release)
        bottom_row.addWidget(self.btn_download)

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

    def _download_release(self):
        url = self.release.download_url or self.release.html_url
        if url:
            QDesktopServices.openUrl(QUrl(url))
        self.accept()
