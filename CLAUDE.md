# Mood Cinema

기분·상황 문장 → Gemini가 작품 추천 → TMDB 실제 데이터로 보강해 보여주는 웹 앱 (개인 포트폴리오).
v0.2(Streamlit)를 거쳐 v0.3에서 화면을 **Reflex**로 바꿨다. Streamlit 코드(`app.py`, `.streamlit/`)는 삭제했다.

## 먼저 읽을 문서

- 설계 문서 (v0.3): `docs/specs/2026-10-22-mood-cinema-design.md`
- 완료된 계획 (Reflex 전환, Task 1~5): `docs/plans/2026-10-22-mood-cinema-reflex.md`
- 완료된 계획 (Streamlit, Task 1~6): `docs/plans/2026-10-22-mood-cinema.md`

## 작업 규칙

- Reflex 전환 계획의 Task를 **한 번에 하나씩, 번호 순서대로** 진행한다.
- 각 Task는 테스트 작성 → 실패 확인 → 구현 → 통과 확인 → 커밋 순서를 지킨다. 화면 Task는 빌드 확인(`reflex export --frontend-only --no-zip`)과 화면 확인 목록까지 끝낸다.
- 계획의 Interfaces(함수 이름, 인자, 반환 타입)는 바꾸지 않는다. 바꿔야 하면 먼저 사용자에게 묻는다.
- Reflex는 `0.10.0` 고정. 실제 API가 계획과 다르면 공식 문서(0.10)를 따르고, 바꾼 점을 커밋 메시지에 적는다.
- `core/` 안에서는 streamlit도 reflex도 import하지 않는다.
- **API 키, API 클라이언트, `MoodService`를 Reflex State 변수에 넣지 않는다.** State 변수는 브라우저로 전송된다. 서비스는 `mood_cinema/state.py`의 `get_service()`로만 꺼낸다.
- 오래 걸리는 호출(Gemini·TMDB)은 `@rx.event(background=True)` + `asyncio.to_thread()`로 실행하고, 상태 변경은 `async with self:` 안에서만 한다.
- API 키를 코드, 로그, 에러 메시지, 커밋 어디에도 넣지 않는다. `.env`는 커밋하지 않는다.
- 테스트는 실제 API를 호출하지 않는다 (가짜 응답 사용).
- 화면 문구는 한국어로 쓰고, 에러 문구는 설계 문서 7장 표 그대로 쓴다. 색·간격은 설계 문서 9.1 디자인 토큰(`mood_cinema/styles.py`)만 쓴다.
- Gemini 모델 기본값은 `gemini-3.5-flash-lite`다. Gemini 2.0 계열은 종료되었으니 쓰지 않는다.
- 사용자는 개발을 배우는 중이다. Task를 끝낼 때마다 무엇을 만들었는지 쉬운 말로 2~3줄 요약한다.

## 브랜치 전략 (기능별 브랜치)

- `main`에는 테스트와 빌드가 통과한 코드만 합친다.
- Task 하나 = 브랜치 하나. 앞 Task를 `main`에 합친 뒤, 최신 `main`에서 다음 브랜치를 만든다.

| Reflex Task | 브랜치 |
|---|---|
| 1 | `feat/07-service-layer` |
| 2 | `feat/08-presenter` |
| 3 | `feat/09-reflex-trending` |
| 4 | `feat/10-reflex-recommend` |
| 5 | `feat/11-reflex-detail-cleanup` |

Task마다 반복하는 순서:

```bash
git switch main
git pull
git switch -c feat/07-service-layer       # Task 번호에 맞는 브랜치
# ... 계획대로 구현, pytest -v 전체 통과 (Task 3부터 reflex export 빌드도 통과), 계획의 커밋 메시지로 커밋 ...
git push -u origin feat/07-service-layer  # → GitHub에서 PR 만들고 main에 머지
```

- 다른 Task의 파일은 그 브랜치에서 고치지 않는다. 꼭 필요하면 사용자에게 먼저 알린다.

## 명령어 (Windows 기준)

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
pytest -v
reflex run                                # http://localhost:3000
reflex export --frontend-only --no-zip    # 화면 코드 빌드 확인
```
