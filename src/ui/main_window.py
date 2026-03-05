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
    # 전체 / YouTube / Instagram 별로 새로 저장된 개수
    finished = pyqtSignal(int, int, int)
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
            ig_error = None

            # 1) YouTube 검색 (검색어 있으면 키워드 검색, 비면 인기/트렌딩)
            rows = yt.search_viral(self.search_query.strip() if self.search_query else "", max_results=25)
            all_rows.extend(rows)

            # 2) 채널 모니터링
            if self.run_channel_monitor:
                for row in ChannelRepository.list_all("youtube"):
                    _id, platform, ch_id, ch_url, ch_name = row[0], row[1], row[2], row[3], row[4]
                    cid = None
                    if ch_id:
                        # 1) 사용자가 진짜 채널 ID(UC로 시작)를 넣은 경우 그대로 사용
                        if str(ch_id).startswith("UC"):
                            cid = ch_id
                        else:
                            # 2) @handle 또는 커스텀 이름만 넣은 경우 → URL 형태로 변환 후 ID 조회 시도
                            handle = str(ch_id).strip()
                            # 이미 @가 붙어 있으면 그대로, 아니라면 @를 붙여서 URL 구성
                            if not handle.startswith("@"):
                                handle = "@" + handle
                            handle_url = f"https://www.youtube.com/{handle}"
                            cid = yt.channel_id_from_url(handle_url) or ch_id
                    elif ch_url:
                        # URL이 있을 때는 URL에서 채널 ID를 추출
                        cid = yt.channel_id_from_url(ch_url)
                    if cid:
                        rows = yt.channel_latest_videos(cid, max_results=10)
                        all_rows.extend(rows)
                for row in ChannelRepository.list_all("instagram"):
                    _id, platform, ch_id, ch_url, ch_name = row[0], row[1], row[2], row[3], row[4]
                    username = ch_id or (ch_url.replace("https://www.instagram.com/", "").replace("https://instagram.com/", "").strip("/").split("?")[0] if ch_url else None) or ch_name
                    if username:
                        try:
                            rows = ig.user_recent_videos(username, max_results=10)
                            all_rows.extend(rows)
                        except Exception as e:
                            # 인스타그램 쪽 에러는 전체 크롤링을 중단하지 않고,
                            # 나중에 상태바에만 안내 메시지를 띄울 수 있도록 저장해 둔다.
                            ig_error = str(e)

            # 3) 조건 필터
            filtered = filter_by_conditions(all_rows, self.conditions)

            # 4) 플랫폼별로 중복 제거 + 저장 (YouTube / Instagram 개수 분리)
            yt_rows = [r for r in filtered if len(r) > 6 and str(r[6]).lower() == "youtube"]
            ig_rows = [r for r in filtered if len(r) > 6 and str(r[6]).lower() == "instagram"]

            yt_added = dedupe_and_save(yt_rows, repo) if yt_rows else 0
            ig_added = dedupe_and_save(ig_rows, repo) if ig_rows else 0
            total_added = yt_added + ig_added

            # 메인 스레드에 결과 전달
            self.finished.emit(total_added, yt_added, ig_added)
            if ig_error:
                self.error.emit(ig_error)
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
        ch_header = self.channel_list.horizontalHeader()
        ch_header.setSectionResizeMode(0, QHeaderView.ResizeToContents)   # 플랫폼
        ch_header.setSectionResizeMode(1, QHeaderView.Stretch)            # 채널 ID/URL (가장 넓게)
        ch_header.setSectionResizeMode(2, QHeaderView.Stretch)            # 채널명
        ch_header.setSectionResizeMode(3, QHeaderView.ResizeToContents)   # 삭제 버튼
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

        # UI에 크롤링/조회 중임을 표시
        QApplication.setOverrideCursor(Qt.WaitCursor)
        self.statusBar().showMessage("채널 정보 조회 및 추가 중...", 0)
        success = False
        try:
            if platform == "youtube":
                # YouTube 채널명 자동 채우기 시도
                yt = YouTubeCrawler()
                ch_id = None
                ch_url = None
                ch_name = ""
                raw = text.strip()
                if raw.startswith("http"):
                    ch_url = raw
                    ch_id = yt.channel_id_from_url(raw) or None
                else:
                    # UC로 시작하면 채널 ID, 아니면 @handle 또는 핸들 후보로 처리
                    if raw.startswith("UC"):
                        ch_id = raw
                    else:
                        handle = raw
                        if not handle.startswith("@"):
                            handle = "@" + handle
                        ch_url = f"https://www.youtube.com/{handle}"
                        ch_id = yt.channel_id_from_url(ch_url) or None
                # 채널 ID가 있으면 최신 영상 1개를 조회해서 채널명 추출 (API 키 필요)
                try:
                    if ch_id:
                        rows = yt.channel_latest_videos(ch_id, max_results=1)
                        if rows:
                            # (title, channel_name, view_count, subscriber_count, upload_date, video_url, platform)
                            ch_name = rows[0][1] or ""
                except Exception:
                    # 채널명 조회 실패해도 추가 자체는 진행
                    pass
                self.channel_repo.add(
                    platform,
                    channel_id=ch_id or raw,
                    channel_url=ch_url or (raw if raw.startswith("http") else ""),
                    channel_name=ch_name,
                )
            else:
                # Instagram: username을 정규화해서 채널명으로 사용
                username = (
                    text.replace("https://www.instagram.com/", "")
                    .replace("https://instagram.com/", "")
                    .strip("/")
                    .split("?")[0]
                    .strip()
                    or text
                )
                self.channel_repo.add(
                    platform,
                    channel_id=username,
                    channel_url=f"https://www.instagram.com/{username}/",
                    channel_name=username,
                )
            success = True
        finally:
            QApplication.restoreOverrideCursor()
            self.statusBar().clearMessage()

        if success:
            self.statusBar().showMessage("채널이 추가되었습니다.", 3000)
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

    def _on_crawl_finished(self, added: int, yt_added: int, ig_added: int):
        self.refresh_results()
        # 마지막 크롤링 시각 갱신
        now = datetime.now().astimezone()
        self.last_crawl_label.setText(
            f"마지막 크롤링(성공): {now.strftime('%Y-%m-%d %H:%M:%S')}  |  YouTube: {yt_added}개, Instagram: {ig_added}개 (신규 저장)"
        )
        if not self.scheduler.is_running:
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
        if added > 0:
            self.statusBar().showMessage(f"저장 완료: {added}건 추가", 8000)
        else:
            self.statusBar().showMessage("크롤링 완료 (추가된 영상 없음). 결과 탭에서 확인하세요.", 5000)

    def _on_crawl_error(self, msg: str):
        # Instagram 레이트리밋(잠시 후 다시 시도) 메시지 감지
        if "Please wait a few minutes before you try again" in msg:
            friendly = "Instagram에서 요청을 잠시 제한했습니다. 잠시 후 다시 시도해 주세요."
            self.statusBar().showMessage(friendly, 10000)
        else:
            self.statusBar().showMessage("크롤링 오류 발생", 3000)
        if not self.scheduler.is_running:
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
        # 팝업 대신 상태바 메시지로만 알림

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
