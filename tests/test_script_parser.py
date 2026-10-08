"""
Unit tests for ScriptParserService covering JSON, SRT, TXT, CSV, and Excel (XLSX).
"""

import unittest
import tempfile
import json
from pathlib import Path

from src.application.services.script_parser_service import (
    ScriptParserService,
    extract_keywords_from_text,
    format_seconds_to_timecode,
    parse_duration_to_seconds,
)


class TestScriptParserService(unittest.TestCase):
    """Test suite for universal script ingestion across all formats."""

    def setUp(self):
        self.parser = ScriptParserService()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.dir_path = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    # ─────────────────────────────────────────────────────────────
    # Helper utilities
    # ─────────────────────────────────────────────────────────────

    def test_format_seconds_to_timecode(self):
        self.assertEqual(format_seconds_to_timecode(0), "00:00")
        self.assertEqual(format_seconds_to_timecode(65), "01:05")
        self.assertEqual(format_seconds_to_timecode(3665), "01:01:05")

    def test_parse_duration_to_seconds(self):
        self.assertEqual(parse_duration_to_seconds(5), 5.0)
        self.assertEqual(parse_duration_to_seconds("4.5s"), 4.5)
        self.assertEqual(parse_duration_to_seconds("10 giây"), 10.0)
        self.assertEqual(parse_duration_to_seconds("00:02:15"), 135.0)
        self.assertEqual(parse_duration_to_seconds(None), 0.0)

    def test_extract_keywords_from_text(self):
        text_vi = "Khám phá vẻ đẹp kỳ vĩ của thiên nhiên tại vườn quốc gia Phong Nha Kẻ Bàng"
        pk, sk = extract_keywords_from_text(text_vi)
        self.assertTrue(len(pk) > 0)
        self.assertTrue(any("phong nha" in k.lower() or "thiên nhiên" in k.lower() or "quốc gia" in k.lower() for k in pk + sk))

        text_en = "Cinematic aerial drone footage of modern skyscraper skyline at sunset"
        pk_en, sk_en = extract_keywords_from_text(text_en)
        self.assertTrue(len(pk_en) > 0)

        short_text = "con mèo"
        pk_short, _ = extract_keywords_from_text(short_text)
        self.assertEqual(pk_short, ["con mèo"])

    # ─────────────────────────────────────────────────────────────
    # Format: JSON
    # ─────────────────────────────────────────────────────────────

    def test_parse_json_screenplay(self):
        json_data = {
            "scenes": [
                {
                    "id": 1,
                    "time_start": "00:00:00",
                    "time_end": "00:00:04",
                    "duration_seconds": 4.0,
                    "dialogue_es": "Xin chào các bạn đến với kênh công nghệ",
                    "primary_keywords": ["công nghệ", "studio"],
                    "secondary_keywords": ["máy tính"]
                },
                {
                    "id": 2,
                    "dialogue": "Hôm nay chúng ta sẽ đánh giá chiếc máy tính xách tay mới",
                    "keywords": "laptop, ultrabook, đánh giá"
                }
            ]
        }
        json_file = self.dir_path / "script.json"
        json_file.write_text(json.dumps(json_data, ensure_ascii=False), encoding="utf-8")

        scenes, meta = self.parser.parse_file(json_file)
        self.assertEqual(len(scenes), 2)
        self.assertEqual(scenes[0]["id"], 1)
        self.assertEqual(scenes[0]["primary_keywords"], ["công nghệ", "studio"])
        self.assertEqual(scenes[1]["id"], 2)
        self.assertEqual(scenes[1]["primary_keywords"], ["laptop", "ultrabook", "đánh giá"])
        self.assertEqual(meta["format"], "json")

    def test_parse_json_markdown_wrapped(self):
        raw_text = """Here is your script:
```json
{
  "scenes": [
    {"id": 1, "dialogue": "First scene", "duration_seconds": 5}
  ]
}
```
Hope you like it!"""
        scenes, meta = self.parser.parse_text(raw_text)
        self.assertEqual(len(scenes), 1)
        self.assertEqual(scenes[0]["dialogue"], "First scene")
        self.assertEqual(scenes[0]["duration_seconds"], 5.0)

    # ─────────────────────────────────────────────────────────────
    # Format: SRT Subtitles
    # ─────────────────────────────────────────────────────────────

    def test_parse_srt_file(self):
        srt_content = """1
00:00:01,000 --> 00:00:05,500
Chào mừng quý vị và các bạn đã quay trở lại.

2
00:00:05,800 --> 00:00:10,000
Hôm nay chúng ta sẽ tìm hiểu về trí tuệ nhân tạo.
Cuộc cách mạng công nghệ mới nhất.
"""
        srt_file = self.dir_path / "subtitles.srt"
        srt_file.write_text(srt_content, encoding="utf-8")

        scenes, meta = self.parser.parse_file(srt_file)
        self.assertEqual(len(scenes), 2)
        self.assertEqual(scenes[0]["id"], 1)
        self.assertEqual(scenes[0]["time_start"], "00:00:01,000")
        self.assertEqual(scenes[0]["time_end"], "00:00:05,500")
        self.assertAlmostEqual(scenes[0]["duration_seconds"], 4.5, places=1)
        self.assertIn("Chào mừng quý vị", scenes[0]["dialogue"])

        self.assertEqual(scenes[1]["id"], 2)
        self.assertAlmostEqual(scenes[1]["duration_seconds"], 4.2, places=1)
        self.assertTrue(len(scenes[1]["primary_keywords"]) > 0)
        self.assertEqual(meta["format"], "srt")

    # ─────────────────────────────────────────────────────────────
    # Format: Plain Text (.txt)
    # ─────────────────────────────────────────────────────────────

    def test_parse_txt_structured_scenes(self):
        txt_content = """Cảnh 1: Một buổi sáng bình minh yên bình tại bờ biển | Từ khóa: bình minh, bờ biển, bình yên
Cảnh 2 (5s): Đôi bạn trẻ đang đi dạo trên bờ cát | Keywords: bãi cát, đi dạo, đôi bạn
Cảnh 3 [00:00:09 - 00:00:14]: Khung cảnh sóng biển vỗ rì rào lúc hoàng hôn
"""
        txt_file = self.dir_path / "script.txt"
        txt_file.write_text(txt_content, encoding="utf-8")

        scenes, meta = self.parser.parse_file(txt_file)
        self.assertEqual(len(scenes), 3)
        self.assertEqual(scenes[0]["id"], 1)
        self.assertIn("bình minh", scenes[0]["primary_keywords"])
        self.assertEqual(scenes[1]["duration_seconds"], 5.0)
        self.assertIn("bãi cát", scenes[1]["primary_keywords"])
        self.assertEqual(scenes[2]["duration_seconds"], 5.0)
        self.assertEqual(meta["format"], "txt")

    def test_parse_txt_plain_paragraphs(self):
        txt_content = """Chào mừng bạn đến với kênh tài chính thông minh.
Hôm nay chúng ta sẽ học cách tiết kiệm 30% thu nhập mỗi tháng.
Đầu tư vào tri thức luôn mang lại lợi nhuận cao nhất.
"""
        scenes, meta = self.parser.parse_text(txt_content, format_hint="txt")
        self.assertEqual(len(scenes), 3)
        self.assertEqual(scenes[0]["id"], 1)
        self.assertTrue(scenes[0]["duration_seconds"] >= 3.0)
        self.assertTrue(len(scenes[0]["primary_keywords"]) > 0)

    # ─────────────────────────────────────────────────────────────
    # Format: CSV / TSV
    # ─────────────────────────────────────────────────────────────

    def test_parse_csv_file(self):
        csv_content = """Cảnh,Lời thoại,Từ khóa,Thời lượng
1,Mở đầu video với hình ảnh thiên nhiên tươi đẹp,"thiên nhiên, núi rừng, phong cảnh",4
2,Tiếp theo là phân cảnh thành phố nhộn nhịp,"thành phố, đô thị, xe cộ",5.5
"""
        csv_file = self.dir_path / "script.csv"
        csv_file.write_text(csv_content, encoding="utf-8-sig")

        scenes, meta = self.parser.parse_file(csv_file)
        self.assertEqual(len(scenes), 2)
        self.assertEqual(scenes[0]["id"], "1")
        self.assertIn("thiên nhiên", scenes[0]["primary_keywords"])
        self.assertEqual(scenes[0]["duration_seconds"], 4.0)
        self.assertEqual(scenes[1]["duration_seconds"], 5.5)
        self.assertIn("thành phố", scenes[1]["primary_keywords"])
        self.assertEqual(meta["format"], "csv")

    def test_parse_tsv_data(self):
        tsv_content = "Scene\tDialogue\tKeywords\tDuration\n1\tA modern office workspace\toffice, laptop, typing\t4.5\n2\tTeam meeting discussion\tbusiness, meeting, team\t6\n"
        scenes, meta = self.parser.parse_text(tsv_content)
        self.assertEqual(len(scenes), 2)
        self.assertEqual(scenes[0]["duration_seconds"], 4.5)
        self.assertIn("office", scenes[0]["primary_keywords"])

    # ─────────────────────────────────────────────────────────────
    # Format: Excel (.xlsx)
    # ─────────────────────────────────────────────────────────────

    def test_parse_excel_xlsx(self):
        try:
            import openpyxl
        except ImportError:
            self.skipTest("openpyxl not installed")

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["STT", "Lời Thoại", "Từ Khóa", "Thời Lượng"])
        ws.append([1, "Khung cảnh quán cà phê ấm cúng", "coffee shop, cozy, warm", 4])
        ws.append([2, "Một lập trình viên đang gõ mã nguồn", "coding, developer, laptop", 5])

        excel_file = self.dir_path / "script.xlsx"
        wb.save(excel_file)

        scenes, meta = self.parser.parse_file(excel_file)
        self.assertEqual(len(scenes), 2)
        self.assertEqual(scenes[0]["id"], "1")
        self.assertIn("Khung cảnh quán cà phê", scenes[0]["dialogue"])
        self.assertIn("coffee shop", scenes[0]["primary_keywords"])
        self.assertEqual(scenes[0]["duration_seconds"], 4.0)
        self.assertEqual(scenes[1]["duration_seconds"], 5.0)
        self.assertIn("coding", scenes[1]["primary_keywords"])
    def test_parse_excel_xlsx_fallback_xml(self):
        try:
            import openpyxl
        except ImportError:
            self.skipTest("openpyxl not installed")

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["Cảnh", "Nội Dung", "Từ Khóa", "Thời Gian"])
        ws.append([1, "Toàn cảnh bãi biển Phú Quốc", "bãi biển, du lịch, việt nam", 5])
        excel_file = self.dir_path / "fallback.xlsx"
        wb.save(excel_file)

        # Directly test pure XML fallback parser
        rows = self.parser._parse_xlsx_xml_fallback(excel_file)
        self.assertTrue(len(rows) >= 2)
        scenes = self.parser._map_table_rows_to_scenes(rows)
        self.assertEqual(len(scenes), 1)
        self.assertIn("bãi biển", scenes[0]["primary_keywords"])

    def test_parse_csv_semicolon_delimited(self):
        content = "Phân đoạn;Lời thoại;Từ khóa phụ;Thời lượng\n1;Giới thiệu công nghệ;AI, robot;3.5\n"
        scenes, meta = self.parser.parse_text(content, format_hint="csv")
        self.assertEqual(len(scenes), 1)
        self.assertEqual(scenes[0]["id"], "1")
        self.assertEqual(scenes[0]["duration_seconds"], 3.5)

    def test_is_supported_file_and_filters(self):
        self.assertTrue(self.parser.is_supported_file("storyboard.json"))
        self.assertTrue(self.parser.is_supported_file("subtitles.srt"))
        self.assertTrue(self.parser.is_supported_file("script.txt"))
        self.assertTrue(self.parser.is_supported_file("scenes.xlsx"))
        self.assertTrue(self.parser.is_supported_file("data.csv"))
        self.assertFalse(self.parser.is_supported_file("video.mp4"))
        self.assertIn("*.xlsx", self.parser.get_supported_filter_string())


if __name__ == "__main__":
    unittest.main()
