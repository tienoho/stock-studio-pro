"""
SceneListItem widget for the scenes sidebar.
"""

from PyQt6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QCursor
from ..styles.icons import get_svg_pixmap


class SceneListItem(QFrame):
    """Interactive scene item in the timeline sidebar."""

    clicked = pyqtSignal(dict)

    def __init__(self, scene: dict, is_active: bool = False, parent=None):
        super().__init__(parent)
        self.scene = scene
        self.is_active = is_active
        self.total_items = 0
        self.selected_count = 0

        self.setFixedHeight(58)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(2)

        scene_id = scene.get("id", "?")
        time_start = scene.get("time_start", "00:00:00")
        if "," in time_start:
            time_start = time_start.split(",")[0]

        top_h = QHBoxLayout()
        top_h.setSpacing(6)
        top_h.setContentsMargins(0, 0, 0, 0)

        self.icon_lbl = QLabel()
        self.icon_lbl.setPixmap(get_svg_pixmap("film", "#818cf8", 12))
        top_h.addWidget(self.icon_lbl)

        self.top_label = QLabel(f"Scene #{scene_id}  •  {time_start}")
        self.top_label.setStyleSheet("color: #f8fafc; font-size: 12px; font-weight: 700; background: transparent;")
        top_h.addWidget(self.top_label)
        top_h.addStretch()
        layout.addLayout(top_h)

        self.bottom_label = QLabel("0 media")
        self.bottom_label.setStyleSheet("color: #94a3b8; font-size: 10px; font-weight: 600; background: transparent;")
        layout.addWidget(self.bottom_label)

        self._update_style()

    def _update_style(self):
        from ..styles.theme_manager import ThemeManager
        is_dark = ThemeManager.get_instance().is_dark()

        if self.is_active:
            grad_stop1 = "#4338ca" if is_dark else "#4f46e5"
            grad_stop2 = "#6d28d9" if is_dark else "#6366f1"
            border_color = "#818cf8" if is_dark else "#4338ca"
            accent_left = "#06b6d4" if is_dark else "#0284c7"
            self.setStyleSheet(f"""
                SceneListItem {{
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 {grad_stop1}, stop:1 {grad_stop2});
                    border-radius: 8px;
                    border: 1px solid {border_color};
                    border-left: 4px solid {accent_left};
                }}
            """)
            self.top_label.setStyleSheet("color: #ffffff; font-size: 12px; font-weight: 800; background: transparent;")
            self.bottom_label.setStyleSheet("color: rgba(255,255,255,0.95); font-size: 10px; font-weight: 700; background: transparent;")
            self.icon_lbl.setPixmap(get_svg_pixmap("film", "#ffffff", 12))
        else:
            if is_dark:
                self.setStyleSheet("""
                    SceneListItem {
                        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                            stop:0 #111724, stop:1 #0b0f18);
                        border: 1px solid #1f2b3f;
                        border-radius: 8px;
                    }
                    SceneListItem:hover {
                        background-color: #161e2e;
                        border-color: #38bdf8;
                    }
                """)
                self.top_label.setStyleSheet("color: #f1f5f9; font-size: 12px; font-weight: 700; background: transparent;")
                self.icon_lbl.setPixmap(get_svg_pixmap("film", "#818cf8", 12))
                if self.selected_count > 0:
                    self.bottom_label.setStyleSheet("color: #34d399; font-size: 10px; font-weight: 750; background: transparent;")
                else:
                    self.bottom_label.setStyleSheet("color: #94a3b8; font-size: 10px; background: transparent;")
            else:
                self.setStyleSheet("""
                    SceneListItem {
                        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                            stop:0 #ffffff, stop:1 #f8fafc);
                        border: 1px solid #e2e8f0;
                        border-radius: 8px;
                    }
                    SceneListItem:hover {
                        background-color: #f1f5f9;
                        border-color: #6366f1;
                    }
                """)
                self.top_label.setStyleSheet("color: #0f172a; font-size: 12px; font-weight: 700; background: transparent;")
                self.icon_lbl.setPixmap(get_svg_pixmap("film", "#4f46e5", 12))
                if self.selected_count > 0:
                    self.bottom_label.setStyleSheet("color: #059669; font-size: 10px; font-weight: 750; background: transparent;")
                else:
                    self.bottom_label.setStyleSheet("color: #64748b; font-size: 10px; background: transparent;")

    def set_active(self, active: bool):
        self.is_active = active
        self._update_style()

    def update_stats(self, total: int, selected: int):
        self.total_items = total
        self.selected_count = selected
        if selected > 0:
            self.bottom_label.setText(f"{total} items  •  Đã chọn {selected}")
        else:
            self.bottom_label.setText(f"{total} items")
        self._update_style()

    def mousePressEvent(self, event):
        self.clicked.emit(self.scene)
        super().mousePressEvent(event)
