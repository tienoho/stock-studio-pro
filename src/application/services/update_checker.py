"""
Update Checker service for AutoStock Studio.
Queries GitHub Releases API to detect new versions, parse release notes, and provide download assets.
Pure Python - fully decoupled from UI code.
"""

import re
import requests
from dataclasses import dataclass
from typing import Tuple, Optional, List, Dict, Any

from ...core.constants import APP_VERSION, GITHUB_REPO_OWNER, GITHUB_REPO_NAME, GITHUB_RELEASES_URL


def parse_semver(version_str: str) -> Tuple[int, int, int]:
    """
    Parses a version string (e.g., '1.0', 'v1.0.2', 'v2.1.0-beta') into a (major, minor, patch) integer tuple.
    """
    cleaned = str(version_str).strip().lower().lstrip("v")
    nums = re.findall(r"\d+", cleaned)
    major = int(nums[0]) if len(nums) > 0 else 0
    minor = int(nums[1]) if len(nums) > 1 else 0
    patch = int(nums[2]) if len(nums) > 2 else 0
    return (major, minor, patch)


def compare_versions(v1: str, v2: str) -> int:
    """
    Compares two semantic versions.
    Returns:
       1 if v1 > v2
       0 if v1 == v2
      -1 if v1 < v2
    """
    t1 = parse_semver(v1)
    t2 = parse_semver(v2)
    if t1 > t2:
        return 1
    elif t1 < t2:
        return -1
    return 0


@dataclass
class ReleaseInfo:
    """Data object describing a GitHub release."""
    tag_name: str
    version: str
    title: str
    body: str
    published_at: str
    html_url: str
    download_url: Optional[str] = None
    asset_name: Optional[str] = None
    asset_size: int = 0

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ReleaseInfo":
        tag = data.get("tag_name", "")
        ver = tag.lstrip("vV")
        title = data.get("name") or f"AutoStock Studio {tag}"
        body = data.get("body") or "Không có nhật ký thay đổi."
        pub_at = data.get("published_at", "")[:10]
        html_url = data.get("html_url", GITHUB_RELEASES_URL)

        # Find Windows zip asset if present
        assets: List[Dict[str, Any]] = data.get("assets", [])
        dl_url = None
        asset_name = None
        asset_size = 0

        for a in assets:
            name = a.get("name", "")
            if name.endswith(".zip"):
                dl_url = a.get("browser_download_url")
                asset_name = name
                asset_size = int(a.get("size", 0))
                if "windows" in name.lower() or "autostock" in name.lower():
                    break

        if not dl_url:
            dl_url = html_url

        return cls(
            tag_name=tag,
            version=ver,
            title=title,
            body=body,
            published_at=pub_at,
            html_url=html_url,
            download_url=dl_url,
            asset_name=asset_name,
            asset_size=asset_size,
        )


class UpdateCheckerService:
    """Enterprise service for checking application updates against GitHub Releases."""

    def __init__(self, owner: str = GITHUB_REPO_OWNER, repo: str = GITHUB_REPO_NAME):
        self.owner = owner
        self.repo = repo
        self.api_url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"

    def check_for_updates(
        self,
        current_version: str = APP_VERSION,
        timeout: float = 6.0
    ) -> Tuple[bool, Optional[ReleaseInfo], str]:
        """
        Checks whether a newer release is published on GitHub.
        Returns:
            (has_update, release_info, status_message)
        """
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": f"AutoStockStudio/{current_version}",
        }

        try:
            resp = requests.get(self.api_url, headers=headers, timeout=timeout)
            if resp.status_code == 404:
                return False, None, "Chưa có bản phát hành nào được công bố trên GitHub."
            if resp.status_code == 403 and "rate limit" in resp.text.lower():
                return False, None, "Giới hạn truy cập GitHub API tạm thời bị chạm. Vui lòng thử lại sau."
            if resp.status_code != 200:
                return False, None, f"Lỗi máy chủ GitHub (HTTP {resp.status_code})."

            data = resp.json()
            release = ReleaseInfo.from_dict(data)

            if compare_versions(release.version, current_version) > 0:
                return True, release, f"Đã có phiên bản mới {release.tag_name} (Hiện tại: v{current_version})."
            else:
                return False, release, f"Bạn đang sử dụng phiên bản mới nhất (v{current_version})."

        except requests.Timeout:
            return False, None, "Kiểm tra cập nhật quá thời gian (Timeout). Vui lòng thử lại."
        except requests.RequestException as e:
            return False, None, f"Không thể kết nối đến máy chủ cập nhật: {e}"
        except Exception as e:
            return False, None, f"Lỗi kiểm tra cập nhật: {e}"
