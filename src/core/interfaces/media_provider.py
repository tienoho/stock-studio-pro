"""
Interface contract for media providers (Pexels, Pixabay, Vecteezy, etc.).
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from ..models.media import MediaItem


class IMediaProvider(ABC):
    """Abstract interface for all stock media providers."""

    @property
    @abstractmethod
    def platform_name(self) -> str:
        """Name of the platform, e.g. 'pexels', 'pixabay'."""
        pass

    @abstractmethod
    def search_videos(self, query: str, per_page: int = 30) -> List[Dict[str, Any]]:
        """Search videos by keyword."""
        pass

    @abstractmethod
    def search_photos(self, query: str, per_page: int = 30) -> List[Dict[str, Any]]:
        """Search photos by keyword."""
        pass

    @abstractmethod
    def test_key(self, key: str) -> bool:
        """Validate if the given key is active and functional."""
        pass

    @abstractmethod
    def refresh_video_url(self, item_id: str, old_url: str = "") -> Optional[str]:
        """Fetch a fresh direct download URL if the old one expired or received 403."""
        pass
