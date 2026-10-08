"""
Status panel widget for displaying realtime system status, progress, and logs.
"""

import re
from datetime import datetime
from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit
)
from PyQt6.QtCore import Qt
from ..styles.icons import get_svg_pixmap


class StatusPanel(QFrame):
    """Panel hiển thị status realtime phong cách AutoStock Studio."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("statusPanel")
        self.setStyleSheet("""
            #statusPanel {
                background-color: #131926;
                border: 1px solid #1e293b;
                border-radius: 12px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # === Header với state badge ===
        header_h = QHBoxLayout()
        header_h.setSpacing(6)

        mon_icon = QLabel()
        mon_icon.setPixmap(get_svg_pixmap("activity", "#818cf8", 14))
        header_h.addWidget(mon_icon)

        header_label = QLabel("TRẠNG THÁI")
        header_label.setStyleSheet("color: #818cf8; font-size: 11px; font-weight: 800; letter-spacing: 1.2px;")
        header_h.addWidget(header_label)

        header_h.addStretch()

        self.state_badge = QLabel("● SẴN SÀNG")
        self.state_badge.setStyleSheet("""
            background-color: rgba(99, 102, 241, 0.15);
            color: #818cf8;
            border: 1px solid rgba(99, 102, 241, 0.35);
            border-radius: 6px;
            padding: 3px 10px;
            font-size: 10px;
            font-weight: 800;
            letter-spacing: 0.5px;
        """)
        header_h.addWidget(self.state_badge)

        layout.addLayout(header_h)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("background-color: #1e293b; max-height: 1px;")
        layout.addWidget(sep)

        # === Main message ===
        self.main_label = QLabel("Hệ thống sẵn sàng")
        self.main_label.setStyleSheet("color: #f8fafc; font-size: 12px; font-weight: 650; padding: 2px 0;")
        self.main_label.setWordWrap(True)
        layout.addWidget(self.main_label)

        # === Progress text ===
        self.progress_label = QLabel("")
        self.progress_label.setStyleSheet("color: #38bdf8; font-size: 11px; font-family: 'Consolas', monospace; font-weight: 600; padding: 1px 0;")
        self.progress_label.setWordWrap(True)
        layout.addWidget(self.progress_label)

        # === Progress bar ===
        self.progress_bar = QFrame()
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setStyleSheet("""
            QFrame {
                background-color: #0e131d;
                border-radius: 4px;
                border: 1px solid #1e293b;
            }
        """)
        self.progress_fill = QFrame(self.progress_bar)
        self.progress_fill.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #6366f1, stop:0.5 #8b5cf6, stop:1 #06b6d4);
                border-radius: 4px;
            }
        """)
        self.progress_fill.setFixedHeight(8)
        self.progress_fill.setFixedWidth(0)
        layout.addWidget(self.progress_bar)

        # === Counter cards (3 micro cards) ===
        counters_h = QHBoxLayout()
        counters_h.setSpacing(6)

        self.counter_scenes = self._create_counter(
            "SCENES", "0/0", "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #1e293b, stop:1 #1e3a8a)"
        )
        counters_h.addWidget(self.counter_scenes['widget'])

        self.counter_items = self._create_counter(
            "ITEMS", "0", "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #1e293b, stop:1 #4c1d95)"
        )
        counters_h.addWidget(self.counter_items['widget'])

        self.counter_selected = self._create_counter(
            "ĐÃ CHỌN", "0", "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #1e293b, stop:1 #064e3b)"
        )
        counters_h.addWidget(self.counter_selected['widget'])

        layout.addLayout(counters_h)

        # === Activity log header ===
        log_h = QHBoxLayout()
        log_h.setSpacing(6)
        log_icon = QLabel()
        log_icon.setPixmap(get_svg_pixmap("file-text", "#64748b", 12))
        log_h.addWidget(log_icon)
        log_header = QLabel("NHẬT KÝ")
        log_header.setStyleSheet("color: #64748b; font-size: 10px; font-weight: 800; letter-spacing: 1px;")
        log_h.addWidget(log_header)
        log_h.addStretch()
        layout.addLayout(log_h)

        # === Activity log ===
        self.activity_log = QTextEdit()
        self.activity_log.setReadOnly(True)
        self.activity_log.setStyleSheet("""
            QTextEdit {
                background-color: #0c0f17;
                color: #cbd5e1;
                border: 1px solid #1e293b;
                border-radius: 8px;
                padding: 6px;
                font-size: 10px;
                font-family: 'Consolas', 'Cascadia Code', monospace;
            }
        """)
        self.activity_log.setMinimumHeight(120)
        layout.addWidget(self.activity_log, 1)

        # === Cooldown notice ===
        self.cooldown_label = QLabel("")
        self.cooldown_label.setStyleSheet("""
            color: #f87171;
            font-size: 11px;
            font-weight: 750;
            background-color: rgba(239, 68, 68, 0.12);
            border: 1px solid rgba(239, 68, 68, 0.4);
            border-radius: 8px;
            padding: 6px;
        """)
        self.cooldown_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cooldown_label.setVisible(False)
        layout.addWidget(self.cooldown_label)

    def _create_counter(self, label: str, value: str, color: str) -> dict:
        """Tạo 1 counter card nhỏ."""
        widget = QFrame()
        widget.setStyleSheet(f"""
            QFrame {{
                background: {color};
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 8px;
            }}
        """)
        lay = QVBoxLayout(widget)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(1)

        value_lbl = QLabel(value)
        value_lbl.setStyleSheet("color: #ffffff; font-size: 13px; font-weight: 850; background: transparent;")
        value_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(value_lbl)

        text_lbl = QLabel(label)
        text_lbl.setStyleSheet("color: rgba(255,255,255,0.7); font-size: 8px; font-weight: 750; background: transparent; letter-spacing: 0.5px;")
        text_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(text_lbl)

        return {'widget': widget, 'value': value_lbl, 'label': text_lbl}

    def update_counters(self, scenes_done: int = 0, scenes_total: int = 0, items: int = 0, selected: int = 0):
        """Update 3 counter cards."""
        self.counter_scenes['value'].setText(f"{scenes_done}/{scenes_total}")
        self.counter_items['value'].setText(str(items))
        self.counter_selected['value'].setText(str(selected))

    def add_log(self, message: str, level: str = "info"):
        """Append message vào activity log."""
        ts = datetime.now().strftime("%H:%M:%S")
        color_map = {
            "info": "#94a3b8",
            "success": "#34d399",
            "warning": "#fbbf24",
            "error": "#f87171",
        }
        color = color_map.get(level, "#94a3b8")
        html = f'<span style="color: #475569">[{ts}]</span> <span style="color: {color}">{message}</span>'
        self.activity_log.append(html)

        scrollbar = self.activity_log.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

        doc = self.activity_log.document()
        if doc.blockCount() > 200:
            cursor = self.activity_log.textCursor()
            cursor.movePosition(cursor.MoveOperation.Start)
            cursor.select(cursor.SelectionType.LineUnderCursor)
            cursor.removeSelectedText()
            cursor.deleteChar()

    def set_idle(self, message: str = "Sẵn sàng"):
        self._set_state("● SẴN SÀNG", "#818cf8", "rgba(99, 102, 241, 0.15)")
        self.main_label.setText(message)
        self.progress_label.setText("")
        self._set_progress(0)
        self.cooldown_label.setVisible(False)

    def set_searching(self, message: str = ""):
        self._set_state("● ĐANG TÌM", "#a78bfa", "rgba(167, 139, 250, 0.15)")
        self.main_label.setText("Đang tìm media...")
        if message:
            self.progress_label.setText(message)
        self.cooldown_label.setVisible(False)

    def set_downloading(self, message: str = ""):
        self._set_state("● ĐANG TẢI", "#38bdf8", "rgba(56, 189, 248, 0.15)")
        self.main_label.setText("Đang tải file...")
        if message:
            self.progress_label.setText(message)
        self.cooldown_label.setVisible(False)

    def set_done(self, success_count: int, fail_count: int):
        self._set_state("● HOÀN TẤT", "#34d399", "rgba(52, 211, 153, 0.15)")
        self.main_label.setText("Hoàn tất tải!")
        self.progress_label.setText(f"{success_count} OK • {fail_count} lỗi")
        self._set_progress(100)
        self.cooldown_label.setVisible(False)
        self.add_log(f"Hoàn tất: {success_count} OK, {fail_count} lỗi",
                     "success" if fail_count == 0 else "warning")

    def set_stopped(self):
        self._set_state("● ĐÃ DỪNG", "#f87171", "rgba(239, 68, 68, 0.15)")
        self.main_label.setText("Đã dừng")
        self.cooldown_label.setVisible(False)
        self.add_log("Đã dừng", "warning")

    def set_progress(self, current: int, total: int, message: str = ""):
        if total > 0:
            pct = int(current / total * 100)
            self._set_progress(pct)
            self.progress_label.setText(f"{current}/{total} ({pct}%)" + (f" • {message}" if message else ""))

    def set_stats(self, delay: float = None, fail_rate: float = None, blocks: int = None, via_refresh: int = None):
        """Update anti-block stats."""
        parts = []
        if delay is not None:
            arrow = " ↑" if delay > 1.5 else (" ↓" if delay < 0.7 else "")
            parts.append(f"Delay: {delay:.1f}s{arrow}")

        if fail_rate is not None:
            success_pct = (1 - fail_rate) * 100
            parts.append(f"Success: {success_pct:.0f}%")

        if via_refresh is not None and via_refresh > 0:
            parts.append(f"Refreshed: {via_refresh}")

        if blocks is not None and blocks > 0:
            parts.append(f"Blocks: {blocks}")

        if parts:
            self.progress_label.setText(self.progress_label.text() + "\n" + " • ".join(parts))

    def set_cooldown(self, remaining_seconds: int):
        """Show cooldown notice."""
        m = remaining_seconds // 60
        s = remaining_seconds % 60
        self._set_state("● COOLDOWN", "#f87171", "rgba(239, 68, 68, 0.15)")
        self.cooldown_label.setText(f"GIỚI HẠN RATE LIMIT\nChờ {m}:{s:02d} còn lại...")
        self.cooldown_label.setVisible(True)

    def end_cooldown(self):
        self.cooldown_label.setVisible(False)

    def _set_state(self, text: str, color: str, bg_color: str):
        self.state_badge.setText(text)
        self.state_badge.setStyleSheet(f"""
            background-color: {bg_color};
            color: {color};
            border: 1px solid {color};
            border-radius: 6px;
            padding: 3px 10px;
            font-size: 10px;
            font-weight: 800;
            letter-spacing: 0.5px;
        """)

    def _set_progress(self, percent: int):
        percent = max(0, min(100, percent))
        total_width = self.progress_bar.width()
        if total_width <= 0:
            total_width = 200
        fill_width = int(total_width * percent / 100)
        self.progress_fill.setFixedWidth(fill_width)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        try:
            current_text = self.progress_label.text()
            if "%" in current_text:
                m = re.search(r'\((\d+)%\)', current_text)
                if m:
                    self._set_progress(int(m.group(1)))
        except Exception:
            pass
