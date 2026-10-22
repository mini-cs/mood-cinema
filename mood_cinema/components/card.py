from collections.abc import Callable

import reflex as rx

from mood_cinema import styles


def _poster(card) -> rx.Component:
    return rx.cond(
        card.poster_url != "",
        rx.image(
            src=card.poster_url,
            alt=card.title,
            width="100%",
            aspect_ratio=styles.POSTER_RATIO,
            object_fit="cover",
            border_radius=styles.POSTER_RADIUS,
            loading="lazy",
        ),
        rx.center(
            rx.text("정보 없음", size="2", color=styles.MUTED),
            width="100%",
            aspect_ratio=styles.POSTER_RATIO,
            background_color=styles.SURFACE,
            border_radius=styles.POSTER_RADIUS,
        ),
    )


def _body(card, show_reason: bool) -> rx.Component:
    children = [
        _poster(card),
        # 0.10의 rx.text는 truncate 속성이 적용되지 않아 CSS로 한 줄 말줄임을 건다
        rx.text(card.title, title=card.title, size="2", weight="bold", color=styles.TEXT, width="100%", style=styles.ONE_LINE),
        rx.cond(card.meta != "", rx.text(card.meta, size="1", color=styles.MUTED)),
    ]
    if show_reason:
        children.append(
            rx.text(card.reason, size="1", color=styles.MUTED, style=styles.THREE_LINES)
        )
    return rx.vstack(*children, spacing="1", width="100%", align="start")


def poster_card(card, *, show_reason: bool = False, on_open: Callable | None = None) -> rx.Component:
    """카드 하나. 이벤트를 조건부로 붙일 수 없어서 rx.cond로 '누르는 카드'와 '정적 카드' 두 갈래를 만든다."""
    events = {"on_click": on_open(card)} if on_open else {}
    clickable = rx.box(
        _body(card, show_reason),
        **events,
        cursor="pointer",
        style=styles.CARD_HOVER,
        width=styles.CARD_WIDTH,
    )
    static = rx.box(_body(card, show_reason), width=styles.CARD_WIDTH)
    return rx.cond(card.clickable, clickable, static)
