"""
Interactive API Key Manager widget embedded directly in the main studio UI.
Persists keys into SQLite database with live testing, toggling, and round-robin sync.
"""

from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from PyQt6.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QCheckBox, QScrollArea, QMessageBox, QFileDialog
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread

from ...core.i18n import t
from ..styles.icons import get_svg_icon, get_svg_pixmap
from ...infrastructure.persistence.sqlite_config_repo import SqliteConfigRepository
from ...infrastructure.providers.pexels_provider import PexelsProvider
from ...infrastructure.providers.pixabay_provider import PixabayProvider
from ...infrastructure.providers.vecteezy_provider import VecteezyProvider
from ...infrastructure.providers.coverr_provider import CoverrProvider
from ...infrastructure.providers.wikimedia_provider import WikimediaProvider
from ...infrastructure.providers.openverse_provider import OpenverseProvider


class KeyTesterThread(QThread):
    """Background thread to validate API key with external provider."""
    resultReady = pyqtSignal(bool, str)

    def __init__(self, platform: str, key_str: str):
        super().__init__()
        self.platform = platform.lower()
        self.key_str = key_str

    def run(self):
        try:
            if "pexels" in self.platform:
                tester = PexelsProvider()
                ok, msg = tester.test_key(self.key_str)
            elif "pixabay" in self.platform:
                tester = PixabayProvider()
                ok, msg = tester.test_key(self.key_str)
            elif "vecteezy" in self.platform:
                tester = VecteezyProvider()
                ok, msg = tester.test_key(self.key_str)
            elif "coverr" in self.platform:
                tester = CoverrProvider()
                ok, msg = tester.test_key(self.key_str)
            elif "wikimedia" in self.platform:
                tester = WikimediaProvider()
                ok, msg = tester.test_key(self.key_str)
            elif "openverse" in self.platform:
                tester = OpenverseProvider()
                ok, msg = tester.test_key(self.key_str)
            else:
                ok, msg = False, "Nguồn không hỗ trợ"
            self.resultReady.emit(ok, msg)
        except Exception as e:
            self.resultReady.emit(False, str(e))


class ApiKeyManagerWidget(QFrame):
    """Interactive widget embedded directly in Setup Sidebar for managing SQLite API keys."""

    keysChanged = pyqtSignal()

    def __init__(self, config_repo: SqliteConfigRepository, parent=None):
        super().__init__(parent)
        self.config_repo = config_repo
        self.setObjectName("apiKeyCard")
        self.setStyleSheet("""
            #apiKeyCard {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #121826, stop:1 #0c101a);
                border: 1px solid #1f2b3f;
                border-radius: 12px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Header with vector key icon and expand/collapse toggle
        header_h = QHBoxLayout()
        header_h.setSpacing(6)

        self.header_icon = QLabel()
        self.header_icon.setPixmap(get_svg_pixmap("key", "#818cf8", 14))
        header_h.addWidget(self.header_icon)

        self.header_lbl = QLabel(t("api_keys.header_title"))
        self.header_lbl.setObjectName("sectionHeader")
        header_h.addWidget(self.header_lbl)
        header_h.addStretch()

        self.btn_backup = QPushButton()
        self.btn_backup.setIcon(get_svg_icon("database", "#38bdf8", 13))
        self.btn_backup.setFixedSize(24, 24)
        self.btn_backup.setToolTip(t("common.backup"))
        self.btn_backup.setStyleSheet("""
            QPushButton {
                background-color: #172133;
                border-radius: 6px;
                border: 1px solid #25334d;
            }
            QPushButton:hover { background-color: #0369a1; border-color: #38bdf8; }
        """)
        self.btn_backup.clicked.connect(self._backup_db)
        header_h.addWidget(self.btn_backup)

        self.btn_toggle_expand = QPushButton()
        self.btn_toggle_expand.setIcon(get_svg_icon("chevron-down", "#94a3b8", 12))
        self.btn_toggle_expand.setFixedSize(24, 24)
        self.btn_toggle_expand.setStyleSheet("""
            QPushButton {
                background-color: #172133;
                border-radius: 6px;
                border: 1px solid #25334d;
            }
            QPushButton:hover { background-color: #25334d; border-color: #3b4d6e; }
        """)
        self.btn_toggle_expand.clicked.connect(self._toggle_expand)
        header_h.addWidget(self.btn_toggle_expand)
        layout.addLayout(header_h)

        # Live status badges row
        self.status_badges_layout = QHBoxLayout()
        self.status_badges_layout.setSpacing(4)
        self.badge_pexels = QLabel("Pexels: 0")
        self.badge_pixabay = QLabel("Pixabay: 0")
        self.badge_coverr = QLabel("Coverr: 0")
        self.badge_vecteezy = QLabel("Vecteezy: 0")
        self.badge_free = QLabel("Wiki/Openverse: Free ✓")

        for b in [self.badge_pexels, self.badge_pixabay, self.badge_coverr, self.badge_vecteezy, self.badge_free]:
            b.setStyleSheet("""
                background: #090d15;
                color: #94a3b8;
                font-size: 9px;
                font-weight: 700;
                padding: 3px 5px;
                border-radius: 5px;
                border: 1px solid #1f2b3f;
            """)
            b.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.status_badges_layout.addWidget(b)

        layout.addLayout(self.status_badges_layout)

        # Quick Add Box
        add_box = QVBoxLayout()
        add_box.setSpacing(6)

        input_row = QHBoxLayout()
        input_row.setSpacing(4)
        self.combo_platform = QComboBox()
        self.combo_platform.addItems(["Pexels", "Pixabay", "Coverr", "Vecteezy"])
        self.combo_platform.setFixedHeight(28)
        self.combo_platform.setStyleSheet("font-size: 11px; font-weight: bold; padding: 2px 6px;")
        input_row.addWidget(self.combo_platform)

        self.input_key = QLineEdit()
        self.input_key.setPlaceholderText(t("api_keys.input_placeholder"))
        self.input_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.input_key.setFixedHeight(28)
        self.input_key.setStyleSheet("font-size: 11px; padding: 2px 8px;")
        input_row.addWidget(self.input_key, 1)

        self.btn_toggle_vis = QPushButton()
        self.btn_toggle_vis.setIcon(get_svg_icon("eye", "#94a3b8", 13))
        self.btn_toggle_vis.setFixedSize(28, 28)
        self.btn_toggle_vis.setToolTip("Hiện/ẩn ký tự key")
        self.btn_toggle_vis.clicked.connect(self._toggle_password_echo)
        input_row.addWidget(self.btn_toggle_vis)
        add_box.addLayout(input_row)

        # Button row: Add Key & Test Key
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)

        self.btn_add = QPushButton(t("api_keys.add_key_btn"))
        self.btn_add.setIcon(get_svg_icon("plus", "#ffffff", 12))
        self.btn_add.setObjectName("primaryBtn")
        self.btn_add.setFixedHeight(28)
        self.btn_add.setStyleSheet("font-size: 11px; font-weight: bold; padding: 2px 10px;")
        self.btn_add.clicked.connect(self._add_key)
        btn_row.addWidget(self.btn_add)

        self.btn_test = QPushButton(t("api_keys.test_key_btn"))
        self.btn_test.setIcon(get_svg_icon("zap", "#38bdf8", 12))
        self.btn_test.setFixedHeight(28)
        self.btn_test.setStyleSheet("""
            QPushButton {
                background: #172133;
                color: #38bdf8;
                border: 1px solid rgba(56, 189, 248, 0.4);
                border-radius: 6px;
                font-size: 11px;
                font-weight: bold;
                padding: 2px 10px;
            }
            QPushButton:hover { background: #0369a1; color: #ffffff; border-color: #38bdf8; }
        """)
        self.btn_test.clicked.connect(self._test_input_key)
        btn_row.addWidget(self.btn_test)

        add_box.addLayout(btn_row)
        layout.addLayout(add_box)

        # Test feedback label
        self.test_feedback_label = QLabel("")
        self.test_feedback_label.setStyleSheet("font-size: 10px; font-weight: 600; padding: 2px 0;")
        self.test_feedback_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.test_feedback_label.setVisible(False)
        layout.addWidget(self.test_feedback_label)

        # Collapsible List of existing keys
        self.keys_scroll = QScrollArea()
        self.keys_scroll.setWidgetResizable(True)
        self.keys_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.keys_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.keys_scroll.setMaximumHeight(150)
        self.keys_scroll.setStyleSheet("""
            QScrollArea {
                background: #090d16;
                border: 1px solid #1f2b3f;
                border-radius: 8px;
            }
        """)

        self.keys_container = QWidget()
        self.keys_layout = QVBoxLayout(self.keys_container)
        self.keys_layout.setContentsMargins(4, 4, 4, 4)
        self.keys_layout.setSpacing(3)
        self.keys_scroll.setWidget(self.keys_container)
        layout.addWidget(self.keys_scroll)

        self._is_expanded = True
        self.refresh_keys_display()

    def _toggle_expand(self):
        self._is_expanded = not self._is_expanded
        self.keys_scroll.setVisible(self._is_expanded)
        icon_name = "chevron-down" if self._is_expanded else "chevron-up"
        self.btn_toggle_expand.setIcon(get_svg_icon(icon_name, "#94a3b8", 12))

    def _toggle_password_echo(self):
        if self.input_key.echoMode() == QLineEdit.EchoMode.Password:
            self.input_key.setEchoMode(QLineEdit.EchoMode.Normal)
            self.btn_toggle_vis.setIcon(get_svg_icon("eye-off", "#94a3b8", 13))
        else:
            self.input_key.setEchoMode(QLineEdit.EchoMode.Password)
            self.btn_toggle_vis.setIcon(get_svg_icon("eye", "#94a3b8", 13))

    def _add_key(self):
        key_str = self.input_key.text().strip()
        if not key_str:
            QMessageBox.warning(self, t("common.warning"), "Vui lòng nhập API key trước khi thêm.")
            return

        platform = self.combo_platform.currentText().lower()
        if not self.config_repo or not hasattr(self.config_repo, "add_api_key"):
            QMessageBox.warning(self, t("common.error"), "Repository không hỗ trợ lưu SQLite.")
            return

        count = len(self.config_repo.get_api_keys(platform)) if hasattr(self.config_repo, "get_api_keys") else 0
        name = f"{platform.capitalize()} Key {count + 1}"

        new_id = self.config_repo.add_api_key(platform, name, key_str, is_active=True)
        if new_id:
            self.input_key.clear()
            self.test_feedback_label.setText(f"{t('api_keys.added_success')} ({name})")
            self.test_feedback_label.setStyleSheet("color: #34d399; font-size: 9px; font-weight: bold;")
            self.test_feedback_label.setVisible(True)
            self.refresh_keys_display()
            self.keysChanged.emit()

    def _test_input_key(self):
        key_str = self.input_key.text().strip()
        if not key_str:
            QMessageBox.warning(self, t("common.warning"), "Nhập API key vào ô để kiểm tra.")
            return

        platform = self.combo_platform.currentText().lower()
        self.btn_test.setEnabled(False)
        self.test_feedback_label.setText(t("api_keys.testing"))
        self.test_feedback_label.setStyleSheet("color: #38bdf8; font-size: 9px;")
        self.test_feedback_label.setVisible(True)

        self.tester = KeyTesterThread(platform, key_str)
        self.tester.resultReady.connect(self._on_test_result)
        self.tester.start()

    def _on_test_result(self, ok: bool, msg: str):
        self.btn_test.setEnabled(True)
        if ok:
            self.test_feedback_label.setText(t("api_keys.test_valid", msg=msg))
            self.test_feedback_label.setStyleSheet("color: #34d399; font-size: 9px; font-weight: bold;")
        else:
            self.test_feedback_label.setText(t("api_keys.test_invalid", msg=msg))
            self.test_feedback_label.setStyleSheet("color: #f87171; font-size: 9px; font-weight: bold;")

    def retranslate_ui(self):
        """Updates all labels and buttons when application language switches."""
        self.header_lbl.setText(t("api_keys.header_title"))
        self.input_key.setPlaceholderText(t("api_keys.input_placeholder"))
        self.btn_add.setText(t("api_keys.add_key_btn"))
        self.btn_test.setText(t("api_keys.test_key_btn"))
        self.btn_backup.setToolTip(t("common.backup"))
        self.refresh_keys_display()

    def refresh_keys_display(self):
        """Re-reads SQLite and renders key rows."""
        # Clear existing rows
        while self.keys_layout.count():
            item = self.keys_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        all_keys = self.config_repo.get_api_keys() if (self.config_repo and hasattr(self.config_repo, "get_api_keys")) else []

        # Update status badges
        n_pex = sum(1 for k in all_keys if k["platform"] == "pexels" and k["is_active"])
        n_pix = sum(1 for k in all_keys if k["platform"] == "pixabay" and k["is_active"])
        n_cov = sum(1 for k in all_keys if k["platform"] == "coverr" and k["is_active"])
        n_vec = sum(1 for k in all_keys if k["platform"] == "vecteezy" and k["is_active"])

        self.badge_pexels.setText(f"Pexels: {n_pex}")
        self.badge_pexels.setStyleSheet(f"background: #0c0f17; color: {'#34d399' if n_pex else '#64748b'}; font-size: 9px; font-weight: 700; padding: 2px 4px; border-radius: 4px; border: 1px solid {'#059669' if n_pex else '#1e293b'};")

        self.badge_pixabay.setText(f"Pixabay: {n_pix}")
        self.badge_pixabay.setStyleSheet(f"background: #0c0f17; color: {'#38bdf8' if n_pix else '#64748b'}; font-size: 9px; font-weight: 700; padding: 2px 4px; border-radius: 4px; border: 1px solid {'#0284c7' if n_pix else '#1e293b'};")

        self.badge_coverr.setText(f"Coverr: {n_cov}")
        self.badge_coverr.setStyleSheet(f"background: #0c0f17; color: {'#ec4899' if n_cov else '#64748b'}; font-size: 9px; font-weight: 700; padding: 2px 4px; border-radius: 4px; border: 1px solid {'#be185d' if n_cov else '#1e293b'};")

        self.badge_vecteezy.setText(f"Vecteezy: {n_vec}")
        self.badge_vecteezy.setStyleSheet(f"background: #0c0f17; color: {'#a78bfa' if n_vec else '#64748b'}; font-size: 9px; font-weight: 700; padding: 2px 4px; border-radius: 4px; border: 1px solid {'#7c3aed' if n_vec else '#1e293b'};")

        self.badge_free.setStyleSheet("background: #0c0f17; color: #10b981; font-size: 9px; font-weight: 700; padding: 2px 4px; border-radius: 4px; border: 1px solid #059669;")

        if not all_keys:
            empty_lbl = QLabel(t("api_keys.empty_db"))
            empty_lbl.setStyleSheet("color: #64748b; font-size: 9px; padding: 10px;")
            empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.keys_layout.addWidget(empty_lbl)
            return

        for k in all_keys:
            row = QFrame()
            row.setStyleSheet("""
                QFrame {
                    background: #131926;
                    border: 1px solid #1e293b;
                    border-radius: 4px;
                }
            """)
            r_lay = QHBoxLayout(row)
            r_lay.setContentsMargins(4, 2, 4, 2)
            r_lay.setSpacing(4)

            # Active checkbox
            cb = QCheckBox()
            cb.setChecked(k["is_active"])
            cb.toggled.connect(lambda checked, kid=k["id"]: self._toggle_key(kid, checked))
            r_lay.addWidget(cb)

            # Platform tag
            plat_color = {
                "pexels": "#34d399",
                "pixabay": "#38bdf8",
                "coverr": "#ec4899",
                "vecteezy": "#a78bfa",
                "wikimedia": "#06b6d4",
                "openverse": "#f97316"
            }.get(k["platform"], "#94a3b8")
            tag = QLabel(k["platform"][:3].upper())
            tag.setStyleSheet(f"color: {plat_color}; font-size: 9px; font-weight: 800;")
            r_lay.addWidget(tag)

            # Masked key
            raw_key = k["key"]
            masked = f"...{raw_key[-6:]}" if len(raw_key) > 6 else raw_key
            val_lbl = QLabel(masked)
            val_lbl.setStyleSheet("color: #cbd5e1; font-family: monospace; font-size: 9px;")
            r_lay.addWidget(val_lbl, 1)

            # Last used timestamp / activity indicator
            if k.get("last_used"):
                time_str = str(k["last_used"]).split(" ")[-1][:5]
                info_lbl = QLabel(time_str)
                info_lbl.setToolTip(t("api_keys.last_used", time=k['last_used']))
                info_lbl.setStyleSheet("color: #64748b; font-size: 8px; font-family: monospace;")
                r_lay.addWidget(info_lbl)

            # Vector trash icon delete button
            del_btn = QPushButton()
            del_btn.setIcon(get_svg_icon("trash", "#f87171", 12))
            del_btn.setToolTip(t("common.delete"))
            del_btn.setFixedSize(20, 20)
            del_btn.setStyleSheet("""
                QPushButton { background: transparent; border: none; }
                QPushButton:hover { background: #450a0a; border-radius: 2px; }
            """)
            del_btn.clicked.connect(lambda _, kid=k["id"]: self._delete_key(kid))
            r_lay.addWidget(del_btn)

            self.keys_layout.addWidget(row)

    def _backup_db(self):
        default_name = f"autostock_studio_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        path, _ = QFileDialog.getSaveFileName(self, t("common.backup"), default_name, "SQLite Database (*.db)")
        if path:
            if self.config_repo and hasattr(self.config_repo, "db"):
                ok = self.config_repo.db.backup_database(Path(path))
                if ok:
                    QMessageBox.information(self, t("api_keys.backup_success_title"), t("api_keys.backup_success_msg", path=path))
                else:
                    QMessageBox.warning(self, t("api_keys.backup_failed_title"), t("api_keys.backup_failed_msg"))

    def _toggle_key(self, key_id: int, is_active: bool):
        if self.config_repo and hasattr(self.config_repo, "toggle_api_key"):
            self.config_repo.toggle_api_key(key_id, is_active)
        self.refresh_keys_display()
        self.keysChanged.emit()

    def _delete_key(self, key_id: int):
        reply = QMessageBox.question(
            self, t("api_keys.delete_confirm_title"), t("api_keys.delete_confirm_msg"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            if self.config_repo and hasattr(self.config_repo, "delete_api_key"):
                self.config_repo.delete_api_key(key_id)
            self.refresh_keys_display()
            self.keysChanged.emit()
