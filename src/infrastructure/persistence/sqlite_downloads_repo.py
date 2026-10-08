"""
SQLite repository for tracking download history and auditing downloaded files.
"""

from typing import List, Dict, Any, Optional
from .sqlite_db import SqliteDatabase


class SqliteDownloadsRepository:
    """Records and queries persistent download history in SQLite."""

    def __init__(self, db: Optional[SqliteDatabase] = None):
        self.db = db or SqliteDatabase.get_instance()

    def record_download(
        self,
        item_key: str,
        scene_id: str,
        source: str,
        media_type: str,
        item_id: str,
        filepath: str,
        filesize: int = 0,
        status: str = "completed"
    ) -> bool:
        """Records or updates a downloaded media item entry."""
        conn = self.db.get_connection()
        with conn:
            conn.execute(
                """INSERT OR REPLACE INTO downloads_history
                   (item_key, scene_id, source, media_type, item_id, filepath, filesize, status, downloaded_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP);""",
                (item_key, str(scene_id), source, media_type, str(item_id), filepath, filesize, status)
            )
        return True

    def is_downloaded(self, item_key: str) -> bool:
        """Checks if a given item has already been successfully downloaded."""
        conn = self.db.get_connection()
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM downloads_history WHERE item_key = ? AND status = 'completed';", (item_key,))
        return cur.fetchone() is not None

    def get_download_info(self, item_key: str) -> Optional[Dict[str, Any]]:
        """Retrieves download record details for an item."""
        conn = self.db.get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM downloads_history WHERE item_key = ?;", (item_key,))
        row = cur.fetchone()
        if row:
            return {
                "id": row["id"],
                "item_key": row["item_key"],
                "scene_id": row["scene_id"],
                "source": row["source"],
                "media_type": row["media_type"],
                "item_id": row["item_id"],
                "filepath": row["filepath"],
                "filesize": row["filesize"],
                "status": row["status"],
                "downloaded_at": row["downloaded_at"],
            }
        return None

    def get_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Returns the most recent download records."""
        conn = self.db.get_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM downloads_history ORDER BY downloaded_at DESC LIMIT ?;",
            (limit,)
        )
        return [
            {
                "id": row["id"],
                "item_key": row["item_key"],
                "scene_id": row["scene_id"],
                "source": row["source"],
                "media_type": row["media_type"],
                "item_id": row["item_id"],
                "filepath": row["filepath"],
                "filesize": row["filesize"],
                "status": row["status"],
                "downloaded_at": row["downloaded_at"],
            }
            for row in cur.fetchall()
        ]

    def clear_history(self) -> None:
        """Clears all download history records."""
        conn = self.db.get_connection()
        with conn:
            conn.execute("DELETE FROM downloads_history;")
