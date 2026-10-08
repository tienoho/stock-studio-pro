"""
SQLite repository for saving, listing, and loading node-based workflow presets.
"""

import json
from typing import List, Dict, Any, Optional
from .sqlite_db import SqliteDatabase


class SqliteWorkflowRepository:
    """Manages workflow presets persisted in SQLite."""

    def __init__(self, db: Optional[SqliteDatabase] = None):
        self.db = db or SqliteDatabase.get_instance()

    def save_preset(self, name: str, payload: Dict[str, Any]) -> bool:
        """Saves or updates a workflow preset by name."""
        name_clean = name.strip()
        if not name_clean:
            return False

        data_json = json.dumps(payload, ensure_ascii=False)
        conn = self.db.get_connection()
        with conn:
            conn.execute(
                """INSERT OR REPLACE INTO workflow_presets (name, data_json, updated_at)
                   VALUES (?, ?, CURRENT_TIMESTAMP);""",
                (name_clean, data_json)
            )
        return True

    def get_preset(self, name: str) -> Optional[Dict[str, Any]]:
        """Retrieves a workflow preset payload by name."""
        conn = self.db.get_connection()
        cur = conn.cursor()
        cur.execute("SELECT data_json FROM workflow_presets WHERE name = ?;", (name.strip(),))
        row = cur.fetchone()
        if row and row["data_json"]:
            try:
                return json.loads(row["data_json"])
            except Exception:
                return None
        return None

    def list_presets(self) -> List[str]:
        """Returns all preset names ordered by most recently updated."""
        conn = self.db.get_connection()
        cur = conn.cursor()
        cur.execute("SELECT name FROM workflow_presets ORDER BY updated_at DESC;")
        return [row["name"] for row in cur.fetchall()]

    def delete_preset(self, name: str) -> bool:
        """Deletes a workflow preset by name."""
        conn = self.db.get_connection()
        with conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM workflow_presets WHERE name = ?;", (name.strip(),))
            return cur.rowcount > 0
