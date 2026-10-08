"""
Scene Voice Matching tab widget.
Matches scene video footage to audio / SRT voice tracks using native FFmpeg processor.
"""

from pathlib import Path
from typing import Optional
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QLineEdit, QPushButton, QCheckBox, QDoubleSpinBox, QPlainTextEdit,
    QFileDialog, QMessageBox, QFrame, QProgressBar
)
from PyQt6.QtCore import pyqtSignal, QThread
from ...application.services.scene_voice_matcher import SceneVoiceMatcher
from ..styles.icons import get_svg_icon, get_svg_pixmap


class SceneVoiceWorker(QThread):
    """Background worker for executing SceneVoiceMatcher safely off the UI thread."""
    progress = pyqtSignal(str)
    progress_val = pyqtSignal(int, int)
    finished_signal = pyqtSignal(bool, str)

    def __init__(
        self,
        root_video_dir: Path,
        output_dir: Path,
        voice_srt_path: Optional[Path] = None,
        voice_audio_dir: Optional[Path] = None,
        full_voice_audio: Optional[Path] = None,
        random_cuts: bool = False,
        concat_final: bool = True,
        chunk_seconds: float = 0.0,
    ):
        super().__init__()
        self.root_video_dir = root_video_dir
        self.output_dir = output_dir
        self.voice_srt_path = voice_srt_path
        self.voice_audio_dir = voice_audio_dir
        self.full_voice_audio = full_voice_audio
        self.random_cuts = random_cuts
        self.concat_final = concat_final
        self.chunk_seconds = chunk_seconds

    def run(self):
        matcher = SceneVoiceMatcher()

        def on_prog(cur, total, text):
            self.progress_val.emit(cur, total)
            self.progress.emit(f"Tiến độ: [{cur}/{total}] {text}")

        def on_log(msg):
            self.progress.emit(msg)

        ok, msg, clips = matcher.match_and_cut(
            root_video_dir=self.root_video_dir,
            output_dir=self.output_dir,
            voice_srt_path=self.voice_srt_path,
            voice_audio_dir=self.voice_audio_dir,
            full_voice_audio=self.full_voice_audio,
            random_cuts=self.random_cuts,
            concat_final=self.concat_final,
            chunk_seconds=self.chunk_seconds,
            progress_cb=on_prog,
            log_cb=on_log,
        )
        self.finished_signal.emit(ok, msg)


class SceneVoiceTab(QWidget):
    """Tab for matching scene video clips to audio/SRT voice track using FFmpeg."""

    finished = pyqtSignal(bool, str)

    def __init__(self, tool_root_fn=None, parent=None):
        super().__init__(parent)
        self.tool_root_fn = tool_root_fn or self._default_tool_root
        self.scene_voice_worker: Optional[SceneVoiceWorker] = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        # Header
        title_h = QHBoxLayout()
        title_h.setSpacing(8)
        self.title_icon = QLabel()
        self.title_icon.setPixmap(get_svg_pixmap("activity", "#f0883e", 20))
        title_h.addWidget(self.title_icon)

        title = QLabel("Khớp Video Với Giọng Đọc")
        title.setObjectName("heroTitle")
        title_h.addWidget(title)
        title_h.addStretch()
        layout.addLayout(title_h)

        hint = QLabel(
            "Tự động cắt ghép các đoạn video cảnh theo đúng thời lượng từng câu thoại hoặc phụ đề SRT bằng FFmpeg."
        )
        hint.setObjectName("mutedText")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        # Config Grid
        grid_frame = QFrame()
        grid_frame.setObjectName("toolCard")
        grid = QGridLayout(grid_frame)
        grid.setSpacing(8)

        self.svc_json = QLineEdit()
        self.svc_root = QLineEdit()
        self.svc_voice = QLineEdit()
        self.svc_full_voice = QLineEdit()
        self.svc_out = QLineEdit()

        rows = [
            ("Kịch bản (JSON, không bắt buộc)", self.svc_json, False),
            ("Thư mục video cảnh (bắt buộc)", self.svc_root, True),
            ("File phụ đề (.srt) hoặc thư mục voice lẻ", self.svc_voice, False),
            ("File âm thanh tổng (Master voice, tùy chọn)", self.svc_full_voice, False),
            ("Thư mục xuất thành phẩm (bắt buộc)", self.svc_out, True),
        ]
        for r, (lab, edit, isdir) in enumerate(rows):
            lbl = QLabel(lab + ":")
            lbl.setStyleSheet("font-size: 12px; font-weight: 600;")
            grid.addWidget(lbl, r, 0)
            grid.addWidget(edit, r, 1)
            btn = QPushButton("Chọn...")
            btn.setIcon(get_svg_icon("folder" if isdir else "file", "#ffffff", 14))
            btn.clicked.connect(lambda _, e=edit, d=isdir: self._browse_line_path(e, d))
            grid.addWidget(btn, r, 2)

        layout.addWidget(grid_frame)

        # Options Row
        row = QHBoxLayout()
        row.setSpacing(12)
        row.addWidget(QLabel("Thời lượng cắt cố định (giây, nếu không có SRT):"))
        self.svc_chunk_seconds = QDoubleSpinBox()
        self.svc_chunk_seconds.setRange(0.0, 120.0)
        self.svc_chunk_seconds.setValue(4.0)
        self.svc_chunk_seconds.setSingleStep(0.5)
        row.addWidget(self.svc_chunk_seconds)

        self.svc_random = QCheckBox("Cắt ngẫu nhiên trong video (Random offset)")
        self.svc_random.setChecked(True)
        row.addWidget(self.svc_random)

        self.svc_concat = QCheckBox("Tự động ghép thành 1 video hoàn chỉnh")
        self.svc_concat.setChecked(True)
        row.addWidget(self.svc_concat)

        row.addStretch()

        self.btn_run = QPushButton("Bắt Đầu Khớp Video")
        self.btn_run.setObjectName("primaryBtn")
        self.btn_run.setIcon(get_svg_icon("play", "#ffffff", 14))
        self.btn_run.setFixedHeight(36)
        self.btn_run.clicked.connect(self.start_scene_voice)
        row.addWidget(self.btn_run)

        layout.addLayout(row)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background: #161b22;
                border: 1px solid #30363d;
                border-radius: 4px;
            }
            QProgressBar::chunk {
                background: #f0883e;
                border-radius: 3px;
            }
        """)
        layout.addWidget(self.progress_bar)

        self.svc_log = QPlainTextEdit()
        self.svc_log.setReadOnly(True)
        self.svc_log.setPlaceholderText("Nhật ký xử lý khớp cảnh sẽ xuất hiện tại đây...")
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
            path, _ = QFileDialog.getOpenFileName(
                self, "Chọn file", line_edit.text() or str(Path.home()),
                "Supported files (*.srt *.mp3 *.wav *.aac *.m4a *.json);;All files (*.*)"
            )
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
        root = self.svc_root.text().strip()
        voice = self.svc_voice.text().strip()
        full_voice = self.svc_full_voice.text().strip()
        out = self.svc_out.text().strip()
        chunk_seconds = self.svc_chunk_seconds.value()

        if not root:
            QMessageBox.information(self, "Thiếu thông tin", "Vui lòng chọn Thư mục video cảnh nguồn.")
            return

        if not out:
            # Default out to root / "matched_output"
            out = str(Path(root) / "matched_output")
            self.svc_out.setText(out)

        if self.scene_voice_worker and self.scene_voice_worker.isRunning():
            QMessageBox.information(self, "Đang xử lý", "Tiến trình khớp video trước đó đang chạy. Vui lòng đợi hoàn tất.")
            return

        voice_srt_path = Path(voice) if (voice and voice.lower().endswith(".srt")) else None
        voice_audio_dir = Path(voice) if (voice and Path(voice).is_dir()) else None
        full_voice_path = Path(full_voice) if full_voice else None

        self.svc_log.clear()
        self.svc_log.appendPlainText("Khởi động tiến trình Native Scene Voice Matcher (FFmpeg)...")
        self.progress_bar.setValue(0)
        self.btn_run.setEnabled(False)

        self.scene_voice_worker = SceneVoiceWorker(
            root_video_dir=Path(root),
            output_dir=Path(out),
            voice_srt_path=voice_srt_path,
            voice_audio_dir=voice_audio_dir,
            full_voice_audio=full_voice_path,
            random_cuts=self.svc_random.isChecked(),
            concat_final=self.svc_concat.isChecked(),
            chunk_seconds=chunk_seconds,
        )

        self.scene_voice_worker.progress.connect(self.svc_log.appendPlainText)
        self.scene_voice_worker.progress_val.connect(self._on_progress_val)
        self.scene_voice_worker.finished_signal.connect(self._on_finished)
        self.scene_voice_worker.start()

    def _on_progress_val(self, cur: int, total: int):
        if total > 0:
            self.progress_bar.setValue(int(cur / total * 100))

    def _on_finished(self, ok: bool, message: str):
        self.btn_run.setEnabled(True)
        self.progress_bar.setValue(100 if ok else 0)
        status = "[HOÀN TẤT THÀNH CÔNG] " if ok else "[LỖI XỬ LÝ] "
        self.svc_log.appendPlainText(f"\n{status}{message}")
        self.finished.emit(ok, message)
