"""Instagram 크롤링: instaloader로 공개 프로필 최신 영상 수집 (로그인 없이)."""
import time
import re
import traceback
from typing import List, Tuple, Optional

PLATFORM = "instagram"

try:
    import instaloader
    INSTALOADER_AVAILABLE = True
except ImportError:
    INSTALOADER_AVAILABLE = False
    instaloader = None


def _username_from_input(text: str) -> Optional[str]:
    """URL 또는 @username 에서 username 추출."""
    if not text or not text.strip():
        return None
    text = text.strip()
    m = re.search(r"instagram\.com/([A-Za-z0-9_.]+)/?", text)
    if m:
        return m.group(1).split("?")[0]
    return text.lstrip("@").split()[0]


class InstagramCrawler:
    """공개 프로필 최신 게시물 중 영상만 수집. instaloader 필요."""

    def __init__(self, delay_sec: float = 2.0, max_retries: int = 3):
        self.delay = delay_sec
        self.max_retries = max_retries
        self._loader = None

    def _get_loader(self):
        if not INSTALOADER_AVAILABLE:
            return None
        if self._loader is None:
            self._loader = instaloader.Instaloader(
                quiet=True,
                download_pictures=False,
                download_videos=False,
                download_video_thumbnails=False,
                download_geotags=False,
                download_comments=False,
                save_metadata=False,
                compress_json=False,
            )
        return self._loader

    def search_viral(self, query: str = "", max_results: int = 20) -> List[Tuple]:
        """인스타는 검색 API 없음 → 빈 리스트 (해시태그 검색은 로그인 필요)."""
        return []

    def user_recent_videos(
        self, username: str, max_results: int = 10
    ) -> List[Tuple]:
        """
        공개 프로필의 최신 게시물 중 영상만 수집.
        반환: (title, channel_name, view_count=likes, subscriber_count=followers, upload_date, video_url, platform)
        """
        loader = self._get_loader()
        if not loader:
            return []

        username = _username_from_input(username) or username
        if not username:
            return []

        out = []
        try:
            time.sleep(self.delay)
            profile = instaloader.Profile.from_username(loader.context, username)
            followers = profile.followers if profile.followers else None
            count = 0
            for post in profile.get_posts():
                if count >= max_results:
                    break
                if not getattr(post, "is_video", False):
                    continue
                count += 1
                title = (post.caption or "").split("\n")[0][:200] if post.caption else "(영상)"
                view_count = getattr(post, "video_view_count", None) or post.likes or 0
                date_str = ""
                if getattr(post, "date_utc", None):
                    date_str = post.date_utc.strftime("%Y-%m-%d")
                shortcode = getattr(post, "shortcode", None) or ""
                url = f"https://www.instagram.com/p/{shortcode}/" if shortcode else ""
                out.append(
                    (title, username, view_count, followers, date_str, url, PLATFORM)
                )
                time.sleep(self.delay * 0.5)
        except Exception as e:
            # 콘솔에 상세 에러 출력 후, 상위에서 처리할 수 있도록 예외를 다시 발생시킨다.
            print(f"[InstagramCrawler] 에러 발생 (username={username!r}): {e}")
            traceback.print_exc()
            raise
        return out
