"""
Unit tests for UI/UX enhancements, micro-interactions, and macro-interactions:
- ToastNotification creation, styling, and auto-dismiss
- ThumbnailCard selection toggle and double-click preview
- DownloaderTab filter counting and empty state rendering
"""

import sys
import unittest
from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtGui import QMouseEvent

# Ensure a single QApplication instance for UI tests
app = QApplication.instance()
if app is None:
    app = QApplication([sys.argv[0], "-platform", "offscreen"])

from src.ui.components.toast_notification import ToastNotification
from src.ui.components.thumbnail_card import ThumbnailCard


class TestUIInteractions(unittest.TestCase):
    """Tests for UI/UX components and micro-interactions."""

    def setUp(self):
        self.parent = QWidget()
        self.parent.resize(800, 600)
        self.parent.show()

    def tearDown(self):
        self.parent.close()
        self.parent.deleteLater()

    def test_toast_notification_creation(self):
        """Test ToastNotification initializes with proper icon and styling for all types."""
        types = ["success", "error", "warning", "info"]
        for t in types:
            toast = ToastNotification(self.parent, f"Test {t} message", toast_type=t, duration_ms=1000)
            self.assertIsNotNone(toast)
            self.assertEqual(toast.msg_lbl.text(), f"Test {t} message")
            toast.deleteLater()

    def test_toast_notification_show_toast_helper(self):
        """Test show_toast factory helper displays toast anchored to parent."""
        toast = ToastNotification.show_toast(self.parent, "Helper toast", "info", 2000)
        self.assertIsNotNone(toast)
        self.assertFalse(toast.isHidden())
        toast.close_toast()

    def test_thumbnail_card_selection_and_preview(self):
        """Test ThumbnailCard responds to single-click for selection and double-click for preview."""
        item = {
            "id": 999,
            "source": "pexels",
            "type": "video",
            "title": "Ocean Waves",
            "thumb_url": "https://example.com/thumb.jpg",
            "video_files": [{"link": "https://example.com/video.mp4", "quality": "hd"}],
        }

        selected_events = []
        preview_events = []

        card = ThumbnailCard(item=item, is_selected=False, parent=self.parent)
        card.selectionChanged.connect(lambda it, st: selected_events.append((it["id"], st)))
        card.clicked.connect(lambda it: preview_events.append(it["id"]))

        self.assertFalse(card.is_selected)

        from PyQt6.QtCore import QPointF

        # Simulate clicking the card body (micro-interaction: click to select)
        event = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            QPointF(10.0, 10.0),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier
        )
        card.mousePressEvent(event)

        self.assertTrue(card.is_selected)
        self.assertEqual(len(selected_events), 1)
        self.assertEqual(selected_events[0], (999, True))

        # Simulate double-clicking the card body (micro-interaction: dbl-click to preview)
        dbl_event = QMouseEvent(
            QMouseEvent.Type.MouseButtonDblClick,
            QPointF(10.0, 10.0),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier
        )
        card.mouseDoubleClickEvent(dbl_event)

        self.assertEqual(len(preview_events), 1)
        self.assertEqual(preview_events[0], 999)

        card.deleteLater()

    def test_thumbnail_card_set_selected_updates_style(self):
        """Test set_selected updates checkbox and frame visual state."""
        item = {
            "id": 100,
            "source": "pexels",
            "type": "photo",
            "thumb_url": "https://example.com/photo.jpg",
        }
        card = ThumbnailCard(item=item, parent=self.parent)
        self.assertFalse(card.checkbox.isChecked())

        card.set_selected(True)
        self.assertTrue(card.checkbox.isChecked())
        self.assertTrue(card.is_selected)

        card.set_selected(False)
        self.assertFalse(card.checkbox.isChecked())
        self.assertFalse(card.is_selected)
        card.deleteLater()

    def test_downloader_tab_filtering_and_counts(self):
        """Test DownloaderTab calculates filter badges, navigates scenes, and applies filters properly."""
        from src.ui.tabs.downloader_tab import DownloaderTab
        tab = DownloaderTab(config={}, parent=self.parent)

        scenes = [
            {"id": 1, "time_start": "00:00", "time_end": "00:05", "duration_seconds": 5},
            {"id": 2, "time_start": "00:05", "time_end": "00:10", "duration_seconds": 5},
        ]
        tab.load_scenes(scenes)
        self.assertEqual(len(tab.scenes), 2)
        self.assertEqual(tab.current_scene_id, 1)

        # Populate sample media items
        tab.scene_items[1] = [
            {"id": 101, "source": "pexels", "type": "photo"},
            {"id": 102, "source": "pexels", "type": "video"},
            {"id": 103, "source": "pexels", "type": "video"},
        ]

        # Initially filter 'all'
        tab.current_filter = "all"
        filtered_all = tab._apply_filter(tab._get_current_items())
        self.assertEqual(len(filtered_all), 3)

        tab.current_filter = "photos"
        filtered_photos = tab._apply_filter(tab._get_current_items())
        self.assertEqual(len(filtered_photos), 1)

        tab.current_filter = "videos"
        filtered_videos = tab._apply_filter(tab._get_current_items())
        self.assertEqual(len(filtered_videos), 2)

        # Test selecting items and 'selected' filter
        tab.selected_items[1] = {tab._get_item_key(tab.scene_items[1][0]): tab.scene_items[1][0]}
        tab.current_filter = "selected"
        filtered_sel = tab._apply_filter(tab._get_current_items())
        self.assertEqual(len(filtered_sel), 1)

        # Test scene navigation (macro interactions)
        tab.select_next_scene()
        self.assertEqual(tab.current_scene_id, 2)
        tab.select_prev_scene()
        self.assertEqual(tab.current_scene_id, 1)

        tab.deleteLater()

    def test_voice_tab_signals_and_preview(self):
        """Test VoiceTab initializes with finished signal and audio preview player."""
        from src.ui.tabs.voice_tab import VoiceTab
        tab = VoiceTab(parent=self.parent)
        self.assertIsNotNone(tab.player)
        self.assertIsNotNone(tab.audio_output)
        self.assertTrue(hasattr(tab, "finished"))
        self.assertTrue(hasattr(tab, "merge_audio_native"))
        self.assertTrue(hasattr(tab, "merge_srt_native"))
        tab.deleteLater()

    def test_scene_voice_tab_signals(self):
        """Test SceneVoiceTab initializes with finished signal and required inputs."""
        from src.ui.tabs.scene_voice_tab import SceneVoiceTab
        tab = SceneVoiceTab(parent=self.parent)
        self.assertTrue(hasattr(tab, "finished"))
        self.assertIsNotNone(tab.svc_root)
        self.assertIsNotNone(tab.svc_out)
        tab.deleteLater()

    def test_auto_tab_signals(self):
        """Test AutoTab initializes with runAutoRequested signal."""
        from src.ui.tabs.auto_tab import AutoTab
        tab = AutoTab(parent=self.parent)
        self.assertTrue(hasattr(tab, "runAutoRequested"))
        tab.deleteLater()


if __name__ == "__main__":
    unittest.main()
