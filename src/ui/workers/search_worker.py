"""
Background search worker querying media providers per scene.
"""

import time
from typing import List, Dict, Any, Optional
from PyQt6.QtCore import QThread, pyqtSignal

from ...core.constants import MAX_KEYWORDS_PER_SCENE, RESULTS_PER_KEYWORD
from ...application.services.media_provider_registry import MediaProviderRegistry


class SearchWorker(QThread):
    """Searches stock media for scenes in a background thread."""

    sceneCompleted = pyqtSignal(object, list)  # scene_id, items
    progress = pyqtSignal(str)
    finished_signal = pyqtSignal()

    def __init__(
        self,
        scenes: List[Dict[str, Any]],
        key_manager,
        search_photos: bool,
        search_videos: bool,
        source_mode: str = "Pexels + Pixabay",
        provider_registry: Optional[MediaProviderRegistry] = None
    ):
        super().__init__()
        self.scenes = scenes
        self.km = key_manager
        self.search_photos = search_photos
        self.search_videos = search_videos
        self.source_mode = source_mode or "Pexels + Pixabay"
        self.registry = provider_registry or MediaProviderRegistry(self.km)
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        try:
            providers = self.registry.resolve_providers_for_mode(self.source_mode, self.km)

            if not providers:
                self.progress.emit(f"[CẢNH BÁO] Chưa có API key hợp lệ cho nguồn: {self.source_mode}")
                return

            total = len(self.scenes)
            for idx, scene in enumerate(self.scenes):
                if self._stop:
                    break

                scene_id = scene.get("id")
                primary_kws = [k for k in scene.get("primary_keywords", []) if k]
                secondary_kws = [k for k in scene.get("secondary_keywords", []) if k]

                n_primary = min(len(primary_kws), max(3, MAX_KEYWORDS_PER_SCENE - 2))
                n_secondary = MAX_KEYWORDS_PER_SCENE - n_primary
                keywords = primary_kws[:n_primary] + secondary_kws[:n_secondary]

                if len(keywords) < MAX_KEYWORDS_PER_SCENE and len(primary_kws) > n_primary:
                    extra = MAX_KEYWORDS_PER_SCENE - len(keywords)
                    keywords += primary_kws[n_primary:n_primary + extra]

                if not keywords:
                    self.sceneCompleted.emit(scene_id, [])
                    continue

                scene_results = []
                seen_keys = set()

                for kw in keywords:
                    if self._stop:
                        break
                    self.progress.emit(f"[{idx + 1}/{total}] Scene #{scene_id}: {kw}")

                    sources_results = []

                    if self.search_photos:
                        photos = []
                        for prov in providers.values():
                            try:
                                photos.extend(prov.search_photos(kw, per_page=RESULTS_PER_KEYWORD))
                            except Exception:
                                pass
                        sources_results.append(photos)
                        for _ in range(3):
                            if self._stop:
                                break
                            time.sleep(0.1)

                    if self.search_videos:
                        videos = []
                        for prov in providers.values():
                            try:
                                videos.extend(prov.search_videos(kw, per_page=RESULTS_PER_KEYWORD))
                            except Exception:
                                pass
                        sources_results.append(videos)
                        for _ in range(3):
                            if self._stop:
                                break
                            time.sleep(0.1)

                    for results in sources_results:
                        for r in results:
                            r["_scene_id"] = scene_id
                            key = f"{r['source']}_{r['type']}_{r['id']}"
                            if key not in seen_keys:
                                seen_keys.add(key)
                                scene_results.append(r)

                self.sceneCompleted.emit(scene_id, scene_results)

            self.progress.emit("Search hoàn tất")
        except Exception as e:
            self.progress.emit(f"[LỖI] {e}")
        finally:
            self.finished_signal.emit()
