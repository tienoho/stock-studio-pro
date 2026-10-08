"""
Unit tests for UpdateCheckerService, SemVer comparisons, and UpdateDialog UI.
"""

import sys
import unittest
from PyQt6.QtWidgets import QApplication, QWidget

# Ensure a single QApplication instance for UI tests
app = QApplication.instance()
if app is None:
    app = QApplication([sys.argv[0], "-platform", "offscreen"])

from src.application.services.update_checker import (
    parse_semver, compare_versions, ReleaseInfo, UpdateCheckerService
)
from src.ui.dialogs.update_dialog import UpdateDialog


class TestUpdateChecker(unittest.TestCase):
    """Test suite for version parsing, comparison, and update notifications."""

    def test_parse_semver(self):
        self.assertEqual(parse_semver("1.0"), (1, 0, 0))
        self.assertEqual(parse_semver("v1.0.2"), (1, 0, 2))
        self.assertEqual(parse_semver("V2.15.4"), (2, 15, 4))
        self.assertEqual(parse_semver("1.2.3-beta"), (1, 2, 3))
        self.assertEqual(parse_semver("invalid"), (0, 0, 0))

    def test_compare_versions(self):
        # v1 > v2 -> 1
        self.assertEqual(compare_versions("1.0.1", "1.0.0"), 1)
        self.assertEqual(compare_versions("v1.1.0", "1.0.9"), 1)
        self.assertEqual(compare_versions("2.0.0", "1.99.99"), 1)

        # v1 == v2 -> 0
        self.assertEqual(compare_versions("1.0.0", "1.0"), 0)
        self.assertEqual(compare_versions("v1.2.3", "1.2.3"), 0)

        # v1 < v2 -> -1
        self.assertEqual(compare_versions("1.0.0", "1.0.1"), -1)
        self.assertEqual(compare_versions("1.0.0", "2.0.0"), -1)

    def test_release_info_from_dict(self):
        data = {
            "tag_name": "v1.1.0",
            "name": "AutoStock Studio v1.1.0 Release",
            "body": "- Thêm tính năng Auto-Update\n- Nâng cấp giao diện",
            "published_at": "2026-10-08T10:00:00Z",
            "html_url": "https://github.com/tienoho/stock-studio-pro/releases/tag/v1.1.0",
            "assets": [
                {
                    "name": "AutoStockStudio-windows-x64.zip",
                    "browser_download_url": "https://github.com/tienoho/stock-studio-pro/releases/download/v1.1.0/AutoStockStudio-windows-x64.zip",
                    "size": 52428800
                }
            ]
        }
        info = ReleaseInfo.from_dict(data)
        self.assertEqual(info.tag_name, "v1.1.0")
        self.assertEqual(info.version, "1.1.0")
        self.assertEqual(info.title, "AutoStock Studio v1.1.0 Release")
        self.assertIn("Auto-Update", info.body)
        self.assertEqual(info.published_at, "2026-10-08")
        self.assertEqual(info.asset_size, 52428800)
        self.assertTrue(info.download_url.endswith(".zip"))

    def test_update_checker_service_init(self):
        service = UpdateCheckerService(owner="testowner", repo="testrepo")
        self.assertEqual(service.owner, "testowner")
        self.assertEqual(service.repo, "testrepo")
        self.assertEqual(service.api_url, "https://api.github.com/repos/testowner/testrepo/releases/latest")

    def test_update_dialog_creation(self):
        release = ReleaseInfo(
            tag_name="v1.2.0",
            version="1.2.0",
            title="AutoStock Studio v1.2.0",
            body="New features and performance boosts.",
            published_at="2026-10-08",
            html_url="https://github.com/tienoho/stock-studio-pro",
            download_url="https://github.com/tienoho/stock-studio-pro/archive/v1.2.0.zip",
            asset_size=40000000
        )
        dialog = UpdateDialog(release, current_version="1.0.0")
        self.assertIsNotNone(dialog)
        self.assertEqual(dialog.release.version, "1.2.0")
        self.assertEqual(dialog.current_version, "1.0.0")
        dialog.close()
        dialog.deleteLater()


if __name__ == "__main__":
    unittest.main()
