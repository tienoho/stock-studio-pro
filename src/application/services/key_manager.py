"""
Service managing multiple API keys with round-robin rotation and limits.
"""

import threading
from typing import List, Optional, Dict, Any
from ...core.models.api_key import APIKey


class KeyManager:
    """Thread-safe multi-platform API key manager."""

    def __init__(
        self,
        pexels_keys: List[Dict[str, Any]],
        pixabay_keys: List[Dict[str, Any]],
        coverr_keys: Optional[List[Dict[str, Any]]] = None,
        vecteezy_keys: Optional[List[Dict[str, Any]]] = None,
        config_repo: Optional[Any] = None,
    ):
        self.config_repo = config_repo
        self.pexels_keys = [
            APIKey(k.get("name", f"Pexels {i+1}"), k["key"], "pexels", id=k.get("id"))
            for i, k in enumerate(pexels_keys or [])
            if k.get("key") and k.get("is_active", 1) in (1, True, "1")
        ]
        self.pixabay_keys = [
            APIKey(k.get("name", f"Pixabay {i+1}"), k["key"], "pixabay", id=k.get("id"))
            for i, k in enumerate(pixabay_keys or [])
            if k.get("key") and k.get("is_active", 1) in (1, True, "1")
        ]
        self.coverr_keys = [
            APIKey(k.get("name", f"Coverr {i+1}"), k["key"], "coverr", id=k.get("id"))
            for i, k in enumerate(coverr_keys or [])
            if k.get("key") and k.get("is_active", 1) in (1, True, "1")
        ]
        self.vecteezy_keys = [
            APIKey(k.get("name", f"Vecteezy {i+1}"), k["key"], "vecteezy", id=k.get("id"))
            for i, k in enumerate(vecteezy_keys or [])
            if k.get("key") and k.get("is_active", 1) in (1, True, "1")
        ]


        self.pexels_idx = 0
        self.pixabay_idx = 0
        self.coverr_idx = 0
        self.vecteezy_idx = 0
        self._lock = threading.Lock()

    def _record_key_activity(self, key: APIKey):
        if self.config_repo and key.id and hasattr(self.config_repo, "update_key_last_used"):
            try:
                self.config_repo.update_key_last_used(key.id)
            except Exception:
                pass

    def get_pexels_key(self) -> Optional[APIKey]:
        with self._lock:
            if not self.pexels_keys:
                return None
            for _ in range(len(self.pexels_keys)):
                key = self.pexels_keys[self.pexels_idx]
                self.pexels_idx = (self.pexels_idx + 1) % len(self.pexels_keys)
                if key.can_use():
                    self._record_key_activity(key)
                    return key
            return None

    def get_pixabay_key(self) -> Optional[APIKey]:
        with self._lock:
            if not self.pixabay_keys:
                return None
            for _ in range(len(self.pixabay_keys)):
                key = self.pixabay_keys[self.pixabay_idx]
                self.pixabay_idx = (self.pixabay_idx + 1) % len(self.pixabay_keys)
                if key.can_use():
                    self._record_key_activity(key)
                    return key
            return None

    def get_vecteezy_key(self) -> Optional[APIKey]:
        with self._lock:
            if not self.vecteezy_keys:
                return None
            for _ in range(len(self.vecteezy_keys)):
                key = self.vecteezy_keys[self.vecteezy_idx]
                self.vecteezy_idx = (self.vecteezy_idx + 1) % len(self.vecteezy_keys)
                if key.can_use():
                    self._record_key_activity(key)
                    return key
            return None

    def get_coverr_key(self) -> Optional[APIKey]:
        with self._lock:
            if not self.coverr_keys:
                return None
            for _ in range(len(self.coverr_keys)):
                key = self.coverr_keys[self.coverr_idx]
                self.coverr_idx = (self.coverr_idx + 1) % len(self.coverr_keys)
                if key.can_use():
                    self._record_key_activity(key)
                    return key
            return None

    def get_next_key(self, platform: str) -> Optional[str]:
        """Convenience method returning the raw key string for a given platform."""
        p = platform.lower()
        if "pexels" in p:
            k = self.get_pexels_key()
        elif "pixabay" in p:
            k = self.get_pixabay_key()
        elif "vecteezy" in p:
            k = self.get_vecteezy_key()
        elif "coverr" in p:
            k = self.get_coverr_key()
        else:
            k = None
        return k.key if k else None
