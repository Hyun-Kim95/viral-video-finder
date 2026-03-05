"""APScheduler 기반 주기적 탐색 (5/10/30분)."""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from typing import Callable, Optional

INTERVAL_OPTIONS = [5, 10, 30]  # 분


class CrawlScheduler:
    def __init__(self):
        self._scheduler = BackgroundScheduler()
        self._job_id = "crawl_job"
        self._interval_minutes = 10

    def set_interval(self, minutes: int):
        if minutes in INTERVAL_OPTIONS:
            self._interval_minutes = minutes

    def start(self, task: Callable[[], None]):
        """주기적으로 task 실행."""
        self.stop()
        self._scheduler.add_job(
            task,
            trigger=IntervalTrigger(minutes=self._interval_minutes),
            id=self._job_id,
            replace_existing=True,
        )
        if not self._scheduler.running:
            self._scheduler.start()

    def stop(self):
        try:
            self._scheduler.remove_job(self._job_id)
        except Exception:
            pass
        # scheduler는 유지하고 job만 제거

    def shutdown(self):
        self._scheduler.shutdown(wait=False)

    @property
    def is_running(self) -> bool:
        return self._scheduler.running and self._scheduler.get_job(self._job_id) is not None
