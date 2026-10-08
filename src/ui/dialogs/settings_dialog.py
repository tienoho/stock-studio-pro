"""
SettingsDialog combining output folder, API key managers, and script loader.
"""

from pathlib import Path
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFileDialog, QWidget
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
        self.setMinimumWidth(650)
        self.setMinimumHeight(520)
        self.setStyleSheet(load_stylesheet())

        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(24, 24, 24, 24)

        # Section 1: Output folder
        layout.addWidget(self._section_header(t("settings.media_output_dir"), "folder"))

        folder_row = QHBoxLayout()
        self.output_input = QLineEdit(self.config.get("output_dir", ""))
        self.output_input.setReadOnly(True)
        folder_row.addWidget(self.output_input, 1)

        btn_browse = QPushButton(t("settings.browse_btn"))
        btn_browse.setIcon(get_svg_icon("folder", "#ffffff", 14))
        btn_browse.clicked.connect(self._browse_output)
        folder_row.addWidget(btn_browse)
        layout.addLayout(folder_row)

        # Section 2: API Keys
        layout.addWidget(self._section_header(t("settings.api_keys_header"), "key"))

        self.keys_info_label = QLabel(
            f"Pexels: <b style='color:#34d399;'>{len(self.config.get('pexels_keys', []))}</b> keys  |  "
            f"Pixabay: <b style='color:#38bdf8;'>{len(self.config.get('pixabay_keys', []))}</b> keys  |  "
            f"Vecteezy: <b style='color:#a78bfa;'>{len(self.config.get('vecteezy_keys', []))}</b> keys"
        )
        self.keys_info_label.setStyleSheet("color: #cbd5e1; font-size: 12px; padding: 4px 0;")
        layout.addWidget(self.keys_info_label)

        key_btn_row = QHBoxLayout()
        btn_manage_pexels = QPushButton("Quản lý Pexels")
        btn_manage_pexels.setIcon(get_svg_icon("key", "#34d399", 14))
        btn_manage_pexels.clicked.connect(lambda: self._manage_keys("pexels"))
        key_btn_row.addWidget(btn_manage_pexels)

        btn_manage_pixabay = QPushButton("Quản lý Pixabay")
        btn_manage_pixabay.setIcon(get_svg_icon("key", "#38bdf8", 14))
        btn_manage_pixabay.clicked.connect(lambda: self._manage_keys("pixabay"))
        key_btn_row.addWidget(btn_manage_pixabay)

        btn_manage_vecteezy = QPushButton("Quản lý Vecteezy")
        btn_manage_vecteezy.setIcon(get_svg_icon("key", "#a78bfa", 14))
        btn_manage_vecteezy.clicked.connect(lambda: self._manage_keys("vecteezy"))
        key_btn_row.addWidget(btn_manage_vecteezy)
        layout.addLayout(key_btn_row)

        # Section 3: JSON Input
        layout.addWidget(self._section_header(t("settings.json_script_header"), "file-text"))

        scenes = getattr(parent, 'scenes', []) if parent else []
        if scenes:
            json_status = t("settings.script_loaded", count=len(scenes))
            color = "#34d399"
        else:
            json_status = t("settings.no_script_loaded")
            color = "#94a3b8"

        self.json_status_label = QLabel(json_status)
        self.json_status_label.setStyleSheet(f"color: {color}; font-size: 12px; padding: 2px 0;")
        layout.addWidget(self.json_status_label)

        btn_json = QPushButton(t("settings.import_json_btn"))
        btn_json.setIcon(get_svg_icon("file-text", "#ffffff", 14))
        btn_json.setObjectName("primaryBtn")
        btn_json.clicked.connect(self._show_json_dialog)
        layout.addWidget(btn_json)

        layout.addStretch()

        # Close button
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_close = QPushButton(t("common.close"))
        btn_close.setFixedWidth(110)
        btn_close.clicked.connect(self.accept)
        btn_row.addWidget(btn_close)
        layout.addLayout(btn_row)

    def _section_header(self, text: str, icon_name: str = "settings"):
        container = QWidget()
        h_lay = QHBoxLayout(container)
        h_lay.setContentsMargins(0, 8, 0, 4)
        h_lay.setSpacing(6)

        icon_lbl = QLabel()
        icon_lbl.setPixmap(get_svg_pixmap(icon_name, "#818cf8", 14))
        h_lay.addWidget(icon_lbl)

        lbl = QLabel(text)
        lbl.setStyleSheet("""
            color: #818cf8;
            font-size: 11px;
            font-weight: 800;
            letter-spacing: 1.2px;
        """)
        h_lay.addWidget(lbl)
        h_lay.addStretch()

        container.setStyleSheet("border-bottom: 1px solid #1e293b;")
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
