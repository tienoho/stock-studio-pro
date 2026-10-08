"""
Interfaces for rate limiting and blocking prevention.
"""

from abc import ABC, abstractmethod
from typing import Tuple


class IRateLimiter(ABC):
    """Abstract rate limiter interface."""

    @abstractmethod
    def get_delay(self) -> float:
        """Get the current sleep delay with jitter."""
        pass

    @abstractmethod
    def record_result(self, success: bool) -> None:
        """Record whether a request succeeded or failed."""
        pass

    @abstractmethod
    def get_stats(self) -> Tuple[float, float, int]:
        """Return (current_delay, fail_rate, sample_size)."""
        pass


class IBlockDetector(ABC):
    """Abstract detector for 403 blocks."""

    @abstractmethod
    def record_403(self) -> bool:
        """Record a 403 response. Returns True if cooldown should be triggered."""
        pass

    @abstractmethod
    def record_success(self) -> None:
        """Reset consecutive 403 counter on success."""
        pass

    @abstractmethod
    def get_block_count(self) -> int:
        """Total times a block was detected."""
        pass
