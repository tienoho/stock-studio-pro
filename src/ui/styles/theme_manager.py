"""
Theme Manager Service for AutoStock Studio.
Provides dynamic Dark / Light mode switching, persistence, and reactive theme notifications.
"""

from typing import Optional
from pathlib import Path
import sys
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QApplication


class ThemeManager(QObject):
    """Central singleton service for application theme management."""

    themeChanged = pyqtSignal(str)
    _instance: Optional["ThemeManager"] = None

    THEME_DARK = "dark"
    THEME_LIGHT = "light"

    def __init__(self, default_theme: str = "dark"):
        super().__init__()
        self._current_theme = default_theme

    @classmethod
    def get_instance(cls, default_theme: str = "dark") -> "ThemeManager":
        if cls._instance is None:
            cls._instance = cls(default_theme=default_theme)
        return cls._instance

    @property
    def current_theme(self) -> str:
        return self._current_theme

    @property
    def theme(self) -> str:
        return self._current_theme

    def is_dark(self) -> bool:
        return self._current_theme == self.THEME_DARK

    def is_light(self) -> bool:
        return self._current_theme == self.THEME_LIGHT

    def set_theme(self, theme_name: str) -> None:
        clean = (theme_name or "").lower().strip()
        if clean not in (self.THEME_DARK, self.THEME_LIGHT):
            clean = self.THEME_DARK
        if clean != self._current_theme:
            self._current_theme = clean
            self.apply_theme()
            self.themeChanged.emit(self._current_theme)

    def toggle_theme(self) -> str:
        new_theme = self.THEME_LIGHT if self.is_dark() else self.THEME_DARK
        self.set_theme(new_theme)
        return new_theme

    def get_stylesheet(self, theme_name: Optional[str] = None) -> str:
        theme = (theme_name or self._current_theme).lower()
        filename = "theme_light.qss" if theme == self.THEME_LIGHT else "theme.qss"

        qss_path = Path(__file__).parent / filename
        if not qss_path.exists() and hasattr(sys, "_MEIPASS"):
            qss_path = Path(sys._MEIPASS) / "src" / "ui" / "styles" / filename

        if qss_path.exists():
            try:
                return qss_path.read_text(encoding="utf-8")
            except Exception as e:
                print(f"[ThemeManager] Error reading {filename}: {e}")
        return ""

    def apply_theme(self) -> None:
        """Applies the current theme stylesheet directly to the active QApplication."""
        app = QApplication.instance()
        if app:
            qss = self.get_stylesheet()
            app.setStyleSheet(qss)
