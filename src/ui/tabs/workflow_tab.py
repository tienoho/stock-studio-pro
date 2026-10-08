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
from PyQt6.QtGui import QKeySequence, QShortcut
from ...core.i18n import t
from ..styles.icons import get_svg_icon, get_svg_pixmap
from ..workflow.canvas import WorkflowCanvas
from ...infrastructure.persistence.sqlite_workflow_repo import SqliteWorkflowRepository
from ..components.toast_notification import ToastNotification
from ..styles.ui_enhancer import enhance_widget_interactions, format_tooltip


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

        # Consolidated Workflow Toolbar Card
        toolbar_card = QFrame()
        toolbar_card.setObjectName("toolCard")
        toolbar_layout = QVBoxLayout(toolbar_card)
        toolbar_layout.setContentsMargins(14, 12, 14, 12)
        toolbar_layout.setSpacing(10)

        # Controls Row 1: Add Node & Execution
        top = QHBoxLayout()
        top.setSpacing(8)

        self.workflow_block_combo = QComboBox()
        self.workflow_block_combo.setFixedHeight(32)
        self.workflow_block_combo.addItems([
            "Load JSON", "Search stock", "Random select", "Download selected",
            "Cut/Mix video", "Create voice", "Scene voice match"
        ])
        top.addWidget(self.workflow_block_combo)

        self.btn_add_node = QPushButton(t("workflow.add_node"))
        self.btn_add_node.setObjectName("secondaryBtn")
        self.btn_add_node.setIcon(get_svg_icon("plus", "#ffffff", 14))
        self.btn_add_node.setFixedHeight(32)
        self.btn_add_node.setToolTip(format_tooltip("Thêm khối chức năng đã chọn vào bảng vẽ"))
        self.btn_add_node.clicked.connect(self._workflow_canvas_add)
        top.addWidget(self.btn_add_node)

        self.btn_auto_layout = QPushButton("Sắp Xếp")
        self.btn_auto_layout.setObjectName("secondaryBtn")
        self.btn_auto_layout.setIcon(get_svg_icon("layout", "#4ec9b0", 14))
        self.btn_auto_layout.setFixedHeight(32)
        self.btn_auto_layout.setToolTip(format_tooltip("Tự động căn chỉnh các bước thẳng hàng", "Ctrl+L"))
        self.btn_auto_layout.clicked.connect(lambda: self.workflow_canvas.auto_arrange())
        top.addWidget(self.btn_auto_layout)

        self.btn_run = QPushButton(t("workflow.run_workflow"))
        self.btn_run.setIcon(get_svg_icon("play", "#ffffff", 14))
        self.btn_run.setObjectName("primaryBtn")
        self.btn_run.setFixedHeight(36)
        self.btn_run.setToolTip(format_tooltip("Khởi chạy chuỗi hành động theo sơ đồ khối", "Ctrl+Enter"))
        self.btn_run.clicked.connect(self.runWorkflowRequested.emit)
        top.addWidget(self.btn_run)

        self.btn_clear = QPushButton(t("workflow.clear_canvas"))
        self.btn_clear.setIcon(get_svg_icon("trash", "#f87171", 14))
        self.btn_clear.setObjectName("dangerBtn")
        self.btn_clear.setFixedHeight(32)
        self.btn_clear.setToolTip(format_tooltip("Xóa sạch toàn bộ các khối trên bảng vẽ", "Ctrl+D"))
        self.btn_clear.clicked.connect(self._workflow_clear)
        top.addWidget(self.btn_clear)

        top.addStretch()
        toolbar_layout.addLayout(top)

        # Controls Row 2: SQLite Presets Bar
        preset_bar = QHBoxLayout()
        preset_bar.setSpacing(8)

        self.preset_icon = QLabel()
        self.preset_icon.setPixmap(get_svg_pixmap("database", "#818cf8", 14))
        preset_bar.addWidget(self.preset_icon)

        self.preset_lbl = QLabel(t("workflow.sqlite_presets"))
        self.preset_lbl.setObjectName("sectionHeader")
        preset_bar.addWidget(self.preset_lbl)

        self.sqlite_preset_combo = QComboBox()
        self.sqlite_preset_combo.setFixedHeight(32)
        self.sqlite_preset_combo.setMinimumWidth(160)
        preset_bar.addWidget(self.sqlite_preset_combo)

        self.btn_load_db = QPushButton(t("workflow.load_db"))
        self.btn_load_db.setObjectName("secondaryBtn")
        self.btn_load_db.setIcon(get_svg_icon("refresh", "#58a6ff", 14))
        self.btn_load_db.setFixedHeight(32)
        self.btn_load_db.setToolTip(format_tooltip("Tải cấu hình mẫu đã lưu từ database"))
        self.btn_load_db.clicked.connect(self._load_sqlite_preset)
        preset_bar.addWidget(self.btn_load_db)

        self.btn_save_db = QPushButton(t("workflow.save_db"))
        self.btn_save_db.setObjectName("secondaryBtn")
        self.btn_save_db.setIcon(get_svg_icon("save", "#34d399", 14))
        self.btn_save_db.setFixedHeight(32)
        self.btn_save_db.setToolTip(format_tooltip("Lưu sơ đồ quy trình hiện tại vào SQLite"))
        self.btn_save_db.clicked.connect(self._save_sqlite_preset)
        preset_bar.addWidget(self.btn_save_db)

        self.btn_del_db = QPushButton(t("workflow.delete_db"))
        self.btn_del_db.setObjectName("secondaryBtn")
        self.btn_del_db.setIcon(get_svg_icon("trash", "#f87171", 14))
        self.btn_del_db.setFixedHeight(32)
        self.btn_del_db.setToolTip(format_tooltip("Xóa mẫu đang chọn khỏi cơ sở dữ liệu"))
        self.btn_del_db.clicked.connect(self._delete_sqlite_preset)
        preset_bar.addWidget(self.btn_del_db)

        preset_bar.addSpacing(8)

        self.btn_save_file = QPushButton("Xuất JSON")
        self.btn_save_file.setObjectName("secondaryBtn")
        self.btn_save_file.setIcon(get_svg_icon("file-text", "#94a3b8", 14))
        self.btn_save_file.setFixedHeight(32)
        self.btn_save_file.setToolTip(format_tooltip("Lưu sơ đồ quy trình ra tệp tin JSON"))
        self.btn_save_file.clicked.connect(self._workflow_save)
        preset_bar.addWidget(self.btn_save_file)

        self.btn_load_file = QPushButton("Mở JSON")
        self.btn_load_file.setObjectName("secondaryBtn")
        self.btn_load_file.setIcon(get_svg_icon("folder", "#94a3b8", 14))
        self.btn_load_file.setFixedHeight(32)
        self.btn_load_file.setToolTip(format_tooltip("Nhập sơ đồ quy trình từ tệp tin JSON"))
        self.btn_load_file.clicked.connect(self._workflow_load)
        preset_bar.addWidget(self.btn_load_file)

        preset_bar.addStretch()
        toolbar_layout.addLayout(preset_bar)

        # Controls Row 3: Quick Templates
        quick_tpl_bar = QHBoxLayout()
        quick_tpl_bar.setSpacing(8)

        tpl_lbl = QLabel("MẪU NHANH:")
        tpl_lbl.setStyleSheet("color: #94a3b8; font-size: 10px; font-weight: 700;")
        quick_tpl_bar.addWidget(tpl_lbl)

        btn_tpl_full = QPushButton("★ Toàn Bộ Pipeline")
        btn_tpl_full.setFixedHeight(26)
        btn_tpl_full.setStyleSheet("""
            QPushButton {
                background: rgba(99, 102, 241, 0.15);
                color: #818cf8;
                border: 1px solid rgba(99, 102, 241, 0.3);
                border-radius: 4px;
                font-size: 10px;
                font-weight: 700;
                padding: 0 8px;
            }
            QPushButton:hover { background: rgba(99, 102, 241, 0.3); color: #ffffff; }
        """)
        btn_tpl_full.setToolTip(format_tooltip("Nạp mẫu hoàn chỉnh từ nạp JSON đến cắt ghép"))
        btn_tpl_full.clicked.connect(lambda: self.load_quick_template("full"))
        quick_tpl_bar.addWidget(btn_tpl_full)

        btn_tpl_media = QPushButton("★ Kho Media")
        btn_tpl_media.setFixedHeight(26)
        btn_tpl_media.setStyleSheet("""
            QPushButton {
                background: rgba(56, 189, 248, 0.15);
                color: #38bdf8;
                border: 1px solid rgba(56, 189, 248, 0.3);
                border-radius: 4px;
                font-size: 10px;
                font-weight: 700;
                padding: 0 8px;
            }
            QPushButton:hover { background: rgba(56, 189, 248, 0.3); color: #ffffff; }
        """)
        btn_tpl_media.setToolTip(format_tooltip("Nạp mẫu tìm kiếm và tải media tự động"))
        btn_tpl_media.clicked.connect(lambda: self.load_quick_template("media"))
        quick_tpl_bar.addWidget(btn_tpl_media)

        btn_tpl_voice = QPushButton("★ Khớp Thoại & Cắt")
        btn_tpl_voice.setFixedHeight(26)
        btn_tpl_voice.setStyleSheet("""
            QPushButton {
                background: rgba(245, 158, 11, 0.15);
                color: #fbbf24;
                border: 1px solid rgba(245, 158, 11, 0.3);
                border-radius: 4px;
                font-size: 10px;
                font-weight: 700;
                padding: 0 8px;
            }
            QPushButton:hover { background: rgba(245, 158, 11, 0.3); color: #ffffff; }
        """)
        btn_tpl_voice.setToolTip(format_tooltip("Nạp mẫu hậu kỳ khớp thoại và cắt ghép video"))
        btn_tpl_voice.clicked.connect(lambda: self.load_quick_template("voice_cut"))
        quick_tpl_bar.addWidget(btn_tpl_voice)

        quick_tpl_bar.addStretch()
        toolbar_layout.addLayout(quick_tpl_bar)

        layout.addWidget(toolbar_card)

        self.workflow_canvas = WorkflowCanvas(parent_window or self)
        layout.addWidget(self.workflow_canvas, 1)

        self.workflow_log = QPlainTextEdit()
        self.workflow_log.setReadOnly(True)
        self.workflow_log.setMaximumHeight(110)
        layout.addWidget(self.workflow_log)

        # Keyboard shortcuts
        sh_run = QShortcut(QKeySequence("Ctrl+Return"), self)
        sh_run.activated.connect(self.btn_run.click)
        sh_layout = QShortcut(QKeySequence("Ctrl+L"), self)
        sh_layout.activated.connect(self.btn_auto_layout.click)
        sh_clear = QShortcut(QKeySequence("Ctrl+D"), self)
        sh_clear.activated.connect(self.btn_clear.click)

        # Initial load of SQLite presets
        self._refresh_sqlite_presets()

        # Apply global interactive UX enhancements
        enhance_widget_interactions(self)

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

    def load_quick_template(self, template_type: str):
        self.workflow_canvas.clear()
        if template_type == "full":
            nodes_def = ["Load JSON", "Search stock", "Download selected", "Cut/Mix video", "Create voice", "Scene voice match"]
            desc = "Toàn Bộ Pipeline"
        elif template_type == "media":
            nodes_def = ["Load JSON", "Search stock", "Random select", "Download selected"]
            desc = "Kho Media"
        elif template_type == "voice_cut":
            nodes_def = ["Cut/Mix video", "Create voice", "Scene voice match"]
            desc = "Khớp Thoại & Cắt"
        else:
            return

        created = []
        for n_type in nodes_def:
            node = self.workflow_canvas.add_node(n_type)
            created.append(node)

        for i in range(len(created) - 1):
            self.workflow_canvas.add_edge(created[i], created[i + 1])

        self.workflow_canvas.auto_arrange()
        self.workflow_log.appendPlainText(f"Đã nạp mẫu quy trình: {desc}")
        ToastNotification.show_toast(self, f"Đã nạp mẫu: {desc}", "success", 2500)

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
            ToastNotification.show_toast(self, f"Đã lưu preset: {name.strip()}", "success", 2000)

    def _load_sqlite_preset(self):
        name = self.sqlite_preset_combo.currentText()
        if not name or name == t("workflow.no_preset") or name == "(Chưa có preset)":
            QMessageBox.information(self, t("common.info"), "Vui lòng chọn một mẫu quy trình hợp lệ để nạp.")
            return

        payload = self.workflow_repo.get_preset(name)
        if payload:
            self.workflow_canvas.load_payload(payload)
            self.workflow_log.appendPlainText(t("workflow.load_success", name=name))
            ToastNotification.show_toast(self, f"Đã nạp preset: {name}", "success", 2000)
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
            ToastNotification.show_toast(self, f"Đã xóa preset: {name}", "info", 2000)

    def _workflow_canvas_add(self):
        self.workflow_canvas.add_node(self.workflow_block_combo.currentText())

    def _workflow_clear(self):
        self.workflow_canvas.clear()
        self.workflow_log.clear()
        ToastNotification.show_toast(self, "Đã làm trống canvas quy trình", "info", 1500)

    def _workflow_save(self):
        path, _ = QFileDialog.getSaveFileName(self, "Lưu file mẫu quy trình", "workflow_preset.json", "JSON (*.json)")
        if path:
            Path(path).write_text(
                json.dumps(self.workflow_canvas.save_payload(), ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
            self.workflow_log.appendPlainText(f"Đã lưu: {path}")
            ToastNotification.show_toast(self, f"Đã xuất file: {Path(path).name}", "success", 2000)

    def _workflow_load(self):
        path, _ = QFileDialog.getOpenFileName(self, "Mở file mẫu quy trình", "", "JSON (*.json)")
        if path:
            self.workflow_canvas.load_payload(json.loads(Path(path).read_text(encoding="utf-8")))
            self.workflow_log.appendPlainText(f"Đã nạp: {path}")
            ToastNotification.show_toast(self, f"Đã nạp file: {Path(path).name}", "success", 2000)
