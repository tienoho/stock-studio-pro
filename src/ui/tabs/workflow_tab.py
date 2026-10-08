"""
Visual Node-based Workflow Canvas Tab with SQLite preset storage.
"""

import json
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QComboBox, QPushButton, QPlainTextEdit, QFileDialog,
    QInputDialog, QMessageBox, QFrame
)
from PyQt6.QtCore import pyqtSignal
from ...core.i18n import t
from ..styles.icons import get_svg_icon, get_svg_pixmap
from ..workflow.canvas import WorkflowCanvas
from ...infrastructure.persistence.sqlite_workflow_repo import SqliteWorkflowRepository


class WorkflowTab(QWidget):
    """Tab containing the node-based workflow visualizer and execution engine."""

    runWorkflowRequested = pyqtSignal()

    def __init__(self, parent_window=None, parent=None):
        super().__init__(parent)
        self.parent_window = parent_window
        self.workflow_repo = SqliteWorkflowRepository()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        self.title_lbl = QLabel(t("workflow.title"))
        self.title_lbl.setObjectName("heroTitle")
        layout.addWidget(self.title_lbl)

        self.hint_lbl = QLabel(t("workflow.hint"))
        self.hint_lbl.setObjectName("mutedText")
        self.hint_lbl.setWordWrap(True)
        layout.addWidget(self.hint_lbl)

        # Controls Row 1: Add Node & Run
        top = QHBoxLayout()
        self.workflow_block_combo = QComboBox()
        self.workflow_block_combo.addItems([
            "Load JSON", "Search stock", "Random select", "Download selected",
            "Cut/Mix video", "Create voice", "Scene voice match"
        ])
        top.addWidget(self.workflow_block_combo)

        self.btn_add_node = QPushButton(t("workflow.add_node"))
        self.btn_add_node.setIcon(get_svg_icon("plus", "#ffffff", 14))
        self.btn_add_node.clicked.connect(self._workflow_canvas_add)
        top.addWidget(self.btn_add_node)

        self.btn_run = QPushButton(t("workflow.run_workflow"))
        self.btn_run.setIcon(get_svg_icon("play", "#ffffff", 14))
        self.btn_run.setObjectName("primaryBtn")
        self.btn_run.clicked.connect(self.runWorkflowRequested.emit)
        top.addWidget(self.btn_run)

        self.btn_clear = QPushButton(t("workflow.clear_canvas"))
        self.btn_clear.setIcon(get_svg_icon("trash", "#f87171", 14))
        self.btn_clear.clicked.connect(self._workflow_clear)
        top.addWidget(self.btn_clear)

        top.addStretch()
        layout.addLayout(top)

        # Controls Row 2: SQLite Presets Bar
        preset_bar = QHBoxLayout()
        preset_bar.setSpacing(6)

        self.preset_icon = QLabel()
        self.preset_icon.setPixmap(get_svg_pixmap("database", "#818cf8", 14))
        preset_bar.addWidget(self.preset_icon)

        self.preset_lbl = QLabel(t("workflow.sqlite_presets"))
        self.preset_lbl.setStyleSheet("color: #818cf8; font-weight: 700; font-size: 11px;")
        preset_bar.addWidget(self.preset_lbl)

        self.sqlite_preset_combo = QComboBox()
        self.sqlite_preset_combo.setMinimumWidth(160)
        preset_bar.addWidget(self.sqlite_preset_combo)

        self.btn_load_db = QPushButton(t("workflow.load_db"))
        self.btn_load_db.setIcon(get_svg_icon("refresh", "#58a6ff", 14))
        self.btn_load_db.clicked.connect(self._load_sqlite_preset)
        preset_bar.addWidget(self.btn_load_db)

        self.btn_save_db = QPushButton(t("workflow.save_db"))
        self.btn_save_db.setIcon(get_svg_icon("save", "#34d399", 14))
        self.btn_save_db.clicked.connect(self._save_sqlite_preset)
        preset_bar.addWidget(self.btn_save_db)

        self.btn_del_db = QPushButton(t("workflow.delete_db"))
        self.btn_del_db.setIcon(get_svg_icon("trash", "#f87171", 14))
        self.btn_del_db.clicked.connect(self._delete_sqlite_preset)
        preset_bar.addWidget(self.btn_del_db)

        # Separator
        preset_bar.addSpacing(12)
        self.file_lbl = QLabel("File:")
        self.file_lbl.setStyleSheet("color: #64748b; font-size: 11px;")
        preset_bar.addWidget(self.file_lbl)

        self.btn_save_file = QPushButton("Xuất JSON")
        self.btn_save_file.setIcon(get_svg_icon("file-text", "#94a3b8", 14))
        self.btn_save_file.clicked.connect(self._workflow_save)
        preset_bar.addWidget(self.btn_save_file)

        self.btn_load_file = QPushButton("Mở JSON")
        self.btn_load_file.setIcon(get_svg_icon("folder", "#94a3b8", 14))
        self.btn_load_file.clicked.connect(self._workflow_load)
        preset_bar.addWidget(self.btn_load_file)

        preset_bar.addStretch()
        layout.addLayout(preset_bar)

        self.workflow_canvas = WorkflowCanvas(parent_window or self)
        layout.addWidget(self.workflow_canvas, 1)

        self.workflow_log = QPlainTextEdit()
        self.workflow_log.setReadOnly(True)
        self.workflow_log.setMaximumHeight(110)
        layout.addWidget(self.workflow_log)

        # Initial load of SQLite presets
        self._refresh_sqlite_presets()

    def retranslate_ui(self):
        """Updates all text elements upon language switch."""
        self.title_lbl.setText(t("workflow.title"))
        self.hint_lbl.setText(t("workflow.hint"))
        self.btn_add_node.setText(t("workflow.add_node"))
        self.btn_run.setText(t("workflow.run_workflow"))
        self.btn_clear.setText(t("workflow.clear_canvas"))
        self.preset_lbl.setText(t("workflow.sqlite_presets"))
        self.btn_load_db.setText(t("workflow.load_db"))
        self.btn_save_db.setText(t("workflow.save_db"))
        self.btn_del_db.setText(t("workflow.delete_db"))

    def _refresh_sqlite_presets(self):
        """Reloads preset names from SQLite into combo box."""
        self.sqlite_preset_combo.clear()
        names = self.workflow_repo.list_presets()
        if names:
            self.sqlite_preset_combo.addItems(names)
        else:
            self.sqlite_preset_combo.addItem(t("workflow.no_preset"))

    def _save_sqlite_preset(self):
        name, ok = QInputDialog.getText(self, t("workflow.prompt_save_title"), t("workflow.prompt_save_label"))
        if ok and name.strip():
            payload = self.workflow_canvas.save_payload()
            self.workflow_repo.save_preset(name.strip(), payload)
            self._refresh_sqlite_presets()
            idx = self.sqlite_preset_combo.findText(name.strip())
            if idx >= 0:
                self.sqlite_preset_combo.setCurrentIndex(idx)
            self.workflow_log.appendPlainText(t("workflow.save_success", name=name.strip()))

    def _load_sqlite_preset(self):
        name = self.sqlite_preset_combo.currentText()
        if not name or name == t("workflow.no_preset") or name == "(Chưa có preset)":
            QMessageBox.information(self, t("common.info"), "Vui lòng chọn một mẫu quy trình hợp lệ để nạp.")
            return

        payload = self.workflow_repo.get_preset(name)
        if payload:
            self.workflow_canvas.load_payload(payload)
            self.workflow_log.appendPlainText(t("workflow.load_success", name=name))
        else:
            QMessageBox.warning(self, t("common.error"), f"Không tìm thấy dữ liệu cho mẫu '{name}'")

    def _delete_sqlite_preset(self):
        name = self.sqlite_preset_combo.currentText()
        if not name or name == t("workflow.no_preset") or name == "(Chưa có preset)":
            return
        reply = QMessageBox.question(
            self, t("common.confirm"), t("workflow.delete_confirm", name=name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.workflow_repo.delete_preset(name)
            self._refresh_sqlite_presets()
            self.workflow_log.appendPlainText(t("workflow.delete_success", name=name))

    def _workflow_canvas_add(self):
        self.workflow_canvas.add_node(self.workflow_block_combo.currentText())

    def _workflow_clear(self):
        self.workflow_canvas.clear()
        self.workflow_log.clear()

    def _workflow_save(self):
        path, _ = QFileDialog.getSaveFileName(self, "Lưu file mẫu quy trình", "workflow_preset.json", "JSON (*.json)")
        if path:
            Path(path).write_text(
                json.dumps(self.workflow_canvas.save_payload(), ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
            self.workflow_log.appendPlainText(f"Đã lưu: {path}")

    def _workflow_load(self):
        path, _ = QFileDialog.getOpenFileName(self, "Mở file mẫu quy trình", "", "JSON (*.json)")
        if path:
            self.workflow_canvas.load_payload(json.loads(Path(path).read_text(encoding="utf-8")))
            self.workflow_log.appendPlainText(f"Đã nạp: {path}")
