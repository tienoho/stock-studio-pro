"""
Background download worker with anti-block mechanisms and reporting.
"""

import re
import time
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any
from PyQt6.QtCore import QThread, pyqtSignal


from ...core.constants import APP_VERSION, BLOCK_COOLDOWN_SECONDS
from ...infrastructure.network.rate_limiter import AdaptiveRateLimiter, BlockDetector
from ...infrastructure.providers.pexels_provider import PexelsProvider
from ...infrastructure.providers.pixabay_provider import PixabayProvider
from ...infrastructure.providers.vecteezy_provider import VecteezyProvider
from ...application.services.smart_downloader import SmartDownloader


class DownloadWorker(QThread):
    """Background download worker with adaptive delay, 403 cooldown, and smart retry."""

    progress = pyqtSignal(str, int, int)
    statsUpdate = pyqtSignal(dict)
    cooldownStart = pyqtSignal(int)
    cooldownTick = pyqtSignal(int)
    cooldownEnd = pyqtSignal()
    finished_signal = pyqtSignal(int, int, str, dict)

    def __init__(
        self,
        scenes: list,
        selected_items: dict,
        output_dir: str,
        json_data: dict,
        key_manager=None,
        downloads_repo=None
    ):
        super().__init__()
        self.scenes = scenes
        self.selected_items = selected_items
        self.output_dir = output_dir
        self.json_data = json_data
        self.key_manager = key_manager
        self.downloads_repo = downloads_repo
        self._stop = False

        self.rate_limiter = AdaptiveRateLimiter()
        self.block_detector = BlockDetector()

        providers = {}
        if key_manager:
            providers["pexels"] = PexelsProvider(key_manager)
            providers["pixabay"] = PixabayProvider(key_manager)
            providers["vecteezy"] = VecteezyProvider(key_manager)

        self.downloader = SmartDownloader(providers=providers, should_stop=lambda: self._stop)

        self.stats = {
            "success": 0,
            "fail": 0,
            "via_refresh": 0,
            "block_cooldowns": 0,
            "error_breakdown": {},
        }

    def stop(self):
        self._stop = True

    def _adaptive_sleep(self):
        delay = self.rate_limiter.get_delay()
        chunks = int(delay * 10)
        for _ in range(chunks):
            if self._stop:
                return
            time.sleep(0.1)

    def _handle_result(self, success: bool, error_type: str):
        self.rate_limiter.record_result(success)
        if success:
            self.block_detector.record_success()
        elif error_type == "forbidden":
            if self.block_detector.record_403():
                self._cool_down()

    def _cool_down(self):
        self.stats["block_cooldowns"] += 1
        self.cooldownStart.emit(BLOCK_COOLDOWN_SECONDS)
        for remaining in range(BLOCK_COOLDOWN_SECONDS, 0, -1):
            if self._stop:
                return
            self.cooldownTick.emit(remaining)
            time.sleep(1)
        self.cooldownEnd.emit()

    def _emit_stats(self):
        delay, fail_rate, sample = self.rate_limiter.get_stats()
        self.statsUpdate.emit({
            "delay": delay,
            "fail_rate": fail_rate,
            "sample": sample,
            "blocks": self.stats["block_cooldowns"],
            "via_refresh": self.stats["via_refresh"],
        })

    def run(self):
        try:
            output_base = Path(self.output_dir)
            output_base.mkdir(parents=True, exist_ok=True)

            if self.json_data:
                try:
                    mapping_path = output_base / "_scene_mapping.json"
                    with open(mapping_path, 'w', encoding='utf-8') as f:
                        json.dump(self.json_data, f, ensure_ascii=False, indent=2)
                except Exception:
                    pass

            project_dir = output_base
            all_downloaded = []
            total = sum(len(s) for s in self.selected_items.values())
            done = 0

            for scene in self.scenes:
                if self._stop:
                    break
                scene_id = scene.get("id")
                selected = self.selected_items.get(scene_id, {})
                if not selected:
                    str_sid = str(scene_id)
                    for k, v in self.selected_items.items():
                        if str(k) == str_sid:
                            selected = v
                            break
                if not selected:
                    continue

                clean_sid = re.sub(r'[\\/*?:"<>|]', '_', str(scene_id).strip())
                scene_name = clean_sid.lstrip("0") or "0"

                for item_idx, item in enumerate(selected.values()):
                    if self._stop:
                        break
                    done += 1

                    ext = ".mp4" if item.get("type") == "video" else ".jpg"
                    filename = f"{scene_name}_{item_idx:02d}{ext}"
                    filepath = output_base / filename
                    while filepath.exists():
                        item_idx += 1
                        filename = f"{scene_name}_{item_idx:02d}{ext}"
                        filepath = output_base / filename

                    self.progress.emit(f"[{done}/{total}] scene #{scene_id}: {filename}", done, total)

                    success, error, error_type = self.downloader.download(item, filepath)
                    self._handle_result(success, error_type)

                    if success:
                        self.stats["success"] += 1
                        all_downloaded.append((scene, item, filename))
                        if error_type == "success_after_refresh":
                            self.stats["via_refresh"] += 1

                        # Audit download into SQLite
                        if self.downloads_repo and hasattr(self.downloads_repo, "record_download"):
                            try:
                                item_key = f"{item.get('source')}_{item.get('type')}_{item.get('id')}"
                                fsize = filepath.stat().st_size if filepath.exists() else 0
                                self.downloads_repo.record_download(
                                    item_key=item_key,
                                    scene_id=str(scene_id),
                                    source=item.get("source", "unknown"),
                                    media_type=item.get("type", "video"),
                                    item_id=str(item.get("id", "")),
                                    filepath=str(filepath),
                                    filesize=fsize,
                                    status="completed"
                                )
                            except Exception:
                                pass
                    else:
                        self.stats["fail"] += 1
                        self.stats["error_breakdown"][error_type] = self.stats["error_breakdown"].get(error_type, 0) + 1

                    self._emit_stats()
                    self._adaptive_sleep()

            self._save_scenes_info(project_dir, all_downloaded)
            self._save_credits(project_dir, [item for _, item, _ in all_downloaded])
            self._save_error_report(project_dir)

            self.finished_signal.emit(
                self.stats["success"],
                self.stats["fail"],
                str(project_dir),
                self.stats["error_breakdown"],
            )
        except Exception as e:
            self.progress.emit(f"[LỖI] {e}", 0, 0)
            self.finished_signal.emit(0, 0, "", {})

    def _save_error_report(self, project_dir: Path):
        try:
            with open(project_dir / "_error_report.txt", 'w', encoding='utf-8') as f:
                f.write("=" * 70 + "\n")
                f.write(f"DOWNLOAD REPORT - v{APP_VERSION}\n")
                f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("=" * 70 + "\n\n")

                total = self.stats["success"] + self.stats["fail"]
                success_rate = (self.stats["success"] / total * 100) if total > 0 else 0

                f.write(f"Total attempted:       {total}\n")
                f.write(f"Successful:            {self.stats['success']}\n")
                f.write(f"Failed:                {self.stats['fail']}\n")
                f.write(f"Success rate:          {success_rate:.1f}%\n")
                f.write(f"Saved via URL refresh: {self.stats['via_refresh']}\n")
                f.write(f"Block cooldowns:       {self.stats['block_cooldowns']}\n\n")
        except Exception:
            pass

    def _save_scenes_info(self, project_dir: Path, downloaded: list):
        try:
            by_scene = {}
            for scene, item, filename in downloaded:
                sid = scene.get("id")
                if sid not in by_scene:
                    by_scene[sid] = {"scene": scene, "files": []}
                by_scene[sid]["files"].append((item, filename))

            with open(project_dir / "_scenes_info.txt", 'w', encoding='utf-8') as f:
                f.write("SCENES INFO - Stock Media Project\n" + "=" * 70 + "\n\n")
                for scene in self.scenes:
                    sid = scene.get("id")
                    if sid not in by_scene:
                        continue
                    files = by_scene[sid]["files"]
                    f.write(f"SCENE {sid} | {scene.get('time_start', '?')} -> {scene.get('time_end', '?')}\n")
                    dialogue = scene.get('dialogue_es') or scene.get('dialogue', '')
                    if dialogue:
                        f.write(f"Dialogue: {dialogue}\n")
                    for item, fn in files:
                        f.write(f"  - {fn} ({item.get('type')})\n")
                    f.write("\n")
        except Exception:
            pass

    def _save_credits(self, project_dir: Path, items: list):
        try:
            with open(project_dir / "_credits.txt", 'w', encoding='utf-8') as f:
                f.write("CREDITS\n" + "=" * 50 + "\n\n")
                seen = set()
                for item in items:
                    key = f"{item.get('source')}_{item.get('author')}"
                    if key not in seen:
                        seen.add(key)
                        f.write(f"{item.get('type', '').title()} by {item.get('author')} ({item.get('source')})\n")
        except Exception:
            pass
