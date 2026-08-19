"""
═══════════════════════════════════════════════════════════════════
STOCK MEDIA PREVIEW DOWNLOADER v5.0 - Pexels + MotionArray Helper
═══════════════════════════════════════════════════════════════════

Streamlined edition: tập trung 2 nguồn chính
- Pexels: Auto search + download (như cũ)
- MotionArray: Manual search in Cốc Cốc + auto file organize

NEW IN v5.0:
- 🎯 Streamlined: chỉ Pexels + MotionArray (bỏ YouTube/TikTok/Coverr/Pixabay)
- 🎯 MotionArray Helper button: click → mở Cốc Cốc với keyword scene
- 🎯 Downloads folder watcher: tự detect file mp4 mới
- 🎯 AssignSceneDialog: chọn scene cho file vừa tải
- 🎯 Auto move + rename: motionarray_001.mp4, motionarray_002.mp4...
- 🎯 Output folder mặc định: D:\\Tool\\Tool\\StockScraper\\stock_media
- 🎯 Auto detect Cốc Cốc path

Yeu cau:
    pip install PyQt6 PyQt6-Multimedia Pillow requests
"""

import os
import re
import sys
import json
import base64
import threading
import time
import random
import hashlib
import io
import pickle
import subprocess
from pathlib import Path
from datetime import datetime
from collections import deque
from concurrent.futures import ThreadPoolExecutor

try:
    from PyQt6.QtCore import (
        Qt, QSize, QUrl, QTimer, QThread, pyqtSignal, QObject,
        QPropertyAnimation, QEasingCurve, QPoint, QPointF, QRect, QEvent, QLineF
    )
    from PyQt6.QtGui import (
        QPixmap, QImage, QIcon, QFont, QPalette, QColor,
        QPainter, QBrush, QPen, QFontMetrics, QCursor, QMovie, QDrag
    )
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QLabel, QPushButton,
        QVBoxLayout, QHBoxLayout, QGridLayout, QFrame, QScrollArea,
        QLineEdit, QTextEdit, QPlainTextEdit, QCheckBox, QComboBox,
        QFileDialog, QMessageBox, QDialog, QTabWidget, QSizePolicy,
        QSpacerItem, QGraphicsDropShadowEffect, QStackedWidget,
        QListWidget, QListWidgetItem, QScrollBar, QToolButton,
        QSlider, QStyle, QStyleOptionSlider, QStatusBar, QSpinBox, QDoubleSpinBox, QGraphicsView, QGraphicsScene, QGraphicsRectItem, QGraphicsTextItem, QGraphicsLineItem, QGraphicsItem
    )
    from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
    from PyQt6.QtMultimediaWidgets import QVideoWidget
except ImportError as e:
    print(f"[ERROR] PyQt6 not installed: {e}")
    print("Run: pip install PyQt6 PyQt6-Multimedia")
    sys.exit(1)

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("[ERROR] Pillow not installed")
    print("Run: pip install Pillow")
    sys.exit(1)

try:
    import requests
except ImportError:
    print("[ERROR] requests not installed")
    print("Run: pip install requests")
    sys.exit(1)


# ═══════════════════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════════════════

APP_VERSION = "5.1"
APP_NAME = "US Economy Video Studio"

CONFIG_FILE = Path.home() / ".stock_preview_v4_config.json"
STATE_FILE = Path.home() / ".stock_preview_v4_state.pkl"
CACHE_DIR = Path.home() / ".stock_preview_cache_v4"
CACHE_DIR.mkdir(exist_ok=True)
VIDEO_CACHE_DIR = CACHE_DIR / "videos"
VIDEO_CACHE_DIR.mkdir(exist_ok=True)

# Grid - responsive based on screen
GRID_COLS = 4
GRID_ROWS = 5
ITEMS_PER_PAGE = GRID_COLS * GRID_ROWS  # 20 items per page

# Sizes - responsive
THUMB_WIDTH = 180
THUMB_HEIGHT = 115
CARD_WIDTH = THUMB_WIDTH + 16
CARD_HEIGHT = THUMB_HEIGHT + 90

# API
PEXELS_LIMIT_PER_HOUR = 200
PIXABAY_LIMIT_PER_MINUTE = 100
RESULTS_PER_KEYWORD = 30
MAX_KEYWORDS_PER_SCENE = 5  # v5: search 5 keywords/scene (cân bằng quota & coverage)

# ═════ ANTI-BLOCK SETTINGS (v4.3) ═════
MIN_DOWNLOAD_DELAY = 0.5
MAX_DOWNLOAD_DELAY = 3.0
DEFAULT_DOWNLOAD_DELAY = 0.8
DELAY_JITTER = 0.2

BLOCK_DETECTION_THRESHOLD = 5
BLOCK_COOLDOWN_SECONDS = 300  # 5 minutes

DELAY_INCREASE_THRESHOLD = 0.3
DELAY_DECREASE_THRESHOLD = 0.1

# Download retry
MAX_RETRIES = 3
RETRY_DELAYS = [1, 2, 4]

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
]


def get_random_ua():
    return random.choice(USER_AGENTS)


def get_jittered_delay(base_delay):
    """Add ±20% random jitter to delay"""
    jitter = random.uniform(-DELAY_JITTER, DELAY_JITTER) * base_delay
    return max(0.1, base_delay + jitter)



def srt_time_to_seconds(value):
    m = re.match(r"(\d{2}):(\d{2}):(\d{2}),(\d{3})", str(value).strip())
    if not m:
        return 0.0
    h, mi, sec, ms = map(int, m.groups())
    return h * 3600 + mi * 60 + sec + ms / 1000

def format_duration(seconds):
    if not seconds:
        return "?"
    m = int(seconds) // 60
    s = int(seconds) % 60
    return f"{m}:{s:02d}"


# ═══════════════════════════════════════════════════════════════════
# QSS STYLE SHEETS - 1ClickSub Studio Aesthetic
# ═══════════════════════════════════════════════════════════════════

QSS_MAIN = """
/* ═══════════════════════════════════════════════════════════════════
   1CLICKSUB STUDIO - ULTRA MODERN OBSIDIAN THEME
   ═══════════════════════════════════════════════════════════════════ */

QMainWindow, QWidget {
    background-color: #0a0d14;
    color: #f1f5f9;
    font-family: 'Segoe UI Variable Display', 'Segoe UI', 'SF Pro Display', -apple-system, sans-serif;
    font-size: 13px;
    selection-background-color: #6366f1;
    selection-color: #ffffff;
}

#mainArea {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #0a0d14, stop:0.45 #0f141f, stop:1 #121826);
}

#setupSidebar, #scenesSidebar {
    background-color: #0d111a;
    border-right: 1px solid #1a2233;
}

#maSidebar {
    background-color: #0d111a;
    border-left: 1px solid #1a2233;
}

/* Glassmorphic Cards & Containers */
QFrame#card, QFrame#toolCard, QGroupBox {
    background-color: #131926;
    border: 1px solid #1e293b;
    border-radius: 14px;
    padding: 12px;
}

QFrame#toolCard:hover, QFrame#card:hover {
    border-color: #6366f1;
    background-color: #161e2e;
}

QFrame#statBox {
    border-radius: 14px;
    padding: 10px;
    border: 1px solid rgba(255, 255, 255, 0.08);
}

/* Typography & Titles */
QLabel#appTitle {
    color: #f8fafc;
    font-size: 22px;
    font-weight: 900;
    letter-spacing: 0.5px;
}

QLabel#heroTitle {
    color: #f8fafc;
    font-size: 20px;
    font-weight: 800;
    letter-spacing: 0.3px;
    padding: 0 0 4px 0;
}

QLabel#appVersion {
    color: #818cf8;
    font-size: 11px;
    font-weight: 700;
    background-color: rgba(99, 102, 241, 0.15);
    border: 1px solid rgba(99, 102, 241, 0.35);
    border-radius: 10px;
    padding: 2px 10px;
}

QLabel#mutedText {
    color: #94a3b8;
    font-size: 12px;
}

QLabel#sectionHeader {
    color: #818cf8;
    font-size: 11px;
    font-weight: 800;
    letter-spacing: 1.2px;
    padding: 8px 0 4px 0;
    text-transform: uppercase;
}

/* Buttons */
QPushButton {
    background-color: #172033;
    color: #f1f5f9;
    border: 1px solid #25334d;
    border-radius: 10px;
    padding: 7px 15px;
    font-weight: 650;
    min-height: 28px;
    font-size: 12px;
}

QPushButton:hover {
    background-color: #1f2c45;
    border-color: #6366f1;
    color: #ffffff;
}

QPushButton:pressed {
    background-color: #131b2c;
    padding-top: 8px;
    padding-bottom: 6px;
}

QPushButton:disabled {
    background-color: #0f1523;
    color: #475569;
    border-color: #172033;
}

/* Primary Studio CTA Button */
QPushButton#primaryBtn {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #6366f1, stop:0.5 #7c3aed, stop:1 #8b5cf6);
    color: #ffffff;
    border: 1px solid #a5b4fc;
    border-radius: 11px;
    font-weight: 800;
    font-size: 13px;
    padding: 8px 18px;
}

QPushButton#primaryBtn:hover {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #4f46e5, stop:0.5 #6d28d9, stop:1 #7c3aed);
    border-color: #c7d2fe;
}

QPushButton#primaryBtn:pressed {
    background-color: #4338ca;
    padding-top: 9px;
    padding-bottom: 7px;
}

/* Danger / Stop Button */
QPushButton#dangerBtn {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #ef4444, stop:1 #dc2626);
    color: #ffffff;
    border: 1px solid #fca5a5;
    border-radius: 10px;
    font-weight: 750;
}

QPushButton#dangerBtn:hover {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #dc2626, stop:1 #b91c1c);
    border-color: #fecaca;
}

/* Cyan / Accent Action Button */
QPushButton#purpleBtn, QPushButton#filterActive {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #0284c7, stop:1 #06b6d4);
    color: #ffffff;
    border: 1px solid #7dd3fc;
    border-radius: 10px;
    font-weight: 800;
}

QPushButton#purpleBtn:hover, QPushButton#filterActive:hover {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #0369a1, stop:1 #0891b2);
}

QPushButton#filterInactive {
    background-color: #131926;
    color: #94a3b8;
    border: 1px solid #1e293b;
    border-radius: 10px;
    font-weight: 600;
}

QPushButton#filterInactive:hover {
    background-color: #1e293b;
    color: #f8fafc;
    border-color: #38bdf8;
}

/* Input Fields */
QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background-color: #0e131d;
    color: #f8fafc;
    border: 1px solid #222d42;
    border-radius: 10px;
    padding: 7px 12px;
    selection-background-color: #6366f1;
    selection-color: #ffffff;
    font-size: 12px;
}

QLineEdit:hover, QTextEdit:hover, QPlainTextEdit:hover, QComboBox:hover,
QSpinBox:hover, QDoubleSpinBox:hover {
    border-color: #3b4d6e;
    background-color: #111724;
}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus,
QSpinBox:focus, QDoubleSpinBox:focus {
    border: 1px solid #818cf8;
    background-color: #131a29;
}

QComboBox::drop-down {
    border: none;
    width: 26px;
}

QComboBox::down-arrow {
    width: 0;
    height: 0;
}

QComboBox QAbstractItemView {
    background-color: #0f1522;
    color: #f8fafc;
    border: 1px solid #25334d;
    border-radius: 10px;
    selection-background-color: #6366f1;
    selection-color: #ffffff;
    padding: 6px;
    outline: none;
}

/* Checkbox */
QCheckBox {
    color: #e2e8f0;
    spacing: 8px;
    font-weight: 600;
    font-size: 12px;
}

QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border: 1.5px solid #334155;
    border-radius: 6px;
    background-color: #0e131d;
}

QCheckBox::indicator:hover {
    border-color: #818cf8;
    background-color: #141a27;
}

QCheckBox::indicator:checked {
    background-color: #6366f1;
    border-color: #a5b4fc;
    image: none;
}

/* Tabs - 1ClickSub Studio Segmented Pill Bar */
QTabWidget::pane {
    border: 1px solid #1e293b;
    background-color: rgba(13, 17, 26, 0.95);
    border-radius: 16px;
    top: -1px;
}

QTabBar::tab {
    background-color: #0e131d;
    color: #94a3b8;
    padding: 10px 22px;
    border: 1px solid #1e293b;
    border-bottom: none;
    border-top-left-radius: 12px;
    border-top-right-radius: 12px;
    margin-right: 4px;
    font-weight: 750;
    font-size: 12px;
}

QTabBar::tab:selected {
    background-color: #172033;
    color: #f8fafc;
    border: 1px solid #6366f1;
    border-bottom: none;
}

QTabBar::tab:hover:!selected {
    background-color: #141a27;
    color: #e2e8f0;
    border-color: #334155;
}

/* Lists & Tables */
QTableWidget, QTreeWidget, QListWidget {
    background-color: #0e131d;
    alternate-background-color: #121825;
    border: 1px solid #1e293b;
    border-radius: 12px;
    gridline-color: #1e293b;
    selection-background-color: #6366f1;
    selection-color: #ffffff;
    padding: 4px;
}

QHeaderView::section {
    background-color: #131926;
    color: #94a3b8;
    border: none;
    border-right: 1px solid #1e293b;
    padding: 8px;
    font-weight: 800;
}

/* Progress Bar */
QProgressBar {
    background-color: #0e131d;
    border: 1px solid #1e293b;
    border-radius: 10px;
    color: #f8fafc;
    text-align: center;
    min-height: 18px;
    font-weight: 700;
    font-size: 11px;
}

QProgressBar::chunk {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #6366f1, stop:0.5 #8b5cf6, stop:1 #06b6d4);
    border-radius: 9px;
}

/* Scrollbars */
QScrollArea {
    border: none;
    background-color: transparent;
}

QScrollBar:vertical, QScrollBar:horizontal {
    background-color: #0a0d14;
    border-radius: 5px;
    margin: 2px;
}

QScrollBar:vertical { width: 9px; }
QScrollBar:horizontal { height: 9px; }

QScrollBar::handle:vertical, QScrollBar::handle:horizontal {
    background-color: #1e293b;
    border-radius: 4px;
    min-height: 28px;
    min-width: 28px;
}

QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover {
    background-color: #6366f1;
}

QScrollBar::add-line, QScrollBar::sub-line {
    width: 0;
    height: 0;
}

/* Status Bar */
QStatusBar {
    background-color: #0d111a;
    color: #94a3b8;
    border-top: 1px solid #1a2233;
    font-size: 11px;
}

/* Tooltips */
QToolTip {
    background-color: #131926;
    color: #f8fafc;
    border: 1px solid #6366f1;
    border-radius: 8px;
    padding: 8px;
    font-size: 11px;
}

/* Dialogs & Message Box */
QMessageBox, QDialog {
    background-color: #0d111a;
}

QMessageBox QLabel, QDialog QLabel {
    color: #f1f5f9;
}
"""

# Stat box colors - 1ClickSub Studio Vibrants
STAT_COLOR_BLUE = "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #1e3a8a, stop:1 #1d4ed8)"
STAT_COLOR_PURPLE = "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #4c1d95, stop:1 #6d28d9)"
STAT_COLOR_RED = "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #831843, stop:1 #be123c)"
STAT_COLOR_GREEN = "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #064e3b, stop:1 #047857)"


# ═══════════════════════════════════════════════════════════════════
# CONFIG & STATE
# ═══════════════════════════════════════════════════════════════════

DEFAULT_OUTPUT_DIR = Path.home() / "Downloads" / "Stock_Media_Output"

DEFAULT_CONFIG = {
    "pexels_keys": [],
    "pixabay_keys": [],
    "vecteezy_keys": [],
    "output_dir": str(DEFAULT_OUTPUT_DIR),
}


def obfuscate(text):
    if not text:
        return ""
    return base64.b64encode(text.encode('utf-8')).decode('utf-8')


def deobfuscate(text):
    if not text:
        return ""
    try:
        return base64.b64decode(text.encode('utf-8')).decode('utf-8')
    except Exception:
        return text


def load_config():
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
            for k in config.get("pexels_keys", []):
                k["key"] = deobfuscate(k.get("key", ""))
            for k in config.get("pixabay_keys", []):
                k["key"] = deobfuscate(k.get("key", ""))
            for k in config.get("coverr_keys", []):
                k["key"] = deobfuscate(k.get("key", ""))
            for k in config.get("vecteezy_keys", []):
                k["key"] = deobfuscate(k.get("key", ""))
            # Preserve all keys including search_prefs
            merged = {**DEFAULT_CONFIG, **config}
            return merged
        except Exception:
            pass
    return DEFAULT_CONFIG.copy()


def save_config(config):
    try:
        config_to_save = {
            "pexels_keys": [{"name": k["name"], "key": obfuscate(k["key"])} for k in config.get("pexels_keys", [])],
            "pixabay_keys": [{"name": k["name"], "key": obfuscate(k["key"])} for k in config.get("pixabay_keys", [])],
            "coverr_keys": [{"name": k["name"], "key": obfuscate(k["key"])} for k in config.get("coverr_keys", [])],
            "vecteezy_keys": [{"name": k["name"], "key": obfuscate(k["key"])} for k in config.get("vecteezy_keys", [])],
            "output_dir": config.get("output_dir", ""),
            "search_prefs": config.get("search_prefs", {}),
        }
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config_to_save, f, indent=2)
    except Exception:
        pass


def save_state(state):
    try:
        with open(STATE_FILE, 'wb') as f:
            pickle.dump(state, f)
    except Exception:
        pass


def load_state():
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, 'rb') as f:
                return pickle.load(f)
        except Exception:
            pass
    return None


def reset_state():
    if STATE_FILE.exists():
        STATE_FILE.unlink()


# ═══════════════════════════════════════════════════════════════════
# KEY MANAGER
# ═══════════════════════════════════════════════════════════════════

class APIKey:
    def __init__(self, name, key, platform):
        self.name = name
        self.key = key
        self.platform = platform
        self.request_history = deque()
        self.is_dead = False
        self.total_requests = 0
    
    def can_use(self):
        if self.is_dead:
            return False
        now = time.time()
        if self.platform == "pexels":
            window_start = now - 3600
            recent = [t for t in self.request_history if t > window_start]
            self.request_history = deque(recent)
            return len(recent) < PEXELS_LIMIT_PER_HOUR
        elif self.platform == "pixabay":
            window_start = now - 60
            recent = [t for t in self.request_history if t > window_start]
            self.request_history = deque(recent)
            return len(recent) < PIXABAY_LIMIT_PER_MINUTE
        elif self.platform == "coverr":
            # Coverr: Demo 50/h, Production 2000/h - dùng 50/h cho an toàn
            window_start = now - 3600
            recent = [t for t in self.request_history if t > window_start]
            self.request_history = deque(recent)
            return len(recent) < 50
        elif self.platform == "vecteezy":
            window_start = now - 60
            recent = [t for t in self.request_history if t > window_start]
            self.request_history = deque(recent)
            return len(recent) < 120
        return True
    
    def record_request(self):
        self.request_history.append(time.time())
        self.total_requests += 1


class KeyManager:
    def __init__(self, pexels_keys, pixabay_keys, coverr_keys=None, vecteezy_keys=None):
        self.pexels_keys = [APIKey(k["name"], k["key"], "pexels") for k in pexels_keys if k.get("key")]
        self.pixabay_keys = [APIKey(k["name"], k["key"], "pixabay") for k in pixabay_keys if k.get("key")]
        self.coverr_keys = [APIKey(k["name"], k["key"], "coverr") for k in (coverr_keys or []) if k.get("key")]
        self.vecteezy_keys = [APIKey(k["name"], k["key"], "vecteezy") for k in (vecteezy_keys or []) if k.get("key")]
        self.pexels_idx = 0
        self.pixabay_idx = 0
        self.coverr_idx = 0
        self.vecteezy_idx = 0
        self._lock = threading.Lock()
    
    def get_pexels_key(self):
        with self._lock:
            if not self.pexels_keys:
                return None
            for _ in range(len(self.pexels_keys)):
                key = self.pexels_keys[self.pexels_idx]
                self.pexels_idx = (self.pexels_idx + 1) % len(self.pexels_keys)
                if key.can_use():
                    return key
            return None
    
    def get_pixabay_key(self):
        with self._lock:
            if not self.pixabay_keys:
                return None
            for _ in range(len(self.pixabay_keys)):
                key = self.pixabay_keys[self.pixabay_idx]
                self.pixabay_idx = (self.pixabay_idx + 1) % len(self.pixabay_keys)
                if key.can_use():
                    return key
            return None

    def get_vecteezy_key(self):
        with self._lock:
            if not self.vecteezy_keys:
                return None
            for _ in range(len(self.vecteezy_keys)):
                key = self.vecteezy_keys[self.vecteezy_idx]
                self.vecteezy_idx = (self.vecteezy_idx + 1) % len(self.vecteezy_keys)
                if key.can_use():
                    return key
            return None
    
    def get_coverr_key(self):
        with self._lock:
            if not self.coverr_keys:
                return None
            for _ in range(len(self.coverr_keys)):
                key = self.coverr_keys[self.coverr_idx]
                self.coverr_idx = (self.coverr_idx + 1) % len(self.coverr_keys)
                if key.can_use():
                    return key
            return None


# ═══════════════════════════════════════════════════════════════════
# API CLIENTS
# ═══════════════════════════════════════════════════════════════════

class PexelsAPI:
    VIDEOS_URL = "https://api.pexels.com/videos"
    PHOTOS_URL = "https://api.pexels.com/v1"
    
    def __init__(self, key_manager):
        self.km = key_manager
    
    def search_videos(self, query, per_page=30):
        key = self.km.get_pexels_key() if self.km else None
        if self.km and not key:
            return []
        
        url = f"{self.VIDEOS_URL}/search"
        params = {"query": query, "per_page": per_page, "orientation": "landscape"}
        headers = {"Authorization": key.key if key else ""}
        
        try:
            r = requests.get(url, headers=headers, params=params, timeout=15)
            if key:
                key.record_request()
            if r.status_code != 200:
                return []
            data = r.json()
            
            items = []
            for v in data.get("videos", []):
                best = self._best_video(v.get("video_files", []))
                if not best:
                    continue
                
                thumb_url = None
                pics = v.get("video_pictures", [])
                if pics:
                    thumb_url = pics[0].get("picture", "")
                if not thumb_url:
                    thumb_url = v.get("image", "")
                
                items.append({
                    "source": "pexels",
                    "type": "video",
                    "id": v["id"],
                    "thumb_url": thumb_url,
                    "download_url": best["link"],
                    "width": best["width"],
                    "height": best["height"],
                    "duration": v.get("duration", 0),
                    "author": v.get("user", {}).get("name", "Unknown"),
                    "author_url": v.get("user", {}).get("url", ""),
                    "page_url": v.get("url", ""),
                    "search_query": query,
                })
            return items
        except Exception as e:
            print(f"[PexelsAPI] search_videos error: {e}")
            return []
    
    def search_photos(self, query, per_page=30):
        key = self.km.get_pexels_key() if self.km else None
        if self.km and not key:
            return []
        
        url = f"{self.PHOTOS_URL}/search"
        params = {"query": query, "per_page": per_page, "orientation": "landscape"}
        headers = {"Authorization": key.key if key else ""}
        
        try:
            r = requests.get(url, headers=headers, params=params, timeout=15)
            if key:
                key.record_request()
            if r.status_code != 200:
                return []
            data = r.json()
            
            items = []
            for p in data.get("photos", []):
                src = p.get("src", {})
                thumb_url = src.get("medium") or src.get("small")
                download_url = src.get("large") or src.get("large2x") or src.get("original")
                if not download_url or not thumb_url:
                    continue
                items.append({
                    "source": "pexels",
                    "type": "photo",
                    "id": p["id"],
                    "thumb_url": thumb_url,
                    "download_url": download_url,
                    "width": p.get("width", 0),
                    "height": p.get("height", 0),
                    "duration": 0,
                    "author": p.get("photographer", "Unknown"),
                    "author_url": p.get("photographer_url", ""),
                    "page_url": p.get("url", ""),
                    "search_query": query,
                })
            return items
        except Exception as e:
            print(f"[PexelsAPI] search_photos error: {e}")
            return []
    
    def refresh_video_url(self, video_id, query):
        """Refresh URL nếu bị expired (cho SmartDownloader)"""
        key = self.km.get_pexels_key() if self.km else None
        if not key:
            return None
        try:
            url = f"{self.VIDEOS_URL}/search"
            params = {"query": query, "per_page": 30, "orientation": "landscape"}
            headers = {"Authorization": key.key}
            r = requests.get(url, headers=headers, params=params, timeout=15)
            key.record_request()
            if r.status_code != 200:
                return None
            data = r.json()
            for v in data.get("videos", []):
                if v["id"] == video_id:
                    best = self._best_video(v.get("video_files", []))
                    if best:
                        return best["link"]
            return None
        except Exception:
            return None
    
    def _best_video(self, files):
        if not files:
            return None
        mp4 = [f for f in files if f.get("file_type") == "video/mp4"]
        files = mp4 if mp4 else files
        files = sorted(files, key=lambda f: (f.get("width", 0) * f.get("height", 0)), reverse=True)
        return files[0] if files else None
    
    def test_key(self, key_str):
        try:
            r = requests.get(
                f"{self.VIDEOS_URL}/search",
                headers={"Authorization": key_str},
                params={"query": "test", "per_page": 1}, timeout=10
            )
            if r.status_code == 200:
                return True, "Key valid"
            elif r.status_code == 401:
                return False, "Key invalid"
            elif r.status_code == 429:
                return True, "Quota exceeded but valid"
            else:
                return False, f"HTTP {r.status_code}"
        except Exception as e:
            return False, str(e)[:50]


class PixabayAPI:
    API_URL = "https://pixabay.com/api/"
    VIDEO_URL = "https://pixabay.com/api/videos/"

    def __init__(self, key_manager):
        self.km = key_manager

    def _get_key(self):
        return self.km.get_pixabay_key() if self.km else None

    def search_photos(self, query, per_page=30):
        key = self._get_key()
        if self.km and not key:
            return []
        params = {
            "key": key.key if key else "",
            "q": query,
            "per_page": min(per_page, 200),
            "image_type": "photo",
            "orientation": "horizontal",
            "safesearch": "true",
        }
        try:
            r = requests.get(self.API_URL, params=params, timeout=15)
            if key:
                key.record_request()
            if r.status_code != 200:
                print(f"[PixabayAPI] photos HTTP {r.status_code}: {r.text[:120]}")
                return []
            items = []
            for p in r.json().get("hits", []):
                thumb_url = p.get("webformatURL") or p.get("previewURL")
                download_url = p.get("largeImageURL") or p.get("webformatURL")
                if not thumb_url or not download_url:
                    continue
                user = p.get("user", "Unknown")
                user_id = p.get("user_id", "")
                items.append({
                    "source": "pixabay",
                    "type": "photo",
                    "id": p.get("id"),
                    "thumb_url": thumb_url,
                    "download_url": download_url,
                    "width": p.get("imageWidth", 0),
                    "height": p.get("imageHeight", 0),
                    "duration": 0,
                    "author": user,
                    "author_url": f"https://pixabay.com/users/{user}-{user_id}/",
                    "page_url": p.get("pageURL", ""),
                    "search_query": query,
                })
            return items
        except Exception as e:
            print(f"[PixabayAPI] search_photos error: {e}")
            return []

    def search_videos(self, query, per_page=30):
        key = self._get_key()
        if self.km and not key:
            return []
        params = {
            "key": key.key if key else "",
            "q": query,
            "per_page": min(per_page, 200),
            "video_type": "film",
            "safesearch": "true",
        }
        try:
            r = requests.get(self.VIDEO_URL, params=params, timeout=15)
            if key:
                key.record_request()
            if r.status_code != 200:
                print(f"[PixabayAPI] videos HTTP {r.status_code}: {r.text[:120]}")
                return []
            items = []
            for v in r.json().get("hits", []):
                videos = v.get("videos", {})
                best = videos.get("large") or videos.get("medium") or videos.get("small") or videos.get("tiny")
                if not best or not best.get("url"):
                    continue
                user = v.get("user", "Unknown")
                user_id = v.get("user_id", "")
                picture_id = v.get("picture_id")
                items.append({
                    "source": "pixabay",
                    "type": "video",
                    "id": v.get("id"),
                    "thumb_url": f"https://i.vimeocdn.com/video/{picture_id}_640x360.jpg" if picture_id else "",
                    "download_url": best.get("url"),
                    "width": best.get("width", 0),
                    "height": best.get("height", 0),
                    "duration": v.get("duration", 0),
                    "author": user,
                    "author_url": f"https://pixabay.com/users/{user}-{user_id}/",
                    "page_url": v.get("pageURL", ""),
                    "search_query": query,
                })
            return items
        except Exception as e:
            print(f"[PixabayAPI] search_videos error: {e}")
            return []

    def refresh_video_url(self, video_id, query):
        for item in self.search_videos(query, per_page=30):
            if item.get("id") == video_id:
                return item.get("download_url")
        return None

    def test_key(self, key_str):
        try:
            r = requests.get(self.API_URL, params={"key": key_str, "q": "test", "per_page": 3}, timeout=10)
            if r.status_code == 200:
                return True, "Key valid"
            if r.status_code == 429:
                return True, "Quota exceeded but valid"
            return False, f"HTTP {r.status_code}: {r.text[:60]}"
        except Exception as e:
            return False, str(e)[:50]


class VecteezyAPI:
    API_URL = "https://www.vecteezy.com/v1/resources"

    def __init__(self, key_manager):
        self.km = key_manager

    def _get_key(self):
        return self.km.get_vecteezy_key() if self.km else None

    def _headers(self, key):
        return {"Authorization": f"Bearer {key.key if key else ''}", "Accept": "application/json"}

    def _extract_dimensions(self, resource):
        sizes = resource.get("file_sizes") or []
        if sizes:
            best = max(sizes, key=lambda x: (x.get("width", 0) or 0) * (x.get("height", 0) or 0))
            return best.get("width", 0) or 0, best.get("height", 0) or 0
        dims = resource.get("thumbnail_dimensions") or {}
        return dims.get("width", 0) or 0, dims.get("height", 0) or 0

    def _download_url(self, resource_id, content_type, key):
        file_type = "mp4" if content_type == "video" else "jpg"
        params = {"file_type": file_type}
        if content_type == "video":
            params["file_size"] = "medium"
        try:
            r = requests.get(f"{self.API_URL}/{resource_id}/download", headers=self._headers(key), params=params, timeout=20)
            key.record_request()
            if r.status_code != 200:
                return ""
            data = r.json()
            return data.get("url") or data.get("inline_url") or ""
        except Exception as e:
            print(f"[VecteezyAPI] download_url error: {e}")
            return ""

    def _search(self, query, content_type, per_page=30):
        key = self._get_key()
        if self.km and not key:
            return []
        params = {
            "term": query,
            "content_type": content_type,
            "page": 1,
            "per_page": min(per_page, 100),
            "sort_by": "relevance",
            "family_friendly": "true",
        }
        try:
            r = requests.get(self.API_URL, headers=self._headers(key), params=params, timeout=20)
            if key:
                key.record_request()
            if r.status_code != 200:
                print(f"[VecteezyAPI] {content_type} HTTP {r.status_code}: {r.text[:160]}")
                return []
            items = []
            for res in r.json().get("resources", []):
                rid = res.get("id")
                if not rid:
                    continue
                thumb_url = res.get("thumbnail_url") or res.get("thumbnail_2x_url") or res.get("preview_url") or res.get("preview_2x_url") or ""
                download_url = self._download_url(rid, content_type, key) if key else ""
                if not download_url:
                    continue
                width, height = self._extract_dimensions(res)
                items.append({
                    "source": "vecteezy",
                    "type": "video" if content_type == "video" else "photo",
                    "id": rid,
                    "thumb_url": thumb_url,
                    "download_url": download_url,
                    "width": width,
                    "height": height,
                    "duration": res.get("duration", 0) or 0,
                    "author": "Vecteezy",
                    "author_url": "https://www.vecteezy.com/",
                    "page_url": res.get("url") or res.get("link") or "",
                    "search_query": query,
                })
            return items
        except Exception as e:
            print(f"[VecteezyAPI] search_{content_type} error: {e}")
            return []

    def search_photos(self, query, per_page=30):
        return self._search(query, "photo", per_page)

    def search_videos(self, query, per_page=30):
        return self._search(query, "video", per_page)

    def test_key(self, key_str):
        try:
            r = requests.get(self.API_URL, headers={"Authorization": f"Bearer {key_str}", "Accept": "application/json"}, params={"term": "test", "content_type": "photo", "per_page": 1}, timeout=12)
            if r.status_code == 200:
                return True, "Key valid"
            if r.status_code in (402, 429):
                return True, "Quota exceeded but valid"
            if r.status_code == 401:
                return False, "Key invalid"
            return False, f"HTTP {r.status_code}: {r.text[:60]}"
        except Exception as e:
            return False, str(e)[:50]


# ═══════════════════════════════════════════════════════════════════
# THUMBNAIL CACHE
# ═══════════════════════════════════════════════════════════════════

class ThumbnailCache:
    """Cache thumbnails as bytes + QPixmap for fast UI"""
    
    def __init__(self, cache_dir):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self._lock = threading.Lock()
        self._pixmap_cache = {}  # url -> QPixmap (in-memory)
    
    def get_cache_path(self, url):
        url_hash = hashlib.md5(url.encode()).hexdigest()
        return self.cache_dir / f"{url_hash}.jpg"
    
    def get_pixmap(self, url):
        """Get QPixmap from cache (memory or disk). Returns None if not cached."""
        # In-memory first
        if url in self._pixmap_cache:
            return self._pixmap_cache[url]
        
        # Disk cache
        cache_path = self.get_cache_path(url)
        if cache_path.exists():
            try:
                pixmap = QPixmap(str(cache_path))
                if not pixmap.isNull():
                    self._pixmap_cache[url] = pixmap
                    return pixmap
            except Exception:
                pass
        return None
    
    def fetch_pixmap(self, url, max_retries=3):
        """Fetch from URL, save to disk, return QPixmap. Threaded use.
        
        v4.5 fix:
        - Session reuse (connection pooling)
        - Tăng timeout 20s → 30s cho slow CDN
        - Force HTTP/1.1 (HTTP/2 đôi khi block với Pixabay)
        - Retry với exponential backoff
        - Headers giả browser
        """
        # Check cache first
        existing = self.get_pixmap(url)
        if existing is not None:
            return existing
        
        # Build headers like a real browser to bypass anti-bot
        headers = {
            "User-Agent": get_random_ua(),
            "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Sec-Fetch-Dest": "image",
            "Sec-Fetch-Mode": "no-cors",
            "Sec-Fetch-Site": "cross-site",
            "Connection": "keep-alive",
        }
        
        # Add Referer based on CDN source
        if "pexels.com" in url or "pexelscdn.com" in url:
            headers["Referer"] = "https://www.pexels.com/"
            headers["Origin"] = "https://www.pexels.com"
        elif "pixabay.com" in url or "pixabaycdn.com" in url:
            headers["Referer"] = "https://pixabay.com/"
            headers["Origin"] = "https://pixabay.com"
        elif "coverr.co" in url or "storage.coverr.co" in url:
            headers["Referer"] = "https://coverr.co/"
            headers["Origin"] = "https://coverr.co"
        elif "motionarray.com" in url or "motionarray.imgix.net" in url or "cms-artifacts.motionarray.com" in url:
            headers["Referer"] = "https://motionarray.com/"
            headers["Origin"] = "https://motionarray.com"
        elif "vimeocdn.com" in url:
            headers["Referer"] = "https://pixabay.com/"
        
        # Retry với delay tăng dần
        retry_delays = [1.0, 2.5, 5.0]
        
        # Use shared session if available, otherwise create one
        if not hasattr(self, '_session'):
            self._session = requests.Session()
            # Force HTTP/1.1 (some CDNs block HTTP/2 from Python)
            adapter = requests.adapters.HTTPAdapter(
                pool_connections=10,
                pool_maxsize=10,
                max_retries=0  # We handle retries manually
            )
            self._session.mount('http://', adapter)
            self._session.mount('https://', adapter)
        
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    time.sleep(retry_delays[min(attempt - 1, len(retry_delays) - 1)])
                
                # Tăng timeout từ 20s → 30s cho slow CDN với VPN
                r = self._session.get(
                    url, 
                    headers=headers, 
                    timeout=(10, 30),  # (connect, read)
                    stream=False,
                    allow_redirects=True
                )
                
                if r.status_code == 200:
                    img_data = r.content
                    if len(img_data) < 500:
                        if "motionarray" in url:
                            print(f"[ThumbCache] MotionArray small response: {len(img_data)} bytes - {url[:80]}")
                        continue
                    
                    try:
                        cache_path = self.get_cache_path(url)
                        with self._lock:
                            with open(cache_path, 'wb') as f:
                                f.write(img_data)
                    except Exception:
                        pass
                    
                    pixmap = QPixmap()
                    if pixmap.loadFromData(img_data) and not pixmap.isNull():
                        self._pixmap_cache[url] = pixmap
                        return pixmap
                    if "motionarray" in url:
                        print(f"[ThumbCache] MotionArray pixmap load fail (data {len(img_data)}b)")
                    continue
                
                elif r.status_code in (429, 503):
                    if "motionarray" in url:
                        print(f"[ThumbCache] MotionArray HTTP {r.status_code} (rate limit)")
                    continue
                elif r.status_code in (403, 404):
                    if "motionarray" in url:
                        print(f"[ThumbCache] MotionArray HTTP {r.status_code} - {url[:100]}")
                    if attempt == 0:
                        continue
                    return None
                else:
                    if "motionarray" in url:
                        print(f"[ThumbCache] MotionArray HTTP {r.status_code}")
                    continue
                    
            except requests.exceptions.Timeout:
                if "motionarray" in url:
                    print(f"[ThumbCache] MotionArray timeout (attempt {attempt+1})")
                continue
            except requests.exceptions.ConnectionError as e:
                if "motionarray" in url:
                    print(f"[ThumbCache] MotionArray connection error: {str(e)[:80]}")
                continue
            except Exception as e:
                if "motionarray" in url:
                    print(f"[ThumbCache] MotionArray unknown error: {str(e)[:80]}")
                continue
        
        return None


# ═══════════════════════════════════════════════════════════════════
# ANTI-BLOCK: AdaptiveRateLimiter
# ═══════════════════════════════════════════════════════════════════

class AdaptiveRateLimiter:
    """Tu dong dieu chinh delay dua tren fail rate"""
    
    def __init__(self):
        self.current_delay = DEFAULT_DOWNLOAD_DELAY
        self.recent_results = deque(maxlen=10)
        self._lock = threading.Lock()
    
    def get_delay(self):
        """Get delay voi jitter"""
        with self._lock:
            return get_jittered_delay(self.current_delay)
    
    def record_result(self, success):
        """Record ket qua download, tu dieu chinh delay"""
        with self._lock:
            self.recent_results.append(success)
            if len(self.recent_results) < 5:
                return
            fail_rate = self.recent_results.count(False) / len(self.recent_results)
            if fail_rate > DELAY_INCREASE_THRESHOLD:
                self.current_delay = min(MAX_DOWNLOAD_DELAY, self.current_delay * 1.5)
            elif fail_rate < DELAY_DECREASE_THRESHOLD:
                self.current_delay = max(MIN_DOWNLOAD_DELAY, self.current_delay * 0.9)
    
    def get_stats(self):
        """Return (delay, fail_rate, sample_size)"""
        with self._lock:
            fail_rate = (self.recent_results.count(False) / len(self.recent_results)
                        if self.recent_results else 0)
            return self.current_delay, fail_rate, len(self.recent_results)


# ═══════════════════════════════════════════════════════════════════
# ANTI-BLOCK: BlockDetector
# ═══════════════════════════════════════════════════════════════════

class BlockDetector:
    """Detect IP block khi co qua nhieu 403 lien tiep"""
    
    def __init__(self, threshold=BLOCK_DETECTION_THRESHOLD):
        self.threshold = threshold
        self.consecutive_403 = 0
        self.block_count = 0
        self._lock = threading.Lock()
    
    def record_403(self):
        """Returns True if block detected"""
        with self._lock:
            self.consecutive_403 += 1
            if self.consecutive_403 >= self.threshold:
                self.consecutive_403 = 0
                self.block_count += 1
                return True
        return False
    
    def record_success(self):
        """Reset counter khi co success"""
        with self._lock:
            self.consecutive_403 = 0
    
    def get_block_count(self):
        with self._lock:
            return self.block_count


# ═══════════════════════════════════════════════════════════════════
# SMART DOWNLOADER - with retry + URL refresh
# ═══════════════════════════════════════════════════════════════════

class SmartDownloader:
    """Downloader voi smart retry + URL refresh on 403"""
    
    def __init__(self, pexels_api=None, pixabay_api=None, should_stop=None):
        self.pexels = pexels_api
        self.pixabay = pixabay_api
        # should_stop: callable() -> bool, để check stop signal trong khi download
        self.should_stop = should_stop or (lambda: False)
    
    def download(self, item, output_path):
        """
        Download file voi smart retry.
        Returns (success: bool, error_msg: str, error_type: str)
        """
        url = item["download_url"]
        media_id = item["id"]
        source = item["source"]
        media_type = item.get("type", "video")
        query = item.get("search_query", "")
        
        # Pexels: HTTP request truyền thống
        last_error = None
        last_error_type = "unknown"
        
        # === ATTEMPT 1-3 with retries ===
        for attempt in range(MAX_RETRIES):
            if attempt > 0:
                delay = RETRY_DELAYS[min(attempt - 1, len(RETRY_DELAYS) - 1)]
                time.sleep(delay)
            
            success, error_msg, error_type = self._try_download(url, output_path, media_type)
            
            if success:
                return True, "", "success"
            
            last_error = error_msg
            last_error_type = error_type
            
            # Don't retry if forbidden/not_found - won't help
            if error_type in ("forbidden", "not_found", "expired_url"):
                break
        
        # === FALLBACK: Refresh URL if video forbidden/not_found ===
        if (media_type == "video" 
            and last_error_type in ("forbidden", "not_found", "expired_url") 
            and query):
            
            new_url = None
            if source == "pexels" and self.pexels:
                new_url = self.pexels.refresh_video_url(media_id, query)
            elif source == "pixabay" and self.pixabay:
                new_url = self.pixabay.refresh_video_url(media_id, query)
            
            if new_url and new_url != url:
                time.sleep(1)
                success, error_msg, error_type = self._try_download(new_url, output_path, media_type)
                if success:
                    return True, "", "success_after_refresh"
                last_error = error_msg
                last_error_type = error_type
        
        return False, last_error, last_error_type
    
    def _try_download(self, url, output_path, media_type="video"):
        """Try downloading once. Returns (success, error_msg, error_type)"""
        try:
            # Build headers like a real browser
            # Referer is CRITICAL for Pexels CDN
            headers = {
                "User-Agent": get_random_ua(),
                "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8" if media_type == "photo" 
                          else "video/mp4,video/*;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "Cache-Control": "no-cache",
                "Sec-Fetch-Dest": "image" if media_type == "photo" else "video",
                "Sec-Fetch-Mode": "no-cors",
                "Sec-Fetch-Site": "cross-site",
            }
            
            # Add Referer based on source CDN
            if "pexels.com" in url or "pexelscdn.com" in url:
                headers["Referer"] = "https://www.pexels.com/"
                headers["Origin"] = "https://www.pexels.com"
            elif "pixabay.com" in url or "pixabaycdn.com" in url:
                headers["Referer"] = "https://pixabay.com/"
                headers["Origin"] = "https://pixabay.com"
            elif "coverr.co" in url or "storage.coverr.co" in url:
                headers["Referer"] = "https://coverr.co/"
                headers["Origin"] = "https://coverr.co"
            elif "motionarray.com" in url or "motionarray.imgix.net" in url or "cms-artifacts.motionarray.com" in url:
                headers["Referer"] = "https://motionarray.com/"
                headers["Origin"] = "https://motionarray.com"
            
            with requests.get(url, stream=True, timeout=60, headers=headers) as r:
                if r.status_code == 403:
                    return False, "403 Forbidden", "forbidden"
                elif r.status_code == 404:
                    return False, "404 Not Found", "not_found"
                elif r.status_code == 429:
                    return False, "429 Rate Limited", "rate_limit"
                r.raise_for_status()
                
                content_type = r.headers.get('Content-Type', '')
                if 'html' in content_type.lower():
                    return False, "Got HTML instead", "expired_url"
                
                with open(output_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        if self.should_stop():
                            # User clicked stop → abort this download
                            try:
                                f.close()
                                output_path.unlink(missing_ok=True)
                            except Exception:
                                pass
                            return False, "Stopped by user", "stopped"
                        if chunk:
                            f.write(chunk)
            
            min_size = 5 * 1024 if media_type == "photo" else 1024
            if output_path.stat().st_size < min_size:
                output_path.unlink()
                return False, "File too small", "expired_url"
            
            return True, "", "success"
        
        except requests.exceptions.Timeout:
            return False, "Timeout", "timeout"
        except requests.exceptions.ConnectionError as e:
            return False, f"Connection: {str(e)[:50]}", "network"
        except Exception as e:
            return False, f"Error: {str(e)[:80]}", "unknown"


# ═══════════════════════════════════════════════════════════════════
# OLD Downloader kept for compatibility (delegates to SmartDownloader)
# ═══════════════════════════════════════════════════════════════════

class Downloader:
    @staticmethod
    def download_file(url, output_path, max_retries=3):
        """Legacy interface - simple download with retries"""
        last_error = None
        for attempt in range(max_retries):
            if attempt > 0:
                time.sleep(RETRY_DELAYS[min(attempt - 1, len(RETRY_DELAYS) - 1)])
            try:
                headers = {"User-Agent": get_random_ua()}
                with requests.get(url, stream=True, timeout=60, headers=headers) as r:
                    if r.status_code != 200:
                        last_error = f"HTTP {r.status_code}"
                        continue
                    with open(output_path, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                if output_path.stat().st_size < 1024:
                    output_path.unlink()
                    last_error = "File too small"
                    continue
                return True, ""
            except Exception as e:
                last_error = str(e)[:80]
        return False, last_error


# ═══════════════════════════════════════════════════════════════════
# UTILITIES
# ═══════════════════════════════════════════════════════════════════

def sanitize_filename(name):
    name = re.sub(r'[<>:"/\\|?*]', '', name)
    name = re.sub(r'\s+', '_', name)
    return name[:60]


def format_timestamp_for_folder(srt_time):
    if not srt_time:
        return "00m00s"
    srt_time = srt_time.split(',')[0]
    parts = srt_time.split(':')
    if len(parts) != 3:
        return "00m00s"
    h, m, s = parts
    try:
        if int(h) > 0:
            return f"{int(h):02d}h{int(m):02d}m{int(s):02d}s"
        return f"{int(m):02d}m{int(s):02d}s"
    except ValueError:
        return "00m00s"


def get_scene_folder_name(scene):
    scene_id = str(scene.get("id", 0)).zfill(3)
    time_slug = format_timestamp_for_folder(scene.get("time_start", ""))
    if "folder_name" in scene:
        return scene["folder_name"]
    primary = scene.get("primary_keywords", [])
    keyword = primary[0] if primary else "scene"
    keyword_slug = sanitize_filename(keyword.lower().replace(" ", "_"))[:30]
    return f"{scene_id}__{time_slug}__{keyword_slug}"


def extract_scenes_from_json(data):
    scenes = []
    if not isinstance(data, dict):
        return scenes
    
    try:
        if "scenes" in data and isinstance(data["scenes"], list):
            scenes.extend(data["scenes"])
        if "part_a_scenes" in data and isinstance(data["part_a_scenes"], list):
            scenes.extend(data["part_a_scenes"])
        if "part_b_segments" in data and isinstance(data["part_b_segments"], list):
            for seg in data["part_b_segments"]:
                if not isinstance(seg, dict):
                    continue
                seg_id = seg.get("id") or seg.get("segment_id") or len(scenes) + 1
                scenes.append({
                    "id": f"seg_{seg_id}",
                    "time_start": seg.get("time_start", ""),
                    "time_end": seg.get("time_end", ""),
                    "duration_seconds": seg.get("duration_seconds", 0),
                    "dialogue_es": seg.get("dialogue_es_excerpt", ""),
                    "primary_keywords": (seg.get("keywords") or [])[:5],
                    "secondary_keywords": (seg.get("keywords") or [])[5:],
                    "_is_segment": True,
                    "_segment_topic": seg.get("segment_topic", "")
                })
    except Exception as e:
        print(f"[extract_scenes] Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
    
    return scenes


def add_duration_to_pixmap(pixmap, duration_seconds):
    """Add duration overlay using QPainter (fast, native)
    
    Vẽ overlay góc phải dưới với padding rộng + font lớn hơn cho dễ đọc.
    """
    if not duration_seconds or pixmap.isNull():
        return pixmap
    
    text = format_duration(duration_seconds)
    
    # Create a new pixmap to draw on
    result = QPixmap(pixmap)
    painter = QPainter(result)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    
    # Font - tăng size từ 9 lên 10 cho rõ
    font = QFont("Segoe UI", 10, QFont.Weight.Bold)
    painter.setFont(font)
    metrics = QFontMetrics(font)
    text_w = metrics.horizontalAdvance(text)
    text_h = metrics.height()
    
    # Position bottom-right với margin lớn hơn
    margin = 6  # khoảng cách từ edge
    padding_x = 6  # padding trong box (trái phải)
    padding_y = 3  # padding trong box (trên dưới)
    
    box_w = text_w + padding_x * 2
    box_h = text_h + padding_y * 2
    box_x = result.width() - box_w - margin
    box_y = result.height() - box_h - margin
    
    # Background đen mờ, bo góc đẹp hơn
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QBrush(QColor(0, 0, 0, 200)))
    painter.drawRoundedRect(box_x, box_y, box_w, box_h, 4, 4)
    
    # Text trắng - căn giữa trong box
    painter.setPen(QColor(255, 255, 255))
    text_x = box_x + padding_x
    text_y = box_y + padding_y + text_h - metrics.descent()
    painter.drawText(text_x, text_y, text)
    
    painter.end()
    return result


# ═══════════════════════════════════════════════════════════════════
# CUSTOM WIDGETS - 1ClickSub Studio Widgets
# ═══════════════════════════════════════════════════════════════════

class StatBox(QFrame):
    """Studio glassmorphic stat box with glowing value and sleek label"""
    
    def __init__(self, value, label, color, parent=None):
        super().__init__(parent)
        self.setObjectName("statBox")
        self.setStyleSheet(f"""
            #statBox {{
                background: {color};
                border-radius: 12px;
                border: 1px solid rgba(255, 255, 255, 0.12);
            }}
        """)
        self.setMinimumHeight(64)
        self.setMaximumHeight(74)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(1)
        
        self.value_label = QLabel(str(value))
        self.value_label.setStyleSheet("color: #ffffff; font-size: 20px; font-weight: 850; background: transparent;")
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.value_label)
        
        label_lbl = QLabel(label.upper())
        label_lbl.setStyleSheet("color: rgba(255, 255, 255, 0.75); font-size: 9px; font-weight: 750; letter-spacing: 0.8px; background: transparent;")
        label_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label_lbl)
    
    def set_value(self, value):
        self.value_label.setText(str(value))


class Badge(QLabel):
    """Modern studio pill badge with subtle glow"""
    
    def __init__(self, text, color, parent=None):
        super().__init__(text, parent)
        self.setStyleSheet(f"""
            background-color: {color};
            color: #ffffff;
            border-radius: 5px;
            padding: 2px 7px;
            font-size: 9px;
            font-weight: 800;
            letter-spacing: 0.5px;
        """)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)


# ═══════════════════════════════════════════════════════════════════
# STATUS PANEL - 1ClickSub Studio Live Monitor
# ═══════════════════════════════════════════════════════════════════

class StatusPanel(QFrame):
    """Panel hiển thị status realtime phong cách 1ClickSub Studio"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("statusPanel")
        self.setStyleSheet("""
            #statusPanel {
                background-color: #131926;
                border: 1px solid #1e293b;
                border-radius: 12px;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        
        # === Header với state badge ===
        header_h = QHBoxLayout()
        header_h.setSpacing(6)
        
        header_label = QLabel("⚡ STUDIO MONITOR")
        header_label.setStyleSheet("color: #818cf8; font-size: 11px; font-weight: 800; letter-spacing: 1.2px;")
        header_h.addWidget(header_label)
        
        header_h.addStretch()
        
        self.state_badge = QLabel("● READY")
        self.state_badge.setStyleSheet("""
            background-color: rgba(99, 102, 241, 0.15);
            color: #818cf8;
            border: 1px solid rgba(99, 102, 241, 0.35);
            border-radius: 6px;
            padding: 3px 10px;
            font-size: 10px;
            font-weight: 800;
            letter-spacing: 0.5px;
        """)
        header_h.addWidget(self.state_badge)
        
        layout.addLayout(header_h)
        
        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("background-color: #1e293b; max-height: 1px;")
        layout.addWidget(sep)
        
        # === Main message ===
        self.main_label = QLabel("Hệ thống sẵn sàng")
        self.main_label.setStyleSheet("color: #f8fafc; font-size: 12px; font-weight: 650; padding: 2px 0;")
        self.main_label.setWordWrap(True)
        layout.addWidget(self.main_label)
        
        # === Progress text ===
        self.progress_label = QLabel("")
        self.progress_label.setStyleSheet("color: #38bdf8; font-size: 11px; font-family: 'Consolas', monospace; font-weight: 600; padding: 1px 0;")
        self.progress_label.setWordWrap(True)
        layout.addWidget(self.progress_label)
        
        # === Progress bar ===
        self.progress_bar = QFrame()
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setStyleSheet("""
            QFrame {
                background-color: #0e131d;
                border-radius: 4px;
                border: 1px solid #1e293b;
            }
        """)
        self.progress_fill = QFrame(self.progress_bar)
        self.progress_fill.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #6366f1, stop:0.5 #8b5cf6, stop:1 #06b6d4);
                border-radius: 4px;
            }
        """)
        self.progress_fill.setFixedHeight(8)
        self.progress_fill.setFixedWidth(0)
        layout.addWidget(self.progress_bar)
        
        # === Counter cards (3 micro cards) ===
        counters_h = QHBoxLayout()
        counters_h.setSpacing(6)
        
        self.counter_scenes = self._create_counter("SCENES", "0/0", "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #1e293b, stop:1 #1e3a8a)")
        counters_h.addWidget(self.counter_scenes['widget'])
        
        self.counter_items = self._create_counter("ITEMS", "0", "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #1e293b, stop:1 #4c1d95)")
        counters_h.addWidget(self.counter_items['widget'])
        
        self.counter_selected = self._create_counter("ĐÃ CHỌN", "0", "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #1e293b, stop:1 #064e3b)")
        counters_h.addWidget(self.counter_selected['widget'])
        
        layout.addLayout(counters_h)
        
        # === Activity log header ===
        log_header = QLabel("📜 CONSOLE LOG")
        log_header.setStyleSheet("color: #64748b; font-size: 10px; font-weight: 800; letter-spacing: 1px; padding-top: 4px;")
        layout.addWidget(log_header)
        
        # === Activity log ===
        self.activity_log = QTextEdit()
        self.activity_log.setReadOnly(True)
        self.activity_log.setStyleSheet("""
            QTextEdit {
                background-color: #0c0f17;
                color: #cbd5e1;
                border: 1px solid #1e293b;
                border-radius: 8px;
                padding: 6px;
                font-size: 10px;
                font-family: 'Consolas', 'Cascadia Code', monospace;
            }
        """)
        self.activity_log.setMinimumHeight(120)
        layout.addWidget(self.activity_log, 1)  # stretch
        
        # === Cooldown notice ===
        self.cooldown_label = QLabel("")
        self.cooldown_label.setStyleSheet("""
            color: #f87171;
            font-size: 11px;
            font-weight: 750;
            background-color: rgba(239, 68, 68, 0.12);
            border: 1px solid rgba(239, 68, 68, 0.4);
            border-radius: 8px;
            padding: 6px;
        """)
        self.cooldown_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cooldown_label.setVisible(False)
        layout.addWidget(self.cooldown_label)
    
    def _create_counter(self, label, value, color):
        """Tạo 1 counter card nhỏ"""
        widget = QFrame()
        widget.setStyleSheet(f"""
            QFrame {{
                background: {color};
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 8px;
            }}
        """)
        lay = QVBoxLayout(widget)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(1)
        
        value_lbl = QLabel(value)
        value_lbl.setStyleSheet("color: #ffffff; font-size: 13px; font-weight: 850; background: transparent;")
        value_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(value_lbl)
        
        text_lbl = QLabel(label)
        text_lbl.setStyleSheet("color: rgba(255,255,255,0.7); font-size: 8px; font-weight: 750; background: transparent; letter-spacing: 0.5px;")
        text_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(text_lbl)
        
        return {'widget': widget, 'value': value_lbl, 'label': text_lbl}
    
    def update_counters(self, scenes_done=0, scenes_total=0, items=0, selected=0):
        """Update 3 counter cards"""
        self.counter_scenes['value'].setText(f"{scenes_done}/{scenes_total}")
        self.counter_items['value'].setText(str(items))
        self.counter_selected['value'].setText(str(selected))
    
    def add_log(self, message, level="info"):
        """Append message vào activity log"""
        from datetime import datetime
        ts = datetime.now().strftime("%H:%M:%S")
        
        color_map = {
            "info": "#94a3b8",
            "success": "#34d399",
            "warning": "#fbbf24",
            "error": "#f87171",
        }
        color = color_map.get(level, "#94a3b8")
        
        html = f'<span style="color: #475569">[{ts}]</span> <span style="color: {color}">{message}</span>'
        self.activity_log.append(html)
        
        scrollbar = self.activity_log.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        
        doc = self.activity_log.document()
        if doc.blockCount() > 200:
            cursor = self.activity_log.textCursor()
            cursor.movePosition(cursor.MoveOperation.Start)
            cursor.select(cursor.SelectionType.LineUnderCursor)
            cursor.removeSelectedText()
            cursor.deleteChar()
    
    def set_idle(self, message="Sẵn sàng"):
        self._set_state("● READY", "#818cf8", "rgba(99, 102, 241, 0.15)")
        self.main_label.setText(message)
        self.progress_label.setText("")
        self._set_progress(0)
        self.cooldown_label.setVisible(False)
    
    def set_searching(self, message=""):
        self._set_state("● SEARCHING", "#a78bfa", "rgba(167, 139, 250, 0.15)")
        self.main_label.setText("🔍 Đang search media...")
        if message:
            self.progress_label.setText(message)
        self.cooldown_label.setVisible(False)
    
    def set_downloading(self, message=""):
        self._set_state("● DOWNLOADING", "#38bdf8", "rgba(56, 189, 248, 0.15)")
        self.main_label.setText("⬇ Đang tải files...")
        if message:
            self.progress_label.setText(message)
        self.cooldown_label.setVisible(False)
    
    def set_done(self, success_count, fail_count):
        self._set_state("● COMPLETED", "#34d399", "rgba(52, 211, 153, 0.15)")
        self.main_label.setText("✅ Hoàn tất tải media!")
        self.progress_label.setText(f"{success_count} OK • {fail_count} lỗi")
        self._set_progress(100)
        self.cooldown_label.setVisible(False)
        self.add_log(f"Hoàn tất: {success_count} OK, {fail_count} lỗi",
                     "success" if fail_count == 0 else "warning")
    
    def set_stopped(self):
        self._set_state("● STOPPED", "#f87171", "rgba(239, 68, 68, 0.15)")
        self.main_label.setText("⏹ Đã dừng tác vụ")
        self.cooldown_label.setVisible(False)
        self.add_log("Đã dừng tác vụ", "warning")
    
    def set_progress(self, current, total, message=""):
        if total > 0:
            pct = int(current / total * 100)
            self._set_progress(pct)
            self.progress_label.setText(f"{current}/{total} ({pct}%)" + (f" • {message}" if message else ""))
    
    def set_stats(self, delay=None, fail_rate=None, blocks=None, via_refresh=None):
        """Update anti-block stats"""
        parts = []
        if delay is not None:
            arrow = ""
            if delay > 1.5:
                arrow = " ↑"
            elif delay < 0.7:
                arrow = " ↓"
            parts.append(f"Delay: {delay:.1f}s{arrow}")
        
        if fail_rate is not None:
            success_pct = (1 - fail_rate) * 100
            parts.append(f"Success: {success_pct:.0f}%")
        
        if via_refresh is not None and via_refresh > 0:
            parts.append(f"Refreshed: {via_refresh}")
        
        if blocks is not None and blocks > 0:
            parts.append(f"⚠ Blocks: {blocks}")
        
        if parts:
            self.progress_label.setText(self.progress_label.text() + "\n" + " • ".join(parts))
    
    def set_cooldown(self, remaining_seconds):
        """Show cooldown notice"""
        m = remaining_seconds // 60
        s = remaining_seconds % 60
        self._set_state("● COOLDOWN", "#f87171", "rgba(239, 68, 68, 0.15)")
        self.cooldown_label.setText(f"🚫 BLOCK DETECTED\nCooldown {m}:{s:02d} còn lại...")
        self.cooldown_label.setVisible(True)
    
    def end_cooldown(self):
        self.cooldown_label.setVisible(False)
    
    def _set_state(self, text, color, bg_color):
        self.state_badge.setText(text)
        self.state_badge.setStyleSheet(f"""
            background-color: {bg_color};
            color: {color};
            border: 1px solid {color};
            border-radius: 6px;
            padding: 3px 10px;
            font-size: 10px;
            font-weight: 800;
            letter-spacing: 0.5px;
        """)
    
    def _set_progress(self, percent):
        """Update visual progress bar"""
        percent = max(0, min(100, percent))
        total_width = self.progress_bar.width()
        if total_width <= 0:
            total_width = 200  # fallback
        fill_width = int(total_width * percent / 100)
        self.progress_fill.setFixedWidth(fill_width)
    
    def resizeEvent(self, event):
        super().resizeEvent(event)
        try:
            current_text = self.progress_label.text()
            if "%" in current_text:
                import re
                m = re.search(r'\((\d+)%\)', current_text)
                if m:
                    self._set_progress(int(m.group(1)))
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════════
# THUMBNAIL LOADER THREAD - for fetching thumbnails async
# ═══════════════════════════════════════════════════════════════════

class ThumbnailLoaderSignals(QObject):
    loaded = pyqtSignal(str, object)  # url, QPixmap
    failed = pyqtSignal(str)  # url


class ThumbnailLoader(QObject):
    def __init__(self, cache):
        super().__init__()
        self.cache = cache
        self.signals = ThumbnailLoaderSignals()
        self.executor = ThreadPoolExecutor(max_workers=2)
        self._pending = set()
        self._lock = threading.Lock()
    
    def load_async(self, url):
        with self._lock:
            if url in self._pending:
                return
            cached = self.cache.get_pixmap(url)
            if cached:
                self.signals.loaded.emit(url, cached)
                return
            self._pending.add(url)
        
        self.executor.submit(self._fetch_worker, url)
    
    def _fetch_worker(self, url):
        try:
            pixmap = self.cache.fetch_pixmap(url)
            with self._lock:
                self._pending.discard(url)
            if pixmap:
                self.signals.loaded.emit(url, pixmap)
            else:
                self.signals.failed.emit(url)
        except Exception:
            with self._lock:
                self._pending.discard(url)
            self.signals.failed.emit(url)
    
    def shutdown(self):
        self.executor.shutdown(wait=False)


# ═══════════════════════════════════════════════════════════════════
# THUMBNAIL CARD - 1ClickSub Studio Card Widget
# ═══════════════════════════════════════════════════════════════════

class ThumbnailCard(QFrame):
    """1 Studio card với thumbnail + badges + checkbox"""
    
    selectionChanged = pyqtSignal(dict, bool)  # item, is_selected
    clicked = pyqtSignal(dict)  # item
    retryRequested = pyqtSignal(dict)  # item
    
    def _on_thumb_clicked(self, event):
        if self.thumb_failed:
            self.retryRequested.emit(self.item)
        else:
            self.clicked.emit(self.item)
    
    def __init__(self, item, is_selected=False, parent=None):
        super().__init__(parent)
        self.item = item
        self.is_selected = is_selected
        self.thumb_loaded = False
        self.thumb_failed = False
        
        self.setFixedSize(CARD_WIDTH, CARD_HEIGHT)
        self.setObjectName("card")
        self._update_style()
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        
        # Thumbnail label
        self.thumb_label = QLabel()
        self.thumb_label.setFixedSize(THUMB_WIDTH, THUMB_HEIGHT)
        self.thumb_label.setStyleSheet("""
            background-color: #0c0f17;
            border-radius: 8px;
            color: #64748b;
            font-size: 11px;
            font-weight: 600;
        """)
        self.thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumb_label.setText("Loading...")
        self.thumb_label.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.thumb_label.mousePressEvent = self._on_thumb_clicked
        layout.addWidget(self.thumb_label)
        
        # Badges row
        badges = QHBoxLayout()
        badges.setSpacing(4)
        badges.setContentsMargins(0, 0, 0, 0)
        
        source_colors = {
            "pexels": "#059669",      # Emerald
            "pixabay": "#0284c7",     # Sky Blue
            "coverr": "#e11d48",      # Rose Red
            "motionarray": "#d97706",  # Amber
            "vecteezy": "#7c3aed",    # Violet
            "youtube": "#dc2626",     # Red
            "tiktok": "#0f172a",      # Slate
        }
        source_color = source_colors.get(item["source"], "#0284c7")
        badges.addWidget(Badge(item["source"].upper(), source_color))
        
        type_color = "#dc2626" if item["type"] == "video" else "#7c3aed"
        type_text = "VIDEO" if item["type"] == "video" else "PHOTO"
        badges.addWidget(Badge(type_text, type_color))
        badges.addStretch()
        
        layout.addLayout(badges)
        
        # Checkbox - 1ClickSub Studio Pill Style
        self.checkbox = QCheckBox("✓ Chọn media")
        self.checkbox.setChecked(is_selected)
        self.checkbox.toggled.connect(self._on_check_changed)
        self.checkbox.setStyleSheet("""
            QCheckBox {
                color: #e2e8f0;
                font-size: 11px;
                font-weight: 700;
                padding: 4px 8px;
                background-color: #1a2233;
                border-radius: 6px;
                spacing: 6px;
            }
            QCheckBox:hover { background-color: #222d42; color: #ffffff; }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border-radius: 4px;
                border: 1.5px solid #3b4d6e;
                background-color: #0c0f17;
            }
            QCheckBox::indicator:checked {
                background-color: #10b981;
                border-color: #34d399;
            }
            QCheckBox::indicator:hover {
                border-color: #818cf8;
            }
        """)
        self.checkbox.setFixedHeight(28)
        layout.addWidget(self.checkbox)
    
    def _update_style(self):
        if self.is_selected:
            self.setStyleSheet("""
                #card {
                    background-color: #0f2720;
                    border: 2px solid #10b981;
                    border-radius: 12px;
                }
            """)
        else:
            self.setStyleSheet("""
                #card {
                    background-color: #131926;
                    border: 1px solid #1e293b;
                    border-radius: 12px;
                }
                #card:hover {
                    border-color: #6366f1;
                    background-color: #161e2e;
                }
            """)
    
    def _on_check_changed(self, checked):
        self.is_selected = checked
        self._update_style()
        self.selectionChanged.emit(self.item, checked)
    
    def set_thumbnail(self, pixmap):
        if pixmap is None or pixmap.isNull():
            return
        
        scaled = pixmap.scaled(
            THUMB_WIDTH, THUMB_HEIGHT,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation
        )
        
        if scaled.width() > THUMB_WIDTH or scaled.height() > THUMB_HEIGHT:
            x_offset = (scaled.width() - THUMB_WIDTH) // 2
            y_offset = (scaled.height() - THUMB_HEIGHT) // 2
            scaled = scaled.copy(x_offset, y_offset, THUMB_WIDTH, THUMB_HEIGHT)
        
        if self.item["type"] == "video" and self.item.get("duration"):
            scaled = add_duration_to_pixmap(scaled, self.item["duration"])
        
        self.thumb_label.setPixmap(scaled)
        self.thumb_loaded = True
        self.thumb_failed = False
    
    def set_failed_state(self):
        self.thumb_failed = True
        self.thumb_loaded = False
        self.thumb_label.clear()
        self.thumb_label.setText("⚠ Load fail\n(Click để retry)")
        self.thumb_label.setStyleSheet("""
            background-color: #261217;
            border: 1px dashed #ef4444;
            border-radius: 8px;
            color: #f87171;
            font-size: 10px;
            font-weight: 700;
        """)
    
    def reset_to_loading(self):
        self.thumb_failed = False
        self.thumb_loaded = False
        self.thumb_label.clear()
        self.thumb_label.setText("Loading...")
        self.thumb_label.setStyleSheet("""
            background-color: #0c0f17;
            border-radius: 8px;
            color: #64748b;
            font-size: 11px;
            font-weight: 600;
        """)
    
    def set_selected(self, selected):
        if self.checkbox.isChecked() != selected:
            self.checkbox.setChecked(selected)


# ═══════════════════════════════════════════════════════════════════
# SCENE LIST ITEM - 1ClickSub Studio Timeline Scene Item
# ═══════════════════════════════════════════════════════════════════

class SceneListItem(QFrame):
    """Item trong scenes sidebar - Studio Timeline Design"""
    
    clicked = pyqtSignal(dict)
    
    def __init__(self, scene, is_active=False, parent=None):
        super().__init__(parent)
        self.scene = scene
        self.is_active = is_active
        self.total_items = 0
        self.selected_count = 0
        
        self.setFixedHeight(58)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(2)
        
        scene_id = scene.get("id", "?")
        time_start = scene.get("time_start", "00:00:00")
        if "," in time_start:
            time_start = time_start.split(",")[0]
        
        self.top_label = QLabel(f"🎬 Scene #{scene_id}   ⏱ {time_start}")
        self.top_label.setStyleSheet("color: #f8fafc; font-size: 12px; font-weight: 700; background: transparent;")
        layout.addWidget(self.top_label)
        
        self.bottom_label = QLabel("0 media")
        self.bottom_label.setStyleSheet("color: #94a3b8; font-size: 10px; font-weight: 600; background: transparent;")
        layout.addWidget(self.bottom_label)
        
        self._update_style()
    
    def _update_style(self):
        if self.is_active:
            self.setStyleSheet("""
                SceneListItem {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 #4f46e5, stop:1 #7c3aed);
                    border-radius: 8px;
                    border-left: 4px solid #38bdf8;
                }
            """)
            self.top_label.setStyleSheet("color: #ffffff; font-size: 12px; font-weight: 800; background: transparent;")
            self.bottom_label.setStyleSheet("color: rgba(255,255,255,0.9); font-size: 10px; font-weight: 600; background: transparent;")
        else:
            self.setStyleSheet("""
                SceneListItem {
                    background-color: #131926;
                    border: 1px solid #1e293b;
                    border-radius: 8px;
                }
                SceneListItem:hover {
                    background-color: #1a2233;
                    border-color: #3b4d6e;
                }
            """)
            self.top_label.setStyleSheet("color: #f1f5f9; font-size: 12px; font-weight: 700; background: transparent;")
            if self.selected_count > 0:
                self.bottom_label.setStyleSheet("color: #34d399; font-size: 10px; font-weight: 750; background: transparent;")
            else:
                self.bottom_label.setStyleSheet("color: #94a3b8; font-size: 10px; background: transparent;")
    
    def set_active(self, active):
        self.is_active = active
        self._update_style()
    
    def update_stats(self, total, selected):
        self.total_items = total
        self.selected_count = selected
        if selected > 0:
            self.bottom_label.setText(f"{total} items  •  ✓ Đã chọn {selected}")
        else:
            self.bottom_label.setText(f"{total} items")
        self._update_style()
    
    def mousePressEvent(self, event):
        self.clicked.emit(self.scene)
        super().mousePressEvent(event)


# ═══════════════════════════════════════════════════════════════════
# DIALOGS
# ═══════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════
# PART MERGER (v4.5) - merge multi-turn JSON parts từ Claude.ai
# ═══════════════════════════════════════════════════════════════════

class PartMergeError(Exception):
    """Raised khi merge fail (validation hoặc parse error)"""
    pass


class PartMerger:
    """Merge multiple part*.md files thành 1 JSON liền mạch
    
    Workflow:
    1. Scan folder tìm part*.md files
    2. Parse từng file → extract JSON code block
    3. Validate metadata + scenes
    4. Combine thành 1 JSON sạch
    """
    
    # Regex tìm JSON code block trong markdown
    JSON_PATTERN = re.compile(r'```json\s*(\{.*?\})\s*```', re.DOTALL)
    PART_FILE_PATTERN = re.compile(r'part(\d+)\.md$', re.IGNORECASE)
    
    @staticmethod
    def scan_folder(folder_path):
        """Scan folder cho tất cả part*.md files
        
        Returns: list of (part_number, filepath) sorted by part_number
        """
        folder = Path(folder_path)
        if not folder.exists() or not folder.is_dir():
            raise PartMergeError(f"Folder không tồn tại: {folder_path}")
        
        files = []
        for f in folder.iterdir():
            if not f.is_file():
                continue
            match = PartMerger.PART_FILE_PATTERN.search(f.name)
            if match:
                part_num = int(match.group(1))
                files.append((part_num, f))
        
        if not files:
            raise PartMergeError(
                f"Không tìm thấy file part*.md trong folder:\n{folder_path}\n\n"
                f"Đảm bảo files có tên: part1.md, part2.md, part3.md..."
            )
        
        # Sort by part number
        files.sort(key=lambda x: x[0])
        
        # Check liên tiếp (1, 2, 3...)
        part_nums = [p[0] for p in files]
        expected = list(range(1, max(part_nums) + 1))
        if part_nums != expected:
            missing = set(expected) - set(part_nums)
            raise PartMergeError(
                f"Part numbers không liên tiếp.\n"
                f"Tìm thấy: {part_nums}\n"
                f"Thiếu: {sorted(missing)}\n\n"
                f"Đảm bảo có đầy đủ part1.md, part2.md, ..."
            )
        
        return files
    
    @staticmethod
    def parse_part_file(filepath):
        """Parse 1 part file - extract JSON từ markdown code block
        
        Returns: dict (parsed JSON)
        Raises: PartMergeError nếu parse fail
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            raise PartMergeError(f"Không đọc được file {filepath.name}: {e}")
        
        # Tìm JSON code block
        match = PartMerger.JSON_PATTERN.search(content)
        if not match:
            raise PartMergeError(
                f"File {filepath.name} không chứa JSON code block.\n\n"
                f"Đảm bảo có dạng:\n"
                f"```json\n"
                f"{{...}}\n"
                f"```"
            )
        
        json_text = match.group(1)
        
        # Parse JSON
        try:
            data = json.loads(json_text)
        except json.JSONDecodeError as e:
            raise PartMergeError(
                f"File {filepath.name} có JSON syntax error.\n\n"
                f"Lỗi: {e.msg}\n"
                f"Vị trí: line {e.lineno}, column {e.colno}\n\n"
                f"Kiểm tra dấu phẩy, ngoặc, dấu ngoặc kép..."
            )
        
        return data
    
    @staticmethod
    def validate_part(data, filepath, expected_part_number=None):
        """Validate 1 part đã parse"""
        # Check _part_metadata
        if "_part_metadata" not in data:
            raise PartMergeError(
                f"File {filepath.name} thiếu '_part_metadata'.\n\n"
                f"Yêu cầu Claude.ai output lại theo prompt v6."
            )
        
        meta = data["_part_metadata"]
        required_meta_fields = [
            "part_number", "total_parts", "first_scene_id",
            "last_scene_id", "first_timestamp", "last_timestamp"
        ]
        for field in required_meta_fields:
            if field not in meta:
                raise PartMergeError(
                    f"File {filepath.name} thiếu metadata: {field}"
                )
        
        # Check part_number match filename
        if expected_part_number is not None:
            if meta["part_number"] != expected_part_number:
                raise PartMergeError(
                    f"File {filepath.name} có part_number={meta['part_number']} "
                    f"nhưng filename gợi ý part{expected_part_number}.\n\n"
                    f"Đổi tên file hoặc kiểm tra Claude.ai output."
                )
        
        # Check scenes array
        if "scenes" not in data:
            raise PartMergeError(
                f"File {filepath.name} thiếu 'scenes' array."
            )
        
        scenes = data["scenes"]
        if not isinstance(scenes, list) or len(scenes) == 0:
            raise PartMergeError(
                f"File {filepath.name}: 'scenes' phải là array không rỗng."
            )
        
        # Check scene IDs match metadata
        first_id = scenes[0].get("id")
        last_id = scenes[-1].get("id")
        
        if first_id != meta["first_scene_id"]:
            raise PartMergeError(
                f"File {filepath.name}: scene đầu có id={first_id}, "
                f"nhưng metadata báo first_scene_id={meta['first_scene_id']}"
            )
        
        if last_id != meta["last_scene_id"]:
            raise PartMergeError(
                f"File {filepath.name}: scene cuối có id={last_id}, "
                f"nhưng metadata báo last_scene_id={meta['last_scene_id']}"
            )
        
        # Validate timestamps tăng dần trong part
        prev_end = None
        for i, scene in enumerate(scenes):
            for required_field in ["id", "time_start", "time_end", "dialogue_es"]:
                if required_field not in scene:
                    raise PartMergeError(
                        f"File {filepath.name}: scene #{scene.get('id', '?')} "
                        f"thiếu field '{required_field}'"
                    )
            
            if prev_end is not None:
                if scene["time_start"] < prev_end:
                    raise PartMergeError(
                        f"File {filepath.name}: scene #{scene['id']} "
                        f"timestamp đi ngược!\n"
                        f"Scene trước kết thúc: {prev_end}\n"
                        f"Scene này bắt đầu: {scene['time_start']}"
                    )
            prev_end = scene["time_end"]
        
        return True
    
    @staticmethod
    def validate_cross_parts(parts_data):
        """Validate consistency giữa các parts
        
        parts_data: list of (data, filepath) đã parse
        """
        total_parts_expected = None
        prev_last_scene_id = 0
        prev_last_timestamp = "00:00:00,000"
        
        for data, filepath in parts_data:
            meta = data["_part_metadata"]
            
            # Check total_parts consistent
            if total_parts_expected is None:
                total_parts_expected = meta["total_parts"]
            elif meta["total_parts"] != total_parts_expected:
                raise PartMergeError(
                    f"Inconsistent total_parts:\n"
                    f"Part {meta['part_number']} ({filepath.name}) báo total={meta['total_parts']}\n"
                    f"Nhưng các parts khác báo total={total_parts_expected}"
                )
            
            # Check scene IDs liên tiếp giữa các parts
            first_id = meta["first_scene_id"]
            expected_first = prev_last_scene_id + 1
            if first_id != expected_first:
                raise PartMergeError(
                    f"Scene IDs không liên tiếp!\n"
                    f"Part trước kết thúc scene #{prev_last_scene_id}\n"
                    f"Part {meta['part_number']} ({filepath.name}) bắt đầu scene #{first_id}\n"
                    f"Phải bắt đầu từ scene #{expected_first}"
                )
            
            # Check timestamps liên tiếp giữa parts
            first_time = meta["first_timestamp"]
            if first_time < prev_last_timestamp:
                raise PartMergeError(
                    f"Timestamps không liên tiếp!\n"
                    f"Part trước kết thúc: {prev_last_timestamp}\n"
                    f"Part {meta['part_number']} ({filepath.name}) bắt đầu: {first_time}\n"
                    f"Part sau phải bắt đầu >= part trước kết thúc"
                )
            
            prev_last_scene_id = meta["last_scene_id"]
            prev_last_timestamp = meta["last_timestamp"]
        
        # Check số parts có đủ không
        total_loaded = len(parts_data)
        if total_loaded != total_parts_expected:
            raise PartMergeError(
                f"Thiếu parts!\n"
                f"Metadata báo total_parts={total_parts_expected}\n"
                f"Nhưng folder chỉ có {total_loaded} parts.\n\n"
                f"Đảm bảo có đủ part1.md, part2.md, ..., part{total_parts_expected}.md"
            )
        
        return True
    
    @staticmethod
    def merge(folder_path):
        """Main merge function - from folder
        
        Returns: dict (merged JSON ready for app)
        Raises: PartMergeError on any validation/parse failure
        """
        # Step 1: Scan folder
        files = PartMerger.scan_folder(folder_path)
        
        # Step 2: Parse all files
        parts_data = []
        for part_num, filepath in files:
            data = PartMerger.parse_part_file(filepath)
            parts_data.append((data, filepath))
        
        # Step 3: Validate each part
        for i, (data, filepath) in enumerate(parts_data):
            expected_part = i + 1
            PartMerger.validate_part(data, filepath, expected_part_number=expected_part)
        
        # Step 4: Validate cross-parts consistency
        PartMerger.validate_cross_parts(parts_data)
        
        # Step 5: Combine into single JSON
        return PartMerger._build_merged(parts_data, [f[1].name for f in files])
    
    @staticmethod
    def parse_part_text(text, part_label="Part"):
        """Parse 1 part text (paste content) - extract JSON
        
        Args:
            text: raw text user pasted (markdown or pure JSON)
            part_label: label dùng trong error message (vd: "Part 1", "Part 2")
        
        Returns: dict (parsed JSON)
        Raises: PartMergeError
        """
        text = text.strip()
        if not text:
            raise PartMergeError(f"{part_label}: nội dung trống")
        
        # Thử tìm JSON code block trước
        match = PartMerger.JSON_PATTERN.search(text)
        if match:
            json_text = match.group(1)
        else:
            # Không có code block, có thể user paste JSON thuần
            # Tìm { đầu và } cuối
            first_brace = text.find('{')
            last_brace = text.rfind('}')
            if first_brace == -1 or last_brace == -1 or first_brace >= last_brace:
                raise PartMergeError(
                    f"{part_label}: không tìm thấy JSON.\n\n"
                    f"Paste cả block ```json ... ``` từ Claude.ai\n"
                    f"hoặc paste JSON thuần (bắt đầu với '{{' và kết thúc '}}')."
                )
            json_text = text[first_brace:last_brace + 1]
        
        # Parse JSON
        try:
            data = json.loads(json_text)
        except json.JSONDecodeError as e:
            raise PartMergeError(
                f"{part_label}: JSON syntax error.\n\n"
                f"Lỗi: {e.msg}\n"
                f"Vị trí: line {e.lineno}, column {e.colno}\n\n"
                f"Kiểm tra dấu phẩy, ngoặc, dấu ngoặc kép..."
            )
        
        return data
    
    @staticmethod
    def merge_from_texts(part_texts):
        """Merge từ list các text (paste content)
        
        Args:
            part_texts: list of (label, text) tuples
                vd: [("Part 1", "...md content..."), ("Part 2", "...")]
        
        Returns: dict (merged JSON)
        Raises: PartMergeError on validation/parse failure
        """
        if not part_texts:
            raise PartMergeError("Không có part nào để merge.\nPaste ít nhất 1 part trước.")
        
        # Filter empty parts
        valid_inputs = [(label, text) for label, text in part_texts if text.strip()]
        if not valid_inputs:
            raise PartMergeError("Tất cả parts đều trống. Paste nội dung Part 1 trước.")
        
        # Parse từng part
        parts_data = []
        for label, text in valid_inputs:
            data = PartMerger.parse_part_text(text, label)
            # Use label as "filename" for error messages
            parts_data.append((data, type('FakePath', (), {'name': label})()))
        
        # Sort by part_number (in case user paste out of order)
        try:
            parts_data.sort(key=lambda pd: pd[0].get("_part_metadata", {}).get("part_number", 0))
        except Exception:
            pass
        
        # Validate each part - không check expected_part_number nữa
        # (user có thể paste theo thứ tự ngẫu nhiên, ta sort theo metadata)
        for data, fake_path in parts_data:
            # Skip filename check (vì là paste content)
            PartMerger.validate_part(data, fake_path, expected_part_number=None)
        
        # Validate cross-parts
        PartMerger.validate_cross_parts(parts_data)
        
        # Build merged
        labels = [fp.name for _, fp in parts_data]
        return PartMerger._build_merged(parts_data, labels)
    
    @staticmethod
    def _build_merged(parts_data, source_labels):
        """Build merged JSON từ parts đã validated"""
        first_data = parts_data[0][0]
        
        all_scenes = []
        for data, _ in parts_data:
            all_scenes.extend(data["scenes"])
        
        # Strip _part_metadata khỏi scenes nếu có
        for scene in all_scenes:
            scene.pop("_part_metadata", None)
        
        # Compute total duration
        total_duration = 0
        for scene in all_scenes:
            total_duration += scene.get("duration_seconds", 0)
        
        merged = {
            "video_topic": first_data.get("video_topic", "Unknown"),
            "language_source": first_data.get("language_source", "es"),
            "language_metadata": first_data.get("language_metadata", "en+vi"),
            "total_scenes": len(all_scenes),
            "total_duration_seconds": round(total_duration, 2),
            "_merge_info": {
                "merged_at": datetime.now().isoformat(),
                "parts_count": len(parts_data),
                "source_files": source_labels
            },
            "scenes": all_scenes
        }
        
        return merged
    
    @staticmethod
    def get_summary(folder_path):
        """Quick scan để hiển thị preview trước khi merge
        
        Returns: dict với thông tin tổng quan, hoặc None nếu lỗi
        """
        try:
            files = PartMerger.scan_folder(folder_path)
            
            parts_info = []
            for part_num, filepath in files:
                try:
                    data = PartMerger.parse_part_file(filepath)
                    meta = data.get("_part_metadata", {})
                    scenes = data.get("scenes", [])
                    parts_info.append({
                        "file": filepath.name,
                        "part_number": part_num,
                        "scenes_count": len(scenes),
                        "first_scene": meta.get("first_scene_id", "?"),
                        "last_scene": meta.get("last_scene_id", "?"),
                        "first_time": meta.get("first_timestamp", "?"),
                        "last_time": meta.get("last_timestamp", "?"),
                        "valid": True,
                        "error": None
                    })
                except PartMergeError as e:
                    parts_info.append({
                        "file": filepath.name,
                        "part_number": part_num,
                        "valid": False,
                        "error": str(e)
                    })
            
            return parts_info
        except PartMergeError:
            return None


# ═══════════════════════════════════════════════════════════════════
# ASSIGN SCENE DIALOG - hỏi user file thuộc scene nào
# ═══════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════
# ASSIGN SCENE DIALOG - 1ClickSub Studio Style
# ═══════════════════════════════════════════════════════════════════

class AssignSceneDialog(QDialog):
    """Dialog phân loại file tải về theo scene phong cách Studio"""
    
    def __init__(self, filename, scenes, suggested_scene_id=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚡ Gán Scene Cho File Tải Về")
        self.setMinimumWidth(620)
        self.setMinimumHeight(450)
        self.setStyleSheet(QSS_MAIN)
        
        self.filename = filename
        self.scenes = scenes
        self.selected_scene_id = None
        self.action = None
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)
        
        # Header với tên file
        header = QLabel(f"📥 File mới phát hiện trong Downloads:")
        header.setStyleSheet("color: #94a3b8; font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.8px;")
        layout.addWidget(header)
        
        file_label = QLabel(f"📄 {filename}")
        file_label.setStyleSheet("""
            background-color: #131926;
            border: 1px solid #f59e0b;
            border-radius: 8px;
            padding: 10px 14px;
            color: #fbbf24;
            font-size: 13px;
            font-weight: 700;
        """)
        file_label.setWordWrap(True)
        layout.addWidget(file_label)
        
        # Suggested scene (nếu có)
        if suggested_scene_id is not None:
            suggested = next((s for s in scenes if s.get("id") == suggested_scene_id), None)
            if suggested:
                ts_start = suggested.get("timestamp_start") or "?"
                preview_text = (suggested.get("dialogue_es") or suggested.get("dialogue") or "")[:80]
                
                suggest_btn = QPushButton(
                    f"⭐ Gán nhanh vào Scene #{suggested_scene_id} [{ts_start}] (đang search)\n{preview_text}..."
                )
                suggest_btn.setObjectName("primaryBtn")
                suggest_btn.setStyleSheet("""
                    QPushButton#primaryBtn {
                        padding: 10px;
                        text-align: left;
                        line-height: 1.3;
                    }
                """)
                suggest_btn.clicked.connect(lambda: self._select_and_close(suggested_scene_id))
                layout.addWidget(suggest_btn)
        
        # Search box
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Tìm scene theo ID, nội dung, keywords...")
        self.search_input.textChanged.connect(self._filter_scenes)
        layout.addWidget(self.search_input)
        
        # Scene list
        self.scene_list = QListWidget()
        self.scene_list.setStyleSheet("""
            QListWidget {
                background-color: #0c0f17;
                border: 1px solid #1e293b;
                border-radius: 10px;
                padding: 4px;
            }
            QListWidget::item {
                padding: 10px 12px;
                border-radius: 6px;
                margin-bottom: 2px;
                color: #f1f5f9;
            }
            QListWidget::item:hover {
                background-color: #1a2233;
            }
            QListWidget::item:selected {
                background-color: #4f46e5;
                color: #ffffff;
                font-weight: 700;
            }
        """)
        self.scene_list.itemDoubleClicked.connect(self._on_item_double_clicked)
        self._populate_scene_list("")
        layout.addWidget(self.scene_list, 1)
        
        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        
        btn_assign = QPushButton("✓ Gán vào scene chọn")
        btn_assign.setObjectName("primaryBtn")
        btn_assign.clicked.connect(self._on_assign)
        btn_row.addWidget(btn_assign)
        
        btn_skip = QPushButton("⏭ Bỏ qua")
        btn_skip.clicked.connect(self._on_skip)
        btn_row.addWidget(btn_skip)
        
        btn_delete = QPushButton("🗑 Xóa file")
        btn_delete.setObjectName("dangerBtn")
        btn_delete.clicked.connect(self._on_delete)
        btn_row.addWidget(btn_delete)
        
        layout.addLayout(btn_row)
    
    def _populate_scene_list(self, filter_text):
        self.scene_list.clear()
        filter_text = filter_text.lower().strip()
        
        for scene in self.scenes:
            scene_id = scene.get("id")
            ts_start = scene.get("timestamp_start") or "?"
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
    
    def _filter_scenes(self, text):
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
        reply = QMessageBox.question(self, "Xác nhận xóa",
                                       f"Bạn có chắc muốn xóa file '{self.filename}' khỏi thư mục Downloads?",
                                       QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.action = "delete"
            self.accept()


# ═══════════════════════════════════════════════════════════════════
# SETTINGS DIALOG (v5.0) - 1ClickSub Studio Settings Hub
# ═══════════════════════════════════════════════════════════════════

class SettingsDialog(QDialog):
    """Dialog cài đặt tổng hợp phong cách 1ClickSub Studio"""
    
    configChanged = pyqtSignal()
    jsonLoaded = pyqtSignal(object, list)
    
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("⚙️ Cài đặt Studio & API Keys")
        self.setMinimumWidth(650)
        self.setMinimumHeight(520)
        self.setStyleSheet(QSS_MAIN)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(24, 24, 24, 24)
        
        # === Section 1: Output folder ===
        layout.addWidget(self._section_header("📁 THƯ MỤC LƯU MEDIA"))
        
        folder_row = QHBoxLayout()
        self.output_input = QLineEdit(self.config.get("output_dir", ""))
        self.output_input.setReadOnly(True)
        folder_row.addWidget(self.output_input, 1)
        
        btn_browse = QPushButton("📁 Đổi thư mục...")
        btn_browse.clicked.connect(self._browse_output)
        folder_row.addWidget(btn_browse)
        layout.addLayout(folder_row)
        
        # === Section 2: API Keys ===
        layout.addWidget(self._section_header("🔑 QUẢN LÝ API KEYS"))

        self.keys_info_label = QLabel(
            f"⚡ Pexels: <b style='color:#34d399;'>{len(self.config.get('pexels_keys', []))}</b> keys  |  "
            f"Pixabay: <b style='color:#38bdf8;'>{len(self.config.get('pixabay_keys', []))}</b> keys  |  "
            f"Vecteezy: <b style='color:#a78bfa;'>{len(self.config.get('vecteezy_keys', []))}</b> keys"
        )
        self.keys_info_label.setStyleSheet("color: #cbd5e1; font-size: 12px; padding: 4px 0;")
        layout.addWidget(self.keys_info_label)

        key_btn_row = QHBoxLayout()
        btn_manage_pexels = QPushButton("🔑 Pexels Keys")
        btn_manage_pexels.clicked.connect(lambda: self._manage_keys("pexels"))
        key_btn_row.addWidget(btn_manage_pexels)
        
        btn_manage_pixabay = QPushButton("🔑 Pixabay Keys")
        btn_manage_pixabay.clicked.connect(lambda: self._manage_keys("pixabay"))
        key_btn_row.addWidget(btn_manage_pixabay)
        
        btn_manage_vecteezy = QPushButton("🔑 Vecteezy Keys")
        btn_manage_vecteezy.clicked.connect(lambda: self._manage_keys("vecteezy"))
        key_btn_row.addWidget(btn_manage_vecteezy)
        layout.addLayout(key_btn_row)
        
        # === Section 3: JSON Input ===
        layout.addWidget(self._section_header("📝 KỊCH BẢN JSON / CLAUDE"))
        
        if parent and hasattr(parent, 'scenes') and parent.scenes:
            json_status = f"✓ Đang nạp: <b style='color:#34d399;'>{len(parent.scenes)}</b> scenes"
            color = "#34d399"
        else:
            json_status = "Chưa nạp kịch bản JSON"
            color = "#94a3b8"
        
        self.json_status_label = QLabel(json_status)
        self.json_status_label.setStyleSheet(f"color: {color}; font-size: 12px; padding: 2px 0;")
        layout.addWidget(self.json_status_label)
        
        btn_json = QPushButton("📝 Nạp / Paste Kịch Bản JSON (Claude.ai)")
        btn_json.setObjectName("primaryBtn")
        btn_json.clicked.connect(self._show_json_dialog)
        layout.addWidget(btn_json)
        
        layout.addStretch()
        
        # === Close button ===
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_close = QPushButton("Đóng")
        btn_close.setFixedWidth(110)
        btn_close.clicked.connect(self.accept)
        btn_row.addWidget(btn_close)
        layout.addLayout(btn_row)
    
    def _section_header(self, text):
        lbl = QLabel(text)
        lbl.setStyleSheet("""
            color: #818cf8;
            font-size: 11px;
            font-weight: 800;
            letter-spacing: 1.2px;
            padding: 8px 0 4px 0;
            border-bottom: 1px solid #1e293b;
        """)
        return lbl
    
    def _browse_output(self):
        current = self.output_input.text() or str(Path.home())
        path = QFileDialog.getExistingDirectory(self, "Chọn thư mục lưu", current)
        if path:
            self.output_input.setText(path)
            self.config["output_dir"] = path
            try:
                save_config(self.config)
            except Exception:
                pass
            self.configChanged.emit()
    
    def _manage_keys(self, platform="pexels"):
        dialog = KeyManagementDialog(platform, self.config, parent=self)
        dialog.exec()
        self.keys_info_label.setText(
            f"⚡ Pexels: <b style='color:#34d399;'>{len(self.config.get('pexels_keys', []))}</b> keys  |  "
            f"Pixabay: <b style='color:#38bdf8;'>{len(self.config.get('pixabay_keys', []))}</b> keys  |  "
            f"Vecteezy: <b style='color:#a78bfa;'>{len(self.config.get('vecteezy_keys', []))}</b> keys"
        )
        self.configChanged.emit()
    
    def _show_json_dialog(self):
        dialog = JsonInputDialog(parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            json_data = dialog.result_data
            scenes = extract_scenes_from_json(json_data) if json_data else []
            if scenes:
                self.json_status_label.setText(f"✓ Đã nạp thành công: <b style='color:#34d399;'>{len(scenes)}</b> scenes")
                self.json_status_label.setStyleSheet("color: #34d399; font-size: 12px;")
                self.jsonLoaded.emit(json_data, scenes)


# ═══════════════════════════════════════════════════════════════════
# JSON INPUT DIALOG
# ═══════════════════════════════════════════════════════════════════

class JsonInputDialog(QDialog):
    """Dialog cho phép paste JSON hoặc chọn file"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.result_data = None
        
        self.setWindowTitle("Nhập JSON từ Claude.ai")
        self.setMinimumSize(800, 600)
        self.setStyleSheet(QSS_MAIN)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Title
        title = QLabel("📝 Nhập JSON từ Claude.ai")
        title.setStyleSheet("color: #e6edf3; font-size: 16px; font-weight: 700;")
        layout.addWidget(title)
        
        # Tabs
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, 1)
        
        # === Tab 1: Paste ===
        paste_tab = QWidget()
        paste_layout = QVBoxLayout(paste_tab)
        paste_layout.setContentsMargins(15, 15, 15, 15)
        
        paste_label = QLabel("Paste JSON từ Claude.ai vào ô bên dưới:")
        paste_label.setStyleSheet("color: #e6edf3; font-size: 12px; font-weight: 600;")
        paste_layout.addWidget(paste_label)
        
        self.text_area = QPlainTextEdit()
        self.text_area.setPlaceholderText('{\n  "scenes": [...]\n}')
        self.text_area.setStyleSheet("font-family: Consolas, monospace; font-size: 11px;")
        paste_layout.addWidget(self.text_area, 1)
        
        self.tabs.addTab(paste_tab, "📋 Paste JSON")
        
        # === Tab 2: File ===
        file_tab = QWidget()
        file_layout = QVBoxLayout(file_tab)
        file_layout.setContentsMargins(15, 30, 15, 15)
        
        file_label = QLabel("Chọn file JSON đã save:")
        file_label.setStyleSheet("color: #e6edf3; font-size: 12px; font-weight: 600;")
        file_layout.addWidget(file_label)
        
        file_h = QHBoxLayout()
        self.file_path_label = QLabel("Chưa chọn file")
        self.file_path_label.setStyleSheet("color: #7d8590; padding: 8px; background: #0d1117; border-radius: 6px;")
        self.file_path_label.setWordWrap(True)
        file_h.addWidget(self.file_path_label, 1)
        
        btn_browse = QPushButton("📁 Browse...")
        btn_browse.setFixedWidth(120)
        btn_browse.clicked.connect(self._browse_file)
        file_h.addWidget(btn_browse)
        
        file_layout.addLayout(file_h)
        file_layout.addStretch()
        
        self.tabs.addTab(file_tab, "📁 Chọn File")
        
        # === Tab 3: Merge Parts (NEW v4.5) - PASTE-BASED ===
        merge_tab = QWidget()
        merge_layout = QVBoxLayout(merge_tab)
        merge_layout.setContentsMargins(15, 10, 15, 10)
        merge_layout.setSpacing(8)
        
        merge_title = QLabel("📋 Merge nhiều parts từ Claude.ai")
        merge_title.setStyleSheet("color: #e6edf3; font-size: 13px; font-weight: 700;")
        merge_layout.addWidget(merge_title)
        
        merge_help = QLabel(
            "Paste từng Part từ Claude.ai vào các ô riêng bên dưới.\n"
            "App tự nhận diện thứ tự (qua _part_metadata) và merge thành 1 JSON."
        )
        merge_help.setStyleSheet("color: #7d8590; font-size: 11px;")
        merge_help.setWordWrap(True)
        merge_layout.addWidget(merge_help)
        
        # Scrollable area cho các part textareas
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
        
        # List of part textareas
        self.part_textareas = []
        
        # Toolbar: + Add Part, Auto-detect status
        toolbar_h = QHBoxLayout()
        
        btn_add_part = QPushButton("➕ Thêm Part")
        btn_add_part.setFixedHeight(32)
        btn_add_part.clicked.connect(self._add_part_textarea)
        toolbar_h.addWidget(btn_add_part)
        
        btn_clear_all = QPushButton("🗑 Clear tất cả")
        btn_clear_all.setObjectName("dangerBtn")
        btn_clear_all.setFixedHeight(32)
        btn_clear_all.clicked.connect(self._clear_all_parts)
        toolbar_h.addWidget(btn_clear_all)
        
        toolbar_h.addStretch()
        
        self.merge_status_label = QLabel("0 parts ready")
        self.merge_status_label.setStyleSheet("color: #7d8590; font-size: 11px;")
        toolbar_h.addWidget(self.merge_status_label)
        
        merge_layout.addLayout(toolbar_h)
        
        self.tabs.addTab(merge_tab, "📋 Merge Parts")
        
        # Add initial 2 parts (default)
        self._add_part_textarea()
        self._add_part_textarea()
        
        # === Bottom buttons ===
        btn_h = QHBoxLayout()
        btn_h.addStretch()
        
        btn_cancel = QPushButton("Hủy")
        btn_cancel.setFixedWidth(100)
        btn_cancel.clicked.connect(self.reject)
        btn_h.addWidget(btn_cancel)
        
        btn_load = QPushButton("✓ Load JSON")
        btn_load.setObjectName("primaryBtn")
        btn_load.setFixedWidth(140)
        btn_load.setFixedHeight(40)
        btn_load.clicked.connect(self._load)
        btn_h.addWidget(btn_load)
        
        layout.addLayout(btn_h)
        
        self.selected_file = None
    
    def _browse_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Chọn JSON", "",
            "JSON Files (*.json);;All Files (*.*)"
        )
        if path:
            self.selected_file = path
            self.file_path_label.setText(path)
            self.file_path_label.setStyleSheet("color: #4ec9b0; padding: 8px; background: #0d1117; border-radius: 6px; font-weight: 600;")
    
    def _add_part_textarea(self):
        """Thêm 1 part textarea mới"""
        part_index = len(self.part_textareas)
        part_number = part_index + 1
        
        # Frame chứa label + textarea + clear button
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
        
        # Header row
        header_h = QHBoxLayout()
        header_h.setSpacing(8)
        
        label = QLabel(f"📄 Part {part_number}")
        label.setStyleSheet("color: #e6edf3; font-size: 11px; font-weight: 600;")
        header_h.addWidget(label)
        
        status_label = QLabel("(empty)")
        status_label.setStyleSheet("color: #7d8590; font-size: 10px;")
        header_h.addWidget(status_label)
        
        header_h.addStretch()
        
        btn_clear = QPushButton("✕")
        btn_clear.setFixedSize(24, 24)
        btn_clear.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #7d8590;
                border: none;
                font-size: 14px;
            }
            QPushButton:hover {
                color: #f85149;
                background-color: rgba(248, 81, 73, 0.1);
                border-radius: 4px;
            }
        """)
        btn_clear.setToolTip("Xóa part này")
        header_h.addWidget(btn_clear)
        
        btn_remove = QPushButton("Xóa")
        btn_remove.setFixedHeight(24)
        btn_remove.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #7d8590;
                border: 1px solid #30363d;
                border-radius: 4px;
                padding: 0px 8px;
                font-size: 10px;
            }
            QPushButton:hover {
                color: #f85149;
                border-color: #f85149;
            }
        """)
        btn_remove.setToolTip("Xóa textarea này")
        header_h.addWidget(btn_remove)
        
        frame_layout.addLayout(header_h)
        
        # Textarea
        textarea = QPlainTextEdit()
        textarea.setPlaceholderText(
            f"Paste Part {part_number} từ Claude.ai vào đây...\n"
            f"(có thể paste cả markdown block ```json...``` hoặc JSON thuần)"
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
        
        # Connect events
        btn_clear.clicked.connect(lambda: textarea.clear())
        btn_remove.clicked.connect(lambda: self._remove_part_textarea(frame))
        textarea.textChanged.connect(lambda: self._update_part_status(textarea, status_label, label))
        
        # Insert before stretch
        stretch_idx = self.parts_layout.count() - 1
        self.parts_layout.insertWidget(stretch_idx, frame)
        
        # Track
        self.part_textareas.append({
            "frame": frame,
            "textarea": textarea,
            "status_label": status_label,
            "header_label": label
        })
        
        self._renumber_parts()
        self._update_merge_status()
    
    def _remove_part_textarea(self, frame):
        """Xóa 1 part textarea"""
        if len(self.part_textareas) <= 1:
            QMessageBox.information(self, "Không thể xóa", "Phải có ít nhất 1 part")
            return
        
        # Find and remove
        for i, item in enumerate(self.part_textareas):
            if item["frame"] is frame:
                frame.setParent(None)
                frame.deleteLater()
                del self.part_textareas[i]
                break
        
        self._renumber_parts()
        self._update_merge_status()
    
    def _renumber_parts(self):
        """Re-number các part labels sau khi add/remove"""
        for i, item in enumerate(self.part_textareas):
            part_num = i + 1
            item["header_label"].setText(f"📄 Part {part_num}")
            # Update placeholder cũng được
            item["textarea"].setPlaceholderText(
                f"Paste Part {part_num} từ Claude.ai vào đây..."
            )
    
    def _update_part_status(self, textarea, status_label, header_label):
        """Update status hiển thị khi user paste"""
        text = textarea.toPlainText().strip()
        if not text:
            status_label.setText("(empty)")
            status_label.setStyleSheet("color: #7d8590; font-size: 10px;")
            header_label.setStyleSheet("color: #e6edf3; font-size: 11px; font-weight: 600;")
        else:
            # Try quick parse để hiện status
            try:
                data = PartMerger.parse_part_text(text, "tmp")
                meta = data.get("_part_metadata", {})
                scenes = data.get("scenes", [])
                part_num = meta.get("part_number", "?")
                total_parts = meta.get("total_parts", "?")
                scenes_count = len(scenes)
                
                status_text = (
                    f"✓ Part {part_num}/{total_parts} • {scenes_count} scenes"
                )
                status_label.setText(status_text)
                status_label.setStyleSheet("color: #4ec9b0; font-size: 10px; font-weight: 600;")
                header_label.setStyleSheet("color: #4ec9b0; font-size: 11px; font-weight: 700;")
            except PartMergeError as e:
                # Parse error
                status_label.setText(f"⚠ {str(e)[:60]}")
                status_label.setStyleSheet("color: #f85149; font-size: 10px;")
                header_label.setStyleSheet("color: #f85149; font-size: 11px; font-weight: 600;")
        
        self._update_merge_status()
    
    def _update_merge_status(self):
        """Update tổng quan ở toolbar"""
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
            self.merge_status_label.setText("0 parts ready")
            self.merge_status_label.setStyleSheet("color: #7d8590; font-size: 11px;")
        else:
            self.merge_status_label.setText(
                f"✓ {len(valid_parts)} parts ready • {total_scenes} scenes total"
            )
            self.merge_status_label.setStyleSheet("color: #4ec9b0; font-size: 11px; font-weight: 600;")
    
    def _clear_all_parts(self):
        """Clear text trong tất cả parts"""
        if not any(item["textarea"].toPlainText().strip() for item in self.part_textareas):
            return
        
        reply = QMessageBox.question(
            self, "Xác nhận",
            "Xóa nội dung tất cả parts?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            for item in self.part_textareas:
                item["textarea"].clear()
    
    def _load(self):
        try:
            current_tab = self.tabs.currentIndex()
            
            if current_tab == 0:
                # Paste tab
                text = self.text_area.toPlainText().strip()
                if not text:
                    QMessageBox.warning(self, "Trống", "Paste JSON trước")
                    return
                
                # Validate: JSON phải bắt đầu bằng { hoặc [
                if not (text.startswith("{") or text.startswith("[")):
                    QMessageBox.critical(
                        self, "JSON lỗi",
                        f"JSON phải bắt đầu bằng '{{' hoặc '['\n\n"
                        f"Text bạn paste bắt đầu bằng: '{text[:50]}...'\n\n"
                        f"Có thể bạn paste thiếu phần đầu JSON. "
                        f"Copy lại TOÀN BỘ JSON từ Claude.ai (Ctrl+A trong code block)."
                    )
                    return
                
                try:
                    self.result_data = json.loads(text)
                except json.JSONDecodeError as e:
                    # Show context around error
                    err_pos = getattr(e, 'pos', 0)
                    snippet_start = max(0, err_pos - 50)
                    snippet_end = min(len(text), err_pos + 50)
                    snippet = text[snippet_start:snippet_end]
                    
                    QMessageBox.critical(
                        self, "JSON lỗi", 
                        f"Không parse được JSON:\n{e}\n\n"
                        f"Vị trí gần lỗi (...{snippet}...):"
                    )
                    return
            elif current_tab == 1:
                # File tab
                if not self.selected_file:
                    QMessageBox.warning(self, "Thiếu", "Chọn file trước")
                    return
                try:
                    with open(self.selected_file, 'r', encoding='utf-8') as f:
                        self.result_data = json.load(f)
                except Exception as e:
                    QMessageBox.critical(self, "Lỗi", f"Không đọc được:\n{e}")
                    return
            elif current_tab == 2:
                # Merge Parts tab - PASTE-BASED
                part_texts = []
                for i, item in enumerate(self.part_textareas):
                    text = item["textarea"].toPlainText().strip()
                    if text:
                        part_texts.append((f"Part {i+1}", text))
                
                if not part_texts:
                    QMessageBox.warning(self, "Trống", 
                                          "Paste ít nhất 1 part trước.\n\n"
                                          "Mở Claude.ai → copy output của Part 1 → paste vào ô Part 1.")
                    return
                
                try:
                    self.result_data = PartMerger.merge_from_texts(part_texts)
                    
                    total = self.result_data.get("total_scenes", 0)
                    parts_count = self.result_data.get("_merge_info", {}).get("parts_count", 0)
                    QMessageBox.information(
                        self, "✅ Merge thành công",
                        f"Đã merge {parts_count} parts thành {total} scenes!\n\n"
                        f"Click OK để load vào app."
                    )
                except PartMergeError as e:
                    QMessageBox.critical(
                        self, "❌ Merge lỗi",
                        f"Không merge được:\n\n{e}\n\n"
                        f"Sửa lỗi rồi thử lại."
                    )
                    return
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    QMessageBox.critical(self, "❌ Lỗi", f"Lỗi không mong đợi:\n{e}")
                    return
            
            # Validate scenes
            scenes = extract_scenes_from_json(self.result_data)
            if not scenes:
                QMessageBox.critical(
                    self, "JSON lỗi", 
                    "Không tìm thấy scenes trong JSON.\n\n"
                    "JSON phải có key 'scenes', 'part_a_scenes', hoặc 'part_b_segments'."
                )
                self.result_data = None
                return
            
            self.accept()
        except Exception as e:
            # Catch-all để KHÔNG crash app
            import traceback
            traceback.print_exc()
            QMessageBox.critical(
                self, "Lỗi không mong đợi",
                f"{type(e).__name__}: {e}\n\nCheck console để xem chi tiết."
            )


class KeyDialog(QDialog):
    """Dialog để thêm/sửa 1 API key phong cách 1ClickSub Studio"""
    
    def __init__(self, platform, existing=None, parent=None):
        super().__init__(parent)
        self.platform = platform
        self.result_key = None
        
        self.setWindowTitle(f"{'Sửa' if existing else 'Thêm'} {platform.title()} API Key")
        self.setFixedSize(520, 320)
        self.setStyleSheet(QSS_MAIN)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)
        
        # Title
        title = QLabel(f"🔑 {platform.title()} API Key")
        title.setStyleSheet("color: #f8fafc; font-size: 16px; font-weight: 800;")
        layout.addWidget(title)
        
        # Name
        layout.addWidget(QLabel("Tên gợi nhớ (Ví dụ: Key_1, Key_VIP):"))
        self.name_input = QLineEdit()
        if existing:
            self.name_input.setText(existing.get("name", ""))
        layout.addWidget(self.name_input)
        
        # Key
        layout.addWidget(QLabel(f"Chuỗi API Key {platform.title()}:"))
        self.key_input = QLineEdit()
        self.key_input.setStyleSheet("font-family: 'Consolas', 'Cascadia Code', monospace;")
        if existing:
            self.key_input.setText(existing.get("key", ""))
        layout.addWidget(self.key_input)
        
        # Test label
        self.test_label = QLabel("")
        self.test_label.setStyleSheet("color: #94a3b8; font-size: 11px; font-weight: 600;")
        layout.addWidget(self.test_label)
        
        layout.addStretch()
        
        # Buttons
        btn_h = QHBoxLayout()
        btn_h.setSpacing(10)
        
        btn_test = QPushButton("🧪 Test Key")
        btn_test.clicked.connect(self._test_key)
        btn_h.addWidget(btn_test)
        
        btn_h.addStretch()
        
        btn_cancel = QPushButton("Hủy")
        btn_cancel.clicked.connect(self.reject)
        btn_h.addWidget(btn_cancel)
        
        btn_save = QPushButton("💾 Lưu Key")
        btn_save.setObjectName("primaryBtn")
        btn_save.clicked.connect(self._save)
        btn_h.addWidget(btn_save)
        
        layout.addLayout(btn_h)
        self.name_input.setFocus()
    
    def _test_key(self):
        key = self.key_input.text().strip()
        if not key:
            self.test_label.setText("⚠ Nhập API key trước khi kiểm tra")
            self.test_label.setStyleSheet("color: #fbbf24; font-size: 11px; font-weight: 600;")
            return
        
        self.test_label.setText("🔄 Đang kết nối API để kiểm tra...")
        self.test_label.setStyleSheet("color: #38bdf8; font-size: 11px; font-weight: 600;")
        QApplication.processEvents()
        
        def do_test():
            try:
                if self.platform == "pixabay":
                    api = PixabayAPI(None)
                elif self.platform == "vecteezy":
                    api = VecteezyAPI(None)
                else:
                    api = PexelsAPI(None)
                ok, msg = api.test_key(key)
                color = "#34d399" if ok else "#f87171"
                icon = "✓" if ok else "✗"
                self.test_label.setText(f"{icon} {msg}")
                self.test_label.setStyleSheet(f"color: {color}; font-size: 11px; font-weight: 700;")
            except Exception as e:
                self.test_label.setText(f"✗ Lỗi kết nối: {e}")
                self.test_label.setStyleSheet("color: #f87171; font-size: 11px;")
        
        threading.Thread(target=do_test, daemon=True).start()
    
    def _save(self):
        name = self.name_input.text().strip()
        key = self.key_input.text().strip()
        if not name or not key:
            QMessageBox.warning(self, "Thiếu thông tin", "Vui lòng nhập đầy đủ tên và API key")
            return
        self.result_key = {"name": name, "key": key}
        self.accept()


class KeyManagementDialog(QDialog):
    """Dialog quản lý các keys của 1 platform phong cách Studio"""
    
    keysChanged = pyqtSignal()
    
    def __init__(self, platform, config, parent=None):
        super().__init__(parent)
        self.platform = platform
        self.config = config
        
        self.setWindowTitle(f"🔑 Quản lý {platform.title()} Keys")
        self.setMinimumSize(640, 520)
        self.setStyleSheet(QSS_MAIN)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)
        
        # Title
        title = QLabel(f"🔑 Quản lý {platform.title()} API Keys")
        title.setStyleSheet("color: #f8fafc; font-size: 18px; font-weight: 800;")
        layout.addWidget(title)
        
        # Info
        info = QLabel("Thêm nhiều API keys để tự động xoay vòng thông minh, chống chạm rate limit.")
        info.setStyleSheet("color: #94a3b8; font-size: 12px;")
        layout.addWidget(info)
        
        # List
        self.list_scroll = QScrollArea()
        self.list_scroll.setWidgetResizable(True)
        self.list_scroll.setStyleSheet("QScrollArea { border: 1px solid #1e293b; border-radius: 10px; background-color: #0c0f17; }")
        
        self.list_container = QWidget()
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setContentsMargins(8, 8, 8, 8)
        self.list_layout.setSpacing(6)
        self.list_layout.addStretch()
        
        self.list_scroll.setWidget(self.list_container)
        layout.addWidget(self.list_scroll, 1)
        
        # Buttons
        btn_h = QHBoxLayout()
        btn_h.setSpacing(8)
        
        btn_add = QPushButton("+ Thêm Key Mới")
        btn_add.setObjectName("primaryBtn")
        btn_add.clicked.connect(self._add_key)
        btn_h.addWidget(btn_add)
        
        btn_register = QPushButton("🌐 Lấy Key Miễn Phí")
        btn_register.clicked.connect(self._open_register)
        btn_h.addWidget(btn_register)
        
        btn_h.addStretch()
        
        btn_close = QPushButton("Đóng")
        btn_close.setFixedWidth(100)
        btn_close.clicked.connect(self.accept)
        btn_h.addWidget(btn_close)
        
        layout.addLayout(btn_h)
        self._refresh_list()
    
    def _refresh_list(self):
        while self.list_layout.count() > 1:
            item = self.list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        keys = self.config.get(f"{self.platform}_keys", [])
        
        if not keys:
            empty = QLabel("Chưa có key nào. Bấm '+ Thêm Key Mới' để bắt đầu.")
            empty.setStyleSheet("color: #64748b; padding: 40px; font-size: 13px; font-weight: 600;")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.list_layout.insertWidget(0, empty)
            return
        
        for idx, k in enumerate(keys):
            row = QFrame()
            row.setStyleSheet("""
                QFrame {
                    background-color: #131926;
                    border: 1px solid #1e293b;
                    border-radius: 8px;
                    padding: 4px;
                }
                QFrame:hover {
                    border-color: #6366f1;
                    background-color: #161e2e;
                }
            """)
            row.setFixedHeight(62)
            
            h = QHBoxLayout(row)
            h.setContentsMargins(12, 6, 12, 6)
            
            v = QVBoxLayout()
            v.setSpacing(2)
            
            name_lbl = QLabel(f"⚡ {k['name']}")
            name_lbl.setStyleSheet("color: #f8fafc; font-size: 13px; font-weight: 750; background: transparent;")
            v.addWidget(name_lbl)
            
            preview = k["key"][:20] + "..." + k["key"][-5:] if len(k["key"]) > 30 else k["key"]
            key_lbl = QLabel(preview)
            key_lbl.setStyleSheet("color: #94a3b8; font-size: 10px; font-family: 'Consolas', monospace; background: transparent;")
            v.addWidget(key_lbl)
            
            h.addLayout(v, 1)
            
            btn_edit = QPushButton("Sửa")
            btn_edit.setFixedSize(60, 28)
            btn_edit.clicked.connect(lambda checked, i=idx: self._edit_key(i))
            h.addWidget(btn_edit)
            
            btn_del = QPushButton("Xóa")
            btn_del.setObjectName("dangerBtn")
            btn_del.setFixedSize(60, 28)
            btn_del.clicked.connect(lambda checked, i=idx: self._delete_key(i))
            h.addWidget(btn_del)
            
            self.list_layout.insertWidget(self.list_layout.count() - 1, row)
    
    def _add_key(self):
        dialog = KeyDialog(self.platform, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.result_key:
            key_list_name = f"{self.platform}_keys"
            if key_list_name not in self.config:
                self.config[key_list_name] = []
            self.config[key_list_name].append(dialog.result_key)
            save_config(self.config)
            self._refresh_list()
            self.keysChanged.emit()
    
    def _edit_key(self, idx):
        keys = self.config.get(f"{self.platform}_keys", [])
        if idx >= len(keys):
            return
        dialog = KeyDialog(self.platform, existing=keys[idx], parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.result_key:
            self.config[f"{self.platform}_keys"][idx] = dialog.result_key
            save_config(self.config)
            self._refresh_list()
            self.keysChanged.emit()
    
    def _delete_key(self, idx):
        keys = self.config.get(f"{self.platform}_keys", [])
        if idx >= len(keys):
            return
        reply = QMessageBox.question(self, "Xác nhận xóa", 
                                       f"Bạn có chắc muốn xóa key '{keys[idx]['name']}'?",
                                       QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            del self.config[f"{self.platform}_keys"][idx]
            save_config(self.config)
            self._refresh_list()
            self.keysChanged.emit()
    
    def _open_register(self):
        import webbrowser
        urls = {
            "pexels": "https://www.pexels.com/api/",
            "pixabay": "https://pixabay.com/api/docs/",
            "coverr": "https://coverr.co/developers",
            "vecteezy": "https://www.vecteezy.com/api-docs/index.html",
        }
        webbrowser.open(urls.get(self.platform, "https://www.pexels.com/api/"))


# ═══════════════════════════════════════════════════════════════════
# SEARCH WORKER (QThread for non-blocking)
# ═══════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════
# DOWNLOADS FOLDER WATCHER (for MotionArray manual downloads)
# ═══════════════════════════════════════════════════════════════════

class DownloadsWatcherSignals(QObject):
    """Signals cho watcher (Qt signals phải nằm trong QObject)"""
    fileDetected = pyqtSignal(str)  # Emit khi phát hiện file mp4 mới


class DownloadsWatcher(QObject):
    """Watch Downloads folder để detect file .mp4 mới (từ MotionArray)
    
    Sử dụng polling (đơn giản, không cần watchdog library)
    Check folder mỗi 2 giây, so sánh với snapshot trước
    """
    
    # File extensions cần track (MotionArray xuất .mp4)
    EXTENSIONS = {'.mp4', '.mov', '.webm', '.avi', '.mkv'}
    
    # Tối thiểu kích thước file (avoid temp/partial files)
    MIN_FILE_SIZE = 100 * 1024  # 100KB
    
    # Thời gian tối đa file được coi là "mới" (giây)
    NEW_FILE_WINDOW = 600  # 10 phút
    
    def __init__(self, downloads_dir=None):
        super().__init__()
        self.signals = DownloadsWatcherSignals()
        self.downloads_dir = Path(downloads_dir) if downloads_dir else Path.home() / "Downloads"
        self._known_files = set()  # snapshot file đã biết
        self._processed_files = set()  # file đã notify user
        self._running = False
        self._thread = None
        self._lock = threading.Lock()
    
    def start(self):
        """Bắt đầu watch trong background thread"""
        if self._running:
            return
        
        if not self.downloads_dir.exists():
            print(f"[DownloadsWatcher] Folder không tồn tại: {self.downloads_dir}")
            return
        
        # Snapshot ban đầu - file CŨ không count
        try:
            self._known_files = set(self._scan_folder())
            print(f"[DownloadsWatcher] Bắt đầu watch {self.downloads_dir}")
            print(f"[DownloadsWatcher] Snapshot ban đầu: {len(self._known_files)} files")
        except Exception as e:
            print(f"[DownloadsWatcher] Snapshot error: {e}")
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._thread.start()
    
    def stop(self):
        """Dừng watcher"""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)
    
    def _scan_folder(self):
        """Scan folder, trả về set các file path .mp4/.mov hợp lệ"""
        files = []
        try:
            for f in self.downloads_dir.iterdir():
                if not f.is_file():
                    continue
                if f.suffix.lower() not in self.EXTENSIONS:
                    continue
                # Bỏ qua file partial (Chrome dùng .crdownload, .tmp)
                if f.name.endswith('.crdownload') or f.name.endswith('.tmp'):
                    continue
                files.append(str(f))
        except Exception as e:
            print(f"[DownloadsWatcher] Scan error: {e}")
        return files
    
    def _watch_loop(self):
        """Loop check folder mỗi 2 giây"""
        while self._running:
            try:
                current_files = set(self._scan_folder())
                
                # File mới = trong current nhưng KHÔNG trong known
                new_files = current_files - self._known_files
                
                for filepath in new_files:
                    if filepath in self._processed_files:
                        continue
                    
                    # Kiểm tra file đã ghi xong (size ổn định + đủ to)
                    if self._is_file_ready(filepath):
                        # Detect file mới
                        with self._lock:
                            self._processed_files.add(filepath)
                            self._known_files.add(filepath)
                        
                        # Emit signal (Qt thread-safe)
                        print(f"[DownloadsWatcher] File mới: {Path(filepath).name}")
                        self.signals.fileDetected.emit(filepath)
                
                # Update known files (add file đã ổn định nhưng chưa process)
                self._known_files = self._known_files | current_files
                
            except Exception as e:
                print(f"[DownloadsWatcher] Loop error: {e}")
            
            time.sleep(2.0)
    
    def _is_file_ready(self, filepath):
        """Check file đã ghi xong: size ổn định + đủ to + tồn tại sau 1s"""
        try:
            if not os.path.exists(filepath):
                return False
            
            size_1 = os.path.getsize(filepath)
            if size_1 < self.MIN_FILE_SIZE:
                return False
            
            time.sleep(0.5)
            
            if not os.path.exists(filepath):
                return False
            
            size_2 = os.path.getsize(filepath)
            return size_1 == size_2  # Size không đổi → file ghi xong
        except Exception:
            return False
    
    def reset(self):
        """Reset snapshot - dùng khi user xác nhận đã sắp xếp xong"""
        with self._lock:
            try:
                self._known_files = set(self._scan_folder())
                self._processed_files.clear()
            except Exception:
                pass


# ═══════════════════════════════════════════════════════════════════
# SEARCH WORKER (QThread)
# ═══════════════════════════════════════════════════════════════════

class SearchWorker(QThread):
    """Background search worker - Pexels + Pixabay."""
    
    sceneCompleted = pyqtSignal(object, list)  # scene_id, items list
    progress = pyqtSignal(str)  # status message
    finished_signal = pyqtSignal()
    
    def __init__(self, scenes, km, search_photos, search_videos, source_mode="Pexels + Pixabay"):
        super().__init__()
        self.scenes = scenes
        self.km = km
        self.search_photos = search_photos
        self.search_videos = search_videos
        self.source_mode = source_mode or "Pexels + Pixabay"
        self._stop = False
    
    def stop(self):
        self._stop = True
    
    def run(self):
        try:
            mode_lower = str(self.source_mode).lower()
            use_pexels = "pexels" in mode_lower or "cả" in mode_lower or "+" in mode_lower or "all" in mode_lower
            use_pixabay = "pixabay" in mode_lower or "cả" in mode_lower or "+" in mode_lower or "all" in mode_lower
            use_vecteezy = "vecteezy" in mode_lower or "cả" in mode_lower or "+" in mode_lower or "all" in mode_lower
            pexels = PexelsAPI(self.km) if use_pexels and self.km.pexels_keys else None
            pixabay = PixabayAPI(self.km) if use_pixabay and self.km.pixabay_keys else None
            vecteezy = VecteezyAPI(self.km) if use_vecteezy and self.km.vecteezy_keys else None
            if not pexels and not pixabay and not vecteezy:
                self.progress.emit(f"⚠ Chưa có API key hợp lệ cho nguồn: {self.source_mode}")
                print(f"[SearchWorker] FAIL: no keys for source_mode={self.source_mode}")
                return
            
            print(f"[SearchWorker] Bắt đầu search {len(self.scenes)} scenes")
            print(f"[SearchWorker] Pexels keys: {len(self.km.pexels_keys)}")
            print(f"[SearchWorker] Pixabay keys: {len(self.km.pixabay_keys)}")
            print(f"[SearchWorker] Vecteezy keys: {len(self.km.vecteezy_keys)}")
            print(f"[SearchWorker] source_mode={self.source_mode}")
            print(f"[SearchWorker] search_photos={self.search_photos}, search_videos={self.search_videos}")
            
            total = len(self.scenes)
            for idx, scene in enumerate(self.scenes):
                if self._stop:
                    break
                
                scene_id = scene.get("id")
                
                # Smart keyword selection: prioritize primary, mix with secondary
                # Lấy MAX_KEYWORDS_PER_SCENE keywords: 60% primary, 40% secondary
                primary_kws = [k for k in scene.get("primary_keywords", []) if k]
                secondary_kws = [k for k in scene.get("secondary_keywords", []) if k]
                
                # Phân bổ: ưu tiên primary, sau đó mix secondary
                # VD MAX=5: lấy 3 primary đầu + 2 secondary đầu
                # Nếu primary < 3 thì lấy thêm từ secondary để bù
                n_primary = min(len(primary_kws), max(3, MAX_KEYWORDS_PER_SCENE - 2))
                n_secondary = MAX_KEYWORDS_PER_SCENE - n_primary
                
                keywords = primary_kws[:n_primary] + secondary_kws[:n_secondary]
                
                # Nếu chưa đủ MAX (vì secondary ít), lấy thêm primary còn lại
                if len(keywords) < MAX_KEYWORDS_PER_SCENE and len(primary_kws) > n_primary:
                    extra = MAX_KEYWORDS_PER_SCENE - len(keywords)
                    keywords += primary_kws[n_primary:n_primary + extra]
                
                if not keywords:
                    print(f"[SearchWorker] Scene #{scene_id}: NO keywords")
                    self.sceneCompleted.emit(scene_id, [])
                    continue
                
                print(f"[SearchWorker] Scene #{scene_id}: {len(keywords)} keywords: {keywords[:3]}")
                
                scene_results = []
                seen_keys = set()
                
                for kw in keywords:
                    if self._stop:
                        break
                    self.progress.emit(f"[{idx + 1}/{total}] Scene #{scene_id}: {kw}")
                    
                    sources_results = []
                    
                    # Photos
                    if self.search_photos:
                        try:
                            photos = []
                            if pexels:
                                photos.extend(pexels.search_photos(kw, per_page=RESULTS_PER_KEYWORD))
                            if pixabay:
                                photos.extend(pixabay.search_photos(kw, per_page=RESULTS_PER_KEYWORD))
                            if vecteezy:
                                photos.extend(vecteezy.search_photos(kw, per_page=RESULTS_PER_KEYWORD))
                            print(f"[SearchWorker] Scene #{scene_id} '{kw}' photos: {len(photos)}")
                            sources_results.append(photos)
                        except Exception as e:
                            print(f"[SearchWorker] Photos search error: {e}")
                        # Check stop NGAY sau request, không đợi sleep
                        if self._stop:
                            break
                        # Sleep chunk nhỏ để check stop thường xuyên
                        for _ in range(3):
                            if self._stop:
                                break
                            time.sleep(0.1)
                    
                    if self._stop:
                        break
                    
                    # Videos
                    if self.search_videos:
                        try:
                            videos = []
                            if pexels:
                                videos.extend(pexels.search_videos(kw, per_page=RESULTS_PER_KEYWORD))
                            if pixabay:
                                videos.extend(pixabay.search_videos(kw, per_page=RESULTS_PER_KEYWORD))
                            if vecteezy:
                                videos.extend(vecteezy.search_videos(kw, per_page=RESULTS_PER_KEYWORD))
                            print(f"[SearchWorker] Scene #{scene_id} '{kw}' videos: {len(videos)}")
                            sources_results.append(videos)
                        except Exception as e:
                            print(f"[SearchWorker] Videos search error: {e}")
                        if self._stop:
                            break
                        for _ in range(3):
                            if self._stop:
                                break
                            time.sleep(0.1)
                    
                    for results in sources_results:
                        for r in results:
                            r["_scene_id"] = scene_id
                            key = f"{r['source']}_{r['type']}_{r['id']}"
                            if key not in seen_keys:
                                seen_keys.add(key)
                                scene_results.append(r)
                
                print(f"[SearchWorker] Scene #{scene_id} TOTAL: {len(scene_results)} items")
                self.sceneCompleted.emit(scene_id, scene_results)
            
            self.progress.emit("✅ Search hoàn tất")
        except Exception as e:
            print(f"[SearchWorker] FATAL EXCEPTION: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            self.progress.emit(f"❌ Lỗi: {e}")
        finally:
            self.finished_signal.emit()


# ═══════════════════════════════════════════════════════════════════
# DOWNLOAD WORKER (QThread)
# ═══════════════════════════════════════════════════════════════════

class DownloadWorker(QThread):
    """Background download worker với ANTI-BLOCK (v4.3)
    
    Features:
    - Adaptive delay (0.5-3s tự điều chỉnh)
    - Block detection (5 consecutive 403 → cooldown 5 min)
    - URL refresh khi 403
    - Smart retry với delays
    - Random jitter
    - Multi-key rotation (qua KeyManager)
    """
    
    progress = pyqtSignal(str, int, int)  # message, current, total
    statsUpdate = pyqtSignal(dict)  # anti-block stats
    cooldownStart = pyqtSignal(int)  # seconds remaining
    cooldownTick = pyqtSignal(int)  # seconds remaining (during countdown)
    cooldownEnd = pyqtSignal()
    finished_signal = pyqtSignal(int, int, str, dict)  # success, fail, project_dir, error_breakdown
    
    def __init__(self, scenes, selected_items, output_dir, json_data, key_manager=None):
        super().__init__()
        self.scenes = scenes
        self.selected_items = selected_items
        self.output_dir = output_dir
        self.json_data = json_data
        self.key_manager = key_manager
        self._stop = False
        
        # Anti-block components
        self.rate_limiter = AdaptiveRateLimiter()
        self.block_detector = BlockDetector()
        
        # Smart downloader with API access for URL refresh
        pexels_api = PexelsAPI(key_manager) if key_manager else None
        pixabay_api = PixabayAPI(key_manager) if key_manager else None
        # Pass stop callback để downloader có thể abort khi user click DỪNG
        self.downloader = SmartDownloader(pexels_api, pixabay_api, should_stop=lambda: self._stop)
        
        # Stats
        self.stats = {
            "success": 0,
            "fail": 0,
            "via_refresh": 0,
            "block_cooldowns": 0,
            "error_breakdown": {}
        }
    
    def stop(self):
        self._stop = True
    
    def _adaptive_sleep(self):
        """Sleep với jittered adaptive delay, có thể break khi stop"""
        delay = self.rate_limiter.get_delay()
        # Break sleep into chunks to allow stopping quickly
        chunks = int(delay * 10)  # 100ms chunks
        for _ in range(chunks):
            if self._stop:
                return
            time.sleep(0.1)
    
    def _handle_result(self, success, error_type):
        """Update rate limiter + block detector based on result"""
        self.rate_limiter.record_result(success)
        if success:
            self.block_detector.record_success()
        elif error_type == "forbidden":
            if self.block_detector.record_403():
                self._cool_down()
    
    def _cool_down(self):
        """Pause 5 minutes after detecting block"""
        self.stats["block_cooldowns"] += 1
        self.cooldownStart.emit(BLOCK_COOLDOWN_SECONDS)
        
        # Countdown
        for remaining in range(BLOCK_COOLDOWN_SECONDS, 0, -1):
            if self._stop:
                return
            self.cooldownTick.emit(remaining)
            time.sleep(1)
        
        self.cooldownEnd.emit()
    
    def _emit_stats(self):
        """Emit current stats for UI display"""
        delay, fail_rate, sample = self.rate_limiter.get_stats()
        self.statsUpdate.emit({
            "delay": delay,
            "fail_rate": fail_rate,
            "sample": sample,
            "blocks": self.stats["block_cooldowns"],
            "via_refresh": self.stats["via_refresh"]
        })
    
    def run(self):
        try:
            # v5.0: KHÔNG tạo project_xxx nữa - lưu trực tiếp vào output_dir/scene_XXX_TIMESTAMP/
            # Format khớp với MotionArray watcher để Download Monitor scan đúng
            output_base = Path(self.output_dir)
            output_base.mkdir(parents=True, exist_ok=True)
            
            # Save JSON mapping ở output_dir gốc (không phải project_xxx)
            if self.json_data:
                try:
                    mapping_path = output_base / "_scene_mapping.json"
                    with open(mapping_path, 'w', encoding='utf-8') as f:
                        json.dump(self.json_data, f, ensure_ascii=False, indent=2)
                except Exception:
                    pass
            
            # project_dir = output_base để giữ backward compat với code emit signal
            project_dir = output_base
            
            all_downloaded = []
            total = sum(len(s) for s in self.selected_items.values())
            done = 0
            
            for scene in self.scenes:
                if self._stop:
                    break
                scene_id = scene.get("id")
                selected = self.selected_items.get(scene_id, {})
                if not selected:
                    continue
                
                # Lưu phẳng trong output_dir: 1_00.mp4, 1_01.mp4... không tạo folder con.
                scene_name = str(scene_id).lstrip("0") or "0"
                
                for item_idx, item in enumerate(selected.values()):
                    if self._stop:
                        break
                    done += 1
                    
                    ext = ".mp4" if item["type"] == "video" else ".jpg"
                    filename = f"{scene_name}_{item_idx:02d}{ext}"
                    filepath = output_base / filename
                    while filepath.exists():
                        item_idx += 1
                        filename = f"{scene_name}_{item_idx:02d}{ext}"
                        filepath = output_base / filename
                    
                    self.progress.emit(
                        f"[{done}/{total}] scene #{scene_id}: {filename}",
                        done, total
                    )
                    
                    # SMART DOWNLOAD with anti-block
                    success, error, error_type = self.downloader.download(item, filepath)
                    
                    # Update tracking
                    self._handle_result(success, error_type)
                    
                    if success:
                        self.stats["success"] += 1
                        all_downloaded.append((scene, item, filename))
                        if error_type == "success_after_refresh":
                            self.stats["via_refresh"] += 1
                    else:
                        self.stats["fail"] += 1
                        self.stats["error_breakdown"][error_type] = self.stats["error_breakdown"].get(error_type, 0) + 1
                    
                    # Emit stats for UI
                    self._emit_stats()
                    
                    # Adaptive sleep before next
                    self._adaptive_sleep()
            
            # Save merged scene info file
            self._save_scenes_info(project_dir, all_downloaded)
            # Save credits
            self._save_credits(project_dir, [item for _, item, _ in all_downloaded])
            # Save error report
            self._save_error_report(project_dir)
            
            self.finished_signal.emit(
                self.stats["success"], 
                self.stats["fail"], 
                str(project_dir),
                self.stats["error_breakdown"]
            )
        except Exception as e:
            self.progress.emit(f"❌ Lỗi: {e}", 0, 0)
            self.finished_signal.emit(0, 0, "", {})
    
    def _save_error_report(self, project_dir):
        """Save error report with anti-block stats"""
        try:
            with open(project_dir / "_error_report.txt", 'w', encoding='utf-8') as f:
                f.write("=" * 70 + "\n")
                f.write(f"DOWNLOAD REPORT - v{APP_VERSION}\n")
                f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("=" * 70 + "\n\n")
                
                total = self.stats["success"] + self.stats["fail"]
                success_rate = (self.stats["success"] / total * 100) if total > 0 else 0
                
                f.write("OVERVIEW:\n")
                f.write(f"  Total attempted:       {total}\n")
                f.write(f"  Successful:            {self.stats['success']}\n")
                f.write(f"  Failed:                {self.stats['fail']}\n")
                f.write(f"  Success rate:          {success_rate:.1f}%\n")
                f.write(f"  Saved via URL refresh: {self.stats['via_refresh']}\n")
                f.write(f"  Block cooldowns:       {self.stats['block_cooldowns']}\n\n")
                
                final_delay, final_fail_rate, _ = self.rate_limiter.get_stats()
                f.write("ANTI-BLOCK STATS:\n")
                f.write(f"  Final delay:           {final_delay:.2f}s\n")
                f.write(f"  Recent fail rate:      {final_fail_rate*100:.1f}%\n\n")
                
                if self.stats["error_breakdown"]:
                    f.write("ERROR BREAKDOWN:\n")
                    for err_type, count in sorted(self.stats["error_breakdown"].items(), key=lambda x: -x[1]):
                        f.write(f"  {err_type}: {count}\n")
        except Exception:
            pass
    
    def _save_scenes_info(self, project_dir, downloaded):
        """Save merged _scenes_info.txt với tất cả scenes"""
        try:
            # Group downloaded by scene_id
            by_scene = {}
            for scene, item, filename in downloaded:
                sid = scene.get("id")
                if sid not in by_scene:
                    by_scene[sid] = {"scene": scene, "files": []}
                by_scene[sid]["files"].append((item, filename))
            
            with open(project_dir / "_scenes_info.txt", 'w', encoding='utf-8') as f:
                f.write("=" * 70 + "\n")
                f.write("SCENES INFO - Stock Media Project\n")
                f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Total scenes with files: {len(by_scene)}\n")
                f.write("=" * 70 + "\n\n")
                
                # Iterate in scene order (not by_scene dict order)
                for scene in self.scenes:
                    sid = scene.get("id")
                    if sid not in by_scene:
                        continue
                    
                    data = by_scene[sid]
                    scene = data["scene"]
                    files = data["files"]
                    
                    f.write("=" * 70 + "\n")
                    f.write(f"SCENE {sid} | {scene.get('time_start', '?')} -> {scene.get('time_end', '?')}\n")
                    f.write("=" * 70 + "\n\n")
                    
                    # Vietnamese description
                    desc_vi = scene.get('description_vi', '') or scene.get('mo_ta', '')
                    if desc_vi:
                        f.write(f"📖 MÔ TẢ (VN):\n{desc_vi}\n\n")
                    
                    # Dialogue
                    dialogue = scene.get('dialogue_es') or scene.get('dialogue_vi', '') or scene.get('dialogue', '')
                    if dialogue:
                        f.write(f"💬 DIALOGUE:\n{dialogue}\n\n")
                    
                    # Context
                    context = scene.get('context_summary_en') or scene.get('context_summary', '')
                    if context:
                        f.write(f"📝 CONTEXT:\n{context}\n\n")
                    
                    # Keywords
                    primary = scene.get('primary_keywords', [])
                    secondary = scene.get('secondary_keywords', [])
                    if primary or secondary:
                        f.write("🔍 KEYWORDS:\n")
                        if primary:
                            f.write(f"  Primary: {', '.join(primary)}\n")
                        if secondary:
                            f.write(f"  Secondary: {', '.join(secondary)}\n")
                        f.write("\n")
                    
                    # Mood + Shot
                    mood = scene.get('mood', '')
                    shot = scene.get('shot_type', '')
                    if mood or shot:
                        extras = []
                        if mood:
                            extras.append(f"Mood: {mood}")
                        if shot:
                            extras.append(f"Shot: {shot}")
                        f.write(" | ".join(extras) + "\n\n")
                    
                    # Editing notes
                    notes = scene.get('editing_notes_en') or scene.get('editing_notes', '')
                    if notes:
                        f.write(f"✏️ EDITING NOTES:\n{notes}\n\n")
                    
                    # Files
                    videos = [(i, fn) for i, fn in files if i["type"] == "video"]
                    photos = [(i, fn) for i, fn in files if i["type"] == "photo"]
                    
                    if videos:
                        f.write(f"🎬 VIDEOS ({len(videos)}):\n")
                        for item, fn in videos:
                            f.write(f"  - {fn}\n")
                            f.write(f"    {item.get('width', '?')}x{item.get('height', '?')} | "
                                   f"{item.get('duration', '?')}s | by {item.get('author', '?')}\n")
                        f.write("\n")
                    
                    if photos:
                        f.write(f"🖼️ PHOTOS ({len(photos)}):\n")
                        for item, fn in photos:
                            f.write(f"  - {fn}\n")
                            f.write(f"    {item.get('width', '?')}x{item.get('height', '?')} | "
                                   f"by {item.get('author', '?')}\n")
                        f.write("\n")
                    
                    f.write("\n")
                
                # Footer
                f.write("=" * 70 + "\n")
                f.write("CAPCUT WORKFLOW:\n")
                f.write("=" * 70 + "\n")
                f.write("1. Open CapCut Pro Desktop\n")
                f.write("2. Import this folder (all files at once)\n")
                f.write("3. CapCut will sort by filename (= timeline order)\n")
                f.write("4. Drag scene 001 files first, then 002, etc.\n")
                f.write("5. Use this _scenes_info.txt as reference for dialogue/mood\n")
        except Exception as e:
            print(f"Error saving scenes_info: {e}")
    
    def _save_credits(self, project_dir, items):
        try:
            with open(project_dir / "_credits.txt", 'w', encoding='utf-8') as f:
                f.write("CREDITS\n" + "=" * 50 + "\n\n")
                seen = set()
                for item in items:
                    key = f"{item['source']}_{item['author']}"
                    if key not in seen:
                        seen.add(key)
                        f.write(f"{item['type'].title()} by {item['author']} ({item['source']})\n")
                        if item.get('author_url'):
                            f.write(f"  {item['author_url']}\n")
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════════
# VIDEO PREVIEW MODAL with QMediaPlayer
# ═══════════════════════════════════════════════════════════════════

class PreviewModal(QDialog):
    """Modal preview video & image phong cách 1ClickSub Studio Pro"""
    
    def __init__(self, item, thumbnail_cache, parent=None):
        super().__init__(parent)
        self.item = item
        self.thumbnail_cache = thumbnail_cache
        self.media_player = None
        self.video_widget = None
        self.audio_output = None
        
        title_text = f"⚡ Studio Preview • {item['source'].title()} {item['type'].title()} #{item['id']}"
        self.setWindowTitle(title_text)
        self.setMinimumSize(1120, 760)
        self.setStyleSheet(QSS_MAIN)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)
        
        # Info bar top
        info_bar = QFrame()
        info_bar.setStyleSheet("""
            QFrame {
                background-color: #131926;
                border: 1px solid #1e293b;
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
            "motionarray": "#f59e0b",
            "youtube": "#ef4444", "tiktok": "#8b5cf6",
        }
        source_color = source_colors.get(item["source"], "#6366f1")
        info_h.addWidget(Badge(f"⚡ {item['source'].upper()}", source_color))
        
        type_color = "#8b5cf6" if item["type"] == "video" else "#ec4899"
        type_text = "🎬 VIDEO" if item["type"] == "video" else "🖼️ PHOTO"
        info_h.addWidget(Badge(type_text, type_color))
        
        # Size & Duration
        size_text = f"📐 {item.get('width', '?')}x{item.get('height', '?')}"
        if item["type"] == "video":
            size_text += f"   ⏱ {format_duration(item.get('duration', 0))}"
        size_label = QLabel(size_text)
        size_label.setStyleSheet("color: #f1f5f9; font-size: 12px; font-weight: 700; background: transparent;")
        info_h.addWidget(size_label)
        
        info_h.addSpacing(12)
        
        # Author
        author_label = QLabel(f"👤 {item.get('author', 'Unknown')}")
        author_label.setStyleSheet("color: #94a3b8; font-size: 12px; font-weight: 600; background: transparent;")
        info_h.addWidget(author_label)
        
        info_h.addStretch()
        
        # Close button
        btn_close = QPushButton("✕ Đóng (ESC)")
        btn_close.setFixedWidth(120)
        btn_close.clicked.connect(self.close)
        info_h.addWidget(btn_close)
        
        layout.addWidget(info_bar)
        
        # Preview area
        preview_frame = QFrame()
        preview_frame.setStyleSheet("""
            QFrame {
                background-color: #06090e;
                border: 1px solid #1e293b;
                border-radius: 12px;
            }
        """)
        preview_layout = QVBoxLayout(preview_frame)
        preview_layout.setContentsMargins(4, 4, 4, 4)
        
        if item["type"] == "video":
            self._setup_video_player(preview_layout, item)
        else:
            self._setup_image_viewer(preview_layout, item)
        
        layout.addWidget(preview_frame, 1)
        
        # Keyword & info
        kw_label = QLabel(f"🔍 Keyword tìm kiếm: {item.get('search_query', '')}")
        kw_label.setStyleSheet("color: #64748b; font-size: 11px; font-weight: 600;")
        kw_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(kw_label)
        
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    
    def _setup_video_player(self, layout, item):
        """Setup QMediaPlayer for video preview"""
        try:
            self.video_widget = QVideoWidget()
            self.video_widget.setStyleSheet("background: #06090e; border-radius: 8px;")
            layout.addWidget(self.video_widget, 1)
            
            self.media_player = QMediaPlayer()
            self.audio_output = QAudioOutput()
            self.media_player.setAudioOutput(self.audio_output)
            self.media_player.setVideoOutput(self.video_widget)
            self.audio_output.setVolume(0.5)
            
            preview_url = item.get("preview_video_url") or item.get("download_url")
            
            # Controls Bar
            controls = QFrame()
            controls.setStyleSheet("""
                QFrame {
                    background-color: #131926;
                    border: 1px solid #1e293b;
                    border-radius: 10px;
                }
            """)
            controls.setFixedHeight(64)
            ch = QHBoxLayout(controls)
            ch.setContentsMargins(16, 8, 16, 8)
            ch.setSpacing(14)
            
            # Play/Pause button
            self.play_btn = QPushButton("▶ Play")
            self.play_btn.setObjectName("primaryBtn")
            self.play_btn.setFixedWidth(100)
            self.play_btn.setFixedHeight(38)
            self.play_btn.clicked.connect(self._toggle_play)
            ch.addWidget(self.play_btn)
            
            # Progress slider
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
            
            # Time label
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
            
            # Volume
            vol_label = QLabel("🔊")
            vol_label.setStyleSheet("background: transparent; font-size: 14px;")
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
            
            # Status label
            self.status_label = QLabel("⏳ Đang kết nối video preview...")
            self.status_label.setStyleSheet("color: #94a3b8; font-size: 11px; font-weight: 600;")
            self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(self.status_label)
            
            # Connect signals
            self.media_player.positionChanged.connect(self._on_position_changed)
            self.media_player.durationChanged.connect(self._on_duration_changed)
            self.media_player.mediaStatusChanged.connect(self._on_media_status_changed)
            self.media_player.playbackStateChanged.connect(self._on_playback_state_changed)
            self.media_player.errorOccurred.connect(self._on_error)
            
            if preview_url:
                self.media_player.setSource(QUrl(preview_url))
            else:
                self.status_label.setText("❌ Không có URL video preview")
                self.status_label.setStyleSheet("color: #f87171; font-size: 11px;")
        
        except Exception as e:
            error_label = QLabel(f"❌ Lỗi khởi tạo video player:\n{e}\n\nCần PyQt6-Multimedia (pip install PyQt6)")
            error_label.setStyleSheet("color: #f87171; font-size: 13px; padding: 50px;")
            error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            error_label.setWordWrap(True)
            layout.addWidget(error_label)
    
    def _setup_image_viewer(self, layout, item):
        """Setup image preview for photos"""
        self.image_label = QLabel("⏳ Đang tải ảnh chất lượng cao...")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet("color: #94a3b8; font-size: 13px; font-weight: 600;")
        layout.addWidget(self.image_label, 1)
        
        threading.Thread(target=self._load_image, args=(item,), daemon=True).start()
    
    def _load_image(self, item):
        """Load image preview với browser-like headers"""
        try:
            url = item.get("thumb_url") or item.get("download_url")
            if not url:
                return
            
            headers = {
                "User-Agent": get_random_ua(),
                "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "Sec-Fetch-Dest": "image",
                "Sec-Fetch-Mode": "no-cors",
                "Sec-Fetch-Site": "cross-site",
            }
            if "pexels.com" in url or "pexelscdn.com" in url:
                headers["Referer"] = "https://www.pexels.com/"
                headers["Origin"] = "https://www.pexels.com"
            elif "pixabay.com" in url or "pixabaycdn.com" in url:
                headers["Referer"] = "https://pixabay.com/"
                headers["Origin"] = "https://pixabay.com"
            elif "coverr.co" in url or "storage.coverr.co" in url:
                headers["Referer"] = "https://coverr.co/"
                headers["Origin"] = "https://coverr.co"
            elif "motionarray.com" in url or "motionarray.imgix.net" in url or "cms-artifacts.motionarray.com" in url:
                headers["Referer"] = "https://motionarray.com/"
                headers["Origin"] = "https://motionarray.com"
            
            pixmap = None
            for attempt in range(2):
                if attempt > 0:
                    time.sleep(1)
                try:
                    r = requests.get(url, headers=headers, timeout=20)
                    if r.status_code == 200 and len(r.content) > 500:
                        pixmap = QPixmap()
                        if pixmap.loadFromData(r.content) and not pixmap.isNull():
                            break
                        pixmap = None
                except Exception:
                    continue
            
            if pixmap and not pixmap.isNull():
                scaled = pixmap.scaled(
                    1024, 600,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                self._update_image_from_thread(scaled)
            else:
                self._update_image_failed()
        except Exception as e:
            print(f"Image load error: {e}")
            self._update_image_failed()
    
    def _update_image_failed(self):
        def do_update():
            if hasattr(self, 'image_label') and self.image_label:
                try:
                    self.image_label.setText("⚠ Không tải được ảnh preview\n(Có thể CDN throttle, vui lòng thử lại sau)")
                    self.image_label.setStyleSheet("color: #f87171; font-size: 13px; font-weight: 600;")
                except RuntimeError:
                    pass
        QTimer.singleShot(0, do_update)
    
    def _update_image_from_thread(self, pixmap):
        def do_update():
            if hasattr(self, 'image_label') and self.image_label:
                try:
                    self.image_label.setPixmap(pixmap)
                except RuntimeError:
                    pass
        QTimer.singleShot(0, do_update)
    
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
            self.status_label.setText("✓ Video sẵn sàng • Bấm ▶ Play để xem")
            self.status_label.setStyleSheet("color: #34d399; font-size: 11px; font-weight: 700;")
            self.media_player.play()
        elif status == QMediaPlayer.MediaStatus.BufferingMedia:
            self.status_label.setText("⏳ Đang tải đệm (Buffering)...")
            self.status_label.setStyleSheet("color: #38bdf8; font-size: 11px;")
        elif status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.status_label.setText("✓ Đã hết clip • Tự động lặp lại")
            self.media_player.setPosition(0)
            self.media_player.play()
        elif status == QMediaPlayer.MediaStatus.InvalidMedia:
            self.status_label.setText("❌ Video không hợp lệ hoặc lỗi định dạng")
            self.status_label.setStyleSheet("color: #f87171; font-size: 11px;")
    
    def _on_playback_state_changed(self, state):
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.play_btn.setText("⏸ Pause")
        else:
            self.play_btn.setText("▶ Play")
    
    def _on_error(self, error, error_string):
        if self.status_label:
            self.status_label.setText(f"❌ Lỗi: {error_string}")
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
                self.media_player.setSource(QUrl())
            except Exception:
                pass
        super().closeEvent(event)



class VideoCutMergeWorker(QThread):
    """Cut videos in scene folders, then create smooth random final videos."""
    progress = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, folder, segment_seconds=1.0, final_count=1, max_clips_per_final=0):
        super().__init__()
        self.folder = Path(folder)
        self.segment_seconds = max(0.1, float(segment_seconds))
        self.final_count = max(1, int(final_count))
        self.max_clips_per_final = max(0, int(max_clips_per_final))
        self._stop = False
        self.video_exts = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}

    def stop(self):
        self._stop = True

    def _run_cmd(self, cmd):
        creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        return subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=creationflags,
        )

    def _ffmpeg_exists(self):
        try:
            return self._run_cmd(["ffmpeg", "-version"]).returncode == 0
        except Exception:
            return False

    def _video_files(self, folder):
        files = []
        for f in folder.iterdir():
            if f.is_file() and f.suffix.lower() in self.video_exts:
                if not f.stem.lower().startswith("final"):
                    files.append(f)
        return sorted(files, key=lambda x: x.name.lower())

    def _target_folders(self):
        # Nếu chọn folder tổng chứa 1,2,3... thì chạy lần lượt từng folder con.
        child_folders = [d for d in self.folder.iterdir() if d.is_dir() and not d.name.startswith("_") and d.name.lower() != "canh"]
        scene_folders = [d for d in child_folders if self._video_files(d)]
        if scene_folders:
            def sort_key(path):
                return (0, int(path.name)) if path.name.isdigit() else (1, path.name.lower())
            return sorted(scene_folders, key=sort_key)
        return [self.folder] if self._video_files(self.folder) else []


    def _video_size(self, video):
        try:
            r = self._run_cmd([
                "ffprobe", "-v", "error", "-select_streams", "v:0",
                "-show_entries", "stream=width,height",
                "-of", "csv=s=x:p=0", str(video)
            ])
            if r.returncode == 0 and "x" in (r.stdout or ""):
                w, h = (r.stdout.strip().splitlines()[0]).split("x")[:2]
                return int(w), int(h)
        except Exception:
            pass
        return 0, 0

    def _is_vertical_video(self, video):
        w, h = self._video_size(video)
        return w > 0 and h > 0 and h > w

    def _clip_duration(self, clip):
        try:
            r = self._run_cmd([
                "ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", str(clip)
            ])
            if r.returncode == 0:
                return max(0.0, float((r.stdout or "0").strip()))
        except Exception:
            pass
        return 0.0

    def _concat_file(self, folder, clips):
        concat_path = folder / "_clips" / f"concat_{int(time.time()*1000)}_{random.randint(1000,9999)}.txt"
        durations = []
        with open(concat_path, "w", encoding="utf-8") as f:
            for clip in clips:
                safe = str(clip).replace("'", "'\\''")
                durations.append(self._clip_duration(clip))
                f.write(f"file '{safe}'\n")
        return concat_path, sum(durations), len([d for d in durations if d > 0])

    def _clear_old_clips(self, clips_dir):
        clips_dir.mkdir(exist_ok=True)
        for old in clips_dir.glob("*.mp4"):
            try:
                old.unlink()
            except Exception:
                pass
        for old in clips_dir.glob("concat_*.txt"):
            try:
                old.unlink()
            except Exception:
                pass

    def _process_folder(self, folder, folder_index, folder_total, canh_dir):
        raw_videos = self._video_files(folder)
        vertical_videos = [v for v in raw_videos if self._is_vertical_video(v)]
        videos = [v for v in raw_videos if v not in vertical_videos]
        if vertical_videos:
            self.progress.emit(f"  Bỏ {len(vertical_videos)} video dọc trong folder {folder.name}")
        if not videos:
            self.progress.emit(f"Bỏ qua {folder.name}: không có video ngang")
            return 0

        clips_dir = folder / "_clips"
        self._clear_old_clips(clips_dir)
        self.progress.emit(f"[{folder_index}/{folder_total}] Folder {folder.name}: {len(videos)} video, cắt mỗi {self.segment_seconds:g}s")

        clips = []
        part_no = 0
        for idx, video in enumerate(videos, 1):
            if self._stop:
                return 0

            duration = self._clip_duration(video)
            if duration <= 0:
                self.progress.emit(f"  ⚠️ Bỏ qua {video.name}: không đọc được duration")
                continue

            self.progress.emit(f"  [{idx}/{len(videos)}] Cắt chính xác: {video.name} ({duration:.1f}s)")
            start_at = 0.0
            while start_at < duration:
                if self._stop:
                    return 0

                part_no += 1
                out_clip = clips_dir / f"{video.stem}_part_{part_no:04d}.mp4"
                # Cắt từng đoạn bằng -ss/-t thay vì segment muxer để tránh clip bị 8s/12s do lệch keyframe.
                cmd = [
                    "ffmpeg", "-y",
                    "-ss", f"{start_at:.3f}", "-t", f"{self.segment_seconds:.3f}",
                    "-i", str(video),
                    "-map", "0:v:0", "-an",
                    "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease:flags=lanczos,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,fps=30,setsar=1,format=yuv420p,setpts=PTS-STARTPTS",
                    "-r", "30",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
                    "-profile:v", "high", "-level", "4.1", "-pix_fmt", "yuv420p",
                    "-movflags", "+faststart", "-f", "mp4", str(out_clip)
                ]
                r = self._run_cmd(cmd)
                if r.returncode == 0 and out_clip.exists() and out_clip.stat().st_size > 1024:
                    clips.append(out_clip)
                else:
                    self.progress.emit(f"  ⚠️ Lỗi đoạn {start_at:.1f}s của {video.name}: {r.stderr[-220:]}")
                start_at += self.segment_seconds

        clips = [c for c in clips if c.exists() and c.stat().st_size > 1024]
        kept_clips = []
        skipped_short = 0
        for clip in clips:
            duration = self._clip_duration(clip)
            if duration >= 3.0:
                kept_clips.append(clip)
            else:
                skipped_short += 1
        clips = kept_clips
        if skipped_short:
            self.progress.emit(f"  Bỏ {skipped_short} clip ngắn hơn 3s")
        if not clips:
            self.progress.emit(f"  ❌ Folder {folder.name}: không còn clip >= 3s để ghép")
            return 0

        self.progress.emit(f"  Đã tạo {len(clips)} clip hợp lệ (>=3s). Ghép random final...")
        made = 0
        for n in range(1, self.final_count + 1):
            if self._stop:
                return made
            picked = clips[:]
            random.shuffle(picked)
            if self.max_clips_per_final > 0:
                picked = picked[:self.max_clips_per_final]
            expected_seconds = sum(self._clip_duration(c) for c in picked)
            out_name = f"{folder_index}.mp4" if self.final_count == 1 else f"{folder_index}_{n}.mp4"
            out_path = canh_dir / out_name
            # Dùng concat filter thay cho concat demuxer để FFmpeg buộc ăn đủ từng clip,
            # tránh tình trạng demuxer đọc sai timestamp và final bị hụt còn 30-50s.
            cmd = ["ffmpeg", "-y"]
            for clip in picked:
                cmd.extend(["-i", str(clip)])
            filter_parts = []
            for i in range(len(picked)):
                filter_parts.append(
                    f"[{i}:v:0]scale=1920:1080:force_original_aspect_ratio=decrease:flags=lanczos,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,fps=30,setsar=1,format=yuv420p,setpts=PTS-STARTPTS[v{i}]"
                )
            filter_parts.append("".join(f"[v{i}]" for i in range(len(picked))) + f"concat=n={len(picked)}:v=1:a=0[v]")
            cmd.extend([
                "-filter_complex", ";".join(filter_parts),
                "-map", "[v]", "-an", "-r", "30",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
                "-profile:v", "high", "-level", "4.1", "-pix_fmt", "yuv420p",
                "-video_track_timescale", "30000",
                "-movflags", "+faststart", "-f", "mp4", str(out_path)
            ])
            self.progress.emit(f"  Ghép {out_path.name} vào folder Canh từ {len(picked)} clip | tổng duration thật ~{expected_seconds:.1f}s...")
            r = self._run_cmd(cmd)
            if r.returncode != 0:
                self.progress.emit(f"  ⚠️ final {n} lỗi: {r.stderr[-300:]}")
            else:
                made += 1
                self.progress.emit(f"  ✅ Đã lưu: {out_path}")
        return made

    def run(self):
        try:
            if not self.folder.exists() or not self.folder.is_dir():
                self.finished_signal.emit(False, "Folder không tồn tại")
                return
            if not self._ffmpeg_exists():
                self.finished_signal.emit(False, "Không thấy ffmpeg. Cài ffmpeg hoặc thêm ffmpeg vào PATH trước nhé")
                return

            folders = self._target_folders()
            if not folders:
                self.finished_signal.emit(False, "Không tìm thấy video trong folder đã chọn hoặc các folder con")
                return

            canh_dir = self.folder / "Canh" if len(folders) > 1 else self.folder.parent / "Canh"
            canh_dir.mkdir(parents=True, exist_ok=True)
            self.progress.emit(f"Sẽ xử lý {len(folders)} folder cảnh: " + ", ".join(f.name for f in folders[:20]))
            self.progress.emit(f"Final cảnh sẽ lưu tại: {canh_dir}")
            total_final = 0
            for idx, folder in enumerate(folders, 1):
                if self._stop:
                    self.finished_signal.emit(False, "Đã dừng")
                    return
                total_final += self._process_folder(folder, idx, len(folders), canh_dir)

            self.finished_signal.emit(True, f"Xong {len(folders)} folder cảnh, tạo {total_final} file final")
        except Exception as e:
            self.finished_signal.emit(False, str(e))


class NodeToolWorker(QThread):
    progress = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, args, cwd):
        super().__init__()
        self.args = args
        self.cwd = cwd

    def run(self):
        try:
            proc = subprocess.Popen(
                self.args,
                cwd=str(self.cwd),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=(subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0),
            )
            chunks = []
            for line in proc.stdout or []:
                chunks.append(line)
                self.progress.emit(line.rstrip())
            proc.wait()
            out = "".join(chunks).strip()
            self.finished_signal.emit(proc.returncode == 0, out or f"Done: {' '.join(self.args)}")
        except Exception as e:
            self.finished_signal.emit(False, str(e))


# ═══════════════════════════════════════════════════════════════════
# NATIVE WORKFLOW CANVAS
# ═══════════════════════════════════════════════════════════════════

class WorkflowNodeItem(QGraphicsRectItem):
    def __init__(self, node_id, title, x=0, y=0, config=None):
        super().__init__(0, 0, 190, 74)
        self.node_id = node_id
        self.title = title
        self.config = dict(config or {})
        self.lines = []
        self.setPos(x, y)
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable |
            QGraphicsItem.GraphicsItemFlag.ItemIsSelectable |
            QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        self.setBrush(QBrush(QColor("#182332")))
        self.setPen(QPen(QColor("#3d5872"), 2))
        self.title_item = QGraphicsTextItem(title, self)
        self.title_item.setDefaultTextColor(QColor("#f4d35e"))
        self.title_item.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.title_item.setPos(12, 10)
        self.sub_item = QGraphicsTextItem("", self)
        self.sub_item.setDefaultTextColor(QColor("#9fb0c3"))
        self.sub_item.setFont(QFont("Segoe UI", 8))
        self.sub_item.setPos(12, 38)
        self.refresh_label()

    def refresh_label(self):
        self.title_item.setPlainText(self.title)
        config_mark = " | có config" if self.config else " | double-click config"
        self.sub_item.setPlainText(f"#{self.node_id} kéo để sắp xếp{config_mark}")

    def center_left(self):
        return self.scenePos() + QPointF(0, 37)

    def center_right(self):
        return self.scenePos() + QPointF(190, 37)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            for line in self.lines:
                line.update_position()
        return super().itemChange(change, value)

class WorkflowEdgeItem(QGraphicsLineItem):
    def __init__(self, source, target):
        super().__init__()
        self.source = source
        self.target = target
        self.setPen(QPen(QColor("#4ec9b0"), 3))
        source.lines.append(self)
        target.lines.append(self)
        self.update_position()

    def update_position(self):
        self.setLine(QLineF(self.source.center_right(), self.target.center_left()))

class WorkflowNodeConfigDialog(QDialog):
    def __init__(self, node, parent=None):
        super().__init__(parent)
        self.node = node
        self.fields = {}
        self.setWindowTitle(f"Cài thông số node: {node.title}")
        self.resize(620, 520)
        self.config = dict(node.config or {})
        layout = QVBoxLayout(self)
        self.title_input = QLineEdit(node.title)
        layout.addWidget(QLabel("Tên node:")); layout.addWidget(self.title_input)
        hint = QLabel("Cài option trực tiếp cho node. Khi workflow chạy, app tự áp các option này trước khi chạy node.")
        hint.setWordWrap(True); layout.addWidget(hint)
        self.form_box = QFrame(); self.form_layout = QGridLayout(self.form_box); self.form_layout.setColumnStretch(1, 1)
        layout.addWidget(self.form_box, 1)
        self._build_form(node.title)
        row = QHBoxLayout(); row.addStretch()
        cancel_btn = QPushButton("Huỷ"); cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton("Lưu node"); save_btn.clicked.connect(self.accept)
        row.addWidget(cancel_btn); row.addWidget(save_btn); layout.addLayout(row)

    def _add_row(self, row, label, widget, key=None, browse=None):
        self.form_layout.addWidget(QLabel(label), row, 0)
        self.form_layout.addWidget(widget, row, 1)
        if key:
            self.fields[key] = widget
        if browse:
            btn = QPushButton("Chọn..."); btn.clicked.connect(lambda: self._browse(widget, browse))
            self.form_layout.addWidget(btn, row, 2)

    def _browse(self, widget, mode):
        if mode == "folder":
            value = QFileDialog.getExistingDirectory(self, "Chọn thư mục")
        else:
            value, _ = QFileDialog.getOpenFileName(self, "Chọn file", "", "All files (*.*)")
        if value:
            widget.setText(value)

    def _combo(self, items, value):
        combo = QComboBox(); combo.addItems(items)
        idx = combo.findText(str(value or ""))
        if idx >= 0: combo.setCurrentIndex(idx)
        return combo

    def _spin(self, value, min_value=1, max_value=99):
        spin = QSpinBox(); spin.setRange(min_value, max_value); spin.setValue(int(value or min_value)); return spin

    def _double_spin(self, value, min_value=0.5, max_value=2.0):
        spin = QDoubleSpinBox(); spin.setRange(min_value, max_value); spin.setSingleStep(0.1); spin.setValue(float(value or 1.0)); return spin

    def _line(self, value=""):
        return QLineEdit(str(value or ""))

    def _check(self, value=False):
        check = QCheckBox(); check.setChecked(bool(value)); return check

    def _build_form(self, title):
        cfg = self.config
        row = 0
        if title == "Load JSON":
            self._add_row(row, "Mở dialog chọn JSON khi chạy", self._check(cfg.get("open_dialog", False)), "open_dialog"); row += 1
            self._add_row(row, "File JSON", self._line(cfg.get("json", "")), "json", "file"); row += 1
        elif title == "Search stock":
            self._add_row(row, "Nguồn search", self._combo(["Pexels + Pixabay", "Pexels + Pixabay + Vecteezy", "Chỉ Pexels", "Chỉ Pixabay", "Chỉ Vecteezy"], cfg.get("source", "Pexels + Pixabay")), "source"); row += 1
            self._add_row(row, "Kiểu media", self._combo(["Video + ảnh", "Chỉ video", "Chỉ ảnh"], cfg.get("media_mode", "Video + ảnh")), "media_mode"); row += 1
            self._add_row(row, "Random mỗi scene sau search", self._spin(cfg.get("random_per_scene", 2), 1, 20), "random_per_scene"); row += 1
        elif title == "Random select":
            self._add_row(row, "Kiểu media", self._combo(["Video + ảnh", "Chỉ video", "Chỉ ảnh"], cfg.get("media_mode", "Video + ảnh")), "media_mode"); row += 1
            self._add_row(row, "Số media/scene", self._spin(cfg.get("count", 2), 1, 20), "count"); row += 1
        elif title == "Download selected":
            self._add_row(row, "Tải không hỏi xác nhận", self._check(not cfg.get("confirm", False)), "confirm_less"); row += 1
            self._add_row(row, "Output folder", self._line(cfg.get("output_dir", "")), "output_dir", "folder"); row += 1
        elif title == "Cut/Mix video":
            self._add_row(row, "Folder tổng/cảnh", self._line(cfg.get("folder", "")), "folder", "folder"); row += 1
            self._add_row(row, "Cắt mỗi giây", self._double_spin(cfg.get("segment_seconds", 1.0), 0.2, 60.0), "segment_seconds"); row += 1
            self._add_row(row, "Số final", self._spin(cfg.get("final_count", 1), 1, 50), "final_count"); row += 1
            self._add_row(row, "Max clip/final (0 = dùng hết)", self._spin(cfg.get("max_clips", 0), 0, 9999), "max_clips"); row += 1
        elif title == "Create voice":
            self._add_row(row, "Mode", self._combo(["TXT folder/file", "JSON parts/scenes"], cfg.get("mode", "TXT folder/file")), "mode"); row += 1
            self._add_row(row, "Thư mục TXT", self._line(cfg.get("txt_dir", "")), "txt_dir", "folder"); row += 1
            self._add_row(row, "File TXT", self._line(cfg.get("txt_file", "")), "txt_file", "file"); row += 1
            self._add_row(row, "File JSON parts/scenes", self._line(cfg.get("json", "")), "json", "file"); row += 1
            self._add_row(row, "Output folder", self._line(cfg.get("output_dir", "")), "output_dir", "folder"); row += 1
        elif title == "Scene voice match":
            self._add_row(row, "File JSON (không bắt buộc)", self._line(cfg.get("json", "")), "json", "file"); row += 1
            self._add_row(row, "Folder video cảnh", self._line(cfg.get("root", "")), "root", "folder"); row += 1
            self._add_row(row, "SRT/TXT hoặc folder voice", self._line(cfg.get("voice", "")), "voice", "file"); row += 1
            self._add_row(row, "Full voice MP3/WAV", self._line(cfg.get("full_voice", "")), "full_voice", "file"); row += 1
            self._add_row(row, "Cắt clip con mỗi giây (0 = tắt)", self._spin(cfg.get("chunk_seconds", 0.0), 0.0, 120.0), "chunk_seconds"); row += 1
            self._add_row(row, "Output folder", self._line(cfg.get("output_dir", "")), "output_dir", "folder"); row += 1
            self._add_row(row, "Random", self._check(cfg.get("random", False)), "random"); row += 1
            self._add_row(row, "Concat", self._check(cfg.get("concat", True)), "concat"); row += 1
        else:
            self.config_input = QPlainTextEdit(json.dumps(cfg, ensure_ascii=False, indent=2))
            self._add_row(row, "Config JSON", self.config_input)

    def _field_value(self, widget):
        if isinstance(widget, QComboBox): return widget.currentText()
        if isinstance(widget, QSpinBox): return widget.value()
        if isinstance(widget, QDoubleSpinBox): return widget.value()
        if isinstance(widget, QCheckBox): return widget.isChecked()
        if isinstance(widget, QLineEdit): return widget.text().strip()
        return None

    def values(self):
        if hasattr(self, "config_input"):
            config = json.loads(self.config_input.toPlainText().strip() or "{}")
        else:
            config = {key: self._field_value(widget) for key, widget in self.fields.items()}
            if "confirm_less" in config:
                config["confirm"] = not config.pop("confirm_less")
        return self.title_input.text().strip() or "Node", config

class WorkflowCanvas(QGraphicsView):
    def __init__(self, parent_window):
        super().__init__()
        self.parent_window = parent_window
        self.scene_obj = QGraphicsScene(self)
        self.setScene(self.scene_obj)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setAcceptDrops(True)
        self.nodes = []
        self.edges = []
        self.next_id = 1
        self.setStyleSheet("background:#0b1118; border:1px solid #2d4053; border-radius:12px;")
        self.setSceneRect(0, 0, 1400, 900)

    def default_config_for(self, title):
        defaults = {
            "Load JSON": {"open_dialog": False},
            "Search stock": {"source": "Pexels + Pixabay", "media_mode": "Video + ảnh", "random_per_scene": 2},
            "Random select": {"media_mode": "Video + ảnh", "count": 2},
            "Download selected": {"confirm": False},
            "Cut/Mix video": {"folder": "", "segment_seconds": 1.0, "final_count": 1, "max_clips": 0},
            "Create voice": {"mode": "TXT folder/file", "txt_dir": "", "txt_file": "", "json": "", "output_dir": ""},
            "Scene voice match": {"random": False, "concat": True, "full_voice": "", "chunk_seconds": 0.0},
        }
        return dict(defaults.get(title, {}))

    def add_node(self, title, x=None, y=None, config=None):
        if x is None:
            x = 60 + (len(self.nodes) % 4) * 230
        if y is None:
            y = 70 + (len(self.nodes) // 4) * 120
        node = WorkflowNodeItem(self.next_id, title, x, y, self.default_config_for(title) if config is None else config)
        self.next_id += 1
        self.scene_obj.addItem(node)
        self.nodes.append(node)
        self.rebuild_edges()
        return node

    def rebuild_edges(self):
        for edge in self.edges:
            self.scene_obj.removeItem(edge)
        self.edges = []
        ordered = self.ordered_nodes()
        for a, b in zip(ordered, ordered[1:]):
            edge = WorkflowEdgeItem(a, b)
            self.scene_obj.addItem(edge)
            self.edges.append(edge)

    def ordered_nodes(self):
        return sorted(self.nodes, key=lambda n: (n.scenePos().x(), n.scenePos().y(), n.node_id))

    def workflow_steps(self):
        return [n.title for n in self.ordered_nodes()]

    def workflow_nodes(self):
        return self.ordered_nodes()

    def clear(self):
        self.scene_obj.clear()
        self.nodes = []
        self.edges = []
        self.next_id = 1

    def save_payload(self):
        return [{"title": n.title, "x": n.scenePos().x(), "y": n.scenePos().y(), "config": n.config} for n in self.nodes]

    def load_payload(self, payload):
        self.clear()
        for item in payload:
            self.add_node(item.get("title", "Node"), item.get("x", 60), item.get("y", 70), item.get("config", {}))
        self.rebuild_edges()

    def mouseDoubleClickEvent(self, event):
        item = self.itemAt(event.pos())
        node = item
        while node and not isinstance(node, WorkflowNodeItem):
            node = node.parentItem()
        if node:
            dialog = WorkflowNodeConfigDialog(node, self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                node.title, node.config = dialog.values()
                node.refresh_label()
                self.rebuild_edges()
            return
        super().mouseDoubleClickEvent(event)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        self.rebuild_edges()

# ═══════════════════════════════════════════════════════════════════
# MAIN WINDOW
# ═══════════════════════════════════════════════════════════════════

class StockPreviewWindow(QMainWindow):
    """Main app window"""
    
    def __init__(self):
        super().__init__()
        
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION} - PyQt6 Edition")
        
        # ═══════════ RESPONSIVE WINDOW SIZING ═══════════
        screen = QApplication.primaryScreen().availableGeometry()
        screen_w = screen.width()
        screen_h = screen.height()
        
        # Set minimum size to ensure usability
        self.setMinimumSize(1200, 700)
        
        # Calculate optimal window size (90% of screen)
        window_w = min(1700, int(screen_w * 0.92))
        window_h = min(950, int(screen_h * 0.92))
        
        # Center on screen
        x = (screen_w - window_w) // 2 + screen.x()
        y = (screen_h - window_h) // 2 + screen.y()
        
        self.setGeometry(x, y, window_w, window_h)
        
        # If screen is small, start maximized
        if screen_w < 1500 or screen_h < 850:
            self.showMaximized()
        
        # State
        self.config = load_config()
        self.thumbnail_cache = ThumbnailCache(CACHE_DIR)
        self.thumb_loader = ThumbnailLoader(self.thumbnail_cache)
        self.thumb_loader.signals.loaded.connect(self._on_thumbnail_loaded)
        self.thumb_loader.signals.failed.connect(self._on_thumbnail_failed)
        
        # Downloads watcher (cho MotionArray manual download)
        self.downloads_watcher = DownloadsWatcher()
        self.downloads_watcher.signals.fileDetected.connect(self._on_download_detected)
        self._watcher_started = False  # start lazy khi có scenes
        
        self.scenes = []
        self.json_data = None
        self.scene_items = {}  # scene_id -> list of items
        self.selected_items = {}  # scene_id -> dict of item_key -> item
        self.current_scene_id = None
        self.current_page = 0
        self.current_filter = "all"
        self._current_ma_scene_id = None  # Scene đang xem MotionArray (cho watcher)
        
        # UI references
        self.scene_list_widgets = []  # SceneListItem widgets
        self.thumb_cards = []  # active ThumbnailCard widgets
        self.url_to_cards = {}  # url -> [cards] for thumb loading
        
        # Threads
        self.search_thread = None
        self.search_worker = None
        self.download_worker = None
        self.download_thread = None
        self.stop_event = threading.Event()
        
        # Try restore state
        self._try_restore_state()
        
        # Build UI
        self.setStyleSheet(QSS_MAIN)
        self._build_ui()
        
        # Restore display
        if self.scenes:
            self._populate_scene_list()
            if self.scene_items:
                first_with_items = next(
                    (s for s in self.scenes if self.scene_items.get(s.get("id"))),
                    None
                )
                if first_with_items:
                    self._on_scene_clicked(first_with_items)
    
    def _try_restore_state(self):
        state = load_state()
        if state:
            try:
                self.scenes = state.get("scenes", [])
                self.json_data = state.get("json_data", None)
                self.scene_items = state.get("scene_items", {})
                self.selected_items = state.get("selected_items", {})
                self.current_scene_id = state.get("current_scene_id", None)
            except Exception:
                pass
    
    def _save_app_state(self):
        try:
            state = {
                "scenes": self.scenes,
                "json_data": self.json_data,
                "scene_items": self.scene_items,
                "selected_items": self.selected_items,
                "current_scene_id": self.current_scene_id,
            }
            save_state(state)
        except Exception:
            pass
    
    def _build_ui(self):
        """Build 4-column layout: setup | scenes | grid | motionarray (1ClickSub Studio Style)"""
        central = QWidget()
        self.setCentralWidget(central)
        
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.main_tabs = QTabWidget()
        root_layout.addWidget(self.main_tabs, 1)

        download_tab = QWidget()
        main_layout = QHBoxLayout(download_tab)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Column 1: Setup sidebar (actions + status)
        self.setup_sidebar = self._build_setup_sidebar()
        main_layout.addWidget(self.setup_sidebar)
        
        # Column 2: Scenes sidebar (scenes list + scene info)
        self.scenes_sidebar = self._build_scenes_sidebar()
        main_layout.addWidget(self.scenes_sidebar)
        
        # Column 3: Main area (grid, stretches)
        self.main_area = self._build_main_area()
        main_layout.addWidget(self.main_area, 1)  # stretch
        
        # Column 4: MotionArray sidebar (right side)
        self.ma_sidebar = self._build_motionarray_sidebar()
        main_layout.addWidget(self.ma_sidebar)

        self.main_tabs.addTab(download_tab, "🎞️ Stock Downloader")
        self.main_tabs.addTab(self._build_video_cut_tab(), "✂️ Cut & Mix Studio")
        self.main_tabs.addTab(self._build_voice_tab(), "🎙️ Voice TXT Studio")
        self.main_tabs.addTab(self._build_scene_voice_tab(), "🎬 Khớp Voice Scene")
        self.main_tabs.addTab(self._build_auto_tab(), "⚡ Auto Mode")
        self.main_tabs.addTab(self._build_workflow_tab(), "🧩 Workflow Node")
        
        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("● Studio Sẵn Sàng")
    
    def _build_setup_sidebar(self):
        sidebar = QFrame()
        sidebar.setObjectName("setupSidebar")
        
        screen_w = QApplication.primaryScreen().availableGeometry().width()
        if screen_w < 1500:
            sidebar.setFixedWidth(245)
        else:
            sidebar.setFixedWidth(275)
        
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)
        
        # 1ClickSub Studio Header Brand Box
        brand_card = QFrame()
        brand_card.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #1a2235, stop:1 #111724);
                border: 1px solid #2d3b55;
                border-radius: 10px;
            }
        """)
        brand_card_layout = QVBoxLayout(brand_card)
        brand_card_layout.setContentsMargins(12, 10, 12, 10)
        brand_card_layout.setSpacing(4)
        
        title = QLabel("⚡ 1CLICK STOCK PRO")
        title.setStyleSheet("""
            color: #ffffff;
            font-size: 14px;
            font-weight: 900;
            letter-spacing: 0.8px;
            background: transparent;
            border: none;
        """)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand_card_layout.addWidget(title)
        
        version_row = QHBoxLayout()
        version_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version_badge = QLabel(f"v{APP_VERSION} STUDIO")
        version_badge.setStyleSheet("""
            background-color: rgba(99, 102, 241, 0.2);
            color: #818cf8;
            font-size: 10px;
            font-weight: 800;
            padding: 2px 8px;
            border-radius: 8px;
            border: 1px solid rgba(99, 102, 241, 0.4);
        """)
        version_row.addWidget(version_badge)
        brand_card_layout.addLayout(version_row)
        layout.addWidget(brand_card)
        
        # Settings button
        btn_settings = QPushButton("⚙️ Cài đặt & API Keys")
        btn_settings.setToolTip("Quản lý thư mục lưu, API keys, JSON input")
        btn_settings.clicked.connect(self._open_settings_dialog)
        btn_settings.setStyleSheet("""
            QPushButton {
                background-color: #131926;
                color: #e2e8f0;
                font-weight: 700;
                font-size: 11px;
                padding: 8px;
                border-radius: 8px;
                border: 1px solid #2d3b55;
            }
            QPushButton:hover {
                background-color: #1e293b;
                border-color: #6366f1;
                color: #ffffff;
            }
        """)
        layout.addWidget(btn_settings)
        
        # JSON status pill
        self.json_status_label = QLabel("Chưa có JSON")
        self.json_status_label.setStyleSheet("""
            color: #94a3b8;
            font-size: 10px;
            font-weight: 600;
            padding: 4px 8px;
            background: #0c0f17;
            border-radius: 6px;
            border: 1px solid #1e293b;
        """)
        self.json_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.json_status_label.setWordWrap(True)
        layout.addWidget(self.json_status_label)
        if self.scenes:
            self.json_status_label.setText(f"✓ Đã nạp {len(self.scenes)} scenes")
            self.json_status_label.setStyleSheet("""
                color: #34d399;
                font-size: 10px;
                font-weight: 700;
                padding: 4px 8px;
                background: rgba(16, 185, 129, 0.1);
                border-radius: 6px;
                border: 1px solid rgba(16, 185, 129, 0.3);
            """)
        
        # Section: Search options
        layout.addWidget(self._section_header("⚙️ TÙY CHỌN TÌM KIẾM"))
        
        search_prefs = self.config.get("search_prefs", {
            "photos": True,
            "videos": True,
            "source": "Pexels + Pixabay",
        })

        source_row = QHBoxLayout()
        source_lbl = QLabel("Nguồn:")
        source_lbl.setStyleSheet("color: #cbd5e1; font-weight: 600; font-size: 11px;")
        source_row.addWidget(source_lbl)
        self.search_source_combo = QComboBox()
        self.search_source_combo.addItems(["Pexels + Pixabay", "Pexels + Pixabay + Vecteezy", "Chỉ Pexels", "Chỉ Pixabay", "Chỉ Vecteezy"])
        self._workflow_set_combo(self.search_source_combo, search_prefs.get("source", "Pexels + Pixabay"))
        self.search_source_combo.currentTextChanged.connect(self._save_search_prefs)
        source_row.addWidget(self.search_source_combo, 1)
        layout.addLayout(source_row)
        
        chk_row = QHBoxLayout()
        self.search_photos_check = QCheckBox("Tìm ảnh")
        self.search_photos_check.setChecked(search_prefs.get("photos", True))
        self.search_photos_check.toggled.connect(self._save_search_prefs)
        chk_row.addWidget(self.search_photos_check)
        
        self.search_videos_check = QCheckBox("Tìm video")
        self.search_videos_check.setChecked(search_prefs.get("videos", True))
        self.search_videos_check.toggled.connect(self._save_search_prefs)
        chk_row.addWidget(self.search_videos_check)
        layout.addLayout(chk_row)
        
        # ACTION buttons
        layout.addWidget(self._section_header("🎬 HÀNH ĐỘNG"))
        
        self.search_btn = QPushButton("🔍 SEARCH TẤT CẢ")
        self.search_btn.setObjectName("primaryBtn")
        self.search_btn.setFixedHeight(42)
        self.search_btn.setStyleSheet("""
            QPushButton#primaryBtn {
                font-size: 13px;
                font-weight: 800;
                letter-spacing: 0.5px;
            }
        """)
        self.search_btn.clicked.connect(self._start_search)
        layout.addWidget(self.search_btn)
        
        action_btn_row = QHBoxLayout()
        action_btn_row.setSpacing(6)
        
        self.stop_btn = QPushButton("⏹ DỪNG")
        self.stop_btn.setObjectName("dangerBtn")
        self.stop_btn.setFixedHeight(34)
        self.stop_btn.clicked.connect(self._stop_action)
        self.stop_btn.setEnabled(False)
        action_btn_row.addWidget(self.stop_btn)
        
        btn_reset = QPushButton("🗑 Reset")
        btn_reset.setFixedHeight(34)
        btn_reset.clicked.connect(self._reset_all)
        action_btn_row.addWidget(btn_reset)
        layout.addLayout(action_btn_row)
        
        # STATUS PANEL
        layout.addSpacing(4)
        self.status_panel = StatusPanel()
        layout.addWidget(self.status_panel, 1)
        
        return sidebar
    
    def _build_scenes_sidebar(self):
        """Sidebar 2: SCENES list + SCENE INFO (1ClickSub Studio Style)"""
        sidebar = QFrame()
        sidebar.setObjectName("scenesSidebar")
        
        screen_w = QApplication.primaryScreen().availableGeometry().width()
        if screen_w < 1500:
            sidebar.setFixedWidth(220)
        else:
            sidebar.setFixedWidth(240)
        
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(10, 12, 10, 12)
        layout.setSpacing(8)
        
        # Header
        header_row = QHBoxLayout()
        header = QLabel("🎬 TIMELINE")
        header.setStyleSheet("color: #f1f5f9; font-size: 12px; font-weight: 800; letter-spacing: 0.5px;")
        header_row.addWidget(header)
        header_row.addStretch()
        
        self.scenes_count_label = QLabel("0 scenes")
        self.scenes_count_label.setStyleSheet("""
            color: #818cf8;
            font-size: 10px;
            font-weight: 800;
            background: rgba(99, 102, 241, 0.15);
            padding: 2px 6px;
            border-radius: 6px;
        """)
        header_row.addWidget(self.scenes_count_label)
        layout.addLayout(header_row)
        
        # Search box
        self.scene_search_input = QLineEdit()
        self.scene_search_input.setPlaceholderText("🔍 Tìm scene...")
        self.scene_search_input.textChanged.connect(self._filter_scenes)
        layout.addWidget(self.scene_search_input)
        
        # Scrollable scenes list
        self.scenes_scroll = QScrollArea()
        self.scenes_scroll.setWidgetResizable(True)
        self.scenes_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scenes_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scenes_scroll.setFixedHeight(380)
        self.scenes_scroll.setStyleSheet("""
            QScrollArea {
                background-color: #0c0f17;
                border: 1px solid #1e293b;
                border-radius: 8px;
            }
        """)
        
        self.scenes_container = QWidget()
        self.scenes_layout = QVBoxLayout(self.scenes_container)
        self.scenes_layout.setContentsMargins(4, 4, 4, 4)
        self.scenes_layout.setSpacing(4)
        self.scenes_layout.addStretch()
        
        self.scenes_scroll.setWidget(self.scenes_container)
        layout.addWidget(self.scenes_scroll)
        
        # SCENE INFO panel
        info_header = QLabel("📝 SCENE INFO & PROMPT")
        info_header.setStyleSheet("color: #94a3b8; font-size: 10px; font-weight: 800; letter-spacing: 0.8px; padding-top: 4px;")
        layout.addWidget(info_header)
        
        self.scene_info_panel = QTextEdit()
        self.scene_info_panel.setReadOnly(True)
        self.scene_info_panel.setMinimumHeight(180)
        self.scene_info_panel.setStyleSheet("""
            QTextEdit {
                background-color: #0c0f17;
                color: #cbd5e1;
                border: 1px solid #1e293b;
                border-radius: 8px;
                padding: 10px;
                font-size: 11px;
                line-height: 1.4;
            }
        """)
        self.scene_info_panel.setPlainText("Chọn scene trong danh sách để xem chi tiết prompt & từ khóa.")
        layout.addWidget(self.scene_info_panel, 1)
        
        return sidebar
    
    def _build_motionarray_sidebar(self):
        """Sidebar 4 (right): MotionArray & Download Monitor (1ClickSub Studio Style)"""
        sidebar = QFrame()
        sidebar.setObjectName("maSidebar")
        
        screen_w = QApplication.primaryScreen().availableGeometry().width()
        if screen_w < 1500:
            sidebar.setFixedWidth(240)
        else:
            sidebar.setFixedWidth(265)
        
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(10, 12, 10, 12)
        layout.setSpacing(10)
        
        # === MotionArray Amber Studio Card ===
        ma_frame = QFrame()
        ma_frame.setStyleSheet("""
            QFrame {
                background-color: #131926;
                border: 1px solid rgba(245, 158, 11, 0.4);
                border-radius: 10px;
            }
        """)
        ma_layout = QVBoxLayout(ma_frame)
        ma_layout.setContentsMargins(10, 10, 10, 10)
        ma_layout.setSpacing(6)
        
        ma_header_h = QHBoxLayout()
        ma_header_h.setSpacing(4)
        ma_header = QLabel("🎬 MOTIONARRAY")
        ma_header.setStyleSheet("""
            color: #fbbf24;
            font-size: 12px;
            font-weight: 800;
            letter-spacing: 0.5px;
            background: transparent;
            border: none;
        """)
        ma_header_h.addWidget(ma_header)
        ma_header_h.addStretch()
        
        btn_select_all_kw = QPushButton("✓ All")
        btn_select_all_kw.setStyleSheet("""
            QPushButton {
                background-color: rgba(245, 158, 11, 0.15);
                color: #fbbf24;
                border: 1px solid rgba(245, 158, 11, 0.3);
                border-radius: 4px;
                padding: 2px 6px;
                font-size: 10px;
                font-weight: 700;
            }
            QPushButton:hover { background-color: rgba(245, 158, 11, 0.3); }
        """)
        btn_select_all_kw.setFixedHeight(22)
        btn_select_all_kw.clicked.connect(self._ma_select_all_keywords)
        ma_header_h.addWidget(btn_select_all_kw)
        
        btn_select_none_kw = QPushButton("✗ Bỏ")
        btn_select_none_kw.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #94a3b8;
                border: 1px solid #334155;
                border-radius: 4px;
                padding: 2px 6px;
                font-size: 10px;
                font-weight: 700;
            }
            QPushButton:hover { background-color: #334155; color: #ffffff; }
        """)
        btn_select_none_kw.setFixedHeight(22)
        btn_select_none_kw.clicked.connect(self._ma_select_no_keywords)
        ma_header_h.addWidget(btn_select_none_kw)
        ma_layout.addLayout(ma_header_h)
        
        ma_instr = QLabel("Chọn keywords để mở tab:")
        ma_instr.setStyleSheet("color: #94a3b8; font-size: 10px; font-weight: 600; background: transparent; border: none;")
        ma_layout.addWidget(ma_instr)
        
        # Keywords list
        self.ma_keywords_scroll = QScrollArea()
        self.ma_keywords_scroll.setWidgetResizable(True)
        self.ma_keywords_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.ma_keywords_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.ma_keywords_scroll.setStyleSheet("""
            QScrollArea {
                background-color: #0c0f17;
                border: 1px solid #1e293b;
                border-radius: 6px;
            }
        """)
        
        self.ma_keywords_container = QWidget()
        self.ma_keywords_layout = QVBoxLayout(self.ma_keywords_container)
        self.ma_keywords_layout.setContentsMargins(6, 6, 6, 6)
        self.ma_keywords_layout.setSpacing(4)
        
        self.ma_keywords_placeholder = QLabel("👈 Chọn scene để tải keywords")
        self.ma_keywords_placeholder.setStyleSheet("color: #64748b; font-size: 11px; padding: 25px 8px; background: transparent;")
        self.ma_keywords_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ma_keywords_placeholder.setWordWrap(True)
        self.ma_keywords_layout.addWidget(self.ma_keywords_placeholder)
        self.ma_keywords_layout.addStretch()
        
        self.ma_keywords_scroll.setWidget(self.ma_keywords_container)
        ma_layout.addWidget(self.ma_keywords_scroll, 1)
        
        self.ma_keyword_checks = []
        
        # Status
        self.ma_status_label = QLabel("Chọn scene trước")
        self.ma_status_label.setStyleSheet("""
            color: #94a3b8;
            font-size: 10px;
            padding: 3px 6px;
            background-color: #0c0f17;
            border-radius: 4px;
            border: 1px solid #1e293b;
        """)
        self.ma_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ma_status_label.setFixedHeight(24)
        ma_layout.addWidget(self.ma_status_label)
        
        # Button mở tab MotionArray
        self.btn_motionarray = QPushButton("🔍 Mở Tabs MotionArray")
        self.btn_motionarray.setEnabled(False)
        self.btn_motionarray.setToolTip("Mở MotionArray search với keywords đã tick chọn")
        self.btn_motionarray.clicked.connect(self._open_motionarray_search)
        self.btn_motionarray.setFixedHeight(36)
        self.btn_motionarray.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #d97706, stop:1 #f59e0b);
                color: #ffffff;
                font-weight: 800;
                font-size: 11px;
                padding: 6px;
                border-radius: 6px;
                border: none;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #b45309, stop:1 #d97706);
            }
            QPushButton:disabled {
                background-color: #1e293b;
                color: #64748b;
                border: 1px solid #334155;
            }
        """)
        ma_layout.addWidget(self.btn_motionarray)
        
        self.ma_watcher_label = QLabel("")
        self.ma_watcher_label.setStyleSheet("color: #64748b; font-size: 9px; background: transparent; border: none;")
        self.ma_watcher_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ma_watcher_label.setWordWrap(True)
        self.ma_watcher_label.setMaximumHeight(18)
        ma_layout.addWidget(self.ma_watcher_label)
        
        layout.addWidget(ma_frame, 2)
        
        # === Download Monitor Emerald Studio Card ===
        dm_frame = QFrame()
        dm_frame.setStyleSheet("""
            QFrame {
                background-color: #131926;
                border: 1px solid rgba(16, 185, 129, 0.4);
                border-radius: 10px;
            }
        """)
        dm_layout = QVBoxLayout(dm_frame)
        dm_layout.setContentsMargins(10, 10, 10, 10)
        dm_layout.setSpacing(6)
        
        dm_header_h = QHBoxLayout()
        dm_header_h.setSpacing(4)
        
        dm_header = QLabel("📥 TIẾN ĐỘ DOWNLOAD")
        dm_header.setStyleSheet("""
            color: #34d399;
            font-size: 12px;
            font-weight: 800;
            letter-spacing: 0.5px;
            background: transparent;
            border: none;
        """)
        dm_header_h.addWidget(dm_header)
        dm_header_h.addStretch()
        
        btn_dm_refresh = QPushButton("🔄")
        btn_dm_refresh.setToolTip("Quét lại folder output")
        btn_dm_refresh.setFixedSize(26, 22)
        btn_dm_refresh.setStyleSheet("""
            QPushButton {
                background-color: rgba(16, 185, 129, 0.15);
                color: #34d399;
                border: 1px solid rgba(16, 185, 129, 0.3);
                border-radius: 4px;
                font-size: 11px;
            }
            QPushButton:hover { background-color: rgba(16, 185, 129, 0.3); }
        """)
        btn_dm_refresh.clicked.connect(self._refresh_download_monitor)
        dm_header_h.addWidget(btn_dm_refresh)
        dm_layout.addLayout(dm_header_h)
        
        self.dm_summary_label = QLabel("0 scenes có file • 0 files tổng")
        self.dm_summary_label.setStyleSheet("""
            color: #cbd5e1;
            font-size: 10px;
            font-weight: 600;
            padding: 4px 6px;
            background-color: #0c0f17;
            border-radius: 4px;
            border: 1px solid #1e293b;
        """)
        self.dm_summary_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.dm_summary_label.setWordWrap(True)
        dm_layout.addWidget(self.dm_summary_label)
        
        self.dm_scroll = QScrollArea()
        self.dm_scroll.setWidgetResizable(True)
        self.dm_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.dm_scroll.setStyleSheet("""
            QScrollArea {
                background-color: #0c0f17;
                border: 1px solid #1e293b;
                border-radius: 6px;
            }
        """)
        
        self.dm_container = QWidget()
        self.dm_container_layout = QVBoxLayout(self.dm_container)
        self.dm_container_layout.setContentsMargins(4, 4, 4, 4)
        self.dm_container_layout.setSpacing(3)
        
        self.dm_placeholder = QLabel("Chưa có scenes\n(Load JSON trước)")
        self.dm_placeholder.setStyleSheet("color: #64748b; font-size: 11px; padding: 25px 8px; background: transparent;")
        self.dm_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.dm_placeholder.setWordWrap(True)
        self.dm_container_layout.addWidget(self.dm_placeholder)
        self.dm_container_layout.addStretch()
        
        self.dm_scroll.setWidget(self.dm_container)
        dm_layout.addWidget(self.dm_scroll, 1)
        
        self.dm_scene_rows = {}
        
        from PyQt6.QtCore import QTimer
        self.dm_refresh_timer = QTimer(self)
        self.dm_refresh_timer.timeout.connect(self._refresh_download_monitor)
        self.dm_refresh_timer.start(3000)
        
        layout.addWidget(dm_frame, 3)
        return sidebar
    
    def _build_main_area(self):
        area = QFrame()
        area.setObjectName("mainArea")
        
        layout = QVBoxLayout(area)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        # Stats bar
        stats_h = QHBoxLayout()
        stats_h.setSpacing(12)
        
        self.stat_scene = StatBox("-", "SCENE HIỆN TẠI", STAT_COLOR_BLUE)
        stats_h.addWidget(self.stat_scene)
        self.stat_total = StatBox(0, "TỔNG MEDIA SCENE", STAT_COLOR_PURPLE)
        stats_h.addWidget(self.stat_total)
        self.stat_selected_scene = StatBox(0, "ĐÃ CHỌN SCENE NÀY", STAT_COLOR_RED)
        stats_h.addWidget(self.stat_selected_scene)
        self.stat_selected_total = StatBox(0, "TỔNG TOÀN DỰ ÁN", STAT_COLOR_GREEN)
        stats_h.addWidget(self.stat_selected_total)
        
        layout.addLayout(stats_h)
        
        # Filter + action bar
        action_h = QHBoxLayout()
        action_h.setSpacing(8)
        
        self.filter_buttons = {}
        for fkey, label in [("all", "Tất Cả"), ("photos", "🖼️ Ảnh"), ("videos", "🎬 Video")]:
            btn = QPushButton(label)
            btn.setFixedHeight(34)
            btn.setMinimumWidth(80)
            btn.setObjectName("filterActive" if fkey == "all" else "filterInactive")
            btn.clicked.connect(lambda checked, k=fkey: self._set_filter(k))
            action_h.addWidget(btn)
            self.filter_buttons[fkey] = btn
        
        action_h.addStretch()

        self.random_count_spin = QSpinBox()
        self.random_count_spin.setRange(1, 999)
        self.random_count_spin.setValue(1)
        self.random_count_spin.setFixedHeight(34)
        self.random_count_spin.setMinimumWidth(65)
        self.random_count_spin.setToolTip("Số media muốn chọn ngẫu nhiên trong scene")
        action_h.addWidget(QLabel("SL:"))
        action_h.addWidget(self.random_count_spin)

        btn_random_select = QPushButton("🎲 Chọn random")
        btn_random_select.setObjectName("purpleBtn")
        btn_random_select.setFixedHeight(34)
        btn_random_select.setToolTip("Chọn ngẫu nhiên media trong scene hiện tại")
        btn_random_select.clicked.connect(self._select_random_scene)
        action_h.addWidget(btn_random_select)
        
        btn_retry = QPushButton("⟳ Retry failed")
        btn_retry.setFixedHeight(34)
        btn_retry.setToolTip("Tải lại các thumbnails bị lỗi")
        btn_retry.setStyleSheet("""
            QPushButton {
                background-color: #131926;
                color: #fbbf24;
                border: 1px solid #f59e0b;
                border-radius: 8px;
                padding: 0 12px;
                font-weight: 700;
            }
            QPushButton:hover {
                background-color: #f59e0b;
                color: #ffffff;
            }
        """)
        btn_retry.clicked.connect(self._retry_failed_thumbnails)
        action_h.addWidget(btn_retry)
        
        btn_select_all = QPushButton("✓ Chọn tất cả")
        btn_select_all.setObjectName("purpleBtn")
        btn_select_all.setFixedHeight(34)
        btn_select_all.clicked.connect(self._select_all_scene)
        action_h.addWidget(btn_select_all)
        
        btn_clear = QPushButton("❌ Xóa chọn")
        btn_clear.setObjectName("dangerBtn")
        btn_clear.setFixedHeight(34)
        btn_clear.clicked.connect(self._clear_scene_selection)
        action_h.addWidget(btn_clear)
        
        btn_download = QPushButton("💾 Tải Đã Chọn")
        btn_download.setObjectName("primaryBtn")
        btn_download.setFixedHeight(34)
        btn_download.setStyleSheet("""
            QPushButton#primaryBtn {
                padding: 0 16px;
                font-size: 12px;
                font-weight: 800;
            }
        """)
        btn_download.clicked.connect(self._start_download)
        action_h.addWidget(btn_download)
        
        layout.addLayout(action_h)
        
        # Grid container
        self.grid_scroll = QScrollArea()
        self.grid_scroll.setWidgetResizable(True)
        self.grid_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.grid_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.grid_scroll.setStyleSheet("""
            QScrollArea {
                background-color: transparent;
                border: none;
            }
            QScrollBar:vertical {
                background-color: #161b22;
                width: 10px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background-color: #30363d;
                border-radius: 5px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #484f58;
            }
        """)
        
        self.grid_container = QWidget()
        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_layout.setSpacing(10)
        self.grid_layout.setContentsMargins(0, 0, 0, 0)
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        
        self.grid_scroll.setWidget(self.grid_container)
        layout.addWidget(self.grid_scroll, 1)
        
        # Placeholder
        self.placeholder_label = QLabel("👈 Chọn scene từ sidebar trái\nhoặc click 'SEARCH TẤT CẢ' để bắt đầu")
        self.placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.placeholder_label.setStyleSheet("color: #484f58; font-size: 14px; padding: 100px;")
        self.grid_layout.addWidget(self.placeholder_label, 0, 0, GRID_ROWS, GRID_COLS)
        
        # Pagination bar
        pag_h = QHBoxLayout()
        
        self.prev_btn = QPushButton("◀ Trang trước")
        self.prev_btn.setEnabled(False)
        self.prev_btn.clicked.connect(self._prev_page)
        pag_h.addWidget(self.prev_btn)
        
        self.page_label = QLabel("Trang 0/0")
        self.page_label.setStyleSheet("color: #e6edf3; font-size: 13px; font-weight: 600;")
        self.page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pag_h.addWidget(self.page_label, 1)
        
        self.next_btn = QPushButton("Trang sau ▶")
        self.next_btn.setEnabled(False)
        self.next_btn.clicked.connect(self._next_page)
        pag_h.addWidget(self.next_btn)
        
        layout.addLayout(pag_h)
        
        return area
    
    def _build_video_cut_tab(self):
        tab = QFrame()
        tab.setObjectName("mainArea")
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)

        title = QLabel("✂️ Cắt/Ghép random tất cả folder cảnh")
        title.setStyleSheet("color: #e6edf3; font-size: 18px; font-weight: 700;")
        layout.addWidget(title)

        hint = QLabel("Chọn folder tổng chứa các folder cảnh 1, 2, 3... Tool sẽ chạy lần lượt từng folder. Nếu chọn trực tiếp folder cảnh thì chỉ xử lý folder đó.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #8b949e; font-size: 12px;")
        layout.addWidget(hint)

        folder_h = QHBoxLayout()
        self.cut_folder_input = QLineEdit()
        self.cut_folder_input.setPlaceholderText("Chọn folder tổng hoặc folder cảnh, ví dụ: E:\\...\\Download Stock Output")
        folder_h.addWidget(self.cut_folder_input, 1)
        btn_browse = QPushButton("📁 Chọn folder tổng/cảnh")
        btn_browse.clicked.connect(self._browse_cut_folder)
        folder_h.addWidget(btn_browse)
        layout.addLayout(folder_h)

        opts_h = QHBoxLayout()
        opts_h.addWidget(QLabel("Cắt mỗi (giây):"))
        self.cut_seconds_spin = QDoubleSpinBox()
        self.cut_seconds_spin.setRange(0.2, 60.0)
        self.cut_seconds_spin.setSingleStep(0.5)
        self.cut_seconds_spin.setValue(1.0)
        self.cut_seconds_spin.setDecimals(1)
        opts_h.addWidget(self.cut_seconds_spin)

        opts_h.addWidget(QLabel("Số final:"))
        self.final_count_spin = QSpinBox()
        self.final_count_spin.setRange(1, 50)
        self.final_count_spin.setValue(1)
        opts_h.addWidget(self.final_count_spin)

        opts_h.addWidget(QLabel("Max clip/final (0 = dùng hết):"))
        self.max_clips_spin = QSpinBox()
        self.max_clips_spin.setRange(0, 9999)
        self.max_clips_spin.setValue(0)
        opts_h.addWidget(self.max_clips_spin)
        opts_h.addStretch()
        layout.addLayout(opts_h)

        btn_h = QHBoxLayout()
        self.btn_start_cut_merge = QPushButton("🚀 Cắt + ghép random")
        self.btn_start_cut_merge.setObjectName("primaryBtn")
        self.btn_start_cut_merge.setFixedHeight(34)
        self.btn_start_cut_merge.clicked.connect(self._start_cut_merge)
        btn_h.addWidget(self.btn_start_cut_merge)

        self.btn_stop_cut_merge = QPushButton("⏹ Dừng")
        self.btn_stop_cut_merge.setObjectName("dangerBtn")
        self.btn_stop_cut_merge.setFixedHeight(34)
        self.btn_stop_cut_merge.setEnabled(False)
        self.btn_stop_cut_merge.clicked.connect(self._stop_cut_merge)
        btn_h.addWidget(self.btn_stop_cut_merge)
        btn_h.addStretch()
        layout.addLayout(btn_h)

        self.cut_log = QPlainTextEdit()
        self.cut_log.setReadOnly(True)
        self.cut_log.setPlaceholderText("Log xử lý sẽ hiện ở đây...")
        layout.addWidget(self.cut_log, 1)
        return tab

    def _browse_cut_folder(self):
        start_dir = self.config.get("output_dir") or str(Path.home())
        path = QFileDialog.getExistingDirectory(self, "Chọn folder tổng hoặc folder cảnh", start_dir)
        if path:
            self.cut_folder_input.setText(path)

    def _start_cut_merge(self):
        folder = self.cut_folder_input.text().strip()
        if not folder:
            QMessageBox.information(self, "Thiếu folder", "Chọn folder tổng hoặc folder cảnh trước nhé")
            return
        if hasattr(self, "cut_merge_worker") and self.cut_merge_worker and self.cut_merge_worker.isRunning():
            QMessageBox.information(self, "Đang chạy", "Đợi job hiện tại xong hoặc bấm Dừng")
            return

        self.cut_log.clear()
        self.btn_start_cut_merge.setEnabled(False)
        self.btn_stop_cut_merge.setEnabled(True)
        self.cut_merge_worker = VideoCutMergeWorker(
            folder,
            self.cut_seconds_spin.value(),
            self.final_count_spin.value(),
            self.max_clips_spin.value(),
        )
        self.cut_merge_worker.progress.connect(self._on_cut_merge_log)
        self.cut_merge_worker.finished_signal.connect(self._on_cut_merge_finished)
        self.cut_merge_worker.start()

    def _stop_cut_merge(self):
        if hasattr(self, "cut_merge_worker") and self.cut_merge_worker:
            self.cut_merge_worker.stop()
            self._on_cut_merge_log("Đang yêu cầu dừng...")

    def _on_cut_merge_log(self, message):
        self.cut_log.appendPlainText(message)
        self.status_bar.showMessage(message[:160], 5000)

    def _on_cut_merge_finished(self, ok, message):
        self.btn_start_cut_merge.setEnabled(True)
        self.btn_stop_cut_merge.setEnabled(False)
        self._on_cut_merge_log(("✅ " if ok else "❌ ") + message)
        if getattr(self, "_workflow_waiting_for", None) == "Cut/Mix video":
            self._workflow_waiting_for = None
            if hasattr(self, "workflow_log"):
                self.workflow_log.appendPlainText("Cut/Mix video: xong, chạy node tiếp theo")
            self._workflow_continue()

    def _tool_root(self):
        roots = []
        try:
            roots.append(Path(sys.executable).resolve().parent)
        except Exception:
            pass
        here = Path(__file__).resolve()
        roots.extend([here.parent, here.parent.parent, here.parent.parent.parent])

        candidates = []
        for root in roots:
            for base in [root, *root.parents]:
                candidates.append(base)
                candidates.append(base.parent)
        seen = set()
        for base in candidates:
            key = str(base).lower()
            if key in seen:
                continue
            seen.add(key)
            if (base / "Voice TXT Tool" / "server.mjs").exists():
                return base
        return here.parent.parent

    def _browse_line_path(self, line_edit, folder=False, caption="Chọn file"):
        if folder:
            path = QFileDialog.getExistingDirectory(self, caption, str(Path.home()))
        else:
            path, _ = QFileDialog.getOpenFileName(self, caption, "", "All Files (*.*)")
        if path:
            line_edit.setText(path)

    def _build_voice_tab(self):
        tab = QFrame(); tab.setObjectName("mainArea")
        root = QHBoxLayout(tab); root.setContentsMargins(20,20,20,20); root.setSpacing(14)

        left = QFrame(); left.setObjectName("toolCard")
        left_l = QVBoxLayout(left); left_l.setSpacing(10)
        title = QLabel("Voice TXT Tool - tích hợp đầy đủ"); title.setObjectName("heroTitle"); left_l.addWidget(title)
        hint = QLabel("Đủ 3 workflow như bản ngoài: tạo voice TXT, ghép SRT kịch bản, JSON 20 phần -> Voice. Backend chạy ẩn, log nằm trong app chính.")
        hint.setObjectName("mutedText"); hint.setWordWrap(True); left_l.addWidget(hint)

        self.voice_tabs = QTabWidget(); left_l.addWidget(self.voice_tabs, 1)

        # Tab 1: TXT -> voice
        txt_tab = QWidget(); txt_l = QVBoxLayout(txt_tab); txt_l.setSpacing(10)
        txt_grid = QGridLayout(); txt_grid.setHorizontalSpacing(10); txt_grid.setVerticalSpacing(8)
        self.voice_txt_dir = QLineEdit(); self.voice_txt_dir.setPlaceholderText("Thư mục chứa TXT, ví dụ ...\\ketqua")
        self.voice_input_path = QLineEdit(); self.voice_input_path.setPlaceholderText("Hoặc chọn 1 file TXT")
        self.voice_output_dir = QLineEdit(str(self._tool_root() / "Voice TXT Tool" / "voices"))
        self.voice_provider_combo = QComboBox(); self.voice_provider_combo.addItems(["11labs", "larvoice", "vivibe", "genmax", "ai84", "vbee", "default"])
        self.voice_speed_spin = QDoubleSpinBox(); self.voice_speed_spin.setRange(0.5, 2.0); self.voice_speed_spin.setSingleStep(0.1); self.voice_speed_spin.setValue(1.0)
        self.voice_id_input = QLineEdit(); self.voice_id_input.setPlaceholderText("Voice ID provider ngoài LarVoice")
        self.larvoice_id_input = QLineEdit("1")
        self.provider_api_keys = QPlainTextEdit(); self.provider_api_keys.setPlaceholderText("API key riêng cho provider/model đang chọn, mỗi dòng một key")
        self.provider_api_keys.setMaximumHeight(90)
        txt_grid.addWidget(QLabel("Thư mục TXT:"),0,0); txt_grid.addWidget(self.voice_txt_dir,0,1); b=QPushButton("Chọn folder"); b.clicked.connect(lambda: self._browse_line_path(self.voice_txt_dir, True)); txt_grid.addWidget(b,0,2)
        txt_grid.addWidget(QLabel("File TXT:"),1,0); txt_grid.addWidget(self.voice_input_path,1,1); b=QPushButton("Chọn file"); b.clicked.connect(lambda: self._browse_line_path(self.voice_input_path)); txt_grid.addWidget(b,1,2)
        txt_grid.addWidget(QLabel("Output audio:"),2,0); txt_grid.addWidget(self.voice_output_dir,2,1); b=QPushButton("Chọn folder"); b.clicked.connect(lambda: self._browse_line_path(self.voice_output_dir, True)); txt_grid.addWidget(b,2,2)
        txt_grid.addWidget(QLabel("Provider:"),3,0); txt_grid.addWidget(self.voice_provider_combo,3,1); txt_grid.addWidget(QLabel("Speed:"),3,2); txt_grid.addWidget(self.voice_speed_spin,3,3)
        txt_grid.addWidget(QLabel("Voice ID:"),4,0); txt_grid.addWidget(self.voice_id_input,4,1); txt_grid.addWidget(QLabel("LarVoice ID:"),4,2); txt_grid.addWidget(self.larvoice_id_input,4,3)
        txt_grid.addWidget(QLabel("API keys:"),5,0); txt_grid.addWidget(self.provider_api_keys,5,1,1,3)
        txt_l.addLayout(txt_grid)
        row=QHBoxLayout()
        for text, fn in [("Quét thư mục TXT", self._voice_scan_txt), ("Tạo voice", self._start_native_voice), ("Xóa danh sách", self._voice_clear_files), ("Lưu API + Voice ID", self._voice_save_provider_config)]:
            btn=QPushButton(text); btn.setObjectName("primaryBtn" if text=="Tạo voice" else ""); btn.clicked.connect(fn); row.addWidget(btn)
        row.addStretch(); txt_l.addLayout(row)
        self.voice_files_list = QListWidget(); txt_l.addWidget(self.voice_files_list, 1)
        self.voice_tabs.addTab(txt_tab, "Tạo voice TXT")

        # Tab 2: merge SRT
        srt_tab = QWidget(); srt_l = QVBoxLayout(srt_tab); srt_l.setSpacing(10)
        srt_grid=QGridLayout(); self.srt_dir_input=QLineEdit(str(self._tool_root()/"Voice TXT Tool"/"voices")); self.srt_output_input=QLineEdit(str(self._tool_root()/"Voice TXT Tool"/"kich_ban_hoan_chinh.srt")); self.srt_gap_spin=QSpinBox(); self.srt_gap_spin.setRange(0,5000); self.srt_gap_spin.setSingleStep(50); self.srt_gap_spin.setValue(250)
        srt_grid.addWidget(QLabel("Thư mục SRT:"),0,0); srt_grid.addWidget(self.srt_dir_input,0,1); b=QPushButton("Chọn folder"); b.clicked.connect(lambda: self._browse_line_path(self.srt_dir_input, True)); srt_grid.addWidget(b,0,2)
        srt_grid.addWidget(QLabel("File SRT xuất:"),1,0); srt_grid.addWidget(self.srt_output_input,1,1); b=QPushButton("Chọn file"); b.clicked.connect(lambda: self._browse_line_path(self.srt_output_input)); srt_grid.addWidget(b,1,2)
        srt_grid.addWidget(QLabel("Khoảng nghỉ ms:"),2,0); srt_grid.addWidget(self.srt_gap_spin,2,1)
        srt_l.addLayout(srt_grid)
        row=QHBoxLayout(); scan=QPushButton("Quét thư mục SRT"); scan.clicked.connect(self._voice_scan_srt); row.addWidget(scan); merge=QPushButton("Ghép SRT"); merge.setObjectName("primaryBtn"); merge.clicked.connect(self._merge_srt_native); row.addWidget(merge); clear=QPushButton("Xóa danh sách SRT"); clear.clicked.connect(lambda: self.srt_files_list.clear()); row.addWidget(clear); row.addStretch(); srt_l.addLayout(row)
        self.srt_files_list=QListWidget(); srt_l.addWidget(self.srt_files_list,1)
        self.voice_tabs.addTab(srt_tab, "Ghép SRT kịch bản")

        # Tab 3: JSON 20 parts -> voice
        json_tab = QWidget(); json_l=QVBoxLayout(json_tab); json_l.setSpacing(10)
        jgrid=QGridLayout(); self.json_script_input=QLineEdit(); self.json_parts_input=QLineEdit(); self.json_output_dir=QLineEdit(str(self._tool_root()/"Voice TXT Tool"/"voices"/"json_20_parts"))
        jgrid.addWidget(QLabel("File kịch bản TXT gốc:"),0,0); jgrid.addWidget(self.json_script_input,0,1); b=QPushButton("Chọn"); b.clicked.connect(lambda: self._browse_line_path(self.json_script_input)); jgrid.addWidget(b,0,2)
        jgrid.addWidget(QLabel("File JSON chia 20 phần:"),1,0); jgrid.addWidget(self.json_parts_input,1,1); b=QPushButton("Chọn"); b.clicked.connect(lambda: self._browse_line_path(self.json_parts_input)); jgrid.addWidget(b,1,2)
        jgrid.addWidget(QLabel("Output voice 20 phần:"),2,0); jgrid.addWidget(self.json_output_dir,2,1); b=QPushButton("Chọn folder"); b.clicked.connect(lambda: self._browse_line_path(self.json_output_dir, True)); jgrid.addWidget(b,2,2)
        json_l.addLayout(jgrid)
        info=QLabel("Đọc mảng parts trong JSON, lấy dialogue/text từng phần, lưu TXT vào parts_txt rồi tạo MP3 theo thứ tự 01 -> 20."); info.setObjectName("mutedText"); info.setWordWrap(True); json_l.addWidget(info)
        row=QHBoxLayout(); run=QPushButton("Cắt JSON + tạo voice"); run.setObjectName("primaryBtn"); run.clicked.connect(self._start_json_parts_voice_native); row.addWidget(run); row.addStretch(); json_l.addLayout(row)
        self.json_parts_list=QListWidget(); json_l.addWidget(self.json_parts_list,1)
        self.voice_tabs.addTab(json_tab, "JSON 20 phần -> Voice")

        root.addWidget(left, 3)
        right = QFrame(); right.setObjectName("toolCard"); right_l=QVBoxLayout(right)
        self.voice_done_label=QLabel("0"); self.voice_done_label.setStyleSheet("font-size:28px;color:#4ec9b0;font-weight:800;")
        self.voice_total_label=QLabel("0 file"); self.voice_total_label.setObjectName("mutedText")
        right_l.addWidget(QLabel("Tiến độ")); right_l.addWidget(self.voice_done_label); right_l.addWidget(self.voice_total_label)
        self.voice_log = QPlainTextEdit(); self.voice_log.setReadOnly(True); self.voice_log.setPlaceholderText("Log tạo voice / merge SRT / JSON parts..."); right_l.addWidget(self.voice_log,1)
        root.addWidget(right, 1)
        return tab

    def _voice_scan_txt(self):
        self.voice_files_list.clear()
        folder=Path(self.voice_txt_dir.text().strip())
        files=[]
        if folder.exists(): files=sorted(folder.glob("*.txt"), key=lambda x: x.name.lower())
        single=Path(self.voice_input_path.text().strip()) if self.voice_input_path.text().strip() else None
        if single and single.exists() and single.suffix.lower()==".txt": files.append(single)
        seen=[]
        for f in files:
            if f not in seen:
                seen.append(f); self.voice_files_list.addItem(str(f))
        self.voice_total_label.setText(f"{len(seen)} file")
        self.voice_log.appendPlainText(f"Đã quét TXT: {len(seen)} file")

    def _voice_scan_srt(self):
        self.srt_files_list.clear()
        folder=Path(self.srt_dir_input.text().strip())
        files=sorted(folder.glob("*.srt"), key=lambda x: x.name.lower()) if folder.exists() else []
        for f in files: self.srt_files_list.addItem(str(f))
        self.voice_log.appendPlainText(f"Đã quét SRT: {len(files)} file")

    def _voice_clear_files(self):
        self.voice_files_list.clear(); self.voice_done_label.setText("0"); self.voice_total_label.setText("0 file")

    def _voice_save_provider_config(self):
        tool=self._tool_root()/"Voice TXT Tool"/"tool-config.json"
        try:
            cfg=json.loads(tool.read_text(encoding="utf-8")) if tool.exists() else {"providers":{}}
            provider=self.voice_provider_combo.currentText(); cfg["provider"]=provider; cfg.setdefault("providers",{})[provider]={"apiKeys":self.provider_api_keys.toPlainText(),"voiceId":self.voice_id_input.text().strip() or self.larvoice_id_input.text().strip()}
            tool.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
            self.voice_log.appendPlainText(f"Đã lưu provider config: {provider}")
        except Exception as e:
            QMessageBox.warning(self,"Lỗi lưu config",str(e))

    def _start_json_parts_voice_native(self):
        parts_path=Path(self.json_parts_input.text().strip()); out_dir=Path(self.json_output_dir.text().strip())
        if not parts_path.exists(): QMessageBox.information(self,"Thiếu JSON","Chọn file JSON chia 20 phần trước nhé"); return
        out_txt=out_dir/"parts_txt"; out_txt.mkdir(parents=True, exist_ok=True)
        data=json.loads(parts_path.read_text(encoding="utf-8", errors="ignore"))
        parts=data.get("parts") or data.get("scenes") or data.get("segments") or []
        self.voice_files_list.clear(); self.json_parts_list.clear()
        for i,part in enumerate(parts,1):
            text=str(part.get("dialogue") or part.get("text") or part.get("content") or part.get("voice") or "").strip()
            if not text: continue
            f=out_txt/f"{i:02d}_part.txt"; f.write_text(text, encoding="utf-8")
            self.voice_files_list.addItem(str(f)); self.json_parts_list.addItem(f"{i:02d}: {text[:90]}")
        self.voice_output_dir.setText(str(out_dir)); self.voice_tabs.setCurrentIndex(0)
        self.voice_log.appendPlainText(f"Đã tạo {self.voice_files_list.count()} TXT từ JSON parts. Bắt đầu tạo voice...")
        self._start_native_voice()

    def _build_scene_voice_tab(self):
        tab = QFrame(); tab.setObjectName("mainArea")
        layout = QVBoxLayout(tab); layout.setContentsMargins(24,24,24,24); layout.setSpacing(12)
        title = QLabel("Khớp voice theo scene - native trong app"); title.setObjectName("heroTitle"); layout.addWidget(title)
        hint = QLabel("Port UI từ Scene Voice Cutter: chọn JSON, folder video cảnh, folder/output voice rồi chạy ffmpeg trong app chính.")
        hint.setObjectName("mutedText"); hint.setWordWrap(True); layout.addWidget(hint)
        grid=QGridLayout(); self.svc_json=QLineEdit(); self.svc_root=QLineEdit(); self.svc_voice=QLineEdit(); self.svc_full_voice=QLineEdit(); self.svc_out=QLineEdit()
        rows=[("JSON scenes (không bắt buộc)",self.svc_json,False),("Folder video cảnh",self.svc_root,True),("SRT/TXT hoặc folder voice lẻ",self.svc_voice,False),("Full voice MP3/WAV (nếu dùng SRT)",self.svc_full_voice,False),("Output folder",self.svc_out,True)]
        for r,(lab,edit,isdir) in enumerate(rows):
            grid.addWidget(QLabel(lab+":"),r,0); grid.addWidget(edit,r,1); btn=QPushButton("Chọn"); btn.clicked.connect(lambda _, e=edit, d=isdir: self._browse_line_path(e,d)); grid.addWidget(btn,r,2)
        layout.addLayout(grid)
        opts=QHBoxLayout(); self.svc_random=QCheckBox("Random điểm bắt đầu nếu video dài hơn voice"); self.svc_random.setChecked(True); self.svc_concat=QCheckBox("Ghép full_video.mp4"); opts.addWidget(self.svc_random); opts.addWidget(self.svc_concat); opts.addWidget(QLabel("Cắt clip con mỗi:")); self.svc_chunk_seconds=QDoubleSpinBox(); self.svc_chunk_seconds.setRange(0.0, 120.0); self.svc_chunk_seconds.setSingleStep(1.0); self.svc_chunk_seconds.setValue(0.0); self.svc_chunk_seconds.setSuffix(" giây"); opts.addWidget(self.svc_chunk_seconds); opts.addStretch(); layout.addLayout(opts)
        row=QHBoxLayout(); run=QPushButton("Bắt đầu khớp voice"); run.setObjectName("primaryBtn"); run.clicked.connect(self._start_scene_voice_native); row.addWidget(run); row.addStretch(); layout.addLayout(row)
        self.svc_log=QPlainTextEdit(); self.svc_log.setReadOnly(True); layout.addWidget(self.svc_log,1)
        return tab

    def _build_auto_tab(self):
        tab = QFrame(); tab.setObjectName("mainArea")
        layout = QVBoxLayout(tab); layout.setContentsMargins(24,24,24,24); layout.setSpacing(12)
        title = QLabel("Auto Mode"); title.setObjectName("heroTitle"); layout.addWidget(title)
        hint = QLabel("Tự search, tự random chọn media theo loại, tự tải, rồi có thể chạy voice/khớp voice từ tab native.")
        hint.setObjectName("mutedText"); hint.setWordWrap(True); layout.addWidget(hint)
        row = QHBoxLayout(); self.auto_media_combo = QComboBox(); self.auto_media_combo.addItems(["Video + ảnh", "Chỉ video", "Chỉ ảnh"]); row.addWidget(QLabel("Định dạng:")); row.addWidget(self.auto_media_combo)
        self.auto_pick_spin = QSpinBox(); self.auto_pick_spin.setRange(1,20); self.auto_pick_spin.setValue(2); row.addWidget(QLabel("Random/scene:")); row.addWidget(self.auto_pick_spin)
        self.auto_voice_check = QCheckBox("Sau tải chuyển sang tab Voice"); row.addWidget(self.auto_voice_check); row.addStretch(); layout.addLayout(row)
        btn = QPushButton("Chạy auto pipeline"); btn.setObjectName("primaryBtn"); btn.setFixedHeight(40); btn.clicked.connect(self._run_auto_mode); layout.addWidget(btn)
        self.auto_log = QPlainTextEdit(); self.auto_log.setReadOnly(True); layout.addWidget(self.auto_log,1)
        return tab

    def _build_workflow_tab(self):
        tab = QFrame(); tab.setObjectName("mainArea")
        layout = QVBoxLayout(tab); layout.setContentsMargins(20,20,20,20); layout.setSpacing(10)
        title = QLabel("Workflow Canvas"); title.setObjectName("heroTitle"); layout.addWidget(title)
        hint = QLabel("Chọn block rồi Add node. Double-click node để cài JSON config riêng; kéo node để đổi thứ tự; app tự nối dây trái → phải và lưu/load preset kèm config.")
        hint.setObjectName("mutedText"); hint.setWordWrap(True); layout.addWidget(hint)
        top=QHBoxLayout(); self.workflow_block_combo=QComboBox(); self.workflow_block_combo.addItems(["Load JSON", "Search stock", "Random select", "Download selected", "Cut/Mix video", "Create voice", "Scene voice match"]); top.addWidget(self.workflow_block_combo)
        for text, fn in [("Add node", self._workflow_canvas_add), ("Run workflow", self._workflow_run), ("Save preset", self._workflow_save), ("Load preset", self._workflow_load), ("Clear", self._workflow_clear)]:
            btn=QPushButton(text); btn.setObjectName("primaryBtn" if text=="Run workflow" else ""); btn.clicked.connect(fn); top.addWidget(btn)
        top.addStretch(); layout.addLayout(top)
        self.workflow_canvas = WorkflowCanvas(self); layout.addWidget(self.workflow_canvas,1)
        self.workflow_log = QPlainTextEdit(); self.workflow_log.setReadOnly(True); self.workflow_log.setMaximumHeight(110); layout.addWidget(self.workflow_log)
        return tab

    def _run_node_tool(self, args, cwd, log_widget):
        try:
            proc = subprocess.Popen(args, cwd=str(cwd), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", creationflags=(subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0))
            out, _ = proc.communicate()
            log_widget.appendPlainText(out[-6000:] if out else f"Done: {' '.join(args)}")
            return proc.returncode == 0
        except Exception as e:
            log_widget.appendPlainText(f"Lỗi: {e}")
            return False

    def _start_native_voice(self):
        if hasattr(self, "voice_files_list") and self.voice_files_list.count() == 0:
            self._voice_scan_txt()
        files=[]
        if hasattr(self, "voice_files_list"):
            files=[self.voice_files_list.item(i).text() for i in range(self.voice_files_list.count())]
        elif self.voice_input_path.text().strip():
            files=[self.voice_input_path.text().strip()]
        out=self.voice_output_dir.text().strip()
        if not files or not out:
            QMessageBox.information(self,"Thiếu input","Chọn/quét file TXT và output folder trước nhé"); return
        self._voice_save_provider_config()
        tool=self._tool_root()/"Voice TXT Tool"; Path(out).mkdir(parents=True, exist_ok=True)
        ok=0
        self.voice_done_label.setText("0") if hasattr(self,"voice_done_label") else None
        self.voice_total_label.setText(f"{len(files)} file") if hasattr(self,"voice_total_label") else None
        for idx, inp in enumerate(files, 1):
            self.voice_log.appendPlainText(f"[{idx}/{len(files)}] Tạo voice: {Path(inp).name}")
            done=self._run_node_tool(["node","server.mjs","--cli",inp,out,self.voice_provider_combo.currentText(),str(self.voice_speed_spin.value())], tool, self.voice_log)
            ok += 1 if done else 0
            if hasattr(self,"voice_done_label"): self.voice_done_label.setText(str(idx))
            QApplication.processEvents()
        self.voice_log.appendPlainText(f"Xong voice: {ok}/{len(files)} file OK")

    def _merge_srt_native(self):
        files=[]
        if hasattr(self,"srt_files_list") and self.srt_files_list.count():
            files=[Path(self.srt_files_list.item(i).text()) for i in range(self.srt_files_list.count())]
        else:
            folder=Path(self.srt_dir_input.text().strip() if hasattr(self,"srt_dir_input") else self.voice_output_dir.text().strip())
            files=sorted(folder.glob("*.srt"), key=lambda x: x.name.lower()) if folder.exists() else []
        if not files:
            QMessageBox.information(self,"Không có SRT","Chọn/quét folder có file .srt trước nhé"); return
        out=Path(self.srt_output_input.text().strip()) if hasattr(self,"srt_output_input") and self.srt_output_input.text().strip() else Path(self.voice_output_dir.text().strip())/"kich_ban_hoan_chinh.srt"
        gap=getattr(self,"srt_gap_spin",None).value() if hasattr(self,"srt_gap_spin") else 250
        blocks=[]; offset_ms=0
        for f in files:
            raw=f.read_text(encoding="utf-8", errors="ignore").replace("\r\n","\n").replace("\r","\n")
            parsed=[]
            for block in re.split(r"\n{2,}", raw.strip()):
                lines=block.strip().split("\n")
                if lines and lines[0].strip().isdigit(): lines=lines[1:]
                if not lines or "-->" not in lines[0]: continue
                a,b=[x.strip().split()[0] for x in lines[0].split("-->")]
                start_ms=int(srt_time_to_seconds(a)*1000); end_ms=int(srt_time_to_seconds(b)*1000)
                parsed.append((start_ms,end_ms,"\n".join(lines[1:]).strip()))
            if not parsed: continue
            base=parsed[0][0]; last=0
            for st,en,txt in parsed:
                ns=offset_ms+(st-base); ne=offset_ms+(en-base); blocks.append((ns,ne,txt)); last=max(last,ne)
            offset_ms=last+gap
        def fmt(ms):
            h=ms//3600000; ms%=3600000; m=ms//60000; ms%=60000; sec=ms//1000; ms%=1000
            return f"{h:02d}:{m:02d}:{sec:02d},{ms:03d}"
        body="\n\n".join(f"{i}\n{fmt(st)} --> {fmt(en)}\n{txt}" for i,(st,en,txt) in enumerate(blocks,1))+"\n"
        out.parent.mkdir(parents=True, exist_ok=True); out.write_text(body, encoding="utf-8")
        self.voice_log.appendPlainText(f"Đã merge {len(files)} SRT / {len(blocks)} blocks -> {out}")

    def _start_scene_voice_native(self):
        jsonp=self.svc_json.text().strip(); root=self.svc_root.text().strip(); voice=self.svc_voice.text().strip(); full_voice=self.svc_full_voice.text().strip() if hasattr(self, "svc_full_voice") else ""; out=self.svc_out.text().strip(); chunk_seconds=self.svc_chunk_seconds.value() if hasattr(self, "svc_chunk_seconds") else 0.0
        if not root or not out:
            QMessageBox.information(self,"Thiếu dữ liệu","Cần folder video cảnh và output folder"); return
        script=self._tool_root()/"Scene Voice Cutter"/"scene_voice_cutter.py"
        if not script.exists():
            self.svc_log.appendPlainText(f"Lỗi: không tìm thấy {script}")
            return
        if hasattr(self, "scene_voice_worker") and self.scene_voice_worker and self.scene_voice_worker.isRunning():
            QMessageBox.information(self, "Đang chạy", "Đợi job khớp voice hiện tại xong nhé")
            return
        args=[sys.executable if not getattr(sys, "frozen", False) else "python",str(script),"--cli",jsonp,root,voice,out,"1" if self.svc_random.isChecked() else "0","1" if self.svc_concat.isChecked() else "0",full_voice,f"{chunk_seconds:.3f}"]
        self.svc_log.appendPlainText("Đang chạy khớp voice bằng ffmpeg...")
        self.scene_voice_worker = NodeToolWorker(args, script.parent)
        self.scene_voice_worker.progress.connect(lambda msg: self.svc_log.appendPlainText(msg) if msg else None)
        self.scene_voice_worker.finished_signal.connect(self._on_scene_voice_finished)
        self.scene_voice_worker.start()

    def _on_scene_voice_finished(self, ok, message):
        self.svc_log.appendPlainText(("✅ " if ok else "❌ ") + (message[-6000:] if message else "Done"))
        if getattr(self, "_workflow_waiting_for", None) == "Scene voice match":
            self._workflow_waiting_for = None
            if hasattr(self, "workflow_log"):
                self.workflow_log.appendPlainText("Scene voice match: xong, chạy node tiếp theo")
            self._workflow_continue()

    def _workflow_canvas_add(self):
        self.workflow_canvas.add_node(self.workflow_block_combo.currentText())

    def _workflow_clear(self):
        self.workflow_canvas.clear(); self.workflow_log.clear()

    def _workflow_save(self):
        path,_=QFileDialog.getSaveFileName(self,"Lưu workflow preset","workflow_preset.json","JSON (*.json)")
        if path:
            Path(path).write_text(json.dumps(self.workflow_canvas.save_payload(), ensure_ascii=False, indent=2), encoding="utf-8")
            self.workflow_log.appendPlainText(f"Saved: {path}")

    def _workflow_load(self):
        path,_=QFileDialog.getOpenFileName(self,"Load workflow preset","","JSON (*.json)")
        if path:
            self.workflow_canvas.load_payload(json.loads(Path(path).read_text(encoding="utf-8")))
            self.workflow_log.appendPlainText(f"Loaded: {path}")

    def _run_auto_mode(self):
        mode = self.auto_media_combo.currentText()
        self.search_videos_check.setChecked("video" in mode.lower() or "Video" in mode)
        self.search_photos_check.setChecked("ảnh" in mode or "Video +" in mode)
        self.random_count_spin.setValue(self.auto_pick_spin.value())
        self.auto_log.appendPlainText("Auto: bắt đầu search stock. Khi search xong app sẽ tự random + tải.")
        self._auto_after_search = True
        self._start_search()

    def _workflow_set_combo(self, combo, value):
        if combo is None or value is None:
            return
        text = str(value)
        idx = combo.findText(text)
        if idx < 0:
            idx = combo.findText(text, Qt.MatchFlag.MatchContains)
        if idx >= 0:
            combo.setCurrentIndex(idx)

    def _workflow_apply_node_config(self, step, config):
        config = config or {}
        if not config:
            return
        self.workflow_log.appendPlainText(f"Config {step}: " + json.dumps(config, ensure_ascii=False))
        if step == "Load JSON" and config.get("json"):
            try:
                raw = Path(str(config.get("json"))).read_text(encoding="utf-8")
                data = json.loads(raw)
                scenes = extract_scenes_from_json(data)
                self._on_json_loaded_from_settings(data, scenes)
            except Exception as e:
                QMessageBox.warning(self, "Load JSON lỗi", str(e))
        if step in ("Search stock", "Random select"):
            mode = config.get("media_mode") or config.get("mode")
            source = config.get("source")
            if step == "Search stock" and source and hasattr(self, "search_source_combo"):
                self._workflow_set_combo(self.search_source_combo, source)
            if hasattr(self, "auto_media_combo"):
                self._workflow_set_combo(self.auto_media_combo, mode)
            if mode and hasattr(self, "search_videos_check") and hasattr(self, "search_photos_check"):
                lower = str(mode).lower()
                self.search_videos_check.setChecked("video" in lower)
                self.search_photos_check.setChecked("ảnh" in str(mode) or "photo" in lower or "+" in str(mode))
            count = config.get("count", config.get("random_per_scene"))
            if count is not None:
                if hasattr(self, "auto_pick_spin"):
                    self.auto_pick_spin.setValue(int(count))
                if hasattr(self, "random_count_spin"):
                    self.random_count_spin.setValue(int(count))
        if step == "Cut/Mix video":
            if hasattr(self, "cut_folder_input") and config.get("folder"):
                self.cut_folder_input.setText(str(config.get("folder")))
            if hasattr(self, "cut_seconds_spin") and config.get("segment_seconds") is not None:
                self.cut_seconds_spin.setValue(float(config.get("segment_seconds")))
            if hasattr(self, "final_count_spin") and config.get("final_count") is not None:
                self.final_count_spin.setValue(int(config.get("final_count")))
            if hasattr(self, "max_clips_spin") and config.get("max_clips") is not None:
                self.max_clips_spin.setValue(int(config.get("max_clips")))
        if step == "Create voice":
            if hasattr(self, "voice_txt_dir") and config.get("txt_dir"):
                self.voice_txt_dir.setText(str(config.get("txt_dir")))
            if hasattr(self, "voice_input_path") and config.get("txt_file"):
                self.voice_input_path.setText(str(config.get("txt_file")))
            if hasattr(self, "json_parts_input") and config.get("json"):
                self.json_parts_input.setText(str(config.get("json")))
            if hasattr(self, "voice_output_dir") and config.get("output_dir"):
                self.voice_output_dir.setText(str(config.get("output_dir")))
            if hasattr(self, "json_output_dir") and config.get("output_dir"):
                self.json_output_dir.setText(str(config.get("output_dir")))
        if step == "Scene voice match":
            if hasattr(self, "svc_random") and config.get("random") is not None:
                self.svc_random.setChecked(bool(config.get("random")))
            if hasattr(self, "svc_concat") and config.get("concat") is not None:
                self.svc_concat.setChecked(bool(config.get("concat")))
            if hasattr(self, "svc_chunk_seconds") and config.get("chunk_seconds") is not None:
                self.svc_chunk_seconds.setValue(float(config.get("chunk_seconds") or 0.0))
            for attr, key in (("svc_json", "json"), ("svc_root", "root"), ("svc_voice", "voice"), ("svc_full_voice", "full_voice"), ("svc_out", "output_dir")):
                if hasattr(self, attr) and config.get(key):
                    getattr(self, attr).setText(str(config.get(key)))

    def _workflow_start_create_voice(self, config):
        config = config or {}
        mode = str(config.get("mode") or "TXT folder/file")
        if "JSON" in mode:
            if not config.get("json"):
                QMessageBox.information(self, "Thiếu JSON", "Node Create voice cần file JSON parts/scenes")
                return
            self._start_json_parts_voice_native()
            return
        if hasattr(self, "voice_files_list"):
            self.voice_files_list.clear()
        if config.get("txt_file") and Path(str(config.get("txt_file"))).exists():
            self.voice_files_list.addItem(str(config.get("txt_file")))
        else:
            self._voice_scan_txt()
        self._start_native_voice()

    def _workflow_run(self):
        nodes = self.workflow_canvas.workflow_nodes() if hasattr(self, "workflow_canvas") else []
        if not nodes:
            QMessageBox.information(self, "Workflow trống", "Add node vào canvas trước nhé"); return
        self._workflow_running_nodes = nodes
        self._workflow_index = 0
        steps = [node.title for node in nodes]
        self.workflow_log.appendPlainText("RUN: " + " -> ".join(steps))
        self._workflow_continue()

    def _workflow_continue(self):
        nodes = getattr(self, "_workflow_running_nodes", [])
        while getattr(self, "_workflow_index", 0) < len(nodes):
            node = nodes[self._workflow_index]
            self._workflow_index += 1
            step = node.title
            self._workflow_apply_node_config(step, getattr(node, "config", {}))
            self.workflow_log.appendPlainText(f"Node: {step}")
            if step == "Load JSON":
                config = getattr(node, "config", {}) or {}
                if config.get("json"):
                    continue
                self._open_settings_dialog(); return
            if step == "Search stock":
                self._workflow_waiting_for = "Search stock"
                self._start_search(); return
            if step == "Random select":
                self._auto_random_all_scenes(); continue
            if step == "Download selected":
                self._workflow_waiting_for = "Download selected"
                self._auto_download_confirmless = True; self._start_download(); return
            if step == "Cut/Mix video":
                self._workflow_waiting_for = "Cut/Mix video"
                self.main_tabs.setCurrentIndex(1)
                self._start_cut_merge(); return
            if step == "Create voice":
                self._workflow_start_create_voice(getattr(node, "config", {}) or {})
                continue
            if step == "Scene voice match":
                self._workflow_waiting_for = "Scene voice match"
                self._start_scene_voice_native(); return
        self.workflow_log.appendPlainText("Workflow: hoàn tất")
        self._workflow_waiting_for = None

    def _auto_random_all_scenes(self):
        count = getattr(self, "auto_pick_spin", None).value() if hasattr(self, "auto_pick_spin") else 2
        self.selected_items = {}
        for scene in self.scenes:
            sid = scene.get("id"); items = list(self.scene_items.get(sid, []))
            if hasattr(self, "auto_media_combo") and self.auto_media_combo.currentText() == "Chỉ video": items = [i for i in items if i.get("type") == "video"]
            if hasattr(self, "auto_media_combo") and self.auto_media_combo.currentText() == "Chỉ ảnh": items = [i for i in items if i.get("type") == "photo"]
            picked = random.sample(items, min(count, len(items))) if items else []
            self.selected_items[sid] = {self._get_item_key(i): i for i in picked}
        self._update_stats(); self._populate_scene_list(); self._save_app_state()

    def _section_header(self, text):
        label = QLabel(text)
        label.setObjectName("sectionHeader")
        return label
    
    # ═════ ACTION HANDLERS (Part 1 stubs - will be expanded in Part 2) ═════
    
    def _browse_output(self):
        """Direct browse - vẫn giữ cho compatibility (settings dialog cũng dùng)"""
        path = QFileDialog.getExistingDirectory(self, "Chọn thư mục lưu")
        if path:
            self.config["output_dir"] = path
            save_config(self.config)
    
    def _refresh_keys_status(self):
        """No-op trong v5.0 (label đã bỏ khỏi sidebar, hiển thị trong Settings dialog)"""
        pass
    
    def _open_settings_dialog(self):
        """Mở dialog Settings - tổng hợp output dir, API keys, JSON input"""
        dialog = SettingsDialog(self.config, parent=self)
        dialog.jsonLoaded.connect(self._on_json_loaded_from_settings)
        dialog.exec()
    
    def _on_json_loaded_from_settings(self, json_data, scenes):
        """Callback khi user load JSON từ Settings dialog"""
        try:
            self.json_data = json_data
            self.scenes = scenes
            self.scene_items = {}
            self.selected_items = {}
            self.current_scene_id = None
            
            # Update UI
            self.json_status_label.setText(f"✓ {len(self.scenes)} scenes")
            self.json_status_label.setStyleSheet("color: #4ec9b0; font-size: 10px; font-weight: 600;")
            
            self._populate_scene_list()
            self._clear_grid()
            
            # Show placeholder
            self._show_empty_placeholder()
            self._update_stats()
            self._save_app_state()
            
            if hasattr(self, 'status_panel'):
                self.status_panel.add_log(f"Loaded JSON: {len(scenes)} scenes", "success")
        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.critical(
                self, "Lỗi load JSON",
                f"{type(e).__name__}: {e}\n\nCheck console để xem chi tiết."
            )
    
    def _manage_keys(self, platform):
        """Open key management dialog (cũ, vẫn giữ cho compat)"""
        dialog = KeyManagementDialog(platform, self.config, parent=self)
        dialog.exec()
    
    def _show_json_dialog(self):
        """Show JSON input dialog directly (compat with old code)"""
        try:
            dialog = JsonInputDialog(parent=self)
            if dialog.exec() == QDialog.DialogCode.Accepted and dialog.result_data:
                try:
                    self.json_data = dialog.result_data
                    self.scenes = extract_scenes_from_json(dialog.result_data)
                    
                    if not self.scenes:
                        QMessageBox.warning(
                            self, "Không có scenes",
                            "JSON load OK nhưng không tìm thấy scenes nào.\n\n"
                            "JSON phải có 'scenes' hoặc 'part_a_scenes' hoặc 'part_b_segments'."
                        )
                        return
                    
                    self.scene_items = {}
                    self.selected_items = {}
                    self.current_scene_id = None
                    
                    # Update UI
                    self.json_status_label.setText(f"✓ {len(self.scenes)} scenes")
                    self.json_status_label.setStyleSheet("color: #4ec9b0; font-size: 10px; font-weight: 600;")
                    
                    self._populate_scene_list()
                    self._clear_grid()
                    
                    # Show placeholder
                    self._show_empty_placeholder()
                    
                    self._update_stats()
                    self._save_app_state()
                    
                    # Log
                    if hasattr(self, 'status_panel'):
                        self.status_panel.add_log(f"Loaded JSON: {len(self.scenes)} scenes", "success")
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    QMessageBox.critical(
                        self, "Lỗi load JSON",
                        f"Không load được JSON vào app:\n\n"
                        f"{type(e).__name__}: {e}\n\n"
                        f"Check console để xem chi tiết."
                    )
        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.critical(
                self, "Lỗi dialog",
                f"Lỗi khi mở dialog:\n\n{type(e).__name__}: {e}"
            )
    
    def _start_search(self):
        """Start search using QThread worker"""
        if not self.scenes:
            QMessageBox.warning(self, "Chưa có JSON", "Load JSON trước")
            return
        if not self.search_photos_check.isChecked() and not self.search_videos_check.isChecked():
            QMessageBox.warning(self, "Chưa chọn loại", "Chọn ít nhất Ảnh hoặc Video")
            return
        source_mode = self.search_source_combo.currentText() if hasattr(self, "search_source_combo") else "Pexels + Pixabay"
        source_lower = source_mode.lower()
        needs_pexels = "pexels" in source_lower or "+" in source_lower
        needs_pixabay = "pixabay" in source_lower or "+" in source_lower
        needs_vecteezy = "vecteezy" in source_lower or "+" in source_lower
        has_source_key = ((needs_pexels and self.config.get("pexels_keys"))
                          or (needs_pixabay and self.config.get("pixabay_keys"))
                          or (needs_vecteezy and self.config.get("vecteezy_keys")))
        if not has_source_key:
            QMessageBox.warning(self, "Thiếu API Key", f"Thêm API key cho nguồn đang chọn: {source_mode}")
            return
        
        # Confirm if already has data
        already_searched = any(self.scene_items.values())
        if already_searched:
            reply = QMessageBox.question(self, "Đã có data",
                                          "Đã có data từ trước. Search lại sẽ ghi đè?",
                                          QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply != QMessageBox.StandardButton.Yes:
                return
        
        # Reset items
        self.scene_items = {scene.get("id"): [] for scene in self.scenes}
        self._render_grid()
        self._update_stats()
        self._populate_scene_list()
        
        # Create KeyManager - Pexels + Pixabay + Vecteezy
        km = KeyManager(self.config.get("pexels_keys", []), self.config.get("pixabay_keys", []), [], self.config.get("vecteezy_keys", []))
        
        # UI state
        self.search_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.stop_btn.setText("⏹ DỪNG SEARCH")
        
        # Update status panel
        self.status_panel.set_searching("Đang khởi tạo...")
        self.status_panel.add_log(f"Bắt đầu search {len(self.scenes)} scenes", "info")
        self.status_panel.update_counters(0, len(self.scenes), 0, 0)
        
        # Start worker
        self.search_worker = SearchWorker(
            self.scenes, km,
            self.search_photos_check.isChecked(),
            self.search_videos_check.isChecked(),
            self.search_source_combo.currentText() if hasattr(self, "search_source_combo") else "Pexels + Pixabay",
        )
        self.search_worker.sceneCompleted.connect(self._on_scene_results)
        self.search_worker.progress.connect(self._on_search_progress)
        self.search_worker.finished_signal.connect(self._on_search_finished)
        self.search_worker.start()
    
    def _on_scene_results(self, scene_id, items):
        """Called when 1 scene's search results are ready"""
        self.scene_items[scene_id] = items
        self._update_scene_list_item(scene_id)
        
        # Log activity
        if hasattr(self, 'status_panel'):
            if items:
                self.status_panel.add_log(f"Scene #{scene_id}: tìm thấy {len(items)} items", "success")
            else:
                self.status_panel.add_log(f"Scene #{scene_id}: 0 items", "warning")
            
            # Update counters
            done = sum(1 for sid in self.scene_items if self.scene_items[sid])
            total = len(self.scenes)
            total_items = sum(len(items) for items in self.scene_items.values())
            total_selected = sum(len(items) for items in self.selected_items.values())
            self.status_panel.update_counters(done, total, total_items, total_selected)
            self.status_panel.set_progress(done, total)
        
        # Auto-show first scene with results
        if self.current_scene_id is None and items:
            scene = next((s for s in self.scenes if s.get("id") == scene_id), None)
            if scene:
                self._on_scene_clicked(scene)
        elif self.current_scene_id == scene_id:
            self._render_grid()
            self._update_stats()
    
    def _on_search_progress(self, message):
        self.status_bar.showMessage(message)
        if hasattr(self, 'status_panel'):
            self.status_panel.progress_label.setText(message)
    
    def _on_search_finished(self):
        self.search_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setText("⏹ DỪNG")
        self._save_app_state()
        self.status_bar.showMessage("✓ Search hoàn tất")
        if hasattr(self, 'status_panel'):
            total_items = sum(len(items) for items in self.scene_items.values())
            self.status_panel.set_idle(f"✓ Search xong: {total_items} items")
            self.status_panel.add_log(f"Search hoàn tất: {total_items} items", "success")
        if getattr(self, "_auto_after_search", False):
            self._auto_after_search = False
            self._auto_random_all_scenes()
            if hasattr(self, "auto_log"):
                self.auto_log.appendPlainText("Auto: đã random chọn media, bắt đầu tải.")
            self._auto_download_confirmless = True
            self._start_download()
            if getattr(self, "auto_voice_check", None) and self.auto_voice_check.isChecked():
                self._run_external_tool("Voice TXT Tool", "node server.mjs")
        elif getattr(self, "_workflow_waiting_for", None) == "Search stock":
            self._workflow_waiting_for = None
            if hasattr(self, "workflow_log"):
                self.workflow_log.appendPlainText("Search stock: xong, chạy node tiếp theo")
            self._workflow_continue()
    
    def _stop_action(self):
        """Stop both search and download workers"""
        stopped_something = False
        
        if hasattr(self, 'search_worker') and self.search_worker and self.search_worker.isRunning():
            self.search_worker.stop()
            stopped_something = True
        
        if hasattr(self, 'download_worker') and self.download_worker and self.download_worker.isRunning():
            self.download_worker.stop()
            stopped_something = True
        
        if stopped_something:
            self.status_bar.showMessage("⏹ Đang dừng... (đợi file hiện tại xong)")
            self.status_panel.main_label.setText("⏹ Đang dừng...")
            self.stop_btn.setEnabled(False)
            self.stop_btn.setText("⏹ Đang dừng...")
        else:
            self.status_bar.showMessage("Không có tác vụ đang chạy")
    
    def _reset_all(self):
        reply = QMessageBox.question(self, "Xác nhận Reset",
                                       "Xóa TẤT CẢ data đã search và lựa chọn?",
                                       QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            reset_state()
            self.scenes = []
            self.json_data = None
            self.scene_items = {}
            self.selected_items = {}
            self.current_scene_id = None
            self._populate_scene_list()
            self._clear_grid()
            self._update_stats()
            self.json_status_label.setText("Chưa có JSON")
            self.json_status_label.setStyleSheet("color: #7d8590; font-size: 10px;")
            
            # Reset search options về default
            try:
                self.search_photos_check.setChecked(True)
                self.search_videos_check.setChecked(True)
            except Exception:
                pass
            
            QMessageBox.information(self, "Done", "Đã reset.")
    
    def _populate_scene_list(self):
        # Clear old
        for widget in self.scene_list_widgets:
            widget.setParent(None)
            widget.deleteLater()
        self.scene_list_widgets = []
        
        # Filter by search
        search_text = self.scene_search_input.text().lower() if hasattr(self, 'scene_search_input') else ""
        filtered = []
        for scene in self.scenes:
            if search_text:
                dialogue = scene.get("dialogue_es", "") or scene.get("dialogue", "")
                kw = " ".join(scene.get("primary_keywords", []))
                if (search_text not in dialogue.lower() and
                    search_text not in kw.lower() and
                    search_text not in str(scene.get("id", ""))):
                    continue
            filtered.append(scene)
        
        self.scenes_count_label.setText(f"{len(filtered)}/{len(self.scenes)} scenes")
        
        # Insert before stretch
        stretch_idx = self.scenes_layout.count() - 1
        for scene in filtered:
            is_active = (self.current_scene_id == scene.get("id"))
            item = SceneListItem(scene, is_active=is_active)
            item.clicked.connect(self._on_scene_clicked)
            
            scene_id = scene.get("id")
            items_count = len(self.scene_items.get(scene_id, []))
            selected_count = len(self.selected_items.get(scene_id, {}))
            item.update_stats(items_count, selected_count)
            
            self.scenes_layout.insertWidget(stretch_idx, item)
            self.scene_list_widgets.append(item)
            stretch_idx += 1
    
    def _filter_scenes(self):
        self._populate_scene_list()
    
    def _on_scene_clicked(self, scene):
        scene_id = scene.get("id")
        self.current_scene_id = scene_id
        self.current_page = 0
        self.current_filter = "all"
        
        # Update active state
        for widget in self.scene_list_widgets:
            widget.set_active(widget.scene.get("id") == scene_id)
        
        # Update filter buttons
        for fkey, btn in self.filter_buttons.items():
            btn.setObjectName("filterActive" if fkey == "all" else "filterInactive")
            btn.setStyleSheet("")  # force re-style
            self.setStyleSheet(self.styleSheet())  # refresh
        
        # Update stats
        self.stat_scene.set_value(f"#{scene_id}")
        
        # Update scene info panel
        self._update_scene_info_panel(scene)
        
        # Populate MotionArray keywords list
        if hasattr(self, 'btn_motionarray'):
            self._populate_ma_keywords(scene)
        
        # Render grid
        self._render_grid()
        self._update_stats()
        self._save_app_state()
    
    def _populate_ma_keywords(self, scene):
        """Render keywords list trong MotionArray panel với checkboxes"""
        # Clear old checkboxes
        for cb in self.ma_keyword_checks:
            cb.setParent(None)
            cb.deleteLater()
        self.ma_keyword_checks = []
        
        # Hide placeholder
        try:
            self.ma_keywords_placeholder.setParent(None)
            self.ma_keywords_placeholder.deleteLater()
        except Exception:
            pass
        self.ma_keywords_placeholder = None
        
        scene_id = scene.get("id")
        primary = scene.get("primary_keywords") or []
        secondary = scene.get("secondary_keywords") or []
        
        # Dedup keep order
        seen = set()
        all_keywords = []
        for kw in (primary + secondary):
            if not kw:
                continue
            k = kw.strip()
            if k.lower() in seen:
                continue
            seen.add(k.lower())
            is_primary = kw in primary
            all_keywords.append((k, is_primary))
        
        if not all_keywords:
            self.ma_status_label.setText(f"⚠ Scene #{scene_id} chưa có keyword")
            self.ma_status_label.setStyleSheet("color: #f39c12; font-size: 10px; padding: 6px; background-color: #0d1117; border-radius: 4px;")
            self.btn_motionarray.setEnabled(False)
            
            # Placeholder
            self.ma_keywords_placeholder = QLabel(f"Scene #{scene_id} không có keyword")
            self.ma_keywords_placeholder.setStyleSheet("color: #6e7681; font-size: 11px; padding: 20px; background: transparent;")
            self.ma_keywords_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.ma_keywords_layout.insertWidget(0, self.ma_keywords_placeholder)
            return
        
        # Insert checkbox cho từng keyword (insert ở đầu, trước stretch)
        for idx, (kw, is_primary) in enumerate(all_keywords):
            # Format: [P] keyword (primary) hoặc [S] keyword (secondary)
            label_prefix = "⭐" if is_primary else "•"
            cb = QCheckBox(f"{label_prefix} {kw}")
            cb.setChecked(True)
            cb.setProperty("keyword", kw)
            cb.setProperty("is_primary", is_primary)
            cb.toggled.connect(self._ma_update_button_text)
            cb.setMinimumHeight(28)  # Đủ to dễ click
            
            # Style: primary highlight orange, secondary normal
            if is_primary:
                color = "#f39c12"
                weight = "700"
                bg_unchecked = "#1f1612"
            else:
                color = "#c9d1d9"
                weight = "500"
                bg_unchecked = "#161b22"
            
            cb.setStyleSheet(f"""
                QCheckBox {{
                    color: {color};
                    font-size: 12px;
                    font-weight: {weight};
                    padding: 6px 8px;
                    background-color: {bg_unchecked};
                    border-radius: 4px;
                    spacing: 8px;
                    border: 1px solid transparent;
                }}
                QCheckBox:hover {{
                    background-color: #21262d;
                    border: 1px solid #f39c12;
                }}
                QCheckBox::indicator {{
                    width: 16px;
                    height: 16px;
                    border-radius: 3px;
                    border: 1.5px solid #484f58;
                    background-color: #0d1117;
                }}
                QCheckBox::indicator:checked {{
                    background-color: #f39c12;
                    border-color: #f39c12;
                }}
                QCheckBox::indicator:hover {{
                    border-color: #f39c12;
                }}
            """)
            
            self.ma_keywords_layout.insertWidget(idx, cb)
            self.ma_keyword_checks.append(cb)
        
        # Enable button + update status
        self.btn_motionarray.setEnabled(True)
        self._ma_update_button_text()
    
    def _ma_update_button_text(self):
        """Update button text dựa trên số keywords được tick"""
        checked = sum(1 for cb in self.ma_keyword_checks if cb.isChecked())
        total = len(self.ma_keyword_checks)
        
        if checked == 0:
            self.btn_motionarray.setText("🔍 (Chưa chọn keyword)")
            self.btn_motionarray.setEnabled(False)
        else:
            self.btn_motionarray.setText(f"🔍 Mở {checked} tab Cốc Cốc")
            self.btn_motionarray.setEnabled(True)
        
        self.ma_status_label.setText(f"Đã chọn {checked}/{total} keywords")
        self.ma_status_label.setStyleSheet(
            "color: #c9d1d9; font-size: 10px; padding: 6px; background-color: #0d1117; border-radius: 4px;"
        )
    
    def _ma_select_all_keywords(self):
        """Tick tất cả keywords"""
        for cb in self.ma_keyword_checks:
            cb.setChecked(True)
    
    def _ma_select_no_keywords(self):
        """Bỏ tick tất cả keywords"""
        for cb in self.ma_keyword_checks:
            cb.setChecked(False)
    
    def _update_scene_info_panel(self, scene):
        """Update the scene info textbox in sidebar"""
        lines = []
        
        # Timestamps
        time_start = scene.get("time_start", "?")
        time_end = scene.get("time_end", "?")
        duration = scene.get("duration_seconds", 0)
        lines.append(f"⏱ {time_start} → {time_end} ({duration}s)")
        lines.append("")
        
        # Vietnamese description (if exists)
        desc_vi = scene.get("description_vi", "") or scene.get("mo_ta", "")
        if desc_vi:
            lines.append("📖 MÔ TẢ:")
            lines.append(desc_vi)
            lines.append("")
        
        # Dialogue
        dialogue = scene.get("dialogue_es", "") or scene.get("dialogue_vi", "") or scene.get("dialogue", "")
        if dialogue:
            lines.append("💬 DIALOGUE:")
            lines.append(dialogue)
            lines.append("")
        
        # Context (English)
        context = scene.get("context_summary_en", "") or scene.get("context_summary", "")
        if context:
            lines.append("📝 CONTEXT:")
            lines.append(context)
            lines.append("")
        
        # Keywords
        primary = scene.get("primary_keywords", [])
        if primary:
            lines.append("🔍 KEYWORDS:")
            lines.append(", ".join(primary[:3]))
        
        # Mood + shot
        mood = scene.get("mood", "")
        shot = scene.get("shot_type", "")
        if mood or shot:
            lines.append("")
            extras = []
            if mood:
                extras.append(f"Mood: {mood}")
            if shot:
                extras.append(f"Shot: {shot}")
            lines.append(" | ".join(extras))
        
        self.scene_info_panel.setPlainText("\n".join(lines))
    
    def _set_filter(self, filter_key):
        self.current_filter = filter_key
        for fkey, btn in self.filter_buttons.items():
            btn.setObjectName("filterActive" if fkey == filter_key else "filterInactive")
        self.setStyleSheet(self.styleSheet())  # refresh styles
        self.current_page = 0
        self._render_grid()
    
    def _get_current_items(self):
        if self.current_scene_id is None:
            return []
        return self.scene_items.get(self.current_scene_id, [])
    
    def _apply_filter(self, items):
        if self.current_filter == "all":
            return items
        elif self.current_filter == "photos":
            return [i for i in items if i["type"] == "photo"]
        elif self.current_filter == "videos":
            return [i for i in items if i["type"] == "video"]
        return items
    
    def _clear_grid(self):
        for card in self.thumb_cards:
            card.setParent(None)
            card.deleteLater()
        self.thumb_cards = []
        self.url_to_cards = {}
        
        # Hide placeholder if shown
        try:
            self.placeholder_label.setParent(None)
        except Exception:
            pass
    
    def _show_empty_placeholder(self):
        """Show placeholder khi grid empty (sau khi load JSON, chưa chọn scene)"""
        self._clear_grid()
        try:
            self.placeholder_label = QLabel("👈 Chọn scene từ sidebar trái\nhoặc click 'SEARCH TẤT CẢ' để bắt đầu")
            self.placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.placeholder_label.setStyleSheet("color: #484f58; font-size: 14px; padding: 100px;")
            self.grid_layout.addWidget(self.placeholder_label, 0, 0, GRID_ROWS, GRID_COLS)
            self._update_pagination()
        except Exception as e:
            print(f"[_show_empty_placeholder] {e}")
    
    def _render_grid(self):
        self._clear_grid()
        
        if self.current_scene_id is None:
            self.placeholder_label = QLabel("👈 Chọn scene từ sidebar trái")
            self.placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.placeholder_label.setStyleSheet("color: #484f58; font-size: 14px;")
            self.grid_layout.addWidget(self.placeholder_label, 0, 0, GRID_ROWS, GRID_COLS)
            self._update_pagination()
            return
        
        all_items = self._get_current_items()
        filtered = self._apply_filter(all_items)
        
        if not filtered:
            self.placeholder_label = QLabel(
                f"Scene #{self.current_scene_id} chưa có data\nClick 'SEARCH TẤT CẢ' để bắt đầu"
            )
            self.placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.placeholder_label.setStyleSheet("color: #484f58; font-size: 14px;")
            self.grid_layout.addWidget(self.placeholder_label, 0, 0, GRID_ROWS, GRID_COLS)
            self._update_pagination(total=0)
            return
        
        start = self.current_page * ITEMS_PER_PAGE
        end = start + ITEMS_PER_PAGE
        page_items = filtered[start:end]
        
        selected_in_scene = self.selected_items.get(self.current_scene_id, {})
        
        for idx, item in enumerate(page_items):
            row = idx // GRID_COLS
            col = idx % GRID_COLS
            
            item_key = self._get_item_key(item)
            is_selected = item_key in selected_in_scene
            
            card = ThumbnailCard(item, is_selected=is_selected)
            card.selectionChanged.connect(self._on_item_select)
            card.clicked.connect(self._show_preview_modal)
            card.retryRequested.connect(self._on_card_retry)
            
            self.grid_layout.addWidget(card, row, col)
            self.thumb_cards.append(card)
            
            # Request thumbnail
            thumb_url = item.get("thumb_url")
            if thumb_url:
                # Check if cached
                pixmap = self.thumbnail_cache.get_pixmap(thumb_url)
                if pixmap:
                    card.set_thumbnail(pixmap)
                else:
                    # Track for async loading
                    self.url_to_cards.setdefault(thumb_url, []).append(card)
                    self.thumb_loader.load_async(thumb_url)
        
        self._update_pagination(total=len(filtered))
    
    def _on_card_retry(self, item):
        """Retry tải 1 card khi user click thumb failed"""
        # Find card by item
        for card in self.thumb_cards:
            try:
                if card.item.get("id") == item.get("id") and card.thumb_failed:
                    card.reset_to_loading()
                    url = item["thumb_url"]
                    # Re-register
                    if url not in self.url_to_cards:
                        self.url_to_cards[url] = []
                    if card not in self.url_to_cards[url]:
                        self.url_to_cards[url].append(card)
                    # Trigger reload
                    self.thumb_loader.load_async(url)
                    break
            except RuntimeError:
                continue
    
    def _on_thumbnail_loaded(self, url, pixmap):
        """Called when a thumbnail is loaded async"""
        cards = self.url_to_cards.get(url, [])
        for card in cards:
            try:
                card.set_thumbnail(pixmap)
            except RuntimeError:
                pass  # card was deleted
        if url in self.url_to_cards:
            del self.url_to_cards[url]
    
    def _on_thumbnail_failed(self, url):
        """Called when a thumbnail load fails"""
        cards = self.url_to_cards.get(url, [])
        for card in cards:
            try:
                card.set_failed_state()
            except RuntimeError:
                pass
        if url in self.url_to_cards:
            del self.url_to_cards[url]
    
    def _save_search_prefs(self):
        """Save search options preferences vào config"""
        self.config["search_prefs"] = {
            "photos": self.search_photos_check.isChecked(),
            "videos": self.search_videos_check.isChecked(),
            "source": self.search_source_combo.currentText() if hasattr(self, "search_source_combo") else "Pexels + Pixabay",
        }
        try:
            save_config(self.config)
        except Exception:
            pass
    
    def _retry_failed_thumbnails(self):
        """Retry tải lại tất cả thumbnails đang failed"""
        retry_count = 0
        for card in self.thumb_cards:
            try:
                if card.thumb_failed:
                    card.reset_to_loading()
                    self.thumb_loader.load_async(card.item["thumb_url"])
                    # Re-register card
                    url = card.item["thumb_url"]
                    if url not in self.url_to_cards:
                        self.url_to_cards[url] = []
                    if card not in self.url_to_cards[url]:
                        self.url_to_cards[url].append(card)
                    retry_count += 1
            except RuntimeError:
                pass
        
        if retry_count > 0:
            self.status_bar.showMessage(f"⟳ Đang retry {retry_count} thumbnails...")
    
    def _update_pagination(self, total=None):
        if total is None:
            filtered = self._apply_filter(self._get_current_items())
            total = len(filtered)
        total_pages = max(1, (total + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)
        current = self.current_page + 1
        self.page_label.setText(f"Trang {current}/{total_pages} ({total} items)")
        self.prev_btn.setEnabled(self.current_page > 0)
        self.next_btn.setEnabled(self.current_page < total_pages - 1)
    
    def _prev_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self._render_grid()
    
    def _next_page(self):
        filtered = self._apply_filter(self._get_current_items())
        total_pages = (len(filtered) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
        if self.current_page < total_pages - 1:
            self.current_page += 1
            self._render_grid()
    
    def _get_item_key(self, item):
        return f"{item['source']}_{item['type']}_{item['id']}"
    
    def _on_item_select(self, item, is_selected):
        if self.current_scene_id is None:
            return
        sid = self.current_scene_id
        if sid not in self.selected_items:
            self.selected_items[sid] = {}
        key = self._get_item_key(item)
        if is_selected:
            self.selected_items[sid][key] = item
        else:
            self.selected_items[sid].pop(key, None)
        self._update_stats()
        self._update_scene_list_item(sid)
        self._save_app_state()
    
    def _update_scene_list_item(self, scene_id):
        for widget in self.scene_list_widgets:
            if widget.scene.get("id") == scene_id:
                items_count = len(self.scene_items.get(scene_id, []))
                selected_count = len(self.selected_items.get(scene_id, {}))
                widget.update_stats(items_count, selected_count)
                break
    
    def _select_all_scene(self):
        if self.current_scene_id is None:
            return
        sid = self.current_scene_id
        items = self._apply_filter(self._get_current_items())
        if sid not in self.selected_items:
            self.selected_items[sid] = {}
        for item in items:
            key = self._get_item_key(item)
            self.selected_items[sid][key] = item
        self._render_grid()
        self._update_stats()
        self._update_scene_list_item(sid)
        self._save_app_state()

    def _select_random_scene(self):
        if self.current_scene_id is None:
            QMessageBox.information(self, "Chưa chọn scene", "Chọn scene trước khi random")
            return

        sid = self.current_scene_id
        items = self._apply_filter(self._get_current_items())
        if not items:
            QMessageBox.information(self, "Không có item", "Tab/filter hiện tại chưa có ảnh hoặc video để chọn")
            return

        count = min(self.random_count_spin.value(), len(items))
        picked = random.sample(items, count)
        self.selected_items[sid] = {self._get_item_key(item): item for item in picked}

        filter_label = {"all": "tất cả", "photos": "ảnh", "videos": "video"}.get(self.current_filter, "item")
        self.status_bar.showMessage(f"🎲 Đã chọn random {count}/{len(items)} {filter_label} cho scene #{sid}", 5000)
        self._render_grid()
        self._update_stats()
        self._update_scene_list_item(sid)
        self._save_app_state()
    
    def _clear_scene_selection(self):
        if self.current_scene_id is None:
            return
        sid = self.current_scene_id
        if sid in self.selected_items:
            self.selected_items[sid] = {}
        self._render_grid()
        self._update_stats()
        self._update_scene_list_item(sid)
        self._save_app_state()
    
    def _show_preview_modal(self, item):
        """Show preview modal (Pexels only)"""
        modal = PreviewModal(item, self.thumbnail_cache, parent=self)
        modal.exec()
    
    def _find_coccoc_path(self):
        """Tìm path Cốc Cốc đã cài"""
        possible_paths = [
            os.path.expandvars(r"%LOCALAPPDATA%\CocCoc\Browser\Application\browser.exe"),
            os.path.expandvars(r"%PROGRAMFILES%\CocCoc\Browser\Application\browser.exe"),
            os.path.expandvars(r"%PROGRAMFILES(X86)%\CocCoc\Browser\Application\browser.exe"),
            r"C:\Users\%USERNAME%\AppData\Local\CocCoc\Browser\Application\browser.exe",
        ]
        for p in possible_paths:
            expanded = os.path.expandvars(p)
            if os.path.exists(expanded):
                return expanded
        return None
    
    def _open_motionarray_search(self):
        """Mở MotionArray search trong Cốc Cốc với keywords ĐÃ TICK CHỌN.
        
        Mỗi keyword mở 1 tab riêng → nhiều tab cùng lúc trong Cốc Cốc.
        """
        if not self.current_scene_id:
            QMessageBox.information(self, "Chưa chọn scene", "Chọn scene trước khi search MotionArray")
            return
        
        # Lấy keywords đã tick chọn từ checkboxes
        selected_keywords = []
        for cb in self.ma_keyword_checks:
            if cb.isChecked():
                kw = cb.property("keyword")
                if kw:
                    selected_keywords.append(kw)
        
        if not selected_keywords:
            QMessageBox.information(
                self, "Chưa chọn keyword", 
                "Tick chọn ít nhất 1 keyword muốn search trong panel MotionArray"
            )
            return
        
        # Track scene đang xem MotionArray (để watcher biết move file vào scene nào)
        self._current_ma_scene_id = self.current_scene_id
        
        # Start watcher nếu chưa start
        if not self._watcher_started:
            self.downloads_watcher.start()
            self._watcher_started = True
            if hasattr(self, 'ma_watcher_label'):
                self.ma_watcher_label.setText(
                    f"👁 Watching: {self.downloads_watcher.downloads_dir}"
                )
                self.ma_watcher_label.setStyleSheet(
                    "color: #2ecc71; font-size: 9px; padding: 2px; background: transparent; border: none;"
                )
        
        # Confirm nếu nhiều keywords (>5) để tránh user mở nhầm
        if len(selected_keywords) > 5:
            reply = QMessageBox.question(
                self, "Xác nhận mở nhiều tab",
                f"Scene #{self.current_scene_id}: sẽ mở {len(selected_keywords)} tab Cốc Cốc:\n\n"
                + "\n".join(f"  • {kw}" for kw in selected_keywords[:7])
                + (f"\n  • ... và {len(selected_keywords) - 7} keywords nữa" if len(selected_keywords) > 7 else "")
                + "\n\nTiếp tục?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        
        # Tìm Cốc Cốc, fallback sang browser mặc định
        coccoc_path = self._find_coccoc_path()
        
        opened = 0
        failed = 0
        from urllib.parse import quote_plus
        
        for kw in selected_keywords:
            try:
                encoded = quote_plus(kw)
                url = f"https://motionarray.com/browse/stock-video/?q={encoded}"
                
                if coccoc_path:
                    subprocess.Popen([coccoc_path, url])
                else:
                    import webbrowser
                    webbrowser.open(url, new=2)  # new=2 = new tab
                
                opened += 1
                # Delay nhỏ giữa các tab để browser xử lý kịp (tránh bị merge)
                time.sleep(0.3)
            except Exception as e:
                print(f"[MotionArray] Lỗi mở tab '{kw}': {e}")
                failed += 1
        
        # Update status
        browser_name = "Cốc Cốc" if coccoc_path else "browser mặc định"
        if opened > 0:
            self.ma_status_label.setText(
                f"✓ Đã mở {opened} tab {browser_name}\n"
                f"Đang watch Downloads folder..."
            )
            self.ma_status_label.setStyleSheet(
                "color: #2ecc71; font-size: 10px; padding: 6px; background-color: #0d1117; border-radius: 4px;"
            )
            self.status_bar.showMessage(
                f"🌐 MotionArray: mở {opened} tab ({browser_name}) cho scene #{self.current_scene_id}"
            )
            
            # Log
            if hasattr(self, 'status_panel'):
                self.status_panel.add_log(
                    f"MotionArray: mở {opened} tab cho scene #{self.current_scene_id}",
                    "info"
                )
        else:
            self.ma_status_label.setText(f"❌ Không mở được tab nào")
            self.ma_status_label.setStyleSheet(
                "color: #f85149; font-size: 10px; padding: 6px; background-color: #0d1117; border-radius: 4px;"
            )
    
    def _on_download_detected(self, filepath):
        """Callback khi DownloadsWatcher detect file mp4 mới
        
        Hiện dialog hỏi user file thuộc scene nào.
        """
        if not self.scenes:
            return  # Chưa có JSON, ignore
        
        filename = os.path.basename(filepath)
        
        # Show dialog
        dialog = AssignSceneDialog(
            filename=filename,
            scenes=self.scenes,
            suggested_scene_id=self._current_ma_scene_id,
            parent=self
        )
        result = dialog.exec()
        
        if result != QDialog.DialogCode.Accepted:
            # User đóng dialog bằng X → coi như skip
            return
        
        if dialog.action == "skip":
            self.status_bar.showMessage(f"⏭ Bỏ qua file: {filename}")
            return
        
        if dialog.action == "delete":
            try:
                os.remove(filepath)
                self.status_bar.showMessage(f"🗑 Đã xóa: {filename}")
            except Exception as e:
                QMessageBox.warning(self, "Lỗi xóa file", str(e))
            return
        
        if dialog.action == "assign":
            scene_id = dialog.selected_scene_id
            self._move_file_to_scene(filepath, scene_id)
    
    def _move_file_to_scene(self, src_path, scene_id):
        """Move file từ Downloads vào output_dir (flat, prefix scene_id) + rename
        
        v5.0: KHÔNG tạo subfolder nữa - lưu chung 1 folder để dễ import CapCut
        """
        try:
            scene = next((s for s in self.scenes if s.get("id") == scene_id), None)
            if not scene:
                QMessageBox.warning(self, "Scene không tồn tại", f"Scene #{scene_id} không tìm thấy")
                return
            
            # output_base: tất cả file flat ở đây
            output_dir = self.config.get("output_dir") or str(DEFAULT_OUTPUT_DIR)
            output_base = Path(output_dir)
            output_base.mkdir(parents=True, exist_ok=True)
            
            # Scene prefix: 037_00-15-57
            scene_id_str = str(scene_id).zfill(3) if isinstance(scene_id, int) else str(scene_id)
            ts_start = scene.get("timestamp_start") or scene.get("time_start") or "00-00-00"
            ts_safe = ts_start.replace(":", "-").replace(",", "-").replace(".", "-")
            scene_prefix = f"{scene_id_str}_{ts_safe}"
            
            # Đếm số file motionarray của scene này đã có (search prefix trong output_base)
            existing = list(output_base.glob(f"{scene_prefix}_motionarray_*"))
            next_num = len(existing) + 1
            
            src = Path(src_path)
            # Filename: 037_00-15-57_motionarray_001.mp4
            new_filename = f"{scene_prefix}_motionarray_{next_num:03d}{src.suffix.lower()}"
            dest_path = output_base / new_filename
            
            # Xử lý nếu trùng tên (rare)
            while dest_path.exists():
                next_num += 1
                new_filename = f"{scene_prefix}_motionarray_{next_num:03d}{src.suffix.lower()}"
                dest_path = output_base / new_filename
            
            # Move file
            import shutil
            shutil.move(str(src), str(dest_path))
            
            self.status_bar.showMessage(f"✓ Đã sắp xếp: {new_filename} → scene #{scene_id}")
            
            # Update MA status
            if hasattr(self, 'ma_status_label'):
                self.ma_status_label.setText(f"✓ File → scene #{scene_id}: {new_filename}")
                self.ma_status_label.setStyleSheet("color: #2ecc71; font-size: 10px; padding: 4px;")
            
            # Trigger refresh download monitor ngay
            if hasattr(self, '_refresh_download_monitor'):
                self._refresh_download_monitor()
            
        except Exception as e:
            QMessageBox.critical(self, "Lỗi move file", f"Không move được file:\n{e}")
    
    def _refresh_download_monitor(self):
        """Scan output folder, đếm files mỗi scene, update panel.
        
        v5.0: Tất cả files FLAT trong output_dir với prefix scene_id_timestamp
        VD: 036_00-15-33_pexels_video_xxx.mp4
            036_00-15-33_motionarray_001.mp4
            037_00-15-57_pexels_photo_yyy.jpg
        """
        if not hasattr(self, 'dm_container_layout') or not self.scenes:
            return
        
        output_dir = Path(self.config.get("output_dir") or str(DEFAULT_OUTPUT_DIR))
        if not output_dir.exists():
            self._dm_clear_rows()
            if hasattr(self, 'dm_placeholder') and self.dm_placeholder is not None:
                try:
                    self.dm_placeholder.setText("Folder output chưa tồn tại\nLoad JSON & search trước")
                    self.dm_placeholder.setParent(self.dm_container)
                    self.dm_container_layout.insertWidget(0, self.dm_placeholder)
                except Exception:
                    pass
            self.dm_summary_label.setText("0 scenes • 0 files")
            return
        
        # Hide placeholder
        if hasattr(self, 'dm_placeholder') and self.dm_placeholder is not None:
            try:
                self.dm_placeholder.setParent(None)
                self.dm_placeholder.deleteLater()
                self.dm_placeholder = None
            except Exception:
                pass
        
        # Build scene_id → counts dict
        scene_counts = {}
        for scene in self.scenes:
            sid = scene.get("id")
            if sid is None:
                continue
            sid_str = str(sid).zfill(3) if isinstance(sid, int) else str(sid)
            
            scene_counts[sid] = {
                'pexels_video': 0,
                'pexels_photo': 0,
                'ma_video': 0,
                'other': 0,
                'folder': output_dir,  # click row → mở folder chung
                'scene': scene,
                'sid_str': sid_str,
            }
        
        # Scan flat files in output_dir - extract scene_id từ prefix 3 chữ số
        for f in output_dir.iterdir():
            if not f.is_file():
                continue
            # Skip metadata files
            if f.name.startswith("_"):
                continue
            
            name = f.name
            m = re.match(r'^(\d{3})_', name)
            if not m:
                continue
            try:
                sid = int(m.group(1))
            except ValueError:
                continue
            if sid not in scene_counts:
                continue
            
            name_lower = name.lower()
            # Phân loại theo source/type trong tên
            if '_pexels_video_' in name_lower and name_lower.endswith(('.mp4', '.mov')):
                scene_counts[sid]['pexels_video'] += 1
            elif '_pexels_photo_' in name_lower and name_lower.endswith(('.jpg', '.jpeg', '.png', '.webp')):
                scene_counts[sid]['pexels_photo'] += 1
            elif '_motionarray_' in name_lower:
                scene_counts[sid]['ma_video'] += 1
            elif name_lower.endswith(('.mp4', '.mov', '.jpg', '.jpeg', '.png', '.webp')):
                scene_counts[sid]['other'] += 1
        
        # Update UI
        scenes_with_files = 0
        total_files = 0
        for sid, info in scene_counts.items():
            n_pv = info['pexels_video']
            n_pp = info['pexels_photo']
            n_ma = info['ma_video']
            n_other = info['other']
            scene_total = n_pv + n_pp + n_ma + n_other
            
            self._dm_update_scene_row(
                sid, info['scene'],
                n_pv, n_pp, n_ma, n_other,
                info['folder']
            )
            
            if scene_total > 0:
                scenes_with_files += 1
                total_files += scene_total
        
        # Summary
        total_scenes = len(self.scenes)
        scenes_empty = total_scenes - scenes_with_files
        if scenes_empty == 0 and total_scenes > 0:
            color = "#4ec9b0"
            icon = "✅"
        elif scenes_with_files > 0:
            color = "#f39c12"
            icon = "⚠"
        else:
            color = "#7d8590"
            icon = "📭"
        
        self.dm_summary_label.setText(
            f"{icon} {scenes_with_files}/{total_scenes} scenes • {total_files} files"
        )
        self.dm_summary_label.setStyleSheet(f"""
            color: {color};
            font-size: 10px;
            font-weight: 600;
            padding: 4px 6px;
            background-color: #0d1117;
            border-radius: 3px;
            border: none;
        """)
    
    def _dm_clear_rows(self):
        """Clear tất cả scene rows trong download monitor"""
        for scene_id, row in list(self.dm_scene_rows.items()):
            try:
                row.setParent(None)
                row.deleteLater()
            except Exception:
                pass
        self.dm_scene_rows = {}
    
    def _dm_update_scene_row(self, scene_id, scene, n_pv, n_pp, n_ma, n_other, folder_path):
        """Update hoặc tạo row mới cho 1 scene trong monitor."""
        total = n_pv + n_pp + n_ma + n_other
        
        # Build display text
        time_start = scene.get("time_start", "?")
        
        if total == 0:
            status_icon = "❌"
            status_color = "#7d8590"
            status_bg = "#161b22"
            detail_text = "chưa có file"
        elif total < 3:
            status_icon = "⚠"
            status_color = "#f39c12"
            status_bg = "#1f1612"
            parts = []
            if n_pv: parts.append(f"{n_pv}V")
            if n_pp: parts.append(f"{n_pp}P")
            if n_ma: parts.append(f"{n_ma}MA")
            if n_other: parts.append(f"{n_other}?")
            detail_text = f"{total} files ({', '.join(parts)})"
        else:
            status_icon = "✅"
            status_color = "#4ec9b0"
            status_bg = "#0f1f15"
            parts = []
            if n_pv: parts.append(f"{n_pv}V")
            if n_pp: parts.append(f"{n_pp}P")
            if n_ma: parts.append(f"{n_ma}MA")
            if n_other: parts.append(f"{n_other}?")
            detail_text = f"{total} files ({', '.join(parts)})"
        
        # Create or update row
        if scene_id not in self.dm_scene_rows:
            # Create new row
            row = QFrame()
            row.setStyleSheet(f"""
                QFrame {{
                    background-color: {status_bg};
                    border: 1px solid #21262d;
                    border-radius: 4px;
                }}
                QFrame:hover {{
                    border: 1px solid {status_color};
                }}
            """)
            row.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(6, 4, 6, 4)
            row_layout.setSpacing(4)
            
            # Icon
            icon_lbl = QLabel(status_icon)
            icon_lbl.setStyleSheet(f"color: {status_color}; font-size: 13px; background: transparent; border: none;")
            icon_lbl.setFixedWidth(20)
            row_layout.addWidget(icon_lbl)
            
            # Scene info (id + time)
            info_lbl = QLabel(f"<b>#{scene_id}</b>  {time_start}")
            info_lbl.setStyleSheet("color: #c9d1d9; font-size: 10px; background: transparent; border: none;")
            row_layout.addWidget(info_lbl)
            
            row_layout.addStretch()
            
            # Files count
            count_lbl = QLabel(detail_text)
            count_lbl.setStyleSheet(f"color: {status_color}; font-size: 10px; font-weight: 600; background: transparent; border: none;")
            row_layout.addWidget(count_lbl)
            
            # Click to open folder
            def open_folder(_event, p=folder_path):
                if p.exists():
                    import platform
                    if platform.system() == "Windows":
                        os.startfile(str(p))
                    else:
                        subprocess.Popen(["xdg-open", str(p)])
            row.mousePressEvent = open_folder
            
            # Insert at correct position (sort by scene_id)
            insert_idx = 0
            for i in range(self.dm_container_layout.count()):
                w = self.dm_container_layout.itemAt(i).widget()
                if w is None:
                    continue
                existing_id = w.property("scene_id")
                if existing_id is not None and existing_id > scene_id:
                    break
                insert_idx = i + 1
            
            row.setProperty("scene_id", scene_id)
            row.setProperty("icon_lbl", icon_lbl)
            row.setProperty("count_lbl", count_lbl)
            
            self.dm_container_layout.insertWidget(insert_idx, row)
            self.dm_scene_rows[scene_id] = row
        else:
            # Update existing row
            row = self.dm_scene_rows[scene_id]
            row.setStyleSheet(f"""
                QFrame {{
                    background-color: {status_bg};
                    border: 1px solid #21262d;
                    border-radius: 4px;
                }}
                QFrame:hover {{
                    border: 1px solid {status_color};
                }}
            """)
            
            # Find labels và update
            for child in row.children():
                if not hasattr(child, 'text'):
                    continue
                text = child.text() if callable(getattr(child, 'text', None)) else ""
                # Icon label (single char)
                if text in ("❌", "⚠", "✅"):
                    child.setText(status_icon)
                    child.setStyleSheet(f"color: {status_color}; font-size: 13px; background: transparent; border: none;")
                # Count label (contains "files" hoặc "chưa")
                elif "file" in text or "chưa" in text:
                    child.setText(detail_text)
                    child.setStyleSheet(f"color: {status_color}; font-size: 10px; font-weight: 600; background: transparent; border: none;")
    
    def _update_stats(self):
        if self.current_scene_id is None:
            self.stat_total.set_value(0)
            self.stat_selected_scene.set_value(0)
        else:
            items = self.scene_items.get(self.current_scene_id, [])
            selected = self.selected_items.get(self.current_scene_id, {})
            self.stat_total.set_value(len(items))
            self.stat_selected_scene.set_value(len(selected))
        total_selected = sum(len(s) for s in self.selected_items.values())
        self.stat_selected_total.set_value(total_selected)
    
    def _start_download(self):
        """Start download using worker thread with ANTI-BLOCK"""
        total_selected = sum(len(s) for s in self.selected_items.values())
        if total_selected == 0:
            QMessageBox.information(self, "Chưa chọn", "Tick chọn items muốn tải")
            return
        
        output_dir = self.config.get("output_dir", "")
        if not output_dir:
            QMessageBox.warning(self, "Chưa có folder", "Chọn thư mục lưu")
            return
        
        if getattr(self, "_auto_download_confirmless", False):
            self._auto_download_confirmless = False
        else:
            reply = QMessageBox.question(self, "Xác nhận",
                                           f"Tải {total_selected} files về?\n\n{output_dir}\n\n"
                                           f"🛡️ Anti-block ON: Adaptive delay + Block detection + URL refresh",
                                           QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply != QMessageBox.StandardButton.Yes:
                return
        
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        # Create KeyManager for URL refresh
        km = KeyManager(self.config.get("pexels_keys", []),
                          self.config.get("pixabay_keys", []), [],
                          self.config.get("vecteezy_keys", []))
        
        # UI state
        self.search_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.stop_btn.setText("⏹ DỪNG TẢI")
        
        # Update status panel
        self.status_panel.set_downloading("Khởi tạo download...")
        
        # Start worker
        self.download_worker = DownloadWorker(
            self.scenes,
            self.selected_items,
            output_dir,
            self.json_data,
            key_manager=km
        )
        self.download_worker.progress.connect(self._on_download_progress)
        self.download_worker.statsUpdate.connect(self._on_download_stats)
        self.download_worker.cooldownStart.connect(self._on_cooldown_start)
        self.download_worker.cooldownTick.connect(self._on_cooldown_tick)
        self.download_worker.cooldownEnd.connect(self._on_cooldown_end)
        self.download_worker.finished_signal.connect(self._on_download_finished)
        self.download_worker.start()
    
    def _on_download_progress(self, message, current, total):
        # Save current progress for combined display
        self._last_progress = (message, current, total)
        self._update_status_display()
        
        # Update status panel
        if hasattr(self, 'status_panel'):
            self.status_panel.set_progress(current, total, message)
    
    def _on_download_stats(self, stats):
        """Update anti-block stats"""
        self._last_stats = stats
        self._update_status_display()
        
        # Update status panel
        if hasattr(self, 'status_panel'):
            self.status_panel.set_stats(
                delay=stats.get("delay"),
                fail_rate=stats.get("fail_rate"),
                blocks=stats.get("blocks"),
                via_refresh=stats.get("via_refresh")
            )
    
    def _on_cooldown_start(self, seconds):
        """Block detected - cooldown started"""
        self._in_cooldown = True
        self._cooldown_remaining = seconds
        self._update_status_display()
        
        # Update status panel
        if hasattr(self, 'status_panel'):
            self.status_panel.set_cooldown(seconds)
        
        # Also show message box
        QMessageBox.warning(self, "🚫 BLOCK DETECTED",
                              f"Đã phát hiện IP block (5 lần 403 liên tiếp).\n\n"
                              f"App sẽ tự pause {seconds // 60} phút để IP cool down.\n\n"
                              f"Bạn có thể click STOP nếu muốn dừng.")
    
    def _on_cooldown_tick(self, remaining):
        self._cooldown_remaining = remaining
        self._update_status_display()
        if hasattr(self, 'status_panel'):
            self.status_panel.set_cooldown(remaining)
    
    def _on_cooldown_end(self):
        self._in_cooldown = False
        self._update_status_display()
        if hasattr(self, 'status_panel'):
            self.status_panel.end_cooldown()
    
    def _update_status_display(self):
        """Build status bar message from progress + stats + cooldown"""
        parts = []
        
        # Cooldown takes priority
        if getattr(self, '_in_cooldown', False):
            remaining = getattr(self, '_cooldown_remaining', 0)
            m = remaining // 60
            s = remaining % 60
            self.status_bar.showMessage(f"🚫 BLOCK DETECTED • Cooldown {m}:{s:02d} còn lại...")
            return
        
        # Progress
        if hasattr(self, '_last_progress'):
            msg, current, total = self._last_progress
            if total > 0:
                parts.append(f"⬇ {current}/{total}")
        
        # Stats
        if hasattr(self, '_last_stats'):
            s = self._last_stats
            delay = s.get("delay", 0)
            fail_rate = s.get("fail_rate", 0)
            blocks = s.get("blocks", 0)
            via_refresh = s.get("via_refresh", 0)
            
            # Delay indicator
            if delay > 1.5:
                parts.append(f"Delay: {delay:.1f}s ↑")  # tăng
            elif delay < 0.7:
                parts.append(f"Delay: {delay:.1f}s ↓")  # giảm
            else:
                parts.append(f"Delay: {delay:.1f}s")
            
            # Fail rate
            success_pct = (1 - fail_rate) * 100
            if fail_rate > 0.2:
                parts.append(f"⚠ Success: {success_pct:.0f}%")
            else:
                parts.append(f"Success: {success_pct:.0f}%")
            
            if via_refresh > 0:
                parts.append(f"Refreshed: {via_refresh}")
            
            if blocks > 0:
                parts.append(f"Blocks: {blocks}")
        
        if parts:
            self.status_bar.showMessage(" • ".join(parts))
    
    def _on_download_finished(self, success, fail, project_dir, error_breakdown):
        self.search_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setText("⏹ DỪNG")
        self._in_cooldown = False
        
        # Update status panel
        if hasattr(self, 'status_panel'):
            if project_dir:
                self.status_panel.set_done(success, fail)
            else:
                self.status_panel.set_stopped()
        
        # Refresh download monitor ngay sau khi tải xong
        if hasattr(self, '_refresh_download_monitor'):
            self._refresh_download_monitor()
        
        if project_dir:
            # Build summary
            total = success + fail
            success_pct = (success / total * 100) if total > 0 else 0
            
            msg = f"✅ Tải xong!\n\n"
            msg += f"Thành công: {success}/{total} ({success_pct:.1f}%)\n"
            msg += f"Lỗi: {fail}\n\n"
            
            if error_breakdown:
                msg += "Chi tiết lỗi:\n"
                for err_type, count in sorted(error_breakdown.items(), key=lambda x: -x[1]):
                    msg += f"  • {err_type}: {count}\n"
                msg += "\n"
            
            msg += f"Folder:\n{project_dir}"
            
            QMessageBox.information(self, "Done", msg)
            self.status_bar.showMessage(f"✓ Done: {success} OK, {fail} fail")
            
            try:
                if os.name == 'nt':
                    os.startfile(project_dir)
            except Exception:
                pass
        else:
            self.status_bar.showMessage("❌ Download failed hoặc đã dừng")
        if getattr(self, "_workflow_waiting_for", None) == "Download selected":
            self._workflow_waiting_for = None
            if hasattr(self, "workflow_log"):
                self.workflow_log.appendPlainText("Download selected: xong, chạy node tiếp theo")
            self._workflow_continue()
    
    def closeEvent(self, event):
        self.thumb_loader.shutdown()
        try:
            self.downloads_watcher.stop()
        except Exception:
            pass
        self._save_app_state()
        super().closeEvent(event)
    
    def keyPressEvent(self, event):
        """F11: toggle fullscreen, F5: refresh grid"""
        if event.key() == Qt.Key.Key_F11:
            if self.isFullScreen():
                self.showNormal()
            else:
                self.showFullScreen()
        elif event.key() == Qt.Key.Key_F5:
            self._render_grid()
        else:
            super().keyPressEvent(event)


# ═══════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════

def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    
    # Force dark style
    app.setStyle("Fusion")
    
    # === GLOBAL EXCEPTION HANDLER ===
    # Ngăn app crash silently khi có lỗi không bắt được
    def excepthook(exc_type, exc_value, exc_tb):
        import traceback
        tb_text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        print("=" * 60)
        print("[GLOBAL CRASH]")
        print(tb_text)
        print("=" * 60)
        
        try:
            from PyQt6.QtWidgets import QMessageBox
            # Hiển thị message box thay vì crash
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Icon.Critical)
            msg.setWindowTitle("Lỗi không mong đợi")
            msg.setText(f"{exc_type.__name__}: {exc_value}")
            # Detailed text trong "Show Details"
            msg.setDetailedText(tb_text)
            msg.exec()
        except Exception:
            # Nếu QMessageBox cũng lỗi, ít nhất print ra console
            pass
    
    sys.excepthook = excepthook
    
    window = StockPreviewWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
