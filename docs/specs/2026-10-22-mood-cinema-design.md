# Mood Cinema 설계 문서 (v0.1)

> 기분·상황을 문장으로 입력하면 AI가 영화/TV 작품을 골라 주고, TMDB의 실제 데이터(포스터·평점·줄거리)로 보강해 보여주는 Streamlit 웹 앱
>
> - 작성일: 2026-10-22
> - 용도: 개인 포트폴리오
> - 상태: v0.2 승인 (v0.1 → v0.2: 참고 화면 반영 — 추천 이유 박스, 테마별 트렌딩 줄, 1순위 히어로 카드, 다크 테마)

---

## 1. 목표와 범위

### 1.1 목표

- 사용자가 "비 오는 날 혼자 보기 좋은 몰입감 있는 스릴러"처럼 자유롭게 입력하면, 실제로 존재하는 작품 3~5개를 추천 이유와 함께 카드로 보여준다.
- 이번 주/오늘 인기 있는 영화·TV TOP 10을 장르별로 탐색할 수 있다.
- 무료 API 한도 안에서 안정적으로 동작하도록 캐싱·호출 제한·재시도를 갖춘다.

### 1.2 완성 기준 (Definition of Done)

1. Streamlit Community Cloud에 배포된 공개 URL에서 위 두 기능이 동작한다.
2. Gemini 호출이 실패하거나 한도를 넘어도 앱이 멈추지 않고, 트렌딩 화면은 계속 보인다.
3. `pytest`가 실제 API 키 없이 통과한다.
4. README에 아키텍처, 실행 방법, 설계 결정 이유가 정리되어 있다.

### 1.3 이번 범위에서 하지 않는 것 (Non-goals)

- 로그인, DB, 사용자별 기록 저장
- 상업적 이용 (TMDB 무료 조건은 비상업 용도에 한정)
- 다국어 UI (한국어만)

---

## 2. 기술 스택

모든 버전은 2026-10-22 기준 PyPI 최신 안정 버전이며, `requirements.txt`에 고정한다.

- Python 3.11 이상
- `streamlit==1.66.1` — 화면(UI), 캐싱, Secrets
- `google-genai==2.32.0` — Gemini API 공식 Python SDK
- `requests==2.34.2` — TMDB REST API 호출
- `pydantic==2.14.1` — Gemini 응답 형식 정의·검증
- `python-dotenv==1.2.4` — 로컬 개발용 `.env` 읽기
- `pytest==9.1.1` — 테스트 (개발용, `requirements-dev.txt`)

**외부 API**

- Gemini 모델: `gemini-3.5-flash-lite` (무료 티어 있음, 공식 문서가 신규 프로젝트에 권장)
- TMDB API v3 (`https://api.themoviedb.org/3`), 인증은 `api_key` 쿼리 파라미터

---

## 3. 아키텍처

### 3.1 3계층 구조

```
[ 화면 계층 ]      app.py  ─ 입력 받기, 카드·팝업 그리기, 캐싱(st.cache_data)
      │
[ 조합 계층 ]      core/recommender.py ─ "AI 추천 + 실제 데이터" 합치기
      │                     │
[ 외부 API 계층 ]  core/gemini_client.py      core/tmdb_client.py
                          └──── core/rate_limit.py (재시도·호출 제한) ────┘
```

### 3.2 폴더 구조

```
mood-cinema/
├─ app.py                  # Streamlit 화면 (유일하게 streamlit을 쓰는 실행 파일)
├─ core/
│  ├─ __init__.py
│  ├─ config.py            # 설정값 로드 (Secrets → 환경 변수 → 기본값)
│  ├─ models.py            # 데이터 모델 (Pydantic, dataclass)
│  ├─ tmdb_client.py       # TMDB 호출
│  ├─ gemini_client.py     # Gemini 호출 + JSON 스키마 강제
│  ├─ recommender.py       # Gemini 결과 → TMDB 매칭 → 결과 조립
│  └─ rate_limit.py        # 지수 백오프 재시도, 호출 횟수 제한기
├─ tests/
│  ├─ test_config.py
│  ├─ test_tmdb_client.py
│  ├─ test_gemini_client.py
│  ├─ test_recommender.py
│  └─ test_rate_limit.py
├─ assets/                 # TMDB 공식 로고 SVG (직접 내려받아 넣기)
├─ docs/specs/             # 이 문서
├─ .streamlit/
│  ├─ config.toml          # 다크 테마 설정 (커밋함)
│  └─ secrets.toml.example
├─ .env.example
├─ .gitignore
├─ requirements.txt
├─ requirements-dev.txt
└─ README.md
```

### 3.3 설계 원칙

- **`core/`는 streamlit을 import하지 않는다.** 그래서 Streamlit 없이도 테스트할 수 있고, 나중에 FastAPI 같은 다른 화면으로 옮기기 쉽다.
- **외부 의존성은 주입받는다.** `TmdbClient`는 HTTP 세션을, `GeminiClient`는 SDK 클라이언트를, 재시도 함수는 `sleep`·난수 함수를 생성자나 인자로 받는다. 테스트에서는 가짜 객체를 넣는다.
- **캐싱은 화면 계층(app.py)에서만 한다.** `st.cache_data`로 감싼 함수가 core 함수를 호출한다.

---

## 4. 기능 명세

### F1. 트렌딩 탐색 (테마별 줄)

참고 화면: The Criterion Channel의 테마별 가로 줄 구성

- **입력:**
  - 종류(전체/영화/TV): 모든 줄에 공통 적용
  - 장르(1개): "장르 픽" 줄에만 적용
- **테마 줄 3개:**
  1. **오늘의 인기** — `GET /trending/{all|movie|tv}/day?language=ko-KR`
  2. **이번 주 인기** — `GET /trending/{all|movie|tv}/week?language=ko-KR`
  3. **장르 픽** — 이번 주 인기(2번과 같은 응답, 추가 호출 없음) 중 선택한 장르만
- **처리:**
  1. 트렌딩은 1페이지(20개)만 쓴다.
  2. `GET /genre/movie/list`, `GET /genre/tv/list`로 장르 ID → 이름 표를 만든다.
  3. 장르 픽은 장르 이름 기준으로 거른다. 영화와 TV는 장르 ID 체계가 달라서 ID로 거르면 안 된다.
- **출력:**
  - 줄마다 1~5위를 카드 5개로 보여준다.
  - 카드: 포스터, 제목, "연도 · ★평점", "상세 보기" 버튼
  - 줄마다 "6~10위 더 보기" 펼침(`st.expander`)으로 TOP 10까지 볼 수 있다.
- **한계:** 장르 픽은 20개 중에서 거르므로 10개보다 적을 수 있다. 이 경우 있는 만큼만 보여주고, 0개면 "이번 주 인기작 중 이 장르가 없어요"를 표시한다.

### F2. AI 감정·상황 맞춤 추천

- **입력:** 자유 문장 (1~300자)
  - 예: "야근 끝나고 머리 비우고 싶을 때 볼 가벼운 코미디"
- **처리:**
  1. 입력을 정리한다 (앞뒤 공백 제거, 연속 공백 1칸으로).
  2. 호출 제한을 확인한다 (6장 참고).
  3. Gemini에 JSON 스키마를 강제해 작품 3~5개를 받는다 (5장 참고).
  4. 작품마다 TMDB를 검색해 실제 작품과 연결한다 (4.1 참고).
  5. 추천 이유는 Gemini, 나머지 정보(포스터·평점·줄거리)는 TMDB 값을 쓴다.
- **출력:**
  - **1순위 히어로 카드** (참고 화면: BritBox의 대표작 히어로)
    - Gemini가 첫 번째로 준 작품을 크게 보여준다.
    - 왼쪽: 가로형 배경 이미지(`backdrop_path`, w780). 없으면 포스터(w500)
    - 오른쪽: 제목, "장르 · 연도 · ★평점", AI 추천 이유 박스, "상세 보기" 버튼
  - **나머지 추천 카드** (2~5순위)
    - 포스터, 제목, "연도 · ★평점", AI 추천 이유(2줄), "상세 보기" 버튼
  - TMDB에서 못 찾은 작품은 이미지 자리에 "정보 없음"을 표시하고, 제목과 추천 이유만 보여준다.
  - 1순위가 TMDB 미확인이면, 확인된 작품 중 가장 앞의 것을 히어로로 올린다. 모두 미확인이면 히어로 없이 카드만 보여준다.

#### 4.0 AI 추천 이유 박스 (참고 화면: MUBI의 "OUR TAKE")

- 제목: "🎬 AI 큐레이터의 한마디"
- 테두리 있는 박스(`st.container(border=True)`)로, 줄거리보다 위에 둔다.
- 쓰이는 곳: 히어로 카드, 상세 팝업 (추천에서 연 경우에만)

#### 4.1 TMDB 매칭 규칙

AI가 말한 제목을 그대로 믿지 않고, 실제 데이터에서 확인한다.

1. `media_type`에 따라 `/search/movie` 또는 `/search/tv`를 호출한다.
   - 1차: `query=원제`, 연도 지정 (영화: `year`, TV: `first_air_date_year`)
   - 2차 (결과 0개일 때): `query=한국어 제목`, 연도 없이
2. 결과 중 **제목이 실제로 같은 작품**만 채택한다 (2026-10-22 실제 테스트 후 변경).
   - 결과의 제목·원제 중 하나가 AI의 원제·한국어 제목 중 하나와 같아야 한다. 대소문자·공백·문장부호는 무시한다.
   - 제목이 같은 작품이 여럿이면 연도가 같은 것을 먼저 고른다 (리메이크 구분).
   - 이유: 검색 1등을 그대로 쓰면 엉뚱한 작품이 붙는다. 예: 원제 "Seven"(1995) → "황야의 7인"(1960), "Parasite"(2019) → 다른 단편.
3. 두 번 모두 제목이 같은 작품이 없으면 "TMDB 미확인"으로 표시한다. 틀린 포스터보다 "정보 없음"이 낫다.
4. 같은 TMDB ID가 중복되면 하나만 남긴다.

### F3. 상세 정보 팝업

- **트리거:** 카드의 "상세 보기" 버튼 → `st.dialog` 팝업
- **처리:** `GET /movie/{id}` 또는 `/tv/{id}`
  - 파라미터: `language=ko-KR&append_to_response=videos&include_video_language=ko,en`
- **출력 순서** (참고 화면: Peacock 상세 화면)
  1. 큰 포스터(w500), 제목/원제
  2. "장르 · 연도 · 러닝타임(영화) 또는 시즌 수(TV) · ★평점"
  3. AI 추천 이유 박스 (추천에서 연 경우에만, 4.0 참고)
  4. 줄거리
  5. 예고편
  - 예고편: `site == "YouTube"`이고 `type == "Trailer"`인 첫 영상을 `st.video`로 보여준다. 없으면 아무 YouTube 영상, 그것도 없으면 숨긴다.
  - 줄거리가 비어 있으면 "한국어 줄거리가 등록되지 않았어요"를 표시한다.

### F4. 출처 표기 (필수)

- 페이지 하단 "Credits" 영역에 아래 고지문과 TMDB 공식 로고를 표시한다.
  - 고지문: `This product uses the TMDB API but is not endorsed or certified by TMDB.`
  - 로고는 앱 로고보다 덜 눈에 띄게 둔다.
  - 로고는 TMDB의 logos-attribution 페이지에서 SVG를 내려받아 `assets/`에 둔다. 파일이 없으면 고지문만 표시한다.
- Gemini 무료 티어 안내: "추천 기능은 Google Gemini API 무료 티어를 사용하며, 입력 내용이 Google 제품 개선에 활용될 수 있습니다."

---

## 5. Gemini 연동 상세

### 5.1 호출 방식

- `client.models.generate_content()`
  - `response_mime_type="application/json"`
  - `response_json_schema=RecommendationList.model_json_schema()`
- 응답 텍스트는 `RecommendationList.model_validate_json()`으로 한 번 더 검증한다.
  - 스키마를 강제해도 검증을 생략하지 않는다.
- Google은 신규 개발에 Interactions API를 권장하지만, `generate_content`도 "fully supported"로 명시되어 있다.
  - 교체할 때 이 파일만 바꾸면 되도록 Gemini 호출은 `gemini_client.py`에만 둔다.

### 5.2 응답 스키마 (`core/models.py`)

```python
class Recommendation(BaseModel):
    title_ko: str          # 한국어 제목 (없으면 원제 그대로)
    original_title: str    # 원제 (TMDB 검색용)
    year: int | None       # 개봉/첫 방영 연도
    media_type: Literal["movie", "tv"]
    reason: str            # 추천 이유 (한국어 1~2문장)

class RecommendationList(BaseModel):
    items: list[Recommendation] = Field(min_length=1, max_length=5)
```

- 프롬프트로 3~5개를 요청한다.
- 스키마는 1~5개까지 허용한다. 1~2개만 와도 버리지 않고 보여주기 위해서다.

### 5.3 프롬프트 원칙

- 역할: 영화·드라마 큐레이터
- 규칙:
  - 실제로 존재하는 작품만 추천한다.
  - 원제와 연도를 정확히 쓴다.
  - 추천 이유는 사용자 입력과 연결해 한국어 1~2문장으로 쓴다.
- 사용자 입력은 `<user_request>` 태그로 감싼다. 그 안의 내용은 "취향 설명"으로만 다루라고 지시한다. 입력에 지시문이 섞여도 추천 규칙이 바뀌지 않게 하기 위해서다.

---

## 6. API 운영 전략

### 6.1 캐싱 (`st.cache_data`, app.py)

| 대상 | TTL |
|---|---|
| 트렌딩 목록 | 1시간 |
| 장르 목록 | 24시간 |
| TMDB 검색 결과 | 24시간 |
| 상세 정보 | 24시간 |
| Gemini 추천 (정리된 입력이 키) | 1시간 |

- 캐시에서 바로 응답한 경우는 호출 제한 횟수에 포함하지 않는다.

### 6.2 호출 제한 (`core/rate_limit.py`)

Gemini 호출 직전에 세 단계로 확인한다.

1. **세션 쿨다운:** 한 브라우저 세션에서 추천 요청 사이 최소 간격
   - 기본 10초 (`RECOMMEND_COOLDOWN_SEC`)
   - `st.session_state`에 마지막 요청 시각을 저장한다.
2. **앱 전체 분당 상한:** 최근 60초 동안의 호출 시각을 기록하는 슬라이딩 윈도우
   - 기본 5회 (`GEMINI_RPM_LIMIT`)
   - `st.cache_resource`로 모든 세션이 같은 카운터를 공유한다.
   - 여러 세션이 동시에 접근하므로 `threading.Lock`으로 보호한다.
3. **앱 전체 일일 상한:** 태평양 시간(America/Los_Angeles) 날짜 기준 카운터
   - 기본 200회 (`GEMINI_DAILY_LIMIT`)
   - Gemini의 일일 한도가 태평양 시간 자정에 리셋되는 것에 맞췄다.

- 기본값은 보수적으로 잡은 앱 자체 상한이다. 실제 Gemini 한도가 아니다.
  - 공식 문서는 무료 한도 숫자를 공개하지 않고 AI Studio에서 확인하라고 안내한다.
  - 배포 전에 AI Studio에서 내 한도를 확인하고, 그보다 낮게 설정한다.
- 한계: 카운터는 메모리에 있으므로 앱이 재시작되면 초기화된다.
  - Streamlit Cloud는 사용이 없으면 앱을 재우기 때문에 재시작될 수 있다.
  - MVP에서는 이를 허용한다.

### 6.3 재시도 (지수 백오프 + 지터)

- 재시도 대상:
  - HTTP 429, 500, 502, 503, 504
  - 연결 오류, 타임아웃
- 재시도 안 함: 그 외 4xx (400 잘못된 요청, 401/403 키 오류 등). 다시 보내도 결과가 같기 때문이다.
- 최대 3회 재시도 (총 4번 시도)
- 대기 시간: `random.uniform(0, min(20, 1 × 2^n))`초 ("full jitter" 방식)
  - n은 재시도 순번 (0부터)
  - 여러 사용자가 동시에 같은 시각에 재시도하는 것을 막는다.
- `Retry-After` 헤더가 있으면 그 값을 우선한다. 20초를 넘으면 기다리지 않고 바로 실패 처리한다.
- TMDB와 Gemini 모두 같은 `with_backoff()` 함수를 쓴다.
- google-genai SDK의 자체 재시도는 기본값(꺼짐)으로 둬서 재시도가 이중으로 돌지 않게 한다.

### 6.4 타임아웃

- TMDB 요청: 10초
- Gemini 요청: 30초

---

## 7. 에러 처리

| 상황 | 사용자에게 보이는 것 |
|---|---|
| API 키 없음 | 설정 방법 안내 화면, 해당 기능 비활성화 |
| 세션 쿨다운 중 | "N초 후에 다시 추천받을 수 있어요" |
| 앱 분당/일일 상한 도달 | "지금 요청이 많아요. 잠시 후 다시 시도해 주세요" |
| Gemini 재시도 후에도 실패 | 경고 메시지, 트렌딩은 정상 표시 |
| Gemini 응답 형식 오류 | "추천 결과를 읽지 못했어요" + 다시 시도 버튼 |
| TMDB에서 작품 못 찾음 | 포스터 없이 제목 + 추천 이유만 |
| TMDB 장애 | 트렌딩 영역에 오류 메시지, 추천은 이유만 표시 |
| 입력이 비었거나 300자 초과 | 입력창 아래 안내 문구, 호출하지 않음 |

- 예외 클래스 (`core/models.py` 또는 각 모듈)
  - `ConfigError`
  - `RateLimitExceeded(reason, retry_after_sec)`
  - `GeminiError`
  - `TmdbError`
- app.py는 이 예외들만 잡아서 위 메시지로 바꾼다.
- 오류 상세(스택 트레이스)는 `logging`으로 서버 로그에만 남긴다. 화면에는 노출하지 않는다.

---

## 8. 설정과 보안

### 8.1 설정 키

| 키 | 필수 | 기본값 |
|---|---|---|
| `TMDB_API_KEY` | 예 | 없음 |
| `GEMINI_API_KEY` | 예 | 없음 |
| `GEMINI_MODEL` | 아니오 | `gemini-3.5-flash-lite` |
| `GEMINI_RPM_LIMIT` | 아니오 | `5` |
| `GEMINI_DAILY_LIMIT` | 아니오 | `200` |
| `RECOMMEND_COOLDOWN_SEC` | 아니오 | `10` |

### 8.2 읽는 순서

`st.secrets` → 환경 변수(`.env` 포함) → 기본값

- `config.load_settings(secrets: Mapping | None)`는 순수 함수로 만든다.
  - app.py가 `st.secrets`를 안전하게 꺼내서 넘긴다.
  - 테스트에서는 딕셔너리를 넘긴다.
- 숫자 설정에 잘못된 값이 들어오면 `ConfigError`를 낸다.

### 8.3 보안 규칙

- `.env`, `.streamlit/secrets.toml`은 `.gitignore`에 등록한다.
- 예시 파일(`.env.example`, `secrets.toml.example`)만 커밋한다.
- API 키는 화면, 로그, 에러 메시지 어디에도 출력하지 않는다.
- 모든 API 호출은 서버(Streamlit 프로세스)에서만 일어난다. 브라우저에는 키가 전달되지 않는다.

---

## 9. 화면 구성 (app.py)

### 9.1 레이아웃

```
┌───────────────────────────────────────────────┐
│ 🎬 Mood Cinema                                 │
│ 지금 기분에 맞는 영화·드라마를 찾아드려요         │
├───────────────────────────────────────────────┤
│ [AI 추천]                                      │
│  ┌ 입력창 ──────────────────────────┐ [추천받기] │
│  예시: 비 오는 날 혼자 보는 스릴러 / ...          │
│                                               │
│  ┌ 1순위 히어로 카드 ─────────────────────────┐ │
│  │ [가로형 이미지]   제목                       │ │
│  │                  장르 · 연도 · ★평점         │ │
│  │                  ┌ AI 큐레이터의 한마디 ┐   │ │
│  │                  └────────────────────┘   │ │
│  │                  [상세 보기]                │ │
│  └───────────────────────────────────────────┘ │
│  [2순위][3순위][4순위][5순위]  ← 추천 카드        │
├───────────────────────────────────────────────┤
│ [트렌딩]  종류: (전체|영화|TV)                   │
│  오늘의 인기   [1][2][3][4][5]  ▸ 6~10위 더 보기 │
│  이번 주 인기  [1][2][3][4][5]  ▸ 6~10위 더 보기 │
│  장르 픽 [장르▼] [1][2][3][4][5] ▸ 6~10위 더 보기│
├───────────────────────────────────────────────┤
│ Credits: TMDB 로고 + 고지문 / Gemini 안내        │
└───────────────────────────────────────────────┘
```

- `st.set_page_config(layout="wide")`
- 히어로 카드는 `st.columns([3, 2])`, 카드 줄은 `st.columns(5)`를 쓴다.
- 추천 결과는 `st.session_state`에 저장한다. 그래서 상세 팝업을 열었다 닫아도 사라지지 않는다.
- 이미지 URL: `https://image.tmdb.org/t/p/{크기}{경로}`
  - 카드 포스터: w342
  - 상세 포스터: w500
  - 히어로 배경: w780

### 9.2 다크 테마

`.streamlit/config.toml`에 고정한다. 영화 포스터가 어두운 배경에서 더 잘 보이고, 참고 화면 5개 중 4개가 어두운 배경이다.

```toml
[theme]
base = "dark"
primaryColor = "#E8A33D"            # 버튼·강조 (따뜻한 앰버)
backgroundColor = "#0E0F13"
secondaryBackgroundColor = "#1A1C23" # 카드·박스 배경
textColor = "#EDEDED"
```

### 9.3 참고 화면

godly.design의 앱스토어 스크린샷이다. 레이아웃 참고용이며, 디자인이나 브랜드 요소를 그대로 가져오지 않는다.

- MUBI 작품 상세 ("OUR TAKE" 박스) → 4.0 AI 추천 이유 박스
- The Criterion Channel 탐색 (테마별 줄) → F1 트렌딩
- Peacock 작품 상세 (정보 순서) → F3 상세 팝업
- BritBox 드라마 홈 (대표작 히어로) → F2 1순위 히어로 카드
- Prime Video 장르 검색 (결과 리스트) → 추후 모바일 화면 개선 시 참고

---

## 10. 테스트 전략

실제 API를 부르지 않고 가짜 응답(mock)으로 검증한다.

- `test_config.py`
  - Secrets가 환경 변수보다 우선하는지
  - 기본값이 적용되는지
  - 숫자 설정이 잘못되면 오류가 나는지
- `test_tmdb_client.py`
  - 트렌딩 응답을 `MediaItem`으로 바꾸는지 (영화 `title` / TV `name` 차이 포함)
  - 장르 이름 기준 필터가 동작하는지
  - 장르 픽 결과가 0개일 때 빈 목록을 돌려주는지
  - 예고편 선택 규칙이 맞는지
- `test_gemini_client.py`
  - 정상 JSON을 파싱하는지
  - 형식이 깨진 JSON이면 `GeminiError`가 나는지
  - 요청 config에 스키마가 들어가는지
- `test_recommender.py`
  - 1차 검색 실패 시 2차 검색으로 넘어가는지
  - 둘 다 실패하면 "미확인" 처리하는지
  - 같은 작품이 중복되면 제거하는지
  - 히어로 선정: 1순위가 미확인이면 확인된 다음 작품이 히어로가 되는지
- `test_rate_limit.py`
  - 429면 재시도하고, 400이면 재시도하지 않는지
  - `Retry-After`를 따르는지
  - 대기 시간이 상한(20초)을 넘지 않는지
  - 슬라이딩 윈도우 상한이 동작하는지
  - 태평양 시간 자정에 일일 카운터가 리셋되는지
  - 시계와 sleep은 주입해서 실제로 기다리지 않는다.

---

## 11. 배포 (Streamlit Community Cloud)

1. GitHub 저장소를 만들고 push한다. 커밋 전에 `.gitignore`에 `.env`, `.streamlit/secrets.toml`이 있는지 확인한다.
2. share.streamlit.io에서 GitHub 계정을 연동하고, 저장소·브랜치·`app.py`를 선택한다.
3. Advanced settings → Secrets에 TOML 형식으로 입력한다.
   ```toml
   TMDB_API_KEY = "..."
   GEMINI_API_KEY = "..."
   GEMINI_RPM_LIMIT = 5
   ```
4. 배포 후 확인한다.
   - 트렌딩이 표시되는지
   - 추천이 1회 성공하는지
   - 쿨다운 메시지가 뜨는지
   - Credits 영역이 보이는지

---

## 12. 로드맵

### MVP 마일스톤

1. **M1 기반:** 프로젝트 구조, 설정 로드, TMDB 트렌딩 + 장르 필터 + 캐싱
2. **M2 AI 추천:** Gemini 구조화 출력, TMDB 매칭, 추천 카드
3. **M3 상세:** 상세 팝업, 예고편
4. **M4 안정성:** 호출 제한, 재시도, 에러 처리, 테스트 보강
5. **M5 공개:** 배포, README(스크린샷, 아키텍처 그림, 트러블슈팅 기록)

### 추후 확장 (이번 범위 아님)

- 찜 목록 (세션 또는 로컬 저장)
- 추천 결과 공유 링크 (`st.query_params`)
- 시청 가능한 OTT 표시 (TMDB watch providers)
- Interactions API로 이전

---

## 13. 검증 기록

### 13.1 공식 문서로 확인한 사실 (2026-10-22)

- `gemini-2.0-flash` / `-lite`는 종료일(가장 이른 예정일)이 2026-06-01이다.
- 신규 프로젝트 권장 모델은 `gemini-3.5-flash-lite` 또는 `gemini-3.8-flash`다.
- `gemini-3.5-flash-lite`는 Standard 무료 티어를 제공한다. 무료 티어 입력은 Google 제품 개선에 활용된다.
- 무료 한도 숫자는 공식 문서에 공개되어 있지 않다. AI Studio에서 확인해야 하고, 한도가 보장되지 않는다고 명시되어 있다.
- 일일 요청 한도(RPD)는 태평양 시간 자정에 리셋된다.
- `generate_content`는 "fully supported"이고, 신규 개발에는 Interactions API를 권장한다.
- TMDB 요청 한도는 대략 초당 40회 수준이며 언제든 바뀔 수 있다. 초과하면 429를 받는다.
- TMDB 무료 이용은 비상업 용도에 한하며 출처 표기가 의무다.
- google-genai SDK는 `retry_options`를 주지 않으면 재시도하지 않는다 (SDK 2.32.0 소스로 확인).
- `response_json_schema`는 `enum`, `minItems`, `maxItems`, null 타입 등을 지원한다. 지원하지 않는 키워드는 모델이 무시한다.
  - 그래서 Pydantic 재검증(5.1)을 생략하지 않는다.
  - 공식 예제도 중첩 Pydantic 모델의 `model_json_schema()`를 그대로 넘긴다.

### 13.2 근거를 찾지 못해 제외한 주장

- "429가 연속되면 Google이 API 키를 박탈한다": 공식 문서 근거를 찾지 못해 설계 근거에서 제외했다.

### 13.3 출처

- Gemini deprecations: https://ai.google.dev/gemini-api/docs/deprecations
- Gemini models: https://ai.google.dev/gemini-api/docs/models
- Gemini rate limits: https://ai.google.dev/gemini-api/docs/rate-limits
- Gemini pricing: https://ai.google.dev/gemini-api/docs/pricing
- Structured outputs (generate_content): https://ai.google.dev/gemini-api/docs/generate-content/structured-output
- Migrating to the Interactions API: https://ai.google.dev/gemini-api/docs/migrate-to-interactions
- TMDB rate limiting: https://developer.themoviedb.org/docs/rate-limiting
- TMDB FAQ (출처 표기·상업 이용): https://developer.themoviedb.org/docs/faq
- TMDB 로고: https://www.themoviedb.org/about/logos-attribution
- 참고 화면 (godly.design): https://godly.design/app/mubi , https://godly.design/app/the-criterion-channel , https://godly.design/app/peacock-tv , https://godly.design/app/britbox , https://godly.design/app/amazon-prime-video
