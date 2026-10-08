"""
Voice TXT Studio tab widget for TTS voiceover generation and SRT subtitle stitching.
"""

import re
import json
import subprocess
import os
import sys
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QLineEdit, QPushButton, QComboBox, QDoubleSpinBox, QSpinBox,
    QPlainTextEdit, QTabWidget, QListWidget, QFileDialog, QMessageBox, QApplication
)
from PyQt6.QtCore import pyqtSignal

from ...core.models.scene import srt_time_to_seconds


class VoiceTab(QWidget):
    """Voice TXT generation and SRT stitching studio."""

    log_message = pyqtSignal(str)

    def __init__(self, tool_root_fn=None, config=None, save_config_fn=None, parent=None):
        super().__init__(parent)
        self.config = config or {}
        self.save_config_fn = save_config_fn
        self.tool_root_fn = tool_root_fn or self._default_tool_root

        root = QHBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(14)

        left = QFrame()
        left.setObjectName("toolCard")
        left_l = QVBoxLayout(left)
        left_l.setSpacing(10)

        title = QLabel("Tạo Giọng Đọc & Phụ Đề")
        title.setObjectName("heroTitle")
        left_l.addWidget(title)

        hint = QLabel(
            "Tạo giọng đọc từ văn bản TXT, ghép nối file phụ đề SRT và xử lý giọng đọc theo kịch bản phân đoạn."
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
        self.voice_output_dir = QLineEdit(str(self.tool_root() / "Voice TXT Tool" / "voices"))
        self.voice_provider_combo = QComboBox()
        self.voice_provider_combo.addItems(["11labs", "larvoice", "vivibe", "genmax", "ai84", "vbee", "default"])
        self.voice_speed_spin = QDoubleSpinBox()
        self.voice_speed_spin.setRange(0.5, 2.0)
        self.voice_speed_spin.setSingleStep(0.1)
        self.voice_speed_spin.setValue(1.0)
        self.voice_id_input = QLineEdit()
        self.voice_id_input.setPlaceholderText("Mã giọng (Voice ID)...")
        self.larvoice_id_input = QLineEdit("1")
        self.provider_api_keys = QPlainTextEdit()
        self.provider_api_keys.setPlaceholderText("Danh sách API key của dịch vụ đã chọn (mỗi dòng một key)...")
        self.provider_api_keys.setMaximumHeight(90)

        txt_grid.addWidget(QLabel("Thư mục TXT:"), 0, 0)
        txt_grid.addWidget(self.voice_txt_dir, 0, 1)
        b = QPushButton("Chọn Thư Mục")
        b.clicked.connect(lambda: self._browse_line_path(self.voice_txt_dir, True))
        txt_grid.addWidget(b, 0, 2)

        txt_grid.addWidget(QLabel("File TXT lẻ:"), 1, 0)
        txt_grid.addWidget(self.voice_input_path, 1, 1)
        b = QPushButton("Chọn File")
        b.clicked.connect(lambda: self._browse_line_path(self.voice_input_path))
        txt_grid.addWidget(b, 1, 2)

        txt_grid.addWidget(QLabel("Thư mục âm thanh:"), 2, 0)
        txt_grid.addWidget(self.voice_output_dir, 2, 1)
        b = QPushButton("Chọn Thư Mục")
        b.clicked.connect(lambda: self._browse_line_path(self.voice_output_dir, True))
        txt_grid.addWidget(b, 2, 2)

        txt_grid.addWidget(QLabel("Nhà cung cấp:"), 3, 0)
        txt_grid.addWidget(self.voice_provider_combo, 3, 1)
        txt_grid.addWidget(QLabel("Tốc độ:"), 3, 2)
        txt_grid.addWidget(self.voice_speed_spin, 3, 3)

        txt_grid.addWidget(QLabel("Mã giọng đọc:"), 4, 0)
        txt_grid.addWidget(self.voice_id_input, 4, 1)
        txt_grid.addWidget(QLabel("Mã LarVoice:"), 4, 2)
        txt_grid.addWidget(self.larvoice_id_input, 4, 3)

        txt_grid.addWidget(QLabel("API Key:"), 5, 0)
        txt_grid.addWidget(self.provider_api_keys, 5, 1, 1, 3)
        txt_l.addLayout(txt_grid)

        row = QHBoxLayout()
        for text, fn in [
            ("Quét Thư Mục", self._voice_scan_txt),
            ("Tạo Giọng Đọc", self.start_native_voice),
            ("Xóa Danh Sách", self._voice_clear_files),
            ("Lưu Cài Đặt", self._voice_save_provider_config),
        ]:
            btn = QPushButton(text)
            btn.setObjectName("primaryBtn" if text == "Tạo Giọng Đọc" else "")
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
        self.srt_dir_input = QLineEdit(str(self.tool_root() / "Voice TXT Tool" / "voices"))
        self.srt_output_input = QLineEdit(str(self.tool_root() / "Voice TXT Tool" / "kich_ban_hoan_chinh.srt"))
        self.srt_gap_spin = QSpinBox()
        self.srt_gap_spin.setRange(0, 5000)
        self.srt_gap_spin.setSingleStep(50)
        self.srt_gap_spin.setValue(250)

        srt_grid.addWidget(QLabel("Thư mục SRT:"), 0, 0)
        srt_grid.addWidget(self.srt_dir_input, 0, 1)
        b = QPushButton("Chọn Thư Mục")
        b.clicked.connect(lambda: self._browse_line_path(self.srt_dir_input, True))
        srt_grid.addWidget(b, 0, 2)

        srt_grid.addWidget(QLabel("File xuất:"), 1, 0)
        srt_grid.addWidget(self.srt_output_input, 1, 1)
        b = QPushButton("Chọn File")
        b.clicked.connect(lambda: self._browse_line_path(self.srt_output_input))
        srt_grid.addWidget(b, 1, 2)

        srt_grid.addWidget(QLabel("Khoảng dừng (ms):"), 2, 0)
        srt_grid.addWidget(self.srt_gap_spin, 2, 1)
        srt_l.addLayout(srt_grid)

        row = QHBoxLayout()
        scan = QPushButton("Quét Thư Mục")
        scan.clicked.connect(self._voice_scan_srt)
        row.addWidget(scan)

        merge = QPushButton("Ghép Phụ Đề")
        merge.setObjectName("primaryBtn")
        merge.clicked.connect(self.merge_srt_native)
        row.addWidget(merge)

        clear = QPushButton("Xóa Danh Sách")
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
        self.json_output_dir = QLineEdit(str(self.tool_root() / "Voice TXT Tool" / "voices" / "json_20_parts"))

        jgrid.addWidget(QLabel("File kịch bản:"), 0, 0)
        jgrid.addWidget(self.json_script_input, 0, 1)
        b = QPushButton("Chọn File")
        b.clicked.connect(lambda: self._browse_line_path(self.json_script_input))
        jgrid.addWidget(b, 0, 2)

        jgrid.addWidget(QLabel("File phân đoạn JSON:"), 1, 0)
        jgrid.addWidget(self.json_parts_input, 1, 1)
        b = QPushButton("Chọn File")
        b.clicked.connect(lambda: self._browse_line_path(self.json_parts_input))
        jgrid.addWidget(b, 1, 2)

        jgrid.addWidget(QLabel("Thư mục xuất:"), 2, 0)
        jgrid.addWidget(self.json_output_dir, 2, 1)
        b = QPushButton("Chọn Thư Mục")
        b.clicked.connect(lambda: self._browse_line_path(self.json_output_dir, True))
        jgrid.addWidget(b, 2, 2)
        json_l.addLayout(jgrid)

        info = QLabel("Đọc các phân đoạn trong file kịch bản, trích xuất lời thoại và tạo âm thanh theo thứ tự.")
        info.setObjectName("mutedText")
        info.setWordWrap(True)
        json_l.addWidget(info)

        row = QHBoxLayout()
        run = QPushButton("Tạo Giọng Đọc Phân Đoạn")
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
        self.voice_done_label = QLabel("0")
        self.voice_done_label.setStyleSheet("font-size:28px;color:#4ec9b0;font-weight:800;")
        self.voice_total_label = QLabel("0 file")
        self.voice_total_label.setObjectName("mutedText")
        right_l.addWidget(QLabel("TIẾN ĐỘ"))
        right_l.addWidget(self.voice_done_label)
        right_l.addWidget(self.voice_total_label)

        self.voice_log = QPlainTextEdit()
        self.voice_log.setReadOnly(True)
        self.voice_log.setPlaceholderText("Nhật ký tạo giọng đọc và ghép phụ đề hiển thị tại đây...")
        right_l.addWidget(self.voice_log, 1)
        root.addWidget(right, 1)

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

    def _voice_scan_txt(self):
        self.voice_files_list.clear()
        folder = Path(self.voice_txt_dir.text().strip())
        single = Path(self.voice_input_path.text().strip()) if self.voice_input_path.text().strip() else None
        seen = []
        if single and single.is_file():
            seen.append(single)
            self.voice_files_list.addItem(str(single))
        elif folder.is_dir():
            files = sorted(folder.glob("*.txt"), key=lambda x: (int(x.stem) if x.stem.isdigit() else 9999, x.name.lower()))
            for f in files:
                seen.append(f)
                self.voice_files_list.addItem(str(f))
        self.voice_total_label.setText(f"{len(seen)} file")
        self.voice_log.appendPlainText(f"Đã quét được {len(seen)} file TXT")

    def _voice_scan_srt(self):
        self.srt_files_list.clear()
        folder = Path(self.srt_dir_input.text().strip())
        files = sorted(folder.glob("*.srt"), key=lambda x: x.name.lower()) if folder.is_dir() else []
        for f in files:
            self.srt_files_list.addItem(str(f))
        self.voice_log.appendPlainText(f"Đã quét được {len(files)} file SRT")

    def _voice_clear_files(self):
        self.voice_files_list.clear()
        self.voice_done_label.setText("0")
        self.voice_total_label.setText("0 file")

    def _voice_save_provider_config(self):
        tool = self.tool_root() / "Voice TXT Tool" / "tool-config.json"
        cfg = json.loads(tool.read_text(encoding="utf-8")) if tool.exists() else {"providers": {}}
        provider = self.voice_provider_combo.currentText()
        cfg["provider"] = provider
        cfg.setdefault("providers", {})[provider] = {
            "apiKeys": self.provider_api_keys.toPlainText(),
            "voiceId": self.voice_id_input.text().strip() or self.larvoice_id_input.text().strip()
        }
        try:
            tool.parent.mkdir(parents=True, exist_ok=True)
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
        self.voice_log.appendPlainText(f"Đã tạo {self.voice_files_list.count()} file TXT từ kịch bản. Bắt đầu tạo giọng đọc...")
        self.start_native_voice()

    def _run_node_tool(self, cmd, cwd, log_widget):
        try:
            proc = subprocess.Popen(
                cmd, cwd=str(cwd), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace",
                creationflags=(subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            )
            for line in proc.stdout or []:
                log_widget.appendPlainText(line.rstrip())
                QApplication.processEvents()
            proc.wait()
            return proc.returncode == 0
        except Exception as e:
            log_widget.appendPlainText(f"Lỗi thực thi: {e}")
            return False

    def start_native_voice(self):
        if self.voice_files_list.count() == 0:
            self._voice_scan_txt()

        files = [self.voice_files_list.item(i).text() for i in range(self.voice_files_list.count())]
        if not files:
            QMessageBox.information(self, "Trống", "Không có file TXT nào để tạo giọng đọc.")
            return

        out = self.voice_output_dir.text().strip()
        self._voice_save_provider_config()
        tool = self.tool_root() / "Voice TXT Tool"
        Path(out).mkdir(parents=True, exist_ok=True)
        self.voice_done_label.setText("0")
        self.voice_total_label.setText(f"{len(files)} file")

        ok = 0
        for idx, inp in enumerate(files, 1):
            self.voice_log.appendPlainText(f"[{idx}/{len(files)}] Đang tạo giọng đọc: {Path(inp).name}")
            done = self._run_node_tool([
                "node", "server.mjs", "--cli", inp, out,
                self.voice_provider_combo.currentText(),
                str(self.voice_speed_spin.value())
            ], tool, self.voice_log)
            ok += 1 if done else 0
            self.voice_done_label.setText(str(idx))
            QApplication.processEvents()

        self.voice_log.appendPlainText(f"Hoàn tất: {ok}/{len(files)} file thành công")

    def merge_srt_native(self):
        if self.srt_files_list.count():
            files = [Path(self.srt_files_list.item(i).text()) for i in range(self.srt_files_list.count())]
        else:
            folder = Path(self.srt_dir_input.text().strip())
            files = sorted(folder.glob("*.srt"), key=lambda x: x.name.lower()) if folder.exists() else []

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
                lines = block.strip().split("\n")
                if lines and lines[0].strip().isdigit():
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
        self.voice_log.appendPlainText(f"Đã ghép {len(files)} file SRT ({len(blocks)} dòng) -> {out}")
