"""메인 윈도우: 조건 설정, 채널 관리, 크롤링 제어, 결과 리스트 통합."""
import sys
from pathlib import Path
from datetime import datetime, timezone

from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QSpinBox,
    QComboBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QAbstractItemView,
    QMessageBox,
    QHeaderView,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QUrl
from PyQt5.QtGui import QDesktopServices

# 상위 경로에서 import
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from src.db import init_db, VideoRepository, ChannelRepository
from src.models import SearchConditions
from src.filtering import filter_by_conditions, dedupe_and_save
from src.crawlers import YouTubeCrawler, InstagramCrawler
from src.scheduler import CrawlScheduler, INTERVAL_OPTIONS


class CrawlWorker(QThread):
    """크롤링을 백그라운드에서 실행."""
    finished = pyqtSignal(int)  # 새로 저장된 개수
    error = pyqtSignal(str)

    def __init__(self, conditions: SearchConditions, search_query: str, run_channel_monitor: bool):
        super().__init__()
        self.conditions = conditions
        self.search_query = search_query
        self.run_channel_monitor = run_channel_monitor

    def run(self):
        try:
            repo = VideoRepository()
            yt = YouTubeCrawler()
            ig = InstagramCrawler()
            all_rows = []

            # 1) YouTube 검색 (검색어 있으면 키워드 검색, 비면 인기/트렌딩)
            rows = yt.search_viral(self.search_query.strip() if self.search_query else "", max_results=25)
            all_rows.extend(rows)

            # 2) 채널 모니터링
            if self.run_channel_monitor:
                for row in ChannelRepository.list_all("youtube"):
                    _id, platform, ch_id, ch_url, ch_name = row[0], row[1], row[2], row[3], row[4]
                    cid = ch_id or (yt.channel_id_from_url(ch_url) if ch_url else None)
                    if cid:
                        rows = yt.channel_latest_videos(cid, max_results=10)
                        all_rows.extend(rows)
                for row in ChannelRepository.list_all("instagram"):
                    _id, platform, ch_id, ch_url, ch_name = row[0], row[1], row[2], row[3], row[4]
                    username = ch_id or (ch_url.replace("https://www.instagram.com/", "").replace("https://instagram.com/", "").strip("/").split("?")[0] if ch_url else None) or ch_name
                    if username:
                        rows = ig.user_recent_videos(username, max_results=10)
                        all_rows.extend(rows)

            # 3) 조건 필터 + 중복 제거 저장
            filtered = filter_by_conditions(all_rows, self.conditions)
            added = dedupe_and_save(filtered, repo)
            self.finished.emit(added)
        except Exception as e:
            self.error.emit(str(e))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        init_db()
        self.repo = VideoRepository()
        self.channel_repo = ChannelRepository()
        self.scheduler = CrawlScheduler()
        self.worker = None
        self.setWindowTitle("Viral Video Finder")
        self.setMinimumSize(900, 600)
        self.resize(1000, 700)
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # ---- 조건 설정 패널 ----
        cond_group = QGroupBox("조건 설정")
        cond_layout = QHBoxLayout(cond_group)
        cond_layout.addWidget(QLabel("구독자 수 이하:"))
        self.max_subs = QSpinBox()
        self.max_subs.setRange(0, 100_000_000)
        self.max_subs.setSpecialValueText("제한 없음")
        self.max_subs.setValue(0)
        cond_layout.addWidget(self.max_subs)
        cond_layout.addWidget(QLabel("조회수 이상:"))
        self.min_views = QSpinBox()
        self.min_views.setRange(0, 1_000_000_000)
        self.min_views.setValue(0)
        cond_layout.addWidget(self.min_views)
        cond_layout.addWidget(QLabel("업로드 N일 이내:"))
        self.upload_days = QSpinBox()
        self.upload_days.setRange(0, 365)
        self.upload_days.setSpecialValueText("제한 없음")
        self.upload_days.setValue(0)
        cond_layout.addWidget(self.upload_days)
        cond_layout.addWidget(QLabel("탐색 주기(분):"))
        self.interval_combo = QComboBox()
        self.interval_combo.addItems([str(m) for m in INTERVAL_OPTIONS])
        self.interval_combo.setCurrentText("10")
        cond_layout.addWidget(self.interval_combo)
        cond_layout.addWidget(QLabel("검색어:"))
        self.search_query = QLineEdit()
        self.search_query.setPlaceholderText("비우면 YouTube 인기/트렌딩 영상")
        cond_layout.addWidget(self.search_query)
        layout.addWidget(cond_group)

        # ---- 채널 관리 패널 ----
        ch_group = QGroupBox("채널 / 계정 모니터링 (YouTube, Instagram)")
        ch_layout = QVBoxLayout(ch_group)
        ch_hint = QLabel("※ 인스타: 아래에 추가한 계정의 최신 영상만 수집. 반드시 URL에 나오는 계정 ID 입력 (표시이름 사용자명은 불가)")
        ch_hint.setStyleSheet("color: #666; font-size: 11px;")
        ch_layout.addWidget(ch_hint)
        ch_row = QHBoxLayout()
        ch_row.addWidget(QLabel("플랫폼:"))
        self.platform_combo = QComboBox()
        self.platform_combo.addItems(["YouTube", "Instagram"])
        ch_row.addWidget(self.platform_combo)
        self.channel_input = QLineEdit()
        self.channel_input.setPlaceholderText("YouTube: 채널 URL/ID  |  인스타: 계정 ID 또는 instagram.com/계정ID")
        ch_row.addWidget(self.channel_input)
        btn_add = QPushButton("추가")
        btn_add.clicked.connect(self.add_channel)
        ch_row.addWidget(btn_add)
        btn_del = QPushButton("삭제")
        btn_del.clicked.connect(self.remove_channel)
        ch_row.addWidget(btn_del)
        ch_layout.addLayout(ch_row)
        self.channel_list = QTableWidget()
        self.channel_list.setColumnCount(4)
        self.channel_list.setHorizontalHeaderLabels(["플랫폼", "채널 ID/URL", "채널명", "삭제"])
        self.channel_list.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.channel_list.setEditTriggers(QAbstractItemView.NoEditTriggers)
        ch_layout.addWidget(self.channel_list)
        layout.addWidget(ch_group)

        # ---- 크롤링 제어 ----
        ctrl_layout = QHBoxLayout()
        self.start_btn = QPushButton("Start Crawling")
        self.stop_btn = QPushButton("Stop Crawling")
        self.stop_btn.setEnabled(False)
        self.start_btn.clicked.connect(self.start_crawling)
        self.stop_btn.clicked.connect(self.stop_crawling)
        ctrl_layout.addWidget(self.start_btn)
        ctrl_layout.addWidget(self.stop_btn)
        layout.addLayout(ctrl_layout)

        # 마지막 크롤링 시각 표시
        self.last_crawl_label = QLabel("마지막 크롤링: -")
        self.last_crawl_label.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(self.last_crawl_label)

        # ---- 결과 리스트 ----
        result_group = QGroupBox("결과 리스트")
        result_layout = QVBoxLayout(result_group)
        self.result_table = QTableWidget()
        self.result_table.setColumnCount(8)
        self.result_table.setHorizontalHeaderLabels(["제목", "채널", "조회수", "구독자", "업로드 날짜", "수집 시각", "URL", "삭제"])
        header = self.result_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)   # 제목
        header.setSectionResizeMode(1, QHeaderView.Stretch)   # 채널
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # 조회수
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # 구독자
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)  # 업로드 날짜
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)  # 수집 시각
        header.setSectionResizeMode(6, QHeaderView.Stretch)   # URL
        header.setSectionResizeMode(7, QHeaderView.ResizeToContents)  # 삭제
        self.result_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.result_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.result_table.cellDoubleClicked.connect(self.open_url)
        result_layout.addWidget(self.result_table)
        layout.addWidget(result_group)

        self.refresh_channels()
        self.refresh_results()

    def _conditions(self):
        return SearchConditions(
            max_subscribers=self.max_subs.value() or None,
            min_views=self.min_views.value() or None,
            upload_within_days=self.upload_days.value() or None,
            interval_minutes=int(self.interval_combo.currentText()),
        )

    def _set_condition_inputs_enabled(self, enabled: bool):
        """조건 설정 영역(구독자/조회수/기간/주기/검색어) 활성/비활성."""
        for w in [
            self.max_subs,
            self.min_views,
            self.upload_days,
            self.interval_combo,
            self.search_query,
        ]:
            w.setEnabled(enabled)

    def add_channel(self):
        text = self.channel_input.text().strip()
        if not text:
            return
        platform = "youtube" if self.platform_combo.currentText() == "YouTube" else "instagram"
        if platform == "youtube":
            self.channel_repo.add(platform, channel_url=text if "youtube" in text or "youtu" in text else None, channel_id=text if not text.startswith("http") else None)
        else:
            username = text.replace("https://www.instagram.com/", "").replace("https://instagram.com/", "").strip("/").split("?")[0].strip() or text
            self.channel_repo.add(platform, channel_id=username, channel_url=f"https://www.instagram.com/{username}/")
        self.channel_input.clear()
        self.refresh_channels()

    def remove_channel(self):
        text = self.channel_input.text().strip()
        if not text:
            return
        platform = "youtube" if self.platform_combo.currentText() == "YouTube" else "instagram"
        key = text.replace("https://www.instagram.com/", "").replace("https://instagram.com/", "").strip("/").split("?")[0] if "instagram" in text else text
        if self.channel_repo.delete(key, platform):
            self.channel_input.clear()
            self.refresh_channels()

    def refresh_channels(self):
        rows = self.channel_repo.list_all()
        self.channel_list.setRowCount(len(rows))
        for i, row in enumerate(rows):
            _id, platform, ch_id, ch_url, ch_name = row[0], row[1], row[2], row[3], row[4]
            self.channel_list.setItem(i, 0, QTableWidgetItem(platform))
            self.channel_list.setItem(i, 1, QTableWidgetItem(ch_url or ch_id or ""))
            self.channel_list.setItem(i, 2, QTableWidgetItem(ch_name or ""))
            btn = QPushButton("삭제")
            btn.clicked.connect(lambda checked=False, r=row: self._delete_channel_row(r))
            self.channel_list.setCellWidget(i, 3, btn)
        if not rows:
            self.channel_list.setRowCount(0)

    def _delete_channel_row(self, row):
        _id, platform, ch_id, ch_url, _ = row[0], row[1], row[2], row[3], row[4]
        key = ch_url or ch_id
        if key and self.channel_repo.delete(key, platform):
            self.refresh_channels()

    def start_crawling(self):
        cond = self._conditions()
        self.scheduler.set_interval(cond.interval_minutes)

        def scheduled_task():
            QTimer.singleShot(0, self._run_one_crawl)

        self.scheduler.start(scheduled_task)
        self._set_condition_inputs_enabled(False)
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self._run_one_crawl()

    def _run_one_crawl(self):
        self.statusBar().showMessage("크롤링 중... (YouTube/인스타 수집 중, 1~2분 걸릴 수 있습니다)")
        QApplication.processEvents()
        cond = self._conditions()
        self.worker = CrawlWorker(cond, self.search_query.text().strip(), run_channel_monitor=True)
        self.worker.finished.connect(self._on_crawl_finished)
        self.worker.error.connect(self._on_crawl_error)
        self.worker.start()

    def _on_crawl_finished(self, added: int):
        self.refresh_results()
        # 마지막 크롤링 시각 갱신
        now = datetime.now().astimezone()
        self.last_crawl_label.setText(f"마지막 크롤링(성공): {now.strftime('%Y-%m-%d %H:%M:%S')}")
        if not self.scheduler.is_running:
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
        if added > 0:
            self.statusBar().showMessage(f"저장 완료: {added}건 추가", 8000)
        else:
            self.statusBar().showMessage("크롤링 완료 (추가된 영상 없음). 결과 탭에서 확인하세요.", 5000)

    def _on_crawl_error(self, msg: str):
        self.statusBar().showMessage("크롤링 오류 발생", 3000)
        now = datetime.now().astimezone()
        self.last_crawl_label.setText(f"마지막 크롤링(실패): {now.strftime('%Y-%m-%d %H:%M:%S')}")
        if not self.scheduler.is_running:
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
        QMessageBox.warning(self, "크롤링 오류", msg)

    def stop_crawling(self):
        self.scheduler.stop()
        if self.worker and self.worker.isRunning():
            self.worker.terminate()
            self.worker.wait(3000)
        self._set_condition_inputs_enabled(True)
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.refresh_results()
        self.statusBar().showMessage("크롤링 중지됨", 3000)

    def _format_collected_at(self, created_at):
        """DB 저장 시각(UTC)을 로컬 시각 문자열으로 변환."""
        if not created_at:
            return ""
        s = str(created_at).strip()
        if not s:
            return ""
        try:
            # SQLite: "YYYY-MM-DD HH:MM:SS" (UTC)
            dt = datetime.strptime(s[:19], "%Y-%m-%d %H:%M:%S")
            dt_utc = dt.replace(tzinfo=timezone.utc)
            local = dt_utc.astimezone()
            return local.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return s

    def refresh_results(self):
        rows = self.repo.list_all()
        self.result_table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            title, channel, views, subs, upload, created_at, url = row[0], row[1], row[2], row[3], row[4], row[5], row[6]
            self.result_table.setItem(i, 0, QTableWidgetItem(str(title or "")))
            self.result_table.setItem(i, 1, QTableWidgetItem(str(channel or "")))
            self.result_table.setItem(i, 2, QTableWidgetItem(str(views) if views is not None else ""))
            self.result_table.setItem(i, 3, QTableWidgetItem(str(subs) if subs is not None else ""))
            self.result_table.setItem(i, 4, QTableWidgetItem(str(upload or "")))
            self.result_table.setItem(i, 5, QTableWidgetItem(self._format_collected_at(created_at)))
            self.result_table.setItem(i, 6, QTableWidgetItem(str(url or "")))
            btn = QPushButton("삭제")
            btn.clicked.connect(lambda checked=False, u=url: self._delete_result_row(u))
            self.result_table.setCellWidget(i, 7, btn)

    def _delete_result_row(self, video_url):
        if not video_url:
            return
        if self.repo.delete_by_url(str(video_url)):
            self.refresh_results()
            self.statusBar().showMessage("결과에서 삭제됨", 2000)

    def open_url(self, row: int, col: int):
        url_item = self.result_table.item(row, 6)
        if url_item and url_item.text():
            QDesktopServices.openUrl(QUrl(url_item.text()))

    def closeEvent(self, event):
        self.scheduler.shutdown()
        if self.worker and self.worker.isRunning():
            self.worker.terminate()
        event.accept()


def run_app():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    run_app()
