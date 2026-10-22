# Mood Cinema Reflex 전환 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 완성된 Streamlit 화면을 Reflex로 교체해, 참고 화면처럼 겹친 히어로 배너·가로 스크롤 줄·호버 카드·상세 팝업을 갖춘 웹 앱으로 만든다.

**Architecture:** `core/`의 API·추천 로직(Task 1~5 결과)은 그대로 쓴다. Streamlit에 묶여 있던 캐싱·호출 제한 흐름을 `core/service.py`로, 화면 문구·URL 만들기를 `core/presenter.py`로 옮겨 테스트 가능하게 만든 뒤, 얇은 Reflex State와 컴포넌트를 그 위에 올린다.

**Tech Stack:** Python 3.11+, reflex 0.10.0, 기존 core 의존성(google-genai 2.32.0, requests 2.34.2, pydantic 2.14.1, python-dotenv 1.2.4, tzdata 2026.5, httpx 0.28.1), pytest 9.1.1

**Spec:** `docs/specs/2026-10-22-mood-cinema-design.md` (v0.3). 이전 계획 `docs/plans/2026-10-22-mood-cinema.md`(Task 1~6)는 완료 상태다.

## Global Constraints

- `reflex==0.10.0`으로 고정. 1.0 전이라 API가 이 계획과 다르면 **공식 문서(0.10)를 따르고, 바꾼 점을 커밋 메시지에 적는다.**
- `core/` 아래 어떤 파일도 `streamlit`이나 `reflex`를 import하지 않는다.
- API 키, `TmdbClient`, `GeminiClient`, `MoodService`는 Reflex State 변수에 넣지 않는다 (State 일반 변수는 브라우저로 간다). 서비스는 `mood_cinema/state.py`의 모듈 수준 함수 `get_service()`로만 꺼낸다.
- Gemini·TMDB 호출은 `@rx.event(background=True)` 핸들러에서 `await asyncio.to_thread(...)`로 실행하고, State 변경은 `async with self:` 안에서만 한다.
- 캐시 TTL(초): 트렌딩 3600, 장르 86400, 검색 86400, 상세 86400, 추천 3600. 캐시 최대 1,024개.
- 이미지 크기: 카드 포스터 `w342`, 히어로 배경 `w1280`(없으면 포스터 `w780`), 상세 배경 `w1280`, 상세 포스터 `w342`.
- 디자인 토큰은 스펙 9.1 값을 `mood_cinema/styles.py`에 상수로 두고 컴포넌트는 그 상수만 쓴다.
- 화면 문구는 스펙 7장 표와 F1~F4 문구 그대로. 고지문·Gemini 안내문도 그대로.
- 기존 core 테스트는 계속 전부 통과해야 한다.

## Review Focus

1. **한글 입력(IME) 조합:** 입력창에 "비 오는 날"을 빠르게 쳐도 글자가 중복·누락되지 않아야 한다. → Task 4 Step 6 수동 확인. 문제가 있으면 입력창을 비제어(uncontrolled) 폼 입력으로 바꾸고 예시 칩은 `key`를 바꿔 다시 그리는 방식으로 채운다.
2. **추천 중복 요청:** 로딩 중 버튼을 연타해도 요청이 1번만 가야 한다. → Task 4: 버튼 `loading`/`disabled` + 핸들러 첫 줄에서 `loading`이면 즉시 return. Step 6 수동 확인.
3. **트렌딩 종류 빠른 전환:** 전체→영화→TV를 빠르게 눌렀을 때 늦게 끝난 이전 요청이 최신 결과를 덮어쓰면 안 된다. → Task 3: 요청 시작 시 `media_label`을 기억해 두고, 결과를 쓸 때 현재 값과 다르면 버린다. Step 7 수동 확인.
4. **호출 한도가 찬 상태의 캐시 적중:** 같은 문장 재요청은 한도와 상관없이 성공해야 한다. → Task 1 `test_recommend_cache_hit_ignores_full_quota`
5. **상세 팝업 실패 시 이전 작품 잔상:** A 상세를 본 뒤 B 상세가 실패하면 A 내용이 남아 있으면 안 된다. → Task 5: 열 때마다 `view = DetailVM()`로 비우고 로딩 표시. Step 5 수동 확인.

---

## Branch Workflow

Task 하나 = 브랜치 하나. 앞 Task를 `main`에 머지한 뒤 최신 `main`에서 다음 브랜치를 만든다. 머지 조건: `pytest -v` 전체 통과 + (Task 3부터) `reflex export --frontend-only --no-zip` 성공.

`feat/07-service-layer` → `feat/08-presenter` → `feat/09-reflex-trending` → `feat/10-reflex-recommend` → `feat/11-reflex-detail-cleanup`

---

### Task 1: 서비스 계층 (`core/ttl_cache.py`, `core/service.py`)

**Files:**
- Create: `core/ttl_cache.py`, `core/service.py`
- Test: `tests/test_ttl_cache.py`, `tests/test_service.py`

**Interfaces:**
- Consumes: `TmdbClient`, `GeminiClient`, `GeminiQuota`, `build_result`, `Settings`, `ConfigError`, 도메인 dataclass (기존)
- Produces (`core/ttl_cache.py`):
  - `class TTLCache` — `__init__(self, *, max_entries: int = 1024, clock: Callable[[], float] = time.monotonic)`, `get_or_set(self, key: Hashable, ttl: float, factory: Callable[[], T]) -> T`, `__len__(self) -> int`. `threading.Lock`으로 dict 접근을 보호하되 factory는 락 밖에서 호출한다(동시에 같은 키가 두 번 계산될 수 있음, 허용). 예외는 저장하지 않는다. 넣을 때 개수가 넘으면 만료된 항목을 먼저, 그래도 넘으면 가장 먼저 넣은 항목부터 지운다.
- Produces (`core/service.py`):
  - 상수 `TTL_TRENDING = 3600`, `TTL_GENRES = 86400`, `TTL_SEARCH = 86400`, `TTL_DETAIL = 86400`, `TTL_RECOMMEND = 3600`
  - `class MoodService` — `__init__(self, tmdb: TmdbClient, gemini: GeminiClient | None, quota: GeminiQuota, *, cache: TTLCache | None = None)`
    - `can_recommend: bool` (property, `gemini is not None`)
    - `trending(media_type, window) -> list[MediaItem]`, `genres() -> dict[int, str]`, `search(query, media_type, year) -> list[MediaItem]`, `detail(tmdb_id, media_type) -> MediaDetail` — 캐시 키는 `("trending", media_type, window)`처럼 첫 원소로 종류를 구분
    - `recommend(self, query: str) -> RecommendationResult` — `query`는 이미 `validate_query`를 거친 값. Gemini 결과만 `("recommend", query)`로 캐시하고, 캐시가 없을 때만 `quota.acquire()` 후 `gemini.recommend(query)`. 그다음 `build_result(recs, self.search)`. Gemini가 없으면 `ConfigError("GEMINI_API_KEY가 설정되지 않았어요")`
  - `build_service(settings: Settings) -> MoodService | None` — TMDB 키가 없으면 `None`. Gemini 키가 없으면 `gemini=None`

- [ ] **Step 1: 실패하는 테스트 작성** (시계·클라이언트는 가짜)

```python
# tests/test_ttl_cache.py
def test_returns_cached_within_ttl():        # t=0 set, t=59 → factory 호출 1회
def test_recomputes_after_ttl():             # ttl=60, t=60 → factory 호출 2회
def test_exceptions_are_not_cached():        # 1회차 ValueError → 2회차 정상값 반환, len == 1
def test_evicts_expired_then_oldest():       # max_entries=2: a(ttl 10), b(ttl 100), t=20에 c → a 삭제 / 이어서 d → b 삭제

# tests/test_service.py
def test_recommend_calls_gemini_and_quota_once_for_same_query():
def test_recommend_cache_hit_ignores_full_quota():
    # quota(rpm=1): 첫 호출 성공 → 같은 문장 재호출도 성공(RateLimitExceeded 없음), 다른 문장은 RateLimitExceeded("rpm")
def test_recommend_uses_cached_search():     # 같은 추천 두 번 → tmdb.search 호출 횟수 변화 없음
def test_trending_genres_detail_cached():    # 각각 두 번 호출 → TMDB 가짜 클라이언트 호출 1회씩
def test_recommend_without_gemini_raises_config_error(): # can_recommend False, ConfigError
def test_build_service():                    # TMDB 키 없음 → None / Gemini 키 없음 → can_recommend False
```

- [ ] **Step 2: 실패 확인** — Run: `pytest tests/test_ttl_cache.py tests/test_service.py -v` / Expected: ImportError
- [ ] **Step 3: 구현** (Interfaces 그대로. Streamlit `app.py`는 건드리지 않는다)
- [ ] **Step 4: 통과 확인** — Run: `pytest -v` / Expected: 전체 PASS (기존 테스트 포함)
- [ ] **Step 5: Commit** — `git commit -m "feat: framework-free service layer with TTL cache and quota"`

---

### Task 2: 화면용 데이터 (`core/presenter.py`)

**Files:**
- Create: `core/presenter.py`
- Test: `tests/test_presenter.py`

**Interfaces:**
- Consumes: `MediaItem`, `MediaDetail`, `RecommendedItem`, `image_url` (기존)
- Produces:
  - `NO_OVERVIEW = "한국어 줄거리가 등록되지 않았어요"`
  - `@dataclass CardVM`: `key: str = "", tmdb_id: int = 0, media_type: str = "", title: str = "", meta: str = "", poster_url: str = "", reason: str = "", rank: int = 0, clickable: bool = False` (일반 dataclass, frozen 아님 — Reflex 상태 값으로 쓰기 때문)
  - `@dataclass HeroVM`: `tmdb_id: int = 0, media_type: str = "", title: str = "", meta: str = "", backdrop_url: str = "", reason: str = ""`
  - `@dataclass DetailVM`: `title, original_title, meta, overview, poster_url, backdrop_url, reason, trailer_embed_url` (모두 `str = ""`)
  - `meta_line(year: int | None, vote_average: float, *, genres: Sequence[str] = (), extra: Sequence[str] = ()) -> str` — 순서: 장르(최대 2개) · 연도 · extra · `★{평점:.1f}`, 구분자 `" · "`
  - `genre_names(media: MediaItem, genre_map: dict[int, str]) -> list[str]` — 최대 2개, 순서 유지
  - `trending_cards(items: Sequence[MediaItem], key: str, *, ranked: bool, limit: int = 10) -> list[CardVM]` — `rank`는 ranked면 1부터, 아니면 0. `clickable=True`
  - `recommended_cards(items: Sequence[RecommendedItem]) -> list[CardVM]` — 제목은 `media.title`(미확인이면 `rec.title_ko`), `reason = rec.reason`, 미확인이면 `meta=""`, `poster_url=""`, `clickable=False`
  - `hero_view(item: RecommendedItem, genre_map: dict[int, str]) -> HeroVM` — 제목은 `rec.title_ko`, meta에 장르 포함, 배경 `w1280` backdrop → 없으면 `w780` poster → 없으면 `""`
  - `detail_view(detail: MediaDetail, reason: str = "") -> DetailVM` — extra: 영화 `"{runtime}분"`, TV `"시즌 {n}개"`. 장르는 `detail.genres[:2]`. 예고편 `https://www.youtube.com/embed/{key}`. 원제가 제목과 같으면 `original_title=""`
  - `card_key(prefix: str, media: MediaItem) -> str` — `f"{prefix}-{media.media_type}-{media.tmdb_id}"` (`trending_cards`·`recommended_cards`가 `CardVM.key`에 사용)

- [ ] **Step 1: 실패하는 테스트 작성**

```python
def test_meta_line_formats():
    assert meta_line(2019, 8.53, genres=["드라마", "스릴러", "코미디"]) == "드라마 · 스릴러 · 2019 · ★8.5"
    assert meta_line(None, 7.0) == "★7.0"
    assert meta_line(2020, 6.0, extra=["132분"]) == "2020 · 132분 · ★6.0"
def test_trending_cards_rank_and_limit():   # 12개 → 10개, ranked=True면 rank 1..10, False면 전부 0
def test_recommended_card_unmatched():      # media None → clickable False, poster_url "", meta "", title == rec.title_ko
def test_hero_view_image_fallback():        # backdrop 있음 → .../w1280/..., 없음 → .../w780/poster, 둘 다 없음 → ""
def test_detail_view_movie_and_tv():        # 영화 runtime 132 → meta에 "132분", TV seasons 3 → "시즌 3개"
def test_detail_view_trailer_and_overview(): # trailer_key "abc" → "https://www.youtube.com/embed/abc", 없음 → "" / overview "" → NO_OVERVIEW
def test_detail_view_hides_same_original_title():
```

- [ ] **Step 2: 실패 확인** — Run: `pytest tests/test_presenter.py -v` / Expected: ImportError
- [ ] **Step 3: 구현** (Interfaces 그대로)
- [ ] **Step 4: 통과 확인** — Run: `pytest -v` / Expected: 전체 PASS
- [ ] **Step 5: Commit** — `git commit -m "feat: presenter view models for UI layer"`

---

### Task 3: Reflex 뼈대 + 트렌딩

**Files:**
- Create: `rxconfig.py`, `mood_cinema/__init__.py`, `mood_cinema/mood_cinema.py`, `mood_cinema/styles.py`, `mood_cinema/state.py`, `mood_cinema/components/__init__.py`, `mood_cinema/components/header.py`, `mood_cinema/components/card.py`, `mood_cinema/components/trending.py`, `mood_cinema/components/footer.py`
- Modify: `requirements.txt` (+ `reflex==0.10.0`, streamlit은 Task 5에서 제거), `.gitignore` (+ `.web/`, `.states/`)

**Interfaces:**
- Consumes: `build_service`, `MoodService` (Task 1), `CardVM`, `trending_cards`, `filter_by_genre` (Task 2, 기존), `load_settings`
- Produces:
  - `rxconfig.py`: `config = rx.Config(app_name="mood_cinema")`
  - `mood_cinema/state.py`:
    - 모듈 import 시 `load_dotenv(find_dotenv(usecwd=True))`
    - `get_service() -> MoodService | None` — `functools.cache`로 프로세스당 1개. `ConfigError`는 그대로 전파
    - `class State(rx.State)`: `missing_keys: list[str] = []`, `config_error: str = ""`, 이벤트 `check_setup()`
    - `class TrendingState(State)`: `media_label: str = "전체"`, `genre: str = "드라마"`, `genre_options: list[str] = []`, `day: list[CardVM] = []`, `week: list[CardVM] = []`, `genre_pick: list[CardVM] = []`, `loading: bool = False`, `error: str = ""`; 백엔드 전용 `_week_items: list[MediaItem] = []`, `_genre_map: dict[int, str] = {}`; 이벤트 `load()`(background), `set_media(label: str)`(값 저장 후 `load` 재실행), `set_genre(name: str)`(API 호출 없이 `_week_items`에서 다시 거름)
  - `mood_cinema/components/card.py`: `poster_card(card: CardVM Var, *, show_reason: bool = False) -> rx.Component` — `rx.cond(card.clickable, 클릭되는 카드, 정적 카드)`로 두 갈래를 만든다(이벤트를 조건부로 붙이지 않는다). 클릭 시 호출할 이벤트는 Task 5 전까지 없으므로 인자 `on_open: Callable[[CardVM Var], EventSpec] | None = None`으로 받는다
  - `mood_cinema/components/trending.py`: `trending_section() -> rx.Component`, 내부 `poster_row(title: str, cards: Var[list[CardVM]], *, ranked: bool)` — `rx.box(overflow_x="auto", scroll_snap_type="x mandatory")` 안에 `rx.hstack(rx.foreach(...))`
  - `mood_cinema/mood_cinema.py`: `app = rx.App(theme=rx.theme(appearance="dark", accent_color="amber", radius="large"), style=...)`, `app.add_page(index, title="Mood Cinema", on_load=[State.check_setup, TrendingState.load])`

- [ ] **Step 1: Reflex 실행 확인용 최소 앱** — `rxconfig.py`와 "Mood Cinema" 제목만 있는 `index`를 만들고 Run: `reflex run` / Expected: http://localhost:3000 에 제목 표시. `reflex init`을 요구하면 실행하되, 끝난 뒤 `git status`로 우리 파일이 덮어써지지 않았는지 확인한다 (폴더 이름에 `-`가 있어 앱 이름은 반드시 `rxconfig.py`의 `mood_cinema`). `mood_cinema/*.py`에서 `from core...` import가 되는지도 여기서 확인
- [ ] **Step 2: 디자인 토큰 `styles.py`** — 스펙 9.1의 색·그라데이션·글꼴·간격·포스터 비율·호버 스타일을 상수로 (`BG`, `SURFACE`, `TEXT`, `MUTED`, `ACCENT`, `REASON_BG`, `HERO_GRADIENT`, `FONT_FAMILY`, `CARD_HOVER` 등)
- [ ] **Step 3: State·컴포넌트 구현** — 상단 바(로고 + "AI 추천"/"트렌딩" 앵커, `position: sticky`, 반투명 배경 + `backdrop-filter: blur`), 트렌딩 세 줄(오늘·이번 주는 순위 배지, 장르 픽 제목 옆 `rx.select`), 종류 `rx.segmented_control`, 로딩 중 카드 모양 `rx.skeleton` 6개, 오류 `rx.callout`(빨강, "인기 작품을 불러오지 못했어요"), 장르 픽 0개 문구, 키 없음 안내(`missing_keys`), Credits(`Path("assets/tmdb_logo.svg").exists()`일 때만 로고). 빠른 전환 대응: `load()` 시작 시 `media_label`을 기억하고, 결과를 쓰기 직전 `async with self:` 안에서 현재 값과 다르면 버린다
- [ ] **Step 4: 키 노출 점검** — Run: `grep -rn "api_key\|_client\|MoodService" mood_cinema/` / Expected: `state.py`의 `get_service` 정의·호출 외에는 없음, State 클래스 변수에는 없음
- [ ] **Step 5: 빌드 확인** — Run: `reflex export --frontend-only --no-zip` / Expected: 오류 없이 종료
- [ ] **Step 6: 테스트** — Run: `pytest -v` / Expected: 전체 PASS
- [ ] **Step 7: 화면 확인** (`reflex run`) — 세 줄이 가로 스크롤되는지, 카드 호버 확대·앰버 테두리, 종류를 전체→영화→TV로 빠르게 바꿔도 마지막 선택 결과만 남는지, 모바일 폭(375px)에서 카드 120px
- [ ] **Step 8: Commit** — `git commit -m "feat: Reflex app shell with themed trending rows"`

---

### Task 4: AI 추천 (입력, 히어로, 카드)

**Files:**
- Create: `mood_cinema/components/recommend.py`
- Modify: `mood_cinema/state.py` (RecommendState 추가), `mood_cinema/mood_cinema.py` (섹션 배치)

**Interfaces:**
- Consumes: `MoodService.recommend`, `genres` (Task 1), `hero_view`, `recommended_cards`, `HeroVM`, `CardVM` (Task 2), `validate_query`, `check_cooldown`, 예외들 (기존), `poster_card` (Task 3)
- Produces:
  - `EXAMPLES = ["비 오는 날 혼자 보기 좋은 몰입감 있는 스릴러", "야근 끝나고 머리 비우고 싶을 때 볼 가벼운 코미디", "주말에 정주행할 감동적인 가족 드라마"]` (칩에는 짧은 이름: "비 오는 날 스릴러", "야근 후 코미디", "주말 가족 드라마")
  - `class RecommendState(State)`: `query: str = ""`, `loading: bool = False`, `warning: str = ""`, `error: str = ""`, `can_retry: bool = False`, `has_hero: bool = False`, `hero: HeroVM = HeroVM()`, `cards: list[CardVM] = []`; 백엔드 전용 `_last_recommend_at: float | None = None`, `_last_query: str = ""`
    - `set_query(text: str)`, `use_example(text: str)` (입력창만 채움)
    - `submit()` (background): `loading`이면 즉시 return → `validate_query` → `check_cooldown(_last_recommend_at, time.time(), cooldown)` → `_last_recommend_at` 갱신 → `loading=True` → `await asyncio.to_thread(service.recommend, q)` → `hero_view`/`recommended_cards`로 저장 → `loading=False`
    - `retry()`: `_last_query`로 `submit`과 같은 흐름 (쿨다운 적용)
    - 예외 → 문구는 스펙 7장 그대로: `ValueError` → `warning=str(e)`, cooldown → `f"{ceil(sec)}초 후에 다시 추천받을 수 있어요"`, rpm/daily → `"지금 요청이 많아요. 잠시 후 다시 시도해 주세요"`, `GeminiFormatError` → `error="추천 결과를 읽지 못했어요"`, `can_retry=True`, `GeminiError` → `warning="AI 추천을 불러오지 못했어요. 잠시 후 다시 시도해 주세요"`. 새 요청을 시작할 때 세 메시지와 `can_retry`를 비운다. 상세 오류는 `logging.exception`
  - `recommend.py`: `recommend_section()`, 내부 `hero_banner(hero: Var[HeroVM])`, `reason_box(reason: Var[str])`(스펙 4.0), `example_chips()`

- [ ] **Step 1: State 구현** (위 순서대로. Gemini 키가 없으면 섹션 전체를 숨기고 `missing_keys` 안내만)
- [ ] **Step 2: 컴포넌트 구현** — 스펙 9.2 레이아웃: 큰 질문 제목 "오늘 기분은 어떤가요?", 2줄 입력창 + "추천받기"(`loading=RecommendState.loading`), 예시 칩, 히어로 배너(배경 이미지 `background_image` + `HERO_GRADIENT` 겹침, 데스크톱 최소 높이 440px, 768px 미만에서 세로 배치 — 반응형 값은 Reflex의 breakpoint 리스트 문법 사용), "AI PICK" 라벨, 이유 박스, "상세 보기"(Task 5 전까지 `on_click` 없음), 2~5순위 카드(`poster_card(..., show_reason=True)`, 이유 3줄 말줄임), 로딩 중 히어로 자리 skeleton + "기분에 맞는 작품을 찾고 있어요...", 메시지 `rx.callout`(경고 앰버, 오류 빨강), `can_retry`면 "다시 시도" 버튼
- [ ] **Step 3: 빌드 확인** — Run: `reflex export --frontend-only --no-zip` / Expected: 오류 없음
- [ ] **Step 4: 테스트** — Run: `pytest -v` / Expected: 전체 PASS
- [ ] **Step 5: 키 노출 점검** — Task 3 Step 4와 같은 명령, 같은 기대 결과
- [ ] **Step 6: 화면 확인** (`reflex run`, 실제 키) — 한글을 빠르게 입력해도 글자 중복·누락 없음(Review Focus 1), 로딩 중 버튼 연타 시 요청 1번(서버 로그로 확인), 히어로 그라데이션 위 글자 대비, 같은 문장 재요청 시 즉시 응답, 10초 안 재요청 시 쿨다운 문구, 빈 입력 시 안내 문구
- [ ] **Step 7: Commit** — `git commit -m "feat: AI recommendation with hero banner and reason box"`

---

### Task 5: 상세 팝업 + Streamlit 제거 + 문서

**Files:**
- Create: `mood_cinema/components/detail_dialog.py`
- Modify: `mood_cinema/state.py` (DetailState), `mood_cinema/components/card.py`, `trending.py`, `recommend.py` (클릭 연결), `requirements.txt`, `README.md`, `CLAUDE.md`
- Delete: `app.py`, `.streamlit/`, `tests/test_app_smoke.py`

**Interfaces:**
- Consumes: `MoodService.detail` (Task 1), `detail_view`, `DetailVM` (Task 2)
- Produces:
  - `class DetailState(State)`: `open: bool = False`, `loading: bool = False`, `error: str = ""`, `view: DetailVM = DetailVM()`; 이벤트 `open_detail(media_type: str, tmdb_id: int, reason: str)` (background: 열면서 `view=DetailVM()`, `loading=True`, `error=""` → `to_thread(service.detail, ...)` → `detail_view(detail, reason)`; `TmdbError`면 `error="상세 정보를 불러오지 못했어요"`), `set_open(value: bool)`
  - `detail_dialog.py`: `detail_dialog()` — `rx.dialog.root(open=DetailState.open, on_open_change=DetailState.set_open)`. 페이지에 한 번만 둔다
  - 연결: `poster_card(on_open=lambda c: DetailState.open_detail(c.media_type, c.tmdb_id, c.reason))`, 히어로 "상세 보기"도 같은 이벤트

- [ ] **Step 1: DetailState + 팝업 구현** — 스펙 F3 출력 순서: 위쪽 배경(w1280) + 아래로 어두워지는 그라데이션, 겹친 포스터(w342) 옆 제목/원제, meta, 이유 박스(`view.reason`이 있을 때), 줄거리, 예고편 16:9 `rx.el.iframe(src=view.trailer_embed_url)`(`trailer_embed_url`이 있을 때), 로딩 skeleton, 오류 callout, 닫기 버튼. 최대 폭 860px
- [ ] **Step 2: Streamlit 제거** — `app.py`, `.streamlit/`, `tests/test_app_smoke.py` 삭제, `requirements.txt`에서 `streamlit` 삭제. Run: `grep -rn "streamlit" --include=*.py .` / Expected: 출력 없음
- [ ] **Step 3: 빌드·테스트** — Run: `reflex export --frontend-only --no-zip && pytest -v` / Expected: 둘 다 성공
- [ ] **Step 4: 문서 갱신** — README: 소개 문구의 "Streamlit" → "Reflex", 아키텍처 그림(스펙 3.1), 실행(`reflex run`), 테스트, 배포(스펙 11), 설계 결정에 "Streamlit → Reflex 전환 이유"와 "서비스·프레젠터 계층 분리" 추가, 한계(스펙 6.2), 스크린샷 자리(`docs/images/`). CLAUDE.md: 명령어를 `reflex run`으로, 규칙에 "State에 키·클라이언트 넣지 않기"
- [ ] **Step 5: 화면 확인** (`reflex run`) — 트렌딩 카드·추천 카드·히어로 버튼에서 팝업이 열리는지, A를 본 뒤 B가 실패하면 A 내용이 남지 않는지(Review Focus 5), 예고편 재생, ESC·바깥 클릭·닫기 버튼으로 닫힘
- [ ] **Step 6: Commit** — `git commit -m "feat: detail dialog, remove Streamlit, update docs"`
- [ ] **Step 7: 배포 (사용자 계정 필요)** — `main` 머지 후 `reflex login` → `reflex deploy --app-name mood-cinema --envfile .env`. 스펙 11장 확인 목록 점검

---

## Self-Review 결과

- 스펙 대응: 3장 구조 → T1~T5, 4장 F1 → T3, F2·4.0 → T4, F3 → T5, F4 → T3, 6.1 → T1, 6.2 쿨다운 → T4·한도 → T1, 7장 → T3·T4·T5, 8장 → T3(`get_service`, dotenv)·T5, 9장 → T3~T5, 10장 → T1·T2 + 각 Task 빌드·화면 확인, 11장 → T5 Step 7, 12장 R1~R5 → T1~T5
- 이름 일관성: `CardVM`·`HeroVM`·`DetailVM` 필드명 T2 정의 = T3~T5 사용, `MoodService.recommend(query)`는 정리된 문장을 받는다(T1) = T4에서 `validate_query` 후 호출
- Reflex 컴포넌트 이름·인자(0.10)는 실제 설치본으로 각 Task 빌드 단계에서 확인한다 — 계획과 다르면 Global Constraints 첫 줄 규칙대로 처리
