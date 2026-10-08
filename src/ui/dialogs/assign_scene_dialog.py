"""
Dialog for assigning a newly downloaded MotionArray media file to a specific scene.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QListWidget, QListWidgetItem, QMessageBox
)
from PyQt6.QtCore import Qt
from ...core.i18n import t
from ..styles.icons import get_svg_icon, get_svg_pixmap
from ..styles.tokens import load_stylesheet
from ..styles.ui_enhancer import enhance_widget_interactions, format_tooltip


class AssignSceneDialog(QDialog):
    """Categorize downloaded video files into script scenes."""

    def __init__(self, filename: str, scenes: list, suggested_scene_id=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("assign_scene.title"))
        self.setMinimumWidth(620)
        self.setMinimumHeight(450)
        self.setStyleSheet(load_stylesheet())

        self.filename = filename
        self.scenes = scenes
        self.selected_scene_id = None
        self.action = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        header_h = QHBoxLayout()
        header_h.setSpacing(8)
        header_icon = QLabel()
        header_icon.setPixmap(get_svg_pixmap("download", "#f59e0b", 16))
        header_h.addWidget(header_icon)

        header = QLabel(t("assign_scene.header"))
        header.setObjectName("sectionHeader")
        header_h.addWidget(header)
        header_h.addStretch()
        layout.addLayout(header_h)

        file_label = QLabel(filename)
        file_label.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #131926, stop:1 #0c101a);
            border: 1px solid rgba(245, 158, 11, 0.4);
            border-radius: 8px;
            padding: 10px 14px;
            color: #fbbf24;
            font-size: 13px;
            font-weight: 700;
        """)
        file_label.setWordWrap(True)
        layout.addWidget(file_label)

        if suggested_scene_id is not None:
            suggested = next((s for s in scenes if str(s.get("id")) == str(suggested_scene_id)), None)
            if suggested:
                ts_start = suggested.get("time_start") or suggested.get("timestamp_start") or "?"
                preview_text = (suggested.get("dialogue_es") or suggested.get("dialogue") or "")[:80]

                suggest_btn = QPushButton(
                    f"Gán nhanh vào Scene #{suggested_scene_id} [{ts_start}] (đang search)\n{preview_text}..."
                )
                suggest_btn.setIcon(get_svg_icon("zap", "#ffffff", 14))
                suggest_btn.setObjectName("primaryBtn")
                suggest_btn.setStyleSheet("""
                    QPushButton#primaryBtn {
                        padding: 10px;
                        text-align: left;
                        line-height: 1.3;
                    }
                """)
                suggest_btn.setToolTip(format_tooltip("Gán nhanh tệp tin vào cảnh đang tìm kiếm"))
                suggest_btn.clicked.connect(lambda: self._select_and_close(suggested_scene_id))
                layout.addWidget(suggest_btn)

        self.search_input = QLineEdit()
        self.search_input.setFixedHeight(34)
        self.search_input.setPlaceholderText(t("assign_scene.search_placeholder"))
        self.search_input.textChanged.connect(self._filter_scenes)
        layout.addWidget(self.search_input)

        self.scene_list = QListWidget()
        self.scene_list.setStyleSheet("""
            QListWidget {
                background-color: #0c101a;
                border: 1px solid #1f2b3f;
                border-radius: 10px;
                padding: 6px;
            }
            QListWidget::item {
                padding: 8px 12px;
                border-radius: 6px;
                margin-bottom: 3px;
                color: #f1f5f9;
            }
            QListWidget::item:hover {
                background-color: #1a2233;
            }
            QListWidget::item:selected {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6366f1, stop:1 #8b5cf6);
                color: #ffffff;
                font-weight: 700;
            }
        """)
        self.scene_list.itemDoubleClicked.connect(self._on_item_double_clicked)
        self._populate_scene_list("")
        layout.addWidget(self.scene_list, 1)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        btn_assign = QPushButton(t("assign_scene.assign_btn"))
        btn_assign.setIcon(get_svg_icon("check", "#ffffff", 14))
        btn_assign.setObjectName("primaryBtn")
        btn_assign.setFixedHeight(36)
        btn_assign.setToolTip(format_tooltip("Xác nhận gán vào cảnh đã chọn", "Enter"))
        btn_assign.clicked.connect(self._on_assign)
        btn_row.addWidget(btn_assign)

        btn_skip = QPushButton("Bỏ qua")
        btn_skip.setObjectName("secondaryBtn")
        btn_skip.setIcon(get_svg_icon("chevron-right", "#ffffff", 14))
        btn_skip.setFixedHeight(36)
        btn_skip.setToolTip(format_tooltip("Bỏ qua tệp tin này không gán"))
        btn_skip.clicked.connect(self._on_skip)
        btn_row.addWidget(btn_skip)

        btn_delete = QPushButton(t("assign_scene.delete_btn"))
        btn_delete.setIcon(get_svg_icon("trash", "#ffffff", 14))
        btn_delete.setObjectName("dangerBtn")
        btn_delete.setFixedHeight(36)
        btn_delete.setToolTip(format_tooltip("Xóa tệp tin đã tải về"))
        btn_delete.clicked.connect(self._on_delete)
        btn_row.addWidget(btn_delete)

        layout.addLayout(btn_row)

        # Apply global interactive UX enhancements
        enhance_widget_interactions(self)

    def _populate_scene_list(self, filter_text: str):
        self.scene_list.clear()
        filter_text = filter_text.lower().strip()

        for scene in self.scenes:
            scene_id = scene.get("id")
            ts_start = scene.get("time_start") or scene.get("timestamp_start") or "?"
            dialogue = scene.get("dialogue_es") or scene.get("dialogue") or ""
            keywords = " ".join(scene.get("primary_keywords", []) or [])

            if filter_text:
                searchable = f"{scene_id} {ts_start} {dialogue} {keywords}".lower()
                if filter_text not in searchable:
                    continue

            text = f"Scene #{scene_id} [{ts_start}]  •  {dialogue[:75]}..."
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, scene_id)
            self.scene_list.addItem(item)

    def _filter_scenes(self, text: str):
        self._populate_scene_list(text)

    def _on_item_double_clicked(self, item):
        scene_id = item.data(Qt.ItemDataRole.UserRole)
        self._select_and_close(scene_id)

    def _select_and_close(self, scene_id):
        self.selected_scene_id = scene_id
        self.action = "assign"
        self.accept()

    def _on_assign(self):
        current = self.scene_list.currentItem()
        if not current:
            QMessageBox.information(self, "Chưa chọn scene", "Chọn scene trong danh sách trước nhé")
            return
        scene_id = current.data(Qt.ItemDataRole.UserRole)
        self._select_and_close(scene_id)

    def _on_skip(self):
        self.action = "skip"
        self.accept()

    def _on_delete(self):
        reply = QMessageBox.question(
            self, t("common.confirm"),
            f"Bạn có chắc muốn xóa file '{self.filename}' khỏi thư mục Downloads?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.action = "delete"
            self.accept()
