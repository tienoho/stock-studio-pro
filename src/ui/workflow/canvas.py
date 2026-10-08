"""
Workflow canvas, items, and node configuration dialog for visual automation.
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
    def __init__(self, node_id, title, x=0, y=0, config=None):
        super().__init__(0, 0, 190, 74)
        self.node_id = node_id
        self.title = title
        self.config = dict(config or {})
        self.lines = []
        self.setPos(x, y)
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable |
            QGraphicsItem.GraphicsItemFlag.ItemIsSelectable |
            QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        self.setBrush(QBrush(QColor("#182332")))
        self.setPen(QPen(QColor("#3d5872"), 2))
        self.title_item = QGraphicsTextItem(title, self)
        self.title_item.setDefaultTextColor(QColor("#f4d35e"))
        self.title_item.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.title_item.setPos(12, 10)
        self.sub_item = QGraphicsTextItem("", self)
        self.sub_item.setDefaultTextColor(QColor("#9fb0c3"))
        self.sub_item.setFont(QFont("Segoe UI", 8))
        self.sub_item.setPos(12, 38)
        self.refresh_label()

    def refresh_label(self):
        self.title_item.setPlainText(self.title)
        config_mark = " | đã cài đặt" if self.config else " | nhấp đúp để cài đặt"
        self.sub_item.setPlainText(f"#{self.node_id} kéo để sắp xếp{config_mark}")

    def center_left(self):
        return self.scenePos() + QPointF(0, 37)

    def center_right(self):
        return self.scenePos() + QPointF(190, 37)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            for line in self.lines:
                line.update_position()
        return super().itemChange(change, value)


class WorkflowEdgeItem(QGraphicsLineItem):
    def __init__(self, source, target):
        super().__init__()
        self.source = source
        self.target = target
        self.setPen(QPen(QColor("#4ec9b0"), 3))
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
        save_btn = QPushButton("Lưu Cài Đặt")
        save_btn.clicked.connect(self.accept)
        row.addWidget(cancel_btn)
        row.addWidget(save_btn)
        layout.addLayout(row)

    def _add_row(self, row, label, widget, key=None, browse=None):
        self.form_layout.addWidget(QLabel(label), row, 0)
        self.form_layout.addWidget(widget, row, 1)
        if key:
            self.fields[key] = widget
        if browse:
            btn = QPushButton("Chọn...")
            btn.clicked.connect(lambda: self._browse(widget, browse))
            self.form_layout.addWidget(btn, row, 2)

    def _browse(self, widget, mode):
        if mode == "folder":
            value = QFileDialog.getExistingDirectory(self, "Chọn thư mục")
        else:
            value, _ = QFileDialog.getOpenFileName(self, "Chọn file", "", "All files (*.*)")
        if value:
            widget.setText(value)

    def _combo(self, items, value):
        combo = QComboBox()
        combo.addItems(items)
        idx = combo.findText(str(value or ""))
        if idx >= 0:
            combo.setCurrentIndex(idx)
        return combo

    def _spin(self, value, min_value=1, max_value=99):
        spin = QSpinBox()
        spin.setRange(int(min_value), int(max_value))
        spin.setValue(int(value or min_value))
        return spin

    def _double_spin(self, value, min_value=0.5, max_value=2.0):
        spin = QDoubleSpinBox()
        spin.setRange(min_value, max_value)
        spin.setSingleStep(0.1)
        spin.setValue(float(value or 1.0))
        return spin

    def _line(self, value=""):
        return QLineEdit(str(value or ""))

    def _check(self, value=False):
        check = QCheckBox()
        check.setChecked(bool(value))
        return check

    def _build_form(self, title):
        cfg = self.config
        row = 0
        if title == "Load JSON":
            self._add_row(row, "Mở hộp thoại chọn kịch bản khi chạy", self._check(cfg.get("open_dialog", False)), "open_dialog")
            row += 1
            self._add_row(row, "File kịch bản JSON", self._line(cfg.get("json", "")), "json", "file")
            row += 1
        elif title == "Search stock":
            self._add_row(row, "Nguồn tìm kiếm", self._combo(["Pexels + Pixabay", "Pexels + Pixabay + Vecteezy", "Chỉ Pexels", "Chỉ Pixabay", "Chỉ Vecteezy"], cfg.get("source", "Pexels + Pixabay")), "source")
            row += 1
            self._add_row(row, "Định dạng media", self._combo(["Video + ảnh", "Chỉ video", "Chỉ ảnh"], cfg.get("media_mode", "Video + ảnh")), "media_mode")
            row += 1
            self._add_row(row, "Số lượng ngẫu nhiên mỗi cảnh", self._spin(cfg.get("random_per_scene", 2), 1, 20), "random_per_scene")
            row += 1
        elif title == "Random select":
            self._add_row(row, "Định dạng media", self._combo(["Video + ảnh", "Chỉ video", "Chỉ ảnh"], cfg.get("media_mode", "Video + ảnh")), "media_mode")
            row += 1
            self._add_row(row, "Số media mỗi cảnh", self._spin(cfg.get("count", 2), 1, 20), "count")
            row += 1
        elif title == "Download selected":
            self._add_row(row, "Tự động tải không cần hỏi lại", self._check(not cfg.get("confirm", False)), "confirm_less")
            row += 1
            self._add_row(row, "Thư mục tải về", self._line(cfg.get("output_dir", "")), "output_dir", "folder")
            row += 1
        elif title == "Cut/Mix video":
            self._add_row(row, "Thư mục video gốc", self._line(cfg.get("folder", "")), "folder", "folder")
            row += 1
            self._add_row(row, "Độ dài mỗi đoạn (giây)", self._double_spin(cfg.get("segment_seconds", 1.0), 0.2, 60.0), "segment_seconds")
            row += 1
            self._add_row(row, "Số video xuất", self._spin(cfg.get("final_count", 1), 1, 50), "final_count")
            row += 1
            self._add_row(row, "Clip tối đa mỗi video (0 = tất cả)", self._spin(cfg.get("max_clips", 0), 0, 9999), "max_clips")
            row += 1
        elif title == "Create voice":
            self._add_row(row, "Chế độ", self._combo(["TXT folder/file", "JSON parts/scenes"], cfg.get("mode", "TXT folder/file")), "mode")
            row += 1
            self._add_row(row, "Thư mục TXT", self._line(cfg.get("txt_dir", "")), "txt_dir", "folder")
            row += 1
            self._add_row(row, "File TXT lẻ", self._line(cfg.get("txt_file", "")), "txt_file", "file")
            row += 1
            self._add_row(row, "File phân đoạn JSON", self._line(cfg.get("json", "")), "json", "file")
            row += 1
            self._add_row(row, "Thư mục lưu âm thanh", self._line(cfg.get("output_dir", "")), "output_dir", "folder")
            row += 1
        elif title == "Scene voice match":
            self._add_row(row, "File kịch bản (không bắt buộc)", self._line(cfg.get("json", "")), "json", "file")
            row += 1
            self._add_row(row, "Thư mục video cảnh", self._line(cfg.get("root", "")), "root", "folder")
            row += 1
            self._add_row(row, "File phụ đề hoặc giọng đọc lẻ", self._line(cfg.get("voice", "")), "voice", "file")
            row += 1
            self._add_row(row, "File âm thanh hoàn chỉnh", self._line(cfg.get("full_voice", "")), "full_voice", "file")
            row += 1
            self._add_row(row, "Chia nhỏ video mỗi (giây, 0 = tắt)", self._double_spin(cfg.get("chunk_seconds", 0.0), 0.0, 120.0), "chunk_seconds")
            row += 1
            self._add_row(row, "Thư mục xuất", self._line(cfg.get("output_dir", "")), "output_dir", "folder")
            row += 1
            self._add_row(row, "Cắt ngẫu nhiên", self._check(cfg.get("random", False)), "random")
            row += 1
            self._add_row(row, "Ghép nối video hoàn chỉnh", self._check(cfg.get("concat", True)), "concat")
            row += 1
        else:
            self.config_input = QPlainTextEdit(json.dumps(cfg, ensure_ascii=False, indent=2))
            self._add_row(row, "Cấu hình JSON", self.config_input)

    def _field_value(self, widget):
        if isinstance(widget, QComboBox):
            return widget.currentText()
        if isinstance(widget, QSpinBox) or isinstance(widget, QDoubleSpinBox):
            return widget.value()
        if isinstance(widget, QCheckBox):
            return widget.isChecked()
        if isinstance(widget, QLineEdit):
            return widget.text().strip()
        return None

    def values(self):
        if hasattr(self, "config_input"):
            try:
                config = json.loads(self.config_input.toPlainText().strip() or "{}")
            except Exception:
                config = {}
        else:
            config = {key: self._field_value(widget) for key, widget in self.fields.items()}
            if "confirm_less" in config:
                config["confirm"] = not config.pop("confirm_less")
        return self.title_input.text().strip() or "Node", config


class WorkflowCanvas(QGraphicsView):
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
        self.setStyleSheet("background:#0b1118; border:1px solid #2d4053; border-radius:12px;")
        self.setSceneRect(0, 0, 1400, 900)

    def default_config_for(self, title):
        defaults = {
            "Load JSON": {"open_dialog": False},
            "Search stock": {"source": "Pexels + Pixabay", "media_mode": "Video + ảnh", "random_per_scene": 2},
            "Random select": {"media_mode": "Video + ảnh", "count": 2},
            "Download selected": {"confirm": False},
            "Cut/Mix video": {"folder": "", "segment_seconds": 1.0, "final_count": 1, "max_clips": 0},
            "Create voice": {"mode": "TXT folder/file", "txt_dir": "", "txt_file": "", "json": "", "output_dir": ""},
            "Scene voice match": {"random": False, "concat": True, "full_voice": "", "chunk_seconds": 0.0},
        }
        return dict(defaults.get(title, {}))

    def add_node(self, title, x=None, y=None, config=None):
        if x is None:
            x = 60 + (len(self.nodes) % 4) * 230
        if y is None:
            y = 70 + (len(self.nodes) // 4) * 120
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
            self.add_node(item.get("title", "Node"), item.get("x", 60), item.get("y", 70), item.get("config", {}))
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
