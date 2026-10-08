"""
Scene Voice Matching tab widget.
Matches scene video footage to audio / SRT voice tracks using native FFmpeg processor.
"""

import os
import subprocess
from pathlib import Path
from typing import Optional
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QLineEdit, QPushButton, QCheckBox, QDoubleSpinBox, QPlainTextEdit,
    QFileDialog, QMessageBox, QFrame, QProgressBar
)
from PyQt6.QtCore import pyqtSignal, QThread
from PyQt6.QtGui import QKeySequence, QShortcut
from ...application.services.scene_voice_matcher import SceneVoiceMatcher
from ..styles.icons import get_svg_icon, get_svg_pixmap
from ..components.toast_notification import ToastNotification
from ..styles.ui_enhancer import enhance_widget_interactions, format_tooltip


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
        script_json: Optional[Path] = None,
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
        self.script_json = script_json
        self.full_voice_audio = full_voice_audio
        self.random_cuts = random_cuts
        self.concat_final = concat_final
        self.chunk_seconds = chunk_seconds
        self._is_stopped = False

    def stop(self):
        self._is_stopped = True

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
            script_json=self.script_json,
            full_voice_audio=self.full_voice_audio,
            random_cuts=self.random_cuts,
            concat_final=self.concat_final,
            chunk_seconds=self.chunk_seconds,
            progress_cb=on_prog,
            log_cb=on_log,
            stop_cb=lambda: self._is_stopped,
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

        # Config Card
        grid_frame = QFrame()
        grid_frame.setObjectName("toolCard")
        grid_layout = QVBoxLayout(grid_frame)
        grid_layout.setContentsMargins(16, 14, 16, 14)
        grid_layout.setSpacing(12)

        paths_header = QLabel("ĐƯỜNG DẪN TỆP & THƯ MỤC NGUỒN")
        paths_header.setObjectName("sectionHeader")
        grid_layout.addWidget(paths_header)

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)

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
            lbl.setObjectName("fieldLabel")
            edit.setFixedHeight(32)
            grid.addWidget(lbl, r, 0)
            grid.addWidget(edit, r, 1)
            btn = QPushButton("Chọn...")
            btn.setObjectName("secondaryBtn")
            btn.setIcon(get_svg_icon("folder" if isdir else "file", "#ffffff", 14))
            btn.setFixedHeight(32)
            btn.setToolTip(format_tooltip(f"Chọn {lab}"))
            btn.clicked.connect(lambda _, e=edit, d=isdir: self._browse_line_path(e, d))
            grid.addWidget(btn, r, 2)

        grid_layout.addLayout(grid)
        layout.addWidget(grid_frame)

        # Options Card
        opts_frame = QFrame()
        opts_frame.setObjectName("toolCard")
        opts_layout = QVBoxLayout(opts_frame)
        opts_layout.setContentsMargins(16, 14, 16, 14)
        opts_layout.setSpacing(10)

        opts_header = QLabel("TÙY CHỌN KHỚP & GHÉP VIDEO")
        opts_header.setObjectName("sectionHeader")
        opts_layout.addWidget(opts_header)

        row = QHBoxLayout()
        row.setSpacing(14)
        lbl_sec = QLabel("Thời lượng cắt cố định (giây):")
        lbl_sec.setObjectName("fieldLabel")
        row.addWidget(lbl_sec)
        self.svc_chunk_seconds = QDoubleSpinBox()
        self.svc_chunk_seconds.setFixedHeight(32)
        self.svc_chunk_seconds.setRange(0.0, 120.0)
        self.svc_chunk_seconds.setValue(4.0)
        self.svc_chunk_seconds.setSingleStep(0.5)
        row.addWidget(self.svc_chunk_seconds)

        self.svc_random = QCheckBox("Cắt ngẫu nhiên trong video (Random offset)")
        self.svc_random.setChecked(True)
        self.svc_random.setToolTip(format_tooltip("Cắt trích xuất ngẫu nhiên đoạn giữa của clip thay vì luôn cắt từ giây 0"))
        row.addWidget(self.svc_random)

        self.svc_concat = QCheckBox("Tự động ghép thành 1 video hoàn chỉnh")
        self.svc_concat.setChecked(True)
        self.svc_concat.setToolTip(format_tooltip("Ghép tất cả các clip con đã cắt thành một video master hoàn thiện"))
        row.addWidget(self.svc_concat)

        self.setAcceptDrops(True)

        row.addStretch()

        self.btn_open_out = QPushButton("Mở Folder Xuất")
        self.btn_open_out.setObjectName("secondaryBtn")
        self.btn_open_out.setIcon(get_svg_icon("folder", "#34d399", 14))
        self.btn_open_out.setFixedHeight(36)
        self.btn_open_out.setToolTip(format_tooltip("Mở thư mục video thành phẩm", "Ctrl+O"))
        self.btn_open_out.clicked.connect(self._open_out_folder)
        row.addWidget(self.btn_open_out)

        self.btn_run = QPushButton("Bắt Đầu Khớp Video")
        self.btn_run.setObjectName("primaryBtn")
        self.btn_run.setIcon(get_svg_icon("play", "#ffffff", 14))
        self.btn_run.setFixedHeight(36)
        self.btn_run.setToolTip(format_tooltip("Khởi chạy tiến trình FFmpeg cắt ghép video theo giọng đọc", "Ctrl+Enter"))
        self.btn_run.clicked.connect(self.start_scene_voice)
        row.addWidget(self.btn_run)

        self.btn_stop = QPushButton("Dừng")
        self.btn_stop.setObjectName("dangerBtn")
        self.btn_stop.setIcon(get_svg_icon("square", "#ffffff", 14))
        self.btn_stop.setFixedHeight(36)
        self.btn_stop.setEnabled(False)
        self.btn_stop.setToolTip(format_tooltip("Hủy bỏ tiến trình ghép video đang chạy"))
        self.btn_stop.clicked.connect(self.stop_scene_voice)
        row.addWidget(self.btn_stop)

        opts_layout.addLayout(row)
        layout.addWidget(opts_frame)

        # Keyboard shortcuts
        sh_run = QShortcut(QKeySequence("Ctrl+Return"), self)
        sh_run.activated.connect(self.btn_run.click)
        sh_open = QShortcut(QKeySequence("Ctrl+O"), self)
        sh_open.activated.connect(self._open_out_folder)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(8)
        layout.addWidget(self.progress_bar)

        log_header = QLabel("TIẾN ĐỘ & NHẬT KÝ KHỚP CẢNH")
        log_header.setObjectName("sectionHeader")
        layout.addWidget(log_header)

        self.svc_log = QPlainTextEdit()
        self.svc_log.setReadOnly(True)
        self.svc_log.setPlaceholderText("Nhật ký xử lý khớp cảnh sẽ xuất hiện tại đây...")
        layout.addWidget(self.svc_log, 1)

        # Apply global interactive UX enhancements
        enhance_widget_interactions(self)

    def _open_out_folder(self):
        out_p = self.svc_out.text().strip() or (str(Path(self.svc_root.text().strip()) / "matched_output") if self.svc_root.text().strip() else "")
        if not out_p:
            ToastNotification.show_toast(self, "Chưa chỉ định thư mục xuất", "warning", 2000)
            return
        p = Path(out_p)
        p.mkdir(parents=True, exist_ok=True)
        if os.name == 'nt':
            os.startfile(str(p))
        else:
            subprocess.Popen(["xdg-open", str(p)])
        ToastNotification.show_toast(self, f"Đang mở: {p.name}", "info", 2000)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                lp = url.toLocalFile()
                p = Path(lp)
                if p.is_dir():
                    if not self.svc_root.text():
                        self.svc_root.setText(lp)
                        ToastNotification.show_toast(self, f"Thư mục cảnh: {p.name}", "success", 2500)
                    else:
                        self.svc_out.setText(lp)
                        ToastNotification.show_toast(self, f"Thư mục xuất: {p.name}", "success", 2500)
                    event.acceptProposedAction()
                    return
                elif p.suffix.lower() == ".json":
                    self.svc_json.setText(lp)
                    ToastNotification.show_toast(self, f"Kịch bản JSON: {p.name}", "success", 2500)
                    event.acceptProposedAction()
                    return
                elif p.suffix.lower() == ".srt":
                    self.svc_voice.setText(lp)
                    ToastNotification.show_toast(self, f"Phụ đề SRT: {p.name}", "success", 2500)
                    event.acceptProposedAction()
                    return
                elif p.suffix.lower() in [".mp3", ".wav", ".aac", ".m4a"]:
                    self.svc_full_voice.setText(lp)
                    ToastNotification.show_toast(self, f"Âm thanh: {p.name}", "success", 2500)
                    event.acceptProposedAction()
                    return
        super().dropEvent(event)

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
            ToastNotification.show_toast(self, f"Đã chọn: {Path(path).name}", "info", 1800)

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
        jsonp = self.svc_json.text().strip()
        script_json_path = Path(jsonp) if (jsonp and Path(jsonp).exists()) else None

        self.svc_log.clear()
        self.svc_log.appendPlainText("Khởi động tiến trình Native Scene Voice Matcher (FFmpeg)...")
        self.progress_bar.setValue(0)
        self.btn_run.setEnabled(False)
        self.btn_stop.setEnabled(True)

        self.scene_voice_worker = SceneVoiceWorker(
            root_video_dir=Path(root),
            output_dir=Path(out),
            voice_srt_path=voice_srt_path,
            voice_audio_dir=voice_audio_dir,
            script_json=script_json_path,
            full_voice_audio=full_voice_path,
            random_cuts=self.svc_random.isChecked(),
            concat_final=self.svc_concat.isChecked(),
            chunk_seconds=chunk_seconds,
        )

        self.scene_voice_worker.progress.connect(self.svc_log.appendPlainText)
        self.scene_voice_worker.progress_val.connect(self._on_progress_val)
        self.scene_voice_worker.finished_signal.connect(self._on_finished)
        self.scene_voice_worker.start()

    def stop_scene_voice(self):
        """Cancel running scene voice worker."""
        if self.scene_voice_worker and self.scene_voice_worker.isRunning():
            self.scene_voice_worker.stop()
            self.svc_log.appendPlainText("[DỪNG] Đang yêu cầu dừng tiến trình ghép video...")
            self.btn_stop.setEnabled(False)

    def _on_progress_val(self, cur: int, total: int):
        if total > 0:
            self.progress_bar.setValue(int(cur / total * 100))

    def _on_finished(self, ok: bool, message: str):
        self.btn_run.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.progress_bar.setValue(100 if ok else 0)
        status = "[HOÀN TẤT THÀNH CÔNG] " if ok else "[LỖI XỬ LÝ] "
        self.svc_log.appendPlainText(f"\n{status}{message}")
        if ok:
            if hasattr(self, "btn_open_out"):
                self.btn_open_out.setStyleSheet("""
                    QPushButton#secondaryBtn {
                        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #10b981, stop:1 #059669);
                        color: #ffffff;
                        font-weight: 800;
                        font-size: 11px;
                        border: 1px solid rgba(255,255,255,0.3);
                    }
                    QPushButton#secondaryBtn:hover {
                        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #059669, stop:1 #047857);
                    }
                """)
                self.btn_open_out.setText("🎬 MỞ XEM VIDEO THÀNH PHẨM TRÊN MÁY")
            ToastNotification.show_toast(self, "Khớp video và giọng đọc thành công!", "success", 3000)
        else:
            ToastNotification.show_toast(self, f"Khớp video gặp lỗi: {message[:40]}", "error", 3500)
        self.finished.emit(ok, message)
