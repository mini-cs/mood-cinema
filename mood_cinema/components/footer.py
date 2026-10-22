from pathlib import Path

import reflex as rx

from mood_cinema import styles

TMDB_LOGO = Path(__file__).resolve().parents[2] / "assets" / "tmdb_logo.svg"
TMDB_NOTICE = "This product uses the TMDB API but is not endorsed or certified by TMDB."
GEMINI_NOTICE = "추천 기능은 Google Gemini API 무료 티어를 사용하며, 입력 내용이 Google 제품 개선에 활용될 수 있습니다."


def footer() -> rx.Component:
    return rx.vstack(
        rx.divider(),
        rx.text("Credits", size="1", weight="bold", color=styles.MUTED),
        # 로고 파일은 사용자가 내려받아 넣는다. 없으면 고지문만 (Reflex는 assets/를 "/"로 제공)
        *([rx.image(src="/tmdb_logo.svg", height="16px", alt="TMDB")] if TMDB_LOGO.exists() else []),
        rx.text(TMDB_NOTICE, size="1", color=styles.MUTED),
        rx.text(GEMINI_NOTICE, size="1", color=styles.MUTED),
        spacing="2",
        width="100%",
        padding_bottom="32px",
    )
