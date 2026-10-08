"""
Workflow canvas, items, and node configuration dialog for visual automation.
Obsidian Dark & Neon Cyber styling with interactive grid background, zoom, and live status glows.
"""

import os
import json
import subprocess
from pathlib import Path
from PyQt6.QtWidgets import (
    QGraphicsView, QGraphicsScene, QGraphicsRectItem, QGraphicsTextItem,
    QGraphicsLineItem, QGraphicsItem, QDialog, QVBoxLayout, QHBoxLayout,
    QGridLayout, QLabel, QLineEdit, QPushButton, QFrame, QFileDialog,
    QComboBox, QSpinBox, QDoubleSpinBox, QCheckBox, QPlainTextEdit
)
from PyQt6.QtCore import Qt, QPointF, QLineF, pyqtSignal, QThread
from PyQt6.QtGui import QBrush, QPen, QColor, QFont, QPainter


class NodeToolWorker(QThread):
    progress = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, args, cwd):
        super().__init__()
        self.args = args
        self.cwd = cwd

    def run(self):
        try:
            proc = subprocess.Popen(
                self.args,
                cwd=str(self.cwd),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=(subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0),
            )
            chunks = []
            for line in proc.stdout or []:
                chunks.append(line)
                self.progress.emit(line.rstrip())
            proc.wait()
            out = "".join(chunks).strip()
            self.finished_signal.emit(proc.returncode == 0, out or f"Done: {' '.join(self.args)}")
        except Exception as e:
            self.finished_signal.emit(False, str(e))


class WorkflowNodeItem(QGraphicsRectItem):
    """Visual Node representing a pipeline execution step."""
    def __init__(self, node_id, title, x=0, y=0, config=None):
        super().__init__(0, 0, 200, 78)
        self.node_id = node_id
        self.title = title
        self.config = dict(config or {})
        self.status = "idle"
        self.lines = []
        self.setPos(x, y)
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable |
            QGraphicsItem.GraphicsItemFlag.ItemIsSelectable |
            QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        self.setBrush(QBrush(QColor("#161b22")))
        self.setPen(QPen(QColor("#30363d"), 2))

        self.title_item = QGraphicsTextItem(title, self)
        self.title_item.setDefaultTextColor(QColor("#f4d35e"))
        self.title_item.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.title_item.setPos(12, 10)

        self.sub_item = QGraphicsTextItem("", self)
        self.sub_item.setDefaultTextColor(QColor("#8b949e"))
        self.sub_item.setFont(QFont("Segoe UI", 8))
        self.sub_item.setPos(12, 42)
        self.refresh_label()

    def set_status(self, status: str = "idle"):
        """Updates visual glow and appearance based on execution state."""
        self.status = status
        if status == "running":
            self.setPen(QPen(QColor("#e3b341"), 3))
            self.setBrush(QBrush(QColor("#272210")))
            self.title_item.setDefaultTextColor(QColor("#fef08a"))
        elif status == "success":
            self.setPen(QPen(QColor("#34d399"), 3))
            self.setBrush(QBrush(QColor("#0d2818")))
            self.title_item.setDefaultTextColor(QColor("#a7f3d0"))
        elif status == "error":
            self.setPen(QPen(QColor("#f87171"), 3))
            self.setBrush(QBrush(QColor("#2f1519")))
            self.title_item.setDefaultTextColor(QColor("#fca5a5"))
        else:  # idle
            self.setPen(QPen(QColor("#30363d"), 2))
            self.setBrush(QBrush(QColor("#161b22")))
            self.title_item.setDefaultTextColor(QColor("#f4d35e"))

    def refresh_label(self):
        self.title_item.setPlainText(self.title)
        config_mark = " | đã cài đặt" if self.config else " | nhấp đúp để cài"
        self.sub_item.setPlainText(f"#{self.node_id} kéo để nối{config_mark}")

    def center_left(self):
        return self.scenePos() + QPointF(0, 39)

    def center_right(self):
        return self.scenePos() + QPointF(200, 39)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            for line in self.lines:
                line.update_position()
        return super().itemChange(change, value)


class WorkflowEdgeItem(QGraphicsLineItem):
    """Directional connection between consecutive workflow nodes."""
    def __init__(self, source, target):
        super().__init__()
        self.source = source
        self.target = target
        self.setPen(QPen(QColor("#58a6ff"), 2, Qt.PenStyle.DashLine))
        source.lines.append(self)
        target.lines.append(self)
        self.update_position()

    def update_position(self):
        self.setLine(QLineF(self.source.center_right(), self.target.center_left()))


class WorkflowNodeConfigDialog(QDialog):
    def __init__(self, node, parent=None):
        super().__init__(parent)
        self.node = node
        self.fields = {}
        self.setWindowTitle(f"Cài đặt bước: {node.title}")
        self.resize(620, 520)
        self.config = dict(node.config or {})
        layout = QVBoxLayout(self)
        self.title_input = QLineEdit(node.title)
        layout.addWidget(QLabel("Tên bước:"))
        layout.addWidget(self.title_input)
        hint = QLabel("Thiết lập tùy chọn cho bước này. Khi quy trình chạy, hệ thống sẽ áp dụng các tùy chọn này tự động.")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.form_box = QFrame()
        self.form_layout = QGridLayout(self.form_box)
        self.form_layout.setColumnStretch(1, 1)
        layout.addWidget(self.form_box, 1)
        self._build_form(node.title)
        row = QHBoxLayout()
        row.addStretch()
        cancel_btn = QPushButton("Hủy")
        cancel_btn.clicked.connect(self.reject)
        row.addWidget(cancel_btn)
        save_btn = QPushButton("Lưu Cài Đặt")
        save_btn.setObjectName("primaryBtn")
        save_btn.clicked.connect(self.accept)
        row.addWidget(save_btn)
        layout.addLayout(row)

    def _add_row(self, row, label_text, widget):
        self.form_layout.addWidget(QLabel(label_text), row, 0)
        self.form_layout.addWidget(widget, row, 1)

    def _add_path_picker(self, row, label_text, key, is_dir=False, default_val=""):
        edit = QLineEdit(str(self.config.get(key, default_val)))
        btn = QPushButton("Chọn...")
        if is_dir:
            btn.clicked.connect(lambda: edit.setText(QFileDialog.getExistingDirectory(self, "Chọn thư mục", edit.text() or str(Path.home())) or edit.text()))
        else:
            btn.clicked.connect(lambda: edit.setText(QFileDialog.getOpenFileName(self, "Chọn file", edit.text() or str(Path.home()), "All files (*.*)")[0] or edit.text()))
        sub = QHBoxLayout()
        sub.addWidget(edit, 1)
        sub.addWidget(btn)
        container = QFrame()
        container.setLayout(sub)
        self._add_row(row, label_text, container)
        self.fields[key] = edit

    def _build_form(self, title):
        cfg = self.config
        if title == "Load JSON":
            self._add_path_picker(0, "File kịch bản JSON:", "json", False, "")
            open_dlg = QCheckBox("Mở hộp thoại kịch bản nếu chưa chọn file")
            open_dlg.setChecked(bool(cfg.get("open_dialog", False)))
            self._add_row(1, "Hành vi:", open_dlg)
            self.fields["open_dialog"] = open_dlg
        elif title == "Search stock":
            source_combo = QComboBox()
            source_combo.addItems(["Pexels + Pixabay", "Chỉ Pexels", "Chỉ Pixabay", "Chỉ Vecteezy"])
            source_combo.setCurrentText(cfg.get("source", "Pexels + Pixabay"))
            self._add_row(0, "Nguồn tìm kiếm:", source_combo)
            self.fields["source"] = source_combo
            media_combo = QComboBox()
            media_combo.addItems(["Video + ảnh", "Chỉ video", "Chỉ ảnh"])
            media_combo.setCurrentText(cfg.get("media_mode", "Video + ảnh"))
            self._add_row(1, "Loại media:", media_combo)
            self.fields["media_mode"] = media_combo
            count_spin = QSpinBox()
            count_spin.setRange(0, 10)
            count_spin.setValue(int(cfg.get("random_per_scene", 2)))
            self._add_row(2, "Số lượng chọn ngẫu nhiên mỗi cảnh:", count_spin)
            self.fields["random_per_scene"] = count_spin
        elif title == "Random select":
            media_combo = QComboBox()
            media_combo.addItems(["Video + ảnh", "Chỉ video", "Chỉ ảnh"])
            media_combo.setCurrentText(cfg.get("media_mode", "Video + ảnh"))
            self._add_row(0, "Loại media:", media_combo)
            self.fields["media_mode"] = media_combo
            count_spin = QSpinBox()
            count_spin.setRange(1, 10)
            count_spin.setValue(int(cfg.get("count", 2)))
            self._add_row(1, "Số lượng mỗi cảnh:", count_spin)
            self.fields["count"] = count_spin
        elif title == "Download selected":
            confirm_box = QCheckBox("Tải ngay không cần hỏi lại")
            confirm_box.setChecked(bool(cfg.get("confirm", True)))
            self._add_row(0, "Xác nhận:", confirm_box)
            self.fields["confirm"] = confirm_box
        elif title == "Cut/Mix video":
            self._add_path_picker(0, "Thư mục video cảnh:", "folder", True, "")
            sec = QDoubleSpinBox()
            sec.setRange(0.5, 60.0)
            sec.setValue(float(cfg.get("segment_seconds", 1.0)))
            self._add_row(1, "Cắt mỗi đoạn (giây):", sec)
            self.fields["segment_seconds"] = sec
            cnt = QSpinBox()
            cnt.setRange(1, 20)
            cnt.setValue(int(cfg.get("final_count", 1)))
            self._add_row(2, "Số lượng video hoàn chỉnh:", cnt)
            self.fields["final_count"] = cnt
        elif title == "Create voice":
            mode_combo = QComboBox()
            mode_combo.addItems(["TXT folder/file", "Kịch bản phân đoạn JSON"])
            mode_combo.setCurrentText(cfg.get("mode", "TXT folder/file"))
            self._add_row(0, "Chế độ:", mode_combo)
            self.fields["mode"] = mode_combo
            self._add_path_picker(1, "Thư mục TXT:", "txt_dir", True, "")
            self._add_path_picker(2, "File kịch bản JSON:", "json", False, "")
            self._add_path_picker(3, "Thư mục xuất âm thanh:", "output_dir", True, "")
        elif title == "Scene voice match":
            self._add_path_picker(0, "Kịch bản JSON:", "json", False, "")
            self._add_path_picker(1, "Thư mục video cảnh:", "root", True, "")
            self._add_path_picker(2, "File phụ đề SRT / Thư mục voice:", "voice", False, "")
            self._add_path_picker(3, "File âm thanh đầy đủ:", "full_voice", False, "")
            self._add_path_picker(4, "Thư mục xuất thành phẩm:", "out", True, "")
            chk_spin = QDoubleSpinBox()
            chk_spin.setRange(0.0, 60.0)
            chk_spin.setValue(float(cfg.get("chunk_seconds", 0.0)))
            self._add_row(5, "Độ dài đoạn (giây):", chk_spin)
            self.fields["chunk_seconds"] = chk_spin
            rnd = QCheckBox("Cắt ngẫu nhiên trong video")
            rnd.setChecked(bool(cfg.get("random", False)))
            self._add_row(6, "Tùy chọn cắt:", rnd)
            self.fields["random"] = rnd
            cc = QCheckBox("Tự động ghép các cảnh lại")
            cc.setChecked(bool(cfg.get("concat", True)))
            self._add_row(7, "Nối clip:", cc)
            self.fields["concat"] = cc

    def values(self):
        config = dict(self.config)
        for key, widget in self.fields.items():
            if isinstance(widget, QLineEdit):
                config[key] = widget.text().strip()
            elif isinstance(widget, QComboBox):
                config[key] = widget.currentText()
            elif isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                config[key] = widget.value()
            elif isinstance(widget, QCheckBox):
                config[key] = widget.isChecked()
        return self.title_input.text().strip() or "Node", config


class WorkflowCanvas(QGraphicsView):
    """Interactive visual workflow canvas with grid dots, zoom, and auto-layout."""

    def __init__(self, parent_window=None):
        super().__init__()
        self.parent_window = parent_window
        self.scene_obj = QGraphicsScene(self)
        self.setScene(self.scene_obj)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setAcceptDrops(True)
        self.nodes = []
        self.edges = []
        self.next_id = 1
        self.setStyleSheet("background:#0d1117; border:1px solid #30363d; border-radius:12px;")
        self.setSceneRect(0, 0, 2400, 1200)

    def drawBackground(self, painter: QPainter, rect):
        """Renders subtle matrix grid dots for Obsidian/Cyber aesthetic."""
        painter.fillRect(rect, QColor("#0d1117"))
        grid_size = 24
        left = int(rect.left()) - (int(rect.left()) % grid_size)
        top = int(rect.top()) - (int(rect.top()) % grid_size)
        painter.setPen(QPen(QColor("#21262d"), 1))
        for x in range(left, int(rect.right()), grid_size):
            for y in range(top, int(rect.bottom()), grid_size):
                painter.drawPoint(x, y)

    def wheelEvent(self, event):
        """Smooth zoom in/out with Ctrl + Wheel or Wheel alone."""
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            factor = 1.12 if delta > 0 else 0.89
            current_scale = self.transform().m11()
            if 0.35 < current_scale * factor < 2.5:
                self.scale(factor, factor)
            event.accept()
        else:
            super().wheelEvent(event)

    def auto_arrange(self):
        """Automatically aligns and formats nodes left-to-right."""
        ordered = self.ordered_nodes()
        if not ordered:
            return
        start_x = 80
        y = 120
        spacing = 250
        for i, node in enumerate(ordered):
            node.setPos(start_x + i * spacing, y)
        self.rebuild_edges()

    def default_config_for(self, title):
        defaults = {
            "Load JSON": {"open_dialog": False},
            "Search stock": {"source": "Pexels + Pixabay", "media_mode": "Video + ảnh", "random_per_scene": 2},
            "Random select": {"media_mode": "Video + ảnh", "count": 2},
            "Download selected": {"confirm": False},
            "Cut/Mix video": {"folder": "", "segment_seconds": 1.0, "final_count": 1, "max_clips": 0},
            "Create voice": {"mode": "TXT folder/file", "txt_dir": "", "txt_file": "", "json": "", "output_dir": ""},
            "Scene voice match": {"random": True, "concat": True, "full_voice": "", "chunk_seconds": 4.0},
        }
        return dict(defaults.get(title, {}))

    def add_node(self, title, x=None, y=None, config=None):
        if x is None:
            x = 80 + len(self.nodes) * 240
        if y is None:
            y = 120
        node = WorkflowNodeItem(self.next_id, title, x, y, self.default_config_for(title) if config is None else config)
        self.next_id += 1
        self.scene_obj.addItem(node)
        self.nodes.append(node)
        self.rebuild_edges()
        return node

    def rebuild_edges(self):
        for edge in self.edges:
            self.scene_obj.removeItem(edge)
        self.edges = []
        ordered = self.ordered_nodes()
        for a, b in zip(ordered, ordered[1:]):
            edge = WorkflowEdgeItem(a, b)
            self.scene_obj.addItem(edge)
            self.edges.append(edge)

    def ordered_nodes(self):
        return sorted(self.nodes, key=lambda n: (n.scenePos().x(), n.scenePos().y(), n.node_id))

    def workflow_steps(self):
        return [n.title for n in self.ordered_nodes()]

    def workflow_nodes(self):
        return self.ordered_nodes()

    def clear(self):
        self.scene_obj.clear()
        self.nodes = []
        self.edges = []
        self.next_id = 1

    def save_payload(self):
        return [{"title": n.title, "x": n.scenePos().x(), "y": n.scenePos().y(), "config": n.config} for n in self.nodes]

    def load_payload(self, payload):
        self.clear()
        for item in payload:
            self.add_node(item.get("title", "Node"), item.get("x", 80), item.get("y", 120), item.get("config", {}))
        self.rebuild_edges()

    def mouseDoubleClickEvent(self, event):
        item = self.itemAt(event.pos())
        node = item
        while node and not isinstance(node, WorkflowNodeItem):
            node = node.parentItem()
        if node:
            dialog = WorkflowNodeConfigDialog(node, self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                node.title, node.config = dialog.values()
                node.refresh_label()
                self.rebuild_edges()
            return
        super().mouseDoubleClickEvent(event)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        self.rebuild_edges()
