# Mood Cinema 설계 문서 (v0.3)

> 기분·상황을 문장으로 입력하면 AI가 영화/TV 작품을 골라 주고, TMDB의 실제 데이터(포스터·평점·줄거리)로 보강해 보여주는 Reflex 웹 앱
>
> - 작성일: 2026-10-22
> - 용도: 개인 포트폴리오
> - 상태: v0.3 초안 (사용자 리뷰 대기)
> - 변경 이력
>   - v0.1 → v0.2: 참고 화면 반영 (추천 이유 박스, 테마별 트렌딩 줄, 1순위 히어로 카드, 다크 테마)
>   - v0.2 → v0.3: 화면 프레임워크를 Streamlit → Reflex로 교체. 참고 화면에 가까운 디자인(겹친 히어로, 가로 스크롤 줄, 호버 효과)을 위해서다. `core/`의 API·추천 로직은 그대로 두고, 캐싱을 `core/service.py`로, 화면용 데이터 변환을 `core/presenter.py`로 옮긴다.

---

## 1. 목표와 범위

### 1.1 목표

- 사용자가 "비 오는 날 혼자 보기 좋은 몰입감 있는 스릴러"처럼 자유롭게 입력하면, 실제로 존재하는 작품 3~5개를 추천 이유와 함께 카드로 보여준다.
- 이번 주/오늘 인기 있는 영화·TV TOP 10을 장르별로 탐색할 수 있다.
- 무료 API 한도 안에서 안정적으로 동작하도록 캐싱·호출 제한·재시도를 갖춘다.

### 1.2 완성 기준 (Definition of Done)

1. Reflex Cloud에 배포된 공개 URL에서 위 두 기능이 동작한다.
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

- Python 3.11 이상 (Reflex 요구 사항과 같음)
- `reflex==0.10.0` — 화면(UI). 파이썬 코드를 React 웹페이지로 바꿔 주고, 파이썬 로직은 서버에서 실행한다
  - 아직 1.0 전이라 버전 사이에 API가 바뀔 수 있다. 버전을 고정하고, 올릴 때는 공식 업그레이드 안내를 먼저 읽는다
- `google-genai==2.32.0` — Gemini API 공식 Python SDK
- `requests==2.34.2` — TMDB REST API 호출
- `pydantic==2.14.1` — Gemini 응답 형식 정의·검증
- `python-dotenv==1.2.4` — 로컬 개발용 `.env` 읽기
- `tzdata==2026.5` — Windows에서 태평양 시간대 계산용
- `httpx==0.28.1` — Gemini SDK 연결 오류 구분용
- `pytest==9.1.1` — 테스트 (개발용, `requirements-dev.txt`)
- 제거: `streamlit`

**외부 API**

- Gemini 모델: `gemini-3.5-flash-lite` (무료 티어 있음, 공식 문서가 신규 프로젝트에 권장)
- TMDB API v3 (`https://api.themoviedb.org/3`), 인증은 `api_key` 쿼리 파라미터

---

## 3. 아키텍처

### 3.1 4계층 구조

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

### 3.2 폴더 구조

```
mood-cinema/
├─ rxconfig.py               # Reflex 설정 (app_name="mood_cinema")
├─ mood_cinema/              # Reflex 앱 (화면 계층)
│  ├─ __init__.py
│  ├─ mood_cinema.py         # rx.App 생성, 페이지 등록, 테마
│  ├─ state.py               # State: 화면 상태 + 이벤트 핸들러 (로직은 core 호출)
│  ├─ styles.py              # 색·간격·그라데이션 등 디자인 토큰
│  └─ components/
│     ├─ header.py           # 상단 바
│     ├─ recommend.py        # 입력창, 예시 칩, 히어로, 추천 카드
│     ├─ trending.py         # 테마별 가로 스크롤 줄
│     ├─ detail_dialog.py    # 상세 팝업
│     └─ footer.py           # Credits
├─ core/
│  ├─ (기존) config.py, models.py, rate_limit.py, tmdb_client.py, gemini_client.py, recommender.py
│  ├─ ttl_cache.py           # 신규: 시간 제한 캐시
│  ├─ service.py             # 신규: MoodService (캐싱·호출 제한·추천 흐름)
│  └─ presenter.py           # 신규: 화면용 dataclass와 변환 함수
├─ assets/                   # Reflex 정적 파일 폴더. tmdb_logo.svg → "/tmdb_logo.svg"로 제공
├─ tests/                    # 기존 core 테스트 + 신규 test_ttl_cache, test_service, test_presenter
├─ docs/specs/, docs/plans/
├─ .env.example, .gitignore, requirements.txt, requirements-dev.txt, README.md, CLAUDE.md
└─ (삭제) app.py, .streamlit/, tests/test_app_smoke.py
```

### 3.3 설계 원칙

- **`core/`는 화면 프레임워크(streamlit, reflex)를 import하지 않는다.** 그래서 프레임워크 없이 테스트할 수 있고, 이번처럼 화면만 갈아 끼울 수 있다.
- **외부 의존성은 주입받는다.** HTTP 세션, SDK 클라이언트, sleep, 시계를 생성자나 인자로 받는다.
- **Reflex State는 얇게 둔다.** State는 "입력 받기 → core 호출 → 결과를 화면용 데이터로 저장"만 한다. 판단 로직(캐시, 제한, 매칭, 문구 만들기)은 `core/`에 둔다.
- **화면에 넘기는 데이터는 평평한 dataclass로 만든다** (`core/presenter.py`). 문자열·숫자·불리언만 쓰고, 값이 없으면 `None` 대신 빈 문자열을 쓴다. Reflex 상태 값은 JSON으로 바뀌어 브라우저로 가므로 단순할수록 안전하다.
- **오래 걸리는 호출은 백그라운드 이벤트로 돌린다.** Gemini·TMDB 호출은 동기 함수이므로 `@rx.event(background=True)` 핸들러 안에서 `asyncio.to_thread()`로 실행하고, 상태 변경은 `async with self:` 블록 안에서만 한다. 그동안 화면은 로딩 표시를 보여준다.

---

## 4. 기능 명세

### F1. 트렌딩 탐색 (테마별 가로 스크롤 줄)

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
  - 줄마다 TOP 10을 **한 줄 가로 스크롤**로 보여준다 (v0.2의 "6~10위 더 보기" 펼침은 없앤다).
  - 카드: 포스터, 제목, "연도 · ★평점". 오늘·이번 주 줄은 포스터 왼쪽 위에 순위 숫자를 붙인다.
  - 카드를 누르면 상세 팝업이 열린다 (별도 "상세 보기" 버튼 없음).
- **한계:** 장르 픽은 20개 중에서 거르므로 10개보다 적을 수 있다. 0개면 "이번 주 인기작 중 이 장르가 없어요"를 표시한다.

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
  - **1순위 히어로 배너** (참고 화면: BritBox 대표작 히어로, Peacock 상세)
    - 확인된 첫 작품의 가로형 배경 이미지(`backdrop_path`, w1280. 없으면 포스터 w780)를 배너 전체 배경으로 깔고, 왼쪽에서 오른쪽으로 옅어지는 어두운 그라데이션을 겹친다.
    - 그라데이션 위 왼쪽에 글자를 올린다: 작은 라벨 "AI PICK", 제목, "장르 · 연도 · ★평점", AI 추천 이유 박스, "상세 보기" 버튼
  - **나머지 추천 카드** (2~5순위): 포스터, 제목, "연도 · ★평점", AI 추천 이유(최대 3줄, 넘치면 말줄임). 카드를 누르면 상세 팝업
  - TMDB에서 못 찾은 작품은 포스터 자리에 "정보 없음" 자리 표시를 보여주고, 누를 수 없다.
  - 1순위가 TMDB 미확인이면, 확인된 작품 중 가장 앞의 것을 히어로로 올린다. 모두 미확인이면 히어로 없이 카드만 보여준다.
  - 추천을 기다리는 동안 히어로 자리에 로딩 뼈대(skeleton)와 "기분에 맞는 작품을 찾고 있어요..."를 보여준다.

#### 4.0 AI 추천 이유 박스 (참고 화면: MUBI의 "OUR TAKE")

- 라벨: "AI 큐레이터의 한마디" (앰버색, 작은 글씨)
- 왼쪽에 앰버색 세로 줄(3px), 옅은 앰버 배경. 줄거리보다 위에 둔다.
- 쓰이는 곳: 히어로 배너, 상세 팝업 (추천에서 연 경우에만)

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

- **트리거:** 히어로의 "상세 보기" 버튼, 또는 카드 클릭 → `rx.dialog`
- **처리:** `GET /movie/{id}` 또는 `/tv/{id}`
  - 파라미터: `language=ko-KR&append_to_response=videos&include_video_language=ko,en`
  - 불러오는 동안 팝업 안에 로딩 뼈대를 보여준다.
  - 실패하면 팝업 안에 "상세 정보를 불러오지 못했어요"를 보여준다 (v0.2의 "목록 정보로 대신 표시"는 없앤다).
- **출력 순서** (참고 화면: Peacock 상세 화면)
  1. 위쪽 배경 이미지(w1280) + 아래로 어두워지는 그라데이션
  2. 배경에 겹친 포스터(w342) 옆에 제목/원제
  3. "장르 · 연도 · 러닝타임(영화) 또는 시즌 수(TV) · ★평점"
  4. AI 추천 이유 박스 (추천에서 연 경우에만, 4.0 참고)
  5. 줄거리. 비어 있으면 "한국어 줄거리가 등록되지 않았어요"
  6. 예고편: `site == "YouTube"`이고 `type == "Trailer"`인 첫 영상, 없으면 아무 YouTube 영상, 그것도 없으면 숨긴다. 16:9 YouTube 임베드(`https://www.youtube.com/embed/{key}`)

### F4. 출처 표기 (필수)

- 페이지 하단 "Credits" 영역에 아래 고지문과 TMDB 공식 로고를 표시한다.
  - 고지문: `This product uses the TMDB API but is not endorsed or certified by TMDB.`
  - 로고는 앱 로고보다 덜 눈에 띄게 둔다 (높이 16px 정도).
  - 로고는 TMDB의 logos-attribution 페이지에서 SVG를 내려받아 `assets/tmdb_logo.svg`로 둔다. Reflex는 `assets/` 파일을 `/tmdb_logo.svg` 주소로 제공한다. 파일이 없으면 고지문만 표시한다.
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

### 6.1 캐싱 (`core/ttl_cache.py` + `core/service.py`)

| 대상 | TTL |
|---|---|
| 트렌딩 목록 | 1시간 |
| 장르 목록 | 24시간 |
| TMDB 검색 결과 | 24시간 |
| 상세 정보 | 24시간 |
| Gemini 추천 (정리된 입력이 키) | 1시간 |

- 캐시에서 바로 응답한 경우는 호출 제한 횟수에 포함하지 않는다.
- 캐시는 백엔드 프로세스 메모리에 있다. 실패(예외)는 캐시하지 않는다.
- 항목이 1,024개를 넘으면 만료된 것부터, 그다음 오래된 것부터 지운다.

### 6.2 호출 제한 (`core/rate_limit.py`)

Gemini 호출 직전에 세 단계로 확인한다.

1. **세션 쿨다운:** 한 브라우저 세션에서 추천 요청 사이 최소 간격
   - 기본 10초 (`RECOMMEND_COOLDOWN_SEC`)
   - Reflex State의 백엔드 전용 변수 `_last_recommend_at`에 마지막 요청 시각을 저장한다 (밑줄로 시작하는 변수는 브라우저로 보내지 않는다).
2. **앱 전체 분당 상한:** 최근 60초 동안의 호출 시각을 기록하는 슬라이딩 윈도우
   - 기본 5회 (`GEMINI_RPM_LIMIT`)
   - 백엔드 프로세스에 `MoodService`를 하나만 만들어 모든 세션이 같은 카운터를 공유한다.
   - 여러 세션이 동시에 접근하므로 `threading.Lock`으로 보호한다.
3. **앱 전체 일일 상한:** 태평양 시간(America/Los_Angeles) 날짜 기준 카운터
   - 기본 200회 (`GEMINI_DAILY_LIMIT`)
   - Gemini의 일일 한도가 태평양 시간 자정에 리셋되는 것에 맞췄다.

- 기본값은 보수적으로 잡은 앱 자체 상한이다. 실제 Gemini 한도가 아니다.
  - 공식 문서는 무료 한도 숫자를 공개하지 않고 AI Studio에서 확인하라고 안내한다.
  - 배포 전에 AI Studio에서 내 한도를 확인하고, 그보다 낮게 설정한다.
- 한계: 카운터는 메모리에 있으므로 앱이 재시작되면 초기화된다.
  - Reflex Cloud 무료 플랜은 상시 실행(Always-on)이 포함되지 않으므로 재시작될 수 있다.
  - 백엔드 프로세스가 여러 개로 뜨면 카운터도 프로세스마다 따로 생긴다.
  - MVP에서는 둘 다 허용한다.

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
- `mood_cinema/state.py`는 이 예외들만 잡아서 위 메시지로 바꾼다.
- 메시지는 해당 영역 안에 `rx.callout`으로 보여준다 (경고: 앰버, 오류: 빨강).
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

환경 변수 → 기본값

- 로컬: `.env` 파일을 `python-dotenv`로 읽어 환경 변수로 올린다 (`mood_cinema/state.py`가 import될 때 한 번).
- 배포: Reflex Cloud의 Secrets(대시보드 Settings > Secrets, 또는 `reflex deploy --envfile .env`)가 환경 변수로 들어온다.
- `core/config.py`의 `load_settings()`는 그대로 쓴다. `secrets` 인자 없이 호출하면 환경 변수만 읽는다.
- 숫자 설정에 잘못된 값이 들어오면 `ConfigError`를 낸다.

### 8.3 보안 규칙

- `.env`는 `.gitignore`에 등록한다. 예시 파일(`.env.example`)만 커밋한다.
- **API 키와 클라이언트 객체는 Reflex State 변수에 절대 넣지 않는다.** State의 일반 변수는 브라우저로 전송된다. 키는 `core/service.py`의 모듈 수준 싱글턴 안에만 둔다.
- API 키는 화면, 로그, 에러 메시지 어디에도 출력하지 않는다.
- 모든 API 호출은 Reflex 백엔드(서버)에서만 일어난다.

---

## 9. 화면 구성 (Reflex)

### 9.1 디자인 토큰 (`mood_cinema/styles.py`)

- 테마: `rx.theme(appearance="dark", accent_color="amber", radius="large")`
- 색
  - 배경 `#0E0F13`, 면(카드·박스) `#1A1C23`, 글자 `#EDEDED`, 보조 글자 `#9AA0A6`
  - 강조 `#E8A33D` (Radix 테마 accent는 amber, 직접 쓰는 곳은 이 값)
  - 이유 박스 배경 `rgba(232, 163, 61, 0.08)`
- 히어로 그라데이션: `linear-gradient(90deg, rgba(14,15,19,0.95) 0%, rgba(14,15,19,0.70) 40%, rgba(14,15,19,0) 75%)` + 아래쪽 `linear-gradient(0deg, #0E0F13 0%, rgba(14,15,19,0) 30%)`
- 글꼴: `Pretendard, "Apple SD Gothic Neo", "Noto Sans KR", sans-serif` (설치된 글꼴을 순서대로 사용)
- 간격: 섹션 사이 48px, 페이지 좌우 여백 데스크톱 48px / 모바일 16px
- 포스터 비율 2:3, 모서리 8px. 카드 호버 시 `scale(1.04)` + 앰버 테두리, 0.15초 전환

### 9.2 레이아웃

```
┌──────────────────────────────────────────────────────────────┐
│ 🎬 Mood Cinema                         AI 추천   트렌딩        │ ← 상단 바 (스크롤해도 고정, 반투명)
├──────────────────────────────────────────────────────────────┤
│  오늘 기분은 어떤가요?                                         │
│  ┌ 입력창 (2줄) ─────────────────────────────┐ [추천받기]      │
│  (비 오는 날 스릴러) (야근 후 코미디) (주말 가족 드라마) ← 칩  │
│                                                              │
│ ┌ 히어로 배너 (배경 이미지 + 그라데이션) ──────────────────────┐ │
│ │ AI PICK                                                    │ │
│ │ 제목 (큰 글씨)                                             │ │
│ │ 장르 · 연도 · ★평점                                        │ │
│ │ ┃ AI 큐레이터의 한마디                                     │ │
│ │ ┃ 추천 이유...                                             │ │
│ │ [상세 보기]                                                │ │
│ └────────────────────────────────────────────────────────────┘ │
│  [카드][카드][카드][카드]   ← 2~5순위 (포스터 + 이유 3줄)        │
├──────────────────────────────────────────────────────────────┤
│  트렌딩                               (전체|영화|TV)          │
│  오늘의 인기   [1][2][3][4][5][6][7] → 가로 스크롤             │
│  이번 주 인기  [1][2][3][4][5][6][7] →                         │
│  장르 픽 [드라마 ▼]  [ ][ ][ ][ ][ ] →                         │
├──────────────────────────────────────────────────────────────┤
│  Credits: TMDB 로고 + 고지문 / Gemini 안내                     │
└──────────────────────────────────────────────────────────────┘
```

- 예시 칩을 누르면 입력창에 그 문장이 채워진다 (바로 요청하지는 않음).
- 추천받기 버튼은 요청 중에 로딩 표시로 바뀌고 다시 누를 수 없다.
- 히어로 높이: 데스크톱 최소 440px, 모바일(768px 미만)에서는 배경 이미지 아래로 글자가 내려가는 세로 배치
- 트렌딩 카드 폭: 데스크톱 160px, 모바일 120px. 줄은 `overflow-x: auto` + `scroll-snap`
- 트렌딩을 불러오는 동안 줄마다 카드 모양 로딩 뼈대 6개
- 페이지 로드 시(`on_load`) 장르 목록과 트렌딩을 불러온다.

### 9.3 화면용 데이터 (`core/presenter.py`)

화면 컴포넌트는 아래 dataclass만 받는다. 모든 필드에 기본값이 있다 (빈 화면 상태를 표현하기 위해).

- `CardVM`: `key, tmdb_id, media_type, title, meta, poster_url, reason, rank, clickable`
- `HeroVM`: `tmdb_id, media_type, title, meta, backdrop_url, reason`
- `DetailVM`: `title, original_title, meta, overview, poster_url, backdrop_url, reason, trailer_embed_url`

### 9.4 참고 화면

godly.design의 앱스토어 스크린샷이다. 레이아웃 참고용이며, 디자인이나 브랜드 요소를 그대로 가져오지 않는다.

- MUBI 작품 상세 ("OUR TAKE" 박스) → 4.0 AI 추천 이유 박스
- The Criterion Channel 탐색 (테마별 줄) → F1 트렌딩
- Peacock 작품 상세 (정보 순서, 배경 위 겹친 배치) → F3 상세 팝업
- BritBox 드라마 홈 (대표작 히어로) → F2 히어로 배너
- Prime Video 장르 검색 (결과 리스트) → 추후 모바일 화면 개선 시 참고

---

## 10. 테스트 전략

실제 API를 부르지 않고 가짜 응답(mock)으로 검증한다.

- 기존 그대로: `test_config.py`, `test_models.py`, `test_rate_limit.py`, `test_tmdb_client.py`, `test_gemini_client.py`, `test_recommender.py`
- 신규 `test_ttl_cache.py`
  - TTL 안에서는 factory를 다시 부르지 않는지, TTL이 지나면 다시 부르는지 (시계 주입)
  - factory가 예외를 내면 캐시에 남지 않는지
  - 1,024개 초과 시 만료·오래된 항목부터 지우는지
- 신규 `test_service.py`
  - 같은 문장으로 두 번 추천하면 Gemini·quota가 한 번만 불리는지
  - 캐시 적중 시 `RateLimitExceeded`가 나지 않는지 (quota가 꽉 차 있어도)
  - 트렌딩·검색·상세가 TTL 동안 TMDB를 다시 부르지 않는지
  - `can_recommend`가 Gemini 키 유무를 반영하는지
- 신규 `test_presenter.py`
  - meta 문구 형식 ("드라마 · 2019 · ★8.5", 연도 없음, 장르 없음)
  - 이미지 URL 크기, 없는 이미지는 빈 문자열
  - 미확인 추천 → `clickable=False`, `poster_url=""`
  - 예고편 키 → `https://www.youtube.com/embed/{key}`, 없으면 빈 문자열
  - 줄거리 빈 값 → "한국어 줄거리가 등록되지 않았어요"
- 삭제: `test_app_smoke.py` (Streamlit AppTest 전용)
- 화면 확인: 자동 테스트 대신, 작업마다 `reflex run`으로 띄워 직접 확인한다. 화면 코드가 Reflex 규칙에 맞는지는 `reflex export --frontend-only --no-zip`이 오류 없이 끝나는지로 확인한다 (프런트엔드 빌드 과정에서 잘못된 컴포넌트 사용이 드러난다).

---

## 11. 배포 (Reflex Cloud)

1. `reflex login`으로 Reflex Cloud에 로그인한다.
2. 프로젝트 루트에서 배포한다.
   ```bash
   reflex deploy --app-name mood-cinema --envfile .env
   ```
   - `--envfile`로 넘긴 값은 앱의 Secrets(환경 변수)로 등록된다. 나중에 바꿀 때는 대시보드 Settings > Secrets에서 고친다.
3. 무료 플랜 조건: 앱 1개, 공유 컴퓨팅, 상시 실행·커스텀 도메인 없음.
4. 배포 후 확인한다.
   - 트렌딩 세 줄이 표시되는지
   - 추천이 1회 성공하는지
   - 쿨다운 메시지가 뜨는지
   - Credits 영역이 보이는지
- 대안: 공식 문서의 Docker 예제로 직접 호스팅할 수 있다 (서버 비용은 별도).

---

## 12. 로드맵

### 완료 (v0.2, Streamlit)

- M1~M5 완료: core 전체, Streamlit 화면, 테스트

### Reflex 전환 마일스톤 (v0.3)

1. **R1 서비스 계층:** `core/ttl_cache.py`, `core/service.py` (Streamlit 화면은 아직 그대로)
2. **R2 화면용 데이터:** `core/presenter.py`
3. **R3 Reflex 뼈대 + 트렌딩:** 프로젝트 초기화, 테마·상단 바·Credits, 트렌딩 가로 스크롤 줄
4. **R4 AI 추천:** 입력창·예시 칩, 백그라운드 추천, 히어로 배너, 추천 카드, 에러 메시지
5. **R5 상세 팝업 + 정리:** 상세 팝업, Streamlit 제거, README·CLAUDE.md 갱신, 배포

### 추후 확장 (이번 범위 아님)

- 찜 목록 (브라우저 저장소)
- 추천 결과 공유 링크 (URL 쿼리)
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

- Reflex (2026-10-22 확인)
  - PyPI 최신 버전 `reflex 0.10.0`, Python 3.11 이상 필요
  - 백그라운드 이벤트: `@rx.event(background=True)` async 핸들러, 상태 변경은 `async with self:` 안에서만 가능 (밖에서 바꾸면 `ImmutableStateError`)
  - 상태 변수는 JSON 직렬화 가능해야 하고, 사용자 정의 타입은 dataclass를 권장한다
  - 배포: `reflex deploy --envfile`/`--env`로 환경 변수 전달, 대시보드 Settings > Secrets에서 관리
  - Reflex Cloud 무료 플랜: 앱 1개, 공유 컴퓨팅, 상시 실행·커스텀 도메인 미포함
  - 직접 호스팅: `reflex run --env prod`, `reflex export`, 공식 Docker 예제

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
- Reflex 설치: https://reflex.dev/docs/getting-started/installation/
- Reflex 백그라운드 이벤트: https://reflex.dev/docs/events/background-events/
- Reflex 사용자 정의 변수 타입: https://reflex.dev/docs/vars/custom-vars/
- Reflex Secrets: https://reflex.dev/docs/hosting/secrets-environment-vars/
- Reflex deploy CLI: https://reflex.dev/docs/hosting/cli/deploy/
- Reflex 직접 호스팅: https://reflex.dev/docs/hosting/self-hosting/
- Reflex 요금제: https://reflex.dev/pricing/
