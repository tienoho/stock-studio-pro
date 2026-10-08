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
        self.assertFalse(dialog.progress_frame.isVisible())
        self.assertIn("Cập Nhật", dialog.btn_action.text())
        dialog.close()
        dialog.deleteLater()

    def test_extract_archive_and_unnesting(self):
        import tempfile
        import zipfile
        import shutil
        from pathlib import Path

        temp_dir = Path(tempfile.mkdtemp())
        try:
            zip_path = temp_dir / "test_package.zip"
            extract_dest = temp_dir / "extracted"

            # Create mock zip archive with a root folder
            with zipfile.ZipFile(zip_path, "w") as zf:
                zf.writestr("AutoStockStudio_Release/run_exe.bat", "@echo off\nstart AutoStockStudio.exe")
                zf.writestr("AutoStockStudio_Release/AutoStockStudio/AutoStockStudio.exe", "fake_binary_content")
                zf.writestr("AutoStockStudio_Release/AutoStockStudio/app.dll", "fake_dll_content")

            service = UpdateCheckerService()
            payload_dir = service.extract_archive(zip_path, extract_dest)

            # Check that unnesting picked the root folder
            self.assertTrue(payload_dir.exists())
            self.assertEqual(payload_dir.name, "AutoStockStudio_Release")
            self.assertTrue((payload_dir / "run_exe.bat").exists())
            self.assertTrue((payload_dir / "AutoStockStudio" / "AutoStockStudio.exe").exists())
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_generate_updater_script(self):
        import tempfile
        import shutil
        from pathlib import Path

        temp_dir = Path(tempfile.mkdtemp())
        try:
            staged_dir = temp_dir / "staged"
            target_dir = temp_dir / "app"
            staged_dir.mkdir(parents=True, exist_ok=True)
            target_dir.mkdir(parents=True, exist_ok=True)

            service = UpdateCheckerService()
            bat_path = service.generate_updater_script(
                staged_dir=staged_dir,
                target_dir=target_dir,
                exe_name="AutoStockStudio.exe",
                app_pid=99999,
                output_script_path=temp_dir / "_apply_update.bat"
            )

            self.assertTrue(bat_path.exists())
            bat_content = bat_path.read_text(encoding="utf-8")
            self.assertIn("PID=99999", bat_content)
            self.assertIn("robocopy", bat_content)
            self.assertIn("AutoStockStudio.exe", bat_content)
            self.assertIn("tasklist", bat_content)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_resolve_update_target_dev_mode(self):
        import tempfile
        import shutil
        from pathlib import Path

        temp_dir = Path(tempfile.mkdtemp())
        try:
            exe_file = temp_dir / "AutoStockStudio.exe"
            exe_file.write_text("dummy")

            service = UpdateCheckerService()
            src_dir, target_dir, exe_name = service.resolve_update_target(temp_dir)
            self.assertEqual(exe_name, "AutoStockStudio.exe")
            self.assertEqual(src_dir.resolve(), temp_dir.resolve())
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_download_asset_mocked(self):
        from unittest.mock import patch, MagicMock
        import tempfile
        import shutil
        from pathlib import Path

        temp_dir = Path(tempfile.mkdtemp())
        try:
            dest_file = temp_dir / "update.zip"
            mock_resp = MagicMock()
            mock_resp.headers = {"content-length": "100"}
            mock_resp.iter_content = MagicMock(return_value=[b"chunk1_" * 5, b"chunk2_" * 5])
            mock_resp.raise_for_status = MagicMock()

            progress_calls = []
            def cb(dl, tot, spd):
                progress_calls.append((dl, tot, spd))

            service = UpdateCheckerService()
            with patch("requests.get", return_value=mock_resp):
                service.download_asset("https://fake.url/pkg.zip", dest_file, progress_cb=cb)

            self.assertTrue(dest_file.exists())
            self.assertGreater(len(progress_calls), 0)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_update_dialog_ui_workflow(self):
        from src.ui.workers.update_worker import UpdateDownloadWorker
        import tempfile
        import shutil
        from pathlib import Path

        temp_dir = Path(tempfile.mkdtemp())
        try:
            fake_payload = temp_dir / "AutoStockStudio_Release"
            fake_payload.mkdir()

            release = ReleaseInfo(
                tag_name="v2.0.0",
                version="2.0.0",
                title="AutoStock Studio v2.0.0",
                body="Major release with full auto updater.",
                published_at="2026-10-08",
                html_url="https://github.com/tienoho/stock-studio-pro",
                download_url="https://github.com/tienoho/stock-studio-pro/releases/download/v2.0.0/AutoStockStudio-windows-x64.zip",
                asset_size=50000000
            )

            dialog = UpdateDialog(release, current_version="1.0.0")
            # 1. Test progress simulation
            dialog.progress_frame.setVisible(True)
            dialog._on_download_progress(25000000, 50000000, 50.0, 5000000)
            self.assertEqual(dialog.progress_bar.value(), 50)
            self.assertIn("50.0%", dialog.lbl_details.text())

            # 2. Test status updates
            dialog._on_download_status("Đang giải nén gói...")
            self.assertEqual(dialog.lbl_status.text(), "Đang giải nén gói...")

            # 3. Test completion (dev mode)
            dialog._on_download_finished(True, "Thành công", fake_payload)
            self.assertEqual(dialog.progress_bar.value(), 100)
            self.assertIn("Mở Thư Mục", dialog.btn_action.text())

            dialog.close()
            dialog.deleteLater()
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()

