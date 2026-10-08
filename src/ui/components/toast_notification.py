"""
ToastNotification component for non-intrusive, micro-interaction feedback.
"""

from typing import Optional
from PyQt6.QtWidgets import QWidget, QFrame, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QGraphicsOpacityEffect
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QPoint
from ..styles.icons import get_svg_pixmap, get_svg_icon


class ToastNotification(QFrame):
    """Floating glassmorphic toast notification."""

    _active_toasts = []

    def __init__(
        self,
        parent: QWidget,
        message: str,
        title: Optional[str] = None,
        toast_type: str = "info",
        duration_ms: int = 3200
    ):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.SubWindow | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        colors = {
            "success": ("#10b981", "#064e3b", "check"),
            "error": ("#ef4444", "#7f1d1d", "x"),
            "warning": ("#f59e0b", "#78350f", "alert-triangle"),
            "info": ("#38bdf8", "#0c4a6e", "info"),
        }
        accent, bg_tint, icon_name = colors.get(toast_type, colors["info"])

        self.setStyleSheet(f"""
            QFrame {{
                background-color: rgba(15, 23, 42, 0.95);
                border: 1px solid {accent};
                border-radius: 10px;
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)

        # Icon
        icon_lbl = QLabel()
        icon_lbl.setPixmap(get_svg_pixmap(icon_name, accent, 18))
        layout.addWidget(icon_lbl)

        # Text column
        text_v = QVBoxLayout()
        text_v.setSpacing(2)
        text_v.setContentsMargins(0, 0, 0, 0)

        if title:
            self.title_lbl = QLabel(title)
            self.title_lbl.setStyleSheet(f"color: {accent}; font-size: 12px; font-weight: 800; background: transparent; border: none;")
            text_v.addWidget(self.title_lbl)
        else:
            self.title_lbl = None

        self.msg_lbl = QLabel(message)
        self.msg_lbl.setStyleSheet("color: #f1f5f9; font-size: 11px; font-weight: 600; background: transparent; border: none;")
        self.msg_lbl.setWordWrap(True)
        text_v.addWidget(self.msg_lbl)
        layout.addLayout(text_v, 1)

        # Close button
        btn_close = QPushButton()
        btn_close.setIcon(get_svg_icon("x", "#94a3b8", 12))
        btn_close.setFixedSize(20, 20)
        btn_close.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.1);
            }
        """)
        btn_close.clicked.connect(self.close_toast)
        layout.addWidget(btn_close)

        self.adjustSize()
        self.setFixedWidth(max(280, min(420, self.sizeHint().width())))

        # Positioning at bottom-right
        self._reposition()

        # Fade in animation
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        self.anim = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.anim.setDuration(220)
        self.anim.setStartValue(0.0)
        self.anim.setEndValue(1.0)
        self.anim.start()

        # Auto close timer
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.close_toast)
        self.timer.start(duration_ms)

        ToastNotification._active_toasts.append(self)
        self.show()

    def _reposition(self):
        if not self.parent():
            return
        parent_rect = self.parent().rect()
        margin_x = 24
        margin_y = 36

        # Calculate offset if multiple toasts are visible
        idx = ToastNotification._active_toasts.index(self) if self in ToastNotification._active_toasts else len(ToastNotification._active_toasts)
        offset_y = idx * (self.height() + 8)

        x = parent_rect.width() - self.width() - margin_x
        y = parent_rect.height() - self.height() - margin_y - offset_y
        self.move(max(10, x), max(10, y))

    def close_toast(self):
        if hasattr(self, "_closing") and self._closing:
            return
        self._closing = True
        self.anim_out = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.anim_out.setDuration(200)
        self.anim_out.setStartValue(1.0)
        self.anim_out.setEndValue(0.0)
        self.anim_out.finished.connect(self._destroy)
        self.anim_out.start()

    def _destroy(self):
        if self in ToastNotification._active_toasts:
            ToastNotification._active_toasts.remove(self)
        self.deleteLater()

    @classmethod
    def show_toast(
        cls,
        parent: QWidget,
        message: str,
        toast_type: str = "info",
        duration_ms: int = 3200,
        title: Optional[str] = None
    ) -> "ToastNotification":
        """Convenience factory method to show toast notification."""
        valid_types = {"success", "error", "warning", "info"}
        if toast_type not in valid_types and title is None:
            title = toast_type
            toast_type = "info"
        return cls(parent, message, title=title, toast_type=toast_type, duration_ms=duration_ms)
