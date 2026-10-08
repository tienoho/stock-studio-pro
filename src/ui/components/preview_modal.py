"""
PreviewModal dialog with QMediaPlayer video playback and image viewer.
"""

import threading
import time
import requests
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFrame, QLabel, QPushButton, QSlider
)
from PyQt6.QtCore import Qt, QUrl, QTimer
from PyQt6.QtGui import QPixmap
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget

from ...core.models.scene import format_duration
from ...infrastructure.network.rate_limiter import get_random_ua
from ..styles.icons import get_svg_icon, get_svg_pixmap
from ..styles.tokens import load_stylesheet
from .stat_box import Badge


class PreviewModal(QDialog):
    """Studio preview modal for HD video and photo assets."""

    def __init__(self, item: dict, thumbnail_cache=None, parent=None):
        super().__init__(parent)
        self.item = item
        self.thumbnail_cache = thumbnail_cache
        self.media_player = None
        self.video_widget = None
        self.audio_output = None

        title_text = f"Studio Preview • {item.get('source', '').title()} {item.get('type', '').title()} #{item.get('id', '')}"
        self.setWindowTitle(title_text)
        self.setMinimumSize(1120, 760)
        self.setStyleSheet(load_stylesheet())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        # Info bar top
        info_bar = QFrame()
        info_bar.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #131926, stop:1 #0c101a);
                border: 1px solid #1f2b3f;
                border-radius: 10px;
            }
        """)
        info_bar.setFixedHeight(54)
        info_h = QHBoxLayout(info_bar)
        info_h.setContentsMargins(16, 6, 16, 6)
        info_h.setSpacing(10)

        # Source & Type Badges
        source_colors = {
            "pexels": "#10b981", "pixabay": "#06b6d4", "coverr": "#ec4899",
            "motionarray": "#f59e0b", "youtube": "#ef4444", "tiktok": "#8b5cf6",
        }
        source_color = source_colors.get(item.get("source", ""), "#6366f1")
        info_h.addWidget(Badge(item.get('source', '').upper(), source_color))

        m_type = item.get("type", "video")
        type_color = "#8b5cf6" if m_type == "video" else "#ec4899"
        type_text = "VIDEO" if m_type == "video" else "PHOTO"
        info_h.addWidget(Badge(type_text, type_color))

        # Size & Duration
        size_text = f"{item.get('width', '?')}x{item.get('height', '?')}"
        if m_type == "video":
            size_text += f"   •   {format_duration(item.get('duration', 0))}"
        size_label = QLabel(size_text)
        size_label.setStyleSheet("color: #f1f5f9; font-size: 12px; font-weight: 700; background: transparent;")
        info_h.addWidget(size_label)

        info_h.addSpacing(12)

        # Author
        author_label = QLabel(f"Author: {item.get('author', 'Unknown')}")
        author_label.setStyleSheet("color: #94a3b8; font-size: 12px; font-weight: 600; background: transparent;")
        info_h.addWidget(author_label)

        info_h.addStretch()

        # Close button
        btn_close = QPushButton("Đóng (ESC)")
        btn_close.setIcon(get_svg_icon("x", "#ffffff", 14))
        btn_close.setFixedWidth(120)
        btn_close.setFixedHeight(34)
        btn_close.clicked.connect(self.close)
        info_h.addWidget(btn_close)

        layout.addWidget(info_bar)

        # Preview area
        preview_frame = QFrame()
        preview_frame.setStyleSheet("""
            QFrame {
                background-color: #06090e;
                border: 1px solid #1f2b3f;
                border-radius: 12px;
            }
        """)
        preview_layout = QVBoxLayout(preview_frame)
        preview_layout.setContentsMargins(4, 4, 4, 4)

        if m_type == "video":
            self._setup_video_player(preview_layout, item)
        else:
            self._setup_image_viewer(preview_layout, item)

        layout.addWidget(preview_frame, 1)

        # Keyword & info
        kw_label = QLabel(f"Từ khóa tìm kiếm: {item.get('search_query', '')}")
        kw_label.setStyleSheet("color: #64748b; font-size: 11px; font-weight: 600;")
        kw_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(kw_label)

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def _setup_video_player(self, layout, item):
        try:
            self.video_widget = QVideoWidget()
            self.video_widget.setStyleSheet("background: #06090e; border-radius: 8px;")
            layout.addWidget(self.video_widget, 1)

            self.media_player = QMediaPlayer()
            self.audio_output = QAudioOutput()
            self.media_player.setAudioOutput(self.audio_output)
            self.media_player.setVideoOutput(self.video_widget)

            preview_url = item.get("preview_url") or item.get("download_url") or item.get("url")

            # Controls
            controls = QFrame()
            controls.setStyleSheet("""
                QFrame {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #131926, stop:1 #0c101a);
                    border: 1px solid #1f2b3f;
                    border-radius: 10px;
                }
            """)
            controls.setFixedHeight(64)
            ch = QHBoxLayout(controls)
            ch.setContentsMargins(16, 8, 16, 8)
            ch.setSpacing(14)

            self.play_btn = QPushButton("Play")
            self.play_btn.setIcon(get_svg_icon("play", "#ffffff", 14))
            self.play_btn.setObjectName("primaryBtn")
            self.play_btn.setFixedWidth(100)
            self.play_btn.setFixedHeight(38)
            self.play_btn.clicked.connect(self._toggle_play)
            ch.addWidget(self.play_btn)

            self.progress_slider = QSlider(Qt.Orientation.Horizontal)
            self.progress_slider.setStyleSheet("""
                QSlider::groove:horizontal {
                    background: #1e293b;
                    height: 6px;
                    border-radius: 3px;
                }
                QSlider::handle:horizontal {
                    background: #38bdf8;
                    border: 2px solid #0284c7;
                    width: 16px;
                    height: 16px;
                    margin: -5px 0;
                    border-radius: 8px;
                }
                QSlider::sub-page:horizontal {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 #6366f1, stop:1 #38bdf8);
                    border-radius: 3px;
                }
            """)
            self.progress_slider.sliderMoved.connect(self._seek)
            ch.addWidget(self.progress_slider, 1)

            self.time_label = QLabel("0:00 / 0:00")
            self.time_label.setStyleSheet("""
                color: #38bdf8;
                font-size: 11px;
                font-family: 'Consolas', monospace;
                font-weight: 700;
                background-color: #0c0f17;
                border: 1px solid #1e293b;
                border-radius: 6px;
                padding: 4px 8px;
            """)
            self.time_label.setMinimumWidth(100)
            self.time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            ch.addWidget(self.time_label)

            vol_label = QLabel("Vol:")
            vol_label.setStyleSheet("color: #94a3b8; font-size: 11px; font-weight: 700; background: transparent;")
            ch.addWidget(vol_label)

            self.volume_slider = QSlider(Qt.Orientation.Horizontal)
            self.volume_slider.setFixedWidth(80)
            self.volume_slider.setMinimum(0)
            self.volume_slider.setMaximum(100)
            self.volume_slider.setValue(50)
            self.volume_slider.setStyleSheet("""
                QSlider::groove:horizontal {
                    background: #1e293b;
                    height: 4px;
                    border-radius: 2px;
                }
                QSlider::handle:horizontal {
                    background: #a855f7;
                    width: 12px;
                    height: 12px;
                    margin: -4px 0;
                    border-radius: 6px;
                }
                QSlider::sub-page:horizontal {
                    background: #a855f7;
                    border-radius: 2px;
                }
            """)
            self.volume_slider.valueChanged.connect(lambda v: self.audio_output.setVolume(v / 100))
            ch.addWidget(self.volume_slider)

            layout.addWidget(controls)

            self.status_label = QLabel("Đang kết nối video preview...")
            self.status_label.setStyleSheet("color: #94a3b8; font-size: 11px; font-weight: 600;")
            self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(self.status_label)

            self.media_player.positionChanged.connect(self._on_position_changed)
            self.media_player.durationChanged.connect(self._on_duration_changed)
            self.media_player.mediaStatusChanged.connect(self._on_media_status_changed)
            self.media_player.playbackStateChanged.connect(self._on_playback_state_changed)
            self.media_player.errorOccurred.connect(self._on_error)

            if preview_url:
                self.media_player.setSource(QUrl(preview_url))
            else:
                self.status_label.setText("Không có URL video preview")
                self.status_label.setStyleSheet("color: #f87171; font-size: 11px;")

        except Exception as e:
            error_label = QLabel(f"Lỗi khởi tạo video player:\n{e}\n\nCần PyQt6-Multimedia")
            error_label.setStyleSheet("color: #f87171; font-size: 13px; padding: 50px;")
            error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            error_label.setWordWrap(True)
            layout.addWidget(error_label)

    def _setup_image_viewer(self, layout, item):
        self.image_label = QLabel("Đang tải ảnh chất lượng cao...")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet("color: #94a3b8; font-size: 13px; font-weight: 600;")
        layout.addWidget(self.image_label, 1)

        threading.Thread(target=self._load_image, args=(item,), daemon=True).start()

    def _load_image(self, item):
        try:
            url = item.get("preview_url") or item.get("url") or item.get("thumbnail_url")
            headers = {"User-Agent": get_random_ua()}
            if item.get("source") == "vecteezy":
                headers["Referer"] = "https://www.vecteezy.com/"

            # Thử 3 lần với backoff
            last_err = None
            for attempt in range(3):
                try:
                    resp = requests.get(url, headers=headers, timeout=15)
                    if resp.status_code == 200:
                        pixmap = QPixmap()
                        pixmap.loadFromData(resp.content)
                        if not pixmap.isNull():
                            def set_pix():
                                scaled = pixmap.scaled(
                                    self.image_label.size(),
                                    Qt.AspectRatioMode.KeepAspectRatio,
                                    Qt.TransformationMode.SmoothTransformation
                                )
                                self.image_label.setPixmap(scaled)
                            QTimer.singleShot(0, set_pix)
                            return
                        else:
                            last_err = "Dữ liệu ảnh không hợp lệ"
                    elif resp.status_code == 429:
                        time.sleep(1.0 * (attempt + 1))
                        continue
                    else:
                        last_err = f"HTTP {resp.status_code}"
                except Exception as e:
                    last_err = str(e)
                    time.sleep(0.5)

            # Fallback sang thumbnail cache
            if self.thumbnail_cache:
                thumb_pix = self.thumbnail_cache.get(item.get("thumbnail_url", ""))
                if thumb_pix and not thumb_pix.isNull():
                    def set_thumb():
                        scaled = thumb_pix.scaled(
                            self.image_label.size(),
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation
                        )
                        self.image_label.setPixmap(scaled)
                    QTimer.singleShot(0, set_thumb)
                    return

            def set_fail():
                self.image_label.setText(f"Không tải được ảnh preview ({last_err})\n(Có thể CDN throttle, vui lòng thử lại sau)")
                self.image_label.setStyleSheet("color: #f87171; font-size: 12px; font-weight: 600;")
            QTimer.singleShot(0, set_fail)

        except Exception as e:
            def set_err():
                self.image_label.setText(f"Lỗi tải ảnh: {e}")
                self.image_label.setStyleSheet("color: #f87171; font-size: 12px;")
            QTimer.singleShot(0, set_err)

    def _toggle_play(self):
        if not self.media_player:
            return
        if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.media_player.pause()
        else:
            self.media_player.play()

    def _seek(self, value):
        if self.media_player:
            self.media_player.setPosition(value)

    def _on_position_changed(self, position):
        self.progress_slider.setValue(position)
        duration = self.media_player.duration()
        self.time_label.setText(f"{self._fmt_time(position)} / {self._fmt_time(duration)}")

    def _on_duration_changed(self, duration):
        self.progress_slider.setMaximum(duration)

    def _on_media_status_changed(self, status):
        if status == QMediaPlayer.MediaStatus.LoadedMedia:
            self.status_label.setText("Video sẵn sàng • Bấm Play để xem")
            self.status_label.setStyleSheet("color: #34d399; font-size: 11px; font-weight: 700;")
            self.media_player.play()
        elif status == QMediaPlayer.MediaStatus.BufferingMedia:
            self.status_label.setText("Đang tải đệm (Buffering)...")
            self.status_label.setStyleSheet("color: #38bdf8; font-size: 11px;")
        elif status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.status_label.setText("Đã hết clip • Tự động lặp lại")
            self.media_player.setPosition(0)
            self.media_player.play()
        elif status == QMediaPlayer.MediaStatus.InvalidMedia:
            self.status_label.setText("Video không hợp lệ hoặc lỗi định dạng")
            self.status_label.setStyleSheet("color: #f87171; font-size: 11px;")

    def _on_playback_state_changed(self, state):
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.play_btn.setIcon(get_svg_icon("stop", "#ffffff", 14))
            self.play_btn.setText("Pause")
        else:
            self.play_btn.setIcon(get_svg_icon("play", "#ffffff", 14))
            self.play_btn.setText("Play")

    def _on_error(self, error, error_string):
        if self.status_label:
            self.status_label.setText(f"Lỗi: {error_string}")
            self.status_label.setStyleSheet("color: #f87171; font-size: 11px;")

    def _fmt_time(self, ms):
        s = ms // 1000
        m = s // 60
        sec = s % 60
        return f"{m}:{sec:02d}"

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        elif event.key() == Qt.Key.Key_Space and self.media_player:
            self._toggle_play()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        if self.media_player:
            try:
                self.media_player.stop()
            except Exception:
                pass
        super().closeEvent(event)
