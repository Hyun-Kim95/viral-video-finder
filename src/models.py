"""조건 설정 모델: 팔로워/구독자, 조회수, 업로드 기간, 탐색 주기."""
from dataclasses import dataclass
from typing import Optional
from datetime import datetime, timedelta


@dataclass
class SearchConditions:
    """바이럴 탐색 조건."""
    max_subscribers: Optional[int] = None   # 이하 (예: 1000)
    min_views: Optional[int] = None        # 이상 (예: 2_000_000)
    upload_within_days: Optional[int] = None  # 업로드 후 N일 이내 (예: 3)
    interval_minutes: int = 10             # 탐색 주기: 5, 10, 30

    def matches(self, subscriber_count: Optional[int], view_count: Optional[int], upload_date_str: Optional[str]) -> bool:
        """단일 영상이 조건 충족 여부."""
        if self.max_subscribers is not None and subscriber_count is not None:
            if subscriber_count > self.max_subscribers:
                return False
        if self.min_views is not None and view_count is not None:
            if view_count < self.min_views:
                return False
        if self.upload_within_days is not None and upload_date_str:
            try:
                # YYYY-MM-DD 또는 유사 형식
                if "T" in upload_date_str:
                    upload_date = datetime.fromisoformat(upload_date_str.replace("Z", "+00:00"))
                else:
                    upload_date = datetime.strptime(upload_date_str[:10], "%Y-%m-%d")
                if upload_date.tzinfo:
                    now = datetime.now(upload_date.tzinfo)
                else:
                    now = datetime.now()
                if (now - upload_date.replace(tzinfo=None)).days > self.upload_within_days:
                    return False
            except Exception:
                pass
        return True


@dataclass
class ChannelMonitorConditions:
    """채널 모니터링 조건."""
    min_views: Optional[int] = None  # 예: 50_000 이상
    interval_minutes: int = 10
