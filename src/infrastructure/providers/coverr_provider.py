"""
Coverr API Provider implementing IMediaProvider.
Free stock video footage with Coverr API key.
"""

from typing import List, Dict, Any, Optional, Tuple
import requests

from ...core.interfaces.media_provider import IMediaProvider
from ...infrastructure.network.rate_limiter import get_random_ua


class CoverrProvider(IMediaProvider):
    """Media provider for Coverr free stock videos."""

    API_URL = "https://api.coverr.co/videos"

    def __init__(self, key_manager=None):
        self.km = key_manager

    @property
    def platform_name(self) -> str:
        return "coverr"

    def _get_key(self):
        return self.km.get_coverr_key() if self.km else None

    def search_videos(self, query: str, per_page: int = 30) -> List[Dict[str, Any]]:
        import re
        clean_query = re.sub(r"[\r\n\t]+", " ", str(query)).strip()[:100]
        if not clean_query:
            return []

        key = self._get_key()
        headers = {
            "User-Agent": get_random_ua(),
            "Accept": "application/json",
        }
        if key and key.key:
            headers["Authorization"] = f"Bearer {key.key}"

        params = {
            "query": clean_query,
            "page": 1,
            "urls": "true"
        }

        try:
            r = requests.get(self.API_URL, params=params, headers=headers, timeout=15)
            if key:
                key.record_request()
            if r.status_code == 401 and key:
                key.is_dead = True
                return []
            if r.status_code != 200:
                return []

            data = r.json()
            hits = data.get("hits", [])
            items: List[Dict[str, Any]] = []

            for h in hits:
                urls = h.get("urls") or {}
                download_url = urls.get("mp4_download") or urls.get("mp4") or h.get("download_url") or ""
                if not download_url:
                    continue

                thumb_url = h.get("poster") or h.get("thumbnail") or ""
                item_id = str(h.get("id", ""))
                duration = float(h.get("duration") or 0)
                width = int(h.get("width") or 1920)
                height = int(h.get("height") or 1080)

                items.append({
                    "source": "coverr",
                    "type": "video",
                    "id": item_id,
                    "thumb_url": thumb_url,
                    "download_url": download_url,
                    "width": width,
                    "height": height,
                    "duration": duration,
                    "author": "Coverr Creator",
                    "author_url": "https://coverr.co/",
                    "page_url": f"https://coverr.co/videos/{item_id}",
                    "search_query": clean_query,
                })

            return items
        except Exception as e:
            print(f"[CoverrProvider] search_videos error: {e}")
            return []

    def search_photos(self, query: str, per_page: int = 30) -> List[Dict[str, Any]]:
        return []

    def test_key(self, key_str: str) -> Tuple[bool, str]:
        try:
            r = requests.get(
                self.API_URL,
                headers={"Authorization": f"Bearer {key_str}", "User-Agent": get_random_ua()},
                params={"query": "nature", "page": 1},
                timeout=12
            )
            if r.status_code == 200:
                return True, "Coverr API Key hợp lệ!"
            elif r.status_code == 401:
                return False, "Coverr API Key không đúng hoặc hết hạn"
            return False, f"Lỗi phản hồi HTTP {r.status_code}"
        except Exception as e:
            return False, f"Lỗi kết nối Coverr: {e}"

    def refresh_video_url(self, item_id: str, old_url: str = "") -> Optional[str]:
        return old_url or None
