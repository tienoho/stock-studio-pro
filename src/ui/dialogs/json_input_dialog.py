"""
Dialog for importing Claude AI JSON scripts via pasting, choosing files, or merging parts.
"""

import json
from pathlib import Path
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPlainTextEdit,
    QPushButton, QTabWidget, QWidget, QFileDialog, QMessageBox, QScrollArea, QFrame,
    QButtonGroup, QMenu
)
from PyQt6.QtGui import QGuiApplication
from ...core.models.scene import extract_scenes_from_json
from ...core.exceptions import PartMergeError
from ...application.services.part_merger import PartMerger
from ...application.services.script_parser_service import ScriptParserService
from ...application.services.script_template_service import ScriptTemplateService
from ...core.i18n import t
from ..styles.icons import get_svg_icon, get_svg_pixmap
from ..styles.tokens import load_stylesheet
from ..styles.ui_enhancer import enhance_widget_interactions, format_tooltip
from ..components.toast_notification import ToastNotification


class JsonInputDialog(QDialog):
    """Import JSON scripts from Claude AI."""

    def __init__(self, parent=None, initial_tab: int = 0):
        super().__init__(parent)
        self.result_data = None
        self.selected_file = None
        self.part_textareas = []
        self._active_prompt_key = "json"

        self.setWindowTitle(t("json_input.title"))
        self.setMinimumSize(880, 680)
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
        title.setObjectName("heroTitle")
        title_h.addWidget(title)
        title_h.addStretch()
        layout.addLayout(title_h)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, 1)

        # Tab 1: Paste JSON
        paste_tab = QWidget()
        paste_layout = QVBoxLayout(paste_tab)
        paste_layout.setContentsMargins(15, 15, 15, 15)
        paste_layout.setSpacing(8)
        paste_label = QLabel("Dán nội dung kịch bản (JSON, Văn bản TXT, Phụ đề SRT, hoặc CSV/TSV):")
        paste_label.setObjectName("fieldLabel")
        paste_layout.addWidget(paste_label)

        self.text_area = QPlainTextEdit()
        self.text_area.setPlaceholderText(
            '{\n  "scenes": [...]\n}\n'
            '-- HOẶC VĂN BẢN (TXT) --\n'
            'Cảnh 1: Lời thoại giới thiệu... | Từ khóa: vlog, công nghệ\n'
            'Cảnh 2 (5s): Đánh giá chi tiết tính năng\n'
            '-- HOẶC PHỤ ĐỀ (SRT) --\n'
            '1\n00:00:01,000 --> 00:00:05,000\nLời thoại phân đoạn video'
        )
        self.text_area.setStyleSheet("font-family: Consolas, monospace; font-size: 11px;")
        paste_layout.addWidget(self.text_area, 1)

        paste_actions = QHBoxLayout()
        paste_actions.setSpacing(6)
        btn_paste_json = QPushButton("✨ Mẫu JSON")
        btn_paste_json.setObjectName("secondaryBtn")
        btn_paste_json.setToolTip("Điền kịch bản JSON mẫu 3 cảnh vào ô dán")
        btn_paste_json.clicked.connect(lambda: self._load_sample_into_paste("json"))
        paste_actions.addWidget(btn_paste_json)

        btn_paste_txt = QPushButton("📄 Mẫu TXT")
        btn_paste_txt.setObjectName("secondaryBtn")
        btn_paste_txt.setToolTip("Điền kịch bản văn bản mẫu 3 cảnh vào ô dán")
        btn_paste_txt.clicked.connect(lambda: self._load_sample_into_paste("txt"))
        paste_actions.addWidget(btn_paste_txt)

        btn_paste_srt = QPushButton("💬 Mẫu SRT")
        btn_paste_srt.setObjectName("secondaryBtn")
        btn_paste_srt.setToolTip("Điền phụ đề SRT mẫu 3 phân cảnh vào ô dán")
        btn_paste_srt.clicked.connect(lambda: self._load_sample_into_paste("srt"))
        paste_actions.addWidget(btn_paste_srt)

        paste_actions.addStretch()

        btn_clear_text = QPushButton("Xóa Trắng")
        btn_clear_text.setIcon(get_svg_icon("trash", "#cbd5e1", 12))
        btn_clear_text.setObjectName("secondaryBtn")
        btn_clear_text.clicked.connect(self.text_area.clear)
        paste_actions.addWidget(btn_clear_text)
        paste_layout.addLayout(paste_actions)

        self.tabs.addTab(paste_tab, t("json_input.paste_tab"))
        self.tabs.setTabIcon(0, get_svg_icon("file-text", "#818cf8", 14))

        # Tab 2: File
        file_tab = QWidget()
        file_layout = QVBoxLayout(file_tab)
        file_layout.setContentsMargins(15, 20, 15, 15)
        file_layout.setSpacing(12)
        file_label = QLabel("Chọn tệp kịch bản (JSON, TXT, SRT, Excel XLSX/XLS, CSV/TSV):")
        file_label.setObjectName("fieldLabel")
        file_layout.addWidget(file_label)

        file_h = QHBoxLayout()
        self.file_path_label = QLabel("Chưa chọn file")
        self.file_path_label.setStyleSheet("color: #94a3b8; padding: 8px 12px; background: #0c101a; border: 1px solid #1f2b3f; border-radius: 8px; font-weight: 600;")
        self.file_path_label.setWordWrap(True)
        file_h.addWidget(self.file_path_label, 1)

        btn_browse = QPushButton(t("json_input.browse_btn"))
        btn_browse.setObjectName("secondaryBtn")
        btn_browse.setIcon(get_svg_icon("folder", "#ffffff", 14))
        btn_browse.setFixedWidth(120)
        btn_browse.setFixedHeight(34)
        btn_browse.setToolTip(format_tooltip("Chọn tệp kịch bản (JSON, TXT, SRT, Excel, CSV)"))
        btn_browse.clicked.connect(self._browse_file)
        file_h.addWidget(btn_browse)
        file_layout.addLayout(file_h)

        file_actions_h = QHBoxLayout()
        btn_dl_template = QPushButton("📥 Tải Tệp Mẫu Về Máy...")
        btn_dl_template.setObjectName("secondaryBtn")
        btn_dl_template.setIcon(get_svg_icon("download", "#38bdf8", 13))
        btn_dl_template.setToolTip("Tải các tệp mẫu Excel, CSV, TXT, SRT hoặc JSON về máy để điền dữ liệu")
        btn_dl_template.clicked.connect(self._export_single_template_dialog)
        file_actions_h.addWidget(btn_dl_template)
        file_actions_h.addStretch()
        file_layout.addLayout(file_actions_h)

        file_layout.addStretch()
        self.tabs.addTab(file_tab, t("json_input.file_tab"))
        self.tabs.setTabIcon(1, get_svg_icon("folder", "#818cf8", 14))

        # Tab 3: Merge Parts
        merge_tab = QWidget()
        merge_layout = QVBoxLayout(merge_tab)
        merge_layout.setContentsMargins(15, 10, 15, 10)
        merge_layout.setSpacing(8)

        merge_title = QLabel(t("json_input.merge_title"))
        merge_title.setObjectName("sectionHeader")
        merge_layout.addWidget(merge_title)

        merge_help = QLabel(
            "Dán từng phần kịch bản vào các ô bên dưới.\n"
            "Ứng dụng sẽ tự động sắp xếp theo thứ tự và ghép nối thành một kịch bản hoàn chỉnh."
        )
        merge_help.setObjectName("mutedText")
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
        btn_add_part.setObjectName("secondaryBtn")
        btn_add_part.setIcon(get_svg_icon("plus", "#ffffff", 14))
        btn_add_part.setFixedHeight(34)
        btn_add_part.setToolTip(format_tooltip("Thêm một khung nhập phần kịch bản"))
        btn_add_part.clicked.connect(self._add_part_textarea)
        toolbar_h.addWidget(btn_add_part)

        btn_clear_all = QPushButton(t("json_input.clear_all"))
        btn_clear_all.setIcon(get_svg_icon("trash", "#ffffff", 14))
        btn_clear_all.setObjectName("dangerBtn")
        btn_clear_all.setFixedHeight(34)
        btn_clear_all.setToolTip(format_tooltip("Xóa sạch toàn bộ các phần kịch bản"))
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

        # Tab 4: Mẫu & Gợi Ý AI
        templates_tab = self._build_templates_guide_tab()
        self.tabs.addTab(templates_tab, "Mẫu & Gợi Ý AI")
        self.tabs.setTabIcon(3, get_svg_icon("sparkles", "#a78bfa", 14))

        if 0 < initial_tab < self.tabs.count():
            self.tabs.setCurrentIndex(initial_tab)

        # Bottom buttons
        btn_h = QHBoxLayout()
        btn_h.addStretch()
        btn_cancel = QPushButton(t("common.cancel"))
        btn_cancel.setObjectName("secondaryBtn")
        btn_cancel.setFixedWidth(100)
        btn_cancel.setFixedHeight(36)
        btn_cancel.clicked.connect(self.reject)
        btn_h.addWidget(btn_cancel)

        btn_load = QPushButton(t("json_input.load_btn"))
        btn_load.setIcon(get_svg_icon("check", "#ffffff", 14))
        btn_load.setObjectName("primaryBtn")
        btn_load.setFixedWidth(140)
        btn_load.setFixedHeight(36)
        btn_load.setToolTip(format_tooltip("Nạp và phân tích kịch bản vào studio", "Enter"))
        btn_load.clicked.connect(self._load)
        btn_h.addWidget(btn_load)

        layout.addLayout(btn_h)

        # Apply global interactive UX enhancements
        enhance_widget_interactions(self)

    def _browse_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Chọn Kịch Bản", "", ScriptParserService.get_supported_filter_string()
        )
        if path:
            self.selected_file = path
            self.file_path_label.setText(path)
            self.file_path_label.setStyleSheet("color: #34d399; padding: 8px 12px; background: #0c101a; border: 1px solid #10b981; border-radius: 8px; font-weight: 600;")

    def _add_part_textarea(self):
        part_index = len(self.part_textareas)
        part_number = part_index + 1

        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #131926, stop:1 #0c101a);
                border: 1px solid #1f2b3f;
                border-radius: 10px;
            }
        """)
        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(10, 10, 10, 10)
        frame_layout.setSpacing(6)

        header_h = QHBoxLayout()
        header_h.setSpacing(8)

        part_icon = QLabel()
        part_icon.setPixmap(get_svg_pixmap("file-text", "#818cf8", 14))
        header_h.addWidget(part_icon)

        label = QLabel(f"Phần {part_number}")
        label.setStyleSheet("color: #f8fafc; font-size: 11px; font-weight: 700;")
        header_h.addWidget(label)

        status_label = QLabel("(trống)")
        status_label.setStyleSheet("color: #94a3b8; font-size: 10px; font-weight: 600;")
        header_h.addWidget(status_label)
        header_h.addStretch()

        btn_clear = QPushButton()
        btn_clear.setObjectName("secondaryBtn")
        btn_clear.setIcon(get_svg_icon("trash", "#cbd5e1", 12))
        btn_clear.setFixedSize(28, 28)
        btn_clear.setToolTip(format_tooltip("Xóa nội dung phần này"))
        header_h.addWidget(btn_clear)

        btn_remove = QPushButton(t("common.delete"))
        btn_remove.setObjectName("dangerBtn")
        btn_remove.setFixedHeight(28)
        btn_remove.setToolTip(format_tooltip("Xóa bỏ khung phần này"))
        header_h.addWidget(btn_remove)
        frame_layout.addLayout(header_h)

        textarea = QPlainTextEdit()
        textarea.setPlaceholderText(
            f"Dán nội dung Phần {part_number} vào đây...\n"
            f"(hỗ trợ cả định dạng khối mã hoặc văn bản JSON thuần)"
        )
        textarea.setStyleSheet("""
            QPlainTextEdit {
                background-color: #080b11;
                color: #e2e8f0;
                border: 1px solid #1e293b;
                border-radius: 6px;
                padding: 8px;
                font-family: 'Consolas', 'Cascadia Code', monospace;
                font-size: 11px;
            }
            QPlainTextEdit:focus {
                border-color: #6366f1;
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

        enhance_widget_interactions(frame)
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
            parser = ScriptParserService()
            current_tab = self.tabs.currentIndex()
            if current_tab == 0:
                text = self.text_area.toPlainText().strip()
                if not text:
                    QMessageBox.warning(self, "Chưa nhập", "Vui lòng dán nội dung kịch bản trước khi tiếp tục.")
                    return

                scenes, meta = parser.parse_text(text)
                if not scenes:
                    QMessageBox.critical(self, "Định dạng không hợp lệ", "Không tìm thấy danh sách cảnh hợp lệ trong nội dung đã dán.")
                    return
                self.extracted_scenes = scenes
                self.result_data = meta if isinstance(meta, dict) and meta.get("scenes") else {"scenes": scenes, **meta}

            elif current_tab == 1:
                if not self.selected_file:
                    QMessageBox.warning(self, "Chưa chọn file", "Vui lòng chọn file kịch bản trước khi tiếp tục.")
                    return
                try:
                    scenes, meta = parser.parse_file(self.selected_file)
                    if not scenes:
                        QMessageBox.critical(self, "Định dạng không hợp lệ", "Tệp kịch bản không chứa danh sách phân đoạn hợp lệ.")
                        return
                    self.extracted_scenes = scenes
                    self.result_data = meta if isinstance(meta, dict) and meta.get("scenes") else {"scenes": scenes, **meta}
                except Exception as e:
                    QMessageBox.critical(self, t("common.error"), f"Không đọc được tệp kịch bản:\n{e}")
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

            elif current_tab == 3:
                self._load_sample_into_paste(self._active_prompt_key)
                text = self.text_area.toPlainText().strip()
                scenes, meta = parser.parse_text(text)
                if not scenes:
                    QMessageBox.critical(self, "Định dạng không hợp lệ", "Không tìm thấy danh sách cảnh hợp lệ trong kịch bản mẫu.")
                    return
                self.extracted_scenes = scenes
                self.result_data = meta if isinstance(meta, dict) and meta.get("scenes") else {"scenes": scenes, **meta}

            scenes = getattr(self, "extracted_scenes", None) or extract_scenes_from_json(self.result_data)
            if not scenes:
                QMessageBox.critical(self, "Định dạng không hợp lệ", "Không tìm thấy danh sách cảnh trong kịch bản.")
                self.result_data = None
                return

            self.extracted_scenes = scenes
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, t("common.error"), f"{type(e).__name__}: {e}")

    def _build_templates_guide_tab(self) -> QWidget:
        container = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(12, 12, 16, 16)
        layout.setSpacing(14)

        # 1. Card: Xuất Tệp Mẫu Chuẩn Về Máy
        export_frame = QFrame()
        export_frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #141b2a, stop:1 #0c101a);
                border: 1px solid #1f2b3f;
                border-radius: 10px;
            }
        """)
        ef_layout = QVBoxLayout(export_frame)
        ef_layout.setContentsMargins(14, 12, 14, 12)
        ef_layout.setSpacing(10)

        ef_header = QHBoxLayout()
        ef_icon = QLabel()
        ef_icon.setPixmap(get_svg_pixmap("download", "#38bdf8", 16))
        ef_header.addWidget(ef_icon)
        ef_title = QLabel("1. Tải Tệp Mẫu Kịch Bản Về Máy")
        ef_title.setStyleSheet("font-size: 13px; font-weight: 700; color: #f8fafc;")
        ef_header.addWidget(ef_title)
        ef_header.addStretch()
        ef_layout.addLayout(ef_header)

        ef_desc = QLabel(
            "Tải file mẫu đã được căn chỉnh sẵn cấu trúc về máy để điền kịch bản của bạn. "
            "Sau khi điền, bạn chỉ cần chọn tệp ở tab 'Từ Tệp' hoặc kéo thả trực tiếp vào phần mềm."
        )
        ef_desc.setStyleSheet("color: #94a3b8; font-size: 11px;")
        ef_desc.setWordWrap(True)
        ef_layout.addWidget(ef_desc)

        ef_btns = QHBoxLayout()
        ef_btns.setSpacing(8)

        btn_exp_xlsx = QPushButton("📊 Mẫu Excel (.xlsx)")
        btn_exp_xlsx.setObjectName("secondaryBtn")
        btn_exp_xlsx.setIcon(get_svg_icon("download", "#34d399", 12))
        btn_exp_xlsx.setToolTip("Xuất file mẫu Excel XLSX có sẵn định dạng bảng và ví dụ 3 cảnh")
        btn_exp_xlsx.clicked.connect(lambda: self._export_single_template("xlsx"))
        ef_btns.addWidget(btn_exp_xlsx)

        btn_exp_csv = QPushButton("📋 Mẫu CSV (.csv)")
        btn_exp_csv.setObjectName("secondaryBtn")
        btn_exp_csv.setIcon(get_svg_icon("download", "#38bdf8", 12))
        btn_exp_csv.setToolTip("Xuất file mẫu bảng tính CSV phân cách bằng dấu phẩy")
        btn_exp_csv.clicked.connect(lambda: self._export_single_template("csv"))
        ef_btns.addWidget(btn_exp_csv)

        btn_exp_txt = QPushButton("📄 Mẫu TXT (.txt)")
        btn_exp_txt.setObjectName("secondaryBtn")
        btn_exp_txt.setIcon(get_svg_icon("download", "#cbd5e1", 12))
        btn_exp_txt.setToolTip("Xuất file mẫu văn bản phân đoạn tự do")
        btn_exp_txt.clicked.connect(lambda: self._export_single_template("txt"))
        ef_btns.addWidget(btn_exp_txt)

        btn_exp_srt = QPushButton("💬 Mẫu Phụ Đề (.srt)")
        btn_exp_srt.setObjectName("secondaryBtn")
        btn_exp_srt.setIcon(get_svg_icon("download", "#fbbf24", 12))
        btn_exp_srt.setToolTip("Xuất file mẫu phụ đề phân đoạn thời gian SubRip")
        btn_exp_srt.clicked.connect(lambda: self._export_single_template("srt"))
        ef_btns.addWidget(btn_exp_srt)

        btn_exp_json = QPushButton("✨ Mẫu JSON (.json)")
        btn_exp_json.setObjectName("secondaryBtn")
        btn_exp_json.setIcon(get_svg_icon("download", "#a78bfa", 12))
        btn_exp_json.setToolTip("Xuất file mẫu cấu trúc JSON đầy đủ chi tiết")
        btn_exp_json.clicked.connect(lambda: self._export_single_template("json"))
        ef_btns.addWidget(btn_exp_json)

        ef_btns.addStretch()

        btn_exp_all = QPushButton("📦 Tải Trọn Bộ Mẫu (Thư mục)")
        btn_exp_all.setObjectName("primaryBtn")
        btn_exp_all.setIcon(get_svg_icon("folder", "#ffffff", 12))
        btn_exp_all.setToolTip("Xuất toàn bộ 5 tệp mẫu kèm file hướng dẫn README vào thư mục bạn chọn")
        btn_exp_all.clicked.connect(self._export_all_templates_folder)
        ef_btns.addWidget(btn_exp_all)

        ef_layout.addLayout(ef_btns)
        layout.addWidget(export_frame)

        # 2. Card: Prompt Gợi Ý Cho AI
        prompt_frame = QFrame()
        prompt_frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #141b2a, stop:1 #0c101a);
                border: 1px solid #1f2b3f;
                border-radius: 10px;
            }
        """)
        pf_layout = QVBoxLayout(prompt_frame)
        pf_layout.setContentsMargins(14, 12, 14, 12)
        pf_layout.setSpacing(10)

        pf_header = QHBoxLayout()
        pf_icon = QLabel()
        pf_icon.setPixmap(get_svg_pixmap("sparkles", "#a78bfa", 16))
        pf_header.addWidget(pf_icon)
        pf_title = QLabel("2. Prompt Gợi Ý Cho AI (ChatGPT / Claude / Gemini / DeepSeek)")
        pf_title.setStyleSheet("font-size: 13px; font-weight: 700; color: #f8fafc;")
        pf_header.addWidget(pf_title)
        pf_header.addStretch()
        pf_layout.addLayout(pf_header)

        pf_desc = QLabel(
            "Sao chép một trong các Prompt chuẩn hóa bên dưới và gửi cho AI. "
            "AI sẽ tự động soạn kịch bản theo đúng định dạng kỹ thuật mà Stock Studio Pro yêu cầu."
        )
        pf_desc.setStyleSheet("color: #94a3b8; font-size: 11px;")
        pf_desc.setWordWrap(True)
        pf_layout.addWidget(pf_desc)

        # Selector buttons
        selector_h = QHBoxLayout()
        selector_h.setSpacing(6)

        self._prompt_buttons = {}
        formats = [
            ("json", "✨ JSON (Tối Ưu Nhất)", "#818cf8"),
            ("excel", "📊 Bảng Excel / CSV", "#34d399"),
            ("txt", "📄 Văn Bản Tự Do (TXT)", "#cbd5e1"),
            ("srt", "💬 Phụ Đề Video (SRT)", "#fbbf24"),
        ]

        for key, label_text, color in formats:
            btn = QPushButton(label_text)
            btn.setFixedHeight(30)
            btn.setCheckable(True)
            btn.setChecked(key == "json")
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: #111827;
                    color: #94a3b8;
                    border: 1px solid #1f293d;
                    border-radius: 6px;
                    padding: 4px 12px;
                    font-size: 11px;
                    font-weight: 600;
                }}
                QPushButton:checked {{
                    background: #1e1b4b;
                    color: {color};
                    border: 1px solid {color};
                }}
                QPushButton:hover:!checked {{
                    background: #1f293d;
                    color: #f1f5f9;
                }}
            """)
            btn.clicked.connect(lambda checked, k=key: self._select_prompt(k))
            selector_h.addWidget(btn)
            self._prompt_buttons[key] = btn

        selector_h.addStretch()
        pf_layout.addLayout(selector_h)

        self.prompt_desc_lbl = QLabel(ScriptTemplateService.PROMPTS["json"].get("description", ""))
        self.prompt_desc_lbl.setStyleSheet("color: #818cf8; font-size: 11px; font-weight: 600;")
        pf_layout.addWidget(self.prompt_desc_lbl)

        self.prompt_display = QPlainTextEdit()
        self.prompt_display.setPlainText(ScriptTemplateService.get_prompt("json"))
        self.prompt_display.setStyleSheet("""
            QPlainTextEdit {
                background-color: #080b11;
                color: #e2e8f0;
                border: 1px solid #1e293b;
                border-radius: 8px;
                padding: 10px;
                font-family: 'Consolas', 'Cascadia Code', monospace;
                font-size: 11px;
                line-height: 1.4;
            }
        """)
        self.prompt_display.setFixedHeight(170)
        pf_layout.addWidget(self.prompt_display)

        pf_actions = QHBoxLayout()
        pf_actions.setSpacing(8)

        btn_copy_prompt = QPushButton("📋 Sao Chép Prompt Vào Clipboard")
        btn_copy_prompt.setObjectName("primaryBtn")
        btn_copy_prompt.setFixedHeight(32)
        btn_copy_prompt.setIcon(get_svg_icon("copy", "#ffffff", 13))
        btn_copy_prompt.setToolTip("Sao chép toàn bộ nội dung prompt để dán vào ChatGPT / Claude / DeepSeek")
        btn_copy_prompt.clicked.connect(self._copy_current_prompt)
        pf_actions.addWidget(btn_copy_prompt)

        btn_test_sample = QPushButton("⚡ Thử Nghiệm Kịch Bản Mẫu Này")
        btn_test_sample.setObjectName("secondaryBtn")
        btn_test_sample.setFixedHeight(32)
        btn_test_sample.setIcon(get_svg_icon("play", "#38bdf8", 12))
        btn_test_sample.setToolTip("Nạp ngay kịch bản mẫu tương ứng vào Tab Dán Kịch Bản để xem trước & nạp vào Studio")
        btn_test_sample.clicked.connect(lambda: self._load_sample_into_paste(self._active_prompt_key))
        pf_actions.addWidget(btn_test_sample)

        pf_actions.addStretch()
        pf_layout.addLayout(pf_actions)
        layout.addWidget(prompt_frame)

        # 3. Card: Cheat Sheet & Quy Chuẩn Định Dạng
        guide_frame = QFrame()
        guide_frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #141b2a, stop:1 #0c101a);
                border: 1px solid #1f2b3f;
                border-radius: 10px;
            }
        """)
        gf_layout = QVBoxLayout(guide_frame)
        gf_layout.setContentsMargins(14, 12, 14, 12)
        gf_layout.setSpacing(8)

        gf_header = QHBoxLayout()
        gf_icon = QLabel()
        gf_icon.setPixmap(get_svg_pixmap("help-circle", "#38bdf8", 16))
        gf_header.addWidget(gf_icon)
        gf_title = QLabel("3. Quy Chuẩn & Lưu Ý Định Dạng Kịch Bản")
        gf_title.setStyleSheet("font-size: 13px; font-weight: 700; color: #f8fafc;")
        gf_header.addWidget(gf_title)
        gf_header.addStretch()
        gf_layout.addLayout(gf_header)

        gf_info = QLabel(
            "• <b>JSON</b>: Định dạng mạnh mẽ nhất. Hỗ trợ đầy đủ trường <code>camera_angle</code>, <code>visual_tags</code>, <code>keywords</code>.<br>"
            "• <b>Excel (.xlsx) / CSV</b>: Bảng tính gồm các cột: <code>scene_id</code> (số thứ tự), <code>description</code> (lời thoại/mô tả), <code>keywords</code> (từ khóa phân cách bằng dấu phẩy), <code>duration</code> (thời lượng giây).<br>"
            "• <b>Văn bản TXT</b>: Tự do và tiện lợi. Mỗi cảnh bắt đầu bằng <code>Cảnh 1: Lời thoại | Từ khóa: keyword1, keyword2</code> hoặc phân tách bằng dòng trống.<br>"
            "• <b>Phụ đề SRT</b>: Tự động tính thời lượng cảnh dựa trên mốc thời gian phụ đề bắt đầu và kết thúc."
        )
        gf_info.setStyleSheet("color: #94a3b8; font-size: 11px; line-height: 1.5;")
        gf_info.setWordWrap(True)
        gf_layout.addWidget(gf_info)

        layout.addWidget(guide_frame)
        layout.addStretch()

        scroll.setWidget(content)
        main_tab_layout = QVBoxLayout(container)
        main_tab_layout.setContentsMargins(0, 0, 0, 0)
        main_tab_layout.addWidget(scroll)

        return container

    def _select_prompt(self, key: str):
        if key not in ScriptTemplateService.PROMPTS:
            return
        self._active_prompt_key = key
        for k, btn in self._prompt_buttons.items():
            btn.setChecked(k == key)
        info = ScriptTemplateService.PROMPTS[key]
        self.prompt_desc_lbl.setText(info.get("description", ""))
        self.prompt_display.setPlainText(info.get("content", ""))

    def _copy_current_prompt(self):
        text = self.prompt_display.toPlainText().strip()
        if text:
            QGuiApplication.clipboard().setText(text)
            ToastNotification.show_toast(self, "Đã sao chép Prompt vào bộ nhớ tạm (Clipboard)!", "success", 3000)

    def _load_sample_into_paste(self, sample_type: str = "json"):
        if sample_type == "json":
            content = ScriptTemplateService.get_sample_json()
        elif sample_type in ("txt", "text"):
            content = ScriptTemplateService.get_sample_txt()
        elif sample_type == "srt":
            content = ScriptTemplateService.get_sample_srt()
        elif sample_type in ("csv", "excel"):
            content = ScriptTemplateService.get_sample_csv()
        else:
            content = ScriptTemplateService.get_sample_json()

        self.text_area.setPlainText(content)
        self.tabs.setCurrentIndex(0)
        ToastNotification.show_toast(self, f"Đã nạp kịch bản mẫu ({sample_type.upper()}) vào ô dán!", "success", 2500)

    def _export_single_template_dialog(self):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #0f172a;
                color: #f1f5f9;
                border: 1px solid #334155;
                border-radius: 8px;
                padding: 6px;
            }
            QMenu::item {
                padding: 8px 24px;
                border-radius: 4px;
                font-weight: 500;
            }
            QMenu::item:selected {
                background-color: #3b82f6;
                color: #ffffff;
            }
        """)
        act_xlsx = menu.addAction("📊 Mẫu Excel (.xlsx)")
        act_csv = menu.addAction("📋 Mẫu Bảng tính (.csv)")
        act_txt = menu.addAction("📄 Mẫu Văn bản (.txt)")
        act_srt = menu.addAction("💬 Mẫu Phụ đề (.srt)")
        act_json = menu.addAction("✨ Mẫu Cấu trúc (.json)")
        menu.addSeparator()
        act_all = menu.addAction("📦 Xuất tất cả các mẫu vào thư mục...")

        sender = self.sender()
        if sender and hasattr(sender, "mapToGlobal"):
            pos = sender.mapToGlobal(sender.rect().bottomLeft())
        else:
            pos = self.mapToGlobal(self.rect().center())

        action = menu.exec(pos)
        if action == act_xlsx:
            self._export_single_template("xlsx")
        elif action == act_csv:
            self._export_single_template("csv")
        elif action == act_txt:
            self._export_single_template("txt")
        elif action == act_srt:
            self._export_single_template("srt")
        elif action == act_json:
            self._export_single_template("json")
        elif action == act_all:
            self._export_all_templates_folder()

    def _export_single_template(self, fmt: str):
        filter_map = {
            "xlsx": "Excel Workbook (*.xlsx)",
            "csv": "Comma-Separated Values (*.csv)",
            "txt": "Text Script (*.txt)",
            "srt": "SubRip Subtitle (*.srt)",
            "json": "JSON File (*.json)",
        }
        default_name = f"mau_kich_ban_stock_studio.{fmt}"
        path, _ = QFileDialog.getSaveFileName(
            self, f"Lưu Tệp Mẫu {fmt.upper()}", default_name, filter_map.get(fmt, "All Files (*.*)")
        )
        if not path:
            return
        try:
            target = Path(path)
            if fmt == "xlsx":
                ScriptTemplateService.generate_sample_xlsx(target)
            elif fmt == "csv":
                target.write_text(ScriptTemplateService.get_sample_csv(), encoding="utf-8")
            elif fmt == "txt":
                target.write_text(ScriptTemplateService.get_sample_txt(), encoding="utf-8")
            elif fmt == "srt":
                target.write_text(ScriptTemplateService.get_sample_srt(), encoding="utf-8")
            elif fmt == "json":
                target.write_text(ScriptTemplateService.get_sample_json(), encoding="utf-8")

            ToastNotification.show_toast(self, f"Đã xuất file mẫu {target.name} thành công!", "success", 3000)
        except Exception as e:
            QMessageBox.critical(self, "Lỗi xuất file", f"Không thể lưu file mẫu:\n{e}")

    def _export_all_templates_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Chọn Thư Mục Lưu Gói Mẫu Kịch Bản")
        if not folder:
            return
        try:
            created = ScriptTemplateService.export_all_templates(folder)
            count = len(created)
            ToastNotification.show_toast(self, f"Đã xuất thành công {count} file mẫu vào thư mục!", "success", 3000)
            QMessageBox.information(
                self, "Xuất Mẫu Thành Công",
                f"Đã tạo {count} tệp mẫu kịch bản chuẩn trong thư mục:\n{folder}\n\n"
                f"• mau_kich_ban.xlsx (Excel có định dạng đẹp)\n"
                f"• mau_kich_ban.csv\n"
                f"• mau_kich_ban.txt\n"
                f"• mau_kich_ban.srt\n"
                f"• mau_kich_ban.json\n"
                f"• README_HUONG_DAN.txt (Hướng dẫn chi tiết)"
            )
        except Exception as e:
            QMessageBox.critical(self, "Lỗi xuất gói mẫu", f"Không thể xuất thư mục mẫu:\n{e}")

