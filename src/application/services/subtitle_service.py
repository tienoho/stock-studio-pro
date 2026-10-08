"""
Subtitle Service managing SRT subtitle parsing, timecode manipulation, and concatenation.
Pure Python application service decoupled from UI framework (PyQt6).
"""

import re
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional


class SubtitleService:
    """Application service for parsing, shifting, and stitching SRT subtitles."""

    TIMECODE_PATTERN = re.compile(
        r"(\d{1,2}):(\d{2}):(\d{2})[,\.](\d{3})\s*-->\s*(\d{1,2}):(\d{2}):(\d{2})[,\.](\d{3})"
    )

    @staticmethod
    def parse_timecode_ms(time_str: str) -> int:
        """Parses an SRT timestamp string (HH:MM:SS,mmm or HH:MM:SS.mmm) into milliseconds."""
        cleaned = time_str.strip().replace(".", ",")
        parts = cleaned.split(":")
        if len(parts) != 3:
            return 0
        h = int(parts[0])
        m = int(parts[1])
        s_parts = parts[2].split(",")
        s = int(s_parts[0])
        ms = int(s_parts[1]) if len(s_parts) > 1 else 0
        return (h * 3600 + m * 60 + s) * 1000 + ms

    @staticmethod
    def format_timecode_ms(total_ms: int) -> str:
        """Formats millisecond integer back into standard SRT timestamp HH:MM:SS,mmm."""
        total_ms = max(0, int(total_ms))
        total_s, ms = divmod(total_ms, 1000)
        total_m, s = divmod(total_s, 60)
        h, m = divmod(total_m, 60)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    def parse_srt_file(self, srt_path: Path) -> List[Dict[str, Any]]:
        """Parses an SRT file into structured subtitle blocks with milliseconds timings."""
        if not srt_path.exists():
            return []
        raw = srt_path.read_text(encoding="utf-8", errors="ignore").replace("\r\n", "\n").replace("\r", "\n")
        blocks = []
        for raw_block in re.split(r"\n{2,}", raw.strip()):
            lines = [l.strip() for l in raw_block.split("\n") if l.strip()]
            if not lines:
                continue
            if lines[0].isdigit():
                lines = lines[1:]
            if not lines:
                continue

            tc_match = self.TIMECODE_PATTERN.search(lines[0])
            if not tc_match:
                continue

            start_str = f"{int(tc_match.group(1)):02d}:{tc_match.group(2)}:{tc_match.group(3)},{tc_match.group(4)}"
            end_str = f"{int(tc_match.group(5)):02d}:{tc_match.group(6)}:{tc_match.group(7)},{tc_match.group(8)}"
            start_ms = self.parse_timecode_ms(start_str)
            end_ms = self.parse_timecode_ms(end_str)
            text_lines = lines[1:]

            blocks.append({
                "start_ms": start_ms,
                "end_ms": end_ms,
                "duration_ms": max(0, end_ms - start_ms),
                "text": "\n".join(text_lines)
            })
        return blocks

    def merge_srt_files(
        self,
        files: List[Path],
        output_path: Path,
        gap_ms: int = 250
    ) -> Tuple[bool, str, int]:
        """
        Merges multiple SRT files in sequence, shifting timestamps progressively with gap_ms.
        Returns: (success, message, total_blocks_written)
        """
        if not files:
            return False, "Không có tệp SRT nào để ghép.", 0

        merged_blocks = []
        offset_ms = 0

        for f in files:
            blocks = self.parse_srt_file(f)
            if not blocks:
                continue

            file_max_end = 0
            for b in blocks:
                shifted_start = b["start_ms"] + offset_ms
                shifted_end = b["end_ms"] + offset_ms
                merged_blocks.append({
                    "start_ms": shifted_start,
                    "end_ms": shifted_end,
                    "text": b["text"]
                })
                file_max_end = max(file_max_end, b["end_ms"])

            offset_ms += file_max_end + gap_ms

        if not merged_blocks:
            return False, "Tất cả các tệp SRT được chọn đều rỗng hoặc không hợp lệ.", 0

        # Construct unified SRT output
        out_lines = []
        for idx, b in enumerate(merged_blocks, start=1):
            s_tc = self.format_timecode_ms(b["start_ms"])
            e_tc = self.format_timecode_ms(b["end_ms"])
            out_lines.append(f"{idx}\n{s_tc} --> {e_tc}\n{b['text']}\n")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            output_path.write_text("\n".join(out_lines).strip() + "\n", encoding="utf-8")
            return True, f"Đã ghép thành công {len(files)} tệp SRT thành {len(merged_blocks)} câu.", len(merged_blocks)
        except Exception as e:
            return False, f"Lỗi ghi tệp SRT đích: {e}", 0
