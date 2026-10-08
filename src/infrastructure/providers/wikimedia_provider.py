"""
Wikimedia Commons API Provider implementing IMediaProvider.
100% Free, Public Domain and Creative Commons stock media (Photos & Videos).
No API key required.
"""

import re
from typing import List, Dict, Any, Optional, Tuple
import requests

from ...core.interfaces.media_provider import IMediaProvider
from ...infrastructure.network.rate_limiter import get_random_ua


class WikimediaProvider(IMediaProvider):
    """Media provider connecting to Wikimedia Commons open repository."""

    API_URL = "https://commons.wikimedia.org/w/api.php"

    def __init__(self, key_manager=None):
        self.km = key_manager

    @property
    def platform_name(self) -> str:
        return "wikimedia"

    def _get_headers(self) -> Dict[str, str]:
        return {
            "User-Agent": "StockStudioPro/2.5 (https://github.com/stock-studio-pro; contact@example.com) " + get_random_ua()
        }

    def _search(self, query: str, content_type: str, per_page: int = 30) -> List[Dict[str, Any]]:
        clean_query = re.sub(r"[\r\n\t]+", " ", str(query)).strip()[:120]
        if not clean_query:
            return []

        is_video = content_type == "video"
        gsrsearch = f"filetype:video {clean_query}" if is_video else f"filetype:bitmap {clean_query}"

        params = {
            "action": "query",
            "generator": "search",
            "gsrsearch": gsrsearch,
            "gsrnamespace": 6,  # File namespace
            "gsrlimit": min(max(per_page, 1), 50),
            "prop": "imageinfo",
            "iiprop": "url|size|mime|extmetadata",
            "iiurlwidth": 500,
            "format": "json",
        }

        try:
            r = requests.get(self.API_URL, params=params, headers=self._get_headers(), timeout=15)
            if r.status_code != 200:
                return []

            data = r.json()
            pages = data.get("query", {}).get("pages", {})
            items: List[Dict[str, Any]] = []

            for page_id, page in pages.items():
                imageinfo = page.get("imageinfo", [])
                if not imageinfo:
                    continue
                info = imageinfo[0]
                url = info.get("url")
                if not url:
                    continue

                thumb_url = info.get("thumburl") or url
                width = int(info.get("width") or 0)
                height = int(info.get("height") or 0)

                metadata = info.get("extmetadata", {})
                artist_raw = metadata.get("Artist", {}).get("value", "Wikimedia Contributor")
                clean_artist = re.sub(r"<[^>]+>", "", str(artist_raw)).strip() or "Wikimedia Contributor"

                description_url = info.get("descriptionurl") or f"https://commons.wikimedia.org/?curid={page_id}"

                items.append({
                    "source": "wikimedia",
                    "type": "video" if is_video else "photo",
                    "id": str(page_id),
                    "thumb_url": thumb_url,
                    "download_url": url,
                    "width": width,
                    "height": height,
                    "duration": 0,
                    "author": clean_artist[:80],
                    "author_url": description_url,
                    "page_url": description_url,
                    "search_query": clean_query,
                })

            return items
        except Exception as e:
            print(f"[WikimediaProvider] Search error: {e}")
            return []

    def search_photos(self, query: str, per_page: int = 30) -> List[Dict[str, Any]]:
        return self._search(query, "photo", per_page)

    def search_videos(self, query: str, per_page: int = 30) -> List[Dict[str, Any]]:
        return self._search(query, "video", per_page)

    def test_key(self, key: str) -> Tuple[bool, str]:
        return True, "Wikimedia Commons là kho tài nguyên mở, hoàn toàn miễn phí không cần API Key!"

    def refresh_video_url(self, item_id: str, old_url: str = "") -> Optional[str]:
        return old_url or None
