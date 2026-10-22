import reflex as rx

from mood_cinema import styles
from mood_cinema.components.footer import footer
from mood_cinema.components.header import header
from mood_cinema.components.trending import trending_section
from mood_cinema.state import State, TrendingState


def setup_notice() -> rx.Component:
    return rx.fragment(
        rx.cond(
            State.config_error != "",
            rx.callout(State.config_error, icon="triangle_alert", color_scheme="red", width="100%"),
        ),
        rx.cond(
            State.missing_keys.length() > 0,
            rx.callout(
                rx.text(
                    "API 키가 설정되지 않았어요: ",
                    State.missing_keys.join(", "),
                    ". 설정 방법: .env에 TMDB_API_KEY / GEMINI_API_KEY 를 등록하세요 (.env.example을 복사해 .env로 만들면 됩니다).",
                ),
                icon="info",
                width="100%",
            ),
        ),
    )


def index() -> rx.Component:
    return rx.box(
        header(),
        rx.vstack(
            setup_notice(),
            # TMDB 키가 없으면 트렌딩을 숨긴다
            rx.cond(State.missing_keys.contains("TMDB_API_KEY"), rx.fragment(), trending_section()),
            footer(),
            spacing="9",
            width="100%",
            max_width="1400px",
            margin_x="auto",
            padding_x=styles.PAGE_PADDING_X,
            padding_top="32px",
        ),
        background_color=styles.BG,
        color=styles.TEXT,
        min_height="100vh",
        font_family=styles.FONT_FAMILY,
    )


app = rx.App(style={"font_family": styles.FONT_FAMILY, "background_color": styles.BG})  # 테마는 rxconfig.py
app.add_page(index, title="Mood Cinema", on_load=[State.check_setup, TrendingState.load])
