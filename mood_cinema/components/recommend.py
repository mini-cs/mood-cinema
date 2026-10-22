import reflex as rx

from mood_cinema import styles
from mood_cinema.components.card import poster_card
from mood_cinema.state import DetailState, RecommendState

EXAMPLES = [
    "비 오는 날 혼자 보기 좋은 몰입감 있는 스릴러",
    "야근 끝나고 머리 비우고 싶을 때 볼 가벼운 코미디",
    "주말에 정주행할 감동적인 가족 드라마",
]
CHIP_LABELS = ["비 오는 날 스릴러", "야근 후 코미디", "주말 가족 드라마"]


def reason_box(reason) -> rx.Component:
    """스펙 4.0: 앰버 세로줄 + 옅은 앰버 배경."""
    return rx.box(
        rx.text("AI 큐레이터의 한마디", size="1", weight="bold", color=styles.ACCENT),
        rx.text(reason, size="2", color=styles.TEXT, margin_top="4px"),
        border_left=f"3px solid {styles.ACCENT}",
        background_color=styles.REASON_BG,
        padding="12px 16px",
        border_radius="0 8px 8px 0",
        width="100%",
    )


def _hero_text(hero) -> rx.Component:
    return rx.vstack(
        rx.badge("AI PICK", variant="solid", size="1", style={"letter_spacing": "0.08em"}),
        rx.heading(hero.title, size="8", color=styles.TEXT),
        rx.text(hero.meta, size="2", color=styles.MUTED),
        reason_box(hero.reason),
        rx.button(
            "상세 보기",
            size="3",
            variant="soft",
            on_click=DetailState.open_detail(hero.media_type, hero.tmdb_id, hero.reason),
        ),
        spacing="3",
        align="start",
        width="100%",
    )


def hero_banner(hero) -> rx.Component:
    # 데스크톱: 배경 이미지 위에 그라데이션과 글자를 겹친다 / 768px 미만: 이미지 아래로 글자가 내려가는 세로 배치
    desktop = rx.box(
        rx.box(_hero_text(hero), max_width="520px", padding="40px"),
        display=["none", "none", "flex"],
        align_items="flex-end",
        min_height="440px",
        border_radius="16px",
        overflow="hidden",
        background_color=styles.SURFACE,
        background_image=rx.cond(
            hero.backdrop_url != "",
            styles.HERO_GRADIENT + ", url(" + hero.backdrop_url + ")",
            styles.HERO_GRADIENT,
        ),
        background_size="cover",
        background_position="center",
    )
    mobile = rx.vstack(
        rx.cond(
            hero.backdrop_url != "",
            rx.image(src=hero.backdrop_url, alt=hero.title, width="100%", aspect_ratio="16 / 9", object_fit="cover", border_radius="12px"),
        ),
        _hero_text(hero),
        display=["flex", "flex", "none"],
        spacing="4",
        width="100%",
    )
    return rx.box(desktop, mobile, width="100%")


def example_chips() -> rx.Component:
    return rx.hstack(
        *[
            rx.button(label, size="1", variant="soft", radius="full", on_click=RecommendState.use_example(text))
            for label, text in zip(CHIP_LABELS, EXAMPLES)
        ],
        spacing="2",
        wrap="wrap",
    )


def _input_row() -> rx.Component:
    return rx.flex(
        rx.text_area(
            value=RecommendState.query,
            on_change=RecommendState.set_query,
            placeholder=EXAMPLES[0],
            rows="2",
            size="3",
            width="100%",
            resize="none",
        ),
        rx.button(
            "추천받기",
            size="3",
            loading=RecommendState.loading,
            disabled=RecommendState.loading,
            on_click=RecommendState.submit,
        ),
        # Radix 속성은 리스트 대신 rx.breakpoints를 쓴다 (sm = 48em = 768px)
        direction=rx.breakpoints(initial="column", sm="row"),
        spacing="3",
        width="100%",
        align=rx.breakpoints(initial="stretch", sm="center"),
    )


def _messages() -> rx.Component:
    return rx.fragment(
        rx.cond(
            RecommendState.warning != "",
            rx.callout(RecommendState.warning, icon="info", color_scheme="amber", width="100%"),
        ),
        rx.cond(
            RecommendState.error != "",
            rx.hstack(
                rx.callout(RecommendState.error, icon="triangle_alert", color_scheme="red", flex="1"),
                rx.cond(RecommendState.can_retry, rx.button("다시 시도", variant="outline", on_click=RecommendState.retry)),
                width="100%",
                align="center",
            ),
        ),
    )


def _loading_view() -> rx.Component:
    return rx.vstack(
        rx.skeleton(rx.box(width="100%", min_height=["240px", "240px", "440px"]), loading=True, width="100%"),
        rx.text("기분에 맞는 작품을 찾고 있어요...", size="2", color=styles.MUTED),
        width="100%",
        spacing="3",
    )


def _results() -> rx.Component:
    return rx.vstack(
        rx.cond(RecommendState.has_hero, hero_banner(RecommendState.hero)),
        rx.cond(
            RecommendState.cards.length() > 0,
            rx.box(
                rx.hstack(
                    rx.foreach(
                        RecommendState.cards,
                        lambda c: rx.box(
                            poster_card(
                                c,
                                show_reason=True,
                                on_open=lambda card: DetailState.open_detail(card.media_type, card.tmdb_id, card.reason),
                            ),
                            flex_shrink="0",
                        ),
                    ),
                    spacing="4",
                    padding="6px 4px 12px",
                    align="start",
                ),
                overflow_x="auto",
                width="100%",
            ),
        ),
        spacing="5",
        width="100%",
    )


def recommend_section() -> rx.Component:
    return rx.vstack(
        rx.heading("오늘 기분은 어떤가요?", size="8"),
        _input_row(),
        example_chips(),
        _messages(),
        rx.cond(RecommendState.loading, _loading_view(), _results()),
        id="recommend",
        spacing="4",
        width="100%",
        scroll_margin_top="72px",
    )
