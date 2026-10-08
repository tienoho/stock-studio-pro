"""
Auto Mode tab widget for one-click automated execution pipeline.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QComboBox, QSpinBox, QCheckBox, QPushButton, QPlainTextEdit
)
from PyQt6.QtCore import pyqtSignal


class AutoTab(QWidget):
    """Auto pipeline tab to search, random pick, and trigger download/voice."""

    runAutoRequested = pyqtSignal(str, int, bool)

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        title = QLabel("Quy Trình Tự Động")
        title.setObjectName("heroTitle")
        layout.addWidget(title)

        hint = QLabel("Tự động tìm kiếm media, chọn ngẫu nhiên theo số lượng đặt trước, tải về máy và chuyển tiếp sang tạo giọng đọc.")
        hint.setObjectName("mutedText")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        row = QHBoxLayout()
        self.auto_media_combo = QComboBox()
        self.auto_media_combo.addItems(["Video + ảnh", "Chỉ video", "Chỉ ảnh"])
        row.addWidget(QLabel("Định dạng media:"))
        row.addWidget(self.auto_media_combo)

        self.auto_pick_spin = QSpinBox()
        self.auto_pick_spin.setRange(1, 20)
        self.auto_pick_spin.setValue(2)
        row.addWidget(QLabel("Số lượng mỗi cảnh:"))
        row.addWidget(self.auto_pick_spin)

        self.auto_voice_check = QCheckBox("Tự chuyển sang tạo giọng đọc sau khi tải")
        row.addWidget(self.auto_voice_check)
        row.addStretch()
        layout.addLayout(row)

        btn = QPushButton("Bắt Đầu Chạy Tự Động")
        btn.setObjectName("primaryBtn")
        btn.setFixedHeight(40)
        btn.clicked.connect(self._on_run_clicked)
        layout.addWidget(btn)

        self.auto_log = QPlainTextEdit()
        self.auto_log.setReadOnly(True)
        layout.addWidget(self.auto_log, 1)

    def _on_run_clicked(self):
        mode = self.auto_media_combo.currentText()
        count = self.auto_pick_spin.value()
        then_voice = self.auto_voice_check.isChecked()
        self.auto_log.appendPlainText("Bắt đầu tìm kiếm media. Hệ thống sẽ tự động chọn và tải về sau khi tìm xong.")
        self.runAutoRequested.emit(mode, count, then_voice)
