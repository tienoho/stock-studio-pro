"""
API Key model with rate limit tracking per platform.
"""

from collections import deque
import time
from typing import Dict, Any, Optional
from ..constants import (
    PEXELS_LIMIT_PER_HOUR,
    PIXABAY_LIMIT_PER_MINUTE,
)


class APIKey:
    """Represents an API key with usage tracking."""
    def __init__(self, name: str, key: str, platform: str, id: Optional[int] = None):
        self.id = id
        self.name = name
        self.key = key
        self.platform = platform.lower()
        self.request_history: deque = deque()
        self.is_dead: bool = False
        self.total_requests: int = 0

    def can_use(self) -> bool:
        """Check if this key can currently make a request under platform rate limits."""
        if self.is_dead:
            return False

        now = time.time()
        if self.platform == "pexels":
            window_start = now - 3600
            recent = [t for t in self.request_history if t > window_start]
            self.request_history = deque(recent)
            return len(recent) < PEXELS_LIMIT_PER_HOUR
        elif self.platform == "pixabay":
            window_start = now - 60
            recent = [t for t in self.request_history if t > window_start]
            self.request_history = deque(recent)
            return len(recent) < PIXABAY_LIMIT_PER_MINUTE
        elif self.platform == "coverr":
            window_start = now - 3600
            recent = [t for t in self.request_history if t > window_start]
            self.request_history = deque(recent)
            return len(recent) < 50
        elif self.platform == "vecteezy":
            window_start = now - 60
            recent = [t for t in self.request_history if t > window_start]
            self.request_history = deque(recent)
            return len(recent) < 120

        return True

    def record_request(self) -> None:
        """Record a successful or attempted API request."""
        self.request_history.append(time.time())
        self.total_requests += 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "key": self.key,
            "platform": self.platform,
        }
