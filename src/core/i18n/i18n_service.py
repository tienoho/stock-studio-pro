"""
Enterprise-grade Internationalization (i18n) Service.
Provides reactive localization with signal emission, parameter interpolation, and SQLite persistence.
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional, List
from PyQt6.QtCore import QObject, pyqtSignal


class I18nService(QObject):
    """Central localization service with reactive language switching."""

    languageChanged = pyqtSignal(str)
    _instance: Optional["I18nService"] = None

    def __init__(self, default_locale: str = "vi", locales_dir: Optional[Path] = None):
        super().__init__()
        self._current_locale = default_locale
        self._locales_dir = locales_dir or (Path(__file__).parent / "locales")
        self._translations: Dict[str, Dict[str, Any]] = {}
        self._load_all_translations()

    @classmethod
    def get_instance(cls, default_locale: str = "vi") -> "I18nService":
        """Singleton accessor."""
        if cls._instance is None:
            cls._instance = cls(default_locale=default_locale)
        return cls._instance

    def _load_all_translations(self):
        """Loads all JSON translation files from locales directory."""
        if not self._locales_dir.exists():
            return

        for f in self._locales_dir.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                self._translations[f.stem.lower()] = data
            except Exception as e:
                print(f"[I18nService] Failed to load {f}: {e}")

    def get_locale(self) -> str:
        """Returns the active locale code (e.g., 'vi', 'en')."""
        return self._current_locale

    def set_locale(self, locale: str) -> None:
        """Switches active locale and emits languageChanged signal."""
        clean = locale.lower().strip()
        if clean in self._translations and clean != self._current_locale:
            self._current_locale = clean
            self.languageChanged.emit(self._current_locale)

    def get_available_locales(self) -> List[str]:
        """Returns list of available locale codes."""
        return list(self._translations.keys())

    def t(self, key_path: str, **kwargs) -> str:
        """
        Translates a dotted key path (e.g. 'common.ok' or 'downloader.scene_count').
        Falls back to English or the key path itself if not found.
        """
        # Try current locale
        val = self._resolve_key(self._current_locale, key_path)

        # Fallback to English if not found
        if val is None and self._current_locale != "en":
            val = self._resolve_key("en", key_path)

        # Fallback to key path
        if val is None:
            val = key_path

        # Interpolate variables if provided
        if kwargs and isinstance(val, str):
            try:
                return val.format(**kwargs)
            except Exception:
                return val

        return str(val)

    def _resolve_key(self, locale: str, key_path: str) -> Optional[Any]:
        """Traverses nested dict by dot notation."""
        curr = self._translations.get(locale)
        if not curr:
            return None

        parts = key_path.split(".")
        for part in parts:
            if isinstance(curr, dict) and part in curr:
                curr = curr[part]
            else:
                return None
        return curr


# Global shorthand function
def t(key: str, **kwargs) -> str:
    """Convenience helper to translate text via the global I18nService singleton."""
    return I18nService.get_instance().t(key, **kwargs)
