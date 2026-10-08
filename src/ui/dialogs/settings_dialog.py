"""
SettingsDialog combining output folder, API key managers, and script loader.
"""

from pathlib import Path
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFileDialog, QWidget, QFrame
)
from PyQt6.QtCore import pyqtSignal

from ...core.i18n import t
from ...core.models.scene import extract_scenes_from_json
from ..styles.tokens import load_stylesheet
from ..styles.icons import get_svg_icon, get_svg_pixmap
from .key_management_dialog import KeyManagementDialog
from .json_input_dialog import JsonInputDialog


class SettingsDialog(QDialog):
    """Studio settings and key management dialog."""

    configChanged = pyqtSignal()
    jsonLoaded = pyqtSignal(object, list)

    def __init__(self, config: dict, save_config_fn=None, parent=None):
        super().__init__(parent)
        self.config = config
        self.save_config_fn = save_config_fn

        self.setWindowTitle(t("settings.dialog_title"))
        self.setMinimumWidth(680)
        self.setMinimumHeight(560)
        self.setStyleSheet(load_stylesheet())

        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(24, 24, 24, 24)

        # Section 1: Output folder Card
        sec1 = QFrame()
        sec1.setObjectName("toolCard")
        sec1_l = QVBoxLayout(sec1)
        sec1_l.setContentsMargins(16, 14, 16, 14)
        sec1_l.setSpacing(10)
        sec1_l.addWidget(self._section_header(t("settings.media_output_dir"), "folder"))

        folder_row = QHBoxLayout()
        folder_row.setSpacing(8)
        self.output_input = QLineEdit(self.config.get("output_dir", ""))
        self.output_input.setReadOnly(True)
        self.output_input.setFixedHeight(34)
        folder_row.addWidget(self.output_input, 1)

        btn_browse = QPushButton(t("settings.browse_btn"))
        btn_browse.setIcon(get_svg_icon("folder", "#ffffff", 14))
        btn_browse.setFixedHeight(34)
        btn_browse.clicked.connect(self._browse_output)
        folder_row.addWidget(btn_browse)
        sec1_l.addLayout(folder_row)
        layout.addWidget(sec1)

        # Section 2: API Keys Card
        sec2 = QFrame()
        sec2.setObjectName("toolCard")
        sec2_l = QVBoxLayout(sec2)
        sec2_l.setContentsMargins(16, 14, 16, 14)
        sec2_l.setSpacing(10)
        sec2_l.addWidget(self._section_header(t("settings.api_keys_header"), "key"))

        self.keys_info_label = QLabel(
            f"Pexels: <b style='color:#34d399;'>{len(self.config.get('pexels_keys', []))}</b> keys  |  "
            f"Pixabay: <b style='color:#38bdf8;'>{len(self.config.get('pixabay_keys', []))}</b> keys  |  "
            f"Vecteezy: <b style='color:#a78bfa;'>{len(self.config.get('vecteezy_keys', []))}</b> keys"
        )
        self.keys_info_label.setStyleSheet("color: #cbd5e1; font-size: 12px; padding: 2px 0;")
        sec2_l.addWidget(self.keys_info_label)

        key_btn_row = QHBoxLayout()
        key_btn_row.setSpacing(8)
        btn_manage_pexels = QPushButton("Quản lý Pexels")
        btn_manage_pexels.setIcon(get_svg_icon("key", "#34d399", 14))
        btn_manage_pexels.setFixedHeight(34)
        btn_manage_pexels.clicked.connect(lambda: self._manage_keys("pexels"))
        key_btn_row.addWidget(btn_manage_pexels)

        btn_manage_pixabay = QPushButton("Quản lý Pixabay")
        btn_manage_pixabay.setIcon(get_svg_icon("key", "#38bdf8", 14))
        btn_manage_pixabay.setFixedHeight(34)
        btn_manage_pixabay.clicked.connect(lambda: self._manage_keys("pixabay"))
        key_btn_row.addWidget(btn_manage_pixabay)

        btn_manage_vecteezy = QPushButton("Quản lý Vecteezy")
        btn_manage_vecteezy.setIcon(get_svg_icon("key", "#a78bfa", 14))
        btn_manage_vecteezy.setFixedHeight(34)
        btn_manage_vecteezy.clicked.connect(lambda: self._manage_keys("vecteezy"))
        key_btn_row.addWidget(btn_manage_vecteezy)
        sec2_l.addLayout(key_btn_row)
        layout.addWidget(sec2)

        # Section 3: JSON Input Card
        sec3 = QFrame()
        sec3.setObjectName("toolCard")
        sec3_l = QVBoxLayout(sec3)
        sec3_l.setContentsMargins(16, 14, 16, 14)
        sec3_l.setSpacing(10)
        sec3_l.addWidget(self._section_header(t("settings.json_script_header"), "file-text"))

        scenes = getattr(parent, 'scenes', []) if parent else []
        if scenes:
            json_status = t("settings.script_loaded", count=len(scenes))
            color = "#34d399"
        else:
            json_status = t("settings.no_script_loaded")
            color = "#94a3b8"

        self.json_status_label = QLabel(json_status)
        self.json_status_label.setStyleSheet(f"color: {color}; font-size: 12px; font-weight: 600; padding: 2px 0;")
        sec3_l.addWidget(self.json_status_label)

        btn_json = QPushButton(t("settings.import_json_btn"))
        btn_json.setIcon(get_svg_icon("file-text", "#ffffff", 14))
        btn_json.setObjectName("primaryBtn")
        btn_json.setFixedHeight(36)
        btn_json.clicked.connect(self._show_json_dialog)
        sec3_l.addWidget(btn_json)
        layout.addWidget(sec3)

        # Section 4: Updates Card
        sec4 = QFrame()
        sec4.setObjectName("toolCard")
        sec4_l = QVBoxLayout(sec4)
        sec4_l.setContentsMargins(16, 14, 16, 14)
        sec4_l.setSpacing(10)
        sec4_l.addWidget(self._section_header(t("update.check_btn"), "arrow_down"))

        upd_row = QHBoxLayout()
        upd_row.setSpacing(10)
        from ...core.constants import APP_NAME, APP_VERSION
        upd_lbl = QLabel(f"{APP_NAME} v{APP_VERSION} [PRO]")
        upd_lbl.setStyleSheet("color: #cbd5e1; font-size: 12px; font-weight: 700;")
        upd_row.addWidget(upd_lbl)

        btn_check_upd = QPushButton(t("update.check_btn"))
        btn_check_upd.setIcon(get_svg_icon("arrow_down", "#ffffff", 14))
        btn_check_upd.setFixedHeight(34)
        btn_check_upd.clicked.connect(self._check_for_updates)
        upd_row.addWidget(btn_check_upd)
        upd_row.addStretch()
        sec4_l.addLayout(upd_row)
        layout.addWidget(sec4)

        layout.addStretch()

        # Close button
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_close = QPushButton(t("common.close"))
        btn_close.setFixedWidth(120)
        btn_close.setFixedHeight(36)
        btn_close.clicked.connect(self.accept)
        btn_row.addWidget(btn_close)
        layout.addLayout(btn_row)

    def _section_header(self, text: str, icon_name: str = "settings"):
        container = QWidget()
        h_lay = QHBoxLayout(container)
        h_lay.setContentsMargins(0, 0, 0, 4)
        h_lay.setSpacing(8)

        icon_lbl = QLabel()
        icon_lbl.setPixmap(get_svg_pixmap(icon_name, "#818cf8", 14))
        h_lay.addWidget(icon_lbl)

        lbl = QLabel(text)
        lbl.setStyleSheet("""
            color: #818cf8;
            font-size: 11px;
            font-weight: 800;
            letter-spacing: 1px;
            text-transform: uppercase;
        """)
        h_lay.addWidget(lbl)
        h_lay.addStretch()
        return container

    def _browse_output(self):
        current = self.output_input.text() or str(Path.home())
        path = QFileDialog.getExistingDirectory(self, t("common.browse"), current)
        if path:
            self.output_input.setText(path)
            self.config["output_dir"] = path
            if callable(self.save_config_fn):
                self.save_config_fn(self.config)
            self.configChanged.emit()

    def _manage_keys(self, platform: str = "pexels"):
        dialog = KeyManagementDialog(platform, self.config, save_config_fn=self.save_config_fn, parent=self)
        dialog.exec()
        self.keys_info_label.setText(
            f"Pexels: <b style='color:#34d399;'>{len(self.config.get('pexels_keys', []))}</b> keys  |  "
            f"Pixabay: <b style='color:#38bdf8;'>{len(self.config.get('pixabay_keys', []))}</b> keys  |  "
            f"Vecteezy: <b style='color:#a78bfa;'>{len(self.config.get('vecteezy_keys', []))}</b> keys"
        )
        self.configChanged.emit()

    def _show_json_dialog(self):
        dialog = JsonInputDialog(parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            json_data = dialog.result_data
            scenes = extract_scenes_from_json(json_data) if json_data else []
            if scenes:
                self.json_status_label.setText(t("settings.script_loaded", count=len(scenes)))
                self.json_status_label.setStyleSheet("color: #34d399; font-size: 12px;")
                self.jsonLoaded.emit(json_data, scenes)

    def _check_for_updates(self):
        from .update_dialog import UpdateDialog
        from ..workers.update_worker import UpdateCheckWorker
        from ...core.constants import APP_VERSION
        from ..components.toast_notification import ToastNotification

        self._upd_worker = UpdateCheckWorker(current_version=APP_VERSION, parent=self)
        def on_avail(release):
            d = UpdateDialog(release, current_version=APP_VERSION, parent=self)
            d.exec()
        def on_none(msg):
            ToastNotification.show_toast(self, msg, "info", 3000)
        def on_err(err):
            ToastNotification.show_toast(self, err, "warning", 3000)

        self._upd_worker.update_available.connect(on_avail)
        self._upd_worker.no_update.connect(on_none)
        self._upd_worker.error_occurred.connect(on_err)
        ToastNotification.show_toast(self, t("update.checking"), "info", 1500)
        self._upd_worker.start()

