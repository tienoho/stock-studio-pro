"""
Tests for KeyManager in src.application.services.key_manager.
"""

import unittest
from concurrent.futures import ThreadPoolExecutor
from src.application.services.key_manager import KeyManager


class TestKeyManager(unittest.TestCase):
    def setUp(self):
        self.pexels_keys = [
            {"name": "Pexels 1", "key": "key_p1"},
            {"name": "Pexels 2", "key": "key_p2"},
            {"name": "Pexels 3", "key": "key_p3"},
        ]
        self.pixabay_keys = [
            {"name": "Pixabay 1", "key": "key_px1"},
        ]
        self.vecteezy_keys = [
            {"name": "Vecteezy 1", "key": "key_vz1"},
        ]

    def test_round_robin_rotation(self):
        km = KeyManager(
            pexels_keys=self.pexels_keys,
            pixabay_keys=self.pixabay_keys,
            vecteezy_keys=self.vecteezy_keys
        )

        k1 = km.get_next_key("pexels")
        k2 = km.get_next_key("pexels")
        k3 = km.get_next_key("pexels")
        k4 = km.get_next_key("pexels")

        self.assertEqual(k1, "key_p1")
        self.assertEqual(k2, "key_p2")
        self.assertEqual(k3, "key_p3")
        self.assertEqual(k4, "key_p1")  # Rotated back to first key

    def test_thread_safe_rotation(self):
        km = KeyManager(
            pexels_keys=self.pexels_keys,
            pixabay_keys=self.pixabay_keys
        )

        results = []
        def fetch():
            return km.get_next_key("pexels")

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(fetch) for _ in range(30)]
            for f in futures:
                results.append(f.result())

        self.assertEqual(len(results), 30)
        # All keys should have been used evenly
        self.assertEqual(results.count("key_p1"), 10)
        self.assertEqual(results.count("key_p2"), 10)
        self.assertEqual(results.count("key_p3"), 10)


if __name__ == "__main__":
    unittest.main()
