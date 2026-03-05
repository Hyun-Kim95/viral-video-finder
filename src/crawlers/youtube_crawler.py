"""YouTube 크롤링: API 우선, 실패 시 없으면 빈 결과 (추후 HTML fallback 가능)."""
import re
import time
from typing import List, Tuple, Optional
from ..config_loader import load_settings
from .base import with_retry, rate_limit

# 반환: (video_title, channel_name, view_count, subscriber_count, upload_date, video_url, platform)
PLATFORM = "youtube"


def _parse_int(s) -> Optional[int]:
    if s is None:
        return None
    if isinstance(s, int):
        return s
    s = str(s).replace(",", "").replace(" ", "")
    m = re.search(r"\d+", s)
    return int(m.group()) if m else None


class YouTubeCrawler:
    def __init__(self, api_key: Optional[str] = None, delay_sec: float = 2.0, max_retries: int = 3):
        settings = load_settings()
        self.api_key = api_key or settings.get("youtube", {}).get("api_key") or ""
        self.use_api = settings.get("youtube", {}).get("use_api", True)
        self.delay = delay_sec or settings.get("crawling", {}).get("request_delay_sec", 2)
        self.max_retries = max_retries or settings.get("crawling", {}).get("max_retries", 3)

    @with_retry(max_retries=3, delay_sec=2.0)
    def search_viral(self, query: str = "", max_results: int = 20) -> List[Tuple]:
        """검색어가 있으면 해당 키워드 인기 영상, 비어 있으면 전체 인기(트렌딩) 영상 수집."""
        q = (query or "").strip()
        if not self.api_key or not self.use_api:
            return self._search_fallback(q, max_results)
        import requests

        # 1) 검색어가 있는 경우: 키워드 기반 인기 영상
        if q:
            rate_limit(self.delay)
            url = "https://www.googleapis.com/youtube/v3/search"
            params = {
                "part": "snippet",
                "q": q,
                "type": "video",
                "maxResults": min(max_results, 50),
                "order": "viewCount",
                "key": self.api_key,
            }
            r = requests.get(url, params=params, timeout=30)
            if r.status_code != 200:
                return self._search_fallback(q, max_results)
            data = r.json()
            video_ids = [it["id"]["videoId"] for it in data.get("items", []) if it.get("id", {}).get("videoId")]
            if not video_ids:
                return []
            return self._video_details(video_ids)

        # 2) 검색어가 비어 있으면: 전체 인기(트렌딩) 영상
        rate_limit(self.delay)
        url = "https://www.googleapis.com/youtube/v3/videos"
        params = {
            "part": "snippet,statistics",
            "chart": "mostPopular",
            "maxResults": min(max_results, 50),
            "regionCode": "KR",  # 기본은 한국 인기 영상
            "key": self.api_key,
        }
        r = requests.get(url, params=params, timeout=30)
        if r.status_code != 200:
            return self._search_fallback(q, max_results)
        out: List[Tuple] = []
        for item in r.json().get("items", []):
            sid = item.get("snippet", {})
            stat = item.get("statistics", {})
            vid = item.get("id", "")
            title = sid.get("title", "")
            channel = sid.get("channelTitle", "")
            upload = sid.get("publishedAt", "")[:10] if sid.get("publishedAt") else ""
            views = _parse_int(stat.get("viewCount"))
            video_url = f"https://www.youtube.com/watch?v={vid}" if vid else ""
            out.append((title, channel, views, None, upload, video_url, PLATFORM))
        return out

    def _video_details(self, video_ids: List[str]) -> List[Tuple]:
        """video id 리스트로 상세 정보 조회."""
        if not self.api_key:
            return []
        rate_limit(self.delay)
        import requests
        url = "https://www.googleapis.com/youtube/v3/videos"
        parts = "snippet,statistics"
        out = []
        for i in range(0, len(video_ids), 50):
            chunk = video_ids[i : i + 50]
            params = {"part": parts, "id": ",".join(chunk), "key": self.api_key}
            r = requests.get(url, params=params, timeout=30)
            if r.status_code != 200:
                continue
            for item in r.json().get("items", []):
                sid = item.get("snippet", {})
                stat = item.get("statistics", {})
                vid = item.get("id", "")
                title = sid.get("title", "")
                channel = sid.get("channelTitle", "")
                upload = sid.get("publishedAt", "")[:10] if sid.get("publishedAt") else ""
                views = _parse_int(stat.get("viewCount"))
                video_url = f"https://www.youtube.com/watch?v={vid}" if vid else ""
                out.append((title, channel, views, None, upload, video_url, PLATFORM))
            if i + 50 < len(video_ids):
                rate_limit(self.delay)
        return out

    def _search_fallback(self, query: str, max_results: int) -> List[Tuple]:
        """API 없을 때: yt-dlp로 검색 결과 수집 (API 키 불필요)."""
        try:
            import yt_dlp
        except ImportError:
            return []
        search_query = (query or "").strip()
        # ytsearchN: 키워드 → 최대 N개 검색 결과, 검색어 없으면 트렌딩 피드 사용
        if search_query:
            url = f"ytsearch{min(max_results, 30)}:{search_query}"
        else:
            url = "https://www.youtube.com/feed/trending"
        out = []
        opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": False,
            "skip_download": True,
            "ignoreerrors": True,
        }
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
            if not info or not info.get("entries"):
                return []
            for entry in info["entries"]:
                if not entry or not isinstance(entry, dict):
                    continue
                vid = entry.get("id") or ""
                if isinstance(vid, dict):
                    vid = vid.get("id", "")
                url_raw = entry.get("webpage_url") or entry.get("url") or ""
                if isinstance(url_raw, str) and "watch?v=" in url_raw:
                    m = re.search(r"v=([A-Za-z0-9_-]+)", url_raw)
                    if m:
                        vid = vid or m.group(1)
                video_url = entry.get("webpage_url") or (entry.get("url") if isinstance(entry.get("url"), str) else None) or (f"https://www.youtube.com/watch?v={vid}" if vid else "")
                if not video_url:
                    continue
                title = entry.get("title") or "(제목 없음)"
                channel = entry.get("channel") or entry.get("uploader") or ""
                views = _parse_int(entry.get("view_count"))
                upload_date = entry.get("upload_date")  # YYYYMMDD
                if upload_date and len(str(upload_date)) >= 8:
                    upload_date = str(upload_date)
                    upload_date = f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:8]}"
                else:
                    upload_date = ""
                out.append((title, channel, views, None, upload_date or "", video_url, PLATFORM))
        except Exception:
            pass
        return out

    def channel_latest_videos(self, channel_id: str, max_results: int = 10) -> List[Tuple]:
        """채널 최신 영상 목록 (API)."""
        if not self.api_key:
            return []
        rate_limit(self.delay)
        import requests
        url = "https://www.googleapis.com/youtube/v3/search"
        params = {
            "part": "snippet",
            "channelId": channel_id,
            "type": "video",
            "maxResults": min(max_results, 50),
            "order": "date",
            "key": self.api_key,
        }
        r = requests.get(url, params=params, timeout=30)
        if r.status_code != 200:
            return []
        video_ids = [it["id"]["videoId"] for it in r.json().get("items", []) if it.get("id", {}).get("videoId")]
        return self._video_details(video_ids) if video_ids else []

    def channel_id_from_url(self, channel_url: str) -> Optional[str]:
        """URL에서 channel id 추출 (API로 해결 가능)."""
        # /channel/UCxxx 또는 /@handle
        m = re.search(r"youtube\.com/channel/([A-Za-z0-9_-]+)", channel_url)
        if m:
            return m.group(1)
        m = re.search(r"youtube\.com/@([A-Za-z0-9_-]+)", channel_url)
        if m and self.api_key:
            rate_limit(self.delay)
            import requests
            r = requests.get(
                "https://www.googleapis.com/youtube/v3/channels",
                params={"part": "id", "forHandle": m.group(1), "key": self.api_key},
                timeout=30,
            )
            if r.status_code == 200 and r.json().get("items"):
                return r.json()["items"][0]["id"]
        return None
