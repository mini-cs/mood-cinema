# 🎬 Mood Cinema

지금 기분이나 상황을 한 문장으로 적으면, Gemini가 영화·드라마를 추천하고 TMDB 실제 데이터(포스터·평점·줄거리·예고편)로 보강해 보여주는 Streamlit 웹 앱입니다.

## 주요 기능

- **AI 감정·상황 맞춤 추천** — "야근 끝나고 볼 가벼운 코미디" 같은 문장으로 3~5개 추천. 1순위는 큰 히어로 카드와 "AI 큐레이터의 한마디"로 보여줍니다.
- **트렌딩 탐색** — 오늘의 인기 / 이번 주 인기 / 장르 픽 세 줄. 전체·영화·TV 전환, 6~10위 펼쳐 보기.
- **상세 팝업** — 장르·연도·러닝타임(시즌 수)·평점, 줄거리, YouTube 예고편.

## 아키텍처

```
[ 화면 계층 ]      app.py  ─ 입력 받기, 카드·팝업 그리기, 캐싱(st.cache_data)
      │
[ 조합 계층 ]      core/recommender.py ─ "AI 추천 + 실제 데이터" 합치기
      │                     │
[ 외부 API 계층 ]  core/gemini_client.py      core/tmdb_client.py
                          └──── core/rate_limit.py (재시도·호출 제한) ────┘
```

`core/`는 streamlit을 import하지 않습니다. 외부 의존성(HTTP 세션, SDK 클라이언트, sleep, 시계)을 주입받기 때문에 API 키 없이 테스트할 수 있습니다.

## 실행 방법

Windows PowerShell 기준입니다.

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
copy .env.example .env      # .env를 열어 TMDB_API_KEY, GEMINI_API_KEY 입력
streamlit run app.py
```

- TMDB 키: themoviedb.org → 설정 → API
- Gemini 키: Google AI Studio
- 키가 없으면 앱이 설정 방법을 안내합니다. TMDB 키만 있으면 트렌딩만 보입니다.

## 테스트

```powershell
pytest -v
```

실제 API는 호출하지 않고 가짜 응답으로 검증합니다. `tests/test_app_smoke.py`는 Streamlit `AppTest`로 화면 전체를 한 번 돌려 봅니다.

## 배포

Streamlit Community Cloud 기준입니다.

1. GitHub 저장소를 만들고 push합니다. 커밋 전에 `.gitignore`에 `.env`, `.streamlit/secrets.toml`이 있는지 확인합니다.
2. share.streamlit.io에서 GitHub 계정을 연동하고, 저장소·브랜치·`app.py`를 선택합니다.
3. Advanced settings → Secrets에 TOML 형식으로 입력합니다.
   ```toml
   TMDB_API_KEY = "..."
   GEMINI_API_KEY = "..."
   GEMINI_RPM_LIMIT = 5
   ```
4. 배포 후 트렌딩 표시, 추천 1회 성공, 쿨다운 메시지, Credits 영역을 확인합니다.

## 설계 결정

- **구조화 출력 + 재검증:** Gemini에 JSON 스키마를 강제하지만, 응답을 Pydantic으로 한 번 더 검증합니다. 6개 이상 오면 앞 5개만 쓰고, 형식이 깨지면 "다시 시도" 버튼을 보여줍니다.
- **TMDB 재검색:** AI가 말한 제목을 그대로 믿지 않습니다. 원제+연도로 먼저 찾고, 없으면 한국어 제목으로 다시 찾습니다. 그래도 없으면 "정보 없음"으로 표시하고 이유만 보여줍니다.
- **캐싱:** 트렌딩 1시간, 장르·검색·상세 하루, 같은 문장의 추천 1시간. 캐시가 적중하면 Gemini 호출 횟수에도 들어가지 않습니다.
- **호출 제한·백오프:** 세션당 10초 쿨다운, 앱 전체 분당 5회·하루 200회(태평양 시간 자정 리셋)로 제한합니다. 429/5xx와 연결 오류는 full jitter 지수 백오프로 최대 3회 재시도합니다. `Retry-After`가 20초를 넘으면 바로 실패합니다.

## 한계와 다음 단계

- 호출 횟수 카운터는 메모리에 있어서 앱이 재시작되면 초기화됩니다. Streamlit Cloud는 사용이 없으면 앱을 재웁니다.
- 기본 상한은 앱이 스스로 정한 보수적인 값이고, 실제 Gemini 한도가 아닙니다. 배포 전에 AI Studio에서 내 한도를 확인하세요.
- 장르 픽은 이번 주 인기 20개 안에서 거르므로 10개보다 적을 수 있습니다.
- 추후 확장: 찜 목록, 추천 결과 공유 링크(`st.query_params`), 시청 가능한 OTT 표시(TMDB watch providers), Interactions API로 이전.

## Credits

This product uses the TMDB API but is not endorsed or certified by TMDB.

TMDB 로고는 TMDB의 logos-attribution 페이지에서 SVG를 내려받아 `assets/tmdb_logo.svg`로 저장하면 앱 하단에 표시됩니다. 파일이 없으면 고지문만 표시됩니다.

추천 기능은 Google Gemini API 무료 티어를 사용하며, 입력 내용이 Google 제품 개선에 활용될 수 있습니다.
