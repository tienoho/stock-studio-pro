"""
Unit tests validating newly added free media resource providers:
Wikimedia Commons, Openverse, and Coverr.
"""

import unittest
from unittest.mock import MagicMock, patch
from src.infrastructure.providers.wikimedia_provider import WikimediaProvider
from src.infrastructure.providers.openverse_provider import OpenverseProvider
from src.infrastructure.providers.coverr_provider import CoverrProvider


class TestFreeMediaProviders(unittest.TestCase):
    """Test suite ensuring free providers parse responses accurately and adhere to contracts."""

    def test_wikimedia_search_photos_mocked(self):
        provider = WikimediaProvider()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "query": {
                "pages": {
                    "12345": {
                        "pageid": 12345,
                        "title": "File:Test Mountain.jpg",
                        "imageinfo": [{
                            "url": "https://upload.wikimedia.org/wikipedia/commons/test.jpg",
                            "thumburl": "https://thumb.wikimedia.org/test_500.jpg",
                            "width": 1920,
                            "height": 1080,
                            "extmetadata": {
                                "Artist": {"value": "<b>John Doe</b>"}
                            },
                            "descriptionurl": "https://commons.wikimedia.org/wiki/File:Test_Mountain.jpg"
                        }]
                    }
                }
            }
        }

        with patch("requests.get", return_value=mock_response):
            items = provider.search_photos("mountain", per_page=10)

        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item["source"], "wikimedia")
        self.assertEqual(item["type"], "photo")
        self.assertEqual(item["id"], "12345")
        self.assertEqual(item["download_url"], "https://upload.wikimedia.org/wikipedia/commons/test.jpg")
        self.assertEqual(item["thumb_url"], "https://thumb.wikimedia.org/test_500.jpg")
        self.assertEqual(item["author"], "John Doe")
        self.assertEqual(item["width"], 1920)
        self.assertEqual(item["height"], 1080)

    def test_wikimedia_search_videos_mocked(self):
        provider = WikimediaProvider()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "query": {
                "pages": {
                    "99999": {
                        "pageid": 99999,
                        "title": "File:Drone Ocean.webm",
                        "imageinfo": [{
                            "url": "https://upload.wikimedia.org/wikipedia/commons/drone.webm",
                            "thumburl": "https://thumb.wikimedia.org/drone_thumb.jpg",
                            "width": 1920,
                            "height": 1080,
                            "extmetadata": {
                                "Artist": {"value": "Ocean Pilot"}
                            }
                        }]
                    }
                }
            }
        }

        with patch("requests.get", return_value=mock_response):
            items = provider.search_videos("ocean drone", per_page=5)

        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item["source"], "wikimedia")
        self.assertEqual(item["type"], "video")
        self.assertEqual(item["download_url"], "https://upload.wikimedia.org/wikipedia/commons/drone.webm")

    def test_openverse_search_photos_mocked(self):
        provider = OpenverseProvider()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {
                    "id": "open-uuid-1",
                    "title": "Sunset View",
                    "url": "https://live.staticflickr.com/sunset.jpg",
                    "thumbnail": "https://api.openverse.org/thumb/sunset.jpg",
                    "creator": "Alice Photographer",
                    "creator_url": "https://flickr.com/alice",
                    "foreign_landing_url": "https://flickr.com/photo/1",
                    "width": 2048,
                    "height": 1536
                }
            ]
        }

        with patch("requests.get", return_value=mock_response):
            items = provider.search_photos("sunset", per_page=10)

        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item["source"], "openverse")
        self.assertEqual(item["type"], "photo")
        self.assertEqual(item["id"], "open-uuid-1")
        self.assertEqual(item["download_url"], "https://live.staticflickr.com/sunset.jpg")
        self.assertEqual(item["author"], "Alice Photographer")
        self.assertEqual(item["width"], 2048)

    def test_coverr_search_videos_mocked(self):
        km_mock = MagicMock()
        key_mock = MagicMock()
        key_mock.key = "mock_coverr_key"
        km_mock.get_coverr_key.return_value = key_mock

        provider = CoverrProvider(km_mock)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "hits": [
                {
                    "id": "cov-123",
                    "title": "City Skyline Timelapse",
                    "poster": "https://coverr.co/poster.jpg",
                    "duration": 14.5,
                    "width": 1920,
                    "height": 1080,
                    "urls": {
                        "mp4_download": "https://storage.coverr.co/city_download.mp4"
                    }
                }
            ]
        }

        with patch("requests.get", return_value=mock_response) as mock_get:
            items = provider.search_videos("city timelapse", per_page=5)
            # Verify Authorization Bearer was passed
            call_kwargs = mock_get.call_args[1]
            self.assertEqual(call_kwargs["headers"]["Authorization"], "Bearer mock_coverr_key")

        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item["source"], "coverr")
        self.assertEqual(item["type"], "video")
        self.assertEqual(item["id"], "cov-123")
        self.assertEqual(item["download_url"], "https://storage.coverr.co/city_download.mp4")
        self.assertEqual(item["thumb_url"], "https://coverr.co/poster.jpg")
        self.assertEqual(item["duration"], 14.5)

    def test_free_providers_keyless_validations(self):
        wiki = WikimediaProvider()
        ok_w, msg_w = wiki.test_key("any_key")
        self.assertTrue(ok_w)
        self.assertIn("miễn phí", msg_w.lower())

        openv = OpenverseProvider()
        ok_o, msg_o = openv.test_key("any_key")
        self.assertTrue(ok_o)
        self.assertIn("miễn phí", msg_o.lower())

    def test_query_sanitization_newlines_and_truncation(self):
        wiki = WikimediaProvider()
        with patch("requests.get") as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = {"query": {"pages": {}}}
            wiki.search_photos("sunset\n\r\tview " + "a" * 200, per_page=5)
            call_params = mock_get.call_args[1]["params"]
            self.assertNotIn("\n", call_params["gsrsearch"])
            self.assertNotIn("\r", call_params["gsrsearch"])
            self.assertLessEqual(len(call_params["gsrsearch"]), 150)


if __name__ == "__main__":
    unittest.main()
