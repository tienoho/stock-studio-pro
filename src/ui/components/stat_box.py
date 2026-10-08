"""
StatBox and Badge visual components.
"""

from PyQt6.QtWidgets import QFrame, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt


class StatBox(QFrame):
    """Studio sleek glassmorphic stat card with glowing value and refined label."""

    def __init__(self, value, label: str, color: str = None, parent=None):
        super().__init__(parent)
        self.setObjectName("statBox")

        accent = "#38bdf8"
        if color:
            color_lower = str(color).lower()
            if "#1e3a8a" in color_lower or "#1d4ed8" in color_lower or "blue" in color_lower:
                accent = "#38bdf8"
            elif "#4c1d95" in color_lower or "#6d28d9" in color_lower or "purple" in color_lower:
                accent = "#c084fc"
            elif "#831843" in color_lower or "#be123c" in color_lower or "red" in color_lower or "rose" in color_lower:
                accent = "#fb7185"
            elif "#064e3b" in color_lower or "#047857" in color_lower or "green" in color_lower or "emerald" in color_lower:
                accent = "#34d399"
            elif color.startswith("#"):
                accent = color
        self.accent_color = accent

        self.setStyleSheet(f"""
            QFrame#statBox {{
                background-color: #0c121e;
                border-radius: 8px;
                border: 1px solid #1a2538;
                border-top: 2px solid {accent};
            }}
        """)
        self.setFixedHeight(46)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(1)

        self.value_label = QLabel(str(value))
        self.value_label.setObjectName("statValue")
        self.value_label.setStyleSheet(f"color: {accent}; font-size: 16px; font-weight: 900; background: transparent;")
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.value_label)

        self.title_label = QLabel(label.upper())
        self.title_label.setObjectName("statTitle")
        self.title_label.setStyleSheet("color: #94a3b8; font-size: 9px; font-weight: 700; letter-spacing: 0.5px; background: transparent;")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title_label)

    def set_value(self, val):
        self.value_label.setText(str(val))


class Badge(QLabel):
    """Pill badge showing status or count."""

    def __init__(self, text: str, bg_color: str = "#182234", text_color: str = "#818cf8", parent=None):
        super().__init__(text, parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(
            f"background-color: {bg_color}; color: {text_color}; "
            f"border-radius: 6px; font-size: 10px; font-weight: 800; padding: 2px 8px; "
            f"border: 1px solid rgba(255, 255, 255, 0.1);"
        )
