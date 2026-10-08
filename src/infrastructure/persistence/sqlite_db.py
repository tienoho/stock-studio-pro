"""
SQLite database connection manager and schema initialization.
Configured with WAL mode and foreign keys for high reliability and performance.
"""

import sqlite3
import threading
import shutil
from pathlib import Path
from ...core.constants import DB_FILE, LEGACY_DB_FILE


class SqliteDatabase:
    """Thread-safe SQLite database manager for production storage."""

    _instance = None
    _init_lock = threading.Lock()

    def __init__(self, db_path: Path = DB_FILE):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.db_path.exists() and LEGACY_DB_FILE.exists() and self.db_path == DB_FILE:
            try:
                shutil.copy2(str(LEGACY_DB_FILE), str(self.db_path))
            except Exception:
                pass
        self._local = threading.local()
        self.init_schema()

    @classmethod
    def get_instance(cls, db_path: Path = DB_FILE) -> "SqliteDatabase":
        with cls._init_lock:
            if cls._instance is None:
                cls._instance = cls(db_path)
            return cls._instance

    def get_connection(self) -> sqlite3.Connection:
        """Returns a thread-local SQLite connection with optimized PRAGMAs."""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            conn = sqlite3.connect(
                str(self.db_path),
                timeout=30.0,
                check_same_thread=False
            )
            conn.row_factory = sqlite3.Row
            # WAL mode for high concurrent read/write throughput
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.execute("PRAGMA foreign_keys=ON;")
            self._local.conn = conn
        return self._local.conn

    def init_schema(self) -> None:
        """Creates the required tables, indexes, and initial metadata."""
        conn = self.get_connection()
        with conn:
            conn.executescript("""
                -- Key-value store for global settings (output_dir, search_prefs, active scene, etc.)
                CREATE TABLE IF NOT EXISTS app_config (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                -- Structured storage for API keys with active toggling and usage timestamp
                CREATE TABLE IF NOT EXISTS api_keys (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    platform TEXT NOT NULL,
                    name TEXT NOT NULL,
                    key TEXT NOT NULL,
                    is_active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_used TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_api_keys_platform ON api_keys(platform, is_active);

                -- Structured storage for project timeline scenes
                CREATE TABLE IF NOT EXISTS scenes (
                    id TEXT PRIMARY KEY,
                    time_start TEXT,
                    time_end TEXT,
                    duration REAL DEFAULT 0,
                    description_vi TEXT,
                    dialogue_es TEXT,
                    primary_keywords TEXT,
                    secondary_keywords TEXT,
                    mood TEXT,
                    shot_type TEXT,
                    raw_json TEXT,
                    order_index INTEGER DEFAULT 0
                );

                -- Structured storage for searched & selected media items
                CREATE TABLE IF NOT EXISTS media_items (
                    key TEXT PRIMARY KEY,
                    item_id TEXT NOT NULL,
                    source TEXT NOT NULL,
                    type TEXT NOT NULL,
                    scene_id TEXT NOT NULL,
                    download_url TEXT,
                    thumbnail_url TEXT,
                    width INTEGER DEFAULT 0,
                    height INTEGER DEFAULT 0,
                    duration REAL DEFAULT 0,
                    author TEXT,
                    author_url TEXT,
                    page_url TEXT,
                    search_query TEXT,
                    is_selected INTEGER DEFAULT 0,
                    raw_json TEXT,
                    FOREIGN KEY (scene_id) REFERENCES scenes(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_media_scene ON media_items(scene_id, is_selected);

                -- Node workflow presets
                CREATE TABLE IF NOT EXISTS workflow_presets (
                    name TEXT PRIMARY KEY,
                    data_json TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                -- Persistent downloads audit history
                CREATE TABLE IF NOT EXISTS downloads_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_key TEXT UNIQUE,
                    scene_id TEXT,
                    source TEXT,
                    media_type TEXT,
                    item_id TEXT,
                    filepath TEXT,
                    filesize INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'completed',
                    downloaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_downloads_history_key ON downloads_history(item_key);
                CREATE INDEX IF NOT EXISTS idx_downloads_history_scene ON downloads_history(scene_id);
            """)

            # Dynamic migration for api_keys counter columns if not yet present
            cur = conn.cursor()
            cur.execute("PRAGMA table_info(api_keys);")
            cols = {row["name"] for row in cur.fetchall()}
            if "request_count" not in cols:
                conn.execute("ALTER TABLE api_keys ADD COLUMN request_count INTEGER DEFAULT 0;")
            if "error_count" not in cols:
                conn.execute("ALTER TABLE api_keys ADD COLUMN error_count INTEGER DEFAULT 0;")

    def backup_database(self, target_path: Path) -> bool:
        """Performs a live online SQLite backup using the native SQLite backup API without blocking."""
        try:
            target_path = Path(target_path)
            target_path.parent.mkdir(parents=True, exist_ok=True)
            source_conn = self.get_connection()
            dest_conn = sqlite3.connect(str(target_path))
            with dest_conn:
                source_conn.backup(dest_conn)
            dest_conn.close()
            return True
        except Exception as e:
            print(f"[SqliteDatabase] Live backup error: {e}")
            return False

    def checkpoint(self, truncate: bool = False) -> None:
        """Flushes the WAL journal to the main database file."""
        try:
            conn = self.get_connection()
            mode = "TRUNCATE" if truncate else "PASSIVE"
            conn.execute(f"PRAGMA wal_checkpoint({mode});")
        except Exception:
            pass

    def optimize(self) -> None:
        """Runs PRAGMA optimize to update query planner statistics."""
        try:
            conn = self.get_connection()
            conn.execute("PRAGMA optimize;")
        except Exception:
            pass

    def vacuum(self) -> None:
        """Rebuilds the database file, repacking it into a minimal amount of disk space."""
        try:
            conn = self.get_connection()
            conn.execute("VACUUM;")
        except Exception:
            pass

    def get_database_stats(self) -> dict:
        """Returns statistics on file size, WAL size, and row counts."""
        db_size_bytes = self.db_path.stat().st_size if self.db_path.exists() else 0
        wal_path = Path(f"{self.db_path}-wal")
        wal_size_bytes = wal_path.stat().st_size if wal_path.exists() else 0

        counts = {}
        try:
            conn = self.get_connection()
            cur = conn.cursor()
            for tbl in ["scenes", "media_items", "api_keys", "workflow_presets", "downloads_history"]:
                cur.execute(f"SELECT COUNT(*) FROM {tbl};")
                counts[tbl] = cur.fetchone()[0]
        except Exception:
            pass

        return {
            "db_path": str(self.db_path),
            "db_size_mb": round(db_size_bytes / (1024 * 1024), 2),
            "wal_size_kb": round(wal_size_bytes / 1024, 2),
            "table_counts": counts,
        }

    def close(self):
        """Optimizes, checkpoints, and cleanly closes the thread-local connection."""
        if hasattr(self._local, "conn") and self._local.conn:
            try:
                self.optimize()
                self.checkpoint(truncate=True)
                self._local.conn.close()
            except Exception:
                pass
            self._local.conn = None
