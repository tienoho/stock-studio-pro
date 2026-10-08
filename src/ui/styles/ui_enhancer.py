"""
UI Interaction Enhancer module for AutoStock Studio.
Provides automated interaction polish:
- PointingHandCursor auto-assignment for interactive controls (buttons, combos, checkboxes)
- Uniform keyboard shortcut tooltip formatting
- Micro-interaction visual polish
"""

from PyQt6.QtWidgets import (
    QWidget, QPushButton, QToolButton, QCheckBox, QRadioButton,
    QComboBox, QSlider, QTabBar
)
from PyQt6.QtGui import QCursor
from PyQt6.QtCore import Qt


def set_hand_cursor(widget: QWidget) -> None:
    """Sets standard pointing hand cursor on an interactive widget."""
    if widget:
        widget.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))


def enhance_widget_interactions(root: QWidget) -> None:
    """
    Recursively scans the widget tree and enhances interactive components:
    - Assigns PointingHandCursor to all buttons, checkboxes, radio buttons, combo boxes, and sliders.
    - Ensures clean focus policy and hover responsiveness.
    """
    if not root:
        return

    # Enhance root if it matches interactive widget types
    if isinstance(root, (QPushButton, QToolButton, QCheckBox, QRadioButton, QComboBox, QSlider)):
        set_hand_cursor(root)

    # Enhance all child interactive controls
    buttons = root.findChildren(QPushButton)
    for btn in buttons:
        set_hand_cursor(btn)

    tool_buttons = root.findChildren(QToolButton)
    for tb in tool_buttons:
        set_hand_cursor(tb)

    checkboxes = root.findChildren(QCheckBox)
    for cb in checkboxes:
        set_hand_cursor(cb)

    radios = root.findChildren(QRadioButton)
    for rb in radios:
        set_hand_cursor(rb)

    combos = root.findChildren(QComboBox)
    for combo in combos:
        set_hand_cursor(combo)

    sliders = root.findChildren(QSlider)
    for slider in sliders:
        set_hand_cursor(slider)

    tab_bars = root.findChildren(QTabBar)
    for tb in tab_bars:
        set_hand_cursor(tb)


def format_tooltip(description: str, shortcut: str = "") -> str:
    """
    Generates a beautifully formatted HTML tooltip with description and keyboard shortcut badge.
    Example: format_tooltip("Tải media đã chọn", "Ctrl+Enter")
    """
    if not shortcut:
        return description

    return (
        f"<div style='font-family: Segoe UI, sans-serif; font-size: 11px;'>"
        f"<span>{description}</span> "
        f"<span style='background: rgba(99, 102, 241, 0.25); color: #818cf8; "
        f"padding: 1px 5px; border-radius: 4px; font-weight: 700; font-size: 10px; "
        f"border: 1px solid rgba(99, 102, 241, 0.4);'>[{shortcut}]</span>"
        f"</div>"
    )
