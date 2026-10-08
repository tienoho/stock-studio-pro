"""
Media models representing stock assets.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, Any


class MediaType(str, Enum):
    VIDEO = "video"
    PHOTO = "photo"


class MediaSource(str, Enum):
    PEXELS = "pexels"
    PIXABAY = "pixabay"
    VECTEEZY = "vecteezy"
    MOTIONARRAY = "motionarray"


@dataclass
class MediaItem:
    """Represents a standardized stock media item (video or photo)."""
    id: str
    source: str
    type: str  # "video" or "photo"
    download_url: str
    thumbnail_url: str
    width: int = 0
    height: int = 0
    duration: float = 0.0
    title: str = ""
    author: str = ""
    search_query: str = ""
    scene_id: Optional[str] = None
    extra_data: Dict[str, Any] = field(default_factory=dict)

    @property
    def key(self) -> str:
        """Unique identifier key across sources."""
        return f"{self.source}_{self.type}_{self.id}"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for backward compatibility with existing components."""
        return {
            "id": self.id,
            "source": self.source,
            "type": self.type,
            "download_url": self.download_url,
            "thumbnail_url": self.thumbnail_url,
            "width": self.width,
            "height": self.height,
            "duration": self.duration,
            "title": self.title,
            "author": self.author,
            "search_query": self.search_query,
            "_scene_id": self.scene_id,
            **self.extra_data,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MediaItem":
        """Instantiate MediaItem from dictionary."""
        source = data.get("source", "unknown")
        m_type = data.get("type", "video")
        m_id = str(data.get("id", ""))
        download_url = data.get("download_url", "")
        thumbnail_url = data.get("thumbnail_url", "")
        width = int(data.get("width") or 0)
        height = int(data.get("height") or 0)
        duration = float(data.get("duration") or 0.0)
        title = data.get("title", "")
        author = data.get("author", "")
        search_query = data.get("search_query", "")
        scene_id = data.get("_scene_id") or data.get("scene_id")
        
        extra = {k: v for k, v in data.items() if k not in {
            "id", "source", "type", "download_url", "thumbnail_url",
            "width", "height", "duration", "title", "author", "search_query", "_scene_id", "scene_id"
        }}

        return cls(
            id=m_id,
            source=source,
            type=m_type,
            download_url=download_url,
            thumbnail_url=thumbnail_url,
            width=width,
            height=height,
            duration=duration,
            title=title,
            author=author,
            search_query=search_query,
            scene_id=str(scene_id) if scene_id is not None else None,
            extra_data=extra
        )
