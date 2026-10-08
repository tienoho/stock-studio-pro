"""
Adaptive rate limiter and block detector to prevent IP blocking.
"""

import threading
import random
from collections import deque
from typing import Tuple
from ...core.interfaces.rate_limiter import IRateLimiter, IBlockDetector
from ...core.constants import (
    MIN_DOWNLOAD_DELAY,
    MAX_DOWNLOAD_DELAY,
    DEFAULT_DOWNLOAD_DELAY,
    DELAY_JITTER,
    BLOCK_DETECTION_THRESHOLD,
    DELAY_INCREASE_THRESHOLD,
    DELAY_DECREASE_THRESHOLD,
    USER_AGENTS,
)


def get_random_ua() -> str:
    """Return a randomized standard browser user agent."""
    return random.choice(USER_AGENTS)


def get_jittered_delay(base_delay: float) -> float:
    """Add +/- 20% random jitter to delay."""
    jitter = random.uniform(-DELAY_JITTER, DELAY_JITTER) * base_delay
    return max(0.1, base_delay + jitter)


class AdaptiveRateLimiter(IRateLimiter):
    """Dynamically adjusts download delay based on recent success/fail rates."""

    def __init__(self, default_delay: float = DEFAULT_DOWNLOAD_DELAY):
        self.current_delay = default_delay
        self.recent_results: deque = deque(maxlen=10)
        self._lock = threading.Lock()

    def get_delay(self) -> float:
        with self._lock:
            return get_jittered_delay(self.current_delay)

    def record_result(self, success: bool) -> None:
        with self._lock:
            self.recent_results.append(success)
            if len(self.recent_results) < 5:
                return
            fail_rate = self.recent_results.count(False) / len(self.recent_results)
            if fail_rate > DELAY_INCREASE_THRESHOLD:
                self.current_delay = min(MAX_DOWNLOAD_DELAY, self.current_delay * 1.5)
            elif fail_rate < DELAY_DECREASE_THRESHOLD:
                self.current_delay = max(MIN_DOWNLOAD_DELAY, self.current_delay * 0.9)

    def record_success(self) -> None:
        self.record_result(True)

    def record_failure(self, _code=None) -> None:
        self.record_result(False)

    def get_stats(self) -> Tuple[float, float, int]:
        with self._lock:
            fail_rate = (
                self.recent_results.count(False) / len(self.recent_results)
                if self.recent_results
                else 0.0
            )
            return self.current_delay, fail_rate, len(self.recent_results)


class BlockDetector(IBlockDetector):
    """Detects consecutive 403 Forbidden errors to trigger temporary cooldown."""

    def __init__(self, threshold: int = BLOCK_DETECTION_THRESHOLD):
        self.threshold = threshold
        self.consecutive_403 = 0
        self.block_count = 0
        self._lock = threading.Lock()

    def record_403(self) -> bool:
        with self._lock:
            self.consecutive_403 += 1
            if self.consecutive_403 >= self.threshold:
                self.consecutive_403 = 0
                self.block_count += 1
                return True
        return False

    def record_success(self) -> None:
        with self._lock:
            self.consecutive_403 = 0

    def get_block_count(self) -> int:
        with self._lock:
            return self.block_count
