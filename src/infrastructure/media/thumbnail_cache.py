"""
Thumbnail cache and image drawing utilities.
"""

import hashlib
import threading
import time
from pathlib import Path
from typing import Optional
import requests
from PyQt6.QtGui import (
    QPixmap, QPainter, QFont, QFontMetrics, QBrush, QColor
)
from PyQt6.QtCore import Qt

from ..network.rate_limiter import get_random_ua
from ...core.models.scene import format_duration
from ...core.constants import CACHE_DIR


def add_duration_to_pixmap(pixmap: QPixmap, duration_seconds: float) -> QPixmap:
    """Add a sleek semi-transparent duration overlay badge on the bottom right."""
    if not duration_seconds or pixmap is None or pixmap.isNull():
        return pixmap

    text = format_duration(duration_seconds)
    if not text or text == "?":
        return pixmap

    result = QPixmap(pixmap)
    painter = QPainter(result)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

    font = QFont("Segoe UI", 10, QFont.Weight.Bold)
    painter.setFont(font)
    metrics = QFontMetrics(font)
    text_w = metrics.horizontalAdvance(text)
    text_h = metrics.height()

    margin = 6
    padding_x = 6
    padding_y = 3

    box_w = text_w + padding_x * 2
    box_h = text_h + padding_y * 2
    box_x = result.width() - box_w - margin
    box_y = result.height() - box_h - margin

    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QBrush(QColor(0, 0, 0, 200)))
    painter.drawRoundedRect(box_x, box_y, box_w, box_h, 4, 4)

    painter.setPen(QColor(255, 255, 255))
    text_x = box_x + padding_x
    text_y = box_y + padding_y + text_h - metrics.descent()
    painter.drawText(text_x, text_y, text)

    painter.end()
    return result


class ThumbnailCache:
    """Manages disk and in-memory caching of thumbnail images."""

    def __init__(self, cache_dir: Path = CACHE_DIR, max_memory_entries: int = 250):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._pixmap_cache = {}
        self._max_memory_entries = max_memory_entries
        self._session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=10,
            pool_maxsize=10,
            max_retries=0
        )
        self._session.mount('http://', adapter)
        self._session.mount('https://', adapter)

    def get_cache_path(self, url: str) -> Path:
        url_hash = hashlib.md5(url.encode()).hexdigest()
        return self.cache_dir / f"{url_hash}.jpg"

    def get_pixmap(self, url: str) -> Optional[QPixmap]:
        with self._lock:
            if url in self._pixmap_cache:
                return self._pixmap_cache[url]

        cache_path = self.get_cache_path(url)
        if cache_path.exists():
            try:
                pixmap = QPixmap(str(cache_path))
                if not pixmap.isNull():
                    with self._lock:
                        if len(self._pixmap_cache) >= self._max_memory_entries:
                            first_key = next(iter(self._pixmap_cache))
                            del self._pixmap_cache[first_key]
                        self._pixmap_cache[url] = pixmap
                    return pixmap
            except Exception:
                pass
        return None

    def get(self, url: str) -> Optional[QPixmap]:
        """Convenience alias for get_pixmap."""
        return self.get_pixmap(url)

    def fetch_pixmap(self, url: str, max_retries: int = 3) -> Optional[QPixmap]:
        existing = self.get_pixmap(url)
        if existing is not None:
            return existing

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

        if "pexels.com" in url or "pexelscdn.com" in url:
            headers["Referer"] = "https://www.pexels.com/"
            headers["Origin"] = "https://www.pexels.com"
        elif "pixabay.com" in url or "pixabaycdn.com" in url:
            headers["Referer"] = "https://pixabay.com/"
            headers["Origin"] = "https://pixabay.com"
        elif "coverr.co" in url or "storage.coverr.co" in url:
            headers["Referer"] = "https://coverr.co/"
            headers["Origin"] = "https://coverr.co"
        elif "wikimedia.org" in url:
            headers["Referer"] = "https://commons.wikimedia.org/"
        elif "openverse.org" in url:
            headers["Referer"] = "https://openverse.org/"
        elif "motionarray.com" in url or "motionarray.imgix.net" in url:
            headers["Referer"] = "https://motionarray.com/"
            headers["Origin"] = "https://motionarray.com"

        retry_delays = [1.0, 2.5, 5.0]

        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    time.sleep(retry_delays[min(attempt - 1, len(retry_delays) - 1)])

                r = self._session.get(
                    url,
                    headers=headers,
                    timeout=(10, 30),
                    allow_redirects=True
                )

                if r.status_code == 200:
                    img_data = r.content
                    if len(img_data) < 500:
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
                        with self._lock:
                            if len(self._pixmap_cache) >= self._max_memory_entries:
                                first_key = next(iter(self._pixmap_cache))
                                del self._pixmap_cache[first_key]
                            self._pixmap_cache[url] = pixmap
                        return pixmap
                    continue
                elif r.status_code in (403, 404):
                    if attempt == 0:
                        continue
                    return None
            except Exception:
                continue

        return None
