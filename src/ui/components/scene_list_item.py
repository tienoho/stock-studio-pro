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
        if self.is_active:
            self.setStyleSheet("""
                SceneListItem {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 #4f46e5, stop:1 #7c3aed);
                    border-radius: 8px;
                    border-left: 4px solid #38bdf8;
                }
            """)
            self.top_label.setStyleSheet("color: #ffffff; font-size: 12px; font-weight: 800; background: transparent;")
            self.bottom_label.setStyleSheet("color: rgba(255,255,255,0.9); font-size: 10px; font-weight: 600; background: transparent;")
            self.icon_lbl.setPixmap(get_svg_pixmap("film", "#ffffff", 12))
        else:
            self.setStyleSheet("""
                SceneListItem {
                    background-color: #131926;
                    border: 1px solid #1e293b;
                    border-radius: 8px;
                }
                SceneListItem:hover {
                    background-color: #1a2233;
                    border-color: #3b4d6e;
                }
            """)
            self.top_label.setStyleSheet("color: #f1f5f9; font-size: 12px; font-weight: 700; background: transparent;")
            self.icon_lbl.setPixmap(get_svg_pixmap("film", "#818cf8", 12))
            if self.selected_count > 0:
                self.bottom_label.setStyleSheet("color: #34d399; font-size: 10px; font-weight: 750; background: transparent;")
            else:
                self.bottom_label.setStyleSheet("color: #94a3b8; font-size: 10px; background: transparent;")

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
