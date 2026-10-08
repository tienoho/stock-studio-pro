"""
Smart Downloader service with adaptive retry, browser simulation, and URL refresh.
"""

import time
from pathlib import Path
from typing import Dict, Any, Tuple, Optional, Callable
import requests

from ...core.constants import MAX_RETRIES, RETRY_DELAYS
from ...core.interfaces.media_provider import IMediaProvider
from ...infrastructure.network.rate_limiter import get_random_ua


class SmartDownloader:
    """Downloads media assets with smart retry, User-Agent rotation, and URL refresh on 403."""

    def __init__(
        self,
        providers: Optional[Dict[str, IMediaProvider]] = None,
        should_stop: Optional[Callable[[], bool]] = None
    ):
        self.providers = providers or {}
        self.should_stop = should_stop or (lambda: False)

    def download(self, item: Dict[str, Any], output_path: Path) -> Tuple[bool, str, str]:
        """Download file with smart retries. Returns (success, error_msg, error_type)."""
        url = item["download_url"]
        media_id = str(item["id"])
        source = item.get("source", "").lower()
        media_type = item.get("type", "video")
        query = item.get("search_query", "")

        last_error = ""
        last_error_type = "unknown"

        # Attempts 1-3 with retries
        for attempt in range(MAX_RETRIES):
            if attempt > 0:
                delay = RETRY_DELAYS[min(attempt - 1, len(RETRY_DELAYS) - 1)]
                time.sleep(delay)

            success, error_msg, error_type = self._try_download(url, output_path, media_type)
            if success:
                return True, "", "success"

            last_error = error_msg
            last_error_type = error_type

            if error_type in ("forbidden", "not_found", "expired_url"):
                break

        # Fallback: Refresh URL if forbidden or expired
        if media_type == "video" and last_error_type in ("forbidden", "not_found", "expired_url"):
            provider = self.providers.get(source)
            if provider:
                new_url = provider.refresh_video_url(media_id, url)
                if new_url and new_url != url:
                    time.sleep(1)
                    success, error_msg, error_type = self._try_download(new_url, output_path, media_type)
                    if success:
                        return True, "", "success_after_refresh"
                    last_error = error_msg
                    last_error_type = error_type

        return False, last_error, last_error_type

    def _try_download(self, url: str, output_path: Path, media_type: str = "video") -> Tuple[bool, str, str]:
        try:
            headers = {
                "User-Agent": get_random_ua(),
                "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8" if media_type == "photo"
                          else "video/mp4,video/*;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "Cache-Control": "no-cache",
                "Sec-Fetch-Dest": "image" if media_type == "photo" else "video",
                "Sec-Fetch-Mode": "no-cors",
                "Sec-Fetch-Site": "cross-site",
            }

            if "pexels.com" in url or "pexelscdn.com" in url:
                headers["Referer"] = "https://www.pexels.com/"
                headers["Origin"] = "https://www.pexels.com"
            elif "pixabay.com" in url or "pixabaycdn.com" in url:
                headers["Referer"] = "https://pixabay.com/"
                headers["Origin"] = "https://pixabay.com"
            elif "coverr.co" in url or "storage.coverr.co" in url:
                headers["Referer"] = "https://coverr.co/"
                headers["Origin"] = "https://coverr.co"
            elif "motionarray.com" in url or "motionarray.imgix.net" in url:
                headers["Referer"] = "https://motionarray.com/"
                headers["Origin"] = "https://motionarray.com"

            output_path.parent.mkdir(parents=True, exist_ok=True)

            with requests.get(url, stream=True, timeout=60, headers=headers) as r:
                if r.status_code == 403:
                    return False, "403 Forbidden", "forbidden"
                elif r.status_code == 404:
                    return False, "404 Not Found", "not_found"
                elif r.status_code == 429:
                    return False, "429 Rate Limited", "rate_limit"
                r.raise_for_status()

                content_type = r.headers.get('Content-Type', '')
                if 'html' in content_type.lower():
                    return False, "Got HTML response instead of media", "expired_url"

                with open(output_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        if self.should_stop():
                            stopped_early = True
                            break
                        if chunk:
                            f.write(chunk)
                    else:
                        stopped_early = False

                if stopped_early:
                    output_path.unlink(missing_ok=True)
                    return False, "Stopped by user", "stopped"

            min_size = 5 * 1024 if media_type == "photo" else 1024
            if not output_path.exists() or output_path.stat().st_size < min_size:
                output_path.unlink(missing_ok=True)
                return False, "File too small or missing", "expired_url"

            return True, "", "success"

        except requests.exceptions.Timeout:
            output_path.unlink(missing_ok=True)
            return False, "Timeout", "timeout"
        except requests.exceptions.ConnectionError as e:
            output_path.unlink(missing_ok=True)
            return False, f"Connection: {str(e)[:50]}", "network"
        except Exception as e:
            output_path.unlink(missing_ok=True)
            return False, f"Error: {str(e)[:80]}", "unknown"

