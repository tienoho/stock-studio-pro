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
from PyQt6.QtCore import pyqtSignal, QUrl
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput

from ...core.models.scene import srt_time_to_seconds, extract_scenes_from_json
from ...infrastructure.media.ffmpeg_processor import FFmpegProcessor
from ...application.services.edge_tts_service import EdgeTTSService, AVAILABLE_VOICES
from ...application.services.subtitle_service import SubtitleService
from ..workers.voice_worker import VoiceGenerationWorker
from ..styles.icons import get_svg_icon, get_svg_pixmap
from ..styles.ui_enhancer import enhance_widget_interactions, format_tooltip
from ..components.stat_box import StatBox


class VoiceTab(QWidget):
    """Voice TXT generation and SRT stitching studio."""

    log_message = pyqtSignal(str)
    finished = pyqtSignal(bool, str)
    nextStepRequested = pyqtSignal()

    def __init__(self, tool_root_fn=None, config=None, save_config_fn=None, parent=None):
        super().__init__(parent)
        self.tool_root_fn = tool_root_fn or self._default_tool_root
        self.config = config or {}
        self.save_config_fn = save_config_fn
        self.subtitle_service = SubtitleService()
        self.worker: Optional[VoiceGenerationWorker] = None
        self.audio_output = QAudioOutput()
        self.player = QMediaPlayer()
        self.player.setAudioOutput(self.audio_output)

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
        b.setFixedHeight(32)
        b.clicked.connect(lambda: self._browse_line_path(self.voice_txt_dir, True))
        txt_grid.addWidget(b, 0, 2)

        txt_grid.addWidget(QLabel("File TXT lẻ:"), 1, 0)
        txt_grid.addWidget(self.voice_input_path, 1, 1)
        b = QPushButton("Chọn...")
        b.setIcon(get_svg_icon("file", "#ffffff", 14))
        b.setFixedHeight(32)
        b.clicked.connect(lambda: self._browse_line_path(self.voice_input_path))
        txt_grid.addWidget(b, 1, 2)

        txt_grid.addWidget(QLabel("Thư mục âm thanh:"), 2, 0)
        txt_grid.addWidget(self.voice_output_dir, 2, 1)
        b = QPushButton("Chọn...")
        b.setIcon(get_svg_icon("folder", "#ffffff", 14))
        b.setFixedHeight(32)
        b.clicked.connect(lambda: self._browse_line_path(self.voice_output_dir, True))
        txt_grid.addWidget(b, 2, 2)

        txt_grid.addWidget(QLabel("Dịch vụ giọng:"), 3, 0)
        txt_grid.addWidget(self.voice_provider_combo, 3, 1)
        txt_grid.addWidget(QLabel("Tốc độ:"), 3, 2)
        txt_grid.addWidget(self.voice_speed_spin, 3, 3)

        self.lbl_edge_voice = QLabel("Giọng đọc AI:")
        txt_grid.addWidget(self.lbl_edge_voice, 4, 0)
        edge_voice_box = QHBoxLayout()
        edge_voice_box.addWidget(self.edge_voice_combo, 1)
        self.btn_preview_voice = QPushButton("Nghe Thử")
        self.btn_preview_voice.setIcon(get_svg_icon("play", "#ffffff", 14))
        self.btn_preview_voice.setObjectName("accentBtn")
        self.btn_preview_voice.setFixedHeight(32)
        self.btn_preview_voice.setToolTip(format_tooltip("Nghe thử một câu mẫu của giọng đọc đã chọn", "Space"))
        self.btn_preview_voice.clicked.connect(self._test_selected_voice)
        edge_voice_box.addWidget(self.btn_preview_voice)
        txt_grid.addLayout(edge_voice_box, 4, 1, 1, 3)

        self.lbl_custom_voice = QLabel("Mã giọng / API Key:")
        txt_grid.addWidget(self.lbl_custom_voice, 5, 0)
        txt_grid.addWidget(self.provider_api_keys, 5, 1, 1, 3)

        txt_l.addLayout(txt_grid)
        txt_l.addWidget(self.generate_srt_checkbox)

        row = QHBoxLayout()
        for text, fn, icon_name, btn_type, sc_hint in [
            ("Quét Thư Mục", self._voice_scan_txt, "refresh", "secondaryBtn", "F5"),
            ("Tạo Giọng Đọc", self.start_native_voice, "play", "successBtn", "Ctrl+Enter"),
            ("Xóa Danh Sách", self._voice_clear_files, "trash", "dangerBtn", "Delete"),
            ("Lưu Cài Đặt", self._voice_save_provider_config, "save", "primaryBtn", "Ctrl+S"),
        ]:
            btn = QPushButton(text)
            btn.setIcon(get_svg_icon(icon_name, "#ffffff", 14))
            btn.setFixedHeight(36)
            btn.setObjectName(btn_type)
            btn.setToolTip(format_tooltip(text, sc_hint))
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
        b.setFixedHeight(32)
        b.clicked.connect(lambda: self._browse_line_path(self.srt_dir_input, True))
        srt_grid.addWidget(b, 0, 2)

        srt_grid.addWidget(QLabel("File xuất:"), 1, 0)
        srt_grid.addWidget(self.srt_output_input, 1, 1)
        b = QPushButton("Chọn File")
        b.setIcon(get_svg_icon("file", "#ffffff", 14))
        b.setFixedHeight(32)
        b.clicked.connect(lambda: self._browse_line_path(self.srt_output_input))
        srt_grid.addWidget(b, 1, 2)

        srt_grid.addWidget(QLabel("Khoảng dừng (ms):"), 2, 0)
        srt_grid.addWidget(self.srt_gap_spin, 2, 1)
        srt_l.addLayout(srt_grid)

        row = QHBoxLayout()
        scan = QPushButton("Quét Thư Mục")
        scan.setIcon(get_svg_icon("refresh", "#ffffff", 14))
        scan.setObjectName("secondaryBtn")
        scan.setFixedHeight(36)
        scan.setToolTip(format_tooltip("Quét lại danh sách file SRT", "F5"))
        scan.clicked.connect(self._voice_scan_srt)
        row.addWidget(scan)

        merge = QPushButton("Ghép Phụ Đề")
        merge.setIcon(get_svg_icon("layers", "#ffffff", 14))
        merge.setObjectName("primaryBtn")
        merge.setFixedHeight(36)
        merge.setToolTip(format_tooltip("Ghép toàn bộ file phụ đề thành 1 kịch bản hoàn chỉnh", "Enter"))
        merge.clicked.connect(lambda: self.merge_srt_native(False))
        row.addWidget(merge)

        merge_audio_btn = QPushButton("Ghép Master Audio")
        merge_audio_btn.setIcon(get_svg_icon("volume", "#ffffff", 14))
        merge_audio_btn.setObjectName("accentBtn")
        merge_audio_btn.setFixedHeight(36)
        merge_audio_btn.setToolTip(format_tooltip("Nối các đoạn âm thanh thành file Master", "Space"))
        merge_audio_btn.clicked.connect(lambda: self.merge_audio_native(False))
        row.addWidget(merge_audio_btn)

        clear = QPushButton("Xóa Danh Sách")
        clear.setIcon(get_svg_icon("trash", "#ffffff", 14))
        clear.setObjectName("dangerBtn")
        clear.setFixedHeight(36)
        clear.setToolTip(format_tooltip("Xóa danh sách file SRT", "Delete"))
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
        b.setFixedHeight(32)
        b.clicked.connect(lambda: self._browse_line_path(self.json_script_input))
        jgrid.addWidget(b, 0, 2)

        jgrid.addWidget(QLabel("File phân đoạn JSON:"), 1, 0)
        jgrid.addWidget(self.json_parts_input, 1, 1)
        b = QPushButton("Chọn File")
        b.setIcon(get_svg_icon("file", "#ffffff", 14))
        b.setFixedHeight(32)
        b.clicked.connect(lambda: self._browse_line_path(self.json_parts_input))
        jgrid.addWidget(b, 1, 2)

        jgrid.addWidget(QLabel("Thư mục xuất:"), 2, 0)
        jgrid.addWidget(self.json_output_dir, 2, 1)
        b = QPushButton("Chọn Thư Mục")
        b.setIcon(get_svg_icon("folder", "#ffffff", 14))
        b.setFixedHeight(32)
        b.clicked.connect(lambda: self._browse_line_path(self.json_output_dir, True))
        jgrid.addWidget(b, 2, 2)
        json_l.addLayout(jgrid)

        # Standardize height for all inputs
        for inp in [
            self.voice_txt_dir, self.voice_input_path, self.voice_output_dir,
            self.voice_provider_combo, self.edge_voice_combo, self.voice_speed_spin,
            self.srt_dir_input, self.srt_output_input, self.srt_gap_spin,
            self.json_script_input, self.json_parts_input, self.json_output_dir
        ]:
            inp.setFixedHeight(32)

        info = QLabel("Đọc các phân đoạn trong file kịch bản, trích xuất lời thoại và tạo âm thanh theo thứ tự.")
        info.setObjectName("mutedText")
        info.setWordWrap(True)
        json_l.addWidget(info)

        row = QHBoxLayout()
        run = QPushButton("Tạo Giọng Đọc Phân Đoạn")
        run.setIcon(get_svg_icon("play", "#ffffff", 14))
        run.setObjectName("primaryBtn")
        run.setFixedHeight(36)
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
        stats_layout.setSpacing(10)

        self.stat_done = StatBox("0", "ĐÃ HOÀN TẤT", "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 rgba(16, 185, 129, 0.22), stop:1 rgba(5, 150, 105, 0.08))")
        self.stat_total = StatBox("0", "TỔNG FILE", "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 rgba(99, 102, 241, 0.22), stop:1 rgba(79, 70, 229, 0.08))")
        self.voice_done_label = self.stat_done.value_label
        self.voice_total_label = self.stat_total.value_label

        stats_layout.addWidget(self.stat_done)
        stats_layout.addWidget(self.stat_total)
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

        self.btn_next_step = QPushButton("Bước 3: Ghép Video Thành Phẩm ➔")
        self.btn_next_step.setIcon(get_svg_icon("activity", "#ffffff", 14))
        self.btn_next_step.setObjectName("accentBtn")
        self.btn_next_step.setFixedHeight(36)
        self.btn_next_step.setStyleSheet("""
            QPushButton#accentBtn {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6366f1, stop:1 #8b5cf6);
                color: #ffffff;
                font-size: 11px;
                font-weight: 800;
                padding: 0 14px;
                border-radius: 6px;
                border: 1px solid rgba(255,255,255,0.18);
            }
            QPushButton#accentBtn:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4f46e5, stop:1 #7c3aed);
            }
        """)
        self.btn_next_step.setToolTip(format_tooltip("Chuyển sang Bước 3: Ghép video khớp với giọng đọc AI", "Ctrl+3"))
        self.btn_next_step.clicked.connect(lambda: self.nextStepRequested.emit())
        right_l.addWidget(self.btn_next_step)

        root.addWidget(right, 2)

        self._on_provider_changed()
        enhance_widget_interactions(self)

    def _default_tool_root(self) -> Path:
        here = Path(__file__).resolve()
        return here.parent.parent.parent.parent

    def tool_root(self) -> Path:
        return self.tool_root_fn()

    def _on_provider_changed(self):
        is_edge = "edge" in self.voice_provider_combo.currentText().lower()
        self.edge_voice_combo.setVisible(is_edge)
        self.lbl_edge_voice.setVisible(is_edge)
        self.btn_preview_voice.setVisible(is_edge)
        self.provider_api_keys.setVisible(not is_edge)
        self.lbl_custom_voice.setVisible(not is_edge)

    def _test_selected_voice(self):
        """Generates a brief sample utterance and plays it immediately."""
        voice_id = self.edge_voice_combo.currentData() or "vi-VN-HoaiMyNeural"
        speed = self.voice_speed_spin.value()
        speed_pct = f"{int((speed - 1.0) * 100):+d}%"
        is_vi = "vi" in voice_id.lower()
        test_text = "Xin chào! Đây là bản nghe thử giọng đọc AI thông minh từ AutoStock Studio." if is_vi else "Hello! This is a smart AI voice sample from AutoStock Studio."
        self.voice_log.appendPlainText(f"Đang sinh giọng mẫu nghe thử ({voice_id})...")

        sample_path = Path.home() / ".autostock_voice_sample.mp3"
        service = EdgeTTSService(default_voice=voice_id)
        ok, msg = service.synthesize(test_text, sample_path, voice=voice_id, rate=speed_pct)
        if ok and sample_path.exists():
            self.voice_log.appendPlainText("Đang phát âm thanh mẫu thử nghiệm...")
            self.player.setSource(QUrl.fromLocalFile(str(sample_path)))
            self.player.play()
        else:
            self.voice_log.appendPlainText(f"Lỗi nghe thử: {msg}")

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
        cfg = json.loads(tool.read_text(encoding="utf-8-sig")) if tool.exists() else {"providers": {}}
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
        target_path_str = self.json_parts_input.text().strip() or self.json_script_input.text().strip()
        json_file = Path(target_path_str)
        if not json_file.exists():
            QMessageBox.information(self, "Thiếu file", "Vui lòng chọn file kịch bản phân đoạn JSON.")
            self.finished.emit(False, "Chưa chọn file kịch bản JSON.")
            return

        out_dir = Path(self.json_output_dir.text().strip() or str(Path(self.tool_root()) / "voices" / "json_parts"))
        txt_dir = out_dir / "parts_txt"
        txt_dir.mkdir(parents=True, exist_ok=True)
        try:
            data = json.loads(json_file.read_text(encoding="utf-8-sig"))
        except Exception as e:
            QMessageBox.warning(self, "Lỗi đọc JSON", str(e))
            self.finished.emit(False, f"Lỗi đọc JSON: {e}")
            return

        parts = data.get("parts") or data.get("scenes") or (data if isinstance(data, list) else [])
        if not parts:
            parts = extract_scenes_from_json(data)

        if not parts:
            QMessageBox.information(self, "Không có phân đoạn", "File JSON không chứa danh sách phân đoạn kịch bản.")
            self.finished.emit(False, "File JSON không chứa phân đoạn.")
            return

        self.voice_files_list.clear()
        self.json_parts_list.clear()
        for i, part in enumerate(parts, 1):
            if isinstance(part, dict):
                text = str(
                    part.get("dialogue") or part.get("dialogue_es") or
                    part.get("text") or part.get("content") or
                    part.get("voice") or part.get("description") or ""
                ).strip()
            else:
                text = str(getattr(part, "dialogue", "") or getattr(part, "description", "")).strip()

            if not text:
                continue

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
            self.finished.emit(False, "Không có file TXT nào để tạo giọng đọc.")
            return

        if self.worker and self.worker.isRunning():
            QMessageBox.information(self, "Đang xử lý", "Tiến trình tạo giọng trước đó đang chạy.")
            self.finished.emit(False, "Tiến trình tạo giọng trước đó đang chạy.")
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

    def stop_voice(self):
        """Request graceful cancellation of running voice worker."""
        if hasattr(self, "worker") and self.worker and self.worker.isRunning():
            self.worker.stop()
            self.voice_log.appendPlainText("[DỪNG] Đang yêu cầu dừng tiến trình tạo giọng...")

    def _on_worker_progress(self, cur: int, total: int):
        self.voice_done_label.setText(str(cur))
        if total > 0:
            self.voice_progress.setValue(int(cur / total * 100))

    def _on_worker_finished(self, success: int, total: int):
        self.voice_progress.setValue(100)
        msg = f"Đã tạo thành công {success}/{total} files giọng đọc."
        self.voice_log.appendPlainText(f"\n[HOÀN TẤT] {msg}")

        # Automatically merge SRT subtitles and audio files if enabled
        if success > 0:
            if self.generate_srt_checkbox.isChecked():
                self.merge_srt_native(silent=True)
            self.merge_audio_native(silent=True)
            if hasattr(self, "btn_next_step"):
                self.btn_next_step.setStyleSheet("""
                    QPushButton#accentBtn {
                        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #10b981, stop:1 #059669);
                        color: #ffffff;
                        font-size: 11px;
                        font-weight: 800;
                        padding: 0 14px;
                        border-radius: 6px;
                        border: 1px solid rgba(255,255,255,0.3);
                    }
                    QPushButton#accentBtn:hover {
                        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #059669, stop:1 #047857);
                    }
                """)
                self.btn_next_step.setText("TIẾP TỤC: GHÉP VIDEO THÀNH PHẨM ➔")

        self.finished.emit(success > 0 or total == 0, msg)

    def merge_audio_native(self, silent: bool = False):
        """Merges generated scene audio clips into a master audio file."""
        folder = Path(self.voice_output_dir.text().strip() or "voices")
        if not folder.exists():
            if not silent:
                QMessageBox.information(self, "Không tìm thấy thư mục", "Thư mục xuất âm thanh không tồn tại.")
            return

        audio_exts = {".mp3", ".wav", ".aac", ".m4a"}
        files = sorted(
            [f for f in folder.iterdir() if f.is_file() and f.suffix.lower() in audio_exts and not f.name.startswith("master_") and not f.name.startswith("kich_ban_")],
            key=lambda x: [int(c) if c.isdigit() else c for c in re.split(r"(\d+)", x.name)]
        )

        if not files:
            if not silent:
                QMessageBox.information(self, "Không có âm thanh", "Không tìm thấy file âm thanh (.mp3, .wav, .aac, .m4a) nào để ghép trong thư mục xuất.")
            return

        out = folder / "master_voice.mp3"
        proc = FFmpegProcessor()
        ok, err = proc.concat_audio(files, out)
        if ok and out.exists():
            self.voice_log.appendPlainText(f"[MASTER AUDIO] Đã ghép {len(files)} file audio -> {out.name} ({out.stat().st_size // 1024} KB)")
        else:
            self.voice_log.appendPlainText(f"[LỖI GHÉP AUDIO] {err[:120] if err else 'Không xác định'}")

    def merge_srt_native(self, silent: bool = False):
        if self.srt_files_list.count():
            files = [Path(self.srt_files_list.item(i).text()) for i in range(self.srt_files_list.count())]
        else:
            folder = Path(self.srt_dir_input.text().strip())
            if not folder.exists():
                folder = Path(self.voice_output_dir.text().strip() or "voices")
            files = sorted(
                [f for f in folder.glob("*.srt") if not f.name.startswith("kich_ban_")],
                key=lambda x: [int(c) if c.isdigit() else c for c in re.split(r"(\d+)", x.name)]
            ) if folder.exists() else []

        if not files:
            if not silent:
                QMessageBox.information(self, "Không có phụ đề", "Vui lòng chọn hoặc quét thư mục chứa file .srt trước.")
            return

        out = Path(self.srt_output_input.text().strip() or str(Path(self.voice_output_dir.text().strip() or "voices") / "kich_ban_hoan_chinh.srt"))
        gap = self.srt_gap_spin.value()
        ok, msg, count = self.subtitle_service.merge_srt_files(files, out, gap_ms=gap)
        if ok:
            self.voice_log.appendPlainText(f"[PHỤ ĐỀ HOÀN THÀNH] {msg} -> {out.name}")
        else:
            self.voice_log.appendPlainText(f"[LỖI GHÉP PHỤ ĐỀ] {msg}")
