import reflex as rx

from mood_cinema import styles
from mood_cinema.components.card import poster_card
from mood_cinema.state import MEDIA_TYPES, TrendingState


def _skeleton_row() -> rx.Component:
    return rx.hstack(
        *[
            rx.skeleton(rx.box(width=styles.CARD_WIDTH, aspect_ratio=styles.POSTER_RATIO), loading=True)
            for _ in range(6)
        ],
        spacing="3",
        overflow="hidden",
        width="100%",
    )


def _rank_badge(card) -> rx.Component:
    return rx.badge(
        card.rank,
        variant="solid",
        size="2",
        position="absolute",
        top="6px",
        left="6px",
        z_index="1",
        style={"font_weight": "700", "box_shadow": "0 2px 6px rgba(0,0,0,0.5)"},
    )


def _row_item(card, ranked: bool) -> rx.Component:
    children = [poster_card(card)]
    if ranked:  # 오늘·이번 주 줄만 포스터 왼쪽 위에 순위 숫자
        children.append(_rank_badge(card))
    return rx.box(*children, position="relative", flex_shrink="0", scroll_snap_align="start")


def poster_row(title: str, cards, *, ranked: bool, extra: rx.Component | None = None) -> rx.Component:
    return rx.vstack(
        rx.hstack(rx.heading(title, size="5"), *([extra] if extra else []), align="center", spacing="3"),
        rx.cond(
            TrendingState.loading,
            _skeleton_row(),
            rx.box(
                rx.hstack(rx.foreach(cards, lambda c: _row_item(c, ranked)), spacing="3", padding="6px 4px 12px"),
                overflow_x="auto",
                scroll_snap_type="x mandatory",
                width="100%",
            ),
        ),
        spacing="2",
        width="100%",
    )


def _genre_select() -> rx.Component:
    return rx.select(
        TrendingState.genre_options,
        value=TrendingState.genre,
        on_change=TrendingState.set_genre,
        size="1",
    )


def trending_section() -> rx.Component:
    return rx.vstack(
        rx.hstack(
            rx.heading("트렌딩", size="7"),
            rx.spacer(),
            rx.segmented_control.root(
                *[rx.segmented_control.item(label, value=label) for label in MEDIA_TYPES],
                value=TrendingState.media_label,
                on_change=TrendingState.set_media,
            ),
            width="100%",
            align="center",
        ),
        rx.cond(
            TrendingState.error != "",
            rx.callout(TrendingState.error, icon="triangle_alert", color_scheme="red", width="100%"),
            rx.vstack(
                poster_row("오늘의 인기", TrendingState.day, ranked=True),
                poster_row("이번 주 인기", TrendingState.week, ranked=True),
                rx.cond(
                    ~TrendingState.loading & (TrendingState.genre_pick.length() == 0),
                    rx.vstack(
                        rx.hstack(rx.heading("장르 픽", size="5"), _genre_select(), align="center", spacing="3"),
                        rx.text("이번 주 인기작 중 이 장르가 없어요", color=styles.MUTED, size="2"),
                        spacing="2",
                        width="100%",
                    ),
                    poster_row("장르 픽", TrendingState.genre_pick, ranked=False, extra=_genre_select()),
                ),
                spacing="6",
                width="100%",
            ),
        ),
        id="trending",
        spacing="5",
        width="100%",
        scroll_margin_top="72px",
    )
