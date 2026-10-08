"""
Update Checker service for AutoStock Studio.
Queries GitHub Releases API to detect new versions, parse release notes, and provide download assets.
Pure Python - fully decoupled from UI code.
"""

import os
import re
import sys
import time
import zipfile
import tempfile
import subprocess
import shutil
import requests
from pathlib import Path
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

    def download_asset(
        self,
        download_url: str,
        dest_path: Path,
        progress_cb=None,
        cancel_fn=None,
        chunk_size: int = 65536,
        timeout: float = 30.0,
        estimated_total: int = 0
    ) -> Path:
        """
        Streams and downloads an update asset to dest_path.
        Calls progress_cb(downloaded_bytes, total_bytes, speed_bps).
        """
        dest_path = Path(dest_path)
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        headers = {
            "Accept": "application/octet-stream",
            "User-Agent": f"AutoStockStudio/{APP_VERSION}",
        }

        resp = requests.get(download_url, stream=True, headers=headers, timeout=timeout)
        resp.raise_for_status()

        content_len_header = resp.headers.get("content-length")
        total_bytes = (
            int(content_len_header)
            if content_len_header and content_len_header.isdigit()
            else estimated_total
        )

        downloaded = 0
        start_time = time.time()
        last_report_time = 0.0

        with open(dest_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=chunk_size):
                if cancel_fn and cancel_fn():
                    raise InterruptedError("Download cancelled by user.")
                if not chunk:
                    continue
                f.write(chunk)
                downloaded += len(chunk)
                now = time.time()
                if progress_cb and (now - last_report_time >= 0.12 or (total_bytes > 0 and downloaded >= total_bytes)):
                    elapsed = max(now - start_time, 0.001)
                    speed = downloaded / elapsed
                    progress_cb(downloaded, total_bytes, speed)
                    last_report_time = now

        if progress_cb and downloaded > 0:
            elapsed = max(time.time() - start_time, 0.001)
            progress_cb(downloaded, total_bytes if total_bytes > 0 else downloaded, downloaded / elapsed)

        return dest_path

    def extract_archive(self, zip_path: Path, target_dir: Path) -> Path:
        """
        Safely extracts the zip archive into target_dir.
        Guards against Zip Slip path traversal.
        Returns the root directory containing the extracted application payload.
        """
        zip_path = Path(zip_path)
        target_dir = Path(target_dir)
        target_dir.mkdir(parents=True, exist_ok=True)

        if not zipfile.is_zipfile(zip_path):
            raise ValueError(f"Tệp không phải là tệp nén ZIP hợp lệ: {zip_path}")

        with zipfile.ZipFile(zip_path, "r") as zf:
            corrupted = zf.testzip()
            if corrupted:
                raise ValueError(f"Gói nén ZIP bị lỗi hoặc hỏng tại: {corrupted}")

            resolved_target = target_dir.resolve()
            for member in zf.infolist():
                member_path = (target_dir / member.filename).resolve()
                if not str(member_path).startswith(str(resolved_target)):
                    raise PermissionError(f"Phát hiện nguy cơ bảo mật đường dẫn ZIP: {member.filename}")

            zf.extractall(target_dir)

        # Unnest if the zip has a single root folder
        items = [p for p in target_dir.iterdir() if p.name not in ("__MACOSX", ".DS_Store")]
        if len(items) == 1 and items[0].is_dir():
            return items[0]

        return target_dir

    @staticmethod
    def is_app_frozen() -> bool:
        """Returns True if the application is running as a compiled PyInstaller executable."""
        return getattr(sys, "frozen", False)

    @classmethod
    def resolve_update_target(cls, staged_payload_dir: Path) -> Tuple[Path, Path, str]:
        """
        Resolves (src_dir, target_dir, exe_name) for copying and relaunching.
        """
        staged_payload_dir = Path(staged_payload_dir).resolve()

        if cls.is_app_frozen():
            current_exe = Path(sys.executable).resolve()
            current_app_dir = current_exe.parent
            exe_name = current_exe.name

            # If staged_payload_dir directly contains the executable
            if (staged_payload_dir / exe_name).exists():
                return staged_payload_dir, current_app_dir, exe_name

            # If staged_payload_dir has a subdirectory with the executable
            found_exes = list(staged_payload_dir.rglob(exe_name))
            if found_exes:
                matched_exe = found_exes[0]
                if (current_app_dir.parent / "run_exe.bat").exists() and (staged_payload_dir / "run_exe.bat").exists():
                    return staged_payload_dir, current_app_dir.parent, exe_name
                return matched_exe.parent, current_app_dir, exe_name

            return staged_payload_dir, current_app_dir, exe_name
        else:
            # Dev mode (running from source): do not overwrite repo
            found_exes = list(staged_payload_dir.rglob("AutoStockStudio.exe"))
            exe_name = found_exes[0].name if found_exes else "AutoStockStudio.exe"
            src_dir = found_exes[0].parent if found_exes else staged_payload_dir
            return src_dir, src_dir, exe_name

    def generate_updater_script(
        self,
        staged_dir: Path,
        target_dir: Path,
        exe_name: str,
        app_pid: Optional[int] = None,
        output_script_path: Optional[Path] = None
    ) -> Path:
        """
        Generates the detached Windows batch script that waits for current process to exit,
        replaces the files in target_dir using robocopy, relaunches the app, and cleans up.
        """
        if app_pid is None:
            app_pid = os.getpid()

        staged_dir = Path(staged_dir).resolve()
        target_dir = Path(target_dir).resolve()

        if output_script_path is None:
            temp_dir = Path(tempfile.gettempdir()) / "autostock_updater"
            temp_dir.mkdir(parents=True, exist_ok=True)
            output_script_path = temp_dir / "_apply_update.bat"
        else:
            output_script_path = Path(output_script_path)
            output_script_path.parent.mkdir(parents=True, exist_ok=True)

        bat_content = f"""@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
title AutoStock Studio - Trinh Cap Nhat Tu Dong

set PID=%1
set "STAGED=%~2"
set "TARGET=%~3"
set "EXE=%~4"

if "%PID%"=="" set PID={app_pid}
if "%STAGED%"=="" set "STAGED={str(staged_dir)}"
if "%TARGET%"=="" set "TARGET={str(target_dir)}"
if "%EXE%"=="" set "EXE={exe_name}"

echo ========================================================
echo   AutoStock Studio - Dang Tu Dong Cap Nhat Phien Ban Moi
echo ========================================================
echo.
echo Dang cho ung dung (PID: %PID%) dong hoan toan...

set WAIT_COUNT=0
:wait_loop
timeout /t 1 /nobreak >nul
set /a WAIT_COUNT+=1
tasklist /fi "PID eq %PID%" 2>nul | findstr /i "%PID%" >nul
if not errorlevel 1 (
    if !WAIT_COUNT! GEQ 30 (
        echo [Thong bao] Dang dong tien trinh cu...
        taskkill /F /PID %PID% >nul 2>nul
    ) else (
        goto wait_loop
    )
)

echo Tien trinh cu da tat. Dang cap nhat cac tep tin moi...
echo Nguon: "!STAGED!"
echo Dich:  "!TARGET!"

:: Sao chep toan bo tep sang thu muc ung dung
robocopy "!STAGED!" "!TARGET!" /E /IS /IT /NP /NDL /NFL /NJH /NJS /R:3 /W:1 >nul

timeout /t 1 /nobreak >nul

echo Dang khoi dong lai AutoStock Studio...
cd /d "!TARGET!"
if exist "!TARGET!\\!EXE!" (
    start "" "!TARGET!\\!EXE!"
) else if exist "!TARGET!\\AutoStockStudio\\!EXE!" (
    start "" "!TARGET!\\AutoStockStudio\\!EXE!"
) else (
    echo [Canh bao] Khong tim thay !EXE! tai !TARGET!
)

:: Don dep thu muc giai nen tam va tu xoa script
rd /s /q "!STAGED!" 2>nul
(goto) 2>nul & del "%~f0"
"""
        output_script_path.write_text(bat_content, encoding="utf-8")
        return output_script_path

    def launch_updater(
        self,
        script_path: Path,
        staged_dir: Path,
        target_dir: Path,
        exe_name: str,
        app_pid: Optional[int] = None
    ) -> None:
        """
        Spawns the updater batch script as a detached background process.
        """
        if app_pid is None:
            app_pid = os.getpid()

        script_path = Path(script_path).resolve()
        staged_dir = Path(staged_dir).resolve()
        target_dir = Path(target_dir).resolve()

        if sys.platform == "win32":
            DETACHED_PROCESS = 0x00000008
            CREATE_NEW_PROCESS_GROUP = 0x00000200
            flags = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP

            cmd = [
                "cmd.exe",
                "/c",
                str(script_path),
                str(app_pid),
                str(staged_dir),
                str(target_dir),
                str(exe_name),
            ]
            subprocess.Popen(
                cmd,
                creationflags=flags,
                close_fds=True,
                shell=False
            )
        else:
            subprocess.Popen(
                ["sh", str(script_path), str(app_pid), str(staged_dir), str(target_dir), str(exe_name)],
                close_fds=True
            )

