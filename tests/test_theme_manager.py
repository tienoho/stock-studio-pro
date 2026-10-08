"""
Unit tests for AutoStock Studio ThemeManager and Dark/Light Mode switching.
"""

import sys
import unittest
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6.QtCore import Qt

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Ensure a single QApplication instance for UI tests
app = QApplication.instance()
if app is None:
    app = QApplication([sys.argv[0], "-platform", "offscreen"])

from src.ui.styles.theme_manager import ThemeManager
from src.ui.styles.tokens import load_stylesheet
from src.ui.components.thumbnail_card import ThumbnailCard
from src.ui.components.status_panel import StatusPanel
from src.ui.components.scene_list_item import SceneListItem


class TestThemeManager(unittest.TestCase):
    """Test suite for ThemeManager singleton and theme transitions."""

    def setUp(self):
        self.theme_mgr = ThemeManager.get_instance()
        # Reset to dark mode for test consistency
        self.theme_mgr.set_theme("dark")

    def tearDown(self):
        # Restore to default dark theme
        self.theme_mgr.set_theme("dark")

    def test_singleton_instance(self):
        """ThemeManager should follow singleton pattern."""
        mgr2 = ThemeManager.get_instance()
        self.assertIs(self.theme_mgr, mgr2)

    def test_default_theme_is_dark(self):
        """Default theme should be dark."""
        self.assertEqual(self.theme_mgr.theme, "dark")
        self.assertTrue(self.theme_mgr.is_dark())
        self.assertFalse(self.theme_mgr.is_light())

    def test_switch_to_light_theme(self):
        """Setting theme to light updates state and emits signal."""
        emitted_themes = []
        self.theme_mgr.themeChanged.connect(lambda t: emitted_themes.append(t))

        self.theme_mgr.set_theme("light")

        self.assertEqual(self.theme_mgr.theme, "light")
        self.assertFalse(self.theme_mgr.is_dark())
        self.assertTrue(self.theme_mgr.is_light())
        self.assertEqual(emitted_themes, ["light"])

    def test_toggle_theme(self):
        """Toggling theme flips between dark and light."""
        self.theme_mgr.set_theme("dark")
        new_theme = self.theme_mgr.toggle_theme()
        self.assertEqual(new_theme, "light")
        self.assertTrue(self.theme_mgr.is_light())

        new_theme_2 = self.theme_mgr.toggle_theme()
        self.assertEqual(new_theme_2, "dark")
        self.assertTrue(self.theme_mgr.is_dark())

    def test_get_stylesheet_contents(self):
        """ThemeManager should load valid QSS files for both dark and light modes."""
        dark_qss = self.theme_mgr.get_stylesheet("dark")
        self.assertIn("#080b11", dark_qss)
        self.assertIn("QMainWindow", dark_qss)

        light_qss = self.theme_mgr.get_stylesheet("light")
        self.assertIn("#f8fafc", light_qss)
        self.assertIn("QMainWindow", light_qss)

    def test_tokens_load_stylesheet_integrates_with_theme_manager(self):
        """load_stylesheet in tokens.py dynamically pulls current or requested theme."""
        self.theme_mgr.set_theme("dark")
        dark_qss = load_stylesheet()
        self.assertIn("#080b11", dark_qss)

        self.theme_mgr.set_theme("light")
        light_qss = load_stylesheet()
        self.assertIn("#f8fafc", light_qss)

        # Explicit argument overrides active theme
        forced_dark = load_stylesheet("dark")
        self.assertIn("#080b11", forced_dark)

    def test_thumbnail_card_theme_awareness(self):
        """ThumbnailCard styles should adapt dynamically to theme changes."""
        item = {
            "id": 1,
            "source": "pexels",
            "type": "video",
            "title": "Sample",
        }
        card = ThumbnailCard(item=item, is_selected=False)
        self.theme_mgr.set_theme("dark")
        self.assertIn("#121826", card.styleSheet())

        self.theme_mgr.set_theme("light")
        self.assertIn("#ffffff", card.styleSheet())
        card.deleteLater()

    def test_status_panel_theme_awareness(self):
        """StatusPanel should update background and text styling on theme changes."""
        panel = StatusPanel()
        self.theme_mgr.set_theme("dark")
        self.assertIn("#121826", panel.styleSheet())

        self.theme_mgr.set_theme("light")
        self.assertIn("#ffffff", panel.styleSheet())
        panel.deleteLater()

    def test_scene_list_item_theme_awareness(self):
        """SceneListItem should update style when theme changes."""
        scene = {
            "id": 10,
            "time_start": "00:00",
            "time_end": "00:05",
            "duration_seconds": 5,
            "primary_keywords": ["city", "night"],
        }
        item = SceneListItem(scene=scene, is_active=False)
        self.theme_mgr.set_theme("dark")
        item._update_style()
        self.assertIn("#111724", item.styleSheet())

        self.theme_mgr.set_theme("light")
        item._update_style()
        self.assertIn("#ffffff", item.styleSheet())
        item.deleteLater()


if __name__ == "__main__":
    unittest.main()
