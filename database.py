import sqlite3
import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional

DB_FILE = "news_monitor.db"

class Database:
    def __init__(self, db_path: str = DB_FILE):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Table for settings
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            ''')
            
            # Table for monitored accounts / feeds
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS accounts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    platform TEXT DEFAULT 'x',
                    identifier TEXT UNIQUE NOT NULL,
                    display_name TEXT,
                    is_active INTEGER DEFAULT 1,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Table for seen posts to avoid duplicate notifications
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS seen_posts (
                    post_id TEXT PRIMARY KEY,
                    platform TEXT,
                    account_identifier TEXT,
                    title TEXT,
                    published_at TIMESTAMP,
                    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Table for logs
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    level TEXT,
                    message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.commit()

    # Settings Methods
    def get_setting(self, key: str, default: Any = None) -> Any:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
            row = cursor.fetchone()
            if row:
                try:
                    return json.loads(row["value"])
                except Exception:
                    return row["value"]
            return default

    def set_setting(self, key: str, value: Any):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            str_val = json.dumps(value) if not isinstance(value, str) else value
            cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str_val))
            conn.commit()

    # Account Methods
    def add_account(self, identifier: str, display_name: str = "", platform: str = "x") -> bool:
        identifier = identifier.strip().lstrip("@")
        if not identifier:
            return False
        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "INSERT INTO accounts (platform, identifier, display_name, is_active) VALUES (?, ?, ?, 1)",
                    (platform, identifier, display_name or identifier)
                )
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                return False

    def get_accounts(self, active_only: bool = False) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM accounts"
            if active_only:
                query += " WHERE is_active = 1"
            cursor.execute(query)
            return [dict(row) for row in cursor.fetchall()]

    def delete_account(self, account_id: int):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
            conn.commit()

    def toggle_account(self, account_id: int, is_active: bool):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE accounts SET is_active = ? WHERE id = ?", (1 if is_active else 0, account_id))
            conn.commit()

    # Seen Post Methods
    def is_post_seen(self, post_id: str) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM seen_posts WHERE post_id = ?", (post_id,))
            return cursor.fetchone() is not None

    def mark_post_seen(self, post_id: str, platform: str, account_identifier: str, title: str, published_at: Optional[str] = None):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR IGNORE INTO seen_posts (post_id, platform, account_identifier, title, published_at) VALUES (?, ?, ?, ?, ?)",
                (post_id, platform, account_identifier, title[:200], published_at)
            )
            conn.commit()

    # Log Methods
    def add_log(self, level: str, message: str):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO logs (level, message) VALUES (?, ?)", (level, message))
            conn.commit()

    def get_recent_logs(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM logs ORDER BY id DESC LIMIT ?", (limit,))
            return [dict(row) for row in cursor.fetchall()]
