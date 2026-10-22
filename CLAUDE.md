# Mood Cinema

기분·상황 문장 → Gemini가 작품 추천 → TMDB 실제 데이터로 보강해 보여주는 Streamlit 웹 앱 (개인 포트폴리오)

## 먼저 읽을 문서

- 설계 문서 (v0.2, 승인됨): `docs/specs/2026-10-22-mood-cinema-design.md`
- 구현 계획 (Task 1~6): `docs/plans/2026-10-22-mood-cinema.md`

## 작업 규칙

- 구현 계획의 Task를 **한 번에 하나씩, 번호 순서대로** 진행한다.
- 각 Task는 테스트 작성 → 실패 확인 → 구현 → 통과 확인 → 커밋 순서를 지킨다.
- 계획의 Interfaces(함수 이름, 인자, 반환 타입)는 바꾸지 않는다. 바꿔야 하면 먼저 사용자에게 묻는다.
- `core/` 안에서는 streamlit을 import하지 않는다.
- API 키를 코드, 로그, 에러 메시지, 커밋 어디에도 넣지 않는다. `.env`, `.streamlit/secrets.toml`은 커밋하지 않는다.
- 테스트는 실제 API를 호출하지 않는다 (가짜 응답 사용).
- 화면 문구는 한국어로 쓰고, 에러 문구는 설계 문서 7장 표 그대로 쓴다.
- Gemini 모델 기본값은 `gemini-3.5-flash-lite`다. Gemini 2.0 계열은 종료되었으니 쓰지 않는다.
- 사용자는 개발을 배우는 중이다. Task를 끝낼 때마다 무엇을 만들었는지 쉬운 말로 2~3줄 요약한다.

## 브랜치 전략 (기능별 브랜치)

- `main`에는 테스트가 통과한 코드만 합친다. 설계·계획 문서는 이미 `main`에 있다.
- Task 하나 = 브랜치 하나. 앞 Task를 `main`에 합친 뒤, 최신 `main`에서 다음 브랜치를 만든다 (Task들이 앞 Task의 코드를 이어 쓰기 때문).

| Task | 브랜치 |
|---|---|
| 1 | `feat/01-scaffold-config` |
| 2 | `feat/02-rate-limit` |
| 3 | `feat/03-tmdb-client` |
| 4 | `feat/04-gemini-client` |
| 5 | `feat/05-recommender` |
| 6 | `feat/06-streamlit-ui` |

Task마다 반복하는 순서:

```bash
git switch main
git pull                                  # GitHub 원격 저장소를 연결한 경우
git switch -c feat/01-scaffold-config     # Task 번호에 맞는 브랜치
# ... 계획대로 구현, pytest -v 전체 통과, 계획의 커밋 메시지로 커밋 ...
git push -u origin feat/01-scaffold-config  # → GitHub에서 PR 만들고 main에 머지
# 원격 없이 로컬로만 할 때:
git switch main
git merge --no-ff feat/01-scaffold-config
git branch -d feat/01-scaffold-config
```

- 브랜치를 `main`에 합치기 전에 반드시 `pytest -v`가 전부 통과해야 한다.
- 다른 Task의 파일은 그 브랜치에서 고치지 않는다. 꼭 필요하면 사용자에게 먼저 알린다.

## 명령어 (Windows 기준)

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt   # Task 1에서 만들어짐
pytest -v
streamlit run app.py
```
