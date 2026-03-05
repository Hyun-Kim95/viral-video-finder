"""크롤링 공통: 재시도, rate limit."""
import time
from dataclasses import dataclass
from typing import List, Tuple, Optional

# 한 영상: (title, channel_name, view_count, subscriber_count, upload_date, video_url, platform)
CrawlResult = List[Tuple]


def with_retry(max_retries: int = 3, delay_sec: float = 2.0):
    """실패 시 재시도 데코레이터."""
    def deco(fn):
        def wrapper(*args, **kwargs):
            last = None
            for _ in range(max_retries):
                try:
                    return fn(*args, **kwargs)
                except Exception as e:
                    last = e
                    time.sleep(delay_sec)
            raise last
        return wrapper
    return deco


def rate_limit(delay_sec: float = 2.0):
    """요청 전 대기 (rate limit 완화)."""
    time.sleep(delay_sec)
