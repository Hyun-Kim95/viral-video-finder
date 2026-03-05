"""데이터 필터링 및 중복 제거, 결과 저장."""
from typing import List, Tuple, Any
from .db import VideoRepository
from .models import SearchConditions

# 한 행: (video_title, channel_name, view_count, subscriber_count, upload_date, video_url, platform)
VideoRow = Tuple[Any, ...]


def filter_by_conditions(rows: List[VideoRow], conditions: SearchConditions) -> List[VideoRow]:
    """조건 충족하는 행만 반환."""
    out = []
    for row in rows:
        # (video_title, channel_name, view_count, subscriber_count, upload_date, video_url, platform)
        if len(row) < 7:
            continue
        _, channel_name, view_count, subscriber_count, upload_date, _, _ = row[:7]
        if conditions.matches(subscriber_count, view_count, upload_date):
            out.append(row)
    return out


def dedupe_and_save(rows: List[Tuple], repo: VideoRepository = None) -> int:
    """URL 기준 중복 제거 후 DB 저장. 새로 저장된 개수 반환."""
    repo = repo or VideoRepository()
    seen = set()
    to_insert = []
    for row in rows:
        if len(row) < 7:
            continue
        # (platform, video_title, video_url, channel_name, subscriber_count, view_count, upload_date)
        platform = row[6] if len(row) > 6 else "youtube"
        title = row[0]
        url = row[5] if len(row) > 5 else ""
        channel = row[1]
        subs = row[3] if len(row) > 3 else None
        views = row[2] if len(row) > 2 else None
        upload = row[4] if len(row) > 4 else None
        if not url or url in seen:
            continue
        seen.add(url)
        to_insert.append((platform, title, url, channel, subs, views, upload))
    return repo.insert_many(to_insert)
