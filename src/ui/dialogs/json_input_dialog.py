"""
Dialog for importing Claude AI JSON scripts via pasting, choosing files, or merging parts.
"""

import json
from pathlib import Path
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPlainTextEdit,
    QPushButton, QTabWidget, QWidget, QFileDialog, QMessageBox, QScrollArea, QFrame
)
from ...core.models.scene import extract_scenes_from_json
from ...core.exceptions import PartMergeError
from ...application.services.part_merger import PartMerger
from ...core.i18n import t
from ..styles.icons import get_svg_icon, get_svg_pixmap
from ..styles.tokens import load_stylesheet


class JsonInputDialog(QDialog):
    """Import JSON scripts from Claude AI."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.result_data = None
        self.selected_file = None
        self.part_textareas = []

        self.setWindowTitle(t("json_input.title"))
        self.setMinimumSize(800, 600)
        self.setStyleSheet(load_stylesheet())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        title_h = QHBoxLayout()
        title_h.setSpacing(8)
        title_icon = QLabel()
        title_icon.setPixmap(get_svg_pixmap("file-text", "#6366f1", 20))
        title_h.addWidget(title_icon)

        title = QLabel(t("json_input.title"))
        title.setStyleSheet("color: #e6edf3; font-size: 16px; font-weight: 700;")
        title_h.addWidget(title)
        title_h.addStretch()
        layout.addLayout(title_h)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, 1)

        # Tab 1: Paste JSON
        paste_tab = QWidget()
        paste_layout = QVBoxLayout(paste_tab)
        paste_layout.setContentsMargins(15, 15, 15, 15)
        paste_label = QLabel("Dán nội dung kịch bản JSON vào ô bên dưới:")
        paste_label.setStyleSheet("color: #e6edf3; font-size: 12px; font-weight: 600;")
        paste_layout.addWidget(paste_label)

        self.text_area = QPlainTextEdit()
        self.text_area.setPlaceholderText('{\n  "scenes": [...]\n}')
        self.text_area.setStyleSheet("font-family: Consolas, monospace; font-size: 11px;")
        paste_layout.addWidget(self.text_area, 1)
        self.tabs.addTab(paste_tab, t("json_input.paste_tab"))
        self.tabs.setTabIcon(0, get_svg_icon("file-text", "#818cf8", 14))

        # Tab 2: File
        file_tab = QWidget()
        file_layout = QVBoxLayout(file_tab)
        file_layout.setContentsMargins(15, 30, 15, 15)
        file_label = QLabel("Chọn file kịch bản JSON đã lưu:")
        file_label.setStyleSheet("color: #e6edf3; font-size: 12px; font-weight: 600;")
        file_layout.addWidget(file_label)

        file_h = QHBoxLayout()
        self.file_path_label = QLabel("Chưa chọn file")
        self.file_path_label.setStyleSheet("color: #7d8590; padding: 8px; background: #0d1117; border-radius: 6px;")
        self.file_path_label.setWordWrap(True)
        file_h.addWidget(self.file_path_label, 1)

        btn_browse = QPushButton(t("json_input.browse_btn"))
        btn_browse.setIcon(get_svg_icon("folder", "#ffffff", 14))
        btn_browse.setFixedWidth(120)
        btn_browse.clicked.connect(self._browse_file)
        file_h.addWidget(btn_browse)
        file_layout.addLayout(file_h)
        file_layout.addStretch()
        self.tabs.addTab(file_tab, t("json_input.file_tab"))
        self.tabs.setTabIcon(1, get_svg_icon("folder", "#818cf8", 14))

        # Tab 3: Merge Parts
        merge_tab = QWidget()
        merge_layout = QVBoxLayout(merge_tab)
        merge_layout.setContentsMargins(15, 10, 15, 10)
        merge_layout.setSpacing(8)

        merge_title = QLabel(t("json_input.merge_title"))
        merge_title.setStyleSheet("color: #e6edf3; font-size: 13px; font-weight: 700;")
        merge_layout.addWidget(merge_title)

        merge_help = QLabel(
            "Dán từng phần kịch bản vào các ô bên dưới.\n"
            "Ứng dụng sẽ tự động sắp xếp theo thứ tự và ghép nối thành một kịch bản hoàn chỉnh."
        )
        merge_help.setStyleSheet("color: #7d8590; font-size: 11px;")
        merge_help.setWordWrap(True)
        merge_layout.addWidget(merge_help)

        parts_scroll = QScrollArea()
        parts_scroll.setWidgetResizable(True)
        parts_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self.parts_container = QWidget()
        self.parts_layout = QVBoxLayout(self.parts_container)
        self.parts_layout.setContentsMargins(0, 0, 0, 0)
        self.parts_layout.setSpacing(8)
        self.parts_layout.addStretch()

        parts_scroll.setWidget(self.parts_container)
        merge_layout.addWidget(parts_scroll, 1)

        toolbar_h = QHBoxLayout()
        btn_add_part = QPushButton(t("json_input.add_part"))
        btn_add_part.setIcon(get_svg_icon("plus", "#ffffff", 14))
        btn_add_part.setFixedHeight(32)
        btn_add_part.clicked.connect(self._add_part_textarea)
        toolbar_h.addWidget(btn_add_part)

        btn_clear_all = QPushButton(t("json_input.clear_all"))
        btn_clear_all.setIcon(get_svg_icon("trash", "#ffffff", 14))
        btn_clear_all.setObjectName("dangerBtn")
        btn_clear_all.setFixedHeight(32)
        btn_clear_all.clicked.connect(self._clear_all_parts)
        toolbar_h.addWidget(btn_clear_all)

        toolbar_h.addStretch()
        self.merge_status_label = QLabel("0 phần sẵn sàng")
        self.merge_status_label.setStyleSheet("color: #7d8590; font-size: 11px;")
        toolbar_h.addWidget(self.merge_status_label)
        merge_layout.addLayout(toolbar_h)

        self.tabs.addTab(merge_tab, t("json_input.merge_tab"))
        self.tabs.setTabIcon(2, get_svg_icon("workflow", "#818cf8", 14))
        self._add_part_textarea()
        self._add_part_textarea()

        # Bottom buttons
        btn_h = QHBoxLayout()
        btn_h.addStretch()
        btn_cancel = QPushButton(t("common.cancel"))
        btn_cancel.setFixedWidth(100)
        btn_cancel.clicked.connect(self.reject)
        btn_h.addWidget(btn_cancel)

        btn_load = QPushButton(t("json_input.load_btn"))
        btn_load.setIcon(get_svg_icon("check", "#ffffff", 14))
        btn_load.setObjectName("primaryBtn")
        btn_load.setFixedWidth(140)
        btn_load.setFixedHeight(40)
        btn_load.clicked.connect(self._load)
        btn_h.addWidget(btn_load)

        layout.addLayout(btn_h)

    def _browse_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Chọn JSON", "", "JSON Files (*.json);;All Files (*.*)"
        )
        if path:
            self.selected_file = path
            self.file_path_label.setText(path)
            self.file_path_label.setStyleSheet("color: #4ec9b0; padding: 8px; background: #0d1117; border-radius: 6px; font-weight: 600;")

    def _add_part_textarea(self):
        part_index = len(self.part_textareas)
        part_number = part_index + 1

        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background-color: #161b22;
                border: 1px solid #21262d;
                border-radius: 6px;
            }
        """)
        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(8, 8, 8, 8)
        frame_layout.setSpacing(4)

        header_h = QHBoxLayout()
        header_h.setSpacing(8)

        part_icon = QLabel()
        part_icon.setPixmap(get_svg_pixmap("file-text", "#818cf8", 14))
        header_h.addWidget(part_icon)

        label = QLabel(f"Phần {part_number}")
        label.setStyleSheet("color: #e6edf3; font-size: 11px; font-weight: 600;")
        header_h.addWidget(label)

        status_label = QLabel("(trống)")
        status_label.setStyleSheet("color: #7d8590; font-size: 10px;")
        header_h.addWidget(status_label)
        header_h.addStretch()

        btn_clear = QPushButton()
        btn_clear.setIcon(get_svg_icon("trash", "#cbd5e1", 12))
        btn_clear.setFixedSize(24, 24)
        btn_clear.setToolTip("Xóa nội dung phần này")
        header_h.addWidget(btn_clear)

        btn_remove = QPushButton(t("common.delete"))
        btn_remove.setFixedHeight(24)
        btn_remove.setToolTip("Xóa phần này")
        header_h.addWidget(btn_remove)
        frame_layout.addLayout(header_h)

        textarea = QPlainTextEdit()
        textarea.setPlaceholderText(
            f"Dán nội dung Phần {part_number} vào đây...\n"
            f"(hỗ trợ cả định dạng khối mã hoặc văn bản JSON thuần)"
        )
        textarea.setStyleSheet("""
            QPlainTextEdit {
                background-color: #0d1117;
                color: #c9d1d9;
                border: 1px solid #21262d;
                border-radius: 4px;
                padding: 6px;
                font-family: Consolas, monospace;
                font-size: 10px;
            }
            QPlainTextEdit:focus {
                border-color: #1f6feb;
            }
        """)
        textarea.setMinimumHeight(120)
        textarea.setMaximumHeight(150)
        frame_layout.addWidget(textarea)

        btn_clear.clicked.connect(lambda: textarea.clear())
        btn_remove.clicked.connect(lambda: self._remove_part_textarea(frame))
        textarea.textChanged.connect(lambda: self._update_part_status(textarea, status_label, label))

        stretch_idx = self.parts_layout.count() - 1
        self.parts_layout.insertWidget(stretch_idx, frame)

        self.part_textareas.append({
            "frame": frame,
            "textarea": textarea,
            "status_label": status_label,
            "header_label": label
        })

        self._renumber_parts()
        self._update_merge_status()

    def _remove_part_textarea(self, frame):
        if len(self.part_textareas) <= 1:
            QMessageBox.information(self, "Không thể xóa", "Phải giữ lại ít nhất 1 phần.")
            return

        for i, item in enumerate(self.part_textareas):
            if item["frame"] is frame:
                frame.setParent(None)
                frame.deleteLater()
                del self.part_textareas[i]
                break

        self._renumber_parts()
        self._update_merge_status()

    def _renumber_parts(self):
        for i, item in enumerate(self.part_textareas):
            part_num = i + 1
            item["header_label"].setText(f"Phần {part_num}")
            item["textarea"].setPlaceholderText(f"Dán nội dung Phần {part_num} vào đây...")

    def _update_part_status(self, textarea, status_label, header_label):
        text = textarea.toPlainText().strip()
        if not text:
            status_label.setText("(trống)")
            status_label.setStyleSheet("color: #7d8590; font-size: 10px;")
            header_label.setStyleSheet("color: #e6edf3; font-size: 11px; font-weight: 600;")
        else:
            try:
                data = PartMerger.parse_part_text(text, "tmp")
                meta = data.get("_part_metadata", {})
                scenes = data.get("scenes", [])
                part_num = meta.get("part_number", "?")
                total_parts = meta.get("total_parts", "?")
                status_label.setText(f"[OK] Phần {part_num}/{total_parts} • {len(scenes)} cảnh")
                status_label.setStyleSheet("color: #4ec9b0; font-size: 10px; font-weight: 600;")
                header_label.setStyleSheet("color: #4ec9b0; font-size: 11px; font-weight: 700;")
            except PartMergeError as e:
                status_label.setText(f"[LỖI] {str(e)[:60]}")
                status_label.setStyleSheet("color: #f85149; font-size: 10px;")
                header_label.setStyleSheet("color: #f85149; font-size: 11px; font-weight: 600;")

        self._update_merge_status()

    def _update_merge_status(self):
        valid_parts = []
        total_scenes = 0
        for item in self.part_textareas:
            text = item["textarea"].toPlainText().strip()
            if not text:
                continue
            try:
                data = PartMerger.parse_part_text(text, "tmp")
                meta = data.get("_part_metadata", {})
                scenes = data.get("scenes", [])
                valid_parts.append(meta.get("part_number", 0))
                total_scenes += len(scenes)
            except PartMergeError:
                pass

        if not valid_parts:
            self.merge_status_label.setText("0 phần sẵn sàng")
            self.merge_status_label.setStyleSheet("color: #7d8590; font-size: 11px;")
        else:
            self.merge_status_label.setText(f"[OK] {len(valid_parts)} phần sẵn sàng • {total_scenes} cảnh")
            self.merge_status_label.setStyleSheet("color: #4ec9b0; font-size: 11px; font-weight: 600;")

    def _clear_all_parts(self):
        if not any(item["textarea"].toPlainText().strip() for item in self.part_textareas):
            return

        reply = QMessageBox.question(
            self, t("common.confirm"), "Xóa nội dung tất cả các phần?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            for item in self.part_textareas:
                item["textarea"].clear()

    def _load(self):
        try:
            current_tab = self.tabs.currentIndex()
            if current_tab == 0:
                text = self.text_area.toPlainText().strip()
                if not text:
                    QMessageBox.warning(self, "Chưa nhập", "Vui lòng dán nội dung kịch bản trước khi tiếp tục.")
                    return

                # Auto-strip markdown ```json ... ``` blocks if present
                if text.startswith("```"):
                    lines = text.splitlines()
                    if lines and lines[0].startswith("```"):
                        lines = lines[1:]
                    if lines and lines[-1].strip() == "```":
                        lines = lines[:-1]
                    text = "\n".join(lines).strip()
                elif not (text.startswith("{") or text.startswith("[")):
                    # Extract outermost JSON if surrounded by explanation text
                    first_brace = text.find('{')
                    first_bracket = text.find('[')
                    start_idx = -1
                    if first_brace != -1 and first_bracket != -1:
                        start_idx = min(first_brace, first_bracket)
                    elif first_brace != -1:
                        start_idx = first_brace
                    elif first_bracket != -1:
                        start_idx = first_bracket

                    if start_idx != -1:
                        last_brace = text.rfind('}')
                        last_bracket = text.rfind(']')
                        end_idx = max(last_brace, last_bracket)
                        if end_idx > start_idx:
                            text = text[start_idx:end_idx + 1].strip()

                if not (text.startswith("{") or text.startswith("[")):
                    QMessageBox.critical(
                        self, "Định dạng không hợp lệ",
                        f"Nội dung kịch bản phải bắt đầu bằng '{{' hoặc '['\n\nNội dung bắt đầu bằng: '{text[:50]}...'"
                    )
                    return
                try:
                    self.result_data = json.loads(text)
                except json.JSONDecodeError as e:
                    QMessageBox.critical(self, "Định dạng không hợp lệ", f"Không đọc được nội dung kịch bản:\n{e}")
                    return
            elif current_tab == 1:
                if not self.selected_file:
                    QMessageBox.warning(self, "Chưa chọn file", "Vui lòng chọn file kịch bản trước khi tiếp tục.")
                    return
                try:
                    with open(self.selected_file, 'r', encoding='utf-8') as f:
                        self.result_data = json.load(f)
                except Exception as e:
                    QMessageBox.critical(self, t("common.error"), f"Không đọc được file:\n{e}")
                    return
            elif current_tab == 2:
                part_texts = []
                for i, item in enumerate(self.part_textareas):
                    text = item["textarea"].toPlainText().strip()
                    if text:
                        part_texts.append((f"Phần {i+1}", text))

                if not part_texts:
                    QMessageBox.warning(self, "Chưa nhập", "Vui lòng dán nội dung cho ít nhất 1 phần.")
                    return

                try:
                    self.result_data = PartMerger.merge_from_texts(part_texts)
                    total = self.result_data.get("total_scenes", 0)
                    parts_count = self.result_data.get("_merge_info", {}).get("parts_count", 0)
                    QMessageBox.information(
                        self, t("json_input.merge_success"),
                        f"Đã ghép thành công {parts_count} phần thành {total} cảnh!\n\nNhấn Đồng ý để nạp vào hệ thống."
                    )
                except PartMergeError as e:
                    QMessageBox.critical(self, t("json_input.merge_error"), f"Không ghép được kịch bản:\n\n{e}")
                    return

            scenes = extract_scenes_from_json(self.result_data)
            if not scenes:
                QMessageBox.critical(self, "Định dạng không hợp lệ", "Không tìm thấy danh sách cảnh trong kịch bản.")
                self.result_data = None
                return

            self.accept()
        except Exception as e:
            QMessageBox.critical(self, t("common.error"), f"{type(e).__name__}: {e}")
