"""
Voice TXT Studio tab widget for TTS voiceover generation and SRT subtitle stitching.
Supports native Microsoft Edge TTS (free, high-quality, Vietnamese & English) and legacy external providers.
"""

import re
import json
import subprocess
import os
import sys
from pathlib import Path
from typing import List, Optional

from PyQt6.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QLineEdit, QPushButton, QComboBox, QDoubleSpinBox, QSpinBox,
    QPlainTextEdit, QTabWidget, QListWidget, QFileDialog, QMessageBox,
    QApplication, QProgressBar, QCheckBox
)
from PyQt6.QtCore import pyqtSignal, QThread

from ...core.models.scene import srt_time_to_seconds
from ...application.services.edge_tts_service import EdgeTTSService, AVAILABLE_VOICES
from ..styles.icons import get_svg_icon, get_svg_pixmap


class VoiceGenerationWorker(QThread):
    """Background thread worker for generating voice audio and subtitles."""
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int, int)
    finished_signal = pyqtSignal(int, int)

    def __init__(
        self,
        files: List[Path],
        output_dir: Path,
        provider: str,
        voice_id: str,
        speed: float,
        generate_srt: bool = True,
        tool_root: Optional[Path] = None
    ):
        super().__init__()
        self.files = files
        self.output_dir = output_dir
        self.provider = provider
        self.voice_id = voice_id
        self.speed = speed
        self.generate_srt = generate_srt
        self.tool_root = tool_root

    def run(self):
        total = len(self.files)
        success = 0

        if "edge" in self.provider.lower():
            # Native Edge TTS
            service = EdgeTTSService(default_voice=self.voice_id)
            speed_pct = f"{int((self.speed - 1.0) * 100):+d}%"

            def on_log(msg):
                self.log_signal.emit(msg)

            def on_prog(cur, tot, text):
                self.progress_signal.emit(cur, tot)

            ok_count, total_count, _ = service.batch_synthesize_txt_files(
                txt_files=self.files,
                output_dir=self.output_dir,
                voice=self.voice_id,
                rate=speed_pct,
                generate_subtitles=self.generate_srt,
                progress_cb=on_prog,
                log_cb=on_log
            )
            success = ok_count
        else:
            # External Node.js provider fallback
            tool = (self.tool_root / "Voice TXT Tool") if self.tool_root else Path("Voice TXT Tool")
            server_script = tool / "server.mjs"
            if not server_script.exists():
                self.log_signal.emit(f"[LỖI] Không tìm thấy script ngoài tại: {server_script}")
                self.log_signal.emit("GỢI Ý: Chuyển sang chọn 'Edge TTS (Miễn phí / Khuyên dùng)' để tạo giọng trực tiếp không cần Node.js.")
                self.finished_signal.emit(0, total)
                return

            for idx, inp in enumerate(self.files, 1):
                self.log_signal.emit(f"[{idx}/{total}] Đang tạo giọng đọc: {inp.name} qua {self.provider}...")
                cmd = [
                    "node", "server.mjs", "--cli", str(inp), str(self.output_dir),
                    self.provider, str(self.speed)
                ]
                try:
                    proc = subprocess.Popen(
                        cmd, cwd=str(tool), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                        text=True, encoding="utf-8", errors="replace",
                        creationflags=(subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
                    )
                    for line in proc.stdout or []:
                        self.log_signal.emit(line.rstrip())
                    proc.wait()
                    if proc.returncode == 0:
                        success += 1
                except Exception as e:
                    self.log_signal.emit(f"[LỖI] {e}")

                self.progress_signal.emit(idx, total)

        self.finished_signal.emit(success, total)


class VoiceTab(QWidget):
    """Voice TXT generation and SRT stitching studio."""

    log_message = pyqtSignal(str)

    def __init__(self, tool_root_fn=None, config=None, save_config_fn=None, parent=None):
        super().__init__(parent)
        self.config = config or {}
        self.save_config_fn = save_config_fn
        self.tool_root_fn = tool_root_fn or self._default_tool_root
        self.worker: Optional[VoiceGenerationWorker] = None

        root = QHBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(14)

        left = QFrame()
        left.setObjectName("toolCard")
        left_l = QVBoxLayout(left)
        left_l.setSpacing(10)

        title_h = QHBoxLayout()
        title_h.setSpacing(8)
        self.title_icon = QLabel()
        self.title_icon.setPixmap(get_svg_pixmap("mic", "#bc8cff", 20))
        title_h.addWidget(self.title_icon)

        title = QLabel("Tạo Giọng Đọc & Phụ Đề")
        title.setObjectName("heroTitle")
        title_h.addWidget(title)
        title_h.addStretch()
        left_l.addLayout(title_h)

        hint = QLabel(
            "Tích hợp Microsoft Edge TTS chuẩn AI tự nhiên (miễn phí), hỗ trợ kịch bản phân đoạn và ghép nối file phụ đề SRT."
        )
        hint.setObjectName("mutedText")
        hint.setWordWrap(True)
        left_l.addWidget(hint)

        self.voice_tabs = QTabWidget()
        left_l.addWidget(self.voice_tabs, 1)

        # Tab 1: TXT -> voice
        txt_tab = QWidget()
        txt_l = QVBoxLayout(txt_tab)
        txt_l.setSpacing(10)
        txt_grid = QGridLayout()
        txt_grid.setHorizontalSpacing(10)
        txt_grid.setVerticalSpacing(8)

        self.voice_txt_dir = QLineEdit()
        self.voice_txt_dir.setPlaceholderText("Thư mục chứa các file TXT...")
        self.voice_input_path = QLineEdit()
        self.voice_input_path.setPlaceholderText("Hoặc chọn một file TXT cụ thể...")
        self.voice_output_dir = QLineEdit(str(Path(self.tool_root()) / "voices"))

        self.voice_provider_combo = QComboBox()
        self.voice_provider_combo.addItems([
            "Edge TTS (Miễn phí / Khuyên dùng)",
            "11labs", "larvoice", "vivibe", "genmax", "ai84", "vbee", "default"
        ])
        self.voice_provider_combo.currentIndexChanged.connect(self._on_provider_changed)

        self.edge_voice_combo = QComboBox()
        for v in AVAILABLE_VOICES:
            self.edge_voice_combo.addItem(v["name"], v["id"])

        self.voice_speed_spin = QDoubleSpinBox()
        self.voice_speed_spin.setRange(0.5, 2.0)
        self.voice_speed_spin.setSingleStep(0.05)
        self.voice_speed_spin.setValue(1.0)

        self.generate_srt_checkbox = QCheckBox("Tự động tạo file phụ đề .srt tương ứng")
        self.generate_srt_checkbox.setChecked(True)

        self.voice_id_input = QLineEdit()
        self.voice_id_input.setPlaceholderText("Mã giọng riêng (nếu dùng key ngoài)...")
        self.larvoice_id_input = QLineEdit("1")

        self.provider_api_keys = QPlainTextEdit()
        self.provider_api_keys.setPlaceholderText("Danh sách API key (chỉ cần nếu chọn 11labs, Larvoice, Vbee...)...")
        self.provider_api_keys.setMaximumHeight(70)

        txt_grid.addWidget(QLabel("Thư mục TXT:"), 0, 0)
        txt_grid.addWidget(self.voice_txt_dir, 0, 1)
        b = QPushButton("Chọn...")
        b.setIcon(get_svg_icon("folder", "#ffffff", 14))
        b.clicked.connect(lambda: self._browse_line_path(self.voice_txt_dir, True))
        txt_grid.addWidget(b, 0, 2)

        txt_grid.addWidget(QLabel("File TXT lẻ:"), 1, 0)
        txt_grid.addWidget(self.voice_input_path, 1, 1)
        b = QPushButton("Chọn...")
        b.setIcon(get_svg_icon("file", "#ffffff", 14))
        b.clicked.connect(lambda: self._browse_line_path(self.voice_input_path))
        txt_grid.addWidget(b, 1, 2)

        txt_grid.addWidget(QLabel("Thư mục âm thanh:"), 2, 0)
        txt_grid.addWidget(self.voice_output_dir, 2, 1)
        b = QPushButton("Chọn...")
        b.setIcon(get_svg_icon("folder", "#ffffff", 14))
        b.clicked.connect(lambda: self._browse_line_path(self.voice_output_dir, True))
        txt_grid.addWidget(b, 2, 2)

        txt_grid.addWidget(QLabel("Dịch vụ giọng:"), 3, 0)
        txt_grid.addWidget(self.voice_provider_combo, 3, 1)
        txt_grid.addWidget(QLabel("Tốc độ:"), 3, 2)
        txt_grid.addWidget(self.voice_speed_spin, 3, 3)

        self.lbl_edge_voice = QLabel("Giọng đọc AI:")
        txt_grid.addWidget(self.lbl_edge_voice, 4, 0)
        txt_grid.addWidget(self.edge_voice_combo, 4, 1, 1, 3)

        self.lbl_custom_voice = QLabel("Mã giọng / API Key:")
        txt_grid.addWidget(self.lbl_custom_voice, 5, 0)
        txt_grid.addWidget(self.provider_api_keys, 5, 1, 1, 3)

        txt_l.addLayout(txt_grid)
        txt_l.addWidget(self.generate_srt_checkbox)

        row = QHBoxLayout()
        for text, fn, icon_name in [
            ("Quét Thư Mục", self._voice_scan_txt, "refresh"),
            ("Tạo Giọng Đọc", self.start_native_voice, "play"),
            ("Xóa Danh Sách", self._voice_clear_files, "trash"),
            ("Lưu Cài Đặt", self._voice_save_provider_config, "save"),
        ]:
            btn = QPushButton(text)
            btn.setIcon(get_svg_icon(icon_name, "#ffffff", 14))
            if text == "Tạo Giọng Đọc":
                btn.setObjectName("primaryBtn")
            btn.clicked.connect(fn)
            row.addWidget(btn)
        row.addStretch()
        txt_l.addLayout(row)

        self.voice_files_list = QListWidget()
        txt_l.addWidget(self.voice_files_list, 1)
        self.voice_tabs.addTab(txt_tab, "Tạo Giọng Từ TXT")

        # Tab 2: merge SRT
        srt_tab = QWidget()
        srt_l = QVBoxLayout(srt_tab)
        srt_l.setSpacing(10)
        srt_grid = QGridLayout()
        self.srt_dir_input = QLineEdit(str(Path(self.tool_root()) / "voices"))
        self.srt_output_input = QLineEdit(str(Path(self.tool_root()) / "voices" / "kich_ban_hoan_chinh.srt"))
        self.srt_gap_spin = QSpinBox()
        self.srt_gap_spin.setRange(0, 5000)
        self.srt_gap_spin.setSingleStep(50)
        self.srt_gap_spin.setValue(250)

        srt_grid.addWidget(QLabel("Thư mục SRT:"), 0, 0)
        srt_grid.addWidget(self.srt_dir_input, 0, 1)
        b = QPushButton("Chọn Thư Mục")
        b.setIcon(get_svg_icon("folder", "#ffffff", 14))
        b.clicked.connect(lambda: self._browse_line_path(self.srt_dir_input, True))
        srt_grid.addWidget(b, 0, 2)

        srt_grid.addWidget(QLabel("File xuất:"), 1, 0)
        srt_grid.addWidget(self.srt_output_input, 1, 1)
        b = QPushButton("Chọn File")
        b.setIcon(get_svg_icon("file", "#ffffff", 14))
        b.clicked.connect(lambda: self._browse_line_path(self.srt_output_input))
        srt_grid.addWidget(b, 1, 2)

        srt_grid.addWidget(QLabel("Khoảng dừng (ms):"), 2, 0)
        srt_grid.addWidget(self.srt_gap_spin, 2, 1)
        srt_l.addLayout(srt_grid)

        row = QHBoxLayout()
        scan = QPushButton("Quét Thư Mục")
        scan.setIcon(get_svg_icon("refresh", "#ffffff", 14))
        scan.clicked.connect(self._voice_scan_srt)
        row.addWidget(scan)

        merge = QPushButton("Ghép Phụ Đề")
        merge.setIcon(get_svg_icon("layers", "#ffffff", 14))
        merge.setObjectName("primaryBtn")
        merge.clicked.connect(self.merge_srt_native)
        row.addWidget(merge)

        clear = QPushButton("Xóa Danh Sách")
        clear.setIcon(get_svg_icon("trash", "#ffffff", 14))
        clear.clicked.connect(lambda: self.srt_files_list.clear())
        row.addWidget(clear)
        row.addStretch()
        srt_l.addLayout(row)

        self.srt_files_list = QListWidget()
        srt_l.addWidget(self.srt_files_list, 1)
        self.voice_tabs.addTab(srt_tab, "Ghép Phụ Đề SRT")

        # Tab 3: JSON 20 parts -> voice
        json_tab = QWidget()
        json_l = QVBoxLayout(json_tab)
        json_l.setSpacing(10)
        jgrid = QGridLayout()
        self.json_script_input = QLineEdit()
        self.json_parts_input = QLineEdit()
        self.json_output_dir = QLineEdit(str(Path(self.tool_root()) / "voices" / "json_20_parts"))

        jgrid.addWidget(QLabel("File kịch bản:"), 0, 0)
        jgrid.addWidget(self.json_script_input, 0, 1)
        b = QPushButton("Chọn File")
        b.setIcon(get_svg_icon("file", "#ffffff", 14))
        b.clicked.connect(lambda: self._browse_line_path(self.json_script_input))
        jgrid.addWidget(b, 0, 2)

        jgrid.addWidget(QLabel("File phân đoạn JSON:"), 1, 0)
        jgrid.addWidget(self.json_parts_input, 1, 1)
        b = QPushButton("Chọn File")
        b.setIcon(get_svg_icon("file", "#ffffff", 14))
        b.clicked.connect(lambda: self._browse_line_path(self.json_parts_input))
        jgrid.addWidget(b, 1, 2)

        jgrid.addWidget(QLabel("Thư mục xuất:"), 2, 0)
        jgrid.addWidget(self.json_output_dir, 2, 1)
        b = QPushButton("Chọn Thư Mục")
        b.setIcon(get_svg_icon("folder", "#ffffff", 14))
        b.clicked.connect(lambda: self._browse_line_path(self.json_output_dir, True))
        jgrid.addWidget(b, 2, 2)
        json_l.addLayout(jgrid)

        info = QLabel("Đọc các phân đoạn trong file kịch bản, trích xuất lời thoại và tạo âm thanh theo thứ tự.")
        info.setObjectName("mutedText")
        info.setWordWrap(True)
        json_l.addWidget(info)

        row = QHBoxLayout()
        run = QPushButton("Tạo Giọng Đọc Phân Đoạn")
        run.setIcon(get_svg_icon("play", "#ffffff", 14))
        run.setObjectName("primaryBtn")
        run.clicked.connect(self._start_json_parts_voice_native)
        row.addWidget(run)
        row.addStretch()
        json_l.addLayout(row)

        self.json_parts_list = QListWidget()
        json_l.addWidget(self.json_parts_list, 1)
        self.voice_tabs.addTab(json_tab, "Kịch Bản Phân Đoạn")

        root.addWidget(left, 3)

        # Right side stats & logs
        right = QFrame()
        right.setObjectName("toolCard")
        right_l = QVBoxLayout(right)
        right_l.setSpacing(10)

        stats_box = QFrame()
        stats_layout = QHBoxLayout(stats_box)
        stats_layout.setContentsMargins(0, 0, 0, 0)

        d_box = QFrame()
        d_box.setObjectName("statCard")
        d_l = QVBoxLayout(d_box)
        d_l.addWidget(QLabel("Đã hoàn tất:"))
        self.voice_done_label = QLabel("0")
        self.voice_done_label.setStyleSheet("color: #34d399; font-size: 20px; font-weight: 800;")
        d_l.addWidget(self.voice_done_label)
        stats_layout.addWidget(d_box)

        t_box = QFrame()
        t_box.setObjectName("statCard")
        t_l = QVBoxLayout(t_box)
        t_l.addWidget(QLabel("Tổng file:"))
        self.voice_total_label = QLabel("0")
        self.voice_total_label.setStyleSheet("color: #58a6ff; font-size: 20px; font-weight: 800;")
        t_l.addWidget(self.voice_total_label)
        stats_layout.addWidget(t_box)

        right_l.addWidget(stats_box)

        self.voice_progress = QProgressBar()
        self.voice_progress.setRange(0, 100)
        self.voice_progress.setValue(0)
        self.voice_progress.setFixedHeight(6)
        right_l.addWidget(self.voice_progress)

        self.voice_log = QPlainTextEdit()
        self.voice_log.setReadOnly(True)
        self.voice_log.setPlaceholderText("Nhật ký sinh giọng AI và tiến trình xử lý...")
        right_l.addWidget(self.voice_log, 1)

        root.addWidget(right, 2)

        self._on_provider_changed()

    def _default_tool_root(self) -> Path:
        here = Path(__file__).resolve()
        return here.parent.parent.parent.parent

    def tool_root(self) -> Path:
        return self.tool_root_fn()

    def _on_provider_changed(self):
        is_edge = "edge" in self.voice_provider_combo.currentText().lower()
        self.edge_voice_combo.setVisible(is_edge)
        self.lbl_edge_voice.setVisible(is_edge)
        self.provider_api_keys.setVisible(not is_edge)
        self.lbl_custom_voice.setVisible(not is_edge)

    def _browse_line_path(self, line_edit: QLineEdit, is_dir: bool = False):
        if is_dir:
            path = QFileDialog.getExistingDirectory(self, "Chọn thư mục", line_edit.text() or str(Path.home()))
        else:
            path, _ = QFileDialog.getOpenFileName(self, "Chọn file", line_edit.text() or str(Path.home()), "All files (*.*)")
        if path:
            line_edit.setText(path)

    def _voice_scan_txt(self):
        folder = Path(self.voice_txt_dir.text().strip())
        if not folder.exists():
            single = Path(self.voice_input_path.text().strip())
            if single.exists() and single.suffix.lower() == ".txt":
                self.voice_files_list.clear()
                self.voice_files_list.addItem(str(single))
                self.voice_total_label.setText("1 file")
                self.voice_log.appendPlainText(f"Đã chọn file TXT lẻ: {single.name}")
                return
            QMessageBox.information(self, "Thư mục không tồn tại", "Vui lòng chọn thư mục hoặc file TXT hợp lệ.")
            return

        files = sorted(folder.glob("*.txt"), key=lambda x: [int(c) if c.isdigit() else c for c in re.split(r"(\d+)", x.name)])
        self.voice_files_list.clear()
        for f in files:
            self.voice_files_list.addItem(str(f))
        self.voice_total_label.setText(f"{len(files)} file")
        self.voice_log.appendPlainText(f"Đã quét được {len(files)} file TXT trong {folder}")

    def _voice_scan_srt(self):
        folder = Path(self.srt_dir_input.text().strip())
        if not folder.exists():
            QMessageBox.information(self, "Thư mục không tồn tại", "Vui lòng chọn thư mục SRT hợp lệ.")
            return
        files = sorted(folder.glob("*.srt"), key=lambda x: [int(c) if c.isdigit() else c for c in re.split(r"(\d+)", x.name)])
        self.srt_files_list.clear()
        for f in files:
            self.srt_files_list.addItem(str(f))
        self.voice_log.appendPlainText(f"Đã quét được {len(files)} file SRT trong {folder}")

    def _voice_clear_files(self):
        self.voice_files_list.clear()
        self.voice_done_label.setText("0")
        self.voice_total_label.setText("0 file")
        self.voice_progress.setValue(0)

    def _voice_save_provider_config(self):
        provider = self.voice_provider_combo.currentText()
        if "edge" in provider.lower():
            self.voice_log.appendPlainText("Edge TTS là dịch vụ miễn phí, không yêu cầu lưu API key!")
            return
        tool = Path(self.tool_root()) / "tool-config.json"
        cfg = json.loads(tool.read_text(encoding="utf-8")) if tool.exists() else {"providers": {}}
        cfg["provider"] = provider
        cfg.setdefault("providers", {})[provider] = {
            "apiKeys": self.provider_api_keys.toPlainText(),
            "voiceId": self.voice_id_input.text().strip() or self.larvoice_id_input.text().strip()
        }
        try:
            tool.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
            self.voice_log.appendPlainText(f"Đã lưu cài đặt dịch vụ: {provider}")
        except Exception as e:
            self.voice_log.appendPlainText(f"Lỗi lưu cài đặt: {e}")

    def _start_json_parts_voice_native(self):
        json_file = Path(self.json_parts_input.text().strip())
        if not json_file.exists():
            QMessageBox.information(self, "Thiếu file", "Vui lòng chọn file kịch bản phân đoạn JSON.")
            return
        out_dir = Path(self.json_output_dir.text().strip())
        txt_dir = out_dir / "parts_txt"
        txt_dir.mkdir(parents=True, exist_ok=True)
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
        except Exception as e:
            QMessageBox.warning(self, "Lỗi đọc JSON", str(e))
            return

        parts = data.get("parts") or data.get("scenes") or (data if isinstance(data, list) else [])
        if not parts:
            QMessageBox.information(self, "Không có phân đoạn", "File JSON không chứa danh sách phân đoạn kịch bản.")
            return

        self.voice_files_list.clear()
        self.json_parts_list.clear()
        for i, part in enumerate(parts, 1):
            text = str(part.get("dialogue") or part.get("text") or part.get("content") or part.get("voice") or "").strip()
            f = txt_dir / f"{i:02d}.txt"
            f.write_text(text, encoding="utf-8")
            self.voice_files_list.addItem(str(f))
            self.json_parts_list.addItem(f"{i:02d}: {text[:90]}")

        self.voice_output_dir.setText(str(out_dir))
        self.voice_tabs.setCurrentIndex(0)
        self.voice_log.appendPlainText(f"Đã tạo {self.voice_files_list.count()} file TXT từ kịch bản phân đoạn.")
        self.start_native_voice()

    def start_native_voice(self):
        if self.voice_files_list.count() == 0:
            self._voice_scan_txt()

        files = [Path(self.voice_files_list.item(i).text()) for i in range(self.voice_files_list.count())]
        if not files:
            QMessageBox.information(self, "Trống", "Không có file TXT nào để tạo giọng đọc.")
            return

        if self.worker and self.worker.isRunning():
            QMessageBox.information(self, "Đang xử lý", "Tiến trình tạo giọng trước đó đang chạy.")
            return

        out = Path(self.voice_output_dir.text().strip() or "voices")
        out.mkdir(parents=True, exist_ok=True)
        self.voice_done_label.setText("0")
        self.voice_total_label.setText(f"{len(files)} file")
        self.voice_progress.setValue(0)

        provider = self.voice_provider_combo.currentText()
        voice_id = self.edge_voice_combo.currentData() if "edge" in provider.lower() else (self.voice_id_input.text().strip() or "default")
        speed = self.voice_speed_spin.value()
        gen_srt = self.generate_srt_checkbox.isChecked()

        self.voice_log.appendPlainText(f"Khởi động tiến trình sinh giọng: {provider} -> {len(files)} files...")

        self.worker = VoiceGenerationWorker(
            files=files,
            output_dir=out,
            provider=provider,
            voice_id=voice_id,
            speed=speed,
            generate_srt=gen_srt,
            tool_root=Path(self.tool_root())
        )

        self.worker.log_signal.connect(self.voice_log.appendPlainText)
        self.worker.progress_signal.connect(self._on_worker_progress)
        self.worker.finished_signal.connect(self._on_worker_finished)
        self.worker.start()

    def _on_worker_progress(self, cur: int, total: int):
        self.voice_done_label.setText(str(cur))
        if total > 0:
            self.voice_progress.setValue(int(cur / total * 100))

    def _on_worker_finished(self, success: int, total: int):
        self.voice_progress.setValue(100)
        self.voice_log.appendPlainText(f"\n[HOÀN TẤT] Đã tạo thành công {success}/{total} files giọng đọc.")

    def merge_srt_native(self):
        if self.srt_files_list.count():
            files = [Path(self.srt_files_list.item(i).text()) for i in range(self.srt_files_list.count())]
        else:
            folder = Path(self.srt_dir_input.text().strip())
            files = sorted(folder.glob("*.srt"), key=lambda x: [int(c) if c.isdigit() else c for c in re.split(r"(\d+)", x.name)]) if folder.exists() else []

        if not files:
            QMessageBox.information(self, "Không có phụ đề", "Vui lòng chọn hoặc quét thư mục chứa file .srt trước.")
            return

        out = Path(self.srt_output_input.text().strip() or str(Path(self.voice_output_dir.text().strip()) / "kich_ban_hoan_chinh.srt"))
        gap = self.srt_gap_spin.value()
        blocks = []
        offset_ms = 0

        for f in files:
            raw = f.read_text(encoding="utf-8", errors="ignore").replace("\r\n", "\n").replace("\r", "\n")
            parsed = []
            for block in re.split(r"\n{2,}", raw.strip()):
                lines = [l.strip() for l in block.split("\n") if l.strip()]
                if lines and lines[0].isdigit():
                    lines = lines[1:]
                if not lines or "-->" not in lines[0]:
                    continue
                a, b = [x.strip().split()[0] for x in lines[0].split("-->")]
                start_ms = int(srt_time_to_seconds(a) * 1000)
                end_ms = int(srt_time_to_seconds(b) * 1000)
                parsed.append((start_ms, end_ms, "\n".join(lines[1:]).strip()))

            if not parsed:
                continue

            base = parsed[0][0]
            last = 0
            for st, en, txt in parsed:
                ns = offset_ms + (st - base)
                ne = offset_ms + (en - base)
                blocks.append((ns, ne, txt))
                last = max(last, ne)
            offset_ms = last + gap

        def fmt(ms):
            h = ms // 3600000
            ms %= 3600000
            m = ms // 60000
            ms %= 60000
            sec = ms // 1000
            ms %= 1000
            return f"{h:02d}:{m:02d}:{sec:02d},{ms:03d}"

        body = "\n\n".join(f"{i}\n{fmt(st)} --> {fmt(en)}\n{txt}" for i, (st, en, txt) in enumerate(blocks, 1)) + "\n"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(body, encoding="utf-8")
        self.voice_log.appendPlainText(f"Đã ghép {len(files)} file SRT ({len(blocks)} dòng phụ đề) -> {out}")
