"""
Tests for rate limiting and block detection in src.infrastructure.network.rate_limiter.
"""

import unittest
from src.infrastructure.network.rate_limiter import (
    AdaptiveRateLimiter, BlockDetector, get_random_ua, get_jittered_delay
)


class TestRateLimiter(unittest.TestCase):
    def test_random_user_agent(self):
        ua1 = get_random_ua()
        self.assertIsInstance(ua1, str)
        self.assertTrue(len(ua1) > 20)

    def test_jittered_delay(self):
        base = 1.0
        d = get_jittered_delay(base)
        self.assertTrue(0.5 <= d <= 1.5)

    def test_adaptive_rate_limiter_adaptation(self):
        limiter = AdaptiveRateLimiter(default_delay=0.8)
        initial_delay = limiter.current_delay

        # Record multiple consecutive failures -> delay should increase
        for _ in range(6):
            limiter.record_failure()
        increased_delay = limiter.current_delay
        self.assertGreater(increased_delay, initial_delay)

        # Record 25 consecutive successes -> flushes failures, repeatedly reduces delay
        for _ in range(25):
            limiter.record_success()
        self.assertLess(limiter.current_delay, increased_delay)

    def test_block_detector(self):
        detector = BlockDetector(threshold=3)
        self.assertEqual(detector.consecutive_403, 0)
        self.assertEqual(detector.block_count, 0)

        # 1st 403
        self.assertFalse(detector.record_403())
        self.assertEqual(detector.consecutive_403, 1)

        # 2nd 403
        self.assertFalse(detector.record_403())
        self.assertEqual(detector.consecutive_403, 2)

        # 3rd 403 -> triggers block
        self.assertTrue(detector.record_403())
        self.assertEqual(detector.consecutive_403, 0)
        self.assertEqual(detector.block_count, 1)

        # Success resets consecutive 403
        detector.record_403()
        self.assertEqual(detector.consecutive_403, 1)
        detector.record_success()
        self.assertEqual(detector.consecutive_403, 0)


if __name__ == "__main__":
    unittest.main()
