"""
Scene Voice Matching tab widget.
"""

import sys
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QLineEdit, QPushButton, QCheckBox, QDoubleSpinBox, QPlainTextEdit,
    QFileDialog, QMessageBox
)
from PyQt6.QtCore import pyqtSignal
from ..workflow.canvas import NodeToolWorker


class SceneVoiceTab(QWidget):
    """Tab for matching scene video clips to audio/SRT voice track using FFmpeg."""

    finished = pyqtSignal(bool, str)

    def __init__(self, tool_root_fn=None, parent=None):
        super().__init__(parent)
        self.tool_root_fn = tool_root_fn or self._default_tool_root
        self.scene_voice_worker = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        title = QLabel("Khớp Video Với Giọng Đọc")
        title.setObjectName("heroTitle")
        layout.addWidget(title)

        hint = QLabel(
            "Ghép nối video theo từng câu thoại hoặc phụ đề để tạo thành video hoàn chỉnh."
        )
        hint.setObjectName("mutedText")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        grid = QGridLayout()
        self.svc_json = QLineEdit()
        self.svc_root = QLineEdit()
        self.svc_voice = QLineEdit()
        self.svc_full_voice = QLineEdit()
        self.svc_out = QLineEdit()

        rows = [
            ("Kịch bản (JSON, không bắt buộc)", self.svc_json, False),
            ("Thư mục video cảnh", self.svc_root, True),
            ("File phụ đề / voice lẻ", self.svc_voice, False),
            ("File âm thanh đầy đủ", self.svc_full_voice, False),
            ("Thư mục xuất", self.svc_out, True),
        ]
        for r, (lab, edit, isdir) in enumerate(rows):
            grid.addWidget(QLabel(lab + ":"), r, 0)
            grid.addWidget(edit, r, 1)
            btn = QPushButton("Chọn")
            btn.clicked.connect(lambda _, e=edit, d=isdir: self._browse_line_path(e, d))
            grid.addWidget(btn, r, 2)
        layout.addLayout(grid)

        opts = QHBoxLayout()
        self.svc_random = QCheckBox("Cắt ngẫu nhiên đoạn video nếu video dài hơn giọng")
        self.svc_random.setChecked(True)
        self.svc_concat = QCheckBox("Xuất video hoàn chỉnh (full_video.mp4)")
        opts.addWidget(self.svc_random)
        opts.addWidget(self.svc_concat)
        opts.addWidget(QLabel("Cắt clip con mỗi:"))
        self.svc_chunk_seconds = QDoubleSpinBox()
        self.svc_chunk_seconds.setRange(0.0, 120.0)
        self.svc_chunk_seconds.setSingleStep(1.0)
        self.svc_chunk_seconds.setValue(0.0)
        self.svc_chunk_seconds.setSuffix(" giây")
        opts.addWidget(self.svc_chunk_seconds)
        opts.addStretch()
        layout.addLayout(opts)

        row = QHBoxLayout()
        run = QPushButton("Bắt Đầu Ghép")
        run.setObjectName("primaryBtn")
        run.clicked.connect(self.start_scene_voice)
        row.addWidget(run)
        row.addStretch()
        layout.addLayout(row)

        self.svc_log = QPlainTextEdit()
        self.svc_log.setReadOnly(True)
        layout.addWidget(self.svc_log, 1)

    def _default_tool_root(self) -> Path:
        here = Path(__file__).resolve()
        return here.parent.parent.parent.parent

    def tool_root(self) -> Path:
        return self.tool_root_fn()

    def _browse_line_path(self, line_edit: QLineEdit, is_dir: bool = False):
        if is_dir:
            path = QFileDialog.getExistingDirectory(self, "Chọn thư mục", line_edit.text() or str(Path.home()))
        else:
            path, _ = QFileDialog.getOpenFileName(self, "Chọn file", line_edit.text() or str(Path.home()), "All files (*.*)")
        if path:
            line_edit.setText(path)

    def set_config(self, json_path="", root_dir="", voice_path="", full_voice="", out_dir="", chunk_seconds=0.0, random=False, concat=True):
        if json_path: self.svc_json.setText(str(json_path))
        if root_dir: self.svc_root.setText(str(root_dir))
        if voice_path: self.svc_voice.setText(str(voice_path))
        if full_voice: self.svc_full_voice.setText(str(full_voice))
        if out_dir: self.svc_out.setText(str(out_dir))
        self.svc_chunk_seconds.setValue(float(chunk_seconds))
        self.svc_random.setChecked(bool(random))
        self.svc_concat.setChecked(bool(concat))

    def start_scene_voice(self):
        jsonp = self.svc_json.text().strip()
        root = self.svc_root.text().strip()
        voice = self.svc_voice.text().strip()
        full_voice = self.svc_full_voice.text().strip()
        out = self.svc_out.text().strip()
        chunk_seconds = self.svc_chunk_seconds.value()

        if not root or not out:
            QMessageBox.information(self, "Thiếu dữ liệu", "Cần folder video cảnh và output folder")
            return

        script = self.tool_root() / "Scene Voice Cutter" / "scene_voice_cutter.py"
        if not script.exists():
            self.svc_log.appendPlainText(f"Lỗi: không tìm thấy {script}")
            return

        if self.scene_voice_worker and self.scene_voice_worker.isRunning():
            QMessageBox.information(self, "Đang chạy", "Đợi job khớp voice hiện tại xong nhé")
            return

        args = [
            sys.executable if not getattr(sys, "frozen", False) else "python",
            str(script), "--cli", jsonp, root, voice, out,
            "1" if self.svc_random.isChecked() else "0",
            "1" if self.svc_concat.isChecked() else "0",
            full_voice, f"{chunk_seconds:.3f}"
        ]
        self.svc_log.appendPlainText("Đang chạy khớp voice bằng ffmpeg...")
        self.scene_voice_worker = NodeToolWorker(args, script.parent)
        self.scene_voice_worker.progress.connect(lambda msg: self.svc_log.appendPlainText(msg) if msg else None)
        self.scene_voice_worker.finished_signal.connect(self._on_finished)
        self.scene_voice_worker.start()

    def _on_finished(self, ok: bool, message: str):
        self.svc_log.appendPlainText(("[SUCCESS] " if ok else "[ERROR] ") + (message[-6000:] if message else "Done"))
        self.finished.emit(ok, message)

    _start_native = start_scene_voice
