"""
Vecteezy API Provider implementing IMediaProvider.
"""

from typing import List, Dict, Any, Optional, Tuple
import requests
from ...core.interfaces.media_provider import IMediaProvider


class VecteezyProvider(IMediaProvider):
    API_URL = "https://www.vecteezy.com/v1/resources"

    def __init__(self, key_manager=None):
        self.km = key_manager

    @property
    def platform_name(self) -> str:
        return "vecteezy"

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
            r = requests.get(
                f"{self.API_URL}/{resource_id}/download",
                headers=self._headers(key),
                params=params,
                timeout=20
            )
            if key:
                key.record_request()
            if r.status_code != 200:
                return ""
            data = r.json()
            return data.get("url") or data.get("inline_url") or ""
        except Exception as e:
            print(f"[VecteezyProvider] download_url error: {e}")
            return ""

    def _search(self, query: str, content_type: str, per_page: int = 30) -> List[Dict[str, Any]]:
        clean_query = str(query).strip()
        if not clean_query:
            return []
        max_attempts = max(1, len(self.km.vecteezy_keys)) if (self.km and self.km.vecteezy_keys) else 1

        for _ in range(max_attempts):
            key = self._get_key()
            if self.km and not key:
                return []
            params = {
                "term": clean_query,
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
                if r.status_code == 401 and key:
                    key.is_dead = True
                if r.status_code in (401, 403, 429) and self.km and len(self.km.vecteezy_keys) > 1:
                    continue
                if r.status_code != 200:
                    return []
                items = []
                for res in r.json().get("resources", []):
                    rid = res.get("id")
                    if not rid:
                        continue
                    thumb_url = (
                        res.get("thumbnail_url")
                        or res.get("thumbnail_2x_url")
                        or res.get("preview_url")
                        or res.get("preview_2x_url")
                        or ""
                    )
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
                        "width": width or 0,
                        "height": height or 0,
                        "duration": res.get("duration") or 0,
                        "author": "Vecteezy",
                        "author_url": "https://www.vecteezy.com/",
                        "page_url": res.get("url") or res.get("link") or "",
                        "search_query": clean_query,
                    })
                return items
            except Exception as e:
                print(f"[VecteezyProvider] search_{content_type} error: {e}")
                return []
        return []

    def search_photos(self, query: str, per_page: int = 30) -> List[Dict[str, Any]]:
        return self._search(query, "photo", per_page)

    def search_videos(self, query: str, per_page: int = 30) -> List[Dict[str, Any]]:
        return self._search(query, "video", per_page)

    def refresh_video_url(self, item_id: str, old_url: str = "") -> Optional[str]:
        key = self._get_key()
        if not key:
            return None
        return self._download_url(item_id, "video", key)

    def test_key(self, key_str: str) -> Tuple[bool, str]:
        try:
            r = requests.get(
                self.API_URL,
                headers={"Authorization": f"Bearer {key_str}", "Accept": "application/json"},
                params={"term": "test", "content_type": "photo", "per_page": 1},
                timeout=12
            )
            if r.status_code == 200:
                return True, "Key valid"
            if r.status_code in (402, 429):
                return True, "Quota exceeded but valid"
            if r.status_code == 401:
                return False, "Key invalid"
            return False, f"HTTP {r.status_code}: {r.text[:60]}"
        except Exception as e:
            return False, str(e)[:50]
