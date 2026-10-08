"""
Pixabay API Provider implementing IMediaProvider.
"""

from typing import List, Dict, Any, Optional, Tuple
import requests
from ...core.interfaces.media_provider import IMediaProvider


class PixabayProvider(IMediaProvider):
    API_URL = "https://pixabay.com/api/"
    VIDEO_URL = "https://pixabay.com/api/videos/"

    def __init__(self, key_manager=None):
        self.km = key_manager

    @property
    def platform_name(self) -> str:
        return "pixabay"

    def _get_key(self):
        return self.km.get_pixabay_key() if self.km else None

    def search_photos(self, query: str, per_page: int = 30) -> List[Dict[str, Any]]:
        max_attempts = max(1, len(self.km.pixabay_keys)) if (self.km and self.km.pixabay_keys) else 1

        for _ in range(max_attempts):
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
                if r.status_code in (429, 401, 403) and self.km and len(self.km.pixabay_keys) > 1:
                    continue
                if r.status_code != 200:
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
                print(f"[PixabayProvider] search_photos error: {e}")
                return []
        return []

    def search_videos(self, query: str, per_page: int = 30) -> List[Dict[str, Any]]:
        max_attempts = max(1, len(self.km.pixabay_keys)) if (self.km and self.km.pixabay_keys) else 1

        for _ in range(max_attempts):
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
                if r.status_code in (429, 401, 403) and self.km and len(self.km.pixabay_keys) > 1:
                    continue
                if r.status_code != 200:
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
                print(f"[PixabayProvider] search_videos error: {e}")
                return []
        return []

    def refresh_video_url(self, item_id: str, old_url: str = "") -> Optional[str]:
        # Pixabay URLs are usually refreshed by searching or querying the hit
        key = self._get_key()
        if not key:
            return None
        try:
            r = requests.get(self.VIDEO_URL, params={"key": key.key, "id": item_id}, timeout=15)
            key.record_request()
            if r.status_code == 200:
                hits = r.json().get("hits", [])
                if hits:
                    videos = hits[0].get("videos", {})
                    best = videos.get("large") or videos.get("medium") or videos.get("small")
                    if best:
                        return best.get("url")
        except Exception:
            pass
        return None

    def test_key(self, key_str: str) -> Tuple[bool, str]:
        try:
            r = requests.get(self.API_URL, params={"key": key_str, "q": "test", "per_page": 3}, timeout=10)
            if r.status_code == 200:
                return True, "Key valid"
            if r.status_code == 429:
                return True, "Quota exceeded but valid"
            return False, f"HTTP {r.status_code}: {r.text[:60]}"
        except Exception as e:
            return False, str(e)[:50]
