"""SQLite 스키마 및 연결."""
import sqlite3
from pathlib import Path

DB_DIR = Path(__file__).resolve().parent.parent.parent / "data"
DB_PATH = DB_DIR / "viral_finder.db"

VIDEO_TABLE = """
CREATE TABLE IF NOT EXISTS video_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    platform TEXT NOT NULL,
    video_title TEXT,
    video_url TEXT UNIQUE NOT NULL,
    channel_name TEXT,
    subscriber_count INTEGER,
    view_count INTEGER,
    upload_date TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_video_url ON video_data(video_url);
CREATE INDEX IF NOT EXISTS idx_video_platform ON video_data(platform);
"""

CHANNEL_TABLE = """
CREATE TABLE IF NOT EXISTS monitored_channels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    platform TEXT NOT NULL,
    channel_id TEXT,
    channel_url TEXT,
    channel_name TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(platform, channel_id)
);
"""


def get_connection():
    """DB 연결 반환."""
    DB_DIR.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(DB_PATH)


def init_db():
    """테이블 생성."""
    conn = get_connection()
    try:
        conn.executescript(VIDEO_TABLE)
        conn.executescript(CHANNEL_TABLE)
        conn.commit()
    finally:
        conn.close()
