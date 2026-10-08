"""
SQLite-based configuration repository implementing IConfigRepository.
Stores API keys and application configuration with Base64 obfuscation and auto-migration from JSON.
"""

import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from ...core.interfaces.storage import IConfigRepository
from ...core.constants import DB_FILE, CONFIG_FILE, DEFAULT_OUTPUT_DIR
from .sqlite_db import SqliteDatabase
from .json_config_repo import obfuscate, deobfuscate, JsonConfigRepository


class SqliteConfigRepository(IConfigRepository):
    """Production-grade configuration repository backed by SQLite database."""

    DEFAULT_CONFIG = {
        "pexels_keys": [],
        "pixabay_keys": [],
        "vecteezy_keys": [],
        "coverr_keys": [],
        "output_dir": str(DEFAULT_OUTPUT_DIR),
        "search_prefs": {},
    }

    def __init__(
        self,
        db: Optional[SqliteDatabase] = None,
        json_fallback_path: Path = CONFIG_FILE,
        legacy_json_path: Optional[Path] = None,
    ):
        self.db = db or SqliteDatabase.get_instance()
        self.json_fallback_path = Path(legacy_json_path or json_fallback_path)
        self._check_and_migrate()

    def _check_and_migrate(self):
        """Migrate from old JSON configuration file if SQLite api_keys is empty."""
        conn = self.db.get_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM api_keys;")
        count = cur.fetchone()[0]

        if count == 0 and self.json_fallback_path.exists():
            try:
                old_repo = JsonConfigRepository(self.json_fallback_path)
                old_config = old_repo.load()
                self.save(old_config)
                print(f"[SqliteConfigRepository] Migrated legacy JSON configuration to SQLite.")
            except Exception as e:
                print(f"[SqliteConfigRepository] Migration error: {e}")

    def load(self) -> Dict[str, Any]:
        """Loads configuration from SQLite into a dictionary format compatible with the application."""
        conn = self.db.get_connection()
        cur = conn.cursor()

        # Load scalar settings
        cur.execute("SELECT key, value FROM app_config;")
        config_map = {row["key"]: row["value"] for row in cur.fetchall()}

        output_dir = config_map.get("output_dir", str(DEFAULT_OUTPUT_DIR))
        search_prefs_raw = config_map.get("search_prefs")
        try:
            search_prefs = json.loads(search_prefs_raw) if search_prefs_raw else {}
        except Exception:
            search_prefs = {}

        # Load API keys per platform
        cur.execute("SELECT id, platform, name, key, is_active FROM api_keys WHERE is_active = 1;")
        rows = cur.fetchall()

        keys_by_platform = {
            "pexels": [],
            "pixabay": [],
            "vecteezy": [],
            "coverr": [],
        }

        for row in rows:
            plat = row["platform"].lower()
            if plat in keys_by_platform:
                keys_by_platform[plat].append({
                    "id": row["id"],
                    "name": row["name"],
                    "key": deobfuscate(row["key"]),
                    "active": bool(row["is_active"])
                })

        result = {
            "pexels_keys": keys_by_platform["pexels"],
            "pixabay_keys": keys_by_platform["pixabay"],
            "vecteezy_keys": keys_by_platform["vecteezy"],
            "coverr_keys": keys_by_platform["coverr"],
            "output_dir": output_dir,
            "search_prefs": search_prefs,
        }

        # Include any extra configuration entries stored in app_config
        reserved_keys = {"output_dir", "search_prefs", "last_json_data", "current_scene_id"}
        for k, v in config_map.items():
            if k in reserved_keys:
                continue
            try:
                result[k] = json.loads(v)
            except Exception:
                result[k] = v

        return result

    def save(self, config: Dict[str, Any]) -> None:
        """Saves configuration and synchronizes keys to SQLite."""
        conn = self.db.get_connection()
        with conn:
            # Save scalar config
            output_dir = str(config.get("output_dir", DEFAULT_OUTPUT_DIR))
            search_prefs = json.dumps(config.get("search_prefs", {}), ensure_ascii=False)

            conn.execute("INSERT OR REPLACE INTO app_config (key, value) VALUES (?, ?);", ("output_dir", output_dir))
            conn.execute("INSERT OR REPLACE INTO app_config (key, value) VALUES (?, ?);", ("search_prefs", search_prefs))

            # Save any extra scalar or json-serializable settings
            reserved_config_keys = {
                "pexels_keys", "pixabay_keys", "vecteezy_keys", "coverr_keys",
                "output_dir", "search_prefs", "last_json_data", "current_scene_id"
            }
            for k, v in config.items():
                if k in reserved_config_keys:
                    continue
                val_str = json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else str(v)
                conn.execute("INSERT OR REPLACE INTO app_config (key, value) VALUES (?, ?);", (k, val_str))

            # Synchronize keys if provided in dict
            for plat in ["pexels", "pixabay", "vecteezy", "coverr"]:
                key_list_name = f"{plat}_keys"
                if key_list_name in config and isinstance(config[key_list_name], list):
                    current_enc_keys = set()
                    for k in config[key_list_name]:
                        raw_key = k.get("key", "").strip()
                        if not raw_key:
                            continue
                        name = k.get("name", f"{plat.capitalize()} Key")
                        enc_key = obfuscate(raw_key)
                        current_enc_keys.add(enc_key)

                        cur = conn.cursor()
                        cur.execute("SELECT id FROM api_keys WHERE platform = ? AND key = ?;", (plat, enc_key))
                        existing = cur.fetchone()
                        if not existing:
                            conn.execute(
                                "INSERT INTO api_keys (platform, name, key, is_active) VALUES (?, ?, ?, 1);",
                                (plat, name, enc_key)
                            )
                        else:
                            conn.execute(
                                "UPDATE api_keys SET name = ? WHERE id = ?;",
                                (name, existing["id"])
                            )

                    # Remove keys that were deleted from config (preserve deactivated keys)
                    cur = conn.cursor()
                    cur.execute("SELECT id, key, is_active FROM api_keys WHERE platform = ?;", (plat,))
                    for row in cur.fetchall():
                        if row["key"] not in current_enc_keys:
                            if row["is_active"]:
                                conn.execute("DELETE FROM api_keys WHERE id = ?;", (row["id"],))

    # ═══════════════════════════════════════════════════════════════
    # DIRECT API KEY MANAGEMENT METHODS (FOR UI)
    # ═══════════════════════════════════════════════════════════════

    def get_api_keys(self, platform: Optional[str] = None) -> List[Dict[str, Any]]:
        """Returns all keys (both active and inactive) for UI management table."""
        conn = self.db.get_connection()
        cur = conn.cursor()
        if platform:
            cur.execute("SELECT id, platform, name, key, is_active, created_at, last_used FROM api_keys WHERE platform = ? ORDER BY id DESC;", (platform.lower(),))
        else:
            cur.execute("SELECT id, platform, name, key, is_active, created_at, last_used FROM api_keys ORDER BY platform, id DESC;")

        return [
            {
                "id": row["id"],
                "platform": row["platform"],
                "name": row["name"],
                "key": deobfuscate(row["key"]),
                "is_active": bool(row["is_active"]),
                "created_at": row["created_at"],
                "last_used": row["last_used"],
            }
            for row in cur.fetchall()
        ]

    def add_api_key(self, platform: str, name: str, key_str: str, is_active: bool = True) -> int:
        """Adds a new key directly into SQLite and returns the new ID."""
        key_clean = key_str.strip()
        if not key_clean:
            return 0
        enc_key = obfuscate(key_clean)
        plat = platform.lower()

        conn = self.db.get_connection()
        with conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO api_keys (platform, name, key, is_active) VALUES (?, ?, ?, ?);",
                (plat, name or f"{platform.capitalize()} Key", enc_key, 1 if is_active else 0)
            )
            return cur.lastrowid

    def delete_api_key(self, key_id: int) -> bool:
        """Deletes a key by ID."""
        conn = self.db.get_connection()
        with conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM api_keys WHERE id = ?;", (key_id,))
            return cur.rowcount > 0

    def toggle_api_key(self, key_id: int, is_active: bool) -> bool:
        """Enables or disables a key."""
        conn = self.db.get_connection()
        with conn:
            cur = conn.cursor()
            cur.execute("UPDATE api_keys SET is_active = ? WHERE id = ?;", (1 if is_active else 0, key_id))
            return cur.rowcount > 0

    def update_key_last_used(self, key_id: int) -> None:
        """Records timestamp of API usage."""
        conn = self.db.get_connection()
        with conn:
            conn.execute("UPDATE api_keys SET last_used = CURRENT_TIMESTAMP WHERE id = ?;", (key_id,))

    def record_key_usage(self, platform: str, raw_key: str) -> None:
        """Records timestamp of API usage by platform and raw key string."""
        enc_key = obfuscate(raw_key.strip())
        conn = self.db.get_connection()
        with conn:
            conn.execute(
                "UPDATE api_keys SET last_used = CURRENT_TIMESTAMP WHERE platform = ? AND key = ?;",
                (platform.lower(), enc_key)
            )

    # Aliases
    load_config = load
    save_config = save
