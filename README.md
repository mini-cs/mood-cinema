# 🎬 Mood Cinema

지금 기분이나 상황을 한 문장으로 적으면, Gemini가 영화·드라마를 추천하고 TMDB 실제 데이터(포스터·평점·줄거리·예고편)로 보강해 보여주는 Reflex 웹 앱입니다.

<!-- 스크린샷: docs/images/ 에 넣고 아래 주석을 풀어 주세요 -->
<!-- ![홈 화면](docs/images/home.png) -->
<!-- ![상세 팝업](docs/images/detail.png) -->

## 주요 기능

- **AI 감정·상황 맞춤 추천** — "야근 끝나고 볼 가벼운 코미디" 같은 문장으로 3~5개 추천. 1순위는 배경 이미지 위에 글자를 겹친 히어로 배너와 "AI 큐레이터의 한마디"로 보여줍니다.
- **트렌딩 탐색** — 오늘의 인기 / 이번 주 인기 / 장르 픽 세 줄을 TOP 10 가로 스크롤로. 전체·영화·TV 전환, 순위 배지, 카드 호버 효과.
- **상세 팝업** — 카드나 "상세 보기"를 누르면 배경 위에 포스터가 겹친 상세 화면. 장르·연도·러닝타임(시즌 수)·평점, 줄거리, YouTube 예고편.

## 아키텍처

```
[ 화면 계층 ]      mood_cinema/  ─ Reflex 페이지·컴포넌트·State (얇게 유지)
      │
[ 서비스 계층 ]    core/service.py   ─ 캐싱(TTL), Gemini 호출 횟수 제한, 추천 흐름
                   core/presenter.py ─ 도메인 데이터 → 화면용 데이터(문자열·URL) 변환
      │
[ 조합 계층 ]      core/recommender.py ─ "AI 추천 + 실제 데이터" 합치기
      │                     │
[ 외부 API 계층 ]  core/gemini_client.py      core/tmdb_client.py
                          └──── core/rate_limit.py (재시도·호출 제한) ────┘
```

`core/`는 화면 프레임워크(Reflex)를 import하지 않습니다. 외부 의존성(HTTP 세션, SDK 클라이언트, sleep, 시계)을 주입받기 때문에 API 키 없이 테스트할 수 있습니다.

## 실행 방법

Windows PowerShell 기준입니다. Python 3.11 이상이 필요합니다.

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
copy .env.example .env      # .env를 열어 TMDB_API_KEY, GEMINI_API_KEY 입력
reflex run                  # http://localhost:3000
```

- TMDB 키: themoviedb.org → 설정 → API
- Gemini 키: Google AI Studio
- 키가 없으면 앱 위쪽에 설정 방법이 표시됩니다. TMDB 키만 있으면 트렌딩만 보입니다.
- 처음 실행할 때는 화면(JavaScript) 패키지를 내려받느라 1~2분 걸릴 수 있습니다.

## 테스트

```powershell
pytest -v                                  # core 단위 테스트 (실제 API 호출 없음)
reflex export --frontend-only --no-zip     # 화면 코드 빌드 확인
```

화면은 자동 테스트 대신 빌드 확인과 `reflex run`으로 직접 확인합니다.

## 배포

Reflex Cloud 기준입니다.

1. `reflex login`으로 로그인합니다.
2. 프로젝트 루트에서 배포합니다.
   ```powershell
   reflex deploy --app-name mood-cinema --envfile .env
   ```
   `--envfile`로 넘긴 값은 앱의 Secrets(환경 변수)로 등록됩니다. 나중에 바꿀 때는 대시보드 Settings > Secrets에서 고칩니다.
3. 무료 플랜은 앱 1개, 공유 컴퓨팅이며 상시 실행·커스텀 도메인이 없습니다.
4. 배포 후 트렌딩 세 줄, 추천 1회 성공, 쿨다운 메시지, Credits 영역을 확인합니다.

## 설계 결정

- **Streamlit → Reflex 전환:** 처음에는 Streamlit으로 만들었지만, 참고한 서비스 화면(겹친 히어로, 가로 스크롤 줄, 호버 효과)을 Streamlit 기본 부품으로는 표현하기 어려웠습니다. 파이썬만으로 React 화면을 만들 수 있는 Reflex로 화면 계층만 갈아 끼웠고, `core/`는 그대로 썼습니다.
- **서비스·프레젠터 계층 분리:** 캐싱·호출 제한·추천 흐름은 `core/service.py`, 화면 문구·이미지 주소 만들기는 `core/presenter.py`로 빼서 프레임워크 없이 테스트합니다. Reflex State는 "입력 받기 → core 호출 → 결과 저장"만 합니다.
- **키는 서버에만:** Reflex State 변수는 브라우저로 전송되므로, API 키와 클라이언트는 State가 아니라 서버 쪽 `get_service()`에만 둡니다.
- **구조화 출력 + 재검증:** Gemini에 JSON 스키마를 강제하고, 응답을 Pydantic으로 한 번 더 검증합니다. 6개 이상 오면 앞 5개만 쓰고, 형식이 깨지면 "다시 시도" 버튼을 보여줍니다.
- **TMDB 재검색 + 제목 확인:** AI가 말한 제목을 원제+연도로 찾고, 없으면 한국어 제목으로 다시 찾습니다. 검색 1등이 아니라 제목이 실제로 같은 작품만 채택합니다 (예: "Seven" 검색 1등인 "황야의 7인"을 거름).
- **캐싱:** 트렌딩 1시간, 장르·검색·상세 하루, 같은 문장의 추천 1시간. 캐시가 적중하면 Gemini 호출 횟수에도 들어가지 않습니다.
- **호출 제한·백오프:** 세션당 10초 쿨다운, 앱 전체 분당 5회·하루 200회(태평양 시간 자정 리셋). 429/5xx와 연결 오류는 full jitter 지수 백오프로 최대 3회 재시도하고, `Retry-After`가 20초를 넘으면 바로 실패합니다.
- **느린 호출은 백그라운드로:** Gemini·TMDB 호출은 Reflex 백그라운드 이벤트에서 돌려 화면이 멈추지 않게 하고, 로딩 중 버튼 연타·빠른 종류 전환·늦게 도착한 이전 응답을 걸러냅니다.

## 한계와 다음 단계

- 호출 횟수 카운터와 캐시는 백엔드 메모리에 있어서 앱이 재시작되면 초기화됩니다. Reflex Cloud 무료 플랜은 상시 실행이 아니라 재시작될 수 있고, 백엔드 프로세스가 여러 개면 카운터도 따로 생깁니다.
- 기본 상한은 앱이 스스로 정한 보수적인 값이고, 실제 Gemini 한도가 아닙니다. 배포 전에 AI Studio에서 내 한도를 확인하세요.
- 장르 픽은 이번 주 인기 20개 안에서 거르므로 10개보다 적을 수 있습니다.
- 추후 확장: 찜 목록(브라우저 저장소), 추천 결과 공유 링크(URL 쿼리), 시청 가능한 OTT 표시(TMDB watch providers), Gemini Interactions API로 이전.

## Credits

This product uses the TMDB API but is not endorsed or certified by TMDB.

TMDB 로고는 TMDB의 logos-attribution 페이지에서 SVG를 내려받아 `assets/tmdb_logo.svg`로 저장하면 앱 하단에 표시됩니다. 파일이 없으면 고지문만 표시됩니다.

추천 기능은 Google Gemini API 무료 티어를 사용하며, 입력 내용이 Google 제품 개선에 활용될 수 있습니다.
