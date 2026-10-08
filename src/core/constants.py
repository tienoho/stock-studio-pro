"""
Constants for AutoStock Studio.
"""

from pathlib import Path

APP_VERSION = "1.0"
APP_NAME = "AutoStock Studio"

# GitHub repository & auto-update
GITHUB_REPO_OWNER = "tienoho"
GITHUB_REPO_NAME = "stock-studio-pro"
GITHUB_RELEASES_URL = f"https://github.com/{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}/releases"
GITHUB_API_LATEST_RELEASE = f"https://api.github.com/repos/{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}/releases/latest"

# Storage paths
DB_FILE = Path.home() / ".autostock_studio.db"
LEGACY_DB_FILE = Path.home() / ".stock_studio_pro.db"
CONFIG_FILE = Path.home() / ".stock_preview_v4_config.json"
STATE_FILE = Path.home() / ".stock_preview_v4_state.pkl"
CACHE_DIR = Path.home() / ".stock_preview_cache_v4"
VIDEO_CACHE_DIR = CACHE_DIR / "videos"
DEFAULT_OUTPUT_DIR = Path.home() / "Downloads" / "Stock_Media_Output"

# UI Grid layout
GRID_COLS = 4
GRID_ROWS = 5
ITEMS_PER_PAGE = GRID_COLS * GRID_ROWS

THUMB_WIDTH = 180
THUMB_HEIGHT = 115
CARD_WIDTH = THUMB_WIDTH + 16
CARD_HEIGHT = THUMB_HEIGHT + 90

# Stat gradient colors
STAT_COLOR_BLUE = "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #1e3a8a, stop:1 #1d4ed8)"
STAT_COLOR_PURPLE = "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #4c1d95, stop:1 #6d28d9)"
STAT_COLOR_RED = "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #831843, stop:1 #be123c)"
STAT_COLOR_GREEN = "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #064e3b, stop:1 #047857)"

# API limits & pagination
PEXELS_LIMIT_PER_HOUR = 200
PIXABAY_LIMIT_PER_MINUTE = 100
RESULTS_PER_KEYWORD = 30
MAX_KEYWORDS_PER_SCENE = 5

# Anti-block & rate limiting settings
MIN_DOWNLOAD_DELAY = 0.5
MAX_DOWNLOAD_DELAY = 3.0
DEFAULT_DOWNLOAD_DELAY = 0.8
DELAY_JITTER = 0.2

BLOCK_DETECTION_THRESHOLD = 5
BLOCK_COOLDOWN_SECONDS = 300  # 5 minutes

DELAY_INCREASE_THRESHOLD = 0.3
DELAY_DECREASE_THRESHOLD = 0.1

MAX_RETRIES = 3
RETRY_DELAYS = [1, 2, 4]

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
]
