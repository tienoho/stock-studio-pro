"""
Color tokens and UI theme styling.
"""

import sys
from pathlib import Path

# Color palettes
COLOR_BG_DARK = "#0a0d14"
COLOR_BG_CARD = "#131926"
COLOR_BORDER = "#1e293b"
COLOR_ACCENT = "#6366f1"
COLOR_TEAL = "#4ec9b0"
COLOR_GOLD = "#f4d35e"
COLOR_TEXT_PRIMARY = "#f1f5f9"
COLOR_TEXT_MUTED = "#94a3b8"

STAT_COLOR_BLUE = "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #1e3a8a, stop:1 #1d4ed8)"
STAT_COLOR_PURPLE = "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #4c1d95, stop:1 #6d28d9)"
STAT_COLOR_RED = "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #831843, stop:1 #be123c)"
STAT_COLOR_GREEN = "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #064e3b, stop:1 #047857)"


def load_stylesheet() -> str:
    """Load QSS stylesheet from disk with PyInstaller bundle support."""
    qss_path = Path(__file__).parent / "theme.qss"
    if not qss_path.exists() and hasattr(sys, "_MEIPASS"):
        qss_path = Path(sys._MEIPASS) / "src" / "ui" / "styles" / "theme.qss"
    if qss_path.exists():
        try:
            return qss_path.read_text(encoding="utf-8")
        except Exception:
            pass
    return ""
