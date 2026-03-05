"""video_data CRUD."""
from .schema import get_connection


class VideoRepository:
    @staticmethod
    def insert(platform, video_title, video_url, channel_name=None,
               subscriber_count=None, view_count=None, upload_date=None):
        """영상 삽입 (중복 URL은 무시)."""
        conn = get_connection()
        try:
            conn.execute(
                """INSERT OR IGNORE INTO video_data
                   (platform, video_title, video_url, channel_name, subscriber_count, view_count, upload_date)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (platform, video_title or "", video_url, channel_name or "", subscriber_count, view_count, upload_date or "")
            )
            conn.commit()
            return conn.total_changes > 0
        finally:
            conn.close()

    @staticmethod
    def insert_many(rows):
        """여러 행 삽입. rows: list of (platform, title, url, channel_name, subs, views, date)."""
        conn = get_connection()
        try:
            conn.executemany(
                """INSERT OR IGNORE INTO video_data
                   (platform, video_title, video_url, channel_name, subscriber_count, view_count, upload_date)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                rows,
            )
            conn.commit()
            return conn.total_changes
        finally:
            conn.close()

    @staticmethod
    def exists_by_url(video_url):
        conn = get_connection()
        try:
            cur = conn.execute("SELECT 1 FROM video_data WHERE video_url = ? LIMIT 1", (video_url,))
            return cur.fetchone() is not None
        finally:
            conn.close()

    @staticmethod
    def delete_by_url(video_url):
        """URL로 영상 한 건 삭제."""
        conn = get_connection()
        try:
            cur = conn.execute("DELETE FROM video_data WHERE video_url = ?", (video_url,))
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()

    @staticmethod
    def list_all():
        """전체 목록 (제목, 채널, 조회수, 구독자, 업로드날짜, 수집시각, URL, platform)."""
        conn = get_connection()
        try:
            cur = conn.execute(
                """SELECT video_title, channel_name, view_count, subscriber_count, upload_date, created_at, video_url, platform
                   FROM video_data ORDER BY created_at DESC"""
            )
            return cur.fetchall()
        finally:
            conn.close()
