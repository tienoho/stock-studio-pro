"""
Pexels API Provider implementing IMediaProvider.
"""

from typing import List, Dict, Any, Optional, Tuple
import requests
from ...core.interfaces.media_provider import IMediaProvider


class PexelsProvider(IMediaProvider):
    VIDEOS_URL = "https://api.pexels.com/videos"
    PHOTOS_URL = "https://api.pexels.com/v1"

    def __init__(self, key_manager=None):
        self.km = key_manager

    @property
    def platform_name(self) -> str:
        return "pexels"

    def _get_key(self):
        return self.km.get_pexels_key() if self.km else None

    def _best_video(self, files: list) -> Optional[dict]:
        if not files:
            return None
        mp4 = [f for f in files if f.get("file_type") == "video/mp4"]
        files = mp4 if mp4 else files
        files = sorted(files, key=lambda f: (f.get("width", 0) * f.get("height", 0)), reverse=True)
        return files[0] if files else None

    def search_videos(self, query: str, per_page: int = 30) -> List[Dict[str, Any]]:
        url = f"{self.VIDEOS_URL}/search"
        params = {"query": query, "per_page": per_page, "orientation": "landscape"}
        max_attempts = max(1, len(self.km.pexels_keys)) if (self.km and self.km.pexels_keys) else 1

        for _ in range(max_attempts):
            key = self._get_key()
            if self.km and not key:
                return []

            headers = {"Authorization": key.key if key else ""}
            try:
                r = requests.get(url, headers=headers, params=params, timeout=15)
                if key:
                    key.record_request()
                if r.status_code in (429, 401, 403) and self.km and len(self.km.pexels_keys) > 1:
                    continue
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
                        "id": v.get("id", ""),
                        "thumb_url": thumb_url,
                        "download_url": best.get("link", ""),
                        "width": best.get("width", 0),
                        "height": best.get("height", 0),

                        "duration": v.get("duration", 0),
                        "author": v.get("user", {}).get("name", "Unknown"),
                        "author_url": v.get("user", {}).get("url", ""),
                        "page_url": v.get("url", ""),
                        "search_query": query,
                    })
                return items
            except Exception as e:
                print(f"[PexelsProvider] search_videos error: {e}")
                return []
        return []

    def search_photos(self, query: str, per_page: int = 30) -> List[Dict[str, Any]]:
        url = f"{self.PHOTOS_URL}/search"
        params = {"query": query, "per_page": per_page, "orientation": "landscape"}
        max_attempts = max(1, len(self.km.pexels_keys)) if (self.km and self.km.pexels_keys) else 1

        for _ in range(max_attempts):
            key = self._get_key()
            if self.km and not key:
                return []

            headers = {"Authorization": key.key if key else ""}
            try:
                r = requests.get(url, headers=headers, params=params, timeout=15)
                if key:
                    key.record_request()
                if r.status_code in (429, 401, 403) and self.km and len(self.km.pexels_keys) > 1:
                    continue
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
                print(f"[PexelsProvider] search_photos error: {e}")
                return []
        return []

    def refresh_video_url(self, item_id: str, old_url: str = "") -> Optional[str]:
        key = self._get_key()
        if not key:
            return None
        try:
            url = f"{self.VIDEOS_URL}/videos/{item_id}"
            headers = {"Authorization": key.key}
            r = requests.get(url, headers=headers, timeout=15)
            key.record_request()
            if r.status_code == 200:
                v = r.json()
                best = self._best_video(v.get("video_files", []))
                if best:
                    return best["link"]
        except Exception:
            pass
        return None

    def test_key(self, key_str: str) -> Tuple[bool, str]:
        try:
            r = requests.get(
                f"{self.VIDEOS_URL}/search",
                headers={"Authorization": key_str},
                params={"query": "test", "per_page": 1},
                timeout=10
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
