"""모니터링 채널 CRUD."""
from .schema import get_connection


class ChannelRepository:
    @staticmethod
    def add(platform, channel_id=None, channel_url=None, channel_name=None):
        conn = get_connection()
        try:
            conn.execute(
                """INSERT OR REPLACE INTO monitored_channels (platform, channel_id, channel_url, channel_name)
                   VALUES (?, ?, ?, ?)""",
                (platform, channel_id or "", channel_url or "", channel_name or ""),
            )
            conn.commit()
            return True
        finally:
            conn.close()

    @staticmethod
    def delete(channel_id_or_url, platform):
        conn = get_connection()
        try:
            cur = conn.execute(
                "DELETE FROM monitored_channels WHERE platform = ? AND (channel_id = ? OR channel_url = ?)",
                (platform, channel_id_or_url, channel_id_or_url),
            )
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()

    @staticmethod
    def list_all(platform=None):
        conn = get_connection()
        try:
            if platform:
                cur = conn.execute(
                    "SELECT id, platform, channel_id, channel_url, channel_name FROM monitored_channels WHERE platform = ?",
                    (platform,),
                )
            else:
                cur = conn.execute(
                    "SELECT id, platform, channel_id, channel_url, channel_name FROM monitored_channels ORDER BY platform, channel_name"
                )
            return cur.fetchall()
        finally:
            conn.close()
