# Viral Video Finder

YouTube·Instagram 바이럴 영상 자동 탐색 Windows 데스크탑 프로그램.

## 요구 사항

- Python 3.10+
- Windows (권장)
- PyQt6 실행 시 **Visual C++ 재배포 패키지** 필요 시 [Microsoft VC++ 최신 배포 패키지](https://learn.microsoft.com/ko-kr/cpp/windows/latest-supported-vc-redist) 설치

## 설치 및 실행

### 1. 가상환경 (권장)

```bash
cd viralVideoFinder
python -m venv venv
venv\Scripts\activate
```

### 2. 의존성 설치

```bash
pip install -r requirements.txt
```

### 3. 설정 (선택)

- `config/settings.example.yaml`을 `config/settings.yaml`로 복사 후 편집
- YouTube API 키를 넣으면 검색·채널 모니터링이 더 빠르고 정확하게 동작합니다. (키 없어도 yt-dlp로 검색 가능)

#### YouTube API 키 발급 방법

1. **Google Cloud Console** 접속  
   - https://console.cloud.google.com/  
   - Google 계정으로 로그인

2. **프로젝트 만들기** (이미 있으면 생략)  
   - 상단 프로젝트 선택 → **새 프로젝트** → 이름 입력 후 만들기

3. **YouTube Data API v3 사용 설정**  
   - 왼쪽 메뉴 **API 및 서비스** → **라이브러리**  
   - "YouTube Data API v3" 검색 → **사용** 클릭

4. **API 키 만들기**  
   - **API 및 서비스** → **사용자 인증 정보**  
   - **+ 사용자 인증 정보 만들기** → **API 키** 선택  
   - 생성된 키가 나오면 **복사**

5. **프로그램에 넣기**  
   - **방법 A**: `config/settings.yaml`에서 `youtube.api_key: "여기에_키_붙여넣기"`  
   - **방법 B**: 터미널에서  
     ```bash
     set YOUTUBE_API_KEY=여기에_키_붙여넣기
     ```  
     (PowerShell: `$env:YOUTUBE_API_KEY="여기에_키_붙여넣기"`)

**참고**: 무료 할당량(quota)이 있어서 하루에 많은 검색/채널 조회 시 제한될 수 있습니다. 개인 사용은 보통 충분합니다.

### 4. 실행

```bash
python main.py
```

## Windows .exe 빌드

1. PyInstaller 설치: `pip install pyinstaller`
2. 빌드:

```bash
pyinstaller --onefile --windowed --name "ViralVideoFinder" main.py
```

실행 파일은 `dist/ViralVideoFinder.exe`에 생성됩니다.

- `--onefile`: 단일 exe
- `--windowed`: 콘솔 창 숨김

## 기능 요약

- **조건 설정**: 구독자 수 이하, 조회수 이상, 업로드 N일 이내, 탐색 주기(5/10/30분)
- **채널 / 계정 모니터링**: YouTube 채널 또는 **Instagram 공개 계정** 추가·삭제, 주기적 최신 영상 수집
  - Instagram: **공개 프로필만** 지원 (로그인 불필요). 플랫폼에서 "Instagram" 선택 후 사용자명(예: `username` 또는 `instagram.com/username`) 입력
- **크롤링 제어**: Start / Stop
- **결과 리스트**: 제목, 채널, 조회수(인스타는 재생수·좋아요), 구독자/팔로워, 업로드 날짜, URL (더블클릭 시 브라우저 열기)
- 데이터 저장: 프로젝트 내 `data/viral_finder.db` (SQLite)

## 범위 제외

- 자동 댓글, 자동 업로드, 계정 로그인, SNS 자동 포스팅은 포함하지 않습니다.
