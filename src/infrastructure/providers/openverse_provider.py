"""
Openverse API Provider implementing IMediaProvider.
Maintained by WordPress.org, indexing 700M+ Creative Commons and Public Domain media.
No API key required.
"""

from typing import List, Dict, Any, Optional, Tuple
import requests

from ...core.interfaces.media_provider import IMediaProvider
from ...infrastructure.network.rate_limiter import get_random_ua


class OpenverseProvider(IMediaProvider):
    """Media provider connecting to Openverse Creative Commons index."""

    API_URL = "https://api.openverse.org/v1/images/"

    def __init__(self, key_manager=None):
        self.km = key_manager

    @property
    def platform_name(self) -> str:
        return "openverse"

    def _get_headers(self) -> Dict[str, str]:
        return {
            "User-Agent": "StockStudioPro/2.5 (https://github.com/stock-studio-pro; contact@example.com) " + get_random_ua()
        }

    def search_photos(self, query: str, per_page: int = 30) -> List[Dict[str, Any]]:
        clean_query = str(query).strip()
        if not clean_query:
            return []

        params = {
            "q": clean_query,
            "page_size": min(max(per_page, 1), 50),
        }

        try:
            r = requests.get(self.API_URL, params=params, headers=self._get_headers(), timeout=15)
            if r.status_code != 200:
                return []

            data = r.json()
            results = data.get("results", [])
            items: List[Dict[str, Any]] = []

            for it in results:
                url = it.get("url")
                if not url:
                    continue

                thumb_url = it.get("thumbnail") or url
                item_id = str(it.get("id", ""))
                author = it.get("creator") or "Creative Commons Contributor"
                author_url = it.get("creator_url") or ""
                page_url = it.get("foreign_landing_url") or f"https://openverse.org/image/{item_id}"

                items.append({
                    "source": "openverse",
                    "type": "photo",
                    "id": item_id,
                    "thumb_url": thumb_url,
                    "download_url": url,
                    "width": int(it.get("width") or 0),
                    "height": int(it.get("height") or 0),
                    "duration": 0,
                    "author": author[:80],
                    "author_url": author_url,
                    "page_url": page_url,
                    "search_query": clean_query,
                })

            return items
        except Exception as e:
            print(f"[OpenverseProvider] search_photos error: {e}")
            return []

    def search_videos(self, query: str, per_page: int = 30) -> List[Dict[str, Any]]:
        return []

    def test_key(self, key: str) -> Tuple[bool, str]:
        return True, "Openverse là kho ảnh mở (WordPress Foundation) - Hoàn toàn miễn phí không cần API Key!"

    def refresh_video_url(self, item_id: str, old_url: str = "") -> Optional[str]:
        return None
