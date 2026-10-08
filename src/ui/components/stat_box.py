"""
StatBox and Badge visual components.
"""

from PyQt6.QtWidgets import QFrame, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt


class StatBox(QFrame):
    """Studio glassmorphic stat box with glowing value and sleek label."""

    def __init__(self, value, label: str, color: str = None, parent=None):
        super().__init__(parent)
        self.setObjectName("statBox")

        if color:
            self.setStyleSheet(f"""
                QFrame#statBox {{
                    background: {color};
                    border-radius: 12px;
                    border: 1px solid rgba(255, 255, 255, 0.12);
                }}
            """)
        self.setMinimumHeight(64)
        self.setMaximumHeight(74)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(1)

        self.value_label = QLabel(str(value))
        self.value_label.setObjectName("statValue")
        self.value_label.setStyleSheet("color: #ffffff; font-size: 20px; font-weight: 850; background: transparent;")
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.value_label)

        self.title_label = QLabel(label.upper())
        self.title_label.setObjectName("statTitle")
        self.title_label.setStyleSheet("color: rgba(255, 255, 255, 0.7); font-size: 9px; font-weight: 800; letter-spacing: 0.8px; background: transparent;")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title_label)

    def set_value(self, val):
        self.value_label.setText(str(val))


class Badge(QLabel):
    """Pill badge showing status or count."""

    def __init__(self, text: str, bg_color: str = "#222d42", text_color: str = "#818cf8", parent=None):
        super().__init__(text, parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(
            f"background-color: {bg_color}; color: {text_color}; "
            f"border-radius: 8px; font-size: 10px; font-weight: 800; padding: 2px 7px;"
        )
