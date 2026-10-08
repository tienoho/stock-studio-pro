"""
Comprehensive Bug Hunter & Stress Test Suite for AutoStock Studio.
Executes end-to-end simulated user workflows, fuzzing, cross-tab signals,
error handling, and edge case inspections to detect latent defects.
"""

import sys
import os
import json
import tempfile
import traceback
from pathlib import Path

# Ensure root workspace is in sys.path
WORKSPACE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE))

# Set headless Qt
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

from src.ui.main_window import AutoStockMainWindow
from src.core.models.scene import Scene, extract_scenes_from_json
from src.application.services.part_merger import PartMerger
from src.application.services.edge_tts_service import EdgeTtsService
from src.application.services.scene_voice_matcher import SceneVoiceMatcher
from src.infrastructure.media.ffmpeg_processor import FFmpegProcessor
from src.infrastructure.persistence.sqlite_db import SqliteDatabase
from src.infrastructure.persistence.sqlite_config_repo import SqliteConfigRepository
from src.infrastructure.persistence.sqlite_state_repo import SqliteStateRepository
from src.ui.dialogs.settings_dialog import SettingsDialog
from src.ui.dialogs.key_management_dialog import KeyDialog, KeyManagementDialog
from src.ui.dialogs.json_input_dialog import JsonInputDialog
from src.ui.dialogs.assign_scene_dialog import AssignSceneDialog
from src.ui.dialogs.update_dialog import UpdateDialog
from src.application.services.update_checker import ReleaseInfo


def run_bug_hunt():
    print("=" * 70)
    print("  🚀 AUTOSTOCK STUDIO - COMPREHENSIVE BUG HUNT & STRESS TEST")
    print("=" * 70)

    app = QApplication.instance() or QApplication(sys.argv)
    bugs_found = []

    # -------------------------------------------------------------
    # 1. Main Window UI Instantiation & Tab Switching
    # -------------------------------------------------------------
    print("\n[Test 1] Testing AutoStockMainWindow Lifecycle & Tab Switching...")
    try:
        win = AutoStockMainWindow()
        win.show()

        for idx in range(6):
            win.main_tabs.setCurrentIndex(idx)
            app.processEvents()

        print("  -> Passed: All 6 tabs switched smoothly without exception.")
    except Exception as e:
        bugs_found.append(f"AutoStockMainWindow Tab Switching: {e}\n{traceback.format_exc()}")
        print(f"  ❌ FAILED: {e}")

    # -------------------------------------------------------------
    # 2. Theme Toggling (Dark <-> Light Stress Test)
    # -------------------------------------------------------------
    print("\n[Test 2] Testing Theme Toggling (Dark <-> Light)...")
    try:
        for _ in range(4):
            win._toggle_theme()
            app.processEvents()
        print("  -> Passed: Themes toggled repeatedly without styling or layout crash.")
    except Exception as e:
        bugs_found.append(f"Theme Toggling: {e}\n{traceback.format_exc()}")
        print(f"  ❌ FAILED: {e}")

    # -------------------------------------------------------------
    # 3. Language Switching (i18n Retranslate Stress Test)
    # -------------------------------------------------------------
    print("\n[Test 3] Testing Language Switching (VI <-> EN)...")
    try:
        for _ in range(4):
            win._toggle_language()
            app.processEvents()
        print("  -> Passed: Language switched between VI and EN smoothly.")
    except Exception as e:
        bugs_found.append(f"Language Switching: {e}\n{traceback.format_exc()}")
        print(f"  ❌ FAILED: {e}")

    # -------------------------------------------------------------
    # 4. JSON Script Parsing & Loading Edge Cases
    # -------------------------------------------------------------
    print("\n[Test 4] Testing JSON Script Loading Edge Cases...")
    test_cases = [
        # Standard schema
        {"scenes": [{"id": 1, "dialogue": "Scene 1", "primary_keywords": ["nature"]}]},
        # Claude markdown wrapper simulation
        '```json\n{"scenes": [{"id": 2, "dialogue": "Scene 2", "time_start": "00:05"}]}\n```',
        # Empty scenes
        {"scenes": []},
        # Weird IDs (float, string, negative)
        {"scenes": [{"id": "scene_A", "dialogue": "Alpha"}, {"id": 99.5, "dialogue": "Beta"}]},
        # Unicode / Vietnamese accents & emoji
        {"scenes": [{"id": "vn_1", "dialogue": "Chào mừng đến với AutoStock Studio! 🚀✨"}]},
    ]
    for i, tc in enumerate(test_cases):
        try:
            if isinstance(tc, str):
                cleaned = tc.strip()
                if cleaned.startswith("```"):
                    lines = cleaned.splitlines()
                    cleaned = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
                data = json.loads(cleaned)
            else:
                data = tc
            scenes = extract_scenes_from_json(data)
            win.downloader_tab.load_scenes(scenes, data)
            app.processEvents()
            print(f"  -> Case {i+1} Passed ({len(scenes)} scenes loaded).")
        except Exception as e:
            bugs_found.append(f"JSON Parsing Case {i+1}: {e}\n{traceback.format_exc()}")
            print(f"  ❌ FAILED on Case {i+1}: {e}")

    # -------------------------------------------------------------
    # 5. Downloader Tab Interactive Controls & Boundary Testing
    # -------------------------------------------------------------
    print("\n[Test 5] Testing Downloader Tab Controls & Boundary Conditions...")
    try:
        dt = win.downloader_tab
        # Boundary: Navigate scenes
        dt.select_next_scene()
        dt.select_prev_scene()
        dt._set_timeline_filter("missing")
        dt._set_timeline_filter("all")

        # Filter toggles
        dt._set_filter("all")
        dt._set_filter("videos")
        dt._set_filter("photos")
        dt._set_filter("selected")

        # Random selection with 0, 1, 10
        dt.auto_random_all_scenes(0)
        dt.auto_random_all_scenes(2)
        dt._select_all_scene()
        dt._clear_scene_selection()
        app.processEvents()
        print("  -> Passed: Downloader navigation, filtering, and selection methods stable.")
    except Exception as e:
        bugs_found.append(f"Downloader Tab Controls: {e}\n{traceback.format_exc()}")
        print(f"  ❌ FAILED: {e}")

    # -------------------------------------------------------------
    # 6. Dialogs Smoke Test
    # -------------------------------------------------------------
    print("\n[Test 6] Testing Dialogs Initialization & Interaction Enhancements...")
    try:
        # SettingsDialog
        sd = SettingsDialog(config=win.config, parent=None)
        sd.close()

        # KeyManagementDialog
        kd = KeyDialog("pexels", parent=None)
        kd.close()
        kmd = KeyManagementDialog("pexels", config=win.config, parent=None)
        kmd.close()

        # JsonInputDialog
        jid = JsonInputDialog(parent=None)
        jid.close()

        # AssignSceneDialog
        sample_scenes = [{"id": 1, "dialogue": "Scene 1", "time_start": "00:00"}]
        asd = AssignSceneDialog("test_video.mp4", sample_scenes, suggested_scene_id=1, parent=None)
        asd.close()

        # UpdateDialog
        rel = ReleaseInfo.from_dict({
            "tag_name": "v2.1.0",
            "name": "AutoStock Studio v2.1.0",
            "body": "New features and ultra-optimized UI",
            "published_at": "2026-10-08T00:00:00Z",
            "html_url": "https://github.com/example/release"
        })
        ud = UpdateDialog(rel, parent=None)
        ud.close()

        print("  -> Passed: All 5 modal dialogs instantiated, styled, and closed cleanly.")
    except Exception as e:
        bugs_found.append(f"Dialogs Smoke Test: {e}\n{traceback.format_exc()}")
        print(f"  ❌ FAILED: {e}")

    # -------------------------------------------------------------
    # 7. Part Merger Fuzzing
    # -------------------------------------------------------------
    print("\n[Test 7] Testing PartMerger Edge Cases...")
    try:
        merger = PartMerger()
        # Clean parts with schema
        p1 = '```json\n{"_part_metadata": {"part_number": 1, "total_parts": 2, "first_scene_id": 1, "last_scene_id": 1, "first_timestamp": "00:00:00,000", "last_timestamp": "00:00:05,000"}, "scenes": [{"id": 1, "time_start": "00:00:00,000", "time_end": "00:00:05,000", "dialogue_es": "Part 1"}]}\n```'
        p2 = '```json\n{"_part_metadata": {"part_number": 2, "total_parts": 2, "first_scene_id": 2, "last_scene_id": 2, "first_timestamp": "00:00:05,000", "last_timestamp": "00:00:10,000"}, "scenes": [{"id": 2, "time_start": "00:00:05,000", "time_end": "00:00:10,000", "dialogue_es": "Part 2"}]}\n```'
        merged = merger.merge_from_texts([("Part 1", p1), ("Part 2", p2)])
        if len(merged["scenes"]) != 2:
            bugs_found.append("PartMerger failed to merge 2 clean parts properly.")
        print("  -> Passed: PartMerger merged multi-part JSON scripts correctly.")
    except Exception as e:
        bugs_found.append(f"PartMerger: {e}\n{traceback.format_exc()}")
        print(f"  ❌ FAILED: {e}")

    # -------------------------------------------------------------
    # 8. Cross-Tab Signal Propagation
    # -------------------------------------------------------------
    print("\n[Test 8] Testing Cross-Tab Signal Propagation...")
    try:
        # Simulate JSON loaded
        win._on_json_loaded(
            {"scenes": [{"id": 1, "dialogue": "Test Cross-Tab"}]},
            [{"id": 1, "dialogue": "Test Cross-Tab"}],
            "d:/test/script.json"
        )
        if hasattr(win, "scene_voice_tab") and win.scene_voice_tab.svc_json.text() != "d:/test/script.json":
            bugs_found.append("Cross-Tab: scene_voice_tab.svc_json not populated upon JSON load.")

        # Simulate Download finished
        win._on_download_finished(1, 0, "d:/test/project_media", {})
        if hasattr(win, "cut_mix_tab") and win.cut_mix_tab.cut_folder_input.text() != "d:/test/project_media":
            bugs_found.append("Cross-Tab: cut_mix_tab.cut_folder_input not synchronized upon download finish.")
        if hasattr(win, "scene_voice_tab") and win.scene_voice_tab.svc_root.text() != "d:/test/project_media":
            bugs_found.append("Cross-Tab: scene_voice_tab.svc_root not synchronized upon download finish.")

        print("  -> Passed: Cross-tab signals propagate paths and states seamlessly.")
    except Exception as e:
        bugs_found.append(f"Cross-Tab Propagation: {e}\n{traceback.format_exc()}")
        print(f"  ❌ FAILED: {e}")

    # -------------------------------------------------------------
    # SUMMARY
    # -------------------------------------------------------------
    print("\n" + "=" * 70)
    if not bugs_found:
        print("  🎉 ALL BUG HUNT TESTS PASSED! 0 DEFECTS FOUND.")
    else:
        print(f"  ⚠️ FOUND {len(bugs_found)} ISSUE(S):")
        for b in bugs_found:
            print(f"  - {b}")
    print("=" * 70)
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0 if not bugs_found else 1)


if __name__ == "__main__":
    run_bug_hunt()
