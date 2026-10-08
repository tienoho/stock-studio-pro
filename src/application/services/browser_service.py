"""
Browser Service for locating installed web browsers and launching URLs safely.
Decouples operating system and process execution from UI widgets.
"""

import os
import time
import subprocess
import webbrowser
from typing import Optional, List


class BrowserService:
    """Application service for browser detection and controlled tab opening."""

    COCCOC_CANDIDATE_PATHS = [
        r"%LOCALAPPDATA%\CocCoc\Browser\Application\browser.exe",
        r"%PROGRAMFILES%\CocCoc\Browser\Application\browser.exe",
        r"%PROGRAMFILES(X86)%\CocCoc\Browser\Application\browser.exe",
        r"C:\Users\%USERNAME%\AppData\Local\CocCoc\Browser\Application\browser.exe",
    ]

    CHROME_CANDIDATE_PATHS = [
        r"%PROGRAMFILES%\Google\Chrome\Application\chrome.exe",
        r"%PROGRAMFILES(X86)%\Google\Chrome\Application\chrome.exe",
        r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe",
    ]

    def find_browser_executable(self, preferred: str = "coccoc") -> Optional[str]:
        """Locates an installed browser executable on Windows, checking preferred first."""
        candidates = []
        if preferred.lower() == "coccoc":
            candidates = self.COCCOC_CANDIDATE_PATHS + self.CHROME_CANDIDATE_PATHS
        else:
            candidates = self.CHROME_CANDIDATE_PATHS + self.COCCOC_CANDIDATE_PATHS

        for path_template in candidates:
            expanded = os.path.expandvars(path_template)
            if os.path.exists(expanded):
                return expanded
        return None

    def open_url(self, url: str, browser_executable: Optional[str] = None) -> bool:
        """Opens a single URL using the given browser executable or the system default."""
        try:
            if browser_executable and os.path.exists(browser_executable):
                subprocess.Popen([browser_executable, url])
            else:
                webbrowser.open(url, new=2)
            return True
        except Exception:
            try:
                webbrowser.open(url, new=2)
                return True
            except Exception:
                return False

    def open_batch_urls(
        self,
        urls: List[str],
        delay_seconds: float = 0.3,
        preferred_browser: str = "coccoc"
    ) -> int:
        """Opens a series of URLs sequentially with a gentle delay to prevent window collisions."""
        browser_exe = self.find_browser_executable(preferred=preferred_browser)
        opened = 0
        for idx, url in enumerate(urls):
            success = self.open_url(url, browser_exe)
            if success:
                opened += 1
            if idx < len(urls) - 1 and delay_seconds > 0:
                time.sleep(delay_seconds)
        return opened
