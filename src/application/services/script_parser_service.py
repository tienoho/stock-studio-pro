"""
Script Parser Service supporting multi-format screenplay ingestion:
JSON (.json), Subtitles (.srt), Plain Text (.txt), and Spreadsheets (Excel .xlsx, .xls and CSV .csv, .tsv).
Decoupled, pure-Python application service adhering to Clean Architecture.
"""

import re
import csv
import json
import io
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional, Union

from ...core.models.scene import extract_scenes_from_json, srt_time_to_seconds, format_duration


# Stop words for smart keyword extraction heuristic
VI_STOPWORDS = {
    "là", "và", "của", "có", "trong", "một", "những", "các", "được", "với", "này", "đó",
    "cho", "để", "khi", "ở", "về", "ra", "vào", "thì", "mà", "như", "nhưng", "lại", "do",
    "bởi", "nếu", "vì", "rồi", "rất", "cũng", "đã", "đang", "sẽ", "tự", "người", "chúng",
    "tôi", "bạn", "họ", "ai", "gì", "nào", "đâu", "sao", "hãy", "đi", "đến", "xem", "video",
    "hôm", "nay", "tại", "qua", "lên", "xuống", "từ", "cùng", "bên", "hay", "trên", "dưới",
    "theo", "chỉ", "phải", "biết", "làm", "thấy", "nói", "việc", "phần", "mình", "ta", "bởi_vì"
}

EN_STOPWORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any",
    "are", "as", "at", "be", "because", "been", "before", "being", "below", "between",
    "both", "but", "by", "can", "could", "did", "do", "does", "doing", "down", "during",
    "each", "few", "for", "from", "further", "had", "has", "have", "having", "he", "her",
    "here", "hers", "him", "himself", "his", "how", "i", "if", "in", "into", "is", "it",
    "its", "just", "me", "more", "most", "my", "myself", "no", "nor", "not", "now", "of",
    "off", "on", "once", "only", "or", "other", "our", "ours", "out", "over", "own", "same",
    "she", "should", "so", "some", "such", "than", "that", "the", "their", "theirs", "them",
    "then", "there", "these", "they", "this", "those", "through", "to", "too", "under",
    "until", "up", "very", "was", "we", "were", "what", "when", "where", "which", "while",
    "who", "whom", "why", "with", "you", "your", "yours"
}

ALL_STOPWORDS = VI_STOPWORDS | EN_STOPWORDS


def extract_keywords_from_text(text: str, max_primary: int = 3, max_secondary: int = 3) -> Tuple[List[str], List[str]]:
    """
    Extracts smart search keywords from dialogue or scene description text.
    Returns (primary_keywords, secondary_keywords).
    """
    if not text or not str(text).strip():
        return [], []

    raw = str(text).strip()
    raw = re.sub(r"```.*?```", " ", raw, flags=re.DOTALL)

    # 1. Look for capitalized phrases (Proper nouns / Locations / Brand names / Acronyms)
    capitalized_phrases = re.findall(r"\b[A-ZÀ-Ỵ][a-zà-ỹ0-9]+(?:\s+[A-ZÀ-Ỵ][a-zà-ỹ0-9]+)*\b", raw)
    acronyms = re.findall(r"\b[A-Z0-9]{2,}\b", raw)

    # 2. Split clauses on punctuation and connectors
    clauses = re.split(r"[,;:.!?–—\n]+", raw)
    clause_candidates = []
    for cl in clauses:
        cl_clean = re.sub(r'[\(\)\[\]\{\}\<\>\"\'`/\-_*#|\\~]', ' ', cl).strip()
        words = [w.strip() for w in cl_clean.split() if w.strip()]
        if not words:
            continue
        if 1 <= len(words) <= 4:
            meaningful_clause = [w for w in words if w.lower() not in ALL_STOPWORDS]
            if meaningful_clause:
                clause_candidates.append(" ".join(words))

    # 3. Clean full text words
    clean = re.sub(r'[\(\)\[\]\{\}\<\>\"\'`.,;?!:/\-_*#|\\~]', ' ', raw)
    words = [w.strip() for w in clean.split() if w.strip()]

    if not words:
        return [], []

    if len(words) <= 3:
        phrase = " ".join(words)
        return [phrase], []

    meaningful = [w for w in words if w.lower() not in ALL_STOPWORDS and len(w) > 1 and not w.isdigit()]
    if not meaningful:
        meaningful = [w for w in words if not w.isdigit() and len(w) > 2]

    # Bigrams
    bigrams = [" ".join(meaningful[i:i+2]) for i in range(len(meaningful)-1)]

    # Prioritize candidate pools:
    all_candidates = capitalized_phrases + acronyms + clause_candidates + bigrams + meaningful

    seen = set()
    deduped = []
    for cand in all_candidates:
        cand_str = cand.strip()
        low = cand_str.lower()
        if low not in seen and len(cand_str) > 2 and low not in ALL_STOPWORDS:
            seen.add(low)
            deduped.append(cand_str)

    primary = deduped[:max_primary]
    secondary = deduped[max_primary:max_primary + max_secondary]
    return primary, secondary



def format_seconds_to_timecode(seconds: float) -> str:
    """Formats seconds into standard HH:MM:SS or MM:SS."""
    sec = max(0.0, float(seconds or 0.0))
    total_sec = int(sec)
    h = total_sec // 3600
    m = (total_sec % 3600) // 60
    s = total_sec % 60
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def parse_duration_to_seconds(value: Any) -> float:
    """Parses numeric, string seconds, or timestamp to float seconds."""
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return max(0.0, float(value))

    val_str = str(value).strip().lower()
    if not val_str:
        return 0.0

    # Strip unit suffix e.g. "4.5s", "5 giây", "5s"
    val_str = re.sub(r"\s*(s|sec|seconds|giây)$", "", val_str)

    # Check HH:MM:SS or MM:SS
    if ":" in val_str:
        return srt_time_to_seconds(val_str)

    try:
        return max(0.0, float(val_str))
    except (ValueError, TypeError):
        return 0.0


class ScriptParserService:
    """
    Universal Script Parser supporting:
    - JSON (.json)
    - Subtitle (.srt)
    - Plain Text (.txt)
    - Excel spreadsheets (.xlsx, .xls)
    - Delimited data (.csv, .tsv)
    """

    SUPPORTED_EXTENSIONS = [".json", ".txt", ".srt", ".csv", ".tsv", ".xlsx", ".xls"]

    SRT_TIMECODE_REGEX = re.compile(
        r"(\d{1,2}:\d{2}:\d{2}[,\.]\d{1,3})\s*-->\s*(\d{1,2}:\d{2}:\d{2}[,\.]\d{1,3})"
    )

    @classmethod
    def is_supported_file(cls, file_path: Union[str, Path]) -> bool:
        """Returns True if the file extension is recognized by this service."""
        suffix = Path(file_path).suffix.lower()
        return suffix in cls.SUPPORTED_EXTENSIONS

    @classmethod
    def get_supported_filter_string(cls) -> str:
        """Returns Qt file dialog filter string."""
        return (
            "Kịch bản hỗ trợ (*.json *.txt *.srt *.csv *.tsv *.xlsx *.xls);;"
            "JSON kịch bản (*.json);;"
            "Văn bản kịch bản (*.txt);;"
            "Phụ đề video (*.srt);;"
            "Bảng tính Excel (*.xlsx *.xls);;"
            "Tệp CSV/TSV (*.csv *.tsv);;"
            "Tất cả tệp (*.*)"
        )

    def parse_file(self, file_path: Union[str, Path]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Parses screenplay file of any supported format.
        Returns: (scenes_list, metadata_dict)
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Tệp không tồn tại: {path}")

        suffix = path.suffix.lower()

        if suffix == ".json":
            content = path.read_text(encoding="utf-8-sig", errors="replace")
            return self.parse_text(content, format_hint="json", source_name=path.name)

        elif suffix == ".srt":
            content = path.read_text(encoding="utf-8-sig", errors="replace")
            return self.parse_text(content, format_hint="srt", source_name=path.name)

        elif suffix in (".csv", ".tsv"):
            content = self._read_text_with_encoding_fallback(path)
            return self.parse_text(content, format_hint="csv", source_name=path.name)

        elif suffix in (".xlsx", ".xls"):
            scenes, meta = self._parse_excel_file(path)
            meta["format"] = "excel"
            meta["source_name"] = path.name
            meta["total_scenes"] = len(scenes)
            return scenes, meta

        elif suffix == ".txt":
            content = self._read_text_with_encoding_fallback(path)
            return self.parse_text(content, format_hint="txt", source_name=path.name)

        else:
            # Fallback: sniff content
            try:
                content = self._read_text_with_encoding_fallback(path)
                return self.parse_text(content, source_name=path.name)
            except Exception as e:
                raise ValueError(f"Định dạng tệp không được hỗ trợ ({suffix}): {e}")

    def parse_text(
        self,
        text: str,
        format_hint: Optional[str] = None,
        source_name: str = "Script"
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Parses raw text content. If format_hint is None, sniffs format automatically.
        format_hint can be: 'json', 'srt', 'csv', 'txt'.
        """
        raw_text = (text or "").strip()
        if not raw_text:
            return [], {"format": "empty", "source_name": source_name, "total_scenes": 0}

        # 1. Determine format
        fmt = (format_hint or "").lower().strip()
        if not fmt:
            fmt = self._sniff_format(raw_text)

        # 2. Dispatch to parser
        if fmt == "json":
            scenes, meta = self._parse_json(raw_text)
        elif fmt == "srt":
            scenes, meta = self._parse_srt(raw_text)
        elif fmt == "csv":
            scenes, meta = self._parse_csv(raw_text)
        else:
            scenes, meta = self._parse_txt(raw_text)

        meta["format"] = fmt
        meta["source_name"] = source_name
        meta["total_scenes"] = len(scenes)

        return scenes, meta

    # ─────────────────────────────────────────────────────────────
    # Format Parsers
    # ─────────────────────────────────────────────────────────────

    def _parse_json(self, raw_text: str) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Parses JSON content."""
        clean_text = raw_text.strip()
        # Strip markdown ```json ... ``` wrapper if present
        if clean_text.startswith("```"):
            lines = clean_text.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            clean_text = "\n".join(lines).strip()
        elif not (clean_text.startswith("{") or clean_text.startswith("[")):
            # Find outermost brackets
            fb = clean_text.find('{')
            fsq = clean_text.find('[')
            start = -1
            if fb != -1 and fsq != -1:
                start = min(fb, fsq)
            elif fb != -1:
                start = fb
            elif fsq != -1:
                start = fsq
            if start != -1:
                end = max(clean_text.rfind('}'), clean_text.rfind(']'))
                if end > start:
                    clean_text = clean_text[start:end+1]

        data = json.loads(clean_text)
        scenes = extract_scenes_from_json(data)
        normalized_scenes = self._normalize_scenes(scenes)

        metadata = data if isinstance(data, dict) else {"scenes": data}
        return normalized_scenes, metadata

    def _parse_srt(self, raw_text: str) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Parses SRT subtitle content."""
        normalized = raw_text.replace("\r\n", "\n").replace("\r", "\n").strip()
        blocks = re.split(r"\n{2,}", normalized)

        scenes: List[Dict[str, Any]] = []

        for b_idx, block in enumerate(blocks, 1):
            lines = [ln.strip() for ln in block.split("\n") if ln.strip()]
            if not lines:
                continue

            # Strip leading sequence index if present
            if lines[0].isdigit():
                scene_num = int(lines[0])
                lines = lines[1:]
            else:
                scene_num = b_idx

            if not lines:
                continue

            tc_match = self.SRT_TIMECODE_REGEX.search(lines[0])
            if not tc_match:
                continue

            time_start_str = tc_match.group(1).replace(".", ",")
            time_end_str = tc_match.group(2).replace(".", ",")
            text_lines = lines[1:]
            dialogue_text = " ".join(text_lines).strip()

            start_sec = srt_time_to_seconds(time_start_str)
            end_sec = srt_time_to_seconds(time_end_str)
            duration = max(0.5, round(end_sec - start_sec, 2))

            pk, sk = extract_keywords_from_text(dialogue_text)

            scenes.append({
                "id": scene_num,
                "time_start": time_start_str,
                "time_end": time_end_str,
                "duration_seconds": duration,
                "dialogue_es": dialogue_text,
                "dialogue": dialogue_text,
                "primary_keywords": pk,
                "secondary_keywords": sk,
            })

        return self._normalize_scenes(scenes), {"type": "srt", "total_subtitles": len(scenes)}

    def _parse_txt(self, raw_text: str) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Parses Plain Text scripts.
        Supports:
        - Structured markers: "Cảnh 1:", "Scene 1:", "Phần 1:", "[1]", "1."
        - Inline duration: "[00:00 - 00:05]", "(4s)", "[5s]"
        - Inline keywords: "| Từ khóa: ...", "| Keywords: ..."
        - Paragraph-by-paragraph or line-by-line fallback.
        """
        lines = [ln.strip() for ln in raw_text.splitlines() if ln.strip()]
        if not lines:
            return [], {}

        scenes: List[Dict[str, Any]] = []
        cumulative_time = 0.0

        # Pattern for scene markers e.g. "Cảnh 1:", "Scene 2 -", "Phân đoạn 3:"
        scene_heading_re = re.compile(
            r"^(?:cảnh|scene|phần|phân đoạn|segment|broll|shot)\s*(\d+)[:\s\-—]*(.*)$",
            re.IGNORECASE
        )
        numbered_re = re.compile(r"^(\d+)[\.\)\]]\s+(.*)$")

        for idx, line in enumerate(lines, 1):
            if line.startswith("#") or line.startswith("//"):
                continue
            scene_id = idx
            content = line
            duration_val = 0.0
            time_start_str = ""
            time_end_str = ""
            primary_kws: List[str] = []
            secondary_kws: List[str] = []

            # 1. Check Scene Heading
            m_scene = scene_heading_re.match(content)
            if m_scene:
                try:
                    scene_id = int(m_scene.group(1))
                except ValueError:
                    scene_id = idx
                content = m_scene.group(2).strip()
            else:
                m_num = numbered_re.match(content)
                if m_num:
                    try:
                        scene_id = int(m_num.group(1))
                    except ValueError:
                        scene_id = idx
                    content = m_num.group(2).strip()

            # 2. Extract inline timestamps: e.g. [00:00 - 00:05] or [00:00:01 --> 00:00:06]
            tc_range_match = re.search(r"[\[\(](\d{1,2}:\d{2}(?::\d{2})?)\s*(?:[-–—]|-->)\s*(\d{1,2}:\d{2}(?::\d{2})?)[\]\)]", content)
            if tc_range_match:
                time_start_str = tc_range_match.group(1)
                time_end_str = tc_range_match.group(2)
                t_start = srt_time_to_seconds(time_start_str)
                t_end = srt_time_to_seconds(time_end_str)
                if t_end > t_start:
                    duration_val = round(t_end - t_start, 2)
                content = content[:tc_range_match.start()] + content[tc_range_match.end():]
                content = content.strip()

            # 3. Extract inline duration: e.g. [4s], (5.5s), [duration: 4s]
            dur_match = re.search(r"[\[\(](?:thời lượng|duration:?)?\s*(\d+(?:\.\d+)?)\s*(?:s|sec|giây)?[\]\)]", content, re.IGNORECASE)
            if dur_match and duration_val <= 0:
                try:
                    duration_val = float(dur_match.group(1))
                except ValueError:
                    pass
                content = content[:dur_match.start()] + content[dur_match.end():]
                content = content.strip()

            # 4. Extract inline keywords: e.g. "| Từ khóa: mèo, thú cưng" or "| Keywords: cat, kitten"
            kw_match = re.search(r"(?:\||;|\b)(?:từ khóa|tu khoa|keywords|tags|search):\s*([^\|;\n]+)", content, re.IGNORECASE)
            if kw_match:
                kw_str = kw_match.group(1).strip()
                kws = [k.strip() for k in re.split(r"[,/|;]", kw_str) if k.strip()]
                primary_kws = kws[:3]
                secondary_kws = kws[3:6]
                content = content[:kw_match.start()] + content[kw_match.end():]
                content = content.strip(" -—:|;")

            # 5. Fallback duration calculation based on dialogue word count
            words = content.split()
            if duration_val <= 0:
                # Average reading speed ~ 2.5 words/sec, minimum 3.0s, default 4.0s
                word_dur = round(len(words) / 2.5, 1)
                duration_val = max(3.0, min(15.0, word_dur if len(words) > 6 else 4.0))

            # 6. Cumulative timestamps if none provided
            if not time_start_str or not time_end_str:
                time_start_str = format_seconds_to_timecode(cumulative_time)
                cumulative_time += duration_val
                time_end_str = format_seconds_to_timecode(cumulative_time)
            else:
                cumulative_time = srt_time_to_seconds(time_end_str)

            # 7. Fallback keywords from dialogue
            if not primary_kws and not secondary_kws:
                primary_kws, secondary_kws = extract_keywords_from_text(content)

            scenes.append({
                "id": scene_id,
                "time_start": time_start_str,
                "time_end": time_end_str,
                "duration_seconds": duration_val,
                "dialogue_es": content,
                "dialogue": content,
                "primary_keywords": primary_kws,
                "secondary_keywords": secondary_kws,
            })

        return self._normalize_scenes(scenes), {"type": "txt", "total_lines": len(lines)}

    def _parse_csv(self, raw_text: str) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Parses CSV and TSV spreadsheet text."""
        # Detect delimiter
        first_line = raw_text.splitlines()[0] if raw_text.splitlines() else ""
        delimiter = "\t" if "\t" in first_line else (";" if ";" in first_line and "," not in first_line else ",")

        reader = csv.reader(io.StringIO(raw_text), delimiter=delimiter)
        rows: List[List[Any]] = []
        for r in reader:
            if any(cell.strip() for cell in r):
                rows.append([cell.strip() for cell in r])

        scenes = self._map_table_rows_to_scenes(rows)
        return self._normalize_scenes(scenes), {"type": "csv", "delimiter": delimiter}

    def _parse_excel_file(self, file_path: Path) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Parses Excel (.xlsx, .xls) workbook into scenes.
        Uses openpyxl when available with fallback to XML parsing.
        """
        rows: List[List[Any]] = []

        try:
            import openpyxl  # type: ignore
            wb = openpyxl.load_workbook(file_path, data_only=True)
            sheet = wb.active
            for row in sheet.iter_rows(values_only=True):
                if any(c is not None and str(c).strip() != "" for c in row):
                    cleaned_row = [str(c).strip() if c is not None else "" for c in row]
                    rows.append(cleaned_row)
        except Exception:
            # Fallback pure-python parser for xlsx
            rows = self._parse_xlsx_xml_fallback(file_path)

        scenes = self._map_table_rows_to_scenes(rows)
        return self._normalize_scenes(scenes), {"type": "excel", "total_rows": len(rows)}

    def _parse_xlsx_xml_fallback(self, file_path: Path) -> List[List[Any]]:
        """Fallback zero-dependency XLSX parser using standard zipfile and xml."""
        rows: List[List[Any]] = []
        try:
            with zipfile.ZipFile(file_path, "r") as z:
                shared_strings = []
                if "xl/sharedStrings.xml" in z.namelist():
                    root = ET.fromstring(z.read("xl/sharedStrings.xml"))
                    for si in root.findall(".//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}si"):
                        t_nodes = si.findall(".//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t")
                        shared_strings.append("".join(t.text or "" for t in t_nodes))

                sheet_name = next((n for n in z.namelist() if n.startswith("xl/worksheets/sheet")), None)
                if not sheet_name:
                    return rows

                sheet_root = ET.fromstring(z.read(sheet_name))
                for row_el in sheet_root.findall(".//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}row"):
                    row_cells = []
                    for c in row_el.findall("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}c"):
                        val = ""
                        v = c.find("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}v")
                        if v is not None and v.text:
                            val = v.text
                        t_attr = c.get("t")
                        if t_attr == "s" and val.isdigit() and int(val) < len(shared_strings):
                            val = shared_strings[int(val)]
                        elif t_attr == "inlineStr" or not val:
                            t_node = c.find(".//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t")
                            if t_node is not None and t_node.text:
                                val = t_node.text
                        row_cells.append(val.strip())
                    if any(c for c in row_cells):
                        rows.append(row_cells)
        except Exception:
            pass
        return rows

    # ─────────────────────────────────────────────────────────────
    # Intelligent Table Row Mapper
    # ─────────────────────────────────────────────────────────────

    def _map_table_rows_to_scenes(self, rows: List[List[Any]]) -> List[Dict[str, Any]]:
        """
        Maps a 2D matrix of table rows into structured scene dictionaries.
        Supports fuzzy matching for Vietnamese and English column headers.
        """
        if not rows:
            return []

        # Find header row
        header_row_idx = -1
        col_map: Dict[str, int] = {}

        header_aliases = {
            "id": ["id", "cảnh", "canh", "phân đoạn", "phan doan", "stt", "scene", "scene_id", "no", "segment", "số", "index"],
            "dialogue": ["dialogue", "dialogue_es", "lời thoại", "loi thoai", "thoại", "thoai", "nội dung", "noi dung",
                         "kịch bản", "kich ban", "mô tả", "mo ta", "text", "script", "content", "prompt", "description", "lời bình"],
            "keywords": ["keywords", "primary_keywords", "từ khóa", "tu khoa", "tags", "nhãn", "search_terms", "broll", "b-roll", "stock"],
            "secondary_keywords": ["secondary_keywords", "từ khóa phụ", "tu khoa phu", "tags_2", "sub_keywords"],
            "time_start": ["time_start", "start", "bắt đầu", "bat dau", "start_time"],
            "time_end": ["time_end", "end", "kết thúc", "ket thuc", "end_time"],
            "duration": ["duration", "duration_seconds", "thời lượng", "thoi luong", "thời gian", "thoi gian", "length", "sec", "giây"]
        }

        for idx, row in enumerate(rows[:5]):
            found_cols = {}
            for col_idx, cell in enumerate(row):
                cell_clean = str(cell).lower().strip()
                for field, aliases in header_aliases.items():
                    if any(cell_clean == alias or (len(alias) > 3 and alias in cell_clean) for alias in aliases):
                        if field not in found_cols:
                            found_cols[field] = col_idx
                            break
            # If we matched at least dialogue or (id and keywords)
            if "dialogue" in found_cols or (len(found_cols) >= 2):
                header_row_idx = idx
                col_map = found_cols
                break

        # If no recognized header found, use positional fallback
        data_rows = rows[header_row_idx + 1:] if header_row_idx != -1 else rows
        if not col_map and data_rows:
            sample_col_count = len(data_rows[0])
            if sample_col_count == 1:
                col_map = {"dialogue": 0}
            elif sample_col_count == 2:
                # If col 0 is numeric, col 0 is id, col 1 is dialogue; else col 0 dialogue, col 1 keywords
                is_num = str(data_rows[0][0]).strip().isdigit()
                if is_num:
                    col_map = {"id": 0, "dialogue": 1}
                else:
                    col_map = {"dialogue": 0, "keywords": 1}
            elif sample_col_count == 3:
                col_map = {"id": 0, "dialogue": 1, "keywords": 2}
            else:
                col_map = {"id": 0, "dialogue": 1, "keywords": 2, "duration": 3}

        scenes: List[Dict[str, Any]] = []
        cumulative_time = 0.0

        for r_idx, row in enumerate(data_rows, 1):
            if not row or not any(str(c).strip() for c in row):
                continue

            def get_val(key: str) -> str:
                idx = col_map.get(key)
                if idx is not None and 0 <= idx < len(row):
                    return str(row[idx]).strip()
                return ""

            raw_id = get_val("id")
            scene_id = raw_id if raw_id else r_idx

            dialogue = get_val("dialogue")
            if not dialogue and len(row) > 0:
                # If dialogue column empty, take first non-empty text column
                dialogue = next((str(c).strip() for c in row if str(c).strip() and not str(c).strip().isdigit()), "")

            kw_val = get_val("keywords")
            if kw_val:
                kws = [k.strip() for k in re.split(r"[,/|;\n]", kw_val) if k.strip()]
                primary_kws = kws[:3]
                secondary_kws = kws[3:6]
            else:
                primary_kws, secondary_kws = extract_keywords_from_text(dialogue)

            sk_val = get_val("secondary_keywords")
            if sk_val:
                extra_sk = [k.strip() for k in re.split(r"[,/|;\n]", sk_val) if k.strip()]
                secondary_kws.extend(extra_sk)

            dur_val = parse_duration_to_seconds(get_val("duration"))
            if dur_val <= 0:
                words = dialogue.split()
                dur_val = max(3.0, min(15.0, round(len(words) / 2.5, 1) if len(words) > 6 else 4.0))

            t_start = get_val("time_start")
            t_end = get_val("time_end")
            if not t_start or not t_end:
                t_start = format_seconds_to_timecode(cumulative_time)
                cumulative_time += dur_val
                t_end = format_seconds_to_timecode(cumulative_time)
            else:
                cumulative_time = srt_time_to_seconds(t_end)

            extra_data = {}
            for c_idx, cell in enumerate(row):
                if c_idx not in col_map.values():
                    extra_data[f"col_{c_idx}"] = str(cell).strip()

            scenes.append({
                "id": scene_id,
                "time_start": t_start,
                "time_end": t_end,
                "duration_seconds": dur_val,
                "dialogue_es": dialogue,
                "dialogue": dialogue,
                "primary_keywords": primary_kws,
                "secondary_keywords": secondary_kws,
                **extra_data
            })

        return scenes

    # ─────────────────────────────────────────────────────────────
    # Internal Utilities
    # ─────────────────────────────────────────────────────────────

    def _normalize_scenes(self, scenes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Ensures all scenes have standard schema expected by studio timeline and downloader."""
        normalized = []
        for idx, sc in enumerate(scenes, 1):
            if not isinstance(sc, dict):
                continue

            sid = sc.get("id")
            if sid is None or str(sid).strip() == "":
                sid = idx

            dialogue = str(sc.get("dialogue_es") or sc.get("dialogue") or sc.get("text") or sc.get("description") or "").strip()

            pk = sc.get("primary_keywords") or []
            sk = sc.get("secondary_keywords") or []
            if isinstance(pk, str):
                pk = [k.strip() for k in re.split(r"[,/|;]", pk) if k.strip()]
            if isinstance(sk, str):
                sk = [k.strip() for k in re.split(r"[,/|;]", sk) if k.strip()]

            if not pk and not sk:
                pk, sk = extract_keywords_from_text(dialogue)

            dur = parse_duration_to_seconds(sc.get("duration_seconds") or sc.get("duration") or 0.0)
            if dur <= 0:
                words = dialogue.split()
                dur = max(3.0, min(15.0, round(len(words) / 2.5, 1) if len(words) > 6 else 4.0))

            t_start = str(sc.get("time_start") or "")
            t_end = str(sc.get("time_end") or "")

            item = dict(sc)
            item["id"] = sid
            item["dialogue_es"] = dialogue
            item["dialogue"] = dialogue
            item["duration_seconds"] = dur
            item["time_start"] = t_start
            item["time_end"] = t_end
            item["primary_keywords"] = pk
            item["secondary_keywords"] = sk
            normalized.append(item)

        return normalized

    def _sniff_format(self, text: str) -> str:
        """Heuristically detects whether raw string is JSON, SRT, CSV, or TXT."""
        clean = text.strip()
        if (clean.startswith("{") and clean.endswith("}")) or (clean.startswith("[") and clean.endswith("]")):
            return "json"
        if "```json" in clean:
            return "json"
        if self.SRT_TIMECODE_REGEX.search(clean):
            return "srt"
        lines = clean.splitlines()
        if len(lines) >= 2:
            first = lines[0]
            if first.count(",") >= 2 or first.count(";") >= 2 or first.count("\t") >= 1:
                return "csv"
        return "txt"

    def _read_text_with_encoding_fallback(self, path: Path) -> str:
        """Reads text file with robust encoding detection."""
        for enc in ("utf-8-sig", "utf-8", "cp1258", "latin-1"):
            try:
                return path.read_text(encoding=enc)
            except UnicodeDecodeError:
                continue
        return path.read_text(encoding="utf-8", errors="replace")
