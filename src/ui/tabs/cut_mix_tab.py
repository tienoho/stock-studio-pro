"""
Cut & Mix Studio tab widget for automated FFmpeg scene video editing.
"""

from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QDoubleSpinBox, QSpinBox, QPlainTextEdit, QFileDialog, QMessageBox
)
from PyQt6.QtCore import pyqtSignal
from ..workers.video_cut_worker import VideoCutMergeWorker
from ..styles.icons import get_svg_icon, get_svg_pixmap
from ...core.i18n import t


class CutMixTab(QWidget):
    """Studio tab for cutting scene clips and shuffling into final scene videos."""

    finished = pyqtSignal(bool, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.worker = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)

        title_h = QHBoxLayout()
        title_h.setSpacing(8)
        self.title_icon = QLabel()
        self.title_icon.setPixmap(get_svg_pixmap("scissors", "#6366f1", 20))
        title_h.addWidget(self.title_icon)

        self.title_lbl = QLabel(t("cut_mix.title"))
        self.title_lbl.setObjectName("heroTitle")
        title_h.addWidget(self.title_lbl)
        title_h.addStretch()
        layout.addLayout(title_h)

        self.hint = QLabel(
            "Chọn thư mục chứa các cảnh (cảnh 1, 2, 3...). Công cụ sẽ tự động cắt ghép video cho từng cảnh."
        )
        self.hint.setObjectName("mutedText")
        self.hint.setWordWrap(True)
        layout.addWidget(self.hint)

        # Main Settings Card
        cfg_card = QFrame()
        cfg_card.setObjectName("toolCard")
        cfg_layout = QVBoxLayout(cfg_card)
        cfg_layout.setContentsMargins(16, 14, 16, 14)
        cfg_layout.setSpacing(12)

        # Section 1: Folder Selection
        sec1_lbl = QLabel("THƯ MỤC CẢNH NGUỒN")
        sec1_lbl.setObjectName("sectionHeader")
        cfg_layout.addWidget(sec1_lbl)

        folder_h = QHBoxLayout()
        folder_h.setSpacing(8)
        self.cut_folder_input = QLineEdit()
        self.cut_folder_input.setFixedHeight(34)
        self.cut_folder_input.setPlaceholderText("Chọn thư mục tổng hoặc thư mục cảnh...")
        folder_h.addWidget(self.cut_folder_input, 1)

        self.btn_browse = QPushButton(t("cut_mix.select_folder"))
        self.btn_browse.setIcon(get_svg_icon("folder", "#ffffff", 14))
        self.btn_browse.setFixedHeight(34)
        self.btn_browse.clicked.connect(self._browse_folder)
        folder_h.addWidget(self.btn_browse)
        cfg_layout.addLayout(folder_h)

        # Section 2: Parameters
        sec2_lbl = QLabel("THAM SỐ CẮT & GHÉP")
        sec2_lbl.setObjectName("sectionHeader")
        cfg_layout.addWidget(sec2_lbl)

        opts_h = QHBoxLayout()
        opts_h.setSpacing(14)

        lbl_sec_box = QHBoxLayout()
        lbl_sec_box.setSpacing(6)
        self.lbl_cut_sec = QLabel("Cắt mỗi (giây):")
        lbl_sec_box.addWidget(self.lbl_cut_sec)
        self.cut_seconds_spin = QDoubleSpinBox()
        self.cut_seconds_spin.setFixedHeight(32)
        self.cut_seconds_spin.setRange(0.2, 60.0)
        self.cut_seconds_spin.setSingleStep(0.5)
        self.cut_seconds_spin.setValue(1.0)
        self.cut_seconds_spin.setDecimals(1)
        lbl_sec_box.addWidget(self.cut_seconds_spin)
        opts_h.addLayout(lbl_sec_box)

        lbl_cnt_box = QHBoxLayout()
        lbl_cnt_box.setSpacing(6)
        self.lbl_final_count = QLabel("Số video xuất:")
        lbl_cnt_box.addWidget(self.lbl_final_count)
        self.final_count_spin = QSpinBox()
        self.final_count_spin.setFixedHeight(32)
        self.final_count_spin.setRange(1, 50)
        self.final_count_spin.setValue(1)
        lbl_cnt_box.addWidget(self.final_count_spin)
        opts_h.addLayout(lbl_cnt_box)

        lbl_clip_box = QHBoxLayout()
        lbl_clip_box.setSpacing(6)
        self.lbl_max_clips = QLabel("Clip tối đa (0 = tất cả):")
        lbl_clip_box.addWidget(self.lbl_max_clips)
        self.max_clips_spin = QSpinBox()
        self.max_clips_spin.setFixedHeight(32)
        self.max_clips_spin.setRange(0, 9999)
        self.max_clips_spin.setValue(0)
        lbl_clip_box.addWidget(self.max_clips_spin)
        opts_h.addLayout(lbl_clip_box)

        opts_h.addStretch()
        cfg_layout.addLayout(opts_h)

        # Action Buttons Row
        btn_h = QHBoxLayout()
        btn_h.setSpacing(10)
        self.btn_start = QPushButton(t("cut_mix.start_btn"))
        self.btn_start.setIcon(get_svg_icon("scissors", "#ffffff", 14))
        self.btn_start.setObjectName("primaryBtn")
        self.btn_start.setFixedHeight(36)
        self.btn_start.clicked.connect(self.start_cut_merge)
        btn_h.addWidget(self.btn_start)

        self.btn_stop = QPushButton(t("common.stop"))
        self.btn_stop.setIcon(get_svg_icon("stop", "#ffffff", 14))
        self.btn_stop.setObjectName("dangerBtn")
        self.btn_stop.setFixedHeight(36)
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.stop_cut_merge)
        btn_h.addWidget(self.btn_stop)

        btn_h.addStretch()
        cfg_layout.addLayout(btn_h)

        layout.addWidget(cfg_card)

        # Process Log Box
        log_header = QLabel("NHẬT KÝ XỬ LÝ (PROCESSING LOG)")
        log_header.setObjectName("sectionHeader")
        layout.addWidget(log_header)

        self.cut_log = QPlainTextEdit()
        self.cut_log.setReadOnly(True)
        self.cut_log.setPlaceholderText("Nhật ký xử lý hiển thị tại đây...")
        layout.addWidget(self.cut_log, 1)

    def _browse_folder(self):
        path = QFileDialog.getExistingDirectory(self, "Chọn folder tổng chứa 1, 2, 3... hoặc 1 folder cảnh")
        if path:
            self.cut_folder_input.setText(path)

    def set_folder(self, folder_path: str):
        self.cut_folder_input.setText(str(folder_path))

    def set_config(self, folder: str = "", segment_seconds: float = 1.0, final_count: int = 1, max_clips: int = 0):
        if folder:
            self.cut_folder_input.setText(str(folder))
        self.cut_seconds_spin.setValue(float(segment_seconds))
        self.final_count_spin.setValue(int(final_count))
        self.max_clips_spin.setValue(int(max_clips))

    def start_cut_merge(self):
        folder = self.cut_folder_input.text().strip()
        if not folder:
            QMessageBox.information(self, "Chưa chọn folder", "Vui lòng chọn folder tổng hoặc folder cảnh trước.")
            return

        if self.worker and self.worker.isRunning():
            QMessageBox.information(self, "Đang chạy", "Tiến trình cắt ghép video đang chạy.")
            return

        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.cut_log.appendPlainText("=" * 60)
        self.cut_log.appendPlainText(f"Bắt đầu cắt ghép: {folder}")

        self.worker = VideoCutMergeWorker(
            folder=folder,
            segment_seconds=self.cut_seconds_spin.value(),
            final_count=self.final_count_spin.value(),
            max_clips_per_final=self.max_clips_spin.value(),
        )
        self.worker.progress.connect(self._on_log)
        self.worker.finished_signal.connect(self._on_finished)
        self.worker.start()

    def stop_cut_merge(self):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.cut_log.appendPlainText("Đang dừng tiến trình...")

    def _on_log(self, msg: str):
        self.cut_log.appendPlainText(msg)

    def _on_finished(self, success: bool, message: str):
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        status = "[SUCCESS]" if success else "[ERROR]"
        self.cut_log.appendPlainText(f"{status} {message}")
        self.finished.emit(success, message)

    def retranslate_ui(self):
        """Update texts upon language switch."""
        self.title_lbl.setText(t("cut_mix.title"))
        self.btn_browse.setText(t("cut_mix.select_folder"))
        self.btn_start.setText(t("cut_mix.start_btn"))
        self.btn_stop.setText(t("common.stop"))

    _start_cut_merge = start_cut_merge
