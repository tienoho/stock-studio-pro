"""
Dialogs for viewing, adding, editing, and deleting API keys for media providers.
"""

import webbrowser
import threading
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QMessageBox, QScrollArea, QWidget, QFrame, QApplication
)
from PyQt6.QtCore import Qt, pyqtSignal

from ...core.i18n import t
from ..styles.icons import get_svg_icon, get_svg_pixmap
from ..styles.tokens import load_stylesheet
from ...infrastructure.providers.pexels_provider import PexelsProvider
from ...infrastructure.providers.pixabay_provider import PixabayProvider
from ...infrastructure.providers.vecteezy_provider import VecteezyProvider


class KeyDialog(QDialog):
    """Dialog for creating or editing an individual API key."""

    def __init__(self, platform: str, existing: dict = None, parent=None):
        super().__init__(parent)
        self.platform = platform.lower()
        self.existing = existing
        self.result_key = None

        action = "Sửa" if existing else "Thêm"
        self.setWindowTitle(f"{action} {platform.title()} API Key")
        self.setFixedWidth(460)
        self.setStyleSheet(load_stylesheet())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        title_h = QHBoxLayout()
        title_h.setSpacing(8)
        title_icon = QLabel()
        title_icon.setPixmap(get_svg_pixmap("key", "#f59e0b", 18))
        title_h.addWidget(title_icon)

        title = QLabel(f"{platform.title()} API Key")
        title.setStyleSheet("color: #f8fafc; font-size: 16px; font-weight: 800;")
        title_h.addWidget(title)
        title_h.addStretch()
        layout.addLayout(title_h)

        layout.addWidget(QLabel("Tên gợi nhớ (ví dụ: Key 1):"))
        self.name_input = QLineEdit()
        if existing:
            self.name_input.setText(existing.get("name", ""))
        layout.addWidget(self.name_input)

        layout.addWidget(QLabel(f"Mã API Key {platform.title()}:"))
        self.key_input = QLineEdit()
        self.key_input.setStyleSheet("font-family: 'Consolas', 'Cascadia Code', monospace;")
        if existing:
            self.key_input.setText(existing.get("key", ""))
        layout.addWidget(self.key_input)

        self.test_label = QLabel("")
        self.test_label.setStyleSheet("color: #94a3b8; font-size: 11px; font-weight: 600;")
        layout.addWidget(self.test_label)

        layout.addStretch()

        btn_h = QHBoxLayout()
        btn_h.setSpacing(10)

        btn_test = QPushButton(t("api_keys.test_key_btn"))
        btn_test.setIcon(get_svg_icon("zap", "#ffffff", 14))
        btn_test.clicked.connect(self._test_key)
        btn_h.addWidget(btn_test)

        btn_h.addStretch()

        btn_cancel = QPushButton(t("common.cancel"))
        btn_cancel.clicked.connect(self.reject)
        btn_h.addWidget(btn_cancel)

        btn_save = QPushButton(t("common.save"))
        btn_save.setIcon(get_svg_icon("save", "#ffffff", 14))
        btn_save.setObjectName("primaryBtn")
        btn_save.clicked.connect(self._save)
        btn_h.addWidget(btn_save)

        layout.addLayout(btn_h)
        self.name_input.setFocus()

    def _test_key(self):
        key = self.key_input.text().strip()
        if not key:
            self.test_label.setText("Vui lòng nhập API key trước khi kiểm tra")
            self.test_label.setStyleSheet("color: #fbbf24; font-size: 11px; font-weight: 600;")
            return

        self.test_label.setText("Đang kiểm tra kết nối...")
        self.test_label.setStyleSheet("color: #38bdf8; font-size: 11px; font-weight: 600;")
        QApplication.processEvents()

        def do_test():
            try:
                if self.platform == "pixabay":
                    provider = PixabayProvider(None)
                elif self.platform == "vecteezy":
                    provider = VecteezyProvider(None)
                else:
                    provider = PexelsProvider(None)

                ok, msg = provider.test_key(key)
                color = "#34d399" if ok else "#f87171"
                prefix = "[OK]" if ok else "[LỖI]"
                self.test_label.setText(f"{prefix} {msg}")
                self.test_label.setStyleSheet(f"color: {color}; font-size: 11px; font-weight: 700;")
            except Exception as e:
                self.test_label.setText(f"[LỖI] Kết nối: {e}")
                self.test_label.setStyleSheet("color: #f87171; font-size: 11px;")

        threading.Thread(target=do_test, daemon=True).start()

    def _save(self):
        name = self.name_input.text().strip()
        key = self.key_input.text().strip()
        if not name or not key:
            QMessageBox.warning(self, "Chưa đủ thông tin", "Vui lòng nhập tên gợi nhớ và mã API key.")
            return
        self.result_key = {"name": name, "key": key}
        self.accept()


class KeyManagementDialog(QDialog):
    """Dialog managing a platform's API keys."""

    keysChanged = pyqtSignal()

    def __init__(self, platform: str, config: dict, save_config_fn=None, parent=None):
        super().__init__(parent)
        self.platform = platform.lower()
        self.config = config
        self.save_config_fn = save_config_fn

        self.setWindowTitle(f"Quản lý {platform.title()} Keys")
        self.setMinimumSize(640, 520)
        self.setStyleSheet(load_stylesheet())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        title_h = QHBoxLayout()
        title_h.setSpacing(8)
        title_icon = QLabel()
        title_icon.setPixmap(get_svg_pixmap("key", "#f59e0b", 20))
        title_h.addWidget(title_icon)

        title = QLabel(f"Quản lý {platform.title()} API Keys")
        title.setStyleSheet("color: #f8fafc; font-size: 18px; font-weight: 800;")
        title_h.addWidget(title)
        title_h.addStretch()
        layout.addLayout(title_h)

        info = QLabel("Thêm nhiều API key để tự động luân phiên khi tải media.")
        info.setStyleSheet("color: #94a3b8; font-size: 12px;")
        layout.addWidget(info)

        self.list_scroll = QScrollArea()
        self.list_scroll.setWidgetResizable(True)
        self.list_scroll.setStyleSheet("QScrollArea { border: 1px solid #1e293b; border-radius: 10px; background-color: #0c0f17; }")

        self.list_container = QWidget()
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setContentsMargins(8, 8, 8, 8)
        self.list_layout.setSpacing(6)
        self.list_layout.addStretch()

        self.list_scroll.setWidget(self.list_container)
        layout.addWidget(self.list_scroll, 1)

        btn_h = QHBoxLayout()
        btn_h.setSpacing(8)

        btn_add = QPushButton(t("api_keys.add_key_btn"))
        btn_add.setIcon(get_svg_icon("plus", "#ffffff", 14))
        btn_add.setObjectName("primaryBtn")
        btn_add.clicked.connect(self._add_key)
        btn_h.addWidget(btn_add)

        btn_register = QPushButton(t("api_keys.get_free_key"))
        btn_register.setIcon(get_svg_icon("globe", "#ffffff", 14))
        btn_register.clicked.connect(self._open_register)
        btn_h.addWidget(btn_register)

        btn_h.addStretch()

        btn_close = QPushButton(t("common.close"))
        btn_close.setFixedWidth(100)
        btn_close.clicked.connect(self.accept)
        btn_h.addWidget(btn_close)

        layout.addLayout(btn_h)
        self._refresh_list()

    def _save_changes(self):
        if callable(self.save_config_fn):
            self.save_config_fn(self.config)

    def _refresh_list(self):
        while self.list_layout.count() > 1:
            item = self.list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        keys = self.config.get(f"{self.platform}_keys", [])
        if not keys:
            empty = QLabel("Chưa có API key nào. Nhấn 'Thêm Key' để bắt đầu.")
            empty.setStyleSheet("color: #64748b; padding: 40px; font-size: 13px; font-weight: 600;")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.list_layout.insertWidget(0, empty)
            return

        for idx, k in enumerate(keys):
            row = QFrame()
            row.setStyleSheet("""
                QFrame {
                    background-color: #131926;
                    border: 1px solid #1e293b;
                    border-radius: 8px;
                    padding: 4px;
                }
                QFrame:hover {
                    border-color: #6366f1;
                    background-color: #161e2e;
                }
            """)
            row.setFixedHeight(62)

            h = QHBoxLayout(row)
            h.setContentsMargins(12, 6, 12, 6)

            v = QVBoxLayout()
            v.setSpacing(2)

            row_header_h = QHBoxLayout()
            row_header_h.setSpacing(6)
            k_icon = QLabel()
            k_icon.setPixmap(get_svg_pixmap("zap", "#38bdf8", 12))
            row_header_h.addWidget(k_icon)

            name_lbl = QLabel(k['name'])
            name_lbl.setStyleSheet("color: #f8fafc; font-size: 13px; font-weight: 750; background: transparent;")
            row_header_h.addWidget(name_lbl)
            row_header_h.addStretch()
            v.addLayout(row_header_h)

            preview = k["key"][:20] + "..." + k["key"][-5:] if len(k["key"]) > 30 else k["key"]
            key_lbl = QLabel(preview)
            key_lbl.setStyleSheet("color: #94a3b8; font-size: 10px; font-family: 'Consolas', monospace; background: transparent;")
            v.addWidget(key_lbl)

            h.addLayout(v, 1)

            btn_edit = QPushButton(t("common.edit"))
            btn_edit.setFixedSize(60, 28)
            btn_edit.clicked.connect(lambda checked, i=idx: self._edit_key(i))
            h.addWidget(btn_edit)

            btn_del = QPushButton(t("common.delete"))
            btn_del.setIcon(get_svg_icon("trash", "#ffffff", 12))
            btn_del.setObjectName("dangerBtn")
            btn_del.setFixedSize(60, 28)
            btn_del.clicked.connect(lambda checked, i=idx: self._delete_key(i))
            h.addWidget(btn_del)

            self.list_layout.insertWidget(self.list_layout.count() - 1, row)

    def _add_key(self):
        dialog = KeyDialog(self.platform, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.result_key:
            key_list_name = f"{self.platform}_keys"
            if key_list_name not in self.config:
                self.config[key_list_name] = []
            self.config[key_list_name].append(dialog.result_key)
            self._save_changes()
            self._refresh_list()
            self.keysChanged.emit()

    def _edit_key(self, idx: int):
        key_list_name = f"{self.platform}_keys"
        keys = self.config.get(key_list_name, [])
        if 0 <= idx < len(keys):
            dialog = KeyDialog(self.platform, existing=keys[idx], parent=self)
            if dialog.exec() == QDialog.DialogCode.Accepted and dialog.result_key:
                keys[idx] = dialog.result_key
                self._save_changes()
                self._refresh_list()
                self.keysChanged.emit()

    def _delete_key(self, idx: int):
        key_list_name = f"{self.platform}_keys"
        keys = self.config.get(key_list_name, [])
        if 0 <= idx < len(keys):
            target = keys[idx]
            reply = QMessageBox.question(
                self, t("common.confirm"),
                f"Bạn có chắc muốn xóa API key '{target.get('name')}'?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                keys.pop(idx)
                self._save_changes()
                self._refresh_list()
                self.keysChanged.emit()

    def _open_register(self):
        urls = {
            "pexels": "https://www.pexels.com/api/",
            "pixabay": "https://pixabay.com/api/docs/",
            "vecteezy": "https://www.vecteezy.com/api"
        }
        url = urls.get(self.platform, "https://www.pexels.com/api/")
        webbrowser.open(url)
