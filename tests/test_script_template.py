"""
Unit tests for ScriptTemplateService.
Verifies sample generation (JSON, TXT, SRT, CSV, XLSX) and round-trip parsing with ScriptParserService.
"""

import unittest
import tempfile
from pathlib import Path

from src.application.services.script_template_service import ScriptTemplateService
from src.application.services.script_parser_service import ScriptParserService


class TestScriptTemplateService(unittest.TestCase):
    """Test suite for script template generators, exporters, and AI prompts."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.dir_path = Path(self.temp_dir.name)
        self.parser = ScriptParserService()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_prompts_dictionary(self):
        prompts = ScriptTemplateService.PROMPTS
        self.assertIn("json", prompts)
        self.assertIn("excel", prompts)
        self.assertIn("txt", prompts)
        self.assertIn("srt", prompts)

        for key, p in prompts.items():
            self.assertTrue(len(p["title"]) > 0)
            self.assertTrue(len(p["content"]) > 50)

    def test_sample_json_roundtrip(self):
        raw_json = ScriptTemplateService.get_sample_json()
        scenes, meta = self.parser.parse_text(raw_json)
        self.assertEqual(len(scenes), 3)
        self.assertEqual(scenes[0]["id"], 1)
        self.assertTrue(len(scenes[0]["primary_keywords"]) > 0)

    def test_sample_txt_roundtrip(self):
        raw_txt = ScriptTemplateService.get_sample_txt()
        scenes, meta = self.parser.parse_text(raw_txt)
        self.assertEqual(len(scenes), 3)
        self.assertEqual(scenes[0]["id"], 1)
        self.assertEqual(scenes[0]["duration_seconds"], 5.0)

    def test_sample_srt_roundtrip(self):
        raw_srt = ScriptTemplateService.get_sample_srt()
        scenes, meta = self.parser.parse_text(raw_srt)
        self.assertEqual(len(scenes), 3)
        self.assertEqual(scenes[0]["id"], 1)
        self.assertAlmostEqual(scenes[0]["duration_seconds"], 5.0, places=1)

    def test_sample_csv_roundtrip(self):
        raw_csv = ScriptTemplateService.get_sample_csv()
        scenes, meta = self.parser.parse_text(raw_csv)
        self.assertEqual(len(scenes), 3)
        self.assertEqual(scenes[0]["id"], "1")
        self.assertEqual(scenes[0]["duration_seconds"], 5.0)

    def test_generate_sample_xlsx_roundtrip(self):
        xlsx_path = self.dir_path / "test_sample.xlsx"
        ScriptTemplateService.generate_sample_xlsx(xlsx_path)
        self.assertTrue(xlsx_path.exists())

        scenes, meta = self.parser.parse_file(xlsx_path)
        self.assertEqual(len(scenes), 3)
        self.assertEqual(scenes[0]["duration_seconds"], 5.0)

    def test_get_prompt_and_info(self):
        content = ScriptTemplateService.get_prompt("json")
        self.assertIn("scenes", content)
        self.assertIn("dialogue_es", content)

        info = ScriptTemplateService.get_prompt_info("excel")
        self.assertEqual(info["title"], "Kịch bản Bảng Tính Excel / CSV")
        self.assertIn("description", info)
        self.assertIn("content", info)

    def test_export_includes_readme(self):
        export_dir = self.dir_path / "bundle_export"
        files = ScriptTemplateService.export_all_templates(str(export_dir))
        names = [f.name for f in files]
        self.assertIn("README_HUONG_DAN.txt", names)
        readme = export_dir / "README_HUONG_DAN.txt"
        self.assertTrue(readme.exists())
        self.assertIn("HƯỚNG DẪN NẠP KỊCH BẢN", readme.read_text(encoding="utf-8"))

    def test_json_input_dialog_templates_tab(self):
        from PyQt6.QtWidgets import QApplication
        from src.ui.dialogs.json_input_dialog import JsonInputDialog

        app = QApplication.instance() or QApplication([])
        dialog = JsonInputDialog(initial_tab=3)
        self.assertEqual(dialog.tabs.currentIndex(), 3)
        self.assertEqual(dialog.tabs.count(), 4)

        # Switch prompt to excel
        dialog._select_prompt("excel")
        self.assertEqual(dialog._active_prompt_key, "excel")
        self.assertIn("CSV", dialog.prompt_display.toPlainText())

        # Load sample into paste
        dialog._load_sample_into_paste("txt")
        self.assertEqual(dialog.tabs.currentIndex(), 0)
        self.assertIn("Cảnh 1", dialog.text_area.toPlainText())
        dialog.close()


if __name__ == "__main__":
    unittest.main()

