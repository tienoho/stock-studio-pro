"""
Unit tests for enterprise i18n translation service and vector SVG icon engine.
"""

import sys
import unittest
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon, QPixmap

# Ensure QApplication exists for QPixmap / QIcon
app = QApplication.instance()
if app is None:
    app = QApplication(sys.argv)

from src.core.i18n.i18n_service import I18nService, t
from src.ui.styles.icons import get_svg_icon, get_svg_pixmap, get_icon_names


class TestI18nService(unittest.TestCase):
    """Test suite for I18nService and reactive locale switching."""

    def setUp(self):
        self.i18n = I18nService.get_instance(default_locale="vi")
        self.i18n.set_locale("vi")

    def test_available_locales(self):
        locales = self.i18n.get_available_locales()
        self.assertIn("vi", locales)
        self.assertIn("en", locales)

    def test_vietnamese_translations(self):
        self.i18n.set_locale("vi")
        self.assertEqual(self.i18n.get_locale(), "vi")
        self.assertEqual(t("app.name"), "AutoStock Studio")
        self.assertEqual(t("common.ok"), "Đồng ý")
        self.assertEqual(t("common.cancel"), "Hủy")
        self.assertEqual(t("tabs.downloader"), "Tải Stock")
        self.assertEqual(t("tabs.workflow"), "Quy Trình")

    def test_english_translations(self):
        self.i18n.set_locale("en")
        self.assertEqual(self.i18n.get_locale(), "en")
        self.assertEqual(t("app.name"), "AutoStock Studio")
        self.assertEqual(t("common.ok"), "OK")
        self.assertEqual(t("common.cancel"), "Cancel")
        self.assertEqual(t("tabs.downloader"), "Stock Downloader")
        self.assertEqual(t("tabs.workflow"), "Workflow")

    def test_parameter_interpolation(self):
        self.i18n.set_locale("vi")
        res = t("downloader.loaded_json_status", count=42)
        self.assertEqual(res, "Đã nạp 42 cảnh")

        self.i18n.set_locale("en")
        res_en = t("downloader.loaded_json_status", count=42)
        self.assertEqual(res_en, "Loaded 42 scenes")

    def test_fallback_to_english_and_key(self):
        self.i18n.set_locale("vi")
        # Non-existent key falls back to key itself
        self.assertEqual(t("non.existent.key"), "non.existent.key")

    def test_reactive_language_changed_signal(self):
        received_locales = []

        def on_lang_changed(new_lang):
            received_locales.append(new_lang)

        self.i18n.languageChanged.connect(on_lang_changed)
        self.i18n.set_locale("en")
        self.assertIn("en", received_locales)

        self.i18n.set_locale("vi")
        self.assertIn("vi", received_locales)
        self.i18n.languageChanged.disconnect(on_lang_changed)


class TestVectorSvgIcons(unittest.TestCase):
    """Test suite for high-DPI vector SVG icons and pixmaps."""

    def test_icon_names_availability(self):
        names = get_icon_names()
        self.assertIn("search", names)
        self.assertIn("stop", names)
        self.assertIn("play", names)
        self.assertIn("settings", names)
        self.assertIn("key", names)
        self.assertIn("folder", names)
        self.assertIn("database", names)
        self.assertIn("globe", names)
        self.assertIn("workflow", names)
        self.assertIn("activity", names)

    def test_get_svg_icon(self):
        icon = get_svg_icon("search", "#6366f1", 16)
        self.assertIsInstance(icon, QIcon)
        self.assertFalse(icon.isNull())

    def test_get_svg_pixmap(self):
        pixmap = get_svg_pixmap("download", "#10b981", 20)
        self.assertIsInstance(pixmap, QPixmap)
        self.assertFalse(pixmap.isNull())
        self.assertEqual(pixmap.width(), 20)
        self.assertEqual(pixmap.height(), 20)

    def test_fallback_on_unknown_icon(self):
        # Unknown icon falls back safely to 'info' icon without crashing
        icon = get_svg_icon("unknown_icon_that_does_not_exist", "#ffffff", 16)
        self.assertIsInstance(icon, QIcon)
        self.assertFalse(icon.isNull())


if __name__ == "__main__":
    unittest.main()
