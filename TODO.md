# Viral Video Finder — 개발 TODO 리스트

PRD 기반 작업 목록입니다. 순서대로 진행하면 됩니다.

---

## 1. 프로젝트 초기 설정
- [x] Python 가상환경 및 프로젝트 폴더 구조 생성
- [x] `requirements.txt` (PyQt6, APScheduler, requests, BeautifulSoup, Selenium/Playwright 등)
- [x] 설정 파일 구조 (API 키, 기본 옵션)

---

## 2. 데이터 레이어
- [x] SQLite DB 스키마 설계
- [x] `video_data` 테이블: platform, video_title, video_url, channel_name, subscriber_count, view_count, upload_date
- [x] 채널 모니터링용 테이블 (채널 ID/URL, 플랫폼 등)
- [x] DB 초기화 및 CRUD 유틸 모듈

---

## 3. 비즈니스 로직
- [x] **조건 설정 모델**: 팔로워/구독자 수, 조회수, 업로드 기간(일), 탐색 주기(5/10/30분)
- [x] **데이터 필터링**: 조건 충족 여부 판단, 중복 영상 필터링(video_url 기준)
- [x] **결과 저장**: 조건 충족 시 DB 저장 및 UI 갱신 이벤트

---

## 4. 크롤링 모듈
- [x] **YouTube**: YouTube Data API 또는 HTML/Selenium 크롤링
- [x] **Instagram**: Graph API 또는 Selenium 기반 크롤링 (정책 고려)
- [x] 크롤링 결과 → 공통 데이터 구조로 변환
- [x] **재시도 로직**: 실패 시 자동 재시도
- [x] **Rate limit 대응**: 요청 간격, quota 관리

---

## 5. 스케줄러
- [x] APScheduler 연동
- [x] 탐색 주기 선택: 5분 / 10분 / 30분
- [x] 실시간 탐색 vs 주기적 탐색 모드 지원
- [x] Start/Stop 시 스케줄러 시작·중지

---

## 6. UI (PyQt 기반 Windows 데스크탑)
- [x] **조건 설정 패널**: 팔로워/구독자, 조회수, 업로드 기간, 탐색 주기 입력
- [x] **채널 관리 패널**: 채널 추가, 삭제, 목록 표시
- [x] **크롤링 제어 패널**: Start Crawling, Stop Crawling 버튼
- [x] **결과 리스트**: 표 형태 — 제목 | 채널 | 조회수 | 구독자 | 업로드 날짜 | URL
- [x] 크롤링 결과 자동 업데이트(시그널/슬롯 또는 스레드 안전 갱신)

---

## 7. 통합 및 마무리
- [x] 메인 윈도우에서 모든 패널 연결
- [x] 크롤링 스레드와 UI 스레드 분리 (멈춤 방지)
- [x] Windows .exe 빌드 (PyInstaller 등) — README에 방법 문서화
- [x] 실행 방법 및 설정 문서 작성 (README 등)

---

## 범위 제외 (PRD 기준)
- 자동 댓글, 자동 업로드, 계정 로그인, SNS 자동 포스팅 → **구현하지 않음**

---

## 리스크 대응
- **Instagram**: API 제한 시 Selenium/Playwright 등 크롤링 방식으로 대체 가능하도록 모듈 분리
- **YouTube API**: Quota 부족 시 HTML 크롤링 fallback 검토
