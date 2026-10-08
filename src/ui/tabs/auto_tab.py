"""
Auto Mode tab widget for one-click automated execution pipeline.
Streamlined UI with visual status badges, pipeline checklist, and real-time logs.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QComboBox, QSpinBox, QCheckBox, QPushButton, QPlainTextEdit, QFrame
)
from PyQt6.QtCore import pyqtSignal
from ..styles.icons import get_svg_icon, get_svg_pixmap


class AutoTab(QWidget):
    """Auto pipeline tab to search, random pick, and trigger download/voice/cut."""

    runAutoRequested = pyqtSignal(str, int, bool)

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # Header
        title_h = QHBoxLayout()
        title_h.setSpacing(8)
        self.title_icon = QLabel()
        self.title_icon.setPixmap(get_svg_pixmap("zap", "#e3b341", 20))
        title_h.addWidget(self.title_icon)

        title = QLabel("Quy Trình Tự Động Một Chạm (1-Click Pipeline)")
        title.setObjectName("heroTitle")
        title_h.addWidget(title)
        title_h.addStretch()
        layout.addLayout(title_h)

        hint = QLabel(
            "Tự động chạy liên hoàn các bước: Tìm media theo từng cảnh -> Chọn ngẫu nhiên media tốt nhất -> Tải về máy -> Chuyển tiếp sang tạo giọng đọc AI."
        )
        hint.setObjectName("mutedText")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        # Visual Pipeline Overview Card
        steps_card = QFrame()
        steps_card.setObjectName("toolCard")
        steps_layout = QHBoxLayout(steps_card)
        steps_layout.setContentsMargins(14, 10, 14, 10)
        steps_layout.setSpacing(8)

        steps_def = [
            ("1. Tìm Media", "#58a6ff"),
            ("→", "#484f58"),
            ("2. Chọn Ngẫu Nhiên", "#bc8cff"),
            ("→", "#484f58"),
            ("3. Tải Về Máy", "#34d399"),
            ("→", "#484f58"),
            ("4. Voice AI / Khớp Cảnh", "#e3b341"),
        ]
        for text, color in steps_def:
            lbl = QLabel(text)
            lbl.setStyleSheet(f"color: {color}; font-weight: 700; font-size: 11px;")
            steps_layout.addWidget(lbl)
        steps_layout.addStretch()
        layout.addWidget(steps_card)

        # Config Card
        cfg_card = QFrame()
        cfg_card.setObjectName("toolCard")
        cfg_layout = QVBoxLayout(cfg_card)
        cfg_layout.setSpacing(10)

        row = QHBoxLayout()
        row.setSpacing(14)

        row.addWidget(QLabel("Định dạng media:"))
        self.auto_media_combo = QComboBox()
        self.auto_media_combo.addItems(["Video + ảnh", "Chỉ video", "Chỉ ảnh"])
        row.addWidget(self.auto_media_combo)

        row.addWidget(QLabel("Số lượng mỗi cảnh:"))
        self.auto_pick_spin = QSpinBox()
        self.auto_pick_spin.setRange(1, 20)
        self.auto_pick_spin.setValue(2)
        row.addWidget(self.auto_pick_spin)

        self.auto_voice_check = QCheckBox("Tự chuyển sang tạo giọng đọc AI sau khi tải xong")
        self.auto_voice_check.setChecked(True)
        row.addWidget(self.auto_voice_check)

        row.addStretch()
        cfg_layout.addLayout(row)

        action_row = QHBoxLayout()
        self.btn_run = QPushButton("Bắt Đầu Chạy Tự Động")
        self.btn_run.setObjectName("primaryBtn")
        self.btn_run.setIcon(get_svg_icon("play", "#ffffff", 14))
        self.btn_run.setFixedHeight(38)
        self.btn_run.clicked.connect(self._on_run_clicked)
        action_row.addWidget(self.btn_run)

        self.btn_clear_log = QPushButton("Xóa Nhật Ký")
        self.btn_clear_log.setIcon(get_svg_icon("trash", "#8b949e", 14))
        self.btn_clear_log.clicked.connect(lambda: self.auto_log.clear())
        action_row.addWidget(self.btn_clear_log)

        action_row.addStretch()
        cfg_layout.addLayout(action_row)

        layout.addWidget(cfg_card)

        # Log Panel
        self.auto_log = QPlainTextEdit()
        self.auto_log.setReadOnly(True)
        self.auto_log.setPlaceholderText("Nhật ký quy trình tự động sẽ xuất hiện tại đây...")
        layout.addWidget(self.auto_log, 1)

    def _on_run_clicked(self):
        mode = self.auto_media_combo.currentText()
        count = self.auto_pick_spin.value()
        then_voice = self.auto_voice_check.isChecked()
        self.auto_log.appendPlainText("=" * 60)
        self.auto_log.appendPlainText("KHỞI ĐỘNG QUY TRÌNH TỰ ĐỘNG:")
        self.auto_log.appendPlainText(f"- Chế độ: {mode}")
        self.auto_log.appendPlainText(f"- Chọn ngẫu nhiên: {count} media / cảnh")
        self.auto_log.appendPlainText(f"- Tự chuyển Voice AI: {'Bật' if then_voice else 'Tắt'}")
        self.auto_log.appendPlainText("=" * 60)
        self.runAutoRequested.emit(mode, count, then_voice)
