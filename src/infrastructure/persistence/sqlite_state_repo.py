"""
SQLite-based session state repository implementing IStateRepository.
Stores project scenes, searched media items, and selection status with auto-migration from pickle.
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional, List
from ...core.interfaces.storage import IStateRepository
from ...core.constants import DB_FILE, STATE_FILE
from .sqlite_db import SqliteDatabase
from .pickle_state_repo import PickleStateRepository


class SqliteStateRepository(IStateRepository):
    """Production session state repository backed by SQLite database."""

    def __init__(
        self,
        db: Optional[SqliteDatabase] = None,
        pickle_fallback_path: Path = STATE_FILE,
        legacy_pickle_path: Optional[Path] = None,
    ):
        self.db = db or SqliteDatabase.get_instance()
        self.pickle_fallback_path = Path(legacy_pickle_path or pickle_fallback_path)
        self._check_and_migrate()

    def _check_and_migrate(self):
        """Migrate from old pickle state file if SQLite scenes table is empty."""
        conn = self.db.get_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM scenes;")
        count = cur.fetchone()[0]

        if count == 0 and self.pickle_fallback_path.exists():
            try:
                old_repo = PickleStateRepository(self.pickle_fallback_path)
                old_state = old_repo.load()
                if old_state:
                    self.save(old_state)
                    print("[SqliteStateRepository] Migrated legacy pickle session state to SQLite.")
            except Exception as e:
                print(f"[SqliteStateRepository] Migration error: {e}")

    def load(self) -> Optional[Dict[str, Any]]:
        """Loads application session state (scenes, items, selections) from SQLite."""
        conn = self.db.get_connection()
        cur = conn.cursor()

        # Load scenes ordered by order_index
        cur.execute("SELECT * FROM scenes ORDER BY order_index ASC;")
        scene_rows = cur.fetchall()

        if not scene_rows:
            return None

        scenes = []
        for r in scene_rows:
            raw = r["raw_json"]
            if raw:
                try:
                    s_dict = json.loads(raw)
                except Exception:
                    s_dict = {}
            else:
                s_dict = {}

            s_dict.update({
                "id": int(r["id"]) if r["id"].isdigit() else r["id"],
                "time_start": r["time_start"] or "",
                "time_end": r["time_end"] or "",
                "duration_seconds": r["duration"] or 0,
                "description_vi": r["description_vi"] or "",
                "dialogue_es": r["dialogue_es"] or "",
                "primary_keywords": (r["primary_keywords"] or "").split(",") if r["primary_keywords"] else [],
                "secondary_keywords": (r["secondary_keywords"] or "").split(",") if r["secondary_keywords"] else [],
                "mood": r["mood"] or "",
                "shot_type": r["shot_type"] or "",
            })
            scenes.append(s_dict)

        # Load media items and selections grouped by scene_id
        cur.execute("SELECT * FROM media_items;")
        media_rows = cur.fetchall()

        scene_items = {s["id"]: [] for s in scenes}
        selected_items = {s["id"]: {} for s in scenes}

        for mr in media_rows:
            sid_raw = mr["scene_id"]
            sid = int(sid_raw) if sid_raw.isdigit() else sid_raw
            if sid not in scene_items:
                scene_items[sid] = []
                selected_items[sid] = {}

            item_dict = {
                "id": mr["item_id"],
                "source": mr["source"],
                "type": mr["type"],
                "download_url": mr["download_url"],
                "thumb_url": mr["thumbnail_url"],
                "width": mr["width"],
                "height": mr["height"],
                "duration": mr["duration"],
                "author": mr["author"],
                "author_url": mr["author_url"],
                "page_url": mr["page_url"],
                "search_query": mr["search_query"],
            }
            if mr["raw_json"]:
                try:
                    extra = json.loads(mr["raw_json"])
                    item_dict.update(extra)
                except Exception:
                    pass

            scene_items[sid].append(item_dict)

            if mr["is_selected"]:
                item_key = f"{mr['source']}_{mr['type']}_{mr['item_id']}"
                selected_items[sid][item_key] = item_dict

        # Load current active scene
        cur.execute("SELECT value FROM app_config WHERE key = 'current_scene_id';")
        curr_row = cur.fetchone()
        curr_sid = None
        if curr_row and curr_row["value"]:
            val = curr_row["value"]
            curr_sid = int(val) if val.isdigit() else val

        # Load last json data
        cur.execute("SELECT value FROM app_config WHERE key = 'last_json_data';")
        jd_row = cur.fetchone()
        json_data = None
        if jd_row and jd_row["value"]:
            try:
                json_data = json.loads(jd_row["value"])
            except Exception:
                json_data = None

        return {
            "scenes": scenes,
            "json_data": json_data,
            "scene_items": scene_items,
            "selected_items": selected_items,
            "current_scene_id": curr_sid,
        }

    def save(self, state: Dict[str, Any]) -> None:
        """Saves current state (scenes, searched items, selections) into SQLite in a fast transaction."""
        scenes = state.get("scenes", [])
        json_data = state.get("json_data")
        scene_items = state.get("scene_items", {})
        selected_items = state.get("selected_items", {})
        current_scene_id = state.get("current_scene_id")

        conn = self.db.get_connection()
        with conn:
            # Save current scene
            if current_scene_id is not None:
                conn.execute(
                    "INSERT OR REPLACE INTO app_config (key, value) VALUES ('current_scene_id', ?);",
                    (str(current_scene_id),)
                )

            # Save json data if present
            if json_data is not None:
                conn.execute(
                    "INSERT OR REPLACE INTO app_config (key, value) VALUES ('last_json_data', ?);",
                    (json.dumps(json_data, ensure_ascii=False),)
                )

            # Clear previous scenes and media items
            conn.execute("DELETE FROM media_items;")
            conn.execute("DELETE FROM scenes;")

            # Insert scenes
            scene_data = []
            seen_sids = set()
            for idx, s in enumerate(scenes):
                raw_id = s.get("id")
                sid = str(raw_id) if (raw_id is not None and str(raw_id).strip() != "") else str(idx + 1)
                if sid in seen_sids:
                    sid = f"{sid}_{idx + 1}"
                seen_sids.add(sid)

                pk = ",".join(s.get("primary_keywords", []))
                sk = ",".join(s.get("secondary_keywords", []))
                raw_json = json.dumps(s, ensure_ascii=False)
                scene_data.append((
                    sid,
                    s.get("time_start", ""),
                    s.get("time_end", ""),
                    float(s.get("duration_seconds", 0) or 0),
                    s.get("description_vi", "") or s.get("mo_ta", ""),
                    s.get("dialogue_es", "") or s.get("dialogue", ""),
                    pk,
                    sk,
                    s.get("mood", ""),
                    s.get("shot_type", ""),
                    raw_json,
                    idx
                ))

            if scene_data:
                conn.executemany(
                    """INSERT OR REPLACE INTO scenes
                       (id, time_start, time_end, duration, description_vi, dialogue_es,
                        primary_keywords, secondary_keywords, mood, shot_type, raw_json, order_index)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);""",
                    scene_data
                )

            valid_scene_ids = seen_sids
            media_data = []
            for sid, items in scene_items.items():
                sid_str = str(sid)
                if sid_str not in valid_scene_ids:
                    continue
                selected_map = selected_items.get(sid, {})
                for item in items:
                    item_id = str(item.get("id", ""))
                    src = item.get("source", "unknown")
                    mtype = item.get("type", "video")
                    item_key = f"{src}_{mtype}_{item_id}"
                    row_key = f"{sid_str}_{item_key}"
                    is_sel = 1 if (item_key in selected_map or item in selected_map.values()) else 0

                    media_data.append((
                        row_key,
                        item_id,
                        src,
                        mtype,
                        sid_str,
                        item.get("download_url", ""),
                        item.get("thumb_url", "") or item.get("thumbnail_url", ""),
                        int(item.get("width", 0) or 0),
                        int(item.get("height", 0) or 0),
                        float(item.get("duration", 0) or 0),
                        item.get("author", ""),
                        item.get("author_url", ""),
                        item.get("page_url", ""),
                        item.get("search_query", ""),
                        is_sel,
                        json.dumps(item, ensure_ascii=False)
                    ))

            if media_data:
                conn.executemany(
                    """INSERT OR REPLACE INTO media_items
                       (key, item_id, source, type, scene_id, download_url, thumbnail_url,
                        width, height, duration, author, author_url, page_url, search_query, is_selected, raw_json)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);""",
                    media_data
                )

    def reset(self) -> None:
        """Clears all session state."""
        conn = self.db.get_connection()
        with conn:
            conn.execute("DELETE FROM media_items;")
            conn.execute("DELETE FROM scenes;")
            conn.execute("DELETE FROM app_config WHERE key = 'current_scene_id';")

    # Aliases
    load_state = load
    save_state = save
